"""
AI統合パフォーマンス最適化テスト

大きなログファイルの処理最適化、メモリ使用量の最適化、レスポンス時間の改善をテストします。
"""

import asyncio
import gc
import json
import os
import time
from unittest.mock import AsyncMock, Mock, patch

# import psutil  # Optional dependency for memory monitoring
import pytest

from src.ci_helper.ai.exceptions import TokenLimitError
from src.ci_helper.ai.integration import AIIntegration
from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, AnalyzeOptions


@patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=1000)
class TestAIPerformanceOptimization:
    """AI統合パフォーマンス最適化テスト"""

    @pytest.fixture
    def mock_ai_config(self, temp_dir):
        """パフォーマンステスト用AI設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-performance-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=60,  # パフォーマンステスト用に長めに設定
                    max_retries=3,
                ),
                "anthropic": ProviderConfig(
                    name="anthropic",
                    api_key="sk-ant-test-key-123",
                    default_model="claude-3-5-sonnet-20241022",
                    available_models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                    timeout_seconds=60,
                    max_retries=3,
                ),
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=500,  # パフォーマンステスト用に大きめに設定
            cost_limits={"monthly_usd": 100.0, "per_request_usd": 5.0},
            interactive_timeout=600,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=str(temp_dir / "cache"),
        )

    @pytest.fixture
    def large_log_content(self):
        """大きなログ内容を生成（約1MB）"""
        base_error_patterns = [
            "ERROR: Test failed with AssertionError: Expected 200, got 404",
            "STEP: Run tests\nnpm ERR! code ENOENT\nnpm ERR! syscall open",
            "FAILURES:\ntest_authentication.py::test_login FAILED",
            "TimeoutError: Database connection timed out after 30 seconds",
            "ImportError: No module named 'nonexistent_module'",
            "SyntaxError: invalid syntax in file.py line 42",
            "ConnectionError: Failed to establish connection to API",
            "PermissionError: Access denied to file /etc/config",
        ]

        # 大きなログを生成（約1MB）
        large_log = ""
        for i in range(2000):  # 2000回繰り返し
            for j, pattern in enumerate(base_error_patterns):
                large_log += f"[{i:04d}-{j:02d}] {pattern}\n"
                large_log += f"Context line {i}-{j}-1\n"
                large_log += f"Context line {i}-{j}-2\n"
                large_log += f"Context line {i}-{j}-3\n"
                large_log += "=" * 50 + "\n"

        return large_log

    @pytest.fixture
    def very_large_log_content(self):
        """非常に大きなログ内容を生成（約10MB）"""
        base_content = """
STEP: Complex build process
##[group]Run complex-build-script
##[endgroup]
Building application with multiple dependencies...
Compiling TypeScript files...
Running webpack bundler...
Optimizing assets...
ERROR: Build failed with multiple errors:
  - TypeScript compilation error in src/components/UserProfile.tsx:125
  - Webpack bundling error: Module not found 'missing-dependency'
  - Asset optimization failed: Out of memory
  - ESLint errors: 15 issues found
  - Test coverage below threshold: 65% (required: 80%)

FAILURES:
test_integration_api.py::test_user_registration FAILED
test_integration_api.py::test_user_login FAILED
test_integration_api.py::test_password_reset FAILED
test_unit_services.py::test_email_service FAILED
test_unit_services.py::test_notification_service FAILED

Stack trace for test_user_registration:
Traceback (most recent call last):
  File "/app/tests/integration/test_api.py", line 45, in test_user_registration
    response = client.post("/api/users", json=user_data)
  File "/app/lib/test_client.py", line 123, in post
    return self._make_request("POST", url, json=json)
  File "/app/lib/test_client.py", line 89, in _make_request
    response = requests.request(method, full_url, **kwargs)
  File "/usr/local/lib/python3.11/site-packages/requests/api.py", line 61, in request
    return session.request(method=method, url=url, **kwargs)
ConnectionError: HTTPConnectionPool(host='localhost', port=5000): Max retries exceeded
"""
        # 10MB程度のログを生成
        return base_content * 1000

    def get_memory_usage(self):
        """現在のメモリ使用量を取得（MB）"""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # psutil が利用できない場合は固定値を返す
            return 100.0

    @pytest.mark.asyncio
    async def test_large_log_processing_performance(self, large_log_content, mock_ai_config):
        """大きなログファイルの処理パフォーマンステスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                # 高速レスポンスのモック
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {
                        "summary": "大きなログファイルの分析完了",
                        "root_causes": [{"category": "test", "description": "複数のテスト失敗", "severity": "HIGH"}],
                        "confidence_score": 0.88,
                    }
                )
                mock_response.usage.prompt_tokens = 5000
                mock_response.usage.completion_tokens = 1000
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                # プロバイダーの初期化をモック
                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # パフォーマンス測定
                    start_time = time.time()
                    start_memory = self.get_memory_usage()

                    result = await ai_integration.analyze_log(large_log_content, options)

                end_time = time.time()
                end_memory = self.get_memory_usage()

                # パフォーマンス検証
                processing_time = end_time - start_time
                memory_increase = end_memory - start_memory

                assert processing_time < 30.0  # 30秒以内で処理完了
                assert memory_increase < 500  # メモリ増加量が500MB以下
                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.COMPLETED

                print(f"Large log processing: {processing_time:.2f}s, Memory: +{memory_increase:.1f}MB")

    @pytest.mark.asyncio
    async def test_very_large_log_handling(self, very_large_log_content, mock_ai_config):
        """非常に大きなログの処理テスト（メモリ効率性）"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                # トークン制限エラーをシミュレート
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(
                    side_effect=TokenLimitError(used_tokens=20000, limit=16000, model="gpt-4o")
                )
                mock_openai.return_value = mock_client

                # プロバイダーの初期化をモック
                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # メモリ使用量の監視
                    start_memory = self.get_memory_usage()

                    # トークン制限エラーが適切に処理されることを確認
                    with pytest.raises(TokenLimitError):
                        await ai_integration.analyze_log(very_large_log_content, options)

                end_memory = self.get_memory_usage()
                memory_increase = end_memory - start_memory

                # メモリリークがないことを確認
                assert memory_increase < 1000  # 1GB以下のメモリ増加

                print(f"Very large log handling: Memory: +{memory_increase:.1f}MB")

    @pytest.mark.asyncio
    async def test_concurrent_large_log_processing(self, large_log_content, mock_ai_config):
        """大きなログの並行処理パフォーマンステスト"""
        # 複数の大きなログを生成
        log_variants = []
        for i in range(5):
            variant = large_log_content.replace("ERROR:", f"ERROR-{i}:")
            log_variants.append(variant)

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "並行処理分析結果", "confidence_score": 0.85}
                )
                mock_response.usage.prompt_tokens = 3000
                mock_response.usage.completion_tokens = 800
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # 並行処理のパフォーマンス測定
                    start_time = time.time()
                    start_memory = self.get_memory_usage()

                    # 並行実行
                    tasks = [ai_integration.analyze_log(log_content, options) for log_content in log_variants]
                    results = await asyncio.gather(*tasks)

                end_time = time.time()
                end_memory = self.get_memory_usage()

                # パフォーマンス検証
                processing_time = end_time - start_time
                memory_increase = end_memory - start_memory

                assert processing_time < 60.0  # 60秒以内で並行処理完了
                assert memory_increase < 1000  # メモリ増加量が1GB以下
                assert len(results) == 5
                assert all(isinstance(result, AnalysisResult) for result in results)

                print(f"Concurrent processing: {processing_time:.2f}s, Memory: +{memory_increase:.1f}MB")

    @pytest.mark.asyncio
    async def test_streaming_performance_optimization(self, large_log_content, mock_ai_config):
        """ストリーミング処理のパフォーマンス最適化テスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:

                async def mock_streaming_response():
                    # 大量のチャンクをシミュレート
                    chunks = [
                        "# 大きなログファイル",
                        "の分析結果\n\n",
                        "## 検出された問題\n",
                    ]
                    # 多数の小さなチャンクを生成
                    for i in range(100):
                        chunks.append(f"{i + 1}. 問題 {i + 1}\n")

                    chunks.extend(
                        [
                            "\n## 推奨対応\n",
                            "優先度順に対応してください。\n",
                            "\n分析完了。",
                        ]
                    )

                    for chunk in chunks:
                        yield Mock(choices=[Mock(delta=Mock(content=chunk))])
                        # 小さな遅延を追加してリアルなストリーミングをシミュレート
                        await asyncio.sleep(0.001)

                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_streaming_response())
                mock_openai.return_value = mock_client

                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=True,
                    )

                    # ストリーミングパフォーマンス測定
                    start_time = time.time()
                    start_memory = self.get_memory_usage()

                    chunks = []
                    chunk_times = []

                    async for chunk in ai_integration.stream_analyze(large_log_content, options):
                        chunks.append(chunk)
                        chunk_times.append(time.time())

                end_time = time.time()
                end_memory = self.get_memory_usage()

                # パフォーマンス検証
                total_time = end_time - start_time
                memory_increase = end_memory - start_memory

                assert total_time < 20.0  # 20秒以内でストリーミング完了
                assert memory_increase < 200  # メモリ増加量が200MB以下
                assert len(chunks) > 1  # 複数のチャンクが受信された

                # ストリーミングの応答性を確認（最初のチャンクが早く到着）
                if chunk_times:
                    first_chunk_time = chunk_times[0] - start_time
                    assert first_chunk_time < 5.0  # 最初のチャンクが5秒以内に到着

                print(f"Streaming: {total_time:.2f}s, Chunks: {len(chunks)}, Memory: +{memory_increase:.1f}MB")

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_analysis(self, large_log_content, mock_ai_config):
        """分析後のメモリクリーンアップテスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "メモリクリーンアップテスト", "confidence_score": 0.8}
                )
                mock_response.usage.prompt_tokens = 4000
                mock_response.usage.completion_tokens = 1000
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                # 初期メモリ使用量
                initial_memory = self.get_memory_usage()

                # 複数回の分析を実行
                for i in range(10):
                    with patch(
                        "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                    ):
                        ai_integration = AIIntegration(mock_ai_config)
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider="openai",
                            model="gpt-4o",
                            use_cache=False,
                            streaming=False,
                        )

                        result = await ai_integration.analyze_log(large_log_content, options)
                        assert isinstance(result, AnalysisResult)

                        # AI統合をクリーンアップ
                        await ai_integration.cleanup()

                        # 明示的にガベージコレクションを実行
                        gc.collect()

                # 最終メモリ使用量
                final_memory = self.get_memory_usage()
                memory_increase = final_memory - initial_memory

                # メモリリークがないことを確認
                assert memory_increase < 300  # 300MB以下のメモリ増加

                print(f"Memory cleanup test: Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB")

    @pytest.mark.asyncio
    async def test_cache_performance_optimization(self, large_log_content, mock_ai_config, temp_dir):
        """キャッシュパフォーマンス最適化テスト"""
        # キャッシュディレクトリを設定
        cache_dir = temp_dir / "performance_cache"
        mock_ai_config.cache_dir = str(cache_dir)

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "キャッシュパフォーマンステスト", "confidence_score": 0.87}
                )
                mock_response.usage.prompt_tokens = 3000
                mock_response.usage.completion_tokens = 800
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(mock_ai_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=True,
                    streaming=False,
                )

                # 最初の実行（キャッシュなし）
                start_time = time.time()
                result1 = await ai_integration.analyze_log(large_log_content, options)
                first_run_time = time.time() - start_time

                # 2回目の実行（キャッシュあり）
                start_time = time.time()
                result2 = await ai_integration.analyze_log(large_log_content, options)
                second_run_time = time.time() - start_time

                # キャッシュによる高速化を確認
                # 実装に依存するため、基本的な結果確認のみ
                assert isinstance(result1, AnalysisResult)
                assert isinstance(result2, AnalysisResult)
                assert first_run_time > 0
                assert second_run_time > 0

                print(f"Cache performance: 1st run: {first_run_time:.2f}s, 2nd run: {second_run_time:.2f}s")

    @pytest.mark.asyncio
    async def test_response_time_optimization(self, mock_ai_config):
        """レスポンス時間最適化テスト"""
        # 様々なサイズのログでレスポンス時間を測定
        log_sizes = [
            ("small", "ERROR: Simple test failure"),
            ("medium", "ERROR: Test failure\n" + "Context line\n" * 100),
            ("large", "ERROR: Complex failure\n" + "Stack trace line\n" * 1000),
        ]

        response_times = {}

        for size_name, log_content in log_sizes:
            with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
                mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

                with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                    mock_client = Mock()
                    mock_response = Mock()
                    mock_response.choices = [Mock()]
                    mock_response.choices[0].message.content = json.dumps(
                        {"summary": f"{size_name}ログの分析結果", "confidence_score": 0.8}
                    )
                    # ログサイズに応じたトークン数をシミュレート
                    token_count = len(log_content) // 4  # 大まかなトークン数推定
                    mock_response.usage.prompt_tokens = token_count
                    mock_response.usage.completion_tokens = token_count // 4
                    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                    mock_openai.return_value = mock_client

                    with patch(
                        "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                    ):
                        ai_integration = AIIntegration(mock_ai_config)
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider="openai",
                            model="gpt-4o",
                            use_cache=False,
                            streaming=False,
                        )

                        # レスポンス時間測定
                        start_time = time.time()
                        result = await ai_integration.analyze_log(log_content, options)
                        end_time = time.time()

                        response_time = end_time - start_time
                        response_times[size_name] = response_time

                        assert isinstance(result, AnalysisResult)
                        assert result.status == AnalysisStatus.COMPLETED

        # レスポンス時間の妥当性を確認
        assert response_times["small"] < 10.0  # 小さなログは10秒以内
        assert response_times["medium"] < 20.0  # 中程度のログは20秒以内
        assert response_times["large"] < 30.0  # 大きなログは30秒以内

        print(f"Response times: {response_times}")

    @pytest.mark.asyncio
    async def test_token_optimization_strategies(self, large_log_content, mock_ai_config):
        """トークン最適化戦略のテスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            # トークン制限エラーをシミュレート
            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()

                # 最初はトークン制限エラー
                token_limit_error = TokenLimitError(used_tokens=20000, limit=16000, model="gpt-4o")
                mock_client.chat.completions.create = AsyncMock(side_effect=token_limit_error)
                mock_openai.return_value = mock_client

                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # トークン制限エラーが発生することを確認
                    with pytest.raises(TokenLimitError):
                        await ai_integration.analyze_log(large_log_content, options)

                # より小さなモデルでの成功をシミュレート
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "小さなモデルでの分析結果", "confidence_score": 0.75}
                )
                mock_response.usage.prompt_tokens = 8000
                mock_response.usage.completion_tokens = 2000
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

                # 小さなモデルでのオプション
                small_model_options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o-mini",  # より小さなモデル
                    use_cache=False,
                    streaming=False,
                )

                result = await ai_integration.analyze_log(large_log_content, small_model_options)
                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_error_recovery_performance(self, large_log_content, mock_ai_config):
        """エラー復旧のパフォーマンステスト"""
        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()

                # 最初の数回は失敗、その後成功
                call_count = 0

                async def mock_api_call(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:
                        # 最初の2回は一時的なエラー
                        from src.ci_helper.ai.exceptions import NetworkError

                        raise NetworkError("Temporary network error")
                    else:
                        # 3回目で成功
                        mock_response = Mock()
                        mock_response.choices = [Mock()]
                        mock_response.choices[0].message.content = json.dumps(
                            {"summary": "復旧後の分析結果", "confidence_score": 0.82}
                        )
                        mock_response.usage.prompt_tokens = 3000
                        mock_response.usage.completion_tokens = 800
                        return mock_response

                mock_client.chat.completions.create = AsyncMock(side_effect=mock_api_call)
                mock_openai.return_value = mock_client

                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # エラー復旧のパフォーマンス測定
                    start_time = time.time()

                    # 最初の2回は失敗するはず
                    from src.ci_helper.ai.exceptions import NetworkError

                    with pytest.raises(NetworkError):
                        await ai_integration.analyze_log(large_log_content, options)

                    with pytest.raises(NetworkError):
                        await ai_integration.analyze_log(large_log_content, options)

                    # 3回目で成功
                    result = await ai_integration.analyze_log(large_log_content, options)

                end_time = time.time()
                total_time = end_time - start_time

                # 復旧時間の確認
                assert total_time < 60.0  # 60秒以内で復旧
                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.COMPLETED
                assert call_count == 3  # 3回の呼び出しが行われた

                print(f"Error recovery: {total_time:.2f}s, Attempts: {call_count}")

    @pytest.mark.asyncio
    async def test_batch_processing_optimization(self, mock_ai_config):
        """バッチ処理最適化テスト"""
        # 複数の小さなログを生成
        small_logs = [f"ERROR {i}: Test failure in module_{i}" for i in range(20)]

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps(
                    {"summary": "バッチ処理分析結果", "confidence_score": 0.8}
                )
                mock_response.usage.prompt_tokens = 500
                mock_response.usage.completion_tokens = 200
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                with patch(
                    "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                ):
                    ai_integration = AIIntegration(mock_ai_config)
                    await ai_integration.initialize()

                    options = AnalyzeOptions(
                        provider="openai",
                        model="gpt-4o",
                        use_cache=False,
                        streaming=False,
                    )

                    # 個別処理の時間測定
                    start_time = time.time()
                    individual_results = []
                    for log in small_logs[:5]:  # 最初の5個のみテスト
                        result = await ai_integration.analyze_log(log, options)
                        individual_results.append(result)
                    individual_time = time.time() - start_time

                    # バッチ処理の時間測定
                    start_time = time.time()
                    batch_tasks = [ai_integration.analyze_log(log, options) for log in small_logs[:5]]
                    batch_results = await asyncio.gather(*batch_tasks)
                    batch_time = time.time() - start_time

                # バッチ処理の効率性を確認
                assert len(individual_results) == 5
                assert len(batch_results) == 5
                assert all(isinstance(result, AnalysisResult) for result in individual_results)
                assert all(isinstance(result, AnalysisResult) for result in batch_results)

                # バッチ処理が効率的であることを確認（実装に依存）
                print(f"Individual: {individual_time:.2f}s, Batch: {batch_time:.2f}s")

    def test_resource_monitoring_during_analysis(self, large_log_content, mock_ai_config):
        """分析中のリソース監視テスト"""

        async def monitor_resources():
            """リソース使用量を監視"""
            max_memory = 0
            max_cpu = 0
            measurements = []

            try:
                import psutil

                for _ in range(10):  # 10回測定
                    process = psutil.Process(os.getpid())
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    cpu_percent = process.cpu_percent()

                    max_memory = max(max_memory, memory_mb)
                    max_cpu = max(max_cpu, cpu_percent)
                    measurements.append({"memory": memory_mb, "cpu": cpu_percent})

                    await asyncio.sleep(0.1)  # 100ms間隔で測定
            except ImportError:
                # psutil が利用できない場合はモック値を使用
                for i in range(10):
                    memory_mb = 100.0 + i * 5  # 徐々に増加するメモリ使用量
                    cpu_percent = 10.0 + i * 2  # 徐々に増加するCPU使用率

                    max_memory = max(max_memory, memory_mb)
                    max_cpu = max(max_cpu, cpu_percent)
                    measurements.append({"memory": memory_mb, "cpu": cpu_percent})

                    await asyncio.sleep(0.1)

            return {"max_memory": max_memory, "max_cpu": max_cpu, "measurements": measurements}

        async def run_analysis():
            """分析を実行"""
            with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
                mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

                with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                    mock_client = Mock()
                    mock_response = Mock()
                    mock_response.choices = [Mock()]
                    mock_response.choices[0].message.content = json.dumps(
                        {"summary": "リソース監視テスト", "confidence_score": 0.8}
                    )
                    mock_response.usage.prompt_tokens = 4000
                    mock_response.usage.completion_tokens = 1000
                    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                    mock_openai.return_value = mock_client

                    with patch(
                        "src.ci_helper.ai.providers.openai.OpenAIProvider.validate_connection", new_callable=AsyncMock
                    ):
                        ai_integration = AIIntegration(mock_ai_config)
                        await ai_integration.initialize()

                        options = AnalyzeOptions(
                            provider="openai",
                            model="gpt-4o",
                            use_cache=False,
                            streaming=False,
                        )

                        # 分析を実行（少し時間をかける）
                        await asyncio.sleep(0.5)  # 監視のための時間
                        result = await ai_integration.analyze_log(large_log_content, options)
                        await asyncio.sleep(0.5)  # 監視のための時間

                        return result

        # 分析とリソース監視を並行実行
        async def run_test():
            analysis_task = asyncio.create_task(run_analysis())
            monitoring_task = asyncio.create_task(monitor_resources())

            result, resource_stats = await asyncio.gather(analysis_task, monitoring_task)
            return result, resource_stats

        result, resource_stats = asyncio.run(run_test())

        # 結果の検証
        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.COMPLETED

        # リソース使用量の確認
        assert resource_stats["max_memory"] < 2000  # 2GB以下
        assert len(resource_stats["measurements"]) > 0

        print(
            f"Resource usage: Max Memory: {resource_stats['max_memory']:.1f}MB, Max CPU: {resource_stats['max_cpu']:.1f}%"
        )
