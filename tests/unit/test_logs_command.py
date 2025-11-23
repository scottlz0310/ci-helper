"""
logs コマンドの詳細ユニットテスト

ログ管理機能の個別テストを提供します。
"""

from pathlib import Path
from unittest.mock import Mock, patch

from ci_helper.cli import cli
from ci_helper.commands.logs import (
    _display_diff_table,
    _display_initial_execution,
    _display_logs_table,
    _show_log_content,
    _show_log_diff,
    _show_log_statistics,
)
from click.testing import CliRunner


class TestShowLogStatistics:
    """ログ統計表示のテスト"""

    @patch("ci_helper.commands.logs.console")
    def test_show_log_statistics_basic(self, mock_console):
        """基本的なログ統計表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_log_statistics.return_value = {
            "total_logs": 15,
            "total_size_mb": 45.2,
            "success_rate": 80,
            "average_duration": 120.5,
            "latest_execution": "2024-01-01 12:00:00",
        }

        _show_log_statistics(mock_log_manager)

        mock_console.print.assert_called()
        mock_log_manager.get_log_statistics.assert_called_once()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_statistics_no_latest(self, mock_console):
        """最新実行がない場合のログ統計表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_log_statistics.return_value = {
            "total_logs": 0,
            "total_size_mb": 0.0,
            "success_rate": 0,
            "average_duration": 0.0,
            "latest_execution": None,
        }

        _show_log_statistics(mock_log_manager)

        mock_console.print.assert_called()


class TestShowLogContent:
    """ログ内容表示のテスト"""

    @patch("ci_helper.commands.logs.console")
    def test_show_log_content_basic(self, mock_console):
        """基本的なログ内容表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_log_content.return_value = "Test log content\nLine 2\nLine 3"

        _show_log_content(mock_log_manager, "test.log", verbose=False)

        mock_log_manager.get_log_content.assert_called_once_with("test.log")
        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_content_verbose(self, mock_console):
        """詳細モードでのログ内容表示テスト"""
        mock_log_manager = Mock()
        long_content = "\n".join([f"Line {i}" for i in range(1, 51)])
        mock_log_manager.get_log_content.return_value = long_content

        _show_log_content(mock_log_manager, "test.log", verbose=True)

        # 詳細モードでは全内容が表示される
        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_content_long_file(self, mock_console):
        """長いログファイルの表示テスト"""
        mock_log_manager = Mock()
        # 150行のログを作成
        long_content = "\n".join([f"Line {i}" for i in range(1, 151)])
        mock_log_manager.get_log_content.return_value = long_content

        _show_log_content(mock_log_manager, "test.log", verbose=False)

        # 省略表示されることを確認
        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_content_error(self, mock_console):
        """ログ内容取得エラーのテスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_log_content.side_effect = Exception("File not found")

        _show_log_content(mock_log_manager, "test.log", verbose=False)

        # エラーメッセージが表示されることを確認
        mock_console.print.assert_called()


class TestDisplayLogsTable:
    """ログテーブル表示のテスト"""

    @patch("ci_helper.commands.logs.console")
    def test_display_logs_table_basic(self, mock_console):
        """基本的なログテーブル表示テスト"""
        logs_list = [
            {
                "timestamp": "2024-01-01T12:00:00",
                "log_file": "act_20240101_120000.log",
                "success": True,
                "total_duration": 120.5,
                "total_failures": 0,
                "workflows": ["test.yml", "build.yml"],
            },
            {
                "timestamp": "2024-01-01T11:00:00",
                "log_file": "act_20240101_110000.log",
                "success": False,
                "total_duration": 85.2,
                "total_failures": 3,
                "workflows": ["test.yml"],
            },
        ]

        _display_logs_table(logs_list)

        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_display_logs_table_with_filter(self, mock_console):
        """ワークフローフィルター付きのログテーブル表示テスト"""
        logs_list = [
            {
                "timestamp": "2024-01-01T12:00:00",
                "log_file": "act_20240101_120000.log",
                "success": True,
                "total_duration": 120.5,
                "total_failures": 0,
                "workflows": ["test.yml"],
            }
        ]

        _display_logs_table(logs_list, workflow_filter="test.yml")

        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_display_logs_table_empty(self, mock_console):
        """空のログリストの表示テスト"""
        logs_list: list[dict[str, str]] = []

        _display_logs_table(logs_list)

        mock_console.print.assert_called()


class TestShowLogDiff:
    """ログ差分表示のテスト"""

    @patch("ci_helper.commands.logs.LogManager")
    @patch("ci_helper.commands.logs.console")
    def test_show_log_diff_success(self, mock_console, mock_log_manager_class):
        """ログ差分表示成功のテスト"""
        # モックの実行履歴を作成
        mock_target_execution = Mock()
        mock_target_execution.log_path = "act_20240101_120000.log"
        mock_previous_execution = Mock()

        mock_log_manager = Mock()
        mock_log_manager.get_execution_history.return_value = [
            mock_target_execution,
            mock_previous_execution,
        ]

        with patch("ci_helper.core.log_comparator.LogComparator") as mock_comparator_class:
            mock_comparator = Mock()
            mock_comparison = Mock()
            mock_comparator.compare_executions.return_value = mock_comparison
            mock_comparator.format_diff_display.return_value = "Diff output"
            mock_comparator_class.return_value = mock_comparator

            _show_log_diff(mock_log_manager, "act_20240101_120000.log", "json", verbose=False)

            mock_comparator.compare_executions.assert_called_once()
            mock_comparator.format_diff_display.assert_called_once()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_diff_file_not_found(self, mock_console):
        """指定ログファイルが見つからない場合のテスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_execution_history.return_value = []

        _show_log_diff(mock_log_manager, "nonexistent.log", "table", verbose=False)

        # エラーメッセージが表示されることを確認
        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs._display_initial_execution")
    @patch("ci_helper.commands.logs.console")
    def test_show_log_diff_no_previous(self, mock_console, mock_display_initial):
        """前回実行が存在しない場合のテスト"""
        mock_target_execution = Mock()
        mock_target_execution.log_path = "act_20240101_120000.log"

        mock_log_manager = Mock()
        mock_log_manager.get_execution_history.return_value = [mock_target_execution]

        _show_log_diff(mock_log_manager, "act_20240101_120000.log", "table", verbose=False)

        # 初回実行として表示されることを確認
        mock_display_initial.assert_called_once()

    @patch("ci_helper.commands.logs._display_diff_table")
    @patch("ci_helper.core.log_comparator.LogComparator")
    @patch("ci_helper.commands.logs.console")
    def test_show_log_diff_table_format(self, mock_console, mock_comparator_class, mock_display_table):
        """テーブル形式での差分表示テスト"""
        mock_target_execution = Mock()
        mock_target_execution.log_path = "act_20240101_120000.log"
        mock_previous_execution = Mock()

        mock_log_manager = Mock()
        mock_log_manager.get_execution_history.return_value = [
            mock_target_execution,
            mock_previous_execution,
        ]

        mock_comparator = Mock()
        mock_comparison = Mock()
        mock_comparator.compare_executions.return_value = mock_comparison
        mock_comparator_class.return_value = mock_comparator

        _show_log_diff(mock_log_manager, "act_20240101_120000.log", "table", verbose=False)

        mock_display_table.assert_called_once()

    @patch("ci_helper.commands.logs.console")
    def test_show_log_diff_error(self, mock_console):
        """差分表示中のエラーテスト"""
        mock_log_manager = Mock()
        mock_log_manager.get_execution_history.side_effect = Exception("Database error")

        _show_log_diff(mock_log_manager, "test.log", "table", verbose=False)

        # エラーメッセージが表示されることを確認
        mock_console.print.assert_called()


class TestDisplayInitialExecution:
    """初回実行表示のテスト"""

    @patch("ci_helper.commands.logs.console")
    def test_display_initial_execution_json(self, mock_console):
        """JSON形式での初回実行表示テスト"""
        from datetime import datetime

        mock_execution = Mock()
        mock_execution.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_execution.success = True
        mock_execution.total_failures = 0
        mock_execution.total_duration = 120.5
        mock_execution.workflows = []

        _display_initial_execution(mock_execution, "json")

        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_display_initial_execution_markdown(self, mock_console):
        """Markdown形式での初回実行表示テスト"""
        from datetime import datetime

        mock_workflow = Mock()
        mock_workflow.name = "test.yml"
        mock_workflow.success = True
        mock_workflow.duration = 60.0

        mock_execution = Mock()
        mock_execution.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_execution.success = True
        mock_execution.total_failures = 0
        mock_execution.total_duration = 120.5
        mock_execution.workflows = [mock_workflow]

        _display_initial_execution(mock_execution, "markdown")

        mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.console")
    def test_display_initial_execution_table(self, mock_console):
        """テーブル形式での初回実行表示テスト"""
        from datetime import datetime

        mock_execution = Mock()
        mock_execution.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_execution.success = False
        mock_execution.total_failures = 2
        mock_execution.total_duration = 85.2
        mock_execution.workflows = []

        _display_initial_execution(mock_execution, "table")

        mock_console.print.assert_called()


class TestDisplayDiffTable:
    """差分テーブル表示のテスト"""

    @patch("ci_helper.core.log_comparator.LogComparator")
    @patch("ci_helper.commands.logs.console")
    def test_display_diff_table_basic(self, mock_console, mock_comparator_class):
        """基本的な差分テーブル表示テスト"""
        mock_comparator = Mock()
        mock_summary = {
            "current_status": "success",
            "previous_status": "failure",
            "error_counts": {
                "current": 0,
                "previous": 3,
                "net_change": -3,
            },
            "performance": {
                "current_duration": 120.0,
                "previous_duration": 150.0,
                "time_change_percent": -20.0,
            },
        }
        mock_comparator.generate_diff_summary.return_value = mock_summary
        mock_comparator_class.return_value = mock_comparator

        mock_comparison = Mock()
        mock_comparison.new_errors = []
        mock_comparison.resolved_errors = []
        mock_comparison.persistent_errors = []

        _display_diff_table(mock_comparison, verbose=False)

        mock_console.print.assert_called()

    @patch("ci_helper.core.log_comparator.LogComparator")
    @patch("ci_helper.commands.logs.console")
    def test_display_diff_table_with_errors(self, mock_console, mock_comparator_class):
        """エラー情報付きの差分テーブル表示テスト"""
        mock_comparator = Mock()
        mock_summary = {
            "current_status": "failure",
            "previous_status": "success",
            "error_counts": {
                "current": 2,
                "previous": 0,
                "net_change": 2,
            },
            "performance": {
                "current_duration": 90.0,
                "previous_duration": 120.0,
                "time_change_percent": -25.0,
            },
        }
        mock_comparator.generate_diff_summary.return_value = mock_summary
        mock_comparator_class.return_value = mock_comparator

        mock_error = Mock()
        mock_error.type = Mock()
        mock_error.type.value = "error"

        mock_comparison = Mock()
        mock_comparison.new_errors = [mock_error]
        mock_comparison.resolved_errors = []
        mock_comparison.persistent_errors = []

        _display_diff_table(mock_comparison, verbose=False)

        mock_console.print.assert_called()

    @patch("ci_helper.core.log_comparator.LogComparator")
    @patch("ci_helper.commands.logs.console")
    def test_display_diff_table_verbose(self, mock_console, mock_comparator_class):
        """詳細モードでの差分テーブル表示テスト"""
        mock_comparator = Mock()
        mock_summary = {
            "current_status": "success",
            "previous_status": "success",
            "error_counts": {
                "current": 1,
                "previous": 2,
                "net_change": -1,
            },
            "performance": {
                "current_duration": 100.0,
                "previous_duration": 100.0,
                "time_change_percent": 0.0,
            },
        }
        mock_comparator.generate_diff_summary.return_value = mock_summary
        mock_comparator_class.return_value = mock_comparator

        mock_error = Mock()
        mock_error.type = Mock()
        mock_error.type.value = "error"
        mock_error.message = "Test error message"
        mock_error.file_path = "test.py"
        mock_error.line_number = 42

        mock_comparison = Mock()
        mock_comparison.new_errors = [mock_error]
        mock_comparison.resolved_errors = [mock_error]
        mock_comparison.persistent_errors = []

        _display_diff_table(mock_comparison, verbose=True)

        mock_console.print.assert_called()


class TestLogsCommandIntegration:
    """logs コマンドの統合テスト"""

    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_basic_listing(self, mock_log_manager_class):
        """基本的なログ一覧表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.list_logs.return_value = [
            {
                "timestamp": "2024-01-01T12:00:00",
                "log_file": "act_20240101_120000.log",
                "success": True,
                "total_duration": 120.5,
                "total_failures": 0,
                "workflows": ["test.yml"],
            }
        ]
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs"])

            assert result.exit_code == 0
            mock_log_manager.list_logs.assert_called_once_with(10)

    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_with_limit(self, mock_log_manager_class):
        """制限数指定でのログ一覧表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.list_logs.return_value = []
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--limit", "20"])

            assert result.exit_code == 0
            mock_log_manager.list_logs.assert_called_once_with(20)

    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_workflow_filter(self, mock_log_manager_class):
        """ワークフローフィルターでのログ表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager.find_logs_by_workflow.return_value = []
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--workflow", "test.yml"])

            assert result.exit_code == 0
            mock_log_manager.find_logs_by_workflow.assert_called_once_with("test.yml")

    @patch("ci_helper.commands.logs._show_log_statistics")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_stats(self, mock_log_manager_class, mock_show_stats):
        """統計情報表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--stats"])

            assert result.exit_code == 0
            mock_show_stats.assert_called_once_with(mock_log_manager)

    @patch("ci_helper.commands.logs._show_log_content")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_show_content(self, mock_log_manager_class, mock_show_content):
        """ログ内容表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--show-content", "test.log"])

            assert result.exit_code == 0
            mock_show_content.assert_called_once()

    @patch("ci_helper.commands.logs._show_log_diff")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_diff(self, mock_log_manager_class, mock_show_diff):
        """差分表示テスト"""
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--diff", "test.log"])

            assert result.exit_code == 0
            mock_show_diff.assert_called_once()

    @patch("ci_helper.commands.logs.LogManager")
    @patch("ci_helper.commands.logs.console")
    def test_logs_command_no_logs(self, mock_console, mock_log_manager_class):
        """ログが存在しない場合のテスト"""
        mock_log_manager = Mock()
        mock_log_manager.list_logs.return_value = []
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs"])

            assert result.exit_code == 0
            # ログが見つからないメッセージが表示されることを確認
            mock_console.print.assert_called()

    @patch("ci_helper.commands.logs.LogManager")
    @patch("ci_helper.commands.logs.console")
    def test_logs_command_workflow_not_found(self, mock_console, mock_log_manager_class):
        """指定ワークフローのログが見つからない場合のテスト"""
        mock_log_manager = Mock()
        mock_log_manager.find_logs_by_workflow.return_value = []
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--workflow", "nonexistent.yml"])

            assert result.exit_code == 0
            # ワークフローが見つからないメッセージが表示されることを確認
            mock_console.print.assert_called()

    def test_logs_command_format_options(self):
        """差分表示フォーマットオプションのテスト"""
        formats = ["table", "markdown", "json"]

        for format_option in formats:
            with patch("ci_helper.commands.logs._show_log_diff") as mock_show_diff:
                with patch("ci_helper.core.log_manager.LogManager") as mock_log_manager_class:
                    mock_log_manager = Mock()
                    mock_log_manager_class.return_value = mock_log_manager

                    runner = CliRunner()
                    with runner.isolated_filesystem():
                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                        result = runner.invoke(cli, ["logs", "--diff", "test.log", "--format", format_option])

                        assert result.exit_code == 0
                        # 指定されたフォーマットが渡されることを確認
                        call_args = mock_show_diff.call_args
                        assert call_args[0][2] == format_option

    @patch("ci_helper.core.error_handler.ErrorHandler.handle_error")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_command_error_handling(self, mock_log_manager_class, mock_error_handler):
        """エラーハンドリングのテスト"""
        from ci_helper.core.exceptions import CIHelperError

        mock_log_manager = Mock()
        mock_log_manager.list_logs.side_effect = CIHelperError("ログ読み込みエラー", "権限を確認してください")
        mock_log_manager_class.return_value = mock_log_manager

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs"])

            assert result.exit_code == 1
            mock_error_handler.assert_called_once()
