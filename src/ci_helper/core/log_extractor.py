"""ログ解析と失敗抽出システム

actの実行ログから失敗情報を抽出し、構造化されたデータとして提供します。
"""

from __future__ import annotations

import re

from ..core.exceptions import LogParsingError
from ..core.models import Failure, FailureType


class LogExtractor:
    """ログから失敗情報を抽出するクラス"""

    def __init__(self, context_lines: int = 3):
        """ログ抽出器を初期化

        Args:
            context_lines: エラー前後に取得するコンテキスト行数

        """
        self.context_lines = context_lines
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """エラーパターンの正規表現をコンパイル"""
        # エラーパターンの定義
        self.error_patterns = {
            FailureType.ERROR: [
                # 一般的なエラーパターン
                re.compile(r"^Error:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^ERROR:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^\[ERROR\]\s*(.+)$", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^.*error:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
                # GitHub Actions特有のエラー
                re.compile(r"^##\[error\](.+)$", re.MULTILINE),
                # プロセス終了エラー
                re.compile(r"Process completed with exit code (\d+)", re.MULTILINE),
                # コマンド実行エラー
                re.compile(r"^.*: command not found$", re.MULTILINE),
                re.compile(r"^.*: No such file or directory$", re.MULTILINE),
            ],
            FailureType.ASSERTION: [
                # テストアサーション失敗
                re.compile(r"AssertionError:\s*(.+)", re.MULTILINE),
                re.compile(r"assert\s+(.+)\s+failed", re.MULTILINE | re.IGNORECASE),
                re.compile(r"Expected:\s*(.+)", re.MULTILINE),
                re.compile(r"Actual:\s*(.+)", re.MULTILINE),
                # Jest/Vitest等のテストフレームワーク
                re.compile(r"^\s*✕\s*(.+)$", re.MULTILINE),
                re.compile(r"^\s*FAIL\s+(.+)$", re.MULTILINE),
                # pytest
                re.compile(r"^>?\s*assert\s+(.+)$", re.MULTILINE),
                re.compile(r"^E\s+(.+)$", re.MULTILINE),
            ],
            FailureType.TIMEOUT: [
                # タイムアウトエラー
                re.compile(r"timeout", re.MULTILINE | re.IGNORECASE),
                re.compile(r"timed out", re.MULTILINE | re.IGNORECASE),
                re.compile(r"exceeded.*timeout", re.MULTILINE | re.IGNORECASE),
                re.compile(r"killed.*timeout", re.MULTILINE | re.IGNORECASE),
            ],
            FailureType.BUILD_FAILURE: [
                # ビルドエラー
                re.compile(r"^Build failed", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^Compilation failed", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^.*: compilation terminated", re.MULTILINE),
                # npm/yarn/pnpm エラー
                re.compile(r"^npm ERR!\s*(.+)$", re.MULTILINE),
                re.compile(r"^yarn error\s*(.+)$", re.MULTILINE),
                re.compile(r"^pnpm ERR!\s*(.+)$", re.MULTILINE),
                # Python ビルドエラー
                re.compile(r"^SyntaxError:\s*(.+)$", re.MULTILINE),
                re.compile(r"^ImportError:\s*(.+)$", re.MULTILINE),
                re.compile(r"^ModuleNotFoundError:\s*(.+)$", re.MULTILINE),
            ],
            FailureType.TEST_FAILURE: [
                # テスト失敗
                re.compile(r"^Tests failed", re.MULTILINE | re.IGNORECASE),
                re.compile(r"^\d+\s+failing", re.MULTILINE),
                re.compile(r"^\d+\s+failed", re.MULTILINE),
                re.compile(r"^FAILED\s+(.+)$", re.MULTILINE),
                # カバレッジ失敗
                re.compile(r"Coverage threshold not met", re.MULTILINE | re.IGNORECASE),
            ],
        }

        # スタックトレースパターン
        self.stack_trace_patterns = [
            # Python スタックトレース
            re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE),
            # JavaScript スタックトレース
            re.compile(r"^\s*at\s+.*\(.*:\d+:\d+\)$", re.MULTILINE),
            # Java スタックトレース
            re.compile(r"^\s*at\s+[\w.]+\(.*\.java:\d+\)$", re.MULTILINE),
            # C# スタックトレース
            re.compile(r"^\s*at\s+.*\s+in\s+.*:\d+$", re.MULTILINE),
        ]

        # ファイルパスと行番号の抽出パターン
        self.file_line_patterns = [
            # 一般的なファイル:行番号パターン
            re.compile(r"([^\s:]+):(\d+):?(\d+)?"),
            # GitHub Actions アノテーション
            re.compile(r"::error file=([^,]+),line=(\d+)"),
            # pytest エラー
            re.compile(r"([^\s]+\.py):(\d+): in"),
        ]

    def extract_failures(self, log_content: str) -> list[Failure]:
        """ログから失敗情報を抽出

        Args:
            log_content: ログファイルの内容

        Returns:
            抽出された失敗情報のリスト

        Raises:
            LogParsingError: ログ解析に失敗した場合

        """
        if not log_content or not log_content.strip():
            return []

        try:
            failures: list[Failure] = []
            log_lines = log_content.splitlines()

            # 各失敗タイプのパターンをチェック（より具体的なものから先に）
            pattern_order = [
                FailureType.ASSERTION,
                FailureType.TIMEOUT,
                FailureType.BUILD_FAILURE,
                FailureType.TEST_FAILURE,
                FailureType.ERROR,  # 最後に一般的なエラーをチェック
            ]

            for failure_type in pattern_order:
                if failure_type in self.error_patterns:
                    patterns = self.error_patterns[failure_type]
                    for pattern in patterns:
                        matches = pattern.finditer(log_content)
                        for match in matches:
                            failure = self._create_failure_from_match(match, failure_type, log_lines, log_content)
                            if failure:
                                failures.append(failure)

            # 重複を除去（同じメッセージと位置の失敗）
            unique_failures = self._deduplicate_failures(failures)

            return unique_failures

        except Exception as e:
            raise LogParsingError(
                f"ログ解析中にエラーが発生しました: {e}",
                "ログファイルが破損している可能性があります。新しい実行を試してください。",
            ) from e

    def _create_failure_from_match(
        self,
        match: re.Match[str],
        failure_type: FailureType,
        log_lines: list[str],
        full_content: str,
    ) -> Failure | None:
        """マッチした結果から失敗オブジェクトを作成

        Args:
            match: 正規表現のマッチ結果
            failure_type: 失敗タイプ
            log_lines: ログの行リスト
            full_content: ログ全体の内容

        Returns:
            失敗オブジェクト（作成できない場合はNone）

        """
        try:
            # マッチした行番号を取得
            match_start = match.start()
            line_number = full_content[:match_start].count("\n") + 1

            # エラーメッセージを抽出
            message = match.group(1) if match.groups() else match.group(0)
            message = message.strip()

            # ファイルパスと行番号を抽出
            file_path, file_line = self._extract_file_info(message)

            # コンテキスト行を取得
            context_before, context_after = self._get_context_lines(log_lines, line_number - 1, self.context_lines)

            # スタックトレースを検索
            stack_trace = self._extract_stack_trace(full_content, match_start)

            return Failure(
                type=failure_type,
                message=message,
                file_path=file_path,
                line_number=file_line,
                context_before=context_before,
                context_after=context_after,
                stack_trace=stack_trace,
            )

        except Exception:
            # 個別の失敗作成でエラーが発生した場合はスキップ
            return None

    def _extract_file_info(self, message: str) -> tuple[str | None, int | None]:
        """メッセージからファイルパスと行番号を抽出

        Args:
            message: エラーメッセージ

        Returns:
            (ファイルパス, 行番号) のタプル

        """
        for pattern in self.file_line_patterns:
            match = pattern.search(message)
            if match:
                file_path = match.group(1)
                try:
                    line_number = int(match.group(2))
                    return file_path, line_number
                except (ValueError, IndexError):
                    return file_path, None

        return None, None

    def _get_context_lines(
        self,
        log_lines: list[str],
        center_line: int,
        context_count: int,
    ) -> tuple[list[str], list[str]]:
        """指定した行の前後のコンテキスト行を取得

        Args:
            log_lines: ログの行リスト
            center_line: 中心となる行番号（0ベース）
            context_count: 前後に取得する行数

        Returns:
            (前のコンテキスト行, 後のコンテキスト行) のタプル

        """
        if not log_lines or center_line < 0 or center_line >= len(log_lines):
            return [], []

        start_before = max(0, center_line - context_count)
        end_before = center_line

        start_after = center_line + 1
        end_after = min(len(log_lines), center_line + 1 + context_count)

        context_before = log_lines[start_before:end_before]
        context_after = log_lines[start_after:end_after]

        return context_before, context_after

    def _extract_stack_trace(self, content: str, error_position: int) -> str | None:
        """エラー位置周辺からスタックトレースを抽出

        Args:
            content: ログ全体の内容
            error_position: エラーが発生した位置

        Returns:
            スタックトレース（見つからない場合はNone）

        """
        # エラー位置から前後の範囲でスタックトレースを検索
        search_start = max(0, error_position - 2000)  # 2KB前から
        search_end = min(len(content), error_position + 2000)  # 2KB後まで
        search_content = content[search_start:search_end]

        for pattern in self.stack_trace_patterns:
            match = pattern.search(search_content)
            if match:
                # スタックトレースの開始位置を見つけた場合、
                # そこから複数行にわたるスタックトレースを抽出
                stack_start = match.start()
                lines = search_content[stack_start:].split("\n")

                stack_lines: list[str] = []
                for line in lines:
                    # スタックトレースの行かどうかを判定
                    stripped = line.strip()
                    has_at = stripped.startswith("at ")
                    has_file = stripped.startswith("File ")
                    has_traceback = "Traceback" in line
                    matches_at = re.match(r"^\s*at\s+", line) is not None
                    matches_file = re.match(r'^\s*File\s+".*", line \d+', line) is not None
                    is_stack_line = has_at or has_file or has_traceback or matches_at or matches_file
                    if is_stack_line:
                        stack_lines.append(line)
                    elif stack_lines and not stripped:
                        # 空行はスタックトレースの一部として含める
                        stack_lines.append(line)
                    elif stack_lines:
                        # スタックトレース以外の行が出現したら終了
                        break

                if stack_lines:
                    return "\n".join(stack_lines)

        return None

    def _deduplicate_failures(self, failures: list[Failure]) -> list[Failure]:
        """重複する失敗を除去

        Args:
            failures: 失敗のリスト

        Returns:
            重複を除去した失敗のリスト

        """
        seen: set[tuple[str, str | None, int | None]] = set()
        unique_failures: list[Failure] = []

        for failure in failures:
            # メッセージ、ファイルパス、行番号の組み合わせで重複判定
            key = (failure.message, failure.file_path, failure.line_number)
            if key not in seen:
                seen.add(key)
                unique_failures.append(failure)

        return unique_failures

    def parse_error_patterns(
        self,
        content: str,
        custom_patterns: dict[str, list[str]] | None = None,
    ) -> list[tuple[FailureType, str]]:
        """カスタムパターンを含むエラーパターンの解析

        Args:
            content: 解析対象のコンテンツ
            custom_patterns: カスタムエラーパターン（失敗タイプ名 -> パターンリスト）

        Returns:
            (失敗タイプ, マッチしたテキスト) のタプルのリスト

        """
        matches: list[tuple[FailureType, str]] = []

        # デフォルトパターンをチェック
        for failure_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    matches.append((failure_type, match.group(0)))

        # カスタムパターンをチェック
        if custom_patterns:
            for type_name, pattern_strings in custom_patterns.items():
                try:
                    failure_type = FailureType(type_name.lower())
                except ValueError:
                    failure_type = FailureType.UNKNOWN

                for pattern_string in pattern_strings:
                    try:
                        pattern = re.compile(pattern_string, re.MULTILINE | re.IGNORECASE)
                        for match in pattern.finditer(content):
                            matches.append((failure_type, match.group(0)))
                    except re.error:
                        # 無効な正規表現はスキップ
                        continue

        return matches

    def get_context_lines(self, content: str, line_number: int, context: int = 3) -> str:
        """指定した行の前後のコンテキストを取得（公開メソッド）

        Args:
            content: コンテンツ
            line_number: 行番号（1ベース）
            context: 前後に取得する行数

        Returns:
            コンテキストを含む文字列

        """
        lines = content.splitlines()
        if line_number < 1 or line_number > len(lines):
            return ""

        # 0ベースに変換
        center_line = line_number - 1
        context_before, context_after = self._get_context_lines(lines, center_line, context)

        # 結果を組み立て
        result_lines: list[str] = []

        # 前のコンテキスト
        start_line = max(1, line_number - len(context_before))
        for i, line in enumerate(context_before):
            result_lines.append(f"{start_line + i:4d}: {line}")

        # 中心行
        if center_line < len(lines):
            result_lines.append(f"{line_number:4d}:>{lines[center_line]}")

        # 後のコンテキスト
        for i, line in enumerate(context_after):
            result_lines.append(f"{line_number + 1 + i:4d}: {line}")

        return "\n".join(result_lines)
