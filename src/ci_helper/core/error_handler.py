"""
包括的エラーハンドリングシステム

エラーの分類、ユーザーフレンドリーなメッセージ表示、復旧提案を提供します。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .exceptions import (
    CIHelperError,
    ConfigurationError,
    DependencyError,
    DiskSpaceError,
    ExecutionError,
    LogParsingError,
    SecurityError,
    ValidationError,
    WorkflowNotFoundError,
)

console = Console()


class ErrorHandler:
    """包括的エラーハンドリングクラス"""

    @staticmethod
    def handle_error(error: Exception, verbose: bool = False) -> None:
        """エラーを適切に処理し、ユーザーフレンドリーなメッセージを表示"""

        if isinstance(error, CIHelperError):
            ErrorHandler._handle_ci_helper_error(error, verbose)
        else:
            ErrorHandler._handle_unexpected_error(error, verbose)

    @staticmethod
    def _handle_ci_helper_error(error: CIHelperError, verbose: bool) -> None:
        """ci-helper固有のエラーを処理"""

        # エラータイプに応じたアイコンと色を設定
        if isinstance(error, DependencyError):
            icon = "🔧"
            color = "red"
            title = "依存関係エラー"
        elif isinstance(error, ConfigurationError):
            icon = "⚙️"
            color = "yellow"
            title = "設定エラー"
        elif isinstance(error, ExecutionError):
            icon = "💥"
            color = "red"
            title = "実行エラー"
        elif isinstance(error, ValidationError):
            icon = "❌"
            color = "red"
            title = "入力検証エラー"
        elif isinstance(error, WorkflowNotFoundError):
            icon = "📁"
            color = "yellow"
            title = "ワークフローエラー"
        elif isinstance(error, LogParsingError):
            icon = "📄"
            color = "yellow"
            title = "ログ解析エラー"
        elif isinstance(error, DiskSpaceError):
            icon = "💾"
            color = "red"
            title = "ディスク容量エラー"
        elif isinstance(error, SecurityError):
            icon = "🔒"
            color = "red"
            title = "セキュリティエラー"
        else:
            icon = "⚠️"
            color = "red"
            title = "エラー"

        # エラーメッセージの構築
        message_parts = [f"{icon} {error.message}"]

        if verbose and error.details:
            message_parts.append(f"\n[dim]詳細: {error.details}[/dim]")

        if error.suggestion:
            message_parts.append(f"\n💡 [bold green]解決方法:[/bold green] {error.suggestion}")

        message = "\n".join(message_parts)

        # パネルで表示
        panel = Panel(message, title=f"[bold {color}]{title}[/bold {color}]", border_style=color, expand=False)

        console.print(panel)

    @staticmethod
    def _handle_unexpected_error(error: Exception, verbose: bool) -> None:
        """予期しないエラーを処理"""

        message_parts = [f"⚠️ 予期しないエラーが発生しました: {type(error).__name__}", f"メッセージ: {error!s}"]

        if verbose:
            import traceback

            message_parts.append(f"\n[dim]スタックトレース:\n{traceback.format_exc()}[/dim]")

        message_parts.append(
            "\n💡 [bold green]解決方法:[/bold green] "
            "このエラーが継続する場合は、--verbose フラグを使用して詳細情報を確認してください"
        )

        message = "\n".join(message_parts)

        panel = Panel(message, title="[bold red]予期しないエラー[/bold red]", border_style="red", expand=False)

        console.print(panel)


class DependencyChecker:
    """依存関係チェック機能"""

    @staticmethod
    def check_act_command() -> None:
        """act コマンドの存在確認"""
        if not shutil.which("act"):
            raise DependencyError.act_not_found()

    @staticmethod
    def check_docker_daemon() -> None:
        """Docker デーモンの実行状態確認"""
        if not shutil.which("docker"):
            raise DependencyError(
                "Docker コマンドが見つかりません",
                "Docker Desktop をインストールしてください: https://www.docker.com/products/docker-desktop/",
                missing_dependency="docker",
            )

        try:
            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10, check=True)
        except subprocess.CalledProcessError:
            raise DependencyError.docker_not_running()
        except subprocess.TimeoutExpired:
            raise DependencyError(
                "Docker の応答がタイムアウトしました",
                "Docker Desktop を再起動してください",
                missing_dependency="docker",
            )

    @staticmethod
    def check_workflows_directory() -> list[Path]:
        """GitHub Workflows ディレクトリとファイルの存在確認"""
        workflows_dir = Path.cwd() / ".github" / "workflows"

        if not workflows_dir.exists():
            raise WorkflowNotFoundError(
                ".github/workflows ディレクトリが存在しません",
                "GitHub Actions ワークフローファイルを .github/workflows/ に配置してください",
            )

        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

        if not workflow_files:
            raise WorkflowNotFoundError.no_workflows_found()

        return workflow_files

    @staticmethod
    def check_disk_space(required_mb: int = 100) -> None:
        """ディスク容量の確認"""
        try:
            import shutil

            total, used, free = shutil.disk_usage(Path.cwd())
            free_mb = free // (1024 * 1024)

            if free_mb < required_mb:
                raise DiskSpaceError.insufficient_space(free_mb, required_mb)

        except Exception as e:
            # ディスク容量チェックに失敗した場合は警告のみ
            console.print(f"[yellow]警告: ディスク容量の確認に失敗しました: {e}[/yellow]")


class ValidationHelper:
    """入力検証ヘルパー"""

    @staticmethod
    def validate_workflow_path(workflow_path: str) -> Path:
        """ワークフローパスの検証"""
        path = Path(workflow_path)

        # 相対パスの場合は .github/workflows からの相対パスとして扱う
        if not path.is_absolute():
            workflows_dir = Path.cwd() / ".github" / "workflows"
            path = workflows_dir / workflow_path

        # ファイルの存在確認
        if not path.exists():
            raise WorkflowNotFoundError.specific_workflow_not_found(workflow_path)

        # 拡張子の確認
        if path.suffix not in [".yml", ".yaml"]:
            raise ValidationError.invalid_workflow_path(workflow_path)

        return path

    @staticmethod
    def validate_log_path(log_path: str) -> Path:
        """ログファイルパスの検証"""
        path = Path(log_path)

        if not path.exists():
            raise LogParsingError(f"ログファイル '{log_path}' が見つかりません", "ログファイルのパスを確認してください")

        if not path.is_file():
            raise LogParsingError(
                f"'{log_path}' はファイルではありません", "有効なログファイルのパスを指定してください"
            )

        return path


class TimeoutHandler:
    """タイムアウト処理"""

    @staticmethod
    def run_with_timeout(
        command: list[str], timeout_seconds: int, cwd: Path | None = None
    ) -> subprocess.CompletedProcess:
        """タイムアウト付きでコマンドを実行"""
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, cwd=cwd, check=True)
        except subprocess.TimeoutExpired:
            raise ExecutionError.timeout_error(" ".join(command), timeout_seconds)
        except subprocess.CalledProcessError as e:
            raise ExecutionError.command_failed(" ".join(command), e.returncode, e.stderr)


class SecurityValidator:
    """セキュリティ検証"""

    # 一般的なシークレットパターン
    SECRET_PATTERNS = [
        r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?',
        r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9_@#$%^&*-]{8,})["\']?',
        r'(?i)(token|auth[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?',
        r'(?i)(access[_-]?key|accesskey)\s*[:=]\s*["\']?([A-Z0-9]{20,})["\']?',
        r'(?i)(private[_-]?key|privatekey)\s*[:=]\s*["\']?([a-zA-Z0-9+/=]{40,})["\']?',
    ]

    @staticmethod
    def check_config_for_secrets(config_content: str, config_file: str) -> None:
        """設定ファイル内のシークレットをチェック"""
        import re

        for pattern in SecurityValidator.SECRET_PATTERNS:
            if re.search(pattern, config_content):
                raise SecurityError.secrets_in_config(config_file)

    @staticmethod
    def sanitize_log_content(content: str) -> str:
        """ログ内容からシークレットを除去"""
        import re

        sanitized = content
        for pattern in SecurityValidator.SECRET_PATTERNS:
            sanitized = re.sub(pattern, r"\1=***REDACTED***", sanitized)

        return sanitized
