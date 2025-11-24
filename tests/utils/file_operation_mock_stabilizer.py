"""
ファイル操作モックの一貫性確保ユーティリティ

テスト間でのファイル状態の分離とファイル操作モックの一貫した動作を提供します。
並行テスト実行時の競合状態を防ぎ、テストの再現性を確保します。
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch


class FileSystemState:
    """ファイルシステム状態の管理クラス

    テスト実行中のファイルシステム状態を追跡し、
    テスト間での適切な分離を確保します。
    """

    def __init__(self):
        self.created_files: set[Path] = set()
        self.created_directories: set[Path] = set()
        self.modified_files: set[Path] = set()
        self.temp_directories: list[Path] = []
        self._lock = threading.Lock()

    def register_file_creation(self, file_path: Path) -> None:
        """ファイル作成を記録"""
        with self._lock:
            self.created_files.add(file_path)

    def register_directory_creation(self, dir_path: Path) -> None:
        """ディレクトリ作成を記録"""
        with self._lock:
            self.created_directories.add(dir_path)

    def register_file_modification(self, file_path: Path) -> None:
        """ファイル変更を記録"""
        with self._lock:
            self.modified_files.add(file_path)

    def register_temp_directory(self, temp_dir: Path) -> None:
        """一時ディレクトリを記録"""
        with self._lock:
            self.temp_directories.append(temp_dir)

    def cleanup_all(self) -> None:
        """すべての作成されたファイル・ディレクトリをクリーンアップ"""
        with self._lock:
            # 一時ディレクトリのクリーンアップ
            for temp_dir in self.temp_directories:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass  # クリーンアップエラーは無視

            # 作成されたファイルのクリーンアップ
            for file_path in self.created_files:
                try:
                    if file_path.exists():
                        file_path.unlink()
                except Exception:
                    pass

            # 作成されたディレクトリのクリーンアップ
            for dir_path in sorted(self.created_directories, reverse=True):
                try:
                    if dir_path.exists() and dir_path.is_dir():
                        dir_path.rmdir()
                except Exception:
                    pass

            # 状態をリセット
            self.created_files.clear()
            self.created_directories.clear()
            self.modified_files.clear()
            self.temp_directories.clear()


class MockFileSystem:
    """モックファイルシステム

    実際のファイルシステムに影響を与えずに
    ファイル操作をシミュレートします。
    """

    def __init__(self):
        self.files: dict[str, str] = {}
        self.directories: set[str] = set()
        self._lock = threading.Lock()

    def create_file(self, path: str, content: str = "") -> None:
        """ファイルを作成"""
        with self._lock:
            # ディレクトリも作成
            parent_dir = str(Path(path).parent)
            if parent_dir != ".":
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

    def create_directory(self, path: str) -> None:
        """ディレクトリを作成"""
        with self._lock:
            self.directories.add(path)

    def file_exists(self, path: str) -> bool:
        """ファイルの存在確認"""
        with self._lock:
            return path in self.files

    def directory_exists(self, path: str) -> bool:
        """ディレクトリの存在確認"""
        with self._lock:
            return path in self.directories

    def list_files(self) -> list[str]:
        """すべてのファイルをリスト"""
        with self._lock:
            return list(self.files.keys())

    def clear(self) -> None:
        """すべてのファイルとディレクトリをクリア"""
        with self._lock:
            self.files.clear()
            self.directories.clear()


class FileOperationMockStabilizer:
    """ファイル操作モックの安定化クラス

    ファイル操作のモックを一貫した動作に修正し、
    テスト間での状態分離を確保します。
    """

    def __init__(self):
        self.fs_state = FileSystemState()
        self.mock_fs = MockFileSystem()
        self._active_patches: list[Any] = []

    @contextmanager
    def isolated_filesystem(self, use_real_temp_dir: bool = True) -> Generator[Path]:
        """分離されたファイルシステム環境を提供

        Args:
            use_real_temp_dir: 実際の一時ディレクトリを使用するか

        Yields:
            Path: 一時ディレクトリのパス（実際またはモック）
        """
        if use_real_temp_dir:
            # 実際の一時ディレクトリを使用
            temp_dir = Path(tempfile.mkdtemp(prefix="ci_helper_test_"))
            self.fs_state.register_temp_directory(temp_dir)
            try:
                yield temp_dir
            finally:
                # クリーンアップ
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
        else:
            # モックファイルシステムを使用
            mock_temp_dir = Path("/mock/temp/dir")
            self.mock_fs.create_directory(str(mock_temp_dir))
            try:
                yield mock_temp_dir
            finally:
                self.mock_fs.clear()

    def setup_consistent_file_mocks(self) -> None:
        """一貫したファイル操作モックを設定"""

        def mock_open_func(file_path, mode="r", *args, **kwargs):
            """一貫したopen関数のモック"""
            path_str = str(file_path)

            if "r" in mode:
                # 読み込みモード
                if not self.mock_fs.file_exists(path_str):
                    raise FileNotFoundError(f"No such file or directory: '{path_str}'")
                content = self.mock_fs.read_file(path_str)
                mock_file = Mock()
                mock_file.read.return_value = content
                mock_file.readlines.return_value = content.splitlines(keepends=True)

                # Context manager methods
                mock_file.__enter__ = Mock(return_value=mock_file)
                mock_file.__exit__ = Mock(return_value=None)
                return mock_file

            elif "w" in mode or "a" in mode:
                # 書き込みモード
                if "w" in mode:
                    # 新規作成または上書き
                    self.mock_fs.create_file(path_str, "")
                elif not self.mock_fs.file_exists(path_str):
                    # 追記モードで存在しないファイル
                    self.mock_fs.create_file(path_str, "")

                mock_file = Mock()
                written_content = []

                def write_func(content):
                    written_content.append(content)
                    current_content = self.mock_fs.read_file(path_str) if self.mock_fs.file_exists(path_str) else ""
                    if "w" in mode:
                        new_content = "".join(written_content)
                    else:  # append mode
                        new_content = current_content + "".join(written_content)
                    self.mock_fs.write_file(path_str, new_content)

                mock_file.write = write_func
                mock_file.flush = Mock()

                # Context manager methods
                mock_file.__enter__ = Mock(return_value=mock_file)
                mock_file.__exit__ = Mock(return_value=None)
                return mock_file

            else:
                raise ValueError(f"Unsupported file mode: {mode}")

        # builtins.openをパッチ
        open_patch = patch("builtins.open", side_effect=mock_open_func)
        self._active_patches.append(open_patch)
        open_patch.start()

    def setup_pathlib_mocks(self) -> None:
        """pathlibのメソッドをモック化（安全な方法）"""

        def mock_path_mkdir(path_self, mode=0o777, parents=False, exist_ok=False):
            """pathlib.Path.mkdir()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                # 実際のpathlibの動作を呼び出す
                return path_self.__class__.mkdir(path_self, mode=mode, parents=parents, exist_ok=exist_ok)

            # 親ディレクトリの作成
            if parents:
                parent_path = str(path_self.parent)
                if parent_path != "/" and parent_path != path_str:
                    self.mock_fs.create_directory(parent_path)

            # ディレクトリを作成
            if not self.mock_fs.directory_exists(path_str):
                self.mock_fs.create_directory(path_str)
            elif not exist_ok:
                raise FileExistsError(f"Directory already exists: {path_str}")

        def mock_path_exists(path_self):
            """pathlib.Path.exists()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                return path_self.__class__.exists(path_self)

            return self.mock_fs.file_exists(path_str) or self.mock_fs.directory_exists(path_str)

        def mock_path_is_dir(path_self):
            """pathlib.Path.is_dir()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                return path_self.__class__.is_dir(path_self)

            return self.mock_fs.directory_exists(path_str)

        def mock_path_is_file(path_self):
            """pathlib.Path.is_file()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                return path_self.__class__.is_file(path_self)

            return self.mock_fs.file_exists(path_str)

        def mock_path_read_text(path_self, encoding="utf-8", errors="strict"):
            """pathlib.Path.read_text()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                return path_self.__class__.read_text(path_self, encoding=encoding, errors=errors)

            if not self.mock_fs.file_exists(path_str):
                raise FileNotFoundError(f"No such file or directory: '{path_str}'")
            return self.mock_fs.read_file(path_str)

        def mock_path_write_text(path_self, data, encoding="utf-8", errors="strict", newline=None):
            """pathlib.Path.write_text()のモック"""
            path_str = str(path_self)

            # /mockで始まるパスのみをモック化
            if not path_str.startswith("/mock"):
                return path_self.__class__.write_text(
                    path_self, data, encoding=encoding, errors=errors, newline=newline
                )

            # 親ディレクトリを作成
            parent_path = str(path_self.parent)
            if parent_path != "/" and parent_path != path_str:
                self.mock_fs.create_directory(parent_path)

            self.mock_fs.create_file(path_str, data)
            return len(data)

        # pathlibメソッドをパッチ
        from pathlib import Path

        mkdir_patch = patch.object(Path, "mkdir", mock_path_mkdir)
        exists_patch = patch.object(Path, "exists", mock_path_exists)
        is_dir_patch = patch.object(Path, "is_dir", mock_path_is_dir)
        is_file_patch = patch.object(Path, "is_file", mock_path_is_file)
        read_text_patch = patch.object(Path, "read_text", mock_path_read_text)
        write_text_patch = patch.object(Path, "write_text", mock_path_write_text)

        patches = [mkdir_patch, exists_patch, is_dir_patch, is_file_patch, read_text_patch, write_text_patch]

        for p in patches:
            self._active_patches.append(p)
            p.start()

    def setup_tempfile_mocks(self) -> None:
        """tempfileモジュールのモック化"""

        def mock_mkdtemp(prefix="tmp"):
            """tempfile.mkdtemp()のモック"""
            import uuid

            temp_path = f"/mock/temp/{prefix}{uuid.uuid4().hex[:8]}"
            self.mock_fs.create_directory(temp_path)
            return temp_path

        def mock_named_temporary_file(*args, **kwargs):
            """tempfile.NamedTemporaryFile()のモック"""
            import uuid

            temp_path = f"/mock/temp/tmp{uuid.uuid4().hex[:8]}.tmp"
            self.mock_fs.create_file(temp_path, "")

            mock_file = Mock()
            mock_file.name = temp_path
            mock_file.write = lambda content: self.mock_fs.write_file(temp_path, content)
            mock_file.read = lambda: self.mock_fs.read_file(temp_path)
            mock_file.flush = Mock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            return mock_file

        def mock_temporary_directory(*args, **kwargs):
            """tempfile.TemporaryDirectory()のモック"""
            import uuid

            temp_path = f"/mock/temp/tmpdir{uuid.uuid4().hex[:8]}"
            self.mock_fs.create_directory(temp_path)

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

    def setup_shutil_mocks(self) -> None:
        """shutilモジュールのモック化"""

        def mock_rmtree(path, ignore_errors=False, onerror=None):
            """shutil.rmtree()のモック"""
            path_str = str(path)
            if self.mock_fs.directory_exists(path_str):
                # ディレクトリ内のファイルも削除
                files_to_remove = [f for f in self.mock_fs.files.keys() if f.startswith(path_str)]
                for file_path in files_to_remove:
                    del self.mock_fs.files[file_path]
                self.mock_fs.directories.discard(path_str)
            elif not ignore_errors:
                raise FileNotFoundError(f"Directory not found: {path_str}")

        def mock_copy2(src, dst):
            """shutil.copy2()のモック"""
            src_str, dst_str = str(src), str(dst)
            if not self.mock_fs.file_exists(src_str):
                raise FileNotFoundError(f"Source file not found: {src_str}")
            content = self.mock_fs.read_file(src_str)
            self.mock_fs.create_file(dst_str, content)

        # shutilモジュールをパッチ
        rmtree_patch = patch("shutil.rmtree", side_effect=mock_rmtree)
        copy2_patch = patch("shutil.copy2", side_effect=mock_copy2)

        patches = [rmtree_patch, copy2_patch]

        for p in patches:
            self._active_patches.append(p)
            p.start()

    def create_test_file(self, path: str | Path, content: str = "") -> Path:
        """テスト用ファイルを作成

        Args:
            path: ファイルパス
            content: ファイル内容

        Returns:
            Path: 作成されたファイルのパス
        """
        path_obj = Path(path)
        self.mock_fs.create_file(str(path_obj), content)
        return path_obj

    def create_test_directory(self, path: str | Path) -> Path:
        """テスト用ディレクトリを作成

        Args:
            path: ディレクトリパス

        Returns:
            Path: 作成されたディレクトリのパス
        """
        path_obj = Path(path)
        self.mock_fs.create_directory(str(path_obj))
        return path_obj

    def setup_all_mocks(self) -> None:
        """すべてのファイル操作モックを設定"""
        self.setup_consistent_file_mocks()
        self.setup_pathlib_mocks()  # pathlibモックを有効化
        self.setup_tempfile_mocks()
        self.setup_shutil_mocks()

    def cleanup_mocks(self) -> None:
        """すべてのモックをクリーンアップ"""
        for patch_obj in self._active_patches:
            try:
                patch_obj.stop()
            except Exception:
                pass  # パッチ停止エラーは無視
        self._active_patches.clear()
        self.mock_fs.clear()
        self.fs_state.cleanup_all()

    @contextmanager
    def stable_file_operations(self, use_mock_fs: bool = True) -> Generator[FileOperationMockStabilizer]:
        """安定したファイル操作環境を提供

        Args:
            use_mock_fs: モックファイルシステムを使用するか

        Yields:
            FileOperationMockStabilizer: 設定済みのスタビライザー
        """
        try:
            if use_mock_fs:
                self.setup_all_mocks()
            yield self
        finally:
            self.cleanup_mocks()


# 便利な関数とデコレータ


@contextmanager
def isolated_file_system(use_real_temp_dir: bool = True) -> Generator[Path]:
    """分離されたファイルシステム環境を提供する便利関数

    Args:
        use_real_temp_dir: 実際の一時ディレクトリを使用するか

    Yields:
        Path: 一時ディレクトリのパス
    """
    stabilizer = FileOperationMockStabilizer()
    with stabilizer.isolated_filesystem(use_real_temp_dir) as temp_dir:
        yield temp_dir


@contextmanager
def stable_file_mocks() -> Generator[FileOperationMockStabilizer]:
    """安定したファイル操作モックを提供する便利関数

    Yields:
        FileOperationMockStabilizer: 設定済みのスタビライザー
    """
    stabilizer = FileOperationMockStabilizer()
    with stabilizer.stable_file_operations() as stab:
        yield stab


def with_stable_file_operations(use_mock_fs: bool = True):
    """安定したファイル操作環境を提供するデコレータ

    Args:
        use_mock_fs: モックファイルシステムを使用するか
    """

    def decorator(test_func):
        def wrapper(*args, **kwargs):
            stabilizer = FileOperationMockStabilizer()
            with stabilizer.stable_file_operations(use_mock_fs):
                return test_func(*args, **kwargs)

        return wrapper

    return decorator


# グローバルスタビライザーインスタンス（テスト間で共有）
_global_stabilizer: FileOperationMockStabilizer | None = None


def get_global_file_stabilizer() -> FileOperationMockStabilizer:
    """グローバルファイルスタビライザーを取得

    Returns:
        FileOperationMockStabilizer: グローバルスタビライザー
    """
    global _global_stabilizer
    if _global_stabilizer is None:
        _global_stabilizer = FileOperationMockStabilizer()
    return _global_stabilizer


def reset_global_file_stabilizer() -> None:
    """グローバルファイルスタビライザーをリセット"""
    global _global_stabilizer
    if _global_stabilizer is not None:
        _global_stabilizer.cleanup_mocks()
        _global_stabilizer = None
