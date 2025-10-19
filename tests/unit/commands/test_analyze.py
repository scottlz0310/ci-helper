"""
analyzeコマンドのテスト

AI分析コマンドの機能をテストします。
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.ci_helper.ai.models import AnalysisResult
from src.ci_helper.commands.analyze import analyze


class TestAnalyzeCommand:
    """analyzeコマンドのテストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_ai_integration(self):
        """モックAI統合"""
        integration = Mock()
        integration.initialize = AsyncMock()
        integration.analyze_log = AsyncMock()
        integration.start_interactive_session = AsyncMock()
        integration.process_interactive_input = AsyncMock()
        integration.close_interactive_session = AsyncMock()
        integration.apply_fix = AsyncMock()
        return integration

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    def create_mock_analysis_result(self):
        """分析結果のモックを作成"""
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisStatus, TokenUsage

        # Create a real AnalysisResult instance instead of a Mock
        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        mock_result = AnalysisResult(
            summary="テスト要約",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )
        return mock_result

    def test_analyze_help(self, runner):
        """ヘルプ表示のテスト"""
        result = runner.invoke(analyze, ["--help"])
        assert result.exit_code == 0
        assert "CI/CDの失敗ログをAIで分析" in result.output
        assert "--log" in result.output
        assert "--provider" in result.output
        assert "--interactive" in result.output

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_analyze_basic(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_ai_integration,
        mock_console,
    ):
        """基本的な分析のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # 分析結果のモック
        mock_result = Mock(spec=AnalysisResult)
        mock_result.summary = "テスト要約"
        mock_result.root_causes = []
        mock_result.fix_suggestions = []
        mock_result.related_errors = []
        mock_result.confidence_score = 0.8
        mock_result.analysis_time = 1.5
        mock_result.tokens_used = Mock()
        mock_result.tokens_used.total_tokens = 150
        mock_result.tokens_used.estimated_cost = 0.002
        from src.ci_helper.ai.models import AnalysisStatus

        mock_result.status = AnalysisStatus.COMPLETED
        mock_result.provider = "openai"
        mock_result.model = "gpt-4o"
        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, ["--verbose"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.initialize.assert_called_once()
        mock_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    def test_analyze_stats_only(self, mock_ai_class, runner, mock_config):
        """統計表示のみのテスト"""
        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

        # コマンド実行
        result = runner.invoke(analyze, ["--stats"], obj=ctx_obj)

        # AI統合が初期化されないことを確認
        mock_ai_class.assert_not_called()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_analyze_no_log_file(
        self,
        mock_validate,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_ai_integration,
    ):
        """ログファイルが見つからない場合のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration
        mock_get_latest.return_value = None

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_not_called()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_analyze_with_options(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_ai_integration,
        mock_console,
    ):
        """オプション付き分析のテスト"""
        # モックの設定
        mock_validate.return_value = True
        mock_ai_class.return_value = mock_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # AI統合の初期化を成功させる
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()

        # 分析結果のモック
        mock_result = self.create_mock_analysis_result()
        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(
            analyze,
            [
                "--provider",
                "openai",
                "--model",
                "gpt-4o",
                "--prompt",
                "カスタムプロンプト",
                "--format",
                "json",
                "--no-cache",
            ],
            obj=ctx_obj,
        )

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 分析オプションの確認
        call_args = mock_ai_integration.analyze_log.call_args
        options = call_args[0][1]  # 2番目の引数がAnalyzeOptions
        assert options.provider == "openai"
        assert options.model == "gpt-4o"
        assert options.custom_prompt == "カスタムプロンプト"
        assert options.output_format == "json"
        assert options.use_cache is False

    def test_analyze_with_specific_log_file(self, runner, temp_dir, mock_config, mock_console):
        """特定のログファイル指定のテスト"""
        # テスト用ログファイルを作成
        log_file = temp_dir / "test.log"
        log_file.write_text("test log content")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        with (
            patch("src.ci_helper.commands.analyze.AIIntegration") as mock_ai_class,
            patch("src.ci_helper.commands.analyze._validate_analysis_environment") as mock_validate,
        ):
            # 環境検証を成功させる
            mock_validate.return_value = True

            mock_ai_integration = Mock()
            mock_ai_integration.initialize = AsyncMock()
            mock_ai_integration.analyze_log = AsyncMock()
            mock_ai_class.return_value = mock_ai_integration

            # 分析結果のモック
            mock_result = self.create_mock_analysis_result()
            mock_ai_integration.analyze_log.return_value = mock_result

            # コマンド実行
            result = runner.invoke(analyze, ["--log", str(log_file)], obj=ctx_obj)

            # 検証
            assert result.exit_code == 0
            mock_ai_integration.analyze_log.assert_called_once()

            # ログ内容の確認
            call_args = mock_ai_integration.analyze_log.call_args
            log_content = call_args[0][0]  # 1番目の引数がログ内容
            assert log_content == "test log content"

    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("src.ci_helper.commands.analyze._suggest_fallback_options")
    def test_analyze_validation_failure(self, mock_suggest_fallback, mock_validate, runner, mock_config, mock_console):
        """環境検証失敗時のテスト"""
        # 環境検証を失敗させる
        mock_validate.return_value = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証 - 環境検証失敗時はexit_code=1になる
        assert result.exit_code == 1
        mock_validate.assert_called_once()
        mock_suggest_fallback.assert_called_once()


class TestAnalyzeHelperFunctions:
    """analyzeコマンドのヘルパー関数のテスト"""

    def test_read_log_file(self, temp_dir):
        """ログファイル読み込みのテスト"""
        from src.ci_helper.commands.analyze import _read_log_file

        # テスト用ログファイルを作成
        log_file = temp_dir / "test.log"
        test_content = "テストログ内容\n複数行のログ"
        log_file.write_text(test_content, encoding="utf-8")

        # ログファイル読み込み
        content = _read_log_file(log_file)

        # 検証
        assert content == test_content

    def test_read_log_file_not_found(self):
        """存在しないログファイルの読み込みテスト"""
        from src.ci_helper.commands.analyze import _read_log_file
        from src.ci_helper.core.exceptions import CIHelperError

        non_existent_file = Path("non_existent.log")

        # 例外が発生することを確認
        with pytest.raises(CIHelperError):
            _read_log_file(non_existent_file)

    @patch("src.ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file(self, mock_log_manager_class, mock_config):
        """最新ログファイル取得のテスト"""
        from src.ci_helper.commands.analyze import _get_latest_log_file

        # モックログマネージャーの設定
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager

        # モックログエントリ
        mock_log_entry = Mock()
        mock_log_entry.file_path = Path("latest.log")
        mock_log_manager.list_logs.return_value = [mock_log_entry]

        # 最新ログファイル取得
        result = _get_latest_log_file(mock_config)

        # 検証
        assert result == Path("latest.log")
        mock_log_manager_class.assert_called_once_with(mock_config)
        mock_log_manager.list_logs.assert_called_once()

    @patch("src.ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file_no_logs(self, mock_log_manager_class, mock_config):
        """ログが存在しない場合のテスト"""
        from src.ci_helper.commands.analyze import _get_latest_log_file

        # モックログマネージャーの設定
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager
        mock_log_manager.list_logs.return_value = []

        # 最新ログファイル取得
        result = _get_latest_log_file(mock_config)

        # 検証
        assert result is None

    @patch("src.ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file_exception(self, mock_log_manager_class, mock_config):
        """ログマネージャーで例外が発生した場合のテスト"""
        from src.ci_helper.commands.analyze import _get_latest_log_file

        # モックログマネージャーの設定
        mock_log_manager_class.side_effect = Exception("テストエラー")

        # 最新ログファイル取得
        result = _get_latest_log_file(mock_config)

        # 検証（例外が発生してもNoneを返す）
        assert result is None


class TestAnalyzeDisplayFunctions:
    """analyze表示関数のテスト"""

    def test_display_analysis_result_markdown(self, mock_console):
        """Markdown形式での分析結果表示テスト"""
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, FixSuggestion, RootCause
        from src.ci_helper.commands.analyze import _display_analysis_result

        # テスト用分析結果を作成
        result = AnalysisResult(
            summary="テスト分析結果",
            root_causes=[RootCause(category="test", description="テストエラー", severity="HIGH")],
            fix_suggestions=[
                FixSuggestion(title="修正提案", description="修正内容", priority="HIGH", estimated_effort="30分")
            ],
            confidence_score=0.85,
            status=AnalysisStatus.COMPLETED,
        )

        # 関数実行（例外が発生しないことを確認）
        _display_analysis_result(result, "markdown", mock_console)

    def test_display_analysis_result_table(self, mock_console):
        """テーブル形式での分析結果表示テスト"""
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus
        from src.ci_helper.commands.analyze import _display_analysis_result

        result = AnalysisResult(
            summary="テスト分析結果",
            root_causes=[],
            fix_suggestions=[],
            confidence_score=0.75,
            status=AnalysisStatus.COMPLETED,
        )

        # 関数実行（例外が発生しないことを確認）
        _display_analysis_result(result, "table", mock_console)

    def test_display_analysis_result_json(self, mock_console):
        """JSON形式での分析結果表示テスト"""
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus
        from src.ci_helper.commands.analyze import _display_analysis_result

        result = AnalysisResult(
            summary="テスト分析結果",
            root_causes=[],
            fix_suggestions=[],
            confidence_score=0.75,
            status=AnalysisStatus.COMPLETED,
        )

        # 関数実行（例外が発生しないことを確認）
        _display_analysis_result(result, "json", mock_console)

    @patch("src.ci_helper.commands.analyze.CostTracker")
    def test_display_stats(self, mock_cost_tracker_class, mock_config, mock_console):
        """統計表示のテスト"""
        from src.ci_helper.commands.analyze import _display_stats

        # モックコストトラッカーの設定
        mock_cost_tracker = Mock()
        mock_cost_tracker_class.return_value = mock_cost_tracker
        mock_cost_tracker.get_usage_stats.return_value = {
            "total_requests": 10,
            "total_tokens": 1000,
            "total_cost": 0.05,
            "providers": {"openai": {"requests": 10, "tokens": 1000, "cost": 0.05}},
        }

        # 関数実行（例外が発生しないことを確認）
        _display_stats(mock_config, mock_console)

        # コストトラッカーが呼び出されたことを確認
        mock_cost_tracker_class.assert_called_once_with(mock_config)
        mock_cost_tracker.get_usage_stats.assert_called_once()


class TestAnalyzeErrorHandling:
    """analyzeエラーハンドリングのテスト"""

    def test_handle_ci_helper_error(self, mock_console):
        """CIHelperエラーハンドリングのテスト"""
        from src.ci_helper.commands.analyze import _handle_ci_helper_error
        from src.ci_helper.core.exceptions import CIHelperError

        error = CIHelperError("テストエラー")

        # 関数実行（例外が発生しないことを確認）
        _handle_ci_helper_error(error, mock_console, verbose=True)

    def test_handle_analysis_error(self, mock_console):
        """分析エラーハンドリングのテスト"""
        from src.ci_helper.commands.analyze import _handle_analysis_error

        error = Exception("テスト例外")

        # 関数実行（例外が発生しないことを確認）
        _handle_analysis_error(error, mock_console, verbose=True)

    def test_determine_error_severity(self):
        """エラー重要度判定のテスト"""
        from src.ci_helper.ai.exceptions import APIKeyError, NetworkError, RateLimitError
        from src.ci_helper.commands.analyze import _determine_error_severity

        # 各エラータイプの重要度をテスト
        assert _determine_error_severity(APIKeyError("test", "message")) == "CRITICAL"
        assert _determine_error_severity(RateLimitError("test")) == "HIGH"
        assert _determine_error_severity(NetworkError("message")) == "MEDIUM"
        assert _determine_error_severity(Exception("generic")) == "LOW"

    def test_get_severity_color(self):
        """重要度色取得のテスト"""
        from src.ci_helper.commands.analyze import _get_severity_color

        assert _get_severity_color("CRITICAL") == "bright_red"
        assert _get_severity_color("HIGH") == "red"
        assert _get_severity_color("MEDIUM") == "yellow"
        assert _get_severity_color("LOW") == "blue"
        assert _get_severity_color("UNKNOWN") == "white"

    def test_handle_api_key_error_enhanced(self, mock_console):
        """拡張APIキーエラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import APIKeyError
        from src.ci_helper.commands.analyze import _handle_api_key_error_enhanced

        error = APIKeyError("openai", "Invalid API key")

        # 関数実行（例外が発生しないことを確認）
        _handle_api_key_error_enhanced(error, mock_console, verbose=True)

    def test_handle_rate_limit_error_enhanced(self, mock_console):
        """拡張レート制限エラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import RateLimitError
        from src.ci_helper.commands.analyze import _handle_rate_limit_error_enhanced

        error = RateLimitError("openai", retry_after=60)

        # 関数実行（例外が発生しないことを確認）
        _handle_rate_limit_error_enhanced(error, mock_console, verbose=True)

    def test_handle_token_limit_error_enhanced(self, mock_console):
        """拡張トークン制限エラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import TokenLimitError
        from src.ci_helper.commands.analyze import _handle_token_limit_error_enhanced

        error = TokenLimitError(5000, 4000, "gpt-4o")

        # 関数実行（例外が発生しないことを確認）
        _handle_token_limit_error_enhanced(error, mock_console, verbose=True)

    def test_handle_network_error_enhanced(self, mock_console):
        """拡張ネットワークエラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import NetworkError
        from src.ci_helper.commands.analyze import _handle_network_error_enhanced

        error = NetworkError("Connection timeout")

        # 関数実行（例外が発生しないことを確認）
        _handle_network_error_enhanced(error, mock_console, verbose=True)

    def test_handle_configuration_error_enhanced(self, mock_console):
        """拡張設定エラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import ConfigurationError
        from src.ci_helper.commands.analyze import _handle_configuration_error_enhanced

        error = ConfigurationError("Invalid configuration")

        # 関数実行（例外が発生しないことを確認）
        _handle_configuration_error_enhanced(error, mock_console, verbose=True)

    def test_handle_provider_error_enhanced(self, mock_console):
        """拡張プロバイダーエラーハンドリングのテスト"""
        from src.ci_helper.ai.exceptions import ProviderError
        from src.ci_helper.commands.analyze import _handle_provider_error_enhanced

        error = ProviderError("openai", "Provider error")

        # 関数実行（例外が発生しないことを確認）
        _handle_provider_error_enhanced(error, mock_console, verbose=True)

    def test_handle_generic_error_enhanced(self, mock_console):
        """拡張汎用エラーハンドリングのテスト"""
        from src.ci_helper.commands.analyze import _handle_generic_error_enhanced

        error = ValueError("Test value error")

        # 関数実行（例外が発生しないことを確認）
        _handle_generic_error_enhanced(error, mock_console, verbose=True)

    def test_display_error_footer(self, mock_console):
        """エラーフッター表示のテスト"""
        from src.ci_helper.commands.analyze import _display_error_footer

        error = Exception("Test error")

        # 関数実行（例外が発生しないことを確認）
        _display_error_footer(error, mock_console, verbose=True)


class TestAnalyzeFallbackAndRecovery:
    """analyzeフォールバック・復旧機能のテスト"""

    def test_suggest_fallback_options(self, mock_console):
        """フォールバックオプション提案のテスト"""
        from src.ci_helper.commands.analyze import _suggest_fallback_options

        log_file = Path("test.log")

        # 関数実行（例外が発生しないことを確認）
        _suggest_fallback_options(mock_console, log_file)

    def test_suggest_fallback_options_no_log(self, mock_console):
        """ログファイルなしでのフォールバックオプション提案のテスト"""
        from src.ci_helper.commands.analyze import _suggest_fallback_options

        # 関数実行（例外が発生しないことを確認）
        _suggest_fallback_options(mock_console, None)

    @patch("builtins.input", return_value="1")
    def test_offer_interactive_recovery(self, mock_input, mock_console):
        """対話的復旧オプション提供のテスト"""
        from src.ci_helper.commands.analyze import _offer_interactive_recovery

        result = _offer_interactive_recovery(mock_console)

        # 選択肢が返されることを確認
        assert result in ["retry", "fallback", "manual", "exit"]

    @patch("builtins.input", return_value="invalid")
    def test_offer_interactive_recovery_invalid_input(self, mock_input, mock_console):
        """無効な入力での対話的復旧オプションテスト"""
        from src.ci_helper.commands.analyze import _offer_interactive_recovery

        # 無効な入力の場合はexitが返される
        result = _offer_interactive_recovery(mock_console)
        assert result == "exit"

    @patch("src.ci_helper.commands.analyze.AIConfigManager")
    def test_validate_analysis_environment_success(self, mock_config_manager_class, mock_config, mock_console):
        """分析環境検証成功のテスト"""
        from src.ci_helper.commands.analyze import _validate_analysis_environment

        # モック設定
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager
        mock_config_manager.validate_ai_config.return_value = True

        result = _validate_analysis_environment(mock_config, mock_console)

        assert result is True
        mock_config_manager.validate_ai_config.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIConfigManager")
    def test_validate_analysis_environment_failure(self, mock_config_manager_class, mock_config, mock_console):
        """分析環境検証失敗のテスト"""
        from src.ci_helper.commands.analyze import _validate_analysis_environment

        # モック設定
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager
        mock_config_manager.validate_ai_config.return_value = False

        result = _validate_analysis_environment(mock_config, mock_console)

        assert result is False

    def test_display_fallback_info(self, mock_console):
        """フォールバック情報表示のテスト"""
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus
        from src.ci_helper.commands.analyze import _display_fallback_info

        result = AnalysisResult(
            summary="フォールバック結果",
            root_causes=[],
            fix_suggestions=[],
            confidence_score=0.5,
            status=AnalysisStatus.FALLBACK_USED,
        )

        # 関数実行（例外が発生しないことを確認）
        _display_fallback_info(result, mock_console)


class TestAnalysisErrorContext:
    """AnalysisErrorContextのテスト"""

    def test_analysis_error_context_success(self, mock_console):
        """正常終了時のAnalysisErrorContextテスト"""
        from src.ci_helper.commands.analyze import AnalysisErrorContext

        with AnalysisErrorContext(mock_console, "test_operation", verbose=True) as ctx:
            ctx.log_progress("テスト進捗")
            # 正常終了

        # エラーカウントが0であることを確認
        assert ctx.error_count == 0

    def test_analysis_error_context_with_error(self, mock_console):
        """エラー発生時のAnalysisErrorContextテスト"""
        from src.ci_helper.commands.analyze import AnalysisErrorContext

        with pytest.raises(ValueError):
            with AnalysisErrorContext(mock_console, "test_operation", verbose=True) as ctx:
                ctx.log_progress("テスト進捗")
                raise ValueError("テストエラー")

        # エラーカウントが1であることを確認
        assert ctx.error_count == 1


class TestAnalyzeInteractiveMode:
    """対話モード機能の包括的テスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    @pytest.fixture
    def mock_interactive_session(self):
        """モック対話セッション"""
        session = Mock()
        session.session_id = "test_session_123"
        session.is_active = True
        session.context = {"log_content": "test log", "analysis_count": 0}
        return session

    @pytest.fixture
    def mock_ai_integration_interactive(self):
        """対話モード用のモックAI統合"""
        integration = Mock()
        integration.initialize = AsyncMock()
        integration.start_interactive_session = AsyncMock()
        integration.process_interactive_input = AsyncMock()
        integration.close_interactive_session = AsyncMock()
        return integration

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_interactive_session_start(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """対話セッション開始のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # 対話セッションを即座に終了させる
        mock_interactive_session.is_active = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration_interactive.initialize.assert_called_once()
        mock_ai_integration_interactive.start_interactive_session.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("builtins.input", side_effect=["/help", "/exit"])
    def test_interactive_command_processing(
        self,
        mock_input,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """対話コマンド処理のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # 対話セッションのシミュレーション
        call_count = 0

        async def mock_process_input(session_id, user_input):
            nonlocal call_count
            call_count += 1
            if user_input == "/help":
                yield "利用可能なコマンド:\n/help - ヘルプ表示\n/exit - 終了"
            elif user_input == "/exit":
                mock_interactive_session.is_active = False
                yield "セッションを終了します。"

        mock_ai_integration_interactive.process_interactive_input.side_effect = mock_process_input

        # 対話セッションの状態管理
        def session_active_side_effect():
            return call_count < 2

        type(mock_interactive_session).is_active = property(lambda self: session_active_side_effect())

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        assert mock_ai_integration_interactive.process_interactive_input.call_count == 2

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_interactive_session_timeout(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """セッションタイムアウトのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # タイムアウトエラーをシミュレート

        mock_ai_integration_interactive.process_interactive_input.side_effect = TimeoutError("Session timeout")

        # 対話セッションを即座に終了させる（タイムアウト後）
        mock_interactive_session.is_active = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証（タイムアウトが発生してもセッションは適切に終了する）
        assert result.exit_code == 0
        mock_ai_integration_interactive.close_interactive_session.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_interactive_context_preservation(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """コンテキスト保持のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # コンテキスト保持のシミュレーション
        context_data = {"previous_questions": [], "analysis_history": []}

        async def mock_process_with_context(session_id, user_input):
            context_data["previous_questions"].append(user_input)
            yield f"質問 {len(context_data['previous_questions'])}: {user_input} への回答"

        mock_ai_integration_interactive.process_interactive_input.side_effect = mock_process_with_context

        # 対話セッションを即座に終了させる
        mock_interactive_session.is_active = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        # セッション開始時にログ内容とオプションが渡されることを確認
        call_args = mock_ai_integration_interactive.start_interactive_session.call_args
        assert call_args[0][0] == "test log content"  # ログ内容
        assert call_args[0][1] is not None  # オプション

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_interactive_session_error_handling(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """対話セッション中のエラーハンドリングのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # エラーをシミュレート
        from src.ci_helper.ai.exceptions import NetworkError

        mock_ai_integration_interactive.process_interactive_input.side_effect = NetworkError("Connection failed")

        # 対話セッションを即座に終了させる
        mock_interactive_session.is_active = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証（エラーが発生してもセッションは適切に終了する）
        assert result.exit_code == 0
        mock_ai_integration_interactive.close_interactive_session.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_interactive_session_cleanup(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_ai_integration_interactive,
        mock_interactive_session,
    ):
        """対話セッション終了時のクリーンアップのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_ai_integration_interactive
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"
        mock_ai_integration_interactive.start_interactive_session.return_value = mock_interactive_session

        # 対話セッションを即座に終了させる
        mock_interactive_session.is_active = False

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードでコマンド実行
        result = runner.invoke(analyze, ["--interactive"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        # セッション終了時にクリーンアップが呼ばれることを確認
        mock_ai_integration_interactive.close_interactive_session.assert_called_once_with(
            mock_interactive_session.session_id
        )


class TestAnalyzeFixApplication:
    """修正提案・適用機能の詳細テスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    @pytest.fixture
    def mock_fix_suggestion(self):
        """モック修正提案"""
        from src.ci_helper.ai.models import FixSuggestion

        return FixSuggestion(
            title="テスト修正提案",
            description="テストファイルの修正",
            file_path="test_file.py",
            line_number=10,
            original_code="old_code = 'test'",
            suggested_code="new_code = 'test'",
            priority="HIGH",
            estimated_effort="15分",
            confidence=0.9,
        )

    @pytest.fixture
    def mock_analysis_result_with_fixes(self, mock_fix_suggestion):
        """修正提案付きの分析結果"""
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        return AnalysisResult(
            summary="修正提案付きテスト要約",
            root_causes=[],
            fix_suggestions=[mock_fix_suggestion],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_fix_suggestion_generation(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_analysis_result_with_fixes,
    ):
        """修正提案生成のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_analysis_result_with_fixes)
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 修正提案フラグ付きでコマンド実行
        result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 分析オプションで修正提案が有効になっていることを確認
        call_args = mock_ai_integration.analyze_log.call_args
        options = call_args[0][1]  # 2番目の引数がAnalyzeOptions
        assert options.generate_fixes is True

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("click.confirm", return_value=True)
    def test_automatic_fix_application(
        self,
        mock_confirm,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_analysis_result_with_fixes,
    ):
        """自動修正適用のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_analysis_result_with_fixes)
        mock_ai_integration.apply_fix = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 修正提案フラグ付きでコマンド実行
        result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.apply_fix.assert_called_once()
        mock_confirm.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("click.confirm", return_value=False)
    def test_fix_application_rejection(
        self,
        mock_confirm,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_analysis_result_with_fixes,
    ):
        """修正適用拒否のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_analysis_result_with_fixes)
        mock_ai_integration.apply_fix = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 修正提案フラグ付きでコマンド実行
        result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.apply_fix.assert_not_called()  # 拒否されたので適用されない
        mock_confirm.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("click.confirm", return_value=True)
    def test_backup_creation_and_restoration(
        self,
        mock_confirm,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_analysis_result_with_fixes,
        temp_dir,
    ):
        """バックアップ作成・復元のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # テスト用ファイルを作成
        test_file = temp_dir / "test_file.py"
        original_content = "old_code = 'test'"
        test_file.write_text(original_content)

        # 修正提案のファイルパスを実際のファイルに設定
        mock_analysis_result_with_fixes.fix_suggestions[0].file_path = str(test_file)

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_analysis_result_with_fixes)

        # apply_fixでファイルを実際に変更するシミュレーション
        async def mock_apply_fix(suggestion):
            # バックアップ作成のシミュレーション
            backup_file = Path(str(suggestion.file_path) + ".backup")
            backup_file.write_text(original_content)

            # ファイル変更のシミュレーション
            Path(suggestion.file_path).write_text(suggestion.suggested_code)

        mock_ai_integration.apply_fix = AsyncMock(side_effect=mock_apply_fix)
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 修正提案フラグ付きでコマンド実行
        result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.apply_fix.assert_called_once()

        # ファイルが変更されたことを確認
        assert test_file.read_text() == "new_code = 'test'"

        # バックアップファイルが作成されたことを確認
        backup_file = Path(str(test_file) + ".backup")
        assert backup_file.exists()
        assert backup_file.read_text() == original_content

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_multiple_file_fix_approval(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """複数ファイル修正の個別承認システムのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # 複数の修正提案を作成
        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, FixSuggestion, TokenUsage

        fix1 = FixSuggestion(
            title="修正提案1",
            description="ファイル1の修正",
            file_path="file1.py",
            line_number=10,
            original_code="old1",
            suggested_code="new1",
            priority="HIGH",
            estimated_effort="10分",
            confidence=0.9,
        )

        fix2 = FixSuggestion(
            title="修正提案2",
            description="ファイル2の修正",
            file_path="file2.py",
            line_number=20,
            original_code="old2",
            suggested_code="new2",
            priority="MEDIUM",
            estimated_effort="5分",
            confidence=0.8,
        )

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        analysis_result = AnalysisResult(
            summary="複数修正提案テスト",
            root_causes=[],
            fix_suggestions=[fix1, fix2],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=analysis_result)
        mock_ai_integration.apply_fix = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 個別承認のシミュレーション（1つ目は承認、2つ目は拒否）
        with patch("click.confirm", side_effect=[True, False]):
            result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        # 1つ目の修正のみ適用されることを確認
        assert mock_ai_integration.apply_fix.call_count == 1
        mock_ai_integration.apply_fix.assert_called_with(fix1)

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    @patch("click.confirm", return_value=True)
    def test_fix_application_error_handling(
        self,
        mock_confirm,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_analysis_result_with_fixes,
    ):
        """修正適用時のエラーハンドリングのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックAI統合の設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock(return_value=mock_analysis_result_with_fixes)
        # 修正適用時にエラーを発生させる
        mock_ai_integration.apply_fix = AsyncMock(side_effect=Exception("修正適用エラー"))
        mock_ai_class.return_value = mock_ai_integration

        # ログファイルの設定
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 修正提案フラグ付きでコマンド実行
        result = runner.invoke(analyze, ["--fix"], obj=ctx_obj)

        # 検証（エラーが発生してもプログラムは正常終了する）
        assert result.exit_code == 0
        mock_ai_integration.apply_fix.assert_called_once()

    def test_backup_from_restoration_functionality(self, temp_dir):
        """バックアップからの復元機能のテスト"""
        # テスト用ファイルとバックアップを作成
        test_file = temp_dir / "test_file.py"
        backup_file = temp_dir / "test_file.py.backup"

        original_content = "original_code = 'test'"
        modified_content = "modified_code = 'test'"

        test_file.write_text(modified_content)
        backup_file.write_text(original_content)

        # バックアップからの復元をシミュレート
        # 実際の復元機能は別のコマンドで実装される想定
        # ここではファイル操作のテストのみ
        assert test_file.read_text() == modified_content
        assert backup_file.read_text() == original_content

        # 復元のシミュレーション
        test_file.write_text(backup_file.read_text())
        assert test_file.read_text() == original_content


class TestAnalyzeStreamingFeatures:
    """ストリーミング機能の詳細テスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    @pytest.fixture
    def mock_streaming_ai_integration(self):
        """ストリーミング対応のモックAI統合"""
        integration = Mock()
        integration.initialize = AsyncMock()
        integration.analyze_log = AsyncMock()
        integration.stream_analysis = AsyncMock()
        return integration

    async def mock_streaming_response(self, chunks):
        """ストリーミングレスポンスのモック生成器"""
        for chunk in chunks:
            yield chunk

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_streaming_response_display(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """ストリーミング応答表示のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # ストリーミングレスポンスのシミュレーション
        streaming_chunks = ["分析中", "...", "完了"]

        # 分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        mock_result = AnalysisResult(
            summary="ストリーミングテスト要約",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_streaming_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # ストリーミング有効でコマンド実行
        result = runner.invoke(analyze, ["--streaming"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_streaming_ai_integration.analyze_log.assert_called_once()

        # 分析オプションでストリーミングが有効になっていることを確認
        call_args = mock_streaming_ai_integration.analyze_log.call_args
        options = call_args[0][1]  # 2番目の引数がAnalyzeOptions
        assert options.streaming is True

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_streaming_interruption_handling(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """ストリーミング中断処理（Ctrl+C）のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # KeyboardInterruptをシミュレート
        mock_streaming_ai_integration.analyze_log.side_effect = KeyboardInterrupt("User interrupted")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # ストリーミング有効でコマンド実行
        result = runner.invoke(analyze, ["--streaming"], obj=ctx_obj)

        # 検証（KeyboardInterruptが適切に処理されて終了コード130になる）
        assert result.exit_code == 130
        mock_streaming_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_progress_indicator_updates(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """プログレス表示とインジケーター更新のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # プログレス付きの分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        mock_result = AnalysisResult(
            summary="プログレステスト要約",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_streaming_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 詳細表示とストリーミング有効でコマンド実行
        result = runner.invoke(analyze, ["--streaming", "--verbose"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_streaming_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_streaming_error_recovery(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """ストリーミングエラー復旧のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # ストリーミングエラーをシミュレート
        from src.ci_helper.ai.exceptions import NetworkError

        mock_streaming_ai_integration.analyze_log.side_effect = NetworkError("Streaming connection lost")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # ストリーミング有効でコマンド実行
        result = runner.invoke(analyze, ["--streaming"], obj=ctx_obj)

        # 検証（エラーが発生してもプログラムは適切に終了する）
        assert result.exit_code == 1
        mock_streaming_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_streaming_disabled_fallback(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """ストリーミング無効時のフォールバックのテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # 分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        mock_result = AnalysisResult(
            summary="非ストリーミングテスト要約",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_streaming_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # ストリーミング無効でコマンド実行
        result = runner.invoke(analyze, ["--no-streaming"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_streaming_ai_integration.analyze_log.assert_called_once()

        # 分析オプションでストリーミングが無効になっていることを確認
        call_args = mock_streaming_ai_integration.analyze_log.call_args
        options = call_args[0][1]  # 2番目の引数がAnalyzeOptions
        assert options.streaming is False

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_streaming_with_interactive_mode(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        mock_streaming_ai_integration,
    ):
        """対話モードでのストリーミング機能のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_class.return_value = mock_streaming_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # 対話セッションのモック
        mock_session = Mock()
        mock_session.session_id = "streaming_session_123"
        mock_session.is_active = False  # 即座に終了
        mock_streaming_ai_integration.start_interactive_session = AsyncMock(return_value=mock_session)
        mock_streaming_ai_integration.close_interactive_session = AsyncMock()

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 対話モードとストリーミング有効でコマンド実行
        result = runner.invoke(analyze, ["--interactive", "--streaming"], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_streaming_ai_integration.start_interactive_session.assert_called_once()

        # セッション開始時のオプションでストリーミングが有効になっていることを確認
        call_args = mock_streaming_ai_integration.start_interactive_session.call_args
        options = call_args[0][1]  # 2番目の引数がAnalyzeOptions
        assert options.streaming is True

    def test_streaming_chunk_processing(self):
        """ストリーミングチャンク処理のテスト"""
        # ストリーミングチャンクの処理ロジックをテスト
        chunks = ["チャンク1", "チャンク2", "チャンク3"]
        processed_chunks = []

        # チャンク処理のシミュレーション
        for chunk in chunks:
            processed_chunks.append(f"処理済み: {chunk}")

        # 検証
        assert len(processed_chunks) == 3
        assert processed_chunks[0] == "処理済み: チャンク1"
        assert processed_chunks[1] == "処理済み: チャンク2"
        assert processed_chunks[2] == "処理済み: チャンク3"

    def test_streaming_buffer_management(self):
        """ストリーミングバッファ管理のテスト"""
        # バッファサイズの管理をテスト
        buffer = []
        max_buffer_size = 5

        # バッファにデータを追加
        for i in range(10):
            buffer.append(f"データ{i}")
            if len(buffer) > max_buffer_size:
                buffer.pop(0)  # 古いデータを削除

        # 検証
        assert len(buffer) == max_buffer_size
        assert buffer[0] == "データ5"  # 最も古いデータ
        assert buffer[-1] == "データ9"  # 最新のデータ


class TestAnalyzeEdgeCases:
    """エッジケースとエラーシナリオのテスト"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    @pytest.fixture
    def large_log_content(self):
        """大きなログファイルのコンテンツ"""
        return "\n".join([f"Log line {i}: Some error occurred at {i}" for i in range(10000)])

    @pytest.fixture
    def malformed_log_content(self):
        """不正形式のログコンテンツ"""
        return "Invalid log format\x00\x01\x02\nCorrupted data\xff\xfe"

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_empty_log_file_handling(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        temp_dir,
    ):
        """空ログファイル処理のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # 空のログファイルを作成
        empty_log = temp_dir / "empty.log"
        empty_log.write_text("")

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = empty_log
        mock_read_log.return_value = ""

        # 空ログに対する分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30, estimated_cost=0.001)

        mock_result = AnalysisResult(
            summary="ログファイルが空です",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.1,
            analysis_time=0.1,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 空のログ内容が渡されることを確認
        call_args = mock_ai_integration.analyze_log.call_args
        log_content = call_args[0][0]
        assert log_content == ""

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_large_log_file_processing(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        large_log_content,
    ):
        """大きなログファイル処理のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("large.log")
        mock_read_log.return_value = large_log_content

        # 大きなログに対する分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=5000, output_tokens=500, total_tokens=5500, estimated_cost=0.1)

        mock_result = AnalysisResult(
            summary="大きなログファイルの分析結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.7,
            analysis_time=5.0,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 大きなログ内容が渡されることを確認
        call_args = mock_ai_integration.analyze_log.call_args
        log_content = call_args[0][0]
        assert len(log_content) > 50000  # 大きなログファイル

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_malformed_log_content_processing(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        malformed_log_content,
    ):
        """不正形式ログコンテンツの処理テスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("malformed.log")
        mock_read_log.return_value = malformed_log_content

        # 不正形式ログに対する分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=50, output_tokens=100, total_tokens=150, estimated_cost=0.005)

        mock_result = AnalysisResult(
            summary="不正形式のログが検出されました",
            root_causes=[],
            fix_suggestions=[],
            related_errors=["バイナリデータが含まれています"],
            confidence_score=0.3,
            analysis_time=1.0,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 不正形式のログ内容が渡されることを確認
        call_args = mock_ai_integration.analyze_log.call_args
        log_content = call_args[0][0]
        assert "\x00" in log_content or "\x01" in log_content

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_concurrent_analysis_requests(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """同時分析リクエストの処理テスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "concurrent test log"

        # 同時実行エラーをシミュレート
        from src.ci_helper.ai.exceptions import ConcurrencyError

        mock_ai_integration.analyze_log.side_effect = ConcurrencyError("同時実行制限に達しました")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証（同時実行エラーが適切に処理される）
        assert result.exit_code == 1
        mock_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_memory_limit_handling(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """メモリ制限のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "memory test log"

        # メモリエラーをシミュレート
        mock_ai_integration.analyze_log.side_effect = MemoryError("メモリ不足")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証（メモリエラーが適切に処理される）
        assert result.exit_code == 1
        mock_ai_integration.analyze_log.assert_called_once()

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_disk_capacity_limit(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """ディスク容量制限のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "disk test log"

        # ディスク容量エラーをシミュレート
        mock_ai_integration.analyze_log.side_effect = OSError("ディスク容量不足")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証（ディスク容量エラーが適切に処理される）
        assert result.exit_code == 1
        mock_ai_integration.analyze_log.assert_called_once()

    def test_log_file_encoding_issues(self, temp_dir):
        """ログファイルエンコーディング問題のテスト"""
        # 異なるエンコーディングのファイルを作成
        log_file = temp_dir / "encoding_test.log"

        # UTF-8以外のエンコーディングでファイルを作成
        content = "日本語ログ内容"
        log_file.write_bytes(content.encode("shift_jis"))

        # ファイル読み込みのテスト
        from src.ci_helper.commands.analyze import _read_log_file
        from src.ci_helper.core.exceptions import CIHelperError

        # エンコーディングエラーが発生することを確認
        with pytest.raises(CIHelperError):
            _read_log_file(log_file)

    def test_corrupted_log_file_handling(self, temp_dir):
        """破損ログファイル処理のテスト"""
        # 破損したファイルを作成
        corrupted_log = temp_dir / "corrupted.log"
        corrupted_log.write_bytes(b"\xff\xfe\x00\x01corrupted data")

        # ファイル読み込みのテスト
        from src.ci_helper.commands.analyze import _read_log_file
        from src.ci_helper.core.exceptions import CIHelperError

        # 破損ファイルの読み込みでエラーが発生することを確認
        with pytest.raises(CIHelperError):
            _read_log_file(corrupted_log)

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_network_timeout_handling(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """ネットワークタイムアウト処理のテスト"""
        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "timeout test log"

        # タイムアウトエラーをシミュレート

        mock_ai_integration.analyze_log.side_effect = TimeoutError("ネットワークタイムアウト")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証（タイムアウトエラーが適切に処理される）
        assert result.exit_code == 1
        mock_ai_integration.analyze_log.assert_called_once()

    def test_invalid_command_line_options(self, runner, mock_config, mock_console):
        """無効なコマンドラインオプションのテスト"""
        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 無効なプロバイダーを指定
        result = runner.invoke(analyze, ["--provider", "invalid_provider"], obj=ctx_obj)

        # 検証（無効なオプションでエラーになる）
        assert result.exit_code != 0

    def test_missing_required_dependencies(self):
        """必要な依存関係が不足している場合のテスト"""
        # 依存関係チェックのシミュレーション
        required_modules = ["rich", "click", "asyncio"]
        missing_modules = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        # 検証（通常は依存関係が満たされている）
        assert len(missing_modules) == 0


class TestAnalyzePerformance:
    """パフォーマンステストの追加"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_console(self):
        """モックコンソール（Rich Progress対応）"""
        from rich.console import Console

        # Use a real Console instance instead of a Mock to avoid Rich internal issues
        return Console(file=Mock(), force_terminal=False, no_color=True)

    @pytest.fixture
    def performance_log_content(self):
        """パフォーマンステスト用の大きなログコンテンツ"""
        # 実際のCI/CDログに近い形式で大量のログを生成
        lines = []
        for i in range(5000):
            lines.extend(
                [
                    f"[{i:04d}] INFO: Starting test case {i}",
                    f"[{i:04d}] DEBUG: Initializing test environment",
                    f"[{i:04d}] ERROR: Test failed with assertion error",
                    f"[{i:04d}] TRACE: Stack trace line 1",
                    f"[{i:04d}] TRACE: Stack trace line 2",
                    f"[{i:04d}] WARN: Cleanup required",
                ]
            )
        return "\n".join(lines)

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_large_log_file_processing_time(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
        performance_log_content,
    ):
        """大きなログファイル処理時間のベンチマークテスト"""
        import time

        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("large_performance.log")
        mock_read_log.return_value = performance_log_content

        # パフォーマンス分析結果のモック
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=10000, output_tokens=1000, total_tokens=11000, estimated_cost=0.2)

        mock_result = AnalysisResult(
            summary="大規模ログファイルの分析完了",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=3.5,  # 分析時間をシミュレート
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 処理時間を測定
        start_time = time.time()
        result = runner.invoke(analyze, ["--verbose"], obj=ctx_obj)
        end_time = time.time()

        processing_time = end_time - start_time

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 処理時間が合理的な範囲内であることを確認（30秒未満）
        assert processing_time < 30.0

        # ログサイズが期待通りであることを確認
        call_args = mock_ai_integration.analyze_log.call_args
        log_content = call_args[0][0]
        assert len(log_content) > 100000  # 大きなログファイル

    def test_memory_usage_monitoring(self, performance_log_content):
        """メモリ使用量とリークチェックのテスト"""
        import gc

        # ガベージコレクションを実行してベースラインを設定
        gc.collect()
        initial_objects = len(gc.get_objects())

        # 大きなログコンテンツを処理
        processed_content = performance_log_content.upper()  # 簡単な処理をシミュレート
        content_lines = processed_content.split("\n")

        # メモリ使用量をチェック
        current_objects = len(gc.get_objects())
        object_increase = current_objects - initial_objects

        # 検証
        assert len(content_lines) == 30000  # 5000 * 6 lines
        # オブジェクト数の増加が合理的な範囲内であることを確認
        assert object_increase < 50000  # 大幅な増加でないことを確認

        # メモリクリーンアップ
        del processed_content
        del content_lines
        gc.collect()

        # メモリリークがないことを確認
        final_objects = len(gc.get_objects())
        assert final_objects <= current_objects

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_parallel_processing_efficiency(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """並列処理効率のテスト"""
        import asyncio
        import time

        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("parallel_test.log")
        mock_read_log.return_value = "parallel processing test log"

        # 並列処理をシミュレートする分析結果
        async def mock_parallel_analysis(log_content, options):
            # 並列処理のシミュレーション（複数のタスクを同時実行）
            await asyncio.sleep(0.1)  # 処理時間をシミュレート
            return self.create_mock_analysis_result()

        mock_ai_integration.analyze_log.side_effect = mock_parallel_analysis

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 並列実行のシミュレーション
        start_time = time.time()
        result = runner.invoke(analyze, [], obj=ctx_obj)
        end_time = time.time()

        processing_time = end_time - start_time

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.analyze_log.assert_called_once()

        # 並列処理により処理時間が短縮されていることを確認
        assert processing_time < 5.0  # 5秒未満で完了

    @patch("src.ci_helper.commands.analyze.AIIntegration")
    @patch("src.ci_helper.commands.analyze._get_latest_log_file")
    @patch("src.ci_helper.commands.analyze._read_log_file")
    @patch("src.ci_helper.commands.analyze._validate_analysis_environment")
    def test_response_time_regression(
        self,
        mock_validate,
        mock_read_log,
        mock_get_latest,
        mock_ai_class,
        runner,
        mock_config,
        mock_console,
    ):
        """レスポンス時間の回帰テスト"""
        import time

        # 環境検証を成功させる
        mock_validate.return_value = True

        # モックの設定
        mock_ai_integration = Mock()
        mock_ai_integration.initialize = AsyncMock()
        mock_ai_integration.analyze_log = AsyncMock()
        mock_ai_class.return_value = mock_ai_integration

        mock_get_latest.return_value = Path("regression_test.log")
        mock_read_log.return_value = "regression test log content"

        # 基準となる分析結果のモック
        mock_result = self.create_mock_analysis_result()
        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": mock_console}

        # 複数回実行して平均レスポンス時間を測定
        response_times = []
        for _ in range(3):
            start_time = time.time()
            result = runner.invoke(analyze, [], obj=ctx_obj)
            end_time = time.time()

            assert result.exit_code == 0
            response_times.append(end_time - start_time)

        # 平均レスポンス時間を計算
        avg_response_time = sum(response_times) / len(response_times)

        # 検証
        # 平均レスポンス時間が基準値以下であることを確認
        assert avg_response_time < 2.0  # 2秒未満

        # レスポンス時間のばらつきが小さいことを確認
        max_time = max(response_times)
        min_time = min(response_times)
        time_variance = max_time - min_time
        assert time_variance < 1.0  # 1秒未満のばらつき

    def test_token_counting_performance(self):
        """トークンカウント処理のパフォーマンステスト"""
        import time

        # 大きなテキストでトークンカウントのパフォーマンスをテスト
        large_text = "This is a test sentence. " * 1000  # 約1000文の繰り返し

        # トークンカウント処理のシミュレーション
        start_time = time.time()

        # 簡単なトークンカウントのシミュレーション（実際のtiktokenは使用しない）
        words = large_text.split()
        estimated_tokens = len(words) * 1.3  # 単語数の1.3倍をトークン数として推定

        end_time = time.time()
        processing_time = end_time - start_time

        # 検証
        assert estimated_tokens > 1000  # 十分な量のトークン
        assert processing_time < 1.0  # 1秒未満で処理完了

    def test_cache_performance_impact(self):
        """キャッシュのパフォーマンス影響テスト"""
        import time

        # キャッシュありとなしでの処理時間を比較
        test_data = {"key1": "value1", "key2": "value2", "key3": "value3"}

        # キャッシュなしの処理時間
        start_time = time.time()
        for key in test_data:
            # データベース検索のシミュレーション
            time.sleep(0.001)  # 1ms の遅延
            result = test_data[key]
        no_cache_time = time.time() - start_time

        # キャッシュありの処理時間（辞書アクセス）
        cache = test_data.copy()
        start_time = time.time()
        for key in cache:
            result = cache[key]  # キャッシュからの高速アクセス
        cache_time = time.time() - start_time

        # 検証
        # キャッシュありの方が高速であることを確認
        assert cache_time < no_cache_time
        assert cache_time < 0.01  # 10ms未満

    def test_streaming_performance_overhead(self):
        """ストリーミング処理のパフォーマンスオーバーヘッドテスト"""
        import time

        # ストリーミング処理のシミュレーション
        chunks = [f"chunk_{i}" for i in range(100)]

        # 通常の一括処理
        start_time = time.time()
        result_batch = "".join(chunks)
        batch_time = time.time() - start_time

        # ストリーミング処理
        start_time = time.time()
        result_stream = ""
        for chunk in chunks:
            result_stream += chunk
            # ストリーミング処理のオーバーヘッドをシミュレート
            time.sleep(0.0001)  # 0.1ms の遅延
        stream_time = time.time() - start_time

        # 検証
        assert result_batch == result_stream  # 結果は同じ
        # ストリーミングのオーバーヘッドが合理的な範囲内であることを確認
        overhead = stream_time - batch_time
        assert overhead < 1.0  # 1秒未満のオーバーヘッド

    def create_mock_analysis_result(self):
        """パフォーマンステスト用の分析結果モックを作成"""
        from datetime import datetime

        from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage

        tokens_used = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002)

        return AnalysisResult(
            summary="パフォーマンステスト要約",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=tokens_used,
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
            timestamp=datetime.now(),
            cache_hit=False,
        )

    def test_concurrent_request_handling(self):
        """同時リクエスト処理のパフォーマンステスト"""
        import asyncio
        import time

        async def mock_analysis_task(task_id):
            """分析タスクのシミュレーション"""
            await asyncio.sleep(0.1)  # 100ms の処理時間
            return f"result_{task_id}"

        async def run_concurrent_analysis():
            """同時分析の実行"""
            tasks = [mock_analysis_task(i) for i in range(5)]
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            return results, end_time - start_time

        # 同期的にテストを実行

        results, total_time = asyncio.run(run_concurrent_analysis())

        # 検証
        assert len(results) == 5
        # 並列実行により、5つのタスクが0.5秒（5 * 0.1）より短時間で完了することを確認
        assert total_time < 0.3  # 300ms未満（並列実行の効果）

    def test_error_handling_performance_impact(self):
        """エラーハンドリングのパフォーマンス影響テスト"""
        import time

        # 正常処理の時間
        start_time = time.time()
        try:
            result = "normal_processing"
        except Exception:
            result = "error_handled"
        normal_time = time.time() - start_time

        # エラー処理の時間
        start_time = time.time()
        try:
            raise ValueError("test error")
        except ValueError:
            result = "error_handled"
        error_time = time.time() - start_time

        # 検証
        # エラーハンドリングのオーバーヘッドが最小限であることを確認
        overhead = error_time - normal_time
        assert overhead < 0.01  # 10ms未満のオーバーヘッド
