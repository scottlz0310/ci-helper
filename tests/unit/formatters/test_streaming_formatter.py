"""
ストリーミングフォーマッターのテスト

ストリーミング出力フォーマット、エラーハンドリング、バッファリング機能をテスト
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from ci_helper.core.models import ExecutionResult
from ci_helper.formatters.base_formatter import BaseLogFormatter
from ci_helper.formatters.streaming_formatter import (
    ChunkedLogProcessor,
    ProgressTrackingFormatter,
    StreamingAwareFormatter,
    StreamingFormatterMixin,
)


class TestStreamingFormatterMixin:
    """StreamingFormatterMixinのテスト"""

    def test_mixin_initialization(self):
        """ミックスインの初期化テスト"""

        class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        assert hasattr(formatter, "performance_optimizer")
        assert formatter.performance_optimizer is not None

    def test_format_with_optimization_no_log_file(self, sample_execution_result):
        """ログファイルがない場合の最適化フォーマットテスト"""

        class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return f"formatted: {execution_result.success}"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        result = formatter.format_with_optimization(sample_execution_result)
        assert "formatted: False" in result

    def test_format_with_optimization_with_log_file(self, sample_execution_result):
        """ログファイルがある場合の最適化フォーマットテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("test log content\nerror: something failed\n")

            # ExecutionResultにlog_pathを設定
            sample_execution_result.log_path = str(log_file)

            class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
                def format(self, execution_result, **options):
                    return f"formatted: {execution_result.success}"

                def get_format_name(self):
                    return "test"

            formatter = TestFormatter()
            result = formatter.format_with_optimization(sample_execution_result)
            assert "formatted: False" in result

    def test_get_log_file_path_exists(self, sample_execution_result):
        """ログファイルパス取得テスト（ファイル存在）"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("test content")

            sample_execution_result.log_path = str(log_file)

            class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
                def format(self, execution_result, **options):
                    return "test"

                def get_format_name(self):
                    return "test"

            formatter = TestFormatter()
            result_path = formatter._get_log_file_path(sample_execution_result)
            assert result_path == log_file

    def test_get_log_file_path_not_exists(self, sample_execution_result):
        """ログファイルパス取得テスト（ファイル不存在）"""
        sample_execution_result.log_path = "/nonexistent/path.log"

        class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        result_path = formatter._get_log_file_path(sample_execution_result)
        assert result_path is None

    def test_get_log_file_path_no_attribute(self, sample_execution_result):
        """ログファイルパス取得テスト（log_path属性なし）"""
        # log_path属性を削除
        if hasattr(sample_execution_result, "log_path"):
            delattr(sample_execution_result, "log_path")

        class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        result_path = formatter._get_log_file_path(sample_execution_result)
        assert result_path is None

    def test_get_streaming_info_no_log_file(self, sample_execution_result):
        """ストリーミング情報取得テスト（ログファイルなし）"""

        class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        info = formatter.get_streaming_info(sample_execution_result)
        assert info["available"] is False
        assert "ログファイルが見つかりません" in info["reason"]

    def test_get_streaming_info_with_log_file(self, sample_execution_result):
        """ストリーミング情報取得テスト（ログファイルあり）"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("test log content\n" * 1000)  # 大きなファイル

            sample_execution_result.log_path = str(log_file)

            class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
                def format(self, execution_result, **options):
                    return "test"

                def get_format_name(self):
                    return "test"

            formatter = TestFormatter()
            info = formatter.get_streaming_info(sample_execution_result)
            assert info["available"] is True
            assert "file_info" in info
            assert "optimization_flags" in info

    def test_format_with_streaming_fallback(self, sample_execution_result):
        """ストリーミングフォーマットのフォールバックテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("test content")

            sample_execution_result.log_path = str(log_file)

            class TestFormatter(StreamingFormatterMixin, BaseLogFormatter):
                def format(self, execution_result, **options):
                    return "fallback result"

                def get_format_name(self):
                    return "test"

            formatter = TestFormatter()
            result = formatter._format_with_streaming(sample_execution_result, log_file)
            assert result == "fallback result"


class TestStreamingAwareFormatter:
    """StreamingAwareFormatterのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        formatter = StreamingAwareFormatter()
        assert hasattr(formatter, "performance_optimizer")
        assert formatter.performance_optimizer is not None

    def test_format_basic(self, sample_execution_result):
        """基本フォーマットテスト"""
        formatter = StreamingAwareFormatter()
        result = formatter.format(sample_execution_result)
        assert "CI実行結果: 失敗" in result
        assert "実行時間:" in result

    def test_format_success(self):
        """成功時のフォーマットテスト"""
        from ci_helper.core.models import JobResult, WorkflowResult

        job_result = JobResult(
            name="test_job",
            success=True,
            failures=[],
            duration=1.0,
        )

        workflow_result = WorkflowResult(
            name="test_workflow",
            success=True,
            jobs=[job_result],
            duration=1.5,
        )

        execution_result = ExecutionResult(
            success=True,
            total_duration=1.5,
            workflows=[workflow_result],
        )
        formatter = StreamingAwareFormatter()
        result = formatter.format(execution_result)
        assert "CI実行結果: 成功" in result
        assert "1.50秒" in result

    def test_get_format_name(self):
        """フォーマット名取得テスト"""
        formatter = StreamingAwareFormatter()
        assert formatter.get_format_name() == "streaming_base"


class TestChunkedLogProcessor:
    """ChunkedLogProcessorのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        processor = ChunkedLogProcessor()
        assert processor.performance_optimizer is not None

    def test_initialization_with_optimizer(self):
        """最適化インスタンス指定での初期化テスト"""
        from ci_helper.utils.performance_optimizer import PerformanceOptimizer

        optimizer = PerformanceOptimizer()
        processor = ChunkedLogProcessor(optimizer)
        assert processor.performance_optimizer is optimizer

    def test_process_log_chunks(self):
        """ログチャンク処理テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("line1\nline2\nline3\n")

            processor = ChunkedLogProcessor()

            def test_processor(chunk, **options):
                return f"processed: {len(chunk)}"

            results = list(processor.process_log_chunks(log_file, test_processor))
            assert len(results) > 0
            assert all("processed:" in result for result in results)

    def test_process_log_chunks_with_error(self):
        """ログチャンク処理エラーハンドリングテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("line1\nline2\nline3\n")

            processor = ChunkedLogProcessor()

            def error_processor(chunk, **options):
                if "line2" in chunk:
                    raise ValueError("Test error")
                return f"processed: {len(chunk)}"

            # エラーが発生してもプロセッサは続行する
            results = list(processor.process_log_chunks(log_file, error_processor))
            # エラーが発生したチャンクは結果に含まれない
            assert all("processed:" in result for result in results)

    def test_process_log_lines(self):
        """ログ行処理テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("line1\nline2\nline3\nline4\nline5\n")

            processor = ChunkedLogProcessor()

            def line_processor(lines, **options):
                return f"batch: {len(lines)} lines"

            results = list(processor.process_log_lines(log_file, line_processor, batch_size=2))
            assert len(results) > 0
            assert all("batch:" in result for result in results)

    def test_process_log_lines_with_remainder(self):
        """ログ行処理テスト（余りあり）"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_file.write_text("line1\nline2\nline3\n")  # 3行（バッチサイズ2で余り1行）

            processor = ChunkedLogProcessor()

            def line_processor(lines, **options):
                return f"batch: {len(lines)}"

            results = list(processor.process_log_lines(log_file, line_processor, batch_size=2))
            # 2行のバッチと1行のバッチが作られる
            assert len(results) >= 1
            assert any("batch: 1" in result or "batch: 2" in result for result in results)

    def test_extract_failures_streaming(self):
        """ストリーミング失敗抽出テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_content = """
            Starting test...
            Test passed
            ERROR: Something went wrong
            Test failed with assertion error
            FAILURE: Database connection failed
            Test completed
            """
            log_file.write_text(log_content)

            processor = ChunkedLogProcessor()
            failures = list(processor.extract_failures_streaming(log_file))

            # エラーキーワードを含む行が抽出される
            assert len(failures) > 0
            error_messages = [f["message"] for f in failures]
            assert any("ERROR" in msg for msg in error_messages)
            assert any("failed" in msg for msg in error_messages)
            assert any("FAILURE" in msg for msg in error_messages)

    def test_extract_failures_streaming_with_context(self):
        """ストリーミング失敗抽出テスト（コンテキスト付き）"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            log_content = """line1
line2
ERROR: test error
line4
line5"""
            log_file.write_text(log_content)

            processor = ChunkedLogProcessor()
            failures = list(processor.extract_failures_streaming(log_file))

            assert len(failures) > 0
            failure = failures[0]
            assert "ERROR" in failure["message"]
            assert failure["type"] == "error"
            # コンテキストが含まれることを確認
            assert "context_before" in failure
            assert "context_after" in failure


class TestProgressTrackingFormatter:
    """ProgressTrackingFormatterのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        formatter = ProgressTrackingFormatter()
        assert formatter.console is not None

    def test_initialization_with_console(self):
        """コンソール指定での初期化テスト"""
        mock_console = Mock()
        formatter = ProgressTrackingFormatter(mock_console)
        assert formatter.console is mock_console

    def test_format_with_progress_small_file(self, sample_execution_result):
        """小さなファイルでの進行状況フォーマットテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "small.log"
            log_file.write_text("small content")  # 小さなファイル

            sample_execution_result.log_path = str(log_file)

            mock_formatter = Mock()
            mock_formatter.format.return_value = "formatted result"

            formatter = ProgressTrackingFormatter()
            result = formatter.format_with_progress(mock_formatter, sample_execution_result)

            assert result == "formatted result"
            mock_formatter.format.assert_called_once()

    def test_format_with_progress_large_file(self, sample_execution_result):
        """大きなファイルでの進行状況フォーマットテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "large.log"
            # 6MB以上のファイルを作成
            large_content = "x" * (6 * 1024 * 1024)
            log_file.write_text(large_content)

            sample_execution_result.log_path = str(log_file)

            mock_formatter = Mock()
            mock_formatter.format.return_value = "formatted result"

            formatter = ProgressTrackingFormatter()
            result = formatter.format_with_progress(mock_formatter, sample_execution_result)

            assert result == "formatted result"
            mock_formatter.format.assert_called_once()

    def test_format_with_progress_no_log_file(self, sample_execution_result):
        """ログファイルなしでの進行状況フォーマットテスト"""
        mock_formatter = Mock()
        mock_formatter.format.return_value = "formatted result"

        formatter = ProgressTrackingFormatter()
        result = formatter.format_with_progress(mock_formatter, sample_execution_result)

        assert result == "formatted result"
        mock_formatter.format.assert_called_once()

    def test_format_with_progress_error_handling(self, sample_execution_result):
        """進行状況フォーマットエラーハンドリングテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "large.log"
            large_content = "x" * (6 * 1024 * 1024)
            log_file.write_text(large_content)

            sample_execution_result.log_path = str(log_file)

            mock_formatter = Mock()
            mock_formatter.format.side_effect = ValueError("Test error")

            formatter = ProgressTrackingFormatter()

            with pytest.raises(ValueError, match="Test error"):
                formatter.format_with_progress(mock_formatter, sample_execution_result)

    def test_estimate_processing_time(self):
        """処理時間推定テスト"""
        formatter = ProgressTrackingFormatter()

        # 1MBのAI形式
        time_ai = formatter.estimate_processing_time(1024 * 1024, "ai")
        assert time_ai == 2.0

        # 1MBのJSON形式
        time_json = formatter.estimate_processing_time(1024 * 1024, "json")
        assert time_json == 0.5

        # 2MBの人間可読形式
        time_human = formatter.estimate_processing_time(2 * 1024 * 1024, "human")
        assert time_human == 2.0

        # 未知の形式
        time_unknown = formatter.estimate_processing_time(1024 * 1024, "unknown")
        assert time_unknown == 1.0


@pytest.fixture
def sample_execution_result():
    """テスト用のExecutionResultフィクスチャ"""
    from ci_helper.core.models import Failure, FailureType, JobResult, WorkflowResult

    failure = Failure(
        type=FailureType.ASSERTION,
        message="Test assertion failed",
        file_path="test_file.py",
        line_number=42,
    )

    job_result = JobResult(
        name="test_job",
        success=False,
        failures=[failure],
        duration=1.0,
    )

    workflow_result = WorkflowResult(
        name="test_workflow",
        success=False,
        jobs=[job_result],
        duration=2.5,
    )

    return ExecutionResult(
        success=False,
        total_duration=2.5,
        workflows=[workflow_result],
    )
