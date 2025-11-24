"""
AI統合用エラーハンドラーのユニットテスト

AI機能で発生する様々なエラーの処理、フォールバック機構、
リトライロジック、復旧プロセスのテストを実装します。
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from ci_helper.ai.error_handler import AIErrorHandler
from ci_helper.ai.exceptions import (
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
from ci_helper.ai.models import AnalysisResult, AnalysisStatus


class TestErrorTypeHandling:
    """エラータイプ別ハンドリングのテスト"""

    @pytest.fixture
    def error_handler(self, mock_config):
        """エラーハンドラーのフィクスチャ"""
        return AIErrorHandler(mock_config)

    def test_handle_api_key_error_openai(self, error_handler):
        """OpenAI APIキーエラーハンドリングのテスト"""
        error = APIKeyError("openai", "Invalid API key provided")

        result = error_handler.handle_api_key_error(error)

        assert result["error_type"] == "api_key_error"
        assert result["provider"] == "openai"
        assert result["message"] == "Invalid API key provided"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 0
        assert "OPENAI_API_KEY 環境変数を設定してください" in result["recovery_steps"][0]
        assert "openai" in result["documentation_url"]

    def test_handle_api_key_error_anthropic(self, error_handler):
        """Anthropic APIキーエラーハンドリングのテスト"""
        error = APIKeyError("anthropic", "Authentication failed")

        result = error_handler.handle_api_key_error(error)

        assert result["error_type"] == "api_key_error"
        assert result["provider"] == "anthropic"
        assert result["message"] == "Authentication failed"
        assert "ANTHROPIC_API_KEY 環境変数を設定してください" in result["recovery_steps"][0]
        assert "anthropic" in result["documentation_url"]

    def test_handle_rate_limit_error_with_retry_after(self, error_handler):
        """リトライ時間指定ありのレート制限エラーハンドリングのテスト"""
        reset_time = datetime.now() + timedelta(minutes=5)
        error = RateLimitError("openai", reset_time=reset_time, retry_after=300)

        result = error_handler.handle_rate_limit_error(error)

        assert result["error_type"] == "rate_limit_error"
        assert result["provider"] == "openai"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 300
        assert result["auto_retry"] is True
        assert result["reset_time"] == reset_time.isoformat()
        assert "300秒待機してから再試行してください" in result["recovery_steps"][0]

    def test_handle_rate_limit_error_without_retry_after(self, error_handler):
        """リトライ時間指定なしのレート制限エラーハンドリングのテスト"""
        error = RateLimitError("anthropic")

        result = error_handler.handle_rate_limit_error(error)

        assert result["error_type"] == "rate_limit_error"
        assert result["provider"] == "anthropic"
        assert result["retry_delay"] == 60  # デフォルト値
        assert result["reset_time"] is None

    def test_handle_network_error_first_retry(self, error_handler):
        """初回リトライのネットワークエラーハンドリングのテスト"""
        error = NetworkError("Connection timeout", retry_count=0)

        result = error_handler.handle_network_error(error)

        assert result["error_type"] == "network_error"
        assert result["message"] == "Connection timeout"
        assert result["retry_count"] == 0
        assert result["can_retry"] is True
        assert result["auto_retry"] is True
        assert result["retry_delay"] == 1  # 2^0 = 1

    def test_handle_network_error_max_retries(self, error_handler):
        """最大リトライ回数到達時のネットワークエラーハンドリングのテスト"""
        error = NetworkError("Connection failed", retry_count=3)

        result = error_handler.handle_network_error(error)

        assert result["error_type"] == "network_error"
        assert result["retry_count"] == 3
        assert result["can_retry"] is False
        assert result["auto_retry"] is False

    def test_handle_network_error_exponential_backoff(self, error_handler):
        """指数バックオフのネットワークエラーハンドリングのテスト"""
        error = NetworkError("Connection failed", retry_count=2)

        result = error_handler.handle_network_error(error)

        assert result["retry_delay"] == 4  # 2^2 = 4

        # 最大遅延時間のテスト
        error_max = NetworkError("Connection failed", retry_count=10)
        result_max = error_handler.handle_network_error(error_max)
        assert result_max["retry_delay"] == 60  # 最大60秒

    def test_handle_token_limit_error(self, error_handler):
        """トークン制限エラーハンドリングのテスト"""
        error = TokenLimitError(used_tokens=5000, limit=4000, model="gpt-4o")

        result = error_handler.handle_token_limit_error(error)

        assert result["error_type"] == "token_limit_error"
        assert result["model"] == "gpt-4o"
        assert result["used_tokens"] == 5000
        assert result["limit"] == 4000
        assert result["can_retry"] is True
        assert result["auto_compress"] is True

        # 削減率の計算確認（約20%削減が必要）
        recovery_steps = result["recovery_steps"]
        assert any("20.0%" in step for step in recovery_steps)

    def test_handle_provider_error(self, error_handler):
        """プロバイダーエラーハンドリングのテスト"""
        error = ProviderError("openai", "Service temporarily unavailable")

        result = error_handler.handle_provider_error(error)

        assert result["error_type"] == "provider_error"
        assert result["provider"] == "openai"
        assert result["message"] == "Service temporarily unavailable"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 5
        assert result["fallback_available"] is True

    def test_handle_configuration_error_with_key(self, error_handler):
        """設定キー指定ありの設定エラーハンドリングのテスト"""
        error = ConfigurationError("Invalid model name", config_key="ai.model")

        result = error_handler.handle_configuration_error(error)

        assert result["error_type"] == "configuration_error"
        assert result["config_key"] == "ai.model"
        assert result["message"] == "Invalid model name"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 0

        # 設定キーが復旧手順に含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("ai.model" in step for step in recovery_steps)

    def test_handle_configuration_error_without_key(self, error_handler):
        """設定キー指定なしの設定エラーハンドリングのテスト"""
        error = ConfigurationError("Configuration file not found")

        result = error_handler.handle_configuration_error(error)

        assert result["config_key"] is None
        recovery_steps = result["recovery_steps"]
        assert len(recovery_steps) == 3  # 設定キー関連のステップが含まれない

    def test_handle_security_error(self, error_handler):
        """セキュリティエラーハンドリングのテスト"""
        error = SecurityError("API key found in config file", security_issue="secrets_in_config")

        result = error_handler.handle_security_error(error)

        assert result["error_type"] == "security_error"
        assert result["message"] == "API key found in config file"
        assert result["security_issue"] == "secrets_in_config"
        assert result["can_retry"] is False
        assert result["requires_manual_fix"] is True

    def test_handle_cache_error(self, error_handler):
        """キャッシュエラーハンドリングのテスト"""
        error = CacheError("Permission denied", cache_path="./test_cache")

        result = error_handler.handle_cache_error(error)

        assert result["error_type"] == "cache_error"
        assert result["cache_path"] == "./test_cache"
        assert result["message"] == "Permission denied"
        assert result["can_retry"] is True
        assert result["disable_cache"] is True

    def test_handle_analysis_error(self, error_handler):
        """分析エラーハンドリングのテスト"""
        error = AnalysisError("Failed to parse log file", log_path="/path/to/log.txt")

        result = error_handler.handle_analysis_error(error)

        assert result["error_type"] == "analysis_error"
        assert result["log_path"] == "/path/to/log.txt"
        assert result["message"] == "Failed to parse log file"
        assert result["can_retry"] is True
        assert result["fallback_available"] is True

    def test_handle_interactive_session_error(self, error_handler):
        """対話セッションエラーハンドリングのテスト"""
        error = InteractiveSessionError("Session timeout", session_id="session-123")

        result = error_handler.handle_interactive_session_error(error)

        assert result["error_type"] == "interactive_session_error"
        assert result["session_id"] == "session-123"
        assert result["message"] == "Session timeout"
        assert result["can_retry"] is True
        assert result["restart_session"] is True

    def test_handle_generic_ai_error(self, error_handler):
        """汎用AIエラーハンドリングのテスト"""
        error = AIError("Unknown AI error occurred")

        result = error_handler.handle_generic_ai_error(error)

        assert result["error_type"] == "generic_ai_error"
        assert result["message"] == "Unknown AI error occurred"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 5

    def test_handle_unexpected_error(self, error_handler):
        """予期しないエラーハンドリングのテスト"""
        error = ValueError("Unexpected error")

        result = error_handler.handle_unexpected_error(error)

        assert result["error_type"] == "unexpected_error"
        assert "予期しないエラーが発生しました" in result["message"]
        assert result["details"] == "Unexpected error"
        assert result["can_retry"] is True
        assert result["retry_delay"] == 10
        assert result["report_bug"] is True

    def test_process_error_routing(self, error_handler):
        """エラー処理のルーティングテスト"""
        # 各エラータイプが適切なハンドラーにルーティングされることを確認

        api_error = APIKeyError("openai")
        result = error_handler.process_error(api_error)
        assert result["error_type"] == "api_key_error"

        rate_error = RateLimitError("anthropic")
        result = error_handler.process_error(rate_error)
        assert result["error_type"] == "rate_limit_error"

        network_error = NetworkError("Connection failed")
        result = error_handler.process_error(network_error)
        assert result["error_type"] == "network_error"

        token_error = TokenLimitError(5000, 4000, "gpt-4o")
        result = error_handler.process_error(token_error)
        assert result["error_type"] == "token_limit_error"

        unexpected_error = ValueError("Unknown")
        result = error_handler.process_error(unexpected_error)
        assert result["error_type"] == "unexpected_error"


class TestFallbackMechanisms:
    """フォールバック機構のテスト"""

    @pytest.fixture
    def error_handler(self, mock_config):
        """エラーハンドラーのフィクスチャ"""
        return AIErrorHandler(mock_config)

    def test_create_fallback_result_with_start_time(self, error_handler):
        """開始時刻指定ありのフォールバック結果作成テスト"""
        start_time = datetime.now() - timedelta(seconds=5)
        error_message = "AI analysis failed"

        result = error_handler.create_fallback_result(error_message, start_time)

        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.FAILED
        assert result.provider == "fallback"
        assert result.model == "error"
        assert result.confidence_score == 0.0
        assert result.cache_hit is False
        assert error_message in result.summary
        assert result.analysis_time > 0  # 処理時間が計算されている
        assert result.analysis_time <= 10  # 合理的な範囲内
        assert len(result.root_causes) == 0
        assert len(result.fix_suggestions) == 0

    def test_create_fallback_result_without_start_time(self, error_handler):
        """開始時刻指定なしのフォールバック結果作成テスト"""
        error_message = "Network connection failed"

        result = error_handler.create_fallback_result(error_message)

        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.FAILED
        assert result.analysis_time == 0.0
        assert error_message in result.summary

    def test_ai_failure_fallback_to_basic_analysis(self, error_handler):
        """AI失敗時の基本分析フォールバックのテスト"""
        # APIキーエラーの場合のフォールバック
        api_error = APIKeyError("openai", "Invalid API key")
        error_info = error_handler.handle_api_key_error(api_error)

        # フォールバック可能であることを確認
        assert error_info["can_retry"] is True

        # フォールバック結果を作成
        fallback_result = error_handler.create_fallback_result(f"AI分析に失敗しました: {api_error.message}")

        assert fallback_result.status == AnalysisStatus.FAILED
        assert "AI分析に失敗しました" in fallback_result.summary
        assert fallback_result.provider == "fallback"

    def test_provider_failure_fallback_chain(self, error_handler):
        """プロバイダー失敗時のフォールバックチェーンのテスト"""
        # プロバイダーエラーの処理
        provider_error = ProviderError("openai", "Service unavailable")
        error_info = error_handler.handle_provider_error(provider_error)

        # フォールバックが利用可能であることを確認
        assert error_info["fallback_available"] is True
        assert error_info["can_retry"] is True

        # 別のプロバイダーへのフォールバックを推奨
        recovery_steps = error_info["recovery_steps"]
        assert any("別のプロバイダーを試してください" in step for step in recovery_steps)

    def test_partial_result_preservation(self, error_handler):
        """部分的結果保存のテスト"""
        # 分析エラーの場合の部分結果保存
        analysis_error = AnalysisError("Partial analysis failed", log_path="/path/to/log")
        error_info = error_handler.handle_analysis_error(analysis_error)

        # フォールバックが利用可能であることを確認
        assert error_info["fallback_available"] is True
        assert error_info["can_retry"] is True

        # 部分結果を含むフォールバック結果を作成
        fallback_result = error_handler.create_fallback_result("部分的な分析結果のみ利用可能です")

        assert "部分的な分析結果" in fallback_result.summary
        assert fallback_result.status == AnalysisStatus.FAILED

    def test_graceful_degradation_strategies(self, error_handler):
        """優雅な機能低下戦略のテスト"""
        # トークン制限エラーの場合の機能低下
        token_error = TokenLimitError(5000, 4000, "gpt-4o")
        error_info = error_handler.handle_token_limit_error(token_error)

        # 自動圧縮が有効であることを確認
        assert error_info["auto_compress"] is True
        assert error_info["can_retry"] is True

        # 機能低下戦略が復旧手順に含まれることを確認
        recovery_steps = error_info["recovery_steps"]
        assert any("要約してから分析" in step for step in recovery_steps)
        assert any("小さなチャンクに分割" in step for step in recovery_steps)

    def test_cache_error_fallback_to_no_cache(self, error_handler):
        """キャッシュエラー時のキャッシュ無効化フォールバックのテスト"""
        cache_error = CacheError("Cache write failed", cache_path="./test_cache")
        error_info = error_handler.handle_cache_error(cache_error)

        # キャッシュ無効化が推奨されることを確認
        assert error_info["disable_cache"] is True
        assert error_info["can_retry"] is True

        # 復旧手順にキャッシュ無効化オプションが含まれることを確認
        recovery_steps = error_info["recovery_steps"]
        assert any("--no-cache" in step for step in recovery_steps)

    def test_interactive_session_fallback_to_restart(self, error_handler):
        """対話セッションエラー時の再開フォールバックのテスト"""
        session_error = InteractiveSessionError("Session corrupted", session_id="sess-123")
        error_info = error_handler.handle_interactive_session_error(session_error)

        # セッション再開が推奨されることを確認
        assert error_info["restart_session"] is True
        assert error_info["can_retry"] is True

        # 復旧手順にセッション再開が含まれることを確認
        recovery_steps = error_info["recovery_steps"]
        assert any("セッションを再開" in step for step in recovery_steps)

    def test_security_error_no_fallback(self, error_handler):
        """セキュリティエラー時のフォールバック無効化テスト"""
        security_error = SecurityError("API key exposed", security_issue="key_in_logs")
        error_info = error_handler.handle_security_error(security_error)

        # セキュリティエラーではフォールバックが無効であることを確認
        assert error_info["can_retry"] is False
        assert error_info["requires_manual_fix"] is True
        assert "fallback_available" not in error_info or not error_info["fallback_available"]

    def test_network_error_fallback_with_retry_limit(self, error_handler):
        """ネットワークエラーのリトライ制限付きフォールバックテスト"""
        # 最大リトライ回数に達した場合
        network_error = NetworkError("Connection failed", retry_count=3)
        error_info = error_handler.handle_network_error(network_error)

        # フォールバックが無効になることを確認
        assert error_info["can_retry"] is False
        assert error_info["auto_retry"] is False

        # 初回エラーの場合はフォールバック可能
        network_error_first = NetworkError("Connection failed", retry_count=0)
        error_info_first = error_handler.handle_network_error(network_error_first)

        assert error_info_first["can_retry"] is True
        assert error_info_first["auto_retry"] is True


class TestRetryLogic:
    """リトライロジックのテスト"""

    @pytest.fixture
    def error_handler(self, mock_config):
        """エラーハンドラーのフィクスチャ"""
        return AIErrorHandler(mock_config)

    @pytest.mark.asyncio
    async def test_exponential_backoff_implementation(self, error_handler):
        """指数バックオフ実装のテスト"""
        operation_name = "test_operation"

        # 初回エラー（リトライ回数0）
        network_error = NetworkError("Connection failed", retry_count=0)
        result = await error_handler.handle_error_with_retry(network_error, operation_name)

        assert result["retry_delay"] == 1  # 2^0 = 1
        assert result["can_retry"] is True
        assert result["auto_retry"] is True

        # 2回目エラー（リトライ回数1）
        network_error_2 = NetworkError("Connection failed", retry_count=1)
        result_2 = await error_handler.handle_error_with_retry(network_error_2, operation_name)

        assert result_2["retry_delay"] == 2  # 2^1 = 2

        # 3回目エラー（リトライ回数2）
        network_error_3 = NetworkError("Connection failed", retry_count=2)
        result_3 = await error_handler.handle_error_with_retry(network_error_3, operation_name)

        assert result_3["retry_delay"] == 4  # 2^2 = 4

    @pytest.mark.asyncio
    async def test_retry_limit_enforcement(self, error_handler):
        """リトライ制限実施のテスト"""
        operation_name = "test_operation_limit"
        max_retries = 2

        # リトライ回数を手動で設定
        error_handler.retry_counts[operation_name] = max_retries

        # 最大リトライ回数に達した場合
        network_error = NetworkError("Connection failed", retry_count=0)
        result = await error_handler.handle_error_with_retry(network_error, operation_name, max_retries)

        assert result["can_retry"] is False
        assert f"最大リトライ回数({max_retries})に達しました" in result["message"]

    @pytest.mark.asyncio
    async def test_retry_condition_evaluation(self, error_handler):
        """リトライ条件評価のテスト"""
        operation_name = "test_retry_condition"

        # リトライ可能なエラー
        retryable_error = NetworkError("Temporary failure")
        result = await error_handler.handle_error_with_retry(retryable_error, operation_name)
        assert result["can_retry"] is True

        # リトライ不可能なエラー
        non_retryable_error = SecurityError("API key exposed")
        result_non_retry = await error_handler.handle_error_with_retry(non_retryable_error, operation_name)
        assert result_non_retry["can_retry"] is False

    @pytest.mark.asyncio
    async def test_retry_state_management(self, error_handler):
        """リトライ状態管理のテスト"""
        operation_name = "test_state_management"

        # 初期状態の確認
        assert error_handler.get_retry_count(operation_name) == 0

        # 自動リトライが有効なエラーでリトライ回数が増加することを確認
        rate_limit_error = RateLimitError("openai", retry_after=1)

        with patch("asyncio.sleep") as mock_sleep:
            result = await error_handler.handle_error_with_retry(rate_limit_error, operation_name)

            # リトライ回数が増加していることを確認
            assert error_handler.get_retry_count(operation_name) == 1
            assert result["retry_count"] == 1

            # asyncio.sleepが呼ばれることを確認
            mock_sleep.assert_called_once_with(1)

    def test_reset_retry_count(self, error_handler):
        """リトライ回数リセットのテスト"""
        operation_name = "test_reset"

        # リトライ回数を設定
        error_handler.retry_counts[operation_name] = 3
        assert error_handler.get_retry_count(operation_name) == 3

        # リセット
        error_handler.reset_retry_count(operation_name)
        assert error_handler.get_retry_count(operation_name) == 0

    def test_get_retry_count_nonexistent_operation(self, error_handler):
        """存在しない操作のリトライ回数取得テスト"""
        result = error_handler.get_retry_count("nonexistent_operation")
        assert result == 0

    @pytest.mark.asyncio
    async def test_auto_retry_disabled_for_manual_errors(self, error_handler):
        """手動修正が必要なエラーでの自動リトライ無効化テスト"""
        operation_name = "test_manual_error"

        # 手動修正が必要なエラー
        config_error = ConfigurationError("Invalid configuration")
        result = await error_handler.handle_error_with_retry(config_error, operation_name)

        # 自動リトライは無効だが、手動でのリトライは可能
        assert result["can_retry"] is True
        assert result.get("auto_retry", False) is False
        assert error_handler.get_retry_count(operation_name) == 0  # 自動リトライしないため回数は増加しない

    @pytest.mark.asyncio
    async def test_retry_delay_calculation_for_rate_limits(self, error_handler):
        """レート制限エラーでのリトライ遅延計算テスト"""
        operation_name = "test_rate_limit_delay"

        # カスタムリトライ遅延を持つレート制限エラー
        rate_limit_error = RateLimitError("anthropic", retry_after=120)

        with patch("asyncio.sleep") as mock_sleep:
            result = await error_handler.handle_error_with_retry(rate_limit_error, operation_name)

            assert result["retry_delay"] == 120
            mock_sleep.assert_called_once_with(120)

    @pytest.mark.asyncio
    async def test_retry_with_different_operations(self, error_handler):
        """異なる操作での独立したリトライ管理テスト"""
        operation_1 = "operation_1"
        operation_2 = "operation_2"

        # 操作1でリトライ回数を増加
        error_1 = RateLimitError("openai", retry_after=1)
        with patch("asyncio.sleep"):
            await error_handler.handle_error_with_retry(error_1, operation_1)

        assert error_handler.get_retry_count(operation_1) == 1
        assert error_handler.get_retry_count(operation_2) == 0

        # 操作2でも独立してリトライ回数を管理
        error_2 = RateLimitError("anthropic", retry_after=1)
        with patch("asyncio.sleep"):
            await error_handler.handle_error_with_retry(error_2, operation_2)

        assert error_handler.get_retry_count(operation_1) == 1
        assert error_handler.get_retry_count(operation_2) == 1

    @pytest.mark.asyncio
    async def test_max_retry_delay_cap(self, error_handler):
        """最大リトライ遅延の上限テスト"""
        operation_name = "test_max_delay"

        # 非常に高いリトライ回数のネットワークエラー
        network_error = NetworkError("Connection failed", retry_count=10)
        result = await error_handler.handle_error_with_retry(network_error, operation_name)

        # 遅延時間が60秒を超えないことを確認
        assert result["retry_delay"] == 60


class TestRecoveryProcesses:
    """復旧プロセスのテスト"""

    @pytest.fixture
    def error_handler(self, mock_config):
        """エラーハンドラーのフィクスチャ"""
        return AIErrorHandler(mock_config)

    def test_automatic_recovery_procedures_api_key(self, error_handler):
        """APIキーエラーの自動復旧手順のテスト"""
        error = APIKeyError("openai", "Invalid API key")
        result = error_handler.handle_api_key_error(error)

        # 自動復旧手順が含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert len(recovery_steps) >= 4
        assert any("環境変数を設定" in step for step in recovery_steps)
        assert any("APIキーが有効であることを確認" in step for step in recovery_steps)
        assert any("権限を確認" in step for step in recovery_steps)
        assert any("再実行" in step for step in recovery_steps)

        # 復旧可能であることを確認
        assert result["can_retry"] is True
        assert result["retry_delay"] == 0

    def test_automatic_recovery_procedures_rate_limit(self, error_handler):
        """レート制限エラーの自動復旧手順のテスト"""
        error = RateLimitError("anthropic", retry_after=300)
        result = error_handler.handle_rate_limit_error(error)

        # 自動復旧手順が含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("300秒待機" in step for step in recovery_steps)
        assert any("より低いレート制限のモデル" in step for step in recovery_steps)
        assert any("プランをアップグレード" in step for step in recovery_steps)

        # 自動復旧が有効であることを確認
        assert result["auto_retry"] is True
        assert result["retry_delay"] == 300

    def test_automatic_recovery_procedures_network(self, error_handler):
        """ネットワークエラーの自動復旧手順のテスト"""
        error = NetworkError("Connection timeout", retry_count=1)
        result = error_handler.handle_network_error(error)

        # 自動復旧手順が含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("インターネット接続を確認" in step for step in recovery_steps)
        assert any("プロキシ設定を確認" in step for step in recovery_steps)
        assert any("ファイアウォール設定を確認" in step for step in recovery_steps)
        assert any("自動的に再試行" in step for step in recovery_steps)

        # 自動復旧が有効であることを確認
        assert result["auto_retry"] is True
        assert result["can_retry"] is True

    def test_manual_recovery_guidance_configuration(self, error_handler):
        """設定エラーの手動復旧ガイダンスのテスト"""
        error = ConfigurationError("Invalid model configuration", config_key="ai.model")
        result = error_handler.handle_configuration_error(error)

        # 手動復旧ガイダンスが含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("ci-helper.toml を確認" in step for step in recovery_steps)
        assert any("ai.model" in step for step in recovery_steps)
        assert any("環境変数が正しく設定" in step for step in recovery_steps)
        assert any("ci-run doctor" in step for step in recovery_steps)

        # 手動復旧が必要であることを確認
        assert result["can_retry"] is True
        assert result["retry_delay"] == 0

    def test_manual_recovery_guidance_security(self, error_handler):
        """セキュリティエラーの手動復旧ガイダンスのテスト"""
        error = SecurityError("API key found in logs", security_issue="key_exposure")
        result = error_handler.handle_security_error(error)

        # セキュリティ関連の手動復旧ガイダンスが含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("環境変数に設定" in step for step in recovery_steps)
        assert any("設定ファイルにAPIキーが含まれていない" in step for step in recovery_steps)
        assert any("ログファイルに機密情報が含まれていない" in step for step in recovery_steps)
        assert any("セキュリティ設定を見直し" in step for step in recovery_steps)

        # 手動修正が必要であることを確認
        assert result["requires_manual_fix"] is True
        assert result["can_retry"] is False

    def test_recovery_progress_tracking_retry_counts(self, error_handler):
        """リトライ回数による復旧進捗追跡のテスト"""
        operation_name = "test_progress_tracking"

        # 初期状態
        assert error_handler.get_retry_count(operation_name) == 0

        # リトライ回数を手動で設定して進捗を追跡
        error_handler.retry_counts[operation_name] = 1
        assert error_handler.get_retry_count(operation_name) == 1

        error_handler.retry_counts[operation_name] = 2
        assert error_handler.get_retry_count(operation_name) == 2

        # リセット後の確認
        error_handler.reset_retry_count(operation_name)
        assert error_handler.get_retry_count(operation_name) == 0

    def test_recovery_progress_tracking_rate_limits(self, error_handler):
        """レート制限による復旧進捗追跡のテスト"""
        provider = "openai"

        # 初期状態（レート制限なし）
        assert not error_handler.is_rate_limited(provider)
        assert error_handler.get_rate_limit_reset_time(provider) is None

        # レート制限を設定
        reset_time = datetime.now() + timedelta(minutes=5)
        error_handler.rate_limit_resets[provider] = reset_time

        # レート制限状態の確認
        assert error_handler.is_rate_limited(provider)
        assert error_handler.get_rate_limit_reset_time(provider) == reset_time

        # 過去の時刻を設定（制限解除）
        past_time = datetime.now() - timedelta(minutes=1)
        error_handler.rate_limit_resets[provider] = past_time

        # 制限解除の確認
        assert not error_handler.is_rate_limited(provider)
        assert error_handler.get_rate_limit_reset_time(provider) is None

    def test_recovery_success_validation_api_key(self, error_handler):
        """APIキーエラー復旧成功検証のテスト"""
        error = APIKeyError("openai", "Invalid API key")
        result = error_handler.handle_api_key_error(error)

        # 復旧成功の条件を確認
        assert result["can_retry"] is True
        assert result["documentation_url"] is not None
        assert "openai" in result["documentation_url"]

        # 復旧手順が具体的であることを確認
        recovery_steps = result["recovery_steps"]
        assert all(step.strip() for step in recovery_steps)  # 空でない手順
        assert len(recovery_steps) >= 4  # 十分な手順数

    def test_recovery_success_validation_token_limit(self, error_handler):
        """トークン制限エラー復旧成功検証のテスト"""
        error = TokenLimitError(5000, 4000, "gpt-4o")
        result = error_handler.handle_token_limit_error(error)

        # 復旧成功の条件を確認
        assert result["can_retry"] is True
        assert result["auto_compress"] is True

        # 具体的な削減率が提示されることを確認
        recovery_steps = result["recovery_steps"]
        reduction_step = next((step for step in recovery_steps if "%" in step), None)
        assert reduction_step is not None
        assert "20.0%" in reduction_step  # (5000-4000)/5000 * 100 = 20%

    def test_recovery_success_validation_cache_error(self, error_handler):
        """キャッシュエラー復旧成功検証のテスト"""
        error = CacheError("Permission denied", cache_path="./test_cache")
        result = error_handler.handle_cache_error(error)

        # 復旧成功の条件を確認
        assert result["can_retry"] is True
        assert result["disable_cache"] is True

        # キャッシュ無効化オプションが提示されることを確認
        recovery_steps = result["recovery_steps"]
        assert any("--no-cache" in step for step in recovery_steps)
        assert any("ci-run clean" in step for step in recovery_steps)

    def test_recovery_validation_for_interactive_session(self, error_handler):
        """対話セッションエラー復旧検証のテスト"""
        error = InteractiveSessionError("Session timeout", session_id="sess-123")
        result = error_handler.handle_interactive_session_error(error)

        # 復旧成功の条件を確認
        assert result["can_retry"] is True
        assert result["restart_session"] is True

        # セッション再開手順が含まれることを確認
        recovery_steps = result["recovery_steps"]
        assert any("セッションを再開" in step for step in recovery_steps)
        assert any("/exit" in step for step in recovery_steps)

    def test_recovery_failure_for_security_errors(self, error_handler):
        """セキュリティエラーでの復旧失敗処理テスト"""
        error = SecurityError("Credentials exposed", security_issue="key_in_config")
        result = error_handler.handle_security_error(error)

        # 自動復旧が不可能であることを確認
        assert result["can_retry"] is False
        assert result["requires_manual_fix"] is True

        # 手動修正が必要であることが明示されることを確認
        recovery_steps = result["recovery_steps"]
        assert len(recovery_steps) >= 4
        assert all("確認" in step or "見直し" in step for step in recovery_steps)

    def test_provider_docs_url_generation(self, error_handler):
        """プロバイダードキュメントURL生成のテスト"""
        # 各プロバイダーの適切なURLが生成されることを確認
        openai_url = error_handler._get_provider_docs_url("openai")
        assert "platform.openai.com" in openai_url

        anthropic_url = error_handler._get_provider_docs_url("anthropic")
        assert "docs.anthropic.com" in anthropic_url

        local_url = error_handler._get_provider_docs_url("local")
        assert "ollama.ai" in local_url

        # 未知のプロバイダーの場合はデフォルトURLが返されることを確認
        unknown_url = error_handler._get_provider_docs_url("unknown")
        assert "github.com/scottlz0310/ci-helper" in unknown_url


class TestErrorLoggingAndNotification:
    """エラーログとユーザー通知のテスト"""

    @pytest.fixture
    def error_handler(self, mock_config):
        """エラーハンドラーのフィクスチャ"""
        return AIErrorHandler(mock_config)

    @patch("ci_helper.ai.error_handler.logger")
    def test_appropriate_log_level_for_api_key_error(self, mock_logger, error_handler):
        """APIキーエラーの適切なログレベルでの記録テスト"""
        error = APIKeyError("openai", "Invalid API key")

        error_handler.handle_api_key_error(error)

        # ERRORレベルでログが記録されることを確認
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0]
        assert "APIキーエラー" in call_args[0]
        assert "openai" in call_args[1]
        assert "Invalid API key" in call_args[2]

    @patch("ci_helper.ai.error_handler.logger")
    def test_appropriate_log_level_for_rate_limit_error(self, mock_logger, error_handler):
        """レート制限エラーの適切なログレベルでの記録テスト"""
        error = RateLimitError("anthropic", retry_after=60)

        error_handler.handle_rate_limit_error(error)

        # WARNINGレベルでログが記録されることを確認（一時的な問題のため）
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0]
        assert "レート制限エラー" in call_args[0]

    @patch("ci_helper.ai.error_handler.logger")
    def test_appropriate_log_level_for_network_error(self, mock_logger, error_handler):
        """ネットワークエラーの適切なログレベルでの記録テスト"""
        error = NetworkError("Connection timeout", retry_count=2)

        error_handler.handle_network_error(error)

        # ERRORレベルでログが記録されることを確認
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0]
        assert "ネットワークエラー" in call_args[0]
        assert "Connection timeout" in call_args[1]
        assert 2 == call_args[2]  # retry_count

    @patch("ci_helper.ai.error_handler.logger")
    def test_appropriate_log_level_for_cache_error(self, mock_logger, error_handler):
        """キャッシュエラーの適切なログレベルでの記録テスト"""
        error = CacheError("Cache write failed", cache_path="./test_cache")

        error_handler.handle_cache_error(error)

        # WARNINGレベルでログが記録されることを確認（重要度が低いため）
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0]
        assert "キャッシュエラー" in call_args[0]

    @patch("ci_helper.ai.error_handler.logger")
    def test_appropriate_log_level_for_unexpected_error(self, mock_logger, error_handler):
        """予期しないエラーの適切なログレベルでの記録テスト"""
        error = ValueError("Unexpected error")

        error_handler.handle_unexpected_error(error)

        # ERRORレベルでログが記録され、スタックトレースも含まれることを確認
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "予期しないエラー" in call_args[0][0]
        assert call_args[1]["exc_info"] is True  # スタックトレース付き

    def test_user_friendly_error_message_content_api_key(self, error_handler):
        """APIキーエラーのユーザー向けエラーメッセージ内容検証テスト"""
        error = APIKeyError("openai", "Invalid API key provided")
        result = error_handler.handle_api_key_error(error)

        formatted_message = error_handler.format_error_message(result)

        # ユーザーフレンドリーな内容が含まれることを確認
        assert "Invalid API key provided" in formatted_message
        assert "対処方法:" in formatted_message
        assert "OPENAI_API_KEY 環境変数を設定" in formatted_message
        assert "ドキュメント:" in formatted_message
        assert "platform.openai.com" in formatted_message

    def test_user_friendly_error_message_content_token_limit(self, error_handler):
        """トークン制限エラーのユーザー向けエラーメッセージ内容検証テスト"""
        error = TokenLimitError(5000, 4000, "gpt-4o")
        result = error_handler.handle_token_limit_error(error)

        formatted_message = error_handler.format_error_message(result)

        # 具体的な情報が含まれることを確認
        assert "5000/4000" in formatted_message
        assert "gpt-4o" in formatted_message
        assert "20.0%削減" in formatted_message
        assert "対処方法:" in formatted_message

    def test_user_friendly_error_message_content_network(self, error_handler):
        """ネットワークエラーのユーザー向けエラーメッセージ内容検証テスト"""
        error = NetworkError("Connection timeout", retry_count=1)
        result = error_handler.handle_network_error(error)

        formatted_message = error_handler.format_error_message(result)

        # 実用的な対処方法が含まれることを確認
        assert "Connection timeout" in formatted_message
        assert "インターネット接続を確認" in formatted_message
        assert "プロキシ設定を確認" in formatted_message
        assert "自動的に再試行" in formatted_message

    def test_error_severity_classification_critical(self, error_handler):
        """重要度判定テスト - 重大エラー"""
        # セキュリティエラーは重大
        security_error = SecurityError("API key exposed")
        result = error_handler.handle_security_error(security_error)

        assert result["can_retry"] is False
        assert result["requires_manual_fix"] is True

    def test_error_severity_classification_high(self, error_handler):
        """重要度判定テスト - 高重要度エラー"""
        # APIキーエラーは高重要度
        api_error = APIKeyError("openai", "Invalid key")
        result = error_handler.handle_api_key_error(api_error)

        assert result["can_retry"] is True
        assert result["retry_delay"] == 0  # 即座に修正可能

    def test_error_severity_classification_medium(self, error_handler):
        """重要度判定テスト - 中重要度エラー"""
        # ネットワークエラーは中重要度
        network_error = NetworkError("Connection failed")
        result = error_handler.handle_network_error(network_error)

        assert result["can_retry"] is True
        assert result["auto_retry"] is True

    def test_error_severity_classification_low(self, error_handler):
        """重要度判定テスト - 低重要度エラー"""
        # キャッシュエラーは低重要度
        cache_error = CacheError("Cache miss")
        result = error_handler.handle_cache_error(cache_error)

        assert result["can_retry"] is True
        assert result["disable_cache"] is True  # 機能を無効化して継続可能

    def test_error_statistics_and_reporting_retry_counts(self, error_handler):
        """エラー統計とレポート機能 - リトライ回数のテスト"""
        # 複数の操作でリトライ回数を設定
        error_handler.retry_counts["operation_1"] = 2
        error_handler.retry_counts["operation_2"] = 1
        error_handler.retry_counts["operation_3"] = 3

        # 統計情報の確認
        total_operations = len(error_handler.retry_counts)
        assert total_operations == 3

        # 文字列表現に統計情報が含まれることを確認
        str_repr = str(error_handler)
        assert "active_retries=3" in str_repr

    def test_error_statistics_and_reporting_rate_limits(self, error_handler):
        """エラー統計とレポート機能 - レート制限のテスト"""
        # 複数のプロバイダーでレート制限を設定
        future_time = datetime.now() + timedelta(minutes=5)
        past_time = datetime.now() - timedelta(minutes=1)

        error_handler.rate_limit_resets["openai"] = future_time  # 制限中
        error_handler.rate_limit_resets["anthropic"] = past_time  # 制限解除済み
        error_handler.rate_limit_resets["local"] = future_time  # 制限中

        # 制限中のプロバイダー数を確認
        rate_limited_count = len([p for p in error_handler.rate_limit_resets if error_handler.is_rate_limited(p)])
        assert rate_limited_count == 2

        # 文字列表現に統計情報が含まれることを確認
        str_repr = str(error_handler)
        assert "rate_limited=2" in str_repr

    def test_comprehensive_error_message_formatting(self, error_handler):
        """包括的なエラーメッセージ整形テスト"""
        error = ProviderError("openai", "Service unavailable")
        error.details = "HTTP 503 Service Unavailable"
        error.suggestion = "Try again later or use a different provider"

        result = error_handler.handle_provider_error(error)
        formatted_message = error_handler.format_error_message(result)

        # すべての要素が含まれることを確認
        assert "Service unavailable" in formatted_message
        assert "詳細: HTTP 503 Service Unavailable" in formatted_message
        assert "提案: Try again later or use a different provider" in formatted_message
        assert "対処方法:" in formatted_message
        assert len(result["recovery_steps"]) >= 4

    def test_error_message_formatting_minimal_info(self, error_handler):
        """最小限の情報でのエラーメッセージ整形テスト"""
        # 詳細や提案がない場合
        result = {"message": "Simple error", "recovery_steps": ["Step 1", "Step 2"]}

        formatted_message = error_handler.format_error_message(result)

        assert "Simple error" in formatted_message
        assert "対処方法:" in formatted_message
        assert "Step 1" in formatted_message
        assert "Step 2" in formatted_message
        # 詳細や提案の項目は含まれない
        assert "詳細:" not in formatted_message
        assert "提案:" not in formatted_message

    def test_error_handler_string_representation(self, error_handler):
        """エラーハンドラーの文字列表現テスト"""
        # 初期状態
        str_repr = str(error_handler)
        assert "AIErrorHandler" in str_repr
        assert "active_retries=0" in str_repr
        assert "rate_limited=0" in str_repr

        # 状態を変更
        error_handler.retry_counts["test_op"] = 1
        error_handler.rate_limit_resets["openai"] = datetime.now() + timedelta(minutes=5)

        # 更新された状態が反映されることを確認
        str_repr_updated = str(error_handler)
        assert "active_retries=1" in str_repr_updated
        assert "rate_limited=1" in str_repr_updated
