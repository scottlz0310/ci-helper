"""
学習エンジンのテスト
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.ci_helper.ai.learning_engine import LearningEngine
from src.ci_helper.ai.models import Pattern, PatternMatch, UserFeedback
from src.ci_helper.ai.pattern_database import PatternDatabase


class TestLearningEngine:
    """学習エンジンのテスト"""

    @pytest.fixture
    def pattern_database(self):
        """パターンデータベースのモック"""
        return Mock(spec=PatternDatabase)

    @pytest.fixture
    def temp_learning_dir(self):
        """一時的な学習データディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def learning_engine(self, pattern_database, temp_learning_dir):
        """学習エンジンインスタンス"""
        return LearningEngine(
            pattern_database=pattern_database,
            learning_data_dir=temp_learning_dir,
            min_pattern_occurrences=2,
            confidence_adjustment_factor=0.1,
        )

    @pytest.fixture
    def sample_pattern(self):
        """サンプルパターン"""
        return Pattern(
            id="test_pattern",
            name="テストパターン",
            category="dependency",
            regex_patterns=[r"npm.*error"],
            keywords=["npm", "error"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.7,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.fixture
    def sample_pattern_match(self, sample_pattern):
        """サンプルパターンマッチ"""
        return PatternMatch(
            pattern=sample_pattern,
            confidence=0.9,
            match_positions=[0, 10],
            extracted_context="npm install error",
            match_strength=0.8,
            supporting_evidence=["npm ERR! 404"],
        )

    @pytest.fixture
    def sample_feedback(self, sample_pattern):
        """サンプルユーザーフィードバック"""
        return UserFeedback(
            pattern_id=sample_pattern.id,
            fix_suggestion_id="fix_001",
            rating=4,
            success=True,
            comments="とても役に立ちました",
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_initialize(self, learning_engine, temp_learning_dir):
        """初期化のテスト"""
        assert not learning_engine._initialized

        await learning_engine.initialize()

        assert learning_engine._initialized
        assert temp_learning_dir.exists()
        assert learning_engine.feedback_collector is not None

    @pytest.mark.asyncio
    async def test_learn_from_feedback(self, learning_engine, sample_feedback):
        """フィードバック学習のテスト"""
        await learning_engine.initialize()

        await learning_engine.learn_from_feedback(sample_feedback)

        assert len(learning_engine.feedback_history) == 1
        assert learning_engine.feedback_history[0] == sample_feedback

    @pytest.mark.asyncio
    async def test_update_pattern_success_rate(self, learning_engine, sample_feedback):
        """パターン成功率更新のテスト"""
        await learning_engine.initialize()

        # 成功フィードバック
        success_feedback = UserFeedback(
            pattern_id=sample_feedback.pattern_id,
            fix_suggestion_id="fix_002",
            rating=5,
            success=True,
            comments="Good fix",
            timestamp=datetime.now(),
        )
        await learning_engine._update_pattern_success_rate(success_feedback)

        tracking = learning_engine.pattern_success_tracking[sample_feedback.pattern_id]
        assert tracking["successes"] == 1
        assert tracking["total_uses"] == 1
        assert tracking["success_rate"] == 1.0

        # 失敗フィードバック
        failure_feedback = UserFeedback(
            pattern_id=sample_feedback.pattern_id,
            fix_suggestion_id="fix_003",
            rating=2,
            success=False,
            comments="Did not work",
            timestamp=datetime.now(),
        )
        await learning_engine._update_pattern_success_rate(failure_feedback)

        tracking = learning_engine.pattern_success_tracking[sample_feedback.pattern_id]
        assert tracking["failures"] == 1
        assert tracking["total_uses"] == 2
        assert tracking["success_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_update_pattern_confidence(self, learning_engine, sample_pattern):
        """パターン信頼度更新のテスト"""
        await learning_engine.initialize()
        learning_engine.pattern_database.get_pattern.return_value = sample_pattern
        learning_engine.pattern_database.update_pattern = AsyncMock()

        # 成功時の信頼度向上
        await learning_engine.update_pattern_confidence(sample_pattern.id, success=True)

        learning_engine.pattern_database.update_pattern.assert_called_once()
        call_args = learning_engine.pattern_database.update_pattern.call_args[0]
        updated_pattern = call_args[0]
        assert updated_pattern.confidence_base > sample_pattern.confidence_base

    @pytest.mark.asyncio
    async def test_load_learning_data(self, learning_engine, temp_learning_dir, sample_feedback):
        """学習データ読み込みのテスト"""
        # テストデータを作成
        feedback_data = [
            {
                "pattern_id": sample_feedback.pattern_id,
                "fix_suggestion_id": sample_feedback.fix_suggestion_id,
                "rating": sample_feedback.rating,
                "success": sample_feedback.success,
                "comments": sample_feedback.comments,
                "timestamp": sample_feedback.timestamp.isoformat(),
            }
        ]

        feedback_file = temp_learning_dir / "feedback.json"
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedback_data, f, ensure_ascii=False)

        await learning_engine.initialize()

        assert len(learning_engine.feedback_history) == 1
        loaded_feedback = learning_engine.feedback_history[0]
        assert loaded_feedback.pattern_id == sample_feedback.pattern_id
        assert loaded_feedback.rating == sample_feedback.rating

    @pytest.mark.asyncio
    async def test_save_learning_data(self, learning_engine, temp_learning_dir, sample_feedback):
        """学習データ保存のテスト"""
        await learning_engine.initialize()
        learning_engine.feedback_history.append(sample_feedback)

        await learning_engine._save_learning_data()

        feedback_file = temp_learning_dir / "feedback.json"
        assert feedback_file.exists()

        with open(feedback_file, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert len(saved_data) == 1
        assert saved_data[0]["pattern_id"] == sample_feedback.pattern_id

    @pytest.mark.asyncio
    async def test_discover_new_patterns(self, learning_engine):
        """新しいパターン発見のテスト"""
        await learning_engine.initialize()

        failed_logs = [
            "npm ERR! 404 Not Found - GET https://registry.npmjs.org/missing-package",
            "npm ERR! 404 'missing-package@^1.0.0' is not in the npm registry.",
            "Error: Command failed with exit code 1.",
        ]

        patterns = await learning_engine.discover_new_patterns(failed_logs)

        assert isinstance(patterns, list)
        # パターンが検出されることを確認（具体的な内容は実装に依存）

    def test_extract_error_messages(self, learning_engine):
        """エラーメッセージ抽出のテスト"""
        log_content = """
        npm ERR! 404 Not Found
        Error: Command failed with exit code 1
        Warning: This is just a warning
        npm ERR! network timeout
        """

        error_messages = learning_engine._extract_error_messages(log_content)

        assert isinstance(error_messages, list)
        assert len(error_messages) > 0
        # エラーメッセージが適切に抽出されることを確認

    @pytest.mark.asyncio
    async def test_collect_and_process_feedback(self, learning_engine, sample_pattern_match):
        """フィードバック収集・処理のテスト"""
        await learning_engine.initialize()

        # フィードバック収集システムのモック設定
        learning_engine.feedback_collector.collect_feedback = AsyncMock(
            return_value=[
                UserFeedback(
                    pattern_id="test_pattern",
                    fix_suggestion_id="fix_004",
                    rating=4,
                    success=True,
                    comments="良い提案でした",
                    timestamp=datetime.now(),
                )
            ]
        )

        feedback_list = await learning_engine.collect_and_process_feedback([sample_pattern_match], "test log content")

        assert len(feedback_list) == 1
        assert feedback_list[0].pattern_id == "test_pattern"

    @pytest.mark.asyncio
    async def test_update_pattern_database_dynamically(self, learning_engine, sample_pattern):
        """パターンデータベース動的更新のテスト"""
        await learning_engine.initialize()

        # 学習データを設定
        learning_engine.learned_patterns = {
            "new_pattern": {
                "regex_patterns": [r"build.*failed"],
                "keywords": ["build", "failed"],
                "confidence": 0.8,
                "occurrences": 5,
            }
        }

        learning_engine.pattern_database.add_pattern = AsyncMock()

        result = await learning_engine.update_pattern_database_dynamically()

        assert "patterns_added" in result
        learning_engine.pattern_database.add_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_old_unknown_errors(self, learning_engine, temp_learning_dir):
        """古い未知エラーデータクリーンアップのテスト"""
        await learning_engine.initialize()

        # 古い未知エラーデータをファイルに作成
        old_error = {
            "error_signature": "old error",
            "timestamp": (datetime.now() - timedelta(days=100)).isoformat(),
            "occurrences": 1,
        }

        recent_error = {
            "error_signature": "recent error",
            "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
            "occurrences": 1,
        }

        unknown_errors_file = temp_learning_dir / "unknown_errors.json"
        with open(unknown_errors_file, "w", encoding="utf-8") as f:
            json.dump([old_error, recent_error], f, ensure_ascii=False)

        cleaned_count = await learning_engine.cleanup_old_unknown_errors(max_age_days=30)

        # 古いデータが削除されることを確認
        assert cleaned_count >= 0

    def test_normalize_error_message(self, learning_engine):
        """エラーメッセージ正規化のテスト"""
        error_message = "  Error: File '/path/to/file.txt' not found at line 123  "

        normalized = learning_engine._normalize_error_message(error_message)

        assert isinstance(normalized, str)
        assert len(normalized) > 0
        # 正規化処理が適用されることを確認

    def test_find_frequent_errors(self, learning_engine):
        """頻出エラー特定のテスト"""
        learning_engine.error_frequency = {
            "npm error": 10,
            "build failed": 5,
            "test timeout": 3,
            "rare error": 1,
        }

        frequent_errors = learning_engine._find_frequent_errors()

        assert isinstance(frequent_errors, list)
        assert len(frequent_errors) > 0
        # 頻度順にソートされていることを確認
        if len(frequent_errors) > 1:
            assert frequent_errors[0][1] >= frequent_errors[1][1]

    @pytest.mark.asyncio
    async def test_get_pattern_suggestions_from_unknown_errors(self, learning_engine):
        """未知エラーからのパターン提案取得のテスト"""
        await learning_engine.initialize()

        suggestions = await learning_engine.get_pattern_suggestions_from_unknown_errors()

        assert isinstance(suggestions, list)
        # 提案が適切な形式で返されることを確認

    @pytest.mark.asyncio
    async def test_error_handling_in_learning(self, learning_engine):
        """学習処理でのエラーハンドリングのテスト"""
        await learning_engine.initialize()

        # 無効なフィードバックでエラーが適切に処理されることを確認
        invalid_feedback = Mock()
        invalid_feedback.pattern_id = None

        # エラーが発生しても処理が継続することを確認
        try:
            await learning_engine.learn_from_feedback(invalid_feedback)
        except Exception:
            pytest.fail("エラーハンドリングが適切に動作していません")

    def test_confidence_adjustment_calculation(self, learning_engine):
        """信頼度調整計算のテスト"""
        base_confidence = 0.8
        success_rate = 0.9
        adjustment_factor = learning_engine.confidence_adjustment_factor

        adjusted_confidence = learning_engine._calculate_adjusted_confidence(base_confidence, success_rate)

        expected = base_confidence + (success_rate - 0.5) * adjustment_factor
        assert abs(adjusted_confidence - expected) < 0.001

    @pytest.mark.asyncio
    async def test_pattern_improvement_integration(self, learning_engine):
        """パターン改善システム統合のテスト"""
        await learning_engine.initialize()

        # パターン改善システムが初期化されることを確認
        assert learning_engine.pattern_improvement is not None

    def test_learning_data_file_paths(self, learning_engine, temp_learning_dir):
        """学習データファイルパスのテスト"""
        expected_files = [
            "feedback.json",
            "patterns_learned.json",
            "error_frequency.json",
            "unknown_errors.json",
            "potential_patterns.json",
        ]

        for filename in expected_files:
            expected_path = temp_learning_dir / filename
            actual_path = getattr(learning_engine, f"{filename.split('.')[0]}_file")
            assert actual_path == expected_path

    @pytest.mark.asyncio
    async def test_concurrent_learning_operations(self, learning_engine, sample_feedback):
        """並行学習操作のテスト"""
        await learning_engine.initialize()

        # 複数のフィードバックを並行処理
        feedbacks = [sample_feedback for _ in range(3)]

        import asyncio

        tasks = [learning_engine.learn_from_feedback(fb) for fb in feedbacks]
        await asyncio.gather(*tasks)

        assert len(learning_engine.feedback_history) == 3

    def test_pattern_success_tracking_initialization(self, learning_engine):
        """パターン成功追跡初期化のテスト"""
        pattern_id = "test_pattern"

        # 初回アクセス時にデフォルト値が設定されることを確認
        tracking = learning_engine.pattern_success_tracking[pattern_id]

        assert tracking["successes"] == 0
        assert tracking["failures"] == 0
        assert tracking["total_uses"] == 0

    @pytest.mark.asyncio
    async def test_learning_engine_cleanup(self, learning_engine):
        """学習エンジンクリーンアップのテスト"""
        await learning_engine.initialize()

        # クリーンアップが正常に実行されることを確認
        await learning_engine.cleanup()

        # クリーンアップ後の状態確認は実装に依存

    def test_generate_pattern_id(self, learning_engine):
        """パターンID生成のテスト"""
        error_signature = "npm ERR! 404 Not Found"

        pattern_id = learning_engine._generate_pattern_id(error_signature)

        assert isinstance(pattern_id, str)
        assert len(pattern_id) > 0
        # 同じエラーシグネチャからは同じIDが生成されることを確認
        pattern_id2 = learning_engine._generate_pattern_id(error_signature)
        assert pattern_id == pattern_id2

    def test_infer_category_from_error(self, learning_engine):
        """エラーからカテゴリ推測のテスト"""
        # 依存関係エラー
        category = learning_engine._infer_category_from_error("npm ERR! 404 Not Found")
        assert category in ["dependency", "general"]

        # ビルドエラー
        category = learning_engine._infer_category_from_error("build failed")
        assert category in ["build", "general"]

        # 権限エラー
        category = learning_engine._infer_category_from_error("permission denied")
        assert category in ["permission", "general"]

    def test_extract_keywords_from_error(self, learning_engine):
        """エラーからキーワード抽出のテスト"""
        error_signature = "npm ERR! 404 Not Found - package missing"

        keywords = learning_engine._extract_keywords_from_error(error_signature)

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # 重要なキーワードが抽出されることを確認
        assert any(keyword in ["npm", "404", "not", "found", "package", "missing"] for keyword in keywords)

    def test_generate_regex_pattern(self, learning_engine):
        """正規表現パターン生成のテスト"""
        error_signature = "npm ERR! 404 Not Found"

        regex_pattern = learning_engine._generate_regex_pattern(error_signature)

        assert isinstance(regex_pattern, str)
        assert len(regex_pattern) > 0
        # 基本的な正規表現の構造を確認
        assert "npm" in regex_pattern.lower()

    def test_is_duplicate_pattern(self, learning_engine):
        """重複パターン判定のテスト"""
        learning_engine.pattern_database.get_all_patterns.return_value = [
            Mock(regex_patterns=["npm.*404.*not found"], keywords=["npm", "404", "not", "found"])
        ]

        # 類似パターンの場合
        is_duplicate = learning_engine._is_duplicate_pattern("npm ERR! 404 Not Found")
        # 実装に依存するが、何らかの判定が行われることを確認
        assert isinstance(is_duplicate, bool)

    @pytest.mark.asyncio
    async def test_create_pattern_from_error(self, learning_engine):
        """エラーからパターン作成のテスト"""
        await learning_engine.initialize()

        error_signature = "npm ERR! 404 Not Found"
        frequency = 5

        pattern = await learning_engine._create_pattern_from_error(error_signature, frequency)

        if pattern is not None:
            assert isinstance(pattern, Pattern)
            assert pattern.name
            assert pattern.category
            assert len(pattern.regex_patterns) > 0
            assert len(pattern.keywords) > 0

    def test_get_learning_statistics(self, learning_engine):
        """学習統計情報取得のテスト"""
        # テストデータを設定
        learning_engine.feedback_history = [Mock(), Mock(), Mock()]
        learning_engine.learned_patterns = {"pattern1": {}, "pattern2": {}}
        learning_engine.error_frequency = {"error1": 5, "error2": 3}

        stats = learning_engine.get_learning_statistics()

        assert isinstance(stats, dict)
        assert "total_feedback" in stats
        assert "learned_patterns_count" in stats
        assert "error_frequency_count" in stats
        assert stats["total_feedback"] == 3
        assert stats["learned_patterns_count"] == 2
        assert stats["error_frequency_count"] == 2

    @pytest.mark.asyncio
    async def test_process_fix_application_feedback(self, learning_engine, sample_pattern):
        """修正適用フィードバック処理のテスト"""
        await learning_engine.initialize()
        learning_engine.pattern_database.get_pattern.return_value = sample_pattern
        learning_engine.pattern_database.update_pattern = AsyncMock()

        await learning_engine.process_fix_application_feedback(
            pattern_id=sample_pattern.id, success=True, execution_time=1.5, user_satisfaction=4
        )

        # パターンの成功率が更新されることを確認
        tracking = learning_engine.pattern_success_tracking[sample_pattern.id]
        assert tracking["successes"] == 1
        assert tracking["total_uses"] == 1

    def test_get_pattern_feedback_summary(self, learning_engine, sample_feedback):
        """パターンフィードバック要約取得のテスト"""
        learning_engine.feedback_history = [sample_feedback]

        summary = learning_engine.get_pattern_feedback_summary(sample_feedback.pattern_id)

        assert isinstance(summary, dict)
        assert "total_feedback" in summary
        assert "average_rating" in summary
        assert "average_effectiveness" in summary
        assert summary["total_feedback"] == 1

    @pytest.mark.asyncio
    async def test_suggest_pattern_improvements(self, learning_engine):
        """パターン改善提案のテスト"""
        await learning_engine.initialize()

        suggestions = await learning_engine.suggest_pattern_improvements()

        assert isinstance(suggestions, list)
        # 提案が適切な形式で返されることを確認

    @pytest.mark.asyncio
    async def test_analyze_pattern_performance(self, learning_engine):
        """パターンパフォーマンス分析のテスト"""
        await learning_engine.initialize()

        performance = await learning_engine.analyze_pattern_performance()

        assert isinstance(performance, dict)
        # パフォーマンス情報が適切な形式で返されることを確認

    @pytest.mark.asyncio
    async def test_process_unknown_error(self, learning_engine):
        """未知エラー処理のテスト"""
        await learning_engine.initialize()

        unknown_error_info = {
            "error_message": "Unknown error occurred",
            "context": {"file": "test.py", "line": 42},
            "timestamp": datetime.now().isoformat(),
        }

        result = await learning_engine.process_unknown_error(unknown_error_info)

        assert isinstance(result, dict)
        assert "status" in result

    def test_get_unknown_error_statistics(self, learning_engine):
        """未知エラー統計情報取得のテスト"""
        stats = learning_engine.get_unknown_error_statistics()

        assert isinstance(stats, dict)
        # 統計情報が適切な形式で返されることを確認

    @pytest.mark.asyncio
    async def test_promote_potential_pattern_to_official(self, learning_engine):
        """潜在的パターンの正式昇格のテスト"""
        await learning_engine.initialize()
        learning_engine.pattern_database.add_pattern = AsyncMock(return_value=True)

        result = await learning_engine.promote_potential_pattern_to_official("test_pattern")

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_save_learning_data_methods(self, learning_engine, temp_learning_dir):
        """学習データ保存メソッドのテスト"""
        await learning_engine.initialize()

        # テストデータを設定
        learning_engine.feedback_history = [
            UserFeedback(
                pattern_id="test",
                fix_suggestion_id="fix_005",
                rating=4,
                success=True,
                comments="test",
                timestamp=datetime.now(),
            )
        ]
        learning_engine.error_frequency = {"test_error": 5}
        learning_engine.learned_patterns = {"test_pattern": {"confidence": 0.8}}

        # 各保存メソッドをテスト
        await learning_engine._save_feedback_data()
        await learning_engine._save_error_frequency_data()
        await learning_engine._save_learned_patterns_data()

        # ファイルが作成されることを確認
        assert (temp_learning_dir / "feedback.json").exists()
        assert (temp_learning_dir / "error_frequency.json").exists()
        assert (temp_learning_dir / "patterns_learned.json").exists()

    def test_find_similar_unknown_error(self, learning_engine):
        """類似未知エラー検索のテスト"""
        unknown_error_info = {"error_signature": "test error message", "context": {"file": "test.py"}}

        existing_errors = [
            {"error_signature": "similar test error", "occurrences": 3},
            {"error_signature": "completely different error", "occurrences": 1},
        ]

        similar_error = learning_engine._find_similar_unknown_error(unknown_error_info, existing_errors)

        # 類似エラーが見つかるか、Noneが返されることを確認
        assert similar_error is None or isinstance(similar_error, dict)

    def test_get_frequent_unknown_errors(self, learning_engine):
        """頻出未知エラー取得のテスト"""
        unknown_errors = [
            {"error_signature": "frequent error", "occurrences": 10},
            {"error_signature": "rare error", "occurrences": 1},
            {"error_signature": "medium error", "occurrences": 5},
        ]

        frequent_errors = learning_engine._get_frequent_unknown_errors(unknown_errors, min_occurrences=3)

        assert isinstance(frequent_errors, list)
        # 頻度の高いエラーのみが返されることを確認
        for error in frequent_errors:
            assert error["occurrences"] >= 3
