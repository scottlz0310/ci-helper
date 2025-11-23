"""
既存AIFormatterとの統合アダプター

既存のAIFormatterを新しいフォーマッターアーキテクチャに統合するためのアダプタークラス。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base_formatter import BaseLogFormatter

if TYPE_CHECKING:
    from ..core.models import ExecutionResult


class LegacyAIFormatterAdapter(BaseLogFormatter):
    """既存AIFormatterのアダプター

    既存のAIFormatterを新しいBaseLogFormatterインターフェースに適合させます。
    """

    def __init__(self, sanitize_secrets: bool = True):
        """アダプターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか
        """
        super().__init__(sanitize_secrets)
        from ..core.ai_formatter import AIFormatter

        self._ai_formatter = AIFormatter(sanitize_secrets=sanitize_secrets)

    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """ログをMarkdown形式でフォーマット

        Args:
            execution_result: CI実行結果
            **options: フォーマットオプション
                - format_type: "markdown" または "json" (デフォルト: "markdown")

        Returns:
            フォーマットされた文字列
        """
        format_type = options.get("format_type", "markdown")

        if format_type.lower() == "json":
            return self._ai_formatter.format_json(execution_result)
        else:
            return self._ai_formatter.format_markdown(execution_result)

    def get_format_name(self) -> str:
        """フォーマット名を取得

        Returns:
            フォーマット名
        """
        return "markdown"

    def get_description(self) -> str:
        """フォーマットの説明を取得

        Returns:
            フォーマットの説明文
        """
        return "既存のAI消費用Markdown形式（互換性維持）"

    def supports_option(self, option_name: str) -> bool:
        """指定されたオプションをサポートしているかチェック

        Args:
            option_name: オプション名

        Returns:
            サポートしている場合True
        """
        supported_options = {"format_type"}
        return option_name in supported_options

    def get_supported_options(self) -> list[str]:
        """サポートされているオプション一覧を取得

        Returns:
            サポートされているオプション名のリスト
        """
        return ["format_type"]

    def validate_options(self, **options: Any) -> dict[str, Any]:
        """オプションの検証と正規化

        Args:
            **options: 検証対象のオプション

        Returns:
            検証・正規化されたオプション

        Raises:
            ValueError: 無効なオプションが指定された場合
        """
        validated_options: dict[str, str] = {}

        # format_typeの検証
        if "format_type" in options:
            format_type = options["format_type"]
            if format_type not in ["markdown", "json"]:
                raise ValueError(f"無効なformat_type: {format_type}. 'markdown'または'json'を指定してください。")
            validated_options["format_type"] = format_type
        else:
            validated_options["format_type"] = "markdown"

        return validated_options

    # 既存AIFormatterの高度な機能へのアクセス
    def count_tokens(self, content: str, model: str = "gpt-4") -> int:
        """コンテンツのトークン数をカウント

        Args:
            content: トークン数をカウントするコンテンツ
            model: 対象のAIモデル名

        Returns:
            推定トークン数
        """
        return self._ai_formatter.count_tokens(content, model)

    def check_token_limits(self, content: str, model: str = "gpt-4") -> dict[str, Any]:
        """トークン制限をチェック

        Args:
            content: チェック対象のコンテンツ
            model: 対象のAIモデル名

        Returns:
            トークン情報と警告を含む辞書
        """
        return self._ai_formatter.check_token_limits(content, model)

    def format_with_token_info(
        self, execution_result: ExecutionResult, format_type: str = "markdown", model: str = "gpt-4"
    ) -> dict[str, Any]:
        """フォーマット結果とトークン情報を含む辞書を返す

        Args:
            execution_result: CI実行結果
            format_type: 出力形式（"markdown" または "json"）
            model: 対象のAIモデル名

        Returns:
            フォーマット結果とトークン情報を含む辞書
        """
        return self._ai_formatter.format_with_token_info(execution_result, format_type, model)
