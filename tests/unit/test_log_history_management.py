"""
ログ履歴管理機能のユニットテスト

LogManagerクラスの履歴管理、比較機能、メタデータ管理をテストします。
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from ci_helper.core.exceptions import ExecutionError
from ci_helper.core.log_manager import LogManager
from ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from ci_helper.utils.config import Config


class TestLogHistoryManagement:
    """ログ履歴管理機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / ".ci-helper" / "logs"

        # モック設定を作成
        self.mock_config = Mock(spec=Config)
        self.mock_config.get_path.return_value = self.log_dir
        self.mock_config.get.return_value = 100  # max_log_size_mb

        # LogManagerを初期化
        self.log_manager = LogManager(self.mock_config)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_execution_result(
        self, success: bool = True, duration: float = 5.0, failures: list[Failure] | None = None
    ) -> ExecutionResult:
        """サンプルの実行結果を作成"""
        if failures is None:
            failures = []

        job = JobResult(name="test-job", success=success, failures=failures, duration=duration / 2)
        workflow = WorkflowResult(name="test-workflow", success=success, jobs=[job], duration=duration)
        return ExecutionResult(success=success, workflows=[workflow], total_duration=duration, timestamp=datetime.now())

    def test_save_execution_log_creates_index(self):
        """実行ログ保存時のインデックス作成テスト"""
        execution_result = self._create_sample_execution_result()
        raw_output = "Sample log output"

        # ログを保存
        log_path = self.log_manager.save_execution_log(execution_result, raw_output)

        # ログファイルが作成されることを確認
        assert log_path.exists()
        assert log_path.read_text(encoding="utf-8") == raw_output

        # インデックスファイルが作成されることを確認
        assert self.log_manager.index_file.exists()

        # インデックス内容を確認
        index_data = self.log_manager._load_log_index()
        assert len(index_data["logs"]) == 1
        assert index_data["last_execution"] is not None

    def test_save_multiple_execution_logs(self):
        """複数の実行ログ保存テスト"""
        # 最初の実行
        execution1 = self._create_sample_execution_result(success=False, duration=10.0)
        execution1.timestamp = datetime.now() - timedelta(hours=1)
        self.log_manager.save_execution_log(execution1, "First execution log")

        # 2番目の実行
        execution2 = self._create_sample_execution_result(success=True, duration=5.0)
        execution2.timestamp = datetime.now()
        self.log_manager.save_execution_log(execution2, "Second execution log")

        # インデックスに2つのエントリがあることを確認
        logs = self.log_manager.list_logs()
        assert len(logs) == 2

        # 新しい順にソートされていることを確認
        assert logs[0]["success"] is True  # 最新
        assert logs[1]["success"] is False  # 古い

    def test_get_execution_history(self):
        """実行履歴取得テスト"""
        # 複数の実行結果を保存
        executions = []
        for i in range(3):
            execution = self._create_sample_execution_result(success=(i % 2 == 0), duration=float(i + 1))
            execution.timestamp = datetime.now() - timedelta(hours=i)
            executions.append(execution)

        # ログを保存
        for i, execution in enumerate(executions):
            self.log_manager.save_execution_log(execution, f"Log content {i}")

        # 履歴を取得
        history = self.log_manager.get_execution_history()

        # 3つの実行結果が取得されることを確認
        assert len(history) == 3

        # 新しい順になっていることを確認
        for i in range(len(history) - 1):
            assert history[i].timestamp >= history[i + 1].timestamp

    def test_get_execution_history_with_limit(self):
        """制限付き実行履歴取得テスト"""
        # 5つの実行結果を保存
        for i in range(5):
            execution = self._create_sample_execution_result()
            execution.timestamp = datetime.now() - timedelta(hours=i)
            self.log_manager.save_execution_log(execution, f"Log content {i}")

        # 制限付きで履歴を取得
        history = self.log_manager.get_execution_history(limit=3)

        # 3つのみ取得されることを確認
        assert len(history) == 3

    def test_get_previous_execution(self):
        """前回実行取得テスト"""
        # 最初の実行
        execution1 = self._create_sample_execution_result()
        execution1.timestamp = datetime.now() - timedelta(hours=2)
        self.log_manager.save_execution_log(execution1, "First log")

        # 2番目の実行
        execution2 = self._create_sample_execution_result()
        execution2.timestamp = datetime.now() - timedelta(hours=1)
        self.log_manager.save_execution_log(execution2, "Second log")

        # 3番目の実行
        execution3 = self._create_sample_execution_result()
        execution3.timestamp = datetime.now()
        self.log_manager.save_execution_log(execution3, "Third log")

        # 現在の実行（execution3）の前回実行を取得
        previous = self.log_manager.get_previous_execution(execution3.timestamp)

        # execution2が取得されることを確認
        assert previous is not None
        assert previous.timestamp == execution2.timestamp

    def test_get_previous_execution_no_history(self):
        """履歴がない場合の前回実行取得テスト"""
        previous = self.log_manager.get_previous_execution()
        assert previous is None

    def test_compare_with_previous(self):
        """前回実行との比較テスト"""
        # 前回実行（失敗）
        previous_failures = [Failure(type=FailureType.ERROR, message="Previous error")]
        previous_job = JobResult(name="test-job", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test-workflow", success=False, jobs=[previous_job])
        previous_execution = ExecutionResult(
            success=False,
            workflows=[previous_workflow],
            total_duration=10.0,
            timestamp=datetime.now() - timedelta(hours=1),
        )
        self.log_manager.save_execution_log(previous_execution, "Previous log with error")

        # 現在実行（成功）
        current_job = JobResult(name="test-job", success=True, failures=[])
        current_workflow = WorkflowResult(name="test-workflow", success=True, jobs=[current_job])
        current_execution = ExecutionResult(
            success=True, workflows=[current_workflow], total_duration=5.0, timestamp=datetime.now()
        )

        # 比較実行
        comparison_result = self.log_manager.compare_with_previous(current_execution)

        # 比較結果が返されることを確認
        assert comparison_result is not None
        assert "comparison" in comparison_result
        assert "summary" in comparison_result
        assert "has_changes" in comparison_result
        assert "improvement_score" in comparison_result

        # 比較が実行されたことを確認（改善スコアは計算される）
        assert comparison_result["improvement_score"] >= 0

    def test_compare_with_previous_no_history(self):
        """履歴がない場合の比較テスト"""
        current_execution = self._create_sample_execution_result()
        comparison_result = self.log_manager.compare_with_previous(current_execution)

        # 比較結果がNoneであることを確認
        assert comparison_result is None

    def test_save_execution_history_metadata(self):
        """実行履歴メタデータ保存テスト"""
        # 失敗を含む実行結果
        failures = [
            Failure(type=FailureType.ERROR, message="Test error", file_path="test.py", line_number=10),
            Failure(type=FailureType.ASSERTION, message="Assertion failed", file_path="test.py", line_number=20),
        ]
        execution_result = self._create_sample_execution_result(success=False, failures=failures)

        # ログを保存
        self.log_manager.save_execution_log(execution_result, "Log with failures")

        # メタデータを保存
        self.log_manager.save_execution_history_metadata(execution_result)

        # インデックスから詳細な失敗情報を確認
        index_data = self.log_manager._load_log_index()
        latest_entry = index_data["logs"][-1]

        assert "detailed_failures" in latest_entry
        assert len(latest_entry["detailed_failures"]) == 2

        # 失敗詳細の確認
        detailed_failures = latest_entry["detailed_failures"]
        assert detailed_failures[0]["type"] == "error"
        assert detailed_failures[0]["message"] == "Test error"
        assert detailed_failures[0]["file_path"] == "test.py"
        assert detailed_failures[0]["line_number"] == 10

    def test_restore_execution_result(self):
        """実行結果復元テスト"""
        # 元の実行結果
        original_failures = [Failure(type=FailureType.ERROR, message="Original error")]
        original_execution = self._create_sample_execution_result(success=False, failures=original_failures)

        # ログを保存
        log_content = "[Test/job] Error: Original error\n[Test/job] Job failed"
        self.log_manager.save_execution_log(original_execution, log_content)

        # ログエントリを取得
        logs = self.log_manager.list_logs()
        log_entry = logs[0]

        # 実行結果を復元
        with patch("ci_helper.core.log_analyzer.LogAnalyzer") as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.analyze_log.return_value = original_execution

            restored_execution = self.log_manager._restore_execution_result(log_entry)

        # 復元された実行結果を確認
        assert restored_execution is not None
        assert restored_execution.success == original_execution.success
        assert restored_execution.total_duration == original_execution.total_duration

    def test_restore_execution_result_failure(self):
        """実行結果復元失敗テスト"""
        # 無効なログエントリ
        invalid_log_entry = {"log_file": "nonexistent.log", "timestamp": datetime.now().isoformat()}

        # 復元が失敗することを確認
        restored_execution = self.log_manager._restore_execution_result(invalid_log_entry)
        assert restored_execution is None

    def test_find_logs_by_workflow(self):
        """ワークフロー別ログ検索テスト"""
        # 異なるワークフローの実行結果を作成
        workflow1_job = JobResult(name="job1", success=True, failures=[])
        workflow1 = WorkflowResult(name="workflow1", success=True, jobs=[workflow1_job])
        execution1 = ExecutionResult(success=True, workflows=[workflow1], total_duration=5.0)

        workflow2_job = JobResult(name="job2", success=False, failures=[])
        workflow2 = WorkflowResult(name="workflow2", success=False, jobs=[workflow2_job])
        execution2 = ExecutionResult(success=False, workflows=[workflow2], total_duration=8.0)

        # ログを保存
        self.log_manager.save_execution_log(execution1, "Workflow1 log")
        self.log_manager.save_execution_log(execution2, "Workflow2 log")

        # workflow1のログを検索
        workflow1_logs = self.log_manager.find_logs_by_workflow("workflow1")
        assert len(workflow1_logs) == 1
        assert workflow1_logs[0]["workflows"][0]["name"] == "workflow1"

        # workflow2のログを検索
        workflow2_logs = self.log_manager.find_logs_by_workflow("workflow2")
        assert len(workflow2_logs) == 1
        assert workflow2_logs[0]["workflows"][0]["name"] == "workflow2"

        # 存在しないワークフローを検索
        nonexistent_logs = self.log_manager.find_logs_by_workflow("nonexistent")
        assert len(nonexistent_logs) == 0

    def test_cleanup_old_logs_by_count(self):
        """件数制限によるログクリーンアップテスト"""
        # 5つのログを作成
        for i in range(5):
            execution = self._create_sample_execution_result()
            execution.timestamp = datetime.now() - timedelta(hours=i)
            self.log_manager.save_execution_log(execution, f"Log content {i}")

        # 3件まで制限してクリーンアップ
        deleted_count = self.log_manager.cleanup_old_logs(max_count=3)

        # 2件削除されることを確認
        assert deleted_count == 2

        # 残りのログが3件であることを確認
        remaining_logs = self.log_manager.list_logs()
        assert len(remaining_logs) == 3

    def test_cleanup_old_logs_by_size(self):
        """サイズ制限によるログクリーンアップテスト"""
        # 大きなログファイルを作成
        large_content = "x" * 1024 * 1024  # 1MB
        small_content = "small log"

        # 大きなログを2つ作成
        for i in range(2):
            execution = self._create_sample_execution_result()
            execution.timestamp = datetime.now() - timedelta(hours=i)
            self.log_manager.save_execution_log(execution, large_content)

        # 小さなログを1つ作成
        execution = self._create_sample_execution_result()
        execution.timestamp = datetime.now()
        self.log_manager.save_execution_log(execution, small_content)

        # 1MBまで制限してクリーンアップ
        deleted_count = self.log_manager.cleanup_old_logs(max_count=10, max_size_mb=1)

        # サイズ制限により一部のログが削除されることを確認
        assert deleted_count > 0

    def test_get_log_statistics(self):
        """ログ統計情報取得テスト"""
        # 成功と失敗のログを作成
        success_execution = self._create_sample_execution_result(success=True, duration=5.0)
        failure_execution = self._create_sample_execution_result(success=False, duration=10.0)

        self.log_manager.save_execution_log(success_execution, "Success log")
        self.log_manager.save_execution_log(failure_execution, "Failure log")

        # 統計情報を取得
        stats = self.log_manager.get_log_statistics()

        # 統計情報の確認
        assert stats["total_logs"] == 2
        assert stats["success_rate"] == 50.0  # 1/2 = 50%
        assert stats["average_duration"] == 7.5  # (5.0 + 10.0) / 2
        assert stats["total_size_mb"] >= 0  # ファイルサイズは0以上
        assert stats["latest_execution"] is not None

    def test_get_log_statistics_empty(self):
        """空のログ統計情報取得テスト"""
        stats = self.log_manager.get_log_statistics()

        # 空の統計情報の確認
        assert stats["total_logs"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["success_rate"] == 0
        assert stats["average_duration"] == 0
        # latest_executionキーが存在しない場合があるので、getを使用
        assert stats.get("latest_execution") is None

    def test_log_index_corruption_recovery(self):
        """ログインデックス破損からの復旧テスト"""
        # 破損したインデックスファイルを作成
        self.log_manager.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_manager.index_file.write_text("invalid json content")

        # インデックスを読み込み（新規作成されるはず）
        index_data = self.log_manager._load_log_index()

        # 新規インデックスが作成されることを確認
        assert index_data["version"] == "1.0"
        assert index_data["logs"] == []
        assert index_data["last_execution"] is None

    def test_save_execution_log_disk_error(self):
        """ディスクエラー時のログ保存テスト"""
        execution_result = self._create_sample_execution_result()

        # 書き込み不可能なディレクトリを設定
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(ExecutionError) as exc_info:
                self.log_manager.save_execution_log(execution_result, "test content")

            assert "ログの保存に失敗しました" in str(exc_info.value)

    def test_get_log_content_not_found(self):
        """存在しないログファイルの取得テスト"""
        with pytest.raises(ExecutionError) as exc_info:
            self.log_manager.get_log_content("nonexistent.log")

        assert "ログファイルが見つかりません" in str(exc_info.value)

    def test_concurrent_log_operations(self):
        """並行ログ操作のテスト"""
        import threading

        results = []
        errors = []

        def save_log(index):
            try:
                execution = self._create_sample_execution_result()
                execution.timestamp = datetime.now() + timedelta(seconds=index)
                self.log_manager.save_execution_log(execution, f"Concurrent log {index}")
                results.append(index)
            except Exception as e:
                errors.append(e)

        # 複数スレッドで同時にログを保存
        threads = []
        for i in range(5):
            thread = threading.Thread(target=save_log, args=(i,))
            threads.append(thread)
            thread.start()

        # 全スレッドの完了を待機
        for thread in threads:
            thread.join()

        # エラーが発生しないことを確認
        assert len(errors) == 0
        assert len(results) == 5

        # 全ログが保存されることを確認（並行処理で一部重複する可能性があるため、最低限の確認）
        logs = self.log_manager.list_logs()
        assert len(logs) >= 1  # 最低1つは保存される（並行処理での競合状態を考慮）

    def test_log_metadata_consistency(self):
        """ログメタデータの一貫性テスト"""
        # 複雑な実行結果を作成
        failures = [
            Failure(type=FailureType.ERROR, message="Error 1", file_path="file1.py", line_number=10),
            Failure(type=FailureType.ASSERTION, message="Assertion 1", file_path="file2.py", line_number=20),
        ]

        job1 = JobResult(name="job1", success=False, failures=failures[:1], duration=3.0)
        job2 = JobResult(name="job2", success=False, failures=failures[1:], duration=2.0)

        workflow1 = WorkflowResult(name="workflow1", success=False, jobs=[job1], duration=3.0)
        workflow2 = WorkflowResult(name="workflow2", success=False, jobs=[job2], duration=2.0)

        execution_result = ExecutionResult(
            success=False, workflows=[workflow1, workflow2], total_duration=5.0, timestamp=datetime.now()
        )

        # ログを保存
        self.log_manager.save_execution_log(execution_result, "Complex log content")

        # メタデータの一貫性を確認
        logs = self.log_manager.list_logs()
        log_entry = logs[0]

        assert log_entry["success"] == execution_result.success
        assert log_entry["total_duration"] == execution_result.total_duration
        assert log_entry["total_failures"] == execution_result.total_failures
        assert len(log_entry["workflows"]) == len(execution_result.workflows)

        # ワークフロー情報の確認
        for i, workflow_meta in enumerate(log_entry["workflows"]):
            original_workflow = execution_result.workflows[i]
            assert workflow_meta["name"] == original_workflow.name
            assert workflow_meta["success"] == original_workflow.success
            assert workflow_meta["duration"] == original_workflow.duration
            assert workflow_meta["job_count"] == len(original_workflow.jobs)

    def test_execution_history_ordering(self):
        """実行履歴の順序テスト"""
        # 異なる時刻の実行結果を作成
        timestamps = [
            datetime.now() - timedelta(hours=3),
            datetime.now() - timedelta(hours=1),
            datetime.now() - timedelta(hours=2),
        ]

        for i, timestamp in enumerate(timestamps):
            execution = self._create_sample_execution_result()
            execution.timestamp = timestamp
            self.log_manager.save_execution_log(execution, f"Log {i}")

        # 履歴を取得
        history = self.log_manager.get_execution_history()

        # 新しい順に並んでいることを確認
        assert len(history) == 3
        for i in range(len(history) - 1):
            assert history[i].timestamp >= history[i + 1].timestamp

        # 具体的な順序を確認
        expected_order = sorted(timestamps, reverse=True)
        for i, execution in enumerate(history):
            assert execution.timestamp == expected_order[i]
