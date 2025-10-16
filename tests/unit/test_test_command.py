"""
test コマンドの詳細ユニットテスト

CI実行機能の個別テストを提供します。
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from ci_helper.cli import cli
from ci_helper.commands.test import (
    _analyze_existing_log,
    _check_dependencies,
    _display_json_results,
    _display_markdown_results,
    _display_table_results,
    _show_diff_with_previous,
)


def create_mock_execution_result():
    """テスト用のExecutionResultモックを作成"""
    mock_execution_result = Mock()
    mock_execution_result.workflows = []
    mock_execution_result.total_failures = 0
    mock_execution_result.total_duration = 10.5
    mock_execution_result.timestamp = Mock()
    mock_execution_result.timestamp.strftime.return_value = "2024-01-01 12:00:00"
    mock_execution_result.all_failures = []
    return mock_execution_result


class TestCheckDependencies:
    """依存関係チェックのテスト"""

    @patch("ci_helper.core.error_handler.DependencyChecker")
    @patch("ci_helper.commands.test.console")
    def test_check_dependencies_success(self, mock_console, mock_dependency_checker):
        """依存関係チェック成功のテスト"""
        mock_dependency_checker.check_act_command.return_value = None
        mock_dependency_checker.check_docker_daemon.return_value = None
        mock_dependency_checker.check_workflows_directory.return_value = None
        mock_dependency_checker.check_disk_space.return_value = None

        # 例外が発生しないことを確認
        _check_dependencies(verbose=False)

        mock_dependency_checker.check_act_command.assert_called_once()
        mock_dependency_checker.check_docker_daemon.assert_called_once()
        mock_dependency_checker.check_workflows_directory.assert_called_once()
        mock_dependency_checker.check_disk_space.assert_called_once()

    @patch("ci_helper.core.error_handler.DependencyChecker")
    @patch("ci_helper.commands.test.console")
    def test_check_dependencies_verbose(self, mock_console, mock_dependency_checker):
        """詳細モードでの依存関係チェック"""
        mock_dependency_checker.check_act_command.return_value = None
        mock_dependency_checker.check_docker_daemon.return_value = None
        mock_dependency_checker.check_workflows_directory.return_value = None
        mock_dependency_checker.check_disk_space.return_value = None

        _check_dependencies(verbose=True)

        # 詳細メッセージが表示されることを確認
        mock_console.print.assert_called()

    @patch("ci_helper.core.error_handler.DependencyChecker")
    def test_check_dependencies_failure(self, mock_dependency_checker):
        """依存関係チェック失敗のテスト"""
        from ci_helper.core.exceptions import DependencyError

        mock_dependency_checker.check_act_command.side_effect = DependencyError(
            "act が見つかりません", "インストールしてください"
        )

        with pytest.raises(DependencyError):
            _check_dependencies(verbose=False)


class TestAnalyzeExistingLog:
    """既存ログ解析のテスト"""

    @patch("ci_helper.commands.test.console")
    def test_analyze_existing_log_basic(self, mock_console, temp_dir: Path):
        """基本的なログ解析テスト"""
        log_file = temp_dir / "test.log"
        log_content = """
[2024-01-01T12:00:00Z] Starting workflow
[2024-01-01T12:00:01Z] Running job: test
[2024-01-01T12:00:02Z] Step completed successfully
[2024-01-01T12:00:03Z] Workflow completed
"""
        log_file.write_text(log_content)

        _analyze_existing_log(log_file, "table", verbose=False)

        # コンソール出力が呼ばれることを確認
        mock_console.print.assert_called()

    @patch("ci_helper.commands.test.console")
    def test_analyze_existing_log_json_format(self, mock_console, temp_dir: Path):
        """JSON形式でのログ解析テスト"""
        log_file = temp_dir / "test.log"
        log_file.write_text("test log content\nline 2\nline 3")

        _analyze_existing_log(log_file, "json", verbose=False)

        # JSON出力が呼ばれることを確認
        mock_console.print.assert_called()
        call_args = mock_console.print.call_args[0][0]
        assert "log_file" in call_args
        assert "total_lines" in call_args

    @patch("ci_helper.commands.test.console")
    def test_analyze_existing_log_markdown_format(self, mock_console, temp_dir: Path):
        """Markdown形式でのログ解析テスト"""
        log_file = temp_dir / "test.log"
        log_file.write_text("test log content")

        _analyze_existing_log(log_file, "markdown", verbose=False)

        # Markdown出力が呼ばれることを確認
        mock_console.print.assert_called()
        call_args = mock_console.print.call_args[0][0]
        assert "# ログ解析結果" in call_args

    def test_analyze_existing_log_file_not_found(self, temp_dir: Path):
        """存在しないログファイルの解析テスト"""
        from ci_helper.core.exceptions import LogParsingError

        log_file = temp_dir / "nonexistent.log"

        with pytest.raises(LogParsingError):
            _analyze_existing_log(log_file, "table", verbose=False)

    def test_analyze_existing_log_permission_error(self, temp_dir: Path):
        """権限エラーでのログ解析テスト"""
        from ci_helper.core.exceptions import LogParsingError

        log_file = temp_dir / "test.log"
        log_file.write_text("test content")

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(LogParsingError):
                _analyze_existing_log(log_file, "table", verbose=False)


class TestShowDiffWithPrevious:
    """前回実行との差分表示のテスト"""

    @patch("ci_helper.commands.test.LogManager")
    @patch("ci_helper.commands.test.console")
    def test_show_diff_success(self, mock_console, mock_log_manager):
        """差分表示成功のテスト"""
        from pathlib import Path

        mock_config = Mock()
        mock_config.get_path.return_value = Path("/tmp/test_logs")
        mock_current_result = Mock()
        mock_current_result.timestamp = "2024-01-01T12:00:00"

        mock_previous_result = Mock()
        mock_manager_instance = Mock()
        mock_manager_instance.get_previous_execution.return_value = mock_previous_result
        mock_log_manager.return_value = mock_manager_instance

        with patch("ci_helper.core.log_comparator.LogComparator") as mock_comparator:
            mock_comparator_instance = Mock()
            mock_comparison = Mock()
            mock_comparator_instance.compare_executions.return_value = mock_comparison
            mock_comparator.return_value = mock_comparator_instance

            with patch("ci_helper.commands.test._display_diff_summary") as mock_display:
                _show_diff_with_previous(mock_config, mock_current_result, verbose=False)

                mock_log_manager.assert_called_once_with(mock_config)
                mock_manager_instance.get_previous_execution.assert_called_once_with("2024-01-01T12:00:00")
                mock_comparator_instance.compare_executions.assert_called_once_with(
                    mock_current_result, mock_previous_result
                )
                mock_display.assert_called_once_with(mock_comparison, False)

    @patch("ci_helper.core.log_manager.LogManager")
    @patch("ci_helper.commands.test.console")
    def test_show_diff_no_previous(self, mock_console, mock_log_manager):
        """前回実行が存在しない場合のテスト"""
        from pathlib import Path

        mock_config = Mock()
        mock_config.get_path.return_value = Path("/tmp/test_logs")
        mock_current_result = Mock()
        mock_current_result.timestamp = "2024-01-01T12:00:00"

        mock_manager_instance = Mock()
        mock_manager_instance.get_previous_execution.return_value = None
        mock_log_manager.return_value = mock_manager_instance

        _show_diff_with_previous(mock_config, mock_current_result, verbose=False)

        # 警告メッセージが表示されることを確認
        mock_console.print.assert_called()
        call_args = mock_console.print.call_args[0][0]
        assert "見つかりません" in call_args

    @patch("ci_helper.core.log_manager.LogManager")
    @patch("ci_helper.commands.test.console")
    def test_show_diff_error(self, mock_console, mock_log_manager):
        """差分計算でエラーが発生する場合のテスト"""
        from pathlib import Path

        mock_config = Mock()
        mock_config.get_path.return_value = Path("/tmp/test_logs")
        mock_current_result = Mock()
        mock_current_result.timestamp = "2024-01-01T12:00:00"

        mock_manager_instance = Mock()
        mock_manager_instance.get_previous_execution.side_effect = Exception("Database error")
        mock_log_manager.return_value = mock_manager_instance

        _show_diff_with_previous(mock_config, mock_current_result, verbose=True)

        # エラーメッセージが表示されることを確認
        mock_console.print.assert_called()

    @patch("ci_helper.core.log_manager.LogManager")
    @patch("ci_helper.commands.test.console")
    def test_show_diff_verbose_mode(self, mock_console, mock_log_manager):
        """詳細モードでの差分表示テスト"""
        from pathlib import Path

        mock_config = Mock()
        mock_config.get_path.return_value = Path("/tmp/test_logs")
        mock_current_result = Mock()
        mock_current_result.timestamp = "2024-01-01T12:00:00"

        mock_manager_instance = Mock()
        mock_manager_instance.get_previous_execution.side_effect = Exception("Test error")
        mock_log_manager.return_value = mock_manager_instance

        _show_diff_with_previous(mock_config, mock_current_result, verbose=True)

        # 詳細エラーメッセージが表示されることを確認
        mock_console.print.assert_called()


class TestDisplayResults:
    """結果表示のテスト"""

    def test_display_table_results(self):
        """テーブル形式結果表示のテスト"""
        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.total_duration = 10.5
        mock_execution_result.total_failures = 0
        mock_execution_result.workflows = []
        mock_execution_result.log_path = "test.log"

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_table_results(mock_execution_result, verbose=False, dry_run=False)

            mock_console.print.assert_called()

    def test_display_table_results_with_workflows(self):
        """ワークフロー情報を含むテーブル表示のテスト"""
        mock_workflow = Mock()
        mock_workflow.name = "test.yml"
        mock_workflow.success = True
        mock_workflow.duration = 5.0
        mock_workflow.jobs = []

        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.total_duration = 10.5
        mock_execution_result.total_failures = 0
        mock_execution_result.workflows = [mock_workflow]
        mock_execution_result.log_path = "test.log"

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_table_results(mock_execution_result, verbose=False, dry_run=False)

            mock_console.print.assert_called()

    def test_display_table_results_verbose_with_jobs(self):
        """詳細モードでのジョブ情報表示テスト"""
        mock_job = Mock()
        mock_job.name = "test-job"
        mock_job.success = True
        mock_job.duration = 3.0
        mock_job.steps = []
        mock_job.failures = []

        mock_workflow = Mock()
        mock_workflow.name = "test.yml"
        mock_workflow.success = True
        mock_workflow.duration = 5.0
        mock_workflow.jobs = [mock_job]

        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.total_duration = 10.5
        mock_execution_result.total_failures = 0
        mock_execution_result.workflows = [mock_workflow]
        mock_execution_result.log_path = "test.log"

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_table_results(mock_execution_result, verbose=True, dry_run=False)

            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_json_results(self, mock_ai_formatter):
        """JSON形式結果表示のテスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_json.return_value = '{"success": true}'
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": False,
            "secret_count": 0,
        }
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_json_results(mock_execution_result, verbose=False, dry_run=False, sanitize=True)

            mock_formatter_instance.format_json.assert_called_once()
            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_json_results_with_secrets(self, mock_ai_formatter):
        """シークレット検出ありのJSON表示テスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_json.return_value = '{"success": true}'
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": True,
            "secret_count": 2,
        }
        mock_formatter_instance.check_token_limits.return_value = {
            "token_count": 1000,
            "token_limit": 4000,
            "usage_percentage": 25.0,
            "warning_level": "none",
            "warning_message": "",
        }
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_json_results(mock_execution_result, verbose=True, dry_run=False, sanitize=True)

            # セキュリティ警告が表示されることを確認
            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_json_results_with_token_info(self, mock_ai_formatter):
        """トークン情報付きのJSON表示テスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_json.return_value = '{"success": true}'
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": False,
            "secret_count": 0,
        }
        mock_formatter_instance.check_token_limits.return_value = {
            "token_count": 1000,
            "token_limit": 4000,
            "usage_percentage": 25.0,
            "warning_level": "none",
            "warning_message": "",
        }
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_json_results(mock_execution_result, verbose=True, dry_run=False, sanitize=True)

            # トークン情報が表示されることを確認
            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_markdown_results(self, mock_ai_formatter):
        """Markdown形式結果表示のテスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown.return_value = "# Test Results\n**Status**: Success"
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": False,
            "secret_count": 0,
        }
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_markdown_results(mock_execution_result, verbose=False, dry_run=False, sanitize=True)

            mock_formatter_instance.format_markdown.assert_called_once()
            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_markdown_results_dry_run(self, mock_ai_formatter):
        """ドライラン時のMarkdown表示テスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown.return_value = "**ステータス**: Success"
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": False,
            "secret_count": 0,
        }
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_markdown_results(mock_execution_result, verbose=False, dry_run=True, sanitize=True)

            # ドライラン用のヘッダーが追加されることを確認
            mock_console.print.assert_called()

    @patch("ci_helper.commands.test.AIFormatter")
    def test_display_markdown_results_with_compression_suggestions(self, mock_ai_formatter):
        """圧縮提案付きのMarkdown表示テスト"""
        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown.return_value = "# Test Results"
        mock_formatter_instance.validate_output_security.return_value = {
            "has_secrets": False,
            "secret_count": 0,
        }
        mock_formatter_instance.check_token_limits.return_value = {
            "token_count": 8000,
            "token_limit": 4000,
            "usage_percentage": 200.0,
            "warning_level": "high",
            "warning_message": "Token limit exceeded",
        }
        mock_formatter_instance.suggest_compression_options.return_value = [
            "Remove verbose logs",
            "Summarize stack traces",
            "Filter common errors",
        ]
        mock_ai_formatter.return_value = mock_formatter_instance

        mock_execution_result = create_mock_execution_result()

        with patch("ci_helper.commands.test.console") as mock_console:
            _display_markdown_results(mock_execution_result, verbose=True, dry_run=False, sanitize=True)

            # 圧縮提案が表示されることを確認
            mock_console.print.assert_called()


class TestTestCommandIntegration:
    """test コマンドの統合テスト"""

    @patch("ci_helper.commands.test._check_dependencies")
    @patch("ci_helper.commands.test.CIRunner")
    def test_test_command_basic_execution(self, mock_ci_runner, mock_check_deps):
        """基本的なtest コマンド実行テスト"""
        mock_runner_instance = Mock()
        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.total_duration = 10.5
        mock_execution_result.total_failures = 0
        mock_execution_result.workflows = []
        mock_execution_result.log_path = "test.log"
        mock_runner_instance.run_workflows.return_value = mock_execution_result
        mock_ci_runner.return_value = mock_runner_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["test"])

            assert result.exit_code == 0
            mock_check_deps.assert_called_once()
            mock_runner_instance.run_workflows.assert_called_once()

    @patch("ci_helper.commands.test._check_dependencies")
    @patch("ci_helper.commands.test.CIRunner")
    def test_test_command_with_failure(self, mock_ci_runner, mock_check_deps):
        """失敗を含むtest コマンド実行テスト"""
        mock_runner_instance = Mock()
        mock_execution_result = Mock()
        mock_execution_result.success = False
        mock_execution_result.total_duration = 5.0
        mock_execution_result.total_failures = 2
        mock_execution_result.workflows = []
        mock_execution_result.log_path = "test.log"
        mock_runner_instance.run_workflows.return_value = mock_execution_result
        mock_ci_runner.return_value = mock_runner_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["test"])

            assert result.exit_code == 1  # 失敗時は終了コード1

    def test_test_command_dry_run_with_log_file(self):
        """ログファイル指定でのドライラン実行テスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # テスト用ログファイルを作成
            log_file = Path("test.log")
            log_file.write_text("test log content")

            result = runner.invoke(cli, ["test", "--dry-run", "--log", str(log_file)])

            assert result.exit_code == 0

    @patch("ci_helper.commands.test._check_dependencies")
    @patch("ci_helper.commands.test.CIRunner")
    def test_test_command_with_diff(self, mock_ci_runner, mock_check_deps):
        """差分表示付きのtest コマンド実行テスト"""
        mock_runner_instance = Mock()
        mock_execution_result = Mock()
        mock_execution_result.success = True
        mock_execution_result.total_duration = 10.5
        mock_execution_result.total_failures = 0
        mock_execution_result.workflows = []
        mock_execution_result.log_path = "test.log"
        mock_runner_instance.run_workflows.return_value = mock_execution_result
        mock_ci_runner.return_value = mock_runner_instance

        with patch("ci_helper.commands.test._show_diff_with_previous") as mock_show_diff:
            runner = CliRunner()
            with runner.isolated_filesystem():
                Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                result = runner.invoke(cli, ["test", "--diff"])

                assert result.exit_code == 0
                mock_show_diff.assert_called_once()

    def test_test_command_multiple_workflows(self):
        """複数ワークフロー指定のテスト"""
        with patch("ci_helper.commands.test._check_dependencies"):
            with patch("ci_helper.commands.test.CIRunner") as mock_ci_runner:
                mock_runner_instance = Mock()
                mock_execution_result = Mock()
                mock_execution_result.success = True
                mock_execution_result.total_duration = 15.0
                mock_execution_result.total_failures = 0
                mock_execution_result.workflows = []
                mock_runner_instance.run_workflows.return_value = mock_execution_result
                mock_ci_runner.return_value = mock_runner_instance

                runner = CliRunner()
                with runner.isolated_filesystem():
                    Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                    result = runner.invoke(cli, ["test", "-w", "test.yml", "-w", "build.yml", "-w", "deploy.yml"])

                    assert result.exit_code == 0
                    # 指定されたワークフローが渡されることを確認
                    call_args = mock_runner_instance.run_workflows.call_args
                    assert call_args[1]["workflows"] == ["test.yml", "build.yml", "deploy.yml"]

    @patch("ci_helper.commands.test._check_dependencies")
    def test_test_command_dependency_error(self, mock_check_deps):
        """依存関係エラーのテスト"""
        from ci_helper.core.exceptions import DependencyError

        mock_check_deps.side_effect = DependencyError("act が見つかりません", "インストールしてください")

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["test"])

            assert result.exit_code == 1

    def test_test_command_all_format_options(self):
        """全フォーマットオプションのテスト"""
        formats = ["table", "json", "markdown"]

        for format_option in formats:
            with patch("ci_helper.commands.test._check_dependencies"):
                with patch("ci_helper.commands.test.CIRunner") as mock_ci_runner:
                    mock_runner_instance = Mock()
                    mock_execution_result = Mock()
                    mock_execution_result.success = True
                    mock_execution_result.total_duration = 5.0
                    mock_execution_result.total_failures = 0
                    mock_execution_result.workflows = []
                    mock_runner_instance.run_workflows.return_value = mock_execution_result
                    mock_ci_runner.return_value = mock_runner_instance

                    runner = CliRunner()
                    with runner.isolated_filesystem():
                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                        result = runner.invoke(cli, ["test", "--format", format_option])

                        assert result.exit_code == 0

    def test_test_command_sanitize_options(self):
        """サニタイズオプションのテスト"""
        sanitize_options = ["--sanitize", "--no-sanitize"]

        for sanitize_option in sanitize_options:
            with patch("ci_helper.commands.test._check_dependencies"):
                with patch("ci_helper.commands.test.CIRunner") as mock_ci_runner:
                    mock_runner_instance = Mock()
                    mock_execution_result = Mock()
                    mock_execution_result.success = True
                    mock_execution_result.total_duration = 5.0
                    mock_execution_result.total_failures = 0
                    mock_execution_result.workflows = []
                    mock_runner_instance.run_workflows.return_value = mock_execution_result
                    mock_ci_runner.return_value = mock_runner_instance

                    runner = CliRunner()
                    with runner.isolated_filesystem():
                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                        result = runner.invoke(cli, ["test", sanitize_option])

                        assert result.exit_code == 0
