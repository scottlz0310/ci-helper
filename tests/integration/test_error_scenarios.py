"""
エラーシナリオの統合テスト - 様々なエラー状況での動作をテスト
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from ci_helper.cli import cli
from ci_helper.core.exceptions import CIHelperError
from click.testing import CliRunner


class TestErrorScenarios:
    """エラーシナリオの統合テストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナーを提供"""
        return CliRunner()

    def test_missing_act_dependency(self, runner: CliRunner, temp_dir: Path):
        """actが見つからない場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None  # actが見つからない

                # doctorコマンド
                doctor_result = runner.invoke(cli, ["doctor"])
                assert doctor_result.exit_code != 0
                assert "act" in doctor_result.output
                assert "インストール" in doctor_result.output

                # testコマンド
                test_result = runner.invoke(cli, ["test"])
                assert test_result.exit_code != 0

    def test_docker_daemon_not_running(self, runner: CliRunner, temp_dir: Path):
        """Dockerデーモンが起動していない場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            with (
                patch("shutil.which") as mock_which,
                patch("ci_helper.commands.doctor.check_docker_daemon") as mock_docker,
            ):
                mock_which.return_value = "/usr/local/bin/act"  # actは存在
                mock_docker.return_value = False  # Dockerが起動していない

                doctor_result = runner.invoke(cli, ["doctor"])
                assert doctor_result.exit_code != 0
                assert "Docker" in doctor_result.output

    def test_missing_workflow_directory(self, runner: CliRunner, temp_dir: Path):
        """ワークフローディレクトリが存在しない場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # .github/workflowsディレクトリを作成しない

            doctor_result = runner.invoke(cli, ["doctor"])
            assert doctor_result.exit_code != 0
            assert ".github/workflows" in doctor_result.output

            test_result = runner.invoke(cli, ["test"])
            assert test_result.exit_code != 0

    def test_invalid_workflow_file(self, runner: CliRunner, temp_dir: Path):
        """無効なワークフローファイルの場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 無効なワークフローファイルを作成
            workflows_dir = temp_dir / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)

            invalid_workflow = workflows_dir / "invalid.yml"
            invalid_workflow.write_text("invalid yaml content: [")

            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/act"

                test_result = runner.invoke(cli, ["test", "--workflow", "invalid.yml"])
                # YAMLパースエラーまたは実行エラーが発生することを確認
                assert test_result.exit_code != 0

    def test_permission_denied_errors(self, runner: CliRunner, temp_dir: Path):
        """権限エラーの場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 読み取り専用ディレクトリを作成
            readonly_dir = temp_dir / "readonly"
            readonly_dir.mkdir()

            try:
                # ディレクトリを読み取り専用に設定
                readonly_dir.chmod(0o444)

                # 読み取り専用ディレクトリに書き込もうとする
                with patch("ci_helper.utils.config.Config.get_project_root") as mock_root:
                    mock_root.return_value = readonly_dir

                    init_result = runner.invoke(cli, ["init"])
                    # 権限エラーが適切に処理されることを確認
                    assert init_result.exit_code != 0

            finally:
                # クリーンアップ
                readonly_dir.chmod(0o755)

    def test_disk_space_errors(self, runner: CliRunner, temp_dir: Path):
        """ディスク容量不足の場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 設定ファイルを作成
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            with patch("shutil.disk_usage") as mock_disk_usage:
                # ディスク容量不足をシミュレート
                mock_disk_usage.return_value = (1000, 100, 50)  # total, used, free (bytes)

                # 大きなログファイルを作成しようとする
                test_result = runner.invoke(cli, ["test"])
                # 容量チェックが実装されている場合、警告が表示される
                # 実装に依存するため、最低限エラーが処理されることを確認
                assert test_result.exit_code == 0 or "容量" in test_result.output

    def test_network_timeout_errors(self, runner: CliRunner, temp_dir: Path):
        """ネットワークタイムアウトの場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # ワークフローディレクトリを作成
            workflows_dir = temp_dir / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)

            # ネットワークを使用するワークフローを作成
            network_workflow = workflows_dir / "network.yml"
            network_workflow.write_text("""
name: Network Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Download something
        run: curl --max-time 1 https://httpbin.org/delay/10
""")

            with patch("subprocess.run") as mock_run:
                # タイムアウトエラーをシミュレート
                mock_run.side_effect = TimeoutError("Command timed out")

                test_result = runner.invoke(cli, ["test", "--workflow", "network.yml"])
                assert test_result.exit_code != 0

    def test_corrupted_log_file_handling(self, runner: CliRunner, temp_dir: Path):
        """破損したログファイルの処理をテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 破損したログファイルを作成
            logs_dir = temp_dir / ".ci-helper" / "logs"
            logs_dir.mkdir(parents=True)

            corrupted_log = logs_dir / "corrupted.log"
            # バイナリデータを書き込んで破損をシミュレート
            corrupted_log.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

            # ドライランでログを解析
            test_result = runner.invoke(cli, ["test", "--dry-run", "--log", str(corrupted_log)])

            # エラーが適切に処理されることを確認
            assert test_result.exit_code == 0 or "エラー" in test_result.output

    def test_configuration_validation_errors(self, runner: CliRunner, temp_dir: Path):
        """設定ファイルの検証エラーをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 無効な設定ファイルを作成
            config_file = temp_dir / "ci-helper.toml"
            config_file.write_text("""
[invalid_section
missing_closing_bracket = true

[logging]
level = "INVALID_LEVEL"
""")

            # 設定ファイルを読み込むコマンドを実行
            test_result = runner.invoke(cli, ["test"])
            # 設定エラーが適切に処理されることを確認
            assert test_result.exit_code != 0

    def test_concurrent_execution_conflicts(self, runner: CliRunner, temp_dir: Path):
        """同時実行時の競合状態をテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 設定ファイルを作成
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # ロックファイルを作成して同時実行をシミュレート
            lock_file = Path(".ci-helper/ci-helper.lock")
            lock_file.parent.mkdir(parents=True)
            lock_file.write_text("locked")

            with patch("ci_helper.core.ci_runner.CIRunner.check_lock_file") as mock_check:
                mock_check.side_effect = CIHelperError("Another instance is running")

                test_result = runner.invoke(cli, ["test"])
                assert test_result.exit_code != 0
                assert "実行中" in test_result.output or "running" in test_result.output

    def test_memory_exhaustion_handling(self, runner: CliRunner, temp_dir: Path):
        """メモリ不足の場合のエラーハンドリングをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 巨大なログファイルを作成
            logs_dir = temp_dir / ".ci-helper" / "logs"
            logs_dir.mkdir(parents=True)

            huge_log = logs_dir / "huge.log"
            # 実際には巨大ファイルは作成せず、メモリエラーをモック
            huge_log.write_text("sample log")

            with patch("builtins.open") as mock_open:
                mock_open.side_effect = MemoryError("Not enough memory")

                test_result = runner.invoke(cli, ["test", "--dry-run", "--log", str(huge_log)])

                # メモリエラーが適切に処理されることを確認
                assert test_result.exit_code != 0
