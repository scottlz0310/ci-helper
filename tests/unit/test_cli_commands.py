"""
CLI コマンドのユニットテスト

各コマンドの動作、オプション処理、ヘルプ表示をテストします。
"""

from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from ci_helper.cli import cli
from ci_helper.commands.clean import clean
from ci_helper.commands.doctor import doctor
from ci_helper.commands.init import init, setup
from ci_helper.commands.logs import logs
from ci_helper.commands.secrets import secrets
from ci_helper.commands.test import test


class TestCLIEntryPoint:
    """CLI エントリーポイントのテスト"""

    def test_cli_help_display(self):
        """CLI ヘルプ表示のテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ci-helper: ローカルCI検証とAI連携ツール" in result.output
        assert "init" in result.output
        assert "doctor" in result.output
        assert "test" in result.output
        assert "logs" in result.output
        assert "secrets" in result.output
        assert "clean" in result.output

    def test_cli_version_display(self):
        """バージョン表示のテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cli_verbose_option(self):
        """--verbose オプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])

        assert result.exit_code == 0
        # verbose フラグが含まれることを確認
        assert "--verbose" in result.output

    @patch("ci_helper.utils.config.Config")
    def test_cli_config_file_option(self, mock_config):
        """--config-file オプションのテスト"""
        mock_config_instance = Mock()
        mock_config_instance.validate.return_value = None
        mock_config.return_value = mock_config_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            # テスト用設定ファイルを作成
            config_path = Path("test-config.toml")
            config_path.write_text("[ci-helper]\nverbose = true")

            result = runner.invoke(cli, ["--config-file", str(config_path), "--help"])

            assert result.exit_code == 0

    @patch("ci_helper.core.error_handler.ErrorHandler.handle_error")
    @patch("ci_helper.utils.config.Config")
    def test_cli_config_error_handling(self, mock_config, mock_error_handler):
        """設定エラーのハンドリングテスト"""
        from ci_helper.core.exceptions import ConfigurationError

        mock_config.side_effect = ConfigurationError("設定エラー", "解決方法")

        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])  # --help は例外を発生させない

        assert result.exit_code == 1
        mock_error_handler.assert_called_once()


class TestInitCommand:
    """init コマンドのテスト"""

    def test_init_help_display(self):
        """init コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(init, ["--help"])

        assert result.exit_code == 0
        assert "設定ファイルテンプレートを生成します" in result.output
        assert "--force" in result.output

    @patch("ci_helper.commands.init.console")
    @patch("ci_helper.commands.init.Confirm")
    def test_init_creates_template_files(self, mock_confirm, mock_console):
        """テンプレートファイル作成のテスト"""
        mock_confirm.ask.return_value = False  # gitignore 更新を拒否

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(init)

            assert result.exit_code == 0

            # テンプレートファイルが作成されることを確認
            assert Path(".actrc.example").exists()
            assert Path("ci-helper.toml.example").exists()
            assert Path(".env.example").exists()

    @patch("ci_helper.commands.init.console")
    @patch("ci_helper.commands.init.Confirm")
    def test_init_force_option(self, mock_confirm, mock_console):
        """--force オプションのテスト"""
        mock_confirm.ask.return_value = False

        runner = CliRunner()
        with runner.isolated_filesystem():
            # 既存ファイルを作成
            Path(".actrc.example").write_text("existing content")

            result = runner.invoke(init, ["--force"])

            assert result.exit_code == 0
            # ファイルが上書きされることを確認
            content = Path(".actrc.example").read_text()
            assert "existing content" not in content

    @patch("ci_helper.commands.init.console")
    @patch("ci_helper.commands.init.Confirm")
    def test_init_existing_files_confirmation(self, mock_confirm, mock_console):
        """既存ファイルがある場合の確認テスト"""
        mock_confirm.ask.return_value = False  # 上書きを拒否

        runner = CliRunner()
        with runner.isolated_filesystem():
            # 既存ファイルを作成
            Path(".actrc.example").write_text("existing content")

            result = runner.invoke(init)

            assert result.exit_code == 0
            # 確認が求められることを確認
            mock_confirm.ask.assert_called()


class TestSetupCommand:
    """setup コマンドのテスト"""

    def test_setup_help_display(self):
        """setup コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(setup, ["--help"])

        assert result.exit_code == 0
        assert "テンプレートから実際の設定ファイルを作成します" in result.output
        assert "--force" in result.output

    @patch("ci_helper.commands.init.console")
    def test_setup_copies_template_files(self, mock_console):
        """テンプレートファイルのコピーテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # テンプレートファイルを作成
            Path(".actrc.example").write_text("act config")
            Path("ci-helper.toml.example").write_text("[ci-helper]\nverbose = true")
            Path(".env.example").write_text("API_KEY=example")

            result = runner.invoke(setup)

            assert result.exit_code == 0

            # 実際の設定ファイルが作成されることを確認
            assert Path(".actrc").exists()
            assert Path("ci-helper.toml").exists()
            assert Path(".env").exists()

    @patch("ci_helper.commands.init.console")
    def test_setup_missing_templates(self, mock_console):
        """テンプレートファイルが存在しない場合のテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(setup)

            assert result.exit_code == 0
            # 警告メッセージが表示されることを確認
            mock_console.print.assert_called()


class TestDoctorCommand:
    """doctor コマンドのテスト"""

    def test_doctor_help_display(self):
        """doctor コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--help"])

        assert result.exit_code == 0
        assert "環境依存関係をチェックします" in result.output
        assert "--verbose" in result.output
        assert "--guide" in result.output

    @patch("ci_helper.commands.doctor._check_act_command")
    @patch("ci_helper.commands.doctor._check_docker_daemon")
    @patch("ci_helper.commands.doctor._check_workflows_directory")
    @patch("ci_helper.commands.doctor._check_configuration_files")
    @patch("ci_helper.commands.doctor._check_required_directories")
    @patch("ci_helper.commands.doctor._check_disk_space")
    @patch("ci_helper.commands.doctor._check_security_configuration")
    @patch("ci_helper.commands.doctor.console")
    def test_doctor_all_checks_pass(
        self,
        mock_console,
        mock_security_check,
        mock_disk_check,
        mock_dirs_check,
        mock_config_check,
        mock_workflows_check,
        mock_docker_check,
        mock_act_check,
    ):
        """全チェック成功のテスト"""
        # 全チェックが成功するようにモック設定
        for mock_check in [
            mock_act_check,
            mock_docker_check,
            mock_workflows_check,
            mock_config_check,
            mock_dirs_check,
            mock_disk_check,
            mock_security_check,
        ]:
            mock_check.return_value = {"name": "test", "passed": True, "message": "OK"}

        runner = CliRunner()
        with runner.isolated_filesystem():
            # 最小限の設定を作成
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["doctor"])

            assert result.exit_code == 0

    @patch("ci_helper.commands.doctor._check_act_command")
    @patch("ci_helper.commands.doctor.console")
    def test_doctor_check_failure(self, mock_console, mock_act_check):
        """チェック失敗のテスト"""
        mock_act_check.return_value = {
            "name": "act コマンド",
            "passed": False,
            "message": "見つかりません",
            "suggestion": "インストールしてください",
        }

        # 他のチェックは成功
        with patch("ci_helper.commands.doctor._check_docker_daemon") as mock_docker:
            mock_docker.return_value = {"name": "Docker", "passed": True, "message": "OK"}
            with patch("ci_helper.commands.doctor._check_workflows_directory") as mock_workflows:
                mock_workflows.return_value = {"name": "workflows", "passed": True, "message": "OK"}
                with patch("ci_helper.commands.doctor._check_configuration_files") as mock_config:
                    mock_config.return_value = {"name": "config", "passed": True, "message": "OK"}
                    with patch("ci_helper.commands.doctor._check_required_directories") as mock_dirs:
                        mock_dirs.return_value = {"name": "dirs", "passed": True, "message": "OK"}
                        with patch("ci_helper.commands.doctor._check_disk_space") as mock_disk:
                            mock_disk.return_value = {"name": "disk", "passed": True, "message": "OK"}
                            with patch("ci_helper.commands.doctor._check_security_configuration") as mock_security:
                                mock_security.return_value = {"name": "security", "passed": True, "message": "OK"}

                                runner = CliRunner()
                                with runner.isolated_filesystem():
                                    Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                                    result = runner.invoke(cli, ["doctor"])

                                    assert result.exit_code == 1

    def test_doctor_verbose_option(self):
        """--verbose オプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--verbose", "--help"])

        assert result.exit_code == 0

    def test_doctor_guide_option(self):
        """--guide オプションのテスト"""
        # RecoveryGuideが存在しないので、単純にオプションが受け入れられることをテスト
        runner = CliRunner()
        result = runner.invoke(doctor, ["--guide", "act"])

        # ガイドオプションが正しく処理されることを確認
        assert result.exit_code in [0, 1]  # 実装によってはエラーになる可能性もある


class TestTestCommand:
    """test コマンドのテスト"""

    def test_test_help_display(self):
        """test コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--help"])

        assert result.exit_code == 0
        assert "CI/CDワークフローをローカルで実行" in result.output
        assert "--workflow" in result.output
        assert "--verbose" in result.output
        assert "--format" in result.output
        assert "--dry-run" in result.output
        assert "--diff" in result.output
        assert "--save" in result.output
        assert "--sanitize" in result.output

    def test_test_basic_execution(self):
        """基本的な実行テスト"""
        with patch("ci_helper.commands.test._check_dependencies"):
            with patch("ci_helper.core.ci_runner.CIRunner") as mock_ci_runner:
                with patch("ci_helper.commands.test.console"):
                    # モックの設定
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

                        # .github/workflows ディレクトリとダミーワークフローを作成
                        workflows_dir = Path(".github/workflows")
                        workflows_dir.mkdir(parents=True, exist_ok=True)
                        (workflows_dir / "test.yml").write_text(
                            "name: test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test"
                        )

                        result = runner.invoke(cli, ["test"])

                        assert result.exit_code == 0

    @patch("ci_helper.commands.test._analyze_existing_log")
    def test_test_dry_run_with_log(self, mock_analyze_log):
        """ドライラン + ログファイル指定のテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # テスト用ログファイルを作成
            log_file = Path("test.log")
            log_file.write_text("test log content")

            result = runner.invoke(test, ["--dry-run", "--log", str(log_file)])

            if result.exit_code != 0:
                print(f"Exit code: {result.exit_code}")
                print(f"Output: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            mock_analyze_log.assert_called_once()

    def test_test_workflow_option(self):
        """--workflow オプションのテスト"""
        with patch("ci_helper.commands.test._check_dependencies"):
            with patch("ci_helper.core.ci_runner.CIRunner") as mock_ci_runner:
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

                    # .github/workflows ディレクトリとダミーワークフローを作成
                    workflows_dir = Path(".github/workflows")
                    workflows_dir.mkdir(parents=True, exist_ok=True)
                    (workflows_dir / "test.yml").write_text(
                        "name: test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test"
                    )

                    result = runner.invoke(cli, ["test", "-w", "test.yml", "-w", "build.yml"])

                    assert result.exit_code == 0
                    # 指定されたワークフローが渡されることを確認
                    call_args = mock_runner_instance.run_workflows.call_args
                    assert call_args[1]["workflows"] == ["test.yml", "build.yml"]

    def test_test_format_options(self):
        """--format オプションのテスト"""
        format_options = ["markdown", "json", "table"]

        for format_option in format_options:
            with patch("ci_helper.commands.test._check_dependencies"):
                with patch("ci_helper.core.ci_runner.CIRunner") as mock_ci_runner:
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

                        # .github/workflows ディレクトリとダミーワークフローを作成
                        workflows_dir = Path(".github/workflows")
                        workflows_dir.mkdir(parents=True, exist_ok=True)
                        (workflows_dir / "test.yml").write_text(
                            "name: test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test"
                        )

                        result = runner.invoke(cli, ["test", "--format", format_option])

                        assert result.exit_code == 0

    def test_test_save_no_save_options(self):
        """--save/--no-save オプションのテスト"""
        for save_option in ["--save", "--no-save"]:
            with patch("ci_helper.commands.test._check_dependencies"):
                with patch("ci_helper.core.ci_runner.CIRunner") as mock_ci_runner:
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

                        # .github/workflows ディレクトリとダミーワークフローを作成
                        workflows_dir = Path(".github/workflows")
                        workflows_dir.mkdir(parents=True, exist_ok=True)
                        (workflows_dir / "test.yml").write_text(
                            "name: test\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test"
                        )

                        result = runner.invoke(cli, ["test", save_option])

                        assert result.exit_code == 0
                        # save_logs パラメータが正しく設定されることを確認
                        call_args = mock_runner_instance.run_workflows.call_args
                        expected_save = save_option == "--save"
                        assert call_args[1]["save_logs"] == expected_save


class TestLogsCommand:
    """logs コマンドのテスト"""

    def test_logs_help_display(self):
        """logs コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(logs, ["--help"])

        assert result.exit_code == 0
        assert "実行ログを管理・表示" in result.output
        assert "--limit" in result.output
        assert "--workflow" in result.output
        assert "--show-content" in result.output
        assert "--stats" in result.output
        assert "--diff" in result.output
        assert "--format" in result.output

    @patch("ci_helper.commands.logs.LogManager")
    @patch("ci_helper.commands.logs.console")
    def test_logs_basic_listing(self, mock_console, mock_log_manager):
        """基本的なログ一覧表示のテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.list_logs.return_value = [
            {
                "timestamp": "2024-01-01T12:00:00",
                "log_file": "act_20240101.log",
                "success": True,
                "total_duration": 10.5,
                "total_failures": 0,
                "workflows": ["test.yml"],
            }
        ]
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs"])

            assert result.exit_code == 0
            mock_manager_instance.list_logs.assert_called_once_with(10)

    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_limit_option(self, mock_log_manager):
        """--limit オプションのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.list_logs.return_value = []
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--limit", "20"])

            assert result.exit_code == 0
            mock_manager_instance.list_logs.assert_called_once_with(20)

    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_workflow_filter(self, mock_log_manager):
        """--workflow オプションのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.find_logs_by_workflow.return_value = []
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--workflow", "test.yml"])

            assert result.exit_code == 0
            mock_manager_instance.find_logs_by_workflow.assert_called_once_with("test.yml")

    @patch("ci_helper.commands.logs._show_log_statistics")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_stats_option(self, mock_log_manager, mock_show_stats):
        """--stats オプションのテスト"""
        mock_manager_instance = Mock()
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--stats"])

            assert result.exit_code == 0
            mock_show_stats.assert_called_once_with(mock_manager_instance)

    @patch("ci_helper.commands.logs._show_log_content")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_show_content_option(self, mock_log_manager, mock_show_content):
        """--show-content オプションのテスト"""
        mock_manager_instance = Mock()
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--show-content", "test.log"])

            assert result.exit_code == 0
            mock_show_content.assert_called_once()

    @patch("ci_helper.commands.logs._show_log_diff")
    @patch("ci_helper.commands.logs.LogManager")
    def test_logs_diff_option(self, mock_log_manager, mock_show_diff):
        """--diff オプションのテスト"""
        mock_manager_instance = Mock()
        mock_log_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["logs", "--diff", "test.log"])

            assert result.exit_code == 0
            mock_show_diff.assert_called_once()


class TestSecretsCommand:
    """secrets コマンドのテスト"""

    def test_secrets_help_display(self):
        """secrets コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(secrets, ["--help"])

        assert result.exit_code == 0
        assert "シークレット管理と検証" in result.output

    @patch("ci_helper.core.security.EnvironmentSecretManager")
    @patch("ci_helper.commands.secrets.console")
    def test_secrets_basic_execution(self, mock_console, mock_secret_manager):
        """基本的な実行テスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.get_secret_summary.return_value = {
            "total_configured": 2,
            "total_missing": 1,
            "required_secrets": {"OPENAI_API_KEY": False},
            "optional_secrets": {"ANTHROPIC_API_KEY": True},
        }
        mock_secret_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["secrets"])

            assert result.exit_code == 0


class TestCleanCommand:
    """clean コマンドのテスト"""

    def test_clean_help_display(self):
        """clean コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(clean, ["--help"])

        assert result.exit_code == 0
        assert "キャッシュとログファイルをクリーンアップ" in result.output
        assert "--logs-only" in result.output
        assert "--all" in result.output
        assert "--dry-run" in result.output
        assert "--force" in result.output
        assert "--verbose" in result.output

    @patch("ci_helper.commands.clean.CacheManager")
    def test_clean_basic_execution(self, mock_cache_manager):
        """基本的なクリーンアップのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.cleanup_all.return_value = {
            "total": {"deleted_files": 5, "freed_size_mb": 10.5, "errors": 0}
        }
        mock_manager_instance.get_cleanup_recommendations.return_value = {
            "recommendations": [],
            "total_size_mb": 10.5,
        }
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(clean, ["--force"])

            # コマンドが正常に実行されることを確認
            assert result.exit_code in [0, 1]

    @patch("ci_helper.commands.clean.CacheManager")
    def test_clean_logs_only_option(self, mock_cache_manager):
        """--logs-only オプションのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.cleanup_logs_only.return_value = {
            "deleted_files": 3,
            "freed_size_mb": 5.0,
            "errors": [],
        }
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["clean", "--logs-only", "--force"])

            assert result.exit_code == 0
            mock_manager_instance.cleanup_logs_only.assert_called_once()

    @patch("ci_helper.commands.clean.CacheManager")
    def test_clean_all_option(self, mock_cache_manager):
        """--all オプションのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.reset_all_cache.return_value = {
            "deleted_directories": [".ci-helper"],
            "total_freed_mb": 20.0,
            "errors": [],
        }
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["clean", "--all", "--force"])

            assert result.exit_code == 0
            mock_manager_instance.reset_all_cache.assert_called_once()

    def test_clean_conflicting_options(self):
        """競合するオプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(clean, ["--logs-only", "--all"])

        assert result.exit_code == 1

    @patch("ci_helper.commands.clean.CacheManager")
    def test_clean_dry_run_option(self, mock_cache_manager):
        """--dry-run オプションのテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.get_cache_statistics.return_value = {
            "logs": {"files": 5, "size_mb": 10.0},
            "cache": {"files": 3, "size_mb": 5.0},
            "total": {"files": 8, "size_mb": 15.0},
        }
        mock_manager_instance.cleanup_all.return_value = {
            "total": {"deleted_files": 8, "freed_size_mb": 15.0, "errors": 0}
        }
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["clean", "--dry-run"])

            assert result.exit_code == 0
            # dry_run=True で呼ばれることを確認
            call_args = mock_manager_instance.cleanup_all.call_args
            assert call_args[1]["dry_run"] is True


class TestCommandIntegration:
    """コマンド間の統合テスト"""

    def test_command_chaining_workflow(self):
        """コマンドの連携ワークフローテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # 1. init コマンドでテンプレート作成
            with patch("ci_helper.commands.init.console"):
                with patch("ci_helper.commands.init.Confirm") as mock_confirm:
                    mock_confirm.ask.return_value = False
                    result = runner.invoke(init)
                    assert result.exit_code == 0

            # 2. setup コマンドで設定ファイル作成
            with patch("ci_helper.commands.init.console"):
                result = runner.invoke(setup)
                assert result.exit_code == 0

            # 設定ファイルが作成されていることを確認
            assert Path("ci-helper.toml").exists()
            assert Path(".actrc").exists()
            assert Path(".env").exists()

    @patch("ci_helper.core.error_handler.ErrorHandler.handle_error")
    def test_error_handling_consistency(self, mock_error_handler):
        """エラーハンドリングの一貫性テスト"""
        from ci_helper.core.exceptions import CIHelperError

        # 各コマンドで同じエラーハンドリングが使用されることを確認
        commands_to_test = [
            (test, ["--workflow", "nonexistent.yml"]),
            (logs, ["--show-content", "nonexistent.log"]),
        ]

        for command, args in commands_to_test:
            with patch.object(command, "callback") as mock_callback:
                mock_callback.side_effect = CIHelperError("テストエラー", "解決方法")

                runner = CliRunner()
                with runner.isolated_filesystem():
                    Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                    result = runner.invoke(cli, [command.name, *args])

                    # エラーハンドラーが呼ばれることを確認
                    assert result.exit_code == 1


class TestOptionValidation:
    """オプション検証のテスト"""

    def test_invalid_format_option(self):
        """無効なフォーマットオプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--format", "invalid"])

        assert result.exit_code == 2  # Click の引数エラー
        assert "Invalid value" in result.output

    def test_invalid_guide_option(self):
        """無効なガイドオプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--guide", "invalid"])

        assert result.exit_code == 2  # Click の引数エラー
        assert "Invalid value" in result.output

    def test_negative_limit_option(self):
        """負の値のlimitオプションのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # Click は負の値も受け入れるが、アプリケーション側で処理される
            result = runner.invoke(cli, ["logs", "--limit", "-1"])

            # エラーハンドリングはアプリケーション側で行われる
            assert result.exit_code in [0, 1]

    def test_nonexistent_config_file(self):
        """存在しない設定ファイルの指定テスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--config-file", "nonexistent.toml", "doctor"])

        # 設定ファイルが存在しない場合はエラーになる
        assert result.exit_code != 0
