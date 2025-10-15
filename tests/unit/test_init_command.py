"""
init コマンドのユニットテスト
"""

from pathlib import Path
from unittest.mock import Mock, patch

from ci_helper.commands.init import _copy_template_to_actual, _handle_gitignore_update


def test_copy_template_to_actual_success(temp_dir: Path):
    """テンプレートファイルのコピー成功テスト"""
    template_path = temp_dir / "template.txt"
    actual_path = temp_dir / "actual.txt"

    # テンプレートファイルを作成
    template_path.write_text("test content", encoding="utf-8")

    # コピー実行
    result = _copy_template_to_actual(template_path, actual_path)

    assert result is True
    assert actual_path.exists()
    assert actual_path.read_text(encoding="utf-8") == "test content"


def test_copy_template_to_actual_existing_file(temp_dir: Path):
    """既存ファイルがある場合のテスト"""
    template_path = temp_dir / "template.txt"
    actual_path = temp_dir / "actual.txt"

    # ファイルを作成
    template_path.write_text("template content", encoding="utf-8")
    actual_path.write_text("existing content", encoding="utf-8")

    # force=False でコピー実行
    result = _copy_template_to_actual(template_path, actual_path, force=False)

    assert result is False
    assert actual_path.read_text(encoding="utf-8") == "existing content"


def test_copy_template_to_actual_force_overwrite(temp_dir: Path):
    """強制上書きのテスト"""
    template_path = temp_dir / "template.txt"
    actual_path = temp_dir / "actual.txt"

    # ファイルを作成
    template_path.write_text("template content", encoding="utf-8")
    actual_path.write_text("existing content", encoding="utf-8")

    # force=True でコピー実行
    result = _copy_template_to_actual(template_path, actual_path, force=True)

    assert result is True
    assert actual_path.read_text(encoding="utf-8") == "template content"


@patch("ci_helper.commands.init.console")
@patch("ci_helper.commands.init.Confirm")
def test_handle_gitignore_update_existing_file(mock_confirm: Mock, mock_console: Mock, temp_dir: Path):
    """既存の .gitignore ファイルの更新テスト"""
    gitignore_path = temp_dir / ".gitignore"
    gitignore_path.write_text("# existing content\n", encoding="utf-8")

    # ユーザーが追加を承認
    mock_confirm.ask.return_value = True

    _handle_gitignore_update(temp_dir)

    # .gitignore が更新されたことを確認
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".ci-helper/" in content

    # コンソール出力の確認
    mock_console.print.assert_called()


@patch("ci_helper.commands.init.console")
@patch("ci_helper.commands.init.Confirm")
def test_handle_gitignore_update_no_file(mock_confirm: Mock, mock_console: Mock, temp_dir: Path):
    """.gitignore ファイルが存在しない場合のテスト"""
    gitignore_path = temp_dir / ".gitignore"

    # ユーザーが作成を承認
    mock_confirm.ask.return_value = True

    _handle_gitignore_update(temp_dir)

    # .gitignore が作成されたことを確認
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".ci-helper/" in content

    # コンソール出力の確認
    mock_console.print.assert_called()


@patch("ci_helper.commands.init.console")
@patch("ci_helper.commands.init.Confirm")
def test_handle_gitignore_update_user_declines(mock_confirm: Mock, mock_console: Mock, temp_dir: Path):
    """ユーザーが更新を拒否した場合のテスト"""
    gitignore_path = temp_dir / ".gitignore"
    original_content = "# existing content\n"
    gitignore_path.write_text(original_content, encoding="utf-8")

    # ユーザーが追加を拒否
    mock_confirm.ask.return_value = False

    _handle_gitignore_update(temp_dir)

    # .gitignore が変更されていないことを確認
    content = gitignore_path.read_text(encoding="utf-8")
    assert content == original_content
    assert ".ci-helper/" not in content
