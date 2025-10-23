"""
対話的AIデバッグコマンド

対話セッション中で使用できる特殊コマンド（/help、/exit等）の実装と
リアルタイムトークン使用量表示、エラーハンドリングを提供します。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .interactive_session import InteractiveSessionManager
from .models import InteractiveSession

logger = logging.getLogger(__name__)


class InteractiveCommand:
    """対話コマンドの基底クラス"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """コマンドを実行

        Args:
            session: 対話セッション
            session_manager: セッション管理インスタンス
            args: コマンド引数

        Returns:
            実行結果
        """
        raise NotImplementedError


class HelpCommand(InteractiveCommand):
    """ヘルプコマンド（/help）"""

    def __init__(self):
        super().__init__("help", "利用可能なコマンドを表示")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """ヘルプを表示"""
        help_text = f"""
🤖 対話的AIデバッグモード - 利用可能なコマンド

**基本コマンド:**
- `/help` - このヘルプを表示
- `/exit` - セッションを終了
- `/summary` - 現在の問題の要約を表示
- `/logs` - 初期ログの再表示
- `/fix` - 修正提案の生成
- `/stats` - セッション統計を表示

**分析コマンド:**
- `/analyze <テキスト>` - 追加のログやエラーを分析
- `/context` - 現在のコンテキストを表示
- `/reset` - 会話履歴をリセット

**設定コマンド:**
- `/model <モデル名>` - 使用モデルを変更
- `/provider <プロバイダー名>` - プロバイダーを変更
- `/timeout <秒数>` - タイムアウトを設定

**使用方法:**
- 通常の質問や指示はそのまま入力してください
- コマンドは `/` で始めてください
- 複数行の入力は `\\` で行を継続できます

**現在のセッション情報:**
- セッションID: {session.session_id[:8]}...
- プロバイダー: {session.provider}
- モデル: {session.model}
- 継続時間: {session.duration_minutes:.1f}分
- メッセージ数: {session.message_count}
- 使用トークン: {session.total_tokens_used}
- 累計コスト: ${session.total_cost:.4f}
"""

        return {"success": True, "output": help_text, "should_display": True}


class ExitCommand(InteractiveCommand):
    """終了コマンド（/exit）"""

    def __init__(self):
        super().__init__("exit", "セッションを終了")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """セッションを終了"""
        session_manager.close_session(session.session_id)

        return {
            "success": True,
            "output": f"セッションを終了しました。継続時間: {session.duration_minutes:.1f}分",
            "should_exit": True,
            "should_display": True,
        }


class SummaryCommand(InteractiveCommand):
    """要約コマンド（/summary）"""

    def __init__(self):
        super().__init__("summary", "現在の問題の要約を表示")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """問題の要約を表示"""
        context = session_manager.get_session_context(session.session_id)

        summary_parts = []

        # 初期コンテキスト
        if context.get("initial_context"):
            summary_parts.append(f"**初期問題**: {context['initial_context'][:200]}...")

        # 分析結果
        analysis_results = context.get("analysis_results", [])
        if analysis_results:
            latest_analysis = analysis_results[-1]
            summary_parts.append(f"**最新分析**: {latest_analysis.get('summary', 'N/A')}")

        # 現在のトピック
        if context.get("current_topic"):
            summary_parts.append(f"**現在のトピック**: {context['current_topic']}")

        # セッション統計
        stats = session_manager.get_session_stats(session.session_id)
        summary_parts.append(
            f"**セッション統計**: {stats['message_count']}メッセージ, {stats['total_tokens']}トークン, ${stats['total_cost']:.4f}"
        )

        summary = "\n\n".join(summary_parts) if summary_parts else "要約できる情報がありません。"

        return {"success": True, "output": f"📋 **セッション要約**\n\n{summary}", "should_display": True}


class LogsCommand(InteractiveCommand):
    """ログ表示コマンド（/logs）"""

    def __init__(self):
        super().__init__("logs", "初期ログの再表示")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """初期ログを再表示"""
        context = session_manager.get_session_context(session.session_id)
        initial_context = context.get("initial_context", "")

        if not initial_context:
            return {"success": False, "output": "初期ログが見つかりません。", "should_display": True}

        # ログの長さに応じて表示を調整
        if len(initial_context) > 2000:
            truncated_log = initial_context[:2000] + "\n\n... (ログが長いため省略) ..."
            output = f"📄 **初期ログ** (省略版):\n\n```\n{truncated_log}\n```"
        else:
            output = f"📄 **初期ログ**:\n\n```\n{initial_context}\n```"

        return {"success": True, "output": output, "should_display": True}


class StatsCommand(InteractiveCommand):
    """統計表示コマンド（/stats）"""

    def __init__(self):
        super().__init__("stats", "セッション統計を表示")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """セッション統計を表示"""
        stats = session_manager.get_session_stats(session.session_id)

        stats_text = f"""
📊 **セッション統計**

**基本情報:**
- セッションID: {stats["session_id"][:8]}...
- 開始時刻: {datetime.fromisoformat(stats["start_time"]).strftime("%Y-%m-%d %H:%M:%S")}
- 継続時間: {stats["duration_minutes"]:.1f}分
- 最終活動: {datetime.fromisoformat(stats["last_activity"]).strftime("%H:%M:%S")}

**使用量:**
- メッセージ数: {stats["message_count"]}
- 総トークン数: {stats["total_tokens"]}
- 累計コスト: ${stats["total_cost"]:.4f}

**AI設定:**
- プロバイダー: {stats["provider"]}
- モデル: {stats["model"]}
- ステータス: {"アクティブ" if stats["is_active"] else "非アクティブ"}
"""

        return {"success": True, "output": stats_text, "should_display": True}


class ContextCommand(InteractiveCommand):
    """コンテキスト表示コマンド（/context）"""

    def __init__(self):
        super().__init__("context", "現在のコンテキストを表示")

    async def execute(
        self, session: InteractiveSession, session_manager: InteractiveSessionManager, args: list[str] | None = None
    ) -> dict[str, Any]:
        """現在のコンテキストを表示"""
        context = session_manager.get_session_context(session.session_id)

        context_info = f"""
🔍 **現在のコンテキスト**

**初期コンテキスト**: {len(context.get("initial_context", ""))} 文字
**現在のトピック**: {context.get("current_topic", "なし")}
**分析結果数**: {len(context.get("analysis_results", []))}
**ユーザー設定**: {len(context.get("user_preferences", {}))} 項目

**最近の会話**:
{session_manager.get_conversation_context(session.session_id, max_messages=5)}
"""

        return {"success": True, "output": context_info, "should_display": True}


class InteractiveCommandProcessor:
    """対話コマンド処理クラス

    対話セッション中の特殊コマンドを処理し、適切なレスポンスを生成します。
    """

    def __init__(self, session_manager: InteractiveSessionManager):
        """コマンド処理器を初期化

        Args:
            session_manager: セッション管理インスタンス
        """
        self.session_manager = session_manager
        self.commands = {
            "help": HelpCommand(),
            "exit": ExitCommand(),
            "summary": SummaryCommand(),
            "logs": LogsCommand(),
            "stats": StatsCommand(),
            "context": ContextCommand(),
        }

    def is_command(self, user_input: str) -> bool:
        """入力がコマンドかどうかを判定

        Args:
            user_input: ユーザー入力

        Returns:
            コマンドの場合True
        """
        return user_input.strip().startswith("/")

    def parse_command(self, user_input: str) -> tuple[str, list[str]]:
        """コマンドを解析

        Args:
            user_input: ユーザー入力

        Returns:
            (コマンド名, 引数リスト)
        """
        parts = user_input.strip()[1:].split()  # 先頭の / を除去
        command_name = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        return command_name, args

    async def process_command(self, session_id: str, user_input: str) -> dict[str, Any]:
        """コマンドを処理

        Args:
            session_id: セッションID
            user_input: ユーザー入力

        Returns:
            処理結果
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"success": False, "output": f"セッション {session_id} が見つかりません。", "should_display": True}

        try:
            command_name, args = self.parse_command(user_input)

            if command_name not in self.commands:
                return {
                    "success": False,
                    "output": f"不明なコマンド: /{command_name}\n利用可能なコマンドは `/help` で確認してください。",
                    "should_display": True,
                }

            # コマンドを実行
            command = self.commands[command_name]
            result = await command.execute(session, self.session_manager, args)

            # セッションにコマンド実行を記録
            self.session_manager.add_message_to_session(session_id, role="user", content=user_input, tokens=0, cost=0.0)

            if result.get("should_display"):
                self.session_manager.add_message_to_session(
                    session_id, role="system", content=result["output"], tokens=0, cost=0.0
                )

            logger.info("コマンド実行: %s (セッション: %s)", command_name, session_id[:8])
            return result

        except Exception as e:
            logger.error("コマンド処理中にエラー: %s", e)
            return {"success": False, "output": f"コマンド処理中にエラーが発生しました: {e}", "should_display": True}

    def get_available_commands(self) -> dict[str, str]:
        """利用可能なコマンド一覧を取得

        Returns:
            コマンド名と説明の辞書
        """
        return {name: cmd.description for name, cmd in self.commands.items()}

    def add_custom_command(self, command: InteractiveCommand) -> None:
        """カスタムコマンドを追加

        Args:
            command: 追加するコマンド
        """
        self.commands[command.name] = command
        logger.info("カスタムコマンドを追加: %s", command.name)


class TokenUsageDisplay:
    """トークン使用量表示クラス

    対話セッション中のリアルタイムトークン使用量表示を管理します。
    """

    def __init__(self):
        self.display_threshold = 100  # 表示更新の閾値（トークン数）
        self.last_displayed_tokens = 0

    def should_update_display(self, current_tokens: int) -> bool:
        """表示を更新すべきかどうかを判定

        Args:
            current_tokens: 現在のトークン数

        Returns:
            更新すべき場合True
        """
        token_diff = current_tokens - self.last_displayed_tokens
        return token_diff >= self.display_threshold

    def format_usage_display(self, session: InteractiveSession, estimated_cost_per_token: float = 0.00002) -> str:
        """使用量表示をフォーマット

        Args:
            session: 対話セッション
            estimated_cost_per_token: トークンあたりの推定コスト

        Returns:
            フォーマットされた使用量表示
        """
        # リアルタイム統計を計算
        avg_tokens_per_message = session.total_tokens_used / session.message_count if session.message_count > 0 else 0

        avg_cost_per_message = session.total_cost / session.message_count if session.message_count > 0 else 0

        return f"""
💰 **リアルタイム使用量**
- 総トークン: {session.total_tokens_used:,}
- 累計コスト: ${session.total_cost:.4f}
- メッセージ数: {session.message_count}
- 平均トークン/メッセージ: {avg_tokens_per_message:.1f}
- 平均コスト/メッセージ: ${avg_cost_per_message:.4f}
- セッション時間: {session.duration_minutes:.1f}分
"""

    def update_display(self, session: InteractiveSession) -> str | None:
        """表示を更新（必要な場合のみ）

        Args:
            session: 対話セッション

        Returns:
            更新された表示（更新不要の場合はNone）
        """
        if self.should_update_display(session.total_tokens_used):
            self.last_displayed_tokens = session.total_tokens_used
            return self.format_usage_display(session)

        return None


class InteractiveErrorHandler:
    """対話中のエラーハンドリング

    対話セッション中に発生するエラーを適切に処理し、
    ユーザーに分かりやすいメッセージを提供します。
    """

    def __init__(self):
        self.error_count = 0
        self.max_consecutive_errors = 3

    def handle_ai_error(self, error: Exception, session_id: str) -> dict[str, Any]:
        """AI関連エラーを処理

        Args:
            error: 発生したエラー
            session_id: セッションID

        Returns:
            エラー処理結果
        """
        self.error_count += 1

        error_message = str(error)

        # エラータイプ別の処理
        if "rate limit" in error_message.lower():
            return {
                "success": False,
                "output": "⚠️ レート制限に達しました。少し待ってから再試行してください。",
                "should_display": True,
                "retry_after": 60,
            }
        elif "api key" in error_message.lower():
            return {
                "success": False,
                "output": "🔑 APIキーの問題が発生しました。設定を確認してください。",
                "should_display": True,
                "should_exit": True,
            }
        elif "network" in error_message.lower():
            return {
                "success": False,
                "output": "🌐 ネットワークエラーが発生しました。接続を確認してください。",
                "should_display": True,
                "retry_suggested": True,
            }
        else:
            return {
                "success": False,
                "output": f"❌ エラーが発生しました: {error_message}",
                "should_display": True,
                "retry_suggested": True,
            }

    def should_terminate_session(self) -> bool:
        """セッションを終了すべきかどうかを判定

        Returns:
            終了すべき場合True
        """
        return self.error_count >= self.max_consecutive_errors

    def reset_error_count(self) -> None:
        """エラーカウントをリセット"""
        self.error_count = 0

    def get_error_recovery_suggestions(self) -> list[str]:
        """エラー回復の提案を取得

        Returns:
            回復提案のリスト
        """
        return [
            "セッションを再開してみてください（/exit → 新しいセッション開始）",
            "異なるプロバイダーやモデルを試してください（/provider, /model）",
            "より簡潔な質問に変更してみてください",
            "ネットワーク接続を確認してください",
            "APIキーの設定を確認してください",
        ]
