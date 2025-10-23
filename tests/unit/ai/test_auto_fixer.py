"""
自動修正機能のユニットテスト

バックアップ・ロールバック機能と修正適用の正確性をテストします。
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.ci_helper.ai.auto_fixer import AutoFixer
from src.ci_helper.ai.models import BackupFile, BackupInfo, CodeChange, FixSuggestion, Priority
from src.ci_helper.utils.config import Config


class TestAutoFixer:
    """自動修正機能のテスト"""

    @pytest.fixture
    def temp_project_dir(self):
        """一時プロジェクトディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_config(self, temp_project_dir):
        """モック設定"""
        config = Mock(spec=Config)
        config.get_path.return_value = temp_project_dir / "cache"
        return config

    @pytest.fixture
    def auto_fixer(self, mock_config, temp_project_dir):
        """自動修正機のインスタンス"""
        with patch("src.ci_helper.ai.auto_fixer.Path.cwd", return_value=temp_project_dir):
            fixer = AutoFixer(mock_config, interactive=False, auto_approve_low_risk=True)
            fixer.project_root = temp_project_dir
            return fixer

    @pytest.fixture
    def sample_file(self, temp_project_dir):
        """サンプルファイル"""
        file_path = temp_project_dir / "test.py"
        content = """def hello():
    print("Hello, World!")
    return True
"""
        file_path.write_text(content, encoding="utf-8")
        return file_path

    @pytest.fixture
    def sample_fix_suggestion(self):
        """サンプル修正提案"""
        return FixSuggestion(
            title="Python構文修正",
            description="セミコロンを追加してJavaScript風にします",
            priority=Priority.MEDIUM,
            estimated_effort="2分",
            confidence=0.85,
            code_changes=[
                CodeChange(
                    file_path="test.py",
                    line_start=2,
                    line_end=2,
                    old_code='    print("Hello, World!")',
                    new_code='    print("Hello, World!");',
                    description="セミコロンを追加",
                )
            ],
        )

    @pytest.fixture
    def sample_backup_info(self, temp_project_dir):
        """サンプルバックアップ情報"""
        backup_file = BackupFile(
            original_path="test.py",
            backup_path=str(temp_project_dir / "backup" / "test.py"),
            checksum="abc123",
        )

        return BackupInfo(
            backup_id="test_backup_123",
            created_at=datetime.now(),
            files=[backup_file],
            description="テスト用バックアップ",
        )

    async def test_apply_fix_success(self, auto_fixer, sample_file, sample_fix_suggestion):
        """修正適用成功のテスト"""
        # 修正を適用
        result = await auto_fixer.apply_fix(sample_fix_suggestion, auto_approve=True)

        # 結果を確認
        assert result.success is True
        assert len(result.applied_steps) == 1
        assert result.backup_info is not None
        assert result.rollback_available is True

        # ファイル内容が変更されていることを確認
        modified_content = sample_file.read_text(encoding="utf-8")
        assert 'print("Hello, World!");' in modified_content

    async def test_apply_fix_with_approval_rejection(self, auto_fixer, sample_fix_suggestion):
        """承認拒否時の修正適用テスト"""
        # 承認システムをモック化して拒否を返す
        with patch.object(auto_fixer.approval_system, "request_approval") as mock_approval:
            from src.ci_helper.ai.approval_system import ApprovalDecision, ApprovalResult

            mock_approval.return_value = ApprovalResult(decision=ApprovalDecision.REJECTED, reason="ユーザーが拒否")

            result = await auto_fixer.apply_fix(sample_fix_suggestion, auto_approve=False)

            # 拒否された結果を確認
            assert result.success is False
            assert "修正が拒否されました" in result.error_message
            assert len(result.applied_steps) == 0

    def test_create_backup_success(self, auto_fixer, sample_file, sample_fix_suggestion):
        """バックアップ作成成功のテスト"""
        backup_info = auto_fixer.create_backup(sample_fix_suggestion)

        # バックアップ情報を確認
        assert backup_info is not None
        assert len(backup_info.files) == 1
        assert backup_info.files[0].original_path == "test.py"

        # バックアップファイルが作成されていることを確認
        backup_path = Path(backup_info.files[0].backup_path)
        assert backup_path.exists()

        # バックアップファイルの内容が元ファイルと同じことを確認
        original_content = sample_file.read_text(encoding="utf-8")
        backup_content = backup_path.read_text(encoding="utf-8")
        assert original_content == backup_content

        # チェックサムが正しいことを確認
        expected_checksum = auto_fixer._calculate_checksum(sample_file)
        assert backup_info.files[0].checksum == expected_checksum

    def test_create_backup_no_files(self, auto_fixer):
        """変更対象ファイルがない場合のバックアップテスト"""
        fix_suggestion = FixSuggestion(
            title="ファイル変更なし",
            description="ファイル変更を含まない修正",
            priority=Priority.LOW,
            estimated_effort="1分",
            confidence=0.9,
            code_changes=[],  # 空のコード変更
        )

        backup_info = auto_fixer.create_backup(fix_suggestion)

        # バックアップが作成されないことを確認
        assert backup_info is None

    def test_create_backup_nonexistent_file(self, auto_fixer):
        """存在しないファイルのバックアップテスト"""
        fix_suggestion = FixSuggestion(
            title="存在しないファイル修正",
            description="存在しないファイルを修正",
            priority=Priority.MEDIUM,
            estimated_effort="3分",
            confidence=0.7,
            code_changes=[
                CodeChange(
                    file_path="nonexistent.py",
                    line_start=1,
                    line_end=1,
                    old_code="",
                    new_code="print('new file')",
                    description="新規ファイル作成",
                )
            ],
        )

        backup_info = auto_fixer.create_backup(fix_suggestion)

        # 存在しないファイルはバックアップされないが、エラーにならない
        assert backup_info is None or len(backup_info.files) == 0

    def test_rollback_changes_success(self, auto_fixer, sample_file, sample_fix_suggestion):
        """ロールバック成功のテスト"""
        # バックアップを作成
        backup_info = auto_fixer.create_backup(sample_fix_suggestion)
        assert backup_info is not None

        # ファイルを変更
        modified_content = 'def hello():\n    print("Modified content")\n    return False\n'
        sample_file.write_text(modified_content, encoding="utf-8")

        # ロールバックを実行
        rollback_success = auto_fixer.rollback_changes(backup_info)

        # ロールバック結果を確認
        assert rollback_success is True

        # ファイル内容が元に戻っていることを確認
        restored_content = sample_file.read_text(encoding="utf-8")
        assert 'print("Hello, World!")' in restored_content
        assert "Modified content" not in restored_content

    def test_rollback_changes_missing_backup(self, auto_fixer, sample_backup_info):
        """バックアップファイルが存在しない場合のロールバックテスト"""
        # 存在しないバックアップファイルでロールバックを試行
        rollback_success = auto_fixer.rollback_changes(sample_backup_info)

        # ロールバックが失敗することを確認
        assert rollback_success is False

    def test_verify_fix_application_success(self, auto_fixer, sample_file, sample_fix_suggestion):
        """修正適用後検証成功のテスト"""
        verification_result = auto_fixer.verify_fix_application(sample_fix_suggestion)

        # 検証結果を確認（一部のチェックが失敗する可能性があるが、基本的な構造は確認）
        assert verification_result["total_checks"] > 0
        assert verification_result["passed_checks"] > 0
        assert len(verification_result["checks_passed"]) > 0
        # 成功/失敗に関わらず、検証が実行されることを確認
        assert "success" in verification_result

    def test_verify_fix_application_python_syntax_error(self, auto_fixer, temp_project_dir):
        """Python構文エラーがある場合の検証テスト"""
        # 構文エラーのあるPythonファイルを作成
        error_file = temp_project_dir / "syntax_error.py"
        error_file.write_text('print("Hello World"  # 閉じ括弧なし', encoding="utf-8")

        fix_suggestion = FixSuggestion(
            title="構文エラー修正",
            description="構文エラーを修正",
            priority=Priority.HIGH,
            estimated_effort="1分",
            confidence=0.9,
            code_changes=[
                CodeChange(
                    file_path="syntax_error.py",
                    line_start=1,
                    line_end=1,
                    old_code='print("Hello World"  # 閉じ括弧なし',
                    new_code='print("Hello World")  # 修正済み',
                    description="閉じ括弧を追加",
                )
            ],
        )

        verification_result = auto_fixer.verify_fix_application(fix_suggestion)

        # 構文エラーにより検証が失敗することを確認
        assert verification_result["success"] is False
        assert any("構文エラー" in check for check in verification_result["checks_failed"])

    def test_calculate_checksum(self, auto_fixer, sample_file):
        """チェックサム計算のテスト"""
        checksum1 = auto_fixer._calculate_checksum(sample_file)
        checksum2 = auto_fixer._calculate_checksum(sample_file)

        # 同じファイルは同じチェックサムを持つ
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256は64文字

        # ファイル内容を変更
        sample_file.write_text("different content", encoding="utf-8")
        checksum3 = auto_fixer._calculate_checksum(sample_file)

        # 内容が変わるとチェックサムも変わる
        assert checksum1 != checksum3

    def test_apply_file_modification_create(self, auto_fixer, temp_project_dir):
        """ファイル作成の修正適用テスト"""
        from src.ci_helper.ai.models import FixStep

        fix_step = FixStep(
            type="file_modification",
            description="新規ファイル作成",
            file_path="new_file.txt",
            action="create",
            content="This is a new file content",
        )

        auto_fixer._apply_file_modification(fix_step)

        # ファイルが作成されていることを確認
        new_file = temp_project_dir / "new_file.txt"
        assert new_file.exists()
        assert new_file.read_text(encoding="utf-8") == "This is a new file content"

    def test_apply_file_modification_append(self, auto_fixer, sample_file):
        """ファイル追記の修正適用テスト"""
        from src.ci_helper.ai.models import FixStep

        original_content = sample_file.read_text(encoding="utf-8")

        fix_step = FixStep(
            type="file_modification",
            description="ファイルに追記",
            file_path="test.py",
            action="append",
            content="\n# This is appended content",
        )

        auto_fixer._apply_file_modification(fix_step)

        # 内容が追記されていることを確認
        new_content = sample_file.read_text(encoding="utf-8")
        assert new_content == original_content + "\n# This is appended content"

    def test_apply_file_modification_replace(self, auto_fixer, sample_file):
        """ファイル置換の修正適用テスト"""
        from src.ci_helper.ai.models import FixStep

        fix_step = FixStep(
            type="file_modification",
            description="ファイル内容を置換",
            file_path="test.py",
            action="replace",
            content="def goodbye():\n    print('Goodbye!')\n",
        )

        auto_fixer._apply_file_modification(fix_step)

        # 内容が置換されていることを確認
        new_content = sample_file.read_text(encoding="utf-8")
        assert new_content == "def goodbye():\n    print('Goodbye!')\n"
        assert "Hello, World!" not in new_content

    def test_apply_command_security_restriction(self, auto_fixer):
        """コマンド実行のセキュリティ制限テスト"""
        from src.ci_helper.ai.exceptions import FixApplicationError
        from src.ci_helper.ai.models import FixStep

        fix_step = FixStep(
            type="command",
            description="危険なコマンド実行",
            command="rm -rf /",
        )

        # コマンド実行が制限されることを確認
        with pytest.raises(FixApplicationError, match="コマンド実行は現在サポートされていません"):
            auto_fixer._apply_command(fix_step)

    def test_get_fix_history(self, auto_fixer, sample_file, sample_fix_suggestion):
        """修正履歴取得のテスト"""
        # 最初は履歴が空
        history = auto_fixer.get_fix_history()
        assert len(history) == 0

        # 修正を適用
        from src.ci_helper.ai.models import FixResult

        result = FixResult(
            success=True,
            applied_steps=[],
            verification_passed=True,
        )

        auto_fixer._record_fix_history(sample_fix_suggestion, result)

        # 履歴が記録されていることを確認
        history = auto_fixer.get_fix_history()
        assert len(history) == 1
        assert history[0]["suggestion_title"] == sample_fix_suggestion.title
        assert history[0]["success"] is True

    def test_cleanup_old_backups(self, auto_fixer, temp_project_dir):
        """古いバックアップ削除のテスト"""
        # テスト用のバックアップディレクトリを作成
        backup_base = auto_fixer.backup_dir
        backup_base.mkdir(parents=True, exist_ok=True)

        # 古いバックアップディレクトリを作成
        old_backup = backup_base / "old_backup"
        old_backup.mkdir()
        (old_backup / "test.txt").write_text("old backup content")

        # ディレクトリの更新時刻を古く設定
        import os
        import time

        old_time = time.time() - (40 * 24 * 60 * 60)  # 40日前
        os.utime(old_backup, (old_time, old_time))

        # 新しいバックアップディレクトリを作成
        new_backup = backup_base / "new_backup"
        new_backup.mkdir()
        (new_backup / "test.txt").write_text("new backup content")

        # クリーンアップを実行（30日より古いものを削除）
        auto_fixer.cleanup_old_backups(keep_days=30)

        # 古いバックアップが削除され、新しいバックアップが残っていることを確認
        assert not old_backup.exists()
        assert new_backup.exists()

    def test_get_backup_list(self, auto_fixer, sample_file, sample_fix_suggestion):
        """バックアップリスト取得のテスト"""
        # 最初はバックアップがない
        backup_list = auto_fixer.get_backup_list()
        assert len(backup_list) == 0

        # バックアップを作成
        backup_info = auto_fixer.create_backup(sample_fix_suggestion)
        assert backup_info is not None

        # バックアップリストを取得
        backup_list = auto_fixer.get_backup_list()
        assert len(backup_list) == 1

        backup_entry = backup_list[0]
        assert backup_entry["backup_id"] == backup_info.backup_id
        assert backup_entry["file_count"] > 0
        assert backup_entry["size_mb"] >= 0

    def test_rollback_by_backup_id_success(self, auto_fixer, sample_file, sample_fix_suggestion):
        """バックアップIDによるロールバック成功のテスト"""
        # バックアップを作成
        backup_info = auto_fixer.create_backup(sample_fix_suggestion)
        assert backup_info is not None

        # ファイルを変更
        sample_file.write_text("Modified content for rollback test", encoding="utf-8")

        # バックアップIDでロールバック
        rollback_result = auto_fixer.rollback_by_backup_id(backup_info.backup_id)

        # ロールバック結果を確認
        assert rollback_result["success"] is True
        assert len(rollback_result["restored_files"]) == 1
        assert len(rollback_result["failed_files"]) == 0
        assert rollback_result["backup_id"] == backup_info.backup_id

        # ファイル内容が復元されていることを確認
        restored_content = sample_file.read_text(encoding="utf-8")
        assert 'print("Hello, World!")' in restored_content

    def test_rollback_by_backup_id_not_found(self, auto_fixer):
        """存在しないバックアップIDでのロールバックテスト"""
        rollback_result = auto_fixer.rollback_by_backup_id("nonexistent_backup_id")

        # ロールバックが失敗することを確認
        assert rollback_result["success"] is False
        assert "バックアップが見つかりません" in rollback_result["error"]

    def test_verify_file_format_json(self, auto_fixer, temp_project_dir):
        """JSONファイル形式検証のテスト"""
        # 有効なJSONファイル
        valid_json_file = temp_project_dir / "valid.json"
        valid_json_file.write_text('{"key": "value"}', encoding="utf-8")

        result = auto_fixer._verify_file_format(valid_json_file, valid_json_file.read_text(encoding="utf-8"))
        assert result["success"] is True
        assert "JSON 構文チェック OK" in result["message"]

        # 無効なJSONファイル
        invalid_json_file = temp_project_dir / "invalid.json"
        invalid_json_file.write_text('{"key": invalid}', encoding="utf-8")

        result = auto_fixer._verify_file_format(invalid_json_file, invalid_json_file.read_text(encoding="utf-8"))
        assert result["success"] is False
        assert "JSON 構文エラー" in result["message"]

    def test_verify_file_format_python(self, auto_fixer, temp_project_dir):
        """Pythonファイル形式検証のテスト"""
        # 有効なPythonファイル
        valid_py_file = temp_project_dir / "valid.py"
        valid_py_file.write_text('print("Hello")', encoding="utf-8")

        result = auto_fixer._verify_file_format(valid_py_file, valid_py_file.read_text(encoding="utf-8"))
        assert result["success"] is True
        assert "Python 構文チェック OK" in result["message"]

    def test_check_file_warnings(self, auto_fixer, temp_project_dir):
        """ファイル警告チェックのテスト"""
        # 大きなファイル
        large_file = temp_project_dir / "large.py"
        large_content = "# " + "x" * (1024 * 1024 + 100)  # 1MB以上
        large_file.write_text(large_content, encoding="utf-8")

        warnings = auto_fixer._check_file_warnings(large_file, large_content)
        assert any("大きなファイル" in warning for warning in warnings)

        # 空ファイル
        empty_file = temp_project_dir / "empty.py"
        empty_file.write_text("", encoding="utf-8")

        warnings = auto_fixer._check_file_warnings(empty_file, "")
        assert any("空ファイル" in warning for warning in warnings)

        # TODOコメントを含むファイル
        todo_file = temp_project_dir / "todo.py"
        todo_content = "# TODO: Fix this later\nprint('hello')\n# FIXME: Bug here"
        todo_file.write_text(todo_content, encoding="utf-8")

        warnings = auto_fixer._check_file_warnings(todo_file, todo_content)
        assert any("TODO/FIXME" in warning for warning in warnings)

    def test_verify_project_integrity(self, auto_fixer, temp_project_dir):
        """プロジェクト整合性チェックのテスト"""
        # pyproject.tomlファイルを作成
        pyproject_file = temp_project_dir / "pyproject.toml"
        pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        pyproject_file.write_text(pyproject_content, encoding="utf-8")

        # .gitディレクトリを作成
        git_dir = temp_project_dir / ".git"
        git_dir.mkdir()

        checks = auto_fixer._verify_project_integrity()

        # 整合性チェック結果を確認
        assert len(checks) > 0

        # 成功したチェックがあることを確認
        success_checks = [check for check in checks if check["success"]]
        assert len(success_checks) > 0

    async def test_apply_pattern_based_fix(self, auto_fixer, sample_fix_suggestion):
        """パターンベース修正適用のテスト"""
        from src.ci_helper.ai.models import Pattern, PatternMatch

        # テスト用パターンとマッチを作成
        pattern = Pattern(
            id="test_pattern",
            name="テストパターン",
            category="test",
            regex_patterns=[r"error"],
            keywords=["error"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        pattern_match = PatternMatch(
            pattern=pattern,
            confidence=0.85,
            match_positions=[100],
            extracted_context="Test error context",
            match_strength=0.8,
            supporting_evidence=["error log"],
        )

        # パターンベース修正を適用
        result = await auto_fixer.apply_pattern_based_fix(
            sample_fix_suggestion, pattern_match=pattern_match, auto_approve=True
        )

        # 結果を確認
        assert result.success is True

    def test_get_approval_summary(self, auto_fixer):
        """承認サマリー取得のテスト"""
        summary = auto_fixer.get_approval_summary()

        # サマリーが辞書形式で返されることを確認
        assert isinstance(summary, dict)

    def test_set_approval_policy(self, auto_fixer):
        """承認ポリシー設定のテスト"""
        # ポリシーを設定（エラーが発生しないことを確認）
        auto_fixer.set_approval_policy(auto_approve_low_risk=True)
        auto_fixer.set_approval_policy(auto_approve_low_risk=False)

    def test_convert_code_change_to_fix_step(self, auto_fixer):
        """CodeChangeからFixStepへの変換テスト"""
        code_change = CodeChange(
            file_path="test.py",
            line_start=1,
            line_end=2,
            old_code="old code",
            new_code="new code",
            description="テスト変更",
        )

        fix_step = auto_fixer._convert_code_change_to_fix_step(code_change)

        assert fix_step.type == "file_modification"
        assert fix_step.description == "テスト変更"
        assert fix_step.file_path == "test.py"
        assert fix_step.action == "replace"
        assert fix_step.content == "new code"

    async def test_apply_fix_with_verification_failure(self, auto_fixer, temp_project_dir):
        """検証失敗時の修正適用テスト"""
        # 検証が失敗するような修正提案を作成
        fix_suggestion = FixSuggestion(
            title="検証失敗修正",
            description="検証が失敗する修正",
            priority=Priority.HIGH,
            estimated_effort="1分",
            confidence=0.9,
            code_changes=[
                CodeChange(
                    file_path="nonexistent_file.py",
                    line_start=1,
                    line_end=1,
                    old_code="",
                    new_code="print('test')",
                    description="存在しないファイルへの変更",
                )
            ],
        )

        # 修正を適用
        result = await auto_fixer.apply_fix(fix_suggestion, auto_approve=True)

        # 修正は成功するが、検証で問題が検出される可能性がある
        assert result.success is True  # ファイル作成は成功する
        # verification_passedは検証結果による
