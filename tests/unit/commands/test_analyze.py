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
from src.ci_helper.utils.config import Config


class TestAnalyzeCommand:
    """analyzeコマンドのテストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_config(self, temp_dir):
        """モック設定"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        # Create a proper AIConfig object
        provider_config = ProviderConfig(
            name="openai",
            api_key="sk-test-key-123",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-4o-mini"],
        )

        ai_config = AIConfig(
            default_provider="openai",
            providers={"openai": provider_config},
            cache_enabled=True,
            cost_limits={"monthly_usd": 50.0},
            cache_dir=str(temp_dir / "cache"),
        )

        config = Mock(spec=Config)
        config.project_root = temp_dir
        config.get_path.return_value = temp_dir / "cache"
        config.get = Mock(return_value=None)
        config.get_ai_config = Mock(return_value=ai_config)
        config.get_available_ai_providers = Mock(return_value=["openai"])
        config.get_ai_provider_api_key = Mock(return_value="sk-test-key-123")
        config.get_default_ai_provider = Mock(return_value="openai")
        config.get_ai_provider_config = Mock(return_value=provider_config)
        config.get_path = Mock(return_value=temp_dir / "cache")
        config.__getitem__ = Mock(return_value=None)
        config.__contains__ = Mock(return_value=False)
        return config

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
        from ci_helper.ai.models import AnalysisResult

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
        self, mock_validate, mock_get_latest, mock_ai_class, runner, mock_config, mock_ai_integration
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

    @pytest.fixture
    def mock_config(self, temp_dir):
        """モック設定"""
        config = Mock(spec=Config)
        config.project_root = temp_dir
        config.get_path.return_value = temp_dir / "cache"
        config.get = Mock(return_value=None)
        config.get_ai_config = Mock(return_value={})
        config.get_available_ai_providers = Mock(return_value=[])
        config.__getitem__ = Mock(return_value=None)
        config.__contains__ = Mock(return_value=False)
        return config

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
