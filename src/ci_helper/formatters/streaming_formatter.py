"""ストリーミングフォーマッター

大きなログファイルを効率的に処理するためのストリーミング対応フォーマッター。
パフォーマンス最適化機能と統合されています。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    from ..core.models import ExecutionResult

from ..utils.performance_optimizer import PerformanceOptimizer
from .base_formatter import BaseLogFormatter

TChunkResult = TypeVar("TChunkResult", covariant=True)
TLineResult = TypeVar("TLineResult", covariant=True)


class ChunkProcessor(Protocol[TChunkResult]):
    """ログチャンク処理関数のプロトコル"""

    def __call__(self, chunk: str, **processor_options: Any) -> TChunkResult | None:
        ...


class LineProcessor(Protocol[TLineResult]):
    """ログ行処理関数のプロトコル"""

    def __call__(self, lines: list[str], **processor_options: Any) -> TLineResult | None:
        ...


class StreamingFormatterMixin(BaseLogFormatter):
    """ストリーミング処理機能を提供するミックスイン

    既存のフォーマッターにストリーミング処理機能を追加します。
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """ストリーミングミックスインを初期化"""
        super().__init__(*args, **kwargs)
        self.performance_optimizer = PerformanceOptimizer()

    def format_with_optimization(self, execution_result: ExecutionResult, **options: Any) -> str:
        """最適化機能を使用してフォーマット実行

        Args:
            execution_result: CI実行結果
            **options: フォーマットオプション

        Returns:
            フォーマット結果

        """
        # ログファイルパスを取得
        log_path = self._get_log_file_path(execution_result)
        if not log_path:
            # ログファイルがない場合は通常のフォーマット
            return self.format(execution_result, **options)

        # キャッシュキーを生成
        cache_key = self.performance_optimizer.cache.get_cache_key(log_path, self.get_format_name(), options)

        # キャッシュから結果を取得
        cached_result = self.performance_optimizer.cache.get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

        # 重複処理チェック
        if self.performance_optimizer.duplicate_preventer.is_processing(log_path):
            # 他のプロセスが処理中の場合は通常のフォーマットにフォールバック
            return self.format(execution_result, **options)

        try:
            # 処理開始をマーク
            if not self.performance_optimizer.duplicate_preventer.start_processing(log_path):
                # 処理開始に失敗した場合は通常のフォーマット
                return self.format(execution_result, **options)

            # 最適化判定
            optimization_flags = self.performance_optimizer.should_use_optimization(log_path)

            if optimization_flags["use_streaming"]:
                # ストリーミング処理を使用
                result = self._format_with_streaming(execution_result, log_path, **options)
            else:
                # 通常のフォーマット処理
                result = self.format(execution_result, **options)

            # 結果をキャッシュに保存
            if optimization_flags["use_cache"]:
                self.performance_optimizer.cache.store_cached_result(
                    cache_key,
                    result,
                    metadata={
                        "format_type": self.get_format_name(),
                        "file_size": log_path.stat().st_size,
                        "options": options,
                    },
                )

            return result

        finally:
            # 処理終了をマーク
            self.performance_optimizer.duplicate_preventer.finish_processing(log_path)

    def _format_with_streaming(self, execution_result: ExecutionResult, log_path: Path, **options: Any) -> str:
        """ストリーミング処理でフォーマット実行

        Args:
            execution_result: CI実行結果
            log_path: ログファイルパス
            **options: フォーマットオプション

        Returns:
            フォーマット結果

        """
        # デフォルト実装では通常のフォーマットにフォールバック
        # 各フォーマッターでオーバーライドして最適化実装を提供
        return self.format(execution_result, **options)

    def _get_log_file_path(self, execution_result: ExecutionResult) -> Path | None:
        """ExecutionResultからログファイルパスを取得

        Args:
            execution_result: CI実行結果

        Returns:
            ログファイルパス（存在しない場合はNone）

        """
        if hasattr(execution_result, "log_path") and execution_result.log_path:
            log_path = Path(execution_result.log_path)
            if log_path.exists():
                return log_path
        return None

    def get_streaming_info(self, execution_result: ExecutionResult) -> dict[str, Any]:
        """ストリーミング処理情報を取得

        Args:
            execution_result: CI実行結果

        Returns:
            ストリーミング処理情報

        """
        log_path = self._get_log_file_path(execution_result)
        if not log_path:
            return {
                "available": False,
                "reason": "ログファイルが見つかりません",
            }

        file_info = self.performance_optimizer.streamer.get_file_info(log_path)
        optimization_flags = self.performance_optimizer.should_use_optimization(log_path)

        return {
            "available": True,
            "file_info": file_info,
            "optimization_flags": optimization_flags,
            "performance_stats": self.performance_optimizer.get_optimization_stats(),
        }


class StreamingAwareFormatter(StreamingFormatterMixin, BaseLogFormatter):
    """ストリーミング対応の基底フォーマッター

    ストリーミング処理機能を統合した基底フォーマッタークラス。
    """

    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """フォーマット実行（基底実装）

        Args:
            execution_result: CI実行結果
            **options: フォーマットオプション

        Returns:
            フォーマット結果

        """
        # 基底実装では簡単なテキスト出力
        status = "成功" if execution_result.success else "失敗"
        return f"CI実行結果: {status}\n実行時間: {execution_result.total_duration:.2f}秒"

    def get_format_name(self) -> str:
        """フォーマット名を取得"""
        return "streaming_base"


class ChunkedLogProcessor:
    """チャンク単位ログ処理クラス

    大きなログファイルをチャンク単位で処理するためのユーティリティ。
    """

    def __init__(self, performance_optimizer: PerformanceOptimizer | None = None):
        """チャンク処理器を初期化

        Args:
            performance_optimizer: パフォーマンス最適化インスタンス

        """
        self.performance_optimizer = performance_optimizer or PerformanceOptimizer()

    def process_log_chunks(
        self,
        log_path: Path,
        processor_func: ChunkProcessor[TChunkResult],
        **processor_options: Any,
    ) -> Iterator[TChunkResult]:
        """ログをチャンク単位で処理

        Args:
            log_path: ログファイルパス
            processor_func: チャンク処理関数
            **processor_options: 処理関数のオプション

        Yields:
            処理されたチャンク結果

        """
        streamer = self.performance_optimizer.streamer

        for chunk in streamer.stream_file_chunks(log_path):
            try:
                processed_chunk = processor_func(chunk, **processor_options)
                if processed_chunk is not None:
                    yield processed_chunk
            except Exception:
                # チャンク処理エラーは無視して続行
                continue

    def process_log_lines(
        self,
        log_path: Path,
        line_processor_func: LineProcessor[TLineResult],
        batch_size: int = 1000,
        **processor_options: Any,
    ) -> Iterator[TLineResult]:
        """ログを行単位でバッチ処理

        Args:
            log_path: ログファイルパス
            line_processor_func: 行処理関数
            batch_size: バッチサイズ
            **processor_options: 処理関数のオプション

        Yields:
            処理されたバッチ結果

        """
        streamer = self.performance_optimizer.streamer

        batch_lines: list[str] = []
        for line in streamer.stream_lines(log_path):
            batch_lines.append(line)

            if len(batch_lines) >= batch_size:
                try:
                    processed_batch = line_processor_func(batch_lines, **processor_options)
                    if processed_batch is not None:
                        yield processed_batch
                except Exception:
                    # バッチ処理エラーは無視して続行
                    pass
                finally:
                    batch_lines = []

        # 残りのバッチを処理
        if batch_lines:
            try:
                processed_batch = line_processor_func(batch_lines, **processor_options)
                if processed_batch is not None:
                    yield processed_batch
            except Exception:
                pass

    def extract_failures_streaming(self, log_path: Path) -> Iterator[dict[str, Any]]:
        """ストリーミングで失敗情報を抽出

        Args:
            log_path: ログファイルパス

        Yields:
            抽出された失敗情報

        """

        def extract_failures_from_lines(lines: list[str], **_: Any) -> list[dict[str, Any]]:
            """行のバッチから失敗情報を抽出"""
            failures: list[dict[str, Any]] = []

            for i, line in enumerate(lines):
                # 簡単な失敗パターンマッチング
                if any(keyword in line.lower() for keyword in ["error", "failed", "failure"]):
                    failure_info = {
                        "line_number": i + 1,
                        "message": line.strip(),
                        "type": "error",
                        "context_before": lines[max(0, i - 2) : i] if i > 0 else [],
                        "context_after": lines[i + 1 : min(len(lines), i + 3)] if i < len(lines) - 1 else [],
                    }
                    failures.append(failure_info)

            return failures

        # 行単位でバッチ処理して失敗情報を抽出
        for batch_failures in self.process_log_lines(log_path, extract_failures_from_lines, batch_size=500):
            if batch_failures:
                yield from batch_failures


class ProgressTrackingFormatter:
    """進行状況追跡機能付きフォーマッター

    大きなファイルの処理進行状況を追跡・表示します。
    """

    def __init__(self, console: Any | None = None):
        """進行状況追跡フォーマッターを初期化

        Args:
            console: Rich Console インスタンス

        """
        self.console = console
        if console is None:
            from rich.console import Console

            self.console = Console()

    def format_with_progress(
        self,
        formatter: BaseLogFormatter,
        execution_result: ExecutionResult,
        **options: Any,
    ) -> str:
        """進行状況表示付きでフォーマット実行

        Args:
            formatter: 使用するフォーマッター
            execution_result: CI実行結果
            **options: フォーマットオプション

        Returns:
            フォーマット結果

        """
        from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

        # ログファイル情報を取得
        log_path: Path | None = None
        file_size: int | None = None
        if hasattr(execution_result, "log_path") and execution_result.log_path:
            log_path = Path(execution_result.log_path)

        # 進行状況表示の判定
        show_progress = False
        if log_path and log_path.exists():
            file_size = log_path.stat().st_size
            show_progress = file_size > 5 * 1024 * 1024  # 5MB以上で進行状況表示

        if not show_progress:
            # 小さなファイルは通常処理
            return formatter.format(execution_result, **options)

        # 進行状況表示付きで処理
        assert file_size is not None
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            # ファイルサイズ情報を表示
            file_size_mb = file_size / (1024 * 1024)
            task_desc = f"ログを整形中... ({file_size_mb:.1f}MB)"
            task = progress.add_task(task_desc, total=None)

            try:
                # フォーマット実行
                result = formatter.format(execution_result, **options)

                # 完了メッセージ
                progress.update(task, description="整形完了")

                return result

            except Exception as e:
                progress.update(task, description=f"エラー: {e}")
                raise

    def estimate_processing_time(self, file_size: int, format_type: str) -> float:
        """処理時間を推定

        Args:
            file_size: ファイルサイズ（バイト）
            format_type: フォーマット種別

        Returns:
            推定処理時間（秒）

        """
        # 簡易的な処理時間推定
        # 実際の使用状況に基づいて調整が必要

        base_time_per_mb = {
            "ai": 2.0,  # AI形式は複雑な処理で時間がかかる
            "human": 1.0,  # 人間可読形式は中程度
            "json": 0.5,  # JSON形式は比較的高速
            "markdown": 1.5,  # Markdown形式は中程度
        }

        time_per_mb = base_time_per_mb.get(format_type, 1.0)
        file_size_mb = file_size / (1024 * 1024)

        return file_size_mb * time_per_mb
