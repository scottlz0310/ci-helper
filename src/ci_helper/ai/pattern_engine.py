"""
パターン認識エンジン

CI失敗ログからエラーパターンを特定し、分類するメインエンジンです。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .confidence_calculator import ConfidenceCalculator
from .models import Pattern, PatternMatch
from .pattern_database import PatternDatabase
from .pattern_matcher import PatternMatcher

logger = logging.getLogger(__name__)


class PatternRecognitionEngine:
    """パターン認識エンジンのメインクラス

    CI失敗ログからエラーパターンを特定し、分類します。
    """

    def __init__(
        self,
        data_directory: Path | str = "test_data",
        confidence_threshold: float = 0.5,
        max_patterns_per_analysis: int = 5,
    ):
        """パターン認識エンジンを初期化

        Args:
            data_directory: パターンデータディレクトリ
            confidence_threshold: 信頼度閾値
            max_patterns_per_analysis: 分析あたりの最大パターン数
        """
        self.data_directory = Path(data_directory)
        self.confidence_threshold = confidence_threshold
        self.max_patterns_per_analysis = max_patterns_per_analysis

        # コンポーネントを初期化
        self.pattern_database = PatternDatabase(data_directory)
        self.pattern_matcher = PatternMatcher()
        self.confidence_calculator = ConfidenceCalculator()

        self._initialized = False

    async def initialize(self) -> None:
        """パターン認識エンジンを初期化"""
        if self._initialized:
            return

        logger.info("パターン認識エンジンを初期化中...")

        # パターンデータベースを読み込み
        await self.pattern_database.load_patterns()

        self._initialized = True
        logger.info("パターン認識エンジンの初期化完了 (パターン数: %d)", len(self.pattern_database.patterns))

    async def analyze_log(self, log_content: str, options: dict[str, Any] | None = None) -> list[PatternMatch]:
        """ログを分析してパターンマッチを実行

        Args:
            log_content: 分析対象のログ内容
            options: 分析オプション

        Returns:
            パターンマッチ結果のリスト
        """
        if not self._initialized:
            await self.initialize()

        if not log_content.strip():
            logger.warning("空のログが提供されました")
            return []

        logger.info("ログ分析を開始 (長さ: %d文字)", len(log_content))

        try:
            # パターンを特定
            patterns = await self.identify_patterns(log_content, options)

            if not patterns:
                logger.info("マッチするパターンが見つかりませんでした")
                return []

            # パターンマッチ結果を作成
            pattern_matches = []
            for pattern in patterns:
                match_result = await self._create_pattern_match(pattern, log_content)
                if match_result:
                    pattern_matches.append(match_result)

            # 信頼度でフィルタリング
            filtered_matches = [match for match in pattern_matches if match.confidence >= self.confidence_threshold]

            # 競合解決
            resolved_matches = self.confidence_calculator.resolve_competing_patterns(filtered_matches)

            # 最大数に制限
            final_matches = resolved_matches[: self.max_patterns_per_analysis]

            logger.info("パターン分析完了: %d個のパターンがマッチ", len(final_matches))
            return final_matches

        except Exception as e:
            logger.error("ログ分析中にエラーが発生: %s", e)
            return []

    async def identify_patterns(self, log_content: str, options: dict[str, Any] | None = None) -> list[Pattern]:
        """ログ内容からエラーパターンを特定

        Args:
            log_content: ログ内容
            options: 分析オプション

        Returns:
            特定されたパターンのリスト
        """
        if not self._initialized:
            await self.initialize()

        options = options or {}

        # 利用可能なパターンを取得
        all_patterns = self.pattern_database.get_all_patterns()

        # カテゴリフィルタリング
        enabled_categories = options.get("enabled_categories")
        if enabled_categories:
            all_patterns = [p for p in all_patterns if p.category in enabled_categories]

        # 正規表現マッチング
        regex_matches = self.pattern_matcher.match_regex_patterns(log_content, all_patterns)

        # キーワードマッチング
        keyword_matches = self.pattern_matcher.match_keyword_patterns(log_content, all_patterns)

        # マッチしたパターンを収集
        matched_pattern_ids = set()
        for match in regex_matches + keyword_matches:
            matched_pattern_ids.add(match.pattern_id)

        # パターンオブジェクトを取得
        matched_patterns = []
        for pattern_id in matched_pattern_ids:
            pattern = self.pattern_database.get_pattern(pattern_id)
            if pattern:
                matched_patterns.append(pattern)

        logger.info("パターン特定完了: %d個のパターンが候補", len(matched_patterns))
        return matched_patterns

    def calculate_confidence(self, pattern: Pattern, match_data: dict[str, Any]) -> float:
        """パターンマッチの信頼度を計算

        Args:
            pattern: パターン
            match_data: マッチデータ

        Returns:
            信頼度スコア（0.0-1.0）
        """
        # PatternMatchオブジェクトを作成
        pattern_match = PatternMatch(
            pattern=pattern,
            confidence=0.0,  # 後で計算
            match_positions=match_data.get("match_positions", []),
            extracted_context=match_data.get("extracted_context", ""),
            match_strength=match_data.get("match_strength", 0.5),
            supporting_evidence=match_data.get("supporting_evidence", []),
        )

        # 信頼度を計算
        confidence = self.confidence_calculator.calculate_pattern_confidence(pattern_match)

        # コンテキストによる調整
        context = match_data.get("context", {})
        if context:
            confidence = self.confidence_calculator.adjust_confidence_by_context(confidence, context)

        return confidence

    async def _create_pattern_match(self, pattern: Pattern, log_content: str) -> PatternMatch | None:
        """パターンマッチ結果を作成

        Args:
            pattern: パターン
            log_content: ログ内容

        Returns:
            パターンマッチ結果、作成できない場合はNone
        """
        try:
            # 正規表現マッチング
            regex_matches = self.pattern_matcher.match_regex_patterns(log_content, [pattern])

            # キーワードマッチング
            keyword_matches = self.pattern_matcher.match_keyword_patterns(log_content, [pattern])

            # 最適なマッチを選択
            all_matches = regex_matches + keyword_matches
            pattern_specific_matches = [m for m in all_matches if m.pattern_id == pattern.id]

            if not pattern_specific_matches:
                return None

            # 最も信頼度の高いマッチを選択
            best_match = max(pattern_specific_matches, key=lambda m: m.confidence)

            # マッチ位置を収集
            match_positions = [best_match.start_position]

            # 裏付け証拠を収集
            supporting_evidence = []
            for match in pattern_specific_matches:
                if match.matched_text not in supporting_evidence:
                    supporting_evidence.append(match.matched_text)

            # マッチデータを作成
            match_data = {
                "match_positions": match_positions,
                "extracted_context": best_match.context_before + " " + best_match.context_after,
                "match_strength": best_match.confidence,
                "supporting_evidence": supporting_evidence,
                "context": {
                    "log_length": len(log_content),
                    "error_type": self._infer_error_type(log_content),
                    "multiple_matches": len(pattern_specific_matches) > 1,
                },
            }

            # 信頼度を計算
            confidence = self.calculate_confidence(pattern, match_data)

            # PatternMatchオブジェクトを作成
            pattern_match = PatternMatch(
                pattern=pattern,
                confidence=confidence,
                match_positions=match_positions,
                extracted_context=match_data["extracted_context"],
                match_strength=best_match.confidence,
                supporting_evidence=supporting_evidence,
            )

            return pattern_match

        except Exception as e:
            logger.warning("パターンマッチ作成中にエラー (パターン: %s): %s", pattern.id, e)
            return None

    def _infer_error_type(self, log_content: str) -> str:
        """ログ内容からエラータイプを推測

        Args:
            log_content: ログ内容

        Returns:
            推測されたエラータイプ
        """
        log_lower = log_content.lower()

        # エラータイプのパターンマッチング
        error_patterns = {
            "syntax_error": ["syntax", "syntaxerror", "invalid syntax"],
            "import_error": ["import", "modulenotfounderror", "importerror"],
            "permission_error": ["permission", "denied", "access denied"],
            "network_error": ["timeout", "connection", "network", "ssl"],
            "configuration_error": ["config", "configuration", "filenotfound"],
            "build_failure": ["build", "compile", "compilation"],
            "test_failure": ["test", "assertion", "failed"],
        }

        for error_type, keywords in error_patterns.items():
            if any(keyword in log_lower for keyword in keywords):
                return error_type

        return "unknown"

    def get_pattern_statistics(self) -> dict[str, Any]:
        """パターン統計情報を取得

        Returns:
            統計情報の辞書
        """
        if not self._initialized:
            return {"error": "エンジンが初期化されていません"}

        db_stats = self.pattern_database.get_statistics()

        return {
            "engine_initialized": self._initialized,
            "confidence_threshold": self.confidence_threshold,
            "max_patterns_per_analysis": self.max_patterns_per_analysis,
            "database_stats": db_stats,
        }

    def update_pattern_success_rate(self, pattern_id: str, success: bool) -> bool:
        """パターンの成功率を更新

        Args:
            pattern_id: パターンID
            success: 成功フラグ

        Returns:
            更新成功の場合True
        """
        pattern = self.pattern_database.get_pattern(pattern_id)
        if not pattern:
            logger.warning("パターンが見つかりません: %s", pattern_id)
            return False

        # 成功率を更新（簡単な移動平均）
        current_rate = pattern.success_rate
        if success:
            new_rate = current_rate * 0.9 + 0.1  # 成功時は上昇
        else:
            new_rate = current_rate * 0.9  # 失敗時は下降

        pattern.success_rate = max(0.1, min(1.0, new_rate))  # 0.1-1.0の範囲に制限

        # データベースを更新
        return self.pattern_database.update_pattern(pattern)

    async def add_custom_pattern(self, pattern: Pattern) -> bool:
        """カスタムパターンを追加

        Args:
            pattern: 追加するパターン

        Returns:
            追加成功の場合True
        """
        if not self._initialized:
            await self.initialize()

        # ユーザー定義フラグを設定
        pattern.user_defined = True

        # パターンを追加
        success = self.pattern_database.add_pattern(pattern)

        if success:
            # パターンデータベースを保存
            await self.pattern_database.save_patterns()
            logger.info("カスタムパターンを追加しました: %s", pattern.id)

        return success

    def search_patterns(self, query: str) -> list[Pattern]:
        """パターンを検索

        Args:
            query: 検索クエリ

        Returns:
            マッチしたパターンのリスト
        """
        if not self._initialized:
            return []

        return self.pattern_database.search_patterns(query)

    def get_pattern_by_id(self, pattern_id: str) -> Pattern | None:
        """IDでパターンを取得

        Args:
            pattern_id: パターンID

        Returns:
            パターン、見つからない場合はNone
        """
        if not self._initialized:
            return None

        return self.pattern_database.get_pattern(pattern_id)

    def get_patterns_by_category(self, category: str) -> list[Pattern]:
        """カテゴリでパターンを取得

        Args:
            category: カテゴリ名

        Returns:
            パターンのリスト
        """
        if not self._initialized:
            return []

        return self.pattern_database.get_patterns_by_category(category)

    async def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        logger.info("パターン認識エンジンをクリーンアップ中...")

        # パターンマッチャーのキャッシュをクリア
        self.pattern_matcher.clear_cache()

        # パターンデータベースを保存
        if self._initialized:
            await self.pattern_database.save_patterns()

        logger.info("パターン認識エンジンのクリーンアップ完了")

    def __str__(self) -> str:
        """文字列表現"""
        pattern_count = len(self.pattern_database.patterns) if self._initialized else 0
        return f"PatternRecognitionEngine(patterns={pattern_count}, threshold={self.confidence_threshold})"

    def __repr__(self) -> str:
        """詳細な文字列表現"""
        return (
            f"PatternRecognitionEngine("
            f"initialized={self._initialized}, "
            f"patterns={len(self.pattern_database.patterns) if self._initialized else 0}, "
            f"threshold={self.confidence_threshold}, "
            f"max_patterns={self.max_patterns_per_analysis}"
            f")"
        )
