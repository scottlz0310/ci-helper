"""
logs コマンドの実装

実行ログの管理・表示機能を提供します。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    pass

from ..core.error_handler import ErrorHandler
from ..core.exceptions import CIHelperError
from ..core.log_manager import LogManager
from ..utils.config import Config

console = Console()


@click.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=10,
    help="表示する最大ログ数（デフォルト: 10）",
)
@click.option(
    "--workflow",
    "-w",
    help="特定のワークフローのログのみ表示",
)
@click.option(
    "--show-content",
    "-c",
    help="指定したログファイルの内容を表示",
)
@click.option(
    "--stats",
    is_flag=True,
    help="ログ統計情報を表示",
)
@click.option(
    "--diff",
    "-d",
    help="指定したログファイルと前回実行の差分を表示",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "markdown", "json"], case_sensitive=False),
    default="table",
    help="差分表示の出力フォーマット（デフォルト: table）",
)
@click.pass_context
def logs(
    ctx: click.Context,
    limit: int,
    workflow: str | None,
    show_content: str | None,
    stats: bool,
    diff: str | None,
    output_format: str,
) -> None:
    """実行ログを管理・表示

    過去のCI実行ログの一覧表示、内容確認、統計情報の表示、差分表示を行います。

    \b
    使用例:
      ci-run logs                    # 最新10件のログを表示
      ci-run logs -l 20              # 最新20件のログを表示
      ci-run logs -w test.yml        # test.ymlのログのみ表示
      ci-run logs -c act_20240101.log # 特定ログの内容を表示
      ci-run logs --stats            # ログ統計情報を表示
      ci-run logs -d act_20240101.log # 指定ログと前回実行の差分を表示
      ci-run logs -d act_20240101.log --format json # JSON形式で差分表示
    """
    config: Config = ctx.obj["config"]
    verbose: bool = ctx.obj.get("verbose", False)

    try:
        log_manager = LogManager(config)

        # 統計情報表示
        if stats:
            _show_log_statistics(log_manager)
            return

        # 特定ログの内容表示
        if show_content:
            _show_log_content(log_manager, show_content, verbose)
            return

        # 差分表示
        if diff:
            _show_log_diff(log_manager, diff, output_format, verbose)
            return

        # ログ一覧表示
        if workflow:
            logs_list = log_manager.find_logs_by_workflow(workflow)
            if not logs_list:
                console.print(f"[yellow]ワークフロー '{workflow}' のログが見つかりません。[/yellow]")
                return
        else:
            logs_list = log_manager.list_logs(limit)

        if not logs_list:
            console.print("[yellow]実行ログが見つかりません。[/yellow]")
            console.print("ci-run test を実行してログを生成してください。")
            return

        _display_logs_table(logs_list, workflow)

    except CIHelperError as e:
        ErrorHandler.handle_error(e, verbose)
        ctx.exit(1)
    except Exception as e:
        ErrorHandler.handle_error(e, verbose)
        ctx.exit(1)


def _show_log_statistics(log_manager: LogManager) -> None:
    """ログ統計情報を表示"""
    stats = log_manager.get_log_statistics()

    table = Table(title="ログ統計情報")
    table.add_column("項目", style="cyan")
    table.add_column("値", style="green")

    table.add_row("総ログ数", str(stats["total_logs"]))
    table.add_row("総サイズ", f"{stats['total_size_mb']} MB")
    table.add_row("成功率", f"{stats['success_rate']}%")
    table.add_row("平均実行時間", f"{stats['average_duration']}秒")

    if stats["latest_execution"]:
        table.add_row("最新実行", stats["latest_execution"])

    console.print(table)


def _show_log_content(log_manager: LogManager, log_filename: str, verbose: bool) -> None:
    """特定ログの内容を表示"""
    try:
        content = log_manager.get_log_content(log_filename)

        console.print(f"[bold cyan]ログファイル: {log_filename}[/bold cyan]")
        console.print("=" * 80)

        if verbose:
            # 詳細モードでは全内容を表示
            console.print(content)
        else:
            # 通常モードでは最初と最後の部分のみ表示
            lines = content.split("\n")
            if len(lines) > 100:
                console.print("\n".join(lines[:50]))
                console.print(f"\n[dim]... ({len(lines) - 100} 行省略) ...[/dim]\n")
                console.print("\n".join(lines[-50:]))
            else:
                console.print(content)

        console.print("=" * 80)

    except Exception as e:
        console.print(f"[red]ログファイルの読み込みに失敗しました: {e}[/red]")


def _display_logs_table(logs_list: list[dict[str, Any]], workflow_filter: str | None = None) -> None:
    """ログ一覧をテーブル形式で表示"""
    title = "実行ログ一覧"
    if workflow_filter:
        title += f" (ワークフロー: {workflow_filter})"

    table = Table(title=title)
    table.add_column("実行日時", style="cyan")
    table.add_column("ログファイル", style="blue")
    table.add_column("ステータス", justify="center")
    table.add_column("実行時間", justify="right")
    table.add_column("失敗数", justify="right")
    table.add_column("ワークフロー数", justify="right")

    for log_entry in logs_list:
        # タイムスタンプをフォーマット
        from datetime import datetime

        timestamp = datetime.fromisoformat(log_entry["timestamp"])
        formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # ステータス表示
        if log_entry["success"]:
            status = "[green]✅ 成功[/green]"
        else:
            status = "[red]❌ 失敗[/red]"

        table.add_row(
            formatted_time,
            log_entry["log_file"],
            status,
            f"{log_entry['total_duration']:.2f}秒",
            str(log_entry["total_failures"]),
            str(len(log_entry["workflows"])),
        )

    console.print(table)

    # 使用方法のヒント
    console.print("\n[dim]ヒント:[/dim]")
    console.print("  ログの内容を表示: [cyan]ci-run logs -c <ログファイル名>[/cyan]")
    console.print("  統計情報を表示: [cyan]ci-run logs --stats[/cyan]")
    console.print("  差分を表示: [cyan]ci-run logs -d <ログファイル名>[/cyan]")


def _show_log_diff(log_manager: LogManager, log_filename: str, output_format: str, verbose: bool) -> None:
    """指定ログと前回実行の差分を表示"""
    try:
        # 指定されたログの実行結果を取得
        execution_history = log_manager.get_execution_history()
        target_execution = None
        previous_execution = None

        # 指定されたログファイルに対応する実行結果を検索
        for i, execution in enumerate(execution_history):
            if execution.log_path and log_filename in execution.log_path:
                target_execution = execution
                # 前回の実行を取得（リストの次の要素）
                if i + 1 < len(execution_history):
                    previous_execution = execution_history[i + 1]
                break

        if not target_execution:
            console.print(f"[red]指定されたログファイルが見つかりません: {log_filename}[/red]")
            return

        if not previous_execution:
            console.print("[yellow]比較対象の前回実行が見つかりません。初回実行の可能性があります。[/yellow]")
            # 初回実行として表示
            _display_initial_execution(target_execution, output_format)
            return

        # 差分を生成
        from ..core.log_comparator import LogComparator

        comparator = LogComparator()
        comparison = comparator.compare_executions(target_execution, previous_execution)

        # フォーマットに応じて表示
        if output_format == "json":
            diff_output = comparator.format_diff_display(comparison, "json")
            console.print(diff_output)
        elif output_format == "markdown":
            diff_output = comparator.format_diff_display(comparison, "markdown")
            console.print(diff_output)
        else:
            _display_diff_table(comparison, verbose)

    except Exception as e:
        console.print(f"[red]差分表示中にエラーが発生しました: {e}[/red]")


def _display_initial_execution(execution, output_format: str) -> None:
    """初回実行の情報を表示"""
    if output_format == "json":
        import json

        result = {
            "type": "initial_execution",
            "timestamp": execution.timestamp.isoformat(),
            "success": execution.success,
            "total_failures": execution.total_failures,
            "total_duration": execution.total_duration,
            "workflows": [
                {
                    "name": w.name,
                    "success": w.success,
                    "duration": w.duration,
                    "job_count": len(w.jobs),
                }
                for w in execution.workflows
            ],
        }
        console.print(json.dumps(result, indent=2, ensure_ascii=False))
    elif output_format == "markdown":
        lines = [
            "# 初回実行",
            "",
            f"**実行日時**: {execution.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**ステータス**: {'✅ 成功' if execution.success else '❌ 失敗'}",
            f"**実行時間**: {execution.total_duration:.2f}秒",
            f"**失敗数**: {execution.total_failures}",
            "",
            "## ワークフロー",
            "",
        ]
        for workflow in execution.workflows:
            status = "✅" if workflow.success else "❌"
            lines.append(f"- **{workflow.name}**: {status} ({workflow.duration:.2f}秒)")

        console.print("\n".join(lines))
    else:
        table = Table(title="初回実行")
        table.add_column("項目", style="cyan")
        table.add_column("値", style="green" if execution.success else "red")

        table.add_row("実行日時", execution.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("ステータス", "成功" if execution.success else "失敗")
        table.add_row("実行時間", f"{execution.total_duration:.2f}秒")
        table.add_row("失敗数", str(execution.total_failures))

        console.print(table)


def _display_diff_table(comparison, verbose: bool) -> None:
    """テーブル形式で差分を表示"""
    from ..core.log_comparator import LogComparator

    comparator = LogComparator()
    summary = comparator.generate_diff_summary(comparison)

    # 概要テーブル
    summary_table = Table(title="実行結果の比較")
    summary_table.add_column("項目", style="cyan")
    summary_table.add_column("現在", justify="center")
    summary_table.add_column("前回", justify="center")
    summary_table.add_column("変化", justify="center")

    # ステータス行
    current_status = "✅ 成功" if summary["current_status"] == "success" else "❌ 失敗"
    previous_status = "✅ 成功" if summary["previous_status"] == "success" else "❌ 失敗"
    status_change = "変化なし"
    if summary["current_status"] != summary["previous_status"]:
        if summary["current_status"] == "success":
            status_change = "[green]改善[/green]"
        else:
            status_change = "[red]悪化[/red]"

    summary_table.add_row("ステータス", current_status, previous_status, status_change)

    # エラー数行
    error_counts = summary["error_counts"]
    current_errors = str(error_counts["current"])
    previous_errors = str(error_counts["previous"])
    net_change = error_counts["net_change"]

    if net_change > 0:
        error_change = f"[red]+{net_change}[/red]"
    elif net_change < 0:
        error_change = f"[green]{net_change}[/green]"
    else:
        error_change = "変化なし"

    summary_table.add_row("エラー数", current_errors, previous_errors, error_change)

    # 実行時間行
    performance = summary["performance"]
    current_time = f"{performance['current_duration']:.2f}秒"
    previous_time = f"{performance['previous_duration']:.2f}秒"
    time_change_percent = performance["time_change_percent"]

    if abs(time_change_percent) < 5:
        time_change = "変化なし"
    elif time_change_percent > 0:
        time_change = f"[red]+{time_change_percent:.1f}%[/red]"
    else:
        time_change = f"[green]{time_change_percent:.1f}%[/green]"

    summary_table.add_row("実行時間", current_time, previous_time, time_change)

    console.print(summary_table)

    # エラー詳細テーブル
    if comparison.new_errors or comparison.resolved_errors:
        console.print()
        error_table = Table(title="エラーの変化")
        error_table.add_column("種類", style="cyan")
        error_table.add_column("数", justify="right")
        error_table.add_column("詳細", style="dim")

        if comparison.new_errors:
            error_table.add_row(
                "[red]新規エラー[/red]",
                str(len(comparison.new_errors)),
                f"{len(comparison.new_errors)}件の新しいエラーが発生",
            )

        if comparison.resolved_errors:
            error_table.add_row(
                "[green]解決済みエラー[/green]",
                str(len(comparison.resolved_errors)),
                f"{len(comparison.resolved_errors)}件のエラーが解決",
            )

        if comparison.persistent_errors:
            error_table.add_row(
                "[yellow]継続エラー[/yellow]",
                str(len(comparison.persistent_errors)),
                f"{len(comparison.persistent_errors)}件のエラーが継続",
            )

        console.print(error_table)

    # 詳細モードでエラー内容も表示
    if verbose and (comparison.new_errors or comparison.resolved_errors):
        if comparison.new_errors:
            console.print()
            new_error_table = Table(title="新規エラーの詳細")
            new_error_table.add_column("タイプ", style="red")
            new_error_table.add_column("メッセージ")
            new_error_table.add_column("場所", style="dim")

            for error in comparison.new_errors[:5]:  # 最初の5件のみ表示
                location = ""
                if error.file_path:
                    location = error.file_path
                    if error.line_number:
                        location += f":{error.line_number}"

                new_error_table.add_row(
                    error.type.value.upper(),
                    error.message[:80] + "..." if len(error.message) > 80 else error.message,
                    location,
                )

            console.print(new_error_table)

        if comparison.resolved_errors:
            console.print()
            resolved_error_table = Table(title="解決済みエラーの詳細")
            resolved_error_table.add_column("タイプ", style="green")
            resolved_error_table.add_column("メッセージ")
            resolved_error_table.add_column("場所", style="dim")

            for error in comparison.resolved_errors[:5]:  # 最初の5件のみ表示
                location = ""
                if error.file_path:
                    location = error.file_path
                    if error.line_number:
                        location += f":{error.line_number}"

                resolved_error_table.add_row(
                    error.type.value.upper(),
                    error.message[:80] + "..." if len(error.message) > 80 else error.message,
                    location,
                )

            console.print(resolved_error_table)
