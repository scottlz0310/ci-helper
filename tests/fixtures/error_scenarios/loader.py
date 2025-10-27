"""
エラーシナリオフィクスチャローダー

エラーシナリオデータを簡単に読み込むためのユーティリティ
"""

import json
from pathlib import Path
from typing import Any


class ErrorScenarioLoader:
    """エラーシナリオデータのローダー"""

    def __init__(self, fixtures_dir: Path | None = None):
        """
        初期化

        Args:
            fixtures_dir: フィクスチャディレクトリのパス（デフォルトは現在のディレクトリ）
        """
        if fixtures_dir is None:
            fixtures_dir = Path(__file__).parent
        self.fixtures_dir = fixtures_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def load_scenario(self, category: str, scenario_name: str) -> dict[str, Any]:
        """
        特定のエラーシナリオを読み込む

        Args:
            category: エラーカテゴリ（例: "network_errors"）
            scenario_name: シナリオ名（例: "timeout_error"）

        Returns:
            エラーシナリオデータ

        Raises:
            FileNotFoundError: カテゴリファイルが見つからない場合
            KeyError: シナリオが見つからない場合
        """
        # キャッシュから取得を試行
        if category not in self._cache:
            self._load_category(category)

        # Try different possible keys for scenarios
        possible_keys = [
            f"{category}_scenarios",
            f"{category.replace('_errors', '_error')}_scenarios",
            f"{category.replace('_', '_')}_scenarios",
        ]

        scenarios = None
        for key in possible_keys:
            if key in self._cache[category]:
                scenarios = self._cache[category][key]
                break

        if scenarios is None:
            available_keys = list(self._cache[category].keys())
            raise KeyError(f"Category '{category}' does not contain scenarios. Available keys: {available_keys}")

        if scenario_name not in scenarios:
            available = list(scenarios.keys())
            raise KeyError(f"Scenario '{scenario_name}' not found in '{category}'. Available: {available}")

        return scenarios[scenario_name]

    def load_all_scenarios(self, category: str) -> dict[str, dict[str, Any]]:
        """
        カテゴリ内のすべてのシナリオを読み込む

        Args:
            category: エラーカテゴリ

        Returns:
            シナリオ名をキーとするシナリオデータの辞書
        """
        if category not in self._cache:
            self._load_category(category)

        # Try different possible keys for scenarios
        possible_keys = [
            f"{category}_scenarios",
            f"{category.replace('_errors', '_error')}_scenarios",
            f"{category.replace('_', '_')}_scenarios",
        ]

        for key in possible_keys:
            if key in self._cache[category]:
                return self._cache[category][key]

        available_keys = list(self._cache[category].keys())
        raise KeyError(f"Category '{category}' does not contain scenarios. Available keys: {available_keys}")

    def list_categories(self) -> list[str]:
        """
        利用可能なエラーカテゴリの一覧を取得

        Returns:
            カテゴリ名のリスト
        """
        json_files = list(self.fixtures_dir.glob("*.json"))
        return [f.stem for f in json_files if f.stem != "README"]

    def list_scenarios(self, category: str) -> list[str]:
        """
        カテゴリ内のシナリオ名一覧を取得

        Args:
            category: エラーカテゴリ

        Returns:
            シナリオ名のリスト
        """
        scenarios = self.load_all_scenarios(category)
        return list(scenarios.keys())

    def _load_category(self, category: str) -> None:
        """
        カテゴリファイルを読み込んでキャッシュに保存

        Args:
            category: エラーカテゴリ

        Raises:
            FileNotFoundError: カテゴリファイルが見つからない場合
        """
        file_path = self.fixtures_dir / f"{category}.json"
        if not file_path.exists():
            available = self.list_categories()
            raise FileNotFoundError(f"Category file '{file_path}' not found. Available: {available}")

        with open(file_path, encoding="utf-8") as f:
            self._cache[category] = json.load(f)


# グローバルローダーインスタンス
_loader = ErrorScenarioLoader()


def load_error_scenario(category: str, scenario_name: str) -> dict[str, Any]:
    """
    エラーシナリオを読み込む（便利関数）

    Args:
        category: エラーカテゴリ
        scenario_name: シナリオ名

    Returns:
        エラーシナリオデータ
    """
    return _loader.load_scenario(category, scenario_name)


def load_all_error_scenarios(category: str) -> dict[str, dict[str, Any]]:
    """
    カテゴリ内のすべてのエラーシナリオを読み込む（便利関数）

    Args:
        category: エラーカテゴリ

    Returns:
        シナリオ名をキーとするシナリオデータの辞書
    """
    return _loader.load_all_scenarios(category)


def list_error_categories() -> list[str]:
    """
    利用可能なエラーカテゴリの一覧を取得（便利関数）

    Returns:
        カテゴリ名のリスト
    """
    return _loader.list_categories()


def list_error_scenarios(category: str) -> list[str]:
    """
    カテゴリ内のシナリオ名一覧を取得（便利関数）

    Args:
        category: エラーカテゴリ

    Returns:
        シナリオ名のリスト
    """
    return _loader.list_scenarios(category)


# よく使用されるシナリオのショートカット関数
def get_network_timeout_scenario() -> dict[str, Any]:
    """ネットワークタイムアウトシナリオを取得"""
    return load_error_scenario("network_errors", "timeout_error")


def get_missing_api_key_scenario() -> dict[str, Any]:
    """APIキー未設定シナリオを取得"""
    return load_error_scenario("configuration_errors", "missing_api_key")


def get_token_limit_scenario() -> dict[str, Any]:
    """トークン制限超過シナリオを取得"""
    return load_error_scenario("ai_processing_errors", "token_limit_exceeded")


def get_file_not_found_scenario() -> dict[str, Any]:
    """ファイル未発見シナリオを取得"""
    return load_error_scenario("file_system_errors", "log_file_not_found")


def get_docker_not_running_scenario() -> dict[str, Any]:
    """Docker未起動シナリオを取得"""
    return load_error_scenario("ci_execution_errors", "docker_not_running")


def get_cache_corruption_scenario() -> dict[str, Any]:
    """キャッシュ破損シナリオを取得"""
    return load_error_scenario("cache_errors", "cache_corruption_detected")


def get_session_timeout_scenario() -> dict[str, Any]:
    """セッションタイムアウトシナリオを取得"""
    return load_error_scenario("interactive_session_errors", "session_timeout")


def get_pattern_not_found_scenario() -> dict[str, Any]:
    """パターンデータベース未発見シナリオを取得"""
    return load_error_scenario("pattern_recognition_errors", "pattern_database_not_found")


def get_secret_detection_scenario() -> dict[str, Any]:
    """シークレット検出シナリオを取得"""
    return load_error_scenario("security_errors", "secret_detection_in_logs")
