"""
ci-helper カスタム例外クラス

エラーハンドリングのための例外階層を定義します。
"""

from __future__ import annotations

import platform
from typing import Any


class CIHelperError(Exception):
    """ci-helperの基底例外クラス"""

    def __init__(self, message: str, suggestion: str | None = None, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.details = details

    def __str__(self) -> str:
        result = self.message
        if self.details:
            result += f"\n詳細: {self.details}"
        if self.suggestion:
            result += f"\n\n💡 提案: {self.suggestion}"
        return result

    def get_user_friendly_message(self) -> str:
        """ユーザーフレンドリーなエラーメッセージを取得"""
        return str(self)


class DependencyError(CIHelperError):
    """依存関係エラー (act, Docker未インストール等)"""

    def __init__(self, message: str, suggestion: str | None = None, missing_dependency: str | None = None):
        super().__init__(message, suggestion)
        self.missing_dependency = missing_dependency

    @classmethod
    def act_not_found(cls) -> DependencyError:
        """act コマンドが見つからない場合のエラー"""
        system = platform.system().lower()

        if system == "darwin":  # macOS
            suggestion = "Homebrew でインストール: brew install act\nまたは GitHub Releases からダウンロード: https://github.com/nektos/act"
        elif system == "linux":
            suggestion = "パッケージマネージャーまたは GitHub Releases からダウンロード: https://github.com/nektos/act"
        elif system == "windows":
            suggestion = "Chocolatey でインストール: choco install act-cli\nまたは GitHub Releases からダウンロード: https://github.com/nektos/act"
        else:
            suggestion = "GitHub Releases からダウンロード: https://github.com/nektos/act"

        return cls("act コマンドが見つかりません", suggestion, missing_dependency="act")

    @classmethod
    def docker_not_running(cls) -> DependencyError:
        """Docker デーモンが実行されていない場合のエラー"""
        return cls(
            "Docker デーモンが実行されていません",
            "Docker Desktop を起動してください。Docker が正しくインストールされていることを確認してください。",
            missing_dependency="docker",
        )


class ConfigurationError(CIHelperError):
    """設定エラー"""

    def __init__(self, message: str, suggestion: str | None = None, config_file: str | None = None):
        super().__init__(message, suggestion)
        self.config_file = config_file

    @classmethod
    def invalid_config(cls, config_file: str, error_details: str) -> ConfigurationError:
        """設定ファイルが無効な場合のエラー"""
        return cls(
            f"設定ファイル '{config_file}' が無効です: {error_details}",
            "設定ファイルの形式を確認し、必要に応じて 'ci-run init' で再生成してください",
            config_file=config_file,
        )

    @classmethod
    def missing_config(cls, config_file: str) -> ConfigurationError:
        """設定ファイルが見つからない場合のエラー"""
        return cls(
            f"設定ファイル '{config_file}' が見つかりません",
            "'ci-run init' を実行して設定ファイルを生成してください",
            config_file=config_file,
        )


class ExecutionError(CIHelperError):
    """実行時エラー"""

    def __init__(
        self, message: str, suggestion: str | None = None, exit_code: int | None = None, command: str | None = None
    ):
        super().__init__(message, suggestion)
        self.exit_code = exit_code
        self.command = command

    @classmethod
    def timeout_error(cls, command: str, timeout_seconds: int) -> ExecutionError:
        """タイムアウトエラー"""
        return cls(
            f"コマンド '{command}' が {timeout_seconds} 秒でタイムアウトしました",
            "より長いタイムアウト値を設定するか、ワークフローを最適化してください",
            command=command,
        )

    @classmethod
    def command_failed(cls, command: str, exit_code: int, stderr: str | None = None) -> ExecutionError:
        """コマンド実行失敗エラー"""
        message = f"コマンド '{command}' が失敗しました (終了コード: {exit_code})"
        details = stderr if stderr else None

        return cls(message, "コマンドの引数と環境を確認してください", exit_code=exit_code, command=command)


class ValidationError(CIHelperError):
    """入力検証エラー"""

    def __init__(self, message: str, suggestion: str | None = None, invalid_value: Any = None):
        super().__init__(message, suggestion)
        self.invalid_value = invalid_value

    @classmethod
    def invalid_workflow_path(cls, path: str) -> ValidationError:
        """無効なワークフローパスエラー"""
        return cls(
            f"無効なワークフローパス: {path}",
            "ワークフローファイルは .github/workflows/ ディレクトリ内の .yml または .yaml ファイルである必要があります",
            invalid_value=path,
        )


class WorkflowNotFoundError(CIHelperError):
    """ワークフローファイルが見つからない"""

    def __init__(self, message: str, suggestion: str | None = None, workflow_path: str | None = None):
        super().__init__(message, suggestion)
        self.workflow_path = workflow_path

    @classmethod
    def no_workflows_found(cls) -> WorkflowNotFoundError:
        """ワークフローファイルが見つからない場合のエラー"""
        return cls(
            ".github/workflows ディレクトリにワークフローファイルが見つかりません",
            "GitHub Actions ワークフローファイル (.yml または .yaml) を .github/workflows/ ディレクトリに配置してください",
        )

    @classmethod
    def specific_workflow_not_found(cls, workflow_name: str) -> WorkflowNotFoundError:
        """指定されたワークフローが見つからない場合のエラー"""
        return cls(
            f"ワークフローファイル '{workflow_name}' が見つかりません",
            "ワークフローファイル名を確認するか、'ci-run logs' で利用可能なワークフローを確認してください",
            workflow_path=workflow_name,
        )


class LogParsingError(CIHelperError):
    """ログ解析エラー"""

    def __init__(self, message: str, suggestion: str | None = None, log_file: str | None = None):
        super().__init__(message, suggestion)
        self.log_file = log_file

    @classmethod
    def corrupted_log(cls, log_file: str) -> LogParsingError:
        """破損したログファイルエラー"""
        return cls(
            f"ログファイル '{log_file}' が破損しているか、読み取れません",
            "ログファイルを削除して新しい実行を試してください",
            log_file=log_file,
        )


class DiskSpaceError(CIHelperError):
    """ディスク容量不足エラー"""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        available_space: int | None = None,
        required_space: int | None = None,
    ):
        super().__init__(message, suggestion)
        self.available_space = available_space
        self.required_space = required_space

    @classmethod
    def insufficient_space(cls, available_mb: int, required_mb: int) -> DiskSpaceError:
        """ディスク容量不足エラー"""
        return cls(
            f"ディスク容量が不足しています (利用可能: {available_mb}MB, 必要: {required_mb}MB)",
            "'ci-run clean' を実行して古いログを削除するか、ディスク容量を確保してください",
            available_space=available_mb,
            required_space=required_mb,
        )


class SecurityError(CIHelperError):
    """セキュリティ関連エラー"""

    def __init__(self, message: str, suggestion: str | None = None, security_issue: str | None = None):
        super().__init__(message, suggestion)
        self.security_issue = security_issue

    @classmethod
    def secrets_in_config(cls, config_file: str) -> SecurityError:
        """設定ファイルにシークレットが含まれている場合のエラー"""
        return cls(
            f"設定ファイル '{config_file}' にシークレットが含まれています",
            "シークレットは環境変数で設定してください。設定ファイルからシークレットを削除してください。",
            security_issue="secrets_in_config",
        )
