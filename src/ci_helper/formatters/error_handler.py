"""
ログ整形エラーハンドラー

ログ整形機能専用のエラーハンドリングとユーザーフレンドリーなエラーメッセージを提供します。
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from ..core.exceptions import FileOperationError, LogFormattingError, UserInputError


class LogFormattingErrorHandler:
    """ログ整形専用エラーハンドラー"""

    def __init__(self, console: Console | None = None):
        """エラーハンドラーを初期化

        Args:
            console: Rich Console インスタンス
        """
        self.console = console or Console()

    def handle_formatting_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        verbose: bool = False,
    ) -> None:
        """フォーマット関連エラーを処理

        Args:
            error: 発生したエラー
            context: エラーコンテキスト情報
            verbose: 詳細情報を表示するかどうか
        """
        context = context or {}

        # エラー種別に応じた処理
        if isinstance(error, LogFormattingError):
            self._handle_log_formatting_error(error, context, verbose)
        elif isinstance(error, FileOperationError):
            self._handle_file_operation_error(error, context, verbose)
        elif isinstance(error, UserInputError):
            self._handle_user_input_error(error, context, verbose)
        elif isinstance(error, (PermissionError, OSError)):
            self._handle_system_error(error, context, verbose)
        elif isinstance(error, json.JSONDecodeError):
            self._handle_json_error(error, context, verbose)
        elif isinstance(error, (ValueError, TypeError)):
            self._handle_validation_error(error, context, verbose)
        elif isinstance(error, MemoryError):
            self._handle_memory_error(error, context, verbose)
        else:
            self._handle_unexpected_error(error, context, verbose)

    def _handle_log_formatting_error(
        self,
        error: LogFormattingError,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """ログ整形エラーを処理"""
        title = "🔧 ログ整形エラー"

        # エラーメッセージを構築
        message_parts = [f"[red]{error.message}[/red]"]

        if error.formatter_name:
            message_parts.append(f"[dim]フォーマッター: {error.formatter_name}[/dim]")

        if error.format_type:
            message_parts.append(f"[dim]フォーマット種別: {error.format_type}[/dim]")

        # コンテキスト情報を追加
        if context.get("input_file"):
            message_parts.append(f"[dim]入力ファイル: {context['input_file']}[/dim]")

        message = "\n".join(message_parts)

        # 修正提案を追加
        suggestions = []
        if error.suggestion:
            suggestions.append(error.suggestion)

        # 追加の修正提案
        suggestions.extend(self._get_formatting_suggestions(error, context))

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_file_operation_error(
        self,
        error: FileOperationError,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """ファイル操作エラーを処理"""
        title = "📁 ファイル操作エラー"

        message_parts = [f"[red]{error.message}[/red]"]

        if error.file_path:
            message_parts.append(f"[dim]ファイル: {error.file_path}[/dim]")

        if error.operation:
            message_parts.append(f"[dim]操作: {error.operation}[/dim]")

        message = "\n".join(message_parts)

        # 修正提案を生成
        suggestions = []
        if error.suggestion:
            suggestions.append(error.suggestion)

        suggestions.extend(self._get_file_operation_suggestions(error, context))

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_user_input_error(
        self,
        error: UserInputError,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """ユーザー入力エラーを処理"""
        title = "⌨️ 入力エラー"

        message_parts = [f"[red]{error.message}[/red]"]

        if error.input_value:
            message_parts.append(f"[dim]入力値: {error.input_value}[/dim]")

        if error.input_type:
            message_parts.append(f"[dim]入力種別: {error.input_type}[/dim]")

        message = "\n".join(message_parts)

        # 修正提案を生成
        suggestions = []
        if error.suggestion:
            suggestions.append(error.suggestion)

        suggestions.extend(self._get_input_suggestions(error, context))

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_system_error(
        self,
        error: Exception,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """システムエラーを処理"""
        title = "🖥️ システムエラー"

        if isinstance(error, PermissionError):
            message = f"[red]権限エラー: {error}[/red]"
            suggestions = [
                "ファイルやディレクトリの権限を確認してください",
                "管理者権限で実行してみてください",
                "別の場所に保存してみてください",
            ]
        elif isinstance(error, FileNotFoundError):
            message = f"[red]ファイルが見つかりません: {error}[/red]"
            suggestions = [
                "ファイルパスを確認してください",
                "'ci-run logs' で利用可能なログファイルを確認してください",
                "相対パスではなく絶対パスを使用してみてください",
            ]
        elif isinstance(error, OSError):
            message = f"[red]OS エラー: {error}[/red]"
            suggestions = [
                "ディスク容量を確認してください",
                "ファイルシステムの状態を確認してください",
                "一時的な問題の可能性があります。しばらく待ってから再試行してください",
            ]
        else:
            message = f"[red]システムエラー: {error}[/red]"
            suggestions = ["システム管理者に相談してください"]

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_validation_error(
        self,
        error: Exception,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """バリデーションエラーを処理"""
        title = "✅ 入力検証エラー"

        message = f"[red]入力値が無効です: {error}[/red]"

        suggestions = [
            "入力値の形式を確認してください",
            "必要な項目がすべて入力されているか確認してください",
            "ヘルプ（--help）で使用方法を確認してください",
        ]

        # コンテキストに応じた追加提案
        if context.get("format_type"):
            suggestions.append("'ci-run format-logs --help' でサポートされているフォーマットを確認してください")

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_json_error(
        self,
        error: json.JSONDecodeError,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """JSON エラーを処理"""
        title = "📄 JSON 形式エラー"

        message_parts = [
            f"[red]JSON の解析に失敗しました: {error.msg}[/red]",
            f"[dim]行: {error.lineno}, 列: {error.colno}[/dim]",
        ]

        if context.get("file_path"):
            message_parts.append(f"[dim]ファイル: {context['file_path']}[/dim]")

        message = "\n".join(message_parts)

        suggestions = [
            "JSON ファイルの形式を確認してください",
            "オンライン JSON バリデーターで検証してください",
            "ファイルが破損していないか確認してください",
        ]

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_memory_error(
        self,
        error: MemoryError,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """メモリエラーを処理"""
        title = "💾 メモリ不足エラー"

        message = "[red]メモリが不足しています[/red]"

        suggestions = [
            "ストリーミングフォーマッターを使用してください",
            "ログファイルを分割してください",
            "不要なプロセスを終了してメモリを確保してください",
            "より小さなログファイルで試してください",
        ]

        # ファイルサイズ情報があれば追加
        if context.get("file_size_mb"):
            size_mb = context["file_size_mb"]
            message += f"\n[dim]ファイルサイズ: {size_mb}MB[/dim]"

            if size_mb > 100:
                suggestions.insert(0, f"ファイルが大きすぎます ({size_mb}MB)。100MB以下に分割することをお勧めします")

        self._display_error_panel(title, message, suggestions, verbose)

    def _handle_unexpected_error(
        self,
        error: Exception,
        context: dict[str, Any],
        verbose: bool,
    ) -> None:
        """予期しないエラーを処理"""
        title = "❌ 予期しないエラー"

        error_type = type(error).__name__
        message = f"[red]予期しないエラーが発生しました ({error_type}): {error}[/red]"

        suggestions = [
            "この問題が継続する場合は、開発者に報告してください",
            "一時的な問題の可能性があります。しばらく待ってから再試行してください",
            "より詳細な情報を得るには --verbose オプションを使用してください",
        ]

        # コンテキスト情報を追加
        if context:
            context_info = []
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    context_info.append(f"{key}: {value}")

            if context_info:
                message += f"\n[dim]コンテキスト: {', '.join(context_info)}[/dim]"

        self._display_error_panel(title, message, suggestions, verbose)

        # 詳細モードの場合はスタックトレースを表示
        if verbose:
            self.console.print("\n[dim]スタックトレース:[/dim]")
            self.console.print(traceback.format_exc())

    def _get_formatting_suggestions(
        self,
        error: LogFormattingError,
        context: dict[str, Any],
    ) -> list[str]:
        """フォーマット関連の追加修正提案を生成"""
        suggestions = []

        # フォーマッター固有の提案
        if error.formatter_name == "ai":
            suggestions.extend(
                [
                    "AI フォーマッターは大きなログファイルに時間がかかる場合があります",
                    "human フォーマッターを試してみてください",
                ]
            )
        elif error.formatter_name == "json":
            suggestions.extend(
                [
                    "JSON フォーマッターは構造化データが必要です",
                    "ログファイルが有効な形式か確認してください",
                ]
            )

        # ファイルサイズに応じた提案
        if context.get("file_size_mb", 0) > 50:
            suggestions.append("大きなファイルの場合は streaming フォーマッターの使用を検討してください")

        return suggestions

    def _get_file_operation_suggestions(
        self,
        error: FileOperationError,
        context: dict[str, Any],
    ) -> list[str]:
        """ファイル操作関連の追加修正提案を生成"""
        suggestions = []

        # 操作種別に応じた提案
        if error.operation == "読み込み":
            suggestions.extend(
                [
                    "ファイルが存在するか確認してください",
                    "ファイルが他のプロセスで使用されていないか確認してください",
                ]
            )
        elif error.operation == "書き込み":
            suggestions.extend(
                [
                    "出力ディレクトリに書き込み権限があるか確認してください",
                    "ディスク容量が十分にあるか確認してください",
                ]
            )

        # パス関連の提案
        if error.file_path:
            file_path = Path(error.file_path)
            if not file_path.is_absolute():
                suggestions.append("絶対パスを使用してみてください")

            if len(str(file_path)) > 200:
                suggestions.append("より短いファイルパスを使用してください")

        return suggestions

    def _get_input_suggestions(
        self,
        error: UserInputError,
        context: dict[str, Any],
    ) -> list[str]:
        """入力関連の追加修正提案を生成"""
        suggestions = []

        # 入力種別に応じた提案
        if error.input_type == "format_type":
            suggestions.extend(
                [
                    "'ci-run format-logs --help' でサポートされているフォーマットを確認してください",
                    "ai、human、json のいずれかを指定してください",
                ]
            )
        elif error.input_type == "file_extension":
            suggestions.append("ログファイルは通常 .log または .txt 拡張子を持ちます")

        return suggestions

    def _display_error_panel(
        self,
        title: str,
        message: str,
        suggestions: list[str],
        verbose: bool,
    ) -> None:
        """エラーパネルを表示

        Args:
            title: パネルタイトル
            message: エラーメッセージ
            suggestions: 修正提案リスト
            verbose: 詳細表示フラグ
        """
        # パネル内容を構築
        content_parts = [message]

        if suggestions:
            content_parts.append("\n[bold yellow]💡 修正提案:[/bold yellow]")
            for i, suggestion in enumerate(suggestions, 1):
                content_parts.append(f"  {i}. {suggestion}")

        content = "\n".join(content_parts)

        # パネルを表示
        panel = Panel(
            content,
            title=title,
            title_align="left",
            border_style="red",
            padding=(1, 2),
        )

        self.console.print(panel)

    def create_error_context(
        self,
        formatter_name: str | None = None,
        format_type: str | None = None,
        input_file: str | Path | None = None,
        output_file: str | Path | None = None,
        file_size_mb: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """エラーコンテキストを作成

        Args:
            formatter_name: フォーマッター名
            format_type: フォーマット種別
            input_file: 入力ファイルパス
            output_file: 出力ファイルパス
            file_size_mb: ファイルサイズ（MB）
            **kwargs: その他のコンテキスト情報

        Returns:
            エラーコンテキスト辞書
        """
        context = {}

        if formatter_name:
            context["formatter_name"] = formatter_name
        if format_type:
            context["format_type"] = format_type
        if input_file:
            context["input_file"] = str(input_file)
        if output_file:
            context["output_file"] = str(output_file)
        if file_size_mb is not None:
            context["file_size_mb"] = file_size_mb

        # 追加のコンテキスト情報をマージ
        context.update(kwargs)

        return context

    def get_recovery_suggestions(self, error: Exception) -> list[str]:
        """エラーからの復旧提案を取得

        Args:
            error: 発生したエラー

        Returns:
            復旧提案のリスト
        """
        suggestions = []

        # エラー種別に応じた基本的な復旧提案
        if isinstance(error, LogFormattingError):
            suggestions.extend(
                [
                    "別のフォーマッターを試してください",
                    "ログファイルの形式を確認してください",
                    "ストリーミング処理を有効にしてください",
                ]
            )
        elif isinstance(error, FileOperationError):
            suggestions.extend(
                [
                    "ファイルパスを確認してください",
                    "権限を確認してください",
                    "ディスク容量を確認してください",
                ]
            )
        elif isinstance(error, UserInputError):
            suggestions.extend(
                [
                    "入力値を確認してください",
                    "ヘルプを参照してください",
                    "デフォルト値を使用してください",
                ]
            )
        else:
            suggestions.extend(
                [
                    "一時的な問題の可能性があります。再試行してください",
                    "詳細情報を得るには --verbose オプションを使用してください",
                ]
            )

        return suggestions

    def format_error_summary(self, error: Exception, context: dict[str, Any] | None = None) -> str:
        """エラーの要約を生成

        Args:
            error: 発生したエラー
            context: エラーコンテキスト

        Returns:
            エラー要約文字列
        """
        context = context or {}

        error_type = type(error).__name__
        summary_parts = [f"エラー種別: {error_type}"]

        if hasattr(error, "message"):
            summary_parts.append(f"メッセージ: {error.message}")
        else:
            summary_parts.append(f"メッセージ: {error!s}")

        # コンテキスト情報を追加
        if context.get("formatter_name"):
            summary_parts.append(f"フォーマッター: {context['formatter_name']}")
        if context.get("input_file"):
            summary_parts.append(f"入力ファイル: {context['input_file']}")

        return " | ".join(summary_parts)
