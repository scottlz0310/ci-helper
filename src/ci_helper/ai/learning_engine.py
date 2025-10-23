"""
学習エンジン

新しいエラーパターンの自動学習とユーザーフィードバックの処理を行います。
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Pattern, PatternMatch, UserFeedback
from .pattern_database import PatternDatabase

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

        # 学習データ
        self.feedback_history: list[UserFeedback] = []
        self.learned_patterns: dict[str, dict[str, Any]] = {}
        self.error_frequency: dict[str, int] = defaultdict(int)
        self.pattern_success_tracking: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"successes": 0, "failures": 0, "total_uses": 0}
        )

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
        if pattern:
            # 指数移動平均で成功率を更新
            alpha = 0.2  # 学習率
            new_success_rate = alpha * (1.0 if feedback.success else 0.0) + (1 - alpha) * pattern.success_rate
            pattern.success_rate = max(0.1, min(1.0, new_success_rate))
            pattern.updated_at = datetime.now()

            self.pattern_database.update_pattern(pattern)
            logger.info("パターン %s の成功率を %.3f に更新", pattern_id, pattern.success_rate)

    async def _adjust_pattern_confidence(self, feedback: UserFeedback) -> None:
        """フィードバックに基づいてパターンの信頼度を調整

        Args:
            feedback: ユーザーフィードバック
        """
        pattern = self.pattern_database.get_pattern(feedback.pattern_id)
        if not pattern:
            return

        # 評価に基づく調整
        rating_adjustment = (feedback.rating - 3) * self.confidence_adjustment_factor / 2  # -1.0 to 1.0

        # 成功/失敗に基づく調整
        success_adjustment = (
            self.confidence_adjustment_factor if feedback.success else -self.confidence_adjustment_factor
        )

        # 総合調整
        total_adjustment = (rating_adjustment + success_adjustment) / 2

        # 信頼度を更新
        new_confidence = pattern.confidence_base + total_adjustment
        pattern.confidence_base = max(0.1, min(1.0, new_confidence))
        pattern.updated_at = datetime.now()

        self.pattern_database.update_pattern(pattern)
        logger.info("パターン %s の信頼度を %.3f に調整", feedback.pattern_id, pattern.confidence_base)

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

        discovered_patterns = []

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
        error_messages = []

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
        normalized = re.sub(r"[A-Za-z]:\\[^\s]+", "C:\\path\\to\\file", normalized)

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
        pattern = pattern.replace(r"C:\\path\\to\\file", r"[A-Za-z]:\\[^\s]+")  # Windowsパス
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
        if pattern:
            # 成功率に基づいて信頼度を調整
            success_rate = tracking["success_rate"]
            adjustment = (success_rate - 0.5) * self.confidence_adjustment_factor

            new_confidence = pattern.confidence_base + adjustment
            pattern.confidence_base = max(0.1, min(1.0, new_confidence))
            pattern.updated_at = datetime.now()

            self.pattern_database.update_pattern(pattern)
            logger.info("パターン %s の信頼度を更新: %.3f", pattern_id, pattern.confidence_base)

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

    def get_learning_statistics(self) -> dict[str, Any]:
        """学習統計情報を取得

        Returns:
            学習統計情報の辞書
        """
        if not self._initialized:
            return {"error": "学習エンジンが初期化されていません"}

        # フィードバック統計
        total_feedback = len(self.feedback_history)
        successful_feedback = sum(1 for fb in self.feedback_history if fb.success)

        # 最近のフィードバック（過去30日）
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_feedback = [fb for fb in self.feedback_history if fb.timestamp >= recent_cutoff]

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
        fix_suggestions: list[Any],
        interactive: bool = True,
        feedback_callback: Callable[[str], str] | None = None,
    ) -> list[UserFeedback]:
        """フィードバックを収集して学習に反映

        Args:
            pattern_matches: パターンマッチ結果のリスト
            fix_suggestions: 修正提案のリスト
            interactive: 対話的フィードバック収集フラグ
            feedback_callback: フィードバック収集用コールバック関数

        Returns:
            収集されたフィードバックのリスト
        """
        if not self._initialized:
            await self.initialize()

        await self._ensure_feedback_collector_initialized()
        logger.info("フィードバック収集と学習処理を開始")

        collected_feedback = []

        try:
            # フィードバックを収集
            for pattern_match, fix_suggestion in zip(pattern_matches, fix_suggestions, strict=False):
                feedback = await self.feedback_collector.collect_feedback_for_suggestion(
                    pattern_match, fix_suggestion, interactive, feedback_callback
                )

                if feedback:
                    collected_feedback.append(feedback)
                    # 即座に学習に反映
                    await self.learn_from_feedback(feedback)

            logger.info("フィードバック収集と学習処理完了: %d 件処理", len(collected_feedback))
            return collected_feedback

        except Exception as e:
            logger.error("フィードバック収集と学習処理中にエラー: %s", e)
            return collected_feedback

    async def process_fix_application_feedback(
        self,
        pattern_id: str,
        fix_suggestion_id: str,
        success: bool,
        error_message: str | None = None,
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

        # フィードバック収集システムに結果を記録
        await self.feedback_collector.record_fix_application_result(
            pattern_id, fix_suggestion_id, success, error_message
        )

        # 学習エンジンでパターン信頼度を更新
        await self.update_pattern_confidence(pattern_id, success)

        logger.info("修正適用フィードバックを処理: パターン=%s, 成功=%s", pattern_id, success)

    def get_pattern_feedback_summary(self, pattern_id: str) -> dict[str, Any]:
        """指定されたパターンのフィードバック要約を取得

        Args:
            pattern_id: パターンID

        Returns:
            フィードバック要約情報
        """
        if not self._initialized:
            return {"error": "学習エンジンが初期化されていません"}

        if self.feedback_collector is None:
            return {"error": "フィードバック収集システムが初期化されていません"}

        # フィードバック収集システムから統計を取得
        feedback_stats = self.feedback_collector.get_feedback_statistics(pattern_id)

        # 学習エンジンの追跡データを取得
        tracking = self.pattern_success_tracking.get(pattern_id, {})

        return {
            "pattern_id": pattern_id,
            "feedback_statistics": feedback_stats,
            "success_tracking": tracking,
            "total_feedback": feedback_stats.get("total_feedback", 0),
            "success_rate": feedback_stats.get("success_rate", 0.0),
            "average_rating": feedback_stats.get("average_rating", 0.0),
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
        logger.info("パターン改善提案を開始")

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # パターン改善システムで改善提案を生成
            improvements = await self.pattern_improvement.suggest_pattern_improvements(all_feedback)

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

    async def get_improvement_recommendations(self, max_recommendations: int = 10) -> list[Any]:
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

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # 改善推奨事項を取得
            recommendations = await self.pattern_improvement.get_improvement_recommendations(
                all_feedback, max_recommendations
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

        try:
            # フィードバック履歴を取得
            all_feedback = self.feedback_collector.feedback_history

            # パフォーマンス分析を実行
            performance_data = await self.pattern_improvement.analyze_pattern_performance(all_feedback)

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

        update_stats = {
            "new_patterns_added": 0,
            "patterns_improved": 0,
            "patterns_analyzed": 0,
            "errors": [],
        }

        try:
            # 1. 新しいパターンを発見して追加
            failed_logs = []  # 実際の実装では失敗ログを収集
            new_patterns = await self.discover_new_patterns(failed_logs)

            for pattern in new_patterns:
                if self.pattern_database.add_pattern(pattern):
                    update_stats["new_patterns_added"] += 1

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
