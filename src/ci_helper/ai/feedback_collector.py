"""
ユーザーフィードバック収集システム

修正提案に対するユーザーフィードバックの収集と処理を行います。
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import FixSuggestion, PatternMatch, UserFeedback

logger = logging.getLogger(__name__)


class FeedbackCollector:
    """ユーザーフィードバック収集クラス

    修正提案に対するユーザーフィードバックの収集と構造化を行います。
    """

    def __init__(
        self,
        feedback_dir: Path | str = "data/learning",
        auto_save: bool = True,
    ):
        """フィードバック収集システムを初期化

        Args:
            feedback_dir: フィードバックデータディレクトリ
            auto_save: 自動保存フラグ
        """
        self.feedback_dir = Path(feedback_dir)
        self.auto_save = auto_save

        # フィードバックファイルのパス
        self.feedback_file = self.feedback_dir / "user_feedback.json"
        self.feedback_sessions_file = self.feedback_dir / "feedback_sessions.json"

        # フィードバックデータ
        self.feedback_history: list[UserFeedback] = []
        self.feedback_sessions: dict[str, dict[str, Any]] = {}
        self.pending_feedback: dict[str, dict[str, Any]] = {}

        self._initialized = False

    async def initialize(self) -> None:
        """フィードバック収集システムを初期化"""
        if self._initialized:
            return

        logger.info("フィードバック収集システムを初期化中...")

        # フィードバックディレクトリを作成
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        # 既存のフィードバックデータを読み込み
        await self._load_feedback_data()

        self._initialized = True
        logger.info("フィードバック収集システムの初期化完了")

    async def _load_feedback_data(self) -> None:
        """既存のフィードバックデータを読み込み"""
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

            # フィードバックセッションを読み込み
            if self.feedback_sessions_file.exists():
                with open(self.feedback_sessions_file, encoding="utf-8") as f:
                    self.feedback_sessions = json.load(f)
                logger.info("フィードバックセッションを %d 件読み込みました", len(self.feedback_sessions))

        except Exception as e:
            logger.error("フィードバックデータの読み込み中にエラー: %s", e)

    async def collect_feedback_for_suggestion(
        self,
        pattern_match: PatternMatch,
        fix_suggestion: FixSuggestion,
        interactive: bool = True,
        feedback_callback: Callable[[str], str] | None = None,
    ) -> UserFeedback | None:
        """修正提案に対するフィードバックを収集

        Args:
            pattern_match: パターンマッチ結果
            fix_suggestion: 修正提案
            interactive: 対話的フィードバック収集フラグ
            feedback_callback: フィードバック収集用コールバック関数

        Returns:
            収集されたフィードバック、キャンセルされた場合はNone
        """
        if not self._initialized:
            await self.initialize()

        logger.info("フィードバック収集開始: パターン=%s", pattern_match.pattern.id)

        try:
            # フィードバックセッションを開始
            session_id = str(uuid.uuid4())
            session_data = {
                "session_id": session_id,
                "pattern_id": pattern_match.pattern.id,
                "fix_suggestion_id": getattr(fix_suggestion, "id", str(uuid.uuid4())),
                "started_at": datetime.now().isoformat(),
                "pattern_confidence": pattern_match.confidence,
                "fix_confidence": fix_suggestion.confidence,
            }

            self.feedback_sessions[session_id] = session_data

            if interactive and feedback_callback:
                # 対話的フィードバック収集
                feedback = await self._collect_interactive_feedback(
                    pattern_match, fix_suggestion, session_id, feedback_callback
                )
            else:
                # 非対話的フィードバック収集（デフォルト値）
                feedback = await self._collect_default_feedback(pattern_match, fix_suggestion, session_id)

            if feedback:
                # フィードバック履歴に追加
                self.feedback_history.append(feedback)

                # セッションを完了
                session_data["completed_at"] = datetime.now().isoformat()
                session_data["feedback_provided"] = True

                # 自動保存
                if self.auto_save:
                    await self._save_feedback_data()

                logger.info("フィードバック収集完了: 評価=%d, 成功=%s", feedback.rating, feedback.success)

            return feedback

        except Exception as e:
            logger.error("フィードバック収集中にエラー: %s", e)
            return None

    async def _collect_interactive_feedback(
        self,
        pattern_match: PatternMatch,
        fix_suggestion: FixSuggestion,
        session_id: str,
        feedback_callback: Callable[[str], str],
    ) -> UserFeedback | None:
        """対話的フィードバック収集

        Args:
            pattern_match: パターンマッチ結果
            fix_suggestion: 修正提案
            session_id: セッションID
            feedback_callback: フィードバック収集用コールバック関数

        Returns:
            収集されたフィードバック
        """
        try:
            # フィードバック収集用のプロンプトを作成
            prompt = self._create_feedback_prompt(pattern_match, fix_suggestion)

            # ユーザーからフィードバックを収集
            response = feedback_callback(prompt)

            if not response or response.lower() in ["skip", "cancel", "キャンセル"]:
                logger.info("フィードバック収集がキャンセルされました")
                return None

            # レスポンスを解析
            feedback_data = self._parse_feedback_response(response)

            # UserFeedbackオブジェクトを作成
            feedback = UserFeedback(
                pattern_id=pattern_match.pattern.id,
                fix_suggestion_id=getattr(fix_suggestion, "id", str(uuid.uuid4())),
                rating=feedback_data["rating"],
                success=feedback_data["success"],
                comments=feedback_data["comments"],
                timestamp=datetime.now(),
            )

            return feedback

        except Exception as e:
            logger.error("対話的フィードバック収集中にエラー: %s", e)
            return None

    async def _collect_default_feedback(
        self,
        pattern_match: PatternMatch,
        fix_suggestion: FixSuggestion,
        session_id: str,
    ) -> UserFeedback:
        """デフォルトフィードバック収集

        Args:
            pattern_match: パターンマッチ結果
            fix_suggestion: 修正提案
            session_id: セッションID

        Returns:
            デフォルトフィードバック
        """
        # 信頼度に基づいてデフォルト評価を設定
        avg_confidence = (pattern_match.confidence + fix_suggestion.confidence) / 2

        if avg_confidence >= 0.8:
            rating = 4
            success = True
        elif avg_confidence >= 0.6:
            rating = 3
            success = True
        else:
            rating = 2
            success = False

        feedback = UserFeedback(
            pattern_id=pattern_match.pattern.id,
            fix_suggestion_id=getattr(fix_suggestion, "id", str(uuid.uuid4())),
            rating=rating,
            success=success,
            comments="自動生成されたデフォルトフィードバック",
            timestamp=datetime.now(),
        )

        logger.info("デフォルトフィードバックを生成: 評価=%d", rating)
        return feedback

    def _create_feedback_prompt(self, pattern_match: PatternMatch, fix_suggestion: FixSuggestion) -> str:
        """フィードバック収集用プロンプトを作成

        Args:
            pattern_match: パターンマッチ結果
            fix_suggestion: 修正提案

        Returns:
            フィードバック収集用プロンプト
        """
        prompt = f"""
修正提案に対するフィードバックをお聞かせください。

【検出されたパターン】
- パターン名: {pattern_match.pattern.name}
- カテゴリ: {pattern_match.pattern.category}
- 信頼度: {pattern_match.confidence:.1%}

【修正提案】
- タイトル: {fix_suggestion.title}
- 説明: {fix_suggestion.description}
- 信頼度: {fix_suggestion.confidence:.1%}

以下の形式でフィードバックを入力してください：

評価: [1-5] (1=非常に悪い, 2=悪い, 3=普通, 4=良い, 5=非常に良い)
成功: [yes/no] (修正提案が問題を解決したかどうか)
コメント: [任意のコメント]

例:
評価: 4
成功: yes
コメント: 提案された修正で問題が解決しました

入力してください (skipでスキップ):
"""
        return prompt.strip()

    def _parse_feedback_response(self, response: str) -> dict[str, Any]:
        """フィードバックレスポンスを解析

        Args:
            response: ユーザーレスポンス

        Returns:
            解析されたフィードバックデータ
        """
        feedback_data = {
            "rating": 3,  # デフォルト
            "success": True,  # デフォルト
            "comments": "",
        }

        try:
            lines = response.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("評価:") or line.startswith("rating:"):
                    rating_str = line.split(":", 1)[1].strip()
                    try:
                        rating = int(rating_str)
                        if 1 <= rating <= 5:
                            feedback_data["rating"] = rating
                    except ValueError:
                        pass

                elif line.startswith("成功:") or line.startswith("success:"):
                    success_str = line.split(":", 1)[1].strip().lower()
                    feedback_data["success"] = success_str in ["yes", "true", "1", "はい", "成功"]

                elif line.startswith("コメント:") or line.startswith("comment:"):
                    comment = line.split(":", 1)[1].strip()
                    feedback_data["comments"] = comment

            # コメントが設定されていない場合、全体をコメントとして扱う
            if not feedback_data["comments"] and response.strip():
                # 構造化されていないレスポンスの場合
                if "評価:" not in response and "成功:" not in response:
                    feedback_data["comments"] = response.strip()

        except Exception as e:
            logger.warning("フィードバックレスポンスの解析に失敗: %s", e)
            feedback_data["comments"] = response.strip()

        return feedback_data

    async def collect_batch_feedback(
        self,
        pattern_matches: list[PatternMatch],
        fix_suggestions: list[FixSuggestion],
        feedback_callback: Callable[[str], str] | None = None,
    ) -> list[UserFeedback]:
        """複数の修正提案に対するバッチフィードバック収集

        Args:
            pattern_matches: パターンマッチ結果のリスト
            fix_suggestions: 修正提案のリスト
            feedback_callback: フィードバック収集用コールバック関数

        Returns:
            収集されたフィードバックのリスト
        """
        if not self._initialized:
            await self.initialize()

        logger.info("バッチフィードバック収集開始: %d 件の提案", len(fix_suggestions))

        collected_feedback = []

        try:
            for i, (pattern_match, fix_suggestion) in enumerate(zip(pattern_matches, fix_suggestions, strict=False)):
                logger.info("フィードバック収集 %d/%d", i + 1, len(fix_suggestions))

                feedback = await self.collect_feedback_for_suggestion(
                    pattern_match,
                    fix_suggestion,
                    interactive=bool(feedback_callback),
                    feedback_callback=feedback_callback,
                )

                if feedback:
                    collected_feedback.append(feedback)

            logger.info("バッチフィードバック収集完了: %d 件のフィードバックを収集", len(collected_feedback))
            return collected_feedback

        except Exception as e:
            logger.error("バッチフィードバック収集中にエラー: %s", e)
            return collected_feedback

    async def record_fix_application_result(
        self,
        pattern_id: str,
        fix_suggestion_id: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """修正適用結果を記録

        Args:
            pattern_id: パターンID
            fix_suggestion_id: 修正提案ID
            success: 適用成功フラグ
            error_message: エラーメッセージ（失敗時）
        """
        if not self._initialized:
            await self.initialize()

        # 自動フィードバックを作成
        rating = 4 if success else 2
        comments = "修正適用成功" if success else f"修正適用失敗: {error_message}"

        feedback = UserFeedback(
            pattern_id=pattern_id,
            fix_suggestion_id=fix_suggestion_id,
            rating=rating,
            success=success,
            comments=comments,
            timestamp=datetime.now(),
        )

        self.feedback_history.append(feedback)

        # 自動保存
        if self.auto_save:
            await self._save_feedback_data()

        logger.info("修正適用結果を記録: パターン=%s, 成功=%s", pattern_id, success)

    def get_feedback_for_pattern(self, pattern_id: str) -> list[UserFeedback]:
        """指定されたパターンのフィードバックを取得

        Args:
            pattern_id: パターンID

        Returns:
            フィードバックのリスト
        """
        return [fb for fb in self.feedback_history if fb.pattern_id == pattern_id]

    def get_feedback_statistics(self, pattern_id: str | None = None) -> dict[str, Any]:
        """フィードバック統計を取得

        Args:
            pattern_id: パターンID（指定時はそのパターンの統計のみ）

        Returns:
            フィードバック統計情報
        """
        if pattern_id:
            feedback_list = self.get_feedback_for_pattern(pattern_id)
        else:
            feedback_list = self.feedback_history

        if not feedback_list:
            return {
                "total_feedback": 0,
                "average_rating": 0.0,
                "success_rate": 0.0,
                "rating_distribution": {},
            }

        total_feedback = len(feedback_list)
        successful_feedback = sum(1 for fb in feedback_list if fb.success)
        total_rating = sum(fb.rating for fb in feedback_list)

        # 評価分布
        rating_distribution = {}
        for rating in range(1, 6):
            count = sum(1 for fb in feedback_list if fb.rating == rating)
            rating_distribution[str(rating)] = count

        return {
            "total_feedback": total_feedback,
            "average_rating": total_rating / total_feedback,
            "success_rate": successful_feedback / total_feedback,
            "rating_distribution": rating_distribution,
            "successful_feedback": successful_feedback,
            "failed_feedback": total_feedback - successful_feedback,
        }

    async def export_feedback_data(self, export_path: Path | str) -> bool:
        """フィードバックデータをエクスポート

        Args:
            export_path: エクスポート先パス

        Returns:
            エクスポート成功フラグ
        """
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_feedback": len(self.feedback_history),
                "feedback_history": [
                    {
                        "pattern_id": fb.pattern_id,
                        "fix_suggestion_id": fb.fix_suggestion_id,
                        "rating": fb.rating,
                        "success": fb.success,
                        "comments": fb.comments,
                        "timestamp": fb.timestamp.isoformat(),
                    }
                    for fb in self.feedback_history
                ],
                "feedback_sessions": self.feedback_sessions,
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info("フィードバックデータをエクスポートしました: %s", export_path)
            return True

        except Exception as e:
            logger.error("フィードバックデータのエクスポートに失敗: %s", e)
            return False

    async def _save_feedback_data(self) -> None:
        """フィードバックデータを保存"""
        try:
            # フィードバック履歴を保存
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

            # フィードバックセッションを保存
            with open(self.feedback_sessions_file, "w", encoding="utf-8") as f:
                json.dump(self.feedback_sessions, f, ensure_ascii=False, indent=2)

            logger.debug("フィードバックデータを保存しました")

        except Exception as e:
            logger.error("フィードバックデータの保存に失敗: %s", e)

    async def cleanup(self) -> None:
        """フィードバック収集システムのクリーンアップ"""
        if not self._initialized:
            return

        logger.info("フィードバック収集システムをクリーンアップ中...")

        # フィードバックデータを保存
        await self._save_feedback_data()

        logger.info("フィードバック収集システムのクリーンアップ完了")
