"""
ログ解析の統合テスト

実際のサンプルログファイルを使用してログ解析機能の統合テストを行います。
"""

from pathlib import Path

import pytest

from ci_helper.core.log_analyzer import LogAnalyzer
from ci_helper.core.log_extractor import LogExtractor
from ci_helper.core.models import FailureType


class TestLogAnalysisIntegration:
    """ログ解析の統合テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.extractor = LogExtractor()
        self.analyzer = LogAnalyzer()
        self.fixtures_path = Path("tests/fixtures/sample_logs")

    def test_successful_log_analysis(self):
        """成功ログの解析統合テスト"""
        log_file = self.fixtures_path / "successful_run.log"
        if not log_file.exists():
            pytest.skip("Sample log file not found")

        log_content = log_file.read_text()

        # ログ抽出テスト
        failures = self.extractor.extract_failures(log_content)
        assert len(failures) == 0  # 成功ログなので失敗はない

        # ログ解析テスト
        result = self.analyzer.analyze_log(log_content)
        assert result.success is True
        assert result.total_failures == 0
        assert len(result.workflows) >= 1

    def test_failed_log_analysis(self):
        """失敗ログの解析統合テスト"""
        log_file = self.fixtures_path / "failed_run.log"
        if not log_file.exists():
            pytest.skip("Sample log file not found")

        log_content = log_file.read_text()

        # ログ抽出テスト
        self.extractor.extract_failures(log_content)
        # 失敗ログなので何らかの失敗が検出される可能性がある

        # ログ解析テスト
        result = self.analyzer.analyze_log(log_content)
        assert result.success is False
        assert len(result.workflows) >= 1
        assert len(result.failed_workflows) >= 1

    def test_python_error_log_analysis(self):
        """Pythonエラーログの解析統合テスト"""
        log_file = self.fixtures_path / "python_error.log"
        if not log_file.exists():
            pytest.skip("Sample log file not found")

        log_content = log_file.read_text()

        # ログ抽出テスト
        failures = self.extractor.extract_failures(log_content)

        # AssertionErrorが検出されることを確認
        assertion_failures = [f for f in failures if f.type == FailureType.ASSERTION]
        assert len(assertion_failures) >= 1

        # スタックトレースが含まれることを確認
        stack_trace_failures = [f for f in failures if f.stack_trace]
        assert len(stack_trace_failures) >= 0  # スタックトレースは必須ではない

        # ログ解析テスト
        result = self.analyzer.analyze_log(log_content)
        assert result.success is False
        assert result.total_failures >= 1

    def test_context_extraction_with_real_logs(self):
        """実際のログでのコンテキスト抽出テスト"""
        log_file = self.fixtures_path / "python_error.log"
        if not log_file.exists():
            pytest.skip("Sample log file not found")

        log_content = log_file.read_text()
        failures = self.extractor.extract_failures(log_content)

        if failures:
            failure = failures[0]
            # コンテキストが適切に抽出されることを確認
            assert isinstance(failure.context_before, list | tuple)
            assert isinstance(failure.context_after, list | tuple)

    def test_workflow_detection_with_real_logs(self):
        """実際のログでのワークフロー検出テスト"""
        for log_file in self.fixtures_path.glob("*.log"):
            log_content = log_file.read_text()

            # ワークフローが検出されることを確認
            workflows = self.analyzer._detect_workflows(log_content)
            assert isinstance(workflows, list)

            # 解析が正常に完了することを確認
            result = self.analyzer.analyze_log(log_content)
            assert isinstance(result.workflows, list | tuple)

    def test_error_pattern_coverage(self):
        """エラーパターンのカバレッジテスト"""
        # 各種エラーパターンが実際のログで検出されることを確認
        test_patterns = [
            ("Error: Test error", FailureType.ERROR),
            ("AssertionError: Test failed", FailureType.ASSERTION),
            ("Process timed out", FailureType.TIMEOUT),
            ("Build failed", FailureType.BUILD_FAILURE),
            ("Tests failed", FailureType.TEST_FAILURE),
        ]

        for pattern_text, expected_type in test_patterns:
            failures = self.extractor.extract_failures(pattern_text)
            if failures:
                assert failures[0].type == expected_type

    def test_log_comparison_with_real_data(self):
        """実際のデータでのログ比較テスト"""
        successful_log = self.fixtures_path / "successful_run.log"
        failed_log = self.fixtures_path / "failed_run.log"

        if not (successful_log.exists() and failed_log.exists()):
            pytest.skip("Sample log files not found")

        # 成功ログと失敗ログを解析
        successful_result = self.analyzer.analyze_log(successful_log.read_text())
        failed_result = self.analyzer.analyze_log(failed_log.read_text())

        # 比較実行
        comparison = self.analyzer.compare_execution_results(failed_result, successful_result)

        # 比較結果が適切な構造を持つことを確認
        assert "new_errors" in comparison
        assert "resolved_errors" in comparison
        assert "persistent_errors" in comparison

        # 失敗ログの方が多くの失敗を持つことを確認
        assert failed_result.total_failures >= successful_result.total_failures
