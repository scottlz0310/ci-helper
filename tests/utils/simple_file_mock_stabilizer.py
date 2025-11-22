"""
シンプルなファイル操作モック安定化機能

テスト間でのファイル状態の分離を確保する軽量版のスタビライザーです。
pytestの内部動作に干渉しないよう、最小限の機能に絞っています。
"""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch


class SimpleFileSystemState:
    """シンプルなファイルシステム状態管理"""

    def __init__(self):
        self.files: dict[str, str] = {}
        self.directories: set[str] = set()
        self._lock = threading.Lock()

    def create_file(self, path: str, content: str = "") -> None:
        """ファイルを作成"""
        with self._lock:
            # 親ディレクトリも作成
            parent_dir = "/".join(path.split("/")[:-1])
            if parent_dir and parent_dir != "/":
                self.directories.add(parent_dir)
            self.files[path] = content

    def read_file(self, path: str) -> str:
        """ファイルを読み込み"""
        with self._lock:
            if path not in self.files:
                raise FileNotFoundError(f"File not found: {path}")
            return self.files[path]

    def write_file(self, path: str, content: str) -> None:
        """ファイルに書き込み"""
        with self._lock:
            if path not in self.files:
                raise FileNotFoundError(f"File not found: {path}")
            self.files[path] = content

    def delete_file(self, path: str) -> None:
        """ファイルを削除"""
        with self._lock:
            if path in self.files:
                del self.files[path]
            else:
                raise FileNotFoundError(f"File not found: {path}")

    def file_exists(self, path: str) -> bool:
        """ファイルの存在確認"""
        with self._lock:
            return path in self.files

    def directory_exists(self, path: str) -> bool:
        """ディレクトリの存在確認"""
        with self._lock:
            return path in self.directories

    def clear(self) -> None:
        """すべてのファイルとディレクトリをクリア"""
        with self._lock:
            self.files.clear()
            self.directories.clear()


class SimpleFileMockStabilizer:
    """シンプルなファイル操作モック安定化クラス"""

    def __init__(self):
        self.fs_state = SimpleFileSystemState()
        self._active_patches = []

    def setup_open_mock(self) -> None:
        """builtins.openのモックを設定"""

        def mock_open_func(file_path, mode="r", *args, **kwargs):
            path_str = str(file_path)

            if "r" in mode:
                if not self.fs_state.file_exists(path_str):
                    raise FileNotFoundError(f"No such file or directory: '{path_str}'")

                content = self.fs_state.read_file(path_str)
                mock_file = Mock()
                mock_file.read.return_value = content
                mock_file.readlines.return_value = content.splitlines(keepends=True)
                mock_file.__enter__.return_value = mock_file
                mock_file.__exit__.return_value = None
                return mock_file

            elif "w" in mode or "a" in mode:
                if "w" in mode or not self.fs_state.file_exists(path_str):
                    # 新規作成または上書き
                    self.fs_state.create_file(path_str, "")

                mock_file = Mock()
                written_content = []

                def write_func(content):
                    written_content.append(content)
                    if "w" in mode:
                        new_content = "".join(written_content)
                    else:  # append mode
                        current_content = (
                            self.fs_state.read_file(path_str) if self.fs_state.file_exists(path_str) else ""
                        )
                        new_content = current_content + "".join(written_content)

                    if self.fs_state.file_exists(path_str):
                        self.fs_state.write_file(path_str, new_content)
                    else:
                        self.fs_state.create_file(path_str, new_content)

                mock_file.write = write_func
                mock_file.flush = Mock()
                mock_file.__enter__.return_value = mock_file
                mock_file.__exit__.return_value = None
                return mock_file

            else:
                raise ValueError(f"Unsupported file mode: {mode}")

        open_patch = patch("builtins.open", side_effect=mock_open_func)
        self._active_patches.append(open_patch)
        open_patch.start()

    def setup_tempfile_mocks(self) -> None:
        """tempfileモジュールのモック"""

        temp_counter = 0

        def mock_mkdtemp(prefix="tmp"):
            nonlocal temp_counter
            temp_counter += 1
            temp_path = f"/mock/temp/{prefix}{temp_counter:04d}"
            self.fs_state.directories.add(temp_path)
            return temp_path

        def mock_named_temporary_file(*args, **kwargs):
            nonlocal temp_counter
            temp_counter += 1
            temp_path = f"/mock/temp/tmp{temp_counter:04d}.tmp"
            self.fs_state.create_file(temp_path, "")

            mock_file = Mock()
            mock_file.name = temp_path

            def write_func(content):
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                current_content = self.fs_state.read_file(temp_path) if self.fs_state.file_exists(temp_path) else ""
                self.fs_state.write_file(temp_path, current_content + content)

            mock_file.write = write_func
            mock_file.read = lambda: self.fs_state.read_file(temp_path)
            mock_file.flush = Mock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            return mock_file

        def mock_temporary_directory(*args, **kwargs):
            nonlocal temp_counter
            temp_counter += 1
            temp_path = f"/mock/temp/tmpdir{temp_counter:04d}"
            self.fs_state.directories.add(temp_path)

            mock_temp_dir = Mock()
            mock_temp_dir.name = temp_path
            mock_temp_dir.__enter__.return_value = temp_path
            mock_temp_dir.__exit__.return_value = None
            return mock_temp_dir

        # tempfileモジュールをパッチ
        mkdtemp_patch = patch("tempfile.mkdtemp", side_effect=mock_mkdtemp)
        named_temp_file_patch = patch("tempfile.NamedTemporaryFile", side_effect=mock_named_temporary_file)
        temp_dir_patch = patch("tempfile.TemporaryDirectory", side_effect=mock_temporary_directory)

        patches = [mkdtemp_patch, named_temp_file_patch, temp_dir_patch]

        for p in patches:
            self._active_patches.append(p)
            p.start()

    def create_test_file(self, path: str, content: str = "") -> None:
        """テスト用ファイルを作成"""
        self.fs_state.create_file(path, content)

    def create_test_directory(self, path: str) -> None:
        """テスト用ディレクトリを作成"""
        self.fs_state.directories.add(path)

    def setup_all_mocks(self) -> None:
        """すべてのモックを設定"""
        self.setup_open_mock()
        self.setup_tempfile_mocks()

    def cleanup_mocks(self) -> None:
        """すべてのモックをクリーンアップ"""
        for patch_obj in self._active_patches:
            try:
                patch_obj.stop()
            except Exception:
                pass  # パッチ停止エラーは無視
        self._active_patches.clear()
        self.fs_state.clear()

    @contextmanager
    def stable_file_operations(self) -> Generator["SimpleFileMockStabilizer", None, None]:
        """安定したファイル操作環境を提供"""
        try:
            self.setup_all_mocks()
            yield self
        finally:
            self.cleanup_mocks()


# 便利な関数


@contextmanager
def simple_stable_file_mocks() -> Generator[SimpleFileMockStabilizer, None, None]:
    """シンプルな安定したファイル操作モックを提供"""
    stabilizer = SimpleFileMockStabilizer()
    with stabilizer.stable_file_operations() as stab:
        yield stab


def with_simple_stable_file_operations(test_func):
    """シンプルな安定したファイル操作環境を提供するデコレータ"""

    def wrapper(*args, **kwargs):
        with simple_stable_file_mocks() as stabilizer:
            return test_func(stabilizer, *args, **kwargs)

    return wrapper


# ファイル操作の一貫性を確保するヘルパー関数


def create_consistent_file_mocks(files: dict[str, str] | None = None) -> dict[str, Any]:
    """一貫したファイル操作モックを作成

    Args:
        files: ファイルパスと内容の辞書

    Returns:
        dict: 設定されたモックオブジェクトの辞書
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

    return {
        "open": Mock(side_effect=mock_open_func),
        "files": files,
    }


def ensure_simple_file_operation_consistency(test_func):
    """シンプルなファイル操作の一貫性を確保するデコレータ"""

    def wrapper(*args, **kwargs):
        mocks = create_consistent_file_mocks()

        with patch("builtins.open", mocks["open"]):
            return test_func(*args, **kwargs)

    return wrapper
