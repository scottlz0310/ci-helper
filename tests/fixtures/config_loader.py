"""
設定ファイルローダー

テスト用の設定ファイルを読み込むためのユーティリティ
"""

import json
import tomllib
from pathlib import Path
from typing import Any

# フィクスチャディレクトリのパス
FIXTURES_DIR = Path(__file__).parent
CONFIG_EXAMPLES_DIR = FIXTURES_DIR / "config_examples"


def load_toml_config(filename: str) -> dict[str, Any]:
    """TOML設定ファイルを読み込み

    Args:
        filename: 設定ファイル名

    Returns:
        設定データの辞書
    """
    config_path = CONFIG_EXAMPLES_DIR / filename
    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_json_config(filename: str) -> dict[str, Any]:
    """JSON設定ファイルを読み込み

    Args:
        filename: 設定ファイル名

    Returns:
        設定データの辞書
    """
    config_path = CONFIG_EXAMPLES_DIR / filename
    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def load_env_file(filename: str) -> dict[str, str]:
    """環境変数ファイルを読み込み

    Args:
        filename: 環境変数ファイル名

    Returns:
        環境変数の辞書
    """
    env_path = CONFIG_EXAMPLES_DIR / filename
    if not env_path.exists():
        raise FileNotFoundError(f"環境変数ファイルが見つかりません: {env_path}")

    env_vars = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    return env_vars


def load_actrc_file(filename: str) -> list[str]:
    """actrc設定ファイルを読み込み

    Args:
        filename: actrc設定ファイル名

    Returns:
        設定行のリスト
    """
    actrc_path = CONFIG_EXAMPLES_DIR / filename
    if not actrc_path.exists():
        raise FileNotFoundError(f"actrc設定ファイルが見つかりません: {actrc_path}")

    config_lines = []
    with open(actrc_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                config_lines.append(line)

    return config_lines


def get_config_file_path(filename: str) -> Path:
    """設定ファイルのパスを取得

    Args:
        filename: 設定ファイル名

    Returns:
        設定ファイルのパス
    """
    return CONFIG_EXAMPLES_DIR / filename


def list_available_configs() -> dict[str, list[str]]:
    """利用可能な設定ファイル一覧を取得

    Returns:
        設定ファイルタイプ別のファイル一覧
    """
    if not CONFIG_EXAMPLES_DIR.exists():
        return {}

    configs = {"toml": [], "json": [], "env": [], "actrc": []}

    for file_path in CONFIG_EXAMPLES_DIR.iterdir():
        if file_path.is_file():
            if file_path.suffix == ".toml":
                configs["toml"].append(file_path.name)
            elif file_path.suffix == ".json":
                configs["json"].append(file_path.name)
            elif file_path.name.startswith(".env"):
                configs["env"].append(file_path.name)
            elif file_path.name.startswith(".actrc"):
                configs["actrc"].append(file_path.name)

    return configs


# 便利な定数
BASIC_CONFIG = "basic_ci_helper.toml"
AI_ENABLED_CONFIG = "ai_enabled_ci_helper.toml"
MINIMAL_CONFIG = "minimal_ci_helper.toml"
MULTI_PROVIDER_CONFIG = "multi_provider_ci_helper.toml"
INVALID_CONFIG = "invalid_ci_helper.toml"
PATTERN_RECOGNITION_CONFIG = "pattern_recognition_ci_helper.toml"
AUTO_FIX_CONFIG = "auto_fix_ci_helper.toml"
LEARNING_ENABLED_CONFIG = "learning_enabled_ci_helper.toml"

AI_CONFIG_JSON = "ai_config.json"
TEST_CONFIG_JSON = "test_config.json"
PERFORMANCE_CONFIG_JSON = "performance_test_config.json"
ERROR_CONFIGS_JSON = "error_configs.json"

ENV_EXAMPLE = ".env.example"
ENV_TEST = ".env.test"

ACTRC_EXAMPLE = ".actrc.example"
ACTRC_BASIC = ".actrc.basic"
ACTRC_PRIVILEGED = ".actrc.privileged"
