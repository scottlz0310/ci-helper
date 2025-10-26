"""
ログ整形エラーハンドラーのテスト

エラーハンドリング機能の動作を検証します。
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from src.ci_helper.core.exceptions import FileOperationError, LogFormattingError, UserInputError
from src.ci_helper.formatters.error_handler import LogFormattingErrorHandler


class TestLogFormattingErrorHandler:
    """ログ整形エラーハンドラーのテストクラス"""

    def setup_method(self):
        """テストメソッドの前処理"""
        self.console = Mock(spec=Console)
        self.error_handler = LogFormattingErrorHandler(self.console)

    def test_handle_log_formatting_error(self):
        """ログ整形エラーの処理をテスト"""
        error = LogFormattingError.formatter_not_found("invalid_formatter", ["ai", "human", "json"])
        context = {"input_file": "test.log", "format_type": "invalid"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "🔧 ログ整形エラー" in call_args.title

    def test_handle_file_operation_error(self):
        """ファイル操作エラーの処理をテスト"""
        error = FileOperationError.file_not_found("/nonexistent/file.log", "読み込み")
        context = {"operation": "read"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "📁 ファイル操作エラー" in call_args.title

    def test_handle_user_input_error(self):
        """ユーザー入力エラーの処理をテスト"""
        error = UserInputError.invalid_format_type("invalid", ["ai", "human", "json"])
        context = {"input_type": "format_type"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "⌨️ 入力エラー" in call_args.title

    def test_handle_system_error_permission(self):
        """システムエラー（権限）の処理をテスト"""
        error = PermissionError("Permission denied")
        context = {"file_path": "/protected/file.log"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "🖥️ システムエラー" in call_args.title

    def test_handle_system_error_file_not_found(self):
        """システムエラー（ファイル未発見）の処理をテスト"""
        error = FileNotFoundError("File not found")
        context = {"file_path": "/missing/file.log"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "🖥️ システムエラー" in call_args.title

    def test_handle_validation_error(self):
        """バリデーションエラーの処理をテスト"""
        error = ValueError("Invalid value")
        context = {"format_type": "ai"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "✅ 入力検証エラー" in call_args.title

    def test_handle_json_error(self):
        """JSON エラーの処理をテスト"""
        error = json.JSONDecodeError("Invalid JSON", "test", 0)
        context = {"file_path": "test.json"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "📄 JSON 形式エラー" in call_args.title

    def test_handle_memory_error(self):
        """メモリエラーの処理をテスト"""
        error = MemoryError("Out of memory")
        context = {"file_size_mb": 500}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "💾 メモリ不足エラー" in call_args.title

    def test_handle_unexpected_error(self):
        """予期しないエラーの処理をテスト"""
        error = RuntimeError("Unexpected error")
        context = {"formatter_name": "ai", "input_file": "test.log"}

        self.error_handler.handle_formatting_error(error, context, verbose=False)

        # エラーパネルが表示されることを確認
        self.console.print.assert_called()
        call_args = self.console.print.call_args[0][0]
        # Panel オブジェクトが渡されることを確認
        from rich.panel import Panel

        assert isinstance(call_args, Panel)
        assert "❌ 予期しないエラー" in call_args.title

    def test_handle_unexpected_error_verbose(self):
        """予期しないエラーの詳細表示をテスト"""
        error = RuntimeError("Unexpected error")
        context = {"formatter_name": "ai"}

        with patch("traceback.format_exc", return_value="Mock traceback"):
            self.error_handler.handle_formatting_error(error, context, verbose=True)

        # スタックトレースが表示されることを確認
        assert self.console.print.call_count >= 2  # エラーパネル + スタックトレース

    def test_create_error_context(self):
        """エラーコンテキスト作成をテスト"""
        context = self.error_handler.create_error_context(
            formatter_name="ai",
            format_type="markdown",
            input_file=Path("test.log"),
            output_file=Path("output.md"),
            file_size_mb=10,
            custom_key="custom_value",
        )

        expected = {
            "formatter_name": "ai",
            "format_type": "markdown",
            "input_file": "test.log",
            "output_file": "output.md",
            "file_size_mb": 10,
            "custom_key": "custom_value",
        }

        assert context == expected

    def test_get_recovery_suggestions_log_formatting_error(self):
        """ログ整形エラーの復旧提案をテスト"""
        error = LogFormattingError.formatting_failed("ai", "Processing failed")
        suggestions = self.error_handler.get_recovery_suggestions(error)

        assert "別のフォーマッターを試してください" in suggestions
        assert "ログファイルの形式を確認してください" in suggestions
        assert "ストリーミング処理を有効にしてください" in suggestions

    def test_get_recovery_suggestions_file_operation_error(self):
        """ファイル操作エラーの復旧提案をテスト"""
        error = FileOperationError.file_not_found("test.log", "読み込み")
        suggestions = self.error_handler.get_recovery_suggestions(error)

        assert "ファイルパスを確認してください" in suggestions
        assert "権限を確認してください" in suggestions
        assert "ディスク容量を確認してください" in suggestions

    def test_get_recovery_suggestions_user_input_error(self):
        """ユーザー入力エラーの復旧提案をテスト"""
        error = UserInputError.invalid_format_type("invalid", ["ai", "human"])
        suggestions = self.error_handler.get_recovery_suggestions(error)

        assert "入力値を確認してください" in suggestions
        assert "ヘルプを参照してください" in suggestions
        assert "デフォルト値を使用してください" in suggestions

    def test_get_recovery_suggestions_generic_error(self):
        """一般的なエラーの復旧提案をテスト"""
        error = RuntimeError("Generic error")
        suggestions = self.error_handler.get_recovery_suggestions(error)

        assert "一時的な問題の可能性があります。再試行してください" in suggestions
        assert "詳細情報を得るには --verbose オプションを使用してください" in suggestions

    def test_format_error_summary(self):
        """エラー要約の生成をテスト"""
        error = LogFormattingError.formatter_not_found("invalid", ["ai", "human"])
        context = {
            "formatter_name": "invalid",
            "input_file": "test.log",
        }

        summary = self.error_handler.format_error_summary(error, context)

        assert "エラー種別: LogFormattingError" in summary
        assert "フォーマッター: invalid" in summary
        assert "入力ファイル: test.log" in summary

    def test_get_formatting_suggestions_ai_formatter(self):
        """AI フォーマッター固有の提案をテスト"""
        error = LogFormattingError.formatting_failed("ai", "Processing failed")
        context = {"file_size_mb": 100}

        suggestions = self.error_handler._get_formatting_suggestions(error, context)

        assert "AI フォーマッターは大きなログファイルに時間がかかる場合があります" in suggestions
        assert "human フォーマッターを試してみてください" in suggestions
        assert "大きなファイルの場合は streaming フォーマッターの使用を検討してください" in suggestions

    def test_get_formatting_suggestions_json_formatter(self):
        """JSON フォーマッター固有の提案をテスト"""
        error = LogFormattingError.formatting_failed("json", "Invalid data")
        context = {}

        suggestions = self.error_handler._get_formatting_suggestions(error, context)

        assert "JSON フォーマッターは構造化データが必要です" in suggestions
        assert "ログファイルが有効な形式か確認してください" in suggestions

    def test_get_file_operation_suggestions_read_operation(self):
        """読み込み操作の提案をテスト"""
        error = FileOperationError.file_not_found("test.log", "読み込み")
        context = {}

        suggestions = self.error_handler._get_file_operation_suggestions(error, context)

        assert "ファイルが存在するか確認してください" in suggestions
        assert "ファイルが他のプロセスで使用されていないか確認してください" in suggestions

    def test_get_file_operation_suggestions_write_operation(self):
        """書き込み操作の提案をテスト"""
        error = FileOperationError.permission_denied("output.txt", "書き込み")
        context = {}

        suggestions = self.error_handler._get_file_operation_suggestions(error, context)

        assert "出力ディレクトリに書き込み権限があるか確認してください" in suggestions
        assert "ディスク容量が十分にあるか確認してください" in suggestions

    def test_get_file_operation_suggestions_long_path(self):
        """長いパスの提案をテスト"""
        long_path = "a" * 250 + ".log"
        error = FileOperationError.path_too_long(long_path)
        context = {}

        suggestions = self.error_handler._get_file_operation_suggestions(error, context)

        assert "より短いファイルパスを使用してください" in suggestions

    def test_get_input_suggestions_format_type(self):
        """フォーマット種別入力の提案をテスト"""
        error = UserInputError.invalid_format_type("invalid", ["ai", "human", "json"])
        context = {}

        suggestions = self.error_handler._get_input_suggestions(error, context)

        assert "'ci-run format-logs --help' でサポートされているフォーマットを確認してください" in suggestions
        assert "ai、human、json のいずれかを指定してください" in suggestions

    def test_get_input_suggestions_file_extension(self):
        """ファイル拡張子入力の提案をテスト"""
        error = UserInputError.invalid_file_extension("test.xyz", [".log", ".txt"])
        context = {}

        suggestions = self.error_handler._get_input_suggestions(error, context)

        assert "ログファイルは通常 .log または .txt 拡張子を持ちます" in suggestions


class TestErrorHandlerIntegration:
    """エラーハンドラーの統合テスト"""

    def test_error_handler_with_real_console(self):
        """実際のコンソールでのエラーハンドラーをテスト"""
        console = Console(file=Mock(), width=80)
        error_handler = LogFormattingErrorHandler(console)

        error = LogFormattingError.formatter_not_found("invalid", ["ai", "human"])
        context = {"input_file": "test.log"}

        # エラーが発生しないことを確認
        error_handler.handle_formatting_error(error, context, verbose=False)

    def test_error_context_creation_with_none_values(self):
        """None 値を含むエラーコンテキスト作成をテスト"""
        console = Console(file=Mock())
        error_handler = LogFormattingErrorHandler(console)

        context = error_handler.create_error_context(
            formatter_name=None,
            format_type="ai",
            input_file=None,
            output_file=None,
        )

        expected = {"format_type": "ai"}
        assert context == expected

    def test_multiple_error_handling(self):
        """複数のエラーの連続処理をテスト"""
        console = Mock(spec=Console)
        error_handler = LogFormattingErrorHandler(console)

        errors = [
            LogFormattingError.formatter_not_found("invalid", ["ai"]),
            FileOperationError.file_not_found("test.log", "読み込み"),
            UserInputError.invalid_format_type("bad", ["ai"]),
        ]

        for error in errors:
            error_handler.handle_formatting_error(error, {}, verbose=False)

        # 各エラーに対してパネルが表示されることを確認
        assert console.print.call_count == len(errors)
