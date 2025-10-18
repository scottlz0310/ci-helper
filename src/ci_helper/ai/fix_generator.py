"""
修正提案生成機能

AI分析結果に基づいて具体的な修正提案を生成し、コード差分や優先度判定を行います。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .exceptions import AIError
from .models import AnalysisResult, CodeChange, FixSuggestion, Priority, Severity
from .prompts import PromptManager

logger = logging.getLogger(__name__)


class FixSuggestionGenerator:
    """修正提案生成クラス

    AI分析結果から具体的な修正提案を生成し、コード差分や優先度を判定します。
    """

    def __init__(self, prompt_manager: PromptManager):
        """修正提案生成器を初期化

        Args:
            prompt_manager: プロンプト管理インスタンス
        """
        self.prompt_manager = prompt_manager
        self.priority_weights = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4,
        }
        self.effort_patterns = {
            "minutes": r"(\d+)\s*(?:分|minutes?)",
            "hours": r"(\d+)\s*(?:時間|hours?)",
            "days": r"(\d+)\s*(?:日|days?)",
        }

    def generate_fix_suggestions(
        self, analysis_result: AnalysisResult, log_content: str, project_context: dict[str, Any] | None = None
    ) -> list[FixSuggestion]:
        """分析結果から修正提案を生成

        Args:
            analysis_result: AI分析結果
            log_content: 元のログ内容
            project_context: プロジェクトコンテキスト（ファイル構造など）

        Returns:
            修正提案のリスト
        """
        logger.info("修正提案を生成中...")

        try:
            # 根本原因から修正提案を生成
            suggestions = []

            for root_cause in analysis_result.root_causes:
                suggestion = self._create_fix_suggestion_from_cause(root_cause, log_content, project_context)
                if suggestion:
                    suggestions.append(suggestion)

            # 一般的な修正提案も追加
            general_suggestions = self._generate_general_fixes(analysis_result, log_content, project_context)
            suggestions.extend(general_suggestions)

            # 優先度でソート
            suggestions.sort(key=lambda x: self._get_priority_score(x.priority), reverse=True)

            logger.info("修正提案を %d 個生成しました", len(suggestions))
            return suggestions

        except Exception as e:
            logger.error("修正提案の生成に失敗: %s", e)
            raise AIError(f"修正提案の生成に失敗しました: {e}") from e

    def _create_fix_suggestion_from_cause(
        self, root_cause: Any, log_content: str, project_context: dict[str, Any] | None = None
    ) -> FixSuggestion | None:
        """根本原因から修正提案を作成

        Args:
            root_cause: 根本原因
            log_content: ログ内容
            project_context: プロジェクトコンテキスト

        Returns:
            修正提案（作成できない場合はNone）
        """
        try:
            # エラーカテゴリに基づく修正提案
            category = getattr(root_cause, "category", "unknown")
            description = getattr(root_cause, "description", "")
            file_path = getattr(root_cause, "file_path", None)
            line_number = getattr(root_cause, "line_number", None)
            severity = getattr(root_cause, "severity", Severity.MEDIUM)

            # カテゴリ別の修正提案生成
            if category == "dependency":
                return self._create_dependency_fix(description, file_path, severity)
            elif category == "syntax":
                return self._create_syntax_fix(description, file_path, line_number, severity)
            elif category == "configuration":
                return self._create_config_fix(description, file_path, severity)
            elif category == "test":
                return self._create_test_fix(description, file_path, line_number, severity)
            elif category == "build":
                return self._create_build_fix(description, file_path, severity)
            else:
                return self._create_general_fix(description, file_path, line_number, severity)

        except Exception as e:
            logger.warning("根本原因からの修正提案作成に失敗: %s", e)
            return None

    def _create_dependency_fix(self, description: str, file_path: str | None, severity: Severity) -> FixSuggestion:
        """依存関係エラーの修正提案を作成"""
        title = "依存関係の修正"

        # パッケージマネージャーを検出
        if "npm" in description.lower() or "package.json" in description.lower():
            fix_description = "Node.js依存関係を更新してください"
            code_changes = [
                CodeChange(
                    file_path="package.json",
                    line_start=1,
                    line_end=1,
                    old_code="// 依存関係の問題",
                    new_code="// npm install または npm update を実行",
                    description="依存関係を更新",
                )
            ]
        elif "pip" in description.lower() or "requirements.txt" in description.lower():
            fix_description = "Python依存関係を更新してください"
            code_changes = [
                CodeChange(
                    file_path="requirements.txt",
                    line_start=1,
                    line_end=1,
                    old_code="# 依存関係の問題",
                    new_code="# pip install -r requirements.txt を実行",
                    description="依存関係を更新",
                )
            ]
        else:
            fix_description = "依存関係を確認し、必要なパッケージをインストールしてください"
            code_changes = []

        priority = self._severity_to_priority(severity)
        effort = self._estimate_dependency_effort(description)

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=priority,
            estimated_effort=effort,
            confidence=0.8,
            references=["https://docs.npmjs.com/", "https://pip.pypa.io/"],
        )

    def _create_syntax_fix(
        self, description: str, file_path: str | None, line_number: int | None, severity: Severity
    ) -> FixSuggestion:
        """構文エラーの修正提案を作成"""
        title = "構文エラーの修正"

        # 構文エラーの種類を判定
        if "missing" in description.lower() and (";" in description or "semicolon" in description):
            fix_description = "セミコロンを追加してください"
            old_code = "console.log('Hello')"
            new_code = "console.log('Hello');"
        elif "missing" in description.lower() and (")" in description or "parenthesis" in description):
            fix_description = "閉じ括弧を追加してください"
            old_code = "function test("
            new_code = "function test()"
        elif "indentation" in description.lower():
            fix_description = "インデントを修正してください"
            old_code = "if True:\nprint('Hello')"
            new_code = "if True:\n    print('Hello')"
        else:
            fix_description = f"構文エラーを修正してください: {description}"
            old_code = "# 構文エラー"
            new_code = "# 修正されたコード"

        code_changes = []
        if file_path and line_number:
            code_changes.append(
                CodeChange(
                    file_path=file_path,
                    line_start=line_number,
                    line_end=line_number,
                    old_code=old_code,
                    new_code=new_code,
                    description=fix_description,
                )
            )

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=Priority.HIGH,  # 構文エラーは通常高優先度
            estimated_effort="5-10分",
            confidence=0.9,
            references=[],
        )

    def _create_config_fix(self, description: str, file_path: str | None, severity: Severity) -> FixSuggestion:
        """設定エラーの修正提案を作成"""
        title = "設定の修正"

        # 設定ファイルの種類を判定
        if "environment" in description.lower() or "env" in description.lower():
            fix_description = "環境変数を設定してください"
            code_changes = [
                CodeChange(
                    file_path=".env",
                    line_start=1,
                    line_end=1,
                    old_code="# 環境変数が未設定",
                    new_code="# 必要な環境変数を追加\nAPI_KEY=your_api_key_here",
                    description="環境変数を追加",
                )
            ]
        elif "config" in description.lower():
            fix_description = "設定ファイルを修正してください"
            code_changes = []
        else:
            fix_description = f"設定を確認してください: {description}"
            code_changes = []

        priority = self._severity_to_priority(severity)
        effort = "10-30分"

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=priority,
            estimated_effort=effort,
            confidence=0.7,
            references=[],
        )

    def _create_test_fix(
        self, description: str, file_path: str | None, line_number: int | None, severity: Severity
    ) -> FixSuggestion:
        """テストエラーの修正提案を作成"""
        title = "テストの修正"

        # テストエラーの種類を判定
        if "assertion" in description.lower():
            fix_description = "アサーションを修正してください"
            old_code = "assert result == expected"
            new_code = "assert result == expected, f'Expected {expected}, got {result}'"
        elif "timeout" in description.lower():
            fix_description = "テストのタイムアウトを調整してください"
            old_code = "@pytest.mark.timeout(5)"
            new_code = "@pytest.mark.timeout(30)"
        else:
            fix_description = f"テストを修正してください: {description}"
            old_code = "# テストエラー"
            new_code = "# 修正されたテスト"

        code_changes = []
        if file_path and line_number:
            code_changes.append(
                CodeChange(
                    file_path=file_path,
                    line_start=line_number,
                    line_end=line_number,
                    old_code=old_code,
                    new_code=new_code,
                    description=fix_description,
                )
            )

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=Priority.MEDIUM,
            estimated_effort="15-45分",
            confidence=0.6,
            references=["https://docs.pytest.org/"],
        )

    def _create_build_fix(self, description: str, file_path: str | None, severity: Severity) -> FixSuggestion:
        """ビルドエラーの修正提案を作成"""
        title = "ビルドの修正"

        # ビルドエラーの種類を判定
        if "memory" in description.lower() or "heap" in description.lower():
            fix_description = "メモリ設定を増やしてください"
            code_changes = [
                CodeChange(
                    file_path="package.json",
                    line_start=1,
                    line_end=1,
                    old_code='"build": "react-scripts build"',
                    new_code='"build": "NODE_OPTIONS=--max_old_space_size=4096 react-scripts build"',
                    description="メモリ制限を増加",
                )
            ]
        elif "typescript" in description.lower() or "tsc" in description.lower():
            fix_description = "TypeScript設定を確認してください"
            code_changes = []
        else:
            fix_description = f"ビルド設定を確認してください: {description}"
            code_changes = []

        priority = self._severity_to_priority(severity)
        effort = "30分-2時間"

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=priority,
            estimated_effort=effort,
            confidence=0.5,
            references=[],
        )

    def _create_general_fix(
        self, description: str, file_path: str | None, line_number: int | None, severity: Severity
    ) -> FixSuggestion:
        """一般的な修正提案を作成"""
        title = "一般的な修正"
        fix_description = f"以下の問題を確認してください: {description}"

        code_changes = []
        if file_path:
            code_changes.append(
                CodeChange(
                    file_path=file_path,
                    line_start=line_number or 1,
                    line_end=line_number or 1,
                    old_code="# 問題のあるコード",
                    new_code="# 修正されたコード",
                    description="コードを確認・修正",
                )
            )

        priority = self._severity_to_priority(severity)
        effort = "不明"

        return FixSuggestion(
            title=title,
            description=fix_description,
            code_changes=code_changes,
            priority=priority,
            estimated_effort=effort,
            confidence=0.3,
            references=[],
        )

    def _generate_general_fixes(
        self, analysis_result: AnalysisResult, log_content: str, project_context: dict[str, Any] | None = None
    ) -> list[FixSuggestion]:
        """一般的な修正提案を生成"""
        suggestions = []

        # ログ内容から一般的な問題を検出
        log_lower = log_content.lower()

        # 権限エラー
        if "permission denied" in log_lower or "access denied" in log_lower:
            suggestions.append(
                FixSuggestion(
                    title="権限エラーの修正",
                    description="ファイルやディレクトリの権限を確認してください",
                    priority=Priority.HIGH,
                    estimated_effort="5-15分",
                    confidence=0.8,
                    references=["https://docs.docker.com/engine/reference/run/#user"],
                )
            )

        # ネットワークエラー
        if "network" in log_lower and "error" in log_lower:
            suggestions.append(
                FixSuggestion(
                    title="ネットワーク接続の確認",
                    description="インターネット接続とファイアウォール設定を確認してください",
                    priority=Priority.MEDIUM,
                    estimated_effort="10-30分",
                    confidence=0.6,
                    references=[],
                )
            )

        # ディスク容量エラー
        if "no space left" in log_lower or "disk full" in log_lower:
            suggestions.append(
                FixSuggestion(
                    title="ディスク容量の確保",
                    description="不要なファイルを削除してディスク容量を確保してください",
                    priority=Priority.HIGH,
                    estimated_effort="15-60分",
                    confidence=0.9,
                    references=[],
                )
            )

        return suggestions

    def _severity_to_priority(self, severity: Severity) -> Priority:
        """重要度を優先度に変換"""
        mapping = {
            Severity.CRITICAL: Priority.URGENT,
            Severity.HIGH: Priority.HIGH,
            Severity.MEDIUM: Priority.MEDIUM,
            Severity.LOW: Priority.LOW,
        }
        return mapping.get(severity, Priority.MEDIUM)

    def _get_priority_score(self, priority: Priority) -> float:
        """優先度のスコアを取得"""
        scores = {
            Priority.URGENT: 1.0,
            Priority.HIGH: 0.8,
            Priority.MEDIUM: 0.6,
            Priority.LOW: 0.4,
        }
        return scores.get(priority, 0.5)

    def _estimate_dependency_effort(self, description: str) -> str:
        """依存関係エラーの工数を推定"""
        if "version" in description.lower() or "conflict" in description.lower():
            return "30分-2時間"  # バージョン競合は時間がかかる
        elif "missing" in description.lower():
            return "5-15分"  # 単純なインストール
        else:
            return "15-60分"  # 一般的な依存関係問題

    def parse_code_diff(self, diff_text: str) -> list[CodeChange]:
        """差分テキストからCodeChangeオブジェクトを生成

        Args:
            diff_text: 差分テキスト（unified diff形式）

        Returns:
            CodeChangeオブジェクトのリスト
        """
        changes = []

        try:
            # 簡単な差分パーサー（実際にはより堅牢な実装が必要）
            lines = diff_text.split("\n")
            current_file = None
            old_code_lines = []
            new_code_lines = []
            line_start = 1

            for line in lines:
                if line.startswith("+++"):
                    # ファイル名を抽出（a/ や b/ プレフィックスを除去）
                    file_path = line[4:].strip()
                    if file_path.startswith("b/"):
                        file_path = file_path[2:]
                    current_file = file_path
                elif line.startswith("@@"):
                    # 行番号情報を抽出
                    match = re.search(r"-(\d+),?\d* \+(\d+),?\d*", line)
                    if match:
                        line_start = int(match.group(1))
                elif line.startswith("-") and not line.startswith("---"):
                    old_code_lines.append(line[1:])
                elif line.startswith("+") and not line.startswith("+++"):
                    new_code_lines.append(line[1:])
                elif (old_code_lines or new_code_lines) and (line.startswith(" ") or not line.strip()):
                    # 変更ブロックの終了
                    if current_file:
                        changes.append(
                            CodeChange(
                                file_path=current_file,
                                line_start=line_start,
                                line_end=line_start + len(old_code_lines) - 1,
                                old_code="\n".join(old_code_lines),
                                new_code="\n".join(new_code_lines),
                                description="コード変更",
                            )
                        )
                    old_code_lines = []
                    new_code_lines = []

            # 最後の変更ブロックを処理
            if (old_code_lines or new_code_lines) and current_file:
                changes.append(
                    CodeChange(
                        file_path=current_file,
                        line_start=line_start,
                        line_end=line_start + len(old_code_lines) - 1,
                        old_code="\n".join(old_code_lines),
                        new_code="\n".join(new_code_lines),
                        description="コード変更",
                    )
                )

        except Exception as e:
            logger.warning("差分の解析に失敗: %s", e)

        return changes

    def estimate_fix_effort(self, fix_suggestion: FixSuggestion) -> str:
        """修正提案の工数を推定

        Args:
            fix_suggestion: 修正提案

        Returns:
            推定工数の文字列
        """
        # 既に工数が設定されている場合はそれを使用
        if fix_suggestion.estimated_effort != "不明":
            return fix_suggestion.estimated_effort

        # コード変更の数と複雑さから推定
        change_count = len(fix_suggestion.code_changes)

        if change_count == 0:
            return "5-15分"  # 設定変更など
        elif change_count == 1:
            return "10-30分"  # 単一ファイルの修正
        elif change_count <= 3:
            return "30分-1時間"  # 複数ファイルの修正
        else:
            return "1-3時間"  # 大規模な修正

    def calculate_fix_priority(
        self, fix_suggestion: FixSuggestion, project_impact: dict[str, Any] | None = None
    ) -> Priority:
        """修正提案の優先度を計算

        Args:
            fix_suggestion: 修正提案
            project_impact: プロジェクトへの影響度情報

        Returns:
            計算された優先度
        """
        # 基本スコア
        base_score = self._get_priority_score(fix_suggestion.priority)

        # 信頼度による調整
        confidence_factor = fix_suggestion.confidence

        # コード変更の影響による調整
        impact_factor = 1.0
        for change in fix_suggestion.code_changes:
            if self._is_critical_file(change.file_path):
                impact_factor *= 1.2

        # 最終スコアを計算
        final_score = base_score * confidence_factor * impact_factor

        # スコアを優先度に変換
        if final_score >= 0.8:
            return Priority.URGENT
        elif final_score >= 0.6:
            return Priority.HIGH
        elif final_score >= 0.4:
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def _is_critical_file(self, file_path: str) -> bool:
        """ファイルがクリティカルかどうかを判定"""
        critical_patterns = [
            r"package\.json$",
            r"requirements\.txt$",
            r"Dockerfile$",
            r"\.github/workflows/",
            r"tsconfig\.json$",
            r"webpack\.config\.",
        ]

        for pattern in critical_patterns:
            if re.search(pattern, file_path):
                return True

        return False
