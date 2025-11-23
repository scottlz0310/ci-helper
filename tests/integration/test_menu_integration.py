"""
メニューシステム統合テスト

メニューシステム全体の統合動作をテストします。
"""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from ci_helper.ui.command_menus import CommandMenuBuilder
from ci_helper.ui.menu_system import MenuSystem
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.utils.mock_helpers import setup_stable_prompt_mock


class TestMenuIntegration:
    """メニューシステム統合テスト"""

    def setup_method(self):
        """テストセットアップ"""
        self.output = StringIO()
        self.console = Console(file=self.output, width=80, legacy_windows=False)

        # モックコマンドハンドラーを作成
        self.command_handlers = {
            "doctor": Mock(return_value=True),
            "init": Mock(return_value=True),
            "test": Mock(return_value=True),
            "analyze": Mock(return_value=True),
            "logs": Mock(return_value=True),
            "secrets": Mock(return_value=True),
            "cache": Mock(return_value=True),
            "clean": Mock(return_value=True),
        }

        self.builder = CommandMenuBuilder(self.console, self.command_handlers)
        self.menu_system = MenuSystem(self.console)

    @patch("rich.prompt.Prompt.ask")
    def test_main_menu_to_doctor_command(self, mock_prompt):
        """メインメニューから環境チェックコマンドへの統合テスト"""
        # ユーザー入力をシミュレート: 環境チェック選択 → 終了
        setup_stable_prompt_mock(mock_prompt, ["2", "", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # doctorコマンドが実行されることを確認
        self.command_handlers["doctor"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_main_menu_to_submenu_navigation(self, mock_prompt):
        """メインメニューからサブメニューへのナビゲーションテスト"""
        # ユーザー入力をシミュレート: 初期設定選択 → 戻る → 終了
        setup_stable_prompt_mock(mock_prompt, ["1", "b", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # サブメニューに入って戻ったことを確認（具体的なアクションは実行されない）
        assert not any(handler.called for handler in self.command_handlers.values())

    @patch("rich.prompt.Prompt.ask")
    def test_submenu_command_execution(self, mock_prompt):
        """サブメニューでのコマンド実行テスト"""
        # ユーザー入力をシミュレート: 初期設定 → 標準初期設定 → 戻る → 終了
        setup_stable_prompt_mock(mock_prompt, ["1", "2", "", "b", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # initコマンドが実行されることを確認
        self.command_handlers["init"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_multiple_command_execution(self, mock_prompt):
        """複数コマンドの連続実行テスト"""
        # ユーザー入力をシミュレート: 環境チェック → クリーンアップ → 終了
        setup_stable_prompt_mock(mock_prompt, ["2", "", "8", "", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # 両方のコマンドが実行されることを確認
        self.command_handlers["doctor"].assert_called_once()
        self.command_handlers["clean"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_invalid_input_handling(self, mock_prompt):
        """無効な入力の処理テスト"""
        # ユーザー入力をシミュレート: 無効な選択 → 有効な選択 → 終了
        setup_stable_prompt_mock(mock_prompt, ["invalid", "2", "", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # 最終的にdoctorコマンドが実行されることを確認
        self.command_handlers["doctor"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_keyboard_interrupt_handling(self, mock_prompt):
        """キーボード割り込みの処理テスト"""
        # キーボード割り込みをシミュレート
        mock_prompt.side_effect = KeyboardInterrupt()

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # コマンドが実行されないことを確認
        assert not any(handler.called for handler in self.command_handlers.values())

    @patch("rich.prompt.Prompt.ask")
    def test_command_exception_handling(self, mock_prompt):
        """コマンド実行時の例外処理テスト"""
        # doctorコマンドで例外を発生させる
        self.command_handlers["doctor"].side_effect = Exception("テストエラー")

        # ユーザー入力をシミュレート: 環境チェック → 終了
        setup_stable_prompt_mock(mock_prompt, ["2", "", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # コマンドが呼び出されたが例外で失敗したことを確認
        self.command_handlers["doctor"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_deep_submenu_navigation(self, mock_prompt):
        """深いサブメニューナビゲーションテスト"""
        # ユーザー入力をシミュレート: AI分析 → 最新ログ分析 → 戻る → 戻る → 終了
        setup_stable_prompt_mock(mock_prompt, ["4", "1", "", "b", "b", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # analyzeコマンドが実行されることを確認
        self.command_handlers["analyze"].assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_menu_stack_management(self, mock_prompt):
        """メニュースタック管理のテスト"""
        # ユーザー入力をシミュレート: サブメニューに入って戻る
        setup_stable_prompt_mock(mock_prompt, ["1", "b", "q"])

        main_menu = self.builder.build_main_menu()

        # メニュースタックの状態を追跡
        stack_states = []

        original_run_menu = self.menu_system.run_menu

        def track_stack(menu):
            stack_states.append(len(self.menu_system.menu_stack))
            return original_run_menu(menu)

        with patch.object(self.menu_system, "run_menu", side_effect=track_stack):
            with patch.object(self.menu_system, "console") as mock_console:
                mock_console.clear = Mock()
                mock_console.print = Mock()
                self.menu_system.run_menu(main_menu)

        # スタックが正しく管理されることを確認
        assert len(self.menu_system.menu_stack) == 0

    @patch("rich.prompt.Prompt.ask")
    def test_start_method_integration(self, mock_prompt):
        """startメソッドの統合テスト"""
        setup_stable_prompt_mock(mock_prompt, ["q"])

        main_menu = self.builder.build_main_menu()

        # startメソッドを呼び出し
        self.menu_system.start(main_menu)

        # 実行状態が正しく管理されることを確認
        assert self.menu_system.running is False

    @patch("rich.prompt.Prompt.ask")
    def test_menu_display_content(self, mock_prompt):
        """メニュー表示内容の統合テスト"""
        setup_stable_prompt_mock(mock_prompt, ["q"])

        main_menu = self.builder.build_main_menu()

        # メニューを表示
        self.menu_system.show_menu(main_menu)
        output = self.output.getvalue()

        # 主要なメニュー項目が表示されることを確認
        assert "CI-Helper メインメニュー" in output
        assert "初期設定" in output
        assert "環境チェック" in output
        assert "CI/CDテスト" in output
        assert "AI分析" in output
        assert "ログ管理" in output
        assert "シークレット管理" in output
        assert "キャッシュ管理" in output
        assert "クリーンアップ" in output
        assert "終了" in output

    @patch("ci_helper.utils.workflow_detector.WorkflowDetector")
    @patch("rich.prompt.Prompt.ask")
    def test_workflow_selection_integration(self, mock_prompt, mock_detector_class):
        """ワークフロー選択の統合テスト"""
        # モックワークフローを設定
        mock_workflow = Mock()
        mock_workflow.name = "Test Workflow"
        mock_workflow.filename = "test.yml"
        mock_workflow.jobs = ["test", "build"]

        mock_detector = Mock()
        mock_detector.find_workflows.return_value = [mock_workflow]
        mock_detector.get_workflow_choices.return_value = {"1": mock_workflow}
        mock_detector_class.return_value = mock_detector

        # ユーザー入力をシミュレート: CI/CDテスト → 特定ワークフロー実行 → ワークフロー選択 → 戻る → 戻る → 終了
        setup_stable_prompt_mock(mock_prompt, ["3", "2", "1", "b", "b", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # ワークフロー検出が呼び出されることを確認
        mock_detector.find_workflows.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    @patch("rich.prompt.Confirm.ask")
    def test_cache_clear_confirmation_integration(self, mock_confirm, mock_prompt):
        """キャッシュクリア確認の統合テスト"""
        mock_confirm.return_value = True

        # ユーザー入力をシミュレート: キャッシュ管理 → キャッシュクリア → 確認 → 戻る → 戻る → 終了
        setup_stable_prompt_mock(mock_prompt, ["7", "4", "b", "b", "q"])

        main_menu = self.builder.build_main_menu()

        with patch.object(self.menu_system, "console") as mock_console:
            mock_console.clear = Mock()
            mock_console.print = Mock()
            self.menu_system.run_menu(main_menu)

        # 確認ダイアログが表示されることを確認
        mock_confirm.assert_called_once()

    def test_menu_system_state_consistency(self):
        """メニューシステムの状態一貫性テスト"""
        main_menu = self.builder.build_main_menu()

        # 初期状態の確認
        assert self.menu_system.is_running() is False
        assert self.menu_system.get_current_menu() is None
        assert len(self.menu_system.menu_stack) == 0

        # メニューをスタックにプッシュ
        self.menu_system.menu_stack.append(main_menu)

        # 状態の確認
        assert self.menu_system.get_current_menu() == main_menu
        assert len(self.menu_system.menu_stack) == 1

        # スタックをクリア
        self.menu_system.menu_stack.clear()

        # 最終状態の確認
        assert self.menu_system.get_current_menu() is None
        assert len(self.menu_system.menu_stack) == 0
