"""ci-helper CLIエントリーポイント

Clickを使用したマルチコマンドCLIインターフェースを提供します。
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from . import __version__

# サブコマンドのインポート
from .commands.cache import cache
from .commands.clean import clean
from .commands.doctor import doctor
from .commands.format_logs import format_logs, format_logs_custom_handler, format_logs_handler
from .commands.init import init, setup
from .commands.logs import logs
from .commands.secrets import secrets
from .commands.test import test
from .core.error_handler import ErrorHandler
from .core.exceptions import CIHelperError
from .ui import CommandMenuBuilder, MenuSystem
from .utils.config import Config

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="ci-run")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="詳細な出力を表示します",
)
@click.option(
    "--config-file",
    type=click.Path(exists=True, path_type=Path),
    help="設定ファイルのパスを指定します",
)
@click.option(
    "--menu",
    "-m",
    is_flag=True,
    help="対話的メニューモードで起動します",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_file: Path | None, menu: bool) -> None:
    """ci-helper: ローカルCI検証とAI連携ツール

    actを使用してGitHub Actionsワークフローをローカルで実行し、
    失敗を分析してAI対応の出力を生成します。

    \b
    主要コマンド:
      init         設定ファイルテンプレートを生成
      doctor       環境依存関係をチェック
      test         CI/CDワークフローをローカルで実行
      analyze      AI分析でCI失敗の根本原因を特定
      logs         実行ログを管理・表示
      format-logs  ログを様々な形式で整形
      secrets      シークレット管理と検証
      clean        キャッシュとログをクリーンアップ
      cache        Dockerイメージのキャッシュ管理

    \b
    使用例:
      ci-run                         # 対話的メニューモードで起動
      ci-run --menu                  # 対話的メニューモードで起動
      ci-run init                    # 初期設定
      ci-run doctor                  # 環境チェック
      ci-run cache --pull            # Dockerイメージを事前プル
      ci-run test                    # 全ワークフローを実行
      ci-run test -w test.yml        # 特定のワークフローを実行
      ci-run analyze                 # 最新のログをAI分析
      ci-run analyze --interactive   # 対話的なAIデバッグ
      ci-run logs                    # ログ一覧を表示
    """
    # コンテキストオブジェクトの初期化
    ctx.ensure_object(dict)

    try:
        # グローバル設定の初期化
        project_root = Path.cwd()
        if config_file:
            project_root = config_file.parent
        else:
            project_root = _find_project_root(project_root)

        config = Config(project_root)
        config.validate()

        # コンテキストに設定を保存
        ctx.obj["config"] = config
        ctx.obj["verbose"] = verbose
        ctx.obj["console"] = console

        # 詳細モードの場合、設定情報を表示
        if verbose:
            console.print(f"[dim]プロジェクトルート: {project_root}[/dim]")
            console.print(f"[dim]設定ファイル: {config.config_file}[/dim]")

        # メニューモードまたはコマンドが指定されていない場合
        if menu or ctx.invoked_subcommand is None:
            _start_menu_mode(ctx)
            return

    except CIHelperError as e:
        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)
    except Exception as e:
        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)


# サブコマンドの登録
cli.add_command(init)
cli.add_command(setup)
cli.add_command(doctor)
cli.add_command(test)
cli.add_command(logs)
cli.add_command(format_logs)
cli.add_command(secrets)
cli.add_command(clean)
cli.add_command(cache)

# フィードバックコマンドの登録
try:
    from .commands.feedback import feedback

    cli.add_command(feedback)
except ImportError:
    pass

# AI統合コマンドの遅延登録（循環インポート回避）
try:
    from .commands.analyze import analyze

    cli.add_command(analyze)
except ImportError:
    # AI統合が利用できない場合はスキップ
    pass


def _find_project_root(start_path: Path) -> Path:
    """プロジェクトルートを探索"""
    search_paths = [start_path, *start_path.parents]

    for path in search_paths:
        workflows_dir = path / ".github" / "workflows"
        if workflows_dir.exists() and workflows_dir.is_dir():
            return path

    for path in search_paths:
        if (path / "ci-helper.toml").exists():
            return path

    return start_path


def _start_menu_mode(ctx: click.Context) -> None:
    """対話的メニューモードを開始

    Args:
        ctx: Click コンテキスト

    """
    console = _get_console(ctx)

    try:
        # コマンドハンドラーを作成
        command_handlers = _create_command_handlers(ctx)

        # メニューシステムを初期化
        menu_builder = CommandMenuBuilder(console, command_handlers)
        menu_system = MenuSystem(console)

        # メインメニューを構築して開始
        main_menu = menu_builder.build_main_menu()
        menu_system.start(main_menu)

    except KeyboardInterrupt:
        console.print("\n[yellow]メニューモードが中断されました。[/yellow]")
    except Exception as e:
        console.print(f"[red]メニューモードでエラーが発生しました: {e}[/red]")


def _get_console(ctx: click.Context) -> Console:
    """Get console from context or create a new one."""
    try:
        if ctx.obj and hasattr(ctx.obj, "get"):
            console = ctx.obj.get("console")
            if console:
                return console  # type: ignore
    except Exception:
        pass
    return Console()


def _invoke_command(ctx: click.Context, command_func: click.Command, *args: object, **kwargs: object) -> object:
    """Safely invoke a command function."""
    console = _get_console(ctx)

    try:
        # メニューから呼び出されたことを示すフラグを設定
        if hasattr(ctx, "obj") and ctx.obj:
            ctx.obj["from_menu"] = True

        # コマンド関数を直接呼び出し
        if command_func.callback is None:
            return False

        result = command_func.callback(*args, **kwargs)

        # CI失敗の場合でも成功として扱う(ExecutionResultが返された場合)
        if result is not None and getattr(result, "success", True) is False:
            console.print("[green]✓[/green] CI実行が完了しました(失敗ログを収集)")
            return True

        return result if result is not None else True

    except SystemExit as e:
        # CI失敗による終了コード1は正常な結果として扱う
        if e.code == 1:
            console.print("[green]✓[/green] CI実行が完了しました(失敗ログを収集)")
            return True

        console.print(f"[red]コマンドが終了コード {e.code} で終了しました[/red]")
        return False
    except Exception as e:
        console.print(f"[red]コマンド実行エラー: {e}[/red]")
        if ctx.obj.get("verbose", False):
            traceback.print_exc()
        return False


def _test_workflow_handler(ctx: click.Context, workflow: str) -> object:
    """Test specific workflow handler."""
    return _invoke_command(
        ctx,
        test,
        workflow=(workflow,),
        verbose=False,
        output_format="markdown",
        dry_run=False,
        log_file=None,
        diff=False,
        save=True,
        sanitize=True,
    )


def _test_job_handler(ctx: click.Context, job: str) -> bool:
    """Test specific job handler."""
    console = ctx.obj["console"]
    console.print(f"[yellow]ジョブ '{job}' の実行は現在開発中です[/yellow]")
    console.print("[dim]代わりに全ワークフローまたは特定ワークフローを実行してください[/dim]")
    return True


def _analyze_interactive_handler(ctx: click.Context) -> object:
    """Interactive AI analysis handler."""
    console = ctx.obj["console"]
    try:
        from .commands.analyze import analyze

        return _invoke_command(
            ctx,
            analyze,
            log_file=None,
            provider=None,
            model=None,
            custom_prompt=None,
            fix=False,
            interactive=True,
            streaming=None,
            cache=True,
            stats=False,
            output_format="markdown",
            verbose=False,
            retry_operation_id=None,
        )
    except (ImportError, NameError):
        console.print("[red]AI分析機能は利用できません。[/red]")
        return False


def _analyze_file_handler(ctx: click.Context, log_file: str) -> object:
    """Specific file analysis handler."""
    console = ctx.obj["console"]
    try:
        from .commands.analyze import analyze

        return _invoke_command(
            ctx,
            analyze,
            log_file=Path(log_file),
            provider=None,
            model=None,
            custom_prompt=None,
            fix=False,
            interactive=False,
            streaming=None,
            cache=True,
            stats=False,
            output_format="markdown",
            verbose=False,
            retry_operation_id=None,
        )
    except NameError:
        console.print("[red]AI分析機能は利用できません。[/red]")
        return False


def _cache_pull_handler(ctx: click.Context, images: tuple[str, ...] | None = None, timeout: int = 3600) -> object:
    """Cache pull handler."""
    if images:
        return _invoke_command(ctx, cache, pull=True, image=images, timeout=timeout)
    return _invoke_command(ctx, cache, pull=True, timeout=timeout)


def _create_command_handlers(ctx: click.Context) -> dict[str, Callable[..., object]]:
    """Create command handlers.

    Args:
        ctx: Click context.

    Returns:
        Mapping of command names to handler functions.

    """
    console = ctx.obj["console"]
    handlers: dict[str, Callable[..., Any]] = {}

    handlers["init"] = lambda: _invoke_command(ctx, init, force=False, interactive=False)
    handlers["init_interactive"] = lambda: _invoke_command(ctx, init, force=False, interactive=True)
    handlers["setup"] = lambda: _invoke_command(ctx, setup, force=False)
    handlers["doctor"] = lambda: _invoke_command(ctx, doctor, verbose=False, guide=None)

    handlers["test"] = lambda: _invoke_command(
        ctx,
        test,
        workflow=(),
        verbose=False,
        output_format="markdown",
        dry_run=False,
        log_file=None,
        diff=False,
        save=True,
        sanitize=True,
    )

    handlers["logs"] = lambda: _invoke_command(ctx, logs)
    handlers["secrets"] = lambda: _invoke_command(ctx, secrets)
    handlers["cache"] = lambda: _invoke_command(ctx, cache)
    handlers["clean"] = lambda: _invoke_command(ctx, clean)

    # analyze command
    try:
        from .commands.analyze import analyze

        handlers["analyze"] = lambda: _invoke_command(
            ctx,
            analyze,
            log_file=None,
            provider=None,
            model=None,
            custom_prompt=None,
            fix=False,
            interactive=False,
            streaming=None,
            cache=True,
            stats=False,
            output_format="markdown",
            verbose=False,
            retry_operation_id=None,
        )
    except (ImportError, NameError):

        def analyze_unavailable() -> bool:
            console.print("[red]AI分析機能は利用できません。必要な依存関係を確認してください。[/red]")
            return False

        handlers["analyze"] = analyze_unavailable

    def test_workflow_wrapper(workflow: str) -> object:
        return _test_workflow_handler(ctx, workflow)

    handlers["test_workflow"] = test_workflow_wrapper

    def test_job_wrapper(job: str) -> bool:
        return _test_job_handler(ctx, job)

    handlers["test_job"] = test_job_wrapper

    def analyze_interactive_wrapper() -> object:
        return _analyze_interactive_handler(ctx)

    handlers["analyze_interactive"] = analyze_interactive_wrapper

    def analyze_file_wrapper(log_file: str) -> object:
        return _analyze_file_handler(ctx, log_file)

    handlers["analyze_file"] = analyze_file_wrapper

    handlers["logs_latest"] = lambda: _invoke_command(ctx, logs, latest=True)

    def logs_compare_wrapper(log1: str, log2: str) -> object:
        return _invoke_command(ctx, logs, compare=[log1, log2])

    handlers["logs_compare"] = logs_compare_wrapper

    handlers["secrets_list"] = lambda: _invoke_command(ctx, secrets, list_secrets=True)

    def cache_pull_wrapper(images: tuple[str, ...] | None = None, timeout: int = 3600) -> object:
        return _cache_pull_handler(ctx, images, timeout)

    handlers["cache_pull"] = cache_pull_wrapper

    handlers["cache_clear"] = lambda: _invoke_command(ctx, cache, clear=True)

    handlers["format_logs"] = format_logs_handler
    handlers["format_logs_custom"] = format_logs_custom_handler

    return handlers


def main() -> None:
    """Run the CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        console.print("\n[yellow]操作がキャンセルされました。[/yellow]")
        sys.exit(130)
    except CIHelperError as e:
        ErrorHandler.handle_error(e, verbose=False)  # メインレベルでは詳細表示しない
        sys.exit(1)
    except Exception as e:
        ErrorHandler.handle_error(e, verbose=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
