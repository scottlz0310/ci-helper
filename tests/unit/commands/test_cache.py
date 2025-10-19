"""
cacheコマンドのテスト

Dockerイメージキャッシュ管理機能をテストします。
"""

import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from src.ci_helper.commands.cache import cache


class TestCacheCommand:
    """cacheコマンドのテストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール"""
        return Mock()

    def test_cache_help(self, runner):
        """ヘルプ表示のテスト"""
        result = runner.invoke(cache, ["--help"])
        assert result.exit_code == 0
        assert "Dockerイメージのキャッシュ管理" in result.output
        assert "--pull" in result.output
        assert "--list" in result.output
        assert "--clean" in result.output

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._show_cache_status")
    def test_cache_default_behavior(self, mock_show_status, mock_check_docker, runner):
        """デフォルト動作（キャッシュ状況表示）のテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, [])

        assert result.exit_code == 0
        mock_check_docker.assert_called_once()
        mock_show_status.assert_called_once()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    def test_cache_docker_unavailable(self, mock_check_docker, runner):
        """Docker利用不可時のテスト"""
        mock_check_docker.return_value = False

        result = runner.invoke(cache, ["--pull"])

        assert result.exit_code == 1
        mock_check_docker.assert_called_once()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._pull_images")
    def test_cache_pull_default_images(self, mock_pull_images, mock_check_docker, runner):
        """デフォルトイメージプルのテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, ["--pull"])

        assert result.exit_code == 0
        mock_check_docker.assert_called_once()
        mock_pull_images.assert_called_once()

        # デフォルトイメージが渡されることを確認
        call_args = mock_pull_images.call_args[0][0]
        assert len(call_args) > 0
        assert "ghcr.io/catthehacker/ubuntu:act-latest" in call_args

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._pull_images")
    def test_cache_pull_specific_images(self, mock_pull_images, mock_check_docker, runner):
        """特定イメージプルのテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, ["--pull", "--image", "ubuntu:20.04", "--image", "alpine:latest"])

        assert result.exit_code == 0
        mock_pull_images.assert_called_once()

        # 指定されたイメージが渡されることを確認
        call_args = mock_pull_images.call_args[0][0]
        assert "ubuntu:20.04" in call_args
        assert "alpine:latest" in call_args

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._list_cached_images")
    def test_cache_list_images(self, mock_list_images, mock_check_docker, runner):
        """イメージ一覧表示のテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, ["--list"])

        assert result.exit_code == 0
        mock_check_docker.assert_called_once()
        mock_list_images.assert_called_once()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._clean_unused_images")
    def test_cache_clean_images(self, mock_clean_images, mock_check_docker, runner):
        """未使用イメージ削除のテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, ["--clean"])

        assert result.exit_code == 0
        mock_check_docker.assert_called_once()
        mock_clean_images.assert_called_once()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._pull_images")
    def test_cache_pull_with_timeout(self, mock_pull_images, mock_check_docker, runner):
        """タイムアウト指定でのプルテスト"""
        mock_check_docker.return_value = True

        result = runner.invoke(cache, ["--pull", "--timeout", "3600"])

        assert result.exit_code == 0
        mock_pull_images.assert_called_once()

        # タイムアウト値が渡されることを確認
        call_args = mock_pull_images.call_args
        assert call_args[1]["timeout"] == 3600


class TestCacheHelperFunctions:
    """cacheヘルパー関数のテスト"""

    @patch("subprocess.run")
    def test_check_docker_available_success(self, mock_subprocess_run):
        """Docker利用可能チェック成功のテスト"""
        from src.ci_helper.commands.cache import _check_docker_available

        # subprocess.runが成功を返すように設定
        mock_subprocess_run.return_value = Mock(returncode=0)

        result = _check_docker_available()

        assert result is True
        mock_subprocess_run.assert_called_once_with(["docker", "--version"], capture_output=True, text=True, timeout=10)

    @patch("subprocess.run")
    def test_check_docker_available_failure(self, mock_subprocess_run):
        """Docker利用不可チェックのテスト"""
        from src.ci_helper.commands.cache import _check_docker_available

        # subprocess.runが失敗を返すように設定
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker")

        result = _check_docker_available()

        assert result is False

    @patch("subprocess.run")
    def test_check_docker_available_timeout(self, mock_subprocess_run):
        """Dockerチェックタイムアウトのテスト"""
        from src.ci_helper.commands.cache import _check_docker_available

        # subprocess.runがタイムアウトするように設定
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        result = _check_docker_available()

        assert result is False

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_pull_images_success(self, mock_console, mock_subprocess_run):
        """イメージプル成功のテスト"""
        from src.ci_helper.commands.cache import _pull_images

        # subprocess.runが成功を返すように設定
        mock_subprocess_run.return_value = Mock(returncode=0)

        images = ["ubuntu:20.04", "alpine:latest"]
        _pull_images(images, timeout=1800)

        # 各イメージに対してdocker pullが呼ばれることを確認
        assert mock_subprocess_run.call_count == len(images)

        # 最初の呼び出しを確認
        first_call = mock_subprocess_run.call_args_list[0]
        assert first_call[0][0] == ["docker", "pull", "ubuntu:20.04"]

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_pull_images_failure(self, mock_console, mock_subprocess_run):
        """イメージプル失敗のテスト"""
        from src.ci_helper.commands.cache import _pull_images

        # subprocess.runが失敗を返すように設定
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker pull")

        images = ["nonexistent:image"]

        # 例外が発生しないことを確認（エラーは内部で処理される）
        _pull_images(images, timeout=1800)

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_pull_images_timeout(self, mock_console, mock_subprocess_run):
        """イメージプルタイムアウトのテスト"""
        from src.ci_helper.commands.cache import _pull_images

        # subprocess.runがタイムアウトするように設定
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired("docker pull", 1800)

        images = ["large:image"]

        # 例外が発生しないことを確認（タイムアウトは内部で処理される）
        _pull_images(images, timeout=1800)

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_list_cached_images_success(self, mock_console, mock_subprocess_run):
        """キャッシュイメージ一覧表示成功のテスト"""
        from src.ci_helper.commands.cache import _list_cached_images

        # docker imagesコマンドの出力をモック
        mock_output = """REPOSITORY                    TAG       IMAGE ID       CREATED        SIZE
ubuntu                        20.04     1234567890ab   2 weeks ago    72.8MB
alpine                        latest    abcdef123456   3 weeks ago    5.61MB"""

        mock_subprocess_run.return_value = Mock(returncode=0, stdout=mock_output)

        _list_cached_images()

        mock_subprocess_run.assert_called_once_with(
            [
                "docker",
                "images",
                "--format",
                "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.CreatedSince}}\\t{{.Size}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_list_cached_images_failure(self, mock_console, mock_subprocess_run):
        """キャッシュイメージ一覧表示失敗のテスト"""
        from src.ci_helper.commands.cache import _list_cached_images

        # subprocess.runが失敗を返すように設定
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker images")

        # 例外が発生しないことを確認（エラーは内部で処理される）
        _list_cached_images()

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_clean_unused_images_success(self, mock_console, mock_subprocess_run):
        """未使用イメージ削除成功のテスト"""
        from src.ci_helper.commands.cache import _clean_unused_images

        # docker system pruneコマンドの出力をモック
        mock_output = "Total reclaimed space: 1.2GB"
        mock_subprocess_run.return_value = Mock(returncode=0, stdout=mock_output)

        _clean_unused_images()

        mock_subprocess_run.assert_called_once_with(
            ["docker", "system", "prune", "-f", "--filter", "until=24h"], capture_output=True, text=True, timeout=300
        )

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_clean_unused_images_failure(self, mock_console, mock_subprocess_run):
        """未使用イメージ削除失敗のテスト"""
        from src.ci_helper.commands.cache import _clean_unused_images

        # subprocess.runが失敗を返すように設定
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker system prune")

        # 例外が発生しないことを確認（エラーは内部で処理される）
        _clean_unused_images()

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_show_cache_status_success(self, mock_console, mock_subprocess_run):
        """キャッシュ状況表示成功のテスト"""
        from src.ci_helper.commands.cache import _show_cache_status

        # docker system dfコマンドの出力をモック
        mock_output = """TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          10        5         2.5GB     1.2GB (48%)
Containers      3         2         100MB     50MB (50%)
Local Volumes   2         1         500MB     250MB (50%)"""

        mock_subprocess_run.return_value = Mock(returncode=0, stdout=mock_output)

        _show_cache_status()

        mock_subprocess_run.assert_called_once_with(
            ["docker", "system", "df"], capture_output=True, text=True, timeout=30
        )

    @patch("subprocess.run")
    @patch("src.ci_helper.commands.cache.console")
    def test_show_cache_status_failure(self, mock_console, mock_subprocess_run):
        """キャッシュ状況表示失敗のテスト"""
        from src.ci_helper.commands.cache import _show_cache_status

        # subprocess.runが失敗を返すように設定
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker system df")

        # 例外が発生しないことを確認（エラーは内部で処理される）
        _show_cache_status()


class TestCacheIntegration:
    """cacheコマンド統合テスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    @patch("src.ci_helper.commands.cache._pull_images")
    @patch("src.ci_helper.commands.cache._list_cached_images")
    @patch("src.ci_helper.commands.cache._clean_unused_images")
    def test_cache_multiple_operations(self, mock_clean, mock_list, mock_pull, mock_check_docker, runner):
        """複数操作の統合テスト"""
        mock_check_docker.return_value = True

        # 複数のオプションを同時に指定
        result = runner.invoke(cache, ["--pull", "--list", "--clean"])

        assert result.exit_code == 0
        mock_check_docker.assert_called_once()
        mock_pull.assert_called_once()
        mock_list.assert_called_once()
        mock_clean.assert_called_once()

    @patch("src.ci_helper.commands.cache._check_docker_available")
    def test_cache_error_handling(self, mock_check_docker, runner):
        """エラーハンドリングの統合テスト"""
        # Dockerが利用不可の場合
        mock_check_docker.return_value = False

        result = runner.invoke(cache, ["--pull"])

        # エラー終了することを確認
        assert result.exit_code == 1
