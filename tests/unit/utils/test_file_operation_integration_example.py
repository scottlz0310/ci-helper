"""
ファイル操作モック安定化機能の統合例

既存のテストでファイル操作モック安定化機能を使用する方法を示します。
"""

import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ci_helper.core.exceptions import ExecutionError
from ci_helper.core.log_manager import LogManager
from ci_helper.core.models import ExecutionResult, Failure, JobResult, WorkflowResult
from ci_helper.utils.config import Config
from tests.utils.file_operation_mock_stabilizer import stable_file_mocks, with_stable_file_operations
from tests.utils.mock_helpers import ensure_file_operation_consistency


class TestLogHistoryManagementWithStabilizer:
    """ファイル操作安定化機能を使用したログ履歴管理テスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        # モック設定を作成
        self.mock_config = Mock(spec=Config)
        self.mock_config.get.return_value = 100  # max_log_size_mb

    def _create_sample_execution_result(
        self, success: bool = True, duration: float = 5.0, failures: list[Failure] | None = None
    ) -> ExecutionResult:
        """サンプルの実行結果を作成"""
        if failures is None:
            failures = []

        job = JobResult(name="test-job", success=success, failures=failures, duration=duration / 2)
        workflow = WorkflowResult(name="test-workflow", success=success, jobs=[job], duration=duration)
        return ExecutionResult(success=success, workflows=[workflow], total_duration=duration, timestamp=datetime.now())

    def test_save_execution_log_with_stable_mocks(self):
        """安定化されたモックを使用したログ保存テスト"""

        with stable_file_mocks() as stabilizer:
            # ログディレクトリを設定
            log_dir = Path("/mock/logs")
            stabilizer.create_test_directory(str(log_dir))
            self.mock_config.get_path.return_value = log_dir

            # LogManagerを初期化
            log_manager = LogManager(self.mock_config)

            # 実行結果を作成
            execution_result = self._create_sample_execution_result()
            raw_output = "Sample log output"

            # インデックスファイルを事前に作成
            index_file_path = str(log_dir / "index.json")
            stabilizer.create_test_file(index_file_path, '{"version": "1.0", "logs": [], "last_execution": null}')

            # ログを保存（モックファイルシステム内で）
            # Path.stat()をモック化してファイルサイズを返す
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = len(raw_output)
                log_path = log_manager.save_execution_log(execution_result, raw_output)

                # 戻り値を確認
                assert log_path is not None
                assert log_path.name.startswith("act_")
                assert log_path.name.endswith(".log")

                # ログファイルがモックファイルシステムに作成されたことを確認
                assert stabilizer.mock_fs.file_exists(str(log_path))
                assert stabilizer.mock_fs.read_file(str(log_path)) == raw_output

    def test_disk_error_with_stable_mocks(self):
        """安定化されたモックを使用したディスクエラーテスト"""

        with stable_file_mocks() as stabilizer:
            # ログディレクトリを設定
            log_dir = Path("/mock/logs")
            stabilizer.create_test_directory(str(log_dir))
            self.mock_config.get_path.return_value = log_dir

            # LogManagerを初期化
            log_manager = LogManager(self.mock_config)

            # 実行結果を作成
            execution_result = self._create_sample_execution_result()

            # ファイル書き込みエラーをシミュレート
            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                with pytest.raises(ExecutionError) as exc_info:
                    log_manager.save_execution_log(execution_result, "test content")

                assert "ログの保存に失敗しました" in str(exc_info.value)

    def test_concurrent_operations_with_stable_mocks(self):
        """安定化されたモックを使用した並行操作テスト"""

        with stable_file_mocks() as stabilizer:
            # ログディレクトリを設定
            log_dir = Path("/mock/logs")
            stabilizer.create_test_directory(str(log_dir))
            self.mock_config.get_path.return_value = log_dir

            # インデックスファイルを事前に作成
            index_file_path = str(log_dir / "index.json")
            stabilizer.create_test_file(index_file_path, '{"version": "1.0", "logs": [], "last_execution": null}')

            results = []
            errors = []

            def save_log(index):
                try:
                    # 各スレッド用のLogManagerを作成
                    log_manager = LogManager(self.mock_config)
                    execution = self._create_sample_execution_result()
                    execution.timestamp = datetime.now() + timedelta(seconds=index)

                    # Path.stat()をモック化してファイルサイズを返す
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = len(f"Concurrent log {index}")
                        log_manager.save_execution_log(execution, f"Concurrent log {index}")
                        results.append(index)

                except Exception as e:
                    errors.append(e)

            # 複数スレッドで同時にログを保存
            threads = []
            for i in range(5):
                thread = threading.Thread(target=save_log, args=(i,))
                threads.append(thread)
                thread.start()

            # 全スレッドの完了を待機
            for thread in threads:
                thread.join()

            # エラーが発生しないことを確認
            assert len(errors) == 0
            assert len(results) == 5

    @with_stable_file_operations(use_mock_fs=True)
    def test_with_decorator(self):
        """デコレータを使用したテスト"""
        # デコレータによりファイル操作が安定化されている

        # ログディレクトリを設定
        log_dir = Path("/mock/logs")
        self.mock_config.get_path.return_value = log_dir

        # LogManagerを初期化
        log_manager = LogManager(self.mock_config)

        # 実行結果を作成
        execution_result = self._create_sample_execution_result()

        # Path.stat()をモック化してファイルサイズを返す
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = len("decorator test")
            log_path = log_manager.save_execution_log(execution_result, "decorator test")

            # 戻り値を確認
            assert log_path is not None

    @ensure_file_operation_consistency
    def test_with_consistency_decorator(self):
        """一貫性確保デコレータを使用したテスト"""
        # デコレータによりファイル操作の一貫性が確保されている

        # ログディレクトリを設定
        log_dir = Path("/mock/logs")
        self.mock_config.get_path.return_value = log_dir

        # LogManagerを初期化
        log_manager = LogManager(self.mock_config)

        # 実行結果を作成
        execution_result = self._create_sample_execution_result()

        # Path.stat()をモック化してファイルサイズを返す
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = len("consistency test")
            log_path = log_manager.save_execution_log(execution_result, "consistency test")

            # 戻り値を確認
            assert log_path is not None


class TestFileOperationStabilityComparison:
    """ファイル操作安定性の比較テスト"""

    def test_without_stabilizer_potential_issues(self):
        """安定化機能なしでの潜在的な問題を示すテスト"""

        # 従来の方法（潜在的な問題あり）
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 複数のテストが同じディレクトリを使用する可能性
            test_file = temp_path / "test.txt"
            test_file.write_text("content")

            # ファイル状態がテスト間で共有される可能性
            assert test_file.exists()

    def test_with_stabilizer_isolated_state(self):
        """安定化機能ありでの分離された状態を示すテスト"""

        # 安定化機能を使用（状態が分離される）
        with stable_file_mocks() as stabilizer:
            # 各テストで独立したファイルシステム状態
            stabilizer.create_test_file("/test/file.txt", "content")

            # ファイル状態が他のテストに影響しない
            assert stabilizer.mock_fs.file_exists("/test/file.txt")

    def test_state_isolation_verification(self):
        """状態分離の検証テスト"""

        # 最初のテスト環境
        with stable_file_mocks() as stabilizer1:
            stabilizer1.create_test_file("/shared/file.txt", "content1")
            assert stabilizer1.mock_fs.file_exists("/shared/file.txt")
            assert stabilizer1.mock_fs.read_file("/shared/file.txt") == "content1"

        # 2番目のテスト環境（完全に分離されている）
        with stable_file_mocks() as stabilizer2:
            # 前のテストのファイルは存在しない
            assert not stabilizer2.mock_fs.file_exists("/shared/file.txt")

            # 新しいファイルを作成
            stabilizer2.create_test_file("/shared/file.txt", "content2")
            assert stabilizer2.mock_fs.read_file("/shared/file.txt") == "content2"

    def test_error_consistency_verification(self):
        """エラー一貫性の検証テスト"""

        with stable_file_mocks() as stabilizer:
            # 存在しないファイルへのアクセスは一貫してエラーになる
            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.read_file("/nonexistent/file.txt")

            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.write_file("/nonexistent/file.txt", "content")

            with pytest.raises(FileNotFoundError):
                stabilizer.mock_fs.delete_file("/nonexistent/file.txt")


class TestRealWorldScenarios:
    """実世界のシナリオテスト"""

    def test_log_rotation_scenario(self):
        """ログローテーションシナリオのテスト"""

        with stable_file_mocks() as stabilizer:
            # ログディレクトリを作成
            log_dir = "/mock/logs"
            stabilizer.create_test_directory(log_dir)

            # 複数のログファイルを作成
            for i in range(5):
                log_file = f"{log_dir}/log_{i}.txt"
                stabilizer.create_test_file(log_file, f"Log content {i}")

            # すべてのログファイルが存在することを確認
            for i in range(5):
                log_file = f"{log_dir}/log_{i}.txt"
                assert stabilizer.mock_fs.file_exists(log_file)
                assert stabilizer.mock_fs.read_file(log_file) == f"Log content {i}"

            # ログローテーション（古いファイルを削除）
            for i in range(2):  # 最初の2つを削除
                log_file = f"{log_dir}/log_{i}.txt"
                stabilizer.mock_fs.delete_file(log_file)

            # 削除されたファイルは存在しない
            for i in range(2):
                log_file = f"{log_dir}/log_{i}.txt"
                assert not stabilizer.mock_fs.file_exists(log_file)

            # 残りのファイルは存在する
            for i in range(2, 5):
                log_file = f"{log_dir}/log_{i}.txt"
                assert stabilizer.mock_fs.file_exists(log_file)

    def test_configuration_file_management(self):
        """設定ファイル管理のテスト"""

        with stable_file_mocks() as stabilizer:
            # 設定ディレクトリを作成
            config_dir = "/mock/config"
            stabilizer.create_test_directory(config_dir)

            # デフォルト設定ファイルを作成
            default_config = f"{config_dir}/default.json"
            stabilizer.create_test_file(default_config, '{"key": "default_value"}')

            # ユーザー設定ファイルを作成
            user_config = f"{config_dir}/user.json"
            stabilizer.create_test_file(user_config, '{"key": "user_value"}')

            # 設定ファイルの存在確認
            assert stabilizer.mock_fs.file_exists(default_config)
            assert stabilizer.mock_fs.file_exists(user_config)

            # 設定内容の確認
            assert '"default_value"' in stabilizer.mock_fs.read_file(default_config)
            assert '"user_value"' in stabilizer.mock_fs.read_file(user_config)

            # 設定ファイルの更新
            stabilizer.mock_fs.write_file(user_config, '{"key": "updated_value"}')
            assert '"updated_value"' in stabilizer.mock_fs.read_file(user_config)

    def test_backup_and_restore_scenario(self):
        """バックアップと復元シナリオのテスト"""

        with stable_file_mocks() as stabilizer:
            # 元ファイルを作成
            original_file = "/mock/data/important.txt"
            stabilizer.create_test_directory("/mock/data")
            stabilizer.create_test_file(original_file, "Important data")

            # バックアップディレクトリを作成
            backup_dir = "/mock/backup"
            stabilizer.create_test_directory(backup_dir)

            # バックアップファイルを作成
            backup_file = f"{backup_dir}/important.txt.bak"
            original_content = stabilizer.mock_fs.read_file(original_file)
            stabilizer.create_test_file(backup_file, original_content)

            # バックアップが正しく作成されたことを確認
            assert stabilizer.mock_fs.file_exists(backup_file)
            assert stabilizer.mock_fs.read_file(backup_file) == "Important data"

            # 元ファイルを変更
            stabilizer.mock_fs.write_file(original_file, "Modified data")
            assert stabilizer.mock_fs.read_file(original_file) == "Modified data"

            # バックアップから復元
            backup_content = stabilizer.mock_fs.read_file(backup_file)
            stabilizer.mock_fs.write_file(original_file, backup_content)

            # 復元が正しく行われたことを確認
            assert stabilizer.mock_fs.read_file(original_file) == "Important data"
