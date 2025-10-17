"""
secrets コマンド実装

シークレット管理と検証を行います。
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from ..core.security import EnvironmentSecretManager
from ..utils.config import Config

console = Console()


@click.command()
@click.option(
    "--validate",
    is_flag=True,
    help="設定ファイルのセキュリティを検証します",
)
@click.option(
    "--status",
    is_flag=True,
    help="現在のシークレット設定状況を表示します",
)
@click.option(
    "--guide",
    is_flag=True,
    help="シークレット管理のガイドを表示します",
)
@click.pass_context
def secrets(ctx: click.Context, validate: bool, status: bool, guide: bool) -> None:
    """シークレット管理と検証を行います

    環境変数の設定状況確認、設定ファイルのセキュリティ検証、
    シークレット管理のベストプラクティスガイドを提供します。
    """
    config = ctx.obj["config"]

    if guide:
        _display_security_guide()
        return

    if validate:
        _validate_config_security(config)
        return

    if status:
        _display_secret_status()
        return

    # デフォルトは状況表示
    _display_secret_status()


def _display_secret_status() -> None:
    """現在のシークレット設定状況を表示"""
    console.print("[bold blue]🔐 シークレット設定状況[/bold blue]\n")

    secret_manager = EnvironmentSecretManager()
    summary = secret_manager.get_secret_summary()

    # 必須シークレットの表
    required_table = Table(title="必須シークレット")
    required_table.add_column("環境変数名", style="bold")
    required_table.add_column("説明")
    required_table.add_column("状態", justify="center")

    for key, info in summary["required_secrets"].items():
        status = "[green]✅ 設定済み[/green]" if info["configured"] else "[red]❌ 未設定[/red]"
        required_table.add_row(key, info["description"], status)

    console.print(required_table)
    console.print()
    # オプションシークレットの表
    optional_table = Table(title="オプション設定")
    optional_table.add_column("環境変数名", style="bold")
    optional_table.add_column("説明")
    optional_table.add_column("状態", justify="center")

    for key, info in summary["optional_secrets"].items():
        status = "[green]✅ 設定済み[/green]" if info["configured"] else "[yellow]⚪ 未設定[/yellow]"
        optional_table.add_row(key, info["description"], status)

    console.print(optional_table)

    # サマリー
    total_configured = summary["total_configured"]
    total_missing = summary["total_missing"]

    console.print("\n[bold]サマリー:[/bold]")
    console.print(f"• 設定済み: {total_configured}件")
    console.print(f"• 未設定: {total_missing}件")

    if total_missing > 0:
        console.print("\n[yellow]💡 AI機能を使用する場合は、必要な環境変数を設定してください[/yellow]")


def _validate_config_security(config: Config) -> None:
    """設定ファイルのセキュリティを検証"""
    console.print("[bold blue]🔍 設定ファイルのセキュリティ検証[/bold blue]\n")

    try:
        validation_result = config.validate_all_config_files()

        if validation_result["overall_valid"]:
            console.print("[green]✅ セキュリティ検証に合格しました[/green]")
            console.print("[green]設定ファイルにセキュリティ問題は検出されませんでした[/green]")
        else:
            critical_issues = validation_result.get("critical_issues", 0)
            warning_issues = validation_result.get("warning_issues", 0)

            if critical_issues > 0:
                console.print(f"[red]❌ {critical_issues}件の重大なセキュリティ問題が検出されました[/red]")

            if warning_issues > 0:
                console.print(f"[yellow]⚠️  {warning_issues}件の警告が検出されました[/yellow]")

            # ファイル別の結果を表示
            file_results = validation_result.get("file_results", {})
            if file_results:
                console.print("\n[bold]ファイル別結果:[/bold]")
                for file_path, result in file_results.items():
                    status = "[green]✅[/green]" if result["valid"] else "[red]❌[/red]"
                    console.print(f"{status} {file_path}")

                    if not result["valid"] and "issues" in result:
                        for issue in result["issues"]:
                            severity_color = "red" if issue["severity"] == "critical" else "yellow"
                            console.print(f"  [{severity_color}]• {issue['message']}[/{severity_color}]")

            # 推奨事項を表示
            recommendations = validation_result.get("recommendations", [])
            if recommendations:
                console.print("\n[bold yellow]🔧 推奨事項:[/bold yellow]")
                for rec in recommendations:
                    console.print(f"  {rec}")

    except Exception as e:
        console.print(f"[red]❌ セキュリティ検証中にエラーが発生しました: {e}[/red]")


def _display_security_guide() -> None:
    """シークレット管理のガイドを表示"""
    console.print("[bold blue]🛡️  シークレット管理ガイド[/bold blue]\n")

    console.print("[bold]1. 環境変数の設定方法[/bold]")
    console.print("```bash")
    console.print("# 一時的な設定")
    console.print("export OPENAI_API_KEY=your_api_key")
    console.print("export GITHUB_TOKEN=your_token")
    console.print("")
    console.print("# 永続的な設定 (~/.bashrc または ~/.zshrc に追加)")
    console.print("echo 'export OPENAI_API_KEY=your_api_key' >> ~/.bashrc")
    console.print("```")
    console.print()

    console.print("[bold]2. .env ファイルの使用[/bold]")
    console.print("```bash")
    console.print("# .env ファイルを作成")
    console.print("echo 'OPENAI_API_KEY=your_api_key' >> .env")
    console.print("echo 'GITHUB_TOKEN=your_token' >> .env")
    console.print("")
    console.print("# .gitignore に追加（重要！）")
    console.print("echo '.env' >> .gitignore")
    console.print("```")
    console.print()

    console.print("[bold]3. 設定ファイルでの安全な参照[/bold]")
    console.print("```toml")
    console.print("# ci-helper.toml")
    console.print("[ci-helper]")
    console.print("# ✅ 良い例: 環境変数参照")
    console.print("api_key = '${OPENAI_API_KEY}'")
    console.print("")
    console.print("# ❌ 悪い例: 直接記載")
    console.print("# api_key = 'sk-1234567890abcdef'")
    console.print("```")
    console.print()

    console.print("[bold]4. セキュリティのベストプラクティス[/bold]")
    console.print("• シークレットは設定ファイルに直接記載しない")
    console.print("• .env ファイルは必ず .gitignore に追加する")
    console.print("• 環境変数名は大文字とアンダースコアを使用する")
    console.print("• 不要になったシークレットは無効化する")
    console.print("• 定期的にシークレットをローテーションする")
    console.print()

    console.print("[bold]5. トラブルシューティング[/bold]")
    console.print("• [cyan]ci-run secrets --validate[/cyan] で設定ファイルを検証")
    console.print("• [cyan]ci-run secrets --status[/cyan] で環境変数の設定状況を確認")
    console.print("• [cyan]ci-run doctor[/cyan] で全体的な環境をチェック")
