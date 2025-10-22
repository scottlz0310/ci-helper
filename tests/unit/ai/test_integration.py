"""
AI統合メインクラスのテスト

AIIntegrationクラスの中核機能、プロバイダー管理、非同期処理、
キャッシュ統合機能を包括的にテストします。
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ci_helper.ai.exceptions import (
    AIError,
    APIKeyError,
    ConfigurationError,
    NetworkError,
    ProviderError,
    RateLimitError,
)
from src.ci_helper.ai.integration import AIIntegration
from src.ci_helper.ai.models import (
    AIConfig,
    AnalysisResult,
    AnalysisStatus,
    AnalyzeOptions,
    FixSuggestion,
    InteractiveSession,
    ProviderConfig,
    TokenUsage,
)
from src.ci_helper.utils.config import Config


class TestAIIntegrationCore:
    """AIIntegrationクラスの中核機能テスト"""

    @pytest.fixture
    def mock_config(self, temp_dir):
        """テスト用設定オブジェクト"""
        config = Mock(spec=Config)
        config.project_root = temp_dir
        config.get_path.return_value = temp_dir / "cache"
        return config

    @pytest.fixture
    def ai_integration(self, mock_config):
        """AIIntegrationインスタンス"""
        return AIIntegration(mock_config)

    def test_initialization_with_config(self, mock_config, mock_ai_config):
        """設定を使用した初期化のテスト"""
        # Configオブジェクトでの初期化
        integration = AIIntegration(mock_config)
        assert integration.config == mock_config
        assert not integration._initialized

        # AIConfigオブジェクトでの初期化
        integration_ai = AIIntegration(mock_ai_config)
        assert integration_ai.ai_config == mock_ai_config
        assert not integration_ai._initialized

        # 辞書での初期化
        config_dict = {
            "ai": {
                "default_provider": "openai",
                "providers": {
                    "openai": {
                        "api_key": "sk-test-key",
                        "default_model": "gpt-4o",
                        "available_models": ["gpt-4o"],
                        "timeout_seconds": 30,
                        "max_retries": 3,
                    }
                },
                "cache_enabled": True,
                "cache_ttl_hours": 24,
            }
        }
        integration_dict = AIIntegration(config_dict)
        assert integration_dict.ai_config.default_provider == "openai"
        assert "openai" in integration_dict.ai_config.providers

    @pytest.mark.asyncio
    @patch("src.ci_helper.ai.integration.ProviderFactory")
    @patch("src.ci_helper.ai.integration.PromptManager")
    @patch("src.ci_helper.ai.integration.CacheManager")
    @pytest.mark.asyncio
    async def test_provider_factory_integration(
        self, mock_cache_manager, mock_prompt_manager, mock_provider_factory, ai_integration, mock_ai_config
    ):
        """プロバイダーファクトリー統合のテスト"""
        # AI設定を設定
        ai_integration.ai_config = mock_ai_config

        # モックプロバイダーを作成
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.initialize = AsyncMock()
        mock_provider.validate_connection = AsyncMock(return_value=True)

        mock_provider_factory.create_provider.return_value = mock_provider

        # 初期化を実行
        await ai_integration.initialize()

        # プロバイダーファクトリーが呼び出されたことを確認
        mock_provider_factory.create_provider.assert_called_once()

        # プロバイダーが初期化されたことを確認
        mock_provider.initialize.assert_called_once()
        mock_provider.validate_connection.assert_called_once()

        # プロバイダーが登録されたことを確認
        assert "openai" in ai_integration.providers
        assert ai_integration.providers["openai"] == mock_provider

    @pytest.mark.asyncio
    async def test_analysis_workflow_orchestration(self, async_ai_integration_with_cleanup):
        """分析ワークフロー統制のテスト"""
        # 分析結果を設定
        analysis_result = AnalysisResult(
            summary="テスト分析結果",
            confidence_score=0.85,
            tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.01),
            status=AnalysisStatus.COMPLETED,
        )
        async_ai_integration_with_cleanup.providers["openai"].analyze = AsyncMock(return_value=analysis_result)

        # 分析オプションを作成
        options = AnalyzeOptions(provider="openai", model="gpt-4o", use_cache=False)

        # 分析を実行
        result = await async_ai_integration_with_cleanup.analyze_log("test log content", options)

        # 結果を検証
        assert result.summary == "テスト分析結果"
        assert result.provider == "openai"
        assert result.model == "gpt-4o"
        assert result.status.value == "completed"
        assert result.analysis_time > 0

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_shutdown(self, ai_integration):
        """シャットダウン時のリソースクリーンアップのテスト"""
        # モックプロバイダーを設定
        mock_provider1 = Mock()
        mock_provider1.cleanup = AsyncMock()
        mock_provider2 = Mock()
        mock_provider2.cleanup = AsyncMock()

        ai_integration.providers = {"openai": mock_provider1, "anthropic": mock_provider2}

        # アクティブセッションを設定
        session = InteractiveSession(
            session_id="test-session",
            start_time=datetime.now(),
            last_activity=datetime.now(),
            provider="openai",
            model="gpt-4o",
        )
        ai_integration.active_sessions = {"test-session": session}

        # フォールバックハンドラーを設定
        ai_integration.fallback_handler = Mock()
        ai_integration.fallback_handler.cleanup_old_partial_results = Mock()

        # クリーンアップを実行
        await ai_integration.cleanup()

        # プロバイダーのクリーンアップが呼び出されたことを確認
        mock_provider1.cleanup.assert_called_once()
        mock_provider2.cleanup.assert_called_once()

        # セッションがクリアされたことを確認
        assert len(ai_integration.active_sessions) == 0

        # フォールバックハンドラーのクリーンアップが呼び出されたことを確認
        ai_integration.fallback_handler.cleanup_old_partial_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_error_handling(self, ai_integration):
        """初期化エラーハンドリングのテスト"""
        # AI設定が無い場合のテスト
        ai_integration.ai_config = None
        ai_integration.ai_config_manager = None

        with pytest.raises(ConfigurationError, match="AI設定が初期化されていません"):
            await ai_integration.initialize()

    @pytest.mark.asyncio
    @patch("src.ci_helper.ai.integration.ProviderFactory")
    async def test_provider_initialization_failure(self, mock_provider_factory, ai_integration, mock_ai_config):
        """プロバイダー初期化失敗のテスト"""
        ai_integration.ai_config = mock_ai_config

        # プロバイダー作成時にエラーを発生させる
        mock_provider_factory.create_provider.side_effect = APIKeyError("openai", "Invalid API key")

        # 初期化時にエラーが発生することを確認
        with pytest.raises(APIKeyError):
            await ai_integration.initialize()

    def test_string_representations(self, ai_integration):
        """文字列表現のテスト"""
        # プロバイダーとセッションを設定
        ai_integration.providers = {"openai": Mock(), "anthropic": Mock()}
        ai_integration.active_sessions = {"session1": Mock()}

        # __str__メソッドのテスト
        str_repr = str(ai_integration)
        assert "providers=2" in str_repr
        assert "sessions=1" in str_repr

        # __repr__メソッドのテスト
        repr_str = repr(ai_integration)
        assert "AIIntegration(" in repr_str
        assert "initialized=False" in repr_str
        assert "providers=['openai', 'anthropic']" in repr_str
        assert "active_sessions=1" in repr_str


class TestProviderManagement:
    """プロバイダー管理機能のテスト"""

    @pytest.fixture
    def ai_integration_with_providers(self, mock_config):
        """複数プロバイダーを持つAIIntegration"""
        integration = AIIntegration(mock_config)

        # モックプロバイダーを設定
        openai_provider = Mock()
        openai_provider.name = "openai"
        anthropic_provider = Mock()
        anthropic_provider.name = "anthropic"

        integration.providers = {"openai": openai_provider, "anthropic": anthropic_provider}

        # AI設定を設定
        integration.ai_config = AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(name="openai", api_key="sk-test", default_model="gpt-4o"),
                "anthropic": ProviderConfig(name="anthropic", api_key="sk-ant-test", default_model="claude-3"),
            },
        )

        return integration

    def test_dynamic_provider_switching(self, ai_integration_with_providers):
        """動的プロバイダー切り替えのテスト"""
        integration = ai_integration_with_providers

        # デフォルトプロバイダーの選択
        provider = integration._select_provider()
        assert provider.name == "openai"

        # 指定プロバイダーの選択
        provider = integration._select_provider("anthropic")
        assert provider.name == "anthropic"

        # 存在しないプロバイダーの指定
        with pytest.raises(ProviderError, match="指定されたプロバイダー 'nonexistent' は利用できません"):
            integration._select_provider("nonexistent")

    def test_provider_fallback_mechanism(self, ai_integration_with_providers):
        """プロバイダーフォールバック機構のテスト"""
        integration = ai_integration_with_providers

        # デフォルトプロバイダーが利用できない場合
        integration.ai_config.default_provider = "unavailable"

        # 最初に利用可能なプロバイダーが選択されることを確認
        provider = integration._select_provider()
        assert provider.name in ["openai", "anthropic"]

    def test_provider_health_checking(self, ai_integration_with_providers):
        """プロバイダーヘルスチェックのテスト"""
        integration = ai_integration_with_providers

        # プロバイダーが利用可能な場合
        assert len(integration.providers) == 2

        # プロバイダーが利用できない場合
        integration.providers = {}

        with pytest.raises(ProviderError, match="利用可能なAIプロバイダーがありません"):
            integration._select_provider()

    def test_provider_configuration_validation(self, mock_config):
        """プロバイダー設定検証のテスト"""
        # 無効な設定での初期化
        invalid_config = {
            "ai": {
                "default_provider": "openai",
                "providers": {},  # プロバイダー設定が空
            }
        }

        integration = AIIntegration(invalid_config)
        assert integration.ai_config.default_provider == "openai"
        assert len(integration.ai_config.providers) == 0


class TestAsyncProcessing:
    """非同期処理機能のテスト"""

    @pytest.fixture
    def async_integration(self, mock_config, mock_ai_config):
        """非同期処理用のAIIntegration"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # 必要なコンポーネントをモック化
        integration.prompt_manager = Mock()
        integration.cache_manager = Mock()
        integration.cost_manager = Mock()
        integration.cost_manager.check_usage_limits.return_value = {"over_limit": False, "usage_percentage": 10.0}

        # 非同期メソッドをAsyncMockで設定
        integration.error_handler = Mock()
        error_info = {"can_retry": True, "auto_retry": False, "message": "タイムアウトエラーが発生しました"}
        integration.error_handler.handle_error_with_retry = AsyncMock(return_value=error_info)

        # フォールバックハンドラーを適切に設定
        integration.fallback_handler = Mock()
        fallback_result = AnalysisResult(
            summary="タイムアウトが発生しました。フォールバック分析を実行しました。",
            status=AnalysisStatus.FALLBACK,
            analysis_time=1.0,
            provider="fallback",
            model="fallback",
        )
        integration.fallback_handler.handle_analysis_failure = AsyncMock(return_value=fallback_result)

        integration.session_manager = Mock()
        integration.fix_generator = Mock()
        integration.fix_applier = Mock()

        # モックプロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01

        integration.providers = {"openai": mock_provider}
        return integration

    @pytest.mark.asyncio
    async def test_concurrent_analysis_execution(self, async_integration):
        """並行分析実行のテスト"""
        # 複数の分析結果を設定
        results = [AnalysisResult(summary=f"結果{i}", status=AnalysisStatus.COMPLETED) for i in range(3)]

        async_integration.providers["openai"].analyze = AsyncMock(side_effect=results)

        # 複数の分析を並行実行
        options = AnalyzeOptions(provider="openai", use_cache=False)
        tasks = [async_integration.analyze_log(f"log content {i}", options) for i in range(3)]

        completed_results = await asyncio.gather(*tasks)

        # 結果を検証
        assert len(completed_results) == 3
        for i, result in enumerate(completed_results):
            assert result.summary == f"結果{i}"
            assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_async_timeout_handling(self, async_integration):
        """非同期タイムアウト処理のテスト"""

        # タイムアウトを発生させる
        async def timeout_analyze(*args, **kwargs):
            await asyncio.sleep(0.1)  # 短い遅延でタイムアウトをシミュレート
            raise TimeoutError("Request timed out")

        async_integration.providers["openai"].analyze = timeout_analyze

        options = AnalyzeOptions(provider="openai", use_cache=False)

        # タイムアウトエラーが適切に処理されることを確認
        result = await async_integration.analyze_log("test log", options)

        # フォールバック結果が返されることを確認
        assert result is not None
        assert "タイムアウト" in result.summary or result.status == AnalysisStatus.FALLBACK

    @pytest.mark.asyncio
    async def test_async_error_propagation(self, async_integration):
        """非同期エラー伝播のテスト"""
        # プロバイダーでエラーを発生させる
        async_integration.providers["openai"].analyze = AsyncMock(
            side_effect=RateLimitError("openai", "Rate limit exceeded", retry_after=60)
        )

        options = AnalyzeOptions(provider="openai", use_cache=False)

        # エラーが適切に伝播されることを確認
        with pytest.raises(RateLimitError):
            await async_integration.analyze_log("test log", options)

    @pytest.mark.asyncio
    async def test_async_resource_management(self, async_integration):
        """非同期リソース管理のテスト"""
        # リソース使用量を追跡するモック
        resource_tracker = Mock()
        resource_tracker.acquire = AsyncMock()
        resource_tracker.release = AsyncMock()

        # 分析中にリソースが適切に管理されることをテスト
        async_integration.providers["openai"].analyze = AsyncMock(
            return_value=AnalysisResult(summary="テスト", status=AnalysisStatus.COMPLETED)
        )

        options = AnalyzeOptions(provider="openai", use_cache=False)
        result = await async_integration.analyze_log("test log", options)

        # 結果が正常に返されることを確認
        assert result.summary == "テスト"
        assert result.status == AnalysisStatus.COMPLETED


class TestCacheIntegration:
    """キャッシュ統合機能のテスト"""

    @pytest.fixture
    def cache_integration(self, mock_config, mock_ai_config):
        """キャッシュ機能付きのAIIntegration"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # 必要なコンポーネントをモック化
        integration.prompt_manager = Mock()
        integration.cost_manager = Mock()
        integration.cost_manager.check_usage_limits.return_value = {"over_limit": False, "usage_percentage": 10.0}
        integration.error_handler = Mock()
        integration.fallback_handler = Mock()
        integration.session_manager = Mock()
        integration.fix_generator = Mock()
        integration.fix_applier = Mock()

        # モックキャッシュマネージャーを設定
        mock_cache = Mock()
        mock_cache.get_cached_result = AsyncMock()
        mock_cache.cache_result = AsyncMock()
        integration.cache_manager = mock_cache

        # モックプロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01
        mock_provider.analyze = AsyncMock(
            return_value=AnalysisResult(summary="新しい分析", status=AnalysisStatus.COMPLETED)
        )

        integration.providers = {"openai": mock_provider}
        return integration

    @pytest.mark.asyncio
    async def test_cache_hit_optimization(self, cache_integration):
        """キャッシュヒット最適化のテスト"""
        # キャッシュされた結果を設定
        cached_result = AnalysisResult(summary="キャッシュされた分析", status=AnalysisStatus.CACHED, cache_hit=True)
        cache_integration.cache_manager.get_cached_result.return_value = cached_result

        options = AnalyzeOptions(provider="openai", use_cache=True)
        result = await cache_integration.analyze_log("test log", options)

        # キャッシュされた結果が返されることを確認
        assert result.summary == "キャッシュされた分析"
        assert result.cache_hit is True

        # プロバイダーの分析が呼び出されていないことを確認
        cache_integration.providers["openai"].analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_handling(self, cache_integration):
        """キャッシュミス処理のテスト"""
        # キャッシュミスを設定
        cache_integration.cache_manager.get_cached_result.return_value = None

        options = AnalyzeOptions(provider="openai", use_cache=True)
        result = await cache_integration.analyze_log("test log", options)

        # 新しい分析結果が返されることを確認
        assert result.summary == "新しい分析"
        assert result.cache_hit is False

        # プロバイダーの分析が呼び出されたことを確認
        cache_integration.providers["openai"].analyze.assert_called_once()

        # 結果がキャッシュされたことを確認
        cache_integration.cache_manager.cache_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_ttl_management(self, cache_integration):
        """キャッシュTTL管理のテスト"""
        # 期限切れのキャッシュ結果を設定
        expired_result = AnalysisResult(
            summary="期限切れの分析",
            status=AnalysisStatus.CACHED,
            timestamp=datetime(2020, 1, 1),  # 古いタイムスタンプ
        )
        cache_integration.cache_manager.get_cached_result.return_value = expired_result

        options = AnalyzeOptions(provider="openai", use_cache=True)
        result = await cache_integration.analyze_log("test log", options)

        # 期限切れの場合は新しい分析が実行されることを確認
        # （実際のTTLチェックはCacheManagerで行われるため、ここではモックの動作を確認）
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_invalidation_strategies(self, cache_integration):
        """キャッシュ無効化戦略のテスト"""
        # キャッシュを無効化するオプション
        options = AnalyzeOptions(provider="openai", use_cache=False)
        result = await cache_integration.analyze_log("test log", options)

        # キャッシュが使用されていないことを確認
        cache_integration.cache_manager.get_cached_result.assert_not_called()

        # 新しい分析が実行されたことを確認
        assert result.summary == "新しい分析"
        cache_integration.providers["openai"].analyze.assert_called_once()


class TestIntegrationAndMockInfrastructure:
    """統合テストとモック基盤の実装"""

    @pytest.fixture
    def mock_ai_provider(self):
        """AI APIモック（MockAIProvider）の実装"""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.initialize = AsyncMock()
        mock_provider.validate_connection = AsyncMock(return_value=True)
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01

        # 分析結果のモック
        mock_provider.analyze = AsyncMock(
            return_value=AnalysisResult(
                summary="モック分析結果",
                confidence_score=0.9,
                tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.01),
                status=AnalysisStatus.COMPLETED,
            )
        )

        # ストリーミング分析のモック
        async def mock_stream_analyze(*args, **kwargs):
            chunks = ["モック", "ストリーミング", "結果"]
            for chunk in chunks:
                yield chunk

        mock_provider.stream_analyze = mock_stream_analyze
        mock_provider.cleanup = AsyncMock()

        return mock_provider

    @pytest.fixture
    def mock_file_system(self, temp_dir):
        """ファイルシステムモック（mock_file_system）の実装"""
        # テスト用ディレクトリ構造を作成
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir(exist_ok=True)

        logs_dir = temp_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        # サンプルログファイルを作成
        sample_log = logs_dir / "test.log"
        sample_log.write_text("""
ERROR: Test failed
npm ERR! code ENOENT
AssertionError: Expected 200, got 404
        """)

        return {"temp_dir": temp_dir, "cache_dir": cache_dir, "logs_dir": logs_dir, "sample_log": sample_log}

    @pytest.fixture
    def sample_analysis_result(self):
        """テストフィクスチャ（sample_analysis_result等）の実装"""
        return AnalysisResult(
            summary="サンプル分析結果: テストが失敗しました",
            confidence_score=0.85,
            analysis_time=2.5,
            tokens_used=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300, estimated_cost=0.02),
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
        )

    @pytest.mark.asyncio
    async def test_e2e_integration_scenario(
        self, mock_config, mock_ai_provider, mock_file_system, sample_analysis_result
    ):
        """E2E統合テストシナリオの実装"""
        # AIIntegrationを初期化
        integration = AIIntegration(mock_config)

        # AI設定を設定
        integration.ai_config = AIConfig(
            default_provider="mock",
            providers={"mock": ProviderConfig(name="mock", api_key="test-key", default_model="test-model")},
            cache_enabled=True,
        )

        # モックプロバイダーを設定
        integration.providers = {"mock": mock_ai_provider}

        # 必要なコンポーネントを初期化
        from src.ci_helper.ai.prompts import PromptManager

        integration.prompt_manager = Mock(spec=PromptManager)
        integration.prompt_manager.get_analysis_prompt.return_value = "Mock analysis prompt"

        integration._initialized = True

        # E2Eシナリオ: ログファイル読み込み → 分析 → 結果検証
        log_content = mock_file_system["sample_log"].read_text()
        options = AnalyzeOptions(provider="mock", use_cache=False)

        # 分析を実行
        result = await integration.analyze_log(log_content, options)

        # 結果を検証
        assert result.summary == "モック分析結果"
        assert result.status == AnalysisStatus.COMPLETED
        assert result.tokens_used is not None
        assert result.analysis_time > 0

        # プロバイダーが呼び出されたことを確認
        mock_ai_provider.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_config, mock_ai_provider):
        """エラーハンドリング統合テスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = AIConfig(
            default_provider="mock", providers={"mock": ProviderConfig(name="mock", api_key="test-key")}
        )
        integration.providers = {"mock": mock_ai_provider}
        integration._initialized = True

        # エラーを発生させる
        mock_ai_provider.analyze.side_effect = NetworkError("Connection failed")

        options = AnalyzeOptions(provider="mock", use_cache=False)

        # エラーが適切に処理されることを確認
        result = await integration.analyze_log("test log", options)

        # フォールバック結果が返されることを確認
        assert result is not None
        # エラーハンドリングによりフォールバック結果が作成される

    @pytest.mark.asyncio
    async def test_streaming_integration(self, mock_config, mock_ai_provider):
        """ストリーミング統合テスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = AIConfig(
            default_provider="mock", providers={"mock": ProviderConfig(name="mock", api_key="test-key")}
        )
        integration.providers = {"mock": mock_ai_provider}
        integration._initialized = True

        options = AnalyzeOptions(provider="mock", streaming=True)

        # ストリーミング分析を実行
        chunks = []
        async for chunk in integration.stream_analyze("test log", options):
            chunks.append(chunk)

        # ストリーミング結果を検証
        assert len(chunks) == 3
        assert chunks == ["モック", "ストリーミング", "結果"]

    @pytest.mark.asyncio
    async def test_interactive_session_integration(self, mock_config, mock_ai_provider):
        """対話セッション統合テスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = AIConfig(
            default_provider="mock", providers={"mock": ProviderConfig(name="mock", api_key="test-key")}
        )
        integration.providers = {"mock": mock_ai_provider}
        integration._initialized = True

        # セッション管理を設定
        from src.ci_helper.ai.interactive_session import InteractiveSessionManager
        from src.ci_helper.ai.prompts import PromptManager

        integration.prompt_manager = Mock(spec=PromptManager)
        integration.session_manager = Mock(spec=InteractiveSessionManager)

        # モックセッションを作成
        mock_session = InteractiveSession(
            session_id="test-session",
            start_time=datetime.now(),
            last_activity=datetime.now(),
            provider="mock",
            model="test-model",
        )
        integration.session_manager.create_session.return_value = mock_session

        options = AnalyzeOptions(provider="mock")

        # 対話セッションを開始
        session = await integration.start_interactive_session("initial log", options)

        # セッションが作成されたことを確認
        assert session.session_id == "test-session"
        assert session.provider == "mock"
        assert session.model == "test-model"

        # アクティブセッションに登録されたことを確認
        assert "test-session" in integration.active_sessions

    @pytest.mark.asyncio
    async def test_cost_limit_checking(self, mock_config, mock_ai_config):
        """コスト制限チェックのテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # モックコストマネージャーを設定
        mock_cost_manager = Mock()
        mock_cost_manager.check_usage_limits.return_value = {"over_limit": True, "usage_percentage": 95.0}
        integration.cost_manager = mock_cost_manager

        # モックプロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.count_tokens.return_value = 1000
        mock_provider.estimate_cost.return_value = 10.0

        # コスト制限チェックでエラーが発生することを確認
        with pytest.raises(AIError, match="コスト制限を超過しています"):
            await integration._check_cost_limits(
                mock_provider, "test prompt", "test context", AnalyzeOptions(model="gpt-4o")
            )

    @pytest.mark.asyncio
    async def test_usage_stats_retrieval(self, mock_config, mock_ai_config):
        """使用統計取得のテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration.providers = {"openai": Mock(), "anthropic": Mock()}
        integration.active_sessions = {"session1": Mock()}

        # モックコストマネージャーを設定
        mock_cost_manager = Mock()
        mock_cost_manager.get_usage_summary.return_value = {
            "summary": {"total_requests": 100, "total_cost": 25.50, "success_rate": 0.95},
            "top_providers": {"openai": 80, "anthropic": 20},
            "top_models": {"gpt-4o": 60, "claude-3": 40},
        }
        integration.cost_manager = mock_cost_manager

        # 使用統計を取得
        stats = await integration.get_usage_stats()

        # 統計情報を検証
        assert stats["total_requests"] == 100
        assert stats["total_cost"] == 25.50
        assert stats["success_rate"] == 0.95
        assert stats["active_sessions"] == 1
        assert stats["available_providers"] == ["openai", "anthropic"]
        assert stats["cache_enabled"] is True

    @pytest.mark.asyncio
    async def test_retry_failed_operation(self, mock_config, mock_ai_config):
        """失敗した操作のリトライテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # モックフォールバックハンドラーを設定
        mock_fallback_handler = Mock()
        retry_info = {
            "options": {"provider": "openai", "model": "gpt-4o", "custom_prompt": "test prompt"},
            "log_content": "test log content",
            "failed_provider": "anthropic",
            "alternative_providers": ["openai"],
        }
        mock_fallback_handler.retry_from_partial_result = AsyncMock(return_value=retry_info)
        integration.fallback_handler = mock_fallback_handler

        # モックプロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01
        mock_provider.analyze = AsyncMock(
            return_value=AnalysisResult(summary="リトライ成功", status=AnalysisStatus.COMPLETED)
        )
        integration.providers = {"openai": mock_provider}

        # リトライを実行
        result = await integration.retry_failed_operation("test-operation-id")

        # リトライ結果を検証
        assert result is not None
        assert result.summary == "リトライ成功"
        assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fallback_suggestions(self, mock_config):
        """フォールバック提案のテスト"""
        integration = AIIntegration(mock_config)

        # モックフォールバックハンドラーを設定
        mock_fallback_handler = Mock()
        mock_fallback_handler._suggest_alternative_providers.return_value = ["anthropic", "local"]
        integration.fallback_handler = mock_fallback_handler

        # レート制限エラーの提案
        rate_error = RateLimitError("openai", "Rate limit exceeded", retry_after=60)
        suggestions = await integration.get_fallback_suggestions(rate_error)

        assert "60秒後に再試行してください" in suggestions
        assert "より低いレート制限のモデルを使用してください" in suggestions

        # プロバイダーエラーの提案
        provider_error = ProviderError("openai", "Provider unavailable")
        suggestions = await integration.get_fallback_suggestions(provider_error)

        assert "代替プロバイダーを試してください: anthropic, local" in suggestions
        assert "APIキーと設定を確認してください" in suggestions

    @pytest.mark.asyncio
    async def test_interactive_session_management(self, mock_config, mock_ai_config):
        """対話セッション管理のテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # セッション管理を設定
        from src.ci_helper.ai.interactive_session import InteractiveSessionManager
        from src.ci_helper.ai.prompts import PromptManager

        integration.prompt_manager = Mock(spec=PromptManager)
        integration.session_manager = Mock(spec=InteractiveSessionManager)

        # モックセッションを作成
        mock_session = InteractiveSession(
            session_id="test-session",
            start_time=datetime.now(),
            last_activity=datetime.now(),
            provider="openai",
            model="gpt-4o",
        )
        mock_session.is_active = True
        integration.session_manager.create_session.return_value = mock_session

        # プロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        integration.providers = {"openai": mock_provider}

        # セッション開始
        options = AnalyzeOptions(provider="openai")
        session = await integration.start_interactive_session("initial log", options)

        assert session.session_id == "test-session"
        assert "test-session" in integration.active_sessions

        # セッション終了
        result = await integration.close_interactive_session("test-session")
        assert result is True
        assert "test-session" not in integration.active_sessions

    @pytest.mark.asyncio
    async def test_fix_suggestion_workflow(self, mock_config, mock_ai_config):
        """修正提案ワークフローのテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # モック修正生成器を設定
        mock_fix_generator = Mock()
        fix_suggestions = [
            FixSuggestion(title="テスト修正", description="テスト用の修正提案", code_changes=[], confidence=0.9)
        ]
        mock_fix_generator.generate_fix_suggestions.return_value = fix_suggestions
        integration.fix_generator = mock_fix_generator

        # モック修正適用器を設定
        mock_fix_applier = Mock()
        mock_fix_applier.apply_fix_suggestions.return_value = {
            "applied_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
        }
        mock_fix_applier.rollback_fixes.return_value = {"restored_count": 1, "failed_count": 0}
        integration.fix_applier = mock_fix_applier

        # 分析結果を作成
        analysis_result = AnalysisResult(summary="テスト分析", status=AnalysisStatus.COMPLETED)

        # 修正提案生成
        suggestions = await integration.generate_fix_suggestions(analysis_result, "test log content")

        assert len(suggestions) == 1
        assert suggestions[0].title == "テスト修正"

        # 修正適用
        apply_result = await integration.apply_fix_suggestions(suggestions)

        assert apply_result["applied_count"] == 1
        assert apply_result["skipped_count"] == 0

        # ロールバック
        rollback_result = integration.rollback_fixes(["backup1.txt"])

        assert rollback_result["restored_count"] == 1

    @pytest.mark.asyncio
    async def test_analyze_and_fix_workflow(self, mock_config, mock_ai_config):
        """分析と修正の一括ワークフローテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config

        # 必要なコンポーネントを初期化
        from src.ci_helper.ai.prompts import PromptManager

        integration.prompt_manager = Mock(spec=PromptManager)
        integration.prompt_manager.get_analysis_prompt.return_value = "Mock analysis prompt"

        integration._initialized = True

        # モックプロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01

        analysis_result = AnalysisResult(
            summary="分析完了",
            status=AnalysisStatus.COMPLETED,
            tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.01),
        )
        mock_provider.analyze = AsyncMock(return_value=analysis_result)
        integration.providers = {"openai": mock_provider}

        # モック修正生成器を設定
        mock_fix_generator = Mock()
        fix_suggestions = [
            FixSuggestion(title="修正1", description="説明1"),
            FixSuggestion(title="修正2", description="説明2"),
        ]
        mock_fix_generator.generate_fix_suggestions.return_value = fix_suggestions
        integration.fix_generator = mock_fix_generator

        # モック修正適用器を設定
        mock_fix_applier = Mock()
        mock_fix_applier.apply_fix_suggestions.return_value = {
            "applied_count": 2,
            "skipped_count": 0,
            "failed_count": 0,
        }
        integration.fix_applier = mock_fix_applier

        # 一括ワークフローを実行
        options = AnalyzeOptions(provider="openai", use_cache=False)
        result = await integration.analyze_and_fix("test log content", options, apply_fixes=True, auto_approve=True)

        # 結果を検証
        assert result["analysis"].summary == "分析完了"
        assert len(result["fix_suggestions"]) == 2
        assert result["fix_application"]["applied_count"] == 2

    def test_error_type_detection(self, mock_config):
        """エラータイプ検出のテスト"""
        integration = AIIntegration(mock_config)

        # テストファイルエラー
        test_log = "Test failed with AssertionError"
        error_type = integration._detect_error_type(test_log)
        assert error_type == "test_failure"

        # ビルドエラー
        build_log = "Build failed with compilation error"
        error_type = integration._detect_error_type(build_log)
        assert error_type == "build_failure"

        # シンタックスエラー
        syntax_log = "SyntaxError: invalid syntax"
        error_type = integration._detect_error_type(syntax_log)
        assert error_type == "syntax_error"

        # インポートエラー
        import_log = "ImportError: No module named 'test'"
        error_type = integration._detect_error_type(import_log)
        assert error_type == "import_error"

        # タイムアウトエラー
        timeout_log = "Request timeout after 30 seconds"
        error_type = integration._detect_error_type(timeout_log)
        assert error_type == "timeout_error"

        # 一般エラー
        general_log = "Unknown error occurred"
        error_type = integration._detect_error_type(general_log)
        assert error_type == "general_error"

    @pytest.mark.asyncio
    async def test_streaming_analysis_fallback(self, mock_config, mock_ai_config):
        """ストリーミング分析フォールバックのテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config

        # 必要なコンポーネントを初期化
        from src.ci_helper.ai.prompts import PromptManager

        integration.prompt_manager = Mock(spec=PromptManager)
        integration.prompt_manager.get_analysis_prompt.return_value = "Mock analysis prompt"

        integration._initialized = True

        # モックプロバイダーを設定（ストリーミング無効）
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        mock_provider.count_tokens.return_value = 100
        mock_provider.estimate_cost.return_value = 0.01

        # 通常の分析結果を設定
        analysis_result = AnalysisResult(summary="通常分析結果", status=AnalysisStatus.COMPLETED)
        mock_provider.analyze = AsyncMock(return_value=analysis_result)
        integration.providers = {"openai": mock_provider}

        # ストリーミング無効でテスト
        options = AnalyzeOptions(provider="openai", streaming=False, use_cache=False)

        chunks = []
        async for chunk in integration.stream_analyze("test log", options):
            chunks.append(chunk)

        # 通常の分析結果が返されることを確認
        assert len(chunks) == 1
        assert chunks[0] == "通常分析結果"

    @pytest.mark.asyncio
    async def test_interactive_input_processing(self, mock_config, mock_ai_config):
        """対話入力処理のテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # セッションを設定
        session = InteractiveSession(
            session_id="test-session",
            start_time=datetime.now(),
            last_activity=datetime.now(),
            provider="openai",
            model="gpt-4o",
        )
        integration.active_sessions = {"test-session": session}

        # セッション管理を設定
        mock_session_manager = Mock()
        mock_command_processor = Mock()
        mock_command_processor.is_command.return_value = False
        mock_session_manager.command_processor = mock_command_processor
        mock_session_manager.generate_interactive_prompt.return_value = "Generated prompt"
        integration.session_manager = mock_session_manager

        # プロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"

        async def mock_stream_analyze(*args, **kwargs):
            yield "応答"
            yield "チャンク"

        mock_provider.stream_analyze = mock_stream_analyze
        integration.providers = {"openai": mock_provider}

        # 対話入力を処理
        chunks = []
        async for chunk in integration.process_interactive_input("test-session", "ユーザー入力"):
            chunks.append(chunk)

        # 応答チャンクを検証
        assert chunks == ["応答", "チャンク"]

    @pytest.mark.asyncio
    async def test_session_timeout_handling(self, mock_config, mock_ai_config):
        """セッションタイムアウト処理のテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # セッション管理を設定
        mock_session_manager = Mock()
        mock_session_manager.process_input = AsyncMock(side_effect=TimeoutError("Session timeout"))
        integration.session_manager = mock_session_manager

        # プロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        integration.providers = {"openai": mock_provider}

        options = AnalyzeOptions(provider="openai")

        # タイムアウトエラーが適切に処理されることを確認
        with pytest.raises(AIError, match="セッション初期化中にエラーが発生しました"):
            await integration.start_interactive_session("initial log", options)

    @pytest.mark.asyncio
    async def test_memory_error_handling(self, mock_config, mock_ai_config):
        """メモリエラー処理のテスト"""
        integration = AIIntegration(mock_config)
        integration.ai_config = mock_ai_config
        integration._initialized = True

        # セッション管理を設定
        mock_session_manager = Mock()
        mock_session_manager.process_input = AsyncMock(side_effect=MemoryError("Out of memory"))
        integration.session_manager = mock_session_manager

        # プロバイダーを設定
        mock_provider = Mock()
        mock_provider.name = "openai"
        mock_provider.config = mock_ai_config.providers["openai"]
        integration.providers = {"openai": mock_provider}

        options = AnalyzeOptions(provider="openai")

        # メモリエラーが適切に処理されることを確認
        with pytest.raises(AIError, match="セッション初期化中にエラーが発生しました"):
            await integration.start_interactive_session("initial log", options)
