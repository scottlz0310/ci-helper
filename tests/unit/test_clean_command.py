"""
clean コマンドのユニットテスト
"""

from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from ci_helper.cli import cli


class TestCleanCommand:
    """clean コマンドのテスト"""

    def test_clean_command_basic(self):
        """基本的なclean コマンド実行テスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # 設定ファイルを作成
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # テスト用ディレクトリとファイルを作成
            cache_dir = Path(".ci-helper/cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "test_cache.json").write_text('{"test": "data"}')

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean"])

            assert result.exit_code == 0

    def test_clean_command_logs_only(self):
        """ログのみクリーンアップのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--logs-only"])

            assert result.exit_code == 0

    def test_clean_command_all(self):
        """全削除のテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            ci_helper_dir = Path(".ci-helper")
            ci_helper_dir.mkdir(exist_ok=True)
            (ci_helper_dir / "test_file.txt").write_text("test content")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--all"])

            assert result.exit_code == 0

    def test_clean_command_dry_run(self):
        """ドライランのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            result = runner.invoke(cli, ["clean", "--dry-run"])

            assert result.exit_code == 0
            # ファイルが削除されていないことを確認
            assert (logs_dir / "test.log").exists()

    def test_clean_command_force(self):
        """強制実行のテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            result = runner.invoke(cli, ["clean", "--force"])

            assert result.exit_code == 0

    def test_clean_command_verbose(self):
        """詳細モードのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--verbose"])

            assert result.exit_code == 0

    def test_clean_command_user_cancellation(self):
        """ユーザーキャンセルのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            with patch("click.confirm", return_value=False):
                result = runner.invoke(cli, ["clean"])

            assert result.exit_code == 0
            # ファイルが削除されていないことを確認
            assert (logs_dir / "test.log").exists()

    def test_clean_command_with_config_error(self):
        """設定エラー時のテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # 無効な設定ファイルを作成
            Path("ci-helper.toml").write_text("invalid toml content [")

            result = runner.invoke(cli, ["clean"])

            assert result.exit_code == 1

    def test_clean_command_conflicting_options(self):
        """競合するオプションのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            result = runner.invoke(cli, ["clean", "--logs-only", "--all"])

            assert result.exit_code == 1

    def test_clean_command_empty_directories(self):
        """空ディレクトリでのクリーンアップテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # 空のディレクトリを作成
            Path(".ci-helper/logs").mkdir(parents=True, exist_ok=True)
            Path(".ci-helper/cache").mkdir(parents=True, exist_ok=True)

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean"])

            assert result.exit_code == 0

    @patch("ci_helper.core.cache_manager.CacheManager")
    def test_clean_command_with_cache_manager_error(self, mock_cache_manager):
        """CacheManager エラー時のテスト"""
        from ci_helper.core.exceptions import ExecutionError

        mock_manager_instance = Mock()
        mock_manager_instance.clear_logs.side_effect = ExecutionError("ログクリアに失敗", "権限を確認してください")
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--logs-only"])

            assert result.exit_code == 1

    @patch("ci_helper.core.cache_manager.CacheManager")
    def test_clean_command_with_permission_error(self, mock_cache_manager):
        """権限エラー時のテスト"""
        mock_manager_instance = Mock()
        mock_manager_instance.clear_cache.side_effect = PermissionError("Permission denied")
        mock_cache_manager.return_value = mock_manager_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean"])

            assert result.exit_code == 1

    def test_clean_command_help(self):
        """ヘルプ表示のテスト"""
        runner = CliRunner()
        result = runner.invoke(cli, ["clean", "--help"])

        assert result.exit_code == 0
        assert "キャッシュとログファイルをクリーンアップ" in result.output

    def test_clean_command_with_large_cache(self):
        """大きなキャッシュでのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # 大きなキャッシュファイルを作成
            cache_dir = Path(".ci-helper/cache")
            cache_dir.mkdir(parents=True, exist_ok=True)

            for i in range(10):
                (cache_dir / f"large_cache_{i}.json").write_text("x" * 10000)

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--verbose"])

            assert result.exit_code == 0

    def test_clean_command_with_nested_directories(self):
        """ネストしたディレクトリでのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            # ネストしたディレクトリ構造を作成
            nested_dir = Path(".ci-helper/cache/nested/deep")
            nested_dir.mkdir(parents=True, exist_ok=True)
            (nested_dir / "nested_cache.json").write_text('{"nested": "data"}')

            with patch("click.confirm", return_value=True):
                result = runner.invoke(cli, ["clean", "--all"])

            assert result.exit_code == 0

    def test_clean_command_dry_run_verbose(self):
        """ドライラン + 詳細モードのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            result = runner.invoke(cli, ["clean", "--dry-run", "--verbose"])

            assert result.exit_code == 0
            # ファイルが削除されていないことを確認
            assert (logs_dir / "test.log").exists()

    def test_clean_command_force_verbose(self):
        """強制実行 + 詳細モードのテスト"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("ci-helper.toml").write_text("[ci-helper]\nverbose = false")

            logs_dir = Path(".ci-helper/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "test.log").write_text("test log content")

            result = runner.invoke(cli, ["clean", "--force", "--verbose"])

            assert result.exit_code == 0
