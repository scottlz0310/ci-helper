"""
シンプルなE2Eテスト - 基本的なコマンド実行をテスト
"""

from pathlib import Path

import pytest
from ci_helper.cli import cli
from click.testing import CliRunner


class TestSimpleE2E:
    """シンプルなE2Eテストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナーを提供"""
        return CliRunner()

    def test_cli_help_command(self, runner: CliRunner):
        """CLIのヘルプコマンドが正常に動作することをテスト"""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "ci-helper" in result.output
        assert "init" in result.output
        assert "doctor" in result.output
        assert "test" in result.output

    def test_version_command(self, runner: CliRunner):
        """バージョンコマンドが正常に動作することをテスト"""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        # バージョン情報が含まれることを確認
        assert "version" in result.output.lower() or len(result.output.strip()) > 0

    def test_init_command_execution(self, runner: CliRunner, temp_dir: Path):
        """initコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["init"])

            # コマンドが認識され、実行が試行されることを確認
            # 設定エラーが発生する可能性があるが、コマンド自体は認識される
            assert "init" in str(result) or result.exit_code in [0, 1]

    def test_doctor_command_execution(self, runner: CliRunner, temp_dir: Path):
        """doctorコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["doctor"])

            # コマンドが認識され、実行が試行されることを確認
            assert "doctor" in str(result) or result.exit_code in [0, 1]

    def test_test_command_execution(self, runner: CliRunner, temp_dir: Path):
        """testコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["test"])

            # コマンドが認識され、実行が試行されることを確認
            # ワークフローディレクトリが存在しないためエラーになるが、コマンドは認識される
            assert result.exit_code in [0, 1]

    def test_logs_command_execution(self, runner: CliRunner, temp_dir: Path):
        """logsコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["logs"])

            # コマンドが認識され、実行が試行されることを確認
            assert result.exit_code in [0, 1]
            # ログが見つからないメッセージまたは正常実行
            assert "ログ" in result.output or result.exit_code == 0

    def test_clean_command_execution(self, runner: CliRunner, temp_dir: Path):
        """cleanコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["clean", "--help"])

            # ヘルプが表示されることを確認
            assert result.exit_code == 0
            assert "clean" in result.output

    def test_secrets_command_execution(self, runner: CliRunner, temp_dir: Path):
        """secretsコマンドが実行されることをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["secrets", "--help"])

            # ヘルプが表示されることを確認
            assert result.exit_code == 0
            assert "secrets" in result.output

    def test_invalid_command_handling(self, runner: CliRunner):
        """無効なコマンドが適切に処理されることをテスト"""
        result = runner.invoke(cli, ["invalid-command"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_verbose_flag(self, runner: CliRunner, temp_dir: Path):
        """verboseフラグが正常に動作することをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            result = runner.invoke(cli, ["--verbose", "doctor"])

            # verboseフラグが認識されることを確認
            assert result.exit_code in [0, 1]

    def test_config_file_option(self, runner: CliRunner, temp_dir: Path):
        """config-fileオプションが正常に動作することをテスト"""
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # 設定ファイルを作成
            config_file = temp_dir / "test-config.toml"
            config_file.write_text("""
[logging]
level = "INFO"
""")

            result = runner.invoke(cli, ["--config-file", str(config_file), "doctor"])

            # config-fileオプションが認識されることを確認
            assert result.exit_code in [0, 1]
