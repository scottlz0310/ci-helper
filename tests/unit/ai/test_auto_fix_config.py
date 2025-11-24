"""
auto_fix_config.py のテスト

自動修正設定システムの機能をテストします。
"""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from ci_helper.ai.auto_fix_config import AutoFixConfigManager, ValidationError
from ci_helper.core.exceptions import ConfigurationError
from ci_helper.utils.config import Config


class TestAutoFixConfigManager:
    """AutoFixConfigManager のテストクラス"""

    @pytest.fixture
    def mock_config(self):
        """モック設定オブジェクト"""
        config = Mock(spec=Config)
        config.project_root = Path("/test/project")
        config.is_auto_fix_enabled.return_value = True
        config.get_auto_fix_confidence_threshold.return_value = 0.8
        config.get_auto_fix_risk_tolerance.return_value = "medium"
        config.is_backup_before_fix_enabled.return_value = True
        config.get_backup_retention_days.return_value = 7
        return config

    @pytest.fixture
    def config_manager(self, mock_config):
        """AutoFixConfigManager インスタンス"""
        return AutoFixConfigManager(mock_config)

    def test_init(self, mock_config):
        """初期化のテスト"""
        manager = AutoFixConfigManager(mock_config)

        assert manager.config == mock_config
        assert manager.auto_fix_config_dir == Path("/test/project/.ci-helper/auto_fix")
        assert manager.auto_fix_config_file == Path("/test/project/.ci-helper/auto_fix/config.json")

    def test_get_auto_fix_settings(self, config_manager):
        """自動修正設定取得のテスト"""
        settings = config_manager.get_auto_fix_settings()

        assert settings["enabled"] is True
        assert settings["confidence_threshold"] == 0.8
        assert settings["risk_tolerance"] == "medium"
        assert "backup_policy" in settings
        assert "approval_settings" in settings
        assert "safety_checks" in settings

    def test_get_backup_policy(self, config_manager):
        """バックアップポリシー取得のテスト"""
        policy = config_manager.get_backup_policy()

        assert policy["enabled"] is True
        assert policy["retention_days"] == 7
        assert policy["compression_enabled"] is True
        assert policy["max_backup_size_mb"] == 100
        assert "backup_location" in policy

    def test_get_approval_settings_low_risk_tolerance(self, config_manager):
        """低リスク許容度での承認設定テスト"""
        config_manager.config.get_auto_fix_risk_tolerance.return_value = "low"

        settings = config_manager.get_approval_settings()

        assert settings["require_approval_for_high_risk"] is True
        assert settings["require_approval_for_medium_risk"] is True
        assert settings["require_approval_for_low_risk"] is False
        assert settings["auto_approve_threshold"] == 0.8
        assert settings["timeout_seconds"] == 300

    def test_get_approval_settings_high_risk_tolerance(self, config_manager):
        """高リスク許容度での承認設定テスト"""
        config_manager.config.get_auto_fix_risk_tolerance.return_value = "high"

        settings = config_manager.get_approval_settings()

        assert settings["require_approval_for_high_risk"] is True
        assert settings["require_approval_for_medium_risk"] is False
        assert settings["require_approval_for_low_risk"] is False

    def test_get_safety_checks(self, config_manager):
        """安全性チェック設定取得のテスト"""
        checks = config_manager.get_safety_checks()

        assert checks["verify_before_apply"] is True
        assert checks["dry_run_enabled"] is True
        assert checks["rollback_on_failure"] is True
        assert checks["validate_file_permissions"] is True
        assert checks["check_git_status"] is True
        assert isinstance(checks["protected_files"], list)

    def test_get_protected_files(self, config_manager):
        """保護ファイルリスト取得のテスト"""
        protected_files = config_manager.get_protected_files()

        assert ".git/*" in protected_files
        assert "*.key" in protected_files
        assert "*.pem" in protected_files
        assert ".env" in protected_files
        assert "secrets/*" in protected_files

    def test_validate_fix_request_valid(self, config_manager):
        """有効な修正リクエストの検証テスト"""
        fix_request = {"confidence": 0.9, "risk_level": "low", "files_to_modify": ["test.py"]}

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is True
        assert result["confidence"] == 0.9
        assert result["risk_level"] == "low"
        assert result["can_auto_apply"] is True
        assert len(result["errors"]) == 0

    def test_validate_fix_request_missing_fields(self, config_manager):
        """必須フィールド不足の修正リクエスト検証テスト"""
        fix_request = {
            "confidence": 0.9
            # risk_level と files_to_modify が不足
        }

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is False
        assert len(result["errors"]) == 2
        assert any("risk_level" in error for error in result["errors"])
        assert any("files_to_modify" in error for error in result["errors"])

    def test_validate_fix_request_invalid_confidence(self, config_manager):
        """無効な信頼度の修正リクエスト検証テスト"""
        fix_request = {
            "confidence": 1.5,  # 無効な値
            "risk_level": "low",
            "files_to_modify": ["test.py"],
        }

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is False
        assert any("信頼度が無効" in error for error in result["errors"])

    def test_validate_fix_request_invalid_risk_level(self, config_manager):
        """無効なリスクレベルの修正リクエスト検証テスト"""
        fix_request = {
            "confidence": 0.8,
            "risk_level": "invalid",  # 無効な値
            "files_to_modify": ["test.py"],
        }

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is False
        assert any("無効なリスクレベル" in error for error in result["errors"])

    def test_validate_fix_request_protected_file(self, config_manager):
        """保護ファイルを含む修正リクエスト検証テスト"""
        fix_request = {
            "confidence": 0.9,
            "risk_level": "low",
            "files_to_modify": ["test.py", "secrets/api.key"],  # 保護ファイルを含む
        }

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is True
        assert result["requires_approval"] is True
        assert len(result["warnings"]) > 0
        assert any("保護されたファイル" in warning for warning in result["warnings"])

    def test_validate_fix_request_low_confidence(self, config_manager):
        """低信頼度の修正リクエスト検証テスト"""
        config_manager.config.get_auto_fix_confidence_threshold.return_value = 0.8

        fix_request = {
            "confidence": 0.7,  # 閾値より低い
            "risk_level": "low",
            "files_to_modify": ["test.py"],
        }

        result = config_manager.validate_fix_request(fix_request)

        assert result["valid"] is True
        assert result["can_auto_apply"] is False

    def test_create_fix_execution_plan_valid(self, config_manager):
        """有効な修正実行計画作成のテスト"""
        fix_request = {
            "confidence": 0.9,
            "risk_level": "low",
            "files_to_modify": ["test.py"],
            "fix_steps": ["step1", "step2"],
        }

        plan = config_manager.create_fix_execution_plan(fix_request)

        assert "fix_id" in plan
        assert "created_at" in plan
        assert "validation_result" in plan
        assert "execution_steps" in plan
        assert "backup_plan" in plan
        assert "rollback_plan" in plan
        assert len(plan["execution_steps"]) > 0

    def test_create_fix_execution_plan_invalid_request(self, config_manager):
        """無効な修正リクエストでの実行計画作成テスト"""
        fix_request = {
            "confidence": 1.5,  # 無効な値
            "risk_level": "low",
            "files_to_modify": ["test.py"],
        }

        with pytest.raises(ValidationError):
            config_manager.create_fix_execution_plan(fix_request)

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_save_auto_fix_settings_success(self, mock_mkdir, mock_file, config_manager):
        """自動修正設定保存成功のテスト"""
        settings = {"enabled": True, "confidence_threshold": 0.8, "risk_tolerance": "medium"}

        config_manager.save_auto_fix_settings(settings)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once()

        # ファイルが書き込まれたことを確認
        assert mock_file().write.called

        # 書き込まれた内容を結合して確認
        write_calls = mock_file().write.call_args_list
        written_content = "".join(call[0][0] for call in write_calls)

        # JSON形式の文字列が書き込まれたことを確認
        assert '"version": "1.0"' in written_content
        assert '"enabled": true' in written_content
        assert '"confidence_threshold": 0.8' in written_content
        assert '"risk_tolerance": "medium"' in written_content

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    @patch("pathlib.Path.mkdir")
    def test_save_auto_fix_settings_permission_error(self, mock_mkdir, mock_file, config_manager):
        """自動修正設定保存時の権限エラーテスト"""
        settings = {"enabled": True, "confidence_threshold": 0.8, "risk_tolerance": "medium"}

        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.save_auto_fix_settings(settings)

        assert "保存に失敗しました" in str(exc_info.value)

    def test_save_auto_fix_settings_invalid_settings(self, config_manager):
        """無効な設定での保存テスト"""
        settings = {
            "enabled": True,
            "confidence_threshold": 1.5,  # 無効な値
            "risk_tolerance": "medium",
        }

        with pytest.raises(ValidationError):
            config_manager.save_auto_fix_settings(settings)

    @patch("pathlib.Path.exists", return_value=False)
    def test_load_auto_fix_settings_no_file(self, mock_exists, config_manager):
        """設定ファイルが存在しない場合の読み込みテスト"""
        settings = config_manager.load_auto_fix_settings()

        # デフォルト設定が返されることを確認
        assert "enabled" in settings
        assert "confidence_threshold" in settings
        assert "risk_tolerance" in settings

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"version": "1.0", "settings": {"enabled": false}}')
    def test_load_auto_fix_settings_success(self, mock_file, mock_exists, config_manager):
        """設定ファイル読み込み成功のテスト"""
        settings = config_manager.load_auto_fix_settings()

        assert settings["enabled"] is False

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_load_auto_fix_settings_json_error(self, mock_file, mock_exists, config_manager):
        """設定ファイル読み込み時のJSONエラーテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.load_auto_fix_settings()

        assert "読み込みに失敗しました" in str(exc_info.value)

    def test_get_backup_directory(self, config_manager):
        """バックアップディレクトリ取得のテスト"""
        backup_dir = config_manager.get_backup_directory()

        assert backup_dir == Path("/test/project/.ci-helper/backups")

    @patch("pathlib.Path.exists", return_value=False)
    def test_cleanup_old_backups_no_directory(self, mock_exists, config_manager):
        """バックアップディレクトリが存在しない場合のクリーンアップテスト"""
        result = config_manager.cleanup_old_backups()

        assert result["cleaned_files"] == 0
        assert result["freed_space_mb"] == 0.0
        assert len(result["errors"]) == 0

    def test_is_protected_file(self, config_manager):
        """保護ファイル判定のテスト"""
        protected_patterns = ["*.key", "secrets/*", ".env"]

        assert config_manager._is_protected_file("api.key", protected_patterns) is True
        assert config_manager._is_protected_file("secrets/config.json", protected_patterns) is True
        assert config_manager._is_protected_file(".env", protected_patterns) is True
        assert config_manager._is_protected_file("normal.py", protected_patterns) is False

    def test_get_risk_assessment_criteria(self, config_manager):
        """リスク評価基準取得のテスト"""
        criteria = config_manager.get_risk_assessment_criteria()

        assert "low_risk" in criteria
        assert "medium_risk" in criteria
        assert "high_risk" in criteria

        assert criteria["low_risk"]["auto_approve"] is True
        assert criteria["medium_risk"]["auto_approve"] is False
        assert criteria["high_risk"]["auto_approve"] is False

    def test_validate_auto_fix_settings_valid(self, config_manager):
        """有効な自動修正設定の検証テスト"""
        settings = {"enabled": True, "confidence_threshold": 0.8, "risk_tolerance": "medium"}

        # 例外が発生しないことを確認
        config_manager._validate_auto_fix_settings(settings)

    def test_validate_auto_fix_settings_missing_field(self, config_manager):
        """必須フィールド不足の設定検証テスト"""
        settings = {
            "enabled": True,
            "confidence_threshold": 0.8,
            # risk_tolerance が不足
        }

        with pytest.raises(ValidationError) as exc_info:
            config_manager._validate_auto_fix_settings(settings)

        assert "risk_tolerance" in str(exc_info.value)

    def test_validate_auto_fix_settings_invalid_confidence(self, config_manager):
        """無効な信頼度閾値の設定検証テスト"""
        settings = {
            "enabled": True,
            "confidence_threshold": 1.5,  # 無効な値
            "risk_tolerance": "medium",
        }

        with pytest.raises(ValidationError) as exc_info:
            config_manager._validate_auto_fix_settings(settings)

        assert "信頼度閾値が無効" in str(exc_info.value)

    def test_validate_auto_fix_settings_invalid_risk_tolerance(self, config_manager):
        """無効なリスク許容度の設定検証テスト"""
        settings = {
            "enabled": True,
            "confidence_threshold": 0.8,
            "risk_tolerance": "invalid",  # 無効な値
        }

        with pytest.raises(ValidationError) as exc_info:
            config_manager._validate_auto_fix_settings(settings)

        assert "無効なリスク許容度" in str(exc_info.value)
