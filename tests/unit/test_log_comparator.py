"""
ログ比較機能のユニットテスト

LogComparatorクラスの差分検出、分類機能、履歴管理機能をテストします。
"""

import json

from ci_helper.core.log_comparator import LogComparator
from ci_helper.core.models import (
    ExecutionResult,
    Failure,
    FailureType,
    JobResult,
    LogComparisonResult,
    WorkflowResult,
)


class TestLogComparator:
    """LogComparatorクラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.comparator = LogComparator()

    def test_compare_executions_initial_run(self):
        """初回実行の比較テスト（前回実行がない場合）"""
        # 現在の実行結果（失敗あり）
        current_failures = [
            Failure(type=FailureType.ERROR, message="Initial error", file_path="test.py", line_number=10)
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=5.0)

        # 前回実行なしで比較
        comparison = self.comparator.compare_executions(current_result, None)

        # 初回実行の場合の検証
        assert isinstance(comparison, LogComparisonResult)
        assert comparison.current_execution == current_result
        assert comparison.previous_execution is None
        assert len(comparison.new_errors) == 1
        assert len(comparison.resolved_errors) == 0
        assert len(comparison.persistent_errors) == 0
        assert comparison.new_errors[0].message == "Initial error"

    def test_compare_executions_with_previous(self):
        """前回実行との比較テスト"""
        # 前回の実行結果
        previous_failures = [
            Failure(type=FailureType.ERROR, message="Old error", file_path="old.py", line_number=5),
            Failure(type=FailureType.ASSERTION, message="Persistent error", file_path="test.py", line_number=20),
        ]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在の実行結果
        current_failures = [
            Failure(type=FailureType.ERROR, message="New error", file_path="new.py", line_number=15),
            Failure(type=FailureType.ASSERTION, message="Persistent error", file_path="test.py", line_number=20),
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        # 比較実行
        comparison = self.comparator.compare_executions(current_result, previous_result)

        # 結果検証
        assert comparison.current_execution == current_result
        assert comparison.previous_execution == previous_result

        # 新規エラーの検証
        assert len(comparison.new_errors) == 1
        assert comparison.new_errors[0].message == "New error"

        # 解決済みエラーの検証
        assert len(comparison.resolved_errors) == 1
        assert comparison.resolved_errors[0].message == "Old error"

        # 継続エラーの検証
        assert len(comparison.persistent_errors) == 1
        assert comparison.persistent_errors[0].message == "Persistent error"

    def test_compare_executions_all_resolved(self):
        """全エラーが解決された場合のテスト"""
        # 前回の実行結果（失敗あり）
        previous_failures = [
            Failure(type=FailureType.ERROR, message="Error 1", file_path="test.py", line_number=10),
            Failure(type=FailureType.ERROR, message="Error 2", file_path="test.py", line_number=20),
        ]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在の実行結果（成功）
        current_job = JobResult(name="test", success=True, failures=[])
        current_workflow = WorkflowResult(name="test", success=True, jobs=[current_job])
        current_result = ExecutionResult(success=True, workflows=[current_workflow], total_duration=5.0)

        # 比較実行
        comparison = self.comparator.compare_executions(current_result, previous_result)

        # 全エラーが解決されていることを確認
        assert len(comparison.new_errors) == 0
        assert len(comparison.resolved_errors) == 2
        assert len(comparison.persistent_errors) == 0
        assert comparison.has_changes is True

    def test_compare_executions_all_new_errors(self):
        """全て新規エラーの場合のテスト"""
        # 前回の実行結果（成功）
        previous_job = JobResult(name="test", success=True, failures=[])
        previous_workflow = WorkflowResult(name="test", success=True, jobs=[previous_job])
        previous_result = ExecutionResult(success=True, workflows=[previous_workflow], total_duration=5.0)

        # 現在の実行結果（新規失敗）
        current_failures = [
            Failure(type=FailureType.ERROR, message="New error 1", file_path="test.py", line_number=10),
            Failure(type=FailureType.ERROR, message="New error 2", file_path="test.py", line_number=20),
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        # 比較実行
        comparison = self.comparator.compare_executions(current_result, previous_result)

        # 全て新規エラーであることを確認
        assert len(comparison.new_errors) == 2
        assert len(comparison.resolved_errors) == 0
        assert len(comparison.persistent_errors) == 0
        assert comparison.has_changes is True

    def test_create_failure_key(self):
        """失敗の比較用キー生成テスト"""
        failure = Failure(
            type=FailureType.ERROR,
            message="  Test error message  ",  # 前後に空白
            file_path="src/test.py",
            line_number=42,
        )

        key = self.comparator._create_failure_key(failure)
        expected_key = ("error", "Test error message", "src/test.py", 42)

        assert key == expected_key

    def test_create_failure_key_no_location(self):
        """場所情報がない失敗のキー生成テスト"""
        failure = Failure(type=FailureType.ASSERTION, message="Assertion failed", file_path=None, line_number=None)

        key = self.comparator._create_failure_key(failure)
        expected_key = ("assertion", "Assertion failed", None, None)

        assert key == expected_key

    def test_generate_diff_summary_initial(self):
        """初回実行の差分サマリー生成テスト"""
        # 初回実行結果
        failures = [Failure(type=FailureType.ERROR, message="Initial error")]
        job = JobResult(name="test", success=False, failures=failures)
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        current_result = ExecutionResult(success=False, workflows=[workflow], total_duration=5.0)

        comparison = LogComparisonResult(
            current_execution=current_result,
            previous_execution=None,
            new_errors=failures,
            resolved_errors=[],
            persistent_errors=[],
        )

        summary = self.comparator.generate_diff_summary(comparison)

        # 初回実行の検証
        assert summary["comparison_type"] == "initial"
        assert summary["current_status"] == "failure"
        assert summary["previous_status"] is None
        assert summary["has_changes"] is True
        assert summary["error_counts"]["current"] == 1
        assert summary["error_counts"]["previous"] == 0
        assert summary["error_counts"]["new"] == 1
        assert summary["error_counts"]["resolved"] == 0

    def test_generate_diff_summary_comparison(self):
        """比較実行の差分サマリー生成テスト"""
        # 前回実行結果
        previous_failures = [Failure(type=FailureType.ERROR, message="Old error")]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在実行結果
        current_failures = [Failure(type=FailureType.ERROR, message="New error")]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        comparison = LogComparisonResult(
            current_execution=current_result,
            previous_execution=previous_result,
            new_errors=current_failures,
            resolved_errors=previous_failures,
            persistent_errors=[],
        )

        summary = self.comparator.generate_diff_summary(comparison)

        # 比較実行の検証
        assert summary["comparison_type"] == "comparison"
        assert summary["current_status"] == "failure"
        assert summary["previous_status"] == "failure"
        assert summary["error_counts"]["net_change"] == 0  # 1つ追加、1つ削除
        assert summary["performance"]["time_change"] == -2.0  # 2秒短縮
        assert summary["performance"]["time_change_percent"] == -20.0  # 20%短縮

    def test_analyze_workflow_changes(self):
        """ワークフロー別変化分析テスト"""
        # 前回実行結果（2つのワークフロー）
        previous_workflow1 = WorkflowResult(name="workflow1", success=True, jobs=[], duration=5.0)
        previous_workflow2 = WorkflowResult(name="workflow2", success=False, jobs=[], duration=3.0)
        previous_result = ExecutionResult(
            success=False, workflows=[previous_workflow1, previous_workflow2], total_duration=8.0
        )

        # 現在実行結果（1つは修正、1つは新規、1つは削除）
        current_workflow1 = WorkflowResult(name="workflow1", success=True, jobs=[], duration=4.0)
        current_workflow2 = WorkflowResult(name="workflow2", success=True, jobs=[], duration=2.0)  # 修正
        current_workflow3 = WorkflowResult(name="workflow3", success=False, jobs=[], duration=6.0)  # 新規
        current_result = ExecutionResult(
            success=False, workflows=[current_workflow1, current_workflow2, current_workflow3], total_duration=12.0
        )

        comparison = LogComparisonResult(
            current_execution=current_result, previous_execution=previous_result, new_errors=[], resolved_errors=[]
        )

        workflow_changes = self.comparator._analyze_workflow_changes(comparison)

        # ワークフロー変化の検証
        assert workflow_changes["workflow1"]["status"] == "unchanged"  # 成功のまま
        assert workflow_changes["workflow2"]["status"] == "fixed"  # 失敗→成功
        assert workflow_changes["workflow3"]["status"] == "new"  # 新規

    def test_analyze_failure_types(self):
        """失敗タイプ別分析テスト"""
        # 前回実行結果
        previous_failures = [
            Failure(type=FailureType.ERROR, message="Error 1"),
            Failure(type=FailureType.ERROR, message="Error 2"),
            Failure(type=FailureType.ASSERTION, message="Assertion 1"),
        ]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在実行結果
        current_failures = [
            Failure(type=FailureType.ERROR, message="Error 1"),  # 継続
            Failure(type=FailureType.TIMEOUT, message="Timeout 1"),  # 新規
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        comparison = LogComparisonResult(
            current_execution=current_result,
            previous_execution=previous_result,
            new_errors=[Failure(type=FailureType.TIMEOUT, message="Timeout 1")],
            resolved_errors=[
                Failure(type=FailureType.ERROR, message="Error 2"),
                Failure(type=FailureType.ASSERTION, message="Assertion 1"),
            ],
            persistent_errors=[Failure(type=FailureType.ERROR, message="Error 1")],
        )

        failure_analysis = self.comparator._analyze_failure_types(comparison)

        # 失敗タイプ分析の検証
        assert failure_analysis["current_types"]["error"] == 1
        assert failure_analysis["current_types"]["timeout"] == 1
        assert failure_analysis["previous_types"]["error"] == 2
        assert failure_analysis["previous_types"]["assertion"] == 1
        assert failure_analysis["new_error_types"]["timeout"] == 1
        assert failure_analysis["resolved_error_types"]["error"] == 1
        assert failure_analysis["resolved_error_types"]["assertion"] == 1

    def test_format_diff_display_json(self):
        """JSON形式の差分表示テスト"""
        # テスト用の比較結果を作成
        current_failures = [
            Failure(type=FailureType.ERROR, message="Current error", file_path="test.py", line_number=10)
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=5.0)

        comparison = LogComparisonResult(
            current_execution=current_result,
            previous_execution=None,
            new_errors=current_failures,
            resolved_errors=[],
            persistent_errors=[],
        )

        json_output = self.comparator.format_diff_display(comparison, "json")

        # JSONとして解析可能であることを確認
        parsed_json = json.loads(json_output)
        assert "summary" in parsed_json
        assert "new_errors" in parsed_json
        assert "resolved_errors" in parsed_json
        assert "persistent_errors" in parsed_json

        # 新規エラーの詳細が含まれることを確認
        assert len(parsed_json["new_errors"]) == 1
        new_error = parsed_json["new_errors"][0]
        assert new_error["type"] == "error"
        assert new_error["message"] == "Current error"
        assert new_error["file_path"] == "test.py"
        assert new_error["line_number"] == 10

    def test_format_diff_display_markdown(self):
        """Markdown形式の差分表示テスト"""
        # 新規エラーと解決済みエラーを含む比較結果
        new_error = Failure(type=FailureType.ERROR, message="New error", file_path="new.py", line_number=15)
        resolved_error = Failure(
            type=FailureType.ASSERTION, message="Resolved error", file_path="old.py", line_number=25
        )

        current_job = JobResult(name="test", success=False, failures=[new_error])
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=5.0)

        previous_job = JobResult(name="test", success=False, failures=[resolved_error])
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=8.0)

        comparison = LogComparisonResult(
            current_execution=current_result,
            previous_execution=previous_result,
            new_errors=[new_error],
            resolved_errors=[resolved_error],
            persistent_errors=[],
        )

        markdown_output = self.comparator.format_diff_display(comparison, "markdown")

        # Markdownの構造を確認
        assert "# 実行結果の比較" in markdown_output
        assert "## 概要" in markdown_output
        assert "## エラー数の変化" in markdown_output
        assert "## 新規エラー" in markdown_output
        assert "## 解決済みエラー" in markdown_output

        # エラー詳細が含まれることを確認
        assert "New error" in markdown_output
        assert "new.py:15" in markdown_output
        assert "Resolved error" in markdown_output
        assert "old.py:25" in markdown_output

    def test_format_diff_display_table(self):
        """テーブル形式の差分表示テスト"""
        current_job = JobResult(name="test", success=True, failures=[])
        current_workflow = WorkflowResult(name="test", success=True, jobs=[current_job])
        current_result = ExecutionResult(success=True, workflows=[current_workflow], total_duration=5.0)

        comparison = LogComparisonResult(
            current_execution=current_result, previous_execution=None, new_errors=[], resolved_errors=[]
        )

        table_output = self.comparator.format_diff_display(comparison, "table")

        # テーブル出力が文字列として返されることを確認
        assert isinstance(table_output, str)
        assert len(table_output) > 0

    def test_log_comparison_result_properties(self):
        """LogComparisonResultのプロパティテスト"""
        # 変更がある場合
        new_error = Failure(type=FailureType.ERROR, message="New error")
        current_result = ExecutionResult(success=False, workflows=[], total_duration=5.0)

        comparison_with_changes = LogComparisonResult(
            current_execution=current_result, previous_execution=None, new_errors=[new_error]
        )

        assert comparison_with_changes.has_changes is True

        # 変更がない場合
        comparison_no_changes = LogComparisonResult(
            current_execution=current_result, previous_execution=None, new_errors=[], resolved_errors=[]
        )

        assert comparison_no_changes.has_changes is False

    def test_improvement_score_calculation(self):
        """改善スコアの計算テスト"""
        # 前回実行結果（2つの失敗）
        previous_failures = [
            Failure(type=FailureType.ERROR, message="Error 1"),
            Failure(type=FailureType.ERROR, message="Error 2"),
        ]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在実行結果（1つの失敗）
        current_failures = [Failure(type=FailureType.ERROR, message="Error 1")]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        comparison = LogComparisonResult(
            current_execution=current_result, previous_execution=previous_result, new_errors=[], resolved_errors=[]
        )

        # 改善スコア：失敗数が2→1なので0.5の改善
        assert comparison.improvement_score == 0.5

        # 完全成功の場合
        success_result = ExecutionResult(success=True, workflows=[], total_duration=5.0)
        success_comparison = LogComparisonResult(
            current_execution=success_result, previous_execution=previous_result, new_errors=[], resolved_errors=[]
        )

        assert success_comparison.improvement_score == 1.0

    def test_improvement_score_no_previous(self):
        """前回実行がない場合の改善スコアテスト"""
        # 成功の場合
        success_result = ExecutionResult(success=True, workflows=[], total_duration=5.0)
        success_comparison = LogComparisonResult(
            current_execution=success_result, previous_execution=None, new_errors=[], resolved_errors=[]
        )

        assert success_comparison.improvement_score == 1.0

        # 失敗の場合
        failure_result = ExecutionResult(success=False, workflows=[], total_duration=5.0)
        failure_comparison = LogComparisonResult(
            current_execution=failure_result, previous_execution=None, new_errors=[], resolved_errors=[]
        )

        assert failure_comparison.improvement_score == 0.0

    def test_multiple_workflows_comparison(self):
        """複数ワークフローの比較テスト"""
        # 前回実行結果
        previous_workflow1 = WorkflowResult(name="workflow1", success=True, jobs=[], duration=3.0)
        previous_workflow2 = WorkflowResult(name="workflow2", success=False, jobs=[], duration=5.0)
        previous_result = ExecutionResult(
            success=False, workflows=[previous_workflow1, previous_workflow2], total_duration=8.0
        )

        # 現在実行結果
        current_workflow1 = WorkflowResult(name="workflow1", success=False, jobs=[], duration=4.0)  # 悪化
        current_workflow2 = WorkflowResult(name="workflow2", success=True, jobs=[], duration=3.0)  # 改善
        current_result = ExecutionResult(
            success=False, workflows=[current_workflow1, current_workflow2], total_duration=7.0
        )

        comparison = self.comparator.compare_executions(current_result, previous_result)
        summary = self.comparator.generate_diff_summary(comparison)

        # ワークフロー変化の確認
        workflow_changes = summary["workflow_changes"]
        assert workflow_changes["workflow1"]["status"] == "broken"  # 成功→失敗
        assert workflow_changes["workflow2"]["status"] == "fixed"  # 失敗→成功

    def test_edge_case_empty_executions(self):
        """空の実行結果の比較テスト"""
        # 空の実行結果
        empty_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        comparison = self.comparator.compare_executions(empty_result, empty_result)

        assert len(comparison.new_errors) == 0
        assert len(comparison.resolved_errors) == 0
        assert len(comparison.persistent_errors) == 0
        assert comparison.has_changes is False

    def test_edge_case_identical_failures(self):
        """同一失敗の比較テスト"""
        # 同じ失敗を持つ実行結果
        identical_failure = Failure(type=FailureType.ERROR, message="Same error", file_path="test.py", line_number=10)

        job1 = JobResult(name="test", success=False, failures=[identical_failure])
        workflow1 = WorkflowResult(name="test", success=False, jobs=[job1])
        result1 = ExecutionResult(success=False, workflows=[workflow1], total_duration=5.0)

        job2 = JobResult(name="test", success=False, failures=[identical_failure])
        workflow2 = WorkflowResult(name="test", success=False, jobs=[job2])
        result2 = ExecutionResult(success=False, workflows=[workflow2], total_duration=5.0)

        comparison = self.comparator.compare_executions(result1, result2)

        # 同一失敗は継続エラーとして分類される
        assert len(comparison.new_errors) == 0
        assert len(comparison.resolved_errors) == 0
        assert len(comparison.persistent_errors) == 1
        assert comparison.persistent_errors[0].message == "Same error"

    def test_performance_metrics_in_summary(self):
        """サマリー内のパフォーマンスメトリクステスト"""
        # 前回実行結果（10秒）
        previous_result = ExecutionResult(success=True, workflows=[], total_duration=10.0)

        # 現在実行結果（5秒）
        current_result = ExecutionResult(success=True, workflows=[], total_duration=5.0)

        comparison = LogComparisonResult(
            current_execution=current_result, previous_execution=previous_result, new_errors=[], resolved_errors=[]
        )

        summary = self.comparator.generate_diff_summary(comparison)

        # パフォーマンス改善の確認
        performance = summary["performance"]
        assert performance["current_duration"] == 5.0
        assert performance["previous_duration"] == 10.0
        assert performance["time_change"] == -5.0  # 5秒短縮
        assert performance["time_change_percent"] == -50.0  # 50%短縮

    def test_zero_duration_handling(self):
        """実行時間が0の場合の処理テスト"""
        # 前回実行時間が0の場合
        previous_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)
        current_result = ExecutionResult(success=True, workflows=[], total_duration=5.0)

        comparison = LogComparisonResult(
            current_execution=current_result, previous_execution=previous_result, new_errors=[], resolved_errors=[]
        )

        summary = self.comparator.generate_diff_summary(comparison)

        # ゼロ除算エラーが発生しないことを確認
        performance = summary["performance"]
        assert performance["time_change_percent"] == 0  # ゼロ除算回避
