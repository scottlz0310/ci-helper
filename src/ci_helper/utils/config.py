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

from ..core.exceptions import ConfigurationError


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

    def __init__(self, project_root: Path | None = None):
        """設定を初期化

        Args:
            project_root: プロジェクトルートディレクトリ（Noneの場合は現在のディレクトリ）
        """
        self.project_root = project_root or Path.cwd()
        self.config_file = self.project_root / "ci-helper.toml"

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
                config.update(project_config.get("ci-helper", {}))
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
        # 必須設定のチェック
        required_keys = ["log_dir", "cache_dir", "reports_dir"]
        for key in required_keys:
            if self.get(key) is None:
                raise ConfigurationError(
                    f"必須設定 '{key}' が設定されていません",
                    f"ci-helper.tomlまたは環境変数 CI_HELPER_{key.upper()} を設定してください",
                )

        # 数値設定の範囲チェック
        timeout = self.get("timeout_seconds")
        if timeout <= 0:
            raise ConfigurationError(f"タイムアウト設定が無効です: {timeout}", "正の整数を指定してください")

        max_log_size = self.get("max_log_size_mb")
        if max_log_size <= 0:
            raise ConfigurationError(f"最大ログサイズ設定が無効です: {max_log_size}", "正の整数を指定してください")

    def __getitem__(self, key: str) -> Any:
        """辞書風アクセスをサポート"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """in演算子をサポート"""
        return key in self._config
