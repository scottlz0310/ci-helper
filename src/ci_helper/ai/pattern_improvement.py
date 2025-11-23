"""
パターン改善システム

学習データに基づくパターンの自動改善と新しいパターンの提案を行います。
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from collections import Counter as CounterType
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Pattern, UserFeedback
from .pattern_database import PatternDatabase

logger = logging.getLogger(__name__)


class PatternImprovement:
    """パターン改善提案"""

    def __init__(
        self,
        pattern_id: str,
        improvement_type: str,
        description: str,
        suggested_changes: dict[str, Any],
        confidence: float,
        supporting_data: dict[str, Any],
    ):
        """パターン改善提案を初期化

        Args:
            pattern_id: 対象パターンID
            improvement_type: 改善タイプ
            description: 改善の説明
            suggested_changes: 提案される変更内容
            confidence: 改善提案の信頼度
            supporting_data: 裏付けデータ
        """
        self.pattern_id = pattern_id
        self.improvement_type = improvement_type
        self.description = description
        self.suggested_changes = suggested_changes
        self.confidence = confidence
        self.supporting_data = supporting_data
        self.created_at = datetime.now()


class PatternImprovementSystem:
    """パターン改善システムクラス

    学習データに基づいてパターンの自動改善と新しいパターンの提案を行います。
    """

    def __init__(
        self,
        pattern_database: PatternDatabase,
        improvement_data_dir: Path | str = "data/learning",
        min_feedback_for_improvement: int = 5,
        improvement_threshold: float = 0.3,
    ):
        """パターン改善システムを初期化

        Args:
            pattern_database: パターンデータベース
            improvement_data_dir: 改善データディレクトリ
            min_feedback_for_improvement: 改善提案に必要な最小フィードバック数
            improvement_threshold: 改善が必要と判断する閾値
        """
        self.pattern_database = pattern_database
        self.improvement_data_dir = Path(improvement_data_dir)
        self.min_feedback_for_improvement = min_feedback_for_improvement
        self.improvement_threshold = improvement_threshold

        # 改善データファイル
        self.improvement_history_file = self.improvement_data_dir / "pattern_improvements.json"
        self.pattern_analytics_file = self.improvement_data_dir / "pattern_analytics.json"

        # 改善データ
        self.improvement_history: list[dict[str, Any]] = []
        self.pattern_analytics: dict[str, dict[str, Any]] = {}

        self._initialized = False

    async def initialize(self) -> None:
        """パターン改善システムを初期化"""
        if self._initialized:
            return

        logger.info("パターン改善システムを初期化中...")

        # 改善データディレクトリを作成
        self.improvement_data_dir.mkdir(parents=True, exist_ok=True)

        # 既存の改善データを読み込み
        await self._load_improvement_data()

        self._initialized = True
        logger.info("パターン改善システムの初期化完了")

    async def _load_improvement_data(self) -> None:
        """既存の改善データを読み込み"""
        try:
            # 改善履歴を読み込み
            if self.improvement_history_file.exists():
                with open(self.improvement_history_file, encoding="utf-8") as f:
                    self.improvement_history = json.load(f)
                logger.info("改善履歴を %d 件読み込みました", len(self.improvement_history))

            # パターン分析データを読み込み
            if self.pattern_analytics_file.exists():
                with open(self.pattern_analytics_file, encoding="utf-8") as f:
                    self.pattern_analytics = json.load(f)
                logger.info("パターン分析データを読み込みました")

        except Exception as e:
            logger.error("改善データの読み込み中にエラー: %s", e)

    async def analyze_pattern_performance(self, feedback_history: list[UserFeedback]) -> dict[str, dict[str, Any]]:
        """パターンのパフォーマンスを分析

        Args:
            feedback_history: フィードバック履歴

        Returns:
            パターン別パフォーマンス分析結果
        """
        if not self._initialized:
            await self.initialize()

        logger.info("パターンパフォーマンス分析を開始")

        pattern_performance: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_feedback": 0,
                "successful_feedback": 0,
                "failed_feedback": 0,
                "average_rating": 0.0,
                "success_rate": 0.0,
                "rating_trend": [],
                "recent_performance": {},
                "issues": [],
            }
        )

        # フィードバックを分析
        for feedback in feedback_history:
            pattern_id = feedback.pattern_id
            perf = pattern_performance[pattern_id]

            perf["total_feedback"] += 1
            if feedback.success:
                perf["successful_feedback"] += 1
            else:
                perf["failed_feedback"] += 1

            # 評価トレンドを記録
            perf["rating_trend"].append(
                {
                    "rating": feedback.rating,
                    "timestamp": feedback.timestamp.isoformat(),
                    "success": feedback.success,
                }
            )

        # 統計を計算
        for pattern_id, perf in pattern_performance.items():
            if perf["total_feedback"] > 0:
                perf["success_rate"] = perf["successful_feedback"] / perf["total_feedback"]

                # 平均評価を計算
                total_rating = sum(item["rating"] for item in perf["rating_trend"])
                perf["average_rating"] = total_rating / perf["total_feedback"]

                # 最近のパフォーマンス（過去30日）
                recent_cutoff = datetime.now() - timedelta(days=30)
                recent_feedback = [
                    item for item in perf["rating_trend"] if datetime.fromisoformat(item["timestamp"]) >= recent_cutoff
                ]

                if recent_feedback:
                    recent_success = sum(1 for item in recent_feedback if item["success"])
                    perf["recent_performance"] = {
                        "total": len(recent_feedback),
                        "success_rate": recent_success / len(recent_feedback),
                        "average_rating": sum(item["rating"] for item in recent_feedback) / len(recent_feedback),
                    }

                # 問題を特定
                perf["issues"] = self._identify_pattern_issues(pattern_id, perf)

        # 分析結果を保存
        self.pattern_analytics = dict(pattern_performance)
        await self._save_pattern_analytics()

        logger.info("パターンパフォーマンス分析完了: %d パターンを分析", len(pattern_performance))
        return dict(pattern_performance)

    def _identify_pattern_issues(self, pattern_id: str, performance: dict[str, Any]) -> list[str]:
        """パターンの問題を特定

        Args:
            pattern_id: パターンID
            performance: パフォーマンスデータ

        Returns:
            特定された問題のリスト
        """
        issues: list[str] = []

        # 成功率が低い
        if performance["success_rate"] < 0.6:
            issues.append("低い成功率")

        # 平均評価が低い
        if performance["average_rating"] < 2.5:
            issues.append("低い評価")

        # 最近のパフォーマンスが悪化
        recent_perf = performance.get("recent_performance", {})
        if recent_perf and recent_perf["success_rate"] < performance["success_rate"] - 0.2:
            issues.append("パフォーマンス悪化")

        # フィードバック数が少ない
        if performance["total_feedback"] < self.min_feedback_for_improvement:
            issues.append("フィードバック不足")

        # 評価のばらつきが大きい
        ratings: list[float] = [item["rating"] for item in performance["rating_trend"]]
        if len(ratings) > 1:
            rating_variance = sum((r - performance["average_rating"]) ** 2 for r in ratings) / len(ratings)
            if rating_variance > 2.0:
                issues.append("評価のばらつき")

        return issues

    async def suggest_pattern_improvements(self, feedback_history: list[UserFeedback]) -> list[PatternImprovement]:
        """パターン改善を提案

        Args:
            feedback_history: フィードバック履歴

        Returns:
            パターン改善提案のリスト
        """
        if not self._initialized:
            await self.initialize()

        logger.info("パターン改善提案を開始")

        # パターンパフォーマンスを分析
        performance_data = await self.analyze_pattern_performance(feedback_history)

        improvements: list[PatternImprovement] = []

        for pattern_id, perf in performance_data.items():
            # 改善が必要なパターンを特定
            if self._needs_improvement(perf):
                pattern_improvements = await self._generate_improvements_for_pattern(pattern_id, perf, feedback_history)
                improvements.extend(pattern_improvements)

        logger.info("パターン改善提案完了: %d 件の改善提案", len(improvements))
        return improvements

    def _needs_improvement(self, performance: dict[str, Any]) -> bool:
        """パターンが改善を必要とするかどうか判定

        Args:
            performance: パフォーマンスデータ

        Returns:
            改善が必要な場合True
        """
        # 十分なフィードバックがない場合は改善対象外
        if performance["total_feedback"] < self.min_feedback_for_improvement:
            return False

        # 成功率が閾値を下回る
        if performance["success_rate"] < (1.0 - self.improvement_threshold):
            return True

        # 平均評価が低い
        if performance["average_rating"] < 2.5:
            return True

        # 最近のパフォーマンスが大幅に悪化
        recent_perf = performance.get("recent_performance", {})
        if recent_perf and recent_perf["success_rate"] < performance["success_rate"] - self.improvement_threshold:
            return True

        return False

    async def _generate_improvements_for_pattern(
        self,
        pattern_id: str,
        performance: dict[str, Any],
        feedback_history: list[UserFeedback],
    ) -> list[PatternImprovement]:
        """指定されたパターンの改善提案を生成

        Args:
            pattern_id: パターンID
            performance: パフォーマンスデータ
            feedback_history: フィードバック履歴

        Returns:
            改善提案のリスト
        """
        improvements: list[PatternImprovement] = []
        pattern = self.pattern_database.get_pattern(pattern_id)

        if not pattern:
            logger.warning("パターンが見つかりません: %s", pattern_id)
            return improvements

        # パターン固有のフィードバックを取得
        pattern_feedback: list[UserFeedback] = [fb for fb in feedback_history if fb.pattern_id == pattern_id]

        # 失敗したケースのコメントを分析
        failed_feedback: list[UserFeedback] = [fb for fb in pattern_feedback if not fb.success and fb.comments]

        try:
            # 1. 正規表現パターンの改善
            regex_improvement = self._suggest_regex_improvements(pattern, failed_feedback, performance)
            if regex_improvement:
                improvements.append(regex_improvement)

            # 2. キーワードの改善
            keyword_improvement = self._suggest_keyword_improvements(pattern, failed_feedback, performance)
            if keyword_improvement:
                improvements.append(keyword_improvement)

            # 3. 信頼度の調整
            confidence_improvement = self._suggest_confidence_adjustments(pattern, performance)
            if confidence_improvement:
                improvements.append(confidence_improvement)

            # 4. カテゴリの見直し
            category_improvement = self._suggest_category_improvements(pattern, failed_feedback, performance)
            if category_improvement:
                improvements.append(category_improvement)

        except Exception as e:
            logger.error("パターン改善提案生成中にエラー (パターン: %s): %s", pattern_id, e)

        return improvements

    def _suggest_regex_improvements(
        self,
        pattern: Pattern,
        failed_feedback: list[UserFeedback],
        performance: dict[str, Any],
    ) -> PatternImprovement | None:
        """正規表現パターンの改善を提案

        Args:
            pattern: パターン
            failed_feedback: 失敗フィードバック
            performance: パフォーマンスデータ

        Returns:
            正規表現改善提案、提案がない場合はNone
        """
        if not failed_feedback or not pattern.regex_patterns:
            return None

        # 失敗コメントから共通パターンを抽出
        failed_comments: list[str] = [fb.comments for fb in failed_feedback if fb.comments]

        if not failed_comments:
            return None

        # 共通する失敗要因を特定
        common_failures = self._extract_common_failure_patterns(failed_comments)

        if not common_failures:
            return None

        # 新しい正規表現パターンを提案
        suggested_patterns: list[str] = []
        for failure_pattern in common_failures:
            # 既存パターンを拡張
            for existing_pattern in pattern.regex_patterns:
                enhanced_pattern = self._enhance_regex_pattern(existing_pattern, failure_pattern)
                if enhanced_pattern and enhanced_pattern not in suggested_patterns:
                    suggested_patterns.append(enhanced_pattern)

        if not suggested_patterns:
            return None

        return PatternImprovement(
            pattern_id=pattern.id,
            improvement_type="regex_enhancement",
            description=f"正規表現パターンの拡張により検出精度を向上 (失敗率: {1 - performance['success_rate']:.1%})",
            suggested_changes={
                "regex_patterns": suggested_patterns,
                "original_patterns": pattern.regex_patterns,
            },
            confidence=0.7,
            supporting_data={
                "failed_feedback_count": len(failed_feedback),
                "common_failures": common_failures,
                "current_success_rate": performance["success_rate"],
            },
        )

    def _extract_common_failure_patterns(self, failed_comments: list[str]) -> list[str]:
        """失敗コメントから共通パターンを抽出

        Args:
            failed_comments: 失敗コメントのリスト

        Returns:
            共通する失敗パターンのリスト
        """
        # エラーメッセージやキーワードを抽出
        all_words: list[str] = []
        for comment in failed_comments:
            # 単語を抽出（英数字のみ）
            words: list[str] = re.findall(r"\b\w+\b", comment.lower())
            all_words.extend(words)

        # 頻出単語を特定
        word_counts: CounterType[str] = Counter(all_words)
        common_words: list[str] = [word for word, count in word_counts.most_common(10) if count >= 2]

        # 共通するフレーズを抽出
        common_phrases: list[str] = []
        for comment in failed_comments:
            comment_lower = comment.lower()
            for word in common_words:
                if word in comment_lower:
                    # 単語の前後のコンテキストを抽出
                    pattern = rf"\b\w*{re.escape(word)}\w*\b"
                    matches: list[str] = re.findall(pattern, comment_lower)
                    common_phrases.extend(matches)

        # 重複を除去して返す
        return list(set(common_phrases))

    def _enhance_regex_pattern(self, original_pattern: str, failure_pattern: str) -> str | None:
        """既存の正規表現パターンを拡張

        Args:
            original_pattern: 元の正規表現パターン
            failure_pattern: 失敗パターン

        Returns:
            拡張された正規表現パターン、拡張できない場合はNone
        """
        try:
            # 失敗パターンをエスケープ
            escaped_failure = re.escape(failure_pattern)

            # 既存パターンと組み合わせ
            enhanced_pattern = f"({original_pattern}|{escaped_failure})"

            # パターンの妥当性をチェック
            re.compile(enhanced_pattern)

            return enhanced_pattern

        except re.error:
            logger.warning("正規表現パターンの拡張に失敗: %s + %s", original_pattern, failure_pattern)
            return None

    def _suggest_keyword_improvements(
        self,
        pattern: Pattern,
        failed_feedback: list[UserFeedback],
        performance: dict[str, Any],
    ) -> PatternImprovement | None:
        """キーワードの改善を提案

        Args:
            pattern: パターン
            failed_feedback: 失敗フィードバック
            performance: パフォーマンスデータ

        Returns:
            キーワード改善提案、提案がない場合はNone
        """
        if not failed_feedback:
            return None

        # 失敗コメントから新しいキーワードを抽出
        failed_comments: list[str] = [fb.comments for fb in failed_feedback if fb.comments]

        if not failed_comments:
            return None

        # 新しいキーワード候補を抽出
        new_keywords = self._extract_keywords_from_comments(failed_comments)

        # 既存キーワードと重複しないものを選択
        existing_keywords_lower = [kw.lower() for kw in pattern.keywords]
        suggested_keywords = [kw for kw in new_keywords if kw.lower() not in existing_keywords_lower]

        if not suggested_keywords:
            return None

        return PatternImprovement(
            pattern_id=pattern.id,
            improvement_type="keyword_enhancement",
            description=f"キーワードの追加により検出範囲を拡張 (現在の成功率: {performance['success_rate']:.1%})",
            suggested_changes={
                "additional_keywords": suggested_keywords,
                "current_keywords": pattern.keywords,
            },
            confidence=0.6,
            supporting_data={
                "failed_feedback_count": len(failed_feedback),
                "extracted_keywords": new_keywords,
            },
        )

    def _extract_keywords_from_comments(self, comments: list[str]) -> list[str]:
        """コメントからキーワードを抽出

        Args:
            comments: コメントのリスト

        Returns:
            抽出されたキーワードのリスト
        """
        all_words: list[str] = []
        for comment in comments:
            # 英数字の単語を抽出
            words: list[str] = re.findall(r"\b[a-zA-Z]\w+\b", comment)
            all_words.extend([word.lower() for word in words])

        # 頻出単語を特定
        word_counts: CounterType[str] = Counter(all_words)

        # ストップワードを除外
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
        }

        # 意味のあるキーワードを選択
        keywords: list[str] = []
        for word, count in word_counts.most_common(20):
            if word not in stop_words and len(word) > 2 and count >= 2 and not word.isdigit():
                keywords.append(word)

        return keywords[:10]  # 上位10個まで

    def _suggest_confidence_adjustments(
        self,
        pattern: Pattern,
        performance: dict[str, Any],
    ) -> PatternImprovement | None:
        """信頼度の調整を提案

        Args:
            pattern: パターン
            performance: パフォーマンスデータ

        Returns:
            信頼度調整提案、提案がない場合はNone
        """
        current_confidence = pattern.confidence_base
        success_rate = performance["success_rate"]

        # 成功率に基づいて適切な信頼度を計算
        suggested_confidence = success_rate * 0.9  # 成功率より少し低めに設定

        # 現在の信頼度との差が大きい場合のみ提案
        confidence_diff = abs(suggested_confidence - current_confidence)

        if confidence_diff < 0.1:  # 差が小さい場合は提案しない
            return None

        return PatternImprovement(
            pattern_id=pattern.id,
            improvement_type="confidence_adjustment",
            description=f"実際の成功率 ({success_rate:.1%}) に基づいて信頼度を調整",
            suggested_changes={
                "confidence_base": suggested_confidence,
                "current_confidence": current_confidence,
            },
            confidence=0.8,
            supporting_data={
                "success_rate": success_rate,
                "total_feedback": performance["total_feedback"],
                "confidence_difference": confidence_diff,
            },
        )

    def _suggest_category_improvements(
        self,
        pattern: Pattern,
        failed_feedback: list[UserFeedback],
        performance: dict[str, Any],
    ) -> PatternImprovement | None:
        """カテゴリの改善を提案

        Args:
            pattern: パターン
            failed_feedback: 失敗フィードバック
            performance: パフォーマンスデータ

        Returns:
            カテゴリ改善提案、提案がない場合はNone
        """
        if not failed_feedback:
            return None

        # 失敗コメントからカテゴリを推測
        failed_comments = [fb.comments for fb in failed_feedback if fb.comments]

        if not failed_comments:
            return None

        suggested_category = self._infer_category_from_comments(failed_comments)

        if suggested_category == pattern.category or not suggested_category:
            return None

        return PatternImprovement(
            pattern_id=pattern.id,
            improvement_type="category_change",
            description=f"失敗パターンの分析に基づいてカテゴリを '{pattern.category}' から '{suggested_category}' に変更",
            suggested_changes={
                "category": suggested_category,
                "current_category": pattern.category,
            },
            confidence=0.5,
            supporting_data={
                "failed_feedback_count": len(failed_feedback),
                "analysis_comments": failed_comments[:5],  # 最初の5件のコメント
            },
        )

    def _infer_category_from_comments(self, comments: list[str]) -> str | None:
        """コメントからカテゴリを推測

        Args:
            comments: コメントのリスト

        Returns:
            推測されたカテゴリ、推測できない場合はNone
        """
        all_text = " ".join(comments).lower()

        category_keywords: dict[str, list[str]] = {
            "permission": ["permission", "denied", "access", "forbidden", "unauthorized", "権限"],
            "network": ["timeout", "connection", "network", "ssl", "certificate", "dns", "ネットワーク"],
            "dependency": ["module", "import", "package", "not found", "missing", "依存"],
            "configuration": ["config", "configuration", "setting", "invalid", "malformed", "設定"],
            "build": ["build", "compile", "compilation", "make", "cmake", "ビルド"],
            "test": ["test", "assertion", "failed", "expect", "should", "テスト"],
            "syntax": ["syntax", "parse", "invalid", "unexpected", "構文"],
            "runtime": ["runtime", "execution", "null", "undefined", "reference", "実行時"],
        }

        category_scores: dict[str, int] = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in all_text)
            if score > 0:
                category_scores[category] = score

        if not category_scores:
            return None

        # 最もスコアの高いカテゴリを返す
        return max(category_scores, key=lambda key: category_scores[key])

    async def apply_pattern_improvement(self, improvement: PatternImprovement) -> bool:
        """パターン改善を適用

        Args:
            improvement: パターン改善提案

        Returns:
            適用成功フラグ
        """
        if not self._initialized:
            await self.initialize()

        logger.info("パターン改善を適用中: %s (%s)", improvement.pattern_id, improvement.improvement_type)

        try:
            pattern = self.pattern_database.get_pattern(improvement.pattern_id)
            if not pattern:
                logger.error("パターンが見つかりません: %s", improvement.pattern_id)
                return False

            # 改善タイプに応じて適用
            if improvement.improvement_type == "regex_enhancement":
                pattern.regex_patterns = improvement.suggested_changes["regex_patterns"]

            elif improvement.improvement_type == "keyword_enhancement":
                additional_keywords = improvement.suggested_changes["additional_keywords"]
                pattern.keywords.extend(additional_keywords)
                # 重複を除去
                pattern.keywords = list(set(pattern.keywords))

            elif improvement.improvement_type == "confidence_adjustment":
                pattern.confidence_base = improvement.suggested_changes["confidence_base"]

            elif improvement.improvement_type == "category_change":
                pattern.category = improvement.suggested_changes["category"]

            # パターンを更新
            pattern.updated_at = datetime.now()
            success = self.pattern_database.update_pattern(pattern)

            if success:
                # 改善履歴に記録
                improvement_record = {
                    "pattern_id": improvement.pattern_id,
                    "improvement_type": improvement.improvement_type,
                    "description": improvement.description,
                    "applied_at": datetime.now().isoformat(),
                    "confidence": improvement.confidence,
                    "changes": improvement.suggested_changes,
                }

                self.improvement_history.append(improvement_record)
                await self._save_improvement_history()

                logger.info("パターン改善を適用しました: %s", improvement.pattern_id)

            return success

        except Exception as e:
            logger.error("パターン改善適用中にエラー: %s", e)
            return False

    async def get_improvement_recommendations(
        self,
        feedback_history: list[UserFeedback],
        max_recommendations: int = 10,
    ) -> list[PatternImprovement]:
        """改善推奨事項を取得

        Args:
            feedback_history: フィードバック履歴
            max_recommendations: 最大推奨数

        Returns:
            改善推奨事項のリスト
        """
        if not self._initialized:
            await self.initialize()

        # パターン改善を提案
        improvements = await self.suggest_pattern_improvements(feedback_history)

        # 信頼度でソート
        improvements.sort(key=lambda x: x.confidence, reverse=True)

        # 最大数に制限
        return improvements[:max_recommendations]

    async def _save_improvement_history(self) -> None:
        """改善履歴を保存"""
        try:
            with open(self.improvement_history_file, "w", encoding="utf-8") as f:
                json.dump(self.improvement_history, f, ensure_ascii=False, indent=2)
            logger.debug("改善履歴を保存しました")
        except Exception as e:
            logger.error("改善履歴の保存に失敗: %s", e)

    async def _save_pattern_analytics(self) -> None:
        """パターン分析データを保存"""
        try:
            with open(self.pattern_analytics_file, "w", encoding="utf-8") as f:
                json.dump(self.pattern_analytics, f, ensure_ascii=False, indent=2)
            logger.debug("パターン分析データを保存しました")
        except Exception as e:
            logger.error("パターン分析データの保存に失敗: %s", e)

    def get_improvement_statistics(self) -> dict[str, Any]:
        """改善統計情報を取得

        Returns:
            改善統計情報
        """
        if not self._initialized:
            return {"error": "パターン改善システムが初期化されていません"}

        # 改善タイプ別の統計
        improvement_types = Counter(record["improvement_type"] for record in self.improvement_history)

        # 最近の改善（過去30日）
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_improvements = [
            record
            for record in self.improvement_history
            if datetime.fromisoformat(record["applied_at"]) >= recent_cutoff
        ]

        return {
            "total_improvements": len(self.improvement_history),
            "improvement_types": dict(improvement_types),
            "recent_improvements": len(recent_improvements),
            "analyzed_patterns": len(self.pattern_analytics),
            "min_feedback_threshold": self.min_feedback_for_improvement,
            "improvement_threshold": self.improvement_threshold,
        }

    async def cleanup(self) -> None:
        """パターン改善システムのクリーンアップ"""
        if not self._initialized:
            return

        logger.info("パターン改善システムをクリーンアップ中...")

        # データを保存
        await self._save_improvement_history()
        await self._save_pattern_analytics()

        logger.info("パターン改善システムのクリーンアップ完了")
