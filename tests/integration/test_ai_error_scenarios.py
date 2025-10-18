"""
AI統合のエラーシナリオテスト

ネットワークエラー、タイムアウト、設定エラーなどの異常系をテストします。
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from src.ci_helper.ai.exceptions import (
    CacheError,
    ConfigurationError,
    CostLimitError,
    NetworkError,
    ProviderError,
    TokenLimitError,
)
from src.ci_helper.ai.integration import AIIntegration
from src.ci_helper.ai.models import AIConfig, AnalyzeOptions, ProviderConfig
from src.ci_helper.utils.config import Config


class TestNetworkErrorScenarios:
    """ネットワークエラーシナリオのテスト"""

    @pytest.fixture
    def mock_ai_config(self):
        """モックAI設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=30,
                    max_retries=3,
                )
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={"monthly_usd": 50.0, "per_request_usd": 1.0},
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=".ci-helper/cache",
        )

    @pytest.mark.asyncio
    async def test_network_timeout_error(self, mock_ai_config):
        """ネットワークタイムアウトエラーのテスト"""
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(side_effect=TimeoutError("Request timeout"))
            mock_openai.return_value = mock_client

            ai_integration = AIIntegration(mock_ai_config)
            await ai_integration.initialize()

            options = AnalyzeOptions(
                provider="openai",
                model="gpt-4o",
                use_cache=False,
                streaming=False,
            )

            with pytest.raises(NetworkError):
                await ai_integration.analyze_log("test log", options)

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_ai_config):
        """接続エラーのテスト"""

        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(side_effect=aiohttp.ClientConnectorError(Mock(), Mock()))
            mock_openai.return_value = mock_client

            ai_integration = AIIntegration(mock_ai_config)
            await ai_integration.initialize()

            options = AnalyzeOptions(
                provider="openai",
                model="gpt-4o",
                use_cache=False,
                streaming=False,
            )

            with pytest.raises(NetworkError):
                await ai_integration.analyze_log("test log", options)

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, mock_ai_config):
        """リトライメカニズムのテスト"""
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()

            # 最初の2回は失敗、3回目は成功
            call_count = 0

            async def mock_create(*_args, **_kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise NetworkError("Temporary network error")

                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "成功した分析結果"
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                return mock_response

            mock_client.chat.completions.create = mock_create
            mock_openai.return_value = mock_client

            ai_integration = AIIntegration(mock_ai_config)
            await ai_integration.initialize()

            options = AnalyzeOptions(
                provider="openai",
                model="gpt-4o",
                use_cache=False,
                streaming=False,
            )

            # リトライにより最終的に成功することを確認
            result = await ai_integration.analyze_log("test log", options)
            assert result.summary == "成功した分析結果"
            assert call_count == 3  # 3回呼び出されたことを確認


class TestConfigurationErrorScenarios:
    """設定エラーシナリオのテスト"""

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        """APIキー未設定エラーのテスト"""
        # 空のAPIキーを持つプロバイダー設定
        openai_config = ProviderConfig(
            name="openai",
            api_key="",  # 空のAPIキー
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
            timeout_seconds=30,
            max_retries=3,
        )

        ai_config_without_key = AIConfig(
            default_provider="openai",
            providers={"openai": openai_config},
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
        )

        ai_integration = AIIntegration(ai_config_without_key)

        with pytest.raises(ConfigurationError):
            await ai_integration.initialize()

    @pytest.mark.asyncio
    async def test_invalid_provider_config(self):
        """無効なプロバイダー設定のテスト"""
        invalid_ai_config = AIConfig(
            default_provider="nonexistent",
            providers={},  # 空のプロバイダー設定
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
        )

        ai_integration = AIIntegration(invalid_ai_config)

        with pytest.raises(ProviderError):
            await ai_integration.initialize()

    @pytest.mark.asyncio
    async def test_invalid_model_selection(self):
        """無効なモデル選択のテスト"""
        openai_config = ProviderConfig(
            name="openai",
            api_key="sk-test-key-123",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
            timeout_seconds=30,
            max_retries=3,
        )

        ai_config = AIConfig(
            default_provider="openai",
            providers={"openai": openai_config},
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
        )

        with patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager:
            mock_config_manager.return_value.get_ai_config.return_value = ai_config

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_openai.return_value = mock_client

                config = Config()
                ai_integration = AIIntegration(config)
                await ai_integration.initialize()

                # 利用不可能なモデルを指定
                options = AnalyzeOptions(
                    provider="openai",
                    model="invalid-model",
                    use_cache=False,
                    streaming=False,
                )

                with pytest.raises(ProviderError):
                    await ai_integration.analyze_log("test log", options)


class TestTokenAndCostLimitScenarios:
    """トークンとコスト制限シナリオのテスト"""

    @pytest.fixture
    def cost_limited_config(self):
        """コスト制限付き設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=30,
                    max_retries=3,
                )
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={
                "monthly_usd": 1.0,  # 非常に低い制限
                "per_request_usd": 0.001,
            },
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=".ci-helper/cache",
        )

    @pytest.mark.asyncio
    async def test_token_limit_exceeded(self, cost_limited_config):
        """トークン制限超過のテスト"""
        # 非常に長いログ（トークン制限を超える）
        very_long_log = "ERROR: " + "A" * 100000  # 約10万文字

        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=Mock())
            mock_openai.return_value = mock_client

            # count_tokensメソッドをモックして制限を超える値を返す
            with patch("src.ci_helper.ai.providers.openai.OpenAIProvider.count_tokens", return_value=150000):
                ai_integration = AIIntegration(cost_limited_config)

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                # トークン制限チェックが実装されている場合
                with pytest.raises(TokenLimitError):
                    await ai_integration.analyze_log(very_long_log, options)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Cost limit validation not yet implemented in integration layer")
    async def test_cost_limit_exceeded(self, cost_limited_config):
        """コスト制限超過のテスト"""
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=Mock())
            mock_openai.return_value = mock_client

            with patch("src.ci_helper.ai.cost_manager.CostManager") as mock_cost_manager_class:
                mock_cost_manager = Mock()
                mock_cost_manager.validate_request_cost.side_effect = CostLimitError(
                    current_cost=2.0, limit=1.0, provider="openai"
                )
                mock_cost_manager_class.return_value = mock_cost_manager

                ai_integration = AIIntegration(cost_limited_config)

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                with pytest.raises(CostLimitError):
                    await ai_integration.analyze_log("test log", options)


class TestCacheErrorScenarios:
    """キャッシュエラーシナリオのテスト"""

    @pytest.fixture
    def cache_enabled_config(self):
        """キャッシュ有効設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=30,
                    max_retries=3,
                )
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={},
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=".ci-helper/cache",
        )

    @pytest.mark.asyncio
    async def test_cache_write_error(self, cache_enabled_config):
        """キャッシュ書き込みエラーのテスト"""
        with patch("src.ci_helper.ai.cache.ResponseCache") as mock_cache_class:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)  # キャッシュミス
            mock_cache.set = AsyncMock(side_effect=CacheError("Disk full"))
            mock_cache_class.return_value = mock_cache

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "分析結果"
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(cache_enabled_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=True,
                    streaming=False,
                )

                # キャッシュエラーが発生しても分析は継続される
                result = await ai_integration.analyze_log("test log", options)
                assert result.summary == "分析結果"

    @pytest.mark.asyncio
    async def test_cache_corruption_recovery(self, cache_enabled_config):
        """キャッシュ破損からの復旧テスト"""
        with patch("src.ci_helper.ai.cache.ResponseCache") as mock_cache_class:
            mock_cache = Mock()
            # 破損したキャッシュデータを返す
            mock_cache.get = AsyncMock(side_effect=CacheError("Corrupted cache data"))
            mock_cache.set = AsyncMock()
            mock_cache_class.return_value = mock_cache

            with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "新しい分析結果"
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                ai_integration = AIIntegration(cache_enabled_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=True,
                    streaming=False,
                )

                # キャッシュ破損時は新しい分析を実行
                result = await ai_integration.analyze_log("test log", options)
                assert result.summary == "新しい分析結果"


class TestInteractiveSessionErrorScenarios:
    """対話セッションエラーシナリオのテスト"""

    @pytest.fixture
    def interactive_config(self):
        """対話セッション設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        return AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                    timeout_seconds=30,
                    max_retries=3,
                )
            },
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={},
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=".ci-helper/cache",
        )

    @pytest.mark.asyncio
    async def test_session_timeout(self, interactive_config):
        """セッションタイムアウトのテスト"""
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=Mock())
            mock_openai.return_value = mock_client

            with patch("src.ci_helper.ai.interactive_session.InteractiveSessionManager") as mock_session_class:
                mock_session_manager = Mock()
                mock_session_manager.create_session = Mock()
                mock_session_manager.process_input = AsyncMock(side_effect=TimeoutError("Session timeout"))
                mock_session_class.return_value = mock_session_manager

                ai_integration = AIIntegration(interactive_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                # セッションタイムアウトが適切に処理されることを確認
                with pytest.raises(asyncio.TimeoutError):
                    await ai_integration.start_interactive_session("initial log", options)

    @pytest.mark.asyncio
    async def test_session_memory_overflow(self, interactive_config):
        """セッションメモリオーバーフローのテスト"""
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=Mock())
            mock_openai.return_value = mock_client

            with patch("src.ci_helper.ai.interactive_session.InteractiveSessionManager") as mock_session_class:
                mock_session_manager = Mock()
                mock_session_manager.create_session = Mock()
                mock_session_manager.process_input = AsyncMock(side_effect=MemoryError("Session memory overflow"))
                mock_session_class.return_value = mock_session_manager

                ai_integration = AIIntegration(interactive_config)
                await ai_integration.initialize()

                options = AnalyzeOptions(
                    provider="openai",
                    model="gpt-4o",
                    use_cache=False,
                    streaming=False,
                )

                # メモリオーバーフローが適切に処理されることを確認
                with pytest.raises(MemoryError):
                    await ai_integration.start_interactive_session("initial log", options)
