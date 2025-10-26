"""
JSONFormatterのテスト
"""

import json
from datetime import datetime

import pytest

from ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, StepResult, WorkflowResult
from ci_helper.formatters.json_formatter import JSONFormatter


class TestJSONFormatter:
    """JSONFormatterのテストクラス"""

    def setup_method(self):
        """テストメソッドの前処理"""
        self.formatter = JSONFormatter(sanitize_secrets=False)

    def test_get_format_name(self):
        """フォーマット名の取得をテスト"""
        assert self.formatter.get_format_name() == "json"

    def test_get_description(self):
        """フォーマット説明の取得をテスト"""
        description = self.formatter.get_description()
        assert "JSON" in description
        assert "プログラム解析" in description

    def test_format_successful_execution(self):
        """成功した実行結果のフォーマットをテスト"""
        # テストデータの作成
        step = StepResult(name="test-step", success=True, duration=1.5, output="test output")
        job = JobResult(name="test-job", success=True, steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=True,
            workflows=[workflow],
            total_duration=5.0,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            log_path="/path/to/log.txt",
        )

        # フォーマット実行
        result = self.formatter.format(execution_result)

        # JSON形式の検証
        parsed = json.loads(result)

        # 基本構造の確認
        assert "format_info" in parsed
        assert "execution_summary" in parsed
        assert "metrics" in parsed
        assert "workflows" in parsed
        assert "failures_summary" in parsed
        assert "all_failures" in parsed

        # 実行サマリーの確認
        summary = parsed["execution_summary"]
        assert summary["success"] is True
        assert summary["total_duration"] == 5.0
        assert summary["total_workflows"] == 1
        assert summary["total_jobs"] == 1
        assert summary["total_steps"] == 1
        assert summary["total_failures"] == 0
        assert summary["log_path"] == "/path/to/log.txt"

    def test_format_failed_execution(self):
        """失敗した実行結果のフォーマットをテスト"""
        # 失敗データの作成
        failure = Failure(
            type=FailureType.ASSERTION,
            message="Test assertion failed",
            file_path="test.py",
            line_number=42,
            context_before=["line 40", "line 41"],
            context_after=["line 43", "line 44"],
            stack_trace="Stack trace here",
        )

        step = StepResult(name="test-step", success=False, duration=1.5, output="error output")
        job = JobResult(name="test-job", success=False, failures=[failure], steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=False, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=False, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        # フォーマット実行
        result = self.formatter.format(execution_result)

        # JSON形式の検証
        parsed = json.loads(result)

        # 実行サマリーの確認
        summary = parsed["execution_summary"]
        assert summary["success"] is False
        assert summary["total_failures"] == 1

        # 失敗情報の確認
        assert len(parsed["all_failures"]) == 1
        failure_data = parsed["all_failures"][0]
        assert failure_data["type"] == "assertion"
        assert failure_data["message"] == "Test assertion failed"
        assert failure_data["file_path"] == "test.py"
        assert failure_data["line_number"] == 42
        assert failure_data["context_before"] == ["line 40", "line 41"]
        assert failure_data["context_after"] == ["line 43", "line 44"]
        assert failure_data["stack_trace"] == "Stack trace here"

        # 失敗サマリーの確認
        failures_summary = parsed["failures_summary"]
        assert failures_summary["total_count"] == 1
        assert failures_summary["by_type"]["assertion"] == 1
        assert failures_summary["by_workflow"]["test-workflow"] == 1
        assert len(failures_summary["critical_failures"]) == 1

    def test_format_with_compact_option(self):
        """compactオプションのテスト"""
        step = StepResult(name="test-step", success=True, duration=1.5, output="test output")
        job = JobResult(name="test-job", success=True, steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=True, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        # 通常フォーマット
        normal_result = self.formatter.format(execution_result)

        # コンパクトフォーマット
        compact_result = self.formatter.format(execution_result, compact=True)

        # コンパクト版の方が短いことを確認
        assert len(compact_result) < len(normal_result)

        # 両方とも有効なJSONであることを確認
        json.loads(normal_result)
        json.loads(compact_result)

    def test_format_with_include_options(self):
        """include_*オプションのテスト"""
        failure = Failure(
            type=FailureType.ERROR,
            message="Test error",
            file_path="test.py",
            line_number=10,
            context_before=["context line"],
            context_after=["after line"],
            stack_trace="stack trace",
        )

        step = StepResult(name="test-step", success=False, duration=1.5, output="error output")
        job = JobResult(name="test-job", success=False, failures=[failure], steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=False, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=False, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        # コンテキストとスタックトレースを除外
        result = self.formatter.format(
            execution_result, include_context=False, include_stack_trace=False, include_output=False
        )

        parsed = json.loads(result)
        failure_data = parsed["all_failures"][0]

        # コンテキストとスタックトレースが含まれていないことを確認
        assert "context_before" not in failure_data
        assert "context_after" not in failure_data
        assert "stack_trace" not in failure_data

        # ステップ出力が含まれていないことを確認
        step_data = parsed["workflows"][0]["jobs"][0]["steps"][0]
        assert "output" not in step_data

    def test_validate_options_valid(self):
        """有効なオプションの検証をテスト"""
        options = {"compact": True, "include_output": False, "include_context": True, "include_stack_trace": False}

        validated = self.formatter.validate_options(**options)
        assert validated == options

    def test_validate_options_invalid_type(self):
        """無効な型のオプションの検証をテスト"""
        with pytest.raises(ValueError, match="compact オプションはbool型である必要があります"):
            self.formatter.validate_options(compact="true")

    def test_validate_options_unknown(self):
        """未知のオプションの検証をテスト"""
        with pytest.raises(ValueError, match="未知のオプション"):
            self.formatter.validate_options(unknown_option=True)

    def test_supports_option(self):
        """オプションサポートの確認をテスト"""
        assert self.formatter.supports_option("compact")
        assert self.formatter.supports_option("include_output")
        assert self.formatter.supports_option("include_context")
        assert self.formatter.supports_option("include_stack_trace")
        assert not self.formatter.supports_option("unknown_option")

    def test_get_supported_options(self):
        """サポートされているオプション一覧の取得をテスト"""
        options = self.formatter.get_supported_options()
        expected = [
            "compact",
            "include_output",
            "include_context",
            "include_stack_trace",
            "pretty_print",
            "include_metadata",
            "detail_level",
            "filter_errors",
            "max_failures",
        ]
        assert set(options) == set(expected)

    def test_validate_json_structure_valid(self):
        """有効なJSON構造の検証をテスト"""
        step = StepResult(name="test-step", success=True, duration=1.5, output="test output")
        job = JobResult(name="test-job", success=True, steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=True, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        json_str = self.formatter.format(execution_result)
        validation_result = self.formatter.validate_json_structure(json_str)

        assert validation_result["valid"] is True
        assert validation_result["parseable"] is True
        assert len(validation_result["missing_fields"]) == 0
        assert validation_result["field_count"] > 0
        assert validation_result["size_bytes"] > 0

    def test_validate_json_structure_invalid(self):
        """無効なJSON構造の検証をテスト"""
        invalid_json = '{"invalid": json}'
        validation_result = self.formatter.validate_json_structure(invalid_json)

        assert validation_result["valid"] is False
        assert validation_result["parseable"] is False
        assert "error" in validation_result

    def test_critical_failures_prioritization(self):
        """クリティカル失敗の優先度付けをテスト"""
        # 異なる優先度の失敗を作成
        assertion_failure = Failure(
            type=FailureType.ASSERTION,
            message="Assertion failed",
            file_path="test.py",
            line_number=10,
            stack_trace="stack trace",
        )

        error_failure = Failure(
            type=FailureType.ERROR,
            message="Generic error",
        )

        timeout_failure = Failure(type=FailureType.TIMEOUT, message="Timeout occurred", file_path="timeout.py")

        job = JobResult(
            name="test-job", success=False, failures=[error_failure, assertion_failure, timeout_failure], duration=2.0
        )
        workflow = WorkflowResult(name="test-workflow", success=False, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=False, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        result = self.formatter.format(execution_result)
        parsed = json.loads(result)

        # クリティカル失敗の順序を確認（アサーションが最優先）
        critical_failures = parsed["failures_summary"]["critical_failures"]
        assert len(critical_failures) == 3
        assert critical_failures[0]["type"] == "assertion"  # 最優先

    def test_sanitize_secrets_disabled(self):
        """シークレットサニタイズ無効時のテスト"""
        formatter = JSONFormatter(sanitize_secrets=False)

        step = StepResult(name="test-step", success=True, duration=1.5, output="API_KEY=secret123")
        job = JobResult(name="test-job", success=True, steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=True, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        result = formatter.format(execution_result)

        # シークレットがそのまま含まれていることを確認
        assert "API_KEY=secret123" in result

    def test_custom_json_options(self):
        """カスタムJSONオプションのテスト"""
        formatter = JSONFormatter(indent=4, ensure_ascii=True)

        step = StepResult(name="test-step", success=True, duration=1.5, output="test output")
        job = JobResult(name="test-job", success=True, steps=[step], duration=2.0)
        workflow = WorkflowResult(name="test-workflow", success=True, jobs=[job], duration=3.0)
        execution_result = ExecutionResult(
            success=True, workflows=[workflow], total_duration=5.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        result = formatter.format(execution_result)

        # インデントが4スペースであることを確認
        lines = result.split("\n")
        indented_lines = [line for line in lines if line.startswith("    ")]
        assert len(indented_lines) > 0  # 4スペースインデントの行が存在

        # 有効なJSONであることを確認
        json.loads(result)
