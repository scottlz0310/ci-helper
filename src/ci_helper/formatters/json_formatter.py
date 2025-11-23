"""JSON専用フォーマッター

CI実行結果を構造化されたJSON形式でフォーマットします。
プログラム的に解析可能な構造を提供し、他のツールやスクリプトでの処理を容易にします。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.models import (
        AnalysisMetrics,
        ExecutionResult,
        Failure,
        JobResult,
        StepResult,
        WorkflowResult,
    )

from ..core.models import AnalysisMetrics
from .base_formatter import BaseLogFormatter


class JSONFormatter(BaseLogFormatter):
    """JSON形式専用フォーマッター

    構造化されたJSONデータを出力し、プログラム的な解析を可能にします。
    """

    def __init__(
        self,
        sanitize_secrets: bool = True,
        indent: int = 2,
        ensure_ascii: bool = False,
    ):
        """JSONフォーマッターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか
            indent: JSON出力のインデント数（Noneで圧縮形式）
            ensure_ascii: ASCII文字のみを使用するかどうか

        """
        super().__init__(sanitize_secrets)
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """実行結果をJSON形式でフォーマット

        Args:
            execution_result: CI実行結果
            **options: フォーマット固有のオプション
                - compact: bool - 圧縮形式で出力（デフォルト: False）
                - include_output: bool - ステップ出力を含める（デフォルト: True）
                - include_context: bool - エラーコンテキストを含める（デフォルト: True）
                - include_stack_trace: bool - スタックトレースを含める（デフォルト: True）
                - pretty_print: bool - 整形されたJSON出力（デフォルト: True）
                - include_metadata: bool - メタデータを含める（デフォルト: True）
                - detail_level: str - 詳細レベル（minimal/normal/detailed）
                - filter_errors: bool - エラーのみをフィルタリング
                - max_failures: int - 最大失敗表示数

        Returns:
            JSON形式の文字列

        """
        # オプションの処理
        validated_options = self.validate_options(**options)
        compact = validated_options.get("compact", False)
        pretty_print = validated_options.get("pretty_print", True)
        include_output = validated_options.get("include_output", True)
        include_context = validated_options.get("include_context", True)
        include_stack_trace = validated_options.get("include_stack_trace", True)
        # detail_levelの取得
        detail_level = validated_options.get("detail_level", "normal")
        max_failures = validated_options.get("max_failures", None)

        # pretty_printがFalseの場合はcompactをTrueに
        if not pretty_print:
            compact = True

        # 詳細レベルに基づく調整
        if detail_level == "minimal":
            include_output = False
            include_context = False
            include_stack_trace = False
            max_failures = min(max_failures or 5, 5)
        elif detail_level == "detailed":
            include_output = True
            include_context = True
            include_stack_trace = True
            max_failures = max_failures or 50

        # メトリクスを生成
        metrics = AnalysisMetrics.from_execution_result(execution_result)

        # JSON構造を構築
        json_data = {
            "format_info": {
                "format": "json",
                "version": "1.0",
                "generated_at": self._format_timestamp_iso(datetime.now()),
                "options": {
                    "compact": compact,
                    "include_output": include_output,
                    "include_context": include_context,
                    "include_stack_trace": include_stack_trace,
                    "sanitize_secrets": self.sanitize_secrets,
                },
            },
            "execution_summary": {
                "success": execution_result.success,
                "timestamp": self._format_timestamp_iso(execution_result.timestamp),
                "total_duration": round(execution_result.total_duration, 3),
                "total_workflows": len(execution_result.workflows),
                "total_jobs": sum(len(w.jobs) for w in execution_result.workflows),
                "total_steps": sum(len(job.steps) for w in execution_result.workflows for job in w.jobs),
                "total_failures": execution_result.total_failures,
                "log_path": execution_result.log_path,
            },
            "metrics": self._metrics_to_dict(metrics),
            "workflows": [
                self._workflow_to_dict(workflow, include_output, include_context, include_stack_trace)
                for workflow in execution_result.workflows
            ],
            "failures_summary": {
                "total_count": len(execution_result.all_failures),
                "by_type": self._get_failure_type_counts(execution_result.all_failures),
                "by_workflow": self._get_failures_by_workflow(execution_result),
                "critical_failures": [
                    self._failure_to_dict(failure, include_context, include_stack_trace)
                    for failure in self._get_critical_failures(execution_result.all_failures)
                ],
            },
            "all_failures": [
                self._failure_to_dict(failure, include_context, include_stack_trace)
                for failure in execution_result.all_failures
            ],
        }

        # JSON文字列に変換
        indent = None if compact else self.indent
        json_content = json.dumps(
            json_data,
            indent=indent,
            ensure_ascii=self.ensure_ascii,
            separators=(",", ":") if compact else (",", ": "),
            sort_keys=True,
        )

        # シークレットのサニタイズ
        if self.sanitize_secrets:
            json_content = self._sanitize_content(json_content)

        return json_content

    def get_format_name(self) -> str:
        """フォーマット名を取得

        Returns:
            フォーマット名

        """
        return "json"

    def get_description(self) -> str:
        """フォーマットの説明を取得

        Returns:
            フォーマットの説明文

        """
        return "構造化されたJSONデータを出力（プログラム解析用）"

    def validate_options(self, **options: Any) -> dict[str, Any]:
        """オプションの検証と正規化

        Args:
            **options: 検証対象のオプション

        Returns:
            検証・正規化されたオプション

        Raises:
            ValueError: 無効なオプションが指定された場合

        """
        # verbose_level を detail_level にマッピング（後方互換性のため）
        if "verbose_level" in options and "detail_level" not in options:
            options = dict(options)  # コピーを作成
            options["detail_level"] = options.pop("verbose_level")

        # サポートされているオプションのチェック
        supported_options = set(self.get_supported_options())
        # verbose_levelは後方互換性のため特別に許可
        supported_options.add("verbose_level")
        for option_name in options:
            if option_name not in supported_options:
                raise ValueError(f"未知のオプション: {option_name}")

        # 基底クラスの検証を呼び出し
        validated = super().validate_options(**options)

        # bool型オプションの検証
        bool_options = [
            "compact",
            "include_output",
            "include_context",
            "include_stack_trace",
            "pretty_print",
            "include_metadata",
        ]
        for option_name in bool_options:
            if option_name in options:
                if not isinstance(options[option_name], bool):
                    raise ValueError(f"{option_name} オプションはbool型である必要があります")
                validated[option_name] = options[option_name]

        # detail_level オプションの検証
        if "detail_level" in options:
            valid_levels = ["minimal", "normal", "detailed"]
            if options["detail_level"] not in valid_levels:
                raise ValueError(f"detail_level は {valid_levels} のいずれかである必要があります")
            validated["detail_level"] = options["detail_level"]

        # max_failures オプションの検証
        if "max_failures" in options and options["max_failures"] is not None:
            if not isinstance(options["max_failures"], int) or options["max_failures"] < 1:
                raise ValueError("max_failures は正の整数である必要があります")
            validated["max_failures"] = options["max_failures"]

        return validated

    def supports_option(self, option_name: str) -> bool:
        """指定されたオプションをサポートしているかチェック

        Args:
            option_name: オプション名

        Returns:
            サポートしている場合True

        """
        return option_name in self.get_supported_options()

    def get_supported_options(self) -> list[str]:
        """サポートされているオプション一覧を取得

        Returns:
            サポートされているオプション名のリスト

        """
        return [
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

    def validate_json_structure(self, json_str: str) -> dict[str, Any]:
        """JSON構造の妥当性を検証

        Args:
            json_str: 検証対象のJSON文字列

        Returns:
            検証結果を含む辞書

        Raises:
            json.JSONDecodeError: 無効なJSON形式の場合

        """
        try:
            # JSON形式の検証
            parsed_data = json.loads(json_str)

            # 必須フィールドの存在確認
            required_fields = [
                "format_info",
                "execution_summary",
                "metrics",
                "workflows",
                "failures_summary",
                "all_failures",
            ]

            missing_fields: list[str] = []
            for field in required_fields:
                if field not in parsed_data:
                    missing_fields.append(field)

            # execution_summaryの必須フィールド確認
            if "execution_summary" in parsed_data:
                summary_required = ["success", "timestamp", "total_duration"]
                for field in summary_required:
                    if field not in parsed_data["execution_summary"]:
                        missing_fields.append(f"execution_summary.{field}")

            return {
                "valid": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "field_count": len(parsed_data),
                "size_bytes": len(json_str.encode("utf-8")),
                "parseable": True,
            }

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "missing_fields": [],
                "field_count": 0,
                "size_bytes": len(json_str.encode("utf-8")),
                "parseable": False,
                "error": str(e),
            }

    def _metrics_to_dict(self, metrics: AnalysisMetrics) -> dict[str, Any]:
        """メトリクスをdict形式に変換"""
        return {
            "total_workflows": metrics.total_workflows,
            "total_jobs": metrics.total_jobs,
            "total_steps": metrics.total_steps,
            "total_failures": metrics.total_failures,
            "success_rate": round(metrics.success_rate, 2),
            "average_duration": round(metrics.average_duration, 3),
            "failure_types": {ft.value: count for ft, count in metrics.failure_types.items()},
        }

    def _workflow_to_dict(
        self,
        workflow: WorkflowResult,
        include_output: bool = True,
        include_context: bool = True,
        include_stack_trace: bool = True,
    ) -> dict[str, Any]:
        """ワークフローをdict形式に変換"""
        return {
            "name": workflow.name,
            "success": workflow.success,
            "duration": round(workflow.duration, 3),
            "job_count": len(workflow.jobs),
            "failed_job_count": sum(1 for job in workflow.jobs if not job.success),
            "jobs": [
                self._job_to_dict(job, include_output, include_context, include_stack_trace) for job in workflow.jobs
            ],
        }

    def _job_to_dict(
        self,
        job: JobResult,
        include_output: bool = True,
        include_context: bool = True,
        include_stack_trace: bool = True,
    ) -> dict[str, Any]:
        """ジョブをdict形式に変換"""
        return {
            "name": job.name,
            "success": job.success,
            "duration": round(job.duration, 3),
            "step_count": len(job.steps),
            "failure_count": len(job.failures),
            "failures": [
                self._failure_to_dict(failure, include_context, include_stack_trace) for failure in job.failures
            ],
            "steps": [self._step_to_dict(step, include_output) for step in job.steps],
        }

    def _step_to_dict(self, step: StepResult, include_output: bool = True) -> dict[str, Any]:
        """ステップをdict形式に変換"""
        step_dict = {
            "name": step.name,
            "success": step.success,
            "duration": round(step.duration, 3),
        }

        if include_output:
            step_dict["output"] = step.output

        return step_dict

    def _failure_to_dict(
        self,
        failure: Failure,
        include_context: bool = True,
        include_stack_trace: bool = True,
    ) -> dict[str, Any]:
        """失敗をdict形式に変換"""
        failure_dict: dict[str, Any] = {
            "type": failure.type.value,
            "message": failure.message,
            "file_path": failure.file_path,
            "line_number": failure.line_number,
        }

        if include_context:
            failure_dict.update(
                {
                    "context_before": list(failure.context_before),
                    "context_after": list(failure.context_after),
                },
            )

        if include_stack_trace:
            failure_dict["stack_trace"] = failure.stack_trace

        return failure_dict

    def _get_failure_type_counts(self, failures: Sequence[Failure]) -> dict[str, int]:
        """失敗タイプ別の件数を取得"""
        counts: dict[str, int] = {}
        for failure in failures:
            failure_type = failure.type.value
            counts[failure_type] = counts.get(failure_type, 0) + 1
        return counts

    def _get_failures_by_workflow(self, execution_result: ExecutionResult) -> dict[str, int]:
        """ワークフロー別の失敗件数を取得"""
        counts: dict[str, int] = {}
        for workflow in execution_result.workflows:
            failure_count = sum(len(job.failures) for job in workflow.jobs)
            if failure_count > 0:
                counts[workflow.name] = failure_count
        return counts

    def _get_critical_failures(self, failures: Sequence[Failure]) -> list[Failure]:
        """クリティカルな失敗を抽出（最大5件）"""

        # 優先度順にソート
        def priority_score(failure: Failure) -> int:
            score = 0
            # アサーションエラーは最優先
            if failure.type.value == "assertion":
                score += 100
            # ファイル情報があるものを優先
            if failure.file_path:
                score += 50
            # 行番号があるものを優先
            if failure.line_number:
                score += 25
            # スタックトレースがあるものを優先
            if failure.stack_trace:
                score += 10
            return score

        sorted_failures = sorted(failures, key=priority_score, reverse=True)
        return sorted_failures[:5]  # 最大5件

    @staticmethod
    def _format_timestamp_iso(timestamp: datetime) -> str:
        """ISO形式のタイムスタンプ文字列を生成"""
        return timestamp.isoformat()
