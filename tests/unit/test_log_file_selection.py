"""
ログファイル選択機能のテスト

Task 6の実装をテストします。
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from src.ci_helper.ui.command_menus import CommandMenuBuilder


class TestLogFileSelection:
    """ログファイル選択機能のテストクラス"""

    def setup_method(self):
        """テストセットアップ"""
        self.console = Console()
        self.command_handlers = {}
        self.builder = CommandMenuBuilder(self.console, self.command_handlers)

    def create_test_logs(self):
        """テスト用のログファイルを作成"""
        temp_dir = Path(tempfile.mkdtemp())

        # テスト用ログファイルを作成
        log1 = temp_dir / "act_20240101_120000.log"
        log2 = temp_dir / "act_20240102_130000.log"
        log3 = temp_dir / "act_20240103_140000.log"

        log1.write_text("Test log 1 content")
        log2.write_text("Test log 2 content")
        log3.write_text("Test log 3 content")

        return temp_dir, [log1, log2, log3]

    @patch("rich.prompt.Prompt.ask")
    def test_select_log_file_latest(self, mock_prompt):
        """最新ログ選択のテスト"""
        mock_prompt.return_value = "latest"

        result = self.builder._select_log_file()

        assert result is None  # 最新ログの場合はNoneを返す
        mock_prompt.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_select_log_file_specific_existing_file(self, mock_prompt):
        """特定ログ選択（存在するファイル）のテスト"""
        _temp_dir, log_files = self.create_test_logs()
        existing_file = str(log_files[0])

        mock_prompt.side_effect = ["specific", existing_file]

        result = self.builder._select_log_file()

        assert result == existing_file
        assert mock_prompt.call_count == 2

    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_select_log_file_specific_non_existing_file(self, mock_prompt, mock_confirm):
        """特定ログ選択（存在しないファイル）のテスト"""
        temp_dir, _log_files = self.create_test_logs()
        non_existing_file = str(temp_dir / "non_existing.log")

        mock_prompt.side_effect = ["specific", non_existing_file]
        mock_confirm.return_value = False  # 再試行しない

        result = self.builder._select_log_file()

        assert result is None
        mock_confirm.assert_called_once()

    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_select_log_file_specific_retry(self, mock_prompt, mock_confirm):
        """特定ログ選択（再試行）のテスト"""
        temp_dir, log_files = self.create_test_logs()
        non_existing_file = str(temp_dir / "non_existing.log")
        existing_file = str(log_files[0])

        mock_prompt.side_effect = [
            "specific",
            non_existing_file,  # 最初は存在しないファイル
            existing_file,  # 再試行で存在するファイル
        ]
        mock_confirm.return_value = True  # 再試行する

        result = self.builder._select_log_file()

        assert result == existing_file
        mock_confirm.assert_called_once()

    def test_input_custom_log_path_existing_file(self):
        """カスタムファイルパス入力（存在するファイル）のテスト"""
        _temp_dir, log_files = self.create_test_logs()
        existing_file = str(log_files[0])

        with patch("rich.prompt.Prompt.ask", return_value=existing_file):
            result = self.builder._input_custom_log_path()

        assert result == existing_file

    def test_input_custom_log_path_empty_input(self):
        """カスタムファイルパス入力（空入力）のテスト"""
        with patch("rich.prompt.Prompt.ask", return_value=""):
            result = self.builder._input_custom_log_path()

        assert result is None

    def test_input_custom_log_path_directory(self):
        """カスタムファイルパス入力（ディレクトリ）のテスト"""
        temp_dir, _ = self.create_test_logs()

        with patch("rich.prompt.Prompt.ask", return_value=str(temp_dir)):
            result = self.builder._input_custom_log_path()

        assert result is None  # ディレクトリの場合はNoneを返す

    @patch("src.ci_helper.core.log_manager.LogManager")
    @patch("src.ci_helper.utils.config.Config")
    @patch("rich.prompt.Prompt.ask")
    def test_select_from_log_list_success(self, mock_prompt, mock_config, mock_log_manager):
        """ログ一覧からの選択（成功）のテスト"""
        # モックの設定
        mock_log_manager_instance = Mock()
        mock_log_manager.return_value = mock_log_manager_instance

        # テスト用ログデータ
        test_logs = [
            {
                "log_file": "act_20240103_140000.log",
                "timestamp": "2024-01-03T14:00:00",
                "success": True,
                "total_duration": 120.5,
            },
            {
                "log_file": "act_20240102_130000.log",
                "timestamp": "2024-01-02T13:00:00",
                "success": False,
                "total_duration": 85.2,
            },
        ]

        mock_log_manager_instance.list_logs.return_value = test_logs
        mock_log_manager_instance.log_dir = Path("/tmp/logs")  # noqa: S108

        # ファイル存在チェックのモック
        with patch("pathlib.Path.exists", return_value=True):
            mock_prompt.return_value = "1"  # 最初のログを選択

            result = self.builder._select_from_log_list()

        expected_path = "/tmp/logs/act_20240103_140000.log"  # noqa: S108
        assert result == expected_path
        mock_log_manager_instance.list_logs.assert_called_once_with(limit=20)

    @patch("src.ci_helper.core.log_manager.LogManager")
    @patch("src.ci_helper.utils.config.Config")
    def test_select_from_log_list_no_logs(self, mock_config, mock_log_manager):
        """ログ一覧からの選択（ログなし）のテスト"""
        # モックの設定
        mock_log_manager_instance = Mock()
        mock_log_manager.return_value = mock_log_manager_instance
        mock_log_manager_instance.list_logs.return_value = []

        result = self.builder._select_from_log_list()

        assert result is None

    @patch("src.ci_helper.core.log_manager.LogManager")
    @patch("src.ci_helper.utils.config.Config")
    @patch("rich.prompt.Prompt.ask")
    def test_select_from_log_list_file_not_exists(self, mock_prompt, mock_config, mock_log_manager):
        """ログ一覧からの選択（ファイル存在しない）のテスト"""
        # モックの設定
        mock_log_manager_instance = Mock()
        mock_log_manager.return_value = mock_log_manager_instance

        test_logs = [
            {
                "log_file": "act_20240103_140000.log",
                "timestamp": "2024-01-03T14:00:00",
                "success": True,
                "total_duration": 120.5,
            }
        ]

        mock_log_manager_instance.list_logs.return_value = test_logs
        mock_log_manager_instance.log_dir = Path("/tmp/logs")  # noqa: S108

        # ファイルが存在しない場合
        with patch("pathlib.Path.exists", return_value=False):
            mock_prompt.return_value = "1"

            result = self.builder._select_from_log_list()

        assert result is None

    def test_show_available_logs_hint_with_logs(self):
        """利用可能ログヒント表示（ログあり）のテスト"""
        with patch("src.ci_helper.core.log_manager.LogManager") as mock_log_manager:
            with patch("src.ci_helper.utils.config.Config"):
                mock_log_manager_instance = Mock()
                mock_log_manager.return_value = mock_log_manager_instance

                test_logs = [{"log_file": "act_20240103_140000.log", "timestamp": "2024-01-03T14:00:00"}]

                mock_log_manager_instance.list_logs.return_value = test_logs
                mock_log_manager_instance.log_dir = Path("/tmp/logs")  # noqa: S108

                # エラーが発生しないことを確認
                self.builder._show_available_logs_hint()

    def test_show_available_logs_hint_no_logs(self):
        """利用可能ログヒント表示（ログなし）のテスト"""
        with patch("src.ci_helper.core.log_manager.LogManager") as mock_log_manager:
            with patch("src.ci_helper.utils.config.Config"):
                mock_log_manager_instance = Mock()
                mock_log_manager.return_value = mock_log_manager_instance
                mock_log_manager_instance.list_logs.return_value = []

                # エラーが発生しないことを確認
                self.builder._show_available_logs_hint()

    def test_show_available_logs_hint_exception(self):
        """利用可能ログヒント表示（例外発生）のテスト"""
        with patch("src.ci_helper.core.log_manager.LogManager", side_effect=Exception("Test error")):
            # 例外が発生してもエラーにならないことを確認
            self.builder._show_available_logs_hint()

    @patch("src.ci_helper.utils.progress_display.ProgressDisplayManager.show_menu_return_option")
    @patch("rich.prompt.Prompt.ask")
    def test_create_latest_log_format_action_console_output(self, mock_prompt, mock_menu_return):
        """最新ログ整形アクション（コンソール出力）のテスト"""
        mock_prompt.return_value = "console"
        mock_menu_return.return_value = None

        action = self.builder._create_latest_log_format_action("ai")

        # アクションが呼び出し可能であることを確認
        assert callable(action)

        # アクションを実行（format_logsハンドラーがない場合）
        result = action()

        # エラーが発生しないことを確認
        assert result is None
        # メニューに戻るオプションが呼び出されることを確認
        mock_menu_return.assert_called()

    @patch("src.ci_helper.utils.progress_display.ProgressDisplayManager.show_menu_return_option")
    @patch("rich.prompt.Prompt.ask")
    def test_create_latest_log_format_action_file_output(self, mock_prompt, mock_menu_return):
        """最新ログ整形アクション（ファイル出力）のテスト"""
        mock_prompt.side_effect = ["file", "test_output.md"]
        mock_menu_return.return_value = None

        action = self.builder._create_latest_log_format_action("ai")

        # アクションが呼び出し可能であることを確認
        assert callable(action)

        # アクションを実行（format_logsハンドラーがない場合）
        result = action()

        # エラーが発生しないことを確認
        assert result is None
        # メニューに戻るオプションが呼び出されることを確認
        mock_menu_return.assert_called()

    @patch("rich.prompt.Prompt.ask")
    def test_create_latest_log_format_action_with_handler(self, mock_prompt):
        """最新ログ整形アクション（ハンドラーあり）のテスト"""
        mock_prompt.return_value = "console"

        # format_logsハンドラーを追加
        mock_handler = Mock(return_value="success")
        self.builder.command_handlers["format_logs"] = mock_handler

        action = self.builder._create_latest_log_format_action("ai")
        result = action()

        # ハンドラーが正しい引数で呼び出されることを確認
        # 実装では return_to_menu_func も渡されるため、それを含めて確認
        call_args = mock_handler.call_args
        assert call_args[1]["format_type"] == "ai"
        assert call_args[1]["input_file"] is None  # 最新ログの場合はNone
        assert call_args[1]["output_file"] is None
        assert "return_to_menu_func" in call_args[1]  # return_to_menu_func が含まれることを確認
        assert result == "success"

    def test_log_formatting_submenu_structure(self):
        """ログ整形サブメニュー構造のテスト"""
        submenu = self.builder._build_log_formatting_submenu()

        assert submenu.title == "ログ整形メニュー"
        assert len(submenu.items) == 3

        # 最新ログ整形
        assert submenu.items[0].title == "最新ログ整形"
        assert submenu.items[0].submenu is not None

        # 特定ログ整形
        assert submenu.items[1].title == "特定ログ整形"
        assert submenu.items[1].submenu is not None

        # カスタム整形
        assert submenu.items[2].title == "カスタム整形"
        assert submenu.items[2].action is not None

    def test_latest_log_formatting_submenu_structure(self):
        """最新ログ整形サブメニュー構造のテスト"""
        submenu = self.builder._build_latest_log_formatting_submenu()

        assert submenu.title == "最新ログ整形メニュー"
        assert len(submenu.items) == 3

        # AI分析用フォーマット
        assert submenu.items[0].title == "AI分析用フォーマット"
        assert submenu.items[0].action is not None

        # 人間可読フォーマット
        assert submenu.items[1].title == "人間可読フォーマット"
        assert submenu.items[1].action is not None

        # JSON形式
        assert submenu.items[2].title == "JSON形式"
        assert submenu.items[2].action is not None

    def test_specific_log_formatting_submenu_structure(self):
        """特定ログ整形サブメニュー構造のテスト"""
        submenu = self.builder._build_specific_log_formatting_submenu()

        assert submenu.title == "特定ログ整形メニュー"
        assert len(submenu.items) == 3

        # AI分析用フォーマット
        assert submenu.items[0].title == "AI分析用フォーマット"
        assert submenu.items[0].action is not None

        # 人間可読フォーマット
        assert submenu.items[1].title == "人間可読フォーマット"
        assert submenu.items[1].action is not None

        # JSON形式
        assert submenu.items[2].title == "JSON形式"
        assert submenu.items[2].action is not None
