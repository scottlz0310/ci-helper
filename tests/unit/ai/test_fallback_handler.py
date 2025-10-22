"""
AI統合フォールバック機能のテスト

AI分析失敗時の代替手段をテストします。
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ci_helper.ai.exceptions import NetworkError, ProviderError, RateLimitError
from src.ci_helper.ai.fallback_handler import FallbackHandler
from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, AnalyzeOptions


class TestFallbackHandler:
    """FallbackHandlerのテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック設定"""
        config = Mock()
        config.get_path.return_value = tmp_path
        return config

    @pytest.fixture
    def fallback_handler(self, mock_config):
        """フォールバックハンドラー"""
        return FallbackHandler(mock_config)

    @pytest.fixture
    def sample_log_content(self):
        """サンプルログ内容"""
        return """
ERROR: Test failed with AssertionError
  File "test.py", line 10, in test_function
    assert result == expected
AssertionError: Expected 200, got 404
"""

    @pytest.fixture
    def sample_analyze_options(self):
        """サンプル分析オプション"""
        return AnalyzeOptions(provider="openai", model="gpt-4o", use_cache=False, streaming=False)

    def test_fallback_handler_initialization(self, fallback_handler, mock_config):
        """フォールバックハンドラー初期化のテスト"""
        assert fallback_handler.config == mock_config
        assert fallback_handler.fallback_dir.exists()
        assert isinstance(fallback_handler.retry_attempts, dict)
        assert isinstance(fallback_handler.partial_results, dict)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_fallback(self, fallback_handler, sample_log_content, sample_analyze_options):
        """レート制限フォールバック処理のテスト"""
        error = RateLimitError("openai", retry_after=60)
        operation_id = "test_operation"

        with patch.object(fallback_handler, "_perform_traditional_analysis") as mock_traditional:
            mock_traditional.return_value = {
                "summary": "従来のログ分析を実行しました。1個の失敗を検出しました。",
                "errors": ["AssertionError detected"],
            }

            result = await fallback_handler.handle_analysis_failure(
                error, sample_log_content, sample_analyze_options, operation_id
            )

            assert isinstance(result, AnalysisResult)
            assert result.status == AnalysisStatus.FALLBACK
            assert "従来の分析を実行しました" in result.summary
            mock_traditional.assert_called_once_with(sample_log_content)

    @pytest.mark.asyncio
    async def test_handle_network_fallback(self, fallback_handler, sample_log_content, sample_analyze_options):
        """ネットワークエラーフォールバック処理のテスト"""
        error = NetworkError("Connection timeout")
        operation_id = "test_operation"

        with patch.object(fallback_handler, "_attempt_auto_retry") as mock_retry:
            mock_retry.return_value = None  # リトライ失敗

            with patch.object(fallback_handler, "_perform_traditional_analysis") as mock_traditional:
                mock_traditional.return_value = {
                    "summary": "Network fallback result",
                    "errors": ["Connection issues detected"],
                }

                result = await fallback_handler.handle_analysis_failure(
                    error, sample_log_content, sample_analyze_options, operation_id
                )

                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.FALLBACK
                mock_retry.assert_called_once()
                mock_traditional.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_provider_fallback(self, fallback_handler, sample_log_content, sample_analyze_options):
        """プロバイダーエラーフォールバック処理のテスト"""
        error = ProviderError("openai", "API error")
        operation_id = "test_operation"

        with patch.object(fallback_handler, "_suggest_alternative_providers") as mock_suggest:
            mock_suggest.return_value = ["anthropic", "local"]

            with patch.object(fallback_handler, "_perform_traditional_analysis") as mock_traditional:
                mock_traditional.return_value = {
                    "summary": "Provider fallback result",
                    "errors": ["Provider issues detected"],
                }

                result = await fallback_handler.handle_analysis_failure(
                    error, sample_log_content, sample_analyze_options, operation_id
                )

                assert isinstance(result, AnalysisResult)
                assert result.status == AnalysisStatus.FALLBACK
                mock_suggest.assert_called_once_with("openai")
                mock_traditional.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_generic_fallback(self, fallback_handler, sample_log_content, sample_analyze_options):
        """汎用エラーフォールバック処理のテスト"""
        error = Exception("Generic error")
        operation_id = "test_operation"

        with patch.object(fallback_handler, "_perform_traditional_analysis") as mock_traditional:
            mock_traditional.return_value = {"summary": "Generic fallback result", "errors": ["Generic error detected"]}

            result = await fallback_handler.handle_analysis_failure(
                error, sample_log_content, sample_analyze_options, operation_id
            )

            assert isinstance(result, AnalysisResult)
            assert result.status == AnalysisStatus.FALLBACK
            mock_traditional.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_auto_retry_success(self, fallback_handler, sample_log_content, sample_analyze_options):
        """自動リトライ成功のテスト"""
        error = NetworkError("Temporary network error")
        operation_id = "test_operation"

        # リトライ回数を初期化
        fallback_handler.retry_attempts[operation_id] = 0

        with patch("asyncio.sleep", new_callable=AsyncMock):
            # リトライが成功したと仮定
            with patch.object(fallback_handler, "_perform_traditional_analysis") as mock_traditional:
                mock_traditional.return_value = {"summary": "Retry successful", "errors": []}

                result = await fallback_handler._attempt_auto_retry(
                    error, sample_log_content, sample_analyze_options, operation_id
                )

                # リトライが実行されることを確認
                assert fallback_handler.retry_attempts[operation_id] == 1

    @pytest.mark.asyncio
    async def test_attempt_auto_retry_max_attempts(self, fallback_handler, sample_log_content, sample_analyze_options):
        """最大リトライ回数到達のテスト"""
        error = NetworkError("Persistent network error")
        operation_id = "test_operation"

        # 最大リトライ回数を設定
        fallback_handler.retry_attempts[operation_id] = 3

        result = await fallback_handler._attempt_auto_retry(
            error, sample_log_content, sample_analyze_options, operation_id
        )

        # リトライが実行されないことを確認
        assert result is None
        assert fallback_handler.retry_attempts[operation_id] == 3

    @pytest.mark.asyncio
    async def test_perform_traditional_analysis(self, fallback_handler, sample_log_content):
        """従来のログ分析のテスト"""
        result = await fallback_handler._perform_traditional_analysis(sample_log_content)

        assert isinstance(result, dict)
        assert "summary" in result
        assert "errors" in result
        assert "patterns" in result
        assert "suggestions" in result

        # エラーパターンが検出されることを確認
        assert len(result["errors"]) > 0
        assert any("AssertionError" in error for error in result["errors"])

    @pytest.mark.asyncio
    async def test_save_and_load_partial_result(self, fallback_handler):
        """部分的な結果の保存と読み込みのテスト"""
        operation_id = "test_save_load"
        test_data = {"partial_analysis": "Test analysis", "timestamp": datetime.now().isoformat(), "progress": 0.5}

        # 保存
        await fallback_handler._save_partial_result(operation_id, test_data)

        # 読み込み
        loaded_data = await fallback_handler.load_partial_result(operation_id)

        assert loaded_data is not None
        assert loaded_data["partial_analysis"] == test_data["partial_analysis"]
        assert loaded_data["progress"] == test_data["progress"]

    @pytest.mark.asyncio
    async def test_load_partial_result_not_found(self, fallback_handler):
        """存在しない部分的な結果の読み込みテスト"""
        result = await fallback_handler.load_partial_result("nonexistent_operation")
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_from_partial_result(self, fallback_handler):
        """部分的な結果からのリトライテスト"""
        operation_id = "test_retry"

        # 部分的な結果を保存
        partial_data = {
            "retry_info": {"last_attempt": datetime.now().isoformat(), "attempt_count": 2, "next_retry_delay": 30}
        }
        await fallback_handler._save_partial_result(operation_id, partial_data)

        # リトライ情報を取得
        retry_info = await fallback_handler.retry_from_partial_result(operation_id)

        assert retry_info is not None
        assert "retry_info" in retry_info
        assert retry_info["retry_info"]["attempt_count"] == 2

    def test_suggest_alternative_providers(self, fallback_handler):
        """代替プロバイダー提案のテスト"""
        # OpenAIが失敗した場合
        alternatives = fallback_handler._suggest_alternative_providers("openai")
        assert "anthropic" in alternatives
        assert "local" in alternatives
        assert "openai" not in alternatives

        # Anthropicが失敗した場合
        alternatives = fallback_handler._suggest_alternative_providers("anthropic")
        assert "openai" in alternatives
        assert "local" in alternatives
        assert "anthropic" not in alternatives

        # ローカルが失敗した場合
        alternatives = fallback_handler._suggest_alternative_providers("local")
        assert "openai" in alternatives
        assert "anthropic" in alternatives
        assert "local" not in alternatives

    def test_cleanup_old_partial_results(self, fallback_handler, tmp_path):
        """古い部分的な結果のクリーンアップテスト"""
        # 古いファイルを作成
        old_file = fallback_handler.fallback_dir / "old_result.json"
        old_file.write_text(json.dumps({"test": "data"}))

        # ファイルの更新時刻を古く設定
        old_time = datetime.now() - timedelta(days=10)
        old_file.touch()
        import os

        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        # 新しいファイルを作成
        new_file = fallback_handler.fallback_dir / "new_result.json"
        new_file.write_text(json.dumps({"test": "data"}))

        # クリーンアップ実行
        cleaned_count = fallback_handler.cleanup_old_partial_results(max_age_days=7)

        # 古いファイルが削除され、新しいファイルが残ることを確認
        assert cleaned_count == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_get_fallback_statistics(self, fallback_handler):
        """フォールバック統計取得のテスト"""
        # テストデータを設定
        fallback_handler.retry_attempts = {"op1": 2, "op2": 1, "op3": 3}
        fallback_handler.partial_results = {"op1": {"status": "partial"}, "op2": {"status": "complete"}}

        stats = fallback_handler.get_fallback_statistics()

        assert isinstance(stats, dict)
        assert stats["total_operations"] == 3
        assert stats["total_retries"] == 6
        assert stats["average_retries"] == 2.0
        assert stats["partial_results_count"] == 2

    def test_fallback_handler_string_representation(self, fallback_handler):
        """フォールバックハンドラーの文字列表現テスト"""
        # テストデータを設定
        fallback_handler.partial_results = {"op1": {}, "op2": {}}
        fallback_handler.retry_attempts = {"op1": 2, "op2": 1}

        str_repr = str(fallback_handler)

        assert "FallbackHandler" in str_repr
        assert "partial_results=2" in str_repr


class TestFallbackHandlerIntegration:
    """FallbackHandler統合テスト"""

    @pytest.fixture
    def fallback_handler(self, tmp_path):
        """統合テスト用フォールバックハンドラー"""
        config = Mock()
        config.get_path.return_value = tmp_path
        return FallbackHandler(config)

    @pytest.mark.asyncio
    async def test_full_fallback_workflow(self, fallback_handler):
        """完全なフォールバックワークフローのテスト"""
        log_content = "ERROR: Connection failed"
        options = AnalyzeOptions(provider="openai", model="gpt-4o")
        operation_id = "integration_test"

        # ネットワークエラーをシミュレート
        error = NetworkError("Connection timeout")

        # フォールバック処理を実行
        result = await fallback_handler.handle_analysis_failure(error, log_content, options, operation_id)

        # 結果の検証
        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.FALLBACK
        assert result.summary is not None
        assert len(result.summary) > 0

        # リトライ回数が記録されることを確認
        assert operation_id in fallback_handler.retry_attempts

    @pytest.mark.asyncio
    async def test_multiple_error_handling(self, fallback_handler):
        """複数エラーの連続処理テスト"""
        log_content = "ERROR: Multiple issues"
        options = AnalyzeOptions(provider="openai", model="gpt-4o")

        errors = [
            RateLimitError("openai", retry_after=30),
            NetworkError("Network timeout"),
            ProviderError("openai", "API error"),
            Exception("Generic error"),
        ]

        results = []
        for i, error in enumerate(errors):
            operation_id = f"multi_error_{i}"
            result = await fallback_handler.handle_analysis_failure(error, log_content, options, operation_id)
            results.append(result)

        # すべての結果がフォールバック結果であることを確認
        for result in results:
            assert isinstance(result, AnalysisResult)
            assert result.status == AnalysisStatus.FALLBACK
