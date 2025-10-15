"""
doctor コマンド実装

環境依存関係をチェックします。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..core.exceptions import DependencyError

console = Console()


@click.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="詳細な診断情報を表示します",
)
@click.option(
    "--guide",
    type=click.Choice(["act", "docker", "workflows", "disk_space", "troubleshooting"]),
    help="特定の復旧ガイドを表示します",
)
@click.pass_context
def doctor(ctx: click.Context, verbose: bool, guide: str | None) -> None:
    """環境依存関係をチェックします

    ci-helperの実行に必要な依存関係とツールの状態を確認し、
    問題がある場合は解決方法を提案します。

    \b
    チェック項目:
    - act コマンドのインストール状態
    - Docker デーモンの実行状態
    - .github/workflows ディレクトリの存在
    - 設定ファイルの状態
    """
    # 特定のガイドが要求された場合は表示して終了
    if guide:
        RecoveryGuide.display_recovery_guide(guide)
        return

    config = ctx.obj["config"]
    global_verbose = ctx.obj.get("verbose", False)
    show_verbose = verbose or global_verbose

    console.print("[bold blue]🔍 環境診断を開始します...[/bold blue]\n")

    # 診断結果を格納
    checks = []
    all_passed = True

    # 1. act コマンドのチェック
    act_result = _check_act_command(show_verbose)
    checks.append(act_result)
    if not act_result["passed"]:
        all_passed = False

    # 2. Docker デーモンのチェック
    docker_result = _check_docker_daemon(show_verbose)
    checks.append(docker_result)
    if not docker_result["passed"]:
        all_passed = False

    # 3. GitHub Workflows ディレクトリのチェック
    workflows_result = _check_workflows_directory(show_verbose)
    checks.append(workflows_result)
    if not workflows_result["passed"]:
        all_passed = False

    # 4. 設定ファイルのチェック
    config_result = _check_configuration_files(config, show_verbose)
    checks.append(config_result)
    if not config_result["passed"]:
        all_passed = False

    # 5. 必要なディレクトリのチェック
    dirs_result = _check_required_directories(config, show_verbose)
    checks.append(dirs_result)
    if not dirs_result["passed"]:
        all_passed = False

    # 6. ディスク容量のチェック
    disk_result = _check_disk_space(show_verbose)
    checks.append(disk_result)
    if not disk_result["passed"]:
        all_passed = False

    # 7. セキュリティ設定のチェック
    security_result = _check_security_configuration(config, show_verbose)
    checks.append(security_result)
    if not security_result["passed"]:
        all_passed = False

    # 結果の表示
    _display_results(checks, show_verbose)

    # 総合結果
    if all_passed:
        console.print("\n[bold green]✅ すべてのチェックが成功しました！[/bold green]")
        console.print("[green]ci-helperを使用する準備が整いました。[/green]")
        console.print("\n[bold]次のステップ:[/bold]")
        console.print("• [cyan]ci-run test[/cyan] でワークフローを実行")
        console.print("• [cyan]ci-run test --help[/cyan] でオプションを確認")
    else:
        console.print("\n[bold red]❌ 一部のチェックが失敗しました[/bold red]")
        console.print("[yellow]上記の解決方法に従って問題を修正してください。[/yellow]")

        # 失敗した項目の詳細を収集
        failed_items = [check["name"] for check in checks if not check["passed"]]

        raise DependencyError(
            f"環境依存関係のチェックに失敗しました: {', '.join(failed_items)}",
            "doctor コマンドの出力を確認して問題を解決してください",
        )


def _check_act_command(verbose: bool) -> dict[str, any]:
    """act コマンドのインストール状態をチェック"""
    check_name = "act コマンド"

    try:
        # act コマンドの存在確認
        act_path = shutil.which("act")
        if not act_path:
            return {
                "name": check_name,
                "passed": False,
                "message": "act コマンドが見つかりません",
                "suggestion": _get_act_install_instructions(),
                "details": "act はローカルでGitHub Actionsを実行するために必要です",
            }

        # バージョン確認
        try:
            result = subprocess.run(
                ["act", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            version = result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            version = "不明"

        return {
            "name": check_name,
            "passed": True,
            "message": f"インストール済み ({version})",
            "suggestion": None,
            "details": f"パス: {act_path}" if verbose else None,
        }

    except Exception as e:
        return {
            "name": check_name,
            "passed": False,
            "message": f"チェック中にエラーが発生: {e}",
            "suggestion": _get_act_install_instructions(),
            "details": None,
        }


def _check_docker_daemon(verbose: bool) -> dict[str, any]:
    """Docker デーモンの実行状態をチェック"""
    check_name = "Docker デーモン"

    try:
        # Docker コマンドの存在確認
        docker_path = shutil.which("docker")
        if not docker_path:
            return {
                "name": check_name,
                "passed": False,
                "message": "Docker コマンドが見つかりません",
                "suggestion": "Docker Desktop をインストールしてください: https://www.docker.com/products/docker-desktop/",
                "details": "Docker は act がコンテナ内でワークフローを実行するために必要です",
            }

        # Docker デーモンの状態確認
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {
                "name": check_name,
                "passed": False,
                "message": "Docker デーモンが実行されていません",
                "suggestion": "Docker Desktop を起動してください",
                "details": result.stderr.strip() if verbose else None,
            }

        return {
            "name": check_name,
            "passed": True,
            "message": "実行中",
            "suggestion": None,
            "details": f"パス: {docker_path}" if verbose else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "name": check_name,
            "passed": False,
            "message": "Docker の応答がタイムアウトしました",
            "suggestion": "Docker Desktop を再起動してください",
            "details": None,
        }
    except Exception as e:
        return {
            "name": check_name,
            "passed": False,
            "message": f"チェック中にエラーが発生: {e}",
            "suggestion": "Docker Desktop のインストール状態を確認してください",
            "details": None,
        }


def _check_workflows_directory(verbose: bool) -> dict[str, any]:
    """GitHub Workflows ディレクトリの存在をチェック"""
    check_name = ".github/workflows ディレクトリ"

    workflows_dir = Path.cwd() / ".github" / "workflows"

    if not workflows_dir.exists():
        return {
            "name": check_name,
            "passed": False,
            "message": "ディレクトリが存在しません",
            "suggestion": "GitHub Actions ワークフローファイルを .github/workflows/ に配置してください",
            "details": f"期待されるパス: {workflows_dir}",
        }

    # ワークフローファイルの確認
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

    if not workflow_files:
        return {
            "name": check_name,
            "passed": False,
            "message": "ワークフローファイルが見つかりません",
            "suggestion": ".github/workflows/ ディレクトリに .yml または .yaml ファイルを配置してください",
            "details": f"ディレクトリは存在しますが、ワークフローファイルがありません: {workflows_dir}",
        }

    workflow_count = len(workflow_files)
    return {
        "name": check_name,
        "passed": True,
        "message": f"{workflow_count} 個のワークフローファイルを発見",
        "suggestion": None,
        "details": f"ファイル: {[f.name for f in workflow_files]}" if verbose else None,
    }


def _check_configuration_files(config, verbose: bool) -> dict[str, any]:
    """設定ファイルの状態をチェック"""
    check_name = "設定ファイル"

    project_root = config.project_root
    config_files = {
        "ci-helper.toml": project_root / "ci-helper.toml",
        ".actrc": project_root / ".actrc",
        ".env": project_root / ".env",
    }

    existing_files = []
    missing_files = []

    for name, path in config_files.items():
        if path.exists():
            existing_files.append(name)
        else:
            missing_files.append(name)

    if not existing_files:
        return {
            "name": check_name,
            "passed": False,
            "message": "設定ファイルが見つかりません",
            "suggestion": "ci-run init を実行して設定ファイルテンプレートを生成してください",
            "details": f"不足ファイル: {missing_files}",
        }

    message_parts = []
    if existing_files:
        message_parts.append(f"存在: {len(existing_files)} 個")
    if missing_files:
        message_parts.append(f"不足: {len(missing_files)} 個")

    return {
        "name": check_name,
        "passed": len(missing_files) == 0,
        "message": ", ".join(message_parts),
        "suggestion": "ci-run init を実行して不足している設定ファイルを生成してください" if missing_files else None,
        "details": f"存在: {existing_files}, 不足: {missing_files}" if verbose else None,
    }


def _check_required_directories(config, verbose: bool) -> dict[str, any]:
    """必要なディレクトリの状態をチェック"""
    check_name = "作業ディレクトリ"

    try:
        # 必要なディレクトリを作成
        config.ensure_directories()

        directories = ["log_dir", "cache_dir", "reports_dir"]
        created_dirs = []

        for dir_key in directories:
            dir_path = config.get_path(dir_key)
            if dir_path.exists():
                created_dirs.append(dir_path.name)

        return {
            "name": check_name,
            "passed": True,
            "message": f"{len(created_dirs)} 個のディレクトリを確認/作成",
            "suggestion": None,
            "details": f"ディレクトリ: {created_dirs}" if verbose else None,
        }

    except Exception as e:
        return {
            "name": check_name,
            "passed": False,
            "message": f"ディレクトリ作成に失敗: {e}",
            "suggestion": "プロジェクトディレクトリの書き込み権限を確認してください",
            "details": None,
        }


def _get_act_install_instructions() -> str:
    """OS別のact インストール手順を取得"""
    import platform

    system = platform.system().lower()

    if system == "darwin":  # macOS
        return "Homebrew: brew install act または GitHub Releases からダウンロード"
    elif system == "linux":
        return "パッケージマネージャーまたは GitHub Releases からダウンロード: https://github.com/nektos/act"
    elif system == "windows":
        return "Chocolatey: choco install act-cli または GitHub Releases からダウンロード"
    else:
        return "GitHub Releases からダウンロード: https://github.com/nektos/act"


def _check_disk_space(verbose: bool) -> dict[str, any]:
    """ディスク容量をチェック"""
    check_name = "ディスク容量"

    try:
        import shutil

        total, used, free = shutil.disk_usage(Path.cwd())

        # MB単位に変換
        total_mb = total // (1024 * 1024)
        used_mb = used // (1024 * 1024)
        free_mb = free // (1024 * 1024)

        # 最小必要容量（100MB）
        required_mb = 100

        if free_mb < required_mb:
            return {
                "name": check_name,
                "passed": False,
                "message": f"容量不足 (利用可能: {free_mb}MB, 必要: {required_mb}MB)",
                "suggestion": "'ci-run clean' を実行して古いログを削除するか、ディスク容量を確保してください",
                "details": f"合計: {total_mb}MB, 使用済み: {used_mb}MB, 利用可能: {free_mb}MB" if verbose else None,
            }

        return {
            "name": check_name,
            "passed": True,
            "message": f"十分な容量 ({free_mb}MB 利用可能)",
            "suggestion": None,
            "details": f"合計: {total_mb}MB, 使用済み: {used_mb}MB, 利用可能: {free_mb}MB" if verbose else None,
        }

    except Exception as e:
        return {
            "name": check_name,
            "passed": False,
            "message": f"容量チェックに失敗: {e}",
            "suggestion": "ディスクの状態を手動で確認してください",
            "details": None,
        }


def _display_results(checks: list[dict], verbose: bool) -> None:
    """診断結果を表形式で表示"""
    table = Table(title="環境診断結果")
    table.add_column("項目", style="bold")
    table.add_column("状態", justify="center")
    table.add_column("詳細")

    for check in checks:
        # ステータスアイコンと色
        if check["passed"]:
            status = "[green]✅ 成功[/green]"
        else:
            status = "[red]❌ 失敗[/red]"

        # 詳細情報
        details = check["message"]
        if verbose and check.get("details"):
            details += f"\n[dim]{check['details']}[/dim]"

        table.add_row(check["name"], status, details)

    console.print(table)

    # 失敗した項目の解決方法を表示
    failed_checks = [check for check in checks if not check["passed"]]
    if failed_checks:
        console.print("\n[bold yellow]🔧 解決方法:[/bold yellow]")
        for i, check in enumerate(failed_checks, 1):
            if check["suggestion"]:
                console.print(f"{i}. [bold]{check['name']}[/bold]: {check['suggestion']}")


def _check_security_configuration(config, verbose: bool) -> dict[str, any]:
    """セキュリティ設定をチェック"""
    check_name = "セキュリティ設定"

    try:
        # 設定ファイルのセキュリティ検証
        validation_result = config.validate_all_config_files()

        if not validation_result["overall_valid"]:
            critical_issues = validation_result.get("critical_issues", 0)
            warning_issues = validation_result.get("warning_issues", 0)

            if critical_issues > 0:
                return {
                    "name": check_name,
                    "passed": False,
                    "message": f"重大なセキュリティ問題: {critical_issues}件",
                    "suggestion": "設定ファイルからシークレットを削除し、環境変数を使用してください",
                    "details": f"警告: {warning_issues}件" if verbose and warning_issues > 0 else None,
                }
            elif warning_issues > 0:
                return {
                    "name": check_name,
                    "passed": True,
                    "message": f"軽微な問題: {warning_issues}件",
                    "suggestion": "シークレット管理のベストプラクティスを確認してください",
                    "details": "環境変数の使用を推奨します" if verbose else None,
                }

        # 環境変数の設定状況をチェック
        from ..core.security import EnvironmentSecretManager

        secret_manager = EnvironmentSecretManager()
        secret_summary = secret_manager.get_secret_summary()

        configured_count = secret_summary["total_configured"]
        missing_count = secret_summary["total_missing"]

        if missing_count > 0:
            return {
                "name": check_name,
                "passed": True,  # 警告レベル
                "message": f"推奨環境変数: {configured_count}件設定済み, {missing_count}件未設定",
                "suggestion": "AI機能を使用する場合は、必要な環境変数を設定してください",
                "details": f"未設定: {list(secret_summary['required_secrets'].keys())}" if verbose else None,
            }

        return {
            "name": check_name,
            "passed": True,
            "message": "セキュリティ設定は適切です",
            "suggestion": None,
            "details": f"設定済み環境変数: {configured_count}件" if verbose else None,
        }

    except Exception as e:
        return {
            "name": check_name,
            "passed": False,
            "message": f"セキュリティチェックに失敗: {e}",
            "suggestion": "設定ファイルの形式を確認してください",
            "details": None,
        }
