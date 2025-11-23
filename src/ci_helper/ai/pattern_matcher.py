"""パターンマッチングエンジン.

正規表現とキーワードベースのパターンマッチング機能を提供します.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import Match, Pattern

logger = logging.getLogger(__name__)

# Constants for match strength calculation
DEFAULT_CONTEXT_WINDOW = 100
BASE_MATCH_STRENGTH = 0.7
MATCH_LENGTH_BONUS_THRESHOLD = 20
MATCH_LENGTH_PENALTY_THRESHOLD = 5
MATCH_LENGTH_BONUS = 0.1
MATCH_LENGTH_PENALTY = 0.1
GROUP_MATCH_BONUS = 0.1
CONTEXT_SCORE_WEIGHT = 0.5
KEYWORD_SCORE_WEIGHT = 0.3
KEYWORD_BASE_SCORE = 0.5
KEYWORD_BOUNDARY_BONUS = 0.2
KEYWORD_LENGTH_BONUS = 0.1
KEYWORD_LENGTH_THRESHOLD = 5


class PatternMatcher:
    """パターンマッチング処理クラス.

    正規表現とキーワードベースのパターンマッチングを実行します.
    """

    def __init__(self, context_window: int = DEFAULT_CONTEXT_WINDOW) -> None:
        """パターンマッチャーを初期化.

        Args:
            context_window: コンテキスト抽出の文字数

        """
        self.context_window = context_window
        self._compiled_patterns: dict[str, list[re.Pattern[str]]] = {}

    def match_regex_patterns(self, text: str, patterns: list[Pattern]) -> list[Match]:
        """正規表現パターンでマッチング.

        Args:
            text: 検索対象のテキスト
            patterns: パターンのリスト

        Returns:
            マッチ結果のリスト

        """
        matches: list[Match] = []

        for pattern in patterns:
            if not pattern.regex_patterns:
                continue

            # パターンのコンパイルとキャッシュ
            compiled_patterns = self._get_compiled_patterns(pattern)

            for regex_pattern in compiled_patterns:
                try:
                    for match in regex_pattern.finditer(text):
                        start_pos = match.start()
                        end_pos = match.end()
                        matched_text = match.group()

                        # コンテキストを抽出
                        context_before, context_after = self.extract_error_context(text, start_pos)

                        # マッチ強度を計算
                        match_strength = self._calculate_regex_match_strength(match, pattern, text)

                        matches.append(
                            Match(
                                pattern_id=pattern.id,
                                match_type="regex",
                                start_position=start_pos,
                                end_position=end_pos,
                                matched_text=matched_text,
                                confidence=match_strength,
                                context_before=context_before,
                                context_after=context_after,
                            ),
                        )

                except re.error as e:
                    logger.warning("正規表現エラー (パターン: %s): %s", pattern.id, e)
                    continue

        return matches

    def match_keyword_patterns(self, text: str, patterns: list[Pattern]) -> list[Match]:
        """キーワードパターンでマッチング.

        Args:
            text: 検索対象のテキスト
            patterns: パターンのリスト

        Returns:
            マッチ結果のリスト

        """
        matches: list[Match] = []
        text_lower = text.lower()

        for pattern in patterns:
            if not pattern.keywords:
                continue

            # キーワードマッチングを実行
            keyword_matches = self._find_keyword_matches(text_lower, pattern.keywords)

            if keyword_matches:
                # 最も強いマッチを選択
                best_match = max(keyword_matches, key=lambda m: m["score"])

                # コンテキストを抽出
                context_before, context_after = self.extract_error_context(text, best_match["position"])

                matches.append(
                    Match(
                        pattern_id=pattern.id,
                        match_type="keyword",
                        start_position=best_match["position"],
                        end_position=best_match["position"] + len(best_match["keyword"]),
                        matched_text=best_match["keyword"],
                        confidence=best_match["score"],
                        context_before=context_before,
                        context_after=context_after,
                    ),
                )

        return matches

    def extract_error_context(self, text: str, match_position: int) -> tuple[str, str]:
        """エラーコンテキストを抽出.

        Args:
            text: 元のテキスト
            match_position: マッチ位置

        Returns:
            前後のコンテキストのタプル

        """
        # 前のコンテキスト
        start_pos = max(0, match_position - self.context_window)
        context_before = text[start_pos:match_position].strip()

        # 後のコンテキスト
        end_pos = min(len(text), match_position + self.context_window)
        context_after = text[match_position:end_pos].strip()

        return context_before, context_after

    def calculate_match_strength(self, match: Match) -> float:
        """マッチ強度を計算.

        Args:
            match: マッチ結果

        Returns:
            マッチ強度(0.0-1.0)

        """
        if match.match_type in {"regex", "keyword"}:
            return match.confidence  # 既に計算済み

        return 0.0

    def _get_compiled_patterns(self, pattern: Pattern) -> list[re.Pattern[str]]:
        """正規表現パターンをコンパイル(キャッシュ付き).

        Args:
            pattern: パターン

        Returns:
            コンパイル済み正規表現のリスト

        """
        if pattern.id not in self._compiled_patterns:
            compiled: list[re.Pattern[str]] = []
            for regex_str in pattern.regex_patterns:
                try:
                    # 大文字小文字を区別しない、複数行対応
                    compiled_pattern = re.compile(regex_str, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    compiled.append(compiled_pattern)
                except re.error as e:
                    logger.warning(
                        "正規表現のコンパイルに失敗 (パターン: %s, 正規表現: %s): %s",
                        pattern.id,
                        regex_str,
                        e,
                    )
                    continue
            self._compiled_patterns[pattern.id] = compiled

        return self._compiled_patterns[pattern.id]

    def _calculate_regex_match_strength(self, match: re.Match[str], pattern: Pattern, full_text: str) -> float:
        """正規表現マッチの強度を計算.

        Args:
            match: 正規表現マッチオブジェクト
            pattern: パターン
            full_text: 全体のテキスト

        Returns:
            マッチ強度(0.0-1.0)

        """
        base_strength = BASE_MATCH_STRENGTH  # 基本強度

        # マッチした文字列の長さによる調整
        match_length = len(match.group())
        if match_length > MATCH_LENGTH_BONUS_THRESHOLD:
            base_strength += MATCH_LENGTH_BONUS
        elif match_length < MATCH_LENGTH_PENALTY_THRESHOLD:
            base_strength -= MATCH_LENGTH_PENALTY

        # グループマッチがある場合は強度を上げる
        if match.groups():
            base_strength += GROUP_MATCH_BONUS

        # コンテキスト要件のチェック
        if pattern.context_requirements:
            context_score = self._check_context_requirements(match, pattern, full_text)
            base_strength = base_strength * (CONTEXT_SCORE_WEIGHT + (1 - CONTEXT_SCORE_WEIGHT) * context_score)

        # キーワードとの組み合わせチェック
        if pattern.keywords:
            keyword_score = self._check_keyword_presence(match, pattern, full_text)
            base_strength = base_strength * (1 - KEYWORD_SCORE_WEIGHT) + KEYWORD_SCORE_WEIGHT * keyword_score

        return min(1.0, max(0.0, base_strength))

    def _find_keyword_matches(self, text_lower: str, keywords: list[str]) -> list[dict[str, Any]]:
        """キーワードマッチを検索.

        Args:
            text_lower: 小文字に変換されたテキスト
            keywords: キーワードのリスト

        Returns:
            マッチ情報のリスト

        """
        matches: list[dict[str, Any]] = []

        for keyword in keywords:
            keyword_lower = keyword.lower()
            position = text_lower.find(keyword_lower)

            if position != -1:
                # 単語境界のチェック
                is_word_boundary = self._check_word_boundary(text_lower, position, len(keyword_lower))

                # スコア計算
                score = KEYWORD_BASE_SCORE  # 基本スコア
                if is_word_boundary:
                    score += KEYWORD_BOUNDARY_BONUS
                if len(keyword) > KEYWORD_LENGTH_THRESHOLD:
                    score += KEYWORD_LENGTH_BONUS

                matches.append(
                    {
                        "keyword": keyword,
                        "position": position,
                        "score": min(1.0, score),
                        "is_word_boundary": is_word_boundary,
                    },
                )

        return matches

    def _check_word_boundary(self, text: str, position: int, length: int) -> bool:
        """単語境界をチェック.

        Args:
            text: テキスト
            position: 開始位置
            length: 長さ

        Returns:
            単語境界の場合True

        """
        # 前の文字をチェック
        if position > 0:
            prev_char = text[position - 1]
            if prev_char.isalnum() or prev_char == "_":
                return False

        # 後の文字をチェック
        end_pos = position + length
        if end_pos < len(text):
            next_char = text[end_pos]
            if next_char.isalnum() or next_char == "_":
                return False

        return True

    def _check_context_requirements(self, match: re.Match[str], pattern: Pattern, full_text: str) -> float:
        """コンテキスト要件をチェック.

        Args:
            match: 正規表現マッチオブジェクト
            pattern: パターン
            full_text: 全体のテキスト

        Returns:
            コンテキストスコア(0.0-1.0)

        """
        if not pattern.context_requirements:
            return 1.0

        # マッチ周辺のコンテキストを取得
        start_pos = max(0, match.start() - self.context_window * 2)
        end_pos = min(len(full_text), match.end() + self.context_window * 2)
        context = full_text[start_pos:end_pos].lower()

        # 要件の充足度を計算
        satisfied_requirements = 0
        for requirement in pattern.context_requirements:
            if requirement.lower() in context:
                satisfied_requirements += 1

        return satisfied_requirements / len(pattern.context_requirements)

    def _check_keyword_presence(self, match: re.Match[str], pattern: Pattern, full_text: str) -> float:
        """キーワードの存在をチェック.

        Args:
            match: 正規表現マッチオブジェクト
            pattern: パターン
            full_text: 全体のテキスト

        Returns:
            キーワードスコア(0.0-1.0)

        """
        if not pattern.keywords:
            return 1.0

        # マッチ周辺のコンテキストを取得
        start_pos = max(0, match.start() - self.context_window)
        end_pos = min(len(full_text), match.end() + self.context_window)
        context = full_text[start_pos:end_pos].lower()

        # キーワードの存在を確認
        found_keywords = 0
        for keyword in pattern.keywords:
            if keyword.lower() in context:
                found_keywords += 1

        return found_keywords / len(pattern.keywords)

    def get_match_summary(self, matches: list[Match]) -> dict[str, Any]:
        """マッチ結果のサマリーを取得.

        Args:
            matches: マッチ結果のリスト

        Returns:
            サマリー情報

        """
        if not matches:
            return {
                "total_matches": 0,
                "regex_matches": 0,
                "keyword_matches": 0,
                "average_confidence": 0.0,
                "patterns_matched": [],
            }

        regex_matches = [m for m in matches if m.match_type == "regex"]
        keyword_matches = [m for m in matches if m.match_type == "keyword"]

        # 平均信頼度を計算
        total_confidence = sum(m.confidence for m in matches)
        average_confidence = total_confidence / len(matches)

        # マッチしたパターンを集計
        patterns_matched = list({m.pattern_id for m in matches})

        return {
            "total_matches": len(matches),
            "regex_matches": len(regex_matches),
            "keyword_matches": len(keyword_matches),
            "average_confidence": average_confidence,
            "patterns_matched": patterns_matched,
            "highest_confidence": max(m.confidence for m in matches),
            "lowest_confidence": min(m.confidence for m in matches),
        }

    def clear_cache(self) -> None:
        """コンパイル済みパターンのキャッシュをクリア."""
        self._compiled_patterns.clear()
        logger.info("パターンマッチャーのキャッシュをクリアしました")
