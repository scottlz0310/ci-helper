"""
パターンマッチング機能のユニットテスト

パターンマッチング精度とアルゴリズムの正確性をテストします。
"""

from datetime import datetime

import pytest

from src.ci_helper.ai.models import Pattern
from src.ci_helper.ai.pattern_matcher import Match, PatternMatcher


class TestPatternMatcher:
    """パターンマッチャーのテスト"""

    @pytest.fixture
    def pattern_matcher(self):
        """パターンマッチャーのインスタンス"""
        return PatternMatcher(context_window=50)

    @pytest.fixture
    def sample_patterns(self):
        """テスト用パターンのリスト"""
        return [
            Pattern(
                id="permission_error",
                name="権限エラー",
                category="permission",
                regex_patterns=[r"permission\s+denied", r"access\s+denied"],
                keywords=["permission", "denied", "access"],
                context_requirements=["docker", "file"],
                confidence_base=0.8,
                success_rate=0.9,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Pattern(
                id="npm_error",
                name="NPMエラー",
                category="dependency",
                regex_patterns=[r"npm\s+ERR!", r"ENOENT.*package\.json"],
                keywords=["npm", "package.json", "ENOENT"],
                context_requirements=["node", "javascript"],
                confidence_base=0.7,
                success_rate=0.85,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Pattern(
                id="python_syntax",
                name="Python構文エラー",
                category="syntax",
                regex_patterns=[r"SyntaxError:", r"IndentationError:"],
                keywords=["SyntaxError", "IndentationError", "python"],
                context_requirements=["python", ".py"],
                confidence_base=0.9,
                success_rate=0.95,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

    @pytest.fixture
    def sample_log_text(self):
        """テスト用ログテキスト"""
        return """
STEP: Run tests
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'

Error: permission denied while trying to connect to the Docker daemon socket
at /var/run/docker.sock: Get "http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/json":
dial unix /var/run/docker.sock: connect: permission denied

File "test.py", line 42
    print("Hello World"
                      ^
SyntaxError: EOL while scanning string literal
"""

    def test_match_regex_patterns_success(self, pattern_matcher, sample_patterns, sample_log_text):
        """正規表現パターンマッチングの成功テスト"""
        matches = pattern_matcher.match_regex_patterns(sample_log_text, sample_patterns)

        # マッチが見つかることを確認
        assert len(matches) > 0

        # 各マッチの基本属性を確認
        for match in matches:
            assert isinstance(match, Match)
            assert match.pattern_id in ["permission_error", "npm_error", "python_syntax"]
            assert match.match_type == "regex"
            assert match.start_position >= 0
            assert match.end_position > match.start_position
            assert len(match.matched_text) > 0
            assert 0.0 <= match.confidence <= 1.0

        # 特定のパターンがマッチしていることを確認
        pattern_ids = {match.pattern_id for match in matches}
        assert "npm_error" in pattern_ids  # NPMエラーパターンがマッチするはず
        assert "permission_error" in pattern_ids  # 権限エラーパターンがマッチするはず
        assert "python_syntax" in pattern_ids  # Python構文エラーパターンがマッチするはず

    def test_match_keyword_patterns_success(self, pattern_matcher, sample_patterns, sample_log_text):
        """キーワードパターンマッチングの成功テスト"""
        matches = pattern_matcher.match_keyword_patterns(sample_log_text, sample_patterns)

        # マッチが見つかることを確認
        assert len(matches) > 0

        # 各マッチの基本属性を確認
        for match in matches:
            assert isinstance(match, Match)
            assert match.pattern_id in ["permission_error", "npm_error", "python_syntax"]
            assert match.match_type == "keyword"
            assert match.start_position >= 0
            assert match.end_position > match.start_position
            assert len(match.matched_text) > 0
            assert 0.0 <= match.confidence <= 1.0

    def test_extract_error_context(self, pattern_matcher, sample_log_text):
        """エラーコンテキスト抽出のテスト"""
        # "permission denied" の位置を見つける
        position = sample_log_text.find("permission denied")
        assert position != -1

        context_before, context_after = pattern_matcher.extract_error_context(sample_log_text, position)

        # コンテキストが抽出されることを確認
        assert len(context_before) > 0
        assert len(context_after) > 0

        # コンテキストに関連する内容が含まれることを確認
        combined_context = context_before + context_after
        assert "docker" in combined_context.lower() or "permission" in combined_context.lower()

    def test_calculate_match_strength(self, pattern_matcher, sample_patterns):
        """マッチ強度計算のテスト"""
        # テスト用のマッチオブジェクトを作成
        test_match = Match(
            pattern_id="permission_error",
            match_type="regex",
            start_position=100,
            end_position=120,
            matched_text="permission denied",
            confidence=0.8,
            context_before="Error:",
            context_after="while trying to connect",
        )

        pattern = sample_patterns[0]  # permission_error パターン
        strength = pattern_matcher.calculate_match_strength(test_match, pattern)

        # 強度が適切な範囲内であることを確認
        assert 0.0 <= strength <= 1.0
        assert strength == test_match.confidence  # 既に計算済みの信頼度を返すはず

    def test_get_match_summary(self, pattern_matcher, sample_patterns, sample_log_text):
        """マッチサマリー取得のテスト"""
        regex_matches = pattern_matcher.match_regex_patterns(sample_log_text, sample_patterns)
        keyword_matches = pattern_matcher.match_keyword_patterns(sample_log_text, sample_patterns)
        all_matches = regex_matches + keyword_matches

        summary = pattern_matcher.get_match_summary(all_matches)

        # サマリーの基本構造を確認
        assert "total_matches" in summary
        assert "regex_matches" in summary
        assert "keyword_matches" in summary
        assert "average_confidence" in summary
        assert "patterns_matched" in summary
        assert "highest_confidence" in summary
        assert "lowest_confidence" in summary

        # 値の妥当性を確認
        assert summary["total_matches"] == len(all_matches)
        assert summary["regex_matches"] == len(regex_matches)
        assert summary["keyword_matches"] == len(keyword_matches)
        assert 0.0 <= summary["average_confidence"] <= 1.0
        assert len(summary["patterns_matched"]) > 0

        if all_matches:
            assert summary["highest_confidence"] >= summary["lowest_confidence"]

    def test_empty_patterns_list(self, pattern_matcher, sample_log_text):
        """空のパターンリストでのテスト"""
        matches = pattern_matcher.match_regex_patterns(sample_log_text, [])
        assert len(matches) == 0

        matches = pattern_matcher.match_keyword_patterns(sample_log_text, [])
        assert len(matches) == 0

    def test_empty_log_text(self, pattern_matcher, sample_patterns):
        """空のログテキストでのテスト"""
        matches = pattern_matcher.match_regex_patterns("", sample_patterns)
        assert len(matches) == 0

        matches = pattern_matcher.match_keyword_patterns("", sample_patterns)
        assert len(matches) == 0

    def test_invalid_regex_pattern(self, pattern_matcher):
        """不正な正規表現パターンのテスト"""
        invalid_pattern = Pattern(
            id="invalid_regex",
            name="不正な正規表現",
            category="test",
            regex_patterns=[r"[invalid(regex"],  # 不正な正規表現
            keywords=[],
            context_requirements=[],
            confidence_base=0.5,
            success_rate=0.5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 不正な正規表現でもクラッシュしないことを確認
        matches = pattern_matcher.match_regex_patterns("test text", [invalid_pattern])
        assert len(matches) == 0  # マッチしないが、エラーも発生しない

    def test_pattern_with_no_regex_or_keywords(self, pattern_matcher):
        """正規表現もキーワードもないパターンのテスト"""
        empty_pattern = Pattern(
            id="empty_pattern",
            name="空のパターン",
            category="test",
            regex_patterns=[],
            keywords=[],
            context_requirements=[],
            confidence_base=0.5,
            success_rate=0.5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        matches = pattern_matcher.match_regex_patterns("test text", [empty_pattern])
        assert len(matches) == 0

        matches = pattern_matcher.match_keyword_patterns("test text", [empty_pattern])
        assert len(matches) == 0

    def test_case_insensitive_matching(self, pattern_matcher):
        """大文字小文字を区別しないマッチングのテスト"""
        pattern = Pattern(
            id="case_test",
            name="大文字小文字テスト",
            category="test",
            regex_patterns=[r"ERROR"],
            keywords=["ERROR"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        test_texts = ["error occurred", "ERROR occurred", "Error occurred", "ErRoR occurred"]

        for text in test_texts:
            regex_matches = pattern_matcher.match_regex_patterns(text, [pattern])
            keyword_matches = pattern_matcher.match_keyword_patterns(text, [pattern])

            # 大文字小文字に関係なくマッチすることを確認
            assert len(regex_matches) > 0, f"正規表現マッチが失敗: {text}"
            assert len(keyword_matches) > 0, f"キーワードマッチが失敗: {text}"

    def test_word_boundary_detection(self, pattern_matcher):
        """単語境界検出のテスト"""
        pattern = Pattern(
            id="word_boundary_test",
            name="単語境界テスト",
            category="test",
            regex_patterns=[],
            keywords=["test"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 単語境界がある場合
        matches_with_boundary = pattern_matcher.match_keyword_patterns("this is a test case", [pattern])
        assert len(matches_with_boundary) > 0

        # 単語境界がない場合
        matches_without_boundary = pattern_matcher.match_keyword_patterns("this is a testing case", [pattern])
        # "testing" に含まれる "test" もマッチするが、信頼度は低くなるはず
        if matches_without_boundary:
            # 単語境界がない場合の信頼度が低いことを確認
            boundary_confidence = matches_with_boundary[0].confidence
            no_boundary_confidence = matches_without_boundary[0].confidence
            assert boundary_confidence >= no_boundary_confidence

    def test_context_requirements_matching(self, pattern_matcher):
        """コンテキスト要件マッチングのテスト"""
        pattern_with_context = Pattern(
            id="context_test",
            name="コンテキストテスト",
            category="test",
            regex_patterns=[r"error"],
            keywords=[],
            context_requirements=["docker", "container"],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # コンテキスト要件を満たすテキスト
        text_with_context = "Docker container error occurred while running the application"
        matches_with_context = pattern_matcher.match_regex_patterns(text_with_context, [pattern_with_context])

        # コンテキスト要件を満たさないテキスト
        text_without_context = "Simple error occurred in the application"
        matches_without_context = pattern_matcher.match_regex_patterns(text_without_context, [pattern_with_context])

        # 両方でマッチするが、コンテキスト要件を満たす方が高い信頼度を持つはず
        assert len(matches_with_context) > 0
        assert len(matches_without_context) > 0

        if matches_with_context and matches_without_context:
            assert matches_with_context[0].confidence >= matches_without_context[0].confidence

    def test_multiple_regex_patterns(self, pattern_matcher):
        """複数の正規表現パターンのテスト"""
        pattern = Pattern(
            id="multi_regex_test",
            name="複数正規表現テスト",
            category="test",
            regex_patterns=[r"error\s+\d+", r"failure\s+code", r"exception\s+thrown"],
            keywords=[],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        test_cases = [
            "error 404 occurred",
            "failure code detected",
            "exception thrown in module",
            "error 500 and failure code both happened",
        ]

        for text in test_cases:
            matches = pattern_matcher.match_regex_patterns(text, [pattern])
            assert len(matches) > 0, f"マッチが見つかりません: {text}"

            # 複数のパターンがマッチする場合、複数のマッチが返されることを確認
            if "error 500 and failure code" in text:
                assert len(matches) >= 2, "複数パターンマッチが検出されませんでした"

    def test_clear_cache(self, pattern_matcher, sample_patterns):
        """キャッシュクリア機能のテスト"""
        # 最初にパターンマッチングを実行してキャッシュを作成
        pattern_matcher.match_regex_patterns("test error", sample_patterns)

        # キャッシュが作成されていることを確認
        assert len(pattern_matcher._compiled_patterns) > 0

        # キャッシュをクリア
        pattern_matcher.clear_cache()

        # キャッシュがクリアされていることを確認
        assert len(pattern_matcher._compiled_patterns) == 0

    def test_match_positions_accuracy(self, pattern_matcher):
        """マッチ位置の正確性テスト"""
        pattern = Pattern(
            id="position_test",
            name="位置テスト",
            category="test",
            regex_patterns=[r"ERROR"],
            keywords=["ERROR"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        text = "INFO: Starting application\nERROR: Connection failed\nWARNING: Retrying"
        expected_position = text.find("ERROR")

        regex_matches = pattern_matcher.match_regex_patterns(text, [pattern])
        keyword_matches = pattern_matcher.match_keyword_patterns(text, [pattern])

        # 正規表現マッチの位置確認
        assert len(regex_matches) > 0
        assert regex_matches[0].start_position == expected_position
        assert regex_matches[0].end_position == expected_position + len("ERROR")
        assert regex_matches[0].matched_text == "ERROR"

        # キーワードマッチの位置確認
        assert len(keyword_matches) > 0
        assert keyword_matches[0].start_position == expected_position

    def test_performance_with_large_text(self, pattern_matcher, sample_patterns):
        """大きなテキストでのパフォーマンステスト"""
        # 大きなテキストを生成（実際のログファイルを模擬）
        large_text = "\n".join([f"Line {i}: Some log message with various content" for i in range(1000)])
        # エラーメッセージを途中に挿入
        large_text += "\nnpm ERR! code ENOENT\nnpm ERR! path /package.json"
        large_text += "\n" + "\n".join([f"Line {i}: More log content after error" for i in range(1000, 2000)])

        # パフォーマンステスト（タイムアウトしないことを確認）
        import time

        start_time = time.time()

        regex_matches = pattern_matcher.match_regex_patterns(large_text, sample_patterns)
        keyword_matches = pattern_matcher.match_keyword_patterns(large_text, sample_patterns)

        end_time = time.time()
        execution_time = end_time - start_time

        # 実行時間が合理的であることを確認（10秒以内）
        assert execution_time < 10.0, f"実行時間が長すぎます: {execution_time}秒"

        # マッチが見つかることを確認
        assert len(regex_matches) > 0 or len(keyword_matches) > 0

    def test_unicode_text_handling(self, pattern_matcher):
        """Unicode文字を含むテキストの処理テスト"""
        pattern = Pattern(
            id="unicode_test",
            name="Unicodeテスト",
            category="test",
            regex_patterns=[r"エラー", r"失敗"],
            keywords=["エラー", "失敗", "例外"],
            context_requirements=[],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        unicode_text = "アプリケーションでエラーが発生しました。処理に失敗しました。例外がスローされました。"

        regex_matches = pattern_matcher.match_regex_patterns(unicode_text, [pattern])
        keyword_matches = pattern_matcher.match_keyword_patterns(unicode_text, [pattern])

        # Unicode文字でもマッチすることを確認
        assert len(regex_matches) > 0, "Unicode正規表現マッチが失敗"
        assert len(keyword_matches) > 0, "Unicodeキーワードマッチが失敗"

        # マッチしたテキストが正しいことを確認
        regex_matched_texts = {match.matched_text for match in regex_matches}
        keyword_matched_texts = {match.matched_text for match in keyword_matches}

        assert "エラー" in regex_matched_texts or "失敗" in regex_matched_texts
        assert any(keyword in keyword_matched_texts for keyword in ["エラー", "失敗", "例外"])
