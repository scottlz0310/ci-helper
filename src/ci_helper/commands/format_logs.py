"""
ログ整形コマンド

CI実行ログを様々な形式で整形するコマンドを提供します。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console

from ..core.exceptions import ExecutionError, FileOperationError, LogFormattingError, UserInputError
from ..core.log_extractor import LogExtractor
from ..core.log_manager import LogManager
from ..core.models import ExecutionResult
from ..formatters import get_formatter_manager
from ..utils.config import Config
from ..utils.file_save_utils import FileSaveManager
from ..utils.progress_display import get_progress_manager

if TYPE_CHECKING:
    pass


@click.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["ai", "human", "json"], case_sensitive=False),
    default="ai",
    help="出力フォーマット（デフォルト: ai）",
)
@click.option(
    "--input",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    help="入力ログファイル（省略時は最新ログを使用）",
)
@click.option(
    "--output",
    "output_file",
    type=click.Path(path_type=Path),
    help="出力ファイル（省略時は標準出力）",
)
@click.option(
    "--filter-errors",
    is_flag=True,
    help="エラーのみをフィルタリング",
)
@click.option(
    "--verbose-level",
    type=click.Choice(["minimal", "normal", "detailed"], case_sensitive=False),
    default="normal",
    help="詳細レベル（デフォルト: normal）",
)
@click.option(
    "--no-confirm",
    is_flag=True,
    help="ファイル上書き確認をスキップ",
)
@click.option(
    "--disable-optimization",
    is_flag=True,
    help="パフォーマンス最適化機能を無効にする",
)
@click.option(
    "--max-memory",
    type=int,
    default=100,
    help="最大メモリ使用量（MB、デフォルト: 100）",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="フォーマット結果キャッシュをクリア",
)
@click.pass_context
def format_logs(
    ctx: click.Context,
    output_format: str,
    input_file: Path | None,
    output_file: Path | None,
    filter_errors: bool,
    verbose_level: str,
    no_confirm: bool,
    disable_optimization: bool,
    max_memory: int,
    clear_cache: bool,
) -> None:
    """ログを指定された形式で整形

    \b
    使用例:
      ci-run format-logs                           # 最新ログをAI形式で標準出力
      ci-run format-logs --format human           # 人間可読形式で出力
      ci-run format-logs --format json --output result.json  # JSON形式でファイル保存
      ci-run format-logs --input act_20240101.log --format ai  # 特定ログをAI形式で出力
    """
    console = Console()
    progress_manager = get_progress_manager(console)

    try:
        # 設定を読み込み
        config = Config()

        # パフォーマンス最適化の処理
        if clear_cache:
            from ..utils.performance_optimizer import PerformanceOptimizer

            optimizer = PerformanceOptimizer(max_memory_mb=max_memory)
            cleared_entries = optimizer.cache.clear_cache()
            console.print(f"[green]キャッシュをクリアしました: {cleared_entries}件[/green]")
            if not input_file:  # キャッシュクリアのみの場合は終了
                return

        # ログマネージャーを初期化
        log_manager = LogManager(config)

        # 処理開始メッセージを表示
        input_file_str = str(input_file) if input_file else None
        output_file_str = str(output_file) if output_file else None

        progress_manager.show_processing_start_message(
            format_type=output_format,
            input_file=input_file_str,
            output_file=output_file_str,
            filter_errors=filter_errors,
            verbose_level=verbose_level,
        )

        # 入力ログを取得
        execution_result = _get_execution_result(log_manager, input_file, console)
        if execution_result is None:
            # ログが見つからない場合は終了コード1
            ctx.exit(1)

        # フォーマッターマネージャーを取得
        formatter_manager = get_formatter_manager()

        # フォーマットオプションを構築
        format_options = {
            "filter_errors": filter_errors,
            "verbose_level": verbose_level,
            "use_optimization": not disable_optimization,
            "max_memory_mb": max_memory,
        }

        # 処理時間を測定
        start_time = time.time()

        # 進行状況表示付きでフォーマット実行
        def format_task():
            return formatter_manager.format_log(execution_result, output_format, **format_options)

        # 標準出力の場合は進行状況を表示しない
        if output_file is None:
            # 標準出力への出力（シンプルな進行状況表示）
            formatted_content = progress_manager.execute_with_progress(
                task_func=format_task,
                task_description="ログを整形中...",
                completion_description="整形完了",
                input_file=input_file_str,
                show_detailed_progress=False,  # 標準出力時はシンプル
            )
            # 標準出力に直接出力（Richフォーマットなし）
            click.echo(formatted_content)
        else:
            # ファイル出力の場合は詳細な進行状況を表示
            formatted_content = progress_manager.execute_with_progress(
                task_func=format_task,
                task_description="ログを整形中...",
                completion_description="整形完了",
                input_file=input_file_str,
                show_detailed_progress=None,  # 自動判定
            )

            # セキュリティ機能を有効にしてファイル保存マネージャーを使用
            file_manager = FileSaveManager(console, enable_security=True)
            success, saved_path = file_manager.save_formatted_log(
                content=formatted_content,
                output_file=str(output_file),
                format_type=output_format,
                default_dir=file_manager.get_default_output_directory(),
                confirm_overwrite=not no_confirm,
            )

            if not success:
                error_suggestions = [
                    "出力ディレクトリの書き込み権限を確認してください",
                    "ディスク容量が十分にあるか確認してください",
                    "別の出力パスを試してみてください",
                ]
                progress_manager.show_error_message(
                    error=Exception("ログの保存に失敗しました"),
                    context="ファイル保存処理",
                    suggestions=error_suggestions,
                )
                # ファイル保存失敗時は終了コード1
                ctx.exit(1)

            # 処理時間を計算
            processing_time = time.time() - start_time

            # 成功メッセージを表示
            progress_manager.show_success_message(
                format_type=output_format,
                output_file=saved_path,
                processing_time=processing_time,
            )

        # 正常終了時は終了コード0（デフォルト）

    except ExecutionError as e:
        suggestions = [e.suggestion] if e.suggestion else []
        progress_manager.show_error_message(
            error=e,
            context="CI-Helper実行エラー",
            suggestions=suggestions,
        )
        # 実行エラー時は終了コード1
        ctx.exit(1)

    except (LogFormattingError, FileOperationError, UserInputError) as e:
        # ログ整形関連の専用エラーハンドリング
        from ..formatters.error_handler import LogFormattingErrorHandler

        error_handler = LogFormattingErrorHandler(console)

        error_context = error_handler.create_error_context(
            format_type=output_format,
            input_file=input_file,
            output_file=output_file,
        )

        error_handler.handle_formatting_error(e, error_context, verbose=ctx.obj.get("verbose", False))
        ctx.exit(1)

    except Exception as e:
        # 予期しないエラーの処理
        from ..formatters.error_handler import LogFormattingErrorHandler

        error_handler = LogFormattingErrorHandler(console)

        error_context = error_handler.create_error_context(
            format_type=output_format,
            input_file=input_file,
            output_file=output_file,
        )

        error_handler.handle_formatting_error(e, error_context, verbose=ctx.obj.get("verbose", False))
        ctx.exit(1)


def _sanitize_log_content(content: str) -> str:
    """ログ内容をサニタイズしてRichマークアップエラーを防ぐ

    Args:
        content: 元のログ内容

    Returns:
        サニタイズされたログ内容
    """
    # Richマークアップと競合する文字をエスケープ
    # ただし、ログの可読性を保つため最小限の変更に留める

    # [と]で囲まれた部分でRichマークアップと誤認される可能性があるものを特定
    # ただし、ログの構造を壊さないよう慎重に処理

    # 一般的なログパターンは保持し、問題のある部分のみエスケープ
    # 例: [CI/test] は保持、[/path/to/file] のような部分をエスケープ

    # 簡単な解決策として、Richマークアップを無効化するためにエスケープ
    content = content.replace("[/", r"\[/")

    return content


def _get_execution_result(log_manager: LogManager, input_file: Path | None, console: Console) -> ExecutionResult | None:
    """実行結果を取得

    Args:
        log_manager: ログマネージャー
        input_file: 入力ファイルパス（Noneの場合は最新ログ）
        console: Rich Console

    Returns:
        実行結果（取得できない場合はNone）
    """
    try:
        if input_file:
            # 指定されたファイルから読み込み
            console.print(f"[dim]ログファイルを読み込み中: {input_file}[/dim]")
            log_content = input_file.read_text(encoding="utf-8")
        else:
            # 最新ログを取得
            console.print("[dim]最新ログを取得中...[/dim]")
            logs = log_manager.list_logs(limit=1)
            if not logs:
                console.print("[red]エラー: 利用可能なログファイルが見つかりません[/red]")
                console.print("[yellow]ci-run test を実行してログを生成してください[/yellow]")
                return None

            latest_log = logs[0]
            log_content = log_manager.get_log_content(latest_log["log_file"])

        # ログ内容をサニタイズ（Richマークアップエラーを防ぐ）
        log_content = _sanitize_log_content(log_content)

        # ログ内容から実行結果を構築
        extractor = LogExtractor()
        failures = extractor.extract_failures(log_content)

        # ダミーのJobResultとWorkflowResultを作成
        from ..core.models import JobResult, WorkflowResult

        job_result = JobResult(
            name="extracted_job",
            success=len(failures) == 0,
            failures=failures,
            duration=0.0,
        )

        workflow_result = WorkflowResult(
            name="extracted_workflow",
            success=len(failures) == 0,
            jobs=[job_result],
            duration=0.0,
        )

        # ExecutionResultを構築
        execution_result = ExecutionResult(
            success=len(failures) == 0,
            workflows=[workflow_result],
            total_duration=0.0,  # ログから抽出できない場合のデフォルト値
        )

        return execution_result

    except FileNotFoundError:
        raise FileOperationError.file_not_found(str(input_file), "読み込み")

    except PermissionError:
        raise FileOperationError.permission_denied(str(input_file), "読み込み")

    except OSError as e:
        if "No space left on device" in str(e):
            raise FileOperationError.disk_space_insufficient(str(input_file), 0, 0)
        else:
            raise FileOperationError.file_corrupted(str(input_file))

    except Exception as e:
        raise LogFormattingError(
            f"ログファイルの読み込み中にエラーが発生しました: {e}",
            "ログファイルの形式を確認するか、別のファイルを試してください",
        )


# メニューシステム用のハンドラー関数
def format_logs_handler(
    format_type: str,
    input_file: str | None = None,
    output_file: str | None = None,
    return_to_menu_func: Any | None = None,
    **options: Any,
) -> bool:
    """メニューシステム用のログ整形ハンドラー

    Args:
        format_type: フォーマット種別
        input_file: 入力ファイルパス
        output_file: 出力ファイルパス
        return_to_menu_func: メニューに戻る関数
        **options: 追加オプション

    Returns:
        成功した場合True
    """
    console = Console()
    progress_manager = get_progress_manager(console)

    try:
        # 処理開始メッセージを表示
        progress_manager.show_processing_start_message(
            format_type=format_type,
            input_file=input_file,
            output_file=output_file,
            **options,
        )

        # 設定を読み込み
        config = Config()

        # ログマネージャーを初期化
        log_manager = LogManager(config)

        # 入力ログを取得
        input_path = Path(input_file) if input_file else None
        execution_result = _get_execution_result(log_manager, input_path, console)
        if execution_result is None:
            return False

        # フォーマッターマネージャーを取得
        formatter_manager = get_formatter_manager()

        # 処理時間を測定
        start_time = time.time()

        # 進行状況表示付きでフォーマット実行
        def format_task():
            return formatter_manager.format_log(execution_result, format_type, **options)

        formatted_content = progress_manager.execute_with_progress(
            task_func=format_task,
            task_description="ログを整形中...",
            completion_description="整形完了",
            input_file=input_file,
        )

        # 出力処理
        success = False
        saved_path = None

        if output_file is None:
            # 標準出力への出力
            console.print(formatted_content)
            success = True
        else:
            # セキュリティ機能を有効にしてファイル保存マネージャーを使用
            file_manager = FileSaveManager(console, enable_security=True)
            success, saved_path = file_manager.save_formatted_log(
                content=formatted_content,
                output_file=output_file,
                format_type=format_type,
                default_dir=file_manager.get_default_output_directory(),
            )

        if success:
            # 処理時間を計算
            processing_time = time.time() - start_time

            # 成功メッセージを表示
            progress_manager.show_success_message(
                format_type=format_type,
                output_file=saved_path,
                processing_time=processing_time,
            )

            # メニューに戻るオプションを提供
            progress_manager.show_menu_return_option(return_to_menu_func)

        return success

    except Exception as e:
        # Rich markupエラーの場合は特別な処理
        from rich.errors import MarkupError

        if isinstance(e, MarkupError):
            console.print("[red]エラー: ログ内容にRichマークアップと競合する文字が含まれています[/red]")
            console.print("[yellow]ヒント: --disable-optimization オプションを試してください[/yellow]")
        else:
            # エラーメッセージと修正提案を表示
            try:
                suggestions = progress_manager.get_file_processing_suggestions(e, input_file)
                progress_manager.show_error_message(
                    error=e,
                    context="メニューからのログ整形処理",
                    suggestions=suggestions,
                )
            except Exception:
                # エラー表示でもエラーが発生した場合は簡単なメッセージを表示
                console.print(f"[red]エラーが発生しました: {str(e)[:100]}...[/red]")

        # メニューに戻るオプションを提供（エラー時も）
        try:
            progress_manager.show_menu_return_option(return_to_menu_func)
        except Exception:
            console.print("[dim]Enterキーを押してメニューに戻ります...[/dim]")
            input()

        return False


# カスタム整形用のハンドラー関数
def format_logs_custom_handler(
    format_type: str,
    detail_level: str = "normal",
    filter_errors: bool = False,
    input_file: str | None = None,
    output_file: str | None = None,
    return_to_menu_func: Any | None = None,
    **advanced_options: Any,
) -> bool:
    """カスタム整形用のハンドラー

    Args:
        format_type: フォーマット種別
        detail_level: 詳細レベル
        filter_errors: エラーフィルタリング
        input_file: 入力ファイルパス
        output_file: 出力ファイルパス
        return_to_menu_func: メニューに戻る関数
        **advanced_options: 高度なオプション

    Returns:
        成功した場合True
    """
    # 基本オプションと高度なオプションを統合
    all_options = {
        "detail_level": detail_level,
        "filter_errors": filter_errors,
        **advanced_options,
    }

    return format_logs_handler(
        format_type=format_type,
        input_file=input_file,
        output_file=output_file,
        return_to_menu_func=return_to_menu_func,
        **all_options,
    )
