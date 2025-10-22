"""
cache コマンド実装

Dockerイメージの事前プルとキャッシュ管理を行います。
"""

import subprocess

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..core.exceptions import CIHelperError

console = Console()

# よく使用されるDockerイメージ
DEFAULT_IMAGES = [
    "ghcr.io/catthehacker/ubuntu:act-latest",
    "ghcr.io/catthehacker/ubuntu:act-22.04",
    "ghcr.io/catthehacker/ubuntu:act-20.04",
    "ghcr.io/catthehacker/ubuntu:full-latest",
    "ghcr.io/catthehacker/ubuntu:full-22.04",
    "ghcr.io/catthehacker/ubuntu:full-20.04",
]


@click.command()
@click.option(
    "--pull",
    is_flag=True,
    help="Dockerイメージを事前にプルしてキャッシュします",
)
@click.option(
    "--list",
    "list_images",
    is_flag=True,
    help="キャッシュされているDockerイメージを一覧表示します",
)
@click.option(
    "--clean",
    is_flag=True,
    help="未使用のDockerイメージを削除します",
)
@click.option(
    "--image",
    multiple=True,
    help="特定のイメージを指定します（複数指定可能）",
)
@click.option(
    "--timeout",
    default=1800,
    help="プルのタイムアウト時間（秒）デフォルト: 1800秒（30分）",
)
@click.pass_context
def cache(ctx: click.Context, pull: bool, list_images: bool, clean: bool, image: tuple[str, ...], timeout: int) -> None:
    """Dockerイメージのキャッシュ管理

    act で使用するDockerイメージを事前にプルしてキャッシュすることで、
    CI実行時の待機時間を短縮します。

    \b
    使用例:
      ci-run cache --pull                         # デフォルトイメージをプル
      ci-run cache --pull --timeout 3600          # 60分タイムアウトでプル
      ci-run cache --pull --image custom:tag      # 特定のイメージをプル
      ci-run cache --list                         # キャッシュ済みイメージを表示
      ci-run cache --clean                        # 未使用イメージを削除
    """
    try:
        if not _check_docker_available():
            console.print("[red]✗[/red] Docker が利用できません")
            console.print("Docker デーモンが起動していることを確認してください")
            ctx.exit(1)

        if pull:
            _pull_images(image if image else DEFAULT_IMAGES, timeout=timeout)
        elif list_images:
            _list_cached_images()
        elif clean:
            _clean_unused_images()
        else:
            # デフォルトでキャッシュ状況を表示
            _show_cache_status()

    except CIHelperError as e:
        console.print(f"[red]✗[/red] {e}")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] 予期しないエラーが発生しました: {e}")
        ctx.exit(1)


def _check_docker_available() -> bool:
    """Dockerが利用可能かチェック"""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def _pull_images(images: tuple[str, ...] | list[str], timeout: int = 1800) -> None:
    """Dockerイメージをプル"""
    console.print("[bold blue]🐳 Dockerイメージをプル中...[/bold blue]")
    console.print(f"[dim]タイムアウト: {timeout // 60}分 | 対象イメージ: {len(images)}個[/dim]\n")

    success_count = 0
    failed_images = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for i, image in enumerate(images, 1):
            task = progress.add_task(f"[{i}/{len(images)}] プル中: {image}", total=None)

            try:
                result = subprocess.run(
                    ["docker", "pull", image],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    progress.update(task, description=f"[green]✓[/green] [{i}/{len(images)}] 完了: {image}")
                    success_count += 1
                else:
                    progress.update(task, description=f"[red]✗[/red] [{i}/{len(images)}] 失敗: {image}")
                    failed_images.append(image)

            except subprocess.TimeoutExpired:
                progress.update(
                    task, description=f"[red]✗[/red] [{i}/{len(images)}] タイムアウト ({timeout // 60}分): {image}"
                )
                failed_images.append(image)
            except Exception:
                progress.update(task, description=f"[red]✗[/red] [{i}/{len(images)}] エラー: {image}")
                failed_images.append(image)

    # 結果サマリー
    console.print(f"\n[green]🎉 {success_count} 個のイメージをプルしました[/green]")

    if failed_images:
        console.print(f"[yellow]⚠[/yellow] {len(failed_images)} 個のイメージでエラーが発生:")
        for image in failed_images:
            console.print(f"  - {image}")


def _list_cached_images() -> None:
    """キャッシュされているDockerイメージを一覧表示"""
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            console.print("[bold blue]📦 キャッシュされているDockerイメージ[/bold blue]\n")
            console.print(result.stdout)
        else:
            console.print("[red]✗[/red] イメージ一覧の取得に失敗しました")

    except Exception as e:
        console.print(f"[red]✗[/red] エラーが発生しました: {e}")


def _clean_unused_images() -> None:
    """未使用のDockerイメージを削除"""
    console.print("[bold yellow]🧹 未使用のDockerイメージを削除中...[/bold yellow]\n")

    try:
        # 未使用イメージを削除
        result = subprocess.run(["docker", "image", "prune", "-f"], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            console.print("[green]✓[/green] 未使用イメージの削除が完了しました")
            if result.stdout.strip():
                console.print(result.stdout)
        else:
            console.print("[red]✗[/red] イメージの削除に失敗しました")
            console.print(result.stderr)

    except Exception as e:
        console.print(f"[red]✗[/red] エラーが発生しました: {e}")


def _show_cache_status() -> None:
    """キャッシュ状況を表示"""
    console.print("[bold blue]📊 Dockerイメージキャッシュ状況[/bold blue]\n")

    try:
        # 全イメージの情報を取得
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            console.print("[red]✗[/red] イメージ情報の取得に失敗しました")
            return

        # act関連のイメージをフィルタ
        act_images = []
        other_images = []

        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    image_name = parts[0]
                    size = parts[1]

                    if "catthehacker" in image_name or "act" in image_name:
                        act_images.append((image_name, size))
                    else:
                        other_images.append((image_name, size))

        # テーブル表示
        if act_images:
            table = Table(title="Act関連イメージ")
            table.add_column("イメージ", style="cyan")
            table.add_column("サイズ", style="green")

            for image_name, size in act_images:
                table.add_row(image_name, size)

            console.print(table)
        else:
            console.print("[yellow]⚠[/yellow] Act関連のイメージがキャッシュされていません")
            console.print("  [dim]ci-run cache --pull でイメージをプルしてください[/dim]")

        # 推奨アクション
        console.print("\n[bold]推奨アクション:[/bold]")
        if not act_images:
            console.print("• [cyan]ci-run cache --pull[/cyan] - デフォルトイメージをプル")
        console.print("• [cyan]ci-run cache --list[/cyan] - 全イメージを表示")
        console.print("• [cyan]ci-run cache --clean[/cyan] - 未使用イメージを削除")

    except Exception as e:
        console.print(f"[red]✗[/red] エラーが発生しました: {e}")
