"""パフォーマンス最適化ユーティリティ

大きなログファイルの処理、メモリ使用量制限、キャッシュ機能を提供します。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict, cast


class CacheEntry(TypedDict, total=False):
    created: str
    last_access: str
    size: int
    hit_count: int
    access_count: int
    metadata: dict[str, Any]


class CacheIndex(TypedDict):
    version: str
    created: str
    entries: dict[str, CacheEntry]


class MemoryLimiter:
    """メモリ使用量制限クラス

    大きなログファイルの処理時にメモリ使用量を制限します。
    """

    def __init__(self, max_memory_mb: int = 100):
        """メモリリミッターを初期化

        Args:
            max_memory_mb: 最大メモリ使用量（MB）

        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.chunk_size = min(self.max_memory_bytes // 4, 1024 * 1024)  # 1MB以下

    def get_chunk_size(self) -> int:
        """チャンクサイズを取得

        Returns:
            チャンクサイズ（バイト）

        """
        return self.chunk_size

    def should_use_streaming(self, file_size: int) -> bool:
        """ストリーミング処理を使用すべきかどうか判定

        Args:
            file_size: ファイルサイズ（バイト）

        Returns:
            ストリーミング処理を使用すべき場合True

        """
        return file_size > self.max_memory_bytes


class LogFileStreamer:
    """ログファイルストリーミング処理クラス

    大きなログファイルをチャンク単位で読み込み、メモリ効率的に処理します。
    """

    def __init__(self, memory_limiter: MemoryLimiter | None = None):
        """ストリーマーを初期化

        Args:
            memory_limiter: メモリリミッター

        """
        self.memory_limiter = memory_limiter or MemoryLimiter()

    def stream_file_chunks(self, file_path: Path) -> Iterator[str]:
        """ファイルをチャンク単位でストリーミング読み込み

        Args:
            file_path: 読み込み対象ファイル

        Yields:
            ファイルのチャンク（文字列）

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            IOError: ファイル読み込みエラー

        """
        if not file_path.exists():
            raise FileNotFoundError(f"ログファイルが見つかりません: {file_path}")

        chunk_size = self.memory_limiter.get_chunk_size()

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            raise OSError(f"ファイル読み込みエラー: {file_path} - {e}") from e

    def stream_lines(self, file_path: Path) -> Iterator[str]:
        """ファイルを行単位でストリーミング読み込み

        Args:
            file_path: 読み込み対象ファイル

        Yields:
            ファイルの行（文字列）

        """
        if not file_path.exists():
            raise FileNotFoundError(f"ログファイルが見つかりません: {file_path}")

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line.rstrip("\n\r")
        except Exception as e:
            raise OSError(f"ファイル読み込みエラー: {file_path} - {e}") from e

    def get_file_info(self, file_path: Path) -> dict[str, Any]:
        """ファイル情報を取得

        Args:
            file_path: 対象ファイル

        Returns:
            ファイル情報の辞書

        """
        if not file_path.exists():
            return {
                "exists": False,
                "size": 0,
                "lines": 0,
                "should_stream": False,
            }

        stat = file_path.stat()
        file_size = stat.st_size

        # 行数を効率的にカウント
        line_count = self._count_lines_efficiently(file_path, file_size)

        return {
            "exists": True,
            "size": file_size,
            "lines": line_count,
            "should_stream": self.memory_limiter.should_use_streaming(file_size),
            "modified_time": datetime.fromtimestamp(stat.st_mtime),
        }

    def _count_lines_efficiently(self, file_path: Path, file_size: int) -> int:
        """効率的に行数をカウント

        Args:
            file_path: 対象ファイル
            file_size: ファイルサイズ

        Returns:
            行数

        """
        if file_size == 0:
            return 0

        # 小さなファイルは直接カウント
        if file_size < 1024 * 1024:  # 1MB未満
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0

        # 大きなファイルはサンプリングで推定
        try:
            sample_size = min(64 * 1024, file_size // 10)  # 64KB or 10%
            with open(file_path, encoding="utf-8", errors="replace") as f:
                sample = f.read(sample_size)
                if not sample:
                    return 0

                lines_in_sample = sample.count("\n")
                if lines_in_sample == 0:
                    return 1  # 改行がない場合は1行とみなす

                # 推定行数を計算
                estimated_lines = int((lines_in_sample * file_size) / len(sample.encode("utf-8")))
                return max(1, estimated_lines)
        except Exception:
            return 0


class FormatResultCache:
    """フォーマット結果キャッシュクラス

    フォーマット結果をキャッシュして重複処理を回避します。
    """

    def __init__(self, cache_dir: Path | None = None, max_cache_size_mb: int = 50):
        """キャッシュを初期化

        Args:
            cache_dir: キャッシュディレクトリ（Noneの場合は一時ディレクトリ）
            max_cache_size_mb: 最大キャッシュサイズ（MB）

        """
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "ci_helper_cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        self.index_file = self.cache_dir / "cache_index.json"

        # キャッシュインデックスを初期化
        self._load_cache_index()

    def get_cache_key(self, file_path: Path, format_type: str, options: dict[str, Any] | None = None) -> str:
        """キャッシュキーを生成

        Args:
            file_path: ログファイルパス
            format_type: フォーマット種別
            options: フォーマットオプション

        Returns:
            キャッシュキー（ハッシュ値）

        """
        # ファイルの最終更新時刻とサイズを含める
        try:
            stat = file_path.stat()
            file_info = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
        except Exception:
            file_info = str(file_path)

        # オプションを正規化
        normalized_options = json.dumps(options or {}, sort_keys=True)

        # キャッシュキーを生成
        key_data = f"{file_info}:{format_type}:{normalized_options}"
        return hashlib.sha256(key_data.encode("utf-8")).hexdigest()

    def get_cached_result(self, cache_key: str) -> str | None:
        """キャッシュされた結果を取得

        Args:
            cache_key: キャッシュキー

        Returns:
            キャッシュされた結果（存在しない場合はNone）

        """
        cache_file = self.cache_dir / f"{cache_key}.cache"

        if not cache_file.exists():
            return None

        try:
            # キャッシュの有効期限をチェック
            if self._is_cache_expired(cache_key):
                self._remove_cache_entry(cache_key)
                return None

            # キャッシュファイルを読み込み
            with open(cache_file, encoding="utf-8") as f:
                result = f.read()

            # アクセス時刻を更新
            self._update_cache_access(cache_key)

            return result

        except Exception:
            # キャッシュファイルが破損している場合は削除
            self._remove_cache_entry(cache_key)
            return None

    def store_cached_result(self, cache_key: str, result: str, metadata: dict[str, Any] | None = None) -> bool:
        """結果をキャッシュに保存

        Args:
            cache_key: キャッシュキー
            result: 保存する結果
            metadata: メタデータ

        Returns:
            保存に成功した場合True

        """
        try:
            # キャッシュサイズをチェック
            if len(result.encode("utf-8")) > self.max_cache_size // 10:
                # 単一エントリが最大サイズの10%を超える場合はキャッシュしない
                return False

            # 古いキャッシュをクリーンアップ
            self._cleanup_cache_if_needed()

            # キャッシュファイルに保存
            cache_file = self.cache_dir / f"{cache_key}.cache"
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(result)

            # インデックスを更新
            self._add_cache_entry(cache_key, len(result.encode("utf-8")), metadata)

            return True

        except Exception:
            return False

    def clear_cache(self) -> int:
        """キャッシュをクリア

        Returns:
            削除されたエントリ数

        """
        deleted_count = 0

        try:
            # キャッシュファイルを削除
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                    deleted_count += 1
                except Exception:
                    pass

            # インデックスファイルを削除
            if self.index_file.exists():
                self.index_file.unlink()

            # インデックスを再初期化
            self._load_cache_index()

        except Exception:
            pass

        return deleted_count

    def get_cache_statistics(self) -> dict[str, Any]:
        """キャッシュ統計情報を取得

        Returns:
            キャッシュ統計情報

        """
        index_data = self._load_cache_index()
        entries = index_data["entries"]

        total_size = sum(entry.get("size", 0) for entry in entries.values())
        total_entries = len(entries)

        # ヒット率を計算（簡易版）
        hit_count = sum(entry.get("hit_count", 0) for entry in entries.values())
        access_count = sum(entry.get("access_count", 0) for entry in entries.values())
        hit_rate = (hit_count / access_count * 100) if access_count > 0 else 0

        return {
            "total_entries": total_entries,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "hit_rate": round(hit_rate, 1),
            "cache_dir": str(self.cache_dir),
        }

    def _load_cache_index(self) -> CacheIndex:
        """キャッシュインデックスを読み込み

        Returns:
            インデックスデータ

        """
        if not self.index_file.exists():
            default_index = self._create_default_index()
            self._save_cache_index(default_index)
            return default_index

        try:
            with open(self.index_file, encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception:
            raw_data = None

        if isinstance(raw_data, dict):
            raw_mapping = cast(dict[str, Any], raw_data)
            entries_field = raw_mapping.get("entries")
            if isinstance(entries_field, Mapping):
                typed_entries_field = cast(Mapping[str, Any], entries_field)
                entries = self._normalize_entries(typed_entries_field)
                return {
                    "version": str(raw_mapping.get("version", "1.0")),
                    "created": str(raw_mapping.get("created", datetime.now().isoformat())),
                    "entries": entries,
                }

        # 破損したインデックスファイルは再作成
        default_index = self._create_default_index()
        self._save_cache_index(default_index)
        return default_index

    def _save_cache_index(self, index_data: CacheIndex) -> None:
        """キャッシュインデックスを保存

        Args:
            index_data: インデックスデータ

        """
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _add_cache_entry(self, cache_key: str, size: int, metadata: dict[str, Any] | None = None) -> None:
        """キャッシュエントリを追加

        Args:
            cache_key: キャッシュキー
            size: データサイズ
            metadata: メタデータ

        """
        index_data = self._load_cache_index()

        entry_metadata: dict[str, Any] = metadata or {}
        entry: CacheEntry = {
            "created": datetime.now().isoformat(),
            "last_access": datetime.now().isoformat(),
            "size": size,
            "hit_count": 0,
            "access_count": 0,
            "metadata": entry_metadata,
        }

        index_data["entries"][cache_key] = entry
        self._save_cache_index(index_data)

    def _update_cache_access(self, cache_key: str) -> None:
        """キャッシュアクセス情報を更新

        Args:
            cache_key: キャッシュキー

        """
        index_data = self._load_cache_index()

        if cache_key in index_data["entries"]:
            entry = index_data["entries"][cache_key]
            entry["last_access"] = datetime.now().isoformat()
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            entry["access_count"] = entry.get("access_count", 0) + 1

            self._save_cache_index(index_data)

    def _remove_cache_entry(self, cache_key: str) -> None:
        """キャッシュエントリを削除

        Args:
            cache_key: キャッシュキー

        """
        # キャッシュファイルを削除
        cache_file = self.cache_dir / f"{cache_key}.cache"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception:
                pass

        # インデックスから削除
        index_data = self._load_cache_index()
        if cache_key in index_data["entries"]:
            del index_data["entries"][cache_key]
            self._save_cache_index(index_data)

    def _is_cache_expired(self, cache_key: str, max_age_hours: int = 24) -> bool:
        """キャッシュが期限切れかどうかチェック

        Args:
            cache_key: キャッシュキー
            max_age_hours: 最大保持時間（時間）

        Returns:
            期限切れの場合True

        """
        index_data = self._load_cache_index()

        if cache_key not in index_data["entries"]:
            return True

        entry = index_data["entries"][cache_key]
        created_str = entry.get("created")
        if not isinstance(created_str, str):
            return True

        created_time = datetime.fromisoformat(created_str)

        return datetime.now() - created_time > timedelta(hours=max_age_hours)

    def _cleanup_cache_if_needed(self) -> None:
        """必要に応じてキャッシュをクリーンアップ"""
        index_data = self._load_cache_index()
        entries = index_data.get("entries", {})

        # 現在のキャッシュサイズを計算
        current_size = sum(entry.get("size", 0) for entry in entries.values())

        if current_size <= self.max_cache_size:
            return

        # LRU（Least Recently Used）でエントリを削除
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].get("last_access", ""),
        )

        # サイズが制限以下になるまで古いエントリを削除
        for cache_key, entry in sorted_entries:
            if current_size <= self.max_cache_size * 0.8:  # 80%まで削減
                break

            self._remove_cache_entry(cache_key)
            current_size -= entry.get("size", 0)

    def _create_default_index(self) -> CacheIndex:
        """空のキャッシュインデックスを生成"""
        entries: dict[str, CacheEntry] = {}
        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "entries": entries,
        }

    def _normalize_entries(self, entries_field: Mapping[str, Any]) -> dict[str, CacheEntry]:
        """JSONから読み込んだエントリを型安全に正規化"""
        normalized: dict[str, CacheEntry] = {}

        for cache_key, entry_data in entries_field.items():
            if isinstance(entry_data, Mapping):
                normalized[cache_key] = self._coerce_cache_entry(cast(Mapping[str, Any], entry_data))

        return normalized

    def _coerce_cache_entry(self, entry_data: Mapping[str, Any]) -> CacheEntry:
        """任意のマッピングを CacheEntry に変換"""
        metadata_field = entry_data.get("metadata")
        if isinstance(metadata_field, dict):
            metadata: dict[str, Any] = cast(dict[str, Any], metadata_field)
        else:
            metadata = {}

        normalized_entry: CacheEntry = {
            "created": str(entry_data.get("created", datetime.now().isoformat())),
            "last_access": str(entry_data.get("last_access", datetime.now().isoformat())),
            "size": int(entry_data.get("size", 0)),
            "hit_count": int(entry_data.get("hit_count", 0)),
            "access_count": int(entry_data.get("access_count", 0)),
            "metadata": metadata,
        }

        return normalized_entry


class DuplicateProcessingPreventer:
    """重複処理防止クラス

    同一ログファイルの重複処理を検出・防止します。
    """

    def __init__(self):
        """重複処理防止機能を初期化"""
        self._processing_files: dict[str, datetime] = {}
        self._lock_timeout_minutes = 30

    def is_processing(self, file_path: Path) -> bool:
        """ファイルが処理中かどうかチェック

        Args:
            file_path: チェック対象ファイル

        Returns:
            処理中の場合True

        """
        file_key = self._get_file_key(file_path)

        if file_key not in self._processing_files:
            return False

        # タイムアウトチェック
        start_time = self._processing_files[file_key]
        if datetime.now() - start_time > timedelta(minutes=self._lock_timeout_minutes):
            # タイムアウトした場合はロックを解除
            del self._processing_files[file_key]
            return False

        return True

    def start_processing(self, file_path: Path) -> bool:
        """ファイル処理を開始

        Args:
            file_path: 処理対象ファイル

        Returns:
            処理を開始できた場合True（既に処理中の場合False）

        """
        if self.is_processing(file_path):
            return False

        file_key = self._get_file_key(file_path)
        self._processing_files[file_key] = datetime.now()
        return True

    def finish_processing(self, file_path: Path) -> None:
        """ファイル処理を終了

        Args:
            file_path: 処理対象ファイル

        """
        file_key = self._get_file_key(file_path)
        if file_key in self._processing_files:
            del self._processing_files[file_key]

    def get_processing_status(self) -> dict[str, Any]:
        """処理状況を取得

        Returns:
            処理状況の辞書

        """
        current_time = datetime.now()
        active_processes: list[dict[str, Any]] = []

        for file_key, start_time in self._processing_files.items():
            duration = current_time - start_time
            active_processes.append(
                {
                    "file": file_key,
                    "start_time": start_time.isoformat(),
                    "duration_minutes": round(duration.total_seconds() / 60, 1),
                },
            )

        return {
            "active_processes": len(self._processing_files),
            "processes": active_processes,
        }

    def cleanup_expired_locks(self) -> int:
        """期限切れのロックをクリーンアップ

        Returns:
            クリーンアップされたロック数

        """
        current_time = datetime.now()
        expired_keys: list[str] = []

        for file_key, start_time in self._processing_files.items():
            if current_time - start_time > timedelta(minutes=self._lock_timeout_minutes):
                expired_keys.append(file_key)

        for key in expired_keys:
            del self._processing_files[key]

        return len(expired_keys)

    def _get_file_key(self, file_path: Path) -> str:
        """ファイルキーを生成

        Args:
            file_path: ファイルパス

        Returns:
            ファイルキー

        """
        try:
            # 絶対パスと最終更新時刻を組み合わせてキーを生成
            abs_path = file_path.resolve()
            stat = file_path.stat()
            return f"{abs_path}:{stat.st_mtime}:{stat.st_size}"
        except Exception:
            # ファイル情報が取得できない場合はパスのみ使用
            return str(file_path)


class PerformanceOptimizer:
    """パフォーマンス最適化統合クラス

    ストリーミング処理、メモリ制限、キャッシュ、重複処理防止を統合します。
    """

    def __init__(
        self,
        max_memory_mb: int = 100,
        cache_dir: Path | None = None,
        max_cache_size_mb: int = 50,
    ):
        """パフォーマンス最適化機能を初期化

        Args:
            max_memory_mb: 最大メモリ使用量（MB）
            cache_dir: キャッシュディレクトリ
            max_cache_size_mb: 最大キャッシュサイズ（MB）

        """
        self.memory_limiter = MemoryLimiter(max_memory_mb)
        self.streamer = LogFileStreamer(self.memory_limiter)
        self.cache = FormatResultCache(cache_dir, max_cache_size_mb)
        self.duplicate_preventer = DuplicateProcessingPreventer()

    def should_use_optimization(self, file_path: Path) -> dict[str, bool]:
        """最適化機能を使用すべきかどうか判定

        Args:
            file_path: 対象ファイル

        Returns:
            最適化機能の使用判定結果

        """
        file_info = self.streamer.get_file_info(file_path)

        return {
            "use_streaming": file_info["should_stream"],
            "use_cache": file_info["size"] > 1024 * 1024,  # 1MB以上でキャッシュ使用
            "check_duplicates": True,  # 常に重複チェック
        }

    def get_optimization_stats(self) -> dict[str, Any]:
        """最適化統計情報を取得

        Returns:
            最適化統計情報

        """
        return {
            "memory_limit_mb": self.memory_limiter.max_memory_bytes // (1024 * 1024),
            "chunk_size_kb": self.memory_limiter.chunk_size // 1024,
            "cache_stats": self.cache.get_cache_statistics(),
            "processing_status": self.duplicate_preventer.get_processing_status(),
        }

    def cleanup_all(self) -> dict[str, int]:
        """全ての最適化機能をクリーンアップ

        Returns:
            クリーンアップ結果

        """
        return {
            "cleared_cache_entries": self.cache.clear_cache(),
            "expired_locks_cleaned": self.duplicate_preventer.cleanup_expired_locks(),
        }
