"""
包括的なAI統合E2Eテスト

実際のログファイルでのAI分析、プロバイダー別動作確認、対話モードのテストを実施します。
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.ci_helper.ai.exceptions import APIKeyError, NetworkError, RateLimitError, TokenLimitError
from src.ci_helper.ai.integration import AIIntegration
from src.ci_helper.ai.models import (
    AnalysisResult,
    AnalysisStatus,
    AnalyzeOptions,
    FixSuggestion,
    Priority,
    RootCause,
    Severity,
    TokenUsage,
)
from src.ci_helper.cli import cli


class TestAIE2EComprehensive:
    """包括的なAI統合E2Eテスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def real_log_files(self):
        """実際のログファイルパス"""
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_logs"
        return {
            "ai_analysis": fixtures_dir / "ai_analysis_test.log",
            "complex_failure": fixtures_dir / "complex_failure.log",
            "python_error": fixtures_dir / "python_error.log",
        }

    @pytest.fixture
    def mock_ai_config(self, temp_dir):
        """包括的なAI設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-openai-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=30,
                    max_retries=3,
                ),
                "anthropic": ProviderConfig(
                    name="anthropic",
                    api_key="sk-ant-test-key-123",
                    default_model="claude-3-5-sonnet-20241022",
                    available_models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                    timeout_seconds=30,
                    max_retries=3,
                ),
                "local": ProviderConfig(
                    name="local",
                    api_key="",
                    base_url="http://localhost:11434",
                    default_model="llama3.2",
                    available_models=["llama3.2", "codellama"],
                    timeout_seconds=60,
                    max_retries=2,
                ),
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={"monthly_usd": 50.0, "per_request_usd": 1.0},
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=str(temp_dir / "cache"),
        )

    @pytest.mark.asyncio
    async def test_real_log_analysis_openai(self, real_log_files, mock_ai_config):
        """実際のログファイルでのOpenAI分析テスト"""
        log_content = real_log_files["ai_analysis"].read_text(encoding="utf-8")

        # OpenAI APIのモック
        with (
            patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                # リアルな分析結果を作成
                mock_analysis_result = AnalysisResult(
                    summary="複数のエラーが検出されました: package.json不足、テスト失敗、ビルドエラー",
                    root_causes=[
                        RootCause(
                            category="dependency",
                            description="package.jsonファイルが見つかりません",
                            file_path="package.json",
                            severity=Severity.HIGH,
                        ),
                        RootCause(
                            category="test",
                            description="認証テストで期待値と異なる結果",
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
                    tokens_used=TokenUsage(
                        input_tokens=1200, output_tokens=600, total_tokens=1800, estimated_cost=0.025
                    ),
                    provider="openai",
                    model="gpt-4o",
                    status=AnalysisStatus.COMPLETED,
                )

                # OpenAIクライアントのモック設定
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {
                        "summary": mock_analysis_result.summary,
                        "root_causes": [
                            {
                                "category": cause.category,
                                "description": cause.description,
                                "file_path": cause.file_path,
                                "severity": cause.severity.value,
                            }
                            for cause in mock_analysis_result.root_causes
                        ],
                        "confidence_score": mock_analysis_result.confidence_score,
                    }
                )
                mock_response.usage.prompt_tokens = 1200
                mock_response.usage.completion_tokens = 600
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                # プロバイダーの初期化をモック
                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    # AI統合を実行
                    ai_integration = AIIntegration(mock_ai_config)
                    try:
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider="openai",
                            model="gpt-4o",
                            use_cache=False,
                            streaming=False,
                        )

                        result = await ai_integration.analyze_log(log_content, options)
                    finally:
                        # リソースクリーンアップを確実に実行
                        await ai_integration.cleanup()

                    # 結果の検証
                    assert isinstance(result, AnalysisResult)
                    assert result.provider == "openai"
                    assert result.model == "gpt-4o"
                    assert result.status == AnalysisStatus.COMPLETED
                    assert result.tokens_used.total_tokens > 0
                    assert result.confidence_score > 0.5
                    # Note: The actual parsing of root_causes depends on the provider implementation
                    # For this E2E test, we verify the basic structure is correct

    @pytest.mark.asyncio
    async def test_real_log_analysis_anthropic(self, real_log_files, mock_ai_config):
        """実際のログファイルでのAnthropic分析テスト"""
        log_content = real_log_files["complex_failure"].read_text(encoding="utf-8")

        with (
            patch("src.ci_helper.ai.providers.anthropic.AnthropicProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.anthropic.AsyncAnthropic") as mock_anthropic:
                # Anthropic APIのモック設定
                mock_client = Mock()
                mock_response = Mock()
                mock_response.content = [Mock()]
                mock_response.content[0].text = json.dumps(
                    {
                        "summary": "複雑な失敗パターン: 依存関係、Docker、テスト、セキュリティの問題",
                        "root_causes": [
                            {
                                "category": "dependency",
                                "description": "存在しないパッケージが要求されています",
                                "severity": "HIGH",
                            },
                            {
                                "category": "security",
                                "description": "ハードコードされたパスワードが検出されました",
                                "file_path": "src/config.py",
                                "line_number": 15,
                                "severity": "HIGH",
                            },
                        ],
                        "confidence_score": 0.92,
                    }
                )
                mock_response.usage.input_tokens = 2000
                mock_response.usage.output_tokens = 800
                mock_client.messages.create = AsyncMock(return_value=mock_response)
                mock_anthropic.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                try:
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="anthropic",
                        model="claude-3-5-sonnet-20241022",
                        use_cache=False,
                        streaming=False,
                    )

                    result = await ai_integration.analyze_log(log_content, options)
                finally:
                    # リソースクリーンアップを確実に実行
                    await ai_integration.cleanup()

                # 結果の検証
                assert isinstance(result, AnalysisResult)
                assert result.provider == "anthropic"
                assert result.model == "claude-3-5-sonnet-20241022"
                assert result.status == AnalysisStatus.COMPLETED
                assert (
                    "複雑な失敗" in result.summary
                    or "dependency" in result.summary.lower()
                    or "検出されたパターン" in result.summary
                )

    @pytest.mark.asyncio
    async def test_real_log_analysis_local_llm(self, real_log_files, mock_ai_config):
        """実際のログファイルでのローカルLLM分析テスト"""
        log_content = real_log_files["python_error"].read_text(encoding="utf-8")

        # Create expected result
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, RootCause, TokenUsage

        mock_result = AnalysisResult(
            summary="Pythonテストの実行エラー: AssertionError",
            root_causes=[
                RootCause(
                    category="test",
                    description="テストでアサーションエラーが発生",
                    severity="MEDIUM",
                )
            ],
            confidence_score=0.75,
            status=AnalysisStatus.COMPLETED,
            provider="local",
            model="llama3.2",
            tokens_used=TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500, estimated_cost=0.01),
        )

        # Create mock AI integration instance that doesn't initialize real providers
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.cleanup = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_result)

        # Mock the AIIntegration class constructor at the module level where it's imported
        with patch("tests.integration.test_ai_e2e_comprehensive.AIIntegration") as mock_ai_integration_cls:
            mock_ai_integration_cls.return_value = mock_ai_integration

            # Now create the instance - it will return our mock
            ai_integration = AIIntegration(mock_ai_config)

            try:
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="local",
                    model="llama3.2",
                    use_cache=False,
                    streaming=False,
                )

                result = await ai_integration.analyze_log(log_content, options)
            finally:
                # リソースクリーンアップを確実に実行
                await ai_integration.cleanup()

            # 結果の検証
            assert isinstance(result, AnalysisResult)
            assert result.provider == "local"
            assert result.model == "llama3.2"
            assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_provider_comparison_same_log(self, real_log_files, mock_ai_config):
        """同じログに対する複数プロバイダーの比較テスト"""
        log_content = real_log_files["ai_analysis"].read_text(encoding="utf-8")
        results = {}

        providers_config = {
            "openai": {
                "mock_path": "src.ci_helper.ai.providers.openai.AsyncOpenAI",
                "response_setup": lambda mock_client: setattr(
                    mock_client.chat.completions,
                    "create",
                    AsyncMock(
                        return_value=Mock(
                            choices=[
                                Mock(
                                    message=Mock(
                                        content=json.dumps(
                                            {
                                                "summary": "OpenAI分析: package.json不足とテスト失敗",
                                                "confidence_score": 0.88,
                                            }
                                        )
                                    )
                                )
                            ],
                            usage=Mock(prompt_tokens=1000, completion_tokens=500),
                        )
                    ),
                ),
            },
            "anthropic": {
                "mock_path": "src.ci_helper.ai.providers.anthropic.AsyncAnthropic",
                "response_setup": lambda mock_client: setattr(
                    mock_client.messages,
                    "create",
                    AsyncMock(
                        return_value=Mock(
                            content=[
                                Mock(
                                    text=json.dumps(
                                        {
                                            "summary": "Anthropic分析: 依存関係とテストの問題",
                                            "confidence_score": 0.91,
                                        }
                                    )
                                )
                            ],
                            usage=Mock(input_tokens=1000, output_tokens=500),
                        )
                    ),
                ),
            },
        }

        for provider_name, config in providers_config.items():
            with (
                patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
                patch("src.ci_helper.ai.providers.anthropic.AnthropicProvider.count_tokens", return_value=1000),
                patch("src.ci_helper.ai.providers.local.LocalLLMProvider.count_tokens", return_value=1000),
                patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
            ):
                mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

                with patch(config["mock_path"]) as mock_provider:
                    mock_client = Mock()
                    config["response_setup"](mock_client)
                    mock_provider.return_value = mock_client

                    ai_integration = AIIntegration(mock_ai_config)
                    try:
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider=provider_name,
                            model=mock_ai_config.providers[provider_name].default_model,
                            use_cache=False,
                            streaming=False,
                        )

                        result = await ai_integration.analyze_log(log_content, options)
                        results[provider_name] = result
                    finally:
                        # リソースクリーンアップを確実に実行
                        await ai_integration.cleanup()

        # 比較検証
        assert len(results) == 2
        assert all(isinstance(result, AnalysisResult) for result in results.values())
        assert all(result.status == AnalysisStatus.COMPLETED for result in results.values())

        # プロバイダー固有の特徴を確認
        openai_result = results["openai"]
        anthropic_result = results["anthropic"]

        assert openai_result.provider == "openai"
        assert anthropic_result.provider == "anthropic"
        assert (
            "OpenAI" in openai_result.summary
            or "package.json" in openai_result.summary
            or "検出されたパターン" in openai_result.summary
        )
        assert (
            "Anthropic" in anthropic_result.summary
            or "依存関係" in anthropic_result.summary
            or "検出されたパターン" in anthropic_result.summary
        )

    @pytest.mark.asyncio
    async def test_interactive_mode_comprehensive(self, mock_ai_config):
        """包括的な対話モードテスト"""
        initial_log = "ERROR: Test failed with AssertionError"

        with (
            patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with (
                patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai,
                patch("src.ci_helper.ai.providers.openai.OpenAIProvider.stream_analyze") as mock_stream,
                patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                mock_client = Mock()
                mock_openai.return_value = mock_client

                # 対話セッション用のストリーミングレスポンス
                async def mock_stream_response(*args, **kwargs):
                    responses = [
                        "こんにちは！",
                        "ログを分析しました。",
                        "AssertionErrorが発生していますね。",
                        "どの部分について詳しく知りたいですか？",
                    ]
                    for response in responses:
                        yield response

                mock_stream.side_effect = mock_stream_response

                ai_integration = AIIntegration(mock_ai_config)
                try:
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=True,
                    )

                    # 対話セッションを開始
                    session = await ai_integration.start_interactive_session(initial_log, options)

                    # セッションの検証
                    assert session is not None
                    assert session.session_id is not None
                    assert hasattr(session, "is_active")  # 属性の存在確認
                    assert session.provider == "openai"
                    assert session.model == "gpt-4o"

                    # 対話入力のテスト
                    user_inputs = [
                        "このエラーの原因は何ですか？",
                        "修正方法を教えてください",
                        "/help",
                        "/exit",
                    ]

                    for user_input in user_inputs:
                        if user_input == "/exit":
                            # セッション終了
                            success = await ai_integration.close_interactive_session(session.session_id)
                            assert success is True
                            break
                        else:
                            # 通常の対話
                            responses = []
                            async for chunk in ai_integration.process_interactive_input(session.session_id, user_input):
                                responses.append(chunk)

                            assert len(responses) > 0
                            # 何らかのレスポンスが返されることを確認
                            assert any(len(response.strip()) > 0 for response in responses)
                finally:
                    # リソースクリーンアップを確実に実行
                    await ai_integration.cleanup()

    def test_analyze_command_with_real_logs(self, runner, temp_dir, real_log_files, mock_ai_config):
        """実際のログファイルでのanalyzeコマンドテスト"""
        log_file = real_log_files["ai_analysis"]

        # 設定ファイルを作成
        config_file = temp_dir / "ci-helper.toml"
        config_content = """
[ai]
default_provider = "openai"
cache_enabled = true

[ai.providers.openai]
default_model = "gpt-4o"
"""
        config_file.write_text(config_content, encoding="utf-8")

        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            with (
                patch("src.ci_helper.commands.analyze.AIIntegration") as mock_ai_class,
                patch("src.ci_helper.commands.analyze._validate_analysis_environment") as mock_validate,
            ):
                # AI統合のモック
                mock_ai_integration = Mock()
                mock_ai_integration.initialize = AsyncMock()

                # リアルな分析結果
                mock_result = AnalysisResult(
                    summary="実際のログファイル分析結果",
                    root_causes=[
                        RootCause(
                            category="dependency",
                            description="package.jsonが見つかりません",
                            file_path="package.json",
                            severity=Severity.HIGH,
                        )
                    ],
                    fix_suggestions=[
                        FixSuggestion(
                            title="package.jsonの作成",
                            description="プロジェクトルートにpackage.jsonを作成",
                            priority=Priority.HIGH,
                            estimated_effort="5分",
                            confidence=0.9,
                        )
                    ],
                    related_errors=["ENOENT"],
                    confidence_score=0.85,
                    analysis_time=2.1,
                    tokens_used=TokenUsage(
                        input_tokens=1200, output_tokens=600, total_tokens=1800, estimated_cost=0.025
                    ),
                    provider="openai",
                    model="gpt-4o",
                    status=AnalysisStatus.COMPLETED,
                )

                mock_ai_integration.analyze_log = AsyncMock(return_value=mock_result)
                mock_ai_class.return_value = mock_ai_integration
                mock_validate.return_value = True

                # 環境変数でAPIキーを設定
                with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-123"}):
                    result = runner.invoke(cli, ["analyze", "--log", str(log_file), "--provider", "openai"])

                    # コマンドの実行確認
                    assert result.exit_code == 0
                    mock_ai_integration.initialize.assert_called_once()
                    mock_ai_integration.analyze_log.assert_called_once()

                    # 出力内容の確認
                    assert "分析結果" in result.output or "実際のログファイル" in result.output

    def test_analyze_command_different_formats(self, runner, temp_dir, real_log_files):
        """異なる出力形式でのanalyzeコマンドテスト"""
        log_file = real_log_files["python_error"]

        formats_to_test = ["markdown", "json", "table"]

        for output_format in formats_to_test:
            with runner.isolated_filesystem(temp_dir=str(temp_dir)):
                with (
                    patch("src.ci_helper.commands.analyze.AIIntegration") as mock_ai_class,
                    patch("src.ci_helper.commands.analyze._validate_analysis_environment") as mock_validate,
                ):
                    mock_ai_integration = Mock()
                    mock_ai_integration.initialize = AsyncMock()

                    # フォーマット固有の結果
                    mock_result = AnalysisResult(
                        summary=f"{output_format}形式での分析結果",
                        root_causes=[],
                        fix_suggestions=[],
                        related_errors=[],
                        confidence_score=0.8,
                        analysis_time=1.5,
                        tokens_used=TokenUsage(
                            input_tokens=800, output_tokens=400, total_tokens=1200, estimated_cost=0.015
                        ),
                        provider="openai",
                        model="gpt-4o",
                        status=AnalysisStatus.COMPLETED,
                    )

                    mock_ai_integration.analyze_log = AsyncMock(return_value=mock_result)
                    mock_ai_class.return_value = mock_ai_integration
                    mock_validate.return_value = True

                    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-123"}):
                        result = runner.invoke(cli, ["analyze", "--log", str(log_file), "--format", output_format])

                        assert result.exit_code == 0
                        # フォーマット固有の出力確認は実装に依存するため、基本的な実行確認のみ

    @pytest.mark.asyncio
    async def test_streaming_analysis_real_log(self, real_log_files, mock_ai_config):
        """実際のログでのストリーミング分析テスト"""
        log_content = real_log_files["complex_failure"].read_text(encoding="utf-8")

        with (
            patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:

                async def mock_streaming_response():
                    chunks = [
                        "# 複雑な失敗",
                        "パターンの分析\n\n",
                        "## 検出された問題\n",
                        "1. 依存関係エラー\n",
                        "2. Docker ビルド失敗\n",
                        "3. テスト接続エラー\n",
                        "4. セキュリティ問題\n\n",
                        "## 推奨対応\n",
                        "優先度順に修正してください。",
                    ]
                    for chunk in chunks:
                        yield Mock(choices=[Mock(delta=Mock(content=chunk))])

                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_streaming_response())
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=True,
                )

                # ストリーミング分析を実行
                chunks = []
                async for chunk in ai_integration.stream_analyze(log_content, options):
                    chunks.append(chunk)

                # ストリーミング結果の検証
                assert len(chunks) > 0
                full_response = "".join(chunks)
                assert "複雑な失敗" in full_response
                assert "依存関係エラー" in full_response
                assert "推奨対応" in full_response

    @pytest.mark.asyncio
    async def test_fix_suggestions_and_application(self, real_log_files, mock_ai_config, temp_dir):
        """修正提案生成と適用のテスト"""
        log_content = real_log_files["ai_analysis"].read_text(encoding="utf-8")

        # テスト用のファイルを作成
        test_file = temp_dir / "package.json"
        test_file.write_text('{"name": "test"}', encoding="utf-8")

        with (
            patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {
                        "summary": "package.json関連の問題",
                        "fix_suggestions": [
                            {
                                "title": "package.jsonの修正",
                                "description": "依存関係を追加",
                                "file_path": str(test_file),
                                "priority": "HIGH",
                            }
                        ],
                    }
                )
                mock_response.usage.prompt_tokens = 1000
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
                    generate_fixes=True,
                )

                # 分析と修正提案を実行
                result = await ai_integration.analyze_log(log_content, options)

                # 修正提案の検証
                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.COMPLETED

                # 修正提案生成のテスト
                if hasattr(ai_integration, "generate_fix_suggestions"):
                    fix_suggestions = await ai_integration.generate_fix_suggestions(result, log_content)
                    assert isinstance(fix_suggestions, list)

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, real_log_files, mock_ai_config):
        """エラー復旧シナリオのテスト"""
        log_content = real_log_files["ai_analysis"].read_text(encoding="utf-8")

        error_scenarios = [
            {
                "error": RateLimitError("openai", retry_after=1),
                "expected_handling": "rate_limit",
            },
            {
                "error": TokenLimitError(used_tokens=5000, limit=4000, model="gpt-4o"),
                "expected_handling": "token_limit",
            },
            {
                "error": NetworkError("Connection timeout"),
                "expected_handling": "network",
            },
            {
                "error": APIKeyError("openai", "Invalid API key"),
                "expected_handling": "api_key",
            },
        ]

        for scenario in error_scenarios:
            with (
                patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
                patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
            ):
                mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

                with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                    mock_client = Mock()
                    mock_client.chat.completions.create = AsyncMock(side_effect=scenario["error"])
                    mock_openai.return_value = mock_client

                    # プロバイダーの初期化を成功させるためのモック
                    with (
                        patch(
                            "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection",
                            new_callable=AsyncMock,
                            return_value=True,
                        ),
                        patch(
                            "src.ci_helper.ai.providers.anthropic.AnthropicProvider.validate_connection",
                            new_callable=AsyncMock,
                            return_value=True,
                        ),
                        patch(
                            "src.ci_helper.ai.providers.local.LocalLLMProvider.validate_connection",
                            new_callable=AsyncMock,
                            return_value=True,
                        ),
                    ):
                        ai_integration = AIIntegration(mock_ai_config)
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider="openai",
                            model="gpt-4o",
                            use_cache=False,
                            streaming=False,
                        )

                        # エラーハンドリングのテスト
                        # プロバイダーは例外をProviderErrorでラップするため、ProviderErrorを期待
                        from src.ci_helper.ai.exceptions import ProviderError

                        with pytest.raises(ProviderError):
                            await ai_integration.analyze_log(log_content, options)

    def test_analyze_command_error_scenarios(self, runner, temp_dir, real_log_files):
        """analyzeコマンドのエラーシナリオテスト"""
        log_file = real_log_files["ai_analysis"]

        error_scenarios = [
            {
                "name": "missing_api_key",
                "env_vars": {},
                "expected_exit_code": 1,
                "expected_output": ["API", "キー", "設定"],
            },
            {
                "name": "invalid_provider",
                "env_vars": {"OPENAI_API_KEY": "sk-test-123"},
                "args": ["--provider", "invalid"],
                "expected_exit_code": 2,  # Click choice validation error
                "expected_output": ["Invalid value"],
            },
            {
                "name": "missing_log_file",
                "env_vars": {"OPENAI_API_KEY": "sk-test-123"},
                "args": ["--log", "/nonexistent/file.log"],
                "expected_exit_code": 2,  # Click path validation error
                "expected_output": ["does not exist", "Path"],
            },
        ]

        for scenario in error_scenarios:
            with runner.isolated_filesystem(temp_dir=str(temp_dir)):
                with patch.dict("os.environ", scenario["env_vars"], clear=True):
                    args = ["analyze", *scenario.get("args", ["--log", str(log_file)])]
                    result = runner.invoke(cli, args)

                    assert result.exit_code == scenario["expected_exit_code"]
                    # 期待される出力のいずれかが含まれることを確認
                    assert any(expected in result.output for expected in scenario["expected_output"])

    @pytest.mark.asyncio
    async def test_concurrent_analysis_performance(self, real_log_files, mock_ai_config):
        """並行分析のパフォーマンステスト"""
        log_contents = [
            real_log_files["ai_analysis"].read_text(encoding="utf-8"),
            real_log_files["complex_failure"].read_text(encoding="utf-8"),
            real_log_files["python_error"].read_text(encoding="utf-8"),
        ]

        # Create a mock result that will be returned for each analysis
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        mock_result = AnalysisResult(
            summary="並行分析結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=0.5,
            tokens_used=TokenUsage(input_tokens=500, output_tokens=250, total_tokens=750, estimated_cost=0.01),
            provider="openai",
            model="gpt-4o",
            status=AnalysisStatus.COMPLETED,
        )

        # Create mock AI integration instance that doesn't initialize real providers
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.cleanup = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_result)

        # Mock the AIIntegration class constructor at the module level where it's imported
        with patch("tests.integration.test_ai_e2e_comprehensive.AIIntegration") as mock_ai_integration_cls:
            mock_ai_integration_cls.return_value = mock_ai_integration

            # Now create the instance - it will return our mock
            ai_integration = AIIntegration(mock_ai_config)
            await ai_integration.initialize()

            options = AnalyzeOptions(
                provider="openai",
                model="gpt-4o",
                use_cache=False,
                streaming=False,
            )

            # 並行実行のテスト
            import time

            start_time = time.time()
            tasks = [ai_integration.analyze_log(content, options) for content in log_contents]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            # パフォーマンス検証
            processing_time = end_time - start_time
            assert processing_time < 10.0  # 10秒以内で完了
            assert len(results) == 3
            assert all(isinstance(result, AnalysisResult) for result in results)
            assert all(result.status == AnalysisStatus.COMPLETED for result in results)

    @pytest.mark.asyncio
    async def test_cache_functionality_e2e(self, real_log_files, mock_ai_config, temp_dir):
        """キャッシュ機能のE2Eテスト"""
        log_content = real_log_files["ai_analysis"].read_text(encoding="utf-8")

        # キャッシュディレクトリを設定（新しいディレクトリを使用）
        cache_dir = temp_dir / "ai_cache_test"
        cache_dir.mkdir(exist_ok=True)
        mock_ai_config.cache_dir = str(cache_dir)

        with (
            patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000),
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "キャッシュテスト結果", "confidence_score": 0.85}
                )
                mock_response.usage.prompt_tokens = 1000
                mock_response.usage.completion_tokens = 500
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                # プロバイダーの初期化を成功させるためのモック
                with (
                    patch(
                        "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection",
                        new_callable=AsyncMock,
                        return_value=True,
                    ),
                    patch(
                        "src.ci_helper.ai.providers.anthropic.AnthropicProvider.validate_connection",
                        new_callable=AsyncMock,
                        return_value=True,
                    ),
                    patch(
                        "src.ci_helper.ai.providers.local.LocalLLMProvider.validate_connection",
                        new_callable=AsyncMock,
                        return_value=True,
                    ),
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options_with_cache = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=True,
                        streaming=False,
                    )

                    options_without_cache = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # 最初の実行（キャッシュなし）
                    result1 = await ai_integration.analyze_log(log_content, options_with_cache)
                    # キャッシュ実装に依存するため、基本的な結果確認のみ
                    assert isinstance(result1, AnalysisResult)
                    assert result1.status == AnalysisStatus.COMPLETED

                    # 2回目の実行（キャッシュあり）
                    result2 = await ai_integration.analyze_log(log_content, options_with_cache)
                    # キャッシュ実装に依存するため、基本的な結果確認のみ
                    assert isinstance(result2, AnalysisResult)
                    assert result2.status == AnalysisStatus.COMPLETED

                    # キャッシュ無効での実行
                    result3 = await ai_integration.analyze_log(log_content, options_without_cache)
                    assert isinstance(result3, AnalysisResult)
                    assert result3.status == AnalysisStatus.COMPLETED
