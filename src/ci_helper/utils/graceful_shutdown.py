"""
優雅なシャットダウンとタイムアウト処理

長時間実行されるプロセスの適切な終了処理を提供します。
"""

from __future__ import annotations

import signal
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core.exceptions import ExecutionError

console = Console()


class GracefulShutdownHandler:
    """優雅なシャットダウンハンドラー"""

    def __init__(self):
        self.shutdown_requested = False
        self.active_processes: list[subprocess.Popen] = []
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """シグナルハンドラーを設定"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """シグナル受信時の処理"""
        if not self.shutdown_requested:
            self.shutdown_requested = True
            console.print("\n[yellow]シャットダウンシグナルを受信しました。プロセスを終了しています...[/yellow]")
            self._terminate_processes()
        else:
            console.print("\n[red]強制終了します。[/red]")
            self._kill_processes()
            exit(1)

    def register_process(self, process: subprocess.Popen) -> None:
        """プロセスを登録"""
        self.active_processes.append(process)

    def unregister_process(self, process: subprocess.Popen) -> None:
        """プロセスの登録を解除"""
        if process in self.active_processes:
            self.active_processes.remove(process)

    def _terminate_processes(self) -> None:
        """プロセスを優雅に終了"""
        for process in self.active_processes[:]:
            try:
                process.terminate()
                # 5秒待機
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # タイムアウトした場合は強制終了
                process.kill()
            except Exception:
                pass
            finally:
                self.unregister_process(process)

    def _kill_processes(self) -> None:
        """プロセスを強制終了"""
        for process in self.active_processes[:]:
            try:
                process.kill()
            except Exception:
                pass
            finally:
                self.unregister_process(process)


class TimeoutManager:
    """タイムアウト管理"""

    @staticmethod
    def run_with_timeout(
        func: Callable,
        timeout_seconds: int,
        args: tuple = (),
        kwargs: dict | None = None,
        on_timeout: Callable | None = None,
    ) -> Any:
        """タイムアウト付きで関数を実行"""
        if kwargs is None:
            kwargs = {}

        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            # タイムアウト発生
            if on_timeout:
                on_timeout()
            raise ExecutionError.timeout_error(
                func.__name__ if hasattr(func, "__name__") else str(func), timeout_seconds
            )

        if exception[0]:
            raise exception[0]

        return result[0]

    @staticmethod
    def run_process_with_timeout(
        command: list[str],
        timeout_seconds: int,
        cwd: str | None = None,
        env: dict | None = None,
        show_progress: bool = True,
    ) -> subprocess.CompletedProcess:
        """タイムアウト付きでプロセスを実行"""

        shutdown_handler = GracefulShutdownHandler()

        try:
            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(f"実行中: {' '.join(command)}", total=None)

                    process = subprocess.Popen(
                        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=env
                    )

                    shutdown_handler.register_process(process)

                    try:
                        stdout, stderr = process.communicate(timeout=timeout_seconds)
                        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            stdout, stderr = process.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            stdout, stderr = process.communicate()

                        raise ExecutionError.timeout_error(" ".join(command), timeout_seconds)
                    finally:
                        shutdown_handler.unregister_process(process)
            else:
                # プログレス表示なしで実行
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=env
                )

                shutdown_handler.register_process(process)

                try:
                    stdout, stderr = process.communicate(timeout=timeout_seconds)
                    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()

                    raise ExecutionError.timeout_error(" ".join(command), timeout_seconds)
                finally:
                    shutdown_handler.unregister_process(process)

        except KeyboardInterrupt:
            console.print("\n[yellow]操作がキャンセルされました。[/yellow]")
            raise


class PartialResultHandler:
    """部分的な結果の処理"""

    @staticmethod
    def save_partial_results(results: dict, output_file: str, error_message: str) -> None:
        """部分的な結果を保存"""
        import json
        from pathlib import Path

        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            partial_data = {"status": "partial", "error": error_message, "timestamp": time.time(), "results": results}

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(partial_data, f, indent=2, ensure_ascii=False)

            console.print(f"[yellow]部分的な結果を保存しました: {output_path}[/yellow]")

        except Exception as e:
            console.print(f"[red]部分的な結果の保存に失敗しました: {e}[/red]")

    @staticmethod
    def load_partial_results(input_file: str) -> dict | None:
        """部分的な結果を読み込み"""
        import json
        from pathlib import Path

        try:
            input_path = Path(input_file)
            if not input_path.exists():
                return None

            with open(input_path, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("status") == "partial":
                return data

            return None

        except Exception:
            return None


# グローバルシャットダウンハンドラー
_global_shutdown_handler = GracefulShutdownHandler()


def get_shutdown_handler() -> GracefulShutdownHandler:
    """グローバルシャットダウンハンドラーを取得"""
    return _global_shutdown_handler
