"""
ファイル操作モック用のヘルパー関数

テストでファイル操作モックを簡単に使用するためのヘルパー関数を提供します。
一貫したファイル操作の動作とテスト間の分離を確保します。
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

from tests.utils.file_operation_mock_stabilizer import FileOperationMockStabilizer


def create_mock_file_system(files: dict[str, str] = None) -> dict[str, Any]:
    """
    モックファイルシステムを作成

    Args:
        files: ファイルパスと内容の辞書

    Returns:
        dict: モックオブジェクトの辞書
    """
    files = files or {}

    def mock_open_func(file_path, mode="r", *args, **kwargs):
        path_str = str(file_path)

        if "r" in mode:
            if path_str not in files:
                raise FileNotFoundError(f"No such file or directory: '{path_str}'")

            mock_file = Mock()
            mock_file.read.return_value = files[path_str]
            mock_file.readlines.return_value = files[path_str].splitlines(keepends=True)
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            return mock_file

        elif "w" in mode or "a" in mode:
            mock_file = Mock()
            written_content = []

            def write_func(content):
                written_content.append(content)
                if "w" in mode:
                    files[path_str] = "".join(written_content)
                else:  # append mode
                    current_content = files.get(path_str, "")
                    files[path_str] = current_content + "".join(written_content)

            mock_file.write = write_func
            mock_file.flush = Mock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            return mock_file

        else:
            raise ValueError(f"Unsupported file mode: {mode}")

    def mock_path_exists(path):
        return str(path) in files

    def mock_path_read_text(path, encoding="utf-8"):
        path_str = str(path)
        if path_str not in files:
            raise FileNotFoundError(f"No such file or directory: '{path_str}'")
        return files[path_str]

    def mock_path_write_text(path, content, encoding="utf-8"):
        files[str(path)] = content

    return {
        "open": Mock(side_effect=mock_open_func),
        "path_exists": Mock(side_effect=mock_path_exists),
        "path_read_text": Mock(side_effect=mock_path_read_text),
        "path_write_text": Mock(side_effect=mock_path_write_text),
        "files": files,
    }


@contextmanager
def mock_file_operations(files: dict[str, str] = None) -> Generator[dict[str, Any], None, None]:
    """
    ファイル操作をモック化するコンテキストマネージャー

    Args:
        files: 初期ファイルの辞書

    Yields:
        dict: モックオブジェクトの辞書
    """
    mocks = create_mock_file_system(files)

    with (
        patch("builtins.open", mocks["open"]),
        patch("pathlib.Path.exists", mocks["path_exists"]),
        patch("pathlib.Path.read_text", mocks["path_read_text"]),
        patch("pathlib.Path.write_text", mocks["path_write_text"]),
    ):
        yield mocks


@contextmanager
def stable_file_environment() -> Generator[FileOperationMockStabilizer, None, None]:
    """
    安定したファイル操作環境を提供するコンテキストマネージャー

    Yields:
        FileOperationMockStabilizer: 設定済みのスタビライザー
    """
    stabilizer = FileOperationMockStabilizer()
    with stabilizer.stable_file_operations() as stab:
        yield stab


def with_mock_files(files: dict[str, str] = None):
    """
    ファイル操作をモック化するデコレータ

    Args:
        files: 初期ファイルの辞書
    """

    def decorator(test_func):
        def wrapper(*args, **kwargs):
            with mock_file_operations(files) as mocks:
                return test_func(mocks, *args, **kwargs)

        return wrapper

    return decorator


def with_stable_files(test_func):
    """
    安定したファイル操作環境を提供するデコレータ
    """

    def wrapper(*args, **kwargs):
        with stable_file_environment() as stabilizer:
            return test_func(stabilizer, *args, **kwargs)

    return wrapper


def create_test_files_in_stabilizer(stabilizer: FileOperationMockStabilizer, files: dict[str, str]) -> None:
    """
    スタビライザーにテストファイルを作成

    Args:
        stabilizer: ファイル操作スタビライザー
        files: ファイルパスと内容の辞書
    """
    for file_path, content in files.items():
        stabilizer.create_test_file(file_path, content)


def create_test_directories_in_stabilizer(stabilizer: FileOperationMockStabilizer, directories: list[str]) -> None:
    """
    スタビライザーにテストディレクトリを作成

    Args:
        stabilizer: ファイル操作スタビライザー
        directories: ディレクトリパスのリスト
    """
    for dir_path in directories:
        stabilizer.create_test_directory(dir_path)


# 便利な定数とテンプレート

SAMPLE_CONFIG_FILE = """
[ai]
default_provider = "openai"
cache_enabled = true

[ai.providers.openai]
api_key = "sk-test-key"
default_model = "gpt-4o"
"""

SAMPLE_WORKFLOW_FILE = """
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Running tests"
"""

SAMPLE_LOG_FILE = """
STEP: Run tests
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'

FAILURES:
test_user_authentication.py::test_login_with_invalid_credentials FAILED
AssertionError: Expected status code 401, got 200
"""

# よく使用されるファイルセット

COMMON_TEST_FILES = {
    "ci-helper.toml": SAMPLE_CONFIG_FILE,
    ".github/workflows/test.yml": SAMPLE_WORKFLOW_FILE,
    "test.log": SAMPLE_LOG_FILE,
    "package.json": '{"name": "test-project", "version": "1.0.0"}',
    "README.md": "# Test Project\n\nThis is a test project.",
}

PROJECT_STRUCTURE_FILES = {
    "src/main.py": "# Main application file\nprint('Hello, World!')",
    "tests/test_main.py": "# Test file\ndef test_main():\n    assert True",
    "requirements.txt": "pytest>=7.0.0\nclick>=8.0.0",
    "pyproject.toml": "[build-system]\nrequires = ['setuptools']\nbuild-backend = 'setuptools.build_meta'",
}

CI_FAILURE_FILES = {
    "ci_failure.log": """
ERROR: test_authentication.py::test_login_invalid_credentials FAILED
AssertionError: Expected 401, got 200

ERROR: test_database.py::test_connection_timeout FAILED  
TimeoutError: Database connection timed out after 30 seconds
""",
    "build_failure.log": """
npm ERR! code ELIFECYCLE
npm ERR! errno 1
npm ERR! test-project@1.0.0 build: `webpack --mode production`
npm ERR! Exit status 1
""",
}
