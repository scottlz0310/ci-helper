"""
settings_manager.py のテスト

設定永続化管理システムの機能をテストします。
"""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from ci_helper.ai.settings_manager import SettingsManager
from ci_helper.core.exceptions import ConfigurationError
from ci_helper.utils.config import Config


class TestSettingsManager:
    """SettingsManager のテストクラス"""

    @pytest.fixture
    def mock_config(self):
        """モック設定オブジェクト"""
        config = Mock(spec=Config)
        config.project_root = Path("/test/project")
        config.config_file = Path("/test/project/ci-helper.toml")
        config.get_ai_config.return_value = {"provider": "openai", "model": "gpt-4", "temperature": 0.7}
        return config

    @pytest.fixture
    def settings_manager(self, mock_config):
        """SettingsManager インスタンス"""
        return SettingsManager(mock_config)

    def test_init(self, mock_config):
        """初期化のテスト"""
        manager = SettingsManager(mock_config)

        assert manager.config == mock_config
        assert manager.settings_dir == Path("/test/project/.ci-helper/settings")
        assert manager.ai_settings_file == Path("/test/project/.ci-helper/settings/ai_config.json")

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    @patch("ci_helper.ai.settings_manager.SettingsManager._get_current_timestamp")
    def test_save_ai_settings_success(self, mock_timestamp, mock_mkdir, mock_file, settings_manager):
        """AI設定保存成功のテスト"""
        mock_timestamp.return_value = "2024-01-01T12:00:00"

        settings = {"provider": "anthropic", "model": "claude-3", "temperature": 0.5}

        settings_manager.save_ai_settings(settings)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once()

        # 書き込まれた内容を確認
        write_calls = mock_file().write.call_args_list
        written_content = "".join(call[0][0] for call in write_calls)

        # JSON形式の文字列が書き込まれたことを確認
        assert '"version": "1.0"' in written_content
        assert '"updated_at": "2024-01-01T12:00:00"' in written_content
        assert '"provider": "anthropic"' in written_content
        assert '"model": "claude-3"' in written_content

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    @patch("pathlib.Path.mkdir")
    def test_save_ai_settings_permission_error(self, mock_mkdir, mock_file, settings_manager):
        """AI設定保存時の権限エラーテスト"""
        settings = {"provider": "openai"}

        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.save_ai_settings(settings)

        assert "AI設定の保存に失敗しました" in str(exc_info.value)
        assert "書き込み権限を確認してください" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=False)
    def test_load_ai_settings_no_file(self, mock_exists, settings_manager):
        """設定ファイルが存在しない場合の読み込みテスト"""
        settings = settings_manager.load_ai_settings()

        assert settings == {}

    @patch("pathlib.Path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"version": "1.0", "ai_settings": {"provider": "openai", "model": "gpt-4"}}',
    )
    def test_load_ai_settings_success(self, mock_file, mock_exists, settings_manager):
        """AI設定読み込み成功のテスト"""
        settings = settings_manager.load_ai_settings()

        assert settings["provider"] == "openai"
        assert settings["model"] == "gpt-4"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"version": "1.0"}')
    def test_load_ai_settings_no_ai_settings_key(self, mock_file, mock_exists, settings_manager):
        """ai_settingsキーが存在しない場合の読み込みテスト"""
        settings = settings_manager.load_ai_settings()

        assert settings == {}

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_load_ai_settings_json_error(self, mock_file, mock_exists, settings_manager):
        """AI設定読み込み時のJSONエラーテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.load_ai_settings()

        assert "AI設定の読み込みに失敗しました" in str(exc_info.value)
        assert "ファイルの形式を確認してください" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=False)
    def test_update_project_config_no_existing_file(self, mock_exists, settings_manager):
        """既存設定ファイルが存在しない場合の更新テスト"""
        ai_settings = {"provider": "anthropic", "model": "claude-3"}

        with patch.object(settings_manager, "_save_toml_config") as mock_save:
            settings_manager.update_project_config(ai_settings)

            # 新しい設定で保存されることを確認
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            config_data = args[1]
            assert config_data["ai"] == ai_settings

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b'[ai]\nprovider = "openai"\nmodel = "gpt-4"')
    def test_update_project_config_with_existing_file(self, mock_file, mock_exists, settings_manager):
        """既存設定ファイルがある場合の更新テスト"""
        ai_settings = {"temperature": 0.5}

        with patch("tomllib.load") as mock_load, patch.object(settings_manager, "_save_toml_config") as mock_save:
            mock_load.return_value = {"ai": {"provider": "openai", "model": "gpt-4"}}

            settings_manager.update_project_config(ai_settings)

            # 既存設定にマージされることを確認
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            config_data = args[1]
            assert config_data["ai"]["provider"] == "openai"
            assert config_data["ai"]["model"] == "gpt-4"
            assert config_data["ai"]["temperature"] == 0.5

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("Read error"))
    def test_update_project_config_read_error(self, mock_file, mock_exists, settings_manager):
        """既存設定ファイル読み込みエラーのテスト"""
        ai_settings = {"provider": "anthropic"}

        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.update_project_config(ai_settings)

        assert "既存設定ファイルの読み込みに失敗しました" in str(exc_info.value)

    @patch.object(SettingsManager, "_save_toml_config", side_effect=Exception("Write error"))
    def test_update_project_config_write_error(self, mock_save, settings_manager):
        """設定ファイル書き込みエラーのテスト"""
        ai_settings = {"provider": "anthropic"}

        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.update_project_config(ai_settings)

        assert "設定ファイルの更新に失敗しました" in str(exc_info.value)

    def test_get_merged_settings(self, settings_manager):
        """マージされた設定取得のテスト"""
        with patch.object(settings_manager, "load_ai_settings") as mock_load:
            mock_load.return_value = {"temperature": 0.5, "max_tokens": 1000}

            merged = settings_manager.get_merged_settings()

            # プロジェクト設定とローカル設定がマージされることを確認
            assert merged["provider"] == "openai"  # プロジェクト設定から
            assert merged["model"] == "gpt-4"  # プロジェクト設定から
            assert merged["temperature"] == 0.5  # ローカル設定から（優先）
            assert merged["max_tokens"] == 1000  # ローカル設定から

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.rmdir")
    def test_reset_to_defaults_success(self, mock_rmdir, mock_unlink, mock_exists, settings_manager):
        """設定リセット成功のテスト"""
        with patch("pathlib.Path.iterdir", return_value=[]):
            settings_manager.reset_to_defaults()

            mock_unlink.assert_called_once()
            mock_rmdir.assert_called_once()

    @patch("pathlib.Path.exists", return_value=False)
    def test_reset_to_defaults_no_file(self, mock_exists, settings_manager):
        """設定ファイルが存在しない場合のリセットテスト"""
        # 例外が発生しないことを確認
        settings_manager.reset_to_defaults()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.unlink", side_effect=PermissionError("Permission denied"))
    def test_reset_to_defaults_permission_error(self, mock_unlink, mock_exists, settings_manager):
        """設定リセット時の権限エラーテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.reset_to_defaults()

        assert "設定のリセットに失敗しました" in str(exc_info.value)

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ci_helper.ai.settings_manager.SettingsManager._get_current_timestamp")
    def test_backup_current_settings_success(self, mock_timestamp, mock_file, mock_mkdir, settings_manager):
        """設定バックアップ成功のテスト"""
        mock_timestamp.return_value = "2024-01-01T12:00:00"

        with patch.object(settings_manager, "get_merged_settings") as mock_get:
            mock_get.return_value = {"provider": "openai", "model": "gpt-4"}

            backup_file = settings_manager.backup_current_settings()

            assert "ai_config_backup_2024-01-01T12-00-00.json" in str(backup_file)
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file.assert_called_once()

    @patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied"))
    @patch.object(SettingsManager, "get_merged_settings", return_value={"test": "data"})
    def test_backup_current_settings_error(self, mock_get, mock_mkdir, settings_manager):
        """設定バックアップ時のエラーテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.backup_current_settings()

        assert "設定のバックアップに失敗しました" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=False)
    def test_restore_from_backup_file_not_found(self, mock_exists, settings_manager):
        """バックアップファイルが存在しない場合の復元テスト"""
        backup_file = Path("/test/backup.json")

        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.restore_from_backup(backup_file)

        assert "バックアップファイルが見つかりません" in str(exc_info.value)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"settings": {"provider": "anthropic"}}')
    def test_restore_from_backup_success(self, mock_file, mock_exists, settings_manager):
        """バックアップからの復元成功のテスト"""
        backup_file = Path("/test/backup.json")

        with patch.object(settings_manager, "save_ai_settings") as mock_save:
            settings_manager.restore_from_backup(backup_file)

            mock_save.assert_called_once_with({"provider": "anthropic"})

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_restore_from_backup_json_error(self, mock_file, mock_exists, settings_manager):
        """バックアップ復元時のJSONエラーテスト"""
        backup_file = Path("/test/backup.json")

        with pytest.raises(ConfigurationError) as exc_info:
            settings_manager.restore_from_backup(backup_file)

        assert "バックアップからの復元に失敗しました" in str(exc_info.value)

    @patch("datetime.datetime")
    def test_get_current_timestamp(self, mock_datetime, settings_manager):
        """現在タイムスタンプ取得のテスト"""
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"

        timestamp = settings_manager._get_current_timestamp()

        assert timestamp == "2024-01-01T12:00:00"

    @patch("builtins.open", new_callable=mock_open)
    def test_save_toml_config_simple(self, mock_file, settings_manager):
        """シンプルなTOML設定保存のテスト"""
        config_file = Path("/test/config.toml")
        config_data = {"ai": {"provider": "openai", "model": "gpt-4", "temperature": 0.7, "enabled": True}}

        settings_manager._save_toml_config(config_file, config_data)

        mock_file.assert_called_once_with(config_file, "w", encoding="utf-8")
        written_content = mock_file().write.call_args[0][0]

        assert "[ai]" in written_content
        assert 'provider = "openai"' in written_content
        assert 'model = "gpt-4"' in written_content
        assert "temperature = 0.7" in written_content
        assert "enabled = true" in written_content

    @patch("builtins.open", new_callable=mock_open)
    def test_save_toml_config_with_subsections(self, mock_file, settings_manager):
        """サブセクション付きTOML設定保存のテスト"""
        config_file = Path("/test/config.toml")
        config_data = {"ai": {"provider": "openai", "openai": {"api_key": "test-key", "model": "gpt-4"}}}

        settings_manager._save_toml_config(config_file, config_data)

        written_content = mock_file().write.call_args[0][0]

        assert "[ai]" in written_content
        assert "[ai.openai]" in written_content
        assert 'api_key = "test-key"' in written_content

    def test_format_toml_value_string(self, settings_manager):
        """文字列値のTOMLフォーマットテスト"""
        result = settings_manager._format_toml_value("test")
        assert result == '"test"'

    def test_format_toml_value_boolean(self, settings_manager):
        """ブール値のTOMLフォーマットテスト"""
        assert settings_manager._format_toml_value(True) == "true"
        assert settings_manager._format_toml_value(False) == "false"

    def test_format_toml_value_number(self, settings_manager):
        """数値のTOMLフォーマットテスト"""
        assert settings_manager._format_toml_value(42) == "42"
        assert settings_manager._format_toml_value(3.14) == "3.14"

    def test_format_toml_value_list(self, settings_manager):
        """リスト値のTOMLフォーマットテスト"""
        result = settings_manager._format_toml_value(["a", "b", "c"])
        assert result == '["a", "b", "c"]'

        result = settings_manager._format_toml_value([1, 2, 3])
        assert result == "[1, 2, 3]"

        result = settings_manager._format_toml_value([True, False])
        assert result == "[true, false]"
