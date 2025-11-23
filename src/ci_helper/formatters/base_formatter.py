"""
基底フォーマッタークラス

全てのログフォーマッターの基底クラスを定義します。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from ..core.models import ExecutionResult
    from ..core.security import SecurityValidator


class LogSecurityValidationResult(TypedDict):
    """ログセキュリティ検証結果"""

    has_secrets: bool
    secret_count: int
    detected_secrets: list[dict[str, Any]]
    sanitized_content: str
    recommendations: list[str]


class BaseLogFormatter(ABC):
    """ログフォーマッターの基底クラス

    全てのフォーマッターはこのクラスを継承し、format()メソッドを実装する必要があります。
    """

    def __init__(self, sanitize_secrets: bool = True):
        """フォーマッターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか
        """
        self.sanitize_secrets = sanitize_secrets
        self.security_validator: SecurityValidator | None = None

        if sanitize_secrets:
            from ..core.security import SecurityValidator

            self.security_validator = SecurityValidator()

    @abstractmethod
    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """ログを指定形式でフォーマット

        Args:
            execution_result: CI実行結果
            **options: フォーマット固有のオプション

        Returns:
            フォーマットされた文字列
        """
        pass

    @abstractmethod
    def get_format_name(self) -> str:
        """フォーマット名を取得

        Returns:
            フォーマット名（例: "ai", "human", "json"）
        """
        pass

    def get_description(self) -> str:
        """フォーマットの説明を取得

        Returns:
            フォーマットの説明文
        """
        return f"{self.get_format_name()}形式でフォーマット"

    def _sanitize_content(self, content: str) -> str:
        """コンテンツのサニタイズ（共通処理）

        Args:
            content: サニタイズ対象のコンテンツ

        Returns:
            サニタイズされたコンテンツ
        """
        if not self.sanitize_secrets or not self.security_validator:
            return content

        try:
            return self.security_validator.secret_detector.sanitize_content(content)
        except Exception as e:
            # サニタイズに失敗した場合はログ整形エラーとして扱う
            from ..core.exceptions import LogFormattingError

            raise LogFormattingError(
                "コンテンツのセキュリティサニタイズに失敗しました",
                "セキュリティ機能を無効にするか、コンテンツを確認してください",
                formatter_name=self.get_format_name(),
            ) from e

    def format_with_optimization(self, execution_result: ExecutionResult, **options: Any) -> str:
        """最適化付きフォーマット（デフォルトは通常フォーマットと同じ挙動）"""
        return self.format(execution_result, **options)

    def validate_log_content_security(self, content: str) -> LogSecurityValidationResult:
        """ログコンテンツのセキュリティ検証

        Args:
            content: 検証対象のコンテンツ

        Returns:
            セキュリティ検証結果
        """
        if not self.security_validator:
            return {
                "has_secrets": False,
                "secret_count": 0,
                "detected_secrets": [],
                "sanitized_content": content,
                "recommendations": [],
            }

        return cast(LogSecurityValidationResult, self.security_validator.validate_log_content(content))

    def validate_options(self, **options: Any) -> dict[str, Any]:
        """オプションの検証と正規化

        Args:
            **options: 検証対象のオプション

        Returns:
            検証・正規化されたオプション

        Raises:
            ValueError: 無効なオプションが指定された場合
        """
        validated_options: dict[str, Any] = {}
        supported_options = self.get_supported_options()

        # サポートされているオプションのみを処理
        for key, value in options.items():
            if not supported_options or key in supported_options:
                validated_options[key] = value
            # サポートされていないオプションは警告を出すが、エラーにはしない
            # これにより、異なるフォーマッター間でのオプション互換性を保つ

        # 共通オプションのデフォルト値設定は各フォーマッターに委ねる
        # 基底クラスではデフォルト値を追加しない

        return validated_options

    def supports_option(self, option_name: str) -> bool:
        """指定されたオプションをサポートしているかチェック

        Args:
            option_name: オプション名

        Returns:
            サポートしている場合True
        """
        # デフォルト実装では全てのオプションをサポート
        return True

    def get_supported_options(self) -> list[str]:
        """サポートされているオプション一覧を取得

        Returns:
            サポートされているオプション名のリスト
        """
        # 基本的なオプション（全フォーマッターで共通）
        return [
            "use_optimization",
            "max_memory_mb",
            "detail_level",
            "filter_errors",
        ]
