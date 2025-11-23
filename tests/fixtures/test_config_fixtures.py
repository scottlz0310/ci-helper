"""
テスト設定フィクスチャ

テストで使用される設定データを提供するフィクスチャ
"""

from pathlib import Path
from typing import Any

import pytest
from ci_helper.ai.models import AIConfig, ProviderConfig
from ci_helper.utils.config import Config

from .config_loader import (
    AI_CONFIG_JSON,
    AI_ENABLED_CONFIG,
    BASIC_CONFIG,
    ENV_TEST,
    MINIMAL_CONFIG,
    TEST_CONFIG_JSON,
    get_config_file_path,
    load_env_file,
    load_json_config,
    load_toml_config,
)


@pytest.fixture
def basic_config_data() -> dict[str, Any]:
    """基本的な設定データを提供"""
    return load_toml_config(BASIC_CONFIG)


@pytest.fixture
def ai_enabled_config_data() -> dict[str, Any]:
    """AI機能を有効にした設定データを提供"""
    return load_toml_config(AI_ENABLED_CONFIG)


@pytest.fixture
def minimal_config_data() -> dict[str, Any]:
    """最小限の設定データを提供"""
    return load_toml_config(MINIMAL_CONFIG)


@pytest.fixture
def ai_config_json_data() -> dict[str, Any]:
    """AI設定のJSONデータを提供"""
    return load_json_config(AI_CONFIG_JSON)


@pytest.fixture
def test_config_json_data() -> dict[str, Any]:
    """テスト用設定のJSONデータを提供"""
    return load_json_config(TEST_CONFIG_JSON)


@pytest.fixture
def test_env_vars() -> dict[str, str]:
    """テスト用環境変数を提供"""
    return load_env_file(ENV_TEST)


@pytest.fixture
def basic_config_file_path() -> Path:
    """基本設定ファイルのパスを提供"""
    return get_config_file_path(BASIC_CONFIG)


@pytest.fixture
def ai_enabled_config_file_path() -> Path:
    """AI有効設定ファイルのパスを提供"""
    return get_config_file_path(AI_ENABLED_CONFIG)


@pytest.fixture
def sample_config_with_data(temp_dir: Path, basic_config_data: dict[str, Any]) -> Config:
    """設定データを含むConfigオブジェクトを提供"""
    config = Config(project_root=temp_dir, validate_security=False)
    # 設定データを直接設定
    config._config.update(basic_config_data.get("ci-helper", {}))
    if "ai" in basic_config_data:
        config._ai_config.update(basic_config_data["ai"])
    return config


@pytest.fixture
def mock_ai_config_with_data(ai_config_json_data: dict[str, Any]) -> AIConfig:
    """実際のデータを持つAIConfigモックを提供"""
    providers = {}
    for name, provider_data in ai_config_json_data["providers"].items():
        providers[name] = ProviderConfig(**provider_data)

    return AIConfig(
        default_provider=ai_config_json_data["default_provider"],
        cache_enabled=ai_config_json_data["cache_enabled"],
        cache_ttl_hours=ai_config_json_data["cache_ttl_hours"],
        interactive_timeout=ai_config_json_data["interactive_timeout"],
        streaming_enabled=ai_config_json_data["streaming_enabled"],
        security_checks_enabled=ai_config_json_data["security_checks_enabled"],
        providers=providers,
        cost_limits=ai_config_json_data["cost_limits"],
        prompt_templates=ai_config_json_data["prompt_templates"],
    )


@pytest.fixture
def config_with_all_features(temp_dir: Path) -> Config:
    """全機能を有効にした設定を提供"""
    config_data = load_toml_config(AI_ENABLED_CONFIG)
    config = Config(project_root=temp_dir, validate_security=False)

    # 基本設定を更新
    if "ci-helper" in config_data:
        config._config.update(config_data["ci-helper"])

    # AI設定を更新
    if "ai" in config_data:
        config._ai_config.update(config_data["ai"])

    return config


@pytest.fixture
def mock_config_dict() -> dict[str, Any]:
    """辞書形式のモック設定を提供"""
    return {
        "default_provider": "openai",
        "cache_enabled": True,
        "providers": {
            "openai": {
                "name": "openai",
                "api_key": "sk-test-key-123",
                "default_model": "gpt-4o",
                "available_models": ["gpt-4o", "gpt-4o-mini"],
                "timeout_seconds": 30,
                "max_retries": 3,
            }
        },
        "cost_limits": {
            "monthly_usd": 50.0,
            "per_request_usd": 1.0,
        },
    }


@pytest.fixture
def config_file_paths() -> dict[str, Path]:
    """各種設定ファイルのパスを提供"""
    return {
        "basic": get_config_file_path(BASIC_CONFIG),
        "ai_enabled": get_config_file_path(AI_ENABLED_CONFIG),
        "minimal": get_config_file_path(MINIMAL_CONFIG),
        "ai_config_json": get_config_file_path(AI_CONFIG_JSON),
        "test_config_json": get_config_file_path(TEST_CONFIG_JSON),
    }


@pytest.fixture
def config_validation_test_cases() -> list[dict[str, Any]]:
    """設定検証テスト用のテストケースを提供"""
    return [
        {
            "name": "valid_basic_config",
            "config_file": BASIC_CONFIG,
            "should_pass": True,
            "expected_provider": None,
        },
        {
            "name": "valid_ai_config",
            "config_file": AI_ENABLED_CONFIG,
            "should_pass": True,
            "expected_provider": "openai",
        },
        {
            "name": "minimal_config",
            "config_file": MINIMAL_CONFIG,
            "should_pass": True,
            "expected_provider": "openai",
        },
    ]


@pytest.fixture
def ai_provider_test_configs() -> dict[str, dict[str, Any]]:
    """AIプロバイダーテスト用の設定を提供"""
    return {
        "openai_only": {
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "name": "openai",
                    "api_key": "sk-test-key-123",
                    "default_model": "gpt-4o",
                    "available_models": ["gpt-4o", "gpt-4o-mini"],
                    "timeout_seconds": 30,
                    "max_retries": 3,
                }
            },
        },
        "anthropic_only": {
            "default_provider": "anthropic",
            "providers": {
                "anthropic": {
                    "name": "anthropic",
                    "api_key": "sk-ant-test-key-123",
                    "default_model": "claude-3-5-sonnet-20241022",
                    "available_models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                    "timeout_seconds": 30,
                    "max_retries": 3,
                }
            },
        },
        "local_only": {
            "default_provider": "local",
            "providers": {
                "local": {
                    "name": "local",
                    "api_key": "",
                    "default_model": "llama3.2",
                    "available_models": ["llama3.2", "codellama"],
                    "base_url": "http://localhost:11434",
                    "timeout_seconds": 60,
                    "max_retries": 2,
                }
            },
        },
    }


@pytest.fixture
def config_error_test_cases() -> list[dict[str, Any]]:
    """設定エラーテスト用のテストケースを提供"""
    return [
        {
            "name": "invalid_toml_syntax",
            "config_content": "[invalid_section\n# 構文エラー",
            "expected_error": "設定ファイルの読み込みに失敗しました",
        },
        {
            "name": "missing_default_provider",
            "config_content": """
[ai]
providers = {}
""",
            "expected_error": "デフォルトAIプロバイダー",
        },
        {
            "name": "invalid_model_selection",
            "config_content": """
[ai]
default_provider = "openai"

[ai.providers.openai]
default_model = "nonexistent-model"
available_models = ["gpt-4o"]
""",
            "expected_error": "デフォルトモデル",
        },
    ]


@pytest.fixture
def performance_test_config() -> dict[str, Any]:
    """パフォーマンステスト用の設定を提供"""
    return load_json_config("performance_test_config.json")


@pytest.fixture
def security_test_configs() -> dict[str, str]:
    """セキュリティテスト用の設定を提供"""
    return {
        "with_secrets": """
[ai]
default_provider = "openai"

[ai.providers.openai]
api_key = "sk-1234567890abcdef"  # セキュリティ問題
""",
        "safe_config": """
[ai]
default_provider = "openai"

[ai.providers.openai]
# APIキーは環境変数から取得
default_model = "gpt-4o"
""",
    }
