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


class LogFormattingError(CIHelperError):
    """ログ整形関連エラー"""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        formatter_name: str | None = None,
        format_type: str | None = None,
    ):
        super().__init__(message, suggestion)
        self.formatter_name = formatter_name
        self.format_type = format_type

    @classmethod
    def formatter_not_found(cls, formatter_name: str, available_formatters: list[str]) -> LogFormattingError:
        """フォーマッターが見つからない場合のエラー"""
        available_list = "、".join(available_formatters) if available_formatters else "なし"
        return cls(
            f"フォーマッター '{formatter_name}' が見つかりません",
            f"利用可能なフォーマッター: {available_list}",
            formatter_name=formatter_name,
        )

    @classmethod
    def invalid_format_options(cls, formatter_name: str, invalid_options: list[str]) -> LogFormattingError:
        """無効なフォーマットオプションが指定された場合のエラー"""
        options_str = "、".join(invalid_options)
        return cls(
            f"フォーマッター '{formatter_name}' に無効なオプションが指定されました: {options_str}",
            "フォーマッターのドキュメントを確認して、有効なオプションを指定してください",
            formatter_name=formatter_name,
        )

    @classmethod
    def formatting_failed(cls, formatter_name: str, error_details: str) -> LogFormattingError:
        """フォーマット処理が失敗した場合のエラー"""
        return cls(
            f"フォーマッター '{formatter_name}' での処理が失敗しました: {error_details}",
            "ログファイルの形式を確認するか、別のフォーマッターを試してください",
            formatter_name=formatter_name,
        )

    @classmethod
    def memory_limit_exceeded(cls, formatter_name: str, file_size_mb: int) -> LogFormattingError:
        """メモリ制限を超えた場合のエラー"""
        return cls(
            f"ログファイルが大きすぎます ({file_size_mb}MB): フォーマッター '{formatter_name}' で処理できません",
            "ストリーミングフォーマッターを使用するか、ログファイルを分割してください",
            formatter_name=formatter_name,
        )


class FileOperationError(CIHelperError):
    """ファイル操作関連エラー"""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        file_path: str | None = None,
        operation: str | None = None,
    ):
        super().__init__(message, suggestion)
        self.file_path = file_path
        self.operation = operation

    @classmethod
    def file_not_found(cls, file_path: str, operation: str = "読み込み") -> FileOperationError:
        """ファイルが見つからない場合のエラー"""
        return cls(
            f"ファイルが見つかりません: {file_path}",
            "ファイルパスを確認するか、'ci-run logs' で利用可能なログファイルを確認してください",
            file_path=file_path,
            operation=operation,
        )

    @classmethod
    def permission_denied(cls, file_path: str, operation: str) -> FileOperationError:
        """ファイルアクセス権限がない場合のエラー"""
        return cls(
            f"ファイル{operation}の権限がありません: {file_path}",
            "ファイルの権限を確認するか、管理者権限で実行してください",
            file_path=file_path,
            operation=operation,
        )

    @classmethod
    def disk_space_insufficient(cls, file_path: str, required_mb: int, available_mb: int) -> FileOperationError:
        """ディスク容量不足の場合のエラー"""
        return cls(
            f"ディスク容量が不足しています: 必要 {required_mb}MB、利用可能 {available_mb}MB",
            "'ci-run clean' でキャッシュを削除するか、別の場所に保存してください",
            file_path=file_path,
            operation="書き込み",
        )

    @classmethod
    def file_corrupted(cls, file_path: str) -> FileOperationError:
        """ファイルが破損している場合のエラー"""
        return cls(
            f"ファイルが破損しているか、読み取れません: {file_path}",
            "ファイルを再生成するか、バックアップから復元してください",
            file_path=file_path,
            operation="読み込み",
        )

    @classmethod
    def path_too_long(cls, file_path: str) -> FileOperationError:
        """ファイルパスが長すぎる場合のエラー"""
        return cls(
            f"ファイルパスが長すぎます: {file_path}",
            "より短いファイル名を使用するか、ディレクトリ階層を浅くしてください",
            file_path=file_path,
            operation="作成",
        )

    @classmethod
    def unsafe_path(cls, file_path: str) -> FileOperationError:
        """安全でないパスが指定された場合のエラー"""
        return cls(
            f"セキュリティ上の理由により、このパスへのアクセスは許可されていません: {file_path}",
            "現在のディレクトリまたはその下位ディレクトリを使用してください",
            file_path=file_path,
            operation="アクセス",
        )


class UserInputError(CIHelperError):
    """ユーザー入力関連エラー"""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        input_value: str | None = None,
        input_type: str | None = None,
    ):
        super().__init__(message, suggestion)
        self.input_value = input_value
        self.input_type = input_type

    @classmethod
    def invalid_format_type(cls, format_type: str, valid_types: list[str]) -> UserInputError:
        """無効なフォーマット種別が指定された場合のエラー"""
        valid_list = "、".join(valid_types)
        return cls(
            f"無効なフォーマット種別です: {format_type}",
            f"有効なフォーマット種別: {valid_list}",
            input_value=format_type,
            input_type="format_type",
        )

    @classmethod
    def invalid_option_value(cls, option_name: str, value: str, expected_type: str) -> UserInputError:
        """無効なオプション値が指定された場合のエラー"""
        return cls(
            f"オプション '{option_name}' の値が無効です: {value}",
            f"期待される型: {expected_type}",
            input_value=value,
            input_type=option_name,
        )

    @classmethod
    def missing_required_input(cls, input_name: str) -> UserInputError:
        """必須入力が不足している場合のエラー"""
        return cls(
            f"必須項目が入力されていません: {input_name}",
            "必要な情報を入力してください",
            input_type=input_name,
        )

    @classmethod
    def input_too_long(cls, input_name: str, max_length: int, actual_length: int) -> UserInputError:
        """入力値が長すぎる場合のエラー"""
        return cls(
            f"入力値が長すぎます ({input_name}): {actual_length}文字 (最大: {max_length}文字)",
            f"{max_length}文字以内で入力してください",
            input_type=input_name,
        )

    @classmethod
    def invalid_file_extension(cls, file_path: str, valid_extensions: list[str]) -> UserInputError:
        """無効なファイル拡張子の場合のエラー"""
        valid_list = "、".join(valid_extensions)
        return cls(
            f"無効なファイル拡張子です: {file_path}",
            f"有効な拡張子: {valid_list}",
            input_value=file_path,
            input_type="file_extension",
        )
