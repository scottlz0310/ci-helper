"""
カスタム例外クラスのユニットテスト

各例外クラスの動作とメッセージ生成のテストを実装します。
"""

from unittest.mock import patch

from ci_helper.core.exceptions import (
    CIHelperError,
    ConfigurationError,
    DependencyError,
    DiskSpaceError,
    ExecutionError,
    LogParsingError,
    SecurityError,
    ValidationError,
    WorkflowNotFoundError,
)


class TestCIHelperError:
    """CIHelperError 基底クラスのテスト"""

    def test_basic_error_creation(self):
        """基本的なエラー作成テスト"""
        error = CIHelperError("テストエラー")

        assert error.message == "テストエラー"
        assert error.suggestion is None
        assert error.details is None
        assert str(error) == "テストエラー"

    def test_error_with_suggestion(self):
        """提案付きエラーのテスト"""
        error = CIHelperError("テストエラー", suggestion="解決方法")

        assert error.message == "テストエラー"
        assert error.suggestion == "解決方法"
        assert "💡 提案: 解決方法" in str(error)

    def test_error_with_details(self):
        """詳細付きエラーのテスト"""
        error = CIHelperError("テストエラー", details="詳細情報")

        assert error.message == "テストエラー"
        assert error.details == "詳細情報"
        assert "詳細: 詳細情報" in str(error)

    def test_error_with_all_fields(self):
        """全フィールド付きエラーのテスト"""
        error = CIHelperError("テストエラー", suggestion="解決方法", details="詳細情報")

        error_str = str(error)
        assert "テストエラー" in error_str
        assert "詳細: 詳細情報" in error_str
        assert "💡 提案: 解決方法" in error_str

    def test_get_user_friendly_message(self):
        """ユーザーフレンドリーメッセージ取得テスト"""
        error = CIHelperError("テストエラー", suggestion="解決方法")

        message = error.get_user_friendly_message()
        assert message == str(error)


class TestDependencyError:
    """DependencyError クラスのテスト"""

    def test_basic_dependency_error(self):
        """基本的な依存関係エラーテスト"""
        error = DependencyError("依存関係エラー", "インストールしてください", missing_dependency="act")

        assert error.message == "依存関係エラー"
        assert error.suggestion == "インストールしてください"
        assert error.missing_dependency == "act"

    @patch("platform.system")
    def test_act_not_found_macos(self, mock_system):
        """macOS での act 未発見エラーテスト"""
        mock_system.return_value = "Darwin"

        error = DependencyError.act_not_found()

        assert "act コマンドが見つかりません" in error.message
        assert error.suggestion is not None
        assert "brew install act" in error.suggestion
        assert error.missing_dependency == "act"

    @patch("platform.system")
    def test_act_not_found_linux(self, mock_system):
        """Linux での act 未発見エラーテスト"""
        mock_system.return_value = "Linux"

        error = DependencyError.act_not_found()

        assert "act コマンドが見つかりません" in error.message
        assert error.suggestion is not None
        assert "パッケージマネージャー" in error.suggestion
        assert error.missing_dependency == "act"

    @patch("platform.system")
    def test_act_not_found_windows(self, mock_system):
        """Windows での act 未発見エラーテスト"""
        mock_system.return_value = "Windows"

        error = DependencyError.act_not_found()

        assert "act コマンドが見つかりません" in error.message
        assert error.suggestion is not None
        assert "choco install act-cli" in error.suggestion
        assert error.missing_dependency == "act"

    @patch("platform.system")
    def test_act_not_found_unknown_os(self, mock_system):
        """未知のOS での act 未発見エラーテスト"""
        mock_system.return_value = "UnknownOS"

        error = DependencyError.act_not_found()

        assert "act コマンドが見つかりません" in error.message
        assert error.suggestion is not None
        assert "GitHub Releases からダウンロード" in error.suggestion
        assert error.missing_dependency == "act"

    def test_docker_not_running(self):
        """Docker 未実行エラーテスト"""
        error = DependencyError.docker_not_running()

        assert "Docker デーモンが実行されていません" in error.message
        assert error.suggestion is not None
        assert "Docker Desktop を起動してください" in error.suggestion
        assert error.missing_dependency == "docker"


class TestConfigurationError:
    """ConfigurationError クラスのテスト"""

    def test_basic_configuration_error(self):
        """基本的な設定エラーテスト"""
        error = ConfigurationError("設定エラー", "設定を確認してください", config_file="ci-helper.toml")

        assert error.message == "設定エラー"
        assert error.suggestion == "設定を確認してください"
        assert error.config_file == "ci-helper.toml"

    def test_invalid_config(self):
        """無効な設定ファイルエラーテスト"""
        error = ConfigurationError.invalid_config("ci-helper.toml", "TOML 構文エラー")

        assert "設定ファイル 'ci-helper.toml' が無効です" in error.message
        assert "TOML 構文エラー" in error.message
        assert error.suggestion is not None
        assert "ci-run init" in error.suggestion
        assert error.config_file == "ci-helper.toml"

    def test_missing_config(self):
        """設定ファイル未発見エラーテスト"""
        error = ConfigurationError.missing_config("ci-helper.toml")

        assert "設定ファイル 'ci-helper.toml' が見つかりません" in error.message
        assert error.suggestion is not None
        assert "ci-run init" in error.suggestion
        assert error.config_file == "ci-helper.toml"


class TestExecutionError:
    """ExecutionError クラスのテスト"""

    def test_basic_execution_error(self):
        """基本的な実行エラーテスト"""
        error = ExecutionError("実行エラー", "再試行してください", exit_code=1, command="act")

        assert error.message == "実行エラー"
        assert error.suggestion == "再試行してください"
        assert error.exit_code == 1
        assert error.command == "act"

    def test_timeout_error(self):
        """タイムアウトエラーテスト"""
        error = ExecutionError.timeout_error("act test", 300)

        assert "コマンド 'act test' が 300 秒でタイムアウトしました" in error.message
        assert error.suggestion is not None
        assert "より長いタイムアウト値" in error.suggestion
        assert error.command == "act test"

    def test_command_failed(self):
        """コマンド失敗エラーテスト"""
        error = ExecutionError.command_failed("act test", 1, "stderr output")

        assert "コマンド 'act test' が失敗しました" in error.message
        assert "終了コード: 1" in error.message
        assert error.suggestion is not None
        assert "コマンドの引数と環境を確認してください" in error.suggestion
        assert error.exit_code == 1
        assert error.command == "act test"

    def test_command_failed_no_stderr(self):
        """stderr なしのコマンド失敗エラーテスト"""
        error = ExecutionError.command_failed("act test", 2)

        assert "コマンド 'act test' が失敗しました" in error.message
        assert "終了コード: 2" in error.message
        assert error.exit_code == 2
        assert error.command == "act test"


class TestValidationError:
    """ValidationError クラスのテスト"""

    def test_basic_validation_error(self):
        """基本的な検証エラーテスト"""
        error = ValidationError("検証エラー", "正しい値を入力してください", invalid_value="invalid")

        assert error.message == "検証エラー"
        assert error.suggestion == "正しい値を入力してください"
        assert error.invalid_value == "invalid"

    def test_invalid_workflow_path(self):
        """無効なワークフローパスエラーテスト"""
        error = ValidationError.invalid_workflow_path("invalid/path.txt")

        assert "無効なワークフローパス: invalid/path.txt" in error.message
        assert ".github/workflows/" in error.suggestion
        assert ".yml または .yaml" in error.suggestion
        assert error.invalid_value == "invalid/path.txt"


class TestWorkflowNotFoundError:
    """WorkflowNotFoundError クラスのテスト"""

    def test_basic_workflow_not_found_error(self):
        """基本的なワークフロー未発見エラーテスト"""
        error = WorkflowNotFoundError(
            "ワークフローが見つかりません", "ファイルを確認してください", workflow_path="test.yml"
        )

        assert error.message == "ワークフローが見つかりません"
        assert error.suggestion == "ファイルを確認してください"
        assert error.workflow_path == "test.yml"

    def test_no_workflows_found(self):
        """ワークフローファイル未発見エラーテスト"""
        error = WorkflowNotFoundError.no_workflows_found()

        assert ".github/workflows ディレクトリにワークフローファイルが見つかりません" in error.message
        assert "GitHub Actions ワークフローファイル" in error.suggestion
        assert ".github/workflows/" in error.suggestion

    def test_specific_workflow_not_found(self):
        """特定ワークフロー未発見エラーテスト"""
        error = WorkflowNotFoundError.specific_workflow_not_found("test.yml")

        assert "ワークフローファイル 'test.yml' が見つかりません" in error.message
        assert "ワークフローファイル名を確認するか" in error.suggestion
        assert "ci-run logs" in error.suggestion
        assert error.workflow_path == "test.yml"


class TestLogParsingError:
    """LogParsingError クラスのテスト"""

    def test_basic_log_parsing_error(self):
        """基本的なログ解析エラーテスト"""
        error = LogParsingError("ログ解析エラー", "ファイルを確認してください", log_file="test.log")

        assert error.message == "ログ解析エラー"
        assert error.suggestion == "ファイルを確認してください"
        assert error.log_file == "test.log"

    def test_corrupted_log(self):
        """破損ログファイルエラーテスト"""
        error = LogParsingError.corrupted_log("corrupted.log")

        assert "ログファイル 'corrupted.log' が破損しているか、読み取れません" in error.message
        assert "ログファイルを削除して新しい実行を試してください" in error.suggestion
        assert error.log_file == "corrupted.log"


class TestDiskSpaceError:
    """DiskSpaceError クラスのテスト"""

    def test_basic_disk_space_error(self):
        """基本的なディスク容量エラーテスト"""
        error = DiskSpaceError("容量不足", "クリーンアップしてください", available_space=50, required_space=100)

        assert error.message == "容量不足"
        assert error.suggestion == "クリーンアップしてください"
        assert error.available_space == 50
        assert error.required_space == 100

    def test_insufficient_space(self):
        """容量不足エラーテスト"""
        error = DiskSpaceError.insufficient_space(50, 100)

        assert "ディスク容量が不足しています" in error.message
        assert "利用可能: 50MB" in error.message
        assert "必要: 100MB" in error.message
        assert "ci-run clean" in error.suggestion
        assert error.available_space == 50
        assert error.required_space == 100


class TestSecurityError:
    """SecurityError クラスのテスト"""

    def test_basic_security_error(self):
        """基本的なセキュリティエラーテスト"""
        error = SecurityError("セキュリティエラー", "設定を確認してください", security_issue="secrets_detected")

        assert error.message == "セキュリティエラー"
        assert error.suggestion == "設定を確認してください"
        assert error.security_issue == "secrets_detected"

    def test_secrets_in_config(self):
        """設定ファイル内シークレットエラーテスト"""
        error = SecurityError.secrets_in_config("ci-helper.toml")

        assert "設定ファイル 'ci-helper.toml' にシークレットが含まれています" in error.message
        assert "シークレットは環境変数で設定してください" in error.suggestion
        assert "設定ファイルからシークレットを削除してください" in error.suggestion
        assert error.security_issue == "secrets_in_config"


class TestExceptionInheritance:
    """例外継承関係のテスト"""

    def test_all_exceptions_inherit_from_ci_helper_error(self):
        """すべての例外が CIHelperError を継承することのテスト"""
        exceptions = [
            DependencyError("test"),
            ConfigurationError("test"),
            ExecutionError("test"),
            ValidationError("test"),
            WorkflowNotFoundError("test"),
            LogParsingError("test"),
            DiskSpaceError("test"),
            SecurityError("test"),
        ]

        for exception in exceptions:
            assert isinstance(exception, CIHelperError)
            assert isinstance(exception, Exception)

    def test_exception_str_methods(self):
        """例外の文字列表現テスト"""
        exceptions = [
            DependencyError("依存関係エラー", "解決方法"),
            ConfigurationError("設定エラー", "解決方法"),
            ExecutionError("実行エラー", "解決方法"),
            ValidationError("検証エラー", "解決方法"),
            WorkflowNotFoundError("ワークフローエラー", "解決方法"),
            LogParsingError("ログエラー", "解決方法"),
            DiskSpaceError("容量エラー", "解決方法"),
            SecurityError("セキュリティエラー", "解決方法"),
        ]

        for exception in exceptions:
            error_str = str(exception)
            assert exception.message in error_str
            assert "💡 提案: 解決方法" in error_str

    def test_exception_attributes_preservation(self):
        """例外属性の保持テスト"""
        # DependencyError
        dep_error = DependencyError("test", missing_dependency="act")
        assert hasattr(dep_error, "missing_dependency")
        assert dep_error.missing_dependency == "act"

        # ConfigurationError
        config_error = ConfigurationError("test", config_file="config.toml")
        assert hasattr(config_error, "config_file")
        assert config_error.config_file == "config.toml"

        # ExecutionError
        exec_error = ExecutionError("test", exit_code=1, command="act")
        assert hasattr(exec_error, "exit_code")
        assert hasattr(exec_error, "command")
        assert exec_error.exit_code == 1
        assert exec_error.command == "act"

        # ValidationError
        val_error = ValidationError("test", invalid_value="invalid")
        assert hasattr(val_error, "invalid_value")
        assert val_error.invalid_value == "invalid"

        # WorkflowNotFoundError
        workflow_error = WorkflowNotFoundError("test", workflow_path="test.yml")
        assert hasattr(workflow_error, "workflow_path")
        assert workflow_error.workflow_path == "test.yml"

        # LogParsingError
        log_error = LogParsingError("test", log_file="test.log")
        assert hasattr(log_error, "log_file")
        assert log_error.log_file == "test.log"

        # DiskSpaceError
        disk_error = DiskSpaceError("test", available_space=50, required_space=100)
        assert hasattr(disk_error, "available_space")
        assert hasattr(disk_error, "required_space")
        assert disk_error.available_space == 50
        assert disk_error.required_space == 100

        # SecurityError
        sec_error = SecurityError("test", security_issue="secrets")
        assert hasattr(sec_error, "security_issue")
        assert sec_error.security_issue == "secrets"
