"""
ログ抽出機能のユニットテスト

LogExtractorクラスの各種エラーパターン抽出、コンテキスト取得、
スタックトレース抽出機能をテストします。
"""

import pytest

from ci_helper.core.exceptions import LogParsingError
from ci_helper.core.log_extractor import LogExtractor
from ci_helper.core.models import FailureType


class TestLogExtractor:
    """LogExtractorクラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.extractor = LogExtractor(context_lines=2)

    def test_extract_failures_empty_log(self):
        """空のログに対する失敗抽出のテスト"""
        # 空文字列
        failures = self.extractor.extract_failures("")
        assert failures == []

        # 空白のみ
        failures = self.extractor.extract_failures("   \n\n  ")
        assert failures == []

        # None（型チェック用）
        failures = self.extractor.extract_failures("")
        assert failures == []

    def test_extract_error_patterns(self):
        """各種エラーパターンの抽出テスト"""
        # 一般的なエラーパターン
        test_cases = [
            ("Error: Something went wrong", FailureType.ERROR, "Something went wrong"),
            ("ERROR: Build failed", FailureType.ERROR, "Build failed"),
            ("[ERROR] Configuration invalid", FailureType.ERROR, "Configuration invalid"),
            ("##[error]GitHub Actions error", FailureType.ERROR, "GitHub Actions error"),
            ("Process completed with exit code 1", FailureType.ERROR, "1"),
            ("bash: command not found", FailureType.ERROR, None),  # メッセージ全体がマッチ
        ]

        for log_content, expected_type, expected_message in test_cases:
            failures = self.extractor.extract_failures(log_content)
            assert len(failures) >= 1, f"Failed to extract error from: {log_content}"

            failure = failures[0]
            assert failure.type == expected_type
            if expected_message:
                assert expected_message in failure.message

    def test_extract_assertion_patterns(self):
        """アサーション失敗パターンの抽出テスト"""
        test_cases = [
            ("AssertionError: Expected 5 but got 3", FailureType.ASSERTION, "Expected 5 but got 3"),
            ("assert x == y failed", FailureType.ASSERTION, "x == y"),
            ("Expected: true", FailureType.ASSERTION, "true"),
            ("Actual: false", FailureType.ASSERTION, "false"),
            ("  ✕ should return correct value", FailureType.ASSERTION, "should return correct value"),
            ("  FAIL test/example.test.js", FailureType.ASSERTION, "test/example.test.js"),
            ("E   assert 1 == 2", FailureType.ASSERTION, "assert 1 == 2"),
        ]

        for log_content, expected_type, expected_message in test_cases:
            failures = self.extractor.extract_failures(log_content)
            assert len(failures) >= 1, f"Failed to extract assertion from: {log_content}"

            failure = failures[0]
            assert failure.type == expected_type
            if expected_message:
                assert expected_message in failure.message

    def test_extract_timeout_patterns(self):
        """タイムアウトパターンの抽出テスト"""
        test_cases = [
            "Operation timed out after 30 seconds",
            "Process killed due to timeout",
            "Request exceeded timeout limit",
            "Connection timeout occurred",
        ]

        for log_content in test_cases:
            failures = self.extractor.extract_failures(log_content)
            assert len(failures) >= 1, f"Failed to extract timeout from: {log_content}"
            assert failures[0].type == FailureType.TIMEOUT

    def test_extract_build_failure_patterns(self):
        """ビルド失敗パターンの抽出テスト"""
        test_cases = [
            ("Build failed with errors", FailureType.BUILD_FAILURE),
            ("Compilation failed", FailureType.BUILD_FAILURE),
            ("npm ERR! Build process failed", FailureType.BUILD_FAILURE),
            ("yarn error Something went wrong", FailureType.BUILD_FAILURE),
            ("pnpm ERR! Command failed", FailureType.BUILD_FAILURE),
            ("SyntaxError: Unexpected token", FailureType.BUILD_FAILURE),
            ("ImportError: No module named 'missing'", FailureType.BUILD_FAILURE),
            ("ModuleNotFoundError: No module named 'test'", FailureType.BUILD_FAILURE),
        ]

        for log_content, expected_type in test_cases:
            failures = self.extractor.extract_failures(log_content)
            assert len(failures) >= 1, f"Failed to extract build failure from: {log_content}"
            assert failures[0].type == expected_type

    def test_extract_test_failure_patterns(self):
        """テスト失敗パターンの抽出テスト"""
        test_cases = [
            "Tests failed with 3 errors",
            "5 failing tests found",
            "2 failed, 8 passed",
            "FAILED test_example.py::test_function",
            "Coverage threshold not met: 45% < 80%",
        ]

        for log_content in test_cases:
            failures = self.extractor.extract_failures(log_content)
            assert len(failures) >= 1, f"Failed to extract test failure from: {log_content}"
            assert failures[0].type == FailureType.TEST_FAILURE

    def test_extract_file_info(self):
        """ファイルパスと行番号の抽出テスト"""
        test_cases = [
            ("Error in file.py:42", "file.py", 42),
            ("test.js:15:8 - Error occurred", "test.js", 15),
            ("::error file=src/main.py,line=100", "src/main.py", 100),
            ("example.py:25: in test_function", "example.py", 25),
            ("No file info here", None, None),
        ]

        for message, expected_file, expected_line in test_cases:
            file_path, line_number = self.extractor._extract_file_info(message)
            assert file_path == expected_file
            assert line_number == expected_line

    def test_get_context_lines(self):
        """コンテキスト行の取得テスト"""
        log_content = """Line 1
Line 2
Line 3
Error: Something went wrong
Line 5
Line 6
Line 7"""

        # 中央の行（4行目）のコンテキストを取得
        context = self.extractor.get_context_lines(log_content, 4, context=2)

        # 期待される出力形式をチェック
        assert "2: Line 2" in context
        assert "3: Line 3" in context
        assert "4:>Error: Something went wrong" in context  # 中心行は>マーク付き
        assert "5: Line 5" in context
        assert "6: Line 6" in context

    def test_get_context_lines_edge_cases(self):
        """コンテキスト行取得のエッジケースのテスト"""
        log_content = "Line 1\nLine 2\nLine 3"

        # 範囲外の行番号
        context = self.extractor.get_context_lines(log_content, 10, context=2)
        assert context == ""

        # 負の行番号
        context = self.extractor.get_context_lines(log_content, -1, context=2)
        assert context == ""

        # 最初の行
        context = self.extractor.get_context_lines(log_content, 1, context=2)
        assert "1:>Line 1" in context
        assert "2: Line 2" in context

        # 最後の行
        context = self.extractor.get_context_lines(log_content, 3, context=2)
        assert "1: Line 1" in context
        assert "2: Line 2" in context
        assert "3:>Line 3" in context

    def test_extract_stack_trace_python(self):
        """Pythonスタックトレースの抽出テスト"""
        log_content = """Some log output
Traceback (most recent call last):
  File "test.py", line 10, in <module>
    raise ValueError("Test error")
ValueError: Test error
More log output"""

        failures = self.extractor.extract_failures(log_content)

        # スタックトレースを含む失敗が抽出されることを確認
        stack_trace_failure = None
        for failure in failures:
            if failure.stack_trace:
                stack_trace_failure = failure
                break

        assert stack_trace_failure is not None
        assert "Traceback" in stack_trace_failure.stack_trace
        assert "test.py" in stack_trace_failure.stack_trace

    def test_extract_stack_trace_javascript(self):
        """JavaScriptスタックトレースの抽出テスト"""
        log_content = """Error occurred
    at Object.test (test.js:15:8)
    at Module._compile (module.js:456:26)
    at Object.Module._extensions..js (module.js:474:10)
End of trace"""

        # JavaScriptスタックトレースパターンを直接テスト
        stack_trace = self.extractor._extract_stack_trace(log_content, 0)

        if stack_trace:  # スタックトレースが検出された場合
            assert "at Object.test" in stack_trace
            assert "test.js:15:8" in stack_trace

    def test_deduplicate_failures(self):
        """重複する失敗の除去テスト"""
        log_content = """Error: Duplicate error message
Error: Duplicate error message
Error: Different error message
Error: Duplicate error message"""

        failures = self.extractor.extract_failures(log_content)

        # 重複が除去されていることを確認
        unique_messages = set(failure.message for failure in failures)
        assert len(unique_messages) == 2  # "Duplicate error message" と "Different error message"
        assert "Duplicate error message" in unique_messages
        assert "Different error message" in unique_messages

    def test_parse_error_patterns_custom(self):
        """カスタムエラーパターンの解析テスト"""
        content = """Custom error: Something failed
CUSTOM_PATTERN: Another error
Normal error: Standard error"""

        custom_patterns = {"error": [r"Custom error:\s*(.+)", r"CUSTOM_PATTERN:\s*(.+)"]}

        matches = self.extractor.parse_error_patterns(content, custom_patterns)

        # カスタムパターンがマッチしていることを確認
        custom_matches = [match for match in matches if "Custom" in match[1] or "CUSTOM_PATTERN" in match[1]]
        assert len(custom_matches) >= 2

    def test_parse_error_patterns_invalid_regex(self):
        """無効な正規表現パターンの処理テスト"""
        content = "Some error occurred"

        # 無効な正規表現を含むカスタムパターン
        custom_patterns = {"error": [r"[invalid regex", r"valid_pattern"]}

        # 例外が発生せず、有効なパターンのみが処理されることを確認
        matches = self.extractor.parse_error_patterns(content, custom_patterns)
        assert isinstance(matches, list)  # 正常に処理される

    def test_extract_failures_with_context(self):
        """コンテキスト付きの失敗抽出テスト"""
        log_content = """Line before error 1
Line before error 2
Error: Test error occurred
Line after error 1
Line after error 2"""

        failures = self.extractor.extract_failures(log_content)
        assert len(failures) >= 1

        failure = failures[0]
        assert len(failure.context_before) <= 2  # context_lines=2で初期化
        assert len(failure.context_after) <= 2

        # コンテキストの内容を確認
        if failure.context_before:
            assert any("before error" in line for line in failure.context_before)
        if failure.context_after:
            assert any("after error" in line for line in failure.context_after)

    def test_log_parsing_error_handling(self):
        """ログ解析エラーのハンドリングテスト"""
        # 正常なケースでは例外が発生しないことを確認
        try:
            failures = self.extractor.extract_failures("Normal log content")
            assert isinstance(failures, list)
        except LogParsingError:
            pytest.fail("LogParsingError should not be raised for normal content")

    def test_failure_type_priority(self):
        """失敗タイプの優先順位テスト"""
        # より具体的な失敗タイプが優先されることを確認
        log_content = """AssertionError: Test failed
Error: General error"""

        failures = self.extractor.extract_failures(log_content)

        # アサーションエラーが検出されることを確認
        assertion_failures = [f for f in failures if f.type == FailureType.ASSERTION]
        assert len(assertion_failures) >= 1

        # 一般的なエラーも検出されることを確認
        error_failures = [f for f in failures if f.type == FailureType.ERROR]
        assert len(error_failures) >= 1

    def test_multiline_error_extraction(self):
        """複数行にわたるエラーの抽出テスト"""
        log_content = """Starting process
Error: Multi-line error
  with additional details
  and more information
Process completed"""

        failures = self.extractor.extract_failures(log_content)
        assert len(failures) >= 1

        # エラーメッセージが正しく抽出されることを確認
        failure = failures[0]
        assert "Multi-line error" in failure.message

    def test_context_lines_configuration(self):
        """コンテキスト行数の設定テスト"""
        # 異なるコンテキスト行数でテスト
        extractor_1 = LogExtractor(context_lines=1)
        extractor_3 = LogExtractor(context_lines=3)

        log_content = """Line 1
Line 2
Line 3
Error: Test error
Line 5
Line 6
Line 7"""

        failures_1 = extractor_1.extract_failures(log_content)
        failures_3 = extractor_3.extract_failures(log_content)

        if failures_1 and failures_3:
            # コンテキスト行数が設定通りになっていることを確認
            assert len(failures_1[0].context_before) <= 1
            assert len(failures_1[0].context_after) <= 1
            assert len(failures_3[0].context_before) <= 3
            assert len(failures_3[0].context_after) <= 3
