"""
コマンド間連携テスト - 複数のコマンドが連携して動作することをテスト
"""

import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from ci_helper.cli import cli
from ci_helper.core.models import ExecutionResult, JobResult, WorkflowResult


class TestCommandIntegration:
    """コマンド間の連携をテストするクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナーを提供"""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, temp_dir: Path) -> Path:
        """初期化済みプロジェクトディレクトリを作成"""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # Confirm.ask をモックして対話的入力を回避
            with patch("ci_helper.commands.init.Confirm.ask", return_value=False):
                # initコマンドを実行
                result = runner.invoke(cli, ["init"])
                assert result.exit_code == 0

            # ワークフローディレクトリを作成
            workflows_dir = temp_dir / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)

            # サンプルワークフローをコピー
            fixtures_dir = Path(__file__).parent.parent / "fixtures" / "sample_workflows"
            for workflow_file in fixtures_dir.glob("*.yml"):
                shutil.copy(workflow_file, workflows_dir)

        return temp_dir

    def test_init_then_doctor_workflow(self, runner: CliRunner, temp_dir: Path):
        """init → doctor の連携フローをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 1. initコマンドを実行
            with patch("ci_helper.commands.init.Confirm.ask", return_value=False):
                init_result = runner.invoke(cli, ["init"])
                assert init_result.exit_code == 0

            # 2. doctorコマンドを実行
            with (
                patch("shutil.which") as mock_which,
                patch("ci_helper.commands.doctor.check_docker_daemon") as mock_docker,
            ):
                mock_which.return_value = "/usr/local/bin/act"  # actが見つかる
                mock_docker.return_value = True  # Dockerが起動している

                doctor_result = runner.invoke(cli, ["doctor"])

                # doctorが成功することを確認
                assert doctor_result.exit_code == 0
                assert "✓" in doctor_result.output or "成功" in doctor_result.output

    @patch("ci_helper.core.ci_runner.CIRunner.run_workflows")
    def test_test_then_logs_workflow(self, mock_run: Mock, runner: CliRunner, initialized_project: Path):
        """test → logs の連携フローをテスト"""
        # テスト実行のモック結果を設定
        log_path = initialized_project / ".ci-helper" / "logs" / "act_20231215_103000.log"
        mock_result = ExecutionResult(
            success=True,
            workflows=[
                WorkflowResult(
                    name="simple_test.yml",
                    success=True,
                    jobs=[JobResult(name="test", success=True, failures=[], steps=[])],
                    duration=10.5,
                )
            ],
            total_duration=10.5,
            log_path=str(log_path),
        )
        mock_run.return_value = mock_result

        with runner.isolated_filesystem(temp_dir=str(initialized_project)):
            # 1. testコマンドを実行
            test_result = runner.invoke(cli, ["test", "--workflow", "simple_test.yml"])
            assert test_result.exit_code == 0

            # ログファイルを作成（実際のテストではCIRunnerが作成する）
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("Sample log content")

            # 2. logsコマンドを実行
            logs_result = runner.invoke(cli, ["logs"])
            assert logs_result.exit_code == 0
            assert "act_20231215_103000.log" in logs_result.output

    @patch("ci_helper.core.ci_runner.CIRunner.run_workflows")
    def test_test_then_clean_workflow(self, mock_run: Mock, runner: CliRunner, initialized_project: Path):
        """test → clean の連携フローをテスト"""
        # テスト実行のモック結果を設定
        log_path = initialized_project / ".ci-helper" / "logs" / "test.log"
        mock_result = ExecutionResult(
            success=True,
            workflows=[
                WorkflowResult(
                    name="simple_test.yml",
                    success=True,
                    jobs=[JobResult(name="test", success=True, failures=[], steps=[])],
                    duration=10.5,
                )
            ],
            total_duration=10.5,
            log_path=str(log_path),
        )
        mock_run.return_value = mock_result

        with runner.isolated_filesystem(temp_dir=str(initialized_project)):
            # 1. testコマンドを実行
            test_result = runner.invoke(cli, ["test"])
            assert test_result.exit_code == 0

            # ログファイルを作成
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("Sample log content")

            # 2. cleanコマンドを実行
            clean_result = runner.invoke(cli, ["clean", "--logs-only"], input="y\n")
            assert clean_result.exit_code == 0

            # ログファイルが削除されたことを確認
            assert not log_path.exists()

    def test_config_persistence_across_commands(self, runner: CliRunner, initialized_project: Path):
        """設定がコマンド間で正しく保持されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(initialized_project)):
            # 設定ファイルを編集
            config_file = initialized_project / "ci-helper.toml"
            config_content = """
[logging]
level = "DEBUG"
save_logs = true

[act]
platform = "ubuntu-latest=catthehacker/ubuntu:act-latest"
"""
            config_file.write_text(config_content)

            # 複数のコマンドで設定が読み込まれることを確認
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/act"

                # doctorコマンド
                doctor_result = runner.invoke(cli, ["doctor", "--verbose"])
                assert doctor_result.exit_code == 0

                # logsコマンド
                logs_result = runner.invoke(cli, ["logs"])
                assert logs_result.exit_code == 0

    def test_error_handling_across_commands(self, runner: CliRunner, temp_dir: Path):
        """エラーハンドリングがコマンド間で一貫していることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # ワークフローディレクトリが存在しない状態でテスト

            # doctorコマンド - ワークフローディレクトリの不在を検出
            doctor_result = runner.invoke(cli, ["doctor"])
            assert ".github/workflows" in doctor_result.output

            # testコマンド - 同様のエラーを検出
            test_result = runner.invoke(cli, ["test"])
            assert test_result.exit_code != 0

    @patch("ci_helper.core.ci_runner.CIRunner.run_workflows")
    def test_log_comparison_workflow(self, mock_run: Mock, runner: CliRunner, initialized_project: Path):
        """ログ比較機能の統合テスト"""
        from ci_helper.core.models import Failure, FailureType

        with runner.isolated_filesystem(temp_dir=str(initialized_project)):
            # 最初のテスト実行（成功）
            success_result = ExecutionResult(
                success=True,
                workflows=[
                    WorkflowResult(
                        name="test.yml",
                        success=True,
                        jobs=[JobResult(name="test", success=True, failures=[], steps=[])],
                        duration=10.0,
                    )
                ],
                total_duration=10.0,
                log_path=str(initialized_project / ".ci-helper" / "logs" / "run1.log"),
            )
            mock_run.return_value = success_result

            first_result = runner.invoke(cli, ["test"])
            assert first_result.exit_code == 0

            # 2回目のテスト実行（失敗）
            failure_result = ExecutionResult(
                success=False,
                workflows=[
                    WorkflowResult(
                        name="test.yml",
                        success=False,
                        jobs=[
                            JobResult(
                                name="test",
                                success=False,
                                failures=[
                                    Failure(
                                        type=FailureType.ERROR,
                                        message="Test failed",
                                        file_path=None,
                                        line_number=None,
                                        context_before=[],
                                        context_after=[],
                                        stack_trace=None,
                                    )
                                ],
                                steps=[],
                            )
                        ],
                        duration=5.0,
                    )
                ],
                total_duration=5.0,
                log_path=str(initialized_project / ".ci-helper" / "logs" / "run2.log"),
            )
            mock_run.return_value = failure_result

            # 差分比較付きでテスト実行
            diff_result = runner.invoke(cli, ["test", "--diff"])
            assert diff_result.exit_code != 0
            # 差分情報が含まれていることを確認（実装に依存）
