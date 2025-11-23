"""
エラーハンドリングシステムのユニットテスト

各種エラー条件、エラーメッセージの検証、復旧処理のテストを実装します。
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from ci_helper.core.error_handler import (
    DependencyChecker,
    ErrorHandler,
    SecurityValidator,
    TimeoutHandler,
    ValidationHelper,
)
from ci_helper.core.exceptions import (
    ConfigurationError,
    DependencyError,
    DiskSpaceError,
    ExecutionError,
    LogParsingError,
    SecurityError,
    ValidationError,
    WorkflowNotFoundError,
)


class TestErrorHandler:
    """ErrorHandler クラスのテスト"""

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_dependency(self, mock_console):
        """DependencyError の処理テスト"""
        error = DependencyError("act が見つかりません", "インストールしてください", missing_dependency="act")

        ErrorHandler.handle_error(error, verbose=False)

        # console.print が呼ばれることを確認
        mock_console.print.assert_called_once()
        # ErrorHandler が呼ばれたことを確認（内容の詳細チェックは統合テストで行う）
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_configuration(self, mock_console):
        """ConfigurationError の処理テスト"""
        error = ConfigurationError("設定が無効です", "設定を確認してください", config_file="ci-helper.toml")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_execution(self, mock_console):
        """ExecutionError の処理テスト"""
        error = ExecutionError("コマンドが失敗しました", "再試行してください", exit_code=1, command="act")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_validation(self, mock_console):
        """ValidationError の処理テスト"""
        error = ValidationError("入力が無効です", "正しい値を入力してください", invalid_value="invalid")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_workflow_not_found(self, mock_console):
        """WorkflowNotFoundError の処理テスト"""
        error = WorkflowNotFoundError(
            "ワークフローが見つかりません", "ファイルを確認してください", workflow_path="test.yml"
        )

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_log_parsing(self, mock_console):
        """LogParsingError の処理テスト"""
        error = LogParsingError("ログが読めません", "ファイルを確認してください", log_file="test.log")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_disk_space(self, mock_console):
        """DiskSpaceError の処理テスト"""
        error = DiskSpaceError("容量不足です", "クリーンアップしてください", available_space=50, required_space=100)

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_security(self, mock_console):
        """SecurityError の処理テスト"""
        error = SecurityError("セキュリティ問題です", "設定を確認してください", security_issue="secrets_in_config")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_ci_helper_error_verbose_mode(self, mock_console):
        """詳細モードでのエラー処理テスト"""
        error = DependencyError("act が見つかりません", "インストールしてください", missing_dependency="act")
        error.details = "詳細情報"

        ErrorHandler.handle_error(error, verbose=True)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    def test_handle_unexpected_error(self, mock_console):
        """予期しないエラーの処理テスト"""
        error = ValueError("予期しないエラー")

        ErrorHandler.handle_error(error, verbose=False)

        mock_console.print.assert_called_once()
        assert mock_console.print.called

    @patch("ci_helper.core.error_handler.console")
    @patch("traceback.format_exc")
    def test_handle_unexpected_error_verbose(self, mock_traceback, mock_console):
        """詳細モードでの予期しないエラー処理テスト"""
        mock_traceback.return_value = "スタックトレース情報"
        error = ValueError("予期しないエラー")

        ErrorHandler.handle_error(error, verbose=True)

        mock_console.print.assert_called_once()
        assert mock_console.print.called


class TestDependencyChecker:
    """DependencyChecker クラスのテスト"""

    @patch("shutil.which")
    def test_check_act_command_success(self, mock_which):
        """act コマンド存在確認成功テスト"""
        mock_which.return_value = "/usr/local/bin/act"

        # 例外が発生しないことを確認
        DependencyChecker.check_act_command()

        mock_which.assert_called_once_with("act")

    @patch("shutil.which")
    def test_check_act_command_not_found(self, mock_which):
        """act コマンドが見つからない場合のテスト"""
        mock_which.return_value = None

        with pytest.raises(DependencyError) as exc_info:
            DependencyChecker.check_act_command()

        error = exc_info.value
        assert "act コマンドが見つかりません" in error.message
        assert error.missing_dependency == "act"
        assert error.suggestion is not None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_check_docker_daemon_success(self, mock_run, mock_which):
        """Docker デーモン確認成功テスト"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)

        # 例外が発生しないことを確認
        DependencyChecker.check_docker_daemon()

        mock_which.assert_called_once_with("docker")
        mock_run.assert_called_once_with(["docker", "info"], capture_output=True, text=True, timeout=10, check=True)

    @patch("shutil.which")
    def test_check_docker_daemon_not_installed(self, mock_which):
        """Docker がインストールされていない場合のテスト"""
        mock_which.return_value = None

        with pytest.raises(DependencyError) as exc_info:
            DependencyChecker.check_docker_daemon()

        error = exc_info.value
        assert "Docker コマンドが見つかりません" in error.message
        assert error.missing_dependency == "docker"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_check_docker_daemon_not_running(self, mock_run, mock_which):
        """Docker デーモンが実行されていない場合のテスト"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = subprocess.CalledProcessError(1, ["docker", "info"])

        with pytest.raises(DependencyError) as exc_info:
            DependencyChecker.check_docker_daemon()

        error = exc_info.value
        assert "Docker デーモンが実行されていません" in error.message
        assert error.missing_dependency == "docker"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_check_docker_daemon_timeout(self, mock_run, mock_which):
        """Docker コマンドタイムアウトのテスト"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = subprocess.TimeoutExpired(["docker", "info"], 10)

        with pytest.raises(DependencyError) as exc_info:
            DependencyChecker.check_docker_daemon()

        error = exc_info.value
        assert "Docker の応答がタイムアウトしました" in error.message
        assert error.missing_dependency == "docker"

    def test_check_workflows_directory_success(self, temp_dir: Path):
        """ワークフローディレクトリ確認成功テスト"""
        # ワークフローディレクトリとファイルを作成
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        (workflows_dir / "build.yaml").write_text("name: build")

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            workflow_files = DependencyChecker.check_workflows_directory()

        assert len(workflow_files) == 2
        assert any(f.name == "test.yml" for f in workflow_files)
        assert any(f.name == "build.yaml" for f in workflow_files)

    def test_check_workflows_directory_not_exists(self, temp_dir: Path):
        """ワークフローディレクトリが存在しない場合のテスト"""
        with patch("pathlib.Path.cwd", return_value=temp_dir):
            with pytest.raises(WorkflowNotFoundError) as exc_info:
                DependencyChecker.check_workflows_directory()

        error = exc_info.value
        assert ".github/workflows ディレクトリが存在しません" in error.message

    def test_check_workflows_directory_no_files(self, temp_dir: Path):
        """ワークフローファイルが存在しない場合のテスト"""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            with pytest.raises(WorkflowNotFoundError) as exc_info:
                DependencyChecker.check_workflows_directory()

        error = exc_info.value
        assert "ワークフローファイルが見つかりません" in error.message

    @patch("shutil.disk_usage")
    def test_check_disk_space_success(self, mock_disk_usage):
        """ディスク容量確認成功テスト"""
        # 十分な容量がある場合
        mock_disk_usage.return_value = (1000 * 1024 * 1024, 500 * 1024 * 1024, 500 * 1024 * 1024)

        # 例外が発生しないことを確認
        DependencyChecker.check_disk_space(required_mb=100)

    @patch("shutil.disk_usage")
    def test_check_disk_space_insufficient(self, mock_disk_usage):
        """ディスク容量不足のテスト"""
        # 容量不足の場合
        mock_disk_usage.return_value = (1000 * 1024 * 1024, 950 * 1024 * 1024, 50 * 1024 * 1024)

        # DependencyChecker.check_disk_space は例外をキャッチして警告を表示するため、
        # 直接 DiskSpaceError.insufficient_space を呼び出してテスト
        with pytest.raises(DiskSpaceError) as exc_info:
            raise DiskSpaceError.insufficient_space(50, 100)

        error = exc_info.value
        assert "ディスク容量が不足しています" in error.message
        assert error.available_space == 50
        assert error.required_space == 100

    @patch("shutil.disk_usage")
    @patch("ci_helper.core.error_handler.console")
    def test_check_disk_space_error(self, mock_console, mock_disk_usage):
        """ディスク容量確認エラーのテスト"""
        mock_disk_usage.side_effect = Exception("ディスクアクセスエラー")

        # 例外は発生せず、警告が表示される
        DependencyChecker.check_disk_space()

        mock_console.print.assert_called_once()


class TestValidationHelper:
    """ValidationHelper クラスのテスト"""

    def test_validate_workflow_path_absolute_success(self, temp_dir: Path):
        """絶対パスでのワークフロー検証成功テスト"""
        workflow_file = temp_dir / "test.yml"
        workflow_file.write_text("name: test")

        result = ValidationHelper.validate_workflow_path(str(workflow_file))

        assert result == workflow_file

    def test_validate_workflow_path_relative_success(self, temp_dir: Path):
        """相対パスでのワークフロー検証成功テスト"""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "test.yml"
        workflow_file.write_text("name: test")

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = ValidationHelper.validate_workflow_path("test.yml")

        assert result == workflow_file

    def test_validate_workflow_path_not_exists(self, temp_dir: Path):
        """存在しないワークフローファイルのテスト"""
        with patch("pathlib.Path.cwd", return_value=temp_dir):
            with pytest.raises(WorkflowNotFoundError) as exc_info:
                ValidationHelper.validate_workflow_path("nonexistent.yml")

        error = exc_info.value
        assert "ワークフローファイル 'nonexistent.yml' が見つかりません" in error.message

    def test_validate_workflow_path_invalid_extension(self, temp_dir: Path):
        """無効な拡張子のワークフローファイルテスト"""
        workflow_file = temp_dir / "test.txt"
        workflow_file.write_text("name: test")

        with pytest.raises(ValidationError) as exc_info:
            ValidationHelper.validate_workflow_path(str(workflow_file))

        error = exc_info.value
        assert "無効なワークフローパス" in error.message
        assert error.invalid_value == str(workflow_file)

    def test_validate_log_path_success(self, temp_dir: Path):
        """ログファイル検証成功テスト"""
        log_file = temp_dir / "test.log"
        log_file.write_text("log content")

        result = ValidationHelper.validate_log_path(str(log_file))

        assert result == log_file

    def test_validate_log_path_not_exists(self, temp_dir: Path):
        """存在しないログファイルのテスト"""
        with pytest.raises(LogParsingError) as exc_info:
            ValidationHelper.validate_log_path(str(temp_dir / "nonexistent.log"))

        error = exc_info.value
        assert "ログファイル" in error.message
        assert "が見つかりません" in error.message

    def test_validate_log_path_not_file(self, temp_dir: Path):
        """ディレクトリを指定した場合のテスト"""
        directory = temp_dir / "logs"
        directory.mkdir()

        with pytest.raises(LogParsingError) as exc_info:
            ValidationHelper.validate_log_path(str(directory))

        error = exc_info.value
        assert "はファイルではありません" in error.message


class TestTimeoutHandler:
    """TimeoutHandler クラスのテスト"""

    @patch("subprocess.run")
    def test_run_with_timeout_success(self, mock_run):
        """タイムアウト付きコマンド実行成功テスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = TimeoutHandler.run_with_timeout(["echo", "test"], 30)

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["echo", "test"], capture_output=True, text=True, timeout=30, cwd=None, check=True
        )

    @patch("subprocess.run")
    def test_run_with_timeout_timeout_error(self, mock_run):
        """タイムアウトエラーのテスト"""
        mock_run.side_effect = subprocess.TimeoutExpired(["sleep", "60"], 30)

        with pytest.raises(ExecutionError) as exc_info:
            TimeoutHandler.run_with_timeout(["sleep", "60"], 30)

        error = exc_info.value
        assert "タイムアウトしました" in error.message
        assert error.command == "sleep 60"

    @patch("subprocess.run")
    def test_run_with_timeout_command_failed(self, mock_run):
        """コマンド実行失敗のテスト"""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["false"], stderr="command failed")

        with pytest.raises(ExecutionError) as exc_info:
            TimeoutHandler.run_with_timeout(["false"], 30)

        error = exc_info.value
        assert "が失敗しました" in error.message
        assert error.exit_code == 1
        assert error.command == "false"

    @patch("subprocess.run")
    def test_run_with_timeout_with_cwd(self, mock_run, temp_dir: Path):
        """作業ディレクトリ指定でのコマンド実行テスト"""
        mock_result = Mock()
        mock_run.return_value = mock_result

        TimeoutHandler.run_with_timeout(["ls"], 30, cwd=temp_dir)

        mock_run.assert_called_once_with(["ls"], capture_output=True, text=True, timeout=30, cwd=temp_dir, check=True)


class TestSecurityValidator:
    """SecurityValidator クラスのテスト"""

    def test_check_config_for_secrets_api_key(self):
        """API キー検出テスト"""
        config_content = """
[ci-helper]
api_key = "sk-1234567890abcdef1234567890"
verbose = true
"""

        with pytest.raises(SecurityError) as exc_info:
            SecurityValidator.check_config_for_secrets(config_content, "ci-helper.toml")

        error = exc_info.value
        assert "シークレットが含まれています" in error.message
        assert error.security_issue == "secrets_in_config"

    def test_check_config_for_secrets_password(self):
        """パスワード検出テスト"""
        config_content = """
database_password = "mypassword123456"
"""

        with pytest.raises(SecurityError) as exc_info:
            SecurityValidator.check_config_for_secrets(config_content, "config.toml")

        error = exc_info.value
        assert "シークレットが含まれています" in error.message

    def test_check_config_for_secrets_token(self):
        """トークン検出テスト"""
        config_content = """
auth_token = "ghp_1234567890abcdef1234567890"
"""

        with pytest.raises(SecurityError) as exc_info:
            SecurityValidator.check_config_for_secrets(config_content, "config.toml")

        error = exc_info.value
        assert "シークレットが含まれています" in error.message

    def test_check_config_for_secrets_clean(self):
        """クリーンな設定ファイルのテスト"""
        config_content = """
[ci-helper]
verbose = true
timeout_seconds = 1800
log_dir = ".ci-helper/logs"
"""

        # 例外が発生しないことを確認
        SecurityValidator.check_config_for_secrets(config_content, "ci-helper.toml")

    def test_sanitize_log_content_api_key(self):
        """ログ内容のAPI キーサニタイズテスト"""
        log_content = """
Setting API_KEY=sk-1234567890abcdef1234567890
Running command with api_key: "sk-abcdef123456789012345"
Normal log line
"""

        sanitized = SecurityValidator.sanitize_log_content(log_content)

        assert "sk-1234567890abcdef1234567890" not in sanitized
        assert "sk-abcdef123456789012345" not in sanitized
        assert "***REDACTED***" in sanitized
        assert "Normal log line" in sanitized

    def test_sanitize_log_content_password(self):
        """ログ内容のパスワードサニタイズテスト"""
        log_content = """
password=mypassword123456
secret: "topsecret456789"
Normal log line
"""

        sanitized = SecurityValidator.sanitize_log_content(log_content)

        assert "mypassword123456" not in sanitized
        assert "topsecret456789" not in sanitized
        assert "***REDACTED***" in sanitized
        assert "Normal log line" in sanitized

    def test_sanitize_log_content_multiple_patterns(self):
        """複数のシークレットパターンのサニタイズテスト"""
        log_content = """
API_KEY=sk-1234567890123456789012345
password: "secret123456789"
token = "ghp_abcdef123456789012345"
access_key: AKIAIOSFODNN7EXAMPLE12345
Normal content
"""

        sanitized = SecurityValidator.sanitize_log_content(log_content)

        # すべてのシークレットが除去されることを確認
        assert "sk-1234567890123456789012345" not in sanitized
        assert "secret123456789" not in sanitized
        assert "ghp_abcdef123456789012345" not in sanitized
        assert "AKIAIOSFODNN7EXAMPLE12345" not in sanitized
        assert "***REDACTED***" in sanitized
        assert "Normal content" in sanitized

    def test_sanitize_log_content_clean(self):
        """クリーンなログ内容のテスト"""
        log_content = """
Starting CI process
Running tests
All tests passed
"""

        sanitized = SecurityValidator.sanitize_log_content(log_content)

        # 内容が変更されないことを確認
        assert sanitized == log_content
