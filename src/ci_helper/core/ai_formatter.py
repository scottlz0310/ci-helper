"""
AI用出力フォーマッター

CI実行結果をAI消費用のMarkdownおよびJSON形式でフォーマットします。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

try:
    import tiktoken
except ImportError:
    tiktoken = None

from ..core.models import AnalysisMetrics, ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from ..core.security import SecurityValidator


class AIFormatter:
    """AI消費用の出力フォーマッター"""

    def __init__(self, sanitize_secrets: bool = True):
        """フォーマッターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか
        """
        self.failure_type_icons = {
            FailureType.ERROR: "🚨",
            FailureType.ASSERTION: "❌",
            FailureType.TIMEOUT: "⏰",
            FailureType.BUILD_FAILURE: "🔨",
            FailureType.TEST_FAILURE: "🧪",
            FailureType.UNKNOWN: "❓",
        }
        self.sanitize_secrets = sanitize_secrets
        if sanitize_secrets:
            self.security_validator = SecurityValidator()

    def format_markdown(self, execution_result: ExecutionResult) -> str:
        """実行結果をMarkdown形式でフォーマット

        Args:
            execution_result: CI実行結果

        Returns:
            Markdown形式の文字列
        """
        sections = []

        # ヘッダー
        sections.append(self._format_markdown_header(execution_result))

        # 実行サマリー
        sections.append(self._format_markdown_summary(execution_result))

        # 失敗がある場合の詳細
        if not execution_result.success:
            sections.append(self._format_markdown_failures(execution_result))

        # ワークフロー詳細
        sections.append(self._format_markdown_workflows(execution_result))

        # メトリクス
        metrics = AnalysisMetrics.from_execution_result(execution_result)
        sections.append(self._format_markdown_metrics(metrics))

        markdown_content = "\n\n".join(sections)

        # シークレットのサニタイズ
        if self.sanitize_secrets:
            markdown_content = self._sanitize_content(markdown_content)

        return markdown_content

    def _format_markdown_header(self, execution_result: ExecutionResult) -> str:
        """Markdownヘッダーを生成"""
        status_icon = "✅" if execution_result.success else "❌"
        status_text = "成功" if execution_result.success else "失敗"

        return f"""# CI実行結果 {status_icon}

**ステータス**: {status_text}
**実行時刻**: {execution_result.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
**総実行時間**: {execution_result.total_duration:.2f}秒
**ワークフロー数**: {len(execution_result.workflows)}"""

    def _format_markdown_summary(self, execution_result: ExecutionResult) -> str:
        """実行サマリーをMarkdown形式で生成"""
        total_jobs = sum(len(w.jobs) for w in execution_result.workflows)
        successful_jobs = sum(1 for w in execution_result.workflows for j in w.jobs if j.success)
        total_failures = execution_result.total_failures

        summary = f"""## 📊 実行サマリー

- **総ジョブ数**: {total_jobs}
- **成功ジョブ**: {successful_jobs}
- **失敗ジョブ**: {total_jobs - successful_jobs}
- **総失敗数**: {total_failures}
- **成功率**: {(successful_jobs / total_jobs * 100) if total_jobs > 0 else 100:.1f}%"""

        return summary

    def _format_markdown_failures(self, execution_result: ExecutionResult) -> str:
        """失敗詳細をMarkdown形式で生成"""
        if execution_result.success:
            return ""

        sections = ["## 🚨 失敗詳細"]

        # 失敗タイプ別の集計
        failure_counts = {}
        for failure in execution_result.all_failures:
            failure_counts[failure.type] = failure_counts.get(failure.type, 0) + 1

        if failure_counts:
            sections.append("### 失敗タイプ別集計")
            for failure_type, count in failure_counts.items():
                icon = self.failure_type_icons.get(failure_type, "❓")
                sections.append(f"- {icon} **{failure_type.value}**: {count}件")

        # 各失敗の詳細
        sections.append("### 失敗一覧")

        failure_num = 1
        for workflow in execution_result.workflows:
            if not workflow.success:
                for job in workflow.jobs:
                    if not job.success:
                        for failure in job.failures:
                            sections.append(
                                self._format_single_failure_markdown(failure, failure_num, workflow.name, job.name)
                            )
                            failure_num += 1

        return "\n\n".join(sections)

    def _format_single_failure_markdown(
        self, failure: Failure, failure_num: int, workflow_name: str, job_name: str
    ) -> str:
        """単一の失敗をMarkdown形式でフォーマット"""
        icon = self.failure_type_icons.get(failure.type, "❓")

        sections = [f"#### {failure_num}. {icon} {failure.type.value.upper()}"]

        # 基本情報
        sections.append(f"**ワークフロー**: {workflow_name}")
        sections.append(f"**ジョブ**: {job_name}")

        # ファイル情報
        if failure.file_path:
            file_info = f"**ファイル**: `{failure.file_path}`"
            if failure.line_number:
                file_info += f" (行 {failure.line_number})"
            sections.append(file_info)

        # エラーメッセージ
        sections.append("**エラーメッセージ**:")
        sections.append(f"```\n{failure.message}\n```")

        # コンテキスト（前後の行）
        if failure.context_before or failure.context_after:
            sections.append("**コンテキスト**:")
            context_lines = []

            # 前のコンテキスト
            for line in failure.context_before:
                context_lines.append(f"  {line}")

            # エラー行（推定）
            context_lines.append(f"> {failure.message}")

            # 後のコンテキスト
            for line in failure.context_after:
                context_lines.append(f"  {line}")

            sections.append("```\n" + "\n".join(context_lines) + "\n```")

        # スタックトレース
        if failure.stack_trace:
            sections.append("**スタックトレース**:")
            sections.append(f"```\n{failure.stack_trace}\n```")

        return "\n".join(sections)

    def _format_markdown_workflows(self, execution_result: ExecutionResult) -> str:
        """ワークフロー詳細をMarkdown形式で生成"""
        sections = ["## 📋 ワークフロー詳細"]

        for workflow in execution_result.workflows:
            workflow_icon = "✅" if workflow.success else "❌"
            sections.append(f"### {workflow_icon} {workflow.name}")

            # ワークフロー情報
            sections.append(f"- **実行時間**: {workflow.duration:.2f}秒")
            sections.append(f"- **ジョブ数**: {len(workflow.jobs)}")
            sections.append(f"- **成功ジョブ**: {sum(1 for j in workflow.jobs if j.success)}")

            # ジョブ詳細
            if workflow.jobs:
                sections.append("#### ジョブ一覧")
                for job in workflow.jobs:
                    job_icon = "✅" if job.success else "❌"
                    failure_count = len(job.failures)
                    failure_text = f" ({failure_count}件の失敗)" if failure_count > 0 else ""
                    sections.append(f"- {job_icon} **{job.name}** - {job.duration:.2f}秒{failure_text}")

        return "\n\n".join(sections)

    def _format_markdown_metrics(self, metrics: AnalysisMetrics) -> str:
        """メトリクスをMarkdown形式で生成"""
        sections = ["## 📈 メトリクス"]

        sections.append(f"- **総ワークフロー数**: {metrics.total_workflows}")
        sections.append(f"- **総ジョブ数**: {metrics.total_jobs}")
        sections.append(f"- **総ステップ数**: {metrics.total_steps}")
        sections.append(f"- **総失敗数**: {metrics.total_failures}")
        sections.append(f"- **成功率**: {metrics.success_rate:.1f}%")
        sections.append(f"- **平均実行時間**: {metrics.average_duration:.2f}秒")

        if metrics.failure_types:
            sections.append("\n### 失敗タイプ分布")
            for failure_type, count in metrics.failure_types.items():
                icon = self.failure_type_icons.get(failure_type, "❓")
                sections.append(f"- {icon} **{failure_type.value}**: {count}件")

        return "\n".join(sections)

    def format_json(self, execution_result: ExecutionResult) -> str:
        """実行結果をJSON形式でフォーマット

        Args:
            execution_result: CI実行結果

        Returns:
            JSON形式の文字列
        """
        # メトリクスを生成
        metrics = AnalysisMetrics.from_execution_result(execution_result)

        # JSON構造を構築
        json_data = {
            "execution_summary": {
                "success": execution_result.success,
                "timestamp": execution_result.timestamp.isoformat(),
                "total_duration": execution_result.total_duration,
                "total_workflows": len(execution_result.workflows),
                "total_failures": execution_result.total_failures,
            },
            "metrics": {
                "total_workflows": metrics.total_workflows,
                "total_jobs": metrics.total_jobs,
                "total_steps": metrics.total_steps,
                "total_failures": metrics.total_failures,
                "success_rate": metrics.success_rate,
                "average_duration": metrics.average_duration,
                "failure_types": {ft.value: count for ft, count in metrics.failure_types.items()},
            },
            "workflows": [self._workflow_to_dict(workflow) for workflow in execution_result.workflows],
            "failures": [self._failure_to_dict(failure) for failure in execution_result.all_failures],
        }

        json_content = json.dumps(json_data, indent=2, ensure_ascii=False)

        # シークレットのサニタイズ
        if self.sanitize_secrets:
            json_content = self._sanitize_content(json_content)

        return json_content

    def _workflow_to_dict(self, workflow: WorkflowResult) -> dict[str, Any]:
        """ワークフローをdict形式に変換"""
        return {
            "name": workflow.name,
            "success": workflow.success,
            "duration": workflow.duration,
            "jobs": [self._job_to_dict(job) for job in workflow.jobs],
        }

    def _job_to_dict(self, job: JobResult) -> dict[str, Any]:
        """ジョブをdict形式に変換"""
        return {
            "name": job.name,
            "success": job.success,
            "duration": job.duration,
            "failure_count": len(job.failures),
            "failures": [self._failure_to_dict(failure) for failure in job.failures],
            "steps": [self._step_to_dict(step) for step in job.steps],
        }

    def _step_to_dict(self, step) -> dict[str, Any]:
        """ステップをdict形式に変換"""
        return {
            "name": step.name,
            "success": step.success,
            "duration": step.duration,
            "output": step.output,
        }

    def _failure_to_dict(self, failure: Failure) -> dict[str, Any]:
        """失敗をdict形式に変換"""
        return {
            "type": failure.type.value,
            "message": failure.message,
            "file_path": failure.file_path,
            "line_number": failure.line_number,
            "context_before": list(failure.context_before),
            "context_after": list(failure.context_after),
            "stack_trace": failure.stack_trace,
        }

    def count_tokens(self, content: str, model: str = "gpt-4") -> int:
        """コンテンツのトークン数をカウント

        Args:
            content: トークン数をカウントするコンテンツ
            model: 対象のAIモデル名

        Returns:
            推定トークン数

        Raises:
            ImportError: tiktokenがインストールされていない場合
        """
        if tiktoken is None:
            raise ImportError(
                "tiktokenがインストールされていません。"
                "pip install tiktoken または uv add tiktoken でインストールしてください。"
            )

        try:
            # モデルに対応するエンコーダーを取得
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # 未知のモデルの場合はcl100k_baseエンコーディングを使用
            encoding = tiktoken.get_encoding("cl100k_base")

        # トークン数をカウント
        tokens = encoding.encode(content)
        return len(tokens)

    def check_token_limits(self, content: str, model: str = "gpt-4") -> dict[str, Any]:
        """トークン制限をチェックし、警告情報を返す

        Args:
            content: チェック対象のコンテンツ
            model: 対象のAIモデル名

        Returns:
            トークン情報と警告を含む辞書
        """
        # モデル別のトークン制限
        model_limits = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "claude-3-haiku": 200000,
            "claude-3-sonnet": 200000,
            "claude-3-opus": 200000,
        }

        try:
            token_count = self.count_tokens(content, model)
        except ImportError:
            # tiktokenが利用できない場合は文字数ベースで推定
            token_count = len(content) // 4  # 大まかな推定（1トークン≈4文字）

        # モデルの制限を取得（デフォルトは8192）
        limit = model_limits.get(model, 8192)

        # 使用率を計算
        usage_ratio = token_count / limit

        # 警告レベルを決定
        warning_level = "none"
        warning_message = ""

        if usage_ratio >= 0.9:
            warning_level = "critical"
            warning_message = "トークン数が制限の90%を超えています。コンテンツの圧縮を検討してください。"
        elif usage_ratio >= 0.7:
            warning_level = "warning"
            warning_message = "トークン数が制限の70%を超えています。"
        elif usage_ratio >= 0.5:
            warning_level = "info"
            warning_message = "トークン数が制限の50%を超えています。"

        return {
            "token_count": token_count,
            "token_limit": limit,
            "usage_ratio": usage_ratio,
            "usage_percentage": usage_ratio * 100,
            "warning_level": warning_level,
            "warning_message": warning_message,
            "model": model,
        }

    def format_with_token_info(
        self, execution_result: ExecutionResult, format_type: str = "markdown", model: str = "gpt-4"
    ) -> dict[str, Any]:
        """フォーマット結果とトークン情報を含む辞書を返す

        Args:
            execution_result: CI実行結果
            format_type: 出力形式（"markdown" または "json"）
            model: 対象のAIモデル名

        Returns:
            フォーマット結果とトークン情報を含む辞書
        """
        # フォーマット実行
        if format_type.lower() == "json":
            formatted_content = self.format_json(execution_result)
        else:
            formatted_content = self.format_markdown(execution_result)

        # トークン情報を取得
        token_info = self.check_token_limits(formatted_content, model)

        return {
            "content": formatted_content,
            "format": format_type,
            "token_info": token_info,
        }

    def suggest_compression_options(self, execution_result: ExecutionResult) -> list[str]:
        """コンテンツ圧縮のオプションを提案

        Args:
            execution_result: CI実行結果

        Returns:
            圧縮オプションのリスト
        """
        suggestions = []

        # 失敗数が多い場合
        if execution_result.total_failures > 10:
            suggestions.append("失敗数が多いため、最も重要な失敗のみに絞り込む")

        # コンテキスト行が多い場合
        has_long_context = Any(
            len(failure.context_before) + len(failure.context_after) > 6 for failure in execution_result.all_failures
        )
        if has_long_context:
            suggestions.append("エラーのコンテキスト行数を削減する")

        # スタックトレースが多い場合
        has_stack_traces = Any(failure.stack_trace for failure in execution_result.all_failures)
        if has_stack_traces:
            suggestions.append("スタックトレースを要約または除外する")

        # ワークフロー数が多い場合
        if len(execution_result.workflows) > 5:
            suggestions.append("失敗したワークフローのみに絞り込む")

        # ジョブ数が多い場合
        total_jobs = sum(len(w.jobs) for w in execution_result.workflows)
        if total_jobs > 10:
            suggestions.append("失敗したジョブのみに絞り込む")

        # デフォルトの提案
        if not suggestions:
            suggestions.extend(
                [
                    "JSON形式を使用してより簡潔な出力にする",
                    "成功したワークフローの詳細を除外する",
                    "メトリクス情報のみに絞り込む",
                ]
            )

        return suggestions

    def _sanitize_content(self, content: str) -> str:
        """コンテンツ内のシークレットをサニタイズ

        Args:
            content: サニタイズ対象のコンテンツ

        Returns:
            サニタイズされたコンテンツ
        """
        if not self.sanitize_secrets or not hasattr(self, "security_validator"):
            return content

        try:
            return self.security_validator.secret_detector.sanitize_content(content)
        except Exception:
            # サニタイズに失敗した場合は元のコンテンツを返す
            return content

    def validate_output_security(self, content: str) -> dict[str, Any]:
        """出力コンテンツのセキュリティを検証

        Args:
            content: 検証対象のコンテンツ

        Returns:
            セキュリティ検証結果
        """
        if not hasattr(self, "security_validator"):
            return {
                "has_secrets": False,
                "secret_count": 0,
                "detected_secrets": [],
                "recommendations": ["セキュリティ検証が無効になっています"],
            }

        return self.security_validator.validate_log_content(content)
