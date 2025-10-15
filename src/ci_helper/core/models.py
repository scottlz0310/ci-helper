"""
ci-helperのデータモデル定義

実行結果、失敗情報、設定などのデータ構造を定義します。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class FailureType(Enum):
    """失敗の種類"""

    ERROR = "error"
    ASSERTION = "assertion"
    TIMEOUT = "timeout"
    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    UNKNOWN = "unknown"


@dataclass
class Failure:
    """失敗情報を表すデータクラス"""

    type: FailureType
    message: str
    file_path: str | None = None
    line_number: int | None = None
    context_before: Sequence[str] = field(default_factory=list)
    context_after: Sequence[str] = field(default_factory=list)
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
    failures: Sequence[Failure] = field(default_factory=list)
    steps: Sequence[StepResult] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class WorkflowResult:
    """ワークフローの実行結果"""

    name: str
    success: bool
    jobs: Sequence[JobResult] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class ExecutionResult:
    """CI実行の全体結果"""

    success: bool
    workflows: Sequence[WorkflowResult]
    total_duration: float
    log_path: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_failures(self) -> int:
        """全失敗数を取得"""
        return sum(len(job.failures) for workflow in self.workflows for job in workflow.jobs)

    @property
    def failed_workflows(self) -> Sequence[WorkflowResult]:
        """失敗したワークフローのリストを取得"""
        return [w for w in self.workflows if not w.success]
