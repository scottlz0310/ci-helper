"""
進行状況表示ユーティリティのテスト
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from ci_helper.utils.progress_display import ProgressDisplayManager, get_progress_manager
from rich.console import Console


class TestProgressDisplayManager:
    """ProgressDisplayManagerのテスト"""

    def setup_method(self):
        """テストセットアップ"""
        self.console = Mock()
        self.console.get_time = Mock(return_value=0.0)
        self.console.print = Mock()
        # コンテキストマネージャープロトコルをサポート
        self.console.__enter__ = Mock(return_value=self.console)
        self.console.__exit__ = Mock(return_value=None)
        # Rich Progress が期待する属性を追加
        self.console.is_terminal = True
        self.console.size = Mock(return_value=(80, 24))
        self.console.options = Mock()
        self.console.file = Mock()
        self.console._live_stack = []
        self.manager = ProgressDisplayManager(self.console)

    def test_init(self):
        """初期化のテスト"""
        assert self.manager.console == self.console
        assert self.manager._large_file_threshold == 10 * 1024 * 1024

    def test_show_processing_start_message(self):
        """処理開始メッセージ表示のテスト"""
        # 基本的な呼び出し
        self.manager.show_processing_start_message(
            format_type="ai",
            input_file="test.log",
            output_file="output.md",
            filter_errors=True,
            verbose_level="normal",
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    def test_show_processing_start_message_no_files(self):
        """ファイル指定なしの処理開始メッセージ表示のテスト"""
        self.manager.show_processing_start_message(
            format_type="human",
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    def test_is_large_file(self):
        """大きなファイル判定のテスト"""
        # ファイルなしの場合
        assert not self.manager.is_large_file(None)

        # 存在しないファイルの場合
        assert not self.manager.is_large_file("nonexistent.log")

        # 実際のファイルでテスト
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

            # 小さなファイル
            tmp_path.write_text("small content")
            assert not self.manager.is_large_file(str(tmp_path))

            # 大きなファイル（閾値を下げてテスト）
            self.manager.set_large_file_threshold(0.001)  # 1KB
            large_content = "x" * 2048  # 2KB
            tmp_path.write_text(large_content)
            assert self.manager.is_large_file(str(tmp_path))

            # クリーンアップ
            tmp_path.unlink()

    def test_create_progress_context(self):
        """進行状況コンテキスト作成のテスト"""
        # 基本的な設定
        progress = self.manager.create_progress_context()
        assert progress is not None

        # カスタム設定
        progress = self.manager.create_progress_context(
            task_description="カスタムタスク",
            show_elapsed=True,
            show_bar=True,
        )
        assert progress is not None

    @patch("ci_helper.utils.progress_display.Progress")
    def test_execute_with_progress_simple(self, mock_progress_class):
        """シンプルな進行状況表示付き実行のテスト"""
        # Progress インスタンスのモック
        mock_progress = Mock()
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        mock_progress.update = Mock()
        mock_progress_class.return_value = mock_progress

        def mock_task():
            return "test result"

        result = self.manager.execute_with_progress(
            task_func=mock_task,
            task_description="テスト中...",
            completion_description="テスト完了",
            show_detailed_progress=False,
        )

        assert result == "test result"
        mock_progress_class.assert_called_once()
        mock_progress.add_task.assert_called_once()
        mock_progress.update.assert_called()

    @patch("ci_helper.utils.progress_display.Progress")
    def test_execute_with_progress_detailed(self, mock_progress_class):
        """詳細な進行状況表示付き実行のテスト"""
        # Progress インスタンスのモック
        mock_progress = Mock()
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        mock_progress.update = Mock()
        mock_progress_class.return_value = mock_progress

        def mock_task():
            return "detailed result"

        result = self.manager.execute_with_progress(
            task_func=mock_task,
            task_description="詳細テスト中...",
            completion_description="詳細テスト完了",
            show_detailed_progress=True,
        )

        assert result == "detailed result"
        mock_progress_class.assert_called_once()
        mock_progress.add_task.assert_called_once()
        # 詳細モードでは複数回updateが呼ばれる
        assert mock_progress.update.call_count >= 1

    @patch("ci_helper.utils.progress_display.Progress")
    def test_execute_with_progress_auto_detection(self, mock_progress_class):
        """自動判定による進行状況表示のテスト"""
        # Progress インスタンスのモック
        mock_progress = Mock()
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        mock_progress.update = Mock()
        mock_progress_class.return_value = mock_progress

        def mock_task():
            return "auto result"

        # 小さなファイル（シンプル表示）
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_text("small")

            result = self.manager.execute_with_progress(
                task_func=mock_task,
                input_file=str(tmp_path),
            )

            assert result == "auto result"
            mock_progress_class.assert_called_once()
            mock_progress.add_task.assert_called_once()
            mock_progress.update.assert_called()
            tmp_path.unlink()

    @patch("ci_helper.utils.progress_display.Progress")
    def test_execute_with_progress_error(self, mock_progress_class):
        """進行状況表示付き実行でのエラーハンドリングのテスト"""
        # Progress インスタンスのモック
        mock_progress = Mock()
        mock_progress.__enter__ = Mock(return_value=mock_progress)
        mock_progress.__exit__ = Mock(return_value=None)
        mock_progress.add_task = Mock(return_value="task_id")
        mock_progress.update = Mock()
        mock_progress_class.return_value = mock_progress

        def error_task():
            raise ValueError("テストエラー")

        with pytest.raises(ValueError, match="テストエラー"):
            self.manager.execute_with_progress(
                task_func=error_task,
                task_description="エラーテスト中...",
            )

        # エラーが発生してもProgressが適切に呼ばれることを確認
        mock_progress_class.assert_called_once()
        mock_progress.add_task.assert_called_once()
        # エラー時にもupdateが呼ばれる（エラーメッセージ表示のため）
        mock_progress.update.assert_called()

    def test_show_success_message(self):
        """成功メッセージ表示のテスト"""
        self.manager.show_success_message(
            format_type="ai",
            output_file="output.md",
            processing_time=1.5,
            failure_count=3,
            total_lines=100,
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    def test_show_success_message_no_file(self):
        """ファイル出力なしの成功メッセージ表示のテスト"""
        self.manager.show_success_message(
            format_type="human",
            processing_time=0.8,
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    def test_show_error_message(self):
        """エラーメッセージ表示のテスト"""
        error = ValueError("テストエラー")
        suggestions = ["提案1", "提案2"]

        self.manager.show_error_message(
            error=error,
            context="テストコンテキスト",
            suggestions=suggestions,
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    def test_show_error_message_no_suggestions(self):
        """修正提案なしのエラーメッセージ表示のテスト"""
        error = RuntimeError("実行時エラー")

        self.manager.show_error_message(
            error=error,
            context="実行時コンテキスト",
        )

        # コンソール出力が呼ばれたことを確認
        assert self.console.print.called

    @patch("ci_helper.utils.progress_display.Confirm.ask")
    def test_show_menu_return_option_simple(self, mock_confirm):
        """シンプルなメニュー戻りオプションのテスト"""
        mock_confirm.return_value = True

        result = self.manager.show_menu_return_option()

        assert result is True
        mock_confirm.assert_called_once()

    @patch("ci_helper.utils.progress_display.Confirm.ask")
    def test_show_menu_return_option_with_func(self, mock_confirm):
        """関数付きメニュー戻りオプションのテスト"""
        mock_confirm.return_value = True
        mock_func = Mock()

        result = self.manager.show_menu_return_option(mock_func)

        assert result is True
        mock_confirm.assert_called_once()
        mock_func.assert_called_once()

    @patch("ci_helper.utils.progress_display.Confirm.ask")
    def test_show_menu_return_option_declined(self, mock_confirm):
        """メニュー戻りを拒否した場合のテスト"""
        mock_confirm.return_value = False

        result = self.manager.show_menu_return_option()

        assert result is False
        mock_confirm.assert_called_once()

    def test_get_file_processing_suggestions(self):
        """ファイル処理エラーの修正提案生成のテスト"""
        # FileNotFoundError
        error = FileNotFoundError("ファイルが見つかりません")
        suggestions = self.manager.get_file_processing_suggestions(error, "test.log")

        assert len(suggestions) > 0
        assert any("ファイルパス" in s for s in suggestions)

        # PermissionError
        error = PermissionError("権限がありません")
        suggestions = self.manager.get_file_processing_suggestions(error)

        assert len(suggestions) > 0
        assert any("権限" in s for s in suggestions)

        # UnicodeDecodeError
        error = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid start byte")
        suggestions = self.manager.get_file_processing_suggestions(error)

        assert len(suggestions) > 0
        assert any("エンコーディング" in s for s in suggestions)

        # MemoryError
        error = MemoryError("メモリ不足")
        suggestions = self.manager.get_file_processing_suggestions(error)

        assert len(suggestions) > 0
        assert any("メモリ" in s for s in suggestions)

        # JSON関連エラー
        error = ValueError("JSON decode error")
        suggestions = self.manager.get_file_processing_suggestions(error)

        assert len(suggestions) > 0
        assert any("JSON" in s for s in suggestions)

        # 一般的なエラー
        error = RuntimeError("一般的なエラー")
        suggestions = self.manager.get_file_processing_suggestions(error)

        assert len(suggestions) > 0

    def test_set_large_file_threshold(self):
        """大きなファイル閾値設定のテスト"""
        # デフォルト値の確認
        assert self.manager._large_file_threshold == 10 * 1024 * 1024

        # 新しい閾値を設定
        self.manager.set_large_file_threshold(5.0)
        assert self.manager._large_file_threshold == 5 * 1024 * 1024

        # 小数点の閾値を設定
        self.manager.set_large_file_threshold(0.5)
        assert self.manager._large_file_threshold == int(0.5 * 1024 * 1024)


class TestGlobalFunctions:
    """グローバル関数のテスト"""

    def test_get_progress_manager(self):
        """グローバル進行状況マネージャー取得のテスト"""
        # 初回取得
        manager1 = get_progress_manager()
        assert isinstance(manager1, ProgressDisplayManager)

        # 同じインスタンスが返されることを確認
        manager2 = get_progress_manager()
        assert manager1 is manager2

        # 異なるコンソールを指定した場合
        console = Console()
        manager3 = get_progress_manager(console)
        assert manager3 is not manager1
        assert manager3.console == console

    def test_reset_progress_manager(self):
        """グローバル進行状況マネージャーリセットのテスト"""
        from ci_helper.utils.progress_display import reset_progress_manager

        # マネージャーを取得
        manager1 = get_progress_manager()

        # リセット
        reset_progress_manager()

        # 新しいインスタンスが返されることを確認
        manager2 = get_progress_manager()
        assert manager1 is not manager2
