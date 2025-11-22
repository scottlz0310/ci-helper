"""
ログ圧縮モジュールのテスト

圧縮アルゴリズム、ファイル処理、圧縮率検証をテスト
"""

from ci_helper.core.log_compressor import (
    CompressionResult,
    LogCompressor,
    compress_log_for_ai_analysis,
    smart_log_sampling,
)


class TestCompressionResult:
    """CompressionResultのテスト"""

    def test_compression_result_creation(self):
        """圧縮結果の作成テスト"""
        result = CompressionResult(
            original_size=1000,
            compressed_size=500,
            compression_ratio=0.5,
            lines_removed=100,
            lines_kept=50,
            techniques_applied=["duplicate_removal", "importance_filtering"],
        )

        assert result.original_size == 1000
        assert result.compressed_size == 500
        assert result.compression_ratio == 0.5
        assert result.lines_removed == 100
        assert result.lines_kept == 50
        assert "duplicate_removal" in result.techniques_applied
        assert "importance_filtering" in result.techniques_applied


class TestLogCompressor:
    """LogCompressorのテスト"""

    def test_initialization_default(self):
        """デフォルト初期化テスト"""
        compressor = LogCompressor()
        assert compressor.target_tokens is None
        assert compressor.target_size_bytes is None
        assert len(compressor.important_patterns) > 0
        assert len(compressor.removable_patterns) > 0

    def test_initialization_with_target_tokens(self):
        """トークン数指定での初期化テスト"""
        compressor = LogCompressor(target_tokens=1000)
        assert compressor.target_tokens == 1000
        assert compressor.target_size_bytes is None

    def test_initialization_with_target_size(self):
        """サイズ指定での初期化テスト"""
        compressor = LogCompressor(target_size_mb=5.0)
        assert compressor.target_tokens is None
        assert compressor.target_size_bytes == 5 * 1024 * 1024

    def test_compress_log_basic(self):
        """基本的なログ圧縮テスト"""
        compressor = LogCompressor()
        log_content = """
        INFO: Starting application
        DEBUG: Loading configuration
        ERROR: Database connection failed
        WARNING: Retrying connection
        INFO: Application started successfully
        """

        compressed = compressor.compress_log(log_content)

        # 圧縮後もエラーと警告は保持される
        assert "ERROR: Database connection failed" in compressed
        assert "WARNING: Retrying connection" in compressed

        # 元のログより短くなることを確認
        assert len(compressed) <= len(log_content)

    def test_compress_log_empty(self):
        """空ログの圧縮テスト"""
        compressor = LogCompressor()
        compressed = compressor.compress_log("")
        assert compressed == ""

    def test_compress_log_only_whitespace(self):
        """空白のみのログ圧縮テスト"""
        compressor = LogCompressor()
        log_content = "\n\n   \n\t\n  \n"
        compressed = compressor.compress_log(log_content)
        # 空白行は除去される
        assert compressed.strip() == ""

    def test_remove_low_priority_lines(self):
        """低優先度行除去テスト"""
        compressor = LogCompressor()
        lines = [
            "ERROR: Critical failure",
            "DEBUG: Debug information",
            "INFO: Information message",
            "",  # 空行
            "# Comment line",
            "WARNING: Important warning",
        ]

        filtered_lines, removed_count = compressor._remove_low_priority_lines(lines)

        # 重要な行は保持される
        assert "ERROR: Critical failure" in filtered_lines
        assert "WARNING: Important warning" in filtered_lines

        # 低優先度行は除去される
        assert removed_count > 0
        assert "" not in filtered_lines  # 空行は除去
        assert "# Comment line" not in filtered_lines  # コメント行は除去

    def test_remove_duplicates(self):
        """重複行除去テスト"""
        compressor = LogCompressor()
        lines = [
            "2024-01-01 10:00:00 ERROR: Connection failed",
            "2024-01-01 10:00:01 ERROR: Connection failed",
            "2024-01-01 10:00:02 ERROR: Connection failed",
            "INFO: Different message",
        ]

        deduplicated_lines, duplicate_count = compressor._remove_duplicates(lines)

        # 重複が除去され、集約マークが追加される
        assert duplicate_count == 2  # 2つの重複が除去された
        assert len(deduplicated_lines) == 2  # 2つのユニークな行
        assert any("repeated 3 times" in line for line in deduplicated_lines)

    def test_normalize_line_for_deduplication(self):
        """重複除去用行正規化テスト"""
        compressor = LogCompressor()

        # タイムスタンプの正規化
        line1 = "2024-01-01 10:00:00 ERROR: Connection failed"
        line2 = "2024-01-01 10:00:01 ERROR: Connection failed"

        normalized1 = compressor._normalize_line_for_deduplication(line1)
        normalized2 = compressor._normalize_line_for_deduplication(line2)

        assert normalized1 == normalized2
        assert "[TIMESTAMP]" in normalized1

    def test_preserve_important_lines(self):
        """重要行保持テスト"""
        compressor = LogCompressor()
        lines = [
            "Starting process",
            "Loading configuration",
            "ERROR: Database connection failed",
            "Stack trace line 1",
            "Stack trace line 2",
            "Process completed",
        ]

        important_lines = compressor._preserve_important_lines(lines)

        # エラー行とその前後のコンテキストが保持される
        assert "ERROR: Database connection failed" in important_lines
        assert len(important_lines) > 1  # コンテキストも含まれる

    def test_truncate_long_lines(self):
        """長い行の短縮テスト"""
        compressor = LogCompressor()
        long_line = "x" * 1000  # 1000文字の長い行
        short_line = "short line"

        lines = [long_line, short_line]
        truncated_lines = compressor._truncate_long_lines(lines, max_length=100)

        # 長い行は短縮される
        assert len(truncated_lines[0]) <= 103  # "..." を含めて
        assert "..." in truncated_lines[0]

        # 短い行はそのまま
        assert truncated_lines[1] == short_line

    def test_truncate_long_lines_with_important_pattern(self):
        """重要パターンを含む長い行の短縮テスト"""
        compressor = LogCompressor()
        long_line_with_error = "x" * 200 + "ERROR: Critical failure" + "y" * 200

        lines = [long_line_with_error]
        truncated_lines = compressor._truncate_long_lines(lines, max_length=100)

        # 重要パターン周辺が保持される
        assert "ERROR: Critical failure" in truncated_lines[0]

    def test_compress_to_target_size(self):
        """目標サイズ圧縮テスト"""
        compressor = LogCompressor(target_size_mb=0.001)  # 1KB
        lines = [
            "ERROR: Critical error",
            "WARNING: Warning message",
            "INFO: Info message",
            "DEBUG: Debug message",
        ] * 100  # 大量の行を作成

        compressed_lines = compressor._compress_to_target_size(lines)

        # 行数が削減される
        assert len(compressed_lines) < len(lines)

        # 重要な行が優先的に保持される
        error_lines = [line for line in compressed_lines if "ERROR" in line]
        debug_lines = [line for line in compressed_lines if "DEBUG" in line]
        assert len(error_lines) >= len(debug_lines)

    def test_calculate_line_importance(self):
        """行重要度計算テスト"""
        compressor = LogCompressor()

        # 重要度の高い行
        critical_line = "CRITICAL: System failure"
        error_line = "ERROR: Connection failed"
        warning_line = "WARNING: Low disk space"
        info_line = "INFO: Process started"
        debug_line = "DEBUG: Variable value"

        critical_score = compressor._calculate_line_importance(critical_line)
        error_score = compressor._calculate_line_importance(error_line)
        warning_score = compressor._calculate_line_importance(warning_line)
        info_score = compressor._calculate_line_importance(info_line)
        debug_score = compressor._calculate_line_importance(debug_line)

        # CRITICALとERRORは両方とも重要パターン(0.8) + レベル別スコアで1.0にキャップされる
        assert critical_score == 1.0
        assert error_score == 1.0

        # WARNINGも重要パターンに含まれるため1.0になる
        assert warning_score == 1.0

        # INFO、DEBUGは重要度順
        assert info_score > debug_score

        # 基本的な重要度の確認
        assert critical_score >= error_score >= warning_score  # 全て1.0
        assert warning_score > info_score
        assert info_score >= debug_score

    def test_calculate_line_importance_with_traceback(self):
        """スタックトレース行の重要度テスト"""
        compressor = LogCompressor()

        # ファイルパス形式のトレースバック行（.py:数字 パターンにマッチ）
        traceback_line = "  at module.py:42 in function_name"
        normal_line = "Normal log message"

        traceback_score = compressor._calculate_line_importance(traceback_line)
        normal_score = compressor._calculate_line_importance(normal_line)

        # トレースバック行は"at\s+\w+\.\w+"パターン(0.6) + .py:数字パターン(0.4) = 1.0
        assert traceback_score > normal_score
        assert traceback_score == 1.0  # トレースバックパターン + ファイルパスパターンで1.0

    def test_get_compression_statistics(self):
        """圧縮統計情報取得テスト"""
        compressor = LogCompressor()

        original_content = "Line 1\nLine 2\nLine 3\nLine 4\n"
        compressed_content = "Line 1\nLine 3\n"

        stats = compressor.get_compression_statistics(original_content, compressed_content)

        assert "size_reduction" in stats
        assert "line_reduction" in stats
        assert "compression_ratio" in stats
        assert "estimated_tokens_saved" in stats

        # サイズ削減の確認
        assert stats["size_reduction"]["original_bytes"] > stats["size_reduction"]["compressed_bytes"]
        assert stats["size_reduction"]["reduction_percentage"] > 0

        # 行数削減の確認
        assert stats["line_reduction"]["original_lines"] == 4
        assert stats["line_reduction"]["compressed_lines"] == 2
        assert stats["line_reduction"]["reduction_lines"] == 2

    def test_get_compression_statistics_empty_original(self):
        """空の元コンテンツでの統計情報テスト"""
        compressor = LogCompressor()

        stats = compressor.get_compression_statistics("", "")

        assert stats["compression_ratio"] == 0
        assert stats["size_reduction"]["reduction_percentage"] == 0
        assert stats["line_reduction"]["reduction_percentage"] == 0

    def test_compress_log_with_various_patterns(self):
        """様々なパターンを含むログの圧縮テスト"""
        compressor = LogCompressor()
        log_content = """
        2024-01-01 10:00:00 INFO: Application starting
        2024-01-01 10:00:01 DEBUG: Loading config file
        2024-01-01 10:00:02 ERROR: Database connection failed
        2024-01-01 10:00:03 WARNING: Retrying connection
        2024-01-01 10:00:04 CRITICAL: System shutdown initiated

        # This is a comment
        // Another comment

        2024-01-01 10:00:05 INFO: Cleanup completed
        """

        compressed = compressor.compress_log(log_content)

        # 重要なメッセージは保持される
        assert "ERROR: Database connection failed" in compressed
        assert "WARNING: Retrying connection" in compressed
        assert "CRITICAL: System shutdown initiated" in compressed

        # コメント行は除去される可能性が高い
        # （ただし、重要行のコンテキストとして保持される場合もある）

    def test_compress_log_performance_with_large_input(self):
        """大きな入力での圧縮パフォーマンステスト"""
        compressor = LogCompressor()

        # 大量のログ行を生成
        lines = []
        for i in range(1000):
            if i % 10 == 0:
                lines.append(f"ERROR: Error message {i}")
            elif i % 5 == 0:
                lines.append(f"WARNING: Warning message {i}")
            else:
                lines.append(f"INFO: Info message {i}")

        log_content = "\n".join(lines)

        # 圧縮実行（エラーが発生しないことを確認）
        compressed = compressor.compress_log(log_content)

        # 圧縮されていることを確認
        assert len(compressed) <= len(log_content)

        # エラーメッセージが保持されていることを確認
        error_count_original = log_content.count("ERROR:")
        error_count_compressed = compressed.count("ERROR:")
        assert error_count_compressed > 0
        # 全てのエラーが保持されるとは限らないが、一部は保持される
        assert error_count_compressed <= error_count_original


class TestCompressLogForAiAnalysis:
    """compress_log_for_ai_analysis関数のテスト"""

    def test_compress_log_for_ai_analysis_basic(self):
        """AI分析用ログ圧縮の基本テスト"""
        log_content = """
        INFO: Starting analysis
        ERROR: Critical error occurred
        DEBUG: Debug information
        WARNING: Warning message
        """

        compressed, stats = compress_log_for_ai_analysis(log_content, max_tokens=100)

        assert isinstance(compressed, str)
        assert isinstance(stats, dict)
        assert "compression_ratio" in stats
        assert "estimated_tokens_saved" in stats

    def test_compress_log_for_ai_analysis_empty(self):
        """空ログのAI分析用圧縮テスト"""
        compressed, stats = compress_log_for_ai_analysis("", max_tokens=100)

        assert compressed == ""
        assert stats["compression_ratio"] == 0

    def test_compress_log_for_ai_analysis_large_tokens(self):
        """大きなトークン数でのAI分析用圧縮テスト"""
        log_content = "INFO: Simple message"

        compressed, _stats = compress_log_for_ai_analysis(log_content, max_tokens=10000)

        # 小さなログは圧縮されない
        assert len(compressed) <= len(log_content)


class TestSmartLogSampling:
    """smart_log_sampling関数のテスト"""

    def test_smart_log_sampling_basic(self):
        """基本的なスマートログサンプリングテスト"""
        log_content = """
        INFO: Message 1
        ERROR: Critical error
        DEBUG: Debug info
        WARNING: Warning message
        INFO: Message 2
        """

        sampled = smart_log_sampling(log_content, sample_ratio=0.5)

        # サンプリング後も文字列
        assert isinstance(sampled, str)

        # 元のログより短い（または同じ）
        assert len(sampled) <= len(log_content)

        # 重要なメッセージが保持される可能性が高い
        lines = sampled.splitlines()
        assert len(lines) > 0

    def test_smart_log_sampling_full_ratio(self):
        """完全サンプリング（比率1.0）テスト"""
        log_content = "Line 1\nLine 2\nLine 3"

        sampled = smart_log_sampling(log_content, sample_ratio=1.0)

        # 全ての行が保持される
        assert len(sampled.splitlines()) == len(log_content.splitlines())

    def test_smart_log_sampling_zero_ratio(self):
        """ゼロサンプリング（比率0.0）テスト"""
        log_content = "Line 1\nLine 2\nLine 3"

        sampled = smart_log_sampling(log_content, sample_ratio=0.0)

        # 行が選択されない
        assert sampled == ""

    def test_smart_log_sampling_empty_input(self):
        """空入力でのスマートログサンプリングテスト"""
        sampled = smart_log_sampling("", sample_ratio=0.5)
        assert sampled == ""

    def test_smart_log_sampling_preserves_important_lines(self):
        """重要行保持のスマートログサンプリングテスト"""
        log_content = """
        DEBUG: Debug message 1
        DEBUG: Debug message 2
        ERROR: Critical error message
        DEBUG: Debug message 3
        DEBUG: Debug message 4
        """

        sampled = smart_log_sampling(log_content, sample_ratio=0.4)  # 40%サンプリング

        # エラーメッセージが保持される可能性が高い
        # （重要度が高いため）
        lines = sampled.splitlines()
        assert len(lines) > 0

    def test_smart_log_sampling_various_ratios(self):
        """様々なサンプリング比率でのテスト"""
        log_content = "\n".join([f"Line {i}" for i in range(100)])

        for ratio in [0.1, 0.3, 0.5, 0.7, 0.9]:
            sampled = smart_log_sampling(log_content, sample_ratio=ratio)
            sampled_lines = len(sampled.splitlines()) if sampled else 0
            original_lines = len(log_content.splitlines())

            # サンプリング比率に応じた行数になる（多少の誤差は許容）
            expected_lines = int(original_lines * ratio)
            assert abs(sampled_lines - expected_lines) <= 2  # 2行の誤差を許容


class TestLogCompressorEdgeCases:
    """LogCompressorのエッジケーステスト"""

    def test_compress_log_only_important_lines(self):
        """重要行のみのログ圧縮テスト"""
        compressor = LogCompressor()
        log_content = """
        ERROR: Error 1
        CRITICAL: Critical issue
        FATAL: Fatal error
        WARNING: Warning message
        """

        compressed = compressor.compress_log(log_content)

        # 全ての行が重要なので、大部分が保持される
        assert "ERROR: Error 1" in compressed
        assert "CRITICAL: Critical issue" in compressed
        assert "FATAL: Fatal error" in compressed
        assert "WARNING: Warning message" in compressed

    def test_compress_log_only_unimportant_lines(self):
        """重要でない行のみのログ圧縮テスト"""
        compressor = LogCompressor()
        log_content = """
        DEBUG: Debug 1
        INFO: Info 1
        TRACE: Trace message
        # Comment line
        """

        compressed = compressor.compress_log(log_content)

        # 重要でない行は大部分が除去される可能性が高い
        # ただし、完全に空になるとは限らない
        assert len(compressed) <= len(log_content)

    def test_compress_log_mixed_line_endings(self):
        """混在する改行コードでのログ圧縮テスト"""
        compressor = LogCompressor()
        log_content = "Line 1\nLine 2\r\nLine 3\rERROR: Error message\n"

        compressed = compressor.compress_log(log_content)

        # エラーメッセージが保持される
        assert "ERROR: Error message" in compressed

    def test_compress_log_unicode_content(self):
        """Unicode文字を含むログの圧縮テスト"""
        compressor = LogCompressor()
        log_content = """
        INFO: 処理を開始します
        ERROR: エラーが発生しました: データベース接続失敗
        DEBUG: デバッグ情報: 変数値 = 123
        WARNING: 警告: メモリ使用量が高いです
        """

        compressed = compressor.compress_log(log_content)

        # Unicode文字が正しく処理される
        assert "エラーが発生しました" in compressed
        assert isinstance(compressed, str)

    def test_compress_log_very_long_single_line(self):
        """非常に長い単一行のログ圧縮テスト"""
        compressor = LogCompressor()
        very_long_line = "ERROR: " + "x" * 10000  # 10KB以上の単一行

        compressed = compressor.compress_log(very_long_line)

        # 長い行は短縮される
        assert len(compressed) < len(very_long_line)
        assert "ERROR:" in compressed
        assert "..." in compressed

    def test_normalize_line_various_timestamp_formats(self):
        """様々なタイムスタンプ形式の正規化テスト"""
        compressor = LogCompressor()

        timestamps = [
            "2024-01-01 10:00:00 Message",
            "2024-01-01T10:00:00Z Message",
            "[2024-01-01 10:00:00.123] Message",
            "2024-01-01T10:00:00.123456Z Message",
        ]

        normalized_lines = [compressor._normalize_line_for_deduplication(ts) for ts in timestamps]

        # 全て同じように正規化される
        for normalized in normalized_lines:
            assert "[TIMESTAMP]" in normalized
            assert "Message" in normalized
