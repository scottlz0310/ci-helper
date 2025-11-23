"""
信頼度計算システム

パターンマッチと修正提案の信頼度を計算するアルゴリズムを提供します。
"""

from __future__ import annotations

import logging
from typing import Any

from .models import FixSuggestion, Pattern, PatternMatch

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """信頼度計算クラス

    パターンマッチと修正提案の信頼度を計算します。
    """

    def __init__(
        self,
        base_weight: float = 0.4,
        success_rate_weight: float = 0.3,
        context_weight: float = 0.2,
        recency_weight: float = 0.1,
    ):
        """信頼度計算機を初期化

        Args:
            base_weight: 基本信頼度の重み
            success_rate_weight: 成功率の重み
            context_weight: コンテキストの重み
            recency_weight: 最新性の重み
        """
        self.base_weight = base_weight
        self.success_rate_weight = success_rate_weight
        self.context_weight = context_weight
        self.recency_weight = recency_weight

        # 重みの合計が1.0になるように正規化
        total_weight = base_weight + success_rate_weight + context_weight + recency_weight
        if total_weight != 1.0:
            self.base_weight /= total_weight
            self.success_rate_weight /= total_weight
            self.context_weight /= total_weight
            self.recency_weight /= total_weight

    def calculate_pattern_confidence(self, pattern_match: PatternMatch) -> float:
        """パターンマッチの信頼度を計算

        Args:
            pattern_match: パターンマッチ結果

        Returns:
            信頼度スコア（0.0-1.0）
        """
        pattern = pattern_match.pattern

        # 基本信頼度
        base_confidence = pattern.confidence_base * self.base_weight

        # 成功率による調整
        success_rate_score = pattern.success_rate * self.success_rate_weight

        # コンテキストの明確さによる調整
        context_score = self._calculate_context_clarity(pattern_match) * self.context_weight

        # 最新性による調整（パターンの更新日時を考慮）
        recency_score = self._calculate_recency_score(pattern) * self.recency_weight

        # 総合信頼度を計算
        total_confidence = base_confidence + success_rate_score + context_score + recency_score

        # マッチ強度による最終調整
        final_confidence = total_confidence * pattern_match.match_strength

        return min(1.0, max(0.0, final_confidence))

    def calculate_fix_confidence(self, fix_suggestion: FixSuggestion, pattern_match: PatternMatch) -> float:
        """修正提案の信頼度を計算

        Args:
            fix_suggestion: 修正提案
            pattern_match: 関連するパターンマッチ

        Returns:
            信頼度スコア（0.0-1.0）
        """
        # パターンマッチの信頼度をベースとする
        pattern_confidence = self.calculate_pattern_confidence(pattern_match)

        # 修正提案固有の信頼度
        fix_base_confidence = fix_suggestion.confidence

        # 修正の複雑さによる調整
        complexity_factor = self._calculate_fix_complexity_factor(fix_suggestion)

        # 修正の優先度による調整
        priority_factor = self._calculate_priority_factor(fix_suggestion)

        # 総合信頼度を計算
        combined_confidence = pattern_confidence * 0.6 + fix_base_confidence * 0.4
        adjusted_confidence = combined_confidence * complexity_factor * priority_factor

        return min(1.0, max(0.0, adjusted_confidence))

    def adjust_confidence_by_context(self, base_confidence: float, context: dict[str, Any]) -> float:
        """コンテキストによる信頼度調整

        Args:
            base_confidence: 基本信頼度
            context: コンテキスト情報

        Returns:
            調整後の信頼度
        """
        adjusted_confidence = base_confidence

        # ログの長さによる調整
        log_length = context.get("log_length", 0)
        if log_length > 0:
            length_factor = self._calculate_log_length_factor(log_length)
            adjusted_confidence *= length_factor

        # エラーの種類による調整
        error_type = context.get("error_type", "")
        if error_type:
            type_factor = self._calculate_error_type_factor(error_type)
            adjusted_confidence *= type_factor

        # 複数パターンマッチによる調整
        multiple_matches = context.get("multiple_matches", False)
        if multiple_matches:
            adjusted_confidence *= 0.9  # 複数マッチは若干信頼度を下げる

        # プロジェクトタイプによる調整
        project_type = context.get("project_type", "")
        if project_type:
            project_factor = self._calculate_project_type_factor(project_type)
            adjusted_confidence *= project_factor

        return min(1.0, max(0.0, adjusted_confidence))

    def resolve_competing_patterns(self, pattern_matches: list[PatternMatch]) -> list[PatternMatch]:
        """複数パターンの競合を解決

        Args:
            pattern_matches: 競合するパターンマッチのリスト

        Returns:
            優先度順にソートされたパターンマッチのリスト
        """
        if len(pattern_matches) <= 1:
            return pattern_matches

        # 各パターンマッチの総合スコアを計算
        scored_matches: list[tuple[PatternMatch, float]] = []
        for match in pattern_matches:
            confidence = self.calculate_pattern_confidence(match)

            # 追加の競合解決要素
            specificity_score = self._calculate_pattern_specificity(match.pattern)
            evidence_score = self._calculate_evidence_strength(match)

            total_score = confidence * 0.6 + specificity_score * 0.25 + evidence_score * 0.15

            scored_matches.append((match, total_score))

        # スコア順にソート
        scored_matches.sort(key=lambda x: x[1], reverse=True)

        # 上位パターンを選択（信頼度が閾値以上のもの）
        threshold = 0.5
        selected_matches: list[PatternMatch] = []

        for match, score in scored_matches:
            if score >= threshold:
                selected_matches.append(match)
            elif not selected_matches:  # 最低1つは選択
                selected_matches.append(match)

        logger.info("パターン競合解決: %d個中%d個を選択", len(pattern_matches), len(selected_matches))
        return selected_matches

    def _calculate_context_clarity(self, pattern_match: PatternMatch) -> float:
        """コンテキストの明確さを計算

        Args:
            pattern_match: パターンマッチ結果

        Returns:
            明確さスコア（0.0-1.0）
        """
        clarity_score = 0.5  # 基本スコア

        # 抽出されたコンテキストの長さ
        context_length = len(pattern_match.extracted_context)
        if context_length > 100:
            clarity_score += 0.2
        elif context_length < 20:
            clarity_score -= 0.2

        # 裏付け証拠の数
        evidence_count = len(pattern_match.supporting_evidence)
        if evidence_count > 2:
            clarity_score += 0.2
        elif evidence_count == 0:
            clarity_score -= 0.3

        # マッチ位置の数（複数箇所でマッチしている場合）
        match_positions = len(pattern_match.match_positions)
        if match_positions > 1:
            clarity_score += 0.1

        return min(1.0, max(0.0, clarity_score))

    def _calculate_recency_score(self, pattern: Pattern) -> float:
        """パターンの最新性スコアを計算

        Args:
            pattern: パターン

        Returns:
            最新性スコア（0.0-1.0）
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        updated_at = pattern.updated_at

        # 更新からの経過時間
        time_diff = now - updated_at

        # 30日以内なら満点、それ以降は指数的に減少
        if time_diff <= timedelta(days=30):
            return 1.0
        elif time_diff <= timedelta(days=90):
            return 0.8
        elif time_diff <= timedelta(days=180):
            return 0.6
        elif time_diff <= timedelta(days=365):
            return 0.4
        else:
            return 0.2

    def _calculate_fix_complexity_factor(self, fix_suggestion: FixSuggestion) -> float:
        """修正の複雑さ要因を計算

        Args:
            fix_suggestion: 修正提案

        Returns:
            複雑さ要因（0.5-1.0）
        """
        complexity_factor = 1.0

        # コード変更の数
        code_changes_count = len(fix_suggestion.code_changes)
        if code_changes_count > 5:
            complexity_factor *= 0.8
        elif code_changes_count > 2:
            complexity_factor *= 0.9

        # 推定工数による調整
        effort = fix_suggestion.estimated_effort.lower()
        if "時間" in effort or "hour" in effort:
            complexity_factor *= 0.7
        elif "分" in effort or "minute" in effort:
            complexity_factor *= 0.9

        return max(0.5, complexity_factor)

    def _calculate_priority_factor(self, fix_suggestion: FixSuggestion) -> float:
        """優先度要因を計算

        Args:
            fix_suggestion: 修正提案

        Returns:
            優先度要因（0.8-1.2）
        """
        priority_map = {
            "urgent": 1.2,
            "high": 1.1,
            "medium": 1.0,
            "low": 0.8,
        }

        return priority_map.get(fix_suggestion.priority.value, 1.0)

    def _calculate_log_length_factor(self, log_length: int) -> float:
        """ログ長による要因を計算

        Args:
            log_length: ログの長さ

        Returns:
            長さ要因（0.8-1.1）
        """
        if log_length < 100:
            return 0.8  # 短すぎるログは信頼度を下げる
        elif log_length < 1000:
            return 1.0  # 適切な長さ
        elif log_length < 10000:
            return 1.1  # 詳細なログは信頼度を上げる
        else:
            return 0.9  # 長すぎるログは若干信頼度を下げる

    def _calculate_error_type_factor(self, error_type: str) -> float:
        """エラータイプによる要因を計算

        Args:
            error_type: エラータイプ

        Returns:
            エラータイプ要因（0.8-1.2）
        """
        # よく知られたエラータイプは信頼度が高い
        known_types = {
            "syntax_error": 1.2,
            "import_error": 1.1,
            "permission_error": 1.1,
            "network_error": 1.0,
            "configuration_error": 1.0,
            "build_failure": 0.9,
            "test_failure": 0.9,
            "unknown": 0.8,
        }

        return known_types.get(error_type, 1.0)

    def _calculate_project_type_factor(self, project_type: str) -> float:
        """プロジェクトタイプによる要因を計算

        Args:
            project_type: プロジェクトタイプ

        Returns:
            プロジェクトタイプ要因（0.9-1.1）
        """
        # 一般的なプロジェクトタイプは信頼度が高い
        type_factors = {
            "python": 1.1,
            "javascript": 1.0,
            "typescript": 1.0,
            "java": 1.0,
            "go": 0.95,
            "rust": 0.9,
            "unknown": 0.9,
        }

        return type_factors.get(project_type.lower(), 1.0)

    def _calculate_pattern_specificity(self, pattern: Pattern) -> float:
        """パターンの特異性を計算

        Args:
            pattern: パターン

        Returns:
            特異性スコア（0.0-1.0）
        """
        specificity_score = 0.5

        # 正規表現パターンの複雑さ
        regex_complexity = sum(len(regex) for regex in pattern.regex_patterns)
        if regex_complexity > 50:
            specificity_score += 0.2
        elif regex_complexity < 10:
            specificity_score -= 0.1

        # キーワードの数
        keyword_count = len(pattern.keywords)
        if keyword_count > 5:
            specificity_score += 0.2
        elif keyword_count < 2:
            specificity_score -= 0.1

        # コンテキスト要件の有無
        if pattern.context_requirements:
            specificity_score += 0.1

        return min(1.0, max(0.0, specificity_score))

    def _calculate_evidence_strength(self, pattern_match: PatternMatch) -> float:
        """証拠の強さを計算

        Args:
            pattern_match: パターンマッチ結果

        Returns:
            証拠の強さスコア（0.0-1.0）
        """
        evidence_score = 0.5

        # 裏付け証拠の数と質
        evidence_count = len(pattern_match.supporting_evidence)
        if evidence_count > 3:
            evidence_score += 0.3
        elif evidence_count > 1:
            evidence_score += 0.2
        elif evidence_count == 0:
            evidence_score -= 0.2

        # マッチ位置の数
        position_count = len(pattern_match.match_positions)
        if position_count > 2:
            evidence_score += 0.2
        elif position_count > 1:
            evidence_score += 0.1

        return min(1.0, max(0.0, evidence_score))

    def get_confidence_explanation(self, confidence: float, pattern_match: PatternMatch) -> str:
        """信頼度の説明を生成

        Args:
            confidence: 信頼度スコア
            pattern_match: パターンマッチ結果

        Returns:
            信頼度の説明文
        """
        if confidence >= 0.9:
            level = "非常に高い"
        elif confidence >= 0.8:
            level = "高い"
        elif confidence >= 0.7:
            level = "中程度"
        elif confidence >= 0.5:
            level = "低い"
        else:
            level = "非常に低い"

        explanation = f"信頼度: {confidence:.1%} ({level})\n"

        # 要因の説明
        factors: list[str] = []

        if pattern_match.pattern.success_rate > 0.8:
            factors.append("過去の成功率が高い")

        if len(pattern_match.supporting_evidence) > 2:
            factors.append("十分な裏付け証拠がある")

        if pattern_match.match_strength > 0.8:
            factors.append("パターンマッチが強い")

        if factors:
            explanation += "理由: " + "、".join(factors)

        return explanation
