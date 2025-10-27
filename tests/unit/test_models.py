"""
データモデルのユニットテスト

ci-helperのデータ構造（ExecutionResult、Failure、WorkflowResult等）の
検証とプロパティの動作をテストします。
"""

from datetime import datetime

from ci_helper.core.models import (
    AnalysisMetrics,
    ExecutionResult,
    Failure,
    FailureType,
    JobResult,
    LogComparisonResult,
    StepResult,
    WorkflowResult,
)


class TestFailureType:
    """FailureTypeエニュメーションのテスト"""

    def test_failure_type_values(self):
        """失敗タイプの値のテスト"""
        assert FailureType.ERROR.value == "error"
        assert FailureType.ASSERTION.value == "assertion"
        assert FailureType.TIMEOUT.value == "timeout"
        assert FailureType.BUILD_FAILURE.value == "build_failure"
        assert FailureType.TEST_FAILURE.value == "test_failure"
        assert FailureType.UNKNOWN.value == "unknown"

    def test_failure_type_enum_membership(self):
        """失敗タイプのエニュメーションメンバーシップテスト"""
        all_types = list(FailureType)
        assert len(all_types) == 7
        assert FailureType.ERROR in all_types
        assert FailureType.ASSERTION in all_types
        assert FailureType.SYNTAX in all_types


class TestFailure:
    """Failureデータクラスのテスト"""

    def test_failure_creation_minimal(self):
        """最小限のパラメータでのFailure作成テスト"""
        failure = Failure(type=FailureType.ERROR, message="Test error message")

        assert failure.type == FailureType.ERROR
        assert failure.message == "Test error message"
        assert failure.file_path is None
        assert failure.line_number is None
        assert len(failure.context_before) == 0
        assert len(failure.context_after) == 0
        assert failure.stack_trace is None

    def test_failure_creation_full(self):
        """全パラメータでのFailure作成テスト"""
        context_before = ["line 1", "line 2"]
        context_after = ["line 4", "line 5"]
        stack_trace = "Traceback (most recent call last):\n  File test.py, line 3"

        failure = Failure(
            type=FailureType.ASSERTION,
            message="Assertion failed",
            file_path="test.py",
            line_number=3,
            context_before=context_before,
            context_after=context_after,
            stack_trace=stack_trace,
        )

        assert failure.type == FailureType.ASSERTION
        assert failure.message == "Assertion failed"
        assert failure.file_path == "test.py"
        assert failure.line_number == 3
        assert failure.context_before == context_before
        assert failure.context_after == context_after
        assert failure.stack_trace == stack_trace

    def test_failure_context_mutability(self):
        """Failureのコンテキストリストの可変性テスト"""
        context_before = ["line 1", "line 2"]
        failure = Failure(type=FailureType.ERROR, message="Test", context_before=context_before)

        # 元のリストを変更するとFailureオブジェクトにも影響することを確認
        # （dataclassはデフォルトでリストのコピーを作らない）
        context_before.append("line 3")
        assert len(failure.context_before) == 3


class TestStepResult:
    """StepResultデータクラスのテスト"""

    def test_step_result_creation(self):
        """StepResult作成テスト"""
        step = StepResult(name="Test Step", success=True, duration=5.2, output="Step completed successfully")

        assert step.name == "Test Step"
        assert step.success is True
        assert step.duration == 5.2
        assert step.output == "Step completed successfully"

    def test_step_result_default_output(self):
        """StepResultのデフォルト出力テスト"""
        step = StepResult(name="Test Step", success=False, duration=1.0)

        assert step.output == ""


class TestJobResult:
    """JobResultデータクラスのテスト"""

    def test_job_result_creation_minimal(self):
        """最小限のパラメータでのJobResult作成テスト"""
        job = JobResult(name="test-job", success=True)

        assert job.name == "test-job"
        assert job.success is True
        assert len(job.failures) == 0
        assert len(job.steps) == 0
        assert job.duration == 0.0

    def test_job_result_creation_with_failures_and_steps(self):
        """失敗とステップを含むJobResult作成テスト"""
        failures = [
            Failure(type=FailureType.ERROR, message="Error 1"),
            Failure(type=FailureType.ASSERTION, message="Assertion failed"),
        ]

        steps = [
            StepResult(name="Step 1", success=True, duration=2.0),
            StepResult(name="Step 2", success=False, duration=1.5),
        ]

        job = JobResult(name="test-job", success=False, failures=failures, steps=steps, duration=3.5)

        assert job.name == "test-job"
        assert job.success is False
        assert len(job.failures) == 2
        assert len(job.steps) == 2
        assert job.duration == 3.5


class TestWorkflowResult:
    """WorkflowResultデータクラスのテスト"""

    def test_workflow_result_creation_minimal(self):
        """最小限のパラメータでのWorkflowResult作成テスト"""
        workflow = WorkflowResult(name="test-workflow", success=True)

        assert workflow.name == "test-workflow"
        assert workflow.success is True
        assert len(workflow.jobs) == 0
        assert workflow.duration == 0.0

    def test_workflow_result_creation_with_jobs(self):
        """ジョブを含むWorkflowResult作成テスト"""
        jobs = [JobResult(name="job1", success=True, duration=5.0), JobResult(name="job2", success=False, duration=3.0)]

        workflow = WorkflowResult(name="test-workflow", success=False, jobs=jobs, duration=8.0)

        assert workflow.name == "test-workflow"
        assert workflow.success is False
        assert len(workflow.jobs) == 2
        assert workflow.duration == 8.0


class TestExecutionResult:
    """ExecutionResultデータクラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        # テスト用のサンプルデータを作成
        self.failure1 = Failure(type=FailureType.ERROR, message="Error 1")
        self.failure2 = Failure(type=FailureType.ASSERTION, message="Assertion failed")

        self.successful_job = JobResult(name="success-job", success=True, duration=2.0)
        self.failed_job = JobResult(
            name="failed-job", success=False, failures=[self.failure1, self.failure2], duration=3.0
        )

        self.successful_workflow = WorkflowResult(
            name="success-workflow", success=True, jobs=[self.successful_job], duration=2.0
        )

        self.failed_workflow = WorkflowResult(
            name="failed-workflow", success=False, jobs=[self.failed_job], duration=3.0
        )

    def test_execution_result_creation(self):
        """ExecutionResult作成テスト"""
        workflows = [self.successful_workflow, self.failed_workflow]

        result = ExecutionResult(success=False, workflows=workflows, total_duration=5.0)

        assert result.success is False
        assert len(result.workflows) == 2
        assert result.total_duration == 5.0
        assert isinstance(result.timestamp, datetime)

    def test_execution_result_custom_timestamp(self):
        """カスタムタイムスタンプでのExecutionResult作成テスト"""
        custom_timestamp = datetime(2024, 1, 1, 12, 0, 0)

        result = ExecutionResult(success=True, workflows=[], total_duration=0.0, timestamp=custom_timestamp)

        assert result.timestamp == custom_timestamp

    def test_total_failures_property(self):
        """total_failuresプロパティのテスト"""
        workflows = [self.successful_workflow, self.failed_workflow]
        result = ExecutionResult(success=False, workflows=workflows, total_duration=5.0)

        # failed_jobには2つの失敗がある
        assert result.total_failures == 2

    def test_total_failures_property_no_failures(self):
        """失敗がない場合のtotal_failuresプロパティのテスト"""
        result = ExecutionResult(success=True, workflows=[self.successful_workflow], total_duration=2.0)

        assert result.total_failures == 0

    def test_failed_workflows_property(self):
        """failed_workflowsプロパティのテスト"""
        workflows = [self.successful_workflow, self.failed_workflow]
        result = ExecutionResult(success=False, workflows=workflows, total_duration=5.0)

        failed_workflows = result.failed_workflows
        assert len(failed_workflows) == 1
        assert failed_workflows[0].name == "failed-workflow"

    def test_failed_jobs_property(self):
        """failed_jobsプロパティのテスト"""
        workflows = [self.successful_workflow, self.failed_workflow]
        result = ExecutionResult(success=False, workflows=workflows, total_duration=5.0)

        failed_jobs = result.failed_jobs
        assert len(failed_jobs) == 1
        assert failed_jobs[0].name == "failed-job"

    def test_all_failures_property(self):
        """all_failuresプロパティのテスト"""
        workflows = [self.successful_workflow, self.failed_workflow]
        result = ExecutionResult(success=False, workflows=workflows, total_duration=5.0)

        all_failures = result.all_failures
        assert len(all_failures) == 2

        messages = [f.message for f in all_failures]
        assert "Error 1" in messages
        assert "Assertion failed" in messages

    def test_execution_result_with_log_path(self):
        """ログパス付きのExecutionResultテスト"""
        result = ExecutionResult(success=True, workflows=[], total_duration=0.0, log_path="/path/to/log.txt")

        assert result.log_path == "/path/to/log.txt"


class TestLogComparisonResult:
    """LogComparisonResultデータクラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.current_execution = ExecutionResult(success=False, workflows=[], total_duration=5.0)

        self.previous_execution = ExecutionResult(success=True, workflows=[], total_duration=3.0)

    def test_log_comparison_result_creation(self):
        """LogComparisonResult作成テスト"""
        new_errors = [Failure(type=FailureType.ERROR, message="New error")]
        resolved_errors = [Failure(type=FailureType.ERROR, message="Resolved error")]
        persistent_errors = [Failure(type=FailureType.ERROR, message="Persistent error")]

        comparison = LogComparisonResult(
            current_execution=self.current_execution,
            previous_execution=self.previous_execution,
            new_errors=new_errors,
            resolved_errors=resolved_errors,
            persistent_errors=persistent_errors,
        )

        assert comparison.current_execution == self.current_execution
        assert comparison.previous_execution == self.previous_execution
        assert len(comparison.new_errors) == 1
        assert len(comparison.resolved_errors) == 1
        assert len(comparison.persistent_errors) == 1

    def test_has_changes_property_with_changes(self):
        """変更がある場合のhas_changesプロパティテスト"""
        comparison = LogComparisonResult(
            current_execution=self.current_execution,
            previous_execution=self.previous_execution,
            new_errors=[Failure(type=FailureType.ERROR, message="New error")],
        )

        assert comparison.has_changes is True

    def test_has_changes_property_no_changes(self):
        """変更がない場合のhas_changesプロパティテスト"""
        comparison = LogComparisonResult(
            current_execution=self.current_execution, previous_execution=self.previous_execution
        )

        assert comparison.has_changes is False

    def test_improvement_score_no_previous(self):
        """前回実行がない場合のimprovement_scoreテスト"""
        comparison = LogComparisonResult(current_execution=self.current_execution, previous_execution=None)

        # 現在の実行が失敗している場合は0.0
        assert comparison.improvement_score == 0.0

        # 現在の実行が成功している場合は1.0
        successful_execution = ExecutionResult(success=True, workflows=[], total_duration=1.0)
        comparison_success = LogComparisonResult(current_execution=successful_execution, previous_execution=None)
        assert comparison_success.improvement_score == 1.0

    def test_improvement_score_with_previous(self):
        """前回実行がある場合のimprovement_scoreテスト"""
        # 前回: 4つの失敗、現在: 2つの失敗 → 50%改善
        prev_failures = [Failure(type=FailureType.ERROR, message=f"Error {i}") for i in range(4)]
        curr_failures = [Failure(type=FailureType.ERROR, message=f"Error {i}") for i in range(2)]

        prev_job = JobResult(name="test", success=False, failures=prev_failures)
        curr_job = JobResult(name="test", success=False, failures=curr_failures)

        prev_workflow = WorkflowResult(name="test", success=False, jobs=[prev_job])
        curr_workflow = WorkflowResult(name="test", success=False, jobs=[curr_job])

        previous_execution = ExecutionResult(success=False, workflows=[prev_workflow], total_duration=5.0)
        current_execution = ExecutionResult(success=False, workflows=[curr_workflow], total_duration=3.0)

        comparison = LogComparisonResult(current_execution=current_execution, previous_execution=previous_execution)

        # 4 → 2 失敗なので、改善スコアは 1 - (2/4) = 0.5
        assert comparison.improvement_score == 0.5

    def test_improvement_score_perfect_improvement(self):
        """完全な改善のimprovement_scoreテスト"""
        # 前回: 失敗あり、現在: 失敗なし
        prev_failures = [Failure(type=FailureType.ERROR, message="Error")]
        prev_job = JobResult(name="test", success=False, failures=prev_failures)
        prev_workflow = WorkflowResult(name="test", success=False, jobs=[prev_job])
        previous_execution = ExecutionResult(success=False, workflows=[prev_workflow], total_duration=5.0)

        curr_job = JobResult(name="test", success=True, failures=[])
        curr_workflow = WorkflowResult(name="test", success=True, jobs=[curr_job])
        current_execution = ExecutionResult(success=True, workflows=[curr_workflow], total_duration=3.0)

        comparison = LogComparisonResult(current_execution=current_execution, previous_execution=previous_execution)

        # 完全な改善なので1.0
        assert comparison.improvement_score == 1.0


class TestAnalysisMetrics:
    """AnalysisMetricsデータクラスのテスト"""

    def test_analysis_metrics_creation(self):
        """AnalysisMetrics作成テスト"""
        failure_types = {FailureType.ERROR: 2, FailureType.ASSERTION: 1}

        metrics = AnalysisMetrics(
            total_workflows=2,
            total_jobs=4,
            total_steps=8,
            total_failures=3,
            success_rate=75.0,
            average_duration=5.5,
            failure_types=failure_types,
        )

        assert metrics.total_workflows == 2
        assert metrics.total_jobs == 4
        assert metrics.total_steps == 8
        assert metrics.total_failures == 3
        assert metrics.success_rate == 75.0
        assert metrics.average_duration == 5.5
        assert metrics.failure_types[FailureType.ERROR] == 2
        assert metrics.failure_types[FailureType.ASSERTION] == 1

    def test_from_execution_result_successful(self):
        """成功した実行結果からのAnalysisMetrics生成テスト"""
        steps = [
            StepResult(name="step1", success=True, duration=1.0),
            StepResult(name="step2", success=True, duration=2.0),
        ]

        job = JobResult(name="job1", success=True, steps=steps, duration=3.0)
        workflow = WorkflowResult(name="workflow1", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(success=True, workflows=[workflow], total_duration=3.0)

        metrics = AnalysisMetrics.from_execution_result(execution_result)

        assert metrics.total_workflows == 1
        assert metrics.total_jobs == 1
        assert metrics.total_steps == 2
        assert metrics.total_failures == 0
        assert metrics.success_rate == 100.0
        assert metrics.average_duration == 3.0

    def test_from_execution_result_with_failures(self):
        """失敗を含む実行結果からのAnalysisMetrics生成テスト"""
        failures = [
            Failure(type=FailureType.ERROR, message="Error 1"),
            Failure(type=FailureType.ASSERTION, message="Assertion failed"),
            Failure(type=FailureType.ERROR, message="Error 2"),
        ]

        successful_job = JobResult(name="job1", success=True, duration=2.0)
        failed_job = JobResult(name="job2", success=False, failures=failures, duration=3.0)

        workflow = WorkflowResult(name="workflow1", success=False, jobs=[successful_job, failed_job], duration=5.0)
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=5.0)

        metrics = AnalysisMetrics.from_execution_result(execution_result)

        assert metrics.total_workflows == 1
        assert metrics.total_jobs == 2
        assert metrics.total_failures == 3
        assert metrics.success_rate == 50.0  # 1/2 jobs successful
        assert metrics.average_duration == 5.0
        assert metrics.failure_types[FailureType.ERROR] == 2
        assert metrics.failure_types[FailureType.ASSERTION] == 1

    def test_from_execution_result_empty(self):
        """空の実行結果からのAnalysisMetrics生成テスト"""
        execution_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        metrics = AnalysisMetrics.from_execution_result(execution_result)

        assert metrics.total_workflows == 0
        assert metrics.total_jobs == 0
        assert metrics.total_steps == 0
        assert metrics.total_failures == 0
        assert metrics.success_rate == 100.0  # ジョブがない場合は100%
        assert metrics.average_duration == 0.0
        assert len(metrics.failure_types) == 0

    def test_analysis_metrics_default_failure_types(self):
        """デフォルトのfailure_typesでのAnalysisMetrics作成テスト"""
        metrics = AnalysisMetrics(
            total_workflows=1, total_jobs=1, total_steps=1, total_failures=0, success_rate=100.0, average_duration=1.0
        )

        assert len(metrics.failure_types) == 0
