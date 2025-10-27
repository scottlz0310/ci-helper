"""
エラーシナリオフィクスチャのテスト

エラーシナリオデータが正しく読み込めることを確認するテスト
"""

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
    list_error_categories,
    list_error_scenarios,
    load_all_error_scenarios,
    load_error_scenario,
)


class TestErrorScenarioLoader:
    """エラーシナリオローダーのテスト"""

    def test_load_scenario_success(self):
        """シナリオの正常読み込みテスト"""
        scenario = load_error_scenario("network_errors", "timeout_error")

        assert scenario["error_type"] == "TimeoutError"
        assert "error_message" in scenario
        assert "context" in scenario
        assert "expected_behavior" in scenario
        assert "recovery_strategy" in scenario

    def test_load_scenario_invalid_category(self):
        """存在しないカテゴリの読み込みテスト"""
        with pytest.raises(FileNotFoundError):
            load_error_scenario("nonexistent_errors", "some_error")

    def test_load_scenario_invalid_scenario(self):
        """存在しないシナリオの読み込みテスト"""
        with pytest.raises(KeyError):
            load_error_scenario("network_errors", "nonexistent_error")

    def test_load_all_scenarios(self):
        """カテゴリ内全シナリオの読み込みテスト"""
        scenarios = load_all_error_scenarios("network_errors")

        assert isinstance(scenarios, dict)
        assert len(scenarios) > 0
        assert "timeout_error" in scenarios
        assert "connection_error" in scenarios

    def test_list_categories(self):
        """カテゴリ一覧取得テスト"""
        categories = list_error_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "network_errors" in categories
        assert "configuration_errors" in categories
        assert "ai_processing_errors" in categories

    def test_list_scenarios(self):
        """シナリオ一覧取得テスト"""
        scenarios = list_error_scenarios("network_errors")

        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        assert "timeout_error" in scenarios
        assert "connection_error" in scenarios


class TestShortcutFunctions:
    """ショートカット関数のテスト"""

    def test_get_network_timeout_scenario(self):
        """ネットワークタイムアウトシナリオ取得テスト"""
        scenario = get_network_timeout_scenario()

        assert scenario["error_type"] == "TimeoutError"
        assert "timeout" in scenario["error_message"].lower()

    def test_get_missing_api_key_scenario(self):
        """APIキー未設定シナリオ取得テスト"""
        scenario = get_missing_api_key_scenario()

        assert scenario["error_type"] == "ConfigurationError"
        assert "api key" in scenario["error_message"].lower()

    def test_get_token_limit_scenario(self):
        """トークン制限超過シナリオ取得テスト"""
        scenario = get_token_limit_scenario()

        assert scenario["error_type"] == "TokenLimitError"
        assert "token" in scenario["error_message"].lower()

    def test_get_file_not_found_scenario(self):
        """ファイル未発見シナリオ取得テスト"""
        scenario = get_file_not_found_scenario()

        assert scenario["error_type"] == "FileNotFoundError"
        assert "not found" in scenario["error_message"].lower()

    def test_get_docker_not_running_scenario(self):
        """Docker未起動シナリオ取得テスト"""
        scenario = get_docker_not_running_scenario()

        assert scenario["error_type"] == "ExecutionError"
        assert "docker" in scenario["error_message"].lower()

    def test_get_cache_corruption_scenario(self):
        """キャッシュ破損シナリオ取得テスト"""
        scenario = get_cache_corruption_scenario()

        assert scenario["error_type"] == "CacheError"
        assert "corruption" in scenario["error_message"].lower()

    def test_get_session_timeout_scenario(self):
        """セッションタイムアウトシナリオ取得テスト"""
        scenario = get_session_timeout_scenario()

        assert scenario["error_type"] == "SessionTimeoutError"
        assert "timed out" in scenario["error_message"].lower()

    def test_get_pattern_not_found_scenario(self):
        """パターンデータベース未発見シナリオ取得テスト"""
        scenario = get_pattern_not_found_scenario()

        assert scenario["error_type"] == "PatternError"
        assert "pattern" in scenario["error_message"].lower()

    def test_get_secret_detection_scenario(self):
        """シークレット検出シナリオ取得テスト"""
        scenario = get_secret_detection_scenario()

        assert scenario["error_type"] == "SecurityError"
        assert "secret" in scenario["error_message"].lower()


class TestScenarioDataStructure:
    """シナリオデータ構造のテスト"""

    @pytest.mark.parametrize(
        "category",
        [
            "network_errors",
            "configuration_errors",
            "ai_processing_errors",
            "file_system_errors",
            "ci_execution_errors",
            "cache_errors",
            "interactive_session_errors",
            "pattern_recognition_errors",
            "security_errors",
        ],
    )
    def test_all_scenarios_have_required_fields(self, category):
        """すべてのシナリオが必須フィールドを持つことをテスト"""
        scenarios = load_all_error_scenarios(category)

        for scenario_name, scenario_data in scenarios.items():
            # 必須フィールドの存在確認
            assert "error_type" in scenario_data, f"{category}.{scenario_name} missing error_type"
            assert "error_message" in scenario_data, f"{category}.{scenario_name} missing error_message"
            assert "context" in scenario_data, f"{category}.{scenario_name} missing context"
            assert "expected_behavior" in scenario_data, f"{category}.{scenario_name} missing expected_behavior"
            assert "recovery_strategy" in scenario_data, f"{category}.{scenario_name} missing recovery_strategy"

            # フィールドの型確認
            assert isinstance(scenario_data["error_type"], str)
            assert isinstance(scenario_data["error_message"], str)
            assert isinstance(scenario_data["context"], dict)
            assert isinstance(scenario_data["expected_behavior"], str)
            assert isinstance(scenario_data["recovery_strategy"], str)

            # 空でないことを確認
            assert len(scenario_data["error_type"]) > 0
            assert len(scenario_data["error_message"]) > 0
            assert len(scenario_data["context"]) > 0
            assert len(scenario_data["expected_behavior"]) > 0
            assert len(scenario_data["recovery_strategy"]) > 0


class TestErrorScenarioUsageExamples:
    """エラーシナリオの使用例テスト"""

    def test_network_error_handling_simulation(self):
        """ネットワークエラーハンドリングのシミュレーション"""
        scenario = get_network_timeout_scenario()

        # シナリオデータを使用してエラーハンドリングをテスト
        error_type = scenario["error_type"]
        error_message = scenario["error_message"]
        context = scenario["context"]

        # エラーハンドリングロジックのテスト（例）
        assert error_type == "TimeoutError"
        assert context["provider"] == "openai"
        assert "retry" in scenario["expected_behavior"]

    def test_configuration_error_recovery(self):
        """設定エラーからの復旧テスト"""
        scenario = get_missing_api_key_scenario()

        # 復旧戦略の確認
        recovery_strategy = scenario["recovery_strategy"]
        context = scenario["context"]

        assert "setup" in recovery_strategy.lower()
        assert "openai" in context["provider"]
        assert context["expected_key_name"] == "OPENAI_API_KEY"

    def test_multiple_error_scenarios_handling(self):
        """複数のエラーシナリオの処理テスト"""
        scenarios = [
            get_network_timeout_scenario(),
            get_missing_api_key_scenario(),
            get_token_limit_scenario(),
            get_file_not_found_scenario(),
        ]

        # すべてのシナリオが適切な構造を持つことを確認
        for scenario in scenarios:
            assert "error_type" in scenario
            assert "recovery_strategy" in scenario
            assert len(scenario["error_message"]) > 0

    def test_scenario_context_usage(self):
        """シナリオコンテキストの使用テスト"""
        scenario = get_docker_not_running_scenario()
        context = scenario["context"]

        # コンテキスト情報を使用した詳細なテスト
        assert "docker_command" in context
        assert "docker_service_status" in context
        assert context["docker_service_status"] == "stopped"

        # 復旧戦略がコンテキストに適している確認
        recovery = scenario["recovery_strategy"]
        assert "docker" in recovery.lower()
        assert "start" in recovery.lower()
