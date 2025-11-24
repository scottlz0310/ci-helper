"""
pattern_improvement.py のテスト

パターン改善システムの機能をテストします。
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, mock_open, patch

import pytest

from ci_helper.ai.models import Pattern, UserFeedback
from ci_helper.ai.pattern_database import PatternDatabase
from ci_helper.ai.pattern_improvement import PatternImprovement, PatternImprovementSystem


class TestPatternImprovement:
    """PatternImprovement のテストクラス"""

    def test_init(self):
        """PatternImprovement初期化のテスト"""
        improvement = PatternImprovement(
            pattern_id="test_pattern",
            improvement_type="regex_update",
            description="正規表現の改善",
            suggested_changes={"regex_patterns": ["new_pattern"]},
            confidence=0.8,
            supporting_data={"feedback_count": 10},
        )

        assert improvement.pattern_id == "test_pattern"
        assert improvement.improvement_type == "regex_update"
        assert improvement.description == "正規表現の改善"
        assert improvement.suggested_changes == {"regex_patterns": ["new_pattern"]}
        assert improvement.confidence == 0.8
        assert improvement.supporting_data == {"feedback_count": 10}
        assert isinstance(improvement.created_at, datetime)


class TestPatternImprovementSystem:
    """PatternImprovementSystem のテストクラス"""

    @pytest.fixture
    def mock_pattern_database(self):
        """モックパターンデータベース"""
        return Mock(spec=PatternDatabase)

    @pytest.fixture
    def improvement_system(self, mock_pattern_database, tmp_path):
        """PatternImprovementSystem インスタンス"""
        return PatternImprovementSystem(
            pattern_database=mock_pattern_database,
            improvement_data_dir=tmp_path / "learning",
            min_feedback_for_improvement=3,
            improvement_threshold=0.3,
        )

    @pytest.fixture
    def sample_pattern(self):
        """サンプルパターン"""
        return Pattern(
            id="test_pattern_001",
            name="テストパターン",
            category="test",
            regex_patterns=[r"error:\s+(.+)"],
            keywords=["error", "failed"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.7,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=False,
        )

    @pytest.fixture
    def sample_feedback_history(self):
        """サンプルフィードバック履歴"""
        base_time = datetime.now()
        return [
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_001",
                rating=4,
                success=True,
                comments="良い修正でした",
                timestamp=base_time - timedelta(days=1),
            ),
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_002",
                rating=2,
                success=False,
                comments="修正が不十分でした",
                timestamp=base_time - timedelta(days=2),
            ),
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_003",
                rating=5,
                success=True,
                comments="完璧な修正",
                timestamp=base_time - timedelta(days=3),
            ),
            UserFeedback(
                pattern_id="test_pattern_002",
                fix_suggestion_id="fix_004",
                rating=1,
                success=False,
                comments="全く役に立たない",
                timestamp=base_time - timedelta(days=4),
            ),
        ]

    def test_init(self, mock_pattern_database, tmp_path):
        """初期化のテスト"""
        system = PatternImprovementSystem(
            pattern_database=mock_pattern_database,
            improvement_data_dir=tmp_path / "learning",
            min_feedback_for_improvement=5,
            improvement_threshold=0.2,
        )

        assert system.pattern_database == mock_pattern_database
        assert system.improvement_data_dir == tmp_path / "learning"
        assert system.min_feedback_for_improvement == 5
        assert system.improvement_threshold == 0.2
        assert system._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, improvement_system):
        """初期化成功のテスト"""
        with patch.object(improvement_system, "_load_improvement_data") as mock_load:
            mock_load.return_value = None

            await improvement_system.initialize()

            assert improvement_system._initialized is True
            mock_load.assert_called_once()
            assert improvement_system.improvement_data_dir.exists()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, improvement_system):
        """既に初期化済みの場合のテスト"""
        improvement_system._initialized = True

        with patch.object(improvement_system, "_load_improvement_data") as mock_load:
            await improvement_system.initialize()

            mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_improvement_data_success(self, improvement_system):
        """改善データ読み込み成功のテスト"""
        # テストデータを準備
        improvement_history = [{"pattern_id": "test", "type": "regex_update"}]
        pattern_analytics = {"test_pattern": {"success_rate": 0.8}}

        improvement_system.improvement_history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(improvement_system.improvement_history_file, "w") as f:
            json.dump(improvement_history, f)

        with open(improvement_system.pattern_analytics_file, "w") as f:
            json.dump(pattern_analytics, f)

        await improvement_system._load_improvement_data()

        assert improvement_system.improvement_history == improvement_history
        assert improvement_system.pattern_analytics == pattern_analytics

    @pytest.mark.asyncio
    async def test_load_improvement_data_no_files(self, improvement_system):
        """改善データファイルが存在しない場合のテスト"""
        await improvement_system._load_improvement_data()

        assert improvement_system.improvement_history == []
        assert improvement_system.pattern_analytics == {}

    @pytest.mark.asyncio
    async def test_analyze_pattern_performance_success(self, improvement_system, sample_feedback_history):
        """パターンパフォーマンス分析成功のテスト"""
        with (
            patch.object(improvement_system, "initialize") as mock_init,
            patch.object(improvement_system, "_save_pattern_analytics") as mock_save,
        ):
            mock_init.return_value = None
            mock_save.return_value = None
            improvement_system._initialized = True

            result = await improvement_system.analyze_pattern_performance(sample_feedback_history)

            assert "test_pattern_001" in result
            assert "test_pattern_002" in result

            pattern_001_perf = result["test_pattern_001"]
            assert pattern_001_perf["total_feedback"] == 3
            assert pattern_001_perf["successful_feedback"] == 2
            assert pattern_001_perf["failed_feedback"] == 1
            assert pattern_001_perf["success_rate"] == 2 / 3
            assert pattern_001_perf["average_rating"] == (4 + 2 + 5) / 3

            mock_save.assert_called_once()

    def test_identify_pattern_issues_low_success_rate(self, improvement_system):
        """低い成功率の問題特定テスト"""
        performance = {
            "success_rate": 0.5,
            "average_rating": 3.0,
            "total_feedback": 10,
            "rating_trend": [{"rating": 3}],
        }

        issues = improvement_system._identify_pattern_issues("test_pattern", performance)

        assert "低い成功率" in issues

    def test_identify_pattern_issues_low_rating(self, improvement_system):
        """低い評価の問題特定テスト"""
        performance = {
            "success_rate": 0.8,
            "average_rating": 2.0,
            "total_feedback": 10,
            "rating_trend": [{"rating": 2}],
        }

        issues = improvement_system._identify_pattern_issues("test_pattern", performance)

        assert "低い評価" in issues

    def test_identify_pattern_issues_performance_degradation(self, improvement_system):
        """パフォーマンス悪化の問題特定テスト"""
        performance = {
            "success_rate": 0.8,
            "average_rating": 3.5,
            "total_feedback": 10,
            "recent_performance": {"success_rate": 0.5},
            "rating_trend": [{"rating": 3}],
        }

        issues = improvement_system._identify_pattern_issues("test_pattern", performance)

        assert "パフォーマンス悪化" in issues

    def test_identify_pattern_issues_insufficient_feedback(self, improvement_system):
        """フィードバック不足の問題特定テスト"""
        performance = {
            "success_rate": 0.8,
            "average_rating": 3.5,
            "total_feedback": 2,  # min_feedback_for_improvement = 3
            "rating_trend": [{"rating": 3}],
        }

        issues = improvement_system._identify_pattern_issues("test_pattern", performance)

        assert "フィードバック不足" in issues

    @pytest.mark.asyncio
    async def test_suggest_pattern_improvements_success(self, improvement_system, sample_feedback_history):
        """パターン改善提案成功のテスト"""
        with (
            patch.object(improvement_system, "analyze_pattern_performance") as mock_analyze,
            patch.object(improvement_system, "_generate_improvements_for_pattern") as mock_generate,
        ):
            mock_analyze.return_value = {
                "test_pattern_001": {
                    "success_rate": 0.5,  # 改善が必要
                    "total_feedback": 5,
                    "average_rating": 2.0,
                }
            }

            mock_improvement = PatternImprovement(
                pattern_id="test_pattern_001",
                improvement_type="regex_update",
                description="テスト改善",
                suggested_changes={},
                confidence=0.8,
                supporting_data={},
            )
            mock_generate.return_value = [mock_improvement]

            improvement_system._initialized = True

            result = await improvement_system.suggest_pattern_improvements(sample_feedback_history)

            assert len(result) == 1
            assert result[0].pattern_id == "test_pattern_001"
            mock_generate.assert_called_once()

    def test_needs_improvement_insufficient_feedback(self, improvement_system):
        """フィードバック不足で改善不要の判定テスト"""
        performance = {"total_feedback": 2}  # min_feedback_for_improvement = 3

        result = improvement_system._needs_improvement(performance)

        assert result is False

    def test_needs_improvement_low_success_rate(self, improvement_system):
        """低い成功率で改善必要の判定テスト"""
        performance = {
            "total_feedback": 5,
            "success_rate": 0.6,  # 1.0 - improvement_threshold(0.3) = 0.7 を下回る
            "average_rating": 3.0,
        }

        result = improvement_system._needs_improvement(performance)

        assert result is True

    def test_needs_improvement_low_rating(self, improvement_system):
        """低い評価で改善必要の判定テスト"""
        performance = {
            "total_feedback": 5,
            "success_rate": 0.8,
            "average_rating": 2.0,  # 2.5を下回る
        }

        result = improvement_system._needs_improvement(performance)

        assert result is True

    def test_needs_improvement_performance_degradation(self, improvement_system):
        """パフォーマンス悪化で改善必要の判定テスト"""
        performance = {
            "total_feedback": 5,
            "success_rate": 0.8,
            "average_rating": 3.5,
            "recent_performance": {"success_rate": 0.4},  # 0.8 - 0.3 = 0.5を下回る
        }

        result = improvement_system._needs_improvement(performance)

        assert result is True

    def test_needs_improvement_no_issues(self, improvement_system):
        """問題なしで改善不要の判定テスト"""
        performance = {
            "total_feedback": 5,
            "success_rate": 0.8,
            "average_rating": 3.5,
            "recent_performance": {"success_rate": 0.8},
        }

        result = improvement_system._needs_improvement(performance)

        assert result is False

    def test_extract_common_failure_patterns(self, improvement_system):
        """共通失敗パターン抽出のテスト"""
        failed_comments = [
            "permission denied error occurred",
            "access denied when trying to read file",
            "permission error in file system",
            "network timeout happened",
            "connection timeout error",
        ]

        result = improvement_system._extract_common_failure_patterns(failed_comments)

        # 共通フレーズが抽出されることを確認
        assert len(result) > 0
        # "permission" や "denied" などの共通語が含まれることを期待

    def test_enhance_regex_pattern_success(self, improvement_system):
        """正規表現パターン拡張成功のテスト"""
        original_pattern = r"error:\s+(.+)"
        failure_pattern = "permission denied"

        result = improvement_system._enhance_regex_pattern(original_pattern, failure_pattern)

        assert result is not None
        assert "permission" in result or "denied" in result

    def test_enhance_regex_pattern_invalid_regex(self, improvement_system):
        """無効な正規表現での拡張テスト"""
        original_pattern = "[invalid regex"
        failure_pattern = "permission denied"

        result = improvement_system._enhance_regex_pattern(original_pattern, failure_pattern)

        assert result is None

    def test_extract_keywords_from_comments(self, improvement_system):
        """コメントからキーワード抽出のテスト"""
        comments = [
            "permission denied error occurred",
            "access denied when trying to read file",
            "file permission error",
            "network connection failed",
        ]

        result = improvement_system._extract_keywords_from_comments(comments)

        assert len(result) > 0
        # 頻出する単語が抽出されることを確認
        assert any("permission" in keyword.lower() for keyword in result)

    def test_infer_category_from_comments(self, improvement_system):
        """コメントからカテゴリ推測のテスト"""
        permission_comments = [
            "permission denied error",
            "access denied",
            "file permission error",
        ]

        result = improvement_system._infer_category_from_comments(permission_comments)

        assert result == "permission"

    def test_infer_category_from_comments_network(self, improvement_system):
        """ネットワーク関連コメントからカテゴリ推測のテスト"""
        network_comments = [
            "connection timeout",
            "network error occurred",
            "failed to connect to server",
        ]

        result = improvement_system._infer_category_from_comments(network_comments)

        assert result == "network"

    @pytest.mark.asyncio
    async def test_apply_pattern_improvement_success(self, improvement_system, sample_pattern):
        """パターン改善適用成功のテスト"""
        improvement = PatternImprovement(
            pattern_id="test_pattern_001",
            improvement_type="regex_update",
            description="正規表現の改善",
            suggested_changes={"regex_patterns": [r"new_pattern:\s+(.+)"]},
            confidence=0.8,
            supporting_data={},
        )

        with (
            patch.object(improvement_system.pattern_database, "get_pattern") as mock_get,
            patch.object(improvement_system.pattern_database, "update_pattern") as mock_update,
            patch.object(improvement_system, "_save_improvement_history") as mock_save,
        ):
            mock_get.return_value = sample_pattern
            mock_update.return_value = True
            mock_save.return_value = None

            result = await improvement_system.apply_pattern_improvement(improvement)

            assert result is True
            mock_get.assert_called_once_with("test_pattern_001")
            mock_update.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_pattern_improvement_pattern_not_found(self, improvement_system):
        """パターンが見つからない場合の改善適用テスト"""
        improvement = PatternImprovement(
            pattern_id="nonexistent_pattern",
            improvement_type="regex_update",
            description="正規表現の改善",
            suggested_changes={"regex_patterns": [r"new_pattern:\s+(.+)"]},
            confidence=0.8,
            supporting_data={},
        )

        with patch.object(improvement_system.pattern_database, "get_pattern") as mock_get:
            mock_get.return_value = None

            result = await improvement_system.apply_pattern_improvement(improvement)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_improvement_recommendations_success(self, improvement_system, sample_feedback_history):
        """改善推奨事項取得成功のテスト"""
        mock_improvements = [
            PatternImprovement(
                pattern_id="test_pattern_001",
                improvement_type="regex_update",
                description="高信頼度改善",
                suggested_changes={},
                confidence=0.9,
                supporting_data={},
            ),
            PatternImprovement(
                pattern_id="test_pattern_002",
                improvement_type="keyword_add",
                description="低信頼度改善",
                suggested_changes={},
                confidence=0.6,
                supporting_data={},
            ),
        ]

        with patch.object(improvement_system, "suggest_pattern_improvements") as mock_suggest:
            mock_suggest.return_value = mock_improvements

            result = await improvement_system.get_improvement_recommendations(
                sample_feedback_history, max_recommendations=5
            )

            # 信頼度でソートされて返される
            assert len(result) == 2
            assert result[0].confidence == 0.9  # 高い信頼度が最初

    @pytest.mark.asyncio
    async def test_save_improvement_history_success(self, improvement_system):
        """改善履歴保存成功のテスト"""
        improvement_system.improvement_history = [{"pattern_id": "test", "type": "regex_update"}]

        with patch("builtins.open", mock_open()) as mock_file:
            await improvement_system._save_improvement_history()

            mock_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_pattern_analytics_success(self, improvement_system):
        """パターン分析データ保存成功のテスト"""
        improvement_system.pattern_analytics = {"test_pattern": {"success_rate": 0.8}}

        with patch("builtins.open", mock_open()) as mock_file:
            await improvement_system._save_pattern_analytics()

            mock_file.assert_called_once()

    def test_get_improvement_statistics(self, improvement_system):
        """改善統計情報取得のテスト"""
        improvement_system._initialized = True
        improvement_system.improvement_history = [
            {"improvement_type": "regex_update", "applied_at": "2024-01-01T12:00:00"},
            {"improvement_type": "keyword_add", "applied_at": "2024-01-02T12:00:00"},
            {"improvement_type": "regex_update", "applied_at": "2024-01-03T12:00:00"},
        ]

        improvement_system.pattern_analytics = {
            "pattern1": {"success_rate": 0.8},
            "pattern2": {"success_rate": 0.6},
        }

        result = improvement_system.get_improvement_statistics()

        assert result["total_improvements"] == 3
        assert result["improvement_types"]["regex_update"] == 2
        assert result["improvement_types"]["keyword_add"] == 1
        assert result["analyzed_patterns"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_success(self, improvement_system):
        """クリーンアップ成功のテスト"""
        improvement_system._initialized = True

        with (
            patch.object(improvement_system, "_save_improvement_history") as mock_save_history,
            patch.object(improvement_system, "_save_pattern_analytics") as mock_save_analytics,
        ):
            mock_save_history.return_value = None
            mock_save_analytics.return_value = None

            await improvement_system.cleanup()

            mock_save_history.assert_called_once()
            mock_save_analytics.assert_called_once()
            # Note: The actual implementation doesn't set _initialized to False

    @pytest.mark.asyncio
    async def test_cleanup_not_initialized(self, improvement_system):
        """未初期化状態でのクリーンアップテスト"""
        improvement_system._initialized = False

        with patch.object(improvement_system, "_save_improvement_history") as mock_save_history:
            await improvement_system.cleanup()

            mock_save_history.assert_not_called()
