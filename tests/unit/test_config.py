"""
設定管理のユニットテスト
"""

import os
from pathlib import Path

import pytest

from ci_helper.core.exceptions import ConfigurationError
from ci_helper.utils.config import Config


def test_default_config(temp_dir: Path):
    """デフォルト設定のテスト"""
    config = Config(project_root=temp_dir)
    
    assert config.get("log_dir") == ".ci-helper/logs"
    assert config.get("verbose") is False
    assert config.get("timeout_seconds") == 1800


def test_env_config_override(temp_dir: Path):
    """環境変数による設定上書きのテスト"""
    # 環境変数を設定
    os.environ["CI_HELPER_VERBOSE"] = "true"
    os.environ["CI_HELPER_TIMEOUT_SECONDS"] = "3600"
    
    try:
        config = Config(project_root=temp_dir)
        
        assert config.get("verbose") is True
        assert config.get("timeout_seconds") == 3600
    finally:
        # 環境変数をクリーンアップ
        os.environ.pop("CI_HELPER_VERBOSE", None)
        os.environ.pop("CI_HELPER_TIMEOUT_SECONDS", None)


def test_config_validation(temp_dir: Path):
    """設定検証のテスト"""
    config = Config(project_root=temp_dir)
    
    # 正常な設定では例外が発生しない
    config.validate()


def test_get_path(temp_dir: Path):
    """パス取得のテスト"""
    config = Config(project_root=temp_dir)
    
    log_path = config.get_path("log_dir")
    expected_path = temp_dir / ".ci-helper" / "logs"
    
    assert log_path == expected_path


def test_ensure_directories(temp_dir: Path):
    """ディレクトリ作成のテスト"""
    config = Config(project_root=temp_dir)
    
    config.ensure_directories()
    
    assert (temp_dir / ".ci-helper" / "logs").exists()
    assert (temp_dir / ".ci-helper" / "cache").exists()
    assert (temp_dir / ".ci-helper" / "reports").exists()