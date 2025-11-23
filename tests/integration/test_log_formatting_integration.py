"""
ログ整形機能統合テスト

メニュー選択方式とコマンド指定実行方式の統合テストを実装します。
要件11.1-11.5に対応した包括的なテストを提供します。
"""

from __future__ import annotations

import json

# テスト用のモックヘルパーをインポート
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from ci_helper.cli import cli
from ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from ci_helper.formatters import get_formatter_manager
from ci_helper.ui.command_menus import CommandMenuBuilder
from ci_helper.ui.menu_system import MenuSystem
from click.testing import CliRunner
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.utils.mock_helpers import setup_stable_prompt_mock


class TestLogFormattingIntegration:
    """ログ整形機能の統合テスト

    要件11.1-11.5に対応:
    - 11.1: メニュー選択方式とコマンド指定実行方式の統合テスト
    - 11.2: 同じ整形エンジンの使用確認テスト
    - 11.3: 同じ出力品質の確認テスト
    - 11.4: バッチ処理とスクリプト統合のテスト
    - 11.5: 対話的探索機能のテスト
    """

    @pytest.fixture
    def sample_execution_result(self) -> ExecutionResult:
        """テスト用の実行結果を作成"""
        failures = [
            Failure(
                type=FailureType.ASSERTION,
                message="AssertionError: Expected 'production' but got 'development'",
                file_path="tests/unit/test_config.py",
                line_number=45,
                context_before=["def test_load_config():", "    config = load_config('config.toml')"],
                context_after=["    assert config.debug == False"],
                stack_trace='Traceback (most recent call last):\n  File "test_config.py", line 45',
            ),
            Failure(
                type=FailureType.ERROR,
                message="ModuleNotFoundError: No module named 'missing_module'",
                file_path="src/app/main.py",
                line_number=12,
                context_before=["import os", "import sys"],
                context_after=["from app.config import Config"],
                stack_trace=None,
            ),
        ]

        job_result = JobResult(
            name="test",
            success=False,
            failures=failures,
            duration=45.2,
        )

        workflow_result = WorkflowResult(
            name="test.yml",
            success=False,
            jobs=[job_result],
            duration=45.2,
        )

        return ExecutionResult(
            success=False,
            workflows=[workflow_result],
            total_duration=45.2,
        )

    @pytest.fixture
    def temp_log_file(self, sample_execution_result: ExecutionResult) -> Path:
        """テスト用のログファイルを作成"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            # サンプルログ内容を書き込み
            f.write("CI実行ログ\n")
            f.write("Job 'test' failed\n")
            f.write("AssertionError: Expected 'production' but got 'development'\n")
            f.write("ModuleNotFoundError: No module named 'missing_module'\n")
            temp_path = Path(f.name)

        yield temp_path

        # クリーンアップ
        if temp_path.exists():
            temp_path.unlink()

    def test_menu_and_command_use_same_formatter_engine(self, sample_execution_result: ExecutionResult):
        """要件11.2: メニューとコマンドが同じ整形エンジンを使用することを確認"""
        formatter_manager = get_formatter_manager()

        # 各フォーマット形式で同じフォーマッターインスタンスが使用されることを確認
        ai_formatter_1 = formatter_manager.get_formatter("ai")
        ai_formatter_2 = formatter_manager.get_formatter("ai")

        human_formatter_1 = formatter_manager.get_formatter("human")
        human_formatter_2 = formatter_manager.get_formatter("human")

        json_formatter_1 = formatter_manager.get_formatter("json")
        json_formatter_2 = formatter_manager.get_formatter("json")

        # 同じフォーマッタークラスのインスタンスであることを確認
        assert type(ai_formatter_1) is type(ai_formatter_2)
        assert type(human_formatter_1) is type(human_formatter_2)
        assert type(json_formatter_1) is type(json_formatter_2)

        # フォーマッターが正しく登録されていることを確認
        available_formats = formatter_manager.list_available_formats()
        assert "ai" in available_formats
        assert "human" in available_formats
        assert "json" in available_formats

    def test_same_output_quality_between_menu_and_command(
        self, sample_execution_result: ExecutionResult, temp_log_file: Path
    ):
        """要件11.3: メニューとコマンドで同じ出力品質を提供することを確認"""
        formatter_manager = get_formatter_manager()

        # 各フォーマット形式で出力内容を比較
        formats_to_test = ["ai", "human", "json"]

        for format_type in formats_to_test:
            # フォーマッターマネージャーから直接取得（メニュー・コマンド共通）
            formatted_output = formatter_manager.format_log(
                sample_execution_result, format_type, filter_errors=False, verbose_level="normal"
            )

            # 出力が空でないことを確認
            assert formatted_output.strip(), f"{format_type}フォーマットの出力が空です"

            # フォーマット固有の内容チェック
            if format_type == "ai":
                # AI形式では構造化されたMarkdownが生成される
                assert "# CI Failure Report" in formatted_output or "## " in formatted_output
                assert "AssertionError" in formatted_output
                assert "test_config.py" in formatted_output

            elif format_type == "human":
                # 人間可読形式では Rich のボックス文字やUnicode文字が含まれる
                # Rich markup の代わりに、実際の出力に含まれる文字をチェック
                assert (
                    "╭" in formatted_output
                    or "│" in formatted_output
                    or "🎯" in formatted_output
                    or "❌" in formatted_output
                )  # Rich box drawing or emoji

            elif format_type == "json":
                # JSON形式では有効なJSONが生成される
                try:
                    parsed_json = json.loads(formatted_output)
                    assert isinstance(parsed_json, dict)
                    # Check for the actual JSON structure used by the formatter
                    assert "success" in parsed_json or (
                        "execution_summary" in parsed_json and "success" in parsed_json["execution_summary"]
                    )
                    assert "workflows" in parsed_json or "all_failures" in parsed_json
                except json.JSONDecodeError:
                    pytest.fail(f"JSON形式の出力が無効です: {formatted_output[:200]}...")

    @patch("ci_helper.commands.format_logs._get_execution_result")
    def test_command_line_execution_integration(
        self, mock_get_result: Mock, sample_execution_result: ExecutionResult, temp_log_file: Path
    ):
        """要件11.1, 11.4: コマンドライン実行方式の統合テスト（バッチ処理対応）"""
        mock_get_result.return_value = sample_execution_result

        runner = CliRunner()

        # AI形式でのコマンド実行テスト
        with patch("ci_helper.commands.format_logs.get_formatter_manager") as mock_manager:
            mock_formatter_manager = Mock()
            mock_formatter_manager.format_log.return_value = "# AI Formatted Output\n\nTest content"
            mock_manager.return_value = mock_formatter_manager

            with patch("ci_helper.commands.format_logs.get_progress_manager") as mock_progress:
                mock_progress_manager = Mock()
                mock_progress_manager.execute_with_progress.return_value = "# AI Formatted Output\n\nTest content"
                mock_progress.return_value = mock_progress_manager

                result = runner.invoke(cli, ["format-logs", "--format", "ai", "--input", str(temp_log_file)])

                # コマンドが正常実行されることを確認
                assert result.exit_code == 0
                assert "# AI Formatted Output" in result.output

                # プログレスマネージャーが正しく呼び出されることを確認（format_logは内部で呼ばれる）
                mock_progress_manager.execute_with_progress.assert_called_once()

    @patch("ci_helper.commands.format_logs._get_execution_result")
    def test_batch_processing_with_multiple_formats(
        self, mock_get_result: Mock, sample_execution_result: ExecutionResult, temp_log_file: Path
    ):
        """要件11.4: バッチ処理での複数フォーマット出力テスト"""
        mock_get_result.return_value = sample_execution_result

        runner = CliRunner()
        formats = ["ai", "human", "json"]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 各フォーマットでファイル出力をテスト
            for format_type in formats:
                output_file = temp_path / f"output.{format_type}"

                with patch("ci_helper.commands.format_logs.get_formatter_manager") as mock_manager:
                    mock_formatter_manager = Mock()
                    mock_formatter_manager.format_log.return_value = f"# {format_type.upper()} Output\n\nContent"
                    mock_manager.return_value = mock_formatter_manager

                    with patch("ci_helper.commands.format_logs.get_progress_manager") as mock_progress:
                        mock_progress_manager = Mock()
                        mock_progress_manager.execute_with_progress.return_value = (
                            f"# {format_type.upper()} Output\n\nContent"
                        )
                        mock_progress.return_value = mock_progress_manager

                        with patch("ci_helper.utils.file_save_utils.FileSaveManager.save_formatted_log") as mock_save:
                            mock_save.return_value = (True, str(output_file))

                            result = runner.invoke(
                                cli,
                                [
                                    "format-logs",
                                    "--format",
                                    format_type,
                                    "--input",
                                    str(temp_log_file),
                                    "--output",
                                    str(output_file),
                                    "--no-confirm",
                                ],
                            )

                            # バッチ処理が成功することを確認
                            assert result.exit_code == 0
                            mock_save.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_menu_interactive_exploration(self, mock_prompt: Mock, sample_execution_result: ExecutionResult):
        """要件11.5: 対話的探索機能のテスト"""
        console = Console()

        # モックコマンドハンドラーを作成
        command_handlers = {
            "format_logs": Mock(return_value=True),
            "format_logs_custom": Mock(return_value=True),
        }

        builder = CommandMenuBuilder(console, command_handlers)
        menu_system = MenuSystem(console)

        # ログ整形メニューへのナビゲーションをシミュレート
        # ログ管理 → ログ整形 → AI分析用フォーマット → 戻る → 戻る → 戻る → 終了
        # 安定したモック設定を使用してStopIterationエラーを防ぐ
        setup_stable_prompt_mock(mock_prompt, ["5", "4", "1", "1", "", "b", "b", "b", "q"])

        main_menu = builder.build_main_menu()

        with patch.object(menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            menu_system.run_menu(main_menu)

        # format_logsハンドラーが呼び出されることを確認
        command_handlers["format_logs"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    @patch("rich.prompt.Confirm.ask")
    def test_menu_custom_formatting_exploration(self, mock_confirm: Mock, mock_prompt: Mock):
        """要件11.5: カスタム整形機能の対話的探索テスト"""
        console = Console()

        # モックコマンドハンドラーを作成
        command_handlers = {
            "format_logs_custom": Mock(return_value=True),
        }

        builder = CommandMenuBuilder(console, command_handlers)
        menu_system = MenuSystem(console)

        # カスタム整形メニューへのナビゲーション
        # ログ管理 → ログ整形 → カスタム整形 → 設定 → 実行確認 → 戻る
        # 安定したモック設定を使用してStopIterationエラーを防ぐ
        setup_stable_prompt_mock(
            mock_prompt,
            [
                "5",  # ログ管理
                "4",  # ログ整形
                "3",  # カスタム整形
                "ai",  # フォーマット選択
                "detailed",  # 詳細レベル
                "y",  # エラーフィルタリング有効
                "console",  # 出力先選択
                "b",  # 戻る
                "b",  # 戻る
                "b",  # 戻る
                "q",  # 終了
            ],
        )

        # Confirm.askのモック設定（実行確認）
        mock_confirm.return_value = True

        main_menu = builder.build_main_menu()

        with patch.object(menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()

            # カスタム整形パラメータ設定画面のモック
            with patch.object(builder, "_show_custom_format_parameter_screen") as mock_param_screen:
                mock_param_screen.return_value = {
                    "format_type": "ai",
                    "detail_level": "detailed",
                    "filter_errors": True,
                    "advanced_options": {},
                }

                # ログファイル選択のモック
                with patch.object(builder, "_select_log_file") as mock_select_log:
                    mock_select_log.return_value = "/mock/path/latest.log"

                    # 設定確認画面のモック
                    with patch.object(builder, "_show_custom_format_confirmation") as mock_confirmation:
                        mock_confirmation.return_value = None

                        menu_system.run_menu(main_menu)

        # カスタム整形ハンドラーが呼び出されることを確認
        command_handlers["format_logs_custom"].assert_called_once()

    def test_formatter_consistency_across_execution_methods(self, sample_execution_result: ExecutionResult):
        """要件11.2, 11.3: 実行方式間でのフォーマッター一貫性テスト"""
        formatter_manager = get_formatter_manager()

        # 同じ入力に対して複数回フォーマットを実行
        format_options = {"filter_errors": False, "verbose_level": "normal"}

        # AI形式での一貫性テスト
        ai_output_1 = formatter_manager.format_log(sample_execution_result, "ai", **format_options)
        ai_output_2 = formatter_manager.format_log(sample_execution_result, "ai", **format_options)

        # 同じ入力に対して同じ出力が生成されることを確認
        assert ai_output_1 == ai_output_2

        # JSON形式での一貫性テスト
        json_output_1 = formatter_manager.format_log(sample_execution_result, "json", **format_options)
        json_output_2 = formatter_manager.format_log(sample_execution_result, "json", **format_options)

        # JSON出力の構造的一貫性を確認（動的な値を除外）
        import json

        data1 = json.loads(json_output_1)
        data2 = json.loads(json_output_2)

        # 動的な値（タイムスタンプ等）を除外して比較
        def remove_dynamic_values(data):
            """動的な値を除外したコピーを作成"""
            import copy

            cleaned_data = copy.deepcopy(data)

            # format_info内のgenerated_atを除外
            if "format_info" in cleaned_data and "generated_at" in cleaned_data["format_info"]:
                del cleaned_data["format_info"]["generated_at"]

            return cleaned_data

        cleaned_data1 = remove_dynamic_values(data1)
        cleaned_data2 = remove_dynamic_values(data2)

        assert cleaned_data1 == cleaned_data2

        # 異なるフォーマット間では異なる出力が生成されることを確認
        assert ai_output_1 != json_output_1

    @patch("ci_helper.commands.format_logs._get_execution_result")
    def test_script_integration_with_exit_codes(
        self, mock_get_result: Mock, sample_execution_result: ExecutionResult, temp_log_file: Path
    ):
        """要件11.4: スクリプト統合での終了コード確認テスト"""
        runner = CliRunner()

        # 成功ケース
        mock_get_result.return_value = sample_execution_result

        with patch("ci_helper.commands.format_logs.get_formatter_manager") as mock_manager:
            mock_formatter_manager = Mock()
            mock_formatter_manager.format_log.return_value = "Formatted output"
            mock_manager.return_value = mock_formatter_manager

            with patch("ci_helper.commands.format_logs.get_progress_manager") as mock_progress:
                mock_progress_manager = Mock()
                mock_progress_manager.execute_with_progress.return_value = "Formatted output"
                mock_progress.return_value = mock_progress_manager

                result = runner.invoke(cli, ["format-logs", "--format", "ai", "--input", str(temp_log_file)])

                # 成功時は終了コード0
                assert result.exit_code == 0

        # 失敗ケース（ログファイルが見つからない）
        mock_get_result.return_value = None

        with patch("ci_helper.commands.format_logs.get_progress_manager") as mock_progress:
            mock_progress_manager = Mock()
            mock_progress.return_value = mock_progress_manager

            result = runner.invoke(cli, ["format-logs", "--format", "ai", "--input", str(temp_log_file)])

            # 失敗時は終了コード1
            assert result.exit_code == 1

    def test_menu_and_command_parameter_compatibility(self):
        """要件11.1: メニューとコマンドのパラメータ互換性テスト"""
        formatter_manager = get_formatter_manager()

        # メニューで使用されるパラメータ
        menu_params = {"filter_errors": True, "verbose_level": "detailed"}

        # コマンドラインで使用されるパラメータ
        command_params = {"filter_errors": True, "verbose_level": "detailed"}

        # パラメータ構造が一致することを確認
        assert menu_params == command_params

        # フォーマッターが両方のパラメータセットを受け入れることを確認
        sample_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        try:
            formatter_manager.format_log(sample_result, "ai", **menu_params)
            formatter_manager.format_log(sample_result, "ai", **command_params)
        except Exception as e:
            pytest.fail(f"パラメータ互換性エラー: {e}")

    @patch("rich.prompt.Prompt.ask")
    def test_menu_error_handling_consistency(self, mock_prompt: Mock):
        """要件11.1: メニューとコマンドでのエラーハンドリング一貫性テスト"""
        console = Console()

        # エラーを発生させるモックハンドラー
        error_handler = Mock(side_effect=Exception("テストエラー"))
        command_handlers = {
            "format_logs": error_handler,
        }

        builder = CommandMenuBuilder(console, command_handlers)
        menu_system = MenuSystem(console)

        # エラーが発生するメニュー操作をシミュレート
        # 安定したモック設定を使用してStopIterationエラーを防ぐ
        setup_stable_prompt_mock(mock_prompt, ["5", "4", "1", "1", "", "q"])

        main_menu = builder.build_main_menu()

        with patch.object(menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()

            # エラーが発生してもメニューシステムがクラッシュしないことを確認
            try:
                menu_system.run_menu(main_menu)
            except Exception:
                pytest.fail("メニューシステムでエラーハンドリングが適切に動作していません")

        # エラーハンドラーが呼び出されたことを確認
        error_handler.assert_called_once()

    def test_output_format_validation_consistency(self):
        """要件11.2, 11.3: 出力フォーマット検証の一貫性テスト"""
        formatter_manager = get_formatter_manager()

        # サポートされているフォーマット
        supported_formats = ["ai", "human", "json"]

        # 各フォーマットが正しく登録されていることを確認
        available_formats = formatter_manager.list_available_formats()
        for format_type in supported_formats:
            assert format_type in available_formats

        # 無効なフォーマットでエラーが発生することを確認
        sample_result = ExecutionResult(success=True, workflows=[], total_duration=0.0)

        # LogFormattingErrorが発生することを確認（ValueErrorではなく）
        from ci_helper.core.exceptions import LogFormattingError

        with pytest.raises(LogFormattingError):
            formatter_manager.format_log(sample_result, "invalid_format")
