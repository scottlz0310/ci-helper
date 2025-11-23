"""
メニューシステムのテスト

MenuSystem、MenuItem、Menu クラスの機能をテストします。
"""

from io import StringIO
from unittest.mock import Mock, patch

from ci_helper.ui.menu_system import Menu, MenuItem, MenuSystem
from rich.console import Console

from tests.utils.mock_helpers import setup_stable_prompt_mock


class TestMenuItem:
    """MenuItem クラスのテスト"""

    def test_menu_item_creation(self):
        """メニュー項目の作成をテスト"""
        action = Mock()
        item = MenuItem(
            key="1", title="テストアイテム", description="テスト用のメニュー項目", action=action, enabled=True
        )

        assert item.key == "1"
        assert item.title == "テストアイテム"
        assert item.description == "テスト用のメニュー項目"
        assert item.action == action
        assert item.submenu is None
        assert item.enabled is True

    def test_menu_item_with_submenu(self):
        """サブメニュー付きメニュー項目のテスト"""
        submenu = Menu(title="サブメニュー", items=[])
        item = MenuItem(key="2", title="サブメニューアイテム", description="サブメニューを持つ項目", submenu=submenu)

        assert item.submenu == submenu
        assert item.action is None

    def test_menu_item_disabled(self):
        """無効化されたメニュー項目のテスト"""
        item = MenuItem(key="3", title="無効アイテム", description="無効化されたアイテム", enabled=False)

        assert item.enabled is False


class TestMenu:
    """Menu クラスのテスト"""

    def test_menu_creation(self):
        """メニューの作成をテスト"""
        items = [
            MenuItem(key="1", title="項目1", description="説明1"),
            MenuItem(key="2", title="項目2", description="説明2"),
        ]
        menu = Menu(title="テストメニュー", items=items, show_back=True, show_quit=False)

        assert menu.title == "テストメニュー"
        assert menu.items == items
        assert menu.show_back is True
        assert menu.show_quit is False

    def test_menu_default_options(self):
        """メニューのデフォルトオプションをテスト"""
        menu = Menu(title="デフォルトメニュー", items=[])

        assert menu.show_back is False
        assert menu.show_quit is True


class TestMenuSystem:
    """MenuSystem クラスのテスト"""

    def setup_method(self):
        """テストセットアップ"""
        # StringIO を使用してコンソール出力をキャプチャ
        self.output = StringIO()
        self.console = Console(file=self.output, width=80, legacy_windows=False)
        self.menu_system = MenuSystem(self.console)

    def test_menu_system_initialization(self):
        """メニューシステムの初期化をテスト"""
        assert self.menu_system.console == self.console
        assert self.menu_system.menu_stack == []
        assert self.menu_system.running is False

    def test_menu_system_with_default_console(self):
        """デフォルトコンソールでのメニューシステム初期化をテスト"""
        menu_system = MenuSystem()
        assert menu_system.console is not None
        assert isinstance(menu_system.console, Console)

    def test_show_menu_basic(self):
        """基本的なメニュー表示をテスト"""
        items = [
            MenuItem(key="1", title="項目1", description="説明1", enabled=True),
            MenuItem(key="2", title="項目2", description="説明2", enabled=True),
        ]
        menu = Menu(title="テストメニュー", items=items)

        self.menu_system.show_menu(menu)
        output = self.output.getvalue()

        # メニュータイトルが表示されることを確認
        assert "テストメニュー" in output
        # メニュー項目が表示されることを確認
        assert "項目1" in output
        assert "項目2" in output
        assert "説明1" in output
        assert "説明2" in output

    def test_show_menu_with_disabled_item(self):
        """無効化された項目を含むメニュー表示をテスト"""
        items = [
            MenuItem(key="1", title="有効項目", description="有効な項目", enabled=True),
            MenuItem(key="2", title="無効項目", description="無効な項目", enabled=False),
        ]
        menu = Menu(title="テストメニュー", items=items)

        self.menu_system.show_menu(menu)
        output = self.output.getvalue()

        # 有効な項目のみが表示されることを確認
        assert "有効項目" in output
        assert "無効項目" not in output

    def test_show_menu_with_back_option(self):
        """戻るオプション付きメニュー表示をテスト"""
        menu = Menu(title="サブメニュー", items=[MenuItem(key="1", title="項目1", description="説明1")], show_back=True)

        self.menu_system.show_menu(menu)
        output = self.output.getvalue()

        assert "戻る" in output

    def test_show_menu_with_quit_option(self):
        """終了オプション付きメニュー表示をテスト"""
        menu = Menu(
            title="メインメニュー", items=[MenuItem(key="1", title="項目1", description="説明1")], show_quit=True
        )

        self.menu_system.show_menu(menu)
        output = self.output.getvalue()

        assert "終了" in output

    @patch("rich.prompt.Prompt.ask")
    def test_get_user_choice_valid(self, mock_prompt):
        """有効なユーザー選択の処理をテスト"""
        mock_prompt.return_value = "1"

        items = [MenuItem(key="1", title="項目1", description="説明1", enabled=True)]
        menu = Menu(title="テストメニュー", items=items)

        choice = self.menu_system.get_user_choice(menu)
        assert choice == "1"

    @patch("rich.prompt.Prompt.ask")
    def test_get_user_choice_case_insensitive(self, mock_prompt):
        """大文字小文字を区別しない選択の処理をテスト"""
        mock_prompt.return_value = "Q"

        menu = Menu(title="テストメニュー", items=[], show_quit=True)

        choice = self.menu_system.get_user_choice(menu)
        assert choice == "q"

    @patch("rich.prompt.Prompt.ask")
    def test_get_user_choice_invalid_then_valid(self, mock_prompt):
        """無効な選択の後に有効な選択をした場合のテスト"""
        setup_stable_prompt_mock(mock_prompt, ["invalid", "1"])

        items = [MenuItem(key="1", title="項目1", description="説明1", enabled=True)]
        menu = Menu(title="テストメニュー", items=items)

        choice = self.menu_system.get_user_choice(menu)
        assert choice == "1"
        # 2回呼び出されることを確認
        assert mock_prompt.call_count == 2

    @patch("rich.prompt.Prompt.ask")
    def test_get_user_choice_keyboard_interrupt(self, mock_prompt):
        """キーボード割り込み時の処理をテスト"""
        mock_prompt.side_effect = KeyboardInterrupt()

        menu = Menu(title="テストメニュー", items=[])

        choice = self.menu_system.get_user_choice(menu)
        assert choice == "q"

    @patch("rich.prompt.Prompt.ask")
    def test_get_user_choice_eof_error(self, mock_prompt):
        """EOF エラー時の処理をテスト"""
        mock_prompt.side_effect = EOFError()

        menu = Menu(title="テストメニュー", items=[])

        choice = self.menu_system.get_user_choice(menu)
        assert choice == "q"

    def test_execute_menu_item_with_action(self):
        """アクション付きメニュー項目の実行をテスト"""
        action_mock = Mock(return_value="実行結果")
        item = MenuItem(key="1", title="テストアクション", description="テスト用アクション", action=action_mock)

        with patch("rich.prompt.Prompt.ask") as mock_prompt:
            mock_prompt.return_value = ""  # Enter キーをシミュレート
            result = self.menu_system.execute_menu_item(item)

        assert result is True
        action_mock.assert_called_once()

    def test_execute_menu_item_with_submenu(self):
        """サブメニュー付きメニュー項目の実行をテスト"""
        submenu = Menu(title="サブメニュー", items=[])
        item = MenuItem(key="1", title="サブメニューアイテム", description="サブメニューを持つ項目", submenu=submenu)

        with patch.object(self.menu_system, "run_menu") as mock_run_menu:
            result = self.menu_system.execute_menu_item(item)

        assert result is True
        mock_run_menu.assert_called_once_with(submenu)

    def test_execute_menu_item_action_exception(self):
        """アクション実行時の例外処理をテスト"""
        action_mock = Mock(side_effect=Exception("テストエラー"))
        item = MenuItem(
            key="1", title="エラーアクション", description="エラーを発生させるアクション", action=action_mock
        )

        with patch("rich.prompt.Prompt.ask") as mock_prompt:
            mock_prompt.return_value = ""
            result = self.menu_system.execute_menu_item(item)

        assert result is True  # エラーが発生してもメニューは継続
        action_mock.assert_called_once()

    def test_execute_menu_item_keyboard_interrupt(self):
        """メニュー項目実行時のキーボード割り込みをテスト"""
        action_mock = Mock(side_effect=KeyboardInterrupt())
        item = MenuItem(
            key="1",
            title="割り込みアクション",
            description="キーボード割り込みを発生させるアクション",
            action=action_mock,
        )

        result = self.menu_system.execute_menu_item(item)

        assert result is True  # 割り込みが発生してもメニューは継続
        action_mock.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_run_menu_quit_selection(self, mock_prompt):
        """終了選択時のメニュー実行をテスト"""
        mock_prompt.return_value = "q"

        menu = Menu(title="テストメニュー", items=[], show_quit=True)

        with patch.object(self.menu_system, "show_menu") as mock_show_menu:
            self.menu_system.run_menu(menu)

        mock_show_menu.assert_called_once_with(menu)
        # メニュースタックが正しく管理されることを確認
        assert len(self.menu_system.menu_stack) == 0

    @patch("rich.prompt.Prompt.ask")
    def test_run_menu_back_selection(self, mock_prompt):
        """戻る選択時のメニュー実行をテスト"""
        mock_prompt.return_value = "b"

        menu = Menu(title="サブメニュー", items=[], show_back=True)

        with patch.object(self.menu_system, "show_menu") as mock_show_menu:
            self.menu_system.run_menu(menu)

        mock_show_menu.assert_called_once_with(menu)

    @patch("rich.prompt.Prompt.ask")
    def test_run_menu_item_selection(self, mock_prompt):
        """メニュー項目選択時の実行をテスト"""
        mock_prompt.return_value = "1"
        action_mock = Mock(return_value=None)

        items = [MenuItem(key="1", title="項目1", description="説明1", action=action_mock, enabled=True)]
        menu = Menu(title="テストメニュー", items=items)

        with patch.object(self.menu_system, "show_menu") as mock_show_menu:
            with patch.object(self.menu_system, "execute_menu_item", return_value=False) as mock_execute:
                self.menu_system.run_menu(menu)

        mock_show_menu.assert_called_once_with(menu)
        mock_execute.assert_called_once_with(items[0])

    def test_is_running_initial_state(self):
        """初期状態での実行状態をテスト"""
        assert self.menu_system.is_running() is False

    def test_get_current_menu_empty_stack(self):
        """空のスタック時の現在メニュー取得をテスト"""
        assert self.menu_system.get_current_menu() is None

    def test_get_current_menu_with_stack(self):
        """スタックにメニューがある時の現在メニュー取得をテスト"""
        menu = Menu(title="テストメニュー", items=[])
        self.menu_system.menu_stack.append(menu)

        current = self.menu_system.get_current_menu()
        assert current == menu

    @patch("rich.prompt.Prompt.ask")
    def test_start_menu_system(self, mock_prompt):
        """メニューシステムの開始をテスト"""
        mock_prompt.return_value = "q"

        main_menu = Menu(title="メインメニュー", items=[], show_quit=True)

        with patch.object(self.menu_system, "run_menu") as mock_run_menu:
            self.menu_system.start(main_menu)

        mock_run_menu.assert_called_once_with(main_menu)
        # 実行状態が正しく管理されることを確認
        assert self.menu_system.running is False

    def test_start_menu_system_keyboard_interrupt(self):
        """メニューシステム開始時のキーボード割り込みをテスト"""
        main_menu = Menu(title="メインメニュー", items=[])

        with patch.object(self.menu_system, "run_menu", side_effect=KeyboardInterrupt()):
            self.menu_system.start(main_menu)

        assert self.menu_system.running is False

    def test_start_menu_system_exception(self):
        """メニューシステム開始時の例外処理をテスト"""
        main_menu = Menu(title="メインメニュー", items=[])

        with patch.object(self.menu_system, "run_menu", side_effect=Exception("テストエラー")):
            self.menu_system.start(main_menu)

        assert self.menu_system.running is False
