"""
フォーマッターマネージャー

利用可能なフォーマッターを管理し、統一されたインターフェースを提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base_formatter import BaseLogFormatter
from .legacy_formatter import LegacyAIFormatterAdapter

if TYPE_CHECKING:
    from ..core.models import ExecutionResult


class FormatterManager:
    """フォーマッター管理クラス

    利用可能なフォーマッターを登録・管理し、統一されたインターフェースを提供します。
    """

    def __init__(self):
        """フォーマッターマネージャーを初期化"""
        self._formatters: dict[str, BaseLogFormatter] = {}
        self._register_default_formatters()

    def _register_default_formatters(self) -> None:
        """デフォルトフォーマッターを登録"""
        from .ai_context_formatter import AIContextFormatter
        from .human_readable_formatter import HumanReadableFormatter
        from .json_formatter import JSONFormatter

        # 新しいAI消費用フォーマッター
        self.register_formatter("ai", AIContextFormatter())

        # 人間可読フォーマッター
        self.register_formatter("human", HumanReadableFormatter())

        # JSON専用フォーマッター
        self.register_formatter("json", JSONFormatter())

        # 既存AIFormatterとの互換性を維持
        self.register_formatter("markdown", LegacyAIFormatterAdapter())

    def register_formatter(self, name: str, formatter: BaseLogFormatter) -> None:
        """フォーマッターを登録

        Args:
            name: フォーマッター名
            formatter: フォーマッターインスタンス

        Raises:
            ValueError: 無効なフォーマッター名、無効なフォーマッター、または既に登録済みの場合
        """
        if not name:
            raise ValueError("フォーマッター名は空にできません")

        # 型アノテーションで保証されているが、実行時検証のため残す
        if not isinstance(formatter, BaseLogFormatter):  # type: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"フォーマッターは BaseLogFormatter のインスタンスである必要があります: {type(formatter)}")

        if name in self._formatters:
            raise ValueError(f"フォーマッター '{name}' は既に登録されています")

        self._formatters[name] = formatter

    def unregister_formatter(self, name: str) -> None:
        """フォーマッターの登録を解除

        Args:
            name: フォーマッター名

        Raises:
            KeyError: 指定されたフォーマッターが存在しない場合
        """
        if name not in self._formatters:
            raise KeyError(f"フォーマッター '{name}' は登録されていません")

        del self._formatters[name]

    def get_formatter(self, name: str) -> BaseLogFormatter:
        """指定されたフォーマッターを取得

        Args:
            name: フォーマッター名

        Returns:
            フォーマッターインスタンス

        Raises:
            LogFormattingError: 指定されたフォーマッターが存在しない場合
        """
        if name not in self._formatters:
            available = self.list_available_formats()
            from ..core.exceptions import LogFormattingError

            raise LogFormattingError.formatter_not_found(name, available)

        return self._formatters[name]

    def has_formatter(self, name: str) -> bool:
        """指定されたフォーマッターが存在するかチェック

        Args:
            name: フォーマッター名

        Returns:
            存在する場合True
        """
        return name in self._formatters

    def list_available_formats(self) -> list[str]:
        """利用可能なフォーマット一覧を取得

        Returns:
            利用可能なフォーマット名のリスト
        """
        return list(self._formatters.keys())

    def get_formatter_info(self, name: str) -> dict[str, Any]:
        """フォーマッターの詳細情報を取得

        Args:
            name: フォーマッター名

        Returns:
            フォーマッターの詳細情報

        Raises:
            KeyError: 指定されたフォーマッターが存在しない場合
        """
        formatter = self.get_formatter(name)

        return {
            "name": name,
            "format_name": formatter.get_format_name(),
            "description": formatter.get_description(),
            "supported_options": formatter.get_supported_options(),
            "class_name": formatter.__class__.__name__,
        }

    def list_all_formatter_info(self) -> list[dict[str, Any]]:
        """全フォーマッターの詳細情報を取得

        Returns:
            全フォーマッターの詳細情報のリスト
        """
        return [self.get_formatter_info(name) for name in self.list_available_formats()]

    def format_log(self, execution_result: ExecutionResult, format_name: str, **options: Any) -> str:
        """ログを指定形式でフォーマット

        Args:
            execution_result: CI実行結果
            format_name: フォーマット名
            **options: フォーマット固有のオプション

        Returns:
            フォーマットされた文字列

        Raises:
            LogFormattingError: フォーマット処理が失敗した場合
            UserInputError: 無効なオプションが指定された場合
        """
        try:
            formatter = self.get_formatter(format_name)

            # オプションの検証
            validated_options = formatter.validate_options(**options)

            # パフォーマンス最適化機能を使用可能かチェック
            use_optimization = validated_options.get("use_optimization", True)

            if use_optimization:
                # 最適化機能を使用してフォーマット実行（未実装の場合は通常フォーマット）
                return formatter.format_with_optimization(execution_result, **validated_options)

            # 通常のフォーマット実行
            return formatter.format(execution_result, **validated_options)

        except (ValueError, TypeError) as e:
            from ..core.exceptions import UserInputError

            raise UserInputError(
                f"フォーマットオプションが無効です: {e}",
                "オプションの値と型を確認してください",
            ) from e
        except MemoryError as e:
            from ..core.exceptions import LogFormattingError

            raise LogFormattingError.memory_limit_exceeded(format_name, 0) from e
        except Exception as e:
            from ..core.exceptions import LogFormattingError

            raise LogFormattingError.formatting_failed(format_name, str(e)) from e

    def format_and_save_log(
        self,
        execution_result: ExecutionResult,
        format_name: str,
        output_file: str | None = None,
        console: Any | None = None,
        **options: Any,
    ) -> tuple[bool, str | None]:
        """ログをフォーマットしてファイルに保存

        Args:
            execution_result: CI実行結果
            format_name: フォーマット名
            output_file: 出力ファイルパス（Noneの場合は標準出力）
            console: Rich Console インスタンス
            **options: フォーマット固有のオプション

        Returns:
            (成功フラグ, 保存されたファイルパス) のタプル

        Raises:
            KeyError: 指定されたフォーマッターが存在しない場合
            ValueError: 無効なオプションが指定された場合
        """
        from ..utils.file_save_utils import FileSaveManager

        # ログをフォーマット
        formatted_content = self.format_log(execution_result, format_name, **options)

        # ファイル保存マネージャーを使用して保存
        file_manager = FileSaveManager(console)
        return file_manager.save_formatted_log(
            content=formatted_content,
            output_file=output_file,
            format_type=format_name,
            default_dir=file_manager.get_default_output_directory(),
        )

    def format_log_safe(
        self, execution_result: ExecutionResult, format_name: str, fallback_format: str = "markdown", **options: Any
    ) -> tuple[str, str]:
        """ログを安全にフォーマット（エラー時はフォールバック）

        Args:
            execution_result: CI実行結果
            format_name: フォーマット名
            fallback_format: フォールバック用フォーマット名
            **options: フォーマット固有のオプション

        Returns:
            (フォーマット結果, 使用されたフォーマット名) のタプル
        """
        try:
            result = self.format_log(execution_result, format_name, **options)
            return result, format_name
        except Exception:
            # フォールバックフォーマットを試行
            try:
                result = self.format_log(execution_result, fallback_format, **options)
                return result, fallback_format
            except Exception:
                # 最後の手段として基本的なテキスト出力
                status = "成功" if execution_result.success else "失敗"
                basic_output = f"CI実行結果: {status}\n"
                basic_output += f"実行時間: {execution_result.total_duration:.2f}秒\n"
                basic_output += f"失敗数: {execution_result.total_failures}"
                return basic_output, "basic"

    def validate_format_options(self, format_name: str, **options: Any) -> dict[str, Any]:
        """フォーマットオプションを検証

        Args:
            format_name: フォーマット名
            **options: 検証対象のオプション

        Returns:
            検証・正規化されたオプション

        Raises:
            KeyError: 指定されたフォーマッターが存在しない場合
            ValueError: 無効なオプションが指定された場合
        """
        formatter = self.get_formatter(format_name)
        return formatter.validate_options(**options)

    def get_default_format(self) -> str:
        """デフォルトフォーマット名を取得

        Returns:
            デフォルトフォーマット名
        """
        # 利用可能なフォーマットの優先順位
        preferred_formats = ["ai", "markdown", "json"]

        for format_name in preferred_formats:
            if self.has_formatter(format_name):
                return format_name

        # フォールバック: 最初に利用可能なフォーマット
        available = self.list_available_formats()
        if available:
            return available[0]

        raise RuntimeError("利用可能なフォーマッターがありません")


# グローバルフォーマッターマネージャーインスタンス
_global_formatter_manager: FormatterManager | None = None


def get_formatter_manager() -> FormatterManager:
    """グローバルフォーマッターマネージャーを取得

    Returns:
        フォーマッターマネージャーインスタンス
    """
    global _global_formatter_manager
    if _global_formatter_manager is None:
        _global_formatter_manager = FormatterManager()
    return _global_formatter_manager


def reset_formatter_manager() -> None:
    """グローバルフォーマッターマネージャーをリセット

    主にテスト用途で使用します。
    """
    global _global_formatter_manager
    _global_formatter_manager = None
