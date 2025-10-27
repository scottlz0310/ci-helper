"""
シンプルなファイル操作モック安定化機能のテスト

SimpleFileMockStabilizerクラスの動作を検証します。
"""

import threading
import time

import pytest

from tests.utils.simple_file_mock_stabilizer import (
    SimpleFileMockStabilizer,
    SimpleFileSystemState,
    ensure_simple_file_operation_consistency,
    simple_stable_file_mocks,
    with_simple_stable_file_operations,
)


class TestSimpleFileSystemState:
    """SimpleFileSystemStateクラスのテスト"""

    def test_file_creation_and_reading(self):
        """ファイル作成と読み込みテスト"""
        state = SimpleFileSystemState()

        state.create_file("/test/file.txt", "test content")

        assert state.file_exists("/test/file.txt")
        assert state.read_file("/test/file.txt") == "test content"

    def test_file_writing(self):
        """ファイル書き込みテスト"""
        state = SimpleFileSystemState()

        state.create_file("/test/file.txt", "original content")
        state.write_file("/test/file.txt", "updated content")

        assert state.read_file("/test/file.txt") == "updated content"

    def test_file_deletion(self):
        """ファイル削除テスト"""
        state = SimpleFileSystemState()

        state.create_file("/test/file.txt", "test content")
        assert state.file_exists("/test/file.txt")

        state.delete_file("/test/file.txt")
        assert not state.file_exists("/test/file.txt")

    def test_directory_operations(self):
        """ディレクトリ操作テスト"""
        state = SimpleFileSystemState()

        state.create_file("/test/dir/file.txt", "content")

        # 親ディレクトリが自動的に作成される
        assert state.directory_exists("/test/dir")

    def test_file_not_found_errors(self):
        """ファイル未発見エラーテスト"""
        state = SimpleFileSystemState()

        with pytest.raises(FileNotFoundError):
            state.read_file("/nonexistent/file.txt")

        with pytest.raises(FileNotFoundError):
            state.write_file("/nonexistent/file.txt", "content")

        with pytest.raises(FileNotFoundError):
            state.delete_file("/nonexistent/file.txt")

    def test_clear(self):
        """クリアテスト"""
        state = SimpleFileSystemState()

        state.create_file("/test/file.txt", "content")

        state.clear()

        assert len(state.files) == 0
        assert len(state.directories) == 0

    def test_thread_safety(self):
        """スレッドセーフティテスト"""
        state = SimpleFileSystemState()
        results = []

        def create_files(start_index):
            for i in range(start_index, start_index + 10):
                file_path = f"/test/file_{i}.txt"
                state.create_file(file_path, f"content_{i}")
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
        assert len(state.files) == 30


class TestSimpleFileMockStabilizer:
    """SimpleFileMockStabilizerクラスのテスト"""

    def test_create_test_file(self):
        """テストファイル作成テスト"""
        stabilizer = SimpleFileMockStabilizer()

        stabilizer.create_test_file("/test/file.txt", "test content")

        assert stabilizer.fs_state.file_exists("/test/file.txt")
        assert stabilizer.fs_state.read_file("/test/file.txt") == "test content"

    def test_create_test_directory(self):
        """テストディレクトリ作成テスト"""
        stabilizer = SimpleFileMockStabilizer()

        stabilizer.create_test_directory("/test/directory")

        assert stabilizer.fs_state.directory_exists("/test/directory")

    def test_stable_file_operations_context(self):
        """安定したファイル操作コンテキストテスト"""
        stabilizer = SimpleFileMockStabilizer()

        with stabilizer.stable_file_operations() as stab:
            # モックが設定されていることを確認
            assert len(stab._active_patches) > 0

            # テストファイルを作成
            stab.create_test_file("/test/file.txt", "content")
            assert stab.fs_state.file_exists("/test/file.txt")

        # コンテキスト終了後はクリーンアップされる
        assert len(stabilizer._active_patches) == 0

    def test_cleanup_mocks(self):
        """モッククリーンアップテスト"""
        stabilizer = SimpleFileMockStabilizer()

        # モックを設定
        stabilizer.setup_all_mocks()
        assert len(stabilizer._active_patches) > 0

        # クリーンアップ実行
        stabilizer.cleanup_mocks()
        assert len(stabilizer._active_patches) == 0
        assert len(stabilizer.fs_state.files) == 0


class TestConvenienceFunctions:
    """便利関数のテスト"""

    def test_simple_stable_file_mocks_function(self):
        """simple_stable_file_mocks関数のテスト"""
        with simple_stable_file_mocks() as stabilizer:
            assert isinstance(stabilizer, SimpleFileMockStabilizer)
            assert len(stabilizer._active_patches) > 0

    def test_with_simple_stable_file_operations_decorator(self):
        """with_simple_stable_file_operationsデコレータのテスト"""

        @with_simple_stable_file_operations
        def test_function(stabilizer):
            # デコレータ内でファイル操作が安定化されていることを確認
            stabilizer.create_test_file("/test/file.txt", "content")
            assert stabilizer.fs_state.file_exists("/test/file.txt")
            return "success"

        result = test_function()
        assert result == "success"

    def test_ensure_simple_file_operation_consistency_decorator(self):
        """ensure_simple_file_operation_consistencyデコレータのテスト"""

        @ensure_simple_file_operation_consistency
        def test_function():
            # デコレータ内でファイル操作の一貫性が確保されていることを確認
            return "success"

        result = test_function()
        assert result == "success"


class TestFileOperationConsistency:
    """ファイル操作の一貫性テスト"""

    def test_consistent_file_creation_across_tests(self):
        """テスト間でのファイル作成の一貫性テスト"""

        # 最初のテスト環境
        with simple_stable_file_mocks() as stabilizer1:
            stabilizer1.create_test_file("/test/file1.txt", "content1")
            assert stabilizer1.fs_state.file_exists("/test/file1.txt")

        # 2番目のテスト環境（分離されている）
        with simple_stable_file_mocks() as stabilizer2:
            # 前のテストのファイルは存在しない
            assert not stabilizer2.fs_state.file_exists("/test/file1.txt")

            # 新しいファイルを作成
            stabilizer2.create_test_file("/test/file2.txt", "content2")
            assert stabilizer2.fs_state.file_exists("/test/file2.txt")

    def test_concurrent_file_operations(self):
        """並行ファイル操作テスト"""
        results = []
        errors = []

        def file_operations(thread_id):
            try:
                # 各スレッドで独立したスタビライザーを使用
                with simple_stable_file_mocks() as stabilizer:
                    # ファイル作成
                    file_path = f"/test/file_{thread_id}.txt"
                    stabilizer.create_test_file(file_path, f"content_{thread_id}")

                    # ファイル存在確認
                    if stabilizer.fs_state.file_exists(file_path):
                        results.append(thread_id)

                    # 少し待機
                    time.sleep(0.01)

                    # ファイル読み込み
                    content = stabilizer.fs_state.read_file(file_path)
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
            with simple_stable_file_mocks() as stabilizer:
                stabilizer.create_test_file("/shared/file.txt", "test1 content")
                return stabilizer.fs_state.file_exists("/shared/file.txt")

        # テスト2: 同じパスのファイルは存在しない
        def test2():
            with simple_stable_file_mocks() as stabilizer:
                return stabilizer.fs_state.file_exists("/shared/file.txt")

        # テスト実行
        result1 = test1()
        result2 = test2()

        # テスト1ではファイルが存在し、テスト2では存在しない
        assert result1 is True
        assert result2 is False

    def test_error_handling_consistency(self):
        """エラーハンドリングの一貫性テスト"""

        with simple_stable_file_mocks() as stabilizer:
            # 存在しないファイルの読み込み
            with pytest.raises(FileNotFoundError):
                stabilizer.fs_state.read_file("/nonexistent/file.txt")

            # 存在しないファイルの削除
            with pytest.raises(FileNotFoundError):
                stabilizer.fs_state.delete_file("/nonexistent/file.txt")

            # 存在しないファイルへの書き込み
            with pytest.raises(FileNotFoundError):
                stabilizer.fs_state.write_file("/nonexistent/file.txt", "content")


class TestMockIntegration:
    """モック統合テスト"""

    def test_open_mock_read_mode(self):
        """openモックの読み込みモードテスト"""

        with simple_stable_file_mocks() as stabilizer:
            # ファイルを作成
            stabilizer.create_test_file("/test/file.txt", "test content")

            # モックされたopenを使用してファイルを読み込み
            # 注意: 実際のテストでは、テスト対象のコードがopenを呼び出す
            # ここでは直接的にテストするため、パッチされた関数を確認
            assert len(stabilizer._active_patches) > 0

    def test_open_mock_write_mode(self):
        """openモックの書き込みモードテスト"""

        with simple_stable_file_mocks() as stabilizer:
            # ファイルシステムが正しく初期化されていることを確認
            assert len(stabilizer.fs_state.files) == 0

            # ファイルを作成
            stabilizer.create_test_file("/test/file.txt", "initial content")

            # ファイルが作成されたことを確認
            assert stabilizer.fs_state.file_exists("/test/file.txt")
            assert stabilizer.fs_state.read_file("/test/file.txt") == "initial content"

    def test_tempfile_mock_integration(self):
        """tempfileモック統合テスト"""

        with simple_stable_file_mocks() as stabilizer:
            # tempfileモックが設定されていることを確認
            assert len(stabilizer._active_patches) > 0

            # 実際のtempfile使用はテスト対象のコードで行われる
            # ここではモックが正しく設定されていることを確認
            assert stabilizer.fs_state is not None


class TestRealWorldScenarios:
    """実世界のシナリオテスト"""

    def test_log_file_management_scenario(self):
        """ログファイル管理シナリオのテスト"""

        with simple_stable_file_mocks() as stabilizer:
            # ログディレクトリを作成
            stabilizer.create_test_directory("/logs")

            # 複数のログファイルを作成
            for i in range(3):
                log_file = f"/logs/app_{i}.log"
                stabilizer.create_test_file(log_file, f"Log entry {i}")

            # すべてのログファイルが存在することを確認
            for i in range(3):
                log_file = f"/logs/app_{i}.log"
                assert stabilizer.fs_state.file_exists(log_file)
                assert stabilizer.fs_state.read_file(log_file) == f"Log entry {i}"

    def test_configuration_file_scenario(self):
        """設定ファイルシナリオのテスト"""

        with simple_stable_file_mocks() as stabilizer:
            # 設定ファイルを作成
            config_file = "/config/app.conf"
            stabilizer.create_test_file(config_file, "debug=true\nport=8080")

            # 設定ファイルの存在確認
            assert stabilizer.fs_state.file_exists(config_file)

            # 設定内容の確認
            content = stabilizer.fs_state.read_file(config_file)
            assert "debug=true" in content
            assert "port=8080" in content

            # 設定ファイルの更新
            stabilizer.fs_state.write_file(config_file, "debug=false\nport=9090")
            updated_content = stabilizer.fs_state.read_file(config_file)
            assert "debug=false" in updated_content
            assert "port=9090" in updated_content

    def test_backup_scenario(self):
        """バックアップシナリオのテスト"""

        with simple_stable_file_mocks() as stabilizer:
            # 元ファイルを作成
            original_file = "/data/important.txt"
            stabilizer.create_test_file(original_file, "Important data")

            # バックアップファイルを作成
            backup_file = "/backup/important.txt.bak"
            original_content = stabilizer.fs_state.read_file(original_file)
            stabilizer.create_test_file(backup_file, original_content)

            # バックアップが正しく作成されたことを確認
            assert stabilizer.fs_state.file_exists(backup_file)
            assert stabilizer.fs_state.read_file(backup_file) == "Important data"

            # 元ファイルを変更
            stabilizer.fs_state.write_file(original_file, "Modified data")
            assert stabilizer.fs_state.read_file(original_file) == "Modified data"

            # バックアップから復元
            backup_content = stabilizer.fs_state.read_file(backup_file)
            stabilizer.fs_state.write_file(original_file, backup_content)

            # 復元が正しく行われたことを確認
            assert stabilizer.fs_state.read_file(original_file) == "Important data"
