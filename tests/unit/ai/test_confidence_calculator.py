"""
信頼度計算アルゴリズムのユニットテスト

信頼度計算の正確性とアルゴリズムの妥当性をテストします。
"""

from datetime import datetime, timedelta

import pytest

from src.ci_helper.ai.confidence_calculator import ConfidenceCalculator
from src.ci_helper.ai.models import FixSuggestion, Pattern, PatternMatch, Priority


class TestConfidenceCalculator:
    """信頼度計算機のテスト"""

    @pytest.fixture
    def confidence_calculator(self):
        """信頼度計算機のインスタンス"""
        return ConfidenceCalculator()

    @pytest.fixture
    def sample_pattern(self):
        """テスト用パターン"""
        return Pattern(
            id="test_pattern",
            name="テストパターン",
            category="test",
            regex_patterns=[r"error"],
            keywords=["error", "failed"],
            context_requirements=["docker", "container"],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now() - timedelta(days=10),
            updated_at=datetime.now() - timedelta(days=5),
        )

    @pytest.fixture
    def sample_pattern_match(self, sample_pattern):
        """テスト用パターンマッチ"""
        return PatternMatch(
            pattern=sample_pattern,
            confidence=0.0,  # 計算で設定される
            match_positions=[100, 200],
            extracted_context="Docker container error occurred while running application",
            match_strength=0.85,
            supporting_evidence=["error message", "stack trace", "log context"],
        )

    @pytest.fixture
    def sample_fix_suggestion(self):
        """テスト用修正提案"""
        return FixSuggestion(
            title="Docker権限修正",
            description="Docker権限エラーを修正します",
            priority=Priority.HIGH,
            estimated_effort="5分",
            confidence=0.8,
            code_changes=[],
        )

    def test_calculate_pattern_confidence_basic(self, confidence_calculator, sample_pattern_match):
        """基本的なパターン信頼度計算のテスト"""
        confidence = confidence_calculator.calculate_pattern_confidence(sample_pattern_match)

        # 信頼度が適切な範囲内であることを確認
        assert 0.0 <= confidence <= 1.0

        # 高い基本信頼度と成功率を持つパターンなので、ある程度高い信頼度が期待される
        assert confidence > 0.5

    def test_calculate_pattern_confidence_components(self, sample_pattern_match):
        """信頼度計算の各コンポーネントのテスト"""
        # カスタム重みで計算機を作成
        calculator = ConfidenceCalculator(
            base_weight=0.5,
            success_rate_weight=0.3,
            context_weight=0.1,
            recency_weight=0.1,
        )

        confidence = calculator.calculate_pattern_confidence(sample_pattern_match)

        # 各コンポーネントが適切に重み付けされていることを確認
        assert 0.0 <= confidence <= 1.0

        # 基本信頼度が高いパターンなので、ある程度の信頼度が期待される
        pattern = sample_pattern_match.pattern
        expected_min = pattern.confidence_base * 0.5 * sample_pattern_match.match_strength * 0.5
        assert confidence >= expected_min

    def test_calculate_fix_confidence(self, confidence_calculator, sample_fix_suggestion, sample_pattern_match):
        """修正提案信頼度計算のテスト"""
        confidence = confidence_calculator.calculate_fix_confidence(sample_fix_suggestion, sample_pattern_match)

        # 信頼度が適切な範囲内であることを確認
        assert 0.0 <= confidence <= 1.0

        # パターンマッチと修正提案の両方が高い信頼度を持つので、ある程度高い信頼度が期待される
        assert confidence > 0.3

    def test_adjust_confidence_by_context(self, confidence_calculator):
        """コンテキストによる信頼度調整のテスト"""
        base_confidence = 0.7

        # 良いコンテキスト
        good_context = {
            "log_length": 1000,
            "error_type": "syntax_error",
            "multiple_matches": False,
            "project_type": "python",
        }

        adjusted_good = confidence_calculator.adjust_confidence_by_context(base_confidence, good_context)
        assert adjusted_good >= base_confidence  # 良いコンテキストは信頼度を上げるか維持

        # 悪いコンテキスト
        bad_context = {
            "log_length": 50,  # 短すぎるログ
            "error_type": "unknown",
            "multiple_matches": True,
            "project_type": "unknown",
        }

        adjusted_bad = confidence_calculator.adjust_confidence_by_context(base_confidence, bad_context)
        assert adjusted_bad <= base_confidence  # 悪いコンテキストは信頼度を下げるか維持

    def test_resolve_competing_patterns(self, confidence_calculator, sample_pattern):
        """競合パターン解決のテスト"""
        # 複数のパターンマッチを作成
        pattern_matches = []

        for i in range(3):
            pattern = Pattern(
                id=f"pattern_{i}",
                name=f"パターン{i}",
                category="test",
                regex_patterns=[r"error"],
                keywords=["error"],
                context_requirements=[],
                confidence_base=0.6 + i * 0.1,  # 異なる基本信頼度
                success_rate=0.7 + i * 0.1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            pattern_match = PatternMatch(
                pattern=pattern,
                confidence=0.0,
                match_positions=[100],
                extracted_context="Error occurred in application",
                match_strength=0.7 + i * 0.1,
                supporting_evidence=[f"evidence_{j}" for j in range(i + 1)],
            )

            pattern_matches.append(pattern_match)

        # 競合解決を実行
        resolved_matches = confidence_calculator.resolve_competing_patterns(pattern_matches)

        # 結果の検証
        assert len(resolved_matches) <= len(pattern_matches)
        assert len(resolved_matches) > 0  # 少なくとも1つは選択される

        # 最も高いスコアのパターンが最初に来ることを確認
        if len(resolved_matches) > 1:
            first_confidence = confidence_calculator.calculate_pattern_confidence(resolved_matches[0])
            second_confidence = confidence_calculator.calculate_pattern_confidence(resolved_matches[1])
            assert first_confidence >= second_confidence

    def test_confidence_with_different_match_strengths(self, confidence_calculator, sample_pattern):
        """異なるマッチ強度での信頼度テスト"""
        match_strengths = [0.3, 0.5, 0.7, 0.9]
        confidences = []

        for strength in match_strengths:
            pattern_match = PatternMatch(
                pattern=sample_pattern,
                confidence=0.0,
                match_positions=[100],
                extracted_context="Test context",
                match_strength=strength,
                supporting_evidence=["evidence"],
            )

            confidence = confidence_calculator.calculate_pattern_confidence(pattern_match)
            confidences.append(confidence)

        # マッチ強度が高いほど信頼度も高くなることを確認
        for i in range(1, len(confidences)):
            assert confidences[i] >= confidences[i - 1], f"信頼度が期待通りに増加していません: {confidences}"

    def test_confidence_with_different_success_rates(self, confidence_calculator):
        """異なる成功率での信頼度テスト"""
        success_rates = [0.5, 0.7, 0.8, 0.95]
        confidences = []

        for success_rate in success_rates:
            pattern = Pattern(
                id="test_pattern",
                name="テストパターン",
                category="test",
                regex_patterns=[r"error"],
                keywords=["error"],
                context_requirements=[],
                confidence_base=0.8,
                success_rate=success_rate,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            pattern_match = PatternMatch(
                pattern=pattern,
                confidence=0.0,
                match_positions=[100],
                extracted_context="Test context",
                match_strength=0.8,
                supporting_evidence=["evidence"],
            )

            confidence = confidence_calculator.calculate_pattern_confidence(pattern_match)
            confidences.append(confidence)

        # 成功率が高いほど信頼度も高くなることを確認
        for i in range(1, len(confidences)):
            assert (
                confidences[i] >= confidences[i - 1]
            ), f"成功率による信頼度が期待通りに増加していません: {confidences}"

    def test_confidence_with_different_evidence_counts(self, confidence_calculator, sample_pattern):
        """異なる証拠数での信頼度テスト"""
        evidence_counts = [0, 1, 3, 5]
        confidences = []

        for count in evidence_counts:
            evidence = [f"evidence_{i}" for i in range(count)]

            pattern_match = PatternMatch(
                pattern=sample_pattern,
                confidence=0.0,
                match_positions=[100],
                extracted_context="Test context with sufficient length for analysis",
                match_strength=0.8,
                supporting_evidence=evidence,
            )

            confidence = confidence_calculator.calculate_pattern_confidence(pattern_match)
            confidences.append(confidence)

        # 証拠が多いほど信頼度も高くなることを確認
        assert confidences[3] >= confidences[0], "証拠数による信頼度向上が確認できません"

    def test_confidence_with_recency(self, confidence_calculator):
        """パターンの最新性による信頼度テスト"""
        # 新しいパターン
        recent_pattern = Pattern(
            id="recent_pattern",
            name="新しいパターン",
            category="test",
            regex_patterns=[r"error"],
            keywords=["error"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),  # 最新
        )

        # 古いパターン
        old_pattern = Pattern(
            id="old_pattern",
            name="古いパターン",
            category="test",
            regex_patterns=[r"error"],
            keywords=["error"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now() - timedelta(days=400),
            updated_at=datetime.now() - timedelta(days=400),  # 1年以上前
        )

        # 同じ条件でパターンマッチを作成
        recent_match = PatternMatch(
            pattern=recent_pattern,
            confidence=0.0,
            match_positions=[100],
            extracted_context="Test context",
            match_strength=0.8,
            supporting_evidence=["evidence"],
        )

        old_match = PatternMatch(
            pattern=old_pattern,
            confidence=0.0,
            match_positions=[100],
            extracted_context="Test context",
            match_strength=0.8,
            supporting_evidence=["evidence"],
        )

        recent_confidence = confidence_calculator.calculate_pattern_confidence(recent_match)
        old_confidence = confidence_calculator.calculate_pattern_confidence(old_match)

        # 新しいパターンの方が高い信頼度を持つことを確認
        assert recent_confidence >= old_confidence, "最新性による信頼度向上が確認できません"

    def test_fix_confidence_with_different_priorities(self, confidence_calculator, sample_pattern_match):
        """異なる優先度での修正信頼度テスト"""
        priorities = [Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.URGENT]
        confidences = []

        for priority in priorities:
            fix_suggestion = FixSuggestion(
                title="テスト修正",
                description="テスト用の修正提案",
                priority=priority,
                estimated_effort="5分",
                confidence=0.8,
                code_changes=[],
            )

            confidence = confidence_calculator.calculate_fix_confidence(fix_suggestion, sample_pattern_match)
            confidences.append(confidence)

        # 優先度が高いほど信頼度も高くなることを確認
        assert confidences[3] >= confidences[0], "優先度による信頼度調整が確認できません"

    def test_fix_confidence_with_different_complexities(self, confidence_calculator, sample_pattern_match):
        """異なる複雑さでの修正信頼度テスト"""
        # シンプルな修正
        simple_fix = FixSuggestion(
            title="シンプル修正",
            description="簡単な修正",
            priority=Priority.MEDIUM,
            estimated_effort="2分",
            confidence=0.8,
            code_changes=[],  # 変更が少ない
        )

        # 複雑な修正
        from src.ci_helper.ai.models import CodeChange

        complex_changes = [
            CodeChange(
                file_path=f"file_{i}.py",
                line_start=1,
                line_end=10,
                old_code="old code",
                new_code="new code",
                description=f"変更{i}",
            )
            for i in range(10)  # 多くの変更
        ]

        complex_fix = FixSuggestion(
            title="複雑修正",
            description="複雑な修正",
            priority=Priority.MEDIUM,
            estimated_effort="2時間",  # 時間単位
            confidence=0.8,
            code_changes=complex_changes,
        )

        simple_confidence = confidence_calculator.calculate_fix_confidence(simple_fix, sample_pattern_match)
        complex_confidence = confidence_calculator.calculate_fix_confidence(complex_fix, sample_pattern_match)

        # シンプルな修正の方が高い信頼度を持つことを確認
        assert simple_confidence >= complex_confidence, "複雑さによる信頼度調整が確認できません"

    def test_get_confidence_explanation(self, confidence_calculator, sample_pattern_match):
        """信頼度説明生成のテスト"""
        confidence = confidence_calculator.calculate_pattern_confidence(sample_pattern_match)
        explanation = confidence_calculator.get_confidence_explanation(confidence, sample_pattern_match)

        # 説明が生成されることを確認
        assert isinstance(explanation, str)
        assert len(explanation) > 0

        # 信頼度レベルが含まれることを確認
        confidence_levels = ["非常に高い", "高い", "中程度", "低い", "非常に低い"]
        assert any(level in explanation for level in confidence_levels)

        # 信頼度パーセンテージが含まれることを確認
        assert "%" in explanation

    def test_edge_cases(self, confidence_calculator):
        """エッジケースのテスト"""
        # 最小値のパターン
        min_pattern = Pattern(
            id="min_pattern",
            name="最小パターン",
            category="test",
            regex_patterns=[],
            keywords=[],
            context_requirements=[],
            confidence_base=0.0,
            success_rate=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        min_match = PatternMatch(
            pattern=min_pattern,
            confidence=0.0,
            match_positions=[],
            extracted_context="",
            match_strength=0.0,
            supporting_evidence=[],
        )

        min_confidence = confidence_calculator.calculate_pattern_confidence(min_match)
        assert 0.0 <= min_confidence <= 1.0

        # 最大値のパターン
        max_pattern = Pattern(
            id="max_pattern",
            name="最大パターン",
            category="test",
            regex_patterns=[r".*"],
            keywords=["test"],
            context_requirements=["context"],
            confidence_base=1.0,
            success_rate=1.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        max_match = PatternMatch(
            pattern=max_pattern,
            confidence=0.0,
            match_positions=[1, 2, 3],
            extracted_context="Very detailed context with lots of information",
            match_strength=1.0,
            supporting_evidence=["evidence1", "evidence2", "evidence3", "evidence4"],
        )

        max_confidence = confidence_calculator.calculate_pattern_confidence(max_match)
        assert 0.0 <= max_confidence <= 1.0

    def test_weight_normalization(self):
        """重み正規化のテスト"""
        # 重みの合計が1.0でない場合
        calculator = ConfidenceCalculator(
            base_weight=0.8,
            success_rate_weight=0.6,
            context_weight=0.4,
            recency_weight=0.2,
        )

        # 重みが正規化されていることを確認
        total_weight = (
            calculator.base_weight
            + calculator.success_rate_weight
            + calculator.context_weight
            + calculator.recency_weight
        )

        assert abs(total_weight - 1.0) < 0.001, f"重みが正規化されていません: {total_weight}"

    def test_empty_competing_patterns(self, confidence_calculator):
        """空の競合パターンリストのテスト"""
        resolved = confidence_calculator.resolve_competing_patterns([])
        assert len(resolved) == 0

    def test_single_competing_pattern(self, confidence_calculator, sample_pattern_match):
        """単一の競合パターンのテスト"""
        resolved = confidence_calculator.resolve_competing_patterns([sample_pattern_match])
        assert len(resolved) == 1
        assert resolved[0] == sample_pattern_match
