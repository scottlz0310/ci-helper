"""
自動修正適用機能のテスト
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.ci_helper.ai.fix_applier import BackupManager, FixApplier, FixApprovalResult
from src.ci_helper.ai.models import CodeChange, FixSuggestion, Priority
from src.ci_helper.utils.config import Config


class TestBackupManager:
    """バックアップ管理のテスト"""

    @pytest.fixture
    def temp_dir(self):
        """一時ディレクトリ"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def backup_manager(self, temp_dir):
        """バックアップ管理インスタンス"""
        backup_dir = temp_dir / "backups"
        return BackupManager(backup_dir)

    @pytest.fixture
    def sample_file(self, temp_dir):
        """サンプルファイル"""
        file_path = temp_dir / "test.txt"
        file_path.write_text("original content", encoding="utf-8")
        return file_path

    def test_create_backup(self, backup_manager, sample_file):
        """バックアップ作成のテスト"""
        backup_path = backup_manager.create_backup(sample_file)

        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "original content"
        assert backup_path.name.endswith(".backup")

    def test_restore_backup(self, backup_manager, sample_file, temp_dir):
        """バックアップ復元のテスト"""
        # バックアップを作成
        backup_path = backup_manager.create_backup(sample_file)

        # 元ファイルを変更
        sample_file.write_text("modified content", encoding="utf-8")

        # バックアップから復元
        backup_manager.restore_backup(sample_file, backup_path)

        assert sample_file.read_text(encoding="utf-8") == "original content"

    def test_list_backups(self, backup_manager, sample_file):
        """バックアップ一覧のテスト"""
        # 複数のバックアップを作成（タイムスタンプが異なるように少し待機）
        import time

        backup1 = backup_manager.create_backup(sample_file)
        time.sleep(1.1)  # 1秒以上待機してタイムスタンプを変える
        backup2 = backup_manager.create_backup(sample_file)

        backups = backup_manager.list_backups()
        assert len(backups) >= 2
        assert backup1 in backups
        assert backup2 in backups

    def test_cleanup_old_backups(self, backup_manager, sample_file):
        """古いバックアップ削除のテスト"""
        # 複数のバックアップを作成（タイムスタンプが異なるように少し待機）
        import time

        backups = []
        for _i in range(5):
            backup = backup_manager.create_backup(sample_file)
            backups.append(backup)
            time.sleep(1.1)  # 1秒以上待機してタイムスタンプを変える

        # 2個だけ保持するようにクリーンアップ
        backup_manager.cleanup_old_backups(keep_count=2)

        remaining_backups = backup_manager.list_backups()
        assert len(remaining_backups) == 2


class TestFixApplier:
    """修正適用器のテスト"""

    @pytest.fixture
    def temp_dir(self):
        """一時ディレクトリ"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_config(self, temp_dir):
        """モック設定"""
        config = Mock(spec=Config)
        config.get_path.return_value = temp_dir
        return config

    @pytest.fixture
    def fix_applier(self, mock_config, temp_dir):
        """修正適用器（非対話モード）"""
        with patch("src.ci_helper.ai.fix_applier.Path.cwd", return_value=temp_dir):
            applier = FixApplier(mock_config, interactive=False)
            applier.project_root = temp_dir
            return applier

    @pytest.fixture
    def sample_file(self, temp_dir):
        """サンプルファイル"""
        file_path = temp_dir / "test.js"
        content = """function test() {
    console.log('Hello')
    return true;
}"""
        file_path.write_text(content, encoding="utf-8")
        return file_path

    @pytest.fixture
    def sample_fix_suggestion(self):
        """サンプル修正提案"""
        return FixSuggestion(
            title="セミコロン追加",
            description="セミコロンを追加してください",
            priority=Priority.HIGH,
            estimated_effort="5分",
            confidence=0.9,
            code_changes=[
                CodeChange(
                    file_path="test.js",
                    line_start=2,
                    line_end=2,
                    old_code="    console.log('Hello')",
                    new_code="    console.log('Hello');",
                    description="セミコロンを追加",
                )
            ],
        )

    def test_apply_single_fix_success(self, fix_applier, sample_file, sample_fix_suggestion):
        """単一修正の成功テスト"""
        result = fix_applier._apply_single_fix(sample_fix_suggestion)

        assert result["success"] is True
        assert len(result["applied_changes"]) == 1
        assert len(result["backups"]) == 1

        # ファイル内容が変更されているか確認
        content = sample_file.read_text(encoding="utf-8")
        assert "console.log('Hello');" in content

    def test_apply_fix_suggestions_auto_approve(self, fix_applier, sample_file, sample_fix_suggestion):
        """修正提案の自動承認適用テスト"""
        result = fix_applier.apply_fix_suggestions([sample_fix_suggestion], auto_approve=True)

        assert result["total_suggestions"] == 1
        assert result["applied_count"] == 1
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0

    def test_validate_fix_python_syntax(self, fix_applier, temp_dir):
        """Python構文検証のテスト"""
        # 正常なPythonファイル
        py_file = temp_dir / "test.py"
        py_file.write_text("print('Hello, World!')", encoding="utf-8")

        result = fix_applier._check_python_syntax("test.py")
        assert result.startswith("構文 OK")

        # 構文エラーのあるPythonファイル
        py_file.write_text("print('Hello, World!'", encoding="utf-8")  # 閉じ括弧なし

        result = fix_applier._check_python_syntax("test.py")
        assert "構文エラー" in result

    def test_rollback_fixes(self, fix_applier, sample_file, sample_fix_suggestion):
        """修正のロールバックテスト"""
        # 修正を適用
        apply_result = fix_applier.apply_fix_suggestions([sample_fix_suggestion], auto_approve=True)
        backup_paths = apply_result["backups_created"]

        # 元の内容を確認
        original_content = sample_file.read_text(encoding="utf-8")
        assert "console.log('Hello');" in original_content

        # ロールバック
        rollback_result = fix_applier.rollback_fixes(backup_paths)

        assert rollback_result["restored_count"] == 1
        assert rollback_result["failed_count"] == 0

        # 内容が元に戻っているか確認
        restored_content = sample_file.read_text(encoding="utf-8")
        assert "console.log('Hello')" in restored_content
        assert "console.log('Hello');" not in restored_content

    def test_apply_code_change_new_file(self, fix_applier, temp_dir):
        """新規ファイル作成のテスト"""
        change = CodeChange(
            file_path="new_file.js",
            line_start=1,
            line_end=1,
            old_code="",
            new_code="console.log('New file');",
            description="新規ファイル作成",
        )

        result = fix_applier._apply_code_change(change)

        assert result["success"] is True

        new_file = temp_dir / "new_file.js"
        assert new_file.exists()
        assert new_file.read_text(encoding="utf-8") == "console.log('New file');"

    def test_get_apply_summary(self, fix_applier, sample_file, sample_fix_suggestion):
        """適用サマリーのテスト"""
        # 修正を適用
        fix_applier.apply_fix_suggestions([sample_fix_suggestion], auto_approve=True)

        summary = fix_applier.get_apply_summary()

        assert summary["applied_fixes_count"] == 1
        assert summary["failed_fixes_count"] == 0
        assert len(summary["applied_fixes"]) == 1
        assert summary["applied_fixes"][0]["title"] == "セミコロン追加"


class TestFixApprovalResult:
    """修正承認結果のテスト"""

    def test_approval_result_creation(self):
        """承認結果作成のテスト"""
        result = FixApprovalResult(True, "ユーザーが承認")

        assert result.approved is True
        assert result.reason == "ユーザーが承認"
        assert result.timestamp is not None

    def test_rejection_result_creation(self):
        """拒否結果作成のテスト"""
        result = FixApprovalResult(False, "ユーザーが拒否")

        assert result.approved is False
        assert result.reason == "ユーザーが拒否"
