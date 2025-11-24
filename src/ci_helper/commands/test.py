"""test コマンドの実装

CI/CDワークフローをローカルで実行し、結果を分析・フォーマットします。
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

if TYPE_CHECKING:
    from ..core.models import ExecutionResult, LogComparisonResult

from ..core.ai_formatter import AIFormatter
from ..core.ci_runner import CIRunner
from ..core.error_handler import DependencyChecker, ErrorHandler
from ..core.exceptions import CIHelperError
from ..core.log_manager import LogManager
from ..utils.config import Config

console = Console()


@click.command()
@click.option(
    "--workflow",
    "-w",
    multiple=True,
    help="実行するワークフローファイル名（複数指定可能）",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="詳細な実行情報を表示",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "table"], case_sensitive=False),
    default="table",
    help="出力フォーマット（デフォルト: table）",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="実際には実行せず、実行予定の内容を表示",
)
@click.option(
    "--log",
    "log_file",
    type=click.Path(exists=True, path_type=Path),
    help="既存のログファイルを解析（ドライラン時のみ）",
)
@click.option(
    "--diff",
    is_flag=True,
    help="前回の実行結果と比較",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="実行ログを保存するかどうか（デフォルト: 保存する）",
)
@click.option(
    "--sanitize/--no-sanitize",
    default=True,
    help="出力からシークレットを自動除去するかどうか（デフォルト: 除去する）",
)
@click.pass_context
def test(
    ctx: click.Context,
    workflow: tuple[str, ...],
    verbose: bool,
    output_format: str,
    dry_run: bool,
    log_file: Path | None,
    diff: bool,
    save: bool,
    sanitize: bool,
) -> ExecutionResult | None:
    """CI/CDワークフローをローカルで実行

    actを使用してGitHub Actionsワークフローをローカルで実行し、
    失敗を分析してAI対応の出力を生成します。

    \b
    使用例:
      ci-run test                           # 全ワークフローを実行
      ci-run test -w test.yml               # 特定のワークフローを実行
      ci-run test -w test.yml -w build.yml  # 複数のワークフローを実行
      ci-run test --verbose                 # 詳細出力で実行
      ci-run test --dry-run                 # ドライラン（実行せずに確認）
      ci-run test --format json             # JSON形式で出力
      ci-run test --diff                    # 前回実行との差分表示
      ci-run test --dry-run --log path.log  # 既存ログを解析
    """
    try:
        config: Config = ctx.obj["config"] if ctx.obj else Config()
        global_verbose: bool = ctx.obj.get("verbose", False) if ctx.obj else False
        verbose = verbose or global_verbose

        # ドライラン時のログファイル解析
        if dry_run and log_file:
            _analyze_existing_log(log_file, output_format, verbose)
            return None

        ci_runner = CIRunner(config)

        if not dry_run:
            ci_runner.check_lock_file()
            _check_dependencies(config.project_root, verbose)

        # CI実行
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            if dry_run:
                task = progress.add_task("ドライラン実行中...", total=None)
            else:
                task = progress.add_task("ワークフロー実行中...", total=None)

            execution_result = ci_runner.run_workflows(
                workflows=list(workflow) if workflow else None,
                verbose=verbose,
                dry_run=dry_run,
                save_logs=save,
            )

            progress.update(task, completed=True)

        # 差分表示の処理
        if diff and not dry_run:
            _show_diff_with_previous(config, execution_result, verbose)

        # 結果の表示
        _display_results(execution_result, output_format, verbose, dry_run, sanitize)

        # 失敗時の処理
        if not execution_result.success and not dry_run:
            # メニューシステムから呼び出された場合は終了コードではなく結果を返す
            if hasattr(ctx, "obj") and ctx.obj and ctx.obj.get("from_menu", False):
                _display_failure_summary(execution_result)
                return execution_result
            ctx.exit(1)

    except CIHelperError as e:
        ErrorHandler.handle_error(e, verbose)
        ctx.exit(1)
    except Exception as e:
        ErrorHandler.handle_error(e, verbose)
        ctx.exit(1)


def _display_failure_summary(execution_result: ExecutionResult) -> None:
    """CI失敗時の概要を表示"""
    console = Console()

    failed_workflows = execution_result.failed_workflows
    failed_jobs = execution_result.failed_jobs

    console.print("\n[yellow]📋 CI実行結果[/yellow]")
    console.print(f"[red]✗[/red] {len(failed_workflows)}個のワークフローが失敗しました")
    console.print(f"[red]✗[/red] {len(failed_jobs)}個のジョブが失敗しました")

    if execution_result.log_path:
        console.print(f"[green]✓[/green] 失敗ログを収集しました: [cyan]{execution_result.log_path}[/cyan]")

    console.print("\n[bold blue]💡 次のステップ:[/bold blue]")
    console.print("• [cyan]AI分析[/cyan] でエラーの根本原因を特定")
    console.print("• [cyan]ログ管理[/cyan] で詳細なログを確認")
    console.print("• [cyan]環境チェック[/cyan] で依存関係を確認")


@contextmanager
def _temporary_cwd(path: Path) -> Generator[None]:
    """一時的にカレントディレクトリを変更"""
    original_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def _check_dependencies(project_root: Path | None = None, verbose: bool = False) -> None:
    """依存関係をチェック"""
    if verbose:
        console.print("[dim]依存関係をチェック中...[/dim]")

    base_dir = project_root or Path.cwd()

    try:
        DependencyChecker.check_act_command()
        DependencyChecker.check_docker_daemon()
        DependencyChecker.check_disk_space()
        with _temporary_cwd(base_dir):
            DependencyChecker.check_workflows_directory()

        if verbose:
            console.print("[green]✓[/green] 全ての依存関係が満たされています")

    except CIHelperError:
        raise


def _analyze_existing_log(log_file: Path, output_format: str, verbose: bool) -> None:
    """既存のログファイルを解析"""
    console.print(f"[dim]ログファイルを解析中: {log_file}[/dim]")

    try:
        with open(log_file, encoding="utf-8") as f:
            log_content = f.read()

        # 基本的なログ解析（詳細な失敗抽出は後のタスクで実装）
        lines = log_content.split("\n")
        total_lines = len(lines)

        # 簡単な統計情報を表示
        if output_format == "json":
            import json

            result = {
                "log_file": str(log_file),
                "total_lines": total_lines,
                "analysis": "基本的なログ解析（詳細な失敗抽出は今後実装予定）",
            }
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
        elif output_format == "markdown":
            console.print(f"""
# ログ解析結果

- **ログファイル**: {log_file}
- **総行数**: {total_lines}
- **解析状況**: 基本的なログ解析（詳細な失敗抽出は今後実装予定）
""")
        else:
            table = Table(title="ログ解析結果")
            table.add_column("項目", style="cyan")
            table.add_column("値", style="green")

            table.add_row("ログファイル", str(log_file))
            table.add_row("総行数", str(total_lines))
            table.add_row("解析状況", "基本的なログ解析（詳細な失敗抽出は今後実装予定）")

            console.print(table)

    except Exception as e:
        from ..core.exceptions import LogParsingError

        raise LogParsingError(
            f"ログファイルの読み込みに失敗しました: {log_file}",
            f"ファイル権限やエンコーディングを確認してください: {e}",
        ) from e


def _show_diff_with_previous(config: Config, current_result: ExecutionResult, verbose: bool) -> None:
    """前回実行との差分を表示"""
    log_manager = LogManager(config)

    if verbose:
        console.print("[dim]前回実行との差分を計算中...[/dim]")

    try:
        # 前回の実行結果を取得
        previous_result = log_manager.get_previous_execution(current_result.timestamp)

        if not previous_result:
            console.print("[yellow]前回の実行ログが見つかりません。差分表示をスキップします。[/yellow]")
            return

        # 差分を生成
        from ..core.log_comparator import LogComparator

        comparator = LogComparator()
        comparison = comparator.compare_executions(current_result, previous_result)

        # 差分を表示
        _display_diff_summary(comparison, verbose)

    except Exception as e:
        if verbose:
            console.print(f"[red]差分計算中にエラーが発生しました: {e}[/red]")
        else:
            console.print("[yellow]差分表示をスキップします。[/yellow]")


def _display_diff_summary(comparison: LogComparisonResult, verbose: bool) -> None:
    """差分サマリーを表示"""
    from ..core.log_comparator import LogComparator

    comparator = LogComparator()
    summary = comparator.generate_diff_summary(comparison)

    # 改善スコアに基づいてパネルの色を決定
    improvement_score = summary["improvement_score"]
    if improvement_score > 0.8:
        border_style = "green"
        title_style = "bold green"
    elif improvement_score > 0.5:
        border_style = "yellow"
        title_style = "bold yellow"
    else:
        border_style = "red"
        title_style = "bold red"

    # パネル内容を構築
    error_counts = summary["error_counts"]
    performance = summary["performance"]

    panel_lines: list[str] = []
    panel_lines.append(f"**前回実行**: {'✅ 成功' if summary['previous_status'] == 'success' else '❌ 失敗'}")
    panel_lines.append(f"**今回実行**: {'✅ 成功' if summary['current_status'] == 'success' else '❌ 失敗'}")
    panel_lines.append("")

    # エラー数の変化
    net_change = error_counts["net_change"]
    if net_change > 0:
        panel_lines.append(f"**エラー数**: {error_counts['previous']} → {error_counts['current']} (+{net_change})")
    elif net_change < 0:
        panel_lines.append(f"**エラー数**: {error_counts['previous']} → {error_counts['current']} ({net_change})")
    else:
        panel_lines.append(f"**エラー数**: {error_counts['current']} (変化なし)")

    # 実行時間の変化
    time_change = performance["time_change"]
    if abs(time_change) > 1:  # 1秒以上の変化
        if time_change > 0:
            panel_lines.append(f"**実行時間**: +{time_change:.1f}秒 遅くなりました")
        else:
            panel_lines.append(f"**実行時間**: {abs(time_change):.1f}秒 速くなりました")

    # 新規・解決済みエラーの概要
    if error_counts["new"] > 0:
        panel_lines.append(f"**新規エラー**: {error_counts['new']}件")
    if error_counts["resolved"] > 0:
        panel_lines.append(f"**解決済みエラー**: {error_counts['resolved']}件")

    panel_content = "\n".join(panel_lines)

    panel = Panel(
        panel_content,
        title=f"[{title_style}]実行結果の比較[/{title_style}]",
        border_style=border_style,
    )
    console.print(panel)

    # 詳細モードで追加情報を表示
    if verbose and (comparison.new_errors or comparison.resolved_errors):
        if comparison.new_errors:
            console.print(f"\n[red]新規エラー ({len(comparison.new_errors)}件):[/red]")
            for i, error in enumerate(comparison.new_errors[:3], 1):  # 最初の3件のみ
                console.print(f"  {i}. [{error.type.value.upper()}] {error.message[:100]}...")

        if comparison.resolved_errors:
            console.print(f"\n[green]解決済みエラー ({len(comparison.resolved_errors)}件):[/green]")
            for i, error in enumerate(comparison.resolved_errors[:3], 1):  # 最初の3件のみ
                console.print(f"  {i}. [{error.type.value.upper()}] {error.message[:100]}...")

        if len(comparison.new_errors) > 3 or len(comparison.resolved_errors) > 3:
            console.print("\n[dim]詳細な差分表示: ci-run logs -d <ログファイル名>[/dim]")


def _display_results(
    execution_result: ExecutionResult,
    output_format: str,
    verbose: bool,
    dry_run: bool,
    sanitize: bool = True,
) -> None:
    """実行結果を表示"""
    if output_format == "json":
        _display_json_results(execution_result, verbose, dry_run, sanitize)
    elif output_format == "markdown":
        _display_markdown_results(execution_result, verbose, dry_run, sanitize)
    else:
        _display_table_results(execution_result, verbose, dry_run)


def _display_json_results(
    execution_result: ExecutionResult,
    verbose: bool,
    dry_run: bool,
    sanitize: bool = True,
) -> None:
    """JSON形式で結果を表示（AI最適化）"""
    formatter = AIFormatter(sanitize_secrets=sanitize)

    # AI最適化されたJSON出力を使用
    json_output = formatter.format_json(execution_result)

    # セキュリティ検証（verbose時）
    if verbose and sanitize:
        security_result = formatter.validate_output_security(json_output)
        if security_result["has_secrets"]:
            console.print(
                f"[yellow]警告: {security_result['secret_count']}件のシークレットが検出され、サニタイズされました[/yellow]",
            )

    # トークン情報を表示（verbose時）
    if verbose:
        try:
            token_info = formatter.check_token_limits(json_output)
            console.print(
                f"[dim]トークン数: {token_info['token_count']} / {token_info['token_limit']} ({token_info['usage_percentage']:.1f}%)[/dim]",
            )

            if token_info["warning_level"] != "none":
                console.print(f"[yellow]警告: {token_info['warning_message']}[/yellow]")
        except ImportError:
            # tiktokenが利用できない場合はスキップ
            pass

    console.print(json_output)


def _display_markdown_results(
    execution_result: ExecutionResult,
    verbose: bool,
    dry_run: bool,
    sanitize: bool = True,
) -> None:
    """Markdown形式で結果を表示（AI最適化）"""
    formatter = AIFormatter(sanitize_secrets=sanitize)

    # AI最適化されたMarkdown出力を使用
    markdown_output = formatter.format_markdown(execution_result)

    # セキュリティ検証（verbose時）
    if verbose and sanitize:
        security_result = formatter.validate_output_security(markdown_output)
        if security_result["has_secrets"]:
            console.print(
                f"[yellow]警告: {security_result['secret_count']}件のシークレットが検出され、サニタイズされました[/yellow]",
            )

    # ドライラン情報を追加
    if dry_run:
        markdown_output = f"# ドライラン結果\n\n{markdown_output[markdown_output.find('**ステータス**') :]}"

    # トークン情報を表示（verbose時）
    if verbose:
        try:
            token_info = formatter.check_token_limits(markdown_output)
            console.print(
                f"[dim]トークン数: {token_info['token_count']} / {token_info['token_limit']} ({token_info['usage_percentage']:.1f}%)[/dim]",
            )

            if token_info["warning_level"] != "none":
                console.print(f"[yellow]警告: {token_info['warning_message']}[/yellow]")

                # 圧縮提案を表示
                suggestions = formatter.suggest_compression_options(execution_result)
                if suggestions:
                    console.print("[dim]圧縮オプション:[/dim]")
                    for suggestion in suggestions[:3]:  # 最初の3つのみ表示
                        console.print(f"[dim]  - {suggestion}[/dim]")
        except ImportError:
            # tiktokenが利用できない場合はスキップ
            pass

    console.print(markdown_output)


def _display_table_results(execution_result: ExecutionResult, verbose: bool, dry_run: bool) -> None:
    """テーブル形式で結果を表示"""
    # 概要テーブル
    summary_table = Table(title=f"CI {'ドライラン' if dry_run else '実行'}結果")
    summary_table.add_column("項目", style="cyan")
    summary_table.add_column("値", style="green" if execution_result.success else "red")

    summary_table.add_row("ステータス", "成功" if execution_result.success else "失敗")
    summary_table.add_row("実行時間", f"{execution_result.total_duration:.2f}秒")
    summary_table.add_row("失敗数", str(execution_result.total_failures))
    summary_table.add_row("ワークフロー数", str(len(execution_result.workflows)))

    if execution_result.log_path:
        summary_table.add_row("ログファイル", str(execution_result.log_path))

    console.print(summary_table)

    # ワークフロー詳細テーブル
    if execution_result.workflows:
        console.print()
        workflow_table = Table(title="ワークフロー詳細")
        workflow_table.add_column("ワークフロー", style="cyan")
        workflow_table.add_column("ステータス", justify="center")
        workflow_table.add_column("実行時間", justify="right")
        workflow_table.add_column("ジョブ数", justify="right")

        for workflow in execution_result.workflows:
            status_icon = "✅" if workflow.success else "❌"
            status_style = "green" if workflow.success else "red"

            workflow_table.add_row(
                workflow.name,
                f"[{status_style}]{status_icon}[/{status_style}]",
                f"{workflow.duration:.2f}秒",
                str(len(workflow.jobs)),
            )

        console.print(workflow_table)

        # 詳細モードでジョブ情報も表示
        if verbose:
            for workflow in execution_result.workflows:
                if workflow.jobs:
                    console.print()
                    job_table = Table(title=f"ジョブ詳細: {workflow.name}")
                    job_table.add_column("ジョブ", style="cyan")
                    job_table.add_column("ステータス", justify="center")
                    job_table.add_column("実行時間", justify="right")
                    job_table.add_column("ステップ数", justify="right")
                    job_table.add_column("失敗数", justify="right")

                    for job in workflow.jobs:
                        job_status_icon = "✅" if job.success else "❌"
                        job_status_style = "green" if job.success else "red"

                        job_table.add_row(
                            job.name,
                            f"[{job_status_style}]{job_status_icon}[/{job_status_style}]",
                            f"{job.duration:.2f}秒",
                            str(len(job.steps)),
                            str(len(job.failures)),
                        )

                    console.print(job_table)
