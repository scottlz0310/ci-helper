"""
AIプロバイダーのテスト

各AIプロバイダー（OpenAI、Anthropic、ローカルLLM）の機能をテストします。
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ci_helper.ai.exceptions import APIKeyError, ProviderError, RateLimitError
from src.ci_helper.ai.models import AnalysisResult, AnalyzeOptions, ProviderConfig
from src.ci_helper.ai.providers.anthropic import AnthropicProvider
from src.ci_helper.ai.providers.local import LocalLLMProvider
from src.ci_helper.ai.providers.openai import OpenAIProvider


class TestAIProviderBase:
    """AIProvider基底クラスのテスト"""

    def test_provider_initialization(self):
        """プロバイダー初期化のテスト"""
        config = ProviderConfig(
            name="test",
            api_key="test-key",
            base_url="https://api.test.com",
            default_model="test-model",
            available_models=["test-model"],
            timeout_seconds=30,
            max_retries=3,
        )

        # 抽象クラスなので直接インスタンス化はできないが、設定は確認できる
        assert config.name == "test"
        assert config.api_key == "test-key"
        assert config.default_model == "test-model"


class TestOpenAIProvider:
    """OpenAIプロバイダーのテスト"""

    @pytest.fixture
    def openai_config(self):
        """OpenAI設定"""
        return ProviderConfig(
            name="openai",
            api_key="sk-test-key-123",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
            timeout_seconds=30,
            max_retries=3,
        )

    @pytest.fixture
    def openai_provider(self, openai_config):
        """OpenAIプロバイダー"""
        return OpenAIProvider(openai_config)

    @pytest.fixture
    def analyze_options(self):
        """分析オプション"""
        return AnalyzeOptions(
            provider="openai",
            model="gpt-4o",
            use_cache=True,
            streaming=False,
            custom_prompt=None,
        )

    def test_openai_provider_initialization(self, openai_provider):
        """OpenAIプロバイダー初期化のテスト"""
        assert openai_provider.name == "openai"
        assert openai_provider.config.api_key == "sk-test-key-123"
        assert openai_provider.config.default_model == "gpt-4o"

    def test_model_limits(self, openai_provider):
        """モデル制限のテスト"""
        assert OpenAIProvider.MODEL_LIMITS["gpt-4o"] == 128000
        assert OpenAIProvider.MODEL_LIMITS["gpt-4o-mini"] == 128000
        assert OpenAIProvider.MODEL_LIMITS["gpt-4"] == 8192

    def test_model_costs(self, openai_provider):
        """モデルコストのテスト"""
        gpt4o_cost = OpenAIProvider.MODEL_COSTS["gpt-4o"]
        assert gpt4o_cost["input"] == 0.0025
        assert gpt4o_cost["output"] == 0.01

        gpt4o_mini_cost = OpenAIProvider.MODEL_COSTS["gpt-4o-mini"]
        assert gpt4o_mini_cost["input"] == 0.00015
        assert gpt4o_mini_cost["output"] == 0.0006

    def test_estimate_cost(self, openai_provider):
        """コスト推定のテスト"""
        # gpt-4oで1000入力トークン、500出力トークンの場合
        cost = openai_provider.estimate_cost(1000, 500, "gpt-4o")
        expected = (1000 * 0.0025 / 1000) + (500 * 0.01 / 1000)  # 0.0025 + 0.005 = 0.0075
        assert cost == expected

    def test_get_available_models(self, openai_provider):
        """利用可能モデル取得のテスト"""
        models = openai_provider.get_available_models()
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models

    def test_validate_model(self, openai_provider):
        """モデル検証のテスト"""
        # 有効なモデル
        assert openai_provider.validate_model("gpt-4o") is True
        assert openai_provider.validate_model("gpt-4o-mini") is True

        # 無効なモデル
        assert openai_provider.validate_model("invalid-model") is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, openai_provider):
        """初期化成功のテスト"""
        # 初期状態では_clientはNone
        assert openai_provider._client is None

        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # validate_connectionをモック
            with patch.object(openai_provider, "validate_connection", return_value=True) as mock_validate:
                await openai_provider.initialize()

                assert openai_provider._client is not None
                mock_openai.assert_called_once_with(
                    api_key="sk-test-key-123",
                    timeout=30,
                    max_retries=3,
                )
                mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_invalid_api_key(self, openai_config):
        """無効なAPIキーでの初期化テスト"""
        openai_config.api_key = "invalid-key"
        provider = OpenAIProvider(openai_config)

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # validate_connectionでAPIKeyErrorを発生させる
            with patch.object(provider, "validate_connection", side_effect=APIKeyError("openai", "Invalid API key")):
                with pytest.raises(ProviderError):  # initializeはProviderErrorでラップする
                    await provider.initialize()

    @pytest.mark.asyncio
    async def test_analyze_success(self, openai_provider, analyze_options):
        """分析成功のテスト"""
        # モックレスポンス
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "分析結果: テストが失敗しました"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            result = await openai_provider.analyze("分析してください", "ログ内容", analyze_options)

            assert isinstance(result, AnalysisResult)
            assert result.summary == "分析結果: テストが失敗しました"
            assert result.tokens_used.input_tokens == 100
            assert result.tokens_used.output_tokens == 50

    @pytest.mark.asyncio
    async def test_analyze_rate_limit_error(self, openai_provider, analyze_options):
        """レート制限エラーのテスト"""
        import openai

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            rate_limit_error = openai.RateLimitError(
                message="Rate limit exceeded",
                response=Mock(),
                body=None,
            )
            mock_client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            with pytest.raises(RateLimitError):
                await openai_provider.analyze("分析してください", "ログ内容", analyze_options)

    @pytest.mark.asyncio
    async def test_stream_analyze(self, openai_provider, analyze_options):
        """ストリーミング分析のテスト"""

        # モックストリームレスポンス
        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content="分析"))]),
                Mock(choices=[Mock(delta=Mock(content="結果"))]),
                Mock(choices=[Mock(delta=Mock(content="です"))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_client
            openai_provider._client = mock_client

            analyze_options.stream = True
            chunks = []
            async for chunk in openai_provider.stream_analyze("分析してください", "ログ内容", analyze_options):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks == ["分析", "結果", "です"]


class TestAnthropicProvider:
    """Anthropicプロバイダーのテスト"""

    @pytest.fixture
    def anthropic_config(self):
        """Anthropic設定"""
        return ProviderConfig(
            name="anthropic",
            api_key="sk-ant-test-key-123",
            base_url="https://api.anthropic.com",
            default_model="claude-3-5-sonnet-20241022",
            available_models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            timeout_seconds=30,
            max_retries=3,
        )

    @pytest.fixture
    def anthropic_provider(self, anthropic_config):
        """Anthropicプロバイダー"""
        return AnthropicProvider(anthropic_config)

    def test_anthropic_provider_initialization(self, anthropic_provider):
        """Anthropicプロバイダー初期化のテスト"""
        assert anthropic_provider.name == "anthropic"
        assert anthropic_provider.config.api_key == "sk-ant-test-key-123"
        assert anthropic_provider.config.default_model == "claude-3-5-sonnet-20241022"

    def test_model_costs(self, anthropic_provider):
        """モデルコストのテスト"""
        sonnet_cost = AnthropicProvider.MODEL_COSTS["claude-3-5-sonnet-20241022"]
        assert sonnet_cost["input"] == 0.003
        assert sonnet_cost["output"] == 0.015

        haiku_cost = AnthropicProvider.MODEL_COSTS["claude-3-5-haiku-20241022"]
        assert haiku_cost["input"] == 0.00025
        assert haiku_cost["output"] == 0.00125

    @pytest.mark.asyncio
    async def test_initialize_success(self, anthropic_provider):
        """初期化成功のテスト"""
        with patch("src.ci_helper.ai.providers.anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            # validate_connectionをモック
            with patch.object(anthropic_provider, "validate_connection", return_value=True) as mock_validate:
                await anthropic_provider.initialize()

                assert anthropic_provider._client is not None
                mock_anthropic.assert_called_once_with(
                    api_key="sk-ant-test-key-123",
                    timeout=30,
                    max_retries=3,
                )
                mock_validate.assert_called_once()


class TestLocalLLMProvider:
    """ローカルLLMプロバイダーのテスト"""

    @pytest.fixture
    def local_config(self):
        """ローカルLLM設定"""
        return ProviderConfig(
            name="local",
            api_key="",  # ローカルLLMはAPIキー不要
            base_url="http://localhost:11434",
            default_model="llama3.2",
            available_models=["llama3.2", "codellama"],
            timeout_seconds=60,
            max_retries=2,
        )

    @pytest.fixture
    def local_provider(self, local_config):
        """ローカルLLMプロバイダー"""
        return LocalLLMProvider(local_config)

    def test_local_provider_initialization(self, local_provider):
        """ローカルLLMプロバイダー初期化のテスト"""
        assert local_provider.name == "local"
        assert local_provider.config.base_url == "http://localhost:11434"
        assert local_provider.config.default_model == "llama3.2"

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, local_provider):
        """Ollama接続確認成功のテスト"""
        # セッションを初期化
        local_provider._session = Mock()

        with patch.object(local_provider._session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"models": [{"name": "llama3.2"}]})
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await local_provider.validate_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, local_provider):
        """Ollama接続確認失敗のテスト"""
        # セッションを初期化
        local_provider._session = Mock()

        with patch.object(local_provider._session, "get") as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            with pytest.raises(ProviderError):
                await local_provider.validate_connection()

    def test_estimate_cost_always_zero(self, local_provider):
        """ローカルLLMのコスト推定（常に0）のテスト"""
        cost = local_provider.estimate_cost("llama3.2", 1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_initialize_success(self, local_provider):
        """初期化成功のテスト"""
        with patch.object(local_provider, "validate_connection", return_value=True):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = Mock()
                mock_session_class.return_value = mock_session

                await local_provider.initialize()
                # 例外が発生しないことを確認
                assert local_provider._session is not None

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, local_provider):
        """接続失敗時の初期化テスト"""
        with patch.object(
            local_provider, "validate_connection", side_effect=ProviderError("local", "Connection failed")
        ):
            with patch("aiohttp.ClientSession"):
                with pytest.raises(ProviderError):
                    await local_provider.initialize()
