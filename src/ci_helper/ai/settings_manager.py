"""設定永続化管理

AI分析機能の設定の保存と読み込みを管理します。
"""

from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ci_helper.core.exceptions import ConfigurationError
from ci_helper.utils.config import Config


class SettingsManager:
    """設定永続化管理クラス."""

    def __init__(self, config: Config) -> None:
        """設定管理を初期化.

        Args:
            config: メイン設定オブジェクト

        """
        self.config = config
        self.settings_dir = self.config.project_root / ".ci-helper" / "settings"
        self.ai_settings_file = self.settings_dir / "ai_config.json"

    def save_ai_settings(self, settings: dict[str, Any]) -> None:
        """AI設定を保存.

        Args:
            settings: 保存するAI設定の辞書

        Raises:
            ConfigurationError: 保存に失敗した場合

        """
        # 設定ディレクトリを作成
        self.settings_dir.mkdir(parents=True, exist_ok=True)

        # 設定データを作成
        settings_data = {
            "version": "1.0",
            "updated_at": self._get_current_timestamp(),
            "ai_settings": settings,
        }

        try:
            with self.ai_settings_file.open("w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            msg = f"AI設定の保存に失敗しました: {self.ai_settings_file}"
            err_msg = f"ファイルの書き込み権限を確認してください: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def load_ai_settings(self) -> dict[str, Any]:
        """AI設定を読み込み.

        Returns:
            AI設定の辞書

        """
        if not self.ai_settings_file.exists():
            return {}

        try:
            with self.ai_settings_file.open(encoding="utf-8") as f:
                settings_data = json.load(f)

            return settings_data.get("ai_settings", {})

        except Exception as e:
            msg = f"AI設定の読み込みに失敗しました: {self.ai_settings_file}"
            err_msg = f"ファイルの形式を確認してください: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def update_project_config(self, ai_settings: dict[str, Any]) -> None:
        """プロジェクト設定ファイル(ci-helper.toml)を更新.

        Args:
            ai_settings: 更新するAI設定

        Raises:
            ConfigurationError: 更新に失敗した場合

        """
        config_file = self.config.config_file

        # 既存の設定を読み込み
        existing_config: dict[str, Any] = {}
        if config_file.exists():
            try:
                with config_file.open("rb") as f:
                    existing_config = tomllib.load(f)
            except Exception as e:
                msg = f"既存設定ファイルの読み込みに失敗しました: {config_file}"
                err_msg = f"ファイルの形式を確認してください: {e}"
                raise ConfigurationError(msg, err_msg) from e

        # AI設定を更新
        if "ai" not in existing_config:
            existing_config["ai"] = {}

        if isinstance(existing_config["ai"], dict):
            cast("dict[str, Any]", existing_config["ai"]).update(ai_settings)

        # TOML形式で保存
        try:
            self._save_toml_config(config_file, existing_config)
        except Exception as e:
            msg = f"設定ファイルの更新に失敗しました: {config_file}"
            err_msg = f"エラー: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def get_merged_settings(self) -> dict[str, Any]:
        """マージされた設定を取得.

        Returns:
            プロジェクト設定とローカル設定をマージした辞書

        """
        # プロジェクト設定から読み込み
        project_ai_config = self.config.get_ai_config()

        # ローカル設定から読み込み
        local_ai_settings = self.load_ai_settings()

        # マージ(ローカル設定が優先)
        merged_settings = project_ai_config.copy()
        merged_settings.update(local_ai_settings)

        return merged_settings

    def reset_to_defaults(self) -> None:
        """設定をデフォルトにリセット.

        Raises:
            ConfigurationError: リセットに失敗した場合

        """
        try:
            # ローカル設定ファイルを削除
            if self.ai_settings_file.exists():
                self.ai_settings_file.unlink()

            # 設定ディレクトリが空の場合は削除
            if self.settings_dir.exists() and not any(self.settings_dir.iterdir()):
                self.settings_dir.rmdir()

        except Exception as e:
            msg = "設定のリセットに失敗しました"
            err_msg = f"エラー: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def backup_current_settings(self) -> Path:
        """現在の設定をバックアップ.

        Returns:
            バックアップファイルのパス

        Raises:
            ConfigurationError: バックアップに失敗した場合

        """
        backup_dir = self.settings_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = self._get_current_timestamp().replace(":", "-")
        backup_file = backup_dir / f"ai_config_backup_{timestamp}.json"

        try:
            current_settings = self.get_merged_settings()
            backup_data = {
                "version": "1.0",
                "backup_created_at": self._get_current_timestamp(),
                "settings": current_settings,
            }

            with backup_file.open("w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            return backup_file

        except Exception as e:
            msg = f"設定のバックアップに失敗しました: {backup_file}"
            err_msg = f"エラー: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def restore_from_backup(self, backup_file: Path) -> None:
        """バックアップから設定を復元.

        Args:
            backup_file: バックアップファイルのパス

        Raises:
            ConfigurationError: 復元に失敗した場合

        """
        if not backup_file.exists():
            msg = f"バックアップファイルが見つかりません: {backup_file}"
            raise ConfigurationError(msg, "ファイルパスを確認してください")

        try:
            with backup_file.open(encoding="utf-8") as f:
                backup_data = json.load(f)

            settings = backup_data.get("settings", {})
            self.save_ai_settings(settings)

        except Exception as e:
            msg = f"バックアップからの復元に失敗しました: {backup_file}"
            err_msg = f"エラー: {e}"
            raise ConfigurationError(msg, err_msg) from e

    def _get_current_timestamp(self) -> str:
        """現在のタイムスタンプを取得.

        Returns:
            ISO形式のタイムスタンプ文字列

        """
        return datetime.now(tz=UTC).isoformat()

    def _save_toml_config(self, config_file: Path, config_data: dict[str, Any]) -> None:
        """TOML設定ファイルを保存.

        Args:
            config_file: 設定ファイルのパス
            config_data: 設定データ

        Note:
            Python標準ライブラリにはTOML書き込み機能がないため、
            シンプルな形式で書き込みを行います。

        """
        lines: list[str] = []

        # ci-helper セクション
        if "ci-helper" in config_data:
            lines.append("[ci-helper]")
            ci_helper_config = cast("dict[str, Any]", config_data["ci-helper"])
            for key, value in ci_helper_config.items():
                lines.append(f"{key} = {self._format_toml_value(value)}")
            lines.append("")

        # ai セクション
        if "ai" in config_data:
            lines.append("[ai]")
            ai_config = config_data["ai"]
            if not isinstance(ai_config, dict):
                ai_config = {}

            ai_config_dict = cast("dict[str, Any]", ai_config)

            # トップレベル設定
            for key, value in ai_config_dict.items():
                if not isinstance(value, dict):
                    lines.append(f"{key} = {self._format_toml_value(value)}")

            lines.append("")

            # サブセクション
            for section_name, section_data in ai_config_dict.items():
                if isinstance(section_data, dict):
                    lines.append(f"[ai.{section_name}]")
                    section_data_dict = cast("dict[str, Any]", section_data)
                    for key, value in section_data_dict.items():
                        lines.append(f"{key} = {self._format_toml_value(value)}")
                    lines.append("")

        # ファイルに書き込み
        with Path(config_file).open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _format_toml_value(self, value: object) -> str:
        """TOML形式の値をフォーマット.

        Args:
            value: フォーマットする値

        Returns:
            TOML形式の文字列

        """
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, list):
            value_list = cast("list[Any]", value)
            formatted_items: list[str] = [self._format_toml_value(item) for item in value_list]
            return f"[{', '.join(formatted_items)}]"
        return str(value)
