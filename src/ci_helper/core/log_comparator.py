"""
ログ比較エンジン

過去実行との結果比較機能、新規エラー・解決済みエラーの分類、
差分表示とサマリー生成を提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ..core.models import ExecutionResult, Failure, LogComparisonResult


class LogComparator:
    """ログ比較エンジンクラス

    現在の実行結果と過去の実行結果を比較し、差分を分析します。
    """

    def __init__(self):
        """ログ比較エンジンを初期化"""
        pass

    def compare_executions(
        self,
        current: ExecutionResult,
        previous: ExecutionResult | None,
    ) -> LogComparisonResult:
        """実行結果を比較して差分を生成

        Args:
            current: 現在の実行結果
            previous: 前回の実行結果（Noneの場合は初回実行）

        Returns:
            ログ比較結果
        """
        if previous is None:
            # 初回実行の場合
            return LogComparisonResult(
                current_execution=current,
                previous_execution=None,
                new_errors=list(current.all_failures),
                resolved_errors=[],
                persistent_errors=[],
            )

        # 現在と前回の失敗を収集
        current_failures = list(current.all_failures)
        previous_failures = list(previous.all_failures)

        # 失敗を比較用のキーで分類
        current_failure_map = {self._create_failure_key(f): f for f in current_failures}
        previous_failure_map = {self._create_failure_key(f): f for f in previous_failures}

        # 差分を計算
        new_error_keys = set(current_failure_map.keys()) - set(previous_failure_map.keys())
        resolved_error_keys = set(previous_failure_map.keys()) - set(current_failure_map.keys())
        persistent_error_keys = set(current_failure_map.keys()) & set(previous_failure_map.keys())

        # 失敗オブジェクトを取得
        new_errors = [current_failure_map[key] for key in new_error_keys]
        resolved_errors = [previous_failure_map[key] for key in resolved_error_keys]
        persistent_errors = [current_failure_map[key] for key in persistent_error_keys]

        return LogComparisonResult(
            current_execution=current,
            previous_execution=previous,
            new_errors=new_errors,
            resolved_errors=resolved_errors,
            persistent_errors=persistent_errors,
        )

    def _create_failure_key(self, failure: Failure) -> tuple[str, str, str | None, int | None]:
        """失敗の比較用キーを生成

        Args:
            failure: 失敗オブジェクト

        Returns:
            比較用のキー（失敗タイプ、メッセージ、ファイルパス、行番号）
        """
        return (
            failure.type.value,
            failure.message.strip(),
            failure.file_path,
            failure.line_number,
        )

    def generate_diff_summary(self, comparison: LogComparisonResult) -> dict[str, any]:
        """差分サマリーを生成

        Args:
            comparison: ログ比較結果

        Returns:
            差分サマリー情報
        """
        current = comparison.current_execution
        previous = comparison.previous_execution

        # 基本統計
        summary = {
            "comparison_type": "initial" if previous is None else "comparison",
            "current_status": "success" if current.success else "failure",
            "previous_status": "success" if previous and previous.success else "failure" if previous else None,
            "has_changes": comparison.has_changes,
            "improvement_score": comparison.improvement_score,
        }

        # エラー数の変化
        current_error_count = len(comparison.current_execution.all_failures)
        previous_error_count = len(comparison.previous_execution.all_failures) if previous else 0

        summary["error_counts"] = {
            "current": current_error_count,
            "previous": previous_error_count,
            "new": len(comparison.new_errors),
            "resolved": len(comparison.resolved_errors),
            "persistent": len(comparison.persistent_errors),
            "net_change": current_error_count - previous_error_count,
        }

        # 実行時間の変化
        if previous:
            time_change = current.total_duration - previous.total_duration
            time_change_percent = (time_change / previous.total_duration * 100) if previous.total_duration > 0 else 0
        else:
            time_change = 0
            time_change_percent = 0

        summary["performance"] = {
            "current_duration": current.total_duration,
            "previous_duration": previous.total_duration if previous else 0,
            "time_change": time_change,
            "time_change_percent": time_change_percent,
        }

        # ワークフロー別の変化
        summary["workflow_changes"] = self._analyze_workflow_changes(comparison)

        # 失敗タイプ別の分析
        summary["failure_type_analysis"] = self._analyze_failure_types(comparison)

        return summary

    def _analyze_workflow_changes(self, comparison: LogComparisonResult) -> dict[str, any]:
        """ワークフロー別の変化を分析

        Args:
            comparison: ログ比較結果

        Returns:
            ワークフロー別の変化情報
        """
        current_workflows = {w.name: w for w in comparison.current_execution.workflows}
        previous_workflows = {}
        if comparison.previous_execution:
            previous_workflows = {w.name: w for w in comparison.previous_execution.workflows}

        workflow_changes = {}

        # 全ワークフローを分析
        all_workflow_names = set(current_workflows.keys()) | set(previous_workflows.keys())

        for workflow_name in all_workflow_names:
            current_workflow = current_workflows.get(workflow_name)
            previous_workflow = previous_workflows.get(workflow_name)

            change_info = {
                "status": "unchanged",
                "current_success": current_workflow.success if current_workflow else None,
                "previous_success": previous_workflow.success if previous_workflow else None,
                "current_duration": current_workflow.duration if current_workflow else 0,
                "previous_duration": previous_workflow.duration if previous_workflow else 0,
            }

            # ステータス変化を判定
            if not previous_workflow:
                change_info["status"] = "new"
            elif not current_workflow:
                change_info["status"] = "removed"
            elif current_workflow.success != previous_workflow.success:
                if current_workflow.success:
                    change_info["status"] = "fixed"
                else:
                    change_info["status"] = "broken"

            workflow_changes[workflow_name] = change_info

        return workflow_changes

    def _analyze_failure_types(self, comparison: LogComparisonResult) -> dict[str, any]:
        """失敗タイプ別の分析

        Args:
            comparison: ログ比較結果

        Returns:
            失敗タイプ別の分析情報
        """
        from collections import defaultdict

        # 現在の失敗タイプを集計
        current_types = defaultdict(int)
        for failure in comparison.current_execution.all_failures:
            current_types[failure.type.value] += 1

        # 前回の失敗タイプを集計
        previous_types = defaultdict(int)
        if comparison.previous_execution:
            for failure in comparison.previous_execution.all_failures:
                previous_types[failure.type.value] += 1

        # 新規エラーのタイプを集計
        new_error_types = defaultdict(int)
        for failure in comparison.new_errors:
            new_error_types[failure.type.value] += 1

        # 解決済みエラーのタイプを集計
        resolved_error_types = defaultdict(int)
        for failure in comparison.resolved_errors:
            resolved_error_types[failure.type.value] += 1

        return {
            "current_types": dict(current_types),
            "previous_types": dict(previous_types),
            "new_error_types": dict(new_error_types),
            "resolved_error_types": dict(resolved_error_types),
        }

    def format_diff_display(self, comparison: LogComparisonResult, format_type: str = "table") -> str:
        """差分表示をフォーマット

        Args:
            comparison: ログ比較結果
            format_type: 表示形式（table, markdown, json）

        Returns:
            フォーマットされた差分表示
        """
        if format_type == "json":
            return self._format_diff_json(comparison)
        elif format_type == "markdown":
            return self._format_diff_markdown(comparison)
        else:
            return self._format_diff_table(comparison)

    def _format_diff_json(self, comparison: LogComparisonResult) -> str:
        """JSON形式で差分を表示

        Args:
            comparison: ログ比較結果

        Returns:
            JSON形式の差分表示
        """
        import json

        summary = self.generate_diff_summary(comparison)

        # 詳細な失敗情報を追加
        detailed_info = {
            "summary": summary,
            "new_errors": [
                {
                    "type": f.type.value,
                    "message": f.message,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                }
                for f in comparison.new_errors
            ],
            "resolved_errors": [
                {
                    "type": f.type.value,
                    "message": f.message,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                }
                for f in comparison.resolved_errors
            ],
            "persistent_errors": [
                {
                    "type": f.type.value,
                    "message": f.message,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                }
                for f in comparison.persistent_errors
            ],
        }

        return json.dumps(detailed_info, indent=2, ensure_ascii=False)

    def _format_diff_markdown(self, comparison: LogComparisonResult) -> str:
        """Markdown形式で差分を表示

        Args:
            comparison: ログ比較結果

        Returns:
            Markdown形式の差分表示
        """
        summary = self.generate_diff_summary(comparison)
        lines = []

        # ヘッダー
        lines.append("# 実行結果の比較")
        lines.append("")

        # 概要
        lines.append("## 概要")
        lines.append("")
        if summary["comparison_type"] == "initial":
            lines.append("**初回実行** - 比較対象なし")
        else:
            current_status = "✅ 成功" if summary["current_status"] == "success" else "❌ 失敗"
            previous_status = "✅ 成功" if summary["previous_status"] == "success" else "❌ 失敗"
            lines.append(f"**現在の実行**: {current_status}")
            lines.append(f"**前回の実行**: {previous_status}")

        lines.append("")

        # エラー数の変化
        error_counts = summary["error_counts"]
        lines.append("## エラー数の変化")
        lines.append("")
        lines.append(f"- **現在のエラー数**: {error_counts['current']}")
        lines.append(f"- **前回のエラー数**: {error_counts['previous']}")
        lines.append(f"- **新規エラー**: {error_counts['new']}")
        lines.append(f"- **解決済みエラー**: {error_counts['resolved']}")
        lines.append(f"- **継続エラー**: {error_counts['persistent']}")

        net_change = error_counts["net_change"]
        if net_change > 0:
            lines.append(f"- **変化**: +{net_change} (悪化)")
        elif net_change < 0:
            lines.append(f"- **変化**: {net_change} (改善)")
        else:
            lines.append("- **変化**: 変化なし")

        lines.append("")

        # 新規エラーの詳細
        if comparison.new_errors:
            lines.append("## 新規エラー")
            lines.append("")
            for i, error in enumerate(comparison.new_errors, 1):
                lines.append(f"### {i}. {error.type.value.upper()}")
                lines.append("")
                lines.append(f"**メッセージ**: {error.message}")
                if error.file_path:
                    location = f"{error.file_path}"
                    if error.line_number:
                        location += f":{error.line_number}"
                    lines.append(f"**場所**: {location}")
                lines.append("")

        # 解決済みエラーの詳細
        if comparison.resolved_errors:
            lines.append("## 解決済みエラー")
            lines.append("")
            for i, error in enumerate(comparison.resolved_errors, 1):
                lines.append(f"### {i}. {error.type.value.upper()}")
                lines.append("")
                lines.append(f"**メッセージ**: {error.message}")
                if error.file_path:
                    location = f"{error.file_path}"
                    if error.line_number:
                        location += f":{error.line_number}"
                    lines.append(f"**場所**: {location}")
                lines.append("")

        return "\n".join(lines)

    def _format_diff_table(self, comparison: LogComparisonResult) -> str:
        """テーブル形式で差分を表示（Rich用の情報を返す）

        Args:
            comparison: ログ比較結果

        Returns:
            テーブル表示用の情報（実際の表示は呼び出し元で行う）
        """
        summary = self.generate_diff_summary(comparison)
        return str(summary)  # 実際のテーブル表示は呼び出し元で実装
