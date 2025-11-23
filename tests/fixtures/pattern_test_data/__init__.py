"""
パターン認識テストデータ

CI-Helperのパターン認識エンジンをテストするための包括的なテストデータセット。

このモジュールには以下のテストデータが含まれています：
- comprehensive_patterns.json: 基本的なパターン認識テスト用の25個のパターン
- test_log_samples.json: パターンマッチング精度テスト用の30個のログサンプル
- pattern_matching_test_cases.json: エッジケースとコーナーケース用の20個のテストケース
- edge_case_patterns.json: エラーハンドリングテスト用の15個のエッジケースパターン
- performance_test_data.json: 性能テスト用の10個のデータセット
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# テストデータディレクトリのパス
TEST_DATA_DIR = Path(__file__).parent


def load_comprehensive_patterns() -> dict[str, Any]:
    """包括的なパターンデータを読み込み"""
    with open(TEST_DATA_DIR / "comprehensive_patterns.json", encoding="utf-8") as f:
        return json.load(f)


def load_test_log_samples() -> dict[str, Any]:
    """テスト用ログサンプルを読み込み"""
    with open(TEST_DATA_DIR / "test_log_samples.json", encoding="utf-8") as f:
        return json.load(f)


def load_pattern_matching_test_cases() -> dict[str, Any]:
    """パターンマッチングテストケースを読み込み"""
    with open(TEST_DATA_DIR / "pattern_matching_test_cases.json", encoding="utf-8") as f:
        return json.load(f)


def load_edge_case_patterns() -> dict[str, Any]:
    """エッジケースパターンを読み込み"""
    with open(TEST_DATA_DIR / "edge_case_patterns.json", encoding="utf-8") as f:
        return json.load(f)


def load_performance_test_data() -> dict[str, Any]:
    """性能テストデータを読み込み"""
    with open(TEST_DATA_DIR / "performance_test_data.json", encoding="utf-8") as f:
        return json.load(f)


def get_patterns_by_category(category: str) -> list[dict[str, Any]]:
    """指定されたカテゴリのパターンを取得"""
    patterns_data = load_comprehensive_patterns()
    return [pattern for pattern in patterns_data["patterns"] if pattern["category"] == category]


def get_log_samples_by_category(category: str) -> list[dict[str, Any]]:
    """指定されたカテゴリのログサンプルを取得"""
    samples_data = load_test_log_samples()
    return [sample for sample in samples_data["log_samples"] if sample["category"] == category]


def get_test_cases_by_difficulty(difficulty: str) -> list[dict[str, Any]]:
    """指定された難易度のテストケースを取得"""
    test_cases_data = load_pattern_matching_test_cases()
    return [case for case in test_cases_data["test_cases"] if case["difficulty"] == difficulty]


def get_test_cases_by_type(test_type: str) -> list[dict[str, Any]]:
    """指定されたタイプのテストケースを取得"""
    test_cases_data = load_pattern_matching_test_cases()
    return [case for case in test_cases_data["test_cases"] if case["test_type"] == test_type]


def get_performance_dataset(dataset_id: str) -> dict[str, Any]:
    """指定されたIDの性能テストデータセットを取得"""
    perf_data = load_performance_test_data()
    for dataset in perf_data["performance_datasets"]:
        if dataset["id"] == dataset_id:
            return dataset
    raise ValueError(f"Performance dataset '{dataset_id}' not found")


# よく使用されるテストデータのショートカット
def get_basic_patterns() -> list[dict[str, Any]]:
    """基本的なテスト用パターンを取得"""
    return get_patterns_by_category("permission") + get_patterns_by_category("dependency")


def get_positive_test_cases() -> list[dict[str, Any]]:
    """ポジティブテストケース（マッチするはず）を取得"""
    return get_test_cases_by_type("positive")


def get_negative_test_cases() -> list[dict[str, Any]]:
    """ネガティブテストケース（マッチしないはず）を取得"""
    return get_test_cases_by_type("negative")


def get_easy_test_cases() -> list[dict[str, Any]]:
    """簡単なテストケースを取得"""
    return get_test_cases_by_difficulty("easy")


def get_hard_test_cases() -> list[dict[str, Any]]:
    """難しいテストケースを取得"""
    return get_test_cases_by_difficulty("hard")


# テストデータの統計情報
def get_test_data_statistics() -> dict[str, Any]:
    """テストデータの統計情報を取得"""
    patterns_data = load_comprehensive_patterns()
    samples_data = load_test_log_samples()
    test_cases_data = load_pattern_matching_test_cases()
    edge_cases_data = load_edge_case_patterns()
    perf_data = load_performance_test_data()

    return {
        "total_patterns": patterns_data["metadata"]["total_patterns"],
        "total_log_samples": samples_data["metadata"]["total_samples"],
        "total_test_cases": test_cases_data["metadata"]["total_test_cases"],
        "total_edge_cases": edge_cases_data["metadata"]["total_patterns"],
        "total_performance_datasets": perf_data["metadata"]["total_datasets"],
        "pattern_categories": list({pattern["category"] for pattern in patterns_data["patterns"]}),
        "test_case_difficulties": list({case["difficulty"] for case in test_cases_data["test_cases"]}),
        "test_case_types": list({case["test_type"] for case in test_cases_data["test_cases"]}),
    }


__all__ = [
    "TEST_DATA_DIR",
    "get_basic_patterns",
    "get_easy_test_cases",
    "get_hard_test_cases",
    "get_log_samples_by_category",
    "get_negative_test_cases",
    "get_patterns_by_category",
    "get_performance_dataset",
    "get_positive_test_cases",
    "get_test_cases_by_difficulty",
    "get_test_cases_by_type",
    "get_test_data_statistics",
    "load_comprehensive_patterns",
    "load_edge_case_patterns",
    "load_pattern_matching_test_cases",
    "load_performance_test_data",
    "load_test_log_samples",
]
