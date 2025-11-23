"""ci-helperのデータモデル定義

実行結果、失敗情報、設定などのデータ構造を定義します。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FailureType(Enum):
    """失敗の種類"""

    ERROR = "error"
    ASSERTION = "assertion"
    TIMEOUT = "timeout"
    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    SYNTAX = "syntax"
    UNKNOWN = "unknown"


@dataclass
class Failure:
    """失敗情報を表すデータクラス"""

    type: FailureType
    message: str
    file_path: str | None = None
    line_number: int | None = None
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    stack_trace: str | None = None


@dataclass
class StepResult:
    """ワークフローステップの実行結果"""

    name: str
    success: bool
    duration: float
    output: str = ""


@dataclass
class JobResult:
    """ワークフロージョブの実行結果"""

    name: str
    success: bool
    failures: list[Failure] = field(default_factory=list)
    steps: list[StepResult] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class WorkflowResult:
    """ワークフローの実行結果"""

    name: str
    success: bool
    jobs: list[JobResult] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class ExecutionResult:
    """CI実行の全体結果"""

    success: bool
    workflows: list[WorkflowResult]
    total_duration: float
    log_path: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_failures(self) -> int:
        """全失敗数を取得"""
        return sum(len(job.failures) for workflow in self.workflows for job in workflow.jobs)

    @property
    def failed_workflows(self) -> list[WorkflowResult]:
        """失敗したワークフローのリストを取得"""
        return [w for w in self.workflows if not w.success]

    @property
    def failed_jobs(self) -> list[JobResult]:
        """失敗したジョブのリストを取得"""
        failed_jobs: list[JobResult] = []
        for workflow in self.workflows:
            failed_jobs.extend([job for job in workflow.jobs if not job.success])
        return failed_jobs

    @property
    def all_failures(self) -> list[Failure]:
        """全ての失敗のリストを取得"""
        all_failures: list[Failure] = []
        for workflow in self.workflows:
            for job in workflow.jobs:
                all_failures.extend(job.failures)
        return all_failures


@dataclass
class LogComparisonResult:
    """ログ比較結果"""

    current_execution: ExecutionResult
    previous_execution: ExecutionResult | None
    new_errors: list[Failure] = field(default_factory=list)
    resolved_errors: list[Failure] = field(default_factory=list)
    persistent_errors: list[Failure] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """変更があるかどうか"""
        return len(self.new_errors) > 0 or len(self.resolved_errors) > 0

    @property
    def improvement_score(self) -> float:
        """改善スコア（0-1、1が最良）"""
        if not self.previous_execution:
            return 1.0 if self.current_execution.success else 0.0

        prev_failures = len(self.previous_execution.all_failures)
        curr_failures = len(self.current_execution.all_failures)

        if prev_failures == 0:
            return 1.0 if curr_failures == 0 else 0.0

        return max(0.0, 1.0 - (curr_failures / prev_failures))


@dataclass
class AnalysisMetrics:
    """解析メトリクス"""

    total_workflows: int
    total_jobs: int
    total_steps: int
    total_failures: int
    success_rate: float
    average_duration: float
    failure_types: dict[FailureType, int] = field(default_factory=dict)

    @classmethod
    def from_execution_result(cls, execution_result: ExecutionResult) -> AnalysisMetrics:
        """ExecutionResultからメトリクスを生成"""
        total_workflows = len(execution_result.workflows)
        total_jobs = sum(len(w.jobs) for w in execution_result.workflows)
        total_steps = sum(len(job.steps) for w in execution_result.workflows for job in w.jobs)
        total_failures = execution_result.total_failures

        # 成功率を計算
        successful_jobs = sum(1 for w in execution_result.workflows for job in w.jobs if job.success)
        success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 100.0

        # 失敗タイプを集計
        failure_types: dict[FailureType, int] = {}
        for failure in execution_result.all_failures:
            failure_types[failure.type] = failure_types.get(failure.type, 0) + 1

        return cls(
            total_workflows=total_workflows,
            total_jobs=total_jobs,
            total_steps=total_steps,
            total_failures=total_failures,
            success_rate=success_rate,
            average_duration=execution_result.total_duration / total_workflows if total_workflows > 0 else 0.0,
            failure_types=failure_types,
        )
