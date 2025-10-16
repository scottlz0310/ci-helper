"""
doctor コマンドの詳細ユニットテスト

環境チェック機能の個別テストを提供します。
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from ci_helper.cli import cli
from ci_helper.commands.doctor import (
    _check_act_command,
    _check_configuration_files,
    _check_disk_space,
    _check_docker_daemon,
    _check_required_directories,
    _check_security_configuration,
    _check_workflows_directory,
    _get_act_install_instructions,
)


class TestActCommandCheck:
    """act コマンドチェックのテスト"""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_act_command_found_with_version(self, mock_run, mock_which):
        """act コマンドが見つかり、バージョンも取得できる場合"""
        mock_which.return_value = "/usr/local/bin/act"
        mock_run.return_value = Mock(stdout="act version 0.2.40", returncode=0)

        result = _check_act_command(verbose=False)

        assert result["passed"] is True
        assert result["name"] == "act コマンド"
        assert "インストール済み" in result["message"]
        assert "act version 0.2.40" in result["message"]

    @patch("shutil.which")
    def test_act_command_not_found(self, mock_which):
        """act コマンドが見つからない場合"""
        mock_which.return_value = None

        result = _check_act_command(verbose=False)

        assert result["passed"] is False
        assert result["name"] == "act コマンド"
        assert "見つかりません" in result["message"]
        assert result["suggestion"] is not None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_act_command_version_error(self, mock_run, mock_which):
        """act コマンドは存在するがバージョン取得でエラー"""
        mock_which.return_value = "/usr/local/bin/act"
        mock_run.side_effect = subprocess.CalledProcessError(1, "act")

        result = _check_act_command(verbose=False)

        assert result["passed"] is True
        assert "不明" in result["message"]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_act_command_timeout(self, mock_run, mock_which):
        """act コマンドのバージョン取得でタイムアウト"""
        mock_which.return_value = "/usr/local/bin/act"
        mock_run.side_effect = subprocess.TimeoutExpired("act", 10)

        result = _check_act_command(verbose=False)

        assert result["passed"] is True
        assert "不明" in result["message"]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_act_command_verbose_mode(self, mock_run, mock_which):
        """詳細モードでのact コマンドチェック"""
        mock_which.return_value = "/usr/local/bin/act"
        mock_run.return_value = Mock(stdout="act version 0.2.40", returncode=0)

        result = _check_act_command(verbose=True)

        assert result["passed"] is True
        assert result["details"] is not None
        assert "/usr/local/bin/act" in result["details"]


class TestDockerDaemonCheck:
    """Docker デーモンチェックのテスト"""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_daemon_running(self, mock_run, mock_which):
        """Docker デーモンが正常に動作している場合"""
        mock_which.return_value = "/usr/local/bin/docker"
        mock_run.return_value = Mock(returncode=0, stderr="")

        result = _check_docker_daemon(verbose=False)

        assert result["passed"] is True
        assert result["name"] == "Docker デーモン"
        assert "実行中" in result["message"]

    @patch("shutil.which")
    def test_docker_command_not_found(self, mock_which):
        """Docker コマンドが見つからない場合"""
        mock_which.return_value = None

        result = _check_docker_daemon(verbose=False)

        assert result["passed"] is False
        assert "見つかりません" in result["message"]
        assert "Docker Desktop" in result["suggestion"]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_daemon_not_running(self, mock_run, mock_which):
        """Docker デーモンが動作していない場合"""
        mock_which.return_value = "/usr/local/bin/docker"
        mock_run.return_value = Mock(returncode=1, stderr="Cannot connect to Docker daemon")

        result = _check_docker_daemon(verbose=False)

        assert result["passed"] is False
        assert "実行されていません" in result["message"]
        assert "Docker Desktop を起動" in result["suggestion"]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_timeout(self, mock_run, mock_which):
        """Docker コマンドでタイムアウト"""
        mock_which.return_value = "/usr/local/bin/docker"
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        result = _check_docker_daemon(verbose=False)

        assert result["passed"] is False
        assert "タイムアウト" in result["message"]
        assert "再起動" in result["suggestion"]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_verbose_mode(self, mock_run, mock_which):
        """詳細モードでのDocker チェック"""
        mock_which.return_value = "/usr/local/bin/docker"
        mock_run.return_value = Mock(returncode=0, stderr="")

        result = _check_docker_daemon(verbose=True)

        assert result["passed"] is True
        assert result["details"] is not None
        assert "/usr/local/bin/docker" in result["details"]


class TestWorkflowsDirectoryCheck:
    """ワークフローディレクトリチェックのテスト"""

    def test_workflows_directory_exists_with_files(self, temp_dir: Path):
        """ワークフローディレクトリが存在し、ファイルもある場合"""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: Test")
        (workflows_dir / "build.yaml").write_text("name: Build")

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _check_workflows_directory(verbose=False)

        assert result["passed"] is True
        assert "2 個のワークフローファイルを発見" in result["message"]

    def test_workflows_directory_not_exists(self, temp_dir: Path):
        """ワークフローディレクトリが存在しない場合"""
        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _check_workflows_directory(verbose=False)

        assert result["passed"] is False
        assert "存在しません" in result["message"]
        assert ".github/workflows/" in result["suggestion"]

    def test_workflows_directory_exists_no_files(self, temp_dir: Path):
        """ワークフローディレクトリは存在するがファイルがない場合"""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _check_workflows_directory(verbose=False)

        assert result["passed"] is False
        assert "見つかりません" in result["message"]
        assert ".yml または .yaml" in result["suggestion"]

    def test_workflows_directory_verbose_mode(self, temp_dir: Path):
        """詳細モードでのワークフローディレクトリチェック"""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: Test")

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _check_workflows_directory(verbose=True)

        assert result["passed"] is True
        assert result["details"] is not None
        assert "test.yml" in str(result["details"])


class TestConfigurationFilesCheck:
    """設定ファイルチェックのテスト"""

    def test_all_config_files_exist(self, temp_dir: Path):
        """全ての設定ファイルが存在する場合"""
        (temp_dir / "ci-helper.toml").write_text("[ci-helper]\nverbose = true")
        (temp_dir / ".actrc").write_text("-P ubuntu-latest=ubuntu:latest")
        (temp_dir / ".env").write_text("API_KEY=test")

        mock_config = Mock()
        mock_config.project_root = temp_dir

        result = _check_configuration_files(mock_config, verbose=False)

        assert result["passed"] is True
        assert "存在: 3 個" in result["message"]

    def test_some_config_files_missing(self, temp_dir: Path):
        """一部の設定ファイルが不足している場合"""
        (temp_dir / "ci-helper.toml").write_text("[ci-helper]\nverbose = true")
        # .actrc と .env は作成しない

        mock_config = Mock()
        mock_config.project_root = temp_dir

        result = _check_configuration_files(mock_config, verbose=False)

        assert result["passed"] is False
        assert "存在: 1 個, 不足: 2 個" in result["message"]
        assert "ci-run init" in result["suggestion"]

    def test_no_config_files_exist(self, temp_dir: Path):
        """設定ファイルが全く存在しない場合"""
        mock_config = Mock()
        mock_config.project_root = temp_dir

        result = _check_configuration_files(mock_config, verbose=False)

        assert result["passed"] is False
        assert "見つかりません" in result["message"]
        assert "ci-run init" in result["suggestion"]

    def test_config_files_verbose_mode(self, temp_dir: Path):
        """詳細モードでの設定ファイルチェック"""
        (temp_dir / "ci-helper.toml").write_text("[ci-helper]\nverbose = true")

        mock_config = Mock()
        mock_config.project_root = temp_dir

        result = _check_configuration_files(mock_config, verbose=True)

        assert result["details"] is not None
        assert "ci-helper.toml" in result["details"]


class TestRequiredDirectoriesCheck:
    """必要ディレクトリチェックのテスト"""

    def test_directories_created_successfully(self, temp_dir: Path):
        """ディレクトリが正常に作成される場合"""
        mock_config = Mock()
        mock_config.ensure_directories.return_value = None
        mock_config.get_path.side_effect = lambda key: {
            "log_dir": temp_dir / "logs",
            "cache_dir": temp_dir / "cache",
            "reports_dir": temp_dir / "reports",
        }[key]

        # ディレクトリを実際に作成
        for dir_name in ["logs", "cache", "reports"]:
            (temp_dir / dir_name).mkdir()

        result = _check_required_directories(mock_config, verbose=False)

        assert result["passed"] is True
        assert "3 個のディレクトリを確認/作成" in result["message"]

    def test_directory_creation_error(self, temp_dir: Path):
        """ディレクトリ作成でエラーが発生する場合"""
        mock_config = Mock()
        mock_config.ensure_directories.side_effect = OSError("Permission denied")

        result = _check_required_directories(mock_config, verbose=False)

        assert result["passed"] is False
        assert "作成に失敗" in result["message"]
        assert "書き込み権限" in result["suggestion"]

    def test_directories_verbose_mode(self, temp_dir: Path):
        """詳細モードでのディレクトリチェック"""
        mock_config = Mock()
        mock_config.ensure_directories.return_value = None
        mock_config.get_path.side_effect = lambda key: {
            "log_dir": temp_dir / "logs",
            "cache_dir": temp_dir / "cache",
            "reports_dir": temp_dir / "reports",
        }[key]

        for dir_name in ["logs", "cache", "reports"]:
            (temp_dir / dir_name).mkdir()

        result = _check_required_directories(mock_config, verbose=True)

        assert result["passed"] is True
        assert result["details"] is not None


class TestDiskSpaceCheck:
    """ディスク容量チェックのテスト"""

    @patch("shutil.disk_usage")
    def test_sufficient_disk_space(self, mock_disk_usage):
        """十分なディスク容量がある場合"""
        # 1GB の空き容量
        mock_disk_usage.return_value = (10 * 1024**3, 5 * 1024**3, 1024**3)

        result = _check_disk_space(verbose=False)

        assert result["passed"] is True
        assert "十分な容量" in result["message"]
        assert "1024MB 利用可能" in result["message"]

    @patch("shutil.disk_usage")
    def test_insufficient_disk_space(self, mock_disk_usage):
        """ディスク容量が不足している場合"""
        # 50MB の空き容量（100MB 未満）
        mock_disk_usage.return_value = (1024**3, 950 * 1024**2, 50 * 1024**2)

        result = _check_disk_space(verbose=False)

        assert result["passed"] is False
        assert "容量不足" in result["message"]
        assert "ci-run clean" in result["suggestion"]

    @patch("shutil.disk_usage")
    def test_disk_space_check_error(self, mock_disk_usage):
        """ディスク容量チェックでエラーが発生する場合"""
        mock_disk_usage.side_effect = OSError("Disk not accessible")

        result = _check_disk_space(verbose=False)

        assert result["passed"] is False
        assert "チェックに失敗" in result["message"]
        assert "手動で確認" in result["suggestion"]

    @patch("shutil.disk_usage")
    def test_disk_space_verbose_mode(self, mock_disk_usage):
        """詳細モードでのディスク容量チェック"""
        mock_disk_usage.return_value = (10 * 1024**3, 5 * 1024**3, 1024**3)

        result = _check_disk_space(verbose=True)

        assert result["passed"] is True
        assert result["details"] is not None
        assert "合計:" in result["details"]
        assert "使用済み:" in result["details"]


class TestSecurityConfigurationCheck:
    """セキュリティ設定チェックのテスト"""

    def test_security_validation_success(self):
        """セキュリティ検証が成功する場合"""
        mock_config = Mock()
        mock_config.validate_all_config_files.return_value = {
            "overall_valid": True,
            "critical_issues": 0,
            "warning_issues": 0,
        }

        with patch("ci_helper.core.security.EnvironmentSecretManager") as mock_secret_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.get_secret_summary.return_value = {
                "total_configured": 2,
                "total_missing": 0,
                "required_secrets": {},
            }
            mock_secret_manager.return_value = mock_manager_instance

            result = _check_security_configuration(mock_config, verbose=False)

        assert result["passed"] is True
        assert "適切です" in result["message"]

    def test_security_validation_critical_issues(self):
        """重大なセキュリティ問題がある場合"""
        mock_config = Mock()
        mock_config.validate_all_config_files.return_value = {
            "overall_valid": False,
            "critical_issues": 2,
            "warning_issues": 1,
        }

        result = _check_security_configuration(mock_config, verbose=False)

        assert result["passed"] is False
        assert "重大なセキュリティ問題" in result["message"]
        assert "環境変数を使用" in result["suggestion"]

    def test_security_validation_warnings_only(self):
        """警告レベルの問題のみの場合"""
        mock_config = Mock()
        mock_config.validate_all_config_files.return_value = {
            "overall_valid": False,
            "critical_issues": 0,
            "warning_issues": 3,
        }

        with patch("ci_helper.core.security.EnvironmentSecretManager") as mock_secret_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.get_secret_summary.return_value = {
                "total_configured": 1,
                "total_missing": 0,
                "required_secrets": {},
            }
            mock_secret_manager.return_value = mock_manager_instance

            result = _check_security_configuration(mock_config, verbose=False)

        assert result["passed"] is True
        assert "軽微な問題" in result["message"]

    def test_security_missing_environment_variables(self):
        """必要な環境変数が不足している場合"""
        mock_config = Mock()
        mock_config.validate_all_config_files.return_value = {
            "overall_valid": True,
            "critical_issues": 0,
            "warning_issues": 0,
        }

        with patch("ci_helper.core.security.EnvironmentSecretManager") as mock_secret_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.get_secret_summary.return_value = {
                "total_configured": 1,
                "total_missing": 2,
                "required_secrets": {"OPENAI_API_KEY": False, "ANTHROPIC_API_KEY": False},
            }
            mock_secret_manager.return_value = mock_manager_instance

            result = _check_security_configuration(mock_config, verbose=False)

        assert result["passed"] is True  # 警告レベル
        assert "未設定" in result["message"]
        assert "環境変数を設定" in result["suggestion"]

    def test_security_check_error(self):
        """セキュリティチェックでエラーが発生する場合"""
        mock_config = Mock()
        mock_config.validate_all_config_files.side_effect = Exception("Validation error")

        result = _check_security_configuration(mock_config, verbose=False)

        assert result["passed"] is False
        assert "チェックに失敗" in result["message"]
        assert "設定ファイルの形式" in result["suggestion"]


class TestActInstallInstructions:
    """act インストール手順のテスト"""

    @patch("platform.system")
    def test_macos_install_instructions(self, mock_system):
        """macOS 用のインストール手順"""
        mock_system.return_value = "Darwin"

        instructions = _get_act_install_instructions()

        assert "Homebrew" in instructions
        assert "brew install act" in instructions

    @patch("platform.system")
    def test_linux_install_instructions(self, mock_system):
        """Linux 用のインストール手順"""
        mock_system.return_value = "Linux"

        instructions = _get_act_install_instructions()

        assert "パッケージマネージャー" in instructions
        assert "GitHub Releases" in instructions

    @patch("platform.system")
    def test_windows_install_instructions(self, mock_system):
        """Windows 用のインストール手順"""
        mock_system.return_value = "Windows"

        instructions = _get_act_install_instructions()

        assert "Chocolatey" in instructions
        assert "choco install act-cli" in instructions

    @patch("platform.system")
    def test_unknown_system_install_instructions(self, mock_system):
        """不明なシステム用のインストール手順"""
        mock_system.return_value = "UnknownOS"

        instructions = _get_act_install_instructions()

        assert "GitHub Releases" in instructions
        assert "nektos/act" in instructions


class TestDoctorCommandIntegration:
    """doctor コマンドの統合テスト"""

    def test_doctor_command_with_mocked_checks(self):
        """モックされたチェック関数を使用したdoctor コマンドテスト"""
        runner = CliRunner()

        with patch("ci_helper.commands.doctor._check_act_command") as mock_act:
            with patch("ci_helper.commands.doctor._check_docker_daemon") as mock_docker:
                with patch("ci_helper.commands.doctor._check_workflows_directory") as mock_workflows:
                    with patch("ci_helper.commands.doctor._check_configuration_files") as mock_config:
                        with patch("ci_helper.commands.doctor._check_required_directories") as mock_dirs:
                            with patch("ci_helper.commands.doctor._check_disk_space") as mock_disk:
                                with patch("ci_helper.commands.doctor._check_security_configuration") as mock_security:
                                    # 全チェックが成功するように設定
                                    for mock_check in [
                                        mock_act,
                                        mock_docker,
                                        mock_workflows,
                                        mock_config,
                                        mock_dirs,
                                        mock_disk,
                                        mock_security,
                                    ]:
                                        mock_check.return_value = {
                                            "name": "test",
                                            "passed": True,
                                            "message": "OK",
                                            "suggestion": None,
                                            "details": None,
                                        }

                                    with runner.isolated_filesystem():
                                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                                        result = runner.invoke(cli, ["doctor"])

                                        assert result.exit_code == 0
                                        assert "すべてのチェックが成功" in result.output

    def test_doctor_command_with_failures(self):
        """一部のチェックが失敗する場合のdoctor コマンドテスト"""
        runner = CliRunner()

        with patch("ci_helper.commands.doctor._check_act_command") as mock_act:
            with patch("ci_helper.commands.doctor._check_docker_daemon") as mock_docker:
                with patch("ci_helper.commands.doctor._check_workflows_directory") as mock_workflows:
                    with patch("ci_helper.commands.doctor._check_configuration_files") as mock_config:
                        with patch("ci_helper.commands.doctor._check_required_directories") as mock_dirs:
                            with patch("ci_helper.commands.doctor._check_disk_space") as mock_disk:
                                with patch("ci_helper.commands.doctor._check_security_configuration") as mock_security:
                                    # act チェックのみ失敗
                                    mock_act.return_value = {
                                        "name": "act コマンド",
                                        "passed": False,
                                        "message": "見つかりません",
                                        "suggestion": "インストールしてください",
                                        "details": None,
                                    }

                                    # 他は成功
                                    for mock_check in [
                                        mock_docker,
                                        mock_workflows,
                                        mock_config,
                                        mock_dirs,
                                        mock_disk,
                                        mock_security,
                                    ]:
                                        mock_check.return_value = {
                                            "name": "test",
                                            "passed": True,
                                            "message": "OK",
                                            "suggestion": None,
                                            "details": None,
                                        }

                                    with runner.isolated_filesystem():
                                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                                        result = runner.invoke(cli, ["doctor"])

                                        assert result.exit_code == 1
                                        assert "一部のチェックが失敗" in result.output

    def test_doctor_verbose_mode(self):
        """詳細モードでのdoctor コマンドテスト"""
        runner = CliRunner()

        with patch("ci_helper.commands.doctor._check_act_command") as mock_act:
            mock_act.return_value = {
                "name": "act コマンド",
                "passed": True,
                "message": "インストール済み",
                "suggestion": None,
                "details": "パス: /usr/local/bin/act",
            }

            with patch("ci_helper.commands.doctor._check_docker_daemon") as mock_docker:
                with patch("ci_helper.commands.doctor._check_workflows_directory") as mock_workflows:
                    with patch("ci_helper.commands.doctor._check_configuration_files") as mock_config:
                        with patch("ci_helper.commands.doctor._check_required_directories") as mock_dirs:
                            with patch("ci_helper.commands.doctor._check_disk_space") as mock_disk:
                                with patch("ci_helper.commands.doctor._check_security_configuration") as mock_security:
                                    # 他のチェックも成功に設定
                                    for mock_check in [
                                        mock_docker,
                                        mock_workflows,
                                        mock_config,
                                        mock_dirs,
                                        mock_disk,
                                        mock_security,
                                    ]:
                                        mock_check.return_value = {
                                            "name": "test",
                                            "passed": True,
                                            "message": "OK",
                                            "suggestion": None,
                                            "details": None,
                                        }

                                    with runner.isolated_filesystem():
                                        Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

                                        result = runner.invoke(cli, ["doctor", "--verbose"])

                                        assert result.exit_code == 0
                                        # 詳細情報が表示されることを確認
                                        assert "/usr/local/bin/act" in result.output
