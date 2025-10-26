"""
人間可読フォーマッターのテスト

HumanReadableFormatterクラスの機能をテストします。
"""

from datetime import datetime

from src.ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from src.ci_helper.formatters import HumanReadableFormatter


class TestHumanReadableFormatter:
    """人間可読フォーマッターのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        formatter = HumanReadableFormatter()
        assert formatter.get_format_name() == "human"
        assert "人間可読" in formatter.get_description()

    def test_format_successful_execution(self):
        """成功した実行のフォーマットテスト"""
        formatter = HumanReadableFormatter()

        execution_result = ExecutionResult(
            success=True,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=True,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=True,
                            failures=[],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        result = formatter.format(execution_result)
        assert isinstance(result, str)
        assert "成功" in result
        assert "test-workflow" in result

    def test_format_failed_execution(self):
        """失敗した実行のフォーマットテスト"""
        formatter = HumanReadableFormatter()

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[
                                Failure(
                                    type=FailureType.TEST_FAILURE,
                                    message="Test failed",
                                    file_path="test.py",
                                    line_number=10,
                                )
                            ],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        result = formatter.format(execution_result)
        assert isinstance(result, str)
        assert "失敗" in result
        assert "test-workflow" in result
        assert "Test failed" in result

    def test_format_options(self):
        """フォーマットオプションのテスト"""
        formatter = HumanReadableFormatter()

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[
                                Failure(
                                    type=FailureType.ASSERTION,
                                    message="Assertion failed",
                                    file_path="test.py",
                                    line_number=42,
                                )
                            ],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        # デフォルトオプション
        result1 = formatter.format(execution_result)
        assert isinstance(result1, str)

        # カスタムオプション
        result2 = formatter.format(
            execution_result,
            show_details=False,
            show_success_jobs=True,
            max_failures=5,
            color_output=False,
        )
        assert isinstance(result2, str)

    def test_get_supported_options(self):
        """サポートオプション一覧テスト"""
        formatter = HumanReadableFormatter()
        options = formatter.get_supported_options()
        expected_options = ["show_details", "show_success_jobs", "max_failures", "color_output"]
        for option in expected_options:
            assert option in options

    def test_prioritize_failures(self):
        """失敗の優先度付けテスト"""
        formatter = HumanReadableFormatter()

        failures = [
            Failure(type=FailureType.UNKNOWN, message="Unknown error"),
            Failure(type=FailureType.ASSERTION, message="Assertion failed", file_path="test.py", line_number=10),
            Failure(type=FailureType.ERROR, message="Runtime error"),
        ]

        prioritized = formatter._prioritize_failures(failures)

        # アサーション失敗が最優先になることを確認
        assert prioritized[0].type == FailureType.ASSERTION
        assert prioritized[0].message == "Assertion failed"

    def test_find_failure_location(self):
        """失敗場所特定テスト"""
        formatter = HumanReadableFormatter()

        failure = Failure(type=FailureType.TEST_FAILURE, message="Test failed")

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[failure],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        workflow_name, job_name = formatter._find_failure_location(failure, execution_result)
        assert workflow_name == "test-workflow"
        assert job_name == "test-job"

    def test_format_with_context(self):
        """コンテキスト付き失敗のフォーマットテスト"""
        formatter = HumanReadableFormatter()

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[
                                Failure(
                                    type=FailureType.ASSERTION,
                                    message="assert x == 5",
                                    file_path="test.py",
                                    line_number=10,
                                    context_before=["def test_function():", "    x = 3"],
                                    context_after=["    assert y == 10"],
                                    stack_trace="Traceback (most recent call last):\n  File test.py, line 10",
                                )
                            ],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        result = formatter.format(execution_result, show_details=True)
        assert "assert x == 5" in result
        assert "test.py" in result
