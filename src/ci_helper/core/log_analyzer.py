"""
ログ解析システム

actの実行ログを解析し、ワークフローとジョブごとに失敗を整理します。
"""

from __future__ import annotations

import re
from datetime import datetime

from ..core.exceptions import LogParsingError
from ..core.log_extractor import LogExtractor
from ..core.models import ExecutionResult, Failure, JobResult, StepResult, WorkflowResult


class LogAnalyzer:
    """ログを解析してワークフローとジョブごとに失敗を整理するクラス"""

    def __init__(self, log_extractor: LogExtractor | None = None):
        """ログアナライザーを初期化

        Args:
            log_extractor: ログ抽出器（Noneの場合は新規作成）
        """
        self.log_extractor = log_extractor or LogExtractor()
        self._compile_act_patterns()

    def _compile_act_patterns(self) -> None:
        """act特有のログパターンをコンパイル"""
        # ワークフロー開始パターン
        self.workflow_start_pattern = re.compile(r"^\[.*\]\s*🚀\s*Start image=.*$", re.MULTILINE)

        # ワークフロー名抽出パターン
        self.workflow_name_pattern = re.compile(r"^\[.*\]\s*.*Job '([^']+)' is about to start", re.MULTILINE)

        # ジョブ開始パターン
        self.job_start_pattern = re.compile(r"^\[.*\]\s*🚀\s*Starting job: ([^\s]+)", re.MULTILINE)

        # ジョブ終了パターン
        self.job_end_pattern = re.compile(r"^\[.*\]\s*✅\s*Job succeeded|^\[.*\]\s*❌\s*Job failed", re.MULTILINE)

        # ステップ開始パターン
        self.step_start_pattern = re.compile(r"^\[.*\]\s*⭐\s*Run (.+)$", re.MULTILINE)

        # ステップ終了パターン
        self.step_end_pattern = re.compile(r"^\[.*\]\s*✅\s*Success - (.+)|^\[.*\]\s*❌\s*Failure - (.+)", re.MULTILINE)

        # 実行時間パターン
        self.duration_pattern = re.compile(r"took (\d+(?:\.\d+)?)s", re.MULTILINE)

        # エラー出力パターン
        self.error_output_pattern = re.compile(r"^\[.*\]\s*💬\s*(.+)$", re.MULTILINE)

    def analyze_log(self, log_content: str, workflows: list[str] | None = None) -> ExecutionResult:
        """ログを解析してExecutionResultを生成

        Args:
            log_content: actの実行ログ
            workflows: 実行されたワークフローのリスト（Noneの場合は自動検出）

        Returns:
            解析されたExecutionResult

        Raises:
            LogParsingError: ログ解析に失敗した場合
        """
        if not log_content or not log_content.strip():
            raise LogParsingError("ログが空です", "有効なactの実行ログを提供してください")

        try:
            # 全体の失敗を抽出
            all_failures = self.log_extractor.extract_failures(log_content)

            # ワークフローを検出または使用
            detected_workflows = workflows or self._detect_workflows(log_content)

            # ワークフローごとに解析
            workflow_results: list[WorkflowResult] = []
            total_duration = 0.0
            overall_success = True

            for workflow_name in detected_workflows:
                workflow_result = self._analyze_workflow(log_content, workflow_name, all_failures)
                workflow_results.append(workflow_result)
                total_duration += workflow_result.duration
                if not workflow_result.success:
                    overall_success = False

            # ワークフローが検出されない場合は単一のワークフローとして扱う
            if not workflow_results:
                workflow_result = self._analyze_single_workflow(log_content, all_failures)
                workflow_results.append(workflow_result)
                total_duration = workflow_result.duration
                overall_success = workflow_result.success

            return ExecutionResult(
                success=overall_success,
                workflows=workflow_results,
                total_duration=total_duration,
            )

        except Exception as e:
            raise LogParsingError(
                f"ログ解析中にエラーが発生しました: {e}", "ログファイルの形式を確認してください"
            ) from e

    def _detect_workflows(self, log_content: str) -> list[str]:
        """ログからワークフロー名を検出

        Args:
            log_content: ログ内容

        Returns:
            検出されたワークフロー名のリスト
        """
        workflow_names: set[str] = set()

        # ワークフロー名パターンから抽出
        for match in self.workflow_name_pattern.finditer(log_content):
            workflow_name = match.group(1)
            workflow_names.add(workflow_name)

        # ジョブ名からワークフローを推測
        for match in self.job_start_pattern.finditer(log_content):
            job_name = match.group(1)
            # ジョブ名からワークフロー名を推測（通常はファイル名ベース）
            if "/" in job_name:
                workflow_name = job_name.split("/")[0]
                workflow_names.add(workflow_name)

        return list(workflow_names)

    def _analyze_workflow(self, log_content: str, workflow_name: str, all_failures: list[Failure]) -> WorkflowResult:
        """特定のワークフローを解析

        Args:
            log_content: ログ内容
            workflow_name: ワークフロー名
            all_failures: 全失敗のリスト

        Returns:
            ワークフローの解析結果
        """
        # ワークフロー関連のログセクションを抽出
        workflow_section = self._extract_workflow_section(log_content, workflow_name)

        # ジョブを検出・解析
        jobs = self._analyze_jobs(workflow_section, all_failures)

        # ワークフローの成功/失敗を判定
        workflow_success = all(job.success for job in jobs)

        # 実行時間を計算
        workflow_duration = sum(job.duration for job in jobs)

        return WorkflowResult(
            name=workflow_name,
            success=workflow_success,
            jobs=jobs,
            duration=workflow_duration,
        )

    def _analyze_single_workflow(self, log_content: str, all_failures: list[Failure]) -> WorkflowResult:
        """単一のワークフローとしてログを解析

        Args:
            log_content: ログ内容
            all_failures: 全失敗のリスト

        Returns:
            ワークフローの解析結果
        """
        # ジョブを検出・解析
        jobs = self._analyze_jobs(log_content, all_failures)

        # デフォルトのワークフロー名
        workflow_name = "default"

        # ワークフローの成功/失敗を判定
        workflow_success = all(job.success for job in jobs) if jobs else True

        # 実行時間を計算
        workflow_duration = sum(job.duration for job in jobs)

        return WorkflowResult(
            name=workflow_name,
            success=workflow_success,
            jobs=jobs,
            duration=workflow_duration,
        )

    def _extract_workflow_section(self, log_content: str, workflow_name: str) -> str:
        """ワークフロー関連のログセクションを抽出

        Args:
            log_content: 全ログ内容
            workflow_name: ワークフロー名

        Returns:
            ワークフロー関連のログセクション
        """
        lines = log_content.splitlines()
        workflow_lines: list[str] = []
        in_workflow = False

        for line in lines:
            # ワークフロー開始の検出
            if workflow_name in line and ("Starting" in line or "Start" in line):
                in_workflow = True

            # ワークフロー終了の検出
            elif in_workflow and ("Job succeeded" in line or "Job failed" in line):
                workflow_lines.append(line)
                # 次のワークフローが始まるまで継続
                continue

            if in_workflow:
                workflow_lines.append(line)

        return "\n".join(workflow_lines)

    def _analyze_jobs(self, log_section: str, all_failures: list[Failure]) -> list[JobResult]:
        """ログセクションからジョブを解析

        Args:
            log_section: 解析対象のログセクション
            all_failures: 全失敗のリスト

        Returns:
            ジョブの解析結果リスト
        """
        jobs: list[JobResult] = []

        # ジョブ開始位置を検出
        job_matches: list[re.Match[str]] = list(self.job_start_pattern.finditer(log_section))

        if not job_matches:
            # ジョブが明示的に検出されない場合は、デフォルトジョブを作成
            job_result = self._create_default_job(log_section, all_failures)
            if job_result:
                jobs.append(job_result)
        else:
            # 各ジョブを解析
            for i, match in enumerate(job_matches):
                job_name = match.group(1)

                # ジョブのログセクションを抽出
                start_pos = match.start()
                end_pos = job_matches[i + 1].start() if i + 1 < len(job_matches) else len(log_section)
                job_section = log_section[start_pos:end_pos]

                # ジョブを解析
                job_result = self._analyze_single_job(job_name, job_section, all_failures)
                jobs.append(job_result)

        return jobs

    def _create_default_job(self, log_section: str, all_failures: list[Failure]) -> JobResult | None:
        """デフォルトジョブを作成

        Args:
            log_section: ログセクション
            all_failures: 全失敗のリスト

        Returns:
            デフォルトジョブの結果（作成できない場合はNone）
        """
        if not log_section.strip():
            return None

        # ログセクション内の失敗を抽出
        job_failures = self._extract_failures_from_section(log_section, all_failures)

        # ステップを解析
        steps = self._analyze_steps(log_section)

        # 成功/失敗を判定
        job_success = len(job_failures) == 0 and all(step.success for step in steps)

        # 実行時間を計算
        job_duration = sum(step.duration for step in steps)
        if job_duration == 0:
            # ステップから時間が取得できない場合は、ログから推測
            job_duration = self._estimate_duration_from_log(log_section)

        return JobResult(
            name="default",
            success=job_success,
            failures=job_failures,
            steps=steps,
            duration=job_duration,
        )

    def _analyze_single_job(self, job_name: str, job_section: str, all_failures: list[Failure]) -> JobResult:
        """単一のジョブを解析

        Args:
            job_name: ジョブ名
            job_section: ジョブのログセクション
            all_failures: 全失敗のリスト

        Returns:
            ジョブの解析結果
        """
        # ジョブセクション内の失敗を抽出
        job_failures = self._extract_failures_from_section(job_section, all_failures)

        # ステップを解析
        steps = self._analyze_steps(job_section)

        # 成功/失敗を判定
        job_success = len(job_failures) == 0 and all(step.success for step in steps)

        # 実行時間を計算
        job_duration = sum(step.duration for step in steps)
        if job_duration == 0:
            job_duration = self._estimate_duration_from_log(job_section)

        return JobResult(
            name=job_name,
            success=job_success,
            failures=job_failures,
            steps=steps,
            duration=job_duration,
        )

    def _analyze_steps(self, job_section: str) -> list[StepResult]:
        """ジョブセクションからステップを解析

        Args:
            job_section: ジョブのログセクション

        Returns:
            ステップの解析結果リスト
        """
        steps: list[StepResult] = []

        # ステップ開始位置を検出
        step_matches: list[re.Match[str]] = list(self.step_start_pattern.finditer(job_section))

        for i, match in enumerate(step_matches):
            step_name = match.group(1)

            # ステップのログセクションを抽出
            start_pos = match.start()
            end_pos = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(job_section)
            step_section = job_section[start_pos:end_pos]

            # ステップの成功/失敗を判定
            step_success = "❌" not in step_section and "Failure" not in step_section

            # ステップの実行時間を抽出
            step_duration = self._extract_duration_from_section(step_section)

            # ステップの出力を抽出
            step_output = self._extract_step_output(step_section)

            steps.append(
                StepResult(
                    name=step_name,
                    success=step_success,
                    duration=step_duration,
                    output=step_output,
                )
            )

        return steps

    def _extract_failures_from_section(self, section: str, all_failures: list[Failure]) -> list[Failure]:
        """セクション内の失敗を抽出

        Args:
            section: ログセクション
            all_failures: 全失敗のリスト

        Returns:
            セクション内の失敗のリスト
        """
        # セクション固有の失敗を直接抽出（より正確）
        section_failures: list[Failure] = self.log_extractor.extract_failures(section)

        # 全失敗リストからセクション内の失敗も確認
        for failure in all_failures:
            # 失敗のメッセージがセクション内に含まれているかチェック
            if failure.message in section:
                # 既に含まれていない場合のみ追加
                if not any(
                    f.message == failure.message
                    and f.file_path == failure.file_path
                    and f.line_number == failure.line_number
                    for f in section_failures
                ):
                    section_failures.append(failure)

        return self._deduplicate_failures(section_failures)

    def _extract_duration_from_section(self, section: str) -> float:
        """セクションから実行時間を抽出

        Args:
            section: ログセクション

        Returns:
            実行時間（秒）
        """
        duration_match = self.duration_pattern.search(section)
        if duration_match:
            try:
                return float(duration_match.group(1))
            except ValueError:
                pass

        return 0.0

    def _estimate_duration_from_log(self, log_section: str) -> float:
        """ログから実行時間を推測

        Args:
            log_section: ログセクション

        Returns:
            推定実行時間（秒）
        """
        # タイムスタンプパターンから時間を推測
        timestamp_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
        timestamps: list[datetime] = []

        for match in timestamp_pattern.finditer(log_section):
            timestamp_str = match.group(1)
            try:
                from datetime import datetime

                timestamp = datetime.fromisoformat(timestamp_str)
                timestamps.append(timestamp)
            except ValueError:
                continue

        if len(timestamps) >= 2:
            duration = (timestamps[-1] - timestamps[0]).total_seconds()
            return max(0.0, duration)

        return 0.0

    def _extract_step_output(self, step_section: str) -> str:
        """ステップの出力を抽出

        Args:
            step_section: ステップのログセクション

        Returns:
            ステップの出力
        """
        output_lines: list[str] = []

        # エラー出力パターンから出力を抽出
        for match in self.error_output_pattern.finditer(step_section):
            output_lines.append(match.group(1))

        # 通常の出力行も含める（actの出力形式に依存）
        lines = step_section.splitlines()
        for line in lines:
            # タイムスタンプ付きの出力行を抽出
            if re.match(r"^\[.*\]\s*💬", line):
                continue  # 既に上で処理済み
            elif re.match(r"^\[.*\]\s*", line):
                # その他のact出力
                clean_line = re.sub(r"^\[.*\]\s*", "", line)
                if clean_line.strip():
                    output_lines.append(clean_line)

        return "\n".join(output_lines)

    def compare_execution_results(
        self, current: ExecutionResult, previous: ExecutionResult
    ) -> dict[str, list[Failure]]:
        """実行結果を比較して差分を抽出

        Args:
            current: 現在の実行結果
            previous: 前回の実行結果

        Returns:
            差分情報（new_errors, resolved_errors, persistent_errors）
        """
        # 現在と前回の失敗を収集
        current_failures = self._collect_all_failures(current)
        previous_failures = self._collect_all_failures(previous)

        # 失敗を比較用のキーで分類
        current_keys = {self._failure_key(f): f for f in current_failures}
        previous_keys = {self._failure_key(f): f for f in previous_failures}

        # 差分を計算
        new_errors = [current_keys[key] for key in current_keys if key not in previous_keys]

        resolved_errors = [previous_keys[key] for key in previous_keys if key not in current_keys]

        persistent_errors = [current_keys[key] for key in current_keys if key in previous_keys]

        return {
            "new_errors": new_errors,
            "resolved_errors": resolved_errors,
            "persistent_errors": persistent_errors,
        }

    def _collect_all_failures(self, execution_result: ExecutionResult) -> list[Failure]:
        """ExecutionResultから全ての失敗を収集

        Args:
            execution_result: 実行結果

        Returns:
            全失敗のリスト
        """
        all_failures: list[Failure] = []
        for workflow in execution_result.workflows:
            for job in workflow.jobs:
                all_failures.extend(job.failures)
        return all_failures

    def _failure_key(self, failure: Failure) -> tuple[str, str | None, int | None]:
        """失敗の比較用キーを生成

        Args:
            failure: 失敗オブジェクト

        Returns:
            比較用のキー
        """
        return (failure.message, failure.file_path, failure.line_number)

    def _deduplicate_failures(self, failures: list[Failure]) -> list[Failure]:
        """重複する失敗を除去

        Args:
            failures: 失敗のリスト

        Returns:
            重複を除去した失敗のリスト
        """
        seen: set[tuple[str, str | None, int | None]] = set()
        unique_failures: list[Failure] = []

        for failure in failures:
            # メッセージ、ファイルパス、行番号の組み合わせで重複判定
            key = self._failure_key(failure)
            if key not in seen:
                seen.add(key)
                unique_failures.append(failure)

        return unique_failures
