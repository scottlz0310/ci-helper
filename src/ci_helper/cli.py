"""
ci-helper CLIエントリーポイント

Clickを使用したマルチコマンドCLIインターフェースを提供します。
"""


import click

from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ci-run")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """ci-helper: ローカルCI検証とAI連携ツール
    
    actを使用してGitHub Actionsワークフローをローカルで実行し、
    失敗を分析してAI対応の出力を生成します。
    """
    # コンテキストオブジェクトの初期化
    ctx.ensure_object(dict)

    # グローバル設定の初期化（後で実装）
    ctx.obj['config'] = {}


# サブコマンドのインポートと登録（後で実装）
# from .commands import init, doctor, test, logs, clean


if __name__ == "__main__":
    cli()
