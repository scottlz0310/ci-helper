"""
ci-helperのデータモデル定義

実行結果、失敗情報、設定などのデータ構造を定義します。
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


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
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context_before: List[str] = None
    context_after: List[str] = None
    stack_trace: Optional[str] = None
    
    def __post_init__(self):
        if self.context_before is None:
            self.context_before = []
        if self.context_after is None:
            self.context_after = []


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
    failures: List[Failure]
    steps: List[StepResult]
    duration: float = 0.0
    
    def __post_init__(self):
        if self.failures is None:
            self.failures = []
        if self.steps is None:
            self.steps = []


@dataclass
class WorkflowResult:
    """ワークフローの実行結果"""
    name: str
    success: bool
    jobs: List[JobResult]
    duration: float = 0.0
    
    def __post_init__(self):
        if self.jobs is None:
            self.jobs = []


@dataclass
class ExecutionResult:
    """CI実行の全体結果"""
    success: bool
    workflows: List[WorkflowResult]
    total_duration: float
    log_path: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.workflows is None:
            self.workflows = []
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def total_failures(self) -> int:
        """全失敗数を取得"""
        return sum(
            len(job.failures) 
            for workflow in self.workflows 
            for job in workflow.jobs
        )
    
    @property
    def failed_workflows(self) -> List[WorkflowResult]:
        """失敗したワークフローのリストを取得"""
        return [w for w in self.workflows if not w.success]