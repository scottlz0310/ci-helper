"""
設定管理ユーティリティ

TOML設定ファイル、環境変数、デフォルト値の管理を行います。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    pass

import tomllib

from ..core.exceptions import ConfigurationError, SecurityError


class Config:
    """設定管理クラス

    優先順位:
    1. コマンドライン引数（呼び出し側で処理）
    2. 環境変数
    3. プロジェクト設定ファイル (ci-helper.toml)
    4. デフォルト値
    """

    # デフォルト設定
    DEFAULT_CONFIG: ClassVar[dict[str, Any]] = {
        "log_dir": ".ci-helper/logs",
        "cache_dir": ".ci-helper/cache",
        "reports_dir": ".ci-helper/reports",
        "context_lines": 3,
        "max_log_size_mb": 100,
        "max_cache_size_mb": 500,
        "act_image": "ghcr.io/catthehacker/ubuntu:full-24.04",
        "timeout_seconds": 1800,  # 30分
        "verbose": False,
        "save_logs": True,
    }

    def __init__(self, project_root: Path | None = None, validate_security: bool = True):
        """設定を初期化

        Args:
            project_root: プロジェクトルートディレクトリ（Noneの場合は現在のディレクトリ）
            validate_security: セキュリティ検証を有効にするかどうか
        """
        self.project_root = project_root or Path.cwd()
        self.config_file = self.project_root / "ci-helper.toml"
        self.validate_security = validate_security

        if validate_security:
            from ..core.security import SecurityValidator

            self.security_validator = SecurityValidator()

        # 設定を読み込み
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """設定を読み込み、優先順位に従ってマージ"""
        config = self.DEFAULT_CONFIG.copy()

        # プロジェクト設定ファイルから読み込み
        if self.config_file.exists():
            try:
                with open(self.config_file, "rb") as f:
                    project_config = tomllib.load(f)

                # セキュリティ検証
                if self.validate_security:
                    self._validate_config_security(self.config_file)

                config.update(project_config.get("ci-helper", {}))
            except SecurityError:
                # セキュリティエラーは再発生
                raise
            except Exception as e:
                raise ConfigurationError(
                    f"設定ファイルの読み込みに失敗しました: {self.config_file}",
                    f"設定ファイルの構文を確認してください: {e}",
                ) from e

        # 環境変数から読み込み
        env_config = self._load_env_config()
        config.update(env_config)

        return config

    def _load_env_config(self) -> dict[str, Any]:
        """環境変数から設定を読み込み"""
        env_config = {}

        # CI_HELPER_* 環境変数をチェック
        for key, default_value in self.DEFAULT_CONFIG.items():
            env_key = f"CI_HELPER_{key.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                # 型変換
                if isinstance(default_value, bool):
                    env_config[key] = env_value.lower() in ("true", "1", "yes", "on")
                elif isinstance(default_value, int):
                    try:
                        env_config[key] = int(env_value)
                    except ValueError as e:
                        raise ConfigurationError(
                            f"環境変数 {env_key} の値が無効です: {env_value}", "整数値を指定してください"
                        ) from e
                else:
                    env_config[key] = env_value

        return env_config

    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得

        Args:
            key: 設定キー
            default: デフォルト値

        Returns:
            設定値
        """
        return self._config.get(key, default)

    def get_path(self, key: str) -> Path:
        """パス設定を絶対パスで取得

        Args:
            key: パス設定のキー

        Returns:
            絶対パス
        """
        path_str = self.get(key)
        if path_str is None:
            raise ConfigurationError(f"パス設定 '{key}' が見つかりません")

        path = Path(path_str)
        if not path.is_absolute():
            path = self.project_root / path

        return path

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        for key in ["log_dir", "cache_dir", "reports_dir"]:
            directory = self.get_path(key)
            directory.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """設定の妥当性をチェック"""
        # 必須設定のチェック - デフォルト値があるので基本的にNoneにはならない
        required_keys = ["log_dir", "cache_dir", "reports_dir"]
        for key in required_keys:
            value = self.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ConfigurationError(
                    f"必須設定 '{key}' が設定されていません",
                    f"ci-helper.tomlまたは環境変数 CI_HELPER_{key.upper()} を設定してください",
                )

        # 数値設定の範囲チェック
        timeout = self.get("timeout_seconds", self.DEFAULT_CONFIG["timeout_seconds"])
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ConfigurationError(f"タイムアウト設定が無効です: {timeout}", "正の整数を指定してください")

        max_log_size = self.get("max_log_size_mb", self.DEFAULT_CONFIG["max_log_size_mb"])
        if not isinstance(max_log_size, (int, float)) or max_log_size <= 0:
            raise ConfigurationError(f"最大ログサイズ設定が無効です: {max_log_size}", "正の整数を指定してください")

    def __getitem__(self, key: str) -> Any:
        """辞書風アクセスをサポート"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """in演算子をサポート"""
        return key in self._config

    def _validate_config_security(self, config_file: Path) -> None:
        """設定ファイルのセキュリティを検証

        Args:
            config_file: 設定ファイルのパス

        Raises:
            SecurityError: セキュリティ問題が検出された場合
        """
        if not hasattr(self, "security_validator"):
            return

        try:
            with open(config_file, encoding="utf-8") as f:
                content = f.read()

            # 設定ファイルのセキュリティ検証
            config_files = {str(config_file): content}
            validation_result = self.security_validator.validate_config_security(config_files)

            if not validation_result["overall_valid"]:
                # 重大な問題がある場合は例外を発生
                critical_issues = validation_result["critical_issues"]
                if critical_issues > 0:
                    raise SecurityError(
                        f"設定ファイル '{config_file}' に{critical_issues}件の重大なセキュリティ問題が検出されました",
                        "シークレットを環境変数に移動し、設定ファイルから削除してください",
                    )

        except SecurityError:
            raise
        except Exception:
            # セキュリティ検証自体のエラーは警告として扱う
            pass

    def validate_all_config_files(self) -> dict[str, Any]:
        """全ての設定ファイルのセキュリティを検証

        Returns:
            検証結果の辞書
        """
        if not hasattr(self, "security_validator"):
            return {
                "overall_valid": True,
                "message": "セキュリティ検証が無効になっています",
            }

        config_files = {}

        # ci-helper.toml
        if self.config_file.exists():
            with open(self.config_file, encoding="utf-8") as f:
                config_files[str(self.config_file)] = f.read()

        # .env ファイル
        env_file = self.project_root / ".env"
        if env_file.exists():
            with open(env_file, encoding="utf-8") as f:
                config_files[str(env_file)] = f.read()

        # .actrc ファイル
        actrc_file = self.project_root / ".actrc"
        if actrc_file.exists():
            with open(actrc_file, encoding="utf-8") as f:
                config_files[str(actrc_file)] = f.read()

        if not config_files:
            return {
                "overall_valid": True,
                "message": "検証対象の設定ファイルが見つかりませんでした",
            }

        return self.security_validator.validate_config_security(config_files)

    def get_secret_recommendations(self) -> list[str]:
        """シークレット管理の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        return [
            "シークレット管理のベストプラクティス:",
            "",
            "1. 環境変数の使用:",
            "   export OPENAI_API_KEY=your_api_key",
            "   export GITHUB_TOKEN=your_token",
            "",
            "2. .env ファイルの使用:",
            "   echo 'OPENAI_API_KEY=your_api_key' >> .env",
            "   echo '.env' >> .gitignore",
            "",
            "3. 設定ファイルでの参照:",
            "   [ci-helper]",
            "   # 良い例: 環境変数参照",
            "   api_key = '${OPENAI_API_KEY}'",
            "   # 悪い例: 直接記載",
            "   # api_key = 'sk-1234567890abcdef'",
            "",
            "4. act実行時の環境変数:",
            "   ci-helperは自動的に安全な環境変数のみをactに渡します",
        ]

    def get_project_root(self) -> Path:
        """プロジェクトルートディレクトリを取得

        Returns:
            プロジェクトルートディレクトリのパス
        """
        return self.project_root
