"""
CLI コマンドの基本的なユニットテスト

各コマンドのヘルプ表示とオプション処理の基本的なテストを提供します。
"""

from click.testing import CliRunner

from ci_helper.cli import cli
from ci_helper.commands.clean import clean
from ci_helper.commands.doctor import doctor
from ci_helper.commands.init import init, setup
from ci_helper.commands.logs import logs
from ci_helper.commands.secrets import secrets
from ci_helper.commands.test import test


class TestCLIBasicFunctionality:
    """CLI の基本機能テスト"""

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

    def test_cli_verbose_option_help(self):
        """--verbose オプションのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])

        assert result.exit_code == 0
        assert "--verbose" in result.output


class TestInitCommandBasic:
    """init コマンドの基本テスト"""

    def test_init_help_display(self):
        """init コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(init, ["--help"])

        assert result.exit_code == 0
        assert "プロジェクトの初期化" in result.output
        assert "--force" in result.output

    def test_init_force_option_help(self):
        """init コマンドの --force オプションヘルプテスト"""
        runner = CliRunner()
        result = runner.invoke(init, ["--help"])

        assert result.exit_code == 0
        assert "既存の設定ファイルを強制的に上書きします" in result.output


class TestSetupCommandBasic:
    """setup コマンドの基本テスト"""

    def test_setup_help_display(self):
        """setup コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(setup, ["--help"])

        assert result.exit_code == 0
        assert "テンプレートから実際の設定ファイルを作成します" in result.output
        assert "--force" in result.output


class TestDoctorCommandBasic:
    """doctor コマンドの基本テスト"""

    def test_doctor_help_display(self):
        """doctor コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--help"])

        assert result.exit_code == 0
        assert "環境依存関係をチェックします" in result.output
        assert "--verbose" in result.output
        assert "--guide" in result.output

    def test_doctor_guide_option_choices(self):
        """doctor コマンドの --guide オプション選択肢テスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--help"])

        assert result.exit_code == 0
        assert "act" in result.output
        assert "docker" in result.output
        assert "workflows" in result.output


class TestTestCommandBasic:
    """test コマンドの基本テスト"""

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

    def test_test_format_option_choices(self):
        """test コマンドの --format オプション選択肢テスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--help"])

        assert result.exit_code == 0
        assert "markdown" in result.output
        assert "json" in result.output
        assert "table" in result.output


class TestLogsCommandBasic:
    """logs コマンドの基本テスト"""

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

    def test_logs_format_option_choices(self):
        """logs コマンドの --format オプション選択肢テスト"""
        runner = CliRunner()
        result = runner.invoke(logs, ["--help"])

        assert result.exit_code == 0
        assert "table" in result.output
        assert "markdown" in result.output
        assert "json" in result.output


class TestSecretsCommandBasic:
    """secrets コマンドの基本テスト"""

    def test_secrets_help_display(self):
        """secrets コマンドのヘルプ表示テスト"""
        runner = CliRunner()
        result = runner.invoke(secrets, ["--help"])

        assert result.exit_code == 0
        assert "シークレット管理と検証" in result.output


class TestCleanCommandBasic:
    """clean コマンドの基本テスト"""

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


class TestOptionValidation:
    """オプション検証のテスト"""

    def test_invalid_format_option_test_command(self):
        """test コマンドの無効なフォーマットオプションテスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--format", "invalid"])

        assert result.exit_code == 2  # Click の引数エラー
        assert "Invalid value" in result.output

    def test_invalid_format_option_logs_command(self):
        """logs コマンドの無効なフォーマットオプションテスト"""
        runner = CliRunner()
        result = runner.invoke(logs, ["--diff", "test.log", "--format", "invalid"])

        assert result.exit_code == 2  # Click の引数エラー
        assert "Invalid value" in result.output

    def test_invalid_guide_option_doctor_command(self):
        """doctor コマンドの無効なガイドオプションテスト"""
        runner = CliRunner()
        result = runner.invoke(doctor, ["--guide", "invalid"])

        assert result.exit_code == 2  # Click の引数エラー
        assert "Invalid value" in result.output

    def test_multiple_workflow_options(self):
        """複数の --workflow オプションが受け入れられることのテスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--workflow", "test1.yml", "--workflow", "test2.yml", "--help"])

        # ヘルプが表示されることで、オプションが正しく解析されることを確認
        assert result.exit_code == 0

    def test_boolean_flag_combinations(self):
        """ブール値フラグの組み合わせテスト"""
        runner = CliRunner()

        # --save と --no-save は相互排他的
        result = runner.invoke(test, ["--save", "--no-save", "--help"])
        assert result.exit_code == 0

        # --sanitize と --no-sanitize は相互排他的
        result = runner.invoke(test, ["--sanitize", "--no-sanitize", "--help"])
        assert result.exit_code == 0


class TestCommandStructure:
    """コマンド構造のテスト"""

    def test_all_commands_registered(self):
        """全コマンドが CLI に登録されていることのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0

        # 各コマンドが表示されることを確認
        expected_commands = ["init", "setup", "doctor", "test", "logs", "secrets", "clean"]
        for command in expected_commands:
            assert command in result.output

    def test_command_descriptions_present(self):
        """各コマンドに説明が含まれていることのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0

        # 各コマンドの説明が含まれることを確認
        assert "プロジェクトの初期化" in result.output
        assert "環境依存関係をチェック" in result.output
        assert "CI/CDワークフローをローカルで実行" in result.output
        assert "実行ログを管理・表示" in result.output
        assert "シークレット管理と検証" in result.output
        assert "キャッシュとログをクリーンアップ" in result.output

    def test_global_options_available(self):
        """グローバルオプションが利用可能であることのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--verbose" in result.output
        assert "--config-file" in result.output
        assert "--version" in result.output


class TestCommandExamples:
    """コマンド使用例のテスト"""

    def test_cli_usage_examples_in_help(self):
        """CLI ヘルプに使用例が含まれることのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "使用例:" in result.output
        assert "ci-run init" in result.output
        assert "ci-run doctor" in result.output
        assert "ci-run test" in result.output

    def test_test_command_usage_examples(self):
        """test コマンドのヘルプに使用例が含まれることのテスト"""
        runner = CliRunner()
        result = runner.invoke(test, ["--help"])

        assert result.exit_code == 0
        assert "使用例:" in result.output
        assert "ci-run test" in result.output
        assert "--verbose" in result.output
        assert "--dry-run" in result.output

    def test_logs_command_usage_examples(self):
        """logs コマンドのヘルプに使用例が含まれることのテスト"""
        runner = CliRunner()
        result = runner.invoke(logs, ["--help"])

        assert result.exit_code == 0
        assert "使用例:" in result.output
        assert "ci-run logs" in result.output


class TestErrorHandling:
    """基本的なエラーハンドリングのテスト"""

    def test_unknown_command(self):
        """存在しないコマンドのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent"])

        assert result.exit_code == 2
        assert "No such command" in result.output

    def test_unknown_option(self):
        """存在しないオプションのテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["--nonexistent"])

        assert result.exit_code == 2
        assert "No such option" in result.output

    def test_missing_required_argument(self):
        """必須引数が不足している場合のテスト"""
        runner = CliRunner()
        result = runner.invoke(logs, ["--show-content"])  # ファイル名が必要

        assert result.exit_code == 2
        assert "Missing argument" in result.output or "requires an argument" in result.output


class TestHelpConsistency:
    """ヘルプ表示の一貫性テスト"""

    def test_all_commands_have_help(self):
        """全コマンドにヘルプが定義されていることのテスト"""
        commands = [init, setup, doctor, test, logs, secrets, clean]

        runner = CliRunner()
        for command in commands:
            result = runner.invoke(command, ["--help"])
            assert result.exit_code == 0
            assert len(result.output) > 0

    def test_help_format_consistency(self):
        """ヘルプ形式の一貫性テスト"""
        commands = [init, setup, doctor, test, logs, secrets, clean]

        runner = CliRunner()
        for command in commands:
            result = runner.invoke(command, ["--help"])
            assert result.exit_code == 0
            # 基本的なヘルプ構造が含まれることを確認
            assert "Usage:" in result.output
            assert "Options:" in result.output
