"""
優雅なシャットダウンとタイムアウト処理のユニットテスト
"""

import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ci_helper.core.exceptions import ExecutionError
from ci_helper.utils.graceful_shutdown import (
    GracefulShutdownHandler,
    PartialResultHandler,
    TimeoutManager,
    get_shutdown_handler,
)


class TestGracefulShutdownHandler:
    """GracefulShutdownHandler クラスのテスト"""

    def test_init(self):
        """初期化テスト"""
        handler = GracefulShutdownHandler()

        assert handler.shutdown_requested is False
        assert handler.active_processes == []

    @patch("signal.signal")
    def test_setup_signal_handlers(self, mock_signal):
        """シグナルハンドラー設定テスト"""
        handler = GracefulShutdownHandler()

        # SIGINT と SIGTERM のハンドラーが設定されることを確認
        assert mock_signal.call_count == 2
        mock_signal.assert_any_call(signal.SIGINT, handler._signal_handler)
        mock_signal.assert_any_call(signal.SIGTERM, handler._signal_handler)

    def test_register_process(self):
        """プロセス登録テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()

        handler.register_process(mock_process)

        assert mock_process in handler.active_processes

    def test_unregister_process(self):
        """プロセス登録解除テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()

        handler.register_process(mock_process)
        handler.unregister_process(mock_process)

        assert mock_process not in handler.active_processes

    def test_unregister_nonexistent_process(self):
        """存在しないプロセスの登録解除テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()

        # 例外が発生しないことを確認
        handler.unregister_process(mock_process)

    @patch("ci_helper.utils.graceful_shutdown.console")
    def test_signal_handler_first_call(self, mock_console):
        """初回シグナル受信時の処理テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None

        handler.register_process(mock_process)

        # 初回シグナル受信
        handler._signal_handler(signal.SIGINT, None)

        assert handler.shutdown_requested is True
        mock_console.print.assert_called_once()
        mock_process.terminate.assert_called_once()

    @patch("ci_helper.utils.graceful_shutdown.console")
    @patch("sys.exit")
    def test_signal_handler_second_call(self, mock_exit, mock_console):
        """2回目シグナル受信時の強制終了テスト"""
        handler = GracefulShutdownHandler()
        handler.shutdown_requested = True
        mock_process = Mock()

        handler.register_process(mock_process)

        # 2回目シグナル受信
        handler._signal_handler(signal.SIGINT, None)

        mock_console.print.assert_called_once()
        mock_process.kill.assert_called_once()
        mock_exit.assert_called_once_with(1)

    def test_terminate_processes_success(self):
        """プロセス正常終了テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()
        mock_process.wait.return_value = None

        handler.register_process(mock_process)
        handler._terminate_processes()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert mock_process not in handler.active_processes

    def test_terminate_processes_timeout(self):
        """プロセス終了タイムアウトテスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

        handler.register_process(mock_process)
        handler._terminate_processes()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process not in handler.active_processes

    def test_kill_processes(self):
        """プロセス強制終了テスト"""
        handler = GracefulShutdownHandler()
        mock_process = Mock()

        handler.register_process(mock_process)
        handler._kill_processes()

        mock_process.kill.assert_called_once()
        assert mock_process not in handler.active_processes


class TestTimeoutManager:
    """TimeoutManager クラスのテスト"""

    def test_run_with_timeout_success(self):
        """タイムアウト付き関数実行成功テスト"""

        def test_func(x, y):
            return x + y

        result = TimeoutManager.run_with_timeout(test_func, 1, args=(2, 3))

        assert result == 5

    def test_run_with_timeout_with_kwargs(self):
        """キーワード引数付き関数実行テスト"""

        def test_func(x, y=10):
            return x + y

        result = TimeoutManager.run_with_timeout(test_func, 1, args=(5,), kwargs={"y": 15})

        assert result == 20

    def test_run_with_timeout_timeout_error(self):
        """タイムアウトエラーテスト"""

        def slow_func():
            time.sleep(2)
            return "done"

        with pytest.raises(ExecutionError) as exc_info:
            TimeoutManager.run_with_timeout(slow_func, 0.1)

        error = exc_info.value
        assert "タイムアウトしました" in error.message

    def test_run_with_timeout_function_exception(self):
        """関数内例外テスト"""

        def error_func():
            raise ValueError("テストエラー")

        with pytest.raises(ValueError) as exc_info:
            TimeoutManager.run_with_timeout(error_func, 1)

        assert "テストエラー" in str(exc_info.value)

    def test_run_with_timeout_on_timeout_callback(self):
        """タイムアウト時コールバックテスト"""
        callback_called = []

        def on_timeout():
            callback_called.append(True)

        def slow_func():
            time.sleep(2)

        with pytest.raises(ExecutionError):
            TimeoutManager.run_with_timeout(slow_func, 0.1, on_timeout=on_timeout)

        assert callback_called == [True]

    @patch("subprocess.Popen")
    @patch("ci_helper.utils.graceful_shutdown.Progress")
    def test_run_process_with_timeout_success(self, mock_progress, mock_popen):
        """プロセス実行成功テスト"""
        mock_process = Mock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = TimeoutManager.run_process_with_timeout(["echo", "test"], 30, show_progress=False)

        assert result.returncode == 0
        assert result.stdout == "output"
        assert result.stderr == ""

    @patch("subprocess.Popen")
    def test_run_process_with_timeout_timeout_error(self, mock_popen):
        """プロセスタイムアウトエラーテスト"""
        mock_process = Mock()
        # 最初の communicate でタイムアウト、その後の terminate/kill 処理をモック
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired("cmd", 1),  # 最初のタイムアウト
            ("", ""),  # terminate 後の communicate
        ]
        mock_process.terminate.return_value = None
        mock_process.kill.return_value = None
        mock_popen.return_value = mock_process

        with pytest.raises(ExecutionError) as exc_info:
            TimeoutManager.run_process_with_timeout(["sleep", "10"], 0.1, show_progress=False)

        error = exc_info.value
        assert "タイムアウトしました" in error.message

    @patch("subprocess.Popen")
    @patch("ci_helper.utils.graceful_shutdown.Progress")
    def test_run_process_with_timeout_with_progress(self, mock_progress, mock_popen):
        """プログレス表示付きプロセス実行テスト"""
        mock_process = Mock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        mock_progress_instance = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance

        TimeoutManager.run_process_with_timeout(["echo", "test"], 30, show_progress=True)

        mock_progress_instance.add_task.assert_called_once()

    @patch("subprocess.Popen")
    @patch("ci_helper.utils.graceful_shutdown.console")
    def test_run_process_with_timeout_keyboard_interrupt(self, mock_console, mock_popen):
        """キーボード割り込みテスト"""
        mock_process = Mock()
        mock_process.communicate.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_process

        with pytest.raises(KeyboardInterrupt):
            TimeoutManager.run_process_with_timeout(["sleep", "10"], 30, show_progress=False)

        mock_console.print.assert_called_once()


class TestPartialResultHandler:
    """PartialResultHandler クラスのテスト"""

    def test_save_partial_results(self, temp_dir: Path):
        """部分的結果保存テスト"""
        results = {"test1": "result1", "test2": "result2"}
        output_file = str(temp_dir / "partial.json")
        error_message = "テストエラー"

        PartialResultHandler.save_partial_results(results, output_file, error_message)

        # ファイルが作成されることを確認
        assert Path(output_file).exists()

        # 内容を確認
        import json

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "partial"
        assert data["error"] == error_message
        assert data["results"] == results
        assert "timestamp" in data

    @patch("ci_helper.utils.graceful_shutdown.console")
    def test_save_partial_results_error(self, mock_console, temp_dir: Path):
        """部分的結果保存エラーテスト"""
        results = {"test": "result"}
        # 無効なパスを指定
        output_file = "/invalid/path/file.json"

        PartialResultHandler.save_partial_results(results, output_file, "error")

        # エラーメッセージが表示されることを確認
        mock_console.print.assert_called_once()

    def test_load_partial_results_success(self, temp_dir: Path):
        """部分的結果読み込み成功テスト"""
        # テストデータを作成
        test_data = {
            "status": "partial",
            "error": "テストエラー",
            "timestamp": time.time(),
            "results": {"test": "result"},
        }

        input_file = temp_dir / "partial.json"
        import json

        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = PartialResultHandler.load_partial_results(str(input_file))

        assert result is not None
        assert result["status"] == "partial"
        assert result["error"] == "テストエラー"
        assert result["results"] == {"test": "result"}

    def test_load_partial_results_file_not_exists(self, temp_dir: Path):
        """存在しないファイルの読み込みテスト"""
        result = PartialResultHandler.load_partial_results(str(temp_dir / "nonexistent.json"))

        assert result is None

    def test_load_partial_results_invalid_json(self, temp_dir: Path):
        """無効なJSONファイルの読み込みテスト"""
        input_file = temp_dir / "invalid.json"
        input_file.write_text("invalid json content")

        result = PartialResultHandler.load_partial_results(str(input_file))

        assert result is None

    def test_load_partial_results_not_partial_status(self, temp_dir: Path):
        """部分的結果でないファイルの読み込みテスト"""
        test_data = {"status": "complete", "results": {"test": "result"}}

        input_file = temp_dir / "complete.json"
        import json

        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = PartialResultHandler.load_partial_results(str(input_file))

        assert result is None


class TestGlobalShutdownHandler:
    """グローバルシャットダウンハンドラーのテスト"""

    def test_get_shutdown_handler(self):
        """グローバルハンドラー取得テスト"""
        handler1 = get_shutdown_handler()
        handler2 = get_shutdown_handler()

        # 同じインスタンスが返されることを確認
        assert handler1 is handler2
        assert isinstance(handler1, GracefulShutdownHandler)
