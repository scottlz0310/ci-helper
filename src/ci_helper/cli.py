"""
ci-helper CLIエントリーポイント

Clickを使用したマルチコマンドCLIインターフェースを提供します。
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__

# サブコマンドのインポート
from .commands.cache import cache
from .commands.clean import clean
from .commands.doctor import doctor
from .commands.init import init, setup
from .commands.logs import logs
from .commands.secrets import secrets
from .commands.test import test
from .core.error_handler import ErrorHandler
from .core.exceptions import CIHelperError
from .utils.config import Config

console = Console()


@click.group()
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
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_file: Path | None) -> None:
    """ci-helper: ローカルCI検証とAI連携ツール

    actを使用してGitHub Actionsワークフローをローカルで実行し、
    失敗を分析してAI対応の出力を生成します。

    \b
    主要コマンド:
      init     設定ファイルテンプレートを生成
      doctor   環境依存関係をチェック
      test     CI/CDワークフローをローカルで実行
      analyze  AI分析でCI失敗の根本原因を特定
      logs     実行ログを管理・表示
      secrets  シークレット管理と検証
      clean    キャッシュとログをクリーンアップ
      cache    Dockerイメージのキャッシュ管理

    \b
    使用例:
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
cli.add_command(secrets)
cli.add_command(clean)
cli.add_command(cache)

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
