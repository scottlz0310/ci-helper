"""
エラーシナリオ用pytestフィクスチャ

テストで簡単にエラーシナリオを使用するためのフィクスチャ定義
"""

from collections.abc import Callable
from typing import Any

import pytest

from .loader import (
    get_cache_corruption_scenario,
    get_docker_not_running_scenario,
    get_file_not_found_scenario,
    get_missing_api_key_scenario,
    get_network_timeout_scenario,
    get_pattern_not_found_scenario,
    get_secret_detection_scenario,
    get_session_timeout_scenario,
    get_token_limit_scenario,
    load_all_error_scenarios,
    load_error_scenario,
)

# カテゴリ別フィクスチャ


@pytest.fixture
def network_error_scenarios() -> dict[str, dict[str, Any]]:
    """ネットワークエラーシナリオ一覧"""
    return load_all_error_scenarios("network_errors")


@pytest.fixture
def configuration_error_scenarios() -> dict[str, dict[str, Any]]:
    """設定エラーシナリオ一覧"""
    return load_all_error_scenarios("configuration_errors")


@pytest.fixture
def ai_processing_error_scenarios() -> dict[str, dict[str, Any]]:
    """AI処理エラーシナリオ一覧"""
    return load_all_error_scenarios("ai_processing_errors")


@pytest.fixture
def file_system_error_scenarios() -> dict[str, dict[str, Any]]:
    """ファイルシステムエラーシナリオ一覧"""
    return load_all_error_scenarios("file_system_errors")


@pytest.fixture
def ci_execution_error_scenarios() -> dict[str, dict[str, Any]]:
    """CI実行エラーシナリオ一覧"""
    return load_all_error_scenarios("ci_execution_errors")


@pytest.fixture
def cache_error_scenarios() -> dict[str, dict[str, Any]]:
    """キャッシュエラーシナリオ一覧"""
    return load_all_error_scenarios("cache_errors")


@pytest.fixture
def interactive_session_error_scenarios() -> dict[str, dict[str, Any]]:
    """対話セッションエラーシナリオ一覧"""
    return load_all_error_scenarios("interactive_session_errors")


@pytest.fixture
def pattern_recognition_error_scenarios() -> dict[str, dict[str, Any]]:
    """パターン認識エラーシナリオ一覧"""
    return load_all_error_scenarios("pattern_recognition_errors")


@pytest.fixture
def security_error_scenarios() -> dict[str, dict[str, Any]]:
    """セキュリティエラーシナリオ一覧"""
    return load_all_error_scenarios("security_errors")


# 個別シナリオフィクスチャ


@pytest.fixture
def network_timeout_scenario() -> dict[str, Any]:
    """ネットワークタイムアウトシナリオ"""
    return get_network_timeout_scenario()


@pytest.fixture
def connection_error_scenario() -> dict[str, Any]:
    """接続エラーシナリオ"""
    return load_error_scenario("network_errors", "connection_error")


@pytest.fixture
def rate_limit_error_scenario() -> dict[str, Any]:
    """レート制限エラーシナリオ"""
    return load_error_scenario("network_errors", "rate_limit_error")


@pytest.fixture
def missing_api_key_scenario() -> dict[str, Any]:
    """APIキー未設定シナリオ"""
    return get_missing_api_key_scenario()


@pytest.fixture
def invalid_api_key_scenario() -> dict[str, Any]:
    """無効なAPIキーシナリオ"""
    return load_error_scenario("configuration_errors", "invalid_api_key_format")


@pytest.fixture
def unsupported_provider_scenario() -> dict[str, Any]:
    """サポートされていないプロバイダーシナリオ"""
    return load_error_scenario("configuration_errors", "unsupported_provider")


@pytest.fixture
def token_limit_exceeded_scenario() -> dict[str, Any]:
    """トークン制限超過シナリオ"""
    return get_token_limit_scenario()


@pytest.fixture
def cost_limit_exceeded_scenario() -> dict[str, Any]:
    """コスト制限超過シナリオ"""
    return load_error_scenario("ai_processing_errors", "cost_limit_exceeded")


@pytest.fixture
def model_overloaded_scenario() -> dict[str, Any]:
    """モデル過負荷シナリオ"""
    return load_error_scenario("ai_processing_errors", "model_overloaded")


@pytest.fixture
def log_file_not_found_scenario() -> dict[str, Any]:
    """ログファイル未発見シナリオ"""
    return get_file_not_found_scenario()


@pytest.fixture
def permission_denied_scenario() -> dict[str, Any]:
    """権限拒否シナリオ"""
    return load_error_scenario("file_system_errors", "permission_denied_log_access")


@pytest.fixture
def disk_space_full_scenario() -> dict[str, Any]:
    """ディスク容量不足シナリオ"""
    return load_error_scenario("file_system_errors", "disk_space_full")


@pytest.fixture
def act_not_installed_scenario() -> dict[str, Any]:
    """act未インストールシナリオ"""
    return load_error_scenario("ci_execution_errors", "act_not_installed")


@pytest.fixture
def docker_not_running_scenario() -> dict[str, Any]:
    """Docker未起動シナリオ"""
    return get_docker_not_running_scenario()


@pytest.fixture
def workflow_not_found_scenario() -> dict[str, Any]:
    """ワークフローファイル未発見シナリオ"""
    return load_error_scenario("ci_execution_errors", "workflow_file_not_found")


@pytest.fixture
def cache_corruption_scenario() -> dict[str, Any]:
    """キャッシュ破損シナリオ"""
    return get_cache_corruption_scenario()


@pytest.fixture
def cache_size_limit_scenario() -> dict[str, Any]:
    """キャッシュサイズ制限シナリオ"""
    return load_error_scenario("cache_errors", "cache_size_limit_exceeded")


@pytest.fixture
def session_timeout_scenario() -> dict[str, Any]:
    """セッションタイムアウトシナリオ"""
    return get_session_timeout_scenario()


@pytest.fixture
def session_memory_overflow_scenario() -> dict[str, Any]:
    """セッションメモリオーバーフローシナリオ"""
    return load_error_scenario("interactive_session_errors", "session_memory_overflow")


@pytest.fixture
def pattern_database_not_found_scenario() -> dict[str, Any]:
    """パターンデータベース未発見シナリオ"""
    return get_pattern_not_found_scenario()


@pytest.fixture
def invalid_pattern_syntax_scenario() -> dict[str, Any]:
    """無効なパターン構文シナリオ"""
    return load_error_scenario("pattern_recognition_errors", "invalid_pattern_syntax")


@pytest.fixture
def secret_detection_scenario() -> dict[str, Any]:
    """シークレット検出シナリオ"""
    return get_secret_detection_scenario()


@pytest.fixture
def unsafe_file_path_scenario() -> dict[str, Any]:
    """安全でないファイルパスシナリオ"""
    return load_error_scenario("security_errors", "unsafe_file_path")


# ユーティリティフィクスチャ


@pytest.fixture
def error_scenario_loader() -> Callable[[str, str], dict[str, Any]]:
    """エラーシナリオローダー関数"""
    return load_error_scenario


@pytest.fixture
def all_error_scenarios() -> dict[str, dict[str, dict[str, Any]]]:
    """すべてのエラーシナリオ"""
    categories = [
        "network_errors",
        "configuration_errors",
        "ai_processing_errors",
        "file_system_errors",
        "ci_execution_errors",
        "cache_errors",
        "interactive_session_errors",
        "pattern_recognition_errors",
        "security_errors",
    ]

    return {category: load_all_error_scenarios(category) for category in categories}


@pytest.fixture
def common_error_scenarios() -> dict[str, dict[str, Any]]:
    """よく使用されるエラーシナリオ"""
    return {
        "network_timeout": get_network_timeout_scenario(),
        "missing_api_key": get_missing_api_key_scenario(),
        "token_limit_exceeded": get_token_limit_scenario(),
        "file_not_found": get_file_not_found_scenario(),
        "docker_not_running": get_docker_not_running_scenario(),
        "cache_corruption": get_cache_corruption_scenario(),
        "session_timeout": get_session_timeout_scenario(),
        "pattern_not_found": get_pattern_not_found_scenario(),
        "secret_detection": get_secret_detection_scenario(),
    }


# パラメータ化テスト用フィクスチャ


@pytest.fixture(
    params=["timeout_error", "connection_error", "dns_resolution_error", "ssl_certificate_error", "rate_limit_error"]
)
def network_error_scenario(request) -> dict[str, Any]:
    """パラメータ化されたネットワークエラーシナリオ"""
    return load_error_scenario("network_errors", request.param)


@pytest.fixture(
    params=[
        "missing_api_key",
        "invalid_api_key_format",
        "unsupported_provider",
        "invalid_model_name",
        "corrupted_config_file",
    ]
)
def configuration_error_scenario(request) -> dict[str, Any]:
    """パラメータ化された設定エラーシナリオ"""
    return load_error_scenario("configuration_errors", request.param)


@pytest.fixture(
    params=[
        "token_limit_exceeded",
        "cost_limit_exceeded",
        "model_overloaded",
        "content_policy_violation",
        "malformed_response",
    ]
)
def ai_processing_error_scenario(request) -> dict[str, Any]:
    """パラメータ化されたAI処理エラーシナリオ"""
    return load_error_scenario("ai_processing_errors", request.param)


# エラーシミュレーション用フィクスチャ


@pytest.fixture
def simulate_network_error(network_timeout_scenario):
    """ネットワークエラーシミュレーション"""

    def _simulate(error_type: str | None = None):
        scenario = network_timeout_scenario
        if error_type:
            scenario = load_error_scenario("network_errors", error_type)

        # エラーシミュレーション用の例外を作成
        error_class = getattr(__builtins__, scenario["error_type"], Exception)
        return error_class(scenario["error_message"])

    return _simulate


@pytest.fixture
def simulate_configuration_error(missing_api_key_scenario):
    """設定エラーシミュレーション"""

    def _simulate(error_type: str | None = None):
        scenario = missing_api_key_scenario
        if error_type:
            scenario = load_error_scenario("configuration_errors", error_type)

        # 設定エラー用の例外を作成
        from src.ci_helper.core.exceptions import ConfigurationError

        return ConfigurationError(scenario["error_message"])

    return _simulate
