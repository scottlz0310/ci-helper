"""
AI例外クラスのテスト

AI統合用の例外クラスをテストします。
"""

from src.ci_helper.ai.exceptions import (
    AIError,
    APIKeyError,
    ConfigurationError,
    NetworkError,
    ProviderError,
    RateLimitError,
    TokenLimitError,
)


class TestAIError:
    """AI基底例外のテスト"""

    def test_ai_error_basic(self):
        """基本的なAIエラーのテスト"""
        message = "AI処理でエラーが発生しました"
        error = AIError(message)

        assert str(error) == message
        assert error.args[0] == message

    def test_ai_error_with_cause(self):
        """原因付きAIエラーのテスト"""
        original_error = ValueError("元のエラー")
        message = "AI処理でエラーが発生しました"

        try:
            raise original_error
        except ValueError as e:
            try:
                raise AIError(message) from e
            except AIError as ai_error:
                assert str(ai_error) == message
                assert ai_error.__cause__ == original_error

    def test_ai_error_inheritance(self):
        """AIエラーの継承関係テスト"""
        error = AIError("テストエラー")
        assert isinstance(error, Exception)


class TestProviderError:
    """プロバイダーエラーのテスト"""

    def test_provider_error_basic(self):
        """基本的なプロバイダーエラーのテスト"""
        provider = "openai"
        message = "プロバイダーでエラーが発生しました"
        error = ProviderError(provider, message)

        assert error.provider == provider
        assert error.message == message
        assert str(error) == f"[{provider}] {message}"

    def test_provider_error_inheritance(self):
        """プロバイダーエラーの継承関係テスト"""
        error = ProviderError("test", "テストエラー")
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_provider_error_empty_message(self):
        """空のメッセージでのプロバイダーエラーテスト"""
        provider = "test"
        message = ""
        error = ProviderError(provider, message)

        assert error.provider == provider
        assert error.message == message
        assert str(error) == f"[{provider}] {message}"


class TestAPIKeyError:
    """APIキーエラーのテスト"""

    def test_api_key_error_basic(self):
        """基本的なAPIキーエラーのテスト"""
        provider = "openai"
        message = "APIキーが無効です"
        error = APIKeyError(provider, message)

        assert error.provider == provider
        assert error.message == message
        assert str(error) == f"[{provider}] {message}"

    def test_api_key_error_inheritance(self):
        """APIキーエラーの継承関係テスト"""
        error = APIKeyError("test", "テストエラー")
        assert isinstance(error, ProviderError)
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_api_key_error_with_details(self):
        """詳細情報付きAPIキーエラーのテスト"""
        provider = "anthropic"
        message = "APIキーの形式が正しくありません: sk-ant-xxx"
        error = APIKeyError(provider, message)

        assert "APIキーの形式が正しくありません" in str(error)
        assert "sk-ant-xxx" in str(error)


class TestRateLimitError:
    """レート制限エラーのテスト"""

    def test_rate_limit_error_basic(self):
        """基本的なレート制限エラーのテスト"""
        provider = "openai"
        error = RateLimitError(provider)

        assert error.provider == provider
        assert error.retry_after is None
        assert error.reset_time is None
        expected_message = f"{provider}のレート制限に達しました"
        assert expected_message in str(error)

    def test_rate_limit_error_with_retry_after(self):
        """リトライ時間付きレート制限エラーのテスト"""
        provider = "anthropic"
        message = "レート制限に達しました"
        retry_after = 60
        error = RateLimitError(provider, message, retry_after=retry_after)

        assert error.provider == provider
        assert error.message == message
        assert error.retry_after == retry_after
        assert str(error) == f"[{provider}] {message}"

    def test_rate_limit_error_inheritance(self):
        """レート制限エラーの継承関係テスト"""
        error = RateLimitError("test", "テストエラー")
        assert isinstance(error, ProviderError)
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_rate_limit_error_zero_retry_after(self):
        """リトライ時間0のレート制限エラーテスト"""
        error = RateLimitError("test", retry_after=0)
        assert error.retry_after == 0


class TestTokenLimitError:
    """トークン制限エラーのテスト"""

    def test_token_limit_error_basic(self):
        """基本的なトークン制限エラーのテスト"""
        used_tokens = 5000
        limit = 4000
        model = "gpt-4o"
        error = TokenLimitError(used_tokens, limit, model)

        assert error.used_tokens == used_tokens
        assert error.limit == limit
        assert error.model == model
        expected_message = f"トークン制限を超過しました: {used_tokens}/{limit}"
        assert str(error) == expected_message

    def test_token_limit_error_inheritance(self):
        """トークン制限エラーの継承関係テスト"""
        error = TokenLimitError(1000, 800, "test-model")
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_token_limit_error_no_model(self):
        """モデル名なしのトークン制限エラーテスト"""
        used_tokens = 2000
        limit = 1500
        model = "test-model"
        error = TokenLimitError(used_tokens, limit, model)

        assert error.used_tokens == used_tokens
        assert error.limit == limit
        assert error.model == model
        expected_message = f"トークン制限を超過しました: {used_tokens}/{limit}"
        assert str(error) == expected_message

    def test_token_limit_error_equal_tokens(self):
        """使用トークンと制限が同じ場合のテスト"""
        tokens = 1000
        error = TokenLimitError(tokens, tokens, "test-model")

        assert error.used_tokens == tokens
        assert error.limit == tokens
        expected_message = f"トークン制限を超過しました: {tokens}/{tokens}"
        assert str(error) == expected_message


class TestNetworkError:
    """ネットワークエラーのテスト"""

    def test_network_error_basic(self):
        """基本的なネットワークエラーのテスト"""
        message = "接続がタイムアウトしました"
        error = NetworkError(message)

        assert error.message == message
        assert error.retry_count == 0
        assert str(error) == message

    def test_network_error_with_retry_count(self):
        """リトライ回数付きネットワークエラーのテスト"""
        message = "接続に失敗しました"
        retry_count = 3
        error = NetworkError(message, retry_count=retry_count)

        assert error.message == message
        assert error.retry_count == retry_count
        assert str(error) == message

    def test_network_error_inheritance(self):
        """ネットワークエラーの継承関係テスト"""
        error = NetworkError("テストエラー")
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_network_error_negative_retry_count(self):
        """負のリトライ回数のネットワークエラーテスト"""
        error = NetworkError("テストエラー", retry_count=-1)
        assert error.retry_count == -1


class TestConfigurationError:
    """設定エラーのテスト"""

    def test_configuration_error_basic(self):
        """基本的な設定エラーのテスト"""
        message = "設定ファイルが見つかりません"
        error = ConfigurationError(message)

        assert str(error) == message
        assert error.args[0] == message

    def test_configuration_error_inheritance(self):
        """設定エラーの継承関係テスト"""
        error = ConfigurationError("テストエラー")
        assert isinstance(error, AIError)
        assert isinstance(error, Exception)

    def test_configuration_error_with_path(self):
        """パス情報付き設定エラーのテスト"""
        path = "/path/to/config.toml"
        message = f"設定ファイルが見つかりません: {path}"
        error = ConfigurationError(message)

        assert path in str(error)

    def test_configuration_error_empty_message(self):
        """空のメッセージでの設定エラーテスト"""
        error = ConfigurationError("")
        assert str(error) == ""


class TestExceptionChaining:
    """例外チェーンのテスト"""

    def test_provider_error_from_api_key_error(self):
        """APIキーエラーからプロバイダーエラーへのチェーンテスト"""
        original_error = APIKeyError("openai", "無効なAPIキー")

        try:
            raise original_error
        except APIKeyError as e:
            try:
                raise ProviderError("openai", "プロバイダー初期化に失敗") from e
            except ProviderError as chained_error:
                assert chained_error.__cause__ == original_error
                assert isinstance(chained_error.__cause__, APIKeyError)

    def test_ai_error_from_standard_exception(self):
        """標準例外からAIエラーへのチェーンテスト"""
        original_error = ValueError("無効な値")

        try:
            raise original_error
        except ValueError as e:
            try:
                raise AIError("AI処理でエラーが発生") from e
            except AIError as ai_error:
                assert ai_error.__cause__ == original_error
                assert isinstance(ai_error.__cause__, ValueError)

    def test_multiple_exception_chaining(self):
        """複数の例外チェーンテスト"""
        try:
            try:
                raise ConnectionError("接続エラー")
            except ConnectionError as e:
                raise NetworkError("ネットワークエラー") from e
        except NetworkError as e:
            try:
                raise ProviderError("openai", "プロバイダーエラー") from e
            except ProviderError as final_error:
                assert isinstance(final_error.__cause__, NetworkError)
                assert isinstance(final_error.__cause__.__cause__, ConnectionError)


class TestExceptionAttributes:
    """例外属性のテスト"""

    def test_provider_error_attributes(self):
        """プロバイダーエラーの属性テスト"""
        provider = "test_provider"
        message = "テストメッセージ"
        error = ProviderError(provider, message)

        # 属性が正しく設定されていることを確認
        assert hasattr(error, "provider")
        assert hasattr(error, "message")
        assert error.provider == provider
        assert error.message == message

    def test_rate_limit_error_attributes(self):
        """レート制限エラーの属性テスト"""
        provider = "test_provider"
        message = "テストメッセージ"
        retry_after = 30
        error = RateLimitError(provider, message, retry_after=retry_after)

        # 継承された属性
        assert hasattr(error, "provider")
        assert hasattr(error, "message")
        # 独自の属性
        assert hasattr(error, "retry_after")
        assert error.retry_after == retry_after

    def test_token_limit_error_attributes(self):
        """トークン制限エラーの属性テスト"""
        used_tokens = 1000
        limit = 800
        model = "test-model"
        error = TokenLimitError(used_tokens, limit, model)

        assert hasattr(error, "used_tokens")
        assert hasattr(error, "limit")
        assert hasattr(error, "model")
        assert error.used_tokens == used_tokens
        assert error.limit == limit
        assert error.model == model

    def test_network_error_attributes(self):
        """ネットワークエラーの属性テスト"""
        message = "テストメッセージ"
        retry_count = 5
        error = NetworkError(message, retry_count=retry_count)

        assert hasattr(error, "message")
        assert hasattr(error, "retry_count")
        assert error.message == message
        assert error.retry_count == retry_count
