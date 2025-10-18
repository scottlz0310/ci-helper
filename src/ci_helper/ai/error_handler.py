"""
AI統合用エラーハンドリング

AI機能で発生する様々なエラーを適切に処理し、ユーザーフレンドリーな
エラーメッセージとリカバリー手順を提供します。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..utils.config import Config
from .exceptions import (
    AIError,
    AnalysisError,
    APIKeyError,
    CacheError,
    ConfigurationError,
    InteractiveSessionError,
    NetworkError,
    ProviderError,
    RateLimitError,
    SecurityError,
    TokenLimitError,
)
from .models import AnalysisResult, AnalysisStatus

logger = logging.getLogger(__name__)


class AIErrorHandler:
    """AI統合用エラーハンドラー

    AI機能で発生するエラーを適切に処理し、ユーザーに分かりやすい
    エラーメッセージとリカバリー手順を提供します。
    """

    def __init__(self, config: Config):
        """エラーハンドラーを初期化

        Args:
            config: メイン設定オブジェクト
        """
        self.config = config
        self.retry_counts: dict[str, int] = {}
        self.last_errors: dict[str, datetime] = {}
        self.rate_limit_resets: dict[str, datetime] = {}

    def handle_api_key_error(self, error: APIKeyError) -> dict[str, Any]:
        """APIキーエラーを処理

        Args:
            error: APIキーエラー

        Returns:
            エラー処理結果
        """
        logger.error("APIキーエラー: %s - %s", error.provider, error.message)

        # 環境変数名を決定
        env_var_name = f"{error.provider.upper()}_API_KEY"
        if error.provider == "openai":
            env_var_name = "OPENAI_API_KEY"
        elif error.provider == "anthropic":
            env_var_name = "ANTHROPIC_API_KEY"

        return {
            "error_type": "api_key_error",
            "provider": error.provider,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                f"1. {env_var_name} 環境変数を設定してください",
                "2. APIキーが有効であることを確認してください",
                f"3. {error.provider}のダッシュボードでAPIキーの権限を確認してください",
                "4. 設定後、コマンドを再実行してください",
            ],
            "documentation_url": self._get_provider_docs_url(error.provider),
            "can_retry": True,
            "retry_delay": 0,
        }

    def handle_rate_limit_error(self, error: RateLimitError) -> dict[str, Any]:
        """レート制限エラーを処理

        Args:
            error: レート制限エラー

        Returns:
            エラー処理結果
        """
        logger.warning("レート制限エラー: %s", error.message)

        # リセット時刻を記録
        if error.reset_time:
            self.rate_limit_resets[error.provider] = error.reset_time

        # リトライ遅延を計算
        retry_delay = error.retry_after or 60

        return {
            "error_type": "rate_limit_error",
            "provider": error.provider,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                f"1. {retry_delay}秒待機してから再試行してください",
                "2. より低いレート制限のモデルを使用することを検討してください",
                "3. プロバイダーのプランをアップグレードすることを検討してください",
            ],
            "reset_time": error.reset_time.isoformat() if error.reset_time else None,
            "can_retry": True,
            "retry_delay": retry_delay,
            "auto_retry": True,
        }

    def handle_network_error(self, error: NetworkError) -> dict[str, Any]:
        """ネットワークエラーを処理

        Args:
            error: ネットワークエラー

        Returns:
            エラー処理結果
        """
        logger.error("ネットワークエラー: %s (リトライ回数: %d)", error.message, error.retry_count)

        # 指数バックオフでリトライ遅延を計算
        retry_delay = min(2**error.retry_count, 60)  # 最大60秒

        return {
            "error_type": "network_error",
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "retry_count": error.retry_count,
            "recovery_steps": [
                "1. インターネット接続を確認してください",
                "2. プロキシ設定を確認してください",
                "3. ファイアウォール設定を確認してください",
                f"4. {retry_delay}秒後に自動的に再試行されます",
            ],
            "can_retry": error.retry_count < 3,
            "retry_delay": retry_delay,
            "auto_retry": error.retry_count < 3,
        }

    def handle_token_limit_error(self, error: TokenLimitError) -> dict[str, Any]:
        """トークン制限エラーを処理

        Args:
            error: トークン制限エラー

        Returns:
            エラー処理結果
        """
        logger.error("トークン制限エラー: %s", error.message)

        # 削減率を計算
        reduction_needed = ((error.used_tokens - error.limit) / error.used_tokens) * 100

        return {
            "error_type": "token_limit_error",
            "model": error.model,
            "used_tokens": error.used_tokens,
            "limit": error.limit,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                f"1. 入力を約{reduction_needed:.1f}%削減してください",
                "2. より大きなコンテキストウィンドウを持つモデルを使用してください",
                "3. ログを要約してから分析してください",
                "4. 複数の小さなチャンクに分割して分析してください",
            ],
            "can_retry": True,
            "retry_delay": 0,
            "auto_compress": True,
        }

    def handle_provider_error(self, error: ProviderError) -> dict[str, Any]:
        """プロバイダーエラーを処理

        Args:
            error: プロバイダーエラー

        Returns:
            エラー処理結果
        """
        logger.error("プロバイダーエラー: %s - %s", error.provider, error.message)

        return {
            "error_type": "provider_error",
            "provider": error.provider,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                f"1. {error.provider}プロバイダーの設定を確認してください",
                "2. APIキーが有効であることを確認してください",
                "3. プロバイダーのサービス状況を確認してください",
                "4. 別のプロバイダーを試してください",
            ],
            "can_retry": True,
            "retry_delay": 5,
            "fallback_available": True,
        }

    def handle_configuration_error(self, error: ConfigurationError) -> dict[str, Any]:
        """設定エラーを処理

        Args:
            error: 設定エラー

        Returns:
            エラー処理結果
        """
        logger.error("設定エラー: %s", error.message)

        recovery_steps = [
            "1. 設定ファイル ci-helper.toml を確認してください",
            "2. 環境変数が正しく設定されていることを確認してください",
            "3. ci-run doctor コマンドで環境を確認してください",
        ]

        if error.config_key:
            recovery_steps.insert(1, f"2. 設定キー '{error.config_key}' の値を確認してください")

        return {
            "error_type": "configuration_error",
            "config_key": error.config_key,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": recovery_steps,
            "can_retry": True,
            "retry_delay": 0,
        }

    def handle_security_error(self, error: SecurityError) -> dict[str, Any]:
        """セキュリティエラーを処理

        Args:
            error: セキュリティエラー

        Returns:
            エラー処理結果
        """
        logger.error("セキュリティエラー: %s", error.message)

        return {
            "error_type": "security_error",
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "security_issue": error.security_issue,
            "recovery_steps": [
                "1. APIキーが環境変数に設定されていることを確認してください",
                "2. 設定ファイルにAPIキーが含まれていないことを確認してください",
                "3. ログファイルに機密情報が含まれていないことを確認してください",
                "4. セキュリティ設定を見直してください",
            ],
            "can_retry": False,
            "retry_delay": 0,
            "requires_manual_fix": True,
        }

    def handle_cache_error(self, error: CacheError) -> dict[str, Any]:
        """キャッシュエラーを処理

        Args:
            error: キャッシュエラー

        Returns:
            エラー処理結果
        """
        logger.warning("キャッシュエラー: %s", error.message)

        return {
            "error_type": "cache_error",
            "cache_path": error.cache_path,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                "1. キャッシュディレクトリの権限を確認してください",
                "2. ディスク容量を確認してください",
                "3. --no-cache オプションを使用してキャッシュを無効にしてください",
                "4. ci-run clean コマンドでキャッシュをクリアしてください",
            ],
            "can_retry": True,
            "retry_delay": 0,
            "disable_cache": True,
        }

    def handle_analysis_error(self, error: AnalysisError) -> dict[str, Any]:
        """分析エラーを処理

        Args:
            error: 分析エラー

        Returns:
            エラー処理結果
        """
        logger.error("分析エラー: %s", error.message)

        return {
            "error_type": "analysis_error",
            "log_path": error.log_path,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                "1. ログファイルが存在し、読み取り可能であることを確認してください",
                "2. ログファイルの形式が正しいことを確認してください",
                "3. 別のログファイルで試してください",
                "4. --format オプションで出力形式を変更してください",
            ],
            "can_retry": True,
            "retry_delay": 0,
            "fallback_available": True,
        }

    def handle_interactive_session_error(self, error: InteractiveSessionError) -> dict[str, Any]:
        """対話セッションエラーを処理

        Args:
            error: 対話セッションエラー

        Returns:
            エラー処理結果
        """
        logger.error("対話セッションエラー: %s", error.message)

        return {
            "error_type": "interactive_session_error",
            "session_id": error.session_id,
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                "1. 対話セッションを再開してください",
                "2. /exit コマンドでセッションを終了してから再開してください",
                "3. 別のプロバイダーで対話セッションを開始してください",
            ],
            "can_retry": True,
            "retry_delay": 0,
            "restart_session": True,
        }

    def handle_generic_ai_error(self, error: AIError) -> dict[str, Any]:
        """汎用AIエラーを処理

        Args:
            error: AIエラー

        Returns:
            エラー処理結果
        """
        logger.error("AIエラー: %s", error.message)

        return {
            "error_type": "generic_ai_error",
            "message": error.message,
            "details": error.details,
            "suggestion": error.suggestion,
            "recovery_steps": [
                "1. コマンドを再実行してください",
                "2. 別のプロバイダーを試してください",
                "3. 設定を確認してください",
                "4. サポートに問い合わせてください",
            ],
            "can_retry": True,
            "retry_delay": 5,
        }

    def handle_unexpected_error(self, error: Exception) -> dict[str, Any]:
        """予期しないエラーを処理

        Args:
            error: 予期しないエラー

        Returns:
            エラー処理結果
        """
        logger.error("予期しないエラー: %s", error, exc_info=True)

        return {
            "error_type": "unexpected_error",
            "message": f"予期しないエラーが発生しました: {error}",
            "details": str(error),
            "suggestion": "システム管理者に問い合わせてください",
            "recovery_steps": [
                "1. コマンドを再実行してください",
                "2. --verbose オプションで詳細ログを確認してください",
                "3. 問題が続く場合はサポートに問い合わせてください",
            ],
            "can_retry": True,
            "retry_delay": 10,
            "report_bug": True,
        }

    async def handle_error_with_retry(
        self, error: Exception, operation_name: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """エラーを処理し、必要に応じてリトライを実行

        Args:
            error: 発生したエラー
            operation_name: 操作名
            max_retries: 最大リトライ回数

        Returns:
            エラー処理結果
        """
        # エラータイプに応じて処理
        error_info = self.process_error(error)

        # リトライ可能かチェック
        if not error_info.get("can_retry", False):
            return error_info

        # リトライ回数をチェック
        retry_count = self.retry_counts.get(operation_name, 0)
        if retry_count >= max_retries:
            error_info["message"] = f"最大リトライ回数({max_retries})に達しました: {error_info['message']}"
            error_info["can_retry"] = False
            return error_info

        # 自動リトライが有効な場合
        if error_info.get("auto_retry", False):
            retry_delay = error_info.get("retry_delay", 0)
            if retry_delay > 0:
                logger.info("自動リトライまで %d秒待機中... (試行 %d/%d)", retry_delay, retry_count + 1, max_retries)
                await asyncio.sleep(retry_delay)

            # リトライ回数を更新
            self.retry_counts[operation_name] = retry_count + 1
            error_info["retry_count"] = retry_count + 1

        return error_info

    def process_error(self, error: Exception) -> dict[str, Any]:
        """エラーを処理して適切な情報を返す

        Args:
            error: 発生したエラー

        Returns:
            エラー処理結果
        """
        # エラータイプに応じて適切なハンドラーを呼び出し
        if isinstance(error, APIKeyError):
            return self.handle_api_key_error(error)
        elif isinstance(error, RateLimitError):
            return self.handle_rate_limit_error(error)
        elif isinstance(error, NetworkError):
            return self.handle_network_error(error)
        elif isinstance(error, TokenLimitError):
            return self.handle_token_limit_error(error)
        elif isinstance(error, ProviderError):
            return self.handle_provider_error(error)
        elif isinstance(error, ConfigurationError):
            return self.handle_configuration_error(error)
        elif isinstance(error, SecurityError):
            return self.handle_security_error(error)
        elif isinstance(error, CacheError):
            return self.handle_cache_error(error)
        elif isinstance(error, AnalysisError):
            return self.handle_analysis_error(error)
        elif isinstance(error, InteractiveSessionError):
            return self.handle_interactive_session_error(error)
        elif isinstance(error, AIError):
            return self.handle_generic_ai_error(error)
        else:
            return self.handle_unexpected_error(error)

    def create_fallback_result(self, error_message: str, start_time: datetime | None = None) -> AnalysisResult:
        """フォールバック用の分析結果を作成

        Args:
            error_message: エラーメッセージ
            start_time: 開始時刻

        Returns:
            フォールバック分析結果
        """
        analysis_time = 0.0
        if start_time:
            analysis_time = (datetime.now() - start_time).total_seconds()

        return AnalysisResult(
            summary=f"AI分析中にエラーが発生しました: {error_message}",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.0,
            analysis_time=analysis_time,
            tokens_used=None,
            status=AnalysisStatus.FAILED,
            timestamp=datetime.now(),
            provider="fallback",
            model="error",
            cache_hit=False,
        )

    def reset_retry_count(self, operation_name: str) -> None:
        """リトライ回数をリセット

        Args:
            operation_name: 操作名
        """
        if operation_name in self.retry_counts:
            del self.retry_counts[operation_name]

    def get_retry_count(self, operation_name: str) -> int:
        """リトライ回数を取得

        Args:
            operation_name: 操作名

        Returns:
            現在のリトライ回数
        """
        return self.retry_counts.get(operation_name, 0)

    def is_rate_limited(self, provider: str) -> bool:
        """プロバイダーがレート制限中かどうかを確認

        Args:
            provider: プロバイダー名

        Returns:
            レート制限中かどうか
        """
        if provider not in self.rate_limit_resets:
            return False

        reset_time = self.rate_limit_resets[provider]
        return datetime.now() < reset_time

    def get_rate_limit_reset_time(self, provider: str) -> datetime | None:
        """レート制限のリセット時刻を取得

        Args:
            provider: プロバイダー名

        Returns:
            リセット時刻（制限中でない場合はNone）
        """
        if not self.is_rate_limited(provider):
            return None
        return self.rate_limit_resets[provider]

    def _get_provider_docs_url(self, provider: str) -> str:
        """プロバイダーのドキュメントURLを取得

        Args:
            provider: プロバイダー名

        Returns:
            ドキュメントURL
        """
        docs_urls = {
            "openai": "https://platform.openai.com/docs/quickstart",
            "anthropic": "https://docs.anthropic.com/claude/docs/getting-started",
            "local": "https://ollama.ai/docs",
        }
        return docs_urls.get(provider, "https://github.com/scottlz0310/ci-helper")

    def format_error_message(self, error_info: dict[str, Any]) -> str:
        """エラー情報をユーザーフレンドリーなメッセージに整形

        Args:
            error_info: エラー処理結果

        Returns:
            整形されたエラーメッセージ
        """
        message = error_info["message"]

        if error_info.get("details"):
            message += f"\n詳細: {error_info['details']}"

        if error_info.get("suggestion"):
            message += f"\n提案: {error_info['suggestion']}"

        if error_info.get("recovery_steps"):
            message += "\n\n対処方法:"
            for step in error_info["recovery_steps"]:
                message += f"\n  {step}"

        if error_info.get("documentation_url"):
            message += f"\n\nドキュメント: {error_info['documentation_url']}"

        return message

    def __str__(self) -> str:
        """文字列表現"""
        active_retries = len(self.retry_counts)
        rate_limited = len([p for p in self.rate_limit_resets if self.is_rate_limited(p)])
        return f"AIErrorHandler(active_retries={active_retries}, rate_limited={rate_limited})"
