"""
ファイル保存ユーティリティのテスト
"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from ci_helper.utils.file_save_utils import FileSaveManager


class TestFileSaveManager:
    """FileSaveManagerのテストクラス"""

    def setup_method(self):
        """テストメソッドの前処理"""
        self.console = MagicMock(spec=Console)
        self.file_manager = FileSaveManager(self.console)

    def test_init_with_console(self):
        """コンソール指定での初期化テスト"""
        console = MagicMock(spec=Console)
        manager = FileSaveManager(console)
        assert manager.console == console

    def test_init_without_console(self):
        """コンソール未指定での初期化テスト"""
        manager = FileSaveManager()
        assert isinstance(manager.console, Console)

    def test_generate_default_filename_basic(self):
        """基本的なデフォルトファイル名生成テスト"""
        filename = self.file_manager.generate_default_filename("ai")
        assert filename.startswith("formatted_log_ai_")
        assert filename.endswith(".md")

    def test_generate_default_filename_json(self):
        """JSON形式のデフォルトファイル名生成テスト"""
        filename = self.file_manager.generate_default_filename("json")
        assert filename.startswith("formatted_log_json_")
        assert filename.endswith(".json")

    def test_generate_default_filename_custom_prefix(self):
        """カスタムプレフィックスでのファイル名生成テスト"""
        filename = self.file_manager.generate_default_filename("ai", prefix="custom_log")
        assert filename.startswith("custom_log_ai_")
        assert filename.endswith(".md")

    def test_generate_default_filename_no_timestamp(self):
        """タイムスタンプなしでのファイル名生成テスト"""
        filename = self.file_manager.generate_default_filename("ai", include_timestamp=False)
        assert filename == "formatted_log_ai.md"

    def test_suggest_output_file_without_input(self):
        """入力ファイルなしでの出力ファイル提案テスト"""
        filename = self.file_manager.suggest_output_file("ai")
        assert filename.startswith("formatted_log_ai_")
        assert filename.endswith(".md")

    def test_suggest_output_file_with_input(self):
        """入力ファイルありでの出力ファイル提案テスト"""
        input_file = Path("test_log.log")
        filename = self.file_manager.suggest_output_file("ai", input_file)
        assert filename.startswith("test_log_ai_")
        assert filename.endswith(".md")

    def test_save_formatted_log_to_console(self, capsys):
        """コンソール出力テスト"""
        content = "Test log content"
        success, saved_path = self.file_manager.save_formatted_log(content, output_file=None)

        assert success is True
        assert saved_path is None
        self.console.print.assert_called_once_with(content)

    def test_save_formatted_log_to_file(self, tmp_path):
        """ファイル保存テスト"""
        content = "Test log content"
        output_file = tmp_path / "test_output.md"

        success, saved_path = self.file_manager.save_formatted_log(
            content, output_file=str(output_file), confirm_overwrite=False
        )

        assert success is True
        assert saved_path == str(output_file)
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == content

    def test_save_formatted_log_create_directory(self, tmp_path):
        """ディレクトリ作成テスト"""
        content = "Test log content"
        output_file = tmp_path / "subdir" / "test_output.md"

        success, saved_path = self.file_manager.save_formatted_log(
            content, output_file=str(output_file), confirm_overwrite=False
        )

        assert success is True
        assert saved_path == str(output_file)
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == content

    @patch("rich.prompt.Confirm.ask")
    def test_save_formatted_log_overwrite_confirmed(self, mock_confirm, tmp_path):
        """ファイル上書き確認（許可）テスト"""
        # 既存ファイルを作成
        output_file = tmp_path / "existing.md"
        output_file.write_text("existing content")

        mock_confirm.return_value = True

        content = "New content"
        success, saved_path = self.file_manager.save_formatted_log(
            content, output_file=str(output_file), confirm_overwrite=True
        )

        assert success is True
        assert saved_path == str(output_file)
        assert output_file.read_text(encoding="utf-8") == content
        mock_confirm.assert_called_once()

    @patch("rich.prompt.Confirm.ask")
    def test_save_formatted_log_overwrite_denied(self, mock_confirm, tmp_path):
        """ファイル上書き確認（拒否）テスト"""
        # 既存ファイルを作成
        output_file = tmp_path / "existing.md"
        original_content = "existing content"
        output_file.write_text(original_content)

        mock_confirm.return_value = False

        content = "New content"
        success, saved_path = self.file_manager.save_formatted_log(
            content, output_file=str(output_file), confirm_overwrite=True
        )

        assert success is False
        assert saved_path is None
        assert output_file.read_text(encoding="utf-8") == original_content
        mock_confirm.assert_called_once()

    def test_save_formatted_log_permission_error(self, tmp_path):
        """権限エラーテスト"""
        # 読み取り専用ディレクトリを作成
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        output_file = readonly_dir / "test.md"
        content = "Test content"

        success, saved_path = self.file_manager.save_formatted_log(
            content, output_file=str(output_file), confirm_overwrite=False
        )

        assert success is False
        assert saved_path is None

        # クリーンアップ
        readonly_dir.chmod(0o755)

    def test_validate_output_path_valid(self, tmp_path):
        """有効なパスの検証テスト"""
        output_file = tmp_path / "valid_output.md"
        is_valid, error_msg = self.file_manager.validate_output_path(output_file)

        assert is_valid is True
        assert error_msg is None

    def test_validate_output_path_existing_file(self, tmp_path):
        """既存ファイルの検証テスト"""
        output_file = tmp_path / "existing.md"
        output_file.write_text("existing")

        is_valid, error_msg = self.file_manager.validate_output_path(output_file)

        assert is_valid is True
        assert error_msg is None

    def test_validate_output_path_dangerous_path(self):
        """危険なパスの検証テスト"""
        # 上位ディレクトリへのパス
        dangerous_path = Path("../../../etc/passwd")
        is_valid, error_msg = self.file_manager.validate_output_path(dangerous_path)

        assert is_valid is False
        assert "セキュリティ" in error_msg

    @patch("rich.prompt.Prompt.ask")
    def test_prompt_for_output_file(self, mock_prompt):
        """出力ファイルプロンプトテスト"""
        mock_prompt.return_value = "custom_output.md"

        result = self.file_manager.prompt_for_output_file("ai")

        assert result == "custom_output.md"
        mock_prompt.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_prompt_for_output_file_with_default_dir(self, mock_prompt, tmp_path):
        """デフォルトディレクトリ付きプロンプトテスト"""
        mock_prompt.return_value = "output.md"

        result = self.file_manager.prompt_for_output_file("ai", default_dir=tmp_path)

        expected = str(tmp_path / "output.md")
        assert result == expected
        mock_prompt.assert_called_once()

    @patch("rich.prompt.Prompt.ask")
    def test_prompt_for_output_file_cancelled(self, mock_prompt):
        """プロンプトキャンセルテスト"""
        mock_prompt.return_value = ""

        result = self.file_manager.prompt_for_output_file("ai")

        assert result is None
        mock_prompt.assert_called_once()

    def test_get_default_output_directory(self):
        """デフォルト出力ディレクトリ取得テスト"""
        default_dir = self.file_manager.get_default_output_directory()

        assert isinstance(default_dir, Path)
        assert default_dir.name == "formatted_logs"
        assert default_dir.exists()

    def test_cleanup_old_files(self, tmp_path):
        """古いファイルクリーンアップテスト"""
        # テスト用ファイルを作成
        for i in range(5):
            test_file = tmp_path / f"test_{i}.md"
            test_file.write_text(f"content {i}")

        # 最大2ファイルに制限してクリーンアップ
        deleted_count = self.file_manager.cleanup_old_files(tmp_path, max_files=2)

        assert deleted_count == 3
        remaining_files = list(tmp_path.iterdir())
        assert len(remaining_files) == 2

    def test_cleanup_old_files_by_age(self, tmp_path):
        """日数制限でのクリーンアップテスト"""
        # 古いファイルを作成（モックで古い更新日時を設定）
        old_file = tmp_path / "old_file.md"
        old_file.write_text("old content")

        # ファイルの更新日時を古く設定
        old_timestamp = datetime.now().timestamp() - (40 * 24 * 3600)  # 40日前
        os.utime(old_file, (old_timestamp, old_timestamp))

        # 新しいファイルを作成
        new_file = tmp_path / "new_file.md"
        new_file.write_text("new content")

        # 30日制限でクリーンアップ
        deleted_count = self.file_manager.cleanup_old_files(tmp_path, max_age_days=30)

        assert deleted_count == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_old_files_nonexistent_directory(self):
        """存在しないディレクトリのクリーンアップテスト"""
        deleted_count = self.file_manager.cleanup_old_files("/nonexistent/directory")
        assert deleted_count == 0

    def test_is_dangerous_path_safe(self):
        """安全なパスの判定テスト"""
        safe_path = Path("./safe_output.md")
        is_dangerous = self.file_manager._is_dangerous_path(safe_path)
        assert is_dangerous is False

    def test_is_dangerous_path_dangerous(self):
        """危険なパスの判定テスト"""
        dangerous_path = Path("../../../etc/passwd")
        is_dangerous = self.file_manager._is_dangerous_path(dangerous_path)
        assert is_dangerous is True

    def test_show_save_success_message(self, tmp_path):
        """保存成功メッセージ表示テスト"""
        test_file = tmp_path / "test.md"
        test_file.write_text("test content")

        self.file_manager._show_save_success_message(test_file)

        # コンソールに成功メッセージが出力されることを確認
        assert self.console.print.call_count >= 1
        calls = [call.args[0] for call in self.console.print.call_args_list]
        success_messages = [msg for msg in calls if "正常に保存されました" in msg]
        assert len(success_messages) > 0
