"""
AI統合の統合テスト

E2E AI分析フロー、複数プロバイダーでの動作、エラーシナリオをテストします。
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.ci_helper.ai.exceptions import APIKeyError, ProviderError, RateLimitError
from src.ci_helper.ai.integration import AIIntegration
from src.ci_helper.ai.models import AnalysisResult, AnalyzeOptions, TokenUsage
from src.ci_helper.cli import cli


class TestAIIntegrationE2E:
    """AI統合のE2Eテスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def sample_log_content(self):
        """サンプルログ内容"""
        return """
STEP: Run tests
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'

FAILURES:
test_user_authentication.py::test_login_with_invalid_credentials FAILED
AssertionError: Expected status code 401, got 200

test_database_connection.py::test_connection_timeout FAILED
TimeoutError: Database connection timed out after 30 seconds
"""

    @pytest.fixture
    def mock_ai_config(self, temp_dir):
        """モックAI設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        provider_config = ProviderConfig(
            name="openai",
            api_key="sk-test-key-123",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
        )

        return AIConfig(
            default_provider="openai",
            providers={"openai": provider_config},
            cache_enabled=True,
            cost_limits={"monthly_usd": 50.0},
            cache_dir=str(temp_dir / "cache"),
        )

    @pytest.fixture
    def sample_analysis_result(self):
        """サンプル分析結果"""
        from ci_helper.ai.models import FixSuggestion, Priority, RootCause, Severity

        return AnalysisResult(
            summary="複数のエラーが検出されました",
            root_causes=[
                RootCause(
                    category="dependency",
                    description="package.jsonが見つかりません",
                    file_path="package.json",
                    severity=Severity.HIGH,
                ),
                RootCause(
                    category="test",
                    description="認証テストが失敗しています",
                    file_path="test_user_authentication.py",
                    line_number=42,
                    severity=Severity.MEDIUM,
                ),
            ],
            fix_suggestions=[
                FixSuggestion(
                    title="package.jsonの作成",
                    description="プロジェクトルートにpackage.jsonを作成してください",
                    priority=Priority.HIGH,
                    estimated_effort="5分",
                    confidence=0.9,
                )
            ],
            related_errors=["ENOENT", "AssertionError", "TimeoutError"],
            confidence_score=0.85,
            analysis_time=2.5,
            tokens_used=TokenUsage(input_tokens=500, output_tokens=300, total_tokens=800, estimated_cost=0.01),
            provider="openai",
            model="gpt-4o",
        )

    @pytest.mark.asyncio
    async def test_full_ai_analysis_workflow(
        self, temp_dir, mock_ai_config, sample_log_content, sample_analysis_result
    ):
        """完全なAI分析ワークフローのテスト"""
        # ログファイルを作成
        log_file = temp_dir / "test.log"
        log_file.write_text(sample_log_content, encoding="utf-8")

        # AI統合を初期化
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                # OpenAIクライアントのモック
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                from dataclasses import asdict

                # Convert enums to strings for JSON serialization
                def convert_enums(obj):
                    if hasattr(obj, "value"):
                        return obj.value
                    elif isinstance(obj, dict):
                        return {k: convert_enums(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_enums(item) for item in obj]
                    else:
                        return obj

                result_dict = asdict(sample_analysis_result)
                serializable_dict = convert_enums(result_dict)
                mock_response.choices[0].message.content = json.dumps(serializable_dict)
                mock_response.usage.prompt_tokens = 500
                mock_response.usage.completion_tokens = 300
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                # AI統合を実行
                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                result = await ai_integration.analyze_log(sample_log_content, options)

                # 結果の検証
                assert isinstance(result, AnalysisResult)
                assert result.provider == "openai"
                assert result.model == "gpt-4o"
                assert result.tokens_used.input_tokens > 0
                assert result.tokens_used.output_tokens > 0

    @pytest.mark.asyncio
    async def test_multiple_providers_comparison(self, mock_ai_config, sample_log_content):
        """複数プロバイダーでの動作比較テスト"""
        # OpenAIとAnthropicの設定を追加
        from src.ci_helper.ai.models import ProviderConfig

        anthropic_config = ProviderConfig(
            name="anthropic",
            api_key="sk-ant-test-key-123",
            default_model="claude-3-5-sonnet-20241022",
            available_models=["claude-3-5-sonnet-20241022"],
        )
        mock_ai_config.providers["anthropic"] = anthropic_config

        providers_to_test = ["openai", "anthropic"]
        results = {}

        for provider in providers_to_test:
            with patch(
                f"src.ci_helper.ai.providers.{provider}.AsyncOpenAI"
                if provider == "openai"
                else f"src.ci_helper.ai.providers.{provider}.AsyncAnthropic"
            ) as mock_client_class:
                # プロバイダー固有のモックレスポンス
                mock_client = Mock()
                mock_response = Mock()

                if provider == "openai":
                    mock_response.choices = [Mock()]
                    mock_response.choices[0].message.content = f"OpenAI分析結果: {provider}による分析"
                    mock_response.usage.prompt_tokens = 500
                    mock_response.usage.completion_tokens = 300
                else:  # anthropic
                    mock_response.content = [Mock()]
                    mock_response.content[0].text = f"Anthropic分析結果: {provider}による分析"
                    mock_response.usage.input_tokens = 500
                    mock_response.usage.output_tokens = 300

                mock_client.chat.completions.create = (
                    AsyncMock(return_value=mock_response) if provider == "openai" else None
                )
                mock_client.messages.create = AsyncMock(return_value=mock_response) if provider == "anthropic" else None
                mock_client_class.return_value = mock_client

                # AI統合を実行
                with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
                    mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider=provider,
                        model=mock_ai_config.providers[provider].default_model,
                        use_cache=False,
                        streaming=False,
                    )

                    result = await ai_integration.analyze_log(sample_log_content, options)
                    results[provider] = result

        # 両方のプロバイダーで結果が得られることを確認
        assert len(results) == 2
        assert "openai" in results
        assert "anthropic" in results
        assert all(isinstance(result, AnalysisResult) for result in results.values())

    @pytest.mark.asyncio
    async def test_streaming_analysis(self, mock_ai_config, sample_log_content):
        """ストリーミング分析のテスト"""

        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content="分析"))]),
                Mock(choices=[Mock(delta=Mock(content="を"))]),
                Mock(choices=[Mock(delta=Mock(content="実行"))]),
                Mock(choices=[Mock(delta=Mock(content="中"))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=True,
                )

                chunks = []
                async for chunk in ai_integration.stream_analyze_log(sample_log_content, options):
                    chunks.append(chunk)

                assert len(chunks) == 4
                assert "".join(chunks) == "分析を実行中"

    def test_analyze_command_integration(
        self, runner, temp_dir, mock_ai_config, sample_log_content, sample_analysis_result
    ):
        """analyzeコマンドの統合テスト"""
        # ログファイルを作成
        log_file = temp_dir / "test.log"
        log_file.write_text(sample_log_content, encoding="utf-8")

        # 設定ファイルを作成
        config_file = temp_dir / "ci-helper.toml"
        config_content = """
[ai]
default_provider = "openai"

[ai.providers.openai]
default_model = "gpt-4o"
"""
        config_file.write_text(config_content, encoding="utf-8")

        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            with patch("src.ci_helper.commands.analyze.AIIntegration") as mock_ai_class:
                # AI統合のモック
                mock_ai_integration = Mock()
                mock_ai_integration.initialize = AsyncMock()
                mock_ai_integration.analyze_log = AsyncMock(return_value=sample_analysis_result)
                mock_ai_class.return_value = mock_ai_integration

                # 環境変数でAPIキーを設定
                with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-123"}):
                    result = runner.invoke(cli, ["analyze", "--log", str(log_file)])

                    # コマンドが正常に実行されることを確認
                    assert result.exit_code == 0
                    mock_ai_integration.initialize.assert_called_once()
                    mock_ai_integration.analyze_log.assert_called_once()


class TestAIErrorScenarios:
    """AIエラーシナリオのテスト"""

    @pytest.fixture
    def mock_ai_config(self):
        """モックAI設定"""
        return {
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "api_key": "sk-test-key-123",
                    "default_model": "gpt-4o",
                }
            },
        }

    @pytest.mark.asyncio
    async def test_api_key_error_handling(self, mock_ai_config):
        """APIキーエラーのハンドリングテスト"""
        # 無効なAPIキーを設定
        mock_ai_config["providers"]["openai"]["api_key"] = "invalid-key"

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_openai.side_effect = APIKeyError("Invalid API key")

                ai_integration = AIIntegration(mock_ai_config)

                with pytest.raises(APIKeyError):
                    await ai_integration.initialize()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, mock_ai_config, sample_log_content):
        """レート制限エラーのハンドリングテスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(side_effect=RateLimitError("openai", retry_after=60))
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                with pytest.raises(RateLimitError):
                    await ai_integration.analyze_log(sample_log_content, options)

    @pytest.mark.asyncio
    async def test_provider_unavailable_fallback(self, mock_ai_config, sample_log_content):
        """プロバイダー利用不可時のフォールバック テスト"""
        # 複数プロバイダーを設定
        mock_ai_config["providers"]["anthropic"] = {
            "api_key": "sk-ant-test-key-123",
            "default_model": "claude-3-5-sonnet-20241022",
        }

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            # OpenAIが利用不可、Anthropicは利用可能
            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_openai.side_effect = ProviderError("openai", "OpenAI unavailable")

                with patch("src.ci_helper.ai.providers.anthropic.AsyncAnthropic") as mock_anthropic:
                    mock_client = Mock()
                    mock_response = Mock()
                    mock_response.content = [Mock()]
                    mock_response.content[0].text = "Anthropic分析結果"
                    mock_response.usage.input_tokens = 500
                    mock_response.usage.output_tokens = 300
                    mock_client.messages.create = AsyncMock(return_value=mock_response)
                    mock_anthropic.return_value = mock_client

                    ai_integration = AIIntegration(mock_ai_config)

                    # フォールバック機能をテスト
                    options = AnalyzeOptions(
                        provider="openai",  # 最初はOpenAIを指定
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # フォールバック処理が実装されている場合のテスト
                    # 実装に応じて調整が必要
                    with pytest.raises(ProviderError):
                        await ai_integration.analyze_log(sample_log_content, options)


class TestAIPerformance:
    """AIパフォーマンステスト"""

    @pytest.fixture
    def large_log_content(self):
        """大きなログ内容"""
        base_content = """
ERROR: Test failed
STEP: Run tests
npm ERR! code ENOENT
AssertionError: Expected 200, got 404
"""
        # 大きなログを生成（約10KB）
        return base_content * 100

    @pytest.fixture
    def mock_ai_config(self):
        """モックAI設定"""
        return {
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "api_key": "sk-test-key-123",
                    "default_model": "gpt-4o",
                }
            },
            "cache_enabled": True,
        }

    @pytest.mark.asyncio
    async def test_large_log_processing(self, mock_ai_config, large_log_content):
        """大きなログの処理パフォーマンステスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "大きなログの分析結果"
                mock_response.usage.prompt_tokens = 2000
                mock_response.usage.completion_tokens = 500
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                import time

                start_time = time.time()
                result = await ai_integration.analyze_log(large_log_content, options)
                end_time = time.time()

                # パフォーマンス検証
                processing_time = end_time - start_time
                assert processing_time < 10.0  # 10秒以内で処理完了
                assert isinstance(result, AnalysisResult)

    @pytest.mark.asyncio
    async def test_concurrent_analysis(self, mock_ai_config):
        """並行分析のテスト"""
        log_contents = [
            "Error 1: Test failed",
            "Error 2: Build failed",
            "Error 3: Deploy failed",
        ]

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "並行分析結果"
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                # 並行実行
                tasks = [ai_integration.analyze_log(content, options) for content in log_contents]

                import time

                start_time = time.time()
                results = await asyncio.gather(*tasks)
                end_time = time.time()

                # 結果検証
                assert len(results) == 3
                assert all(isinstance(result, AnalysisResult) for result in results)

                # 並行実行により処理時間が短縮されることを確認
                processing_time = end_time - start_time
                assert processing_time < 5.0  # 5秒以内で並行処理完了
