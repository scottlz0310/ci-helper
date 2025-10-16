"""
AI フォーマッターのユニットテスト

AI 用出力フォーマッター（AIFormatter）の機能をテストします。
Markdown 出力、JSON 出力、トークン数カウント機能を検証します。
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from ci_helper.core.ai_formatter import AIFormatter
from ci_helper.core.models import (
    AnalysisMetrics,
    ExecutionResult,
    Failure,
    FailureType,
    JobResult,
    StepResult,
    WorkflowResult,
)


class TestAIFormatter:
    """AIFormatter クラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter(sanitize_secrets=False)  # テスト用にサニタイズ無効

        # テスト用のサンプルデータを作成
        self.sample_failure = Failure(
            type=FailureType.ERROR,
            message="Test error message",
            file_path="test.py",
            line_number=42,
            context_before=["line 40", "line 41"],
            context_after=["line 43", "line 44"],
            stack_trace="Traceback (most recent call last):\n  File test.py, line 42",
        )

        self.sample_step = StepResult(name="Test Step", success=False, duration=2.5, output="Step failed")

        self.sample_job = JobResult(
            name="test-job", success=False, failures=[self.sample_failure], steps=[self.sample_step], duration=5.0
        )

        self.sample_workflow = WorkflowResult(name="test-workflow", success=False, jobs=[self.sample_job], duration=5.0)

        self.sample_execution_result = ExecutionResult(
            success=False,
            workflows=[self.sample_workflow],
            total_duration=5.0,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

    def test_formatter_initialization_default(self):
        """デフォルト設定でのフォーマッター初期化テスト"""
        formatter = AIFormatter()

        assert formatter.sanitize_secrets is True
        assert hasattr(formatter, "security_validator")
        assert len(formatter.failure_type_icons) == 6

    def test_formatter_initialization_no_sanitize(self):
        """サニタイズ無効でのフォーマッター初期化テスト"""
        formatter = AIFormatter(sanitize_secrets=False)

        assert formatter.sanitize_secrets is False
        assert not hasattr(formatter, "security_validator")

    def test_failure_type_icons_mapping(self):
        """失敗タイプアイコンのマッピングテスト"""
        expected_icons = {
            FailureType.ERROR: "🚨",
            FailureType.ASSERTION: "❌",
            FailureType.TIMEOUT: "⏰",
            FailureType.BUILD_FAILURE: "🔨",
            FailureType.TEST_FAILURE: "🧪",
            FailureType.UNKNOWN: "❓",
        }

        assert self.formatter.failure_type_icons == expected_icons


class TestMarkdownFormatting:
    """Markdown 形式の出力テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter(sanitize_secrets=False)

        # 成功した実行結果のサンプル
        successful_job = JobResult(name="success-job", success=True, duration=2.0)
        successful_workflow = WorkflowResult(name="success-workflow", success=True, jobs=[successful_job], duration=2.0)
        self.successful_execution = ExecutionResult(
            success=True, workflows=[successful_workflow], total_duration=2.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        # 失敗した実行結果のサンプル
        failure = Failure(
            type=FailureType.ASSERTION,
            message="Assertion failed: expected 5, got 3",
            file_path="test_math.py",
            line_number=15,
            context_before=["def test_addition():", "    result = add(2, 3)"],
            context_after=["    # This should pass", "    pass"],
            stack_trace="AssertionError: expected 5, got 3",
        )

        failed_job = JobResult(name="failed-job", success=False, failures=[failure], duration=3.0)
        failed_workflow = WorkflowResult(name="failed-workflow", success=False, jobs=[failed_job], duration=3.0)
        self.failed_execution = ExecutionResult(
            success=False, workflows=[failed_workflow], total_duration=3.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

    def test_format_markdown_successful_execution(self):
        """成功した実行のMarkdown形式フォーマットテスト"""
        result = self.formatter.format_markdown(self.successful_execution)

        # ヘッダーの確認
        assert "# CI実行結果 ✅" in result
        assert "**ステータス**: 成功" in result
        assert "**実行時刻**: 2024-01-01 12:00:00" in result
        assert "**総実行時間**: 2.00秒" in result
        assert "**ワークフロー数**: 1" in result

        # サマリーの確認
        assert "## 📊 実行サマリー" in result
        assert "**総ジョブ数**: 1" in result
        assert "**成功ジョブ**: 1" in result
        assert "**失敗ジョブ**: 0" in result
        assert "**総失敗数**: 0" in result
        assert "**成功率**: 100.0%" in result

        # ワークフロー詳細の確認
        assert "## 📋 ワークフロー詳細" in result
        assert "### ✅ success-workflow" in result

        # 失敗詳細は含まれないことを確認
        assert "## 🚨 失敗詳細" not in result

    def test_format_markdown_failed_execution(self):
        """失敗した実行のMarkdown形式フォーマットテスト"""
        result = self.formatter.format_markdown(self.failed_execution)

        # ヘッダーの確認
        assert "# CI実行結果 ❌" in result
        assert "**ステータス**: 失敗" in result

        # 失敗詳細の確認
        assert "## 🚨 失敗詳細" in result
        assert "### 失敗タイプ別集計" in result
        assert "- ❌ **assertion**: 1件" in result

        # 失敗一覧の確認
        assert "### 失敗一覧" in result
        assert "#### 1. ❌ ASSERTION" in result
        assert "**ワークフロー**: failed-workflow" in result
        assert "**ジョブ**: failed-job" in result
        assert "**ファイル**: `test_math.py` (行 15)" in result
        assert "**エラーメッセージ**:" in result
        assert "Assertion failed: expected 5, got 3" in result

        # コンテキストの確認
        assert "**コンテキスト**:" in result
        assert "def test_addition():" in result
        assert "result = add(2, 3)" in result

        # スタックトレースの確認
        assert "**スタックトレース**:" in result
        assert "AssertionError: expected 5, got 3" in result

    def test_format_markdown_header_generation(self):
        """Markdownヘッダー生成のテスト"""
        header = self.formatter._format_markdown_header(self.successful_execution)

        assert header.startswith("# CI実行結果 ✅")
        assert "**ステータス**: 成功" in header
        assert "**実行時刻**: 2024-01-01 12:00:00" in header
        assert "**総実行時間**: 2.00秒" in header
        assert "**ワークフロー数**: 1" in header

    def test_format_markdown_summary_generation(self):
        """実行サマリー生成のテスト"""
        summary = self.formatter._format_markdown_summary(self.failed_execution)

        assert "## 📊 実行サマリー" in summary
        assert "**総ジョブ数**: 1" in summary
        assert "**成功ジョブ**: 0" in summary
        assert "**失敗ジョブ**: 1" in summary
        assert "**総失敗数**: 1" in summary
        assert "**成功率**: 0.0%" in summary

    def test_format_single_failure_markdown(self):
        """単一失敗のMarkdown形式フォーマットテスト"""
        failure = Failure(
            type=FailureType.TIMEOUT, message="Operation timed out", file_path="slow_test.py", line_number=25
        )

        result = self.formatter._format_single_failure_markdown(failure, 1, "timeout-workflow", "timeout-job")

        assert "#### 1. ⏰ TIMEOUT" in result
        assert "**ワークフロー**: timeout-workflow" in result
        assert "**ジョブ**: timeout-job" in result
        assert "**ファイル**: `slow_test.py` (行 25)" in result
        assert "**エラーメッセージ**:" in result
        assert "Operation timed out" in result

    def test_format_markdown_workflows_section(self):
        """ワークフロー詳細セクションのテスト"""
        workflows_section = self.formatter._format_markdown_workflows(self.failed_execution)

        assert "## 📋 ワークフロー詳細" in workflows_section
        assert "### ❌ failed-workflow" in workflows_section
        assert "- **実行時間**: 3.00秒" in workflows_section
        assert "- **ジョブ数**: 1" in workflows_section
        assert "- **成功ジョブ**: 0" in workflows_section
        assert "#### ジョブ一覧" in workflows_section
        assert "- ❌ **failed-job** - 3.00秒 (1件の失敗)" in workflows_section

    def test_format_markdown_metrics_section(self):
        """メトリクスセクションのテスト"""
        metrics = AnalysisMetrics.from_execution_result(self.failed_execution)
        metrics_section = self.formatter._format_markdown_metrics(metrics)

        assert "## 📈 メトリクス" in metrics_section
        assert "- **総ワークフロー数**: 1" in metrics_section
        assert "- **総ジョブ数**: 1" in metrics_section
        assert "- **総失敗数**: 1" in metrics_section
        assert "- **成功率**: 0.0%" in metrics_section
        assert "### 失敗タイプ分布" in metrics_section
        assert "- ❌ **assertion**: 1件" in metrics_section


class TestJSONFormatting:
    """JSON 形式の出力テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter(sanitize_secrets=False)

        # テスト用のサンプルデータ
        failure = Failure(
            type=FailureType.ERROR,
            message="Runtime error occurred",
            file_path="main.py",
            line_number=10,
            context_before=["import sys"],
            context_after=["sys.exit(1)"],
            stack_trace="RuntimeError: Something went wrong",
        )

        step = StepResult(name="Build", success=False, duration=1.5, output="Build failed")
        job = JobResult(name="build-job", success=False, failures=[failure], steps=[step], duration=2.0)
        workflow = WorkflowResult(name="build-workflow", success=False, jobs=[job], duration=2.0)

        self.execution_result = ExecutionResult(
            success=False, workflows=[workflow], total_duration=2.0, timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

    def test_format_json_structure(self):
        """JSON形式の構造テスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        # トップレベルキーの確認
        assert "execution_summary" in data
        assert "metrics" in data
        assert "workflows" in data
        assert "failures" in data

    def test_format_json_execution_summary(self):
        """JSON形式の実行サマリーテスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        summary = data["execution_summary"]
        assert summary["success"] is False
        assert summary["timestamp"] == "2024-01-01T12:00:00"
        assert summary["total_duration"] == 2.0
        assert summary["total_workflows"] == 1
        assert summary["total_failures"] == 1

    def test_format_json_metrics(self):
        """JSON形式のメトリクステスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        metrics = data["metrics"]
        assert metrics["total_workflows"] == 1
        assert metrics["total_jobs"] == 1
        assert metrics["total_steps"] == 1
        assert metrics["total_failures"] == 1
        assert metrics["success_rate"] == 0.0
        assert metrics["average_duration"] == 2.0
        assert metrics["failure_types"]["error"] == 1

    def test_format_json_workflows(self):
        """JSON形式のワークフローテスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        workflows = data["workflows"]
        assert len(workflows) == 1

        workflow = workflows[0]
        assert workflow["name"] == "build-workflow"
        assert workflow["success"] is False
        assert workflow["duration"] == 2.0
        assert len(workflow["jobs"]) == 1

    def test_format_json_jobs(self):
        """JSON形式のジョブテスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        job = data["workflows"][0]["jobs"][0]
        assert job["name"] == "build-job"
        assert job["success"] is False
        assert job["duration"] == 2.0
        assert job["failure_count"] == 1
        assert len(job["failures"]) == 1
        assert len(job["steps"]) == 1

    def test_format_json_failures(self):
        """JSON形式の失敗情報テスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        failures = data["failures"]
        assert len(failures) == 1

        failure = failures[0]
        assert failure["type"] == "error"
        assert failure["message"] == "Runtime error occurred"
        assert failure["file_path"] == "main.py"
        assert failure["line_number"] == 10
        assert failure["context_before"] == ["import sys"]
        assert failure["context_after"] == ["sys.exit(1)"]
        assert failure["stack_trace"] == "RuntimeError: Something went wrong"

    def test_format_json_steps(self):
        """JSON形式のステップテスト"""
        result = self.formatter.format_json(self.execution_result)
        data = json.loads(result)

        step = data["workflows"][0]["jobs"][0]["steps"][0]
        assert step["name"] == "Build"
        assert step["success"] is False
        assert step["duration"] == 1.5
        assert step["output"] == "Build failed"

    def test_format_json_valid_json(self):
        """生成されたJSONが有効であることのテスト"""
        result = self.formatter.format_json(self.execution_result)

        # JSONとしてパースできることを確認
        try:
            json.loads(result)
        except json.JSONDecodeError:
            pytest.fail("Generated JSON is not valid")

    def test_format_json_unicode_handling(self):
        """JSON形式でのUnicode文字の処理テスト"""
        # 日本語を含む失敗メッセージ
        failure = Failure(type=FailureType.ERROR, message="エラーが発生しました: テスト失敗", file_path="テスト.py")

        job = JobResult(name="テストジョブ", success=False, failures=[failure])
        workflow = WorkflowResult(name="テストワークフロー", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        result = self.formatter.format_json(execution_result)
        data = json.loads(result)

        # Unicode文字が正しく保持されていることを確認
        assert "エラーが発生しました" in data["failures"][0]["message"]
        assert data["workflows"][0]["name"] == "テストワークフロー"


class TestTokenCounting:
    """トークン数カウント機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter()

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_count_tokens_with_tiktoken(self, mock_tiktoken):
        """tiktoken利用時のトークン数カウントテスト"""
        # モックの設定
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5トークン
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        content = "This is a test content"
        result = self.formatter.count_tokens(content, "gpt-4")

        assert result == 5
        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4")
        mock_encoding.encode.assert_called_once_with(content)

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_count_tokens_unknown_model(self, mock_tiktoken):
        """未知のモデルでのトークン数カウントテスト"""
        # モックの設定：encoding_for_modelでKeyErrorを発生させる
        mock_tiktoken.encoding_for_model.side_effect = KeyError("Unknown model")

        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1, 2, 3]  # 3トークン
        mock_tiktoken.get_encoding.return_value = mock_encoding

        content = "Test content"
        result = self.formatter.count_tokens(content, "unknown-model")

        assert result == 3
        mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")

    @patch("ci_helper.core.ai_formatter.tiktoken", None)
    def test_count_tokens_no_tiktoken(self):
        """tiktokenがない場合のエラーテスト"""
        content = "Test content"

        with pytest.raises(ImportError) as exc_info:
            self.formatter.count_tokens(content)

        assert "tiktokenがインストールされていません" in str(exc_info.value)

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_check_token_limits_normal(self, mock_tiktoken):
        """通常のトークン制限チェックテスト"""
        # モックの設定：100トークンと仮定
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1] * 100  # 100トークン
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        content = "Test content"
        result = self.formatter.check_token_limits(content, "gpt-4")

        # gpt-4の制限は8192なので、100/8192 = 約1.2%
        assert result["token_count"] == 100
        assert result["token_limit"] == 8192
        assert result["usage_ratio"] == pytest.approx(100 / 8192)
        assert result["usage_percentage"] == pytest.approx(100 / 8192 * 100)
        assert result["warning_level"] == "none"
        assert result["warning_message"] == ""
        assert result["model"] == "gpt-4"

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_check_token_limits_warning_levels(self, mock_tiktoken):
        """トークン制限の警告レベルテスト"""
        mock_encoding = Mock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        # 50%使用（info レベル）
        mock_encoding.encode.return_value = [1] * 4096  # 4096トークン
        result = self.formatter.check_token_limits("content", "gpt-4")
        assert result["warning_level"] == "info"
        assert "50%" in result["warning_message"]

        # 70%使用（warning レベル）
        mock_encoding.encode.return_value = [1] * 5735  # 5735トークン (70% of 8192)
        result = self.formatter.check_token_limits("content", "gpt-4")
        assert result["warning_level"] == "warning"
        assert "70%" in result["warning_message"]

        # 90%使用（critical レベル）
        mock_encoding.encode.return_value = [1] * 7373  # 約90%
        result = self.formatter.check_token_limits("content", "gpt-4")
        assert result["warning_level"] == "critical"
        assert "90%" in result["warning_message"]
        assert "圧縮を検討" in result["warning_message"]

    @patch("ci_helper.core.ai_formatter.tiktoken", None)
    def test_check_token_limits_no_tiktoken_fallback(self):
        """tiktokenがない場合のフォールバック推定テスト"""
        content = "a" * 400  # 400文字
        result = self.formatter.check_token_limits(content, "gpt-4")

        # 文字数ベースの推定：400 / 4 = 100トークン
        assert result["token_count"] == 100
        assert result["token_limit"] == 8192

    def test_check_token_limits_different_models(self):
        """異なるモデルでのトークン制限テスト"""
        with patch("ci_helper.core.ai_formatter.tiktoken") as mock_tiktoken:
            mock_encoding = Mock()
            mock_encoding.encode.return_value = [1] * 1000  # 1000トークン
            mock_tiktoken.encoding_for_model.return_value = mock_encoding

            # gpt-3.5-turbo（制限: 4096）
            result = self.formatter.check_token_limits("content", "gpt-3.5-turbo")
            assert result["token_limit"] == 4096

            # gpt-4-32k（制限: 32768）
            result = self.formatter.check_token_limits("content", "gpt-4-32k")
            assert result["token_limit"] == 32768

            # claude-3-sonnet（制限: 200000）
            result = self.formatter.check_token_limits("content", "claude-3-sonnet")
            assert result["token_limit"] == 200000

            # 未知のモデル（デフォルト: 8192）
            result = self.formatter.check_token_limits("content", "unknown-model")
            assert result["token_limit"] == 8192


class TestFormatWithTokenInfo:
    """フォーマット結果とトークン情報の統合テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter(sanitize_secrets=False)

        # シンプルな実行結果
        job = JobResult(name="test", success=True)
        workflow = WorkflowResult(name="test", success=True, jobs=[job])
        self.execution_result = ExecutionResult(success=True, workflows=[workflow], total_duration=1.0)

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_format_with_token_info_markdown(self, mock_tiktoken):
        """Markdown形式でのトークン情報付きフォーマットテスト"""
        # モックの設定
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1] * 500  # 500トークン
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        result = self.formatter.format_with_token_info(self.execution_result, format_type="markdown", model="gpt-4")

        assert "content" in result
        assert "format" in result
        assert "token_info" in result

        assert result["format"] == "markdown"
        assert "# CI実行結果" in result["content"]
        assert result["token_info"]["token_count"] == 500
        assert result["token_info"]["model"] == "gpt-4"

    @patch("ci_helper.core.ai_formatter.tiktoken")
    def test_format_with_token_info_json(self, mock_tiktoken):
        """JSON形式でのトークン情報付きフォーマットテスト"""
        # モックの設定
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1] * 300  # 300トークン
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        result = self.formatter.format_with_token_info(self.execution_result, format_type="json", model="gpt-3.5-turbo")

        assert result["format"] == "json"

        # JSONとしてパースできることを確認
        json_data = json.loads(result["content"])
        assert "execution_summary" in json_data

        assert result["token_info"]["token_count"] == 300
        assert result["token_info"]["model"] == "gpt-3.5-turbo"


class TestCompressionSuggestions:
    """圧縮提案機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter()

    def test_suggest_compression_mAny_failures(self):
        """多数の失敗がある場合の圧縮提案テスト"""
        # 15個の失敗を作成
        failures = [Failure(type=FailureType.ERROR, message=f"Error {i}") for i in range(15)]

        job = JobResult(name="test", success=False, failures=failures)
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        assert Any("最も重要な失敗のみに絞り込む" in s for s in suggestions)

    def test_suggest_compression_long_context(self):
        """長いコンテキストがある場合の圧縮提案テスト"""
        failure = Failure(
            type=FailureType.ERROR,
            message="Error",
            context_before=["line " + str(i) for i in range(10)],  # 10行のコンテキスト
            context_after=["line " + str(i) for i in range(10)],
        )

        job = JobResult(name="test", success=False, failures=[failure])
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        assert Any("コンテキスト行数を削減" in s for s in suggestions)

    def test_suggest_compression_stack_traces(self):
        """スタックトレースがある場合の圧縮提案テスト"""
        failure = Failure(type=FailureType.ERROR, message="Error", stack_trace="Long stack trace here...")

        job = JobResult(name="test", success=False, failures=[failure])
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        assert Any("スタックトレースを要約" in s for s in suggestions)

    def test_suggest_compression_mAny_workflows(self):
        """多数のワークフローがある場合の圧縮提案テスト"""
        # 7個のワークフローを作成
        workflows = []
        for i in range(7):
            job = JobResult(name=f"job{i}", success=True)
            workflow = WorkflowResult(name=f"workflow{i}", success=True, jobs=[job])
            workflows.append(workflow)

        execution_result = ExecutionResult(success=True, workflows=workflows, total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        assert Any("失敗したワークフローのみに絞り込む" in s for s in suggestions)

    def test_suggest_compression_mAny_jobs(self):
        """多数のジョブがある場合の圧縮提案テスト"""
        # 15個のジョブを作成
        jobs = [JobResult(name=f"job{i}", success=True) for i in range(15)]
        workflow = WorkflowResult(name="test", success=True, jobs=jobs)
        execution_result = ExecutionResult(success=True, workflows=[workflow], total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        assert Any("失敗したジョブのみに絞り込む" in s for s in suggestions)

    def test_suggest_compression_default_suggestions(self):
        """デフォルトの圧縮提案テスト"""
        # シンプルな成功実行
        job = JobResult(name="test", success=True)
        workflow = WorkflowResult(name="test", success=True, jobs=[job])
        execution_result = ExecutionResult(success=True, workflows=[workflow], total_duration=1.0)

        suggestions = self.formatter.suggest_compression_options(execution_result)

        # デフォルトの提案が含まれることを確認
        assert Any("JSON形式を使用" in s for s in suggestions)
        assert Any("成功したワークフローの詳細を除外" in s for s in suggestions)
        assert Any("メトリクス情報のみに絞り込む" in s for s in suggestions)


class TestSecurityFeatures:
    """セキュリティ機能のテスト"""

    def test_formatter_with_sanitization_enabled(self):
        """サニタイズ有効時のフォーマッターテスト"""
        formatter = AIFormatter(sanitize_secrets=True)

        assert formatter.sanitize_secrets is True
        assert hasattr(formatter, "security_validator")

    @patch("ci_helper.core.ai_formatter.SecurityValidator")
    def test_sanitize_content_called(self, mock_security_validator_class):
        """コンテンツサニタイズが呼ばれることのテスト"""
        # モックの設定
        mock_validator = Mock()
        mock_detector = Mock()
        mock_detector.sanitize_content.return_value = "sanitized content"
        mock_validator.secret_detector = mock_detector
        mock_security_validator_class.return_value = mock_validator

        formatter = AIFormatter(sanitize_secrets=True)

        # テスト用の実行結果
        job = JobResult(name="test", success=True)
        workflow = WorkflowResult(name="test", success=True, jobs=[job])
        execution_result = ExecutionResult(success=True, workflows=[workflow], total_duration=1.0)

        # Markdown形式でフォーマット
        formatter.format_markdown(execution_result)

        # サニタイズが呼ばれたことを確認
        mock_detector.sanitize_content.assert_called_once()

    def test_sanitize_content_error_handling(self):
        """サニタイズエラー時の処理テスト"""
        formatter = AIFormatter(sanitize_secrets=True)

        # security_validatorを削除してエラーを発生させる
        if hasattr(formatter, "security_validator"):
            delattr(formatter, "security_validator")

        # エラーが発生しても元のコンテンツが返されることを確認
        original_content = "test content"
        result = formatter._sanitize_content(original_content)

        assert result == original_content

    @patch("ci_helper.core.ai_formatter.SecurityValidator")
    def test_validate_output_security(self, mock_security_validator_class):
        """出力セキュリティ検証のテスト"""
        # モックの設定
        mock_validator = Mock()
        mock_validator.validate_log_content.return_value = {
            "has_secrets": True,
            "secret_count": 2,
            "detected_secrets": ["api_key", "password"],
            "recommendations": ["Remove API keys"],
        }
        mock_security_validator_class.return_value = mock_validator

        formatter = AIFormatter(sanitize_secrets=True)

        result = formatter.validate_output_security("content with secrets")

        assert result["has_secrets"] is True
        assert result["secret_count"] == 2
        assert "api_key" in result["detected_secrets"]
        mock_validator.validate_log_content.assert_called_once_with("content with secrets")

    def test_validate_output_security_no_validator(self):
        """セキュリティバリデーターがない場合のテスト"""
        formatter = AIFormatter(sanitize_secrets=False)

        result = formatter.validate_output_security("test content")

        assert result["has_secrets"] is False
        assert result["secret_count"] == 0
        assert result["detected_secrets"] == []
        assert "セキュリティ検証が無効" in result["recommendations"][0]


class TestEdgeCases:
    """エッジケースのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.formatter = AIFormatter(sanitize_secrets=False)

    def test_empty_execution_result(self):
        """空の実行結果のテスト"""
        execution_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        # Markdown形式
        markdown_result = self.formatter.format_markdown(execution_result)
        assert "**ワークフロー数**: 0" in markdown_result
        assert "**総失敗数**: 0" in markdown_result

        # JSON形式
        json_result = self.formatter.format_json(execution_result)
        data = json.loads(json_result)
        assert data["execution_summary"]["total_workflows"] == 0
        assert len(data["workflows"]) == 0
        assert len(data["failures"]) == 0

    def test_failure_without_optional_fields(self):
        """オプションフィールドがない失敗のテスト"""
        failure = Failure(type=FailureType.UNKNOWN, message="Unknown error")

        job = JobResult(name="test", success=False, failures=[failure])
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        # Markdown形式でフォーマット
        result = self.formatter.format_markdown(execution_result)

        # オプションフィールドがなくてもエラーにならないことを確認
        assert "Unknown error" in result
        assert "❓ **unknown**: 1件" in result

    def test_very_long_content_handling(self):
        """非常に長いコンテンツの処理テスト"""
        # 非常に長いエラーメッセージ
        long_message = "Error: " + "x" * 10000
        failure = Failure(type=FailureType.ERROR, message=long_message)

        job = JobResult(name="test", success=False, failures=[failure])
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        # フォーマットが正常に完了することを確認
        markdown_result = self.formatter.format_markdown(execution_result)
        json_result = self.formatter.format_json(execution_result)

        assert long_message in markdown_result

        data = json.loads(json_result)
        assert data["failures"][0]["message"] == long_message

    def test_unicode_and_special_characters(self):
        """Unicode文字と特殊文字の処理テスト"""
        # 様々な特殊文字を含むメッセージ
        special_message = "エラー: 🚨 テスト失敗 \n\t\"quotes\" 'apostrophe' & <tags>"
        failure = Failure(type=FailureType.ERROR, message=special_message)

        job = JobResult(name="テスト", success=False, failures=[failure])
        workflow = WorkflowResult(name="ワークフロー", success=False, jobs=[job])
        execution_result = ExecutionResult(success=False, workflows=[workflow], total_duration=1.0)

        # Markdown形式
        markdown_result = self.formatter.format_markdown(execution_result)
        assert special_message in markdown_result

        # JSON形式（有効なJSONであることを確認）
        json_result = self.formatter.format_json(execution_result)
        data = json.loads(json_result)
        assert data["failures"][0]["message"] == special_message
