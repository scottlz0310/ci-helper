"""対話的AIセッション管理

AI分析との対話的なデバッグセッションを管理し、会話履歴の保持、
コンテキストの維持、セッション状態の管理を行います。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from .exceptions import AIError
from .models import AnalyzeOptions, InteractiveSession
from .prompts import PromptManager

logger = logging.getLogger(__name__)


class InteractiveSessionManager:
    """対話セッション管理クラス

    AI分析との対話的なセッションを管理し、会話履歴の保持、
    コンテキストの維持、セッション状態の管理を行います。
    """

    def __init__(self, prompt_manager: PromptManager, session_timeout: int = 300):
        """対話セッション管理を初期化

        Args:
            prompt_manager: プロンプト管理インスタンス
            session_timeout: セッションタイムアウト時間（秒）

        """
        self.prompt_manager = prompt_manager
        self.session_timeout = session_timeout
        self.active_sessions: dict[str, InteractiveSession] = {}
        self.active_sessions: dict[str, InteractiveSession] = {}
        self.session_contexts: dict[str, dict[str, Any]] = {}
        self.command_processor: Any = None

    async def process_input(self, session_id: str, user_input: str, options: AnalyzeOptions | None = None) -> str:
        """ユーザー入力を処理

        Args:
            session_id: セッションID
            user_input: ユーザー入力
            options: 分析オプション

        Returns:
            処理結果

        """
        if self.command_processor:
            return await self.command_processor.process_command(session_id, user_input)
        return ""

    def create_session(
        self,
        provider: str,
        model: str,
        initial_context: str = "",
        options: AnalyzeOptions | None = None,
    ) -> InteractiveSession:
        """新しい対話セッションを作成

        Args:
            provider: AIプロバイダー名
            model: 使用するモデル名
            initial_context: 初期コンテキスト（ログ内容など）
            options: 分析オプション

        Returns:
            作成された対話セッション

        """
        session_id = str(uuid.uuid4())

        session = InteractiveSession(
            session_id=session_id,
            start_time=datetime.now(),
            last_activity=datetime.now(),
            provider=provider,
            model=model,
        )

        # セッションコンテキストを初期化
        self.session_contexts[session_id] = {
            "initial_context": initial_context,
            "options": options,
            "current_topic": None,
            "analysis_results": [],
            "user_preferences": {},
        }

        # セッションを登録
        self.active_sessions[session_id] = session

        # 初期メッセージを追加
        if initial_context:
            session.add_message(
                role="system",
                content=f"セッション開始。初期コンテキスト: {initial_context[:100]}...",
                tokens=0,
                cost=0.0,
            )

        logger.info("新しい対話セッションを作成: %s", session_id)
        return session

    def get_session(self, session_id: str) -> InteractiveSession | None:
        """セッションを取得

        Args:
            session_id: セッションID

        Returns:
            セッション（存在しない場合はNone）

        """
        return self.active_sessions.get(session_id)

    def update_session_activity(self, session_id: str) -> None:
        """セッションの最終活動時刻を更新

        Args:
            session_id: セッションID

        """
        if session_id in self.active_sessions:
            self.active_sessions[session_id].last_activity = datetime.now()

    def add_message_to_session(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> bool:
        """セッションにメッセージを追加

        Args:
            session_id: セッションID
            role: メッセージの役割（user, assistant, system）
            content: メッセージ内容
            tokens: 使用トークン数
            cost: コスト

        Returns:
            成功した場合True

        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.add_message(role, content, tokens, cost)
        self.update_session_activity(session_id)

        logger.debug("セッション %s にメッセージを追加: %s", session_id, role)
        return True

    def get_conversation_context(self, session_id: str, max_messages: int = 10) -> str:
        """会話コンテキストを取得

        Args:
            session_id: セッションID
            max_messages: 含める最大メッセージ数

        Returns:
            フォーマットされた会話履歴

        """
        session = self.get_session(session_id)
        if not session:
            return ""

        # 最新のメッセージを取得
        recent_messages = session.conversation_history[-max_messages:]

        context_lines = []
        for msg in recent_messages:
            role = msg["role"]
            content = msg["content"]
            timestamp = msg["timestamp"].strftime("%H:%M:%S")

            if role == "user":
                context_lines.append(f"[{timestamp}] ユーザー: {content}")
            elif role == "assistant":
                context_lines.append(f"[{timestamp}] AI: {content}")
            elif role == "system":
                context_lines.append(f"[{timestamp}] システム: {content}")

        return "\n".join(context_lines)

    def get_session_context(self, session_id: str) -> dict[str, Any]:
        """セッションコンテキストを取得

        Args:
            session_id: セッションID

        Returns:
            セッションコンテキスト

        """
        return self.session_contexts.get(session_id, {})

    def update_session_context(self, session_id: str, key: str, value: Any) -> bool:
        """セッションコンテキストを更新

        Args:
            session_id: セッションID
            key: コンテキストキー
            value: 設定する値

        Returns:
            成功した場合True

        """
        if session_id not in self.session_contexts:
            return False

        self.session_contexts[session_id][key] = value
        self.update_session_activity(session_id)

        logger.debug("セッション %s のコンテキストを更新: %s", session_id, key)
        return True

    def generate_interactive_prompt(self, session_id: str, user_input: str) -> str:
        """対話用プロンプトを生成

        Args:
            session_id: セッションID
            user_input: ユーザー入力

        Returns:
            生成されたプロンプト

        """
        session = self.get_session(session_id)
        if not session:
            raise AIError(f"セッション {session_id} が見つかりません")

        # 会話履歴を取得
        conversation_history = self.get_conversation_context(session_id)

        # セッションコンテキストを取得
        context = self.get_session_context(session_id)
        initial_context = context.get("initial_context", "")

        # 現在のコンテキストを構築
        current_context = f"""
初期コンテキスト: {initial_context}

現在の会話:
{conversation_history}

ユーザーの新しい入力: {user_input}
"""

        # プロンプトマネージャーを使用してプロンプトを生成
        return self.prompt_manager.get_interactive_prompt(
            conversation_history=[conversation_history],
            context=current_context,
        )

    def close_session(self, session_id: str) -> bool:
        """セッションを終了

        Args:
            session_id: セッションID

        Returns:
            成功した場合True

        """
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        session.is_active = False

        # セッション終了メッセージを追加
        session.add_message(
            role="system",
            content=f"セッション終了。継続時間: {session.duration_minutes:.1f}分",
            tokens=0,
            cost=0.0,
        )

        # セッションを削除
        del self.active_sessions[session_id]
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]

        logger.info("セッション %s を終了しました", session_id)
        return True

    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションをクリーンアップ

        Returns:
            削除されたセッション数

        """
        current_time = datetime.now()
        expired_sessions = []

        for session_id, session in self.active_sessions.items():
            time_since_activity = current_time - session.last_activity
            if time_since_activity > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)

        # 期限切れセッションを削除
        for session_id in expired_sessions:
            self.close_session(session_id)

        if expired_sessions:
            logger.info("期限切れセッション %d 個を削除しました", len(expired_sessions))

        return len(expired_sessions)

    def get_active_sessions(self) -> list[InteractiveSession]:
        """アクティブなセッション一覧を取得

        Returns:
            アクティブなセッションのリスト

        """
        return list(self.active_sessions.values())

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """セッション統計を取得

        Args:
            session_id: セッションID

        Returns:
            セッション統計情報

        """
        session = self.get_session(session_id)
        if not session:
            return {}

        return {
            "session_id": session_id,
            "duration_minutes": session.duration_minutes,
            "message_count": session.message_count,
            "total_tokens": session.total_tokens_used,
            "total_cost": session.total_cost,
            "provider": session.provider,
            "model": session.model,
            "is_active": session.is_active,
            "start_time": session.start_time.isoformat(),
            "last_activity": session.last_activity.isoformat(),
        }

    async def auto_cleanup_task(self) -> None:
        """自動クリーンアップタスク（バックグラウンド実行用）"""
        while True:
            try:
                self.cleanup_expired_sessions()
                await asyncio.sleep(60)  # 1分ごとにチェック
            except Exception as e:
                logger.error("自動クリーンアップでエラー: %s", e)
                await asyncio.sleep(60)

    def __len__(self) -> int:
        """アクティブセッション数を取得"""
        return len(self.active_sessions)

    def __contains__(self, session_id: str) -> bool:
        """セッションが存在するかチェック"""
        return session_id in self.active_sessions
