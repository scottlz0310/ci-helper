"""
対話コマンドのテスト

InteractiveCommandProcessorと各種コマンドクラスの機能をテストします。
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from ci_helper.ai.interactive_commands import (
    ContextCommand,
    ExitCommand,
    HelpCommand,
    InteractiveCommandProcessor,
    InteractiveErrorHandler,
    LogsCommand,
    StatsCommand,
    SummaryCommand,
    TokenUsageDisplay,
)
from ci_helper.ai.interactive_session import InteractiveSessionManager
from ci_helper.ai.models import InteractiveSession


@pytest.fixture
def mock_session():
    """モックセッション"""
    session = Mock(spec=InteractiveSession)
    session.session_id = "test-session-123"
    session.provider = "openai"
    session.model = "gpt-4o"
    session.duration_minutes = 5.5
    session.message_count = 10
    session.total_tokens_used = 1500
    session.total_cost = 0.03
    session.is_active = True
    session.start_time = datetime.now()
    session.last_activity = datetime.now()
    return session


@pytest.fixture
def mock_session_manager(mock_session):
    """モックセッション管理"""
    manager = Mock(spec=InteractiveSessionManager)
    manager.get_session.return_value = mock_session
    manager.get_session_context.return_value = {
        "initial_context": "テスト用の初期コンテキスト",
        "current_topic": "エラー分析",
        "analysis_results": [{"summary": "テスト分析結果"}],
        "user_preferences": {"verbose": True},
    }
    manager.get_conversation_context.return_value = "ユーザー: 質問\nAI: 回答"
    manager.get_session_stats.return_value = {
        "session_id": "test-session-123",
        "duration_minutes": 5.5,
        "message_count": 10,
        "total_tokens": 1500,
        "total_cost": 0.03,
        "provider": "openai",
        "model": "gpt-4o",
        "is_active": True,
        "start_time": datetime.now().isoformat(),
        "last_activity": datetime.now().isoformat(),
    }
    return manager


@pytest.fixture
def command_processor(mock_session_manager):
    """コマンド処理器"""
    return InteractiveCommandProcessor(mock_session_manager)


class TestInteractiveCommands:
    """対話コマンドのテストクラス"""


class TestHelpCommand:
    """ヘルプコマンドのテスト"""

    @pytest.mark.asyncio
    async def test_help_command_execution(self, mock_session, mock_session_manager):
        """ヘルプコマンド実行のテスト"""
        command = HelpCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "利用可能なコマンド" in result["output"]
        assert "/help" in result["output"]
        assert "/exit" in result["output"]
        assert "test-ses" in result["output"]  # セッションIDは最初の8文字に省略される


class TestExitCommand:
    """終了コマンドのテスト"""

    @pytest.mark.asyncio
    async def test_exit_command_execution(self, mock_session, mock_session_manager):
        """終了コマンド実行のテスト"""
        command = ExitCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert result["should_exit"] is True
        assert "セッションを終了しました" in result["output"]
        mock_session_manager.close_session.assert_called_once_with(mock_session.session_id)


class TestSummaryCommand:
    """要約コマンドのテスト"""

    @pytest.mark.asyncio
    async def test_summary_command_with_context(self, mock_session, mock_session_manager):
        """コンテキスト付き要約コマンドのテスト"""
        command = SummaryCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "セッション要約" in result["output"]
        assert "初期問題" in result["output"]
        assert "最新分析" in result["output"]

    @pytest.mark.asyncio
    async def test_summary_command_empty_context(self, mock_session, mock_session_manager):
        """空のコンテキストでの要約コマンドのテスト"""
        # 空のコンテキストを設定
        mock_session_manager.get_session_context.return_value = {}

        command = SummaryCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        # セッション統計は常に表示されるため、それが含まれることを確認
        assert "セッション統計" in result["output"]


class TestLogsCommand:
    """ログコマンドのテスト"""

    @pytest.mark.asyncio
    async def test_logs_command_with_context(self, mock_session, mock_session_manager):
        """コンテキスト付きログコマンドのテスト"""
        command = LogsCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "初期ログ" in result["output"]
        assert "テスト用の初期コンテキスト" in result["output"]

    @pytest.mark.asyncio
    async def test_logs_command_no_context(self, mock_session, mock_session_manager):
        """コンテキストなしログコマンドのテスト"""
        # 初期コンテキストを空に設定
        mock_session_manager.get_session_context.return_value = {"initial_context": ""}

        command = LogsCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is False
        assert result["should_display"] is True
        assert "初期ログが見つかりません" in result["output"]

    @pytest.mark.asyncio
    async def test_logs_command_long_context(self, mock_session, mock_session_manager):
        """長いコンテキストでのログコマンドのテスト"""
        # 長いコンテキストを設定
        long_context = "x" * 3000
        mock_session_manager.get_session_context.return_value = {"initial_context": long_context}

        command = LogsCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "省略版" in result["output"]
        assert "省略" in result["output"]


class TestStatsCommand:
    """統計コマンドのテスト"""

    @pytest.mark.asyncio
    async def test_stats_command_execution(self, mock_session, mock_session_manager):
        """統計コマンド実行のテスト"""
        command = StatsCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "セッション統計" in result["output"]
        assert "test-ses" in result["output"]  # セッションIDは最初の8文字に省略される
        assert "openai" in result["output"]
        assert "gpt-4o" in result["output"]


class TestContextCommand:
    """コンテキストコマンドのテスト"""

    @pytest.mark.asyncio
    async def test_context_command_execution(self, mock_session, mock_session_manager):
        """コンテキストコマンド実行のテスト"""
        command = ContextCommand()
        result = await command.execute(mock_session, mock_session_manager)

        assert result["success"] is True
        assert result["should_display"] is True
        assert "現在のコンテキスト" in result["output"]
        assert "エラー分析" in result["output"]
        assert "最近の会話" in result["output"]


class TestInteractiveCommandProcessor:
    """コマンド処理器のテスト"""

    def test_is_command(self, command_processor):
        """コマンド判定のテスト"""
        assert command_processor.is_command("/help") is True
        assert command_processor.is_command("/exit") is True
        assert command_processor.is_command("  /stats  ") is True
        assert command_processor.is_command("help") is False
        assert command_processor.is_command("普通のメッセージ") is False

    def test_parse_command(self, command_processor):
        """コマンド解析のテスト"""
        # 基本的なコマンド
        command, args = command_processor.parse_command("/help")
        assert command == "help"
        assert args == []

        # 引数付きコマンド
        command, args = command_processor.parse_command("/analyze error.log")
        assert command == "analyze"
        assert args == ["error.log"]

        # 複数引数
        command, args = command_processor.parse_command("/model gpt-4o --temperature 0.5")
        assert command == "model"
        assert args == ["gpt-4o", "--temperature", "0.5"]

        # 空のコマンド
        command, args = command_processor.parse_command("/")
        assert command == ""
        assert args == []

    @pytest.mark.asyncio
    async def test_process_valid_command(self, command_processor, mock_session_manager):
        """有効なコマンド処理のテスト"""
        session_id = "test-session-123"

        result = await command_processor.process_command(session_id, "/help")

        assert result["success"] is True
        assert result["should_display"] is True
        assert "利用可能なコマンド" in result["output"]

        # セッションにメッセージが追加されることを確認
        assert mock_session_manager.add_message_to_session.call_count == 2  # user + system

    @pytest.mark.asyncio
    async def test_process_invalid_command(self, command_processor, mock_session_manager):
        """無効なコマンド処理のテスト"""
        session_id = "test-session-123"

        result = await command_processor.process_command(session_id, "/invalid")

        assert result["success"] is False
        assert result["should_display"] is True
        assert "不明なコマンド" in result["output"]
        assert "/help" in result["output"]

    @pytest.mark.asyncio
    async def test_process_command_no_session(self, command_processor, mock_session_manager):
        """セッションなしでのコマンド処理のテスト"""
        # セッションが見つからない場合
        mock_session_manager.get_session.return_value = None

        result = await command_processor.process_command("non-existent", "/help")

        assert result["success"] is False
        assert result["should_display"] is True
        assert "セッション" in result["output"]
        assert "見つかりません" in result["output"]

    @pytest.mark.asyncio
    async def test_process_command_exception(self, command_processor, mock_session_manager):
        """コマンド処理中の例外のテスト"""
        # コマンド実行時に例外を発生させる
        with patch.object(command_processor.commands["help"], "execute", side_effect=Exception("テストエラー")):
            result = await command_processor.process_command("test-session-123", "/help")

            assert result["success"] is False
            assert result["should_display"] is True
            assert "エラーが発生しました" in result["output"]

    def test_get_available_commands(self, command_processor):
        """利用可能コマンド一覧取得のテスト"""
        commands = command_processor.get_available_commands()

        assert isinstance(commands, dict)
        assert "help" in commands
        assert "exit" in commands
        assert "summary" in commands
        assert commands["help"] == "利用可能なコマンドを表示"

    def test_add_custom_command(self, command_processor):
        """カスタムコマンド追加のテスト"""
        # カスタムコマンドを作成
        from ci_helper.ai.interactive_commands import InteractiveCommand

        class CustomCommand(InteractiveCommand):
            def __init__(self):
                super().__init__("custom", "カスタムコマンド")

            async def execute(self, session, session_manager, args=None):
                return {"success": True, "output": "カスタム実行", "should_display": True}

        custom_command = CustomCommand()
        command_processor.add_custom_command(custom_command)

        # カスタムコマンドが追加されることを確認
        assert "custom" in command_processor.commands
        assert command_processor.commands["custom"] == custom_command


class TestTokenUsageDisplay:
    """トークン使用量表示のテスト"""

    @pytest.fixture
    def token_display(self):
        """トークン使用量表示インスタンス"""
        return TokenUsageDisplay()

    @pytest.fixture
    def mock_session_with_usage(self):
        """使用量付きモックセッション"""
        session = Mock(spec=InteractiveSession)
        session.total_tokens_used = 1500
        session.total_cost = 0.03
        session.message_count = 10
        session.duration_minutes = 5.5
        return session

    def test_should_update_display(self, token_display):
        """表示更新判定のテスト"""
        # 初期状態では更新すべき
        assert token_display.should_update_display(150) is True

        # 閾値未満では更新しない
        token_display.last_displayed_tokens = 100
        assert token_display.should_update_display(150) is False

        # 閾値以上では更新する
        assert token_display.should_update_display(250) is True

    def test_format_usage_display(self, token_display, mock_session_with_usage):
        """使用量表示フォーマットのテスト"""
        display = token_display.format_usage_display(mock_session_with_usage)

        assert "リアルタイム使用量" in display
        assert "1,500" in display  # トークン数
        assert "$0.0300" in display  # コスト
        assert "10" in display  # メッセージ数
        assert "5.5" in display  # セッション時間

    def test_update_display(self, token_display, mock_session_with_usage):
        """表示更新のテスト"""
        # 初回は更新される
        display = token_display.update_display(mock_session_with_usage)
        assert display is not None
        assert "リアルタイム使用量" in display

        # 閾値未満では更新されない
        mock_session_with_usage.total_tokens_used = 1550
        display = token_display.update_display(mock_session_with_usage)
        assert display is None

        # 閾値以上では更新される
        mock_session_with_usage.total_tokens_used = 1650
        display = token_display.update_display(mock_session_with_usage)
        assert display is not None


class TestInteractiveErrorHandler:
    """対話エラーハンドラーのテスト"""

    @pytest.fixture
    def error_handler(self):
        """エラーハンドラーインスタンス"""
        return InteractiveErrorHandler()

    def test_handle_rate_limit_error(self, error_handler):
        """レート制限エラー処理のテスト"""
        error = Exception("Rate limit exceeded")
        result = error_handler.handle_ai_error(error, "test-session")

        assert result["success"] is False
        assert result["should_display"] is True
        assert "レート制限" in result["output"]
        assert result["retry_after"] == 60

    def test_handle_api_key_error(self, error_handler):
        """APIキーエラー処理のテスト"""
        error = Exception("Invalid API key")
        result = error_handler.handle_ai_error(error, "test-session")

        assert result["success"] is False
        assert result["should_display"] is True
        assert result["should_exit"] is True
        assert "APIキー" in result["output"]

    def test_handle_network_error(self, error_handler):
        """ネットワークエラー処理のテスト"""
        error = Exception("Network connection failed")
        result = error_handler.handle_ai_error(error, "test-session")

        assert result["success"] is False
        assert result["should_display"] is True
        assert result["retry_suggested"] is True
        assert "ネットワーク" in result["output"]

    def test_handle_generic_error(self, error_handler):
        """一般的なエラー処理のテスト"""
        error = Exception("Unknown error")
        result = error_handler.handle_ai_error(error, "test-session")

        assert result["success"] is False
        assert result["should_display"] is True
        assert result["retry_suggested"] is True
        assert "Unknown error" in result["output"]

    def test_should_terminate_session(self, error_handler):
        """セッション終了判定のテスト"""
        # 初期状態では終了しない
        assert error_handler.should_terminate_session() is False

        # エラーを蓄積
        for _ in range(3):
            error_handler.handle_ai_error(Exception("test"), "session")

        # 最大エラー数に達したら終了
        assert error_handler.should_terminate_session() is True

    def test_reset_error_count(self, error_handler):
        """エラーカウントリセットのテスト"""
        # エラーを蓄積
        error_handler.handle_ai_error(Exception("test"), "session")
        assert error_handler.error_count == 1

        # リセット
        error_handler.reset_error_count()
        assert error_handler.error_count == 0

    def test_get_error_recovery_suggestions(self, error_handler):
        """エラー回復提案取得のテスト"""
        suggestions = error_handler.get_error_recovery_suggestions()

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert any("セッションを再開" in s for s in suggestions)
        assert any("プロバイダー" in s for s in suggestions)
