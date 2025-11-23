"""clean コマンド

キャッシュとログファイルのクリーンアップ機能を提供します。
"""

from __future__ import annotations

from typing import Any, cast

import click
from rich.console import Console
from rich.table import Table

from ..core.cache_manager import CacheManager
from ..core.exceptions import ExecutionError
from ..utils.config import Config


@click.command()
@click.option(
    "--logs-only",
    is_flag=True,
    help="ログファイルのみを削除（キャッシュは保持）",
)
@click.option(
    "--all",
    "clean_all",
    is_flag=True,
    help="すべてのキャッシュとログを削除（完全リセット）",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="実際の削除を行わず、削除対象のみを表示",
)
@click.option(
    "--force",
    is_flag=True,
    help="確認なしで削除を実行",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="詳細な出力を表示",
)
@click.pass_context
def clean(ctx: click.Context, logs_only: bool, clean_all: bool, dry_run: bool, force: bool, verbose: bool) -> None:
    """キャッシュとログファイルをクリーンアップ

    デフォルトでは、設定に基づいて古いログとキャッシュファイルを自動削除します。
    """
    console = Console()

    try:
        # 設定を読み込み
        config: Config = ctx.obj.get("config") if ctx.obj else Config()
        cache_manager = CacheManager(config)

        # 相互排他的なオプションのチェック
        if sum([logs_only, clean_all]) > 1:
            raise ExecutionError("オプションが競合しています", "--logs-only と --all は同時に指定できません")

        # 現在の状況を表示
        if verbose or dry_run:
            _display_cache_status(console, cache_manager)

        # クリーンアップの実行
        if clean_all:
            result = _clean_all(console, cache_manager, dry_run, force)
        elif logs_only:
            result = _clean_logs_only(console, cache_manager, dry_run, force)
        else:
            result = _clean_default(console, cache_manager, dry_run, force)

        # 結果を表示
        _display_cleanup_result(console, result, dry_run, verbose)

        # 推奨事項を表示
        if not dry_run and verbose:
            _display_recommendations(console, cache_manager)

    except ExecutionError as e:
        console.print(f"[red]エラー:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]提案:[/yellow] {e.suggestion}")
        raise click.Abort() from e
    except Exception as e:
        console.print(f"[red]予期しないエラーが発生しました:[/red] {e}")
        raise click.Abort() from e


def _display_cache_status(console: Console, cache_manager: CacheManager) -> None:
    """現在のキャッシュ状況を表示

    Args:
        console: Rich コンソール
        cache_manager: キャッシュマネージャー

    """
    console.print("\n[bold blue]現在のキャッシュ状況[/bold blue]")

    stats = cache_manager.get_cache_statistics()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("カテゴリ", style="cyan")
    table.add_column("ファイル数", justify="right")
    table.add_column("サイズ (MB)", justify="right")
    table.add_column("最古ファイル", style="dim")
    table.add_column("最新ファイル", style="dim")

    for category, data in stats.items():
        if category == "total":
            table.add_row()  # 区切り線
            table.add_row(
                "[bold]合計[/bold]",
                f"[bold]{data['files']}[/bold]",
                f"[bold]{data['size_mb']:.2f}[/bold]",
                data["oldest_file"].strftime("%Y-%m-%d") if data["oldest_file"] else "-",
                data["newest_file"].strftime("%Y-%m-%d") if data["newest_file"] else "-",
            )
        else:
            oldest = data["oldest_file"].strftime("%Y-%m-%d") if data["oldest_file"] else "-"
            newest = data["newest_file"].strftime("%Y-%m-%d") if data["newest_file"] else "-"

            table.add_row(
                category.capitalize(),
                str(data["files"]),
                f"{data['size_mb']:.2f}",
                oldest,
                newest,
            )

    console.print(table)


def _clean_all(console: Console, cache_manager: CacheManager, dry_run: bool, force: bool) -> dict[str, Any]:
    """すべてのキャッシュを削除

    Args:
        console: Rich コンソール
        cache_manager: キャッシュマネージャー
        dry_run: ドライラン実行
        force: 強制実行

    Returns:
        クリーンアップ結果

    """
    if not dry_run and not force:
        console.print("\n[bold red]警告: すべてのキャッシュとログが削除されます！[/bold red]")
        console.print("この操作は元に戻せません。")

        if not click.confirm("続行しますか？"):
            console.print("[yellow]操作がキャンセルされました。[/yellow]")
            return {"skipped": True, "reason": "ユーザーによりキャンセルされました"}

    if dry_run:
        console.print("\n[bold yellow]ドライラン: すべてのキャッシュ削除[/bold yellow]")
        return cache_manager.cleanup_all(dry_run=True)
    console.print("\n[bold red]すべてのキャッシュを削除中...[/bold red]")
    return cache_manager.reset_all_cache(confirm=True)


def _clean_logs_only(console: Console, cache_manager: CacheManager, dry_run: bool, force: bool) -> dict[str, Any]:
    """ログファイルのみを削除

    Args:
        console: Rich コンソール
        cache_manager: キャッシュマネージャー
        dry_run: ドライラン実行
        force: 強制実行

    Returns:
        クリーンアップ結果

    """
    if not dry_run and not force:
        stats = cache_manager.get_cache_statistics()
        log_stats = stats["logs"]

        if log_stats["files"] > 0:
            console.print(
                f"\n[yellow]ログファイル {log_stats['files']} 個 ({log_stats['size_mb']:.2f}MB) を削除します。[/yellow]",
            )

            if not click.confirm("続行しますか？"):
                console.print("[yellow]操作がキャンセルされました。[/yellow]")
                return {"skipped": True, "reason": "ユーザーによりキャンセルされました"}

    if dry_run:
        console.print("\n[bold yellow]ドライラン: ログファイル削除[/bold yellow]")
    else:
        console.print("\n[bold blue]ログファイルを削除中...[/bold blue]")

    return cache_manager.cleanup_logs_only(dry_run=dry_run, remove_all=True)


def _clean_default(console: Console, cache_manager: CacheManager, dry_run: bool, force: bool) -> dict[str, Any]:
    """デフォルトのクリーンアップ

    Args:
        console: Rich コンソール
        cache_manager: キャッシュマネージャー
        dry_run: ドライラン実行
        force: 強制実行

    Returns:
        クリーンアップ結果

    """
    if not dry_run and not force:
        # 推奨事項を表示
        recommendations = cache_manager.get_cleanup_recommendations()

        if recommendations["recommendations"]:
            console.print("\n[bold yellow]クリーンアップ推奨事項:[/bold yellow]")
            for rec in recommendations["recommendations"]:
                priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(rec["priority"], "white")

                console.print(f"[{priority_color}]• {rec['message']}[/{priority_color}]")
                console.print(f"  {rec['action']}")

        console.print(f"\n[blue]合計キャッシュサイズ: {recommendations['total_size_mb']:.2f}MB[/blue]")

        if not click.confirm("標準クリーンアップを実行しますか？"):
            console.print("[yellow]操作がキャンセルされました。[/yellow]")
            return {"skipped": True, "reason": "ユーザーによりキャンセルされました"}

    if dry_run:
        console.print("\n[bold yellow]ドライラン: 標準クリーンアップ[/bold yellow]")
    else:
        console.print("\n[bold blue]標準クリーンアップを実行中...[/bold blue]")

    return cache_manager.cleanup_all(dry_run=dry_run)


def _display_cleanup_result(console: Console, result: dict[str, Any], dry_run: bool, verbose: bool) -> None:
    """クリーンアップ結果を表示

    Args:
        console: Rich コンソール
        result: クリーンアップ結果
        dry_run: ドライラン実行
        verbose: 詳細表示

    """
    console.print()

    if "skipped" in result:
        console.print(f"[yellow]スキップ:[/yellow] {result['reason']}")
        return

    # 完全リセットの場合
    if "deleted_directories" in result:
        console.print("[bold green]完全リセット完了[/bold green]")

        if result["deleted_directories"]:
            console.print(f"削除されたディレクトリ: {', '.join(result['deleted_directories'])}")

        console.print(f"解放されたサイズ: {result['total_freed_mb']:.2f}MB")

        if result["errors"]:
            console.print("\n[red]エラー:[/red]")
            for error in result["errors"]:
                console.print(f"  • {error}")

        return

    # 通常のクリーンアップ結果
    action_text = "削除予定" if dry_run else "削除完了"

    if "total" in result:
        # 複数カテゴリの結果
        console.print(f"[bold green]{action_text}[/bold green]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("カテゴリ", style="cyan")
        table.add_column("ファイル数", justify="right")
        table.add_column("サイズ (MB)", justify="right")
        table.add_column("エラー数", justify="right")

        for category, data in result.items():
            if category == "total":
                table.add_row()  # 区切り線
                table.add_row(
                    "[bold]合計[/bold]",
                    f"[bold]{data['deleted_files']}[/bold]",
                    f"[bold]{data['freed_size_mb']:.2f}[/bold]",
                    f"[bold]{data['errors']}[/bold]",
                )
            elif isinstance(data, dict) and "deleted_files" in data:
                data_dict = cast("dict[str, Any]", data)
                table.add_row(
                    category.capitalize(),
                    str(data_dict["deleted_files"]),
                    f"{data_dict['freed_size_mb']:.2f}",
                    str(len(cast("list[Any]", data_dict.get("errors", [])))),
                )

        console.print(table)

    else:
        # 単一カテゴリの結果
        console.print(f"[bold green]{action_text}[/bold green]")
        console.print(f"ファイル数: {result['deleted_files']}")
        console.print(f"解放サイズ: {result['freed_size_mb']:.2f}MB")

    # エラーの詳細表示
    if verbose:
        all_errors: list[str] = []
        if "errors" in result:
            all_errors.extend(cast("list[str]", result["errors"]))
        elif "total" in result:
            for key, category_result in result.items():
                if key != "total" and isinstance(category_result, dict) and "errors" in category_result:
                    category_dict = cast("dict[str, Any]", category_result)
                    all_errors.extend(cast("list[str]", category_dict["errors"]))

        if all_errors:
            console.print("\n[red]エラー詳細:[/red]")
            for error in all_errors:
                console.print(f"  • {error}")

    # ドライランの場合は削除対象ファイルを表示
    if dry_run and verbose and "files_to_delete" in result:
        files_to_delete = result["files_to_delete"]
        if files_to_delete:
            console.print(f"\n[yellow]削除対象ファイル ({len(files_to_delete)}個):[/yellow]")
            for file_path in files_to_delete[:10]:  # 最初の10個のみ表示
                console.print(f"  • {file_path}")

            if len(files_to_delete) > 10:
                console.print(f"  ... 他 {len(files_to_delete) - 10} 個")


def _display_recommendations(console: Console, cache_manager: CacheManager) -> None:
    """クリーンアップ後の推奨事項を表示

    Args:
        console: Rich コンソール
        cache_manager: キャッシュマネージャー

    """
    recommendations = cache_manager.get_cleanup_recommendations()

    if recommendations["recommendations"]:
        console.print("\n[bold blue]追加の推奨事項:[/bold blue]")
        for rec in recommendations["recommendations"]:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(rec["priority"], "white")

            console.print(f"[{priority_color}]• {rec['message']}[/{priority_color}]")
            console.print(f"  {rec['action']}")

    # 自動クリーンアップの状態
    if recommendations["auto_cleanup_enabled"]:
        next_cleanup = recommendations["next_auto_cleanup"]
        if next_cleanup:
            console.print(f"\n[dim]次回自動クリーンアップ: {next_cleanup.strftime('%Y-%m-%d %H:%M')}[/dim]")
    else:
        console.print("\n[dim]自動クリーンアップは無効です[/dim]")
