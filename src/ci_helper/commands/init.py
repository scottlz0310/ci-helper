"""
init コマンド実装

設定ファイルテンプレートを生成します。
"""

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from ..config.templates import (
    ACTRC_TEMPLATE,
    CI_HELPER_TOML_TEMPLATE,
    ENV_EXAMPLE_TEMPLATE,
    GITIGNORE_ADDITIONS,
)
from ..core.exceptions import ConfigurationError

console = Console()


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="既存ファイルを上書きします",
)
def init(force: bool) -> None:
    """設定ファイルテンプレートを生成します

    このコマンドは以下のファイルを生成します:
    - .actrc.example: act用の設定テンプレート
    - ci-helper.toml.example: ci-helper設定テンプレート
    - .env.example: 環境変数設定テンプレート
    """
    try:
        project_root = Path.cwd()

        # 生成するファイルの定義
        template_files = [
            (".actrc.example", ACTRC_TEMPLATE),
            ("ci-helper.toml.example", CI_HELPER_TOML_TEMPLATE),
            (".env.example", ENV_EXAMPLE_TEMPLATE),
        ]

        # 既存ファイルのチェック
        existing_files = []
        for filename, _ in template_files:
            file_path = project_root / filename
            if file_path.exists():
                existing_files.append(filename)

        # 既存ファイルがある場合の確認
        if existing_files and not force:
            console.print("[yellow]以下のファイルが既に存在します:[/yellow]")
            for filename in existing_files:
                console.print(f"  - {filename}")

            if not Confirm.ask("上書きしますか？"):
                console.print("[yellow]初期化をキャンセルしました。[/yellow]")
                return

        # テンプレートファイルの生成
        created_files = []
        for filename, template_content in template_files:
            file_path = project_root / filename

            try:
                file_path.write_text(template_content, encoding="utf-8")
                created_files.append(filename)
                console.print(f"[green]✓[/green] {filename} を作成しました")
            except OSError as e:
                console.print(f"[red]✗[/red] {filename} の作成に失敗しました: {e}")
                raise ConfigurationError(
                    f"テンプレートファイル {filename} の作成に失敗しました",
                    "ディレクトリの書き込み権限を確認してください",
                ) from e

        # .gitignore への追加提案
        _handle_gitignore_update(project_root)

        # 成功メッセージと次のステップ
        console.print("\n[green]🎉 初期化が完了しました！[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("1. .actrc.example を .actrc にコピーして必要に応じて編集")
        console.print("2. ci-helper.toml.example を ci-helper.toml にコピーして設定を調整")
        console.print("3. .env.example を .env にコピーして環境変数を設定")
        console.print("4. [cyan]ci-run doctor[/cyan] で環境をチェック")

    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            "初期化処理中にエラーが発生しました", "プロジェクトディレクトリの権限を確認してください"
        ) from e


def _handle_gitignore_update(project_root: Path) -> None:
    """gitignore ファイルの更新処理"""
    gitignore_path = project_root / ".gitignore"

    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        if ".ci-helper/" not in gitignore_content:
            console.print("\n[yellow]推奨:[/yellow] .gitignore に以下を追加することをお勧めします:")
            console.print(GITIGNORE_ADDITIONS)

            if Confirm.ask(".gitignore に自動追加しますか？"):
                try:
                    with gitignore_path.open("a", encoding="utf-8") as f:
                        f.write(GITIGNORE_ADDITIONS)
                    console.print("[green]✓[/green] .gitignore を更新しました")
                except OSError as e:
                    console.print(f"[red]✗[/red] .gitignore の更新に失敗しました: {e}")
    else:
        console.print("\n[yellow]推奨:[/yellow] .gitignore ファイルを作成することをお勧めします")
        if Confirm.ask(".gitignore を作成しますか？"):
            try:
                gitignore_path.write_text(GITIGNORE_ADDITIONS, encoding="utf-8")
                console.print("[green]✓[/green] .gitignore を作成しました")
            except OSError as e:
                console.print(f"[red]✗[/red] .gitignore の作成に失敗しました: {e}")


def _copy_template_to_actual(template_path: Path, actual_path: Path, force: bool = False) -> bool:
    """テンプレートファイルを実際の設定ファイルにコピー

    Args:
        template_path: テンプレートファイルのパス
        actual_path: 実際の設定ファイルのパス
        force: 既存ファイルを強制上書きするか

    Returns:
        コピーが成功したかどうか
    """
    if actual_path.exists() and not force:
        return False

    try:
        template_content = template_path.read_text(encoding="utf-8")
        actual_path.write_text(template_content, encoding="utf-8")
        return True
    except OSError:
        return False


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="既存ファイルを上書きします",
)
def setup(force: bool) -> None:
    """テンプレートから実際の設定ファイルを作成します

    .example ファイルから実際の設定ファイルを作成します。
    """
    project_root = Path.cwd()

    # コピーするファイルの定義
    copy_files = [
        (".actrc.example", ".actrc"),
        ("ci-helper.toml.example", "ci-helper.toml"),
        (".env.example", ".env"),
    ]

    copied_files = []
    skipped_files = []

    for template_name, actual_name in copy_files:
        template_path = project_root / template_name
        actual_path = project_root / actual_name

        if not template_path.exists():
            console.print(
                f"[yellow]⚠[/yellow] {template_name} が見つかりません。"
                "先に [cyan]ci-run init[/cyan] を実行してください。"
            )
            continue

        if _copy_template_to_actual(template_path, actual_path, force):
            copied_files.append(actual_name)
            console.print(f"[green]✓[/green] {actual_name} を作成しました")
        else:
            skipped_files.append(actual_name)
            console.print(f"[yellow]⚠[/yellow] {actual_name} は既に存在します（--force で上書き可能）")

    if copied_files:
        console.print(f"\n[green]🎉 {len(copied_files)} 個のファイルを作成しました！[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("1. 作成された設定ファイルを必要に応じて編集")
        console.print("2. [cyan]ci-run doctor[/cyan] で環境をチェック")

    if skipped_files:
        console.print(f"\n[yellow]{len(skipped_files)} 個のファイルをスキップしました。[/yellow]")
