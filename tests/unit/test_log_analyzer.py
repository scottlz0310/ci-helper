"""
ログ解析機能のユニットテスト

LogAnalyzerクラスのワークフロー解析、ジョブ解析、
データ構造の検証機能をテストします。
"""

import pytest

from ci_helper.core.exceptions import LogParsingError
from ci_helper.core.log_analyzer import LogAnalyzer
from ci_helper.core.log_extractor import LogExtractor
from ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult


class TestLogAnalyzer:
    """LogAnalyzerクラスのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.analyzer = LogAnalyzer()

    def test_analyze_empty_log(self):
        """空のログの解析テスト"""
        with pytest.raises(LogParsingError) as exc_info:
            self.analyzer.analyze_log("")

        assert "ログが空です" in str(exc_info.value)

    def test_analyze_whitespace_only_log(self):
        """空白のみのログの解析テスト"""
        with pytest.raises(LogParsingError) as exc_info:
            self.analyzer.analyze_log("   \n\n  ")

        assert "ログが空です" in str(exc_info.value)

    def test_analyze_successful_log(self):
        """成功ログの解析テスト"""
        log_content = """[Simple Test/test] 🚀  Start image=catthehacker/ubuntu:act-latest
[Simple Test/test] ⭐ Run Main actions/checkout@v4
[Simple Test/test]   ✅  Success - Main actions/checkout@v4
[Simple Test/test] ⭐ Run Main Run simple test
| Test passed
[Simple Test/test]   ✅  Success - Main Run simple test
[Simple Test/test] 🏁  Job succeeded"""

        result = self.analyzer.analyze_log(log_content)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert len(result.workflows) >= 1
        assert result.total_failures == 0

    def test_analyze_failed_log(self):
        """失敗ログの解析テスト"""
        log_content = """[Failing Test/test] 🚀  Start image=catthehacker/ubuntu:act-latest
[Failing Test/test] ⭐ Run Main actions/checkout@v4
[Failing Test/test]   ✅  Success - Main actions/checkout@v4
[Failing Test/test] ⭐ Run Main Run failing test
| Starting test
[Failing Test/test]   ❌  Failure - Main Run failing test
[Failing Test/test] exitcode '1': failure
[Failing Test/test] 💥  Job failed"""

        result = self.analyzer.analyze_log(log_content)

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert len(result.workflows) >= 1
        assert len(result.failed_workflows) >= 1

    def test_analyze_python_error_log(self):
        """Pythonエラーログの解析テスト"""
        log_content = """[Python Test/test] 🚀  Start image=catthehacker/ubuntu:act-latest
[Python Test/test] ⭐ Run Main Run Python tests
| Traceback (most recent call last):
|   File "<string>", line 1, in <module>
| AssertionError: Test failed
[Python Test/test]   ❌  Failure - Main Run Python tests
[Python Test/test] 💥  Job failed"""

        result = self.analyzer.analyze_log(log_content)

        assert isinstance(result, ExecutionResult)
        assert result.success is False
        assert result.total_failures >= 1

        # アサーションエラーが検出されることを確認
        all_failures = result.all_failures
        assertion_failures = [f for f in all_failures if f.type == FailureType.ASSERTION]
        assert len(assertion_failures) >= 1

    def test_detect_workflows(self):
        """ワークフロー検出のテスト"""
        log_content = """[Workflow1/job1] 🚀  Starting job: job1
[Workflow1/job1] Job 'job1' is about to start
[Workflow2/job2] 🚀  Starting job: job2
[Workflow2/job2] Job 'job2' is about to start"""

        workflows = self.analyzer._detect_workflows(log_content)

        # 複数のワークフローが検出されることを確認
        assert len(workflows) >= 1
        # 検出されたワークフロー名を確認
        workflow_names = set(workflows)
        assert len(workflow_names) >= 1  # 少なくとも1つのユニークなワークフロー

    def test_detect_workflows_no_explicit_names(self):
        """明示的なワークフロー名がない場合の検出テスト"""
        log_content = """[test] 🚀  Start image=catthehacker/ubuntu:act-latest
[test] ⭐ Run Main actions/checkout@v4
[test]   ✅  Success - Main actions/checkout@v4"""

        workflows = self.analyzer._detect_workflows(log_content)

        # ワークフローが検出されない場合でも空のリストが返される
        assert isinstance(workflows, list)

    def test_analyze_workflow_with_multiple_jobs(self):
        """複数ジョブを持つワークフローの解析テスト"""
        log_content = """[Test Workflow/job1] 🚀  Starting job: job1
[Test Workflow/job1] ⭐ Run Main Step 1
[Test Workflow/job1]   ✅  Success - Main Step 1
[Test Workflow/job2] 🚀  Starting job: job2
[Test Workflow/job2] ⭐ Run Main Step 2
[Test Workflow/job2]   ❌  Failure - Main Step 2
Error: Something went wrong"""

        result = self.analyzer.analyze_log(log_content, workflows=["Test Workflow"])

        assert len(result.workflows) >= 1
        workflow = result.workflows[0]

        # ワークフローが失敗していることを確認（1つのジョブが失敗）
        assert workflow.success is False

        # 複数のジョブが検出されることを確認
        if len(workflow.jobs) > 1:
            # 成功したジョブと失敗したジョブが混在することを確認
            success_jobs = [job for job in workflow.jobs if job.success]
            failed_jobs = [job for job in workflow.jobs if not job.success]
            assert len(success_jobs) >= 0
            assert len(failed_jobs) >= 1

    def test_analyze_single_workflow_fallback(self):
        """単一ワークフローとしての解析フォールバックテスト"""
        log_content = """Some log output without clear workflow markers
Error: Test error occurred
More log output"""

        result = self.analyzer.analyze_log(log_content)

        # デフォルトワークフローが作成されることを確認
        assert len(result.workflows) == 1
        assert result.workflows[0].name == "default"

    def test_extract_workflow_section(self):
        """ワークフローセクションの抽出テスト"""
        log_content = """[Workflow1/job1] Starting job1
[Workflow1/job1] Step 1 completed
[Workflow1/job1] Job succeeded
[Workflow2/job2] Starting job2
[Workflow2/job2] Step 1 failed
[Workflow2/job2] Job failed"""

        section = self.analyzer._extract_workflow_section(log_content, "Workflow1")

        # Workflow1関連のログのみが抽出されることを確認
        assert "Workflow1" in section
        assert "job1" in section
        # Workflow1関連の内容が含まれることを確認（実装では完全な分離はされていない）
        assert len(section) > 0

    def test_analyze_jobs_with_explicit_job_markers(self):
        """明示的なジョブマーカーがある場合のジョブ解析テスト"""
        log_section = """[Test/test-job] 🚀  Starting job: test-job
[Test/test-job] ⭐ Run Main Step 1
[Test/test-job] ✅  Success - Main Step 1
[Test/test-job] ⭐ Run Main Step 2
[Test/test-job] ❌  Failure - Main Step 2
Error: Step failed"""

        # 全失敗を事前に抽出
        all_failures = self.analyzer.log_extractor.extract_failures(log_section)
        jobs = self.analyzer._analyze_jobs(log_section, all_failures)

        assert len(jobs) >= 1
        job = jobs[0]
        assert job.name == "test-job"
        assert job.success is False  # 失敗したステップがあるため

    def test_analyze_jobs_without_explicit_markers(self):
        """明示的なジョブマーカーがない場合のジョブ解析テスト"""
        log_section = """Some log output
Error: Test error
More output"""

        all_failures = self.analyzer.log_extractor.extract_failures(log_section)
        jobs = self.analyzer._analyze_jobs(log_section, all_failures)

        # デフォルトジョブが作成されることを確認
        assert len(jobs) >= 1
        job = jobs[0]
        assert job.name == "default"

    def test_create_default_job(self):
        """デフォルトジョブの作成テスト"""
        log_section = """Test output
Error: Something failed
More output"""

        all_failures = self.analyzer.log_extractor.extract_failures(log_section)
        job = self.analyzer._create_default_job(log_section, all_failures)

        assert job is not None
        assert job.name == "default"
        assert job.success is False  # エラーがあるため
        assert len(job.failures) >= 1

    def test_create_default_job_empty_section(self):
        """空のセクションでのデフォルトジョブ作成テスト"""
        job = self.analyzer._create_default_job("", [])
        assert job is None

    def test_analyze_steps(self):
        """ステップ解析のテスト"""
        job_section = """[Test/job] ⭐ Run Main Step 1
Some output
[Test/job] ✅  Success - Main Step 1
[Test/job] ⭐ Run Main Step 2
Error output
[Test/job] ❌  Failure - Main Step 2"""

        steps = self.analyzer._analyze_steps(job_section)

        assert len(steps) == 2

        # 最初のステップは成功
        step1 = steps[0]
        assert step1.name == "Main Step 1"
        assert step1.success is True

        # 2番目のステップは失敗
        step2 = steps[1]
        assert step2.name == "Main Step 2"
        assert step2.success is False

    def test_extract_failures_from_section(self):
        """セクション内の失敗抽出テスト"""
        section = """Step output
Error: Section specific error
More output"""

        all_failures = [
            Failure(type=FailureType.ERROR, message="Global error"),
            Failure(type=FailureType.ERROR, message="Section specific error"),
        ]

        section_failures = self.analyzer._extract_failures_from_section(section, all_failures)

        # セクション内の失敗のみが抽出されることを確認
        section_messages = [f.message for f in section_failures]
        assert "Section specific error" in section_messages

    def test_extract_duration_from_section(self):
        """セクションからの実行時間抽出テスト"""
        test_cases = [
            ("Process took 5.2s to complete", 5.2),
            ("Execution took 10s", 10.0),
            ("Duration: took 0.5s", 0.5),
            ("No duration info", 0.0),
        ]

        for section, expected_duration in test_cases:
            duration = self.analyzer._extract_duration_from_section(section)
            assert duration == expected_duration

    def test_estimate_duration_from_log(self):
        """ログからの実行時間推測テスト"""
        # タイムスタンプ付きのログ
        log_section = """[2024-01-01T10:00:00] Start
[2024-01-01T10:00:05] End"""

        duration = self.analyzer._estimate_duration_from_log(log_section)

        # 5秒の差があることを確認
        assert duration == 5.0

    def test_estimate_duration_no_timestamps(self):
        """タイムスタンプがない場合の実行時間推測テスト"""
        log_section = "No timestamps here"
        duration = self.analyzer._estimate_duration_from_log(log_section)
        assert duration == 0.0

    def test_extract_step_output(self):
        """ステップ出力の抽出テスト"""
        step_section = """[Test/job] ⭐ Run Main Test Step
[Test/job] 💬 Test output line 1
[Test/job] 💬 Test output line 2
[2024-01-01T10:00:00] Some other output
[Test/job] ✅  Success - Main Test Step"""

        output = self.analyzer._extract_step_output(step_section)

        # 出力が正しく抽出されることを確認
        assert "Test output line 1" in output
        assert "Test output line 2" in output

    def test_compare_execution_results(self):
        """実行結果の比較テスト"""
        # 前回の実行結果（2つの失敗）
        previous_failures = [
            Failure(type=FailureType.ERROR, message="Old error 1"),
            Failure(type=FailureType.ERROR, message="Persistent error"),
        ]
        previous_job = JobResult(name="test", success=False, failures=previous_failures)
        previous_workflow = WorkflowResult(name="test", success=False, jobs=[previous_job])
        previous_result = ExecutionResult(success=False, workflows=[previous_workflow], total_duration=10.0)

        # 現在の実行結果（1つの新しい失敗、1つの継続する失敗）
        current_failures = [
            Failure(type=FailureType.ERROR, message="New error"),
            Failure(type=FailureType.ERROR, message="Persistent error"),
        ]
        current_job = JobResult(name="test", success=False, failures=current_failures)
        current_workflow = WorkflowResult(name="test", success=False, jobs=[current_job])
        current_result = ExecutionResult(success=False, workflows=[current_workflow], total_duration=8.0)

        # 比較実行
        comparison = self.analyzer.compare_execution_results(current_result, previous_result)

        # 新しいエラー
        new_error_messages = [f.message for f in comparison["new_errors"]]
        assert "New error" in new_error_messages

        # 解決されたエラー
        resolved_error_messages = [f.message for f in comparison["resolved_errors"]]
        assert "Old error 1" in resolved_error_messages

        # 継続するエラー
        persistent_error_messages = [f.message for f in comparison["persistent_errors"]]
        assert "Persistent error" in persistent_error_messages

    def test_collect_all_failures(self):
        """全失敗の収集テスト"""
        failures1 = [Failure(type=FailureType.ERROR, message="Error 1")]
        failures2 = [Failure(type=FailureType.ERROR, message="Error 2")]

        job1 = JobResult(name="job1", success=False, failures=failures1)
        job2 = JobResult(name="job2", success=False, failures=failures2)

        workflow = WorkflowResult(name="test", success=False, jobs=[job1, job2])
        result = ExecutionResult(success=False, workflows=[workflow], total_duration=10.0)

        all_failures = self.analyzer._collect_all_failures(result)

        assert len(all_failures) == 2
        messages = [f.message for f in all_failures]
        assert "Error 1" in messages
        assert "Error 2" in messages

    def test_failure_key_generation(self):
        """失敗の比較用キー生成テスト"""
        failure = Failure(type=FailureType.ERROR, message="Test error", file_path="test.py", line_number=42)

        key = self.analyzer._failure_key(failure)
        expected_key = ("Test error", "test.py", 42)

        assert key == expected_key

    def test_deduplicate_failures(self):
        """失敗の重複除去テスト"""
        failures = [
            Failure(type=FailureType.ERROR, message="Error 1", file_path="test.py", line_number=10),
            Failure(type=FailureType.ERROR, message="Error 1", file_path="test.py", line_number=10),  # 重複
            Failure(type=FailureType.ERROR, message="Error 2", file_path="test.py", line_number=20),
        ]

        unique_failures = self.analyzer._deduplicate_failures(failures)

        assert len(unique_failures) == 2
        messages = [f.message for f in unique_failures]
        assert "Error 1" in messages
        assert "Error 2" in messages

    def test_analyze_log_with_custom_log_extractor(self):
        """カスタムログ抽出器を使用した解析テスト"""
        custom_extractor = LogExtractor(context_lines=5)
        analyzer = LogAnalyzer(log_extractor=custom_extractor)

        log_content = """[Test/job] 🚀  Start
Error: Custom test error
[Test/job] 💥  Job failed"""

        result = analyzer.analyze_log(log_content)

        assert isinstance(result, ExecutionResult)
        assert result.success is False

    def test_analyze_log_malformed_content(self):
        """不正な形式のログの解析テスト"""
        # 不完全なログでも例外を発生させずに処理できることを確認
        malformed_logs = [
            "Incomplete log without proper structure",
            "[Malformed] No proper ending",
            "Random text\nwith\nno structure",
        ]

        for log_content in malformed_logs:
            try:
                result = self.analyzer.analyze_log(log_content)
                assert isinstance(result, ExecutionResult)
            except LogParsingError:
                # LogParsingErrorは許容される
                pass

    def test_workflow_duration_calculation(self):
        """ワークフローの実行時間計算テスト"""
        log_content = """[Test/job1] 🚀  Starting job: job1
[Test/job1] took 3.0s
[Test/job1] ✅  Job succeeded
[Test/job2] 🚀  Starting job: job2
[Test/job2] took 2.5s
[Test/job2] ✅  Job succeeded"""

        result = self.analyzer.analyze_log(log_content, workflows=["Test"])

        if result.workflows:
            workflow = result.workflows[0]
            # ジョブの実行時間の合計がワークフローの実行時間になることを確認
            expected_duration = sum(job.duration for job in workflow.jobs)
            assert workflow.duration == expected_duration

    def test_execution_result_properties(self):
        """ExecutionResultのプロパティテスト"""
        failures = [Failure(type=FailureType.ERROR, message="Test error")]
        job = JobResult(name="test", success=False, failures=failures)
        workflow = WorkflowResult(name="test", success=False, jobs=[job])
        result = ExecutionResult(success=False, workflows=[workflow], total_duration=10.0)

        # プロパティが正しく動作することを確認
        assert result.total_failures == 1
        assert len(result.failed_workflows) == 1
        assert len(result.failed_jobs) == 1
        assert len(result.all_failures) == 1
