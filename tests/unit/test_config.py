"""
設定管理のユニットテスト
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ci_helper.core.exceptions import ConfigurationError, SecurityError
from ci_helper.utils.config import Config


class TestConfigFileLoading:
    """設定ファイル読み込みのテスト"""

    def test_default_config(self, temp_dir: Path):
        """デフォルト設定のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        assert config.get("log_dir") == ".ci-helper/logs"
        assert config.get("cache_dir") == ".ci-helper/cache"
        assert config.get("reports_dir") == ".ci-helper/reports"
        assert config.get("context_lines") == 3
        assert config.get("max_log_size_mb") == 100
        assert config.get("max_cache_size_mb") == 500
        assert config.get("act_image") == "ghcr.io/catthehacker/ubuntu:full-24.04"
        assert config.get("timeout_seconds") == 1800
        assert config.get("verbose") is False
        assert config.get("save_logs") is True

    def test_project_config_file_loading(self, temp_dir: Path):
        """プロジェクト設定ファイル読み込みのテスト"""
        # 設定ファイルを作成
        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("""
[ci-helper]
verbose = true
timeout_seconds = 3600
log_dir = "custom/logs"
context_lines = 5
""")

        config = Config(project_root=temp_dir, validate_security=False)

        assert config.get("verbose") is True
        assert config.get("timeout_seconds") == 3600
        assert config.get("log_dir") == "custom/logs"
        assert config.get("context_lines") == 5
        # デフォルト値は保持される
        assert config.get("cache_dir") == ".ci-helper/cache"

    def test_invalid_toml_file(self, temp_dir: Path):
        """無効なTOMLファイルのテスト"""
        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("invalid toml content [")

        with pytest.raises(ConfigurationError) as exc_info:
            Config(project_root=temp_dir, validate_security=False)

        assert "設定ファイルの読み込みに失敗しました" in str(exc_info.value)

    def test_missing_config_file(self, temp_dir: Path):
        """設定ファイルが存在しない場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # デフォルト設定が使用される
        assert config.get("verbose") is False
        assert config.get("timeout_seconds") == 1800


class TestEnvironmentVariables:
    """環境変数による設定上書きのテスト"""

    def test_env_config_override_boolean(self, temp_dir: Path):
        """環境変数によるブール値設定上書きのテスト"""
        test_cases = [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for env_value, expected in test_cases:
            os.environ["CI_HELPER_VERBOSE"] = env_value

            try:
                config = Config(project_root=temp_dir, validate_security=False)
                assert config.get("verbose") is expected
            finally:
                os.environ.pop("CI_HELPER_VERBOSE", None)

    def test_env_config_override_integer(self, temp_dir: Path):
        """環境変数による整数値設定上書きのテスト"""
        os.environ["CI_HELPER_TIMEOUT_SECONDS"] = "3600"
        os.environ["CI_HELPER_CONTEXT_LINES"] = "10"

        try:
            config = Config(project_root=temp_dir, validate_security=False)

            assert config.get("timeout_seconds") == 3600
            assert config.get("context_lines") == 10
        finally:
            os.environ.pop("CI_HELPER_TIMEOUT_SECONDS", None)
            os.environ.pop("CI_HELPER_CONTEXT_LINES", None)

    def test_env_config_override_string(self, temp_dir: Path):
        """環境変数による文字列設定上書きのテスト"""
        os.environ["CI_HELPER_LOG_DIR"] = "custom/logs"
        os.environ["CI_HELPER_ACT_IMAGE"] = "custom:image"

        try:
            config = Config(project_root=temp_dir, validate_security=False)

            assert config.get("log_dir") == "custom/logs"
            assert config.get("act_image") == "custom:image"
        finally:
            os.environ.pop("CI_HELPER_LOG_DIR", None)
            os.environ.pop("CI_HELPER_ACT_IMAGE", None)

    def test_invalid_env_integer(self, temp_dir: Path):
        """無効な整数値環境変数のテスト"""
        os.environ["CI_HELPER_TIMEOUT_SECONDS"] = "invalid"

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                Config(project_root=temp_dir, validate_security=False)

            assert "環境変数 CI_HELPER_TIMEOUT_SECONDS の値が無効です" in str(exc_info.value)
        finally:
            os.environ.pop("CI_HELPER_TIMEOUT_SECONDS", None)


class TestPriorityControl:
    """優先順位制御のテスト"""

    def test_priority_order(self, temp_dir: Path):
        """設定の優先順位テスト（環境変数 > 設定ファイル > デフォルト）"""
        # 設定ファイルを作成
        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("""
[ci-helper]
verbose = true
timeout_seconds = 2400
log_dir = "config/logs"
""")

        # 環境変数を設定（一部のみ）
        os.environ["CI_HELPER_VERBOSE"] = "false"
        os.environ["CI_HELPER_CONTEXT_LINES"] = "7"

        try:
            config = Config(project_root=temp_dir, validate_security=False)

            # 環境変数が最優先
            assert config.get("verbose") is False
            assert config.get("context_lines") == 7

            # 環境変数がない場合は設定ファイル
            assert config.get("timeout_seconds") == 2400
            assert config.get("log_dir") == "config/logs"

            # 設定ファイルにもない場合はデフォルト
            assert config.get("cache_dir") == ".ci-helper/cache"
        finally:
            os.environ.pop("CI_HELPER_VERBOSE", None)
            os.environ.pop("CI_HELPER_CONTEXT_LINES", None)

    def test_env_overrides_config_file(self, temp_dir: Path):
        """環境変数が設定ファイルを上書きすることのテスト"""
        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("""
[ci-helper]
verbose = true
timeout_seconds = 1200
""")

        os.environ["CI_HELPER_VERBOSE"] = "false"

        try:
            config = Config(project_root=temp_dir, validate_security=False)

            # 環境変数が設定ファイルを上書き
            assert config.get("verbose") is False
            # 環境変数がない項目は設定ファイルの値
            assert config.get("timeout_seconds") == 1200
        finally:
            os.environ.pop("CI_HELPER_VERBOSE", None)


class TestValidation:
    """検証機能のテスト"""

    def test_valid_config_validation(self, temp_dir: Path):
        """正常な設定の検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 正常な設定では例外が発生しない
        config.validate()

    def test_missing_required_config(self, temp_dir: Path):
        """必須設定が不足している場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 必須設定を削除
        config._config["log_dir"] = None

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "必須設定 'log_dir' が設定されていません" in str(exc_info.value)

    def test_invalid_timeout_validation(self, temp_dir: Path):
        """無効なタイムアウト設定の検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 無効なタイムアウト値を設定
        config._config["timeout_seconds"] = 0

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "タイムアウト設定が無効です" in str(exc_info.value)

    def test_invalid_log_size_validation(self, temp_dir: Path):
        """無効なログサイズ設定の検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 無効なログサイズを設定
        config._config["max_log_size_mb"] = -1

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "最大ログサイズ設定が無効です" in str(exc_info.value)

    def test_negative_timeout_validation(self, temp_dir: Path):
        """負のタイムアウト値の検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        config._config["timeout_seconds"] = -100

        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "タイムアウト設定が無効です: -100" in str(exc_info.value)


class TestUtilityMethods:
    """ユーティリティメソッドのテスト"""

    def test_get_method(self, temp_dir: Path):
        """get メソッドのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 存在するキー
        assert config.get("verbose") is False

        # 存在しないキー（デフォルト値なし）
        assert config.get("nonexistent") is None

        # 存在しないキー（デフォルト値あり）
        assert config.get("nonexistent", "default") == "default"

    def test_get_path_method(self, temp_dir: Path):
        """get_path メソッドのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # 相対パスが絶対パスに変換される
        log_path = config.get_path("log_dir")
        expected_path = temp_dir / ".ci-helper" / "logs"
        assert log_path == expected_path

        # 絶対パスはそのまま
        config._config["log_dir"] = "/absolute/path"
        log_path = config.get_path("log_dir")
        assert log_path == Path("/absolute/path")

    def test_get_path_missing_key(self, temp_dir: Path):
        """存在しないパス設定キーのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        with pytest.raises(ConfigurationError) as exc_info:
            config.get_path("nonexistent_path")

        assert "パス設定 'nonexistent_path' が見つかりません" in str(exc_info.value)

    def test_ensure_directories(self, temp_dir: Path):
        """ディレクトリ作成のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        config.ensure_directories()

        assert (temp_dir / ".ci-helper" / "logs").exists()
        assert (temp_dir / ".ci-helper" / "cache").exists()
        assert (temp_dir / ".ci-helper" / "reports").exists()

    def test_dict_like_access(self, temp_dir: Path):
        """辞書風アクセスのテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # __getitem__
        assert config["verbose"] is False

        # __contains__
        assert "verbose" in config
        assert "nonexistent" not in config


class TestSecurityValidation:
    """セキュリティ検証のテスト"""

    @patch("ci_helper.core.security.SecurityValidator")
    def test_security_validation_enabled(self, mock_security_validator, temp_dir: Path):
        """セキュリティ検証が有効な場合のテスト"""
        mock_validator_instance = Mock()
        mock_security_validator.return_value = mock_validator_instance

        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("""
[ci-helper]
verbose = true
""")

        config = Config(project_root=temp_dir, validate_security=True)

        # SecurityValidatorが作成される
        mock_security_validator.assert_called_once()
        assert hasattr(config, "security_validator")

    def test_security_validation_disabled(self, temp_dir: Path):
        """セキュリティ検証が無効な場合のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)

        # SecurityValidatorが作成されない
        assert not hasattr(config, "security_validator")

    @patch("ci_helper.core.security.SecurityValidator")
    def test_config_security_error(self, mock_security_validator, temp_dir: Path):
        """設定ファイルのセキュリティエラーのテスト"""
        mock_validator_instance = Mock()
        mock_validator_instance.validate_config_security.return_value = {"overall_valid": False, "critical_issues": 1}
        mock_security_validator.return_value = mock_validator_instance

        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text("""
[ci-helper]
api_key = "sk-1234567890"
""")

        with pytest.raises(SecurityError) as exc_info:
            Config(project_root=temp_dir, validate_security=True)

        assert "重大なセキュリティ問題が検出されました" in str(exc_info.value)

    @patch("ci_helper.core.security.SecurityValidator")
    def test_validate_all_config_files(self, mock_security_validator, temp_dir: Path):
        """全設定ファイル検証のテスト"""
        mock_validator_instance = Mock()
        mock_validator_instance.validate_config_security.return_value = {"overall_valid": True, "critical_issues": 0}
        mock_security_validator.return_value = mock_validator_instance

        # 複数の設定ファイルを作成
        (temp_dir / "ci-helper.toml").write_text("[ci-helper]\nverbose = true")
        (temp_dir / ".env").write_text("API_KEY=test")
        (temp_dir / ".actrc").write_text("-P ubuntu-latest=ubuntu:latest")

        config = Config(project_root=temp_dir, validate_security=True)
        config.validate_all_config_files()

        # 3つのファイルが検証される
        mock_validator_instance.validate_config_security.assert_called()
        call_args = mock_validator_instance.validate_config_security.call_args[0][0]
        assert len(call_args) == 3

    def test_validate_all_config_files_no_security(self, temp_dir: Path):
        """セキュリティ検証無効時の全設定ファイル検証テスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        result = config.validate_all_config_files()

        assert result["overall_valid"] is True
        assert "セキュリティ検証が無効になっています" in result["message"]

    def test_get_secret_recommendations(self, temp_dir: Path):
        """シークレット管理推奨事項のテスト"""
        config = Config(project_root=temp_dir, validate_security=False)
        recommendations = config.get_secret_recommendations()

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert Any("環境変数の使用" in rec for rec in recommendations)
        assert Any("OPENAI_API_KEY" in rec for rec in recommendations)
