"""
CI実行エンジンのユニットテスト

CIRunnerクラスの各機能をテストします。
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ci_helper.core.ci_runner import CIRunner
from ci_helper.core.exceptions import ExecutionError, SecurityError
from ci_helper.core.models import ExecutionResult, WorkflowResult
from ci_helper.utils.config import Config


class TestCIRunnerInitialization:
    """CIRunnerの初期化テスト"""

    def test_init_with_config(self, sample_config: Config):
        """設定を使用した初期化テスト"""
        runner = CIRunner(sample_config)

        assert runner.config == sample_config
        assert runner.project_root == sample_config.project_root
        assert hasattr(runner, "secret_manager")
        assert hasattr(runner, "security_validator")

    def test_init_with_custom_project_root(self, temp_dir: Path):
        """カスタムプロジェクトルートでの初期化テスト"""
        config = Config(project_root=temp_dir)
        runner = CIRunner(config)

        assert runner.project_root == temp_dir


class TestWorkflowDiscovery:
    """ワークフロー検出のテスト"""

    def test_discover_workflows_all(self, sample_workflow_dir: Path, sample_config: Config):
        """全ワークフロー検出のテスト"""
        # 追加のワークフローファイルを作成
        (sample_workflow_dir / "build.yml").write_text("name: Build")
        (sample_workflow_dir / "deploy.yaml").write_text("name: Deploy")

        runner = CIRunner(sample_config)
        workflows = runner._discover_workflows()

        assert len(workflows) == 3
        workflow_names = [w.name for w in workflows]
        assert "test.yml" in workflow_names
        assert "build.yml" in workflow_names
        assert "deploy.yaml" in workflow_names

    def test_discover_workflows_specific(self, sample_workflow_dir: Path, sample_config: Config):
        """特定ワークフロー検出のテスト"""
        (sample_workflow_dir / "build.yml").write_text("name: Build")

        runner = CIRunner(sample_config)
        workflows = runner._discover_workflows(["test"])

        assert len(workflows) == 1
        assert workflows[0].name == "test.yml"

    def test_discover_workflows_with_extension(self, sample_workflow_dir: Path, sample_config: Config):
        """拡張子付きワークフロー検出のテスト"""
        runner = CIRunner(sample_config)
        workflows = runner._discover_workflows(["test.yml"])

        assert len(workflows) == 1
        assert workflows[0].name == "test.yml"

    def test_discover_workflows_no_directory(self, sample_config: Config):
        """ワークフローディレクトリが存在しない場合のテスト"""
        runner = CIRunner(sample_config)
        workflows = runner._discover_workflows()

        assert len(workflows) == 0

    def test_discover_workflows_empty_directory(self, temp_dir: Path):
        """空のワークフローディレクトリのテスト"""
        workflow_dir = temp_dir / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)

        config = Config(project_root=temp_dir)
        runner = CIRunner(config)
        workflows = runner._discover_workflows()

        assert len(workflows) == 0

    def test_discover_workflows_nonexistent_specific(self, sample_workflow_dir: Path, sample_config: Config):
        """存在しない特定ワークフローの検出テスト"""
        runner = CIRunner(sample_config)
        workflows = runner._discover_workflows(["nonexistent"])

        assert len(workflows) == 0


class TestActExecution:
    """act実行のテスト"""

    @patch("subprocess.run")
    def test_execute_act_success(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """act実行成功のテスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Workflow completed successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        result = runner._execute_act(workflow_file, verbose=False)

        assert result.returncode == 0
        assert "successfully" in result.stdout
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_act_with_verbose(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """詳細モードでのact実行テスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Verbose output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        runner._execute_act(workflow_file, verbose=True)

        # -v オプションが含まれることを確認
        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args

    @patch("subprocess.run")
    def test_execute_act_with_custom_image(self, mock_run, sample_workflow_dir: Path, temp_dir: Path):
        """カスタムDockerイメージでのact実行テスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Custom image output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # カスタムイメージ設定を含む設定を作成
        config = Config(project_root=temp_dir)
        with patch.object(config, "get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "act_image": "custom-ubuntu:latest",
                "timeout_seconds": 1800,
                "env_file": None,
                "environment_variables": {},
            }.get(key, default)

            runner = CIRunner(config)
            workflow_file = sample_workflow_dir / "test.yml"

            runner._execute_act(workflow_file, verbose=False)

            # カスタムイメージオプションが含まれることを確認
            call_args = mock_run.call_args[0][0]
            assert "-P" in call_args
            assert "ubuntu-latest=custom-ubuntu:latest" in call_args

    @patch("subprocess.run")
    def test_execute_act_with_env_file(self, mock_run, sample_workflow_dir: Path, temp_dir: Path):
        """環境変数ファイル付きのact実行テスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Env file output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # 環境変数ファイルを作成
        env_file = temp_dir / ".env"
        env_file.write_text("TEST_VAR=test_value")

        config = Config(project_root=temp_dir)
        with patch.object(config, "get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "env_file": str(env_file),
                "timeout_seconds": 1800,
                "act_image": None,
                "environment_variables": {},
            }.get(key, default)

            runner = CIRunner(config)
            workflow_file = sample_workflow_dir / "test.yml"

            runner._execute_act(workflow_file, verbose=False)

            # 環境変数ファイルオプションが含まれることを確認
            call_args = mock_run.call_args[0][0]
            assert "--env-file" in call_args
            assert str(env_file) in call_args

    @patch("subprocess.run")
    def test_execute_act_command_not_found(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """actコマンドが見つからない場合のテスト"""
        mock_run.side_effect = FileNotFoundError("act command not found")

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        with pytest.raises(ExecutionError) as exc_info:
            runner._execute_act(workflow_file, verbose=False)

        assert "actコマンドが見つかりません" in str(exc_info.value)

    @patch("subprocess.run")
    def test_execute_act_timeout(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """act実行タイムアウトのテスト"""
        mock_run.side_effect = subprocess.TimeoutExpired("act", 1800)

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        with pytest.raises(ExecutionError) as exc_info:
            runner._execute_act(workflow_file, verbose=False)

        assert "タイムアウト" in str(exc_info.value)

    @patch("ci_helper.core.ci_runner.CIRunner._prepare_secure_environment")
    @patch("subprocess.run")
    def test_execute_act_with_secure_environment(
        self, mock_run, mock_prepare_env, sample_workflow_dir: Path, sample_config: Config
    ):
        """安全な環境変数でのact実行テスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Secure execution"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        mock_secure_env = {"PATH": "/usr/bin", "SAFE_VAR": "safe_value"}
        mock_prepare_env.return_value = mock_secure_env

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        runner._execute_act(workflow_file, verbose=False)

        # 安全な環境変数が使用されることを確認
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == mock_secure_env


class TestSingleWorkflowExecution:
    """単一ワークフロー実行のテスト"""

    @patch("ci_helper.core.ci_runner.CIRunner._execute_act")
    def test_run_single_workflow_success(self, mock_execute_act, sample_workflow_dir: Path, sample_config: Config):
        """単一ワークフロー実行成功のテスト"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Workflow output"
        mock_result.stderr = ""
        mock_execute_act.return_value = mock_result

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        workflow_result, output = runner._run_single_workflow(workflow_file, verbose=False)

        assert workflow_result.success is True
        assert workflow_result.name == "test.yml"
        assert len(workflow_result.jobs) == 1
        assert workflow_result.jobs[0].name == "default"
        assert workflow_result.jobs[0].success is True
        assert output == "Workflow output"

    @patch("ci_helper.core.ci_runner.CIRunner._execute_act")
    def test_run_single_workflow_failure(self, mock_execute_act, sample_workflow_dir: Path, sample_config: Config):
        """単一ワークフロー実行失敗のテスト"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Workflow failed"
        mock_result.stderr = "Error occurred"
        mock_execute_act.return_value = mock_result

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        workflow_result, output = runner._run_single_workflow(workflow_file, verbose=False)

        assert workflow_result.success is False
        assert workflow_result.name == "test.yml"
        assert len(workflow_result.jobs) == 1
        assert workflow_result.jobs[0].success is False
        assert "Workflow failed" in output
        assert "Error occurred" in output

    @patch("ci_helper.core.ci_runner.CIRunner._execute_act")
    def test_run_single_workflow_timeout_exception(
        self, mock_execute_act, sample_workflow_dir: Path, sample_config: Config
    ):
        """単一ワークフロー実行でタイムアウト例外のテスト"""
        mock_execute_act.side_effect = subprocess.TimeoutExpired("act", 1800)

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        with pytest.raises(ExecutionError) as exc_info:
            runner._run_single_workflow(workflow_file, verbose=False)

        assert "タイムアウト" in str(exc_info.value)
        assert "test.yml" in str(exc_info.value)

    @patch("ci_helper.core.ci_runner.CIRunner._execute_act")
    def test_run_single_workflow_general_exception(
        self, mock_execute_act, sample_workflow_dir: Path, sample_config: Config
    ):
        """単一ワークフロー実行で一般的な例外のテスト"""
        mock_execute_act.side_effect = Exception("Unexpected error")

        runner = CIRunner(sample_config)
        workflow_file = sample_workflow_dir / "test.yml"

        with pytest.raises(ExecutionError) as exc_info:
            runner._run_single_workflow(workflow_file, verbose=False)

        assert "実行に失敗しました" in str(exc_info.value)
        assert "test.yml" in str(exc_info.value)


class TestWorkflowsExecution:
    """複数ワークフロー実行のテスト"""

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_success(self, mock_discover, mock_run_single, sample_config: Config):
        """複数ワークフロー実行成功のテスト"""
        # モックワークフローファイルを設定
        mock_workflow_files = [Path("test.yml"), Path("build.yml")]
        mock_discover.return_value = mock_workflow_files

        # モック実行結果を設定
        mock_workflow_result1 = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_workflow_result2 = WorkflowResult(name="build.yml", success=True, jobs=[], duration=3.0)

        mock_run_single.side_effect = [(mock_workflow_result1, "Test output"), (mock_workflow_result2, "Build output")]

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=False)

        assert result.success is True
        assert len(result.workflows) == 2
        assert result.workflows[0].name == "test.yml"
        assert result.workflows[1].name == "build.yml"
        assert result.total_duration > 0

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_with_failure(self, mock_discover, mock_run_single, sample_config: Config):
        """一部失敗を含む複数ワークフロー実行のテスト"""
        mock_workflow_files = [Path("test.yml"), Path("build.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result1 = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_workflow_result2 = WorkflowResult(name="build.yml", success=False, jobs=[], duration=3.0)

        mock_run_single.side_effect = [(mock_workflow_result1, "Test output"), (mock_workflow_result2, "Build failed")]

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=False)

        assert result.success is False
        assert len(result.workflows) == 2
        assert result.workflows[0].success is True
        assert result.workflows[1].success is False

    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_no_workflows_found(self, mock_discover, sample_config: Config):
        """ワークフローが見つからない場合のテスト"""
        mock_discover.return_value = []

        runner = CIRunner(sample_config)

        with pytest.raises(ExecutionError) as exc_info:
            runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=False)

        assert "実行するワークフローが見つかりません" in str(exc_info.value)

    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_dry_run(self, mock_discover, sample_config: Config):
        """ドライラン実行のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=None, verbose=False, dry_run=True, save_logs=False)

        assert result.success is True
        assert len(result.workflows) == 1
        assert result.workflows[0].success is True
        assert result.workflows[0].duration == 0.0

    @patch("ci_helper.core.log_manager.LogManager")
    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_with_log_saving(
        self, mock_discover, mock_run_single, mock_log_manager, sample_config: Config
    ):
        """ログ保存付きワークフロー実行のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_run_single.return_value = (mock_workflow_result, "Test output")

        mock_log_manager_instance = Mock()
        mock_log_manager.return_value = mock_log_manager_instance

        runner = CIRunner(sample_config)
        runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=True)

        # ログ保存メソッドが呼ばれることを確認
        mock_log_manager_instance.save_execution_log.assert_called_once()
        mock_log_manager_instance.save_execution_history_metadata.assert_called_once()

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_run_workflows_specific_workflows(self, mock_discover, mock_run_single, sample_config: Config):
        """特定ワークフロー指定での実行テスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_run_single.return_value = (mock_workflow_result, "Test output")

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=["test"], verbose=False, dry_run=False, save_logs=False)

        # 指定されたワークフローで検出が呼ばれることを確認
        mock_discover.assert_called_once_with(["test"])
        assert result.success is True


class TestDependencyChecking:
    """依存関係チェックのテスト"""

    @patch("subprocess.run")
    def test_check_dependencies_all_available(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """全依存関係が利用可能な場合のテスト"""
        # act と docker コマンドが成功することをモック
        mock_run.return_value = Mock(returncode=0)

        runner = CIRunner(sample_config)
        checks = runner.check_dependencies()

        assert checks["act"] is True
        assert checks["docker"] is True
        assert checks["workflows_dir"] is True

    @patch("subprocess.run")
    def test_check_dependencies_act_missing(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """actコマンドが見つからない場合のテスト"""

        def mock_run_side_effect(cmd, **kwargs):
            if "act" in cmd:
                raise FileNotFoundError("act not found")
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        runner = CIRunner(sample_config)
        checks = runner.check_dependencies()

        assert checks["act"] is False
        assert checks["docker"] is True
        assert checks["workflows_dir"] is True

    @patch("subprocess.run")
    def test_check_dependencies_docker_not_running(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """Dockerデーモンが実行されていない場合のテスト"""

        def mock_run_side_effect(cmd, **kwargs):
            if "docker" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        runner = CIRunner(sample_config)
        checks = runner.check_dependencies()

        assert checks["act"] is True
        assert checks["docker"] is False
        assert checks["workflows_dir"] is True

    @patch("subprocess.run")
    def test_check_dependencies_no_workflows_dir(self, mock_run, sample_config: Config):
        """ワークフローディレクトリが存在しない場合のテスト"""
        mock_run.return_value = Mock(returncode=0)

        runner = CIRunner(sample_config)
        checks = runner.check_dependencies()

        assert checks["act"] is True
        assert checks["docker"] is True
        assert checks["workflows_dir"] is False

    @patch("subprocess.run")
    def test_check_dependencies_timeout(self, mock_run, sample_workflow_dir: Path, sample_config: Config):
        """依存関係チェックでタイムアウトが発生する場合のテスト"""

        def mock_run_side_effect(cmd, **kwargs):
            if "act" in cmd:
                raise subprocess.TimeoutExpired(cmd, 10)
            return Mock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        runner = CIRunner(sample_config)
        checks = runner.check_dependencies()

        assert checks["act"] is False
        assert checks["docker"] is True
        assert checks["workflows_dir"] is True


class TestSecurityValidation:
    """セキュリティ検証のテスト"""

    def test_validate_security_success(self, sample_config: Config):
        """セキュリティ検証成功のテスト"""
        runner = CIRunner(sample_config)

        with patch.object(runner.secret_manager, "validate_secrets") as mock_validate:
            mock_validate.return_value = {"valid": True, "missing_secrets": []}

            result = runner.validate_security(["API_KEY", "SECRET_TOKEN"])

            assert result["valid"] is True
            mock_validate.assert_called_once_with(["API_KEY", "SECRET_TOKEN"])

    def test_validate_security_missing_secrets(self, sample_config: Config):
        """必須シークレットが不足している場合のテスト"""
        runner = CIRunner(sample_config)

        with patch.object(runner.secret_manager, "validate_secrets") as mock_validate:
            mock_validate.return_value = {"valid": False, "missing_secrets": ["API_KEY"]}

            result = runner.validate_security(["API_KEY", "SECRET_TOKEN"])

            assert result["valid"] is False
            assert "API_KEY" in result["missing_secrets"]

    def test_get_secret_summary(self, sample_config: Config):
        """シークレット設定状況取得のテスト"""
        runner = CIRunner(sample_config)

        with patch.object(runner.secret_manager, "get_secret_summary") as mock_summary:
            mock_summary.return_value = {"total_secrets": 3, "environment_secrets": 2, "file_secrets": 1}

            result = runner.get_secret_summary()

            assert result["total_secrets"] == 3
            assert result["environment_secrets"] == 2
            mock_summary.assert_called_once()


class TestSecureEnvironmentPreparation:
    """安全な環境変数準備のテスト"""

    def test_prepare_secure_environment_success(self, sample_config: Config):
        """安全な環境変数準備成功のテスト"""
        runner = CIRunner(sample_config)

        with patch.object(runner.secret_manager, "prepare_act_environment") as mock_prepare:
            mock_prepare.return_value = {"PATH": "/usr/bin", "API_KEY": "safe_key_value", "CUSTOM_VAR": "custom_value"}

            with patch.object(sample_config, "get") as mock_get:
                mock_get.return_value = {"CUSTOM_VAR": "custom_value"}

                result = runner._prepare_secure_environment()

                assert "PATH" in result
                assert "API_KEY" in result
                assert "CUSTOM_VAR" in result
                mock_prepare.assert_called_once()

    def test_prepare_secure_environment_error(self, sample_config: Config):
        """安全な環境変数準備でエラーが発生する場合のテスト"""
        runner = CIRunner(sample_config)

        with patch.object(runner.secret_manager, "prepare_act_environment") as mock_prepare:
            mock_prepare.side_effect = Exception("Environment preparation failed")

            with patch.object(sample_config, "get") as mock_get:
                mock_get.return_value = {}

                with pytest.raises(SecurityError) as exc_info:
                    runner._prepare_secure_environment()

                assert "環境変数の準備中にエラーが発生しました" in str(exc_info.value)


class TestOptionProcessing:
    """オプション処理のテスト"""

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_verbose_option_processing(self, mock_discover, mock_run_single, sample_config: Config):
        """詳細オプション処理のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_run_single.return_value = (mock_workflow_result, "Verbose output")

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=None, verbose=True, dry_run=False, save_logs=False)

        # 詳細モードで実行されることを確認
        mock_run_single.assert_called_once_with(mock_workflow_files[0], True)
        assert result.success is True

    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_save_logs_option_processing(self, mock_discover, sample_config: Config):
        """ログ保存オプション処理のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        with patch("ci_helper.core.log_manager.LogManager") as mock_log_manager:
            mock_log_manager_instance = Mock()
            mock_log_manager.return_value = mock_log_manager_instance

            with patch.object(CIRunner, "_run_single_workflow") as mock_run_single:
                mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
                mock_run_single.return_value = (mock_workflow_result, "Test output")

                runner = CIRunner(sample_config)

                # save_logs=True の場合
                runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=True)
                mock_log_manager_instance.save_execution_log.assert_called_once()

                # save_logs=False の場合
                mock_log_manager_instance.reset_mock()
                runner.run_workflows(workflows=None, verbose=False, dry_run=False, save_logs=False)
                mock_log_manager_instance.save_execution_log.assert_not_called()

    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_dry_run_option_processing(self, mock_discover, sample_config: Config):
        """ドライランオプション処理のテスト"""
        mock_workflow_files = [Path("test.yml"), Path("build.yml")]
        mock_discover.return_value = mock_workflow_files

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=None, verbose=False, dry_run=True, save_logs=False)

        # ドライランでは実際の実行は行われない
        assert result.success is True
        assert len(result.workflows) == 2
        for workflow in result.workflows:
            assert workflow.success is True
            assert workflow.duration == 0.0

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_workflow_selection_option_processing(self, mock_discover, mock_run_single, sample_config: Config):
        """ワークフロー選択オプション処理のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_run_single.return_value = (mock_workflow_result, "Test output")

        runner = CIRunner(sample_config)
        result = runner.run_workflows(workflows=["test", "build"], verbose=False, dry_run=False, save_logs=False)

        # 指定されたワークフローで検出が呼ばれることを確認
        mock_discover.assert_called_once_with(["test", "build"])
        assert result.success is True


class TestLogSaving:
    """ログ保存機能のテスト"""

    @patch("ci_helper.core.log_manager.LogManager")
    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_log_saving_with_metadata(self, mock_discover, mock_run_single, mock_log_manager, sample_config: Config):
        """メタデータ付きログ保存のテスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        mock_workflow_result = WorkflowResult(name="test.yml", success=True, jobs=[], duration=5.0)
        mock_run_single.return_value = (mock_workflow_result, "Test output")

        mock_log_manager_instance = Mock()
        mock_log_manager.return_value = mock_log_manager_instance

        runner = CIRunner(sample_config)
        runner.run_workflows(workflows=["test"], verbose=True, dry_run=False, save_logs=True)

        # ログ保存が適切な引数で呼ばれることを確認
        mock_log_manager_instance.save_execution_log.assert_called_once()
        call_args = mock_log_manager_instance.save_execution_log.call_args

        # ExecutionResult が渡されることを確認
        assert isinstance(call_args[0][0], ExecutionResult)
        # 出力が渡されることを確認
        assert call_args[0][1] == "Test output"
        # コマンド引数が渡されることを確認
        command_args = call_args[0][2]
        assert command_args["workflows"] == ["test"]
        assert command_args["verbose"] is True
        assert command_args["dry_run"] is False

        # 実行履歴メタデータも保存されることを確認
        mock_log_manager_instance.save_execution_history_metadata.assert_called_once()

    @patch("ci_helper.core.ci_runner.CIRunner._run_single_workflow")
    @patch("ci_helper.core.ci_runner.CIRunner._discover_workflows")
    def test_log_saving_disabled_in_dry_run(self, mock_discover, mock_run_single, sample_config: Config):
        """ドライラン時のログ保存無効化テスト"""
        mock_workflow_files = [Path("test.yml")]
        mock_discover.return_value = mock_workflow_files

        with patch("ci_helper.core.log_manager.LogManager") as mock_log_manager:
            mock_log_manager_instance = Mock()
            mock_log_manager.return_value = mock_log_manager_instance

            runner = CIRunner(sample_config)
            runner.run_workflows(
                workflows=None,
                verbose=False,
                dry_run=True,
                save_logs=True,  # ドライランでは無視される
            )

            # ドライランではログ保存されないことを確認
            mock_log_manager_instance.save_execution_log.assert_not_called()
            mock_log_manager_instance.save_execution_history_metadata.assert_not_called()
