"""
analyzeコマンドのテスト

AI分析コマンドの機能をテストします。
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from ci_helper.commands.analyze import analyze
from ci_helper.utils.config import Config


class TestAnalyzeCommand:
    """analyzeコマンドのテストクラス"""

    @pytest.fixture
    def runner(self):
        """CLIランナー"""
        return CliRunner()

    @pytest.fixture
    def mock_config(self, temp_dir):
        """モック設定"""
        config = Mock(spec=Config)
        config.project_root = temp_dir
        config.get_path.return_value = temp_dir / "cache"
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

    def test_analyze_help(self, runner):
        """ヘルプ表示のテスト"""
        result = runner.invoke(analyze, ["--help"])
        assert result.exit_code == 0
        assert "CI/CDの失敗ログをAIで分析" in result.output
        assert "--log" in result.output
        assert "--provider" in result.output
        assert "--interactive" in result.output

    @patch("ci_helper.commands.analyze.AIIntegration")
    @patch("ci_helper.commands.analyze._get_latest_log_file")
    @patch("ci_helper.commands.analyze._read_log_file")
    def test_analyze_basic(
        self, mock_read_log, mock_get_latest, mock_ai_class, runner, mock_config, mock_ai_integration
    ):
        """基本的な分析のテスト"""
        # モックの設定
        mock_ai_class.return_value = mock_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # 分析結果のモック
        from ci_helper.ai.models import AnalysisResult

        mock_result = Mock(spec=AnalysisResult)
        mock_result.summary = "テスト要約"
        mock_result.root_cause = "テスト原因"
        mock_result.recommendations = ["推奨事項1", "推奨事項2"]
        mock_result.tokens_used = 100
        mock_result.cost = 0.002
        mock_result.fix_suggestions = []
        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

        # コマンド実行
        result = runner.invoke(analyze, [], obj=ctx_obj)

        # 検証
        assert result.exit_code == 0
        mock_ai_integration.initialize.assert_called_once()
        mock_ai_integration.analyze_log.assert_called_once()

    @patch("ci_helper.commands.analyze.AIIntegration")
    def test_analyze_stats_only(self, mock_ai_class, runner, mock_config):
        """統計表示のみのテスト"""
        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

        # コマンド実行
        result = runner.invoke(analyze, ["--stats"], obj=ctx_obj)

        # AI統合が初期化されないことを確認
        mock_ai_class.assert_not_called()

    @patch("ci_helper.commands.analyze.AIIntegration")
    @patch("ci_helper.commands.analyze._get_latest_log_file")
    def test_analyze_no_log_file(self, mock_get_latest, mock_ai_class, runner, mock_config, mock_ai_integration):
        """ログファイルが見つからない場合のテスト"""
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

    @patch("ci_helper.commands.analyze.AIIntegration")
    @patch("ci_helper.commands.analyze._get_latest_log_file")
    @patch("ci_helper.commands.analyze._read_log_file")
    def test_analyze_with_options(
        self, mock_read_log, mock_get_latest, mock_ai_class, runner, mock_config, mock_ai_integration
    ):
        """オプション付き分析のテスト"""
        # モックの設定
        mock_ai_class.return_value = mock_ai_integration
        mock_get_latest.return_value = Path("test.log")
        mock_read_log.return_value = "test log content"

        # 分析結果のモック
        from ci_helper.ai.models import AnalysisResult

        mock_result = Mock(spec=AnalysisResult)
        mock_result.summary = "テスト要約"
        mock_result.root_cause = "テスト原因"
        mock_result.recommendations = []
        mock_result.tokens_used = 100
        mock_result.cost = 0.002
        mock_result.fix_suggestions = []
        mock_ai_integration.analyze_log.return_value = mock_result

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

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

    def test_analyze_with_specific_log_file(self, runner, temp_dir, mock_config):
        """特定のログファイル指定のテスト"""
        # テスト用ログファイルを作成
        log_file = temp_dir / "test.log"
        log_file.write_text("test log content")

        # コンテキストオブジェクトの設定
        ctx_obj = {"config": mock_config, "console": Mock()}

        with patch("ci_helper.commands.analyze.AIIntegration") as mock_ai_class:
            mock_ai_integration = Mock()
            mock_ai_integration.initialize = AsyncMock()
            mock_ai_integration.analyze_log = AsyncMock()
            mock_ai_class.return_value = mock_ai_integration

            # 分析結果のモック
            from ci_helper.ai.models import AnalysisResult

            mock_result = Mock(spec=AnalysisResult)
            mock_result.summary = "テスト要約"
            mock_result.root_cause = "テスト原因"
            mock_result.recommendations = []
            mock_result.tokens_used = 100
            mock_result.cost = 0.002
            mock_result.fix_suggestions = []
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


class TestAnalyzeHelperFunctions:
    """analyzeコマンドのヘルパー関数のテスト"""

    @pytest.fixture
    def mock_config(self, temp_dir):
        """モック設定"""
        config = Mock(spec=Config)
        config.project_root = temp_dir
        config.get_path.return_value = temp_dir / "cache"
        return config

    def test_read_log_file(self, temp_dir):
        """ログファイル読み込みのテスト"""
        from ci_helper.commands.analyze import _read_log_file

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
        from ci_helper.commands.analyze import _read_log_file
        from ci_helper.core.exceptions import CIHelperError

        non_existent_file = Path("non_existent.log")

        # 例外が発生することを確認
        with pytest.raises(CIHelperError):
            _read_log_file(non_existent_file)

    @patch("ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file(self, mock_log_manager_class, mock_config):
        """最新ログファイル取得のテスト"""
        from ci_helper.commands.analyze import _get_latest_log_file

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

    @patch("ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file_no_logs(self, mock_log_manager_class, mock_config):
        """ログが存在しない場合のテスト"""
        from ci_helper.commands.analyze import _get_latest_log_file

        # モックログマネージャーの設定
        mock_log_manager = Mock()
        mock_log_manager_class.return_value = mock_log_manager
        mock_log_manager.list_logs.return_value = []

        # 最新ログファイル取得
        result = _get_latest_log_file(mock_config)

        # 検証
        assert result is None

    @patch("ci_helper.commands.analyze.LogManager")
    def test_get_latest_log_file_exception(self, mock_log_manager_class, mock_config):
        """ログマネージャーで例外が発生した場合のテスト"""
        from ci_helper.commands.analyze import _get_latest_log_file

        # モックログマネージャーの設定
        mock_log_manager_class.side_effect = Exception("テストエラー")

        # 最新ログファイル取得
        result = _get_latest_log_file(mock_config)

        # 検証（例外が発生してもNoneを返す）
        assert result is None
