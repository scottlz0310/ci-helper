"""
キャッシュ管理のユニットテスト
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from ci_helper.core.cache_manager import CacheManager
from ci_helper.core.exceptions import ExecutionError
from ci_helper.utils.config import Config


class TestCacheManagerInitialization:
    """キャッシュマネージャー初期化のテスト"""

    def test_cache_manager_initialization(self, temp_dir: Path):
        """キャッシュマネージャーの初期化テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        assert cache_manager.config == config
        assert cache_manager.log_dir == config.get_path("log_dir")
        assert cache_manager.cache_dir == config.get_path("cache_dir")
        assert cache_manager.reports_dir == config.get_path("reports_dir")

    def test_ensure_directories_creation(self, temp_dir: Path):
        """必要なディレクトリが作成されることのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # ディレクトリが作成されている
        assert cache_manager.log_dir.exists()
        assert cache_manager.cache_dir.exists()
        assert cache_manager.reports_dir.exists()

    def test_cache_index_file_path(self, temp_dir: Path):
        """キャッシュインデックスファイルのパス設定テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        expected_path = cache_manager.cache_dir / "cache_index.json"
        assert cache_manager.cache_index_file == expected_path


class TestCacheStatistics:
    """キャッシュ統計情報のテスト"""

    def test_get_cache_statistics_empty_directories(self, temp_dir: Path):
        """空のディレクトリの統計情報テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        stats = cache_manager.get_cache_statistics()

        assert stats["logs"]["files"] == 0
        assert stats["logs"]["size_mb"] == 0.0
        assert stats["logs"]["oldest_file"] is None
        assert stats["logs"]["newest_file"] is None

        assert stats["cache"]["files"] == 0
        assert stats["reports"]["files"] == 0

        assert stats["total"]["files"] == 0
        assert stats["total"]["size_mb"] == 0.0

    def test_get_cache_statistics_with_files(self, temp_dir: Path):
        """ファイルがある場合の統計情報テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # テストファイルを作成
        log_file1 = cache_manager.log_dir / "test1.log"
        log_file2 = cache_manager.log_dir / "test2.log"
        cache_file = cache_manager.cache_dir / "test.cache"

        log_file1.write_text("test log content 1")
        log_file2.write_text("test log content 2 with more data")
        cache_file.write_text("cache data")

        stats = cache_manager.get_cache_statistics()

        assert stats["logs"]["files"] == 2
        assert stats["logs"]["size_mb"] >= 0  # ファイルサイズは0以上
        assert stats["cache"]["files"] == 1
        assert stats["total"]["files"] == 3
        assert stats["total"]["size_mb"] >= 0  # ファイルサイズは0以上
        assert stats["total"]["oldest_file"] is not None
        assert stats["total"]["newest_file"] is not None

    def test_directory_stats_nonexistent_directory(self, temp_dir: Path):
        """存在しないディレクトリの統計情報テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 存在しないディレクトリのパス
        nonexistent_dir = temp_dir / "nonexistent"

        stats = cache_manager._get_directory_stats(nonexistent_dir)

        assert stats["files"] == 0
        assert stats["size_mb"] == 0.0
        assert stats["oldest_file"] is None
        assert stats["newest_file"] is None

    def test_directory_stats_with_subdirectories(self, temp_dir: Path):
        """サブディレクトリを含む統計情報テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # サブディレクトリとファイルを作成
        subdir = cache_manager.log_dir / "subdir"
        subdir.mkdir()

        (cache_manager.log_dir / "root_file.log").write_text("root content")
        (subdir / "sub_file.log").write_text("sub content")

        stats = cache_manager._get_directory_stats(cache_manager.log_dir)

        # サブディレクトリ内のファイルも含まれる
        assert stats["files"] == 2
        assert stats["size_mb"] >= 0  # ファイルサイズは0以上


class TestLogsOnlyCleanup:
    """ログファイルのみのクリーンアップテスト"""

    def test_cleanup_logs_only_dry_run(self, temp_dir: Path):
        """ログファイルのドライランクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いログファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_log.write_text("old log content")

        # ファイルの更新時刻を古くする
        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_logs_only(dry_run=True)

        assert result["deleted_files"] == 1
        assert result["freed_size_mb"] >= 0  # ファイルサイズは0以上
        assert len(result["files_to_delete"]) == 1
        assert str(old_log) in result["files_to_delete"]
        assert len(result["errors"]) == 0

        # ドライランなので実際には削除されない
        assert old_log.exists()

    def test_cleanup_logs_only_actual_deletion(self, temp_dir: Path):
        """ログファイルの実際の削除テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いログファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_log.write_text("old log content")

        # ファイルの更新時刻を古くする
        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_logs_only(dry_run=False)

        assert result["deleted_files"] == 1
        assert result["freed_size_mb"] >= 0  # ファイルサイズは0以上
        assert len(result["errors"]) == 0

        # 実際に削除される
        assert not old_log.exists()

    def test_cleanup_logs_by_count_limit(self, temp_dir: Path):
        """ファイル数制限によるログクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        # 最大ファイル数を2に設定
        config._config["max_log_files"] = 2
        cache_manager = CacheManager(config)

        # 3つのログファイルを作成（時間差をつける）
        for i in range(3):
            log_file = cache_manager.log_dir / f"test_{i}.log"
            log_file.write_text(f"log content {i}")

            # 時間差をつける（新しいファイルほど新しい時刻）
            file_time = datetime.now() - timedelta(minutes=10 - i)
            os.utime(log_file, (file_time.timestamp(), file_time.timestamp()))

        result = cache_manager.cleanup_logs_only(dry_run=False)

        # 最も古いファイルが削除される
        assert result["deleted_files"] == 1
        assert not (cache_manager.log_dir / "test_0.log").exists()
        assert (cache_manager.log_dir / "test_1.log").exists()
        assert (cache_manager.log_dir / "test_2.log").exists()

    def test_cleanup_logs_by_size_limit(self, temp_dir: Path):
        """サイズ制限によるログクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        # 最大サイズを非常に小さく設定（1MB未満）
        config._config["max_log_size_mb"] = 0.001  # 1KB程度
        cache_manager = CacheManager(config)

        # 大きなログファイルを作成
        large_log = cache_manager.log_dir / "large.log"
        large_log.write_text("x" * 2000)  # 2KB

        small_log = cache_manager.log_dir / "small.log"
        small_log.write_text("small")

        # 大きなファイルを古くする
        old_time = datetime.now() - timedelta(minutes=10)
        os.utime(large_log, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_logs_only(dry_run=False)

        # 大きなファイルが削除される
        assert result["deleted_files"] == 1
        assert not large_log.exists()
        assert small_log.exists()

    def test_cleanup_logs_no_files_to_delete(self, temp_dir: Path):
        """削除対象がない場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 新しいログファイルを作成
        new_log = cache_manager.log_dir / "new.log"
        new_log.write_text("new log content")

        result = cache_manager.cleanup_logs_only(dry_run=False)

        assert result["deleted_files"] == 0
        assert result["freed_size_mb"] == 0.0
        assert len(result["errors"]) == 0
        assert new_log.exists()


class TestCacheOnlyCleanup:
    """キャッシュファイルのみのクリーンアップテスト"""

    def test_cleanup_cache_only_by_age(self, temp_dir: Path):
        """年齢によるキャッシュクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いキャッシュファイルを作成
        old_cache = cache_manager.cache_dir / "old.cache"
        old_cache.write_text("old cache content")

        # ファイルの更新時刻を古くする
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_cache, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_cache_only(dry_run=False)

        assert result["deleted_files"] == 1
        assert not old_cache.exists()

    def test_cleanup_cache_excludes_index_file(self, temp_dir: Path):
        """キャッシュインデックスファイルが除外されることのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # キャッシュインデックスファイルを作成
        cache_manager.cache_index_file.write_text('{"test": "data"}')

        # 古いキャッシュファイルを作成
        old_cache = cache_manager.cache_dir / "old.cache"
        old_cache.write_text("old cache content")

        # 両方のファイルを古くする
        old_time = datetime.now() - timedelta(days=10)
        os.utime(cache_manager.cache_index_file, (old_time.timestamp(), old_time.timestamp()))
        os.utime(old_cache, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_cache_only(dry_run=False)

        # インデックスファイルは削除されない
        assert cache_manager.cache_index_file.exists()
        assert not old_cache.exists()
        assert result["deleted_files"] == 1

    def test_cleanup_cache_by_size_limit(self, temp_dir: Path):
        """サイズ制限によるキャッシュクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        # 最大キャッシュサイズを小さく設定
        config._config["max_cache_size_mb"] = 0.001  # 1KB程度
        cache_manager = CacheManager(config)

        # 大きなキャッシュファイルを作成
        large_cache = cache_manager.cache_dir / "large.cache"
        large_cache.write_text("x" * 2000)  # 2KB

        result = cache_manager.cleanup_cache_only(dry_run=False)

        assert result["deleted_files"] == 1
        assert not large_cache.exists()


class TestCleanupAll:
    """全体クリーンアップのテスト"""

    def test_cleanup_all_combines_results(self, temp_dir: Path):
        """全体クリーンアップが各ディレクトリの結果を統合することのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 各ディレクトリに古いファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_cache = cache_manager.cache_dir / "old.cache"
        old_report = cache_manager.reports_dir / "old.html"

        old_log.write_text("old log")
        old_cache.write_text("old cache")
        old_report.write_text("old report")

        # すべてのファイルを古くする
        old_time = datetime.now() - timedelta(days=35)
        for file_path in [old_log, old_cache, old_report]:
            os.utime(file_path, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_all(dry_run=False)

        # 各ディレクトリの結果が含まれる
        assert "logs" in result
        assert "cache" in result
        assert "reports" in result
        assert "total" in result

        # 合計結果が正しい
        assert result["total"]["deleted_files"] == 3
        assert result["total"]["freed_size_mb"] >= 0  # ファイルサイズは0以上
        assert result["total"]["errors"] == 0

        # ファイルが削除されている
        assert not old_log.exists()
        assert not old_cache.exists()
        assert not old_report.exists()

    def test_cleanup_all_dry_run(self, temp_dir: Path):
        """全体クリーンアップのドライランテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_log.write_text("old log")

        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.cleanup_all(dry_run=True)

        # ドライランなので削除されない
        assert old_log.exists()
        assert result["total"]["deleted_files"] == 1
        assert len(result["logs"]["files_to_delete"]) == 1


class TestAutoCleanup:
    """自動クリーンアップのテスト"""

    def test_auto_cleanup_disabled(self, temp_dir: Path):
        """自動クリーンアップが無効な場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        config._config["auto_cleanup_enabled"] = False
        cache_manager = CacheManager(config)

        result = cache_manager.auto_cleanup()

        assert result["skipped"] is True
        assert "自動クリーンアップが無効です" in result["reason"]

    def test_auto_cleanup_too_soon(self, temp_dir: Path):
        """自動クリーンアップの間隔が短すぎる場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        config._config["cleanup_interval_hours"] = 24
        cache_manager = CacheManager(config)

        # 最近のクリーンアップ時刻を設定
        recent_time = datetime.now() - timedelta(hours=1)
        cache_data = {"last_cleanup": recent_time.isoformat()}

        cache_manager.cache_index_file.write_text(json.dumps(cache_data))

        result = cache_manager.auto_cleanup()

        assert result["skipped"] is True
        assert "次回クリーンアップ予定" in result["reason"]

    def test_auto_cleanup_executes(self, temp_dir: Path):
        """自動クリーンアップが実行される場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        config._config["cleanup_interval_hours"] = 24
        cache_manager = CacheManager(config)

        # 古いクリーンアップ時刻を設定
        old_time = datetime.now() - timedelta(hours=25)
        cache_data = {"last_cleanup": old_time.isoformat()}

        cache_manager.cache_index_file.write_text(json.dumps(cache_data))

        # 古いファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_log.write_text("old log")

        file_old_time = datetime.now() - timedelta(days=35)
        os.utime(old_log, (file_old_time.timestamp(), file_old_time.timestamp()))

        result = cache_manager.auto_cleanup()

        assert "skipped" not in result
        assert result["auto_cleanup"] is True
        assert result["total"]["deleted_files"] >= 0

        # 最後のクリーンアップ時刻が更新される
        updated_data = json.loads(cache_manager.cache_index_file.read_text())
        assert "last_cleanup" in updated_data

    def test_auto_cleanup_no_previous_cleanup(self, temp_dir: Path):
        """過去のクリーンアップ履歴がない場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いファイルを作成
        old_log = cache_manager.log_dir / "old.log"
        old_log.write_text("old log")

        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))

        result = cache_manager.auto_cleanup()

        # 初回実行なので実行される
        assert "skipped" not in result
        assert result["auto_cleanup"] is True


class TestLastCleanupTimeManagement:
    """最後のクリーンアップ時刻管理のテスト"""

    def test_get_last_cleanup_time_no_file(self, temp_dir: Path):
        """キャッシュインデックスファイルがない場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        last_cleanup = cache_manager._get_last_cleanup_time()
        assert last_cleanup is None

    def test_get_last_cleanup_time_valid_file(self, temp_dir: Path):
        """有効なキャッシュインデックスファイルがある場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 有効なキャッシュデータを作成
        test_time = datetime.now() - timedelta(hours=5)
        cache_data = {"last_cleanup": test_time.isoformat()}

        cache_manager.cache_index_file.write_text(json.dumps(cache_data))

        last_cleanup = cache_manager._get_last_cleanup_time()
        assert last_cleanup is not None
        assert abs((last_cleanup - test_time).total_seconds()) < 1

    def test_get_last_cleanup_time_invalid_file(self, temp_dir: Path):
        """無効なキャッシュインデックスファイルがある場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 無効なJSONファイルを作成
        cache_manager.cache_index_file.write_text("invalid json")

        last_cleanup = cache_manager._get_last_cleanup_time()
        assert last_cleanup is None

    def test_update_last_cleanup_time_new_file(self, temp_dir: Path):
        """新しいキャッシュインデックスファイルの作成テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        cache_manager._update_last_cleanup_time()

        assert cache_manager.cache_index_file.exists()

        data = json.loads(cache_manager.cache_index_file.read_text())
        assert "last_cleanup" in data

        # 時刻が現在時刻に近い
        last_cleanup = datetime.fromisoformat(data["last_cleanup"])
        assert abs((datetime.now() - last_cleanup).total_seconds()) < 5

    def test_update_last_cleanup_time_existing_file(self, temp_dir: Path):
        """既存のキャッシュインデックスファイルの更新テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 既存データを作成
        existing_data = {"other_key": "other_value"}
        cache_manager.cache_index_file.write_text(json.dumps(existing_data))

        cache_manager._update_last_cleanup_time()

        data = json.loads(cache_manager.cache_index_file.read_text())
        assert "last_cleanup" in data
        assert "other_key" in data  # 既存データが保持される
        assert data["other_key"] == "other_value"


class TestResetAllCache:
    """全キャッシュリセットのテスト"""

    def test_reset_all_cache_without_confirmation(self, temp_dir: Path):
        """確認なしでのキャッシュリセットテスト（エラー）"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        with pytest.raises(ExecutionError) as exc_info:
            cache_manager.reset_all_cache(confirm=False)

        assert "キャッシュの完全リセットには確認が必要です" in str(exc_info.value)

    def test_reset_all_cache_with_confirmation(self, temp_dir: Path):
        """確認ありでのキャッシュリセットテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # テストファイルを作成
        test_log = cache_manager.log_dir / "test.log"
        test_cache = cache_manager.cache_dir / "test.cache"
        test_report = cache_manager.reports_dir / "test.html"

        test_log.write_text("test log")
        test_cache.write_text("test cache")
        test_report.write_text("test report")

        result = cache_manager.reset_all_cache(confirm=True)

        # ディレクトリは存在するがファイルは削除される
        assert cache_manager.log_dir.exists()
        assert cache_manager.cache_dir.exists()
        assert cache_manager.reports_dir.exists()

        assert not test_log.exists()
        assert not test_cache.exists()
        assert not test_report.exists()

        # 結果が正しい
        assert "logs" in result["deleted_directories"]
        assert "cache" in result["deleted_directories"]
        assert "reports" in result["deleted_directories"]
        assert result["total_freed_mb"] >= 0  # ファイルサイズは0以上
        assert len(result["errors"]) == 0

    def test_reset_all_cache_with_errors(self, temp_dir: Path):
        """キャッシュリセット時のエラーハンドリングテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 削除できないディレクトリを模擬
        with patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            result = cache_manager.reset_all_cache(confirm=True)

        # エラーが記録される
        assert len(result["errors"]) > 0
        assert any("Permission denied" in error for error in result["errors"])


class TestCleanupRecommendations:
    """クリーンアップ推奨事項のテスト"""

    def test_get_cleanup_recommendations_no_issues(self, temp_dir: Path):
        """問題がない場合の推奨事項テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        recommendations = cache_manager.get_cleanup_recommendations()

        assert len(recommendations["recommendations"]) == 0
        assert recommendations["total_size_mb"] == 0.0
        assert recommendations["auto_cleanup_enabled"] is True

    def test_get_cleanup_recommendations_log_size_exceeded(self, temp_dir: Path):
        """ログサイズ超過時の推奨事項テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 大きなログファイルを作成
        large_log = cache_manager.log_dir / "large.log"
        large_log.write_text("x" * 1024 * 1024 * 2)  # 2MB

        # 制限を1MBに設定
        config._config["max_log_size_mb"] = 1

        recommendations = cache_manager.get_cleanup_recommendations()

        assert len(recommendations["recommendations"]) > 0

        log_recommendation = next((r for r in recommendations["recommendations"] if r["type"] == "logs"), None)
        assert log_recommendation is not None
        assert log_recommendation["priority"] == "high"
        assert "制限サイズを超過" in log_recommendation["message"]

    def test_get_cleanup_recommendations_too_many_log_files(self, temp_dir: Path):
        """ログファイル数過多時の推奨事項テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        config._config["max_log_files"] = 2
        cache_manager = CacheManager(config)

        # 多数のログファイルを作成
        for i in range(5):
            log_file = cache_manager.log_dir / f"test_{i}.log"
            log_file.write_text(f"log {i}")

        recommendations = cache_manager.get_cleanup_recommendations()

        log_recommendation = next((r for r in recommendations["recommendations"] if r["type"] == "logs"), None)
        assert log_recommendation is not None
        assert log_recommendation["priority"] == "medium"
        assert "ファイル数が多すぎます" in log_recommendation["message"]

    def test_get_cleanup_recommendations_cache_size_exceeded(self, temp_dir: Path):
        """キャッシュサイズ超過時の推奨事項テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 大きなキャッシュファイルを作成
        large_cache = cache_manager.cache_dir / "large.cache"
        large_cache.write_text("x" * 1024 * 1024 * 2)  # 2MB

        # 制限を1MBに設定
        config._config["max_cache_size_mb"] = 1

        recommendations = cache_manager.get_cleanup_recommendations()

        cache_recommendation = next((r for r in recommendations["recommendations"] if r["type"] == "cache"), None)
        assert cache_recommendation is not None
        assert cache_recommendation["priority"] == "high"
        assert "キャッシュサイズが制限を超過" in cache_recommendation["message"]

    def test_get_cleanup_recommendations_old_files(self, temp_dir: Path):
        """古いファイルがある場合の推奨事項テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 古いファイルを作成
        old_file = cache_manager.log_dir / "old.log"
        old_file.write_text("old content")

        # 35日前に設定
        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        recommendations = cache_manager.get_cleanup_recommendations()

        age_recommendation = next((r for r in recommendations["recommendations"] if r["type"] == "age"), None)
        assert age_recommendation is not None
        assert age_recommendation["priority"] == "low"
        assert "古いファイルが存在します" in age_recommendation["message"]

    def test_get_next_auto_cleanup_time(self, temp_dir: Path):
        """次回自動クリーンアップ時刻の取得テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        config._config["cleanup_interval_hours"] = 24
        cache_manager = CacheManager(config)

        # 最後のクリーンアップ時刻を設定
        last_cleanup = datetime.now() - timedelta(hours=5)
        cache_data = {"last_cleanup": last_cleanup.isoformat()}
        cache_manager.cache_index_file.write_text(json.dumps(cache_data))

        next_cleanup = cache_manager._get_next_auto_cleanup_time()

        expected_next = last_cleanup + timedelta(hours=24)
        assert next_cleanup is not None
        assert abs((next_cleanup - expected_next).total_seconds()) < 1


class TestCacheIntegrityValidation:
    """キャッシュ整合性検証のテスト"""

    def test_validate_cache_integrity_all_valid(self, temp_dir: Path):
        """すべて正常な場合の整合性検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        result = cache_manager.validate_cache_integrity()

        assert result["is_valid"] is True
        assert len(result["issues"]) == 0
        assert "checked_at" in result

    def test_validate_cache_integrity_missing_directories(self, temp_dir: Path):
        """ディレクトリが存在しない場合の整合性検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # ディレクトリを削除
        shutil.rmtree(cache_manager.log_dir)

        result = cache_manager.validate_cache_integrity()

        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert any("logsディレクトリが存在しません" in issue for issue in result["issues"])

    def test_validate_cache_integrity_permission_issues(self, temp_dir: Path):
        """権限問題がある場合の整合性検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 権限チェックをモック
        with patch("os.access", return_value=False):
            result = cache_manager.validate_cache_integrity()

        assert result["is_valid"] is False
        assert any("書き込み権限がありません" in issue for issue in result["issues"])

    def test_validate_cache_integrity_corrupted_index(self, temp_dir: Path):
        """破損したキャッシュインデックスファイルの整合性検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        # 破損したJSONファイルを作成
        cache_manager.cache_index_file.write_text("invalid json content")

        result = cache_manager.validate_cache_integrity()

        assert result["is_valid"] is False
        assert any("キャッシュインデックスファイルが破損" in issue for issue in result["issues"])


class TestCleanupDirectoryMethod:
    """_cleanup_directory メソッドのテスト"""

    def test_cleanup_directory_nonexistent(self, temp_dir: Path):
        """存在しないディレクトリのクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        nonexistent_dir = temp_dir / "nonexistent"
        result = cache_manager._cleanup_directory(nonexistent_dir)

        assert result["deleted_files"] == 0
        assert result["freed_size_mb"] == 0.0
        assert len(result["errors"]) == 0
        assert len(result["files_to_delete"]) == 0

    def test_cleanup_directory_with_file_pattern(self, temp_dir: Path):
        """ファイルパターンを使用したクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        # 異なる拡張子のファイルを作成
        log_file = test_dir / "test.log"
        txt_file = test_dir / "test.txt"

        log_file.write_text("log content")
        txt_file.write_text("txt content")

        # ログファイルのみを対象とする
        result = cache_manager._cleanup_directory(
            test_dir,
            max_age_days=0,  # すべて削除対象
            file_pattern="*.log",
            dry_run=False,
        )

        assert result["deleted_files"] == 1
        assert not log_file.exists()
        assert txt_file.exists()  # .txtファイルは残る

    def test_cleanup_directory_with_exclusions(self, temp_dir: Path):
        """除外ファイルを使用したクリーンアップテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        # ファイルを作成
        file1 = test_dir / "file1.txt"
        file2 = test_dir / "exclude_me.txt"

        file1.write_text("content1")
        file2.write_text("content2")

        # file2を除外
        result = cache_manager._cleanup_directory(
            test_dir,
            max_age_days=0,  # すべて削除対象
            exclude_files=["exclude_me.txt"],
            dry_run=False,
        )

        assert result["deleted_files"] == 1
        assert not file1.exists()
        assert file2.exists()  # 除外されたファイルは残る

    def test_cleanup_directory_deletion_error(self, temp_dir: Path):
        """ファイル削除エラーのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        test_file = test_dir / "test.txt"
        test_file.write_text("content")

        # ファイル削除時にエラーを発生させる
        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            result = cache_manager._cleanup_directory(test_dir, max_age_days=0, dry_run=False)

        assert result["deleted_files"] == 0
        assert len(result["errors"]) == 1
        assert "Permission denied" in result["errors"][0]
        assert test_file.exists()  # エラーでファイルは残る

    def test_cleanup_directory_multiple_criteria(self, temp_dir: Path):
        """複数の削除条件を組み合わせたテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        cache_manager = CacheManager(config)

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        # 複数のファイルを作成（時間差をつける）
        files = []
        for i in range(5):
            file_path = test_dir / f"file_{i}.txt"
            file_path.write_text(f"content {i}")
            files.append(file_path)

            # 時間差をつける
            file_time = datetime.now() - timedelta(minutes=i * 10)
            os.utime(file_path, (file_time.timestamp(), file_time.timestamp()))

        # 年齢（30分以上古い）と件数（最大2ファイル）の両方で制限
        result = cache_manager._cleanup_directory(
            test_dir,
            max_count=2,
            max_age_days=0.02,  # 約30分
            dry_run=False,
        )

        # 古いファイルと件数超過分が削除される
        assert result["deleted_files"] >= 2

        # 最新の2ファイルは残る可能性が高い
        remaining_files = [f for f in files if f.exists()]
        assert len(remaining_files) <= 2
