"""
feedback_collector.py のテスト

ユーザーフィードバック収集システムの機能をテストします。
"""

import json
from datetime import datetime
from unittest.mock import mock_open, patch

import pytest
from ci_helper.ai.feedback_collector import FeedbackCollector
from ci_helper.ai.models import FixSuggestion, Pattern, PatternMatch, UserFeedback


class TestFeedbackCollector:
    """FeedbackCollector のテストクラス"""

    @pytest.fixture
    def feedback_collector(self, tmp_path):
        """FeedbackCollector インスタンス"""
        return FeedbackCollector(
            feedback_dir=tmp_path / "feedback",
            auto_save=True,
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
    def sample_pattern_match(self, sample_pattern):
        """サンプルパターンマッチ"""
        return PatternMatch(
            pattern=sample_pattern,
            confidence=0.85,
            match_positions=[10, 20],
            extracted_context="error: test failed",
            match_strength=0.9,
            supporting_evidence=["error keyword found"],
        )

    @pytest.fixture
    def sample_fix_suggestion(self):
        """サンプル修正提案"""
        return FixSuggestion(
            title="テスト修正",
            description="テストエラーの修正提案",
            confidence=0.8,
        )

    @pytest.fixture
    def sample_feedback_history(self):
        """サンプルフィードバック履歴"""
        return [
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_001",
                rating=4,
                success=True,
                comments="良い修正でした",
                timestamp=datetime.now(),
            ),
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_002",
                rating=2,
                success=False,
                comments="修正が不十分でした",
                timestamp=datetime.now(),
            ),
            UserFeedback(
                pattern_id="test_pattern_002",
                fix_suggestion_id="fix_003",
                rating=5,
                success=True,
                comments="完璧な修正",
                timestamp=datetime.now(),
            ),
        ]

    def test_init(self, tmp_path):
        """初期化のテスト"""
        collector = FeedbackCollector(
            feedback_dir=tmp_path / "feedback",
            auto_save=False,
        )

        assert collector.feedback_dir == tmp_path / "feedback"
        assert collector.auto_save is False
        assert collector.feedback_history == []
        assert collector.feedback_sessions == {}
        assert collector.pending_feedback == {}
        assert collector._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, feedback_collector):
        """初期化成功のテスト"""
        with patch.object(feedback_collector, "_load_feedback_data") as mock_load:
            mock_load.return_value = None

            await feedback_collector.initialize()

            assert feedback_collector._initialized is True
            mock_load.assert_called_once()
            assert feedback_collector.feedback_dir.exists()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, feedback_collector):
        """既に初期化済みの場合のテスト"""
        feedback_collector._initialized = True

        with patch.object(feedback_collector, "_load_feedback_data") as mock_load:
            await feedback_collector.initialize()

            mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_feedback_data_success(self, feedback_collector, sample_feedback_history):
        """フィードバックデータ読み込み成功のテスト"""
        # テストデータを準備
        feedback_data = [
            {
                "pattern_id": fb.pattern_id,
                "fix_suggestion_id": fb.fix_suggestion_id,
                "rating": fb.rating,
                "success": fb.success,
                "comments": fb.comments,
                "timestamp": fb.timestamp.isoformat(),
            }
            for fb in sample_feedback_history
        ]

        sessions_data = {"session_001": {"pattern_id": "test_pattern_001"}}

        feedback_collector.feedback_file.parent.mkdir(parents=True, exist_ok=True)

        with open(feedback_collector.feedback_file, "w") as f:
            json.dump(feedback_data, f)

        with open(feedback_collector.feedback_sessions_file, "w") as f:
            json.dump(sessions_data, f)

        await feedback_collector._load_feedback_data()

        assert len(feedback_collector.feedback_history) == 3
        assert feedback_collector.feedback_history[0].pattern_id == "test_pattern_001"
        assert feedback_collector.feedback_sessions == sessions_data

    @pytest.mark.asyncio
    async def test_load_feedback_data_no_files(self, feedback_collector):
        """フィードバックデータファイルが存在しない場合のテスト"""
        await feedback_collector._load_feedback_data()

        assert feedback_collector.feedback_history == []
        assert feedback_collector.feedback_sessions == {}

    @pytest.mark.asyncio
    async def test_collect_feedback_for_suggestion_interactive_success(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """対話的フィードバック収集成功のテスト"""

        def mock_callback(prompt):
            return "評価: 4\n成功: yes\nコメント: 良い修正でした"

        with (
            patch.object(feedback_collector, "initialize") as mock_init,
            patch.object(feedback_collector, "_save_feedback_data") as mock_save,
        ):
            mock_init.return_value = None
            mock_save.return_value = None
            feedback_collector._initialized = True

            feedback = await feedback_collector.collect_feedback_for_suggestion(
                sample_pattern_match, sample_fix_suggestion, interactive=True, feedback_callback=mock_callback
            )

            assert feedback is not None
            assert feedback.rating == 4
            assert feedback.success is True
            assert feedback.comments == "良い修正でした"
            assert feedback.pattern_id == sample_pattern_match.pattern.id
            assert len(feedback_collector.feedback_history) == 1
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_feedback_for_suggestion_non_interactive(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """非対話的フィードバック収集のテスト"""
        with (
            patch.object(feedback_collector, "initialize") as mock_init,
            patch.object(feedback_collector, "_save_feedback_data") as mock_save,
        ):
            mock_init.return_value = None
            mock_save.return_value = None
            feedback_collector._initialized = True

            feedback = await feedback_collector.collect_feedback_for_suggestion(
                sample_pattern_match, sample_fix_suggestion, interactive=False
            )

            assert feedback is not None
            assert feedback.rating in [2, 3, 4]  # 信頼度に基づく評価
            assert feedback.comments == "自動生成されたデフォルトフィードバック"
            assert feedback.pattern_id == sample_pattern_match.pattern.id
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_feedback_for_suggestion_cancelled(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """フィードバック収集キャンセルのテスト"""

        def mock_callback(prompt):
            return "cancel"

        with patch.object(feedback_collector, "initialize") as mock_init:
            mock_init.return_value = None
            feedback_collector._initialized = True

            feedback = await feedback_collector.collect_feedback_for_suggestion(
                sample_pattern_match, sample_fix_suggestion, interactive=True, feedback_callback=mock_callback
            )

            assert feedback is None
            assert len(feedback_collector.feedback_history) == 0

    @pytest.mark.asyncio
    async def test_collect_default_feedback_high_confidence(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """高信頼度でのデフォルトフィードバック収集テスト"""
        # 高信頼度に設定
        sample_pattern_match.confidence = 0.9
        sample_fix_suggestion.confidence = 0.8

        feedback = await feedback_collector._collect_default_feedback(
            sample_pattern_match, sample_fix_suggestion, "session_001"
        )

        assert feedback.rating == 4
        assert feedback.success is True
        assert feedback.comments == "自動生成されたデフォルトフィードバック"

    @pytest.mark.asyncio
    async def test_collect_default_feedback_medium_confidence(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """中信頼度でのデフォルトフィードバック収集テスト"""
        # 中信頼度に設定
        sample_pattern_match.confidence = 0.7
        sample_fix_suggestion.confidence = 0.6

        feedback = await feedback_collector._collect_default_feedback(
            sample_pattern_match, sample_fix_suggestion, "session_001"
        )

        assert feedback.rating == 3
        assert feedback.success is True

    @pytest.mark.asyncio
    async def test_collect_default_feedback_low_confidence(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """低信頼度でのデフォルトフィードバック収集テスト"""
        # 低信頼度に設定
        sample_pattern_match.confidence = 0.4
        sample_fix_suggestion.confidence = 0.3

        feedback = await feedback_collector._collect_default_feedback(
            sample_pattern_match, sample_fix_suggestion, "session_001"
        )

        assert feedback.rating == 2
        assert feedback.success is False

    def test_create_feedback_prompt(self, feedback_collector, sample_pattern_match, sample_fix_suggestion):
        """フィードバックプロンプト作成のテスト"""
        prompt = feedback_collector._create_feedback_prompt(sample_pattern_match, sample_fix_suggestion)

        assert "テストパターン" in prompt
        assert "test" in prompt
        assert "テスト修正" in prompt
        assert "評価:" in prompt
        assert "成功:" in prompt
        assert "コメント:" in prompt

    def test_parse_feedback_response_valid(self, feedback_collector):
        """有効なフィードバックレスポンス解析のテスト"""
        response = "評価: 4\n成功: yes\nコメント: 良い修正でした"

        result = feedback_collector._parse_feedback_response(response)

        assert result["rating"] == 4
        assert result["success"] is True
        assert result["comments"] == "良い修正でした"

    def test_parse_feedback_response_minimal(self, feedback_collector):
        """最小限のフィードバックレスポンス解析のテスト"""
        response = "評価: 3\n成功: no"

        result = feedback_collector._parse_feedback_response(response)

        assert result["rating"] == 3
        assert result["success"] is False
        assert result["comments"] == ""

    def test_parse_feedback_response_invalid_rating(self, feedback_collector):
        """無効な評価でのフィードバックレスポンス解析のテスト"""
        response = "評価: 10\n成功: yes\nコメント: テスト"

        result = feedback_collector._parse_feedback_response(response)

        assert result["rating"] == 3  # デフォルト値
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_collect_batch_feedback_success(
        self, feedback_collector, sample_pattern_match, sample_fix_suggestion
    ):
        """バッチフィードバック収集成功のテスト"""
        pattern_matches = [sample_pattern_match]

        with patch.object(feedback_collector, "collect_feedback_for_suggestion") as mock_collect:
            mock_feedback = UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_001",
                rating=4,
                success=True,
                comments="テスト",
                timestamp=datetime.now(),
            )
            mock_collect.return_value = mock_feedback

            result = await feedback_collector.collect_batch_feedback(pattern_matches, [sample_fix_suggestion])

            assert len(result) == 1
            assert result[0] == mock_feedback
            mock_collect.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_fix_application_result_success(self, feedback_collector):
        """修正適用結果記録成功のテスト"""
        feedback_collector._initialized = True
        feedback_collector.feedback_history = [
            UserFeedback(
                pattern_id="test_pattern_001",
                fix_suggestion_id="fix_001",
                rating=4,
                success=True,
                comments="テスト",
                timestamp=datetime.now(),
            )
        ]

        with patch.object(feedback_collector, "_save_feedback_data") as mock_save:
            mock_save.return_value = None

            await feedback_collector.record_fix_application_result(
                "test_pattern_001", "fix_001", True, "修正が成功しました"
            )

            # フィードバックが更新されることを確認
            mock_save.assert_called_once()

    def test_get_feedback_for_pattern(self, feedback_collector, sample_feedback_history):
        """パターン別フィードバック取得のテスト"""
        feedback_collector.feedback_history = sample_feedback_history

        result = feedback_collector.get_feedback_for_pattern("test_pattern_001")

        assert len(result) == 2
        assert all(fb.pattern_id == "test_pattern_001" for fb in result)

    def test_get_feedback_for_pattern_not_found(self, feedback_collector, sample_feedback_history):
        """存在しないパターンのフィードバック取得テスト"""
        feedback_collector.feedback_history = sample_feedback_history

        result = feedback_collector.get_feedback_for_pattern("nonexistent_pattern")

        assert result == []

    def test_get_feedback_statistics_specific_pattern(self, feedback_collector, sample_feedback_history):
        """特定パターンのフィードバック統計取得のテスト"""
        feedback_collector.feedback_history = sample_feedback_history

        result = feedback_collector.get_feedback_statistics("test_pattern_001")

        assert result["total_feedback"] == 2
        assert result["successful_feedback"] == 1
        assert result["failed_feedback"] == 1
        assert result["average_rating"] == 3.0
        assert result["success_rate"] == 0.5

    def test_get_feedback_statistics_all_patterns(self, feedback_collector, sample_feedback_history):
        """全パターンのフィードバック統計取得のテスト"""
        feedback_collector.feedback_history = sample_feedback_history

        result = feedback_collector.get_feedback_statistics()

        assert result["total_feedback"] == 3
        assert result["successful_feedback"] == 2
        assert result["failed_feedback"] == 1
        assert result["average_rating"] == (4 + 2 + 5) / 3
        assert result["success_rate"] == 2 / 3

    @pytest.mark.asyncio
    async def test_export_feedback_data_success(self, feedback_collector, sample_feedback_history, tmp_path):
        """フィードバックデータエクスポート成功のテスト"""
        feedback_collector.feedback_history = sample_feedback_history
        feedback_collector.feedback_sessions = {"session_001": {"pattern_id": "test"}}
        export_path = tmp_path / "export.json"

        result = await feedback_collector.export_feedback_data(export_path)

        assert result is True
        assert export_path.exists()

        # エクスポートされたデータを確認
        with open(export_path) as f:
            exported_data = json.load(f)

        assert "feedback_history" in exported_data
        assert "feedback_sessions" in exported_data
        assert len(exported_data["feedback_history"]) == 3

    @pytest.mark.asyncio
    async def test_export_feedback_data_error(self, feedback_collector, tmp_path):
        """フィードバックデータエクスポートエラーのテスト"""
        # 書き込み不可能なパスを指定
        export_path = tmp_path / "readonly" / "export.json"

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = await feedback_collector.export_feedback_data(export_path)

            assert result is False

    @pytest.mark.asyncio
    async def test_save_feedback_data_success(self, feedback_collector, sample_feedback_history):
        """フィードバックデータ保存成功のテスト"""
        feedback_collector.feedback_history = sample_feedback_history
        feedback_collector.feedback_sessions = {"session_001": {"pattern_id": "test"}}

        with patch("builtins.open", mock_open()) as mock_file:
            await feedback_collector._save_feedback_data()

            # ファイルが2回開かれることを確認（履歴とセッション）
            assert mock_file.call_count == 2

    @pytest.mark.asyncio
    async def test_save_feedback_data_error(self, feedback_collector):
        """フィードバックデータ保存エラーのテスト"""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # エラーが発生しても例外が発生しないことを確認
            await feedback_collector._save_feedback_data()

    @pytest.mark.asyncio
    async def test_cleanup_success(self, feedback_collector):
        """クリーンアップ成功のテスト"""
        feedback_collector._initialized = True

        with patch.object(feedback_collector, "_save_feedback_data") as mock_save:
            mock_save.return_value = None

            await feedback_collector.cleanup()

            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_not_initialized(self, feedback_collector):
        """未初期化状態でのクリーンアップテスト"""
        feedback_collector._initialized = False

        with patch.object(feedback_collector, "_save_feedback_data") as mock_save:
            await feedback_collector.cleanup()

            mock_save.assert_not_called()

    def test_parse_feedback_response_english_format(self, feedback_collector):
        """英語形式のフィードバックレスポンス解析のテスト"""
        response = "rating: 5\nsuccess: yes\ncomment: Great fix!"

        result = feedback_collector._parse_feedback_response(response)

        assert result["rating"] == 5
        assert result["success"] is True
        assert result["comments"] == "Great fix!"

    def test_parse_feedback_response_mixed_case(self, feedback_collector):
        """大文字小文字混在のフィードバックレスポンス解析のテスト"""
        response = "評価: 3\n成功: YES\nコメント: OK"

        result = feedback_collector._parse_feedback_response(response)

        assert result["rating"] == 3
        assert result["success"] is True
        assert result["comments"] == "OK"
