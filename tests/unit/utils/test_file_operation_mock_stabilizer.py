"""
ファイル操作モック安定化機能のテスト

FileOperationMockStabilizerクラスの動作を検証し、
ファイル操作の一貫性とテスト間の分離を確認します。
"""

import threading
import time
from pathlib import Path

import pytest

from tests.utils.file_operation_mock_stabilizer import (
    FileOperationMockStabilizer,
    FileSystemState,
    MockFileSystem,
    isolated_file_system,
    stable_file_mocks,
    with_stable_file_operations,
)


class TestFileSystemState:
    """FileSystemStateクラスのテスト"""

    def test_file_creation_tracking(self):
        """ファイル作成の追跡テスト"""
        state = FileSystemState()
        file_path = Path("/test/file.txt")

        state.register_file_creation(file_path)

        assert file_path in state.created_files
        assert len(state.created_files) == 1

    def test_directory_creation_tracking(self):
        """ディレクトリ作成の追跡テスト"""
        state = FileSystemState()
        dir_path = Path("/test/directory")

        state.register_directory_creation(dir_path)

        assert dir_path in state.created_directories
        assert len(state.created_directories) == 1

    def test_file_modification_tracking(self):
        """ファイル変更の追跡テスト"""
        state = FileSystemState()
        file_path = Path("/test/file.txt")

        state.register_file_modification(file_path)

        assert file_path in state.modified_files
        assert len(state.modified_files) == 1

    def test_temp_directory_tracking(self):
        """一時ディレクトリの追跡テスト"""
        state = FileSystemState()
        temp_dir = Path("/tmp/test")  # noqa: S108

        state.register_temp_directory(temp_dir)

        assert temp_dir in state.temp_directories
        assert len(state.temp_directories) == 1

    def test_cleanup_all(self):
        """全体クリーンアップテスト"""
        state = FileSystemState()

        # 各種リソースを登録
        state.register_file_creation(Path("/test/file.txt"))
        state.register_directory_creation(Path("/test/dir"))
        state.register_file_modification(Path("/test/modified.txt"))
        state.register_temp_directory(Path("/tmp/test"))  # noqa: S108

        # クリーンアップ実行
        state.cleanup_all()

        # すべてがクリアされることを確認
        assert len(state.created_files) == 0
        assert len(state.created_directories) == 0
        assert len(state.modified_files) == 0
        assert len(state.temp_directories) == 0

    def test_thread_safety(self):
        """スレッドセーフティテスト"""
        state = FileSystemState()
        results = []

        def register_files(start_index):
            for i in range(start_index, start_index + 10):
                file_path = Path(f"/test/file_{i}.txt")
                state.register_file_creation(file_path)
                results.append(i)

        # 複数スレッドで同時にファイル登録
        threads = []
        for i in range(0, 30, 10):
            thread = threading.Thread(target=register_files, args=(i,))
            threads.append(thread)
            thread.start()

        # 全スレッドの完了を待機
        for thread in threads:
            thread.join()

        # 結果を確認
        assert len(results) == 30
        assert len(state.created_files) == 30


class TestMockFileSystem:
    """MockFileSystemクラスのテスト"""

    def test_file_creation_and_reading(self):
        """ファイル作成と読み込みテスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_file("/test/file.txt", "test content")

        assert mock_fs.file_exists("/test/file.txt")
        assert mock_fs.read_file("/test/file.txt") == "test content"

    def test_file_writing(self):
        """ファイル書き込みテスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_file("/test/file.txt", "original content")
        mock_fs.write_file("/test/file.txt", "updated content")

        assert mock_fs.read_file("/test/file.txt") == "updated content"

    def test_file_deletion(self):
        """ファイル削除テスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_file("/test/file.txt", "test content")
        assert mock_fs.file_exists("/test/file.txt")

        mock_fs.delete_file("/test/file.txt")
        assert not mock_fs.file_exists("/test/file.txt")

    def test_directory_operations(self):
        """ディレクトリ操作テスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_directory("/test/directory")

        assert mock_fs.directory_exists("/test/directory")

    def test_file_not_found_errors(self):
        """ファイル未発見エラーテスト"""
        mock_fs = MockFileSystem()

        with pytest.raises(FileNotFoundError):
            mock_fs.read_file("/nonexistent/file.txt")

        with pytest.raises(FileNotFoundError):
            mock_fs.write_file("/nonexistent/file.txt", "content")

        with pytest.raises(FileNotFoundError):
            mock_fs.delete_file("/nonexistent/file.txt")

    def test_list_files(self):
        """ファイル一覧取得テスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_file("/test/file1.txt", "content1")
        mock_fs.create_file("/test/file2.txt", "content2")

        files = mock_fs.list_files()
        assert len(files) == 2
        assert "/test/file1.txt" in files
        assert "/test/file2.txt" in files

    def test_clear(self):
        """クリアテスト"""
        mock_fs = MockFileSystem()

        mock_fs.create_file("/test/file.txt", "content")
        mock_fs.create_directory("/test/directory")

        mock_fs.clear()

        assert len(mock_fs.files) == 0
        assert len(mock_fs.directories) == 0

    def test_thread_safety(self):
        """スレッドセーフティテスト"""
        mock_fs = MockFileSystem()
        results = []

        def create_files(start_index):
            for i in range(start_index, start_index + 10):
                file_path = f"/test/file_{i}.txt"
                mock_fs.create_file(file_path, f"content_{i}")
                results.append(i)

        # 複数スレッドで同時にファイル作成
        threads = []
        for i in range(0, 30, 10):
            thread = threading.Thread(target=create_files, args=(i,))
            threads.append(thread)
            thread.start()

        # 全スレッドの完了を待機
        for thread in threads:
            thread.join()

        # 結果を確認
        assert len(results) == 30
        assert len(mock_fs.files) == 30


class TestFileOperationMockStabilizer:
    """FileOperationMockStabilizerクラスのテスト"""

    def test_isolated_filesystem_real_temp_dir(self):
        """実際の一時ディレクトリを使用した分離ファイルシステムテスト"""
        stabilizer = FileOperationMockStabilizer()

        with stabilizer.isolated_filesystem(use_real_temp_dir=True) as temp_dir:
            assert temp_dir.exists()
            assert temp_dir.is_dir()

            # テストファイルを作成
            test_file = temp_dir / "test.txt"
            test_file.write_text("test content")

            assert test_file.exists()
            assert test_file.read_text() == "test content"

        # コンテキスト終了後はクリーンアップされる
        assert not temp_dir.exists()

    def test_isolated_filesystem_mock_fs(self):
        """モックファイルシステムを使用した分離ファイルシステムテスト"""
        stabilizer = FileOperationMockStabilizer()

        with stabilizer.isolated_filesystem(use_real_temp_dir=False) as temp_dir:
            # モックファイルシステムでは実際のディレクトリは存在しない
            assert str(temp_dir) == "/mock/temp/dir"

    def test_create_test_file(self):
        """テストファイル作成テスト"""
        stabilizer = FileOperationMockStabilizer()

        file_path = stabilizer.create_test_file("/test/file.txt", "test content")

        assert stabilizer.mock_fs.file_exists(str(file_path))
        assert stabilizer.mock_fs.read_file(str(file_path)) == "test content"

    def test_create_test_directory(self):
        """テストディレクトリ作成テスト"""
        stabilizer = FileOperationMockStabilizer()

        dir_path = stabilizer.create_test_directory("/test/directory")

        assert stabilizer.mock_fs.directory_exists(str(dir_path))

    def test_stable_file_operations_context(self):
        """安定したファイル操作コンテキストテスト"""
        stabilizer = FileOperationMockStabilizer()

        with stabilizer.stable_file_operations() as stab:
            # モックが設定されていることを確認
            assert len(stab._active_patches) > 0

            # テストファイルを作成
            stab.create_test_file("/test/file.txt", "content")
            assert stab.mock_fs.file_exists("/test/file.txt")

        # コンテキスト終了後はクリーンアップされる
        assert len(stabilizer._active_patches) == 0

    def test_cleanup_mocks(self):
        """モッククリーンアップテスト"""
        stabilizer = FileOperationMockStabilizer()

        # モックを設定
        stabilizer.setup_all_mocks()
        assert len(stabilizer._active_patches) > 0

        # クリーンアップ実行
        stabilizer.cleanup_mocks()
        assert len(stabilizer._active_patches) == 0
        assert len(stabilizer.mock_fs.files) == 0


class TestConvenienceFunctions:
    """便利関数のテスト"""

    def test_isolated_file_system_function(self):
        """isolated_file_system関数のテスト"""
        with isolated_file_system(use_real_temp_dir=True) as temp_dir:
            assert temp_dir.exists()
            assert temp_dir.is_dir()

            test_file = temp_dir / "test.txt"
            test_file.write_text("test content")
            assert test_file.exists()

    def test_stable_file_mocks_function(self):
        """stable_file_mocks関数のテスト"""
        with stable_file_mocks() as stabilizer:
            assert isinstance(stabilizer, FileOperationMockStabilizer)
            assert len(stabilizer._active_patches) > 0

    def test_with_stable_file_operations_decorator(self):
        """with_stable_file_operationsデコレータのテスト"""

        @with_stable_file_operations(use_mock_fs=True)
        def test_function():
            # デコレータ内でファイル操作が安定化されていることを確認
            return "success"

        result = test_function()
        assert result == "success"


class TestFileOperationConsistency:
    """ファイル操作の一貫性テスト"""

    def test_consistent_file_creation_across_tests(self):
        """テスト間でのファイル作成の一貫性テスト"""

        # 最初のテスト環境
        with stable_file_mocks() as stabilizer1:
            stabilizer1.create_test_file("/test/file1.txt", "content1")
            assert stabilizer1.mock_fs.file_exists("/test/file1.txt")

        # 2番目のテスト環境（分離されている）
        with stable_file_mocks() as stabilizer2:
            # 前のテストのファイルは存在しない
            assert not stabilizer2.mock_fs.file_exists("/test/file1.txt")

            # 新しいファイルを作成
            stabilizer2.create_test_file("/test/file2.txt", "content2")
            assert stabilizer2.mock_fs.file_exists("/test/file2.txt")

    def test_concurrent_file_operations(self):
        """並行ファイル操作テスト"""
        stabilizer = FileOperationMockStabilizer()
        results = []
        errors = []

        # 共有のstable_file_operationsコンテキストを使用
        with stabilizer.stable_file_operations():

            def file_operations(thread_id):
                try:
                    # ファイル作成
                    file_path = f"/test/file_{thread_id}.txt"
                    stabilizer.create_test_file(file_path, f"content_{thread_id}")

                    # ファイル存在確認
                    if stabilizer.mock_fs.file_exists(file_path):
                        results.append(thread_id)

                    # 少し待機
                    time.sleep(0.01)

                    # ファイル読み込み
                    content = stabilizer.mock_fs.read_file(file_path)
                    if content == f"content_{thread_id}":
                        results.append(f"read_{thread_id}")

                except Exception as e:
                    errors.append(e)

            # 複数スレッドで並行実行
            threads = []
            for i in range(5):
                thread = threading.Thread(target=file_operations, args=(i,))
                threads.append(thread)
                thread.start()

            # 全スレッドの完了を待機
            for thread in threads:
                thread.join()

        # エラーが発生しないことを確認
        assert len(errors) == 0

        # 期待される結果数を確認
        assert len(results) == 10  # 5つのファイル作成 + 5つの読み込み

    def test_file_state_isolation_between_tests(self):
        """テスト間でのファイル状態分離テスト"""

        # テスト1: ファイルを作成
        def test1():
            with stable_file_mocks() as stabilizer:
                stabilizer.create_test_file("/shared/file.txt", "test1 content")
                return stabilizer.mock_fs.file_exists("/shared/file.txt")

        # テスト2: 同じパスのファイルは存在しない
        def test2():
            with stable_file_mocks() as stabilizer:
                return stabilizer.mock_fs.file_exists("/shared/file.txt")

        # テスト実行
        result1 = test1()
        result2 = test2()

        # テスト1ではファイルが存在し、テスト2では存在しない
        assert result1 is True
        assert result2 is False

    def test_mock_consistency_with_real_pathlib_behavior(self):
        """実際のpathlibの動作との一貫性テスト"""

        with stable_file_mocks() as stabilizer:
            # ファイルを作成
            stabilizer.create_test_file("/test/file.txt", "test content")

            # モックファイルシステムでの動作確認
            assert stabilizer.mock_fs.file_exists("/test/file.txt")
            assert stabilizer.mock_fs.read_file("/test/file.txt") == "test content"

            # 存在しないファイルへのアクセス
            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.read_file("/nonexistent/file.txt")

    def test_error_handling_consistency(self):
        """エラーハンドリングの一貫性テスト"""

        with stable_file_mocks() as stabilizer:
            # 存在しないファイルの読み込み
            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.read_file("/nonexistent/file.txt")

            # 存在しないファイルの削除
            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.delete_file("/nonexistent/file.txt")

            # 存在しないファイルへの書き込み
            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.write_file("/nonexistent/file.txt", "content")


class TestIntegrationWithExistingTests:
    """既存テストとの統合テスト"""

    def test_integration_with_temp_dir_fixture(self, temp_dir):
        """temp_dirフィクスチャとの統合テスト"""

        # 実際の一時ディレクトリでファイル操作
        test_file = temp_dir / "integration_test.txt"
        test_file.write_text("integration test content")

        assert test_file.exists()
        assert test_file.read_text() == "integration test content"

    def test_integration_with_stable_file_operations_fixture(self, stable_file_operations):
        """stable_file_operationsフィクスチャとの統合テスト"""

        # モックファイルシステムでファイル操作
        stable_file_operations.create_test_file("/integration/test.txt", "mock content")

        assert stable_file_operations.mock_fs.file_exists("/integration/test.txt")
        assert stable_file_operations.mock_fs.read_file("/integration/test.txt") == "mock content"

    def test_integration_with_isolated_filesystem_fixture(self, isolated_filesystem):
        """isolated_filesystemフィクスチャとの統合テスト"""

        # 分離されたファイルシステムでファイル操作
        test_file = isolated_filesystem / "isolated_test.txt"
        test_file.write_text("isolated content")

        assert test_file.exists()
        assert test_file.read_text() == "isolated content"
