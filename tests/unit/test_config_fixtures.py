"""
設定フィクスチャのテスト

設定例データが正しく読み込まれることを確認するテスト
"""

from pathlib import Path

import pytest

from tests.fixtures.config_loader import (
    AI_CONFIG_JSON,
    AI_ENABLED_CONFIG,
    BASIC_CONFIG,
    ENV_TEST,
    MINIMAL_CONFIG,
    get_config_file_path,
    list_available_configs,
    load_env_file,
    load_json_config,
    load_toml_config,
)


class TestConfigLoader:
    """設定ローダーのテスト"""

    def test_list_available_configs(self):
        """利用可能な設定ファイル一覧の取得テスト"""
        configs = list_available_configs()

        assert isinstance(configs, dict)
        assert "toml" in configs
        assert "json" in configs
        assert "env" in configs
        assert "actrc" in configs

        # 基本的な設定ファイルが存在することを確認
        assert BASIC_CONFIG in configs["toml"]
        assert AI_ENABLED_CONFIG in configs["toml"]
        assert MINIMAL_CONFIG in configs["toml"]
        assert AI_CONFIG_JSON in configs["json"]

    def test_load_basic_toml_config(self):
        """基本TOML設定の読み込みテスト"""
        config = load_toml_config(BASIC_CONFIG)

        assert isinstance(config, dict)
        assert "ci-helper" in config

        ci_helper_config = config["ci-helper"]
        assert ci_helper_config["verbose"] is False
        assert ci_helper_config["log_dir"] == ".ci-helper/logs"
        assert ci_helper_config["cache_dir"] == ".ci-helper/cache"

    def test_load_ai_enabled_toml_config(self):
        """AI有効TOML設定の読み込みテスト"""
        config = load_toml_config(AI_ENABLED_CONFIG)

        assert isinstance(config, dict)
        assert "ci-helper" in config
        assert "ai" in config

        ai_config = config["ai"]
        assert ai_config["default_provider"] == "openai"
        assert ai_config["cache_enabled"] is True
        assert "providers" in ai_config
        assert "openai" in ai_config["providers"]
        assert "anthropic" in ai_config["providers"]

    def test_load_minimal_toml_config(self):
        """最小TOML設定の読み込みテスト"""
        config = load_toml_config(MINIMAL_CONFIG)

        assert isinstance(config, dict)
        assert "ci-helper" in config
        assert "ai" in config

        ci_helper_config = config["ci-helper"]
        assert ci_helper_config["verbose"] is False

        ai_config = config["ai"]
        assert ai_config["default_provider"] == "openai"

    def test_load_ai_json_config(self):
        """AI JSON設定の読み込みテスト"""
        config = load_json_config(AI_CONFIG_JSON)

        assert isinstance(config, dict)
        assert config["default_provider"] == "openai"
        assert config["cache_enabled"] is True
        assert "providers" in config
        assert "openai" in config["providers"]
        assert "anthropic" in config["providers"]
        assert "local" in config["providers"]

    def test_load_env_file(self):
        """環境変数ファイルの読み込みテスト"""
        env_vars = load_env_file(ENV_TEST)

        assert isinstance(env_vars, dict)
        assert "CI_HELPER_TEST_MODE" in env_vars
        assert env_vars["CI_HELPER_TEST_MODE"] == "1"
        assert "OPENAI_API_KEY" in env_vars
        assert env_vars["OPENAI_API_KEY"].startswith("sk-test-key")

    def test_get_config_file_path(self):
        """設定ファイルパスの取得テスト"""
        path = get_config_file_path(BASIC_CONFIG)

        assert isinstance(path, Path)
        assert path.exists()
        assert path.name == BASIC_CONFIG

    def test_file_not_found_error(self):
        """存在しないファイルのエラーテスト"""
        with pytest.raises(FileNotFoundError):
            load_toml_config("nonexistent.toml")

        with pytest.raises(FileNotFoundError):
            load_json_config("nonexistent.json")

        with pytest.raises(FileNotFoundError):
            load_env_file(".env.nonexistent")


class TestConfigValidation:
    """設定データの妥当性テスト"""

    def test_all_toml_configs_are_valid(self):
        """すべてのTOML設定ファイルが有効であることを確認"""
        configs = list_available_configs()

        for toml_file in configs["toml"]:
            if toml_file == "invalid_ci_helper.toml":
                # 無効な設定ファイルはスキップ
                continue

            try:
                config = load_toml_config(toml_file)
                assert isinstance(config, dict)
                print(f"✓ {toml_file} は有効な設定ファイルです")
            except Exception as e:
                pytest.fail(f"{toml_file} の読み込みに失敗: {e}")

    def test_all_json_configs_are_valid(self):
        """すべてのJSON設定ファイルが有効であることを確認"""
        configs = list_available_configs()

        for json_file in configs["json"]:
            try:
                config = load_json_config(json_file)
                assert isinstance(config, dict)
                print(f"✓ {json_file} は有効な設定ファイルです")
            except Exception as e:
                pytest.fail(f"{json_file} の読み込みに失敗: {e}")

    def test_ai_config_structure(self):
        """AI設定の構造が正しいことを確認"""
        config = load_json_config(AI_CONFIG_JSON)

        # 必須フィールドの確認
        required_fields = [
            "default_provider",
            "cache_enabled",
            "providers",
            "cost_limits",
        ]

        for field in required_fields:
            assert field in config, f"必須フィールド '{field}' が見つかりません"

        # プロバイダー設定の確認
        providers = config["providers"]
        for provider_name, provider_config in providers.items():
            assert "name" in provider_config
            assert "default_model" in provider_config
            assert "available_models" in provider_config
            assert isinstance(provider_config["available_models"], list)

    def test_config_consistency(self):
        """設定ファイル間の一貫性を確認"""
        # TOML設定とJSON設定で同じプロバイダーが定義されていることを確認
        toml_config = load_toml_config(AI_ENABLED_CONFIG)
        json_config = load_json_config(AI_CONFIG_JSON)

        toml_providers = set(toml_config["ai"]["providers"].keys())
        json_providers = set(json_config["providers"].keys())

        # 共通のプロバイダーが存在することを確認
        common_providers = toml_providers.intersection(json_providers)
        assert len(common_providers) > 0, "TOML設定とJSON設定で共通のプロバイダーが見つかりません"


class TestConfigIntegration:
    """設定統合テスト"""

    def test_config_with_ci_helper_class(self, temp_dir):
        """CI-Helper Configクラスとの統合テスト"""
        import shutil

        from ci_helper.utils.config import Config

        # 基本設定ファイルをテスト環境にコピー
        config_source = get_config_file_path(BASIC_CONFIG)
        config_dest = temp_dir / "ci-helper.toml"
        shutil.copy(config_source, config_dest)

        # Configクラスで読み込み
        config = Config(project_root=temp_dir, validate_security=False)

        # 設定値の確認
        assert config.get("verbose") is False
        assert config.get("log_dir") == ".ci-helper/logs"
        assert config.get("cache_dir") == ".ci-helper/cache"

        # 設定検証
        config.validate()

    def test_ai_config_with_ci_helper_class(self, temp_dir):
        """AI設定とCI-Helper Configクラスの統合テスト"""
        import shutil

        from ci_helper.utils.config import Config

        # AI有効設定ファイルをテスト環境にコピー
        config_source = get_config_file_path(AI_ENABLED_CONFIG)
        config_dest = temp_dir / "ci-helper.toml"
        shutil.copy(config_source, config_dest)

        # Configクラスで読み込み
        config = Config(project_root=temp_dir, validate_security=False)

        # AI設定値の確認
        assert config.get_default_ai_provider() == "openai"
        assert config.is_ai_cache_enabled() is True
        assert "openai" in config.get_available_ai_providers()
        assert "anthropic" in config.get_available_ai_providers()

        # AI設定検証
        config.validate_ai_config()
