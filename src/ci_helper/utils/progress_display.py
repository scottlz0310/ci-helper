"""進行状況表示ユーティリティ

ログ整形処理の進行状況表示機能を提供します。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm


class ProgressDisplayManager:
    """進行状況表示マネージャー

    ログ整形処理の進行状況を管理し、適切なメッセージとインジケータを表示します。
    """

    def __init__(self, console: Console | None = None):
        """進行状況表示マネージャーを初期化

        Args:
            console: Rich Console インスタンス

        """
        self.console = console or Console()
        self._large_file_threshold = 10 * 1024 * 1024  # 10MB

    def show_processing_start_message(
        self,
        format_type: str,
        input_file: str | None = None,
        output_file: str | None = None,
        **options: Any,
    ) -> None:
        """処理開始メッセージを表示

        Args:
            format_type: フォーマット種別
            input_file: 入力ファイルパス
            output_file: 出力ファイルパス
            **options: 追加オプション

        """
        # フォーマット種別の日本語名
        format_names = {
            "ai": "AI分析用",
            "human": "人間可読",
            "json": "JSON",
            "markdown": "Markdown",
        }
        format_display = format_names.get(format_type, format_type)

        # 処理開始メッセージ
        self.console.print()
        self.console.print("[bold green]🚀 ログ整形処理を開始します[/bold green]")
        self.console.print(f"[cyan]形式: {format_display}フォーマット[/cyan]")

        # 入力情報
        if input_file:
            self.console.print(f"[dim]入力: {input_file}[/dim]")
            # ファイルサイズ情報
            try:
                file_size = Path(input_file).stat().st_size
                size_mb = file_size / (1024 * 1024)
                if size_mb >= 1:
                    self.console.print(f"[dim]サイズ: {size_mb:.1f}MB[/dim]")
                else:
                    size_kb = file_size / 1024
                    self.console.print(f"[dim]サイズ: {size_kb:.1f}KB[/dim]")
            except (OSError, FileNotFoundError):
                pass
        else:
            self.console.print("[dim]入力: 最新ログ[/dim]")

        # 出力情報
        if output_file:
            self.console.print(f"[dim]出力: {output_file}[/dim]")
        else:
            self.console.print("[dim]出力: コンソール[/dim]")

        # オプション情報
        if options:
            option_info: list[str] = []
            if options.get("filter_errors"):
                option_info.append("エラーフィルタ有効")
            if options.get("verbose_level"):
                option_info.append(f"詳細レベル: {options['verbose_level']}")
            if option_info:
                self.console.print(f"[dim]オプション: {', '.join(option_info)}[/dim]")

        self.console.print()

    def is_large_file(self, file_path: str | None) -> bool:
        """ファイルが大きいかどうかを判定

        Args:
            file_path: ファイルパス

        Returns:
            大きなファイルの場合True

        """
        if not file_path:
            return False

        try:
            file_size = Path(file_path).stat().st_size
            return file_size > self._large_file_threshold
        except (OSError, FileNotFoundError):
            return False

    def create_progress_context(
        self,
        task_description: str = "ログを整形中...",
        show_elapsed: bool = True,
        show_bar: bool = False,
    ) -> Progress:
        """進行状況コンテキストを作成

        Args:
            task_description: タスクの説明
            show_elapsed: 経過時間を表示するか
            show_bar: プログレスバーを表示するか

        Returns:
            Progress インスタンス

        """
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
        ]

        if show_bar:
            columns.append(BarColumn())

        if show_elapsed:
            columns.append(TimeElapsedColumn())

        return Progress(*columns, console=self.console)

    def execute_with_progress(
        self,
        task_func: Callable[[], Any],
        task_description: str = "ログを整形中...",
        completion_description: str = "整形完了",
        input_file: str | None = None,
        show_detailed_progress: bool | None = None,
    ) -> Any:
        """進行状況表示付きでタスクを実行

        Args:
            task_func: 実行するタスク関数
            task_description: タスクの説明
            completion_description: 完了時の説明
            input_file: 入力ファイルパス（大きなファイル判定用）
            show_detailed_progress: 詳細な進行状況を表示するか（Noneの場合は自動判定）

        Returns:
            タスク関数の実行結果

        """
        # 詳細な進行状況表示の判定
        if show_detailed_progress is None:
            show_detailed_progress = self.is_large_file(input_file)

        if show_detailed_progress:
            # 大きなファイルの場合は詳細な進行状況を表示
            return self._execute_with_detailed_progress(task_func, task_description, completion_description)
        # 通常のファイルの場合はシンプルな進行状況を表示
        return self._execute_with_simple_progress(task_func, task_description, completion_description)

    def _execute_with_detailed_progress(
        self,
        task_func: Callable[[], Any],
        task_description: str,
        completion_description: str,
    ) -> Any:
        """詳細な進行状況表示付きでタスクを実行"""
        with self.create_progress_context(task_description, show_elapsed=True, show_bar=False) as progress:
            task = progress.add_task(task_description, total=None)

            # 処理段階を表示
            stages = [
                "ログファイルを読み込み中...",
                "失敗情報を抽出中...",
                "コンテンツを整形中...",
                "出力を準備中...",
            ]

            start_time = time.time()

            try:
                # 各段階を表示しながら実行
                for i, stage in enumerate(stages):
                    progress.update(task, description=stage)
                    time.sleep(0.1)  # 視覚的な効果のための短い待機

                    # 最後の段階で実際のタスクを実行
                    if i == len(stages) - 1:
                        result = task_func()

                # 完了メッセージ
                elapsed_time = time.time() - start_time
                progress.update(
                    task,
                    description=f"{completion_description} ({elapsed_time:.1f}秒)",
                )
                time.sleep(0.5)  # 完了メッセージを表示する時間

                return result

            except Exception as e:
                # エラー時の表示
                progress.update(task, description=f"エラーが発生しました: {e!s}")
                time.sleep(1.0)  # エラーメッセージを表示する時間
                raise

    def _execute_with_simple_progress(
        self,
        task_func: Callable[[], Any],
        task_description: str,
        completion_description: str,
    ) -> Any:
        """シンプルな進行状況表示付きでタスクを実行"""
        with self.create_progress_context(task_description, show_elapsed=False, show_bar=False) as progress:
            task = progress.add_task(task_description, total=None)

            try:
                # タスクを実行
                result = task_func()

                # 完了メッセージ
                progress.update(task, description=completion_description)
                time.sleep(0.3)  # 完了メッセージを表示する時間

                return result

            except Exception as e:
                # エラー時の表示
                progress.update(task, description=f"エラー: {e!s}")
                time.sleep(1.0)  # エラーメッセージを表示する時間
                raise

    def show_success_message(
        self,
        format_type: str,
        output_file: str | None = None,
        processing_time: float | None = None,
        **details: Any,
    ) -> None:
        """処理完了時の成功メッセージを表示

        Args:
            format_type: フォーマット種別
            output_file: 出力ファイルパス
            processing_time: 処理時間（秒）
            **details: 追加の詳細情報

        """
        # フォーマット種別の日本語名
        format_names = {
            "ai": "AI分析用",
            "human": "人間可読",
            "json": "JSON",
            "markdown": "Markdown",
        }
        format_display = format_names.get(format_type, format_type)

        # 成功メッセージ
        self.console.print()
        self.console.print("[bold green]✅ ログ整形が完了しました[/bold green]")

        # 詳細情報をパネルで表示
        info_lines = [f"[cyan]形式:[/cyan] {format_display}フォーマット"]

        if output_file:
            info_lines.append(f"[cyan]保存先:[/cyan] {output_file}")

            # ファイルサイズ情報
            try:
                file_size = Path(output_file).stat().st_size
                if file_size >= 1024 * 1024:
                    size_mb = file_size / (1024 * 1024)
                    info_lines.append(f"[cyan]サイズ:[/cyan] {size_mb:.1f}MB")
                elif file_size >= 1024:
                    size_kb = file_size / 1024
                    info_lines.append(f"[cyan]サイズ:[/cyan] {size_kb:.1f}KB")
                else:
                    info_lines.append(f"[cyan]サイズ:[/cyan] {file_size}バイト")
            except (OSError, FileNotFoundError):
                pass
        else:
            info_lines.append("[cyan]出力:[/cyan] コンソール")

        if processing_time is not None:
            info_lines.append(f"[cyan]処理時間:[/cyan] {processing_time:.2f}秒")

        # 追加の詳細情報
        if details:
            for key, value in details.items():
                if key == "failure_count":
                    info_lines.append(f"[cyan]失敗数:[/cyan] {value}")
                elif key == "total_lines":
                    info_lines.append(f"[cyan]総行数:[/cyan] {value}")
                elif key == "filtered_lines":
                    info_lines.append(f"[cyan]フィルタ後行数:[/cyan] {value}")

        # パネルで表示
        panel = Panel(
            "\n".join(info_lines),
            title="[bold green]処理結果[/bold green]",
            border_style="green",
        )
        self.console.print(panel)
        self.console.print()

    def show_error_message(
        self,
        error: Exception,
        context: str | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """エラー発生時の詳細エラーメッセージを表示

        Args:
            error: 発生したエラー
            context: エラーのコンテキスト
            suggestions: 修正提案のリスト

        """
        self.console.print()
        self.console.print("[bold red]❌ エラーが発生しました[/bold red]")

        # エラー詳細をパネルで表示
        error_lines: list[str] = []

        # エラータイプと基本メッセージ
        error_type = type(error).__name__
        error_lines.append(f"[red]エラータイプ:[/red] {error_type}")
        error_lines.append(f"[red]メッセージ:[/red] {error!s}")

        # コンテキスト情報
        if context:
            error_lines.append(f"[red]コンテキスト:[/red] {context}")

        # エラーパネル
        error_panel = Panel(
            "\n".join(error_lines),
            title="[bold red]エラー詳細[/bold red]",
            border_style="red",
        )
        self.console.print(error_panel)

        # 修正提案
        if suggestions:
            self.console.print("\n[bold yellow]💡 修正提案:[/bold yellow]")
            for i, suggestion in enumerate(suggestions, 1):
                self.console.print(f"  {i}. {suggestion}")

        self.console.print()

    def show_menu_return_option(self, return_to_menu_func: Callable[[], Any] | None = None) -> bool:
        """メニューに戻るオプションを提供

        Args:
            return_to_menu_func: メニューに戻る関数

        Returns:
            メニューに戻る場合True

        """
        self.console.print("[dim]処理が完了しました。[/dim]")

        if return_to_menu_func is None:
            # 単純な確認のみ
            return Confirm.ask(
                "[bold cyan]メニューに戻りますか？[/bold cyan]",
                default=True,
                console=self.console,
            )
        # メニューに戻るかの確認と実行
        if Confirm.ask(
            "[bold cyan]メニューに戻りますか？[/bold cyan]",
            default=True,
            console=self.console,
        ):
            try:
                return_to_menu_func()
                return True
            except Exception as e:
                self.console.print(f"[red]メニューに戻る際にエラーが発生しました: {e}[/red]")
                return False
        else:
            return False

    def get_file_processing_suggestions(self, error: Exception, file_path: str | None = None) -> list[str]:
        """ファイル処理エラーに対する修正提案を生成

        Args:
            error: 発生したエラー
            file_path: 関連するファイルパス

        Returns:
            修正提案のリスト

        """
        suggestions: list[str] = []
        error_type = type(error).__name__

        if error_type == "FileNotFoundError":
            suggestions.extend(
                [
                    "ファイルパスが正しいか確認してください",
                    "ファイルが存在するか確認してください",
                    "相対パスではなく絶対パスを使用してみてください",
                ],
            )
            if file_path:
                suggestions.append(f"指定されたパス: {file_path}")

        elif error_type == "PermissionError":
            suggestions.extend(
                [
                    "ファイルの読み取り権限を確認してください",
                    "ファイルが他のプロセスで使用されていないか確認してください",
                    "管理者権限で実行してみてください",
                ],
            )

        elif error_type == "UnicodeDecodeError":
            suggestions.extend(
                [
                    "ファイルの文字エンコーディングを確認してください",
                    "UTF-8以外のエンコーディングの場合は変換してください",
                    "バイナリファイルではないか確認してください",
                ],
            )

        elif error_type == "MemoryError":
            suggestions.extend(
                [
                    "ログファイルが大きすぎる可能性があります",
                    "不要なプロセスを終了してメモリを確保してください",
                    "ファイルを分割して処理してみてください",
                ],
            )

        elif "JSON" in str(error) or "json" in str(error):
            suggestions.extend(
                [
                    "JSON形式が正しいか確認してください",
                    "ファイルが破損していないか確認してください",
                    "別のフォーマット（ai, human）を試してみてください",
                ],
            )

        else:
            # 一般的な提案
            suggestions.extend(
                [
                    "ログファイルが正しい形式か確認してください",
                    "ディスク容量が十分にあるか確認してください",
                    "別のフォーマットを試してみてください",
                    "ci-run doctor で環境をチェックしてください",
                ],
            )

        return suggestions

    def set_large_file_threshold(self, threshold_mb: float) -> None:
        """大きなファイルの閾値を設定

        Args:
            threshold_mb: 閾値（MB単位）

        """
        self._large_file_threshold = int(threshold_mb * 1024 * 1024)


# グローバルインスタンス
_global_progress_manager: ProgressDisplayManager | None = None


def get_progress_manager(console: Console | None = None) -> ProgressDisplayManager:
    """グローバル進行状況表示マネージャーを取得

    Args:
        console: Rich Console インスタンス

    Returns:
        進行状況表示マネージャーインスタンス

    """
    global _global_progress_manager
    if _global_progress_manager is None or (console and _global_progress_manager.console != console):
        _global_progress_manager = ProgressDisplayManager(console)
    return _global_progress_manager


def reset_progress_manager() -> None:
    """グローバル進行状況表示マネージャーをリセット

    主にテスト用途で使用します。
    """
    global _global_progress_manager
    _global_progress_manager = None
