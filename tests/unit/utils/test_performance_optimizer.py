"""
パフォーマンス最適化機能のテスト
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from ci_helper.core.models import ExecutionResult, FailureType, JobResult, WorkflowResult
from ci_helper.utils.performance_optimizer import (
    DuplicateProcessingPreventer,
    FormatResultCache,
    LogFileStreamer,
    MemoryLimiter,
    PerformanceOptimizer,
)


class TestMemoryLimiter:
    """メモリリミッターのテスト"""

    def test_init_default_values(self):
        """デフォルト値での初期化テスト"""
        limiter = MemoryLimiter()
        assert limiter.max_memory_bytes == 100 * 1024 * 1024  # 100MB
        assert limiter.chunk_size <= 1024 * 1024  # 1MB以下

    def test_init_custom_values(self):
        """カスタム値での初期化テスト"""
        limiter = MemoryLimiter(max_memory_mb=200)
        assert limiter.max_memory_bytes == 200 * 1024 * 1024  # 200MB

    def test_get_chunk_size(self):
        """チャンクサイズ取得テスト"""
        limiter = MemoryLimiter(max_memory_mb=100)
        chunk_size = limiter.get_chunk_size()
        assert isinstance(chunk_size, int)
        assert chunk_size > 0
        assert chunk_size <= 1024 * 1024  # 1MB以下

    def test_should_use_streaming_small_file(self):
        """小さなファイルでのストリーミング判定テスト"""
        limiter = MemoryLimiter(max_memory_mb=100)
        small_file_size = 50 * 1024 * 1024  # 50MB
        assert not limiter.should_use_streaming(small_file_size)

    def test_should_use_streaming_large_file(self):
        """大きなファイルでのストリーミング判定テスト"""
        limiter = MemoryLimiter(max_memory_mb=100)
        large_file_size = 150 * 1024 * 1024  # 150MB
        assert limiter.should_use_streaming(large_file_size)


class TestLogFileStreamer:
    """ログファイルストリーマーのテスト"""

    def test_init(self):
        """初期化テスト"""
        streamer = LogFileStreamer()
        assert streamer.memory_limiter is not None
        assert isinstance(streamer.memory_limiter, MemoryLimiter)

    def test_init_with_custom_limiter(self):
        """カスタムメモリリミッターでの初期化テスト"""
        custom_limiter = MemoryLimiter(max_memory_mb=200)
        streamer = LogFileStreamer(custom_limiter)
        assert streamer.memory_limiter is custom_limiter

    def test_stream_file_chunks_nonexistent_file(self):
        """存在しないファイルでのチャンクストリーミングテスト"""
        streamer = LogFileStreamer()
        nonexistent_file = Path("/nonexistent/file.log")

        with pytest.raises(FileNotFoundError):
            list(streamer.stream_file_chunks(nonexistent_file))

    def test_stream_file_chunks_existing_file(self):
        """既存ファイルでのチャンクストリーミングテスト"""
        streamer = LogFileStreamer()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            test_content = "Line 1\nLine 2\nLine 3\n" * 1000  # 大きなコンテンツ
            f.write(test_content)
            f.flush()

            temp_path = Path(f.name)

        try:
            chunks = list(streamer.stream_file_chunks(temp_path))
            assert len(chunks) > 0

            # 全チャンクを結合すると元のコンテンツになることを確認
            combined_content = "".join(chunks)
            assert combined_content == test_content
        finally:
            temp_path.unlink()

    def test_stream_lines_existing_file(self):
        """既存ファイルでの行ストリーミングテスト"""
        streamer = LogFileStreamer()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            test_lines = ["Line 1", "Line 2", "Line 3"]
            f.write("\n".join(test_lines))
            f.flush()

            temp_path = Path(f.name)

        try:
            lines = list(streamer.stream_lines(temp_path))
            assert lines == test_lines
        finally:
            temp_path.unlink()

    def test_get_file_info_nonexistent_file(self):
        """存在しないファイルの情報取得テスト"""
        streamer = LogFileStreamer()
        nonexistent_file = Path("/nonexistent/file.log")

        info = streamer.get_file_info(nonexistent_file)
        assert info["exists"] is False
        assert info["size"] == 0
        assert info["lines"] == 0
        assert info["should_stream"] is False

    def test_get_file_info_existing_file(self):
        """既存ファイルの情報取得テスト"""
        streamer = LogFileStreamer()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            test_content = "Line 1\nLine 2\nLine 3\n"
            f.write(test_content)
            f.flush()

            temp_path = Path(f.name)

        try:
            info = streamer.get_file_info(temp_path)
            assert info["exists"] is True
            assert info["size"] > 0
            assert info["lines"] >= 3
            assert "should_stream" in info
            assert "modified_time" in info
        finally:
            temp_path.unlink()


class TestFormatResultCache:
    """フォーマット結果キャッシュのテスト"""

    def test_init_default_cache_dir(self):
        """デフォルトキャッシュディレクトリでの初期化テスト"""
        cache = FormatResultCache()
        assert cache.cache_dir.exists()
        assert cache.max_cache_size > 0

    def test_init_custom_cache_dir(self):
        """カスタムキャッシュディレクトリでの初期化テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "custom_cache"
            cache = FormatResultCache(cache_dir)
            assert cache.cache_dir == cache_dir
            assert cache.cache_dir.exists()

    def test_get_cache_key(self):
        """キャッシュキー生成テスト"""
        cache = FormatResultCache()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            key1 = cache.get_cache_key(temp_path, "ai", {"option1": "value1"})
            key2 = cache.get_cache_key(temp_path, "ai", {"option1": "value1"})
            key3 = cache.get_cache_key(temp_path, "human", {"option1": "value1"})

            # 同じ条件では同じキーが生成される
            assert key1 == key2

            # 異なる条件では異なるキーが生成される
            assert key1 != key3

            # キーはハッシュ値（64文字の16進数）
            assert len(key1) == 64
            assert all(c in "0123456789abcdef" for c in key1)
        finally:
            temp_path.unlink()

    def test_cache_operations(self):
        """キャッシュ操作テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "test_cache"
            cache = FormatResultCache(cache_dir)

            # テストデータ
            cache_key = "test_key_123"
            test_result = "Test formatted result content"

            # 初期状態では結果が存在しない
            assert cache.get_cached_result(cache_key) is None

            # 結果を保存
            success = cache.store_cached_result(cache_key, test_result)
            assert success is True

            # 保存した結果を取得
            retrieved_result = cache.get_cached_result(cache_key)
            assert retrieved_result == test_result

    def test_cache_statistics(self):
        """キャッシュ統計テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "test_cache"
            cache = FormatResultCache(cache_dir)

            # 初期統計
            stats = cache.get_cache_statistics()
            assert stats["total_entries"] == 0
            assert stats["total_size_mb"] == 0

            # テストデータを追加
            cache.store_cached_result("key1", "content1")
            cache.store_cached_result("key2", "content2")

            # 統計を再取得
            stats = cache.get_cache_statistics()
            assert stats["total_entries"] == 2
            assert stats["total_size_mb"] >= 0  # サイズは0以上であることを確認

    def test_clear_cache(self):
        """キャッシュクリアテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "test_cache"
            cache = FormatResultCache(cache_dir)

            # テストデータを追加
            cache.store_cached_result("key1", "content1")
            cache.store_cached_result("key2", "content2")

            # キャッシュをクリア
            cleared_count = cache.clear_cache()
            assert cleared_count == 2

            # クリア後の統計確認
            stats = cache.get_cache_statistics()
            assert stats["total_entries"] == 0


class TestDuplicateProcessingPreventer:
    """重複処理防止機能のテスト"""

    def test_init(self):
        """初期化テスト"""
        preventer = DuplicateProcessingPreventer()
        assert len(preventer._processing_files) == 0

    def test_processing_lifecycle(self):
        """処理ライフサイクルテスト"""
        preventer = DuplicateProcessingPreventer()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            # 初期状態では処理中ではない
            assert not preventer.is_processing(temp_path)

            # 処理開始
            assert preventer.start_processing(temp_path) is True
            assert preventer.is_processing(temp_path) is True

            # 重複処理開始は失敗
            assert preventer.start_processing(temp_path) is False

            # 処理終了
            preventer.finish_processing(temp_path)
            assert not preventer.is_processing(temp_path)

            # 再度処理開始可能
            assert preventer.start_processing(temp_path) is True
        finally:
            temp_path.unlink()

    def test_get_processing_status(self):
        """処理状況取得テスト"""
        preventer = DuplicateProcessingPreventer()

        # 初期状態
        status = preventer.get_processing_status()
        assert status["active_processes"] == 0
        assert len(status["processes"]) == 0

        # 処理開始後
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            preventer.start_processing(temp_path)

            status = preventer.get_processing_status()
            assert status["active_processes"] == 1
            assert len(status["processes"]) == 1
        finally:
            temp_path.unlink()

    def test_cleanup_expired_locks(self):
        """期限切れロッククリーンアップテスト"""
        preventer = DuplicateProcessingPreventer()

        # タイムアウト時間を短く設定（テスト用）
        preventer._lock_timeout_minutes = 0.001  # 0.06秒

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            # 処理開始
            preventer.start_processing(temp_path)
            assert preventer.is_processing(temp_path) is True

            # 少し待機してタイムアウトさせる
            import time

            time.sleep(0.1)

            # 期限切れロックをクリーンアップ
            cleaned_count = preventer.cleanup_expired_locks()
            assert cleaned_count == 1

            # 処理中ではなくなっている
            assert not preventer.is_processing(temp_path)
        finally:
            temp_path.unlink()


class TestPerformanceOptimizer:
    """パフォーマンス最適化統合クラスのテスト"""

    def test_init(self):
        """初期化テスト"""
        optimizer = PerformanceOptimizer()
        assert optimizer.memory_limiter is not None
        assert optimizer.streamer is not None
        assert optimizer.cache is not None
        assert optimizer.duplicate_preventer is not None

    def test_init_with_custom_params(self):
        """カスタムパラメータでの初期化テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "custom_cache"
            optimizer = PerformanceOptimizer(max_memory_mb=200, cache_dir=cache_dir, max_cache_size_mb=100)
            assert optimizer.memory_limiter.max_memory_bytes == 200 * 1024 * 1024
            assert optimizer.cache.cache_dir == cache_dir

    def test_should_use_optimization(self):
        """最適化使用判定テスト"""
        optimizer = PerformanceOptimizer()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            # 小さなファイル
            f.write("small content")
            f.flush()
            temp_path = Path(f.name)

        try:
            flags = optimizer.should_use_optimization(temp_path)
            assert "use_streaming" in flags
            assert "use_cache" in flags
            assert "check_duplicates" in flags
            assert flags["check_duplicates"] is True
        finally:
            temp_path.unlink()

    def test_get_optimization_stats(self):
        """最適化統計取得テスト"""
        optimizer = PerformanceOptimizer()

        stats = optimizer.get_optimization_stats()
        assert "memory_limit_mb" in stats
        assert "chunk_size_kb" in stats
        assert "cache_stats" in stats
        assert "processing_status" in stats

    def test_cleanup_all(self):
        """全クリーンアップテスト"""
        optimizer = PerformanceOptimizer()

        # テストデータを追加
        optimizer.cache.store_cached_result("test_key", "test_content")

        # クリーンアップ実行
        result = optimizer.cleanup_all()
        assert "cleared_cache_entries" in result
        assert "expired_locks_cleaned" in result
        assert isinstance(result["cleared_cache_entries"], int)
        assert isinstance(result["expired_locks_cleaned"], int)


@pytest.fixture
def sample_execution_result():
    """テスト用のExecutionResultを作成"""
    failure = Mock()
    failure.type = FailureType.ASSERTION
    failure.message = "Test assertion failed"
    failure.file_path = "test_file.py"
    failure.line_number = 42

    job_result = JobResult(name="test_job", success=False, failures=[failure], duration=1.5)

    workflow_result = WorkflowResult(name="test_workflow", success=False, jobs=[job_result], duration=2.0)

    return ExecutionResult(success=False, workflows=[workflow_result], total_duration=2.0)


class TestIntegration:
    """統合テスト"""

    def test_streaming_formatter_integration(self, sample_execution_result):
        """ストリーミングフォーマッター統合テスト"""
        from ci_helper.formatters.base_formatter import BaseLogFormatter
        from ci_helper.formatters.streaming_formatter import StreamingFormatterMixin

        class TestStreamingFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return f"Formatted: {execution_result.success}"

            def get_format_name(self):
                return "test_streaming"

        formatter = TestStreamingFormatter()

        # 最適化機能が初期化されていることを確認
        assert hasattr(formatter, "performance_optimizer")
        assert formatter.performance_optimizer is not None

        # 通常のフォーマット
        result = formatter.format(sample_execution_result)
        assert "Formatted: False" in result

        # 最適化機能付きフォーマット（ログファイルなしの場合）
        result = formatter.format_with_optimization(sample_execution_result)
        assert "Formatted: False" in result

    def test_cache_integration_with_real_file(self, sample_execution_result):
        """実ファイルを使用したキャッシュ統合テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "test_cache"
            optimizer = PerformanceOptimizer(cache_dir=cache_dir)

            # テストログファイルを作成
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("Test log content\nError: Something failed\n")

            # ExecutionResultにログパスを設定
            sample_execution_result.log_path = str(log_file)

            # キャッシュキーを生成
            cache_key = optimizer.cache.get_cache_key(log_file, "ai", {})

            # 初期状態ではキャッシュされていない
            assert optimizer.cache.get_cached_result(cache_key) is None

            # 結果をキャッシュに保存
            test_result = "Cached formatted result"
            optimizer.cache.store_cached_result(cache_key, test_result)

            # キャッシュから取得
            cached_result = optimizer.cache.get_cached_result(cache_key)
            assert cached_result == test_result
