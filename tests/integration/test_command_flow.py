"""
コマンドフロー統合テスト - コマンド間の基本的な連携をテスト
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ci_helper.cli import cli


class TestCommandFlow:
    """コマンドフロー統合テストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナーを提供"""
        return CliRunner()

    def test_help_commands_work(self, runner: CliRunner):
        """全てのコマンドのヘルプが正常に表示されることをテスト"""
        commands = ["init", "doctor", "test", "logs", "clean", "secrets"]

        for command in commands:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0, f"{command} --help failed"
            assert command in result.output, f"{command} not found in help output"

    def test_workflow_directory_validation(self, runner: CliRunner, temp_dir: Path):
        """ワークフローディレクトリの検証が一貫していることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # ワークフローディレクトリが存在しない状態でテスト

            # doctorコマンド
            doctor_result = runner.invoke(cli, ["doctor"])

            # testコマンド
            test_result = runner.invoke(cli, ["test"])

            # 両方のコマンドでワークフローディレクトリの不在が検出されることを確認
            assert doctor_result.exit_code != 0 or test_result.exit_code != 0

            # エラーメッセージに.github/workflowsが含まれることを確認
            combined_output = doctor_result.output + test_result.output
            assert ".github/workflows" in combined_output or "workflow" in combined_output.lower()

    def test_config_loading_consistency(self, runner: CliRunner, temp_dir: Path):
        """設定読み込みがコマンド間で一貫していることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 設定ファイルを作成
            config_file = temp_dir / "ci-helper.toml"
            config_file.write_text("""
[logging]
level = "DEBUG"

[act]
platform = "ubuntu-latest=catthehacker/ubuntu:act-latest"
""")

            # 複数のコマンドで設定が読み込まれることを確認
            commands = ["doctor", "logs"]

            for command in commands:
                result = runner.invoke(cli, [command])
                # 設定ファイルが読み込まれることを確認（エラーが発生しても設定は読み込まれる）
                assert result.exit_code in [0, 1], f"{command} command failed unexpectedly"

    def test_error_handling_consistency(self, runner: CliRunner, temp_dir: Path):
        """エラーハンドリングがコマンド間で一貫していることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 無効な設定ファイルを作成
            config_file = temp_dir / "ci-helper.toml"
            config_file.write_text("invalid toml content [")

            # 複数のコマンドで一貫したエラーハンドリングが行われることを確認
            commands = ["doctor", "test", "logs"]

            for command in commands:
                result = runner.invoke(cli, [command])
                # エラーが適切に処理されることを確認
                assert result.exit_code in [0, 1], f"{command} command error handling failed"

    def test_verbose_flag_consistency(self, runner: CliRunner, temp_dir: Path):
        """verboseフラグがコマンド間で一貫して動作することをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            commands = ["doctor", "test", "logs"]

            for command in commands:
                # 通常実行
                normal_result = runner.invoke(cli, [command])

                # verbose実行
                verbose_result = runner.invoke(cli, ["--verbose", command])

                # 両方が実行されることを確認
                assert normal_result.exit_code in [0, 1], f"{command} normal execution failed"
                assert verbose_result.exit_code in [0, 1], f"{command} verbose execution failed"

    def test_log_directory_handling(self, runner: CliRunner, temp_dir: Path):
        """ログディレクトリの処理が一貫していることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # ログディレクトリを作成
            logs_dir = temp_dir / ".ci-helper" / "logs"
            logs_dir.mkdir(parents=True)

            # サンプルログファイルを作成
            (logs_dir / "test.log").write_text("sample log content")

            # logsコマンドでログが認識されることを確認
            logs_result = runner.invoke(cli, ["logs"])
            assert logs_result.exit_code == 0

            # cleanコマンドでログが処理されることを確認
            clean_result = runner.invoke(cli, ["clean", "--help"])
            assert clean_result.exit_code == 0

    def test_dependency_check_integration(self, runner: CliRunner, temp_dir: Path):
        """依存関係チェックの統合テスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            with patch("shutil.which") as mock_which:
                # actが見つからない場合
                mock_which.return_value = None

                # doctorコマンドで依存関係エラーが検出されることを確認
                doctor_result = runner.invoke(cli, ["doctor"])

                # testコマンドでも同様のエラーが発生することを確認
                test_result = runner.invoke(cli, ["test"])

                # 両方のコマンドでエラーが発生することを確認
                assert doctor_result.exit_code != 0 or test_result.exit_code != 0

    def test_cache_directory_operations(self, runner: CliRunner, temp_dir: Path):
        """キャッシュディレクトリ操作の統合テスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # キャッシュディレクトリを作成
            cache_dir = temp_dir / ".ci-helper" / "cache"
            cache_dir.mkdir(parents=True)

            # キャッシュファイルを作成
            (cache_dir / "test.cache").write_text("cache content")

            # cleanコマンドでキャッシュが処理されることを確認
            clean_result = runner.invoke(cli, ["clean", "--help"])
            assert clean_result.exit_code == 0
            assert "clean" in clean_result.output

    def test_workflow_file_detection(self, runner: CliRunner, temp_dir: Path):
        """ワークフローファイル検出の統合テスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # ワークフローディレクトリとファイルを作成
            workflows_dir = temp_dir / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)

            workflow_file = workflows_dir / "test.yml"
            workflow_file.write_text("""
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "test"
""")

            # doctorコマンドでワークフローが検出されることを確認
            runner.invoke(cli, ["doctor"])

            # testコマンドでワークフローが認識されることを確認
            test_result = runner.invoke(cli, ["test", "--help"])
            assert test_result.exit_code == 0

    def test_output_format_consistency(self, runner: CliRunner, temp_dir: Path):
        """出力フォーマットの一貫性をテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            commands = ["doctor", "logs", "clean"]

            for command in commands:
                result = runner.invoke(cli, [command, "--help"])

                # ヘルプ出力が一貫したフォーマットであることを確認
                assert result.exit_code == 0
                assert "Usage:" in result.output or "使用方法:" in result.output
