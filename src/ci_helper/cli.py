"""
ci-helper CLIエントリーポイント

Clickを使用したマルチコマンドCLIインターフェースを提供します。
"""

from __future__ import annotations

import sys
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
    try:
        console = ctx.obj["console"]

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


def _create_command_handlers(ctx: click.Context) -> dict[str, Any]:
    """コマンドハンドラーを作成

    Args:
        ctx: Click コンテキスト

    Returns:
        コマンド名とハンドラー関数のマッピング
    """
    console = ctx.obj["console"]

    def invoke_command(command_func, *args, **kwargs):
        """コマンド関数を安全に呼び出す"""
        try:
            # メニューから呼び出されたことを示すフラグを設定
            if hasattr(ctx, "obj") and ctx.obj:
                ctx.obj["from_menu"] = True

            # コマンド関数を直接呼び出し
            result = command_func.callback(*args, **kwargs)

            # CI失敗の場合でも成功として扱う（ExecutionResultが返された場合）
            if hasattr(result, "success") and not result.success:
                console.print("[green]✓[/green] CI実行が完了しました（失敗ログを収集）")
                return True

            return result if result is not None else True

        except SystemExit as e:
            # CI失敗による終了コード1は正常な結果として扱う
            if e.code == 1:
                console.print("[green]✓[/green] CI実行が完了しました（失敗ログを収集）")
                return True
            else:
                console.print(f"[red]コマンドが終了コード {e.code} で終了しました[/red]")
                return False
        except Exception as e:
            console.print(f"[red]コマンド実行エラー: {e}[/red]")
            import traceback

            if ctx.obj.get("verbose", False):
                traceback.print_exc()
            return False

    # 基本コマンドハンドラー
    handlers = {}

    # init コマンド
    def init_handler():
        return invoke_command(init, force=False, interactive=False)

    handlers["init"] = init_handler

    # 対話的 init コマンド
    def init_interactive_handler():
        return invoke_command(init, force=False, interactive=True)

    handlers["init_interactive"] = init_interactive_handler

    # setup コマンド
    def setup_handler():
        return invoke_command(setup, force=False)

    handlers["setup"] = setup_handler

    # doctor コマンド
    def doctor_handler():
        return invoke_command(doctor, verbose=False, guide=None)

    handlers["doctor"] = doctor_handler

    # test コマンド
    def test_handler():
        return invoke_command(
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

    handlers["test"] = test_handler

    # logs コマンド
    def logs_handler():
        return invoke_command(logs)

    handlers["logs"] = logs_handler

    # secrets コマンド
    def secrets_handler():
        return invoke_command(secrets)

    handlers["secrets"] = secrets_handler

    # cache コマンド
    def cache_handler():
        return invoke_command(cache)

    handlers["cache"] = cache_handler

    # clean コマンド
    def clean_handler():
        return invoke_command(clean)

    handlers["clean"] = clean_handler

    # analyze コマンド（AI統合が利用可能な場合のみ）
    try:

        def analyze_handler():
            return invoke_command(
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

        handlers["analyze"] = analyze_handler
    except NameError:
        # AI統合が利用できない場合
        def analyze_unavailable():
            console.print("[red]AI分析機能は利用できません。必要な依存関係を確認してください。[/red]")
            return False

        handlers["analyze"] = analyze_unavailable

    # 拡張コマンドハンドラー（パラメータ付き）
    def test_workflow_handler(workflow: str):
        """特定ワークフローテストハンドラー"""
        return invoke_command(
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

    handlers["test_workflow"] = test_workflow_handler

    def test_job_handler(job: str):
        """特定ジョブテストハンドラー"""
        # ジョブ指定の場合は、testコマンドに適切なオプションを渡す
        # 実際の実装では、testコマンドがjobオプションをサポートする必要がある
        console.print(f"[yellow]ジョブ '{job}' の実行は現在開発中です[/yellow]")
        console.print("[dim]代わりに全ワークフローまたは特定ワークフローを実行してください[/dim]")
        return True

    handlers["test_job"] = test_job_handler

    def analyze_interactive_handler():
        """対話的AI分析ハンドラー"""
        try:
            return invoke_command(
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
        except NameError:
            console.print("[red]AI分析機能は利用できません。[/red]")
            return False

    handlers["analyze_interactive"] = analyze_interactive_handler

    def analyze_file_handler(log_file: str):
        """特定ファイル分析ハンドラー"""
        try:
            from pathlib import Path

            return invoke_command(
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

    handlers["analyze_file"] = analyze_file_handler

    def logs_latest_handler():
        """最新ログ表示ハンドラー"""
        return invoke_command(logs, latest=True)

    handlers["logs_latest"] = logs_latest_handler

    def logs_compare_handler(log1: str, log2: str):
        """ログ比較ハンドラー"""
        return invoke_command(logs, compare=[log1, log2])

    handlers["logs_compare"] = logs_compare_handler

    def secrets_list_handler():
        """シークレット一覧ハンドラー"""
        return invoke_command(secrets, list_secrets=True)

    handlers["secrets_list"] = secrets_list_handler

    def cache_pull_handler(images=None, timeout=3600):
        """キャッシュプルハンドラー"""
        if images:
            # 特定のイメージとタイムアウトを指定
            return invoke_command(cache, pull=True, image=images, timeout=timeout)
        else:
            # デフォルト設定でプル
            return invoke_command(cache, pull=True, timeout=timeout)

    handlers["cache_pull"] = cache_pull_handler

    def cache_clear_handler():
        """キャッシュクリアハンドラー"""
        return invoke_command(cache, clear=True)

    handlers["cache_clear"] = cache_clear_handler

    # format_logs コマンドハンドラー（メニューシステム用）
    handlers["format_logs"] = format_logs_handler
    handlers["format_logs_custom"] = format_logs_custom_handler

    return handlers


def main() -> None:
    """メインエントリーポイント

    例外処理とエラーハンドリングを含む安全なCLI実行を提供します。
    """
    try:
        cli(obj={})
    except KeyboardInterrupt:
        console.print("\n[yellow]操作がキャンセルされました。[/yellow]")
        sys.exit(130)
    except CIHelperError as e:
        ErrorHandler.handle_error(e, False)  # メインレベルでは詳細表示しない
        sys.exit(1)
    except Exception as e:
        ErrorHandler.handle_error(e, False)
        sys.exit(1)


if __name__ == "__main__":
    main()
