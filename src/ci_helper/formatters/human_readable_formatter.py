"""
人間可読フォーマッター

Rich ライブラリを使用して色付けされた構造化出力を生成し、
開発者が読みやすい形式でCI実行結果を表示します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from ..core.models import ExecutionResult, Failure

from ..core.models import FailureType
from .base_formatter import BaseLogFormatter


class HumanReadableFormatter(BaseLogFormatter):
    """人間が読みやすい形式のフォーマッター

    Rich ライブラリを使用して以下の機能を提供します：
    - 色付けされた構造化出力
    - セクション分けされたレイアウト
    - 重要なエラー情報のハイライト表示
    - 実行時間とステータス情報の表示
    """

    def __init__(self, sanitize_secrets: bool = True):
        """フォーマッターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか
        """
        super().__init__(sanitize_secrets)

        # Rich コンソールを初期化（文字列出力用）
        self.console = Console(file=None, width=120, legacy_windows=False)

        # 失敗タイプ別の色とアイコン設定
        self.failure_type_styles = {
            FailureType.ASSERTION: {"color": "red", "icon": "❌", "style": "bold red"},
            FailureType.ERROR: {"color": "bright_red", "icon": "🚨", "style": "bold bright_red"},
            FailureType.BUILD_FAILURE: {"color": "orange3", "icon": "🔨", "style": "bold orange3"},
            FailureType.TIMEOUT: {"color": "yellow", "icon": "⏰", "style": "bold yellow"},
            FailureType.TEST_FAILURE: {"color": "magenta", "icon": "🧪", "style": "bold magenta"},
            FailureType.UNKNOWN: {"color": "dim", "icon": "❓", "style": "dim"},
        }

        # ステータス別の色設定
        self.status_styles = {
            "success": {"color": "green", "icon": "✅"},
            "failure": {"color": "red", "icon": "❌"},
            "warning": {"color": "yellow", "icon": "⚠️"},
            "info": {"color": "blue", "icon": "ℹ️"},
        }

    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """人間可読形式でフォーマット

        Args:
            execution_result: CI実行結果
            **options: フォーマットオプション
                - show_details: 詳細情報を表示するか（デフォルト: True）
                - show_success_jobs: 成功したジョブも表示するか（デフォルト: False）
                - max_failures: 表示する最大失敗数（デフォルト: 20）
                - color_output: カラー出力を有効にするか（デフォルト: True）
                - detail_level: 詳細レベル（minimal/normal/detailed）
                - verbose_level: 詳細レベル（detail_levelのエイリアス、後方互換性のため）
                - filter_errors: エラーのみをフィルタリングするか

        Returns:
            人間可読形式でフォーマットされた文字列
        """
        # verbose_level を detail_level にマッピング（後方互換性のため）
        if "verbose_level" in options and "detail_level" not in options:
            options = dict(options)  # コピーを作成
            options["detail_level"] = options.pop("verbose_level")

        # オプションの検証と正規化
        validated_options = self.validate_options(**options)

        # オプションの処理
        show_details = validated_options.get("show_details", True)
        show_success_jobs = validated_options.get("show_success_jobs", False)
        max_failures = validated_options.get("max_failures", 20)
        color_output = validated_options.get("color_output", True)
        detail_level = validated_options.get("detail_level", "normal")
        filter_errors = validated_options.get("filter_errors", False)

        # 詳細レベルに基づく調整
        if detail_level == "minimal":
            show_details = False
            max_failures = min(max_failures or 5, 5)
            show_success_jobs = False
        elif detail_level == "detailed":
            show_details = True
            max_failures = max_failures or 50

        # max_failuresがNoneの場合はデフォルト値を設定
        if max_failures is None:
            max_failures = 20

        # カラー出力の設定
        if not color_output:
            self.console = Console(file=None, width=120, legacy_windows=False, no_color=True)

        # 出力セクションを構築
        sections = []

        # 1. 実行サマリー
        sections.append(self._format_execution_summary(execution_result))

        # 2. ワークフロー概要
        sections.append(self._format_workflow_overview(execution_result, show_success_jobs))

        # 3. 失敗詳細（失敗がある場合のみ）
        if not execution_result.success:
            sections.append(self._format_failure_details(execution_result, max_failures, show_details))

        # 4. 実行統計
        if show_details:
            sections.append(self._format_execution_statistics(execution_result))

        # 5. 推奨アクション
        if not execution_result.success:
            sections.append(self._format_recommended_actions(execution_result))

        # セクションを結合して文字列として出力
        with self.console.capture() as capture:
            for section in sections:
                self.console.print(section)
                self.console.print()  # セクション間の空行

        output = capture.get()

        # シークレットのサニタイズ
        if self.sanitize_secrets:
            output = self._sanitize_content(output)

        return output

    def get_format_name(self) -> str:
        """フォーマット名を取得"""
        return "human"

    def get_description(self) -> str:
        """フォーマットの説明を取得"""
        return "色付けされた構造化出力（人間可読形式）"

    def get_supported_options(self) -> list[str]:
        """サポートされているオプション一覧を取得"""
        return [
            "show_details",
            "show_success_jobs",
            "max_failures",
            "color_output",
            "detail_level",
            "verbose_level",  # 後方互換性のため
            "filter_errors",
        ]

    def _format_execution_summary(self, execution_result: ExecutionResult) -> Panel:
        """実行サマリーを生成"""
        # ステータス情報
        status_style = self.status_styles["success" if execution_result.success else "failure"]
        status_text = Text()
        status_text.append(f"{status_style['icon']} ", style=status_style["color"])
        status_text.append("成功" if execution_result.success else "失敗", style=f"bold {status_style['color']}")

        # 実行時間の分析
        duration = execution_result.total_duration
        duration_text = Text(f"{duration:.1f}秒")
        if duration > 300:  # 5分以上
            duration_text.stylize("bold red")
            duration_text.append(" (長時間実行)", style="red")
        elif duration > 60:  # 1分以上
            duration_text.stylize("bold yellow")
            duration_text.append(" (やや長時間)", style="yellow")
        else:
            duration_text.stylize("green")

        # サマリー情報を構築
        summary_table = Table.grid(padding=1)
        summary_table.add_column(style="bold cyan", min_width=15)
        summary_table.add_column()

        summary_table.add_row("ステータス:", status_text)
        summary_table.add_row("実行時間:", duration_text)
        summary_table.add_row("実行時刻:", execution_result.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        summary_table.add_row("ワークフロー数:", f"{len(execution_result.workflows)}個")

        if not execution_result.success:
            failure_text = Text(f"{execution_result.total_failures}件", style="bold red")
            summary_table.add_row("総失敗数:", failure_text)

        return Panel(
            summary_table,
            title="🎯 CI実行結果サマリー",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        )

    def _format_workflow_overview(self, execution_result: ExecutionResult, show_success_jobs: bool = False) -> Panel:
        """ワークフロー概要を生成"""
        tree = Tree("📋 ワークフロー実行結果", style="bold blue")

        for workflow in execution_result.workflows:
            # ワークフローノード
            workflow_status = self.status_styles["success" if workflow.success else "failure"]
            workflow_text = Text()
            workflow_text.append(f"{workflow_status['icon']} ", style=workflow_status["color"])
            workflow_text.append(workflow.name, style=f"bold {workflow_status['color']}")
            workflow_text.append(f" ({workflow.duration:.1f}秒)", style="dim")

            workflow_node = tree.add(workflow_text)

            # ジョブノード
            for job in workflow.jobs:
                if not show_success_jobs and job.success:
                    continue

                job_status = self.status_styles["success" if job.success else "failure"]
                job_text = Text()
                job_text.append(f"{job_status['icon']} ", style=job_status["color"])
                job_text.append(job.name, style=job_status["color"])
                job_text.append(f" ({job.duration:.1f}秒)", style="dim")

                if job.failures:
                    job_text.append(f" - {len(job.failures)}件の失敗", style="red")

                workflow_node.add(job_text)

        return Panel(
            tree,
            title="ワークフロー概要",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        )

    def _format_failure_details(
        self, execution_result: ExecutionResult, max_failures: int = 20, show_details: bool = True
    ) -> Panel:
        """失敗詳細を生成"""
        if execution_result.success:
            return Panel("失敗はありません", title="失敗詳細", border_style="green")

        # 失敗を優先度順にソート
        prioritized_failures = self._prioritize_failures(execution_result.all_failures)
        displayed_failures = prioritized_failures[:max_failures]

        failure_tree = Tree("🚨 失敗詳細", style="bold red")

        for i, failure in enumerate(displayed_failures, 1):
            # 失敗が発生したワークフローとジョブを特定
            workflow_name, job_name = self._find_failure_location(failure, execution_result)

            # 失敗ノードを作成
            failure_node = self._create_failure_node(failure, i, workflow_name, job_name, show_details)
            failure_tree.add(failure_node)

        # 省略された失敗がある場合の注記
        if len(prioritized_failures) > max_failures:
            omitted_count = len(prioritized_failures) - max_failures
            omitted_text = Text(f"... 他 {omitted_count}件の失敗が省略されています", style="dim italic")
            failure_tree.add(omitted_text)

        return Panel(
            failure_tree,
            title="失敗詳細",
            title_align="left",
            border_style="red",
            padding=(1, 2),
        )

    def _create_failure_node(
        self, failure: Failure, failure_num: int, workflow_name: str, job_name: str, show_details: bool = True
    ) -> Tree:
        """単一の失敗ノードを作成"""
        # 失敗タイプのスタイル取得
        style_config = self.failure_type_styles.get(failure.type, self.failure_type_styles[FailureType.UNKNOWN])

        # メインノードテキスト
        main_text = Text()
        main_text.append(f"{failure_num}. ", style="bold")
        main_text.append(f"{style_config['icon']} ", style=style_config["color"])
        main_text.append(f"{failure.type.value.upper()}", style=style_config["style"])

        failure_node = Tree(main_text)

        # 場所情報
        location_text = Text()
        location_text.append("📍 場所: ", style="bold cyan")
        location_text.append(f"{workflow_name} → {job_name}", style="cyan")
        failure_node.add(location_text)

        # ファイル情報
        if failure.file_path:
            file_text = Text()
            file_text.append("📄 ファイル: ", style="bold cyan")
            file_text.append(failure.file_path, style="cyan")
            if failure.line_number:
                file_text.append(f" (行 {failure.line_number})", style="dim cyan")
            failure_node.add(file_text)

        # エラーメッセージ
        message_text = Text()
        message_text.append("💬 メッセージ: ", style="bold yellow")
        message_text.append(failure.message, style="white")
        failure_node.add(message_text)

        # 詳細情報（オプション）
        if show_details:
            # コードコンテキスト
            if failure.context_before or failure.context_after:
                context_node = self._create_context_node(failure)
                failure_node.add(context_node)

            # スタックトレース（要約版）
            if failure.stack_trace:
                stack_text = Text()
                stack_text.append("📚 スタックトレース: ", style="bold magenta")
                # 最初の2行のみ表示
                stack_lines = failure.stack_trace.split("\n")[:2]
                stack_text.append(" | ".join(stack_lines), style="dim white")
                failure_node.add(stack_text)

        return failure_node

    def _create_context_node(self, failure: Failure) -> Tree:
        """コードコンテキストノードを作成"""
        context_node = Tree(Text("🔍 コードコンテキスト", style="bold green"))

        # 行番号を計算
        start_line = (failure.line_number or 1) - len(failure.context_before)

        # 前のコンテキスト
        for i, line in enumerate(failure.context_before):
            line_num = start_line + i
            line_text = Text()
            line_text.append(f"{line_num:4d} | ", style="dim")
            line_text.append(line, style="white")
            context_node.add(line_text)

        # エラー行（推定）
        if failure.line_number:
            error_text = Text()
            error_text.append(f"{failure.line_number:4d} | ", style="dim")
            error_text.append(">>> ", style="bold red")
            error_text.append("ERROR HERE", style="bold red")
            error_text.append(" <<<", style="bold red")
            context_node.add(error_text)

        # 後のコンテキスト
        for i, line in enumerate(failure.context_after):
            line_num = (failure.line_number or 1) + i + 1
            line_text = Text()
            line_text.append(f"{line_num:4d} | ", style="dim")
            line_text.append(line, style="white")
            context_node.add(line_text)

        return context_node

    def _format_execution_statistics(self, execution_result: ExecutionResult) -> Panel:
        """実行統計を生成"""
        # 統計テーブルを作成
        stats_table = Table(title="実行統計", show_header=True, header_style="bold magenta")
        stats_table.add_column("項目", style="cyan", min_width=20)
        stats_table.add_column("値", style="white", min_width=15)
        stats_table.add_column("詳細", style="dim", min_width=30)

        # 基本統計
        total_jobs = sum(len(w.jobs) for w in execution_result.workflows)
        successful_jobs = sum(1 for w in execution_result.workflows for j in w.jobs if j.success)
        failed_jobs = total_jobs - successful_jobs

        stats_table.add_row("ワークフロー数", str(len(execution_result.workflows)), "実行されたワークフローの総数")
        stats_table.add_row("ジョブ数", str(total_jobs), f"成功: {successful_jobs}, 失敗: {failed_jobs}")
        stats_table.add_row("総実行時間", f"{execution_result.total_duration:.2f}秒", "全ワークフローの合計時間")

        if total_jobs > 0:
            success_rate = (successful_jobs / total_jobs) * 100
            success_color = "green" if success_rate >= 80 else "yellow" if success_rate >= 50 else "red"
            stats_table.add_row("成功率", f"{success_rate:.1f}%", f"[{success_color}]ジョブベース[/{success_color}]")

        # 失敗タイプ別統計
        if not execution_result.success:
            failure_types = {}
            for failure in execution_result.all_failures:
                failure_types[failure.type] = failure_types.get(failure.type, 0) + 1

            for failure_type, count in failure_types.items():
                style_config = self.failure_type_styles.get(failure_type, self.failure_type_styles[FailureType.UNKNOWN])
                stats_table.add_row(
                    f"{style_config['icon']} {failure_type.value}",
                    f"{count}件",
                    f"[{style_config['color']}]{failure_type.value}エラーの発生数[/{style_config['color']}]",
                )

        return Panel(
            stats_table,
            title="📊 実行統計",
            title_align="left",
            border_style="magenta",
            padding=(1, 2),
        )

    def _format_recommended_actions(self, execution_result: ExecutionResult) -> Panel:
        """推奨アクションを生成"""
        if execution_result.success:
            success_text = Text("🎉 全てのテストが成功しました！", style="bold green")
            return Panel(success_text, title="推奨アクション", border_style="green")

        actions = []

        # 失敗パターンに基づく推奨アクション
        failure_types = set(f.type for f in execution_result.all_failures)

        if FailureType.ASSERTION in failure_types:
            actions.append("🔍 アサーション失敗を確認し、期待値と実際の値を比較してください")

        if FailureType.BUILD_FAILURE in failure_types:
            actions.append("🔨 依存関係とビルド設定を確認してください")

        if FailureType.TIMEOUT in failure_types:
            actions.append("⏰ タイムアウト設定を見直すか、処理を最適化してください")

        if FailureType.TEST_FAILURE in failure_types:
            actions.append("🧪 テストケースとテスト対象コードを確認してください")

        # 一般的な推奨アクション
        actions.extend(
            [
                "📋 上記の失敗詳細を確認し、優先度の高い問題から対処してください",
                "🔄 修正後は再度CI実行して結果を確認してください",
                "📚 不明な点があれば、ログの詳細やドキュメントを参照してください",
            ]
        )

        # アクションリストを作成
        action_tree = Tree("💡 推奨アクション", style="bold yellow")
        for action in actions:
            action_tree.add(Text(action, style="white"))

        return Panel(
            action_tree,
            title="推奨アクション",
            title_align="left",
            border_style="yellow",
            padding=(1, 2),
        )

    def _prioritize_failures(self, failures: list[Failure]) -> list[Failure]:
        """失敗を優先度順にソート（AI Context Formatterと同じロジック）"""

        def calculate_priority_score(failure: Failure) -> int:
            """失敗の優先度スコアを計算"""
            # 基本優先度（失敗タイプ別）
            type_priorities = {
                FailureType.ASSERTION: 100,
                FailureType.ERROR: 90,
                FailureType.BUILD_FAILURE: 85,
                FailureType.TIMEOUT: 80,
                FailureType.TEST_FAILURE: 75,
                FailureType.UNKNOWN: 50,
            }
            base_priority = type_priorities.get(failure.type, 50)

            # 追加スコア
            additional_score = 0

            # ファイル情報があるものを優先
            if failure.file_path:
                additional_score += 20

            # 行番号があるものを優先
            if failure.line_number:
                additional_score += 15

            # スタックトレースがあるものを優先
            if failure.stack_trace:
                additional_score += 10

            # コンテキスト情報があるものを優先
            if failure.context_before or failure.context_after:
                additional_score += 5

            return base_priority + additional_score

        return sorted(failures, key=calculate_priority_score, reverse=True)

    def _find_failure_location(self, failure: Failure, execution_result: ExecutionResult) -> tuple[str, str]:
        """失敗が発生したワークフローとジョブを特定"""
        for workflow in execution_result.workflows:
            for job in workflow.jobs:
                if failure in job.failures:
                    return workflow.name, job.name
        return "不明", "不明"
