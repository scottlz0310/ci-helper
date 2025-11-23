"""パフォーマンス最適化モジュール

大量ログファイルの処理速度改善、パターンマッチングアルゴリズムの最適化、
メモリ使用量の削減を提供します。
"""

from __future__ import annotations

import asyncio
import gc
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""

    processing_time: float
    memory_usage_mb: float
    patterns_processed: int
    log_size_mb: float
    throughput_mb_per_sec: float
    cache_hit_rate: float
    optimization_applied: list[str]


class LogChunker:
    """ログファイルのチャンク分割処理"""

    def __init__(self, chunk_size_mb: float = 1.0, overlap_lines: int = 50):
        """Args:
        chunk_size_mb: チャンクサイズ（MB）
        overlap_lines: チャンク間のオーバーラップ行数

        """
        self.chunk_size_bytes = int(chunk_size_mb * 1024 * 1024)
        self.overlap_lines = overlap_lines

    def chunk_log_content(self, log_content: str) -> list[tuple[str, int, int]]:
        """ログ内容をチャンクに分割

        Args:
            log_content: ログ内容

        Returns:
            (チャンク内容, 開始行, 終了行) のリスト

        """
        lines = log_content.splitlines()
        total_lines = len(lines)

        if len(log_content.encode("utf-8")) <= self.chunk_size_bytes:
            # 小さなファイルはそのまま返す
            return [(log_content, 0, total_lines)]

        chunks: list[tuple[str, int, int]] = []
        current_pos = 0

        while current_pos < total_lines:
            # チャンクの終了位置を計算
            chunk_lines: list[str] = []
            chunk_size = 0
            end_pos = current_pos

            while end_pos < total_lines and chunk_size < self.chunk_size_bytes:
                line = lines[end_pos]
                line_size = len(line.encode("utf-8")) + 1  # +1 for newline
                if chunk_size + line_size > self.chunk_size_bytes and chunk_lines:
                    break
                chunk_lines.append(line)
                chunk_size += line_size
                end_pos += 1

            # オーバーラップを追加
            if end_pos < total_lines:
                overlap_end = min(end_pos + self.overlap_lines, total_lines)
                for i in range(end_pos, overlap_end):
                    chunk_lines.append(lines[i])

            chunk_content = "\n".join(chunk_lines)
            chunks.append((chunk_content, current_pos, end_pos))

            # 次のチャンクの開始位置（オーバーラップを考慮）
            current_pos = max(end_pos - self.overlap_lines, end_pos)

        return chunks

    async def process_chunks_parallel(
        self,
        chunks: list[tuple[str, int, int]],
        processor_func: Callable[[str], list[Any]],
        max_workers: int = 4,
    ) -> list[Any]:
        """チャンクを並列処理

        Args:
            chunks: 処理するチャンクのリスト
            processor_func: 処理関数
            max_workers: 最大ワーカー数

        Returns:
            処理結果のリスト

        """
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks: list[asyncio.Future[Any]] = []
            for chunk_content, _start_line, _end_line in chunks:
                task = loop.run_in_executor(executor, processor_func, chunk_content)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # エラーハンドリング
        successful_results: list[Any] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("チャンク %d の処理に失敗: %s", i, result)
            else:
                successful_results.append(result)

        return successful_results


class OptimizedPatternMatcher:
    """最適化されたパターンマッチャー"""

    def __init__(self):
        self.compiled_patterns: dict[str, re.Pattern[str]] = {}
        self.pattern_cache: dict[str, list[Any]] = {}
        self.keyword_trie: KeywordTrie | None = None

    def compile_patterns(self, patterns: list[Any]) -> None:
        """パターンを事前コンパイル

        Args:
            patterns: パターンのリスト

        """
        logger.info("パターンを事前コンパイル中... (%d パターン)", len(patterns))

        for pattern in patterns:
            pattern_id = pattern.id
            for regex_pattern in pattern.regex_patterns:
                try:
                    # 正規表現を事前コンパイル
                    compiled = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)
                    self.compiled_patterns[f"{pattern_id}:{regex_pattern}"] = compiled
                except re.error as e:
                    logger.warning("正規表現のコンパイルに失敗: %s - %s", regex_pattern, e)

        # キーワードトライを構築
        all_keywords: list[str] = []
        for pattern in patterns:
            all_keywords.extend(pattern.keywords)

        if all_keywords:
            self.keyword_trie = KeywordTrie(all_keywords)

        logger.info(
            "パターンコンパイル完了: %d 正規表現, %d キーワード",
            len(self.compiled_patterns),
            len(all_keywords),
        )

    def match_patterns_optimized(self, text: str, patterns: list[Any]) -> list[Any]:
        """最適化されたパターンマッチング

        Args:
            text: 検索対象テキスト
            patterns: パターンのリスト

        Returns:
            マッチ結果のリスト

        """
        # キャッシュチェック
        text_hash = hash(text[:1000])  # 最初の1000文字でハッシュ化
        cache_key = f"{text_hash}:{len(patterns)}"

        if cache_key in self.pattern_cache:
            return self.pattern_cache[cache_key]

        matches: list[Any] = []

        # 1. 高速キーワード検索でフィルタリング
        candidate_patterns = self._filter_patterns_by_keywords(text, patterns)

        # 2. 正規表現マッチング（候補パターンのみ）
        for pattern in candidate_patterns:
            pattern_matches = self._match_single_pattern_optimized(text, pattern)
            matches.extend(pattern_matches)

        # 結果をキャッシュ
        if len(self.pattern_cache) < 1000:  # キャッシュサイズ制限
            self.pattern_cache[cache_key] = matches

        return matches

    def _filter_patterns_by_keywords(self, text: str, patterns: list[Any]) -> list[Any]:
        """キーワードによるパターンフィルタリング

        Args:
            text: 検索対象テキスト
            patterns: パターンのリスト

        Returns:
            候補パターンのリスト

        """
        if not self.keyword_trie:
            return patterns

        # テキスト内のキーワードを高速検索
        found_keywords = self.keyword_trie.find_keywords(text.lower())

        # キーワードにマッチするパターンのみを返す
        candidate_patterns: list[Any] = []
        for pattern in patterns:
            pattern_keywords = [kw.lower() for kw in pattern.keywords]
            if any(keyword in found_keywords for keyword in pattern_keywords):
                candidate_patterns.append(pattern)

        logger.debug("キーワードフィルタリング: %d/%d パターンが候補", len(candidate_patterns), len(patterns))

        return candidate_patterns

    def _match_single_pattern_optimized(self, text: str, pattern: Any) -> list[Any]:
        """単一パターンの最適化マッチング

        Args:
            text: 検索対象テキスト
            pattern: パターン

        Returns:
            マッチ結果のリスト

        """
        matches: list[Any] = []

        # 事前コンパイルされた正規表現を使用
        for regex_pattern in pattern.regex_patterns:
            compiled_key = f"{pattern.id}:{regex_pattern}"
            compiled_regex = self.compiled_patterns.get(compiled_key)

            if compiled_regex:
                try:
                    regex_matches = compiled_regex.finditer(text)
                    for match in regex_matches:
                        match_result = self._create_match_result(pattern, match, text)
                        matches.append(match_result)
                except Exception as e:
                    logger.warning("正規表現マッチング中にエラー: %s", e)

        return matches

    def _create_match_result(self, pattern: Any, regex_match: re.Match[str], text: str) -> Any:
        """マッチ結果オブジェクトを作成

        Args:
            pattern: パターン
            regex_match: 正規表現マッチ結果
            text: 元のテキスト

        Returns:
            マッチ結果オブジェクト

        """
        from .models import Match

        # コンテキストを抽出（前後50文字）
        start_pos = max(0, regex_match.start() - 50)
        end_pos = min(len(text), regex_match.end() + 50)
        text[start_pos:end_pos]

        return Match(
            pattern_id=pattern.id,
            match_type="regex",  # 正規表現マッチ
            matched_text=regex_match.group(),
            start_position=regex_match.start(),
            end_position=regex_match.end(),
            confidence=0.8,  # デフォルト信頼度
            context_before=text[start_pos : regex_match.start()],
            context_after=text[regex_match.end() : end_pos],
        )

    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self.pattern_cache.clear()
        gc.collect()


class KeywordTrie:
    """キーワード検索用のトライ木"""

    def __init__(self, keywords: list[str]):
        self.root: dict[str, Any] = {}
        self.keywords = set(keywords)
        self._build_trie(keywords)

    def _build_trie(self, keywords: list[str]) -> None:
        """トライ木を構築

        Args:
            keywords: キーワードのリスト

        """
        for keyword in keywords:
            node = self.root
            for char in keyword.lower():
                if char not in node:
                    node[char] = {}
                node = node[char]
            node["$"] = True  # 終端マーカー

    def find_keywords(self, text: str) -> set[str]:
        """テキスト内のキーワードを高速検索

        Args:
            text: 検索対象テキスト

        Returns:
            見つかったキーワードのセット

        """
        found_keywords: set[str] = set()
        text_lower = text.lower()

        for i in range(len(text_lower)):
            node = self.root
            j = i

            while j < len(text_lower) and text_lower[j] in node:
                node = node[text_lower[j]]
                j += 1

                if "$" in node:
                    # キーワードが見つかった
                    keyword = text_lower[i:j]
                    if keyword in self.keywords:
                        found_keywords.add(keyword)

        return found_keywords


class MemoryOptimizer:
    """メモリ使用量最適化"""

    def __init__(self, max_memory_mb: float = 500.0):
        """Args:
        max_memory_mb: 最大メモリ使用量（MB）

        """
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self.memory_warnings: list[str] = []

    def monitor_memory_usage(self) -> float:
        """現在のメモリ使用量を監視

        Returns:
            メモリ使用量（MB）

        """
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_bytes = process.memory_info().rss
            memory_mb = memory_bytes / (1024 * 1024)

            if memory_bytes > self.max_memory_bytes:
                warning = f"メモリ使用量が制限を超過: {memory_mb:.1f}MB > {self.max_memory_bytes / (1024 * 1024):.1f}MB"
                self.memory_warnings.append(warning)
                logger.warning(warning)

            return memory_mb

        except ImportError:
            logger.warning("psutilが利用できません。メモリ監視をスキップします。")
            return 0.0

    def optimize_memory_usage(self) -> None:
        """メモリ使用量を最適化"""
        # ガベージコレクションを強制実行
        collected = gc.collect()
        logger.debug("ガベージコレクション実行: %d オブジェクトを回収", collected)

        # メモリ使用量を再チェック
        current_memory = self.monitor_memory_usage()
        logger.debug("最適化後のメモリ使用量: %.1f MB", current_memory)

    def get_memory_statistics(self) -> dict[str, Any]:
        """メモリ統計情報を取得

        Returns:
            メモリ統計情報

        """
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "warnings_count": len(self.memory_warnings),
                "warnings": self.memory_warnings[-5:],  # 最新の5件
            }

        except ImportError:
            return {"error": "psutilが利用できません"}


class PerformanceOptimizer:
    """パフォーマンス最適化の統合クラス"""

    def __init__(
        self,
        chunk_size_mb: float = 1.0,
        max_workers: int = 4,
        max_memory_mb: float = 500.0,
        enable_caching: bool = True,
    ):
        """Args:
        chunk_size_mb: ログチャンクサイズ（MB）
        max_workers: 最大並列ワーカー数
        max_memory_mb: 最大メモリ使用量（MB）
        enable_caching: キャッシュ有効フラグ

        """
        self.log_chunker = LogChunker(chunk_size_mb)
        self.pattern_matcher = OptimizedPatternMatcher()
        self.memory_optimizer = MemoryOptimizer(max_memory_mb)
        self.max_workers = max_workers
        self.enable_caching = enable_caching

        self.performance_metrics = PerformanceMetrics(
            processing_time=0.0,
            memory_usage_mb=0.0,
            patterns_processed=0,
            log_size_mb=0.0,
            throughput_mb_per_sec=0.0,
            cache_hit_rate=0.0,
            optimization_applied=[],
        )

    async def optimize_pattern_matching(
        self,
        log_content: str,
        patterns: list[Any],
        force_chunking: bool = False,
    ) -> tuple[list[Any], PerformanceMetrics]:
        """パターンマッチングを最適化実行

        Args:
            log_content: ログ内容
            patterns: パターンのリスト
            force_chunking: 強制チャンク分割フラグ

        Returns:
            (マッチ結果, パフォーマンスメトリクス)

        """
        start_time = time.time()
        start_memory = self.memory_optimizer.monitor_memory_usage()

        # パターンを事前コンパイル
        self.pattern_matcher.compile_patterns(patterns)

        log_size_mb = len(log_content.encode("utf-8")) / (1024 * 1024)
        optimization_applied: list[str] = []

        try:
            # ログサイズに応じて処理方法を決定
            if log_size_mb > 5.0 or force_chunking:
                # 大きなログはチャンク分割して並列処理
                optimization_applied.append("chunk_processing")
                matches = await self._process_large_log(log_content, patterns)
            else:
                # 小さなログは通常処理
                optimization_applied.append("direct_processing")
                matches = self.pattern_matcher.match_patterns_optimized(log_content, patterns)

            # メモリ最適化
            if self.memory_optimizer.monitor_memory_usage() > 300:  # 300MB超過時
                optimization_applied.append("memory_optimization")
                self.memory_optimizer.optimize_memory_usage()

            # パフォーマンスメトリクスを計算
            end_time = time.time()
            end_memory = self.memory_optimizer.monitor_memory_usage()

            processing_time = end_time - start_time
            throughput = log_size_mb / processing_time if processing_time > 0 else 0

            self.performance_metrics = PerformanceMetrics(
                processing_time=processing_time,
                memory_usage_mb=max(start_memory, end_memory),
                patterns_processed=len(patterns),
                log_size_mb=log_size_mb,
                throughput_mb_per_sec=throughput,
                cache_hit_rate=self._calculate_cache_hit_rate(),
                optimization_applied=optimization_applied,
            )

            logger.info(
                "パターンマッチング完了: %.2f秒, %.1f MB/s, %d マッチ",
                processing_time,
                throughput,
                len(matches),
            )

            return matches, self.performance_metrics

        except Exception as e:
            logger.error("パターンマッチング最適化中にエラー: %s", e)
            raise

    async def _process_large_log(self, log_content: str, patterns: list[Any]) -> list[Any]:
        """大きなログの並列処理

        Args:
            log_content: ログ内容
            patterns: パターンのリスト

        Returns:
            マッチ結果のリスト

        """
        # ログをチャンクに分割
        chunks = self.log_chunker.chunk_log_content(log_content)
        logger.info("ログを %d チャンクに分割", len(chunks))

        # 並列処理用の関数を定義
        def process_chunk(chunk_content: str) -> list[Any]:
            return self.pattern_matcher.match_patterns_optimized(chunk_content, patterns)

        # チャンクを並列処理
        chunk_results = await self.log_chunker.process_chunks_parallel(chunks, process_chunk, self.max_workers)

        # 結果をマージ（重複除去）
        all_matches: list[Any] = []
        seen_matches: set[tuple[str, int, str]] = set()

        for chunk_matches in chunk_results:
            for match in chunk_matches:
                # 重複チェック（位置とパターンIDで判定）
                match_key = (match.pattern_id, match.start_position, match.matched_text)
                if match_key not in seen_matches:
                    seen_matches.add(match_key)
                    all_matches.append(match)

        logger.info("チャンク処理完了: %d マッチを統合", len(all_matches))
        return all_matches

    def _calculate_cache_hit_rate(self) -> float:
        """キャッシュヒット率を計算

        Returns:
            キャッシュヒット率（0.0-1.0）

        """
        if not self.enable_caching:
            return 0.0

        cache_size = len(self.pattern_matcher.pattern_cache)
        if cache_size == 0:
            return 0.0

        # 簡易的なヒット率計算（実際の実装では詳細な統計が必要）
        return min(cache_size / 100.0, 1.0)

    def get_performance_report(self) -> dict[str, Any]:
        """パフォーマンスレポートを取得

        Returns:
            パフォーマンスレポート

        """
        memory_stats = self.memory_optimizer.get_memory_statistics()

        return {
            "processing_metrics": {
                "processing_time_sec": self.performance_metrics.processing_time,
                "throughput_mb_per_sec": self.performance_metrics.throughput_mb_per_sec,
                "patterns_processed": self.performance_metrics.patterns_processed,
                "log_size_mb": self.performance_metrics.log_size_mb,
            },
            "memory_metrics": memory_stats,
            "optimization_metrics": {
                "cache_hit_rate": self.performance_metrics.cache_hit_rate,
                "optimizations_applied": self.performance_metrics.optimization_applied,
                "compiled_patterns": len(self.pattern_matcher.compiled_patterns),
                "cached_results": len(self.pattern_matcher.pattern_cache),
            },
            "recommendations": self._generate_performance_recommendations(),
        }

    def _generate_performance_recommendations(self) -> list[str]:
        """パフォーマンス改善の推奨事項を生成

        Returns:
            推奨事項のリスト

        """
        recommendations: list[str] = []

        # 処理時間の推奨事項
        if self.performance_metrics.processing_time > 10.0:
            recommendations.append("処理時間が長いため、チャンクサイズを小さくすることを検討してください")

        # スループットの推奨事項
        if self.performance_metrics.throughput_mb_per_sec < 1.0:
            recommendations.append("スループットが低いため、並列ワーカー数を増やすことを検討してください")

        # メモリ使用量の推奨事項
        if self.performance_metrics.memory_usage_mb > 400:
            recommendations.append("メモリ使用量が多いため、キャッシュサイズを制限することを検討してください")

        # キャッシュヒット率の推奨事項
        if self.performance_metrics.cache_hit_rate < 0.3:
            recommendations.append("キャッシュヒット率が低いため、キャッシュ戦略を見直すことを検討してください")

        if not recommendations:
            recommendations.append("パフォーマンスは良好です")

        return recommendations

    def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        self.pattern_matcher.clear_cache()
        self.memory_optimizer.optimize_memory_usage()
        logger.info("パフォーマンス最適化リソースをクリーンアップしました")


# パフォーマンス最適化のユーティリティ関数


def estimate_processing_time(log_size_mb: float, patterns_count: int) -> float:
    """処理時間を推定

    Args:
        log_size_mb: ログサイズ（MB）
        patterns_count: パターン数

    Returns:
        推定処理時間（秒）

    """
    # 経験的な計算式（実際の環境に応じて調整が必要）
    base_time = log_size_mb * 0.1  # 基本処理時間
    pattern_overhead = patterns_count * 0.01  # パターン数による追加時間
    return base_time + pattern_overhead


def recommend_chunk_size(log_size_mb: float, available_memory_mb: float) -> float:
    """推奨チャンクサイズを計算

    Args:
        log_size_mb: ログサイズ（MB）
        available_memory_mb: 利用可能メモリ（MB）

    Returns:
        推奨チャンクサイズ（MB）

    """
    # メモリの20%をチャンクサイズの上限とする
    max_chunk_size = available_memory_mb * 0.2

    # ログサイズに応じた推奨サイズ
    if log_size_mb < 5:
        return min(log_size_mb, max_chunk_size)
    if log_size_mb < 50:
        return min(2.0, max_chunk_size)
    return min(5.0, max_chunk_size)


def optimize_regex_patterns(patterns: list[str]) -> list[str]:
    """正規表現パターンを最適化

    Args:
        patterns: 正規表現パターンのリスト

    Returns:
        最適化されたパターンのリスト

    """
    optimized: list[str] = []

    for pattern in patterns:
        # 基本的な最適化
        optimized_pattern = pattern

        # 不要な括弧を除去
        optimized_pattern = re.sub(r"\(([^)]+)\)", r"\1", optimized_pattern)

        # 重複する文字クラスを統合
        optimized_pattern = re.sub(r"\[a-zA-Z\]", r"[a-zA-Z]", optimized_pattern)

        optimized.append(optimized_pattern)

    return optimized
