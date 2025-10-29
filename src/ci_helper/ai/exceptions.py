"""
AI統合用の例外クラス

AI機能で発生する様々なエラーを適切に分類し、処理するための例外クラスを定義します。
"""

from __future__ import annotations

from datetime import datetime


class AIError(Exception):
    """AI統合の基底例外クラス"""

    def __init__(self, message: str, details: str | None = None, suggestion: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.suggestion = suggestion


class ProviderError(AIError):
    """プロバイダー固有のエラー"""

    def __init__(self, provider: str, message: str, details: str | None = None):
        super().__init__(message, details)
        self.provider = provider
        self.message = message

    def __str__(self) -> str:
        return f"[{self.provider}] {self.message}"


class APIKeyError(ProviderError):
    """APIキー関連のエラー"""

    def __init__(self, provider: str, message: str = "APIキーが無効または設定されていません"):
        super().__init__(provider, message)
        details = f"{provider}のAPIキーを確認してください"
        suggestion = f"環境変数 {provider.upper()}_API_KEY を設定してください"
        self.details = details
        self.suggestion = suggestion


class RateLimitError(ProviderError):
    """レート制限エラー"""

    def __init__(
        self,
        provider: str,
        message: str | None = None,
        retry_after: int | None = None,
        reset_time: datetime | None = None,
    ):
        if message is None:
            message = f"{provider}のレート制限に達しました"

        super().__init__(provider, message)

        details = None
        suggestion = "しばらく待ってから再試行してください"

        if reset_time:
            details = f"制限リセット時刻: {reset_time.strftime('%Y-%m-%d %H:%M:%S')}"
        if retry_after:
            suggestion = f"{retry_after}秒後に再試行してください"

        self.details = details
        self.suggestion = suggestion
        self.reset_time = reset_time
        self.retry_after = retry_after


class TokenLimitError(AIError):
    """トークン制限エラー"""

    def __init__(self, used_tokens: int, limit: int, model: str):
        message = f"トークン制限を超過しました: {used_tokens}/{limit}"
        details = f"モデル: {model}"
        suggestion = "入力を短縮するか、より大きなコンテキストウィンドウを持つモデルを使用してください"

        super().__init__(message, details, suggestion)
        self.used_tokens = used_tokens
        self.limit = limit
        self.model = model


class NetworkError(AIError):
    """ネットワーク関連のエラー"""

    def __init__(self, message: str, retry_count: int = 0):
        super().__init__(
            message,
            f"リトライ回数: {retry_count}",
            "ネットワーク接続を確認し、再試行してください",
        )
        self.message = message
        self.retry_count = retry_count


class ConfigurationError(AIError):
    """設定関連のエラー"""

    def __init__(self, message: str, config_key: str | None = None):
        details = f"設定キー: {config_key}" if config_key else None
        super().__init__(message, details, "設定ファイルまたは環境変数を確認してください")
        self.config_key = config_key


class CacheError(AIError):
    """キャッシュ関連のエラー"""

    def __init__(self, message: str, cache_path: str | None = None):
        details = f"キャッシュパス: {cache_path}" if cache_path else None
        super().__init__(message, details, "キャッシュディレクトリの権限を確認してください")
        self.cache_path = cache_path


class SecurityError(AIError):
    """セキュリティ関連のエラー"""

    def __init__(self, message: str, security_issue: str | None = None):
        super().__init__(
            message,
            security_issue,
            "セキュリティ設定を確認し、機密情報が適切に保護されていることを確認してください",
        )
        self.security_issue = security_issue


class AnalysisError(AIError):
    """分析処理関連のエラー"""

    def __init__(self, message: str, log_path: str | None = None):
        details = f"ログファイル: {log_path}" if log_path else None
        super().__init__(message, details, "ログファイルの形式を確認してください")
        self.log_path = log_path


class InteractiveSessionError(AIError):
    """対話セッション関連のエラー"""

    def __init__(self, message: str, session_id: str | None = None):
        details = f"セッションID: {session_id}" if session_id else None
        super().__init__(message, details, "対話セッションを再開してください")
        self.session_id = session_id


class CostLimitError(AIError):
    """コスト制限エラー"""

    def __init__(self, current_cost: float, limit: float, provider: str):
        message = f"コスト制限を超過しました: ${current_cost:.4f}/${limit:.2f}"
        details = f"プロバイダー: {provider}"
        suggestion = "コスト制限を増やすか、使用量を削減してください"

        super().__init__(message, details, suggestion)
        self.current_cost = current_cost
        self.limit = limit
        self.provider = provider


class FixApplicationError(AIError):
    """修正適用関連のエラー"""

    def __init__(self, message: str, rollback_info: dict | None = None):
        super().__init__(
            message,
            f"ロールバック情報: {rollback_info}" if rollback_info else None,
            "バックアップからロールバックを実行してください",
        )
        self.rollback_info = rollback_info


class PatternRecognitionError(AnalysisError):
    """パターン認識関連のエラー"""

    def __init__(self, message: str, log_path: str | None = None, confidence: float = 0.0):
        super().__init__(message, log_path)
        self.confidence = confidence


class UnknownErrorError(AIError):
    """未知エラー処理関連のエラー"""

    def __init__(self, message: str, error_category: str | None = None):
        super().__init__(
            message,
            f"エラーカテゴリ: {error_category}" if error_category else None,
            "ログの詳細を確認し、手動で調査してください",
        )
        self.error_category = error_category


class ValidationError(AIError):
    """検証エラー"""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            message,
            f"フィールド: {field}" if field else None,
            "入力データを確認してください",
        )
        self.field = field
