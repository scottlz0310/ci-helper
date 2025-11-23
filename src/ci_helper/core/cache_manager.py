"""
キャッシュ管理システム

ログファイル、レポート、一時ファイルのキャッシュ管理と自動クリーンアップ機能を提供します。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict, cast

from ..core.exceptions import ExecutionError
from ..utils.config import Config


class DirectoryStats(TypedDict):
    files: int
    size_mb: float
    oldest_file: datetime | None
    newest_file: datetime | None


class CleanupResult(TypedDict):
    deleted_files: int
    freed_size_mb: float
    errors: list[str]
    files_to_delete: list[str]


class FullCleanupSummary(TypedDict):
    deleted_files: int
    freed_size_mb: float
    errors: int


class CleanupRecommendation(TypedDict):
    type: str
    priority: str
    message: str
    action: str


class CacheManager:
    """キャッシュ管理クラス

    ログファイル、キャッシュデータ、レポートファイルの管理と自動クリーンアップを行います。
    """

    def __init__(self, config: Config):
        """キャッシュマネージャーを初期化

        Args:
            config: 設定オブジェクト
        """
        self.config = config
        self.log_dir = config.get_path("log_dir")
        self.cache_dir = config.get_path("cache_dir")
        self.reports_dir = config.get_path("reports_dir")

        # キャッシュメタデータファイル
        self.cache_index_file = self.cache_dir / "cache_index.json"

        # 必要なディレクトリを作成
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        for directory in [self.log_dir, self.cache_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def get_cache_statistics(self) -> dict[str, DirectoryStats]:
        """キャッシュ統計情報を取得

        Returns:
            キャッシュ統計情報
        """
        stats: dict[str, DirectoryStats] = {
            "logs": self._get_directory_stats(self.log_dir),
            "cache": self._get_directory_stats(self.cache_dir),
            "reports": self._get_directory_stats(self.reports_dir),
        }

        # 合計統計
        total_stats: DirectoryStats = {
            "files": sum(s["files"] for s in stats.values()),
            "size_mb": sum(s["size_mb"] for s in stats.values()),
            "oldest_file": min((s["oldest_file"] for s in stats.values() if s["oldest_file"]), default=None),
            "newest_file": max((s["newest_file"] for s in stats.values() if s["newest_file"]), default=None),
        }

        stats["total"] = total_stats
        return stats

    def _get_directory_stats(self, directory: Path) -> DirectoryStats:
        """ディレクトリの統計情報を取得

        Args:
            directory: 対象ディレクトリ

        Returns:
            ディレクトリ統計情報
        """
        if not directory.exists():
            return DirectoryStats(files=0, size_mb=0.0, oldest_file=None, newest_file=None)

        files = list(directory.rglob("*"))
        files = [f for f in files if f.is_file()]

        if not files:
            return DirectoryStats(files=0, size_mb=0.0, oldest_file=None, newest_file=None)

        total_size = sum(f.stat().st_size for f in files)
        file_times = [f.stat().st_mtime for f in files]

        return DirectoryStats(
            files=len(files),
            size_mb=round(total_size / (1024 * 1024), 2),
            oldest_file=datetime.fromtimestamp(min(file_times)),
            newest_file=datetime.fromtimestamp(max(file_times)),
        )

    def cleanup_logs_only(self, dry_run: bool = False, remove_all: bool = False) -> CleanupResult:
        """ログファイルのみをクリーンアップ

        Args:
            dry_run: 実際の削除を行わずに削除対象のみを返す

        Returns:
            クリーンアップ結果
        """
        if remove_all:
            files = [f for f in self.log_dir.glob("*.log") if f.is_file()]
            errors: list[str] = []
            freed_size = 0

            if dry_run:
                freed_size = sum(f.stat().st_size for f in files)
                return CleanupResult(
                    deleted_files=len(files),
                    freed_size_mb=round(freed_size / (1024 * 1024), 2),
                    errors=errors,
                    files_to_delete=[str(f) for f in files],
                )

            deleted_files = 0
            for file_path in files:
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_files += 1
                    freed_size += file_size
                except Exception as e:
                    errors.append(f"ファイル削除エラー {file_path}: {e}")

            return CleanupResult(
                deleted_files=deleted_files,
                freed_size_mb=round(freed_size / (1024 * 1024), 2),
                errors=errors,
                files_to_delete=[],
            )

        max_count = self.config.get("max_log_files", 50)
        max_size_mb = self.config.get("max_log_size_mb", 100)
        max_age_days = self.config.get("max_log_age_days", 30)

        return self._cleanup_directory(
            self.log_dir,
            max_count=max_count,
            max_size_mb=max_size_mb,
            max_age_days=max_age_days,
            dry_run=dry_run,
            file_pattern="*.log",
        )

    def cleanup_cache_only(self, dry_run: bool = False) -> CleanupResult:
        """キャッシュファイルのみをクリーンアップ

        Args:
            dry_run: 実際の削除を行わずに削除対象のみを返す

        Returns:
            クリーンアップ結果
        """
        max_size_mb = self.config.get("max_cache_size_mb", 500)
        max_age_days = self.config.get("max_cache_age_days", 7)

        return self._cleanup_directory(
            self.cache_dir,
            max_size_mb=max_size_mb,
            max_age_days=max_age_days,
            dry_run=dry_run,
            exclude_files=["cache_index.json"],
        )

    def cleanup_all(self, dry_run: bool = False) -> dict[str, CleanupResult | FullCleanupSummary]:
        """すべてのキャッシュとログをクリーンアップ

        Args:
            dry_run: 実際の削除を行わずに削除対象のみを返す

        Returns:
            クリーンアップ結果
        """
        results: dict[str, CleanupResult | FullCleanupSummary] = {
            "logs": self.cleanup_logs_only(dry_run=dry_run),
            "cache": self.cleanup_cache_only(dry_run=dry_run),
            "reports": self._cleanup_directory(
                self.reports_dir, max_age_days=self.config.get("max_report_age_days", 14), dry_run=dry_run
            ),
        }

        # 合計結果
        logs_result = cast(CleanupResult, results["logs"])
        cache_result = cast(CleanupResult, results["cache"])
        reports_result = cast(CleanupResult, results["reports"])
        cleanup_results = [logs_result, cache_result, reports_result]
        total_summary: FullCleanupSummary = {
            "deleted_files": sum(r["deleted_files"] for r in cleanup_results),
            "freed_size_mb": sum(r["freed_size_mb"] for r in cleanup_results),
            "errors": sum(len(r["errors"]) for r in cleanup_results),
        }
        results["total"] = total_summary

        return results

    def _cleanup_directory(
        self,
        directory: Path,
        max_count: int | None = None,
        max_size_mb: int | None = None,
        max_age_days: float | int | None = None,
        dry_run: bool = False,
        file_pattern: str = "*",
        exclude_files: list[str] | None = None,
    ) -> CleanupResult:
        """ディレクトリのクリーンアップを実行

        Args:
            directory: 対象ディレクトリ
            max_count: 保持する最大ファイル数
            max_size_mb: 保持する最大サイズ（MB）
            max_age_days: 保持する最大日数
            dry_run: 実際の削除を行わない
            file_pattern: ファイルパターン
            exclude_files: 除外するファイル名のリスト

        Returns:
            クリーンアップ結果
        """
        if not directory.exists():
            return CleanupResult(deleted_files=0, freed_size_mb=0.0, errors=[], files_to_delete=[])

        exclude_files = exclude_files or []

        # ファイル一覧を取得（新しい順）
        files: list[Path] = list(directory.glob(file_pattern))
        files = [f for f in files if f.is_file() and f.name not in exclude_files]
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        files_to_delete: list[Path] = []
        errors: list[str] = []

        # 年齢による削除
        if max_age_days is not None:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            cutoff_timestamp = cutoff_time.timestamp()

            for file_path in files:
                if file_path.stat().st_mtime < cutoff_timestamp:
                    files_to_delete.append(file_path)

        # 残りのファイルで件数とサイズをチェック
        remaining_files: list[Path] = [f for f in files if f not in files_to_delete]

        # 件数による削除
        if max_count is not None and len(remaining_files) > max_count:
            files_to_delete.extend(remaining_files[max_count:])
            remaining_files = remaining_files[:max_count]

        # サイズによる削除
        if max_size_mb is not None:
            total_size = 0
            size_limit = max_size_mb * 1024 * 1024

            for file_path in remaining_files:
                file_size = file_path.stat().st_size
                if total_size + file_size > size_limit:
                    files_to_delete.append(file_path)
                else:
                    total_size += file_size

        # 重複を除去
        files_to_delete = list(set(files_to_delete))

        # 削除実行
        deleted_files = 0
        freed_size = 0

        if not dry_run:
            for file_path in files_to_delete:
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_files += 1
                    freed_size += file_size
                except Exception as e:
                    errors.append(f"ファイル削除エラー {file_path}: {e}")
        else:
            deleted_files = len(files_to_delete)
            freed_size = sum(f.stat().st_size for f in files_to_delete)

        return CleanupResult(
            deleted_files=deleted_files,
            freed_size_mb=round(freed_size / (1024 * 1024), 2),
            errors=errors,
            files_to_delete=[str(f) for f in files_to_delete] if dry_run else [],
        )

    def auto_cleanup(self) -> dict[str, Any]:
        """自動クリーンアップを実行

        設定に基づいて自動的にクリーンアップを実行します。

        Returns:
            クリーンアップ結果
        """
        # 自動クリーンアップが無効の場合はスキップ
        if not self.config.get("auto_cleanup_enabled", True):
            return {
                "skipped": True,
                "reason": "自動クリーンアップが無効です",
            }

        # 最後のクリーンアップ時刻をチェック
        last_cleanup = self._get_last_cleanup_time()
        cleanup_interval_hours = self.config.get("cleanup_interval_hours", 24)

        if last_cleanup:
            next_cleanup = last_cleanup + timedelta(hours=cleanup_interval_hours)
            if datetime.now() < next_cleanup:
                return {
                    "skipped": True,
                    "reason": f"次回クリーンアップ予定: {next_cleanup}",
                }

        # クリーンアップ実行
        cleanup_result = self.cleanup_all(dry_run=False)

        # 最後のクリーンアップ時刻を更新
        self._update_last_cleanup_time()

        result_with_flag: dict[str, Any] = dict(cleanup_result)
        result_with_flag["auto_cleanup"] = True
        return result_with_flag

    def _get_last_cleanup_time(self) -> datetime | None:
        """最後のクリーンアップ時刻を取得

        Returns:
            最後のクリーンアップ時刻（存在しない場合はNone）
        """
        try:
            if self.cache_index_file.exists():
                with open(self.cache_index_file, encoding="utf-8") as f:
                    data = json.load(f)
                    last_cleanup_str = data.get("last_cleanup")
                    if last_cleanup_str:
                        return datetime.fromisoformat(last_cleanup_str)
        except Exception:
            pass
        return None

    def _update_last_cleanup_time(self) -> None:
        """最後のクリーンアップ時刻を更新"""
        try:
            data = {}
            if self.cache_index_file.exists():
                with open(self.cache_index_file, encoding="utf-8") as f:
                    data = json.load(f)

            data["last_cleanup"] = datetime.now().isoformat()

            with open(self.cache_index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            # ログ記録は行うが、エラーで停止はしない
            pass

    def reset_all_cache(self, confirm: bool = False) -> dict[str, Any]:
        """すべてのキャッシュを完全にリセット

        Args:
            confirm: 削除の確認フラグ

        Returns:
            リセット結果

        Raises:
            ExecutionError: 確認なしで実行された場合
        """
        if not confirm:
            raise ExecutionError("キャッシュの完全リセットには確認が必要です", "confirm=True を指定してください")

        deleted_directories: list[str] = []
        reset_errors: list[str] = []
        results: dict[str, Any] = {
            "deleted_directories": deleted_directories,
            "errors": reset_errors,
            "total_freed_mb": 0.0,
        }

        # 各ディレクトリを削除
        for dir_name, directory in [
            ("logs", self.log_dir),
            ("cache", self.cache_dir),
            ("reports", self.reports_dir),
        ]:
            try:
                if directory.exists():
                    # ディレクトリサイズを計算
                    size_mb = self._get_directory_stats(directory)["size_mb"]

                    # ディレクトリを削除
                    shutil.rmtree(directory)

                    # 再作成
                    directory.mkdir(parents=True, exist_ok=True)

                    deleted_directories.append(dir_name)
                    results["total_freed_mb"] += size_mb

            except Exception as e:
                reset_errors.append(f"{dir_name}ディレクトリのリセットエラー: {e}")

        return results

    def get_cleanup_recommendations(self) -> dict[str, Any]:
        """クリーンアップの推奨事項を取得

        Returns:
            推奨事項
        """
        stats = self.get_cache_statistics()
        recommendations: list[CleanupRecommendation] = []

        # ログファイルの推奨事項
        log_stats = stats["logs"]
        if log_stats["size_mb"] > self.config.get("max_log_size_mb", 100):
            recommendations.append(
                {
                    "type": "logs",
                    "priority": "high",
                    "message": f"ログファイルが制限サイズを超過しています ({log_stats['size_mb']}MB)",
                    "action": "ci-run clean --logs-only を実行してください",
                }
            )
        elif log_stats["files"] > self.config.get("max_log_files", 50):
            recommendations.append(
                {
                    "type": "logs",
                    "priority": "medium",
                    "message": f"ログファイル数が多すぎます ({log_stats['files']}ファイル)",
                    "action": "古いログファイルの削除を検討してください",
                }
            )

        # キャッシュファイルの推奨事項
        cache_stats = stats["cache"]
        if cache_stats["size_mb"] > self.config.get("max_cache_size_mb", 500):
            recommendations.append(
                {
                    "type": "cache",
                    "priority": "high",
                    "message": f"キャッシュサイズが制限を超過しています ({cache_stats['size_mb']}MB)",
                    "action": "ci-run clean を実行してください",
                }
            )

        # 古いファイルの推奨事項
        if stats["total"]["oldest_file"]:
            age_days = (datetime.now() - stats["total"]["oldest_file"]).days
            if age_days > 30:
                recommendations.append(
                    {
                        "type": "age",
                        "priority": "low",
                        "message": f"古いファイルが存在します ({age_days}日前)",
                        "action": "定期的なクリーンアップを検討してください",
                    }
                )

        return {
            "recommendations": recommendations,
            "total_size_mb": stats["total"]["size_mb"],
            "auto_cleanup_enabled": self.config.get("auto_cleanup_enabled", True),
            "next_auto_cleanup": self._get_next_auto_cleanup_time(),
        }

    def _get_next_auto_cleanup_time(self) -> datetime | None:
        """次回の自動クリーンアップ時刻を取得

        Returns:
            次回の自動クリーンアップ時刻
        """
        last_cleanup = self._get_last_cleanup_time()
        if last_cleanup:
            interval_hours = self.config.get("cleanup_interval_hours", 24)
            return last_cleanup + timedelta(hours=interval_hours)
        return None

    def validate_cache_integrity(self) -> dict[str, Any]:
        """キャッシュの整合性をチェック

        Returns:
            整合性チェック結果
        """
        issues: list[str] = []

        # ディレクトリの存在チェック
        for name, directory in [
            ("logs", self.log_dir),
            ("cache", self.cache_dir),
            ("reports", self.reports_dir),
        ]:
            if not directory.exists():
                issues.append(f"{name}ディレクトリが存在しません: {directory}")

        # 権限チェック
        for name, directory in [
            ("logs", self.log_dir),
            ("cache", self.cache_dir),
            ("reports", self.reports_dir),
        ]:
            if directory.exists() and not os.access(directory, os.W_OK):
                issues.append(f"{name}ディレクトリに書き込み権限がありません: {directory}")

        # 破損ファイルのチェック
        if self.cache_index_file.exists():
            try:
                with open(self.cache_index_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError:
                issues.append("キャッシュインデックスファイルが破損しています")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now().isoformat(),
        }
