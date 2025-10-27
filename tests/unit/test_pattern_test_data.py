"""
パターンテストデータの検証テスト

作成したパターンテストデータが正しく読み込まれ、
期待される構造を持っていることを確認するテスト。
"""

import json

import pytest

from tests.fixtures.pattern_test_data import (
    TEST_DATA_DIR,
    get_log_samples_by_category,
    get_patterns_by_category,
    get_performance_dataset,
    get_test_cases_by_difficulty,
    get_test_cases_by_type,
    get_test_data_statistics,
    load_comprehensive_patterns,
    load_edge_case_patterns,
    load_pattern_matching_test_cases,
    load_performance_test_data,
    load_test_log_samples,
)


class TestPatternTestData:
    """パターンテストデータの検証テスト"""

    def test_test_data_files_exist(self):
        """テストデータファイルが存在することを確認"""
        expected_files = [
            "comprehensive_patterns.json",
            "test_log_samples.json",
            "pattern_matching_test_cases.json",
            "edge_case_patterns.json",
            "performance_test_data.json",
            "README.md",
            "__init__.py",
        ]

        for filename in expected_files:
            file_path = TEST_DATA_DIR / filename
            assert file_path.exists(), f"テストデータファイル {filename} が存在しません"

    def test_comprehensive_patterns_structure(self):
        """包括的パターンデータの構造を確認"""
        data = load_comprehensive_patterns()

        # メタデータの確認
        assert "metadata" in data
        assert "patterns" in data
        assert data["metadata"]["total_patterns"] == 25

        # パターンの構造確認
        for pattern in data["patterns"]:
            required_fields = [
                "id",
                "name",
                "category",
                "regex_patterns",
                "keywords",
                "context_requirements",
                "confidence_base",
                "success_rate",
                "created_at",
                "updated_at",
                "user_defined",
                "auto_generated",
                "source",
                "occurrence_count",
            ]
            for field in required_fields:
                assert field in pattern, f"パターン {pattern['id']} に必須フィールド {field} がありません"

            # データ型の確認
            assert isinstance(pattern["regex_patterns"], list)
            assert isinstance(pattern["keywords"], list)
            assert isinstance(pattern["context_requirements"], list)
            assert isinstance(pattern["confidence_base"], (int, float))
            assert isinstance(pattern["success_rate"], (int, float))
            assert 0.0 <= pattern["confidence_base"] <= 1.0
            assert 0.0 <= pattern["success_rate"] <= 1.0

    def test_test_log_samples_structure(self):
        """ログサンプルデータの構造を確認"""
        data = load_test_log_samples()

        # メタデータの確認
        assert "metadata" in data
        assert "log_samples" in data
        assert data["metadata"]["total_samples"] == 30

        # ログサンプルの構造確認
        for sample in data["log_samples"]:
            required_fields = [
                "id",
                "description",
                "expected_pattern_ids",
                "log_content",
                "expected_confidence",
                "category",
                "severity",
            ]
            for field in required_fields:
                assert field in sample, f"ログサンプル {sample['id']} に必須フィールド {field} がありません"

            # データ型の確認
            assert isinstance(sample["expected_pattern_ids"], list)
            assert isinstance(sample["log_content"], str)
            assert isinstance(sample["expected_confidence"], (int, float))
            assert 0.0 <= sample["expected_confidence"] <= 1.0
            assert len(sample["log_content"]) > 0

    def test_pattern_matching_test_cases_structure(self):
        """パターンマッチングテストケースの構造を確認"""
        data = load_pattern_matching_test_cases()

        # メタデータの確認
        assert "metadata" in data
        assert "test_cases" in data
        assert data["metadata"]["total_test_cases"] == 20

        # テストケースの構造確認
        for case in data["test_cases"]:
            required_fields = ["id", "name", "description", "input_log", "expected_matches", "test_type", "difficulty"]
            for field in required_fields:
                assert field in case, f"テストケース {case['id']} に必須フィールド {field} がありません"

            # データ型の確認
            assert isinstance(case["expected_matches"], list)
            assert case["test_type"] in ["positive", "negative"]
            assert case["difficulty"] in ["easy", "medium", "hard"]

    def test_edge_case_patterns_structure(self):
        """エッジケースパターンの構造を確認"""
        data = load_edge_case_patterns()

        # メタデータの確認
        assert "metadata" in data
        assert "edge_case_patterns" in data
        assert data["metadata"]["total_patterns"] == 15

        # エッジケースパターンの構造確認
        for pattern in data["edge_case_patterns"]:
            required_fields = [
                "id",
                "name",
                "category",
                "regex_patterns",
                "keywords",
                "context_requirements",
                "confidence_base",
                "success_rate",
                "test_purpose",
            ]
            for field in required_fields:
                assert field in pattern, f"エッジケースパターン {pattern['id']} に必須フィールド {field} がありません"

    def test_performance_test_data_structure(self):
        """性能テストデータの構造を確認"""
        data = load_performance_test_data()

        # メタデータの確認
        assert "metadata" in data
        assert "performance_datasets" in data
        assert "benchmark_thresholds" in data
        assert data["metadata"]["total_datasets"] == 10

        # 性能データセットの構造確認
        for dataset in data["performance_datasets"]:
            required_fields = [
                "id",
                "name",
                "description",
                "pattern_count",
                "log_size_kb",
                "expected_processing_time_ms",
                "performance_metrics",
            ]
            for field in required_fields:
                assert field in dataset, f"性能データセット {dataset['id']} に必須フィールド {field} がありません"

    def test_get_patterns_by_category(self):
        """カテゴリ別パターン取得機能のテスト"""
        permission_patterns = get_patterns_by_category("permission")
        assert len(permission_patterns) > 0

        for pattern in permission_patterns:
            assert pattern["category"] == "permission"

    def test_get_log_samples_by_category(self):
        """カテゴリ別ログサンプル取得機能のテスト"""
        network_samples = get_log_samples_by_category("network")
        assert len(network_samples) > 0

        for sample in network_samples:
            assert sample["category"] == "network"

    def test_get_test_cases_by_difficulty(self):
        """難易度別テストケース取得機能のテスト"""
        easy_cases = get_test_cases_by_difficulty("easy")
        hard_cases = get_test_cases_by_difficulty("hard")

        assert len(easy_cases) > 0
        assert len(hard_cases) > 0

        for case in easy_cases:
            assert case["difficulty"] == "easy"

        for case in hard_cases:
            assert case["difficulty"] == "hard"

    def test_get_test_cases_by_type(self):
        """タイプ別テストケース取得機能のテスト"""
        positive_cases = get_test_cases_by_type("positive")
        negative_cases = get_test_cases_by_type("negative")

        assert len(positive_cases) > 0
        assert len(negative_cases) > 0

        for case in positive_cases:
            assert case["test_type"] == "positive"

        for case in negative_cases:
            assert case["test_type"] == "negative"

    def test_get_performance_dataset(self):
        """性能データセット取得機能のテスト"""
        small_dataset = get_performance_dataset("small_dataset")
        assert small_dataset["id"] == "small_dataset"
        assert small_dataset["pattern_count"] == 5

        # 存在しないデータセットの場合はエラー
        with pytest.raises(ValueError):
            get_performance_dataset("nonexistent_dataset")

    def test_get_test_data_statistics(self):
        """テストデータ統計情報取得機能のテスト"""
        stats = get_test_data_statistics()

        required_fields = [
            "total_patterns",
            "total_log_samples",
            "total_test_cases",
            "total_edge_cases",
            "total_performance_datasets",
            "pattern_categories",
            "test_case_difficulties",
            "test_case_types",
        ]

        for field in required_fields:
            assert field in stats, f"統計情報に {field} がありません"

        # 数値の確認
        assert stats["total_patterns"] == 25
        assert stats["total_log_samples"] == 30
        assert stats["total_test_cases"] == 20
        assert stats["total_edge_cases"] == 15
        assert stats["total_performance_datasets"] == 10

        # カテゴリの確認
        expected_categories = [
            "permission",
            "dependency",
            "network",
            "config",
            "build",
            "test",
            "system",
            "ci_cd",
            "database",
            "syntax",
            "filesystem",
            "test_mock",
            "async",
            "attribute",
            "test_fixture",
            "type",
            "value",
            "key",
            "index",
            "math",
        ]
        for category in expected_categories:
            assert category in stats["pattern_categories"]

    def test_json_files_valid_format(self):
        """JSONファイルが有効な形式であることを確認"""
        json_files = [
            "comprehensive_patterns.json",
            "test_log_samples.json",
            "pattern_matching_test_cases.json",
            "edge_case_patterns.json",
            "performance_test_data.json",
        ]

        for filename in json_files:
            file_path = TEST_DATA_DIR / filename
            try:
                with open(file_path, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"JSONファイル {filename} の形式が無効です: {e}")

    def test_pattern_ids_unique(self):
        """パターンIDが一意であることを確認"""
        patterns_data = load_comprehensive_patterns()
        edge_cases_data = load_edge_case_patterns()

        # 包括的パターンのID重複チェック
        pattern_ids = [pattern["id"] for pattern in patterns_data["patterns"]]
        assert len(pattern_ids) == len(set(pattern_ids)), "包括的パターンにID重複があります"

        # エッジケースパターンのID重複チェック
        edge_case_ids = [pattern["id"] for pattern in edge_cases_data["edge_case_patterns"]]
        assert len(edge_case_ids) == len(set(edge_case_ids)), "エッジケースパターンにID重複があります"

    def test_log_sample_ids_unique(self):
        """ログサンプルIDが一意であることを確認"""
        samples_data = load_test_log_samples()
        sample_ids = [sample["id"] for sample in samples_data["log_samples"]]
        assert len(sample_ids) == len(set(sample_ids)), "ログサンプルにID重複があります"

    def test_test_case_ids_unique(self):
        """テストケースIDが一意であることを確認"""
        test_cases_data = load_pattern_matching_test_cases()
        case_ids = [case["id"] for case in test_cases_data["test_cases"]]
        assert len(case_ids) == len(set(case_ids)), "テストケースにID重複があります"

    def test_confidence_values_valid_range(self):
        """信頼度の値が有効な範囲内であることを確認"""
        patterns_data = load_comprehensive_patterns()
        samples_data = load_test_log_samples()

        # パターンの信頼度確認
        for pattern in patterns_data["patterns"]:
            assert 0.0 <= pattern["confidence_base"] <= 1.0, f"パターン {pattern['id']} の信頼度が範囲外です"
            assert 0.0 <= pattern["success_rate"] <= 1.0, f"パターン {pattern['id']} の成功率が範囲外です"

        # ログサンプルの期待信頼度確認
        for sample in samples_data["log_samples"]:
            assert 0.0 <= sample["expected_confidence"] <= 1.0, f"ログサンプル {sample['id']} の期待信頼度が範囲外です"

    def test_regex_patterns_not_empty(self):
        """正規表現パターンが空でないことを確認（エッジケースを除く）"""
        patterns_data = load_comprehensive_patterns()

        for pattern in patterns_data["patterns"]:
            # 少なくとも正規表現またはキーワードのどちらかは存在するはず
            has_regex = pattern["regex_patterns"] and any(p.strip() for p in pattern["regex_patterns"])
            has_keywords = pattern["keywords"] and any(k.strip() for k in pattern["keywords"])
            assert has_regex or has_keywords, f"パターン {pattern['id']} に有効な正規表現またはキーワードがありません"

    def test_performance_metrics_reasonable(self):
        """性能メトリクスが妥当な値であることを確認"""
        perf_data = load_performance_test_data()

        for dataset in perf_data["performance_datasets"]:
            metrics = dataset["performance_metrics"]

            # 精度は0.0-1.0の範囲
            if "expected_accuracy" in metrics:
                assert 0.0 <= metrics["expected_accuracy"] <= 1.0, f"データセット {dataset['id']} の精度が範囲外です"

            # メモリ使用量は正の値
            if "max_memory_mb" in metrics:
                assert metrics["max_memory_mb"] > 0, f"データセット {dataset['id']} のメモリ使用量が無効です"

            # CPU使用率は0-100の範囲
            if "max_cpu_percent" in metrics:
                assert 0 <= metrics["max_cpu_percent"] <= 100, f"データセット {dataset['id']} のCPU使用率が範囲外です"
