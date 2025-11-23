"""ログ圧縮モジュール

大量ログファイルを効率的に圧縮し、重要な情報を保持しながら
サイズを削減します。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """圧縮結果"""

    original_size: int
    compressed_size: int
    compression_ratio: float
    lines_removed: int
    lines_kept: int
    techniques_applied: list[str]


class LogCompressor:
    """ログ圧縮クラス"""

    def __init__(self, target_tokens: int | None = None, target_size_mb: float | None = None):
        """Args:
        target_tokens: 目標トークン数
        target_size_mb: 目標サイズ（MB）

        """
        self.target_tokens = target_tokens
        self.target_size_bytes = int(target_size_mb * 1024 * 1024) if target_size_mb else None

        # 重要度の高いパターン（保持すべき）
        self.important_patterns = [
            r"error|ERROR|Error",
            r"fail|FAIL|Fail|failed|FAILED|Failed",
            r"exception|Exception|EXCEPTION",
            r"traceback|Traceback|TRACEBACK",
            r"warning|WARNING|Warning",
            r"critical|CRITICAL|Critical",
            r"fatal|FATAL|Fatal",
            r"denied|DENIED|Denied",
            r"timeout|TIMEOUT|Timeout",
            r"not found|NOT FOUND|Not Found",
            r"permission|Permission|PERMISSION",
            r"module.*not.*found",
            r"import.*error",
            r"syntax.*error",
            r"connection.*error",
            r"network.*error",
        ]

        # 削除対象パターン（重要度の低い）
        self.removable_patterns = [
            r"^\s*$",  # 空行
            r"^\s*#.*$",  # コメント行
            r"^\s*//.*$",  # コメント行
            r"^\s*\*.*$",  # コメント行
            r"debug|DEBUG|Debug",
            r"info|INFO|Info",
            r"trace|TRACE|Trace",
            r"verbose|VERBOSE|Verbose",
            r"^\d{4}-\d{2}-\d{2}.*INFO.*$",  # INFO レベルのタイムスタンプ付きログ
            r"^\[\d{4}-\d{2}-\d{2}.*\]\s*(INFO|Debug|TRACE)",  # 括弧付きタイムスタンプ
        ]

        # 重複除去用のパターン
        self.duplicate_patterns = [
            r"^(.+)\s+\(repeated \d+ times\)$",  # 既に重複マークされた行
            r"^Downloading\s+.*$",  # ダウンロード進捗
            r"^Installing\s+.*$",  # インストール進捗
            r"^Processing\s+.*$",  # 処理進捗
            r"^\s*\.\s*$",  # 進捗ドット
            r"^\s*\d+%\s*$",  # パーセンテージ
        ]

    def compress_log(self, log_content: str) -> str:
        """ログを圧縮

        Args:
            log_content: 元のログ内容

        Returns:
            圧縮されたログ内容

        """
        original_size = len(log_content.encode("utf-8"))
        lines = log_content.splitlines()
        original_line_count = len(lines)

        logger.info("ログ圧縮開始: %d 行, %.1f MB", original_line_count, original_size / (1024 * 1024))

        techniques_applied: list[str] = []
        compressed_lines = lines.copy()

        # 1. 空行とコメント行の除去
        compressed_lines, removed_count = self._remove_low_priority_lines(compressed_lines)
        if removed_count > 0:
            techniques_applied.append(f"low_priority_removal({removed_count})")

        # 2. 重複行の除去と集約
        compressed_lines, duplicate_count = self._remove_duplicates(compressed_lines)
        if duplicate_count > 0:
            techniques_applied.append(f"duplicate_removal({duplicate_count})")

        # 3. 重要な行の保持と不要な行の削除
        compressed_lines = self._preserve_important_lines(compressed_lines)
        techniques_applied.append("importance_filtering")

        # 4. 長い行の短縮
        compressed_lines = self._truncate_long_lines(compressed_lines)
        techniques_applied.append("line_truncation")

        # 5. 目標サイズに合わせた追加圧縮
        if self.target_tokens or self.target_size_bytes:
            compressed_lines = self._compress_to_target_size(compressed_lines)
            techniques_applied.append("target_size_compression")

        # 圧縮結果の作成
        compressed_content = "\n".join(compressed_lines)
        compressed_size = len(compressed_content.encode("utf-8"))

        compression_result = CompressionResult(
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compressed_size / original_size if original_size > 0 else 0,
            lines_removed=original_line_count - len(compressed_lines),
            lines_kept=len(compressed_lines),
            techniques_applied=techniques_applied,
        )

        logger.info(
            "ログ圧縮完了: %d → %d 行 (%.1f%%), %.1f → %.1f MB (%.1f%%)",
            original_line_count,
            len(compressed_lines),
            (len(compressed_lines) / original_line_count) * 100 if original_line_count > 0 else 0,
            original_size / (1024 * 1024),
            compressed_size / (1024 * 1024),
            compression_result.compression_ratio * 100,
        )

        return compressed_content

    def _remove_low_priority_lines(self, lines: list[str]) -> tuple[list[str], int]:
        """低優先度行の除去

        Args:
            lines: 行のリスト

        Returns:
            (フィルタ後の行, 除去された行数)

        """
        filtered_lines: list[str] = []
        removed_count = 0

        for line in lines:
            # 重要なパターンが含まれている場合は保持
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.important_patterns):
                filtered_lines.append(line)
                continue

            # 削除対象パターンにマッチする場合は除去
            if any(re.match(pattern, line) for pattern in self.removable_patterns):
                removed_count += 1
                continue

            # その他の行は保持
            filtered_lines.append(line)

        return filtered_lines, removed_count

    def _remove_duplicates(self, lines: list[str]) -> tuple[list[str], int]:
        """重複行の除去と集約

        Args:
            lines: 行のリスト

        Returns:
            (重複除去後の行, 除去された行数)

        """
        line_counts: dict[str, int] = {}
        unique_lines: list[str] = []
        duplicate_count = 0

        for line in lines:
            # タイムスタンプを除去して正規化
            normalized_line = self._normalize_line_for_deduplication(line)

            if normalized_line in line_counts:
                line_counts[normalized_line] += 1
                duplicate_count += 1
            else:
                line_counts[normalized_line] = 1
                unique_lines.append(line)

        # 重複が多い行には集約マークを追加
        final_lines: list[str] = []
        for line in unique_lines:
            normalized_line = self._normalize_line_for_deduplication(line)
            count = line_counts[normalized_line]

            if count > 1:
                final_lines.append(f"{line} (repeated {count} times)")
            else:
                final_lines.append(line)

        return final_lines, duplicate_count

    def _normalize_line_for_deduplication(self, line: str) -> str:
        """重複除去用の行正規化

        Args:
            line: 元の行

        Returns:
            正規化された行

        """
        # タイムスタンプパターンを除去
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[.\d]*[Z]?", "[TIMESTAMP]", line)
        normalized = re.sub(r"\[\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[.\d]*[Z]?\]", "[TIMESTAMP]", normalized)

        # 数値を正規化
        normalized = re.sub(r"\b\d+\b", "[NUMBER]", normalized)

        # パスを正規化
        normalized = re.sub(r"/[^\s]+", "[PATH]", normalized)

        # 先頭と末尾の空白を除去
        return normalized.strip()

    def _preserve_important_lines(self, lines: list[str]) -> list[str]:
        """重要な行の保持

        Args:
            lines: 行のリスト

        Returns:
            重要な行を保持したリスト

        """
        important_lines: list[str] = []
        context_buffer: list[str] = []
        context_size = 2  # 重要な行の前後2行を保持

        for i, line in enumerate(lines):
            is_important = any(re.search(pattern, line, re.IGNORECASE) for pattern in self.important_patterns)

            if is_important:
                # 重要な行の前のコンテキストを追加
                start_context = max(0, i - context_size)
                for j in range(start_context, i):
                    if j < len(lines) and lines[j] not in important_lines:
                        important_lines.append(lines[j])

                # 重要な行を追加
                important_lines.append(line)

                # 重要な行の後のコンテキストを予約
                end_context = min(len(lines), i + context_size + 1)
                for j in range(i + 1, end_context):
                    if j < len(lines):
                        context_buffer.append(lines[j])

            elif context_buffer and line in context_buffer:
                # コンテキストバッファにある行を追加
                important_lines.append(line)
                context_buffer.remove(line)

        return important_lines

    def _truncate_long_lines(self, lines: list[str], max_length: int = 500) -> list[str]:
        """長い行の短縮

        Args:
            lines: 行のリスト
            max_length: 最大行長

        Returns:
            短縮された行のリスト

        """
        truncated_lines: list[str] = []

        for line in lines:
            if len(line) > max_length:
                # 重要な部分（エラーメッセージなど）を保持
                if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.important_patterns):
                    # 重要なパターンの周辺を保持
                    for pattern in self.important_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            start = max(0, match.start() - 100)
                            end = min(len(line), match.end() + 100)
                            truncated_line = line[start:end]
                            if start > 0:
                                truncated_line = "..." + truncated_line
                            if end < len(line):
                                truncated_line = truncated_line + "..."
                            truncated_lines.append(truncated_line)
                            break
                    else:
                        # パターンが見つからない場合は先頭を保持
                        truncated_lines.append(line[:max_length] + "...")
                else:
                    # 重要でない長い行は先頭のみ保持
                    truncated_lines.append(line[:max_length] + "...")
            else:
                truncated_lines.append(line)

        return truncated_lines

    def _compress_to_target_size(self, lines: list[str]) -> list[str]:
        """目標サイズに合わせた圧縮

        Args:
            lines: 行のリスト

        Returns:
            目標サイズに圧縮された行のリスト

        """
        current_content = "\n".join(lines)
        current_size = len(current_content.encode("utf-8"))

        # 目標サイズを決定
        target_size = None
        if self.target_size_bytes:
            target_size = self.target_size_bytes
        elif self.target_tokens:
            # 1トークン ≈ 4文字として概算
            target_size = self.target_tokens * 4

        if not target_size or current_size <= target_size:
            return lines

        # 圧縮率を計算
        compression_ratio = target_size / current_size
        target_line_count = int(len(lines) * compression_ratio)

        # 重要度でソートして上位を保持
        scored_lines: list[tuple[float, int, str]] = []
        for i, line in enumerate(lines):
            importance_score = self.calculate_line_importance(line)
            scored_lines.append((importance_score, i, line))

        # 重要度順にソート
        scored_lines.sort(key=lambda x: x[0], reverse=True)

        # 上位の行を選択（元の順序を保持）
        selected_indices = sorted([item[1] for item in scored_lines[:target_line_count]])
        compressed_lines = [lines[i] for i in selected_indices]

        return compressed_lines

    def calculate_line_importance(self, line: str) -> float:
        """行の重要度を計算

        Args:
            line: 行内容

        Returns:
            重要度スコア（0.0-1.0）

        """
        score = 0.0

        # 重要なパターンにマッチする場合は高スコア
        for pattern in self.important_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                score += 0.8
                break

        # エラーレベルによる重み付け
        if re.search(r"critical|fatal", line, re.IGNORECASE):
            score += 0.9
        elif re.search(r"error", line, re.IGNORECASE):
            score += 0.7
        elif re.search(r"warning", line, re.IGNORECASE):
            score += 0.5
        elif re.search(r"info", line, re.IGNORECASE):
            score += 0.2

        # 行の長さによる重み付け（長い行は詳細情報を含む可能性）
        if len(line) > 100:
            score += 0.1

        # スタックトレースや詳細情報
        if re.search(r"traceback|stack trace|at\s+\w+\.\w+", line, re.IGNORECASE):
            score += 0.6

        # ファイルパスや行番号
        if re.search(r"\.py:\d+|\.js:\d+|\.java:\d+", line):
            score += 0.4

        return min(score, 1.0)

    def get_compression_statistics(self, original_content: str, compressed_content: str) -> dict[str, Any]:
        """圧縮統計情報を取得

        Args:
            original_content: 元のログ内容
            compressed_content: 圧縮後のログ内容

        Returns:
            圧縮統計情報

        """
        original_size = len(original_content.encode("utf-8"))
        compressed_size = len(compressed_content.encode("utf-8"))
        original_lines = len(original_content.splitlines())
        compressed_lines = len(compressed_content.splitlines())

        return {
            "size_reduction": {
                "original_bytes": original_size,
                "compressed_bytes": compressed_size,
                "reduction_bytes": original_size - compressed_size,
                "reduction_percentage": ((original_size - compressed_size) / original_size) * 100
                if original_size > 0
                else 0,
            },
            "line_reduction": {
                "original_lines": original_lines,
                "compressed_lines": compressed_lines,
                "reduction_lines": original_lines - compressed_lines,
                "reduction_percentage": ((original_lines - compressed_lines) / original_lines) * 100
                if original_lines > 0
                else 0,
            },
            "compression_ratio": compressed_size / original_size if original_size > 0 else 0,
            "estimated_tokens_saved": (original_size - compressed_size) // 4,  # 概算
        }


def compress_log_for_ai_analysis(log_content: str, max_tokens: int = 8000) -> tuple[str, dict[str, Any]]:
    """AI分析用のログ圧縮

    Args:
        log_content: 元のログ内容
        max_tokens: 最大トークン数

    Returns:
        (圧縮されたログ, 統計情報)

    """
    compressor = LogCompressor(target_tokens=max_tokens)
    compressed_content = compressor.compress_log(log_content)
    statistics = compressor.get_compression_statistics(log_content, compressed_content)

    return compressed_content, statistics


def smart_log_sampling(log_content: str, sample_ratio: float = 0.3) -> str:
    """スマートログサンプリング

    重要な部分を保持しながらログをサンプリングします。

    Args:
        log_content: 元のログ内容
        sample_ratio: サンプリング比率（0.0-1.0）

    Returns:
        サンプリングされたログ内容

    """
    lines = log_content.splitlines()
    target_line_count = int(len(lines) * sample_ratio)

    compressor = LogCompressor()

    # 重要度でソート
    scored_lines: list[tuple[float, int, str]] = []
    for i, line in enumerate(lines):
        importance_score = compressor.calculate_line_importance(line)
        scored_lines.append((importance_score, i, line))

    # 重要度順にソート
    scored_lines.sort(key=lambda x: x[0], reverse=True)

    # 上位の行を選択（元の順序を保持）
    selected_indices = sorted([item[1] for item in scored_lines[:target_line_count]])
    sampled_lines = [lines[i] for i in selected_indices]

    return "\n".join(sampled_lines)
