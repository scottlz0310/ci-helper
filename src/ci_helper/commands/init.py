"""
init コマンド実装

設定ファイルテンプレートを生成します。
"""

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from ..config.templates import ACTRC_TEMPLATE, CI_HELPER_TOML_TEMPLATE, ENV_EXAMPLE_TEMPLATE, GITIGNORE_ADDITIONS
from ..core.exceptions import ConfigurationError

console = Console()


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="既存の設定ファイルを強制的に上書きします",
)
def init(force: bool) -> None:
    """プロジェクトの初期化

    ci-helper の設定ファイルを作成し、プロジェクトを初期化します。
    環境に依存しない汎用的な設定を生成します。

    \b
    生成されるファイル:
    - .actrc: act の設定ファイル（Git除外）
    - ci-helper.toml: ci-helper の設定ファイル（Git除外）
    - .env: 環境変数ファイル（Git除外）
    - .actrc.example, ci-helper.toml.example, .env.example: 参考用テンプレート（Git管理）

    \b
    注意:
    実際の設定ファイルは環境固有のため Git 除外されます。
    .example ファイルをチーム共有の参考として使用してください。
    """
    try:
        project_root = Path.cwd()

        console.print("[bold blue]🚀 プロジェクトを初期化しています...[/bold blue]\n")

        # 実際の設定ファイルの定義
        config_files = [
            (".actrc", "act の設定ファイル"),
            ("ci-helper.toml", "ci-helper の設定ファイル"),
            (".env", "環境変数ファイル"),
        ]

        # 既存の設定ファイルをチェック
        existing_config_files = []
        for filename, _ in config_files:
            file_path = project_root / filename
            if file_path.exists():
                existing_config_files.append(filename)

        # 既存の設定ファイルがある場合の確認
        if existing_config_files and not force:
            console.print("[yellow]以下の設定ファイルが既に存在します:[/yellow]")
            for filename in existing_config_files:
                console.print(f"  - {filename}")

            if not Confirm.ask("上書きしますか？"):
                console.print("[yellow]初期化をキャンセルしました。[/yellow]")
                return

        # テンプレートファイルを常に作成/更新（参考用）
        _create_template_files(project_root)

        # 実際の設定ファイルを作成
        _create_actual_config_files(project_root, force)

        # .gitignore への追加提案
        _handle_gitignore_update(project_root)

        # 環境変数の状況を表示
        _show_environment_status()

        # 成功メッセージと次のステップ
        console.print("\n[green]🎉 初期化が完了しました！[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("1. 必要に応じて設定ファイルを編集")
        console.print("2. [cyan]ci-run doctor[/cyan] で環境をチェック")

    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            "初期化処理中にエラーが発生しました", "プロジェクトディレクトリの権限を確認してください"
        ) from e


def _create_template_files(project_root: Path) -> None:
    """テンプレートファイルを作成（参考用）"""
    template_files = [
        (".actrc.example", ACTRC_TEMPLATE),
        ("ci-helper.toml.example", CI_HELPER_TOML_TEMPLATE),
        (".env.example", ENV_EXAMPLE_TEMPLATE),
    ]

    for filename, template_content in template_files:
        file_path = project_root / filename
        try:
            file_path.write_text(template_content, encoding="utf-8")
            console.print(f"[dim]✓ {filename} を更新しました[/dim]")
        except OSError as e:
            console.print(f"[red]✗[/red] {filename} の作成に失敗しました: {e}")


def _create_actual_config_files(project_root: Path, _force: bool) -> None:
    """実際の設定ファイルを作成"""
    import os
    import platform

    # システム情報を取得
    system_info = {
        "os": platform.system().lower(),
        "arch": platform.machine().lower(),
        "user": os.getenv("USER", "user"),
        "home": os.getenv("HOME", str(Path.home())),
    }

    # .actrc の作成（環境に応じた設定）
    actrc_content = _generate_actrc_content(system_info)
    _write_config_file(project_root / ".actrc", actrc_content, "act の設定ファイル")

    # ci-helper.toml の作成（プロジェクト固有の設定）
    toml_content = _generate_ci_helper_toml_content(project_root)
    _write_config_file(project_root / "ci-helper.toml", toml_content, "ci-helper の設定ファイル")

    # .env の作成（環境変数）
    env_content = _generate_env_content()
    _write_config_file(project_root / ".env", env_content, "環境変数ファイル")


def _generate_actrc_content(system_info: dict[str, str]) -> str:
    """汎用的な .actrc の内容を生成（環境固有の設定は避ける）"""
    # 汎用的なDockerイメージを使用（環境に依存しない）
    return """# act configuration file
# Generated by ci-helper

# Docker image to use for running actions (multi-arch compatible)
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-latest
-P ubuntu-22.04=ghcr.io/catthehacker/ubuntu:act-22.04
-P ubuntu-20.04=ghcr.io/catthehacker/ubuntu:act-20.04

# Bind the workspace to the container
--bind

# Use host network for better performance
--use-gitignore=false

# Verbose output
--verbose
"""


def _generate_ci_helper_toml_content(project_root: Path) -> str:
    """汎用的な ci-helper.toml の内容を生成（環境固有の設定は避ける）"""
    return """# ci-helper configuration file
# Generated by ci-helper

[ci-helper]
# Verbose output
verbose = false

# Log directory
log_dir = ".ci-helper/logs"

# Cache directory
cache_dir = ".ci-helper/cache"

# Reports directory
reports_dir = ".ci-helper/reports"

# Maximum log file size in MB
max_log_size_mb = 100

# Maximum cache size in MB
max_cache_size_mb = 500

# Timeout for CI operations in seconds (30 minutes)
timeout_seconds = 1800

# Save logs after execution
save_logs = true

# Context lines to show around failures
context_lines = 3

# Docker image for act
act_image = "ghcr.io/catthehacker/ubuntu:full-latest"
"""


def _generate_env_content() -> str:
    """環境変数ファイルの内容を生成"""
    import os

    # 既存の環境変数をチェック
    github_token_exists = any(key in os.environ for key in ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"])

    if github_token_exists:
        github_token_comment = "# GitHub token is already set in system environment variables"
    else:
        github_token_comment = "# GITHUB_TOKEN=your_github_token_here"

    return f"""# Environment variables for ci-helper
# Generated by ci-helper

# GitHub token for API access
{github_token_comment}

# Docker registry credentials (if needed)
# DOCKER_USERNAME=your_username
# DOCKER_PASSWORD=your_password

# Custom environment variables for your workflows
# Add your project-specific environment variables below

# Note: System environment variables take precedence over .env file
# Current GitHub token status: {"✓ Found in system" if github_token_exists else "✗ Not found"}
"""


def _show_environment_status() -> None:
    """環境変数の状況を表示"""
    import os

    console.print("\n[bold blue]📋 環境変数の状況[/bold blue]")

    # GitHub トークンの確認
    github_tokens = ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"]
    github_token_found = None

    for token_name in github_tokens:
        if token_name in os.environ:
            github_token_found = token_name
            break

    if github_token_found:
        console.print(f"[green]✓[/green] GitHub トークン: {github_token_found} が設定済み")
        console.print("  [dim].env ファイルの GitHub トークン設定は無視されます[/dim]")
    else:
        console.print("[yellow]⚠[/yellow] GitHub トークンが見つかりません")
        console.print("  [dim].env ファイルで設定するか、システム環境変数を設定してください[/dim]")

    # Docker 関連の確認
    docker_vars = ["DOCKER_USERNAME", "DOCKER_PASSWORD", "DOCKER_TOKEN"]
    docker_found = [var for var in docker_vars if var in os.environ]

    if docker_found:
        console.print(f"[green]✓[/green] Docker 認証情報: {', '.join(docker_found)} が設定済み")
    else:
        console.print("[dim]ℹ[/dim] Docker 認証情報は設定されていません（必要に応じて設定）")


def _write_config_file(file_path: Path, content: str, description: str) -> None:
    """設定ファイルを書き込み"""
    try:
        file_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] {file_path.name} を作成しました ({description})")
    except OSError as e:
        console.print(f"[red]✗[/red] {file_path.name} の作成に失敗しました: {e}")


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
