"""
ci-helper カスタム例外クラス

エラーハンドリングのための例外階層を定義します。
"""


class CIHelperError(Exception):
    """ci-helperの基底例外クラス"""

    def __init__(self, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion

    def __str__(self) -> str:
        if self.suggestion:
            return f"{self.message}\n\n💡 提案: {self.suggestion}"
        return self.message


class DependencyError(CIHelperError):
    """依存関係エラー (act, Docker未インストール等)"""

    pass


class ConfigurationError(CIHelperError):
    """設定エラー"""

    pass


class ExecutionError(CIHelperError):
    """実行時エラー"""

    pass


class ValidationError(CIHelperError):
    """入力検証エラー"""

    pass


class WorkflowNotFoundError(CIHelperError):
    """ワークフローファイルが見つからない"""

    pass


class LogParsingError(CIHelperError):
    """ログ解析エラー"""

    pass
