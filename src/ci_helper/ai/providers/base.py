"""
AIプロバイダーの基底クラス

すべてのAIプロバイダー（OpenAI、Anthropic、ローカルLLM等）が実装すべき
共通インターフェースを定義します。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..exceptions import ProviderError
from ..models import AnalysisResult, AnalyzeOptions, ProviderConfig, TokenUsage


class AIProvider(ABC):
    """AIプロバイダーの抽象基底クラス"""

    def __init__(self, config: ProviderConfig):
        """プロバイダーを初期化

        Args:
            config: プロバイダー設定
        """
        self.config = config
        self.name = config.name
        self._client = None

    @abstractmethod
    async def initialize(self) -> None:
        """プロバイダーを初期化

        APIクライアントの設定、認証の確認等を行います。

        Raises:
            ProviderError: 初期化に失敗した場合
        """

    @abstractmethod
    async def analyze(self, prompt: str, context: str, options: AnalyzeOptions) -> AnalysisResult:
        """ログを分析してAI結果を返す

        Args:
            prompt: 分析用プロンプト
            context: 分析対象のログコンテンツ
            options: 分析オプション

        Returns:
            分析結果

        Raises:
            ProviderError: 分析に失敗した場合
            TokenLimitError: トークン制限を超過した場合
            RateLimitError: レート制限に達した場合
        """

    @abstractmethod
    async def stream_analyze(self, prompt: str, context: str, options: AnalyzeOptions) -> AsyncIterator[str]:
        """ストリーミング分析を実行

        Args:
            prompt: 分析用プロンプト
            context: 分析対象のログコンテンツ
            options: 分析オプション

        Yields:
            分析結果の部分文字列

        Raises:
            ProviderError: 分析に失敗した場合
            TokenLimitError: トークン制限を超過した場合
            RateLimitError: レート制限に達した場合
        """

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        """コストを推定

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            推定コスト（USD）
        """

    @abstractmethod
    def count_tokens(self, text: str, model: str | None = None) -> int:
        """テキストのトークン数をカウント

        Args:
            text: カウント対象のテキスト
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            トークン数
        """

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """利用可能なモデル一覧を取得

        Returns:
            モデル名のリスト
        """

    @abstractmethod
    async def validate_connection(self) -> bool:
        """接続を検証

        Returns:
            接続が有効かどうか

        Raises:
            ProviderError: 接続検証に失敗した場合
        """

    def get_model(self, model: str | None = None) -> str:
        """使用するモデルを取得

        Args:
            model: 指定されたモデル名

        Returns:
            実際に使用するモデル名
        """
        if model and model in self.config.available_models:
            return model
        return self.config.default_model

    def validate_model(self, model: str) -> bool:
        """モデルが利用可能かどうかを検証

        Args:
            model: モデル名

        Returns:
            利用可能かどうか
        """
        return model in self.config.available_models

    async def health_check(self) -> dict[str, any]:
        """ヘルスチェックを実行

        Returns:
            ヘルスチェック結果
        """
        try:
            is_connected = await self.validate_connection()
            return {
                "provider": self.name,
                "status": "healthy" if is_connected else "unhealthy",
                "available_models": self.get_available_models(),
                "default_model": self.config.default_model,
                "rate_limit": self.config.rate_limit_per_minute,
            }
        except RateLimitError as e:
            return {
                "provider": self.name,
                "status": "rate_limited",
                "error": str(e),
                "reset_time": e.reset_time.isoformat() if e.reset_time else None,
            }
        except NetworkError as e:
            return {
                "provider": self.name,
                "status": "network_error",
                "error": str(e),
                "retry_count": e.retry_count,
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "error",
                "error": str(e),
            }

    def create_token_usage(self, input_tokens: int, output_tokens: int, model: str | None = None) -> TokenUsage:
        """TokenUsageオブジェクトを作成

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            model: モデル名

        Returns:
            TokenUsageオブジェクト
        """
        total_tokens = input_tokens + output_tokens
        estimated_cost = self.estimate_cost(input_tokens, output_tokens, model)

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        )

    def handle_api_error(self, error: Exception, operation: str) -> Exception:
        """API エラーを適切な例外に変換

        Args:
            error: 元のエラー
            operation: 実行していた操作

        Returns:
            変換された例外
        """
        error_str = str(error).lower()

        # レート制限エラーの検出
        if "rate limit" in error_str or "too many requests" in error_str:
            return RateLimitError(self.name)

        # トークン制限エラーの検出
        if "token" in error_str and ("limit" in error_str or "maximum" in error_str):
            return TokenLimitError(0, 0, self.config.default_model)

        # ネットワークエラーの検出
        if any(keyword in error_str for keyword in ["connection", "network", "timeout", "unreachable"]):
            return NetworkError(f"{operation}中にネットワークエラーが発生しました: {error}")

        # その他はプロバイダーエラーとして処理
        return ProviderError(self.name, f"{operation}中にエラーが発生しました: {error}")

    async def cleanup(self) -> None:
        """リソースをクリーンアップ

        プロバイダーが使用していたリソース（接続、セッション等）を解放します。
        """
        if hasattr(self, "_client") and self._client:
            if hasattr(self._client, "close"):
                await self._client.close()
            elif hasattr(self._client, "aclose"):
                await self._client.aclose()

    def __str__(self) -> str:
        """文字列表現"""
        return f"{self.__class__.__name__}(name={self.name}, model={self.config.default_model})"

    def __repr__(self) -> str:
        """詳細な文字列表現"""
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"default_model={self.config.default_model}, "
            f"available_models={len(self.config.available_models)}, "
            f"timeout={self.config.timeout_seconds}s"
            f")"
        )


class ProviderFactory:
    """AIプロバイダーのファクトリークラス"""

    _providers: dict[str, type[AIProvider]] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: type[AIProvider]) -> None:
        """プロバイダーを登録

        Args:
            name: プロバイダー名
            provider_class: プロバイダークラス
        """
        cls._providers[name] = provider_class

    @classmethod
    def create_provider(cls, name: str, config: ProviderConfig) -> AIProvider:
        """プロバイダーを作成

        Args:
            name: プロバイダー名
            config: プロバイダー設定

        Returns:
            プロバイダーインスタンス

        Raises:
            ProviderError: 未知のプロバイダーの場合
        """
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ProviderError(
                name,
                f"未知のプロバイダー: {name}",
                f"利用可能なプロバイダー: {available}",
            )

        provider_class = cls._providers[name]
        return provider_class(config)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """利用可能なプロバイダー一覧を取得

        Returns:
            プロバイダー名のリスト
        """
        return list(cls._providers.keys())

    @classmethod
    def is_provider_available(cls, name: str) -> bool:
        """プロバイダーが利用可能かどうかを確認

        Args:
            name: プロバイダー名

        Returns:
            利用可能かどうか
        """
        return name in cls._providers


# プロバイダー設定のヘルパー関数
def create_provider_config(
    name: str,
    api_key: str,
    default_model: str,
    available_models: list[str] | None = None,
    base_url: str | None = None,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    rate_limit_per_minute: int | None = None,
    cost_per_input_token: float = 0.0,
    cost_per_output_token: float = 0.0,
) -> ProviderConfig:
    """プロバイダー設定を作成するヘルパー関数

    Args:
        name: プロバイダー名
        api_key: APIキー
        default_model: デフォルトモデル
        available_models: 利用可能なモデルリスト
        base_url: ベースURL
        timeout_seconds: タイムアウト時間
        max_retries: 最大リトライ回数
        rate_limit_per_minute: 分あたりのレート制限
        cost_per_input_token: 入力トークンあたりのコスト
        cost_per_output_token: 出力トークンあたりのコスト

    Returns:
        プロバイダー設定
    """
    if available_models is None:
        available_models = [default_model]

    return ProviderConfig(
        name=name,
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        available_models=available_models,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        rate_limit_per_minute=rate_limit_per_minute,
        cost_per_input_token=cost_per_input_token,
        cost_per_output_token=cost_per_output_token,
    )
