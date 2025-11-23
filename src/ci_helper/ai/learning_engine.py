"""
学習エンジン

新しいエラーパターンの自動学習とユーザーフィードバックの処理を行います。
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .models import FixSuggestion, Pattern, PatternMatch, UserFeedback
from .pattern_database import PatternDatabase

if TYPE_CHECKING:
    from .feedback_collector import FeedbackCollector

logger = logging.getLogger(__name__)


class LearningEngine:
    """学習エンジンクラス

    新しいパターンの学習とユーザーフィードバックの処理を行います。
    """

    def __init__(
        self,
        pattern_database: PatternDatabase,
        learning_data_dir: Path | str = "data/learning",
        min_pattern_occurrences: int = 3,
        confidence_adjustment_factor: float = 0.1,
        feedback_collector: FeedbackCollector | None = None,
    ):
        """学習エンジンを初期化

        Args:
            pattern_database: パターンデータベース
            learning_data_dir: 学習データディレクトリ
            min_pattern_occurrences: パターン提案に必要な最小出現回数
            confidence_adjustment_factor: 信頼度調整係数
            feedback_collector: フィードバック収集システム
        """
        self.pattern_database = pattern_database
        self.learning_data_dir = Path(learning_data_dir)
        self.min_pattern_occurrences = min_pattern_occurrences
        self.confidence_adjustment_factor = confidence_adjustment_factor

        # フィードバック収集システム
        self.feedback_collector = feedback_collector
        self._feedback_collector_config = {"learning_data_dir": learning_data_dir}

        # パターン改善システム（遅延初期化）
        self.pattern_improvement = None
        self._pattern_improvement_config = {
            "pattern_database": pattern_database,
            "learning_data_dir": learning_data_dir,
            "min_pattern_occurrences": min_pattern_occurrences,
        }

        # 学習データファイルのパス
        self.feedback_file = self.learning_data_dir / "feedback.json"
        self.patterns_learned_file = self.learning_data_dir / "patterns_learned.json"
        self.error_frequency_file = self.learning_data_dir / "error_frequency.json"
        self.unknown_errors_file = self.learning_data_dir / "unknown_errors.json"
        self.potential_patterns_file = self.learning_data_dir / "potential_patterns.json"

        # 学習データ
        self.feedback_history: list[UserFeedback] = []
        self.learned_patterns: dict[str, dict[str, Any]] = {}
        self.error_frequency: dict[str, int] = defaultdict(int)
        self.pattern_success_tracking: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"successes": 0, "failures": 0, "total_uses": 0}
        )
        self.fix_application_history: list[dict[str, Any]] = []

        self._initialized = False

    async def initialize(self) -> None:
        """学習エンジンを初期化"""
        if self._initialized:
            return

        logger.info("学習エンジンを初期化中...")

        # 学習データディレクトリを作成
        self.learning_data_dir.mkdir(parents=True, exist_ok=True)

        # フィードバック収集システムを初期化
        if self.feedback_collector is None:
            from .feedback_collector import FeedbackCollector

            self.feedback_collector = FeedbackCollector(self._feedback_collector_config["learning_data_dir"])
        await self.feedback_collector.initialize()

        # パターン改善システムを初期化
        if self.pattern_improvement is None:
            from .pattern_improvement import PatternImprovementSystem

            self.pattern_improvement = PatternImprovementSystem(
                self._pattern_improvement_config["pattern_database"],
                self._pattern_improvement_config["learning_data_dir"],
                self._pattern_improvement_config["min_pattern_occurrences"],
            )
        await self.pattern_improvement.initialize()

        # 既存の学習データを読み込み
        await self._load_learning_data()

        self._initialized = True
        logger.info("学習エンジンの初期化完了")

    async def _ensure_feedback_collector_initialized(self) -> None:
        """フィードバック収集システムが初期化されていることを確認"""
        if self.feedback_collector is None:
            from .feedback_collector import FeedbackCollector

            self.feedback_collector = FeedbackCollector(self._feedback_collector_config["learning_data_dir"])
            await self.feedback_collector.initialize()

    async def _ensure_pattern_improvement_initialized(self) -> None:
        """パターン改善システムが初期化されていることを確認"""
        if self.pattern_improvement is None:
            from .pattern_improvement import PatternImprovementSystem

            self.pattern_improvement = PatternImprovementSystem(
                self._pattern_improvement_config["pattern_database"],
                self._pattern_improvement_config["learning_data_dir"],
                self._pattern_improvement_config["min_pattern_occurrences"],
            )
            await self.pattern_improvement.initialize()

    async def _load_learning_data(self) -> None:
        """既存の学習データを読み込み"""
        try:
            # フィードバック履歴を読み込み
            if self.feedback_file.exists():
                with open(self.feedback_file, encoding="utf-8") as f:
                    feedback_data = json.load(f)
                    self.feedback_history = [
                        UserFeedback(
                            pattern_id=fb["pattern_id"],
                            fix_suggestion_id=fb["fix_suggestion_id"],
                            rating=fb["rating"],
                            success=fb["success"],
                            comments=fb.get("comments"),
                            timestamp=datetime.fromisoformat(fb["timestamp"]),
                        )
                        for fb in feedback_data
                    ]
                logger.info("フィードバック履歴を %d 件読み込みました", len(self.feedback_history))

            # 学習済みパターンを読み込み
            if self.patterns_learned_file.exists():
                with open(self.patterns_learned_file, encoding="utf-8") as f:
                    self.learned_patterns = json.load(f)
                logger.info("学習済みパターンを %d 個読み込みました", len(self.learned_patterns))

            # エラー頻度データを読み込み
            if self.error_frequency_file.exists():
                with open(self.error_frequency_file, encoding="utf-8") as f:
                    frequency_data = json.load(f)
                    self.error_frequency = defaultdict(int, frequency_data)
                logger.info("エラー頻度データを読み込みました")

            # パターン成功率追跡データを構築
            self._build_pattern_success_tracking()

        except Exception as e:
            logger.error("学習データの読み込み中にエラー: %s", e)

    def _build_pattern_success_tracking(self) -> None:
        """フィードバック履歴からパターン成功率追跡データを構築"""
        for feedback in self.feedback_history:
            pattern_id = feedback.pattern_id
            tracking = self.pattern_success_tracking[pattern_id]

            tracking["total_uses"] += 1
            if feedback.success:
                tracking["successes"] += 1
            else:
                tracking["failures"] += 1

            # 成功率を計算
            tracking["success_rate"] = tracking["successes"] / tracking["total_uses"]

    async def learn_from_feedback(self, feedback: UserFeedback) -> None:
        """ユーザーフィードバックから学習

        Args:
            feedback: ユーザーフィードバック
        """
        if not self._initialized:
            await self.initialize()

        logger.info("フィードバックから学習中: パターン=%s, 成功=%s", feedback.pattern_id, feedback.success)

        # フィードバック履歴に追加
        self.feedback_history.append(feedback)

        # パターン成功率を更新
        await self._update_pattern_success_rate(feedback)

        # 信頼度を調整
        await self._adjust_pattern_confidence(feedback)

        # 学習データを保存
        await self._save_feedback_data()

        logger.info("フィードバック学習完了")

    async def _update_pattern_success_rate(self, feedback: UserFeedback) -> None:
        """パターンの成功率を更新

        Args:
            feedback: ユーザーフィードバック
        """
        pattern_id = feedback.pattern_id
        tracking = self.pattern_success_tracking[pattern_id]

        tracking["total_uses"] += 1
        if feedback.success:
            tracking["successes"] += 1
        else:
            tracking["failures"] += 1

        # 成功率を計算
        tracking["success_rate"] = tracking["successes"] / tracking["total_uses"]

        # パターンデータベースの成功率も更新
        pattern = self.pattern_database.get_pattern(pattern_id)
        if isinstance(pattern, Pattern):
            updated_pattern = replace(pattern)
            # 指数移動平均で成功率を更新
            alpha = 0.2
            success_value = 1.0 if feedback.success else 0.0
            new_success_rate = alpha * success_value + (1 - alpha) * updated_pattern.success_rate
            updated_pattern.success_rate = max(0.1, min(1.0, new_success_rate))
            updated_pattern.updated_at = datetime.now()

            self.pattern_database.update_pattern(updated_pattern)
            logger.info("パターン %s の成功率を %.3f に更新", pattern_id, updated_pattern.success_rate)

    async def _adjust_pattern_confidence(self, feedback: UserFeedback) -> None:
        """フィードバックに基づいてパターンの信頼度を調整

        Args:
            feedback: ユーザーフィードバック
        """
        pattern = self.pattern_database.get_pattern(feedback.pattern_id)
        if not isinstance(pattern, Pattern):
            return
        updated_pattern = replace(pattern)

        # 評価に基づく調整
        rating_adjustment = (feedback.rating - 3) * self.confidence_adjustment_factor / 2  # -1.0 to 1.0

        # 成功/失敗に基づく調整
        success_adjustment = (
            self.confidence_adjustment_factor if feedback.success else -self.confidence_adjustment_factor
        )

        # 総合調整
        total_adjustment = (rating_adjustment + success_adjustment) / 2

        # 信頼度を更新
        new_confidence = updated_pattern.confidence_base + total_adjustment
        updated_pattern.confidence_base = max(0.1, min(1.0, new_confidence))
        updated_pattern.updated_at = datetime.now()

        self.pattern_database.update_pattern(updated_pattern)
        logger.info(
            "パターン %s の信頼度を %.3f に調整",
            feedback.pattern_id,
            updated_pattern.confidence_base,
        )

    async def discover_new_patterns(self, failed_logs: list[str]) -> list[Pattern]:
        """失敗ログから新しいパターンを発見

        Args:
            failed_logs: 失敗ログのリスト

        Returns:
            発見された新しいパターンのリスト
        """
        if not self._initialized:
            await self.initialize()

        logger.info("新しいパターンの発見を開始: %d 個のログを分析", len(failed_logs))

        discovered_patterns: list[Pattern] = []

        try:
            # エラーメッセージを抽出
            error_messages = []
            for log in failed_logs:
                extracted_errors = self._extract_error_messages(log)
                error_messages.extend(extracted_errors)

            # エラー頻度を更新
            for error in error_messages:
                self.error_frequency[error] += 1

            # 頻出エラーから新しいパターンを生成
            frequent_errors = self._find_frequent_errors()
            for error_signature, frequency in frequent_errors:
                if frequency >= self.min_pattern_occurrences:
                    # 既存パターンと重複していないかチェック
                    if not self._is_duplicate_pattern(error_signature):
                        new_pattern = await self._create_pattern_from_error(error_signature, frequency)
                        if new_pattern:
                            discovered_patterns.append(new_pattern)

            # 学習データを保存
            await self._save_error_frequency_data()

            logger.info("新しいパターンを %d 個発見しました", len(discovered_patterns))
            return discovered_patterns

        except Exception as e:
            logger.error("パターン発見中にエラー: %s", e)
            return []

    def _extract_error_messages(self, log_content: str) -> list[str]:
        """ログからエラーメッセージを抽出

        Args:
            log_content: ログ内容

        Returns:
            抽出されたエラーメッセージのリスト
        """
        error_messages: list[str] = []

        # 一般的なエラーパターン
        error_patterns = [
            r"Error: (.+)",
            r"Exception: (.+)",
            r"ERROR: (.+)",
            r"FAILED: (.+)",
            r"(.+Error): (.+)",
            r"(.+Exception): (.+)",
            r"CRITICAL: (.+)",
            r"FATAL: (.+)",
        ]

        for pattern in error_patterns:
            matches = re.finditer(pattern, log_content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                error_msg = match.group(1) if match.lastindex == 1 else match.group(0)
                # エラーメッセージを正規化
                normalized_error = self._normalize_error_message(error_msg)
                if normalized_error and len(normalized_error) > 10:  # 短すぎるエラーは除外
                    error_messages.append(normalized_error)

        return error_messages

    def _normalize_error_message(self, error_message: str) -> str:
        """エラーメッセージを正規化

        Args:
            error_message: 元のエラーメッセージ

        Returns:
            正規化されたエラーメッセージ
        """
        # 改行を削除
        normalized = error_message.replace("\n", " ").replace("\r", " ")

        # 複数のスペースを単一のスペースに
        normalized = re.sub(r"\s+", " ", normalized)

        # 先頭と末尾の空白を削除
        normalized = normalized.strip()

        # パスや数値などの可変部分を汎用化
        # ファイルパス
        normalized = re.sub(r"/[^\s]+", "/path/to/file", normalized)
        normalized = re.sub(r"[A-Za-z]:\\\\[^\s]+", "C:\\\\path\\\\to\\\\file", normalized)

        # 数値
        normalized = re.sub(r"\b\d+\b", "N", normalized)

        # UUIDやハッシュ
        normalized = re.sub(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", "UUID", normalized)
        normalized = re.sub(r"\b[a-f0-9]{32,}\b", "HASH", normalized)

        return normalized

    def _find_frequent_errors(self) -> list[tuple[str, int]]:
        """頻出エラーを特定

        Returns:
            (エラーシグネチャ, 頻度) のタプルのリスト
        """
        # 頻度でソート
        sorted_errors = sorted(self.error_frequency.items(), key=lambda x: x[1], reverse=True)

        # 最小出現回数以上のエラーのみ返す
        frequent_errors = [(error, freq) for error, freq in sorted_errors if freq >= self.min_pattern_occurrences]

        return frequent_errors

    def _is_duplicate_pattern(self, error_signature: str) -> bool:
        """既存パターンと重複していないかチェック

        Args:
            error_signature: エラーシグネチャ

        Returns:
            重複している場合True
        """
        existing_patterns = self.pattern_database.get_all_patterns()

        for pattern in existing_patterns:
            # 正規表現パターンとの類似性をチェック
            for regex_pattern in pattern.regex_patterns:
                try:
                    if re.search(regex_pattern, error_signature, re.IGNORECASE):
                        return True
                except re.error:
                    continue

            # キーワードとの類似性をチェック
            error_words = set(error_signature.lower().split())
            pattern_words = set(" ".join(pattern.keywords).lower().split())

            # 共通単語の割合が高い場合は重複とみなす
            if error_words and pattern_words:
                intersection = error_words & pattern_words
                similarity = len(intersection) / len(error_words | pattern_words)
                if similarity > 0.7:  # 70%以上の類似性
                    return True

        return False

    async def _create_pattern_from_error(self, error_signature: str, frequency: int) -> Pattern | None:
        """エラーシグネチャから新しいパターンを作成

        Args:
            error_signature: エラーシグネチャ
            frequency: 出現頻度

        Returns:
            作成されたパターン、作成できない場合はNone
        """
        try:
            # パターンIDを生成
            pattern_id = self._generate_pattern_id(error_signature)

            # カテゴリを推測
            category = self._infer_category_from_error(error_signature)

            # キーワードを抽出
            keywords = self._extract_keywords_from_error(error_signature)

            # 正規表現パターンを生成
            regex_pattern = self._generate_regex_pattern(error_signature)

            # 信頼度を頻度に基づいて設定
            confidence_base = min(0.9, 0.5 + (frequency - self.min_pattern_occurrences) * 0.1)

            # パターンを作成
            new_pattern = Pattern(
                id=pattern_id,
                name=f"自動学習パターン: {error_signature[:50]}...",
                category=category,
                regex_patterns=[regex_pattern],
                keywords=keywords,
                context_requirements=[],
                confidence_base=confidence_base,
                success_rate=0.5,  # 初期値
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,  # 自動学習パターン
            )

            # 学習済みパターンとして記録
            self.learned_patterns[pattern_id] = {
                "error_signature": error_signature,
                "frequency": frequency,
                "created_at": datetime.now().isoformat(),
                "category": category,
            }

            logger.info("新しいパターンを作成: %s (頻度: %d)", pattern_id, frequency)
            return new_pattern

        except Exception as e:
            logger.error("パターン作成中にエラー: %s", e)
            return None

    def _generate_pattern_id(self, error_signature: str) -> str:
        """エラーシグネチャからパターンIDを生成

        Args:
            error_signature: エラーシグネチャ

        Returns:
            生成されたパターンID
        """
        # エラーシグネチャから主要な単語を抽出
        words = re.findall(r"\b\w+\b", error_signature.lower())

        # ストップワードを除外
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        meaningful_words = [word for word in words if word not in stop_words and len(word) > 2]

        # 最初の3つの単語を使用してIDを生成
        id_words = meaningful_words[:3]
        if not id_words:
            id_words = ["learned", "pattern"]

        pattern_id = "_".join(id_words)

        # 既存のIDと重複しないように番号を追加
        base_id = pattern_id
        counter = 1
        while self.pattern_database.get_pattern(pattern_id) or pattern_id in self.learned_patterns:
            pattern_id = f"{base_id}_{counter}"
            counter += 1

        return pattern_id

    def _infer_category_from_error(self, error_signature: str) -> str:
        """エラーシグネチャからカテゴリを推測

        Args:
            error_signature: エラーシグネチャ

        Returns:
            推測されたカテゴリ
        """
        error_lower = error_signature.lower()

        category_patterns = {
            "permission": ["permission", "denied", "access", "forbidden", "unauthorized"],
            "network": ["timeout", "connection", "network", "ssl", "certificate", "dns"],
            "dependency": ["module", "import", "package", "not found", "missing"],
            "configuration": ["config", "configuration", "setting", "invalid", "malformed"],
            "build": ["build", "compile", "compilation", "make", "cmake"],
            "test": ["test", "assertion", "failed", "expect", "should"],
            "syntax": ["syntax", "parse", "invalid", "unexpected"],
            "runtime": ["runtime", "execution", "null", "undefined", "reference"],
        }

        for category, keywords in category_patterns.items():
            if any(keyword in error_lower for keyword in keywords):
                return category

        return "general"

    def _extract_keywords_from_error(self, error_signature: str) -> list[str]:
        """エラーシグネチャからキーワードを抽出

        Args:
            error_signature: エラーシグネチャ

        Returns:
            抽出されたキーワードのリスト
        """
        # 単語を抽出
        words = re.findall(r"\b\w+\b", error_signature.lower())

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
        }
        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        # 頻度でソートして上位を選択
        word_counts = Counter(keywords)
        top_keywords = [word for word, _ in word_counts.most_common(10)]

        return top_keywords

    def _generate_regex_pattern(self, error_signature: str) -> str:
        """エラーシグネチャから正規表現パターンを生成

        Args:
            error_signature: エラーシグネチャ

        Returns:
            生成された正規表現パターン
        """
        # 特殊文字をエスケープ
        escaped = re.escape(error_signature)

        # 汎用化された部分を正規表現に変換
        pattern = escaped
        pattern = pattern.replace(r"\/path\/to\/file", r"[^\s]+")  # パス
        pattern = pattern.replace(r"C:\\\\path\\\\to\\\\file", r"[A-Za-z]:\\\\[^\s]+")  # Windowsパス
        pattern = pattern.replace(r"\bN\b", r"\d+")  # 数値
        pattern = pattern.replace("UUID", r"[a-f0-9-]+")  # UUID
        pattern = pattern.replace("HASH", r"[a-f0-9]+")  # ハッシュ

        return pattern

    async def update_pattern_confidence(self, pattern_id: str, success: bool) -> None:
        """パターンの信頼度を更新

        Args:
            pattern_id: パターンID
            success: 成功フラグ
        """
        if not self._initialized:
            await self.initialize()

        # 成功率追跡を更新
        tracking = self.pattern_success_tracking[pattern_id]
        tracking["total_uses"] += 1

        if success:
            tracking["successes"] += 1
        else:
            tracking["failures"] += 1

        tracking["success_rate"] = tracking["successes"] / tracking["total_uses"]

        # パターンデータベースの信頼度を更新
        pattern = self.pattern_database.get_pattern(pattern_id)
        if isinstance(pattern, Pattern):
            success_rate = tracking["success_rate"]
            updated_pattern = replace(pattern)
            updated_pattern.confidence_base = self._calculate_adjusted_confidence(
                updated_pattern.confidence_base,
                success_rate,
            )
            updated_pattern.updated_at = datetime.now()

            self.pattern_database.update_pattern(updated_pattern)
            logger.info("パターン %s の信頼度を更新: %.3f", pattern_id, updated_pattern.confidence_base)

    def _calculate_adjusted_confidence(self, base_confidence: float, success_rate: float) -> float:
        """成功率を元に信頼度を調整"""

        adjustment = (success_rate - 0.5) * self.confidence_adjustment_factor
        new_confidence = base_confidence + adjustment
        return max(0.1, min(1.0, new_confidence))

    async def _save_feedback_data(self) -> None:
        """フィードバックデータを保存"""
        try:
            feedback_data = [
                {
                    "pattern_id": fb.pattern_id,
                    "fix_suggestion_id": fb.fix_suggestion_id,
                    "rating": fb.rating,
                    "success": fb.success,
                    "comments": fb.comments,
                    "timestamp": fb.timestamp.isoformat(),
                }
                for fb in self.feedback_history
            ]

            with open(self.feedback_file, "w", encoding="utf-8") as f:
                json.dump(feedback_data, f, ensure_ascii=False, indent=2)

            logger.debug("フィードバックデータを保存しました")

        except Exception as e:
            logger.error("フィードバックデータの保存に失敗: %s", e)

    async def _save_error_frequency_data(self) -> None:
        """エラー頻度データを保存"""
        try:
            with open(self.error_frequency_file, "w", encoding="utf-8") as f:
                json.dump(dict(self.error_frequency), f, ensure_ascii=False, indent=2)

            logger.debug("エラー頻度データを保存しました")

        except Exception as e:
            logger.error("エラー頻度データの保存に失敗: %s", e)

    async def _save_learned_patterns_data(self) -> None:
        """学習済みパターンデータを保存"""
        try:
            with open(self.patterns_learned_file, "w", encoding="utf-8") as f:
                json.dump(self.learned_patterns, f, ensure_ascii=False, indent=2)

            logger.debug("学習済みパターンデータを保存しました")

        except Exception as e:
            logger.error("学習済みパターンデータの保存に失敗: %s", e)

    async def _save_learning_data(self) -> None:
        """学習関連データをまとめて保存"""

        await self._save_feedback_data()
        await self._save_error_frequency_data()
        await self._save_learned_patterns_data()

    def get_learning_statistics(self) -> dict[str, Any]:
        """学習統計情報を取得

        Returns:
            学習統計情報の辞書
        """
        # フィードバック統計
        total_feedback = len(self.feedback_history)
        successful_feedback = 0
        recent_feedback: list[UserFeedback] = []
        recent_cutoff = datetime.now() - timedelta(days=30)

        for feedback in self.feedback_history:
            success_flag = getattr(feedback, "success", False)
            if isinstance(success_flag, bool) and success_flag:
                successful_feedback += 1

            timestamp = getattr(feedback, "timestamp", None)
            if isinstance(timestamp, datetime) and timestamp >= recent_cutoff:
                recent_feedback.append(feedback)

        # パターン成功率統計
        pattern_stats = {}
        for pattern_id, tracking in self.pattern_success_tracking.items():
            if tracking["total_uses"] > 0:
                pattern_stats[pattern_id] = {
                    "success_rate": tracking["success_rate"],
                    "total_uses": tracking["total_uses"],
                }

        return {
            "initialized": self._initialized,
            "total_feedback": total_feedback,
            "successful_feedback": successful_feedback,
            "success_rate": successful_feedback / total_feedback if total_feedback > 0 else 0.0,
            "recent_feedback_count": len(recent_feedback),
            "learned_patterns_count": len(self.learned_patterns),
            "error_frequency_count": len(self.error_frequency),
            "tracked_errors_count": len(self.error_frequency),
            "pattern_success_stats": pattern_stats,
            "min_pattern_occurrences": self.min_pattern_occurrences,
        }

    async def cleanup(self) -> None:
        """学習エンジンのクリーンアップ"""
        if not self._initialized:
            return

        logger.info("学習エンジンをクリーンアップ中...")

        # 学習データを保存
        await self._save_feedback_data()
        await self._save_error_frequency_data()
        await self._save_learned_patterns_data()

        # フィードバック収集システムをクリーンアップ
        if self.feedback_collector:
            await self.feedback_collector.cleanup()

        # パターン改善システムをクリーンアップ
        if self.pattern_improvement:
            await self.pattern_improvement.cleanup()

        logger.info("学習エンジンのクリーンアップ完了")

    async def collect_and_process_feedback(
        self,
        pattern_matches: list[PatternMatch],
        fix_suggestions_or_log: list[FixSuggestion | Any] | str | None = None,
        interactive: bool = True,
        feedback_callback: Callable[[str], str] | None = None,
    ) -> list[UserFeedback]:
        """フィードバックを収集して学習に反映

        Args:
            pattern_matches: パターンマッチ結果のリスト
            fix_suggestions_or_log: 修正提案リストまたはログ文字列
            interactive: 対話的フィードバック収集フラグ
            feedback_callback: フィードバック収集用コールバック関数

        Returns:
            収集されたフィードバックのリスト
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_feedback_collector_initialized()
        assert self.feedback_collector is not None
        logger.info("フィードバック収集と学習処理を開始")

        collected_feedback: list[UserFeedback] = []
        log_content: str | None = None
        fix_suggestions: list[Any] | None = None

        if isinstance(fix_suggestions_or_log, str):
            log_content = fix_suggestions_or_log
        elif isinstance(fix_suggestions_or_log, list):
            fix_suggestions = fix_suggestions_or_log

        try:
            fallback_collect: Callable[..., Any] | None = None
            collector_fallback = getattr(
                self.feedback_collector,
                "collect_feedback",
                None,
            )
            if callable(collector_fallback):
                fallback_collect = collector_fallback

            suggestion_collector = self.feedback_collector.collect_feedback_for_suggestion

            if fix_suggestions is not None:
                iterable = zip(pattern_matches, fix_suggestions, strict=False)
            else:
                iterable = ((pattern_match, None) for pattern_match in pattern_matches)

            for pattern_match, fix_suggestion in iterable:
                feedback_result: UserFeedback | list[UserFeedback] | None

                if fix_suggestion is not None:
                    feedback_result = await suggestion_collector(
                        pattern_match,
                        fix_suggestion,
                        interactive,
                        feedback_callback,
                    )
                elif fallback_collect is not None:
                    feedback_result = fallback_collect(
                        pattern_match,
                        log_content,
                        interactive,
                        feedback_callback,
                    )
                    if inspect.isawaitable(feedback_result):
                        feedback_result = await feedback_result
                else:
                    continue

                feedback_items = self._normalize_feedback_results(feedback_result)

                for feedback in feedback_items:
                    collected_feedback.append(feedback)
                    await self.learn_from_feedback(feedback)

            logger.info("フィードバック収集と学習処理完了: %d 件処理", len(collected_feedback))
            return collected_feedback

        except Exception as e:
            logger.error("フィードバック収集と学習処理中にエラー: %s", e)
            return collected_feedback

    def _normalize_feedback_results(
        self, feedback_result: UserFeedback | list[UserFeedback] | None
    ) -> list[UserFeedback]:
        """フィードバック収集の結果をリスト形式に正規化"""

        if isinstance(feedback_result, list):
            return [fb for fb in feedback_result if isinstance(fb, UserFeedback)]

        if isinstance(feedback_result, UserFeedback):
            return [feedback_result]

        return []

    async def process_fix_application_feedback(
        self,
        pattern_id: str,
        fix_suggestion_id: str,
        success: bool,
        error_message: str | None = None,
        **metadata: Any,
    ) -> None:
        """修正適用結果のフィードバックを処理

        Args:
            pattern_id: パターンID
            fix_suggestion_id: 修正提案ID
            success: 適用成功フラグ
            error_message: エラーメッセージ（失敗時）
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_feedback_collector_initialized()
        assert self.feedback_collector is not None

        # フィードバック収集システムに結果を記録
        await self.feedback_collector.record_fix_application_result(
            pattern_id,
            fix_suggestion_id,
            success,
            error_message,
        )

        record = {
            "pattern_id": pattern_id,
            "fix_suggestion_id": fix_suggestion_id,
            "success": success,
            "error_message": error_message,
            "metadata": metadata,
            "recorded_at": datetime.now().isoformat(),
        }
        self.fix_application_history.append(record)

        # 学習エンジンでパターン信頼度を更新
        await self.update_pattern_confidence(pattern_id, success)

        logger.info("修正適用フィードバックを処理: パターン=%s, 成功=%s", pattern_id, success)

    def get_pattern_feedback_summary(self, pattern_id: str) -> dict[str, Any]:
        """指定されたパターンのフィードバック要約を取得"""

        feedback_stats: dict[str, Any]
        if self.feedback_collector is not None:
            feedback_stats = self.feedback_collector.get_feedback_statistics(pattern_id)
        else:
            feedback_stats = self._calculate_local_feedback_statistics(pattern_id)

        tracking_source = self.pattern_success_tracking.get(pattern_id, {})
        tracking = dict(tracking_source)
        total_uses = tracking.get("total_uses", 0) or 0
        successes = tracking.get("successes", 0)
        if total_uses > 0:
            tracking.setdefault("success_rate", successes / total_uses)
        else:
            tracking.setdefault("success_rate", 0.0)

        return {
            "pattern_id": pattern_id,
            "feedback_statistics": feedback_stats,
            "success_tracking": tracking,
            "total_feedback": feedback_stats.get("total_feedback", 0),
            "success_rate": feedback_stats.get("success_rate", 0.0),
            "average_rating": feedback_stats.get("average_rating", 0.0),
            "average_effectiveness": feedback_stats.get("success_rate", 0.0),
        }

    def _calculate_local_feedback_statistics(
        self,
        pattern_id: str,
    ) -> dict[str, Any]:
        """フィードバック収集システムが未初期化の場合の簡易統計"""

        relevant_feedback = [fb for fb in self.feedback_history if getattr(fb, "pattern_id", None) == pattern_id]

        if not relevant_feedback:
            return {
                "total_feedback": 0,
                "average_rating": 0.0,
                "success_rate": 0.0,
                "successful_feedback": 0,
                "failed_feedback": 0,
            }

        total_feedback = len(relevant_feedback)
        rating_sum = sum(getattr(fb, "rating", 0) or 0 for fb in relevant_feedback)
        success_count = sum(
            1
            for fb in relevant_feedback
            if isinstance(getattr(fb, "success", False), bool) and getattr(fb, "success", False)
        )
        failed_count = total_feedback - success_count

        average_rating = rating_sum / total_feedback if total_feedback else 0.0
        success_rate = success_count / total_feedback if total_feedback else 0.0

        return {
            "total_feedback": total_feedback,
            "average_rating": average_rating,
            "success_rate": success_rate,
            "successful_feedback": success_count,
            "failed_feedback": failed_count,
        }

    async def suggest_pattern_improvements(self) -> list[Any]:
        """パターン改善を提案

        Returns:
            パターン改善提案のリスト
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_pattern_improvement_initialized()
        await self._ensure_feedback_collector_initialized()
        assert self.pattern_improvement is not None
        assert self.feedback_collector is not None
        logger.info("パターン改善提案を開始")

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # パターン改善システムで改善提案を生成
            suggest_improvements = self.pattern_improvement.suggest_pattern_improvements
            improvements = await suggest_improvements(all_feedback)

            logger.info("パターン改善提案完了: %d 件の提案", len(improvements))
            return improvements

        except Exception as e:
            logger.error("パターン改善提案中にエラー: %s", e)
            return []

    async def apply_pattern_improvement(self, improvement: Any) -> bool:
        """パターン改善を適用

        Args:
            improvement: パターン改善提案

        Returns:
            適用成功フラグ
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_pattern_improvement_initialized()
        assert self.pattern_improvement is not None

        try:
            success = await self.pattern_improvement.apply_pattern_improvement(improvement)

            if success:
                # パターンデータベースを保存
                await self.pattern_database.save_patterns()
                logger.info("パターン改善を適用しました: %s", improvement.pattern_id)

            return success

        except Exception as e:
            logger.error("パターン改善適用中にエラー: %s", e)
            return False

    async def get_improvement_recommendations(
        self,
        max_recommendations: int = 10,
    ) -> list[Any]:
        """改善推奨事項を取得

        Args:
            max_recommendations: 最大推奨数

        Returns:
            改善推奨事項のリスト
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_pattern_improvement_initialized()
        await self._ensure_feedback_collector_initialized()
        assert self.pattern_improvement is not None
        assert self.feedback_collector is not None

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # 改善推奨事項を取得
            get_recommendations = self.pattern_improvement.get_improvement_recommendations
            recommendations = await get_recommendations(
                all_feedback,
                max_recommendations,
            )

            logger.info("改善推奨事項を %d 件取得", len(recommendations))
            return recommendations

        except Exception as e:
            logger.error("改善推奨事項取得中にエラー: %s", e)
            return []

    async def analyze_pattern_performance(self) -> dict[str, Any]:
        """パターンパフォーマンスを分析

        Returns:
            パターン別パフォーマンス分析結果
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_pattern_improvement_initialized()
        await self._ensure_feedback_collector_initialized()
        assert self.pattern_improvement is not None
        assert self.feedback_collector is not None

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # パフォーマンス分析を実行
            analyze_performance = self.pattern_improvement.analyze_pattern_performance
            performance_data = await analyze_performance(all_feedback)

            logger.info("パターンパフォーマンス分析完了: %d パターンを分析", len(performance_data))
            return performance_data

        except Exception as e:
            logger.error("パターンパフォーマンス分析中にエラー: %s", e)
            return {}

    async def update_pattern_database_dynamically(self) -> dict[str, Any]:
        """パターンデータベースを動的に更新

        Returns:
            更新結果の統計情報
        """
        if not self._initialized:
            await self.initialize()

        logger.info("パターンデータベースの動的更新を開始")

        update_stats: dict[str, int | list[str]] = {
            "new_patterns_added": 0,
            "patterns_added": 0,
            "patterns_improved": 0,
            "patterns_analyzed": 0,
            "errors": [],
        }

        try:
            # 1. 新しいパターンを発見して追加
            failed_logs: list[str] = []  # 実際の実装では失敗ログを収集
            new_patterns = await self.discover_new_patterns(failed_logs)

            for pattern in new_patterns:
                if self.pattern_database.add_pattern(pattern):
                    update_stats["new_patterns_added"] += 1

            update_stats["patterns_added"] = update_stats["new_patterns_added"]

            # 2. 既存パターンの改善提案を取得
            improvements = await self.suggest_pattern_improvements()

            # 3. 高信頼度の改善を自動適用
            for improvement in improvements:
                if improvement.confidence >= 0.8:  # 高信頼度の改善のみ自動適用
                    if await self.apply_pattern_improvement(improvement):
                        update_stats["patterns_improved"] += 1

            # 4. パフォーマンス分析を実行
            performance_data = await self.analyze_pattern_performance()
            update_stats["patterns_analyzed"] = len(performance_data)

            # 5. パターンデータベースを保存
            await self.pattern_database.save_patterns()

            logger.info("パターンデータベースの動的更新完了: %s", update_stats)
            return update_stats

        except Exception as e:
            logger.error("パターンデータベース動的更新中にエラー: %s", e)
            update_stats["errors"].append(str(e))
            return update_stats

    async def process_unknown_error(
        self,
        unknown_error_info: dict[str, Any],
    ) -> dict[str, Any]:
        """未知エラー情報を処理して学習データに追加"""

        if not self._initialized:
            await self.initialize()

        normalized_info = self._normalize_unknown_error_payload(unknown_error_info)
        logger.info(
            "未知エラーを処理中: カテゴリ=%s",
            normalized_info.get("error_category"),
        )

        try:
            unknown_errors: list[dict[str, Any]] = []
            if self.unknown_errors_file.exists():
                try:
                    with self.unknown_errors_file.open(
                        "r",
                        encoding="utf-8",
                    ) as file_obj:
                        content = file_obj.read().strip()
                        if content:
                            stored_errors = json.loads(content)
                            unknown_errors = [
                                self._normalize_unknown_error_payload(error)
                                for error in stored_errors
                                if isinstance(error, dict)
                            ]
                except (json.JSONDecodeError, FileNotFoundError):
                    logger.warning("未知エラーファイルが破損しています。空のリストで初期化します。")

            similar_error = self._find_similar_unknown_error(
                normalized_info,
                unknown_errors,
            )

            if similar_error:
                similar_error["occurrence_count"] = similar_error.get("occurrence_count", 0) + 1
                similar_error["last_seen"] = datetime.now().isoformat()
                logger.info(
                    "既存の未知エラーを更新: %s",
                    similar_error.get("error_category"),
                )
            else:
                unknown_errors.append(normalized_info)
                logger.info(
                    "新しい未知エラーを追加: %s",
                    normalized_info.get("error_category"),
                )

            with self.unknown_errors_file.open(
                "w",
                encoding="utf-8",
            ) as file_obj:
                json.dump(
                    unknown_errors,
                    file_obj,
                    ensure_ascii=False,
                    indent=2,
                )

            frequent_errors = self._get_frequent_unknown_errors(unknown_errors)

            potential_patterns_created = 0
            for frequent_error in frequent_errors:
                occurrence_count = frequent_error.get("occurrence_count", 0)
                if occurrence_count >= self.min_pattern_occurrences:
                    created = await self._create_potential_pattern(frequent_error)
                    if created:
                        potential_patterns_created += 1

            return {
                "processed": True,
                "status": "processed",
                "error_category": normalized_info.get("error_category"),
                "is_new": similar_error is None,
                "occurrence_count": (
                    similar_error.get("occurrence_count")
                    if similar_error
                    else normalized_info.get("occurrence_count", 1)
                ),
                "potential_patterns_created": potential_patterns_created,
                "frequent_errors_count": len(frequent_errors),
            }

        except Exception as exc:
            logger.error("未知エラー処理中にエラー: %s", exc)
            return {
                "processed": False,
                "status": "error",
                "error": str(exc),
                "error_category": normalized_info.get("error_category"),
            }

    def _find_similar_unknown_error(
        self, unknown_error_info: dict[str, Any], existing_errors: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """類似の未知エラーを検索

        Args:
            unknown_error_info: 新しい未知エラー情報
            existing_errors: 既存の未知エラーリスト

        Returns:
            類似のエラー、見つからない場合はNone
        """
        new_category = unknown_error_info.get("error_category")
        new_keywords = set(unknown_error_info.get("error_features", {}).get("error_keywords", []))

        for existing_error in existing_errors:
            # カテゴリが同じかチェック
            if existing_error.get("error_category") != new_category:
                continue

            # キーワードの類似度をチェック
            existing_keywords = set(existing_error.get("error_features", {}).get("error_keywords", []))

            if existing_keywords and new_keywords:
                similarity = len(existing_keywords & new_keywords) / len(existing_keywords | new_keywords)
                if similarity > 0.7:  # 70%以上の類似度
                    return existing_error

        return None

    def _get_frequent_unknown_errors(
        self, unknown_errors: list[dict[str, Any]], min_occurrences: int | None = None
    ) -> list[dict[str, Any]]:
        """頻繁に発生する未知エラーを取得

        Args:
            unknown_errors: 未知エラーリスト
            min_occurrences: 最小発生回数

        Returns:
            頻繁な未知エラーのリスト
        """
        if min_occurrences is None:
            min_occurrences = self.min_pattern_occurrences

        frequent_errors = [error for error in unknown_errors if error.get("occurrence_count", 1) >= min_occurrences]

        # 発生回数でソート
        frequent_errors.sort(key=lambda x: x.get("occurrence_count", 1), reverse=True)
        return frequent_errors

    def _normalize_unknown_error_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """未知エラー情報のフォーマットを正規化"""

        normalized: dict[str, Any] = dict(payload) if payload is not None else {}

        normalized.setdefault("error_category", "unknown")
        normalized.setdefault("context", {})
        normalized.setdefault("error_features", {})

        if "occurrence_count" not in normalized:
            occurrences = normalized.pop("occurrences", None)
            if isinstance(occurrences, int):
                normalized["occurrence_count"] = max(1, occurrences)
            else:
                normalized["occurrence_count"] = 1

        timestamp = normalized.get("timestamp")
        if not timestamp:
            timestamp = datetime.now().isoformat()
        normalized["timestamp"] = timestamp
        normalized.setdefault("last_seen", timestamp)

        return normalized

    async def _create_potential_pattern(self, unknown_error_info: dict[str, Any]) -> bool:
        """未知エラーから潜在的なパターンを作成

        Args:
            unknown_error_info: 未知エラー情報

        Returns:
            作成成功の場合True
        """
        try:
            # 潜在的なパターン情報を取得
            potential_pattern_info = unknown_error_info.get("potential_pattern", {})

            if not potential_pattern_info:
                logger.warning("潜在的なパターン情報が見つかりません")
                return False

            # パターンオブジェクトを作成
            pattern = Pattern(
                id=potential_pattern_info["id"],
                name=potential_pattern_info["name"],
                category=potential_pattern_info["category"],
                regex_patterns=potential_pattern_info.get("regex_patterns", []),
                keywords=potential_pattern_info.get("keywords", []),
                context_requirements=[],
                confidence_base=potential_pattern_info.get("confidence_base", 0.6),
                success_rate=0.5,  # 初期成功率
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
                auto_generated=True,
                source="unknown_error_learning",
                occurrence_count=unknown_error_info.get("occurrence_count", 1),
            )

            # 潜在的なパターンファイルに保存
            potential_patterns = []
            if self.potential_patterns_file.exists():
                with self.potential_patterns_file.open("r", encoding="utf-8") as f:
                    potential_patterns = json.load(f)

            # 既存の潜在的なパターンと重複チェック
            existing_pattern = next((p for p in potential_patterns if p.get("id") == pattern.id), None)

            if existing_pattern:
                # 既存パターンの発生回数を更新
                existing_pattern["occurrence_count"] = unknown_error_info.get("occurrence_count", 1)
                existing_pattern["last_updated"] = datetime.now().isoformat()
                logger.info("既存の潜在的なパターンを更新: %s", pattern.id)
            else:
                # 新しい潜在的なパターンとして追加
                pattern_data = {
                    "id": pattern.id,
                    "name": pattern.name,
                    "category": pattern.category,
                    "regex_patterns": pattern.regex_patterns,
                    "keywords": pattern.keywords,
                    "confidence_base": pattern.confidence_base,
                    "success_rate": pattern.success_rate,
                    "created_at": pattern.created_at.isoformat(),
                    "auto_generated": True,
                    "source": "unknown_error_learning",
                    "occurrence_count": unknown_error_info.get("occurrence_count", 1),
                    "last_updated": datetime.now().isoformat(),
                }
                potential_patterns.append(pattern_data)
                logger.info("新しい潜在的なパターンを作成: %s", pattern.id)

            # ファイルに保存
            with self.potential_patterns_file.open("w", encoding="utf-8") as f:
                json.dump(potential_patterns, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error("潜在的なパターン作成中にエラー: %s", e)
            return False

    async def get_pattern_suggestions_from_unknown_errors(self) -> list[dict[str, Any]]:
        """未知エラーから新しいパターンの提案を取得

        Returns:
            パターン提案のリスト
        """
        if not self._initialized:
            await self.initialize()

        try:
            suggestions = []

            # 潜在的なパターンを読み込み
            if self.potential_patterns_file.exists():
                with self.potential_patterns_file.open("r", encoding="utf-8") as f:
                    potential_patterns = json.load(f)

                # 発生回数が閾値を超えるパターンを提案
                for pattern_data in potential_patterns:
                    occurrence_count = pattern_data.get("occurrence_count", 0)
                    if occurrence_count >= self.min_pattern_occurrences:
                        suggestion = {
                            "pattern_id": pattern_data["id"],
                            "pattern_name": pattern_data["name"],
                            "category": pattern_data["category"],
                            "occurrence_count": occurrence_count,
                            "confidence": min(0.8, 0.5 + (occurrence_count * 0.1)),
                            "keywords": pattern_data.get("keywords", []),
                            "regex_patterns": pattern_data.get("regex_patterns", []),
                            "recommendation": "このパターンを正式なパターンデータベースに追加することを推奨します",
                            "auto_generated": True,
                        }
                        suggestions.append(suggestion)

            # 発生回数でソート
            suggestions.sort(key=lambda x: x["occurrence_count"], reverse=True)

            logger.info("未知エラーから %d 個のパターン提案を生成", len(suggestions))
            return suggestions

        except Exception as e:
            logger.error("パターン提案生成中にエラー: %s", e)
            return []

    async def promote_potential_pattern_to_official(self, pattern_id: str) -> bool:
        """潜在的なパターンを正式なパターンデータベースに昇格

        Args:
            pattern_id: パターンID

        Returns:
            昇格成功の場合True
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 潜在的なパターンを検索
            if not self.potential_patterns_file.exists():
                logger.warning("潜在的なパターンファイルが存在しません")
                return False

            with self.potential_patterns_file.open("r", encoding="utf-8") as f:
                potential_patterns = json.load(f)

            pattern_data = next((p for p in potential_patterns if p["id"] == pattern_id), None)
            if not pattern_data:
                logger.warning("潜在的なパターンが見つかりません: %s", pattern_id)
                return False

            # 正式なパターンオブジェクトを作成
            pattern = Pattern(
                id=pattern_data["id"],
                name=pattern_data["name"],
                category=pattern_data["category"],
                regex_patterns=pattern_data.get("regex_patterns", []),
                keywords=pattern_data.get("keywords", []),
                context_requirements=[],
                confidence_base=pattern_data.get("confidence_base", 0.7),
                success_rate=pattern_data.get("success_rate", 0.6),
                created_at=datetime.fromisoformat(pattern_data["created_at"]),
                updated_at=datetime.now(),
                user_defined=False,
                auto_generated=True,
                source="promoted_from_unknown_error",
            )

            # パターンデータベースに追加
            success = self.pattern_database.add_pattern(pattern)
            if success:
                # パターンデータベースを保存
                await self.pattern_database.save_patterns()

                # 潜在的なパターンリストから削除
                potential_patterns = [p for p in potential_patterns if p["id"] != pattern_id]
                with self.potential_patterns_file.open("w", encoding="utf-8") as f:
                    json.dump(potential_patterns, f, ensure_ascii=False, indent=2)

                logger.info("潜在的なパターンを正式パターンに昇格: %s", pattern_id)
                return True
            else:
                logger.error("パターンデータベースへの追加に失敗: %s", pattern_id)
                return False

        except Exception as e:
            logger.error("パターン昇格中にエラー: %s", e)
            return False

    def get_unknown_error_statistics(self) -> dict[str, Any]:
        """未知エラーの統計情報を取得

        Returns:
            統計情報
        """
        try:
            stats = {
                "total_unknown_errors": 0,
                "frequent_unknown_errors": 0,
                "potential_patterns": 0,
                "categories": {},
                "top_categories": [],
            }

            # 未知エラー統計
            if self.unknown_errors_file.exists():
                try:
                    with self.unknown_errors_file.open("r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            unknown_errors = json.loads(content)
                        else:
                            unknown_errors = []
                except (json.JSONDecodeError, FileNotFoundError):
                    logger.warning("未知エラーファイルが破損しています。統計をスキップします。")
                    unknown_errors = []

                stats["total_unknown_errors"] = len(unknown_errors)

                # カテゴリ別統計
                category_counts = Counter()
                for error in unknown_errors:
                    category = error.get("error_category", "unknown")
                    occurrence_count = error.get("occurrence_count", 1)
                    category_counts[category] += occurrence_count

                stats["categories"] = dict(category_counts)
                stats["top_categories"] = category_counts.most_common(5)

                # 頻繁なエラー数
                frequent_errors = self._get_frequent_unknown_errors(unknown_errors)
                stats["frequent_unknown_errors"] = len(frequent_errors)

            # 潜在的なパターン統計
            if self.potential_patterns_file.exists():
                with self.potential_patterns_file.open("r", encoding="utf-8") as f:
                    potential_patterns = json.load(f)
                stats["potential_patterns"] = len(potential_patterns)

            return stats

        except Exception as e:
            logger.error("未知エラー統計取得中にエラー: %s", e)
            return {"error": str(e)}

    async def cleanup_old_unknown_errors(self, max_age_days: int = 30) -> int:
        """古い未知エラーデータをクリーンアップ

        Args:
            max_age_days: 保持する最大日数

        Returns:
            削除されたエラー数
        """
        try:
            if not self.unknown_errors_file.exists():
                return 0

            try:
                with self.unknown_errors_file.open("r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        unknown_errors = cast(list[dict[str, Any]], json.loads(content))
                    else:
                        unknown_errors = []
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("未知エラーファイルが破損しています。クリーンアップをスキップします。")
                return 0

            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            # 古いエラーを除外
            filtered_errors: list[dict[str, Any]] = []
            deleted_count = 0

            for error in unknown_errors:
                last_seen_str = error.get("last_seen") or error.get("timestamp")
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                        if last_seen >= cutoff_date:
                            filtered_errors.append(error)
                        else:
                            deleted_count += 1
                    except ValueError:
                        # 日付解析に失敗した場合は保持
                        filtered_errors.append(error)
                else:
                    # タイムスタンプがない場合は保持
                    filtered_errors.append(error)

            # ファイルを更新
            if deleted_count > 0:
                with self.unknown_errors_file.open("w", encoding="utf-8") as f:
                    json.dump(filtered_errors, f, ensure_ascii=False, indent=2)

            logger.info("古い未知エラーを %d 個削除しました", deleted_count)
            return deleted_count

        except Exception as e:
            logger.error("未知エラークリーンアップ中にエラー: %s", e)
            return 0
