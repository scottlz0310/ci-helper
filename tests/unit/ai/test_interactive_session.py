"""
対話セッション管理のテスト

InteractiveSessionManagerクラスの機能をテストします。
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ci_helper.ai.exceptions import AIError
from ci_helper.ai.interactive_session import InteractiveSessionManager
from ci_helper.ai.models import AnalyzeOptions, InteractiveSession
from ci_helper.ai.prompts import PromptManager


class TestInteractiveSessionManager:
    """InteractiveSessionManagerのテストクラス"""

    @pytest.fixture
    def prompt_manager(self):
        """プロンプトマネージャーのモック"""
        mock_manager = Mock(spec=PromptManager)
        mock_manager.get_interactive_prompt.return_value = "テスト用プロンプト"
        return mock_manager

    @pytest.fixture
    def session_manager(self, prompt_manager):
        """セッション管理インスタンス"""
        return InteractiveSessionManager(prompt_manager, session_timeout=300)

    def test_create_session(self, session_manager):
        """セッション作成のテスト"""
        # セッションを作成
        session = session_manager.create_session(
            provider="openai", model="gpt-4o", initial_context="テストコンテキスト"
        )

        # セッションが正しく作成されることを確認
        assert isinstance(session, InteractiveSession)
        assert session.provider == "openai"
        assert session.model == "gpt-4o"
        assert session.is_active is True
        assert session.message_count == 1  # 初期メッセージが追加される

        # セッションが管理されていることを確認
        assert session.session_id in session_manager.active_sessions
        assert session.session_id in session_manager.session_contexts

    def test_create_session_with_options(self, session_manager):
        """オプション付きセッション作成のテスト"""
        options = AnalyzeOptions(
            provider="anthropic", model="claude-3-sonnet", custom_prompt="カスタムプロンプト", streaming=True
        )

        session = session_manager.create_session(
            provider="anthropic", model="claude-3-sonnet", initial_context="テストコンテキスト", options=options
        )

        # オプションがコンテキストに保存されることを確認
        context = session_manager.get_session_context(session.session_id)
        assert context["options"] == options

    def test_get_session(self, session_manager):
        """セッション取得のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")

        # セッションを取得
        retrieved_session = session_manager.get_session(session.session_id)
        assert retrieved_session == session

        # 存在しないセッションの場合
        non_existent_session = session_manager.get_session("non-existent-id")
        assert non_existent_session is None

    def test_update_session_activity(self, session_manager):
        """セッション活動更新のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")
        original_activity = session.last_activity

        # 少し待ってから活動を更新
        import time

        time.sleep(0.01)
        session_manager.update_session_activity(session.session_id)

        # 最終活動時刻が更新されることを確認
        assert session.last_activity > original_activity

    def test_add_message_to_session(self, session_manager):
        """セッションメッセージ追加のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")
        initial_count = session.message_count

        # メッセージを追加
        success = session_manager.add_message_to_session(
            session.session_id, role="user", content="テストメッセージ", tokens=10, cost=0.001
        )

        # メッセージが正しく追加されることを確認
        assert success is True
        assert session.message_count == initial_count + 1
        assert session.total_tokens_used == 10
        assert session.total_cost == 0.001

        # 存在しないセッションの場合
        success = session_manager.add_message_to_session(
            "non-existent-id", role="user", content="テスト", tokens=5, cost=0.0005
        )
        assert success is False

    def test_get_conversation_context(self, session_manager):
        """会話コンテキスト取得のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")

        # 複数のメッセージを追加
        session_manager.add_message_to_session(session.session_id, role="user", content="質問1", tokens=5, cost=0.001)
        session_manager.add_message_to_session(
            session.session_id, role="assistant", content="回答1", tokens=10, cost=0.002
        )
        session_manager.add_message_to_session(session.session_id, role="user", content="質問2", tokens=5, cost=0.001)

        # 会話コンテキストを取得
        context = session_manager.get_conversation_context(session.session_id, max_messages=3)

        # コンテキストが正しくフォーマットされることを確認
        assert "ユーザー: 質問1" in context
        assert "AI: 回答1" in context
        assert "ユーザー: 質問2" in context

        # 存在しないセッションの場合
        empty_context = session_manager.get_conversation_context("non-existent-id")
        assert empty_context == ""

    def test_get_session_context(self, session_manager):
        """セッションコンテキスト取得のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o", initial_context="初期コンテキスト")

        # コンテキストを取得
        context = session_manager.get_session_context(session.session_id)

        # 初期コンテキストが設定されることを確認
        assert context["initial_context"] == "初期コンテキスト"
        assert "options" in context
        assert "current_topic" in context
        assert "analysis_results" in context
        assert "user_preferences" in context

    def test_update_session_context(self, session_manager):
        """セッションコンテキスト更新のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")

        # コンテキストを更新
        success = session_manager.update_session_context(session.session_id, "current_topic", "エラー分析")
        assert success is True

        # 更新されたコンテキストを確認
        context = session_manager.get_session_context(session.session_id)
        assert context["current_topic"] == "エラー分析"

        # 存在しないセッションの場合
        success = session_manager.update_session_context("non-existent-id", "key", "value")
        assert success is False

    def test_generate_interactive_prompt(self, session_manager, prompt_manager):
        """対話プロンプト生成のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o", initial_context="初期コンテキスト")

        # メッセージを追加
        session_manager.add_message_to_session(session.session_id, role="user", content="質問", tokens=5, cost=0.001)

        # プロンプトを生成
        prompt = session_manager.generate_interactive_prompt(session.session_id, "新しい質問")

        # プロンプトマネージャーが呼び出されることを確認
        prompt_manager.get_interactive_prompt.assert_called_once()
        assert prompt == "テスト用プロンプト"

        # 存在しないセッションの場合
        with pytest.raises(AIError):
            session_manager.generate_interactive_prompt("non-existent-id", "質問")

    def test_close_session(self, session_manager):
        """セッション終了のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")
        session_id = session.session_id

        # セッションが存在することを確認
        assert session_id in session_manager.active_sessions
        assert session_id in session_manager.session_contexts

        # セッションを終了
        success = session_manager.close_session(session_id)
        assert success is True

        # セッションが削除されることを確認
        assert session_id not in session_manager.active_sessions
        assert session_id not in session_manager.session_contexts
        assert session.is_active is False

        # 存在しないセッションの場合
        success = session_manager.close_session("non-existent-id")
        assert success is False

    def test_cleanup_expired_sessions(self, session_manager):
        """期限切れセッションクリーンアップのテスト"""
        # 短いタイムアウトでセッション管理を作成
        short_timeout_manager = InteractiveSessionManager(Mock(), session_timeout=1)

        # セッションを作成
        session = short_timeout_manager.create_session(provider="openai", model="gpt-4o")

        # セッションが存在することを確認
        assert len(short_timeout_manager.active_sessions) == 1

        # 時間を進める（モック）
        with patch("ci_helper.ai.interactive_session.datetime") as mock_datetime:
            # 現在時刻を2秒後に設定
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time

            # クリーンアップを実行
            cleaned_count = short_timeout_manager.cleanup_expired_sessions()

            # 期限切れセッションが削除されることを確認
            assert cleaned_count == 1
            assert len(short_timeout_manager.active_sessions) == 0

    def test_get_active_sessions(self, session_manager):
        """アクティブセッション一覧取得のテスト"""
        # 複数のセッションを作成
        session1 = session_manager.create_session(provider="openai", model="gpt-4o")
        session2 = session_manager.create_session(provider="anthropic", model="claude-3-sonnet")

        # アクティブセッション一覧を取得
        active_sessions = session_manager.get_active_sessions()

        # 両方のセッションが含まれることを確認
        assert len(active_sessions) == 2
        session_ids = [s.session_id for s in active_sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids

    def test_get_session_stats(self, session_manager):
        """セッション統計取得のテスト"""
        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")

        # メッセージを追加
        session_manager.add_message_to_session(session.session_id, role="user", content="質問", tokens=10, cost=0.002)

        # 統計を取得
        stats = session_manager.get_session_stats(session.session_id)

        # 統計が正しく計算されることを確認
        assert stats["session_id"] == session.session_id
        assert stats["provider"] == "openai"
        assert stats["model"] == "gpt-4o"
        assert stats["message_count"] == session.message_count  # 実際のメッセージ数
        assert stats["total_tokens"] == session.total_tokens_used
        assert stats["total_cost"] == session.total_cost
        assert stats["is_active"] is True

        # 存在しないセッションの場合
        empty_stats = session_manager.get_session_stats("non-existent-id")
        assert empty_stats == {}

    @pytest.mark.asyncio
    async def test_auto_cleanup_task(self, session_manager):
        """自動クリーンアップタスクのテスト"""
        # 短時間でテストするためにモックを使用
        with patch.object(session_manager, "cleanup_expired_sessions") as mock_cleanup:
            with patch("asyncio.sleep") as mock_sleep:
                # 1回実行してから例外を発生させてループを終了
                mock_sleep.side_effect = [KeyboardInterrupt()]

                # 自動クリーンアップタスクを実行
                with pytest.raises(KeyboardInterrupt):
                    await session_manager.auto_cleanup_task()

                # クリーンアップが呼び出されることを確認
                mock_cleanup.assert_called()

    def test_len_and_contains(self, session_manager):
        """__len__と__contains__のテスト"""
        # 初期状態
        assert len(session_manager) == 0

        # セッションを作成
        session = session_manager.create_session(provider="openai", model="gpt-4o")

        # セッション数とcontainsをテスト
        assert len(session_manager) == 1
        assert session.session_id in session_manager
        assert "non-existent-id" not in session_manager

        # セッションを追加
        session2 = session_manager.create_session(provider="anthropic", model="claude-3-sonnet")
        assert len(session_manager) == 2
        assert session2.session_id in session_manager

        # セッションを終了
        session_manager.close_session(session.session_id)
        assert len(session_manager) == 1
        assert session.session_id not in session_manager
        assert session2.session_id in session_manager
