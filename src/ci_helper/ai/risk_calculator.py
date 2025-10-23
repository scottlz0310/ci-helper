"""
リスクレベルと推定時間の計算機能

修正提案のリスクレベル（低/中/高）の自動判定と、
修正にかかる推定時間の計算を行います。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import FixSuggestion, FixTemplate


class RiskCalculator:
    """リスクレベル計算クラス"""

    def __init__(self) -> None:
        """リスク計算器を初期化"""
        # クリティカルファイルのパターン
        self.critical_file_patterns = [
            r"package\.json$",
            r"requirements\.txt$",
            r"pyproject\.toml$",
            r"Dockerfile$",
            r"docker-compose\.ya?ml$",
            r"\.github/workflows/.*\.ya?ml$",
            r"tsconfig\.json$",
            r"webpack\.config\.",
            r"babel\.config\.",
            r"\.env$",
            r"\.env\..*$",
            r"config/.*\.ya?ml$",
            r"src/main\.",
            r"index\.(js|ts|py)$",
        ]

        # 重要ディレクトリのパターン
        self.important_directory_patterns = [
            r"^src/",
            r"^lib/",
            r"^app/",
            r"^config/",
            r"^\.github/",
            r"^docker/",
            r"^scripts/",
        ]

        # 高リスク操作のパターン
        self.high_risk_operations = [
            "delete",
            "remove",
            "rm ",
            "DROP",
            "DELETE",
            "truncate",
            "format",
            "chmod 777",
            "sudo",
            "--force",
            "--hard",
        ]

        # 中リスク操作のパターン
        self.medium_risk_operations = [
            "replace",
            "modify",
            "update",
            "install",
            "upgrade",
            "migrate",
            "chmod",
            "chown",
        ]

    def calculate_risk_level(
        self, fix_suggestion: FixSuggestion, template: FixTemplate | None = None, context: dict[str, Any] | None = None
    ) -> str:
        """修正提案のリスクレベルを計算

        Args:
            fix_suggestion: 修正提案
            template: 修正テンプレート（利用可能な場合）
            context: コンテキスト情報

        Returns:
            リスクレベル（"low", "medium", "high"）
        """
        risk_score = 0.0

        # テンプレートのベースリスクレベル
        if template:
            base_risk = self._get_base_risk_score(template.risk_level)
            risk_score += base_risk

        # ファイルの重要度による調整
        file_risk = self._calculate_file_risk(fix_suggestion)
        risk_score += file_risk

        # 操作の危険度による調整
        operation_risk = self._calculate_operation_risk(fix_suggestion)
        risk_score += operation_risk

        # 影響範囲による調整
        scope_risk = self._calculate_scope_risk(fix_suggestion)
        risk_score += scope_risk

        # 信頼度による調整（信頼度が低いほどリスクが高い）
        confidence_risk = self._calculate_confidence_risk(fix_suggestion.confidence)
        risk_score += confidence_risk

        # コンテキストによる調整
        if context:
            context_risk = self._calculate_context_risk(context)
            risk_score += context_risk

        # スコアをリスクレベルに変換
        return self._score_to_risk_level(risk_score)

    def _get_base_risk_score(self, risk_level: str) -> float:
        """ベースリスクレベルをスコアに変換"""
        risk_mapping = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
        }
        return risk_mapping.get(risk_level.lower(), 0.5)

    def _calculate_file_risk(self, fix_suggestion: FixSuggestion) -> float:
        """ファイルの重要度によるリスクを計算"""
        risk_score = 0.0

        for code_change in fix_suggestion.code_changes:
            file_path = code_change.file_path

            # クリティカルファイルのチェック
            if self._is_critical_file(file_path):
                risk_score += 0.3

            # 重要ディレクトリのチェック
            elif self._is_important_directory(file_path):
                risk_score += 0.2

            # システムファイルのチェック
            elif self._is_system_file(file_path):
                risk_score += 0.4

        return min(risk_score, 0.5)  # 最大0.5に制限

    def _calculate_operation_risk(self, fix_suggestion: FixSuggestion) -> float:
        """操作の危険度によるリスクを計算"""
        risk_score = 0.0

        # 修正内容から危険な操作を検出
        all_content = (
            fix_suggestion.description + " " + " ".join(change.new_code for change in fix_suggestion.code_changes)
        )

        # 高リスク操作のチェック
        for operation in self.high_risk_operations:
            if operation.lower() in all_content.lower():
                risk_score += 0.3

        # 中リスク操作のチェック
        for operation in self.medium_risk_operations:
            if operation.lower() in all_content.lower():
                risk_score += 0.1

        return min(risk_score, 0.4)  # 最大0.4に制限

    def _calculate_scope_risk(self, fix_suggestion: FixSuggestion) -> float:
        """影響範囲によるリスクを計算"""
        # 変更するファイル数による調整
        file_count = len(fix_suggestion.code_changes)

        if file_count == 0:
            return 0.0
        elif file_count == 1:
            return 0.05
        elif file_count <= 3:
            return 0.1
        elif file_count <= 5:
            return 0.2
        else:
            return 0.3

    def _calculate_confidence_risk(self, confidence: float) -> float:
        """信頼度によるリスクを計算"""
        # 信頼度が低いほどリスクが高い
        if confidence >= 0.9:
            return 0.0
        elif confidence >= 0.8:
            return 0.05
        elif confidence >= 0.7:
            return 0.1
        elif confidence >= 0.5:
            return 0.2
        else:
            return 0.3

    def _calculate_context_risk(self, context: dict[str, Any]) -> float:
        """コンテキストによるリスクを計算"""
        risk_score = 0.0

        # 本番環境での実行
        if context.get("environment") == "production":
            risk_score += 0.2

        # 重要なサービスへの影響
        if context.get("service_criticality") == "high":
            risk_score += 0.15

        # データベース操作
        if context.get("involves_database", False):
            risk_score += 0.1

        return min(risk_score, 0.3)

    def _is_critical_file(self, file_path: str) -> bool:
        """ファイルがクリティカルかどうかを判定"""
        for pattern in self.critical_file_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        return False

    def _is_important_directory(self, file_path: str) -> bool:
        """ファイルが重要ディレクトリにあるかどうかを判定"""
        for pattern in self.important_directory_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        return False

    def _is_system_file(self, file_path: str) -> bool:
        """ファイルがシステムファイルかどうかを判定"""
        system_patterns = [
            r"^/etc/",
            r"^/usr/",
            r"^/var/",
            r"^/opt/",
            r"^C:\\Windows\\",
            r"^C:\\Program Files\\",
        ]

        for pattern in system_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        return False

    def _score_to_risk_level(self, score: float) -> str:
        """スコアをリスクレベルに変換"""
        if score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        else:
            return "low"


class TimeEstimator:
    """推定時間計算クラス"""

    def __init__(self) -> None:
        """時間推定器を初期化"""
        # 操作タイプ別の基本時間（分）
        self.base_times = {
            "file_modification": 5,
            "command": 3,
            "config_change": 10,
            "dependency_install": 15,
            "build": 30,
            "test": 20,
            "deployment": 45,
        }

        # ファイルタイプ別の複雑度係数
        self.complexity_factors = {
            ".py": 1.2,
            ".js": 1.1,
            ".ts": 1.3,
            ".java": 1.4,
            ".cpp": 1.5,
            ".c": 1.4,
            ".go": 1.1,
            ".rs": 1.3,
            ".yaml": 0.8,
            ".yml": 0.8,
            ".json": 0.7,
            ".toml": 0.8,
            ".xml": 0.9,
            ".html": 0.9,
            ".css": 0.8,
        }

    def estimate_fix_time(
        self, fix_suggestion: FixSuggestion, template: FixTemplate | None = None, context: dict[str, Any] | None = None
    ) -> str:
        """修正にかかる推定時間を計算

        Args:
            fix_suggestion: 修正提案
            template: 修正テンプレート（利用可能な場合）
            context: コンテキスト情報

        Returns:
            推定時間の文字列（例: "10-20分", "1-2時間"）
        """
        # テンプレートに推定時間が設定されている場合はそれを使用
        if template and template.estimated_time:
            base_time = self._parse_time_string(template.estimated_time)
        else:
            # 修正内容から推定時間を計算
            base_time = self._calculate_base_time(fix_suggestion)

        # 複雑度による調整
        complexity_factor = self._calculate_complexity_factor(fix_suggestion)
        adjusted_time = base_time * complexity_factor

        # コンテキストによる調整
        if context:
            context_factor = self._calculate_context_factor(context)
            adjusted_time *= context_factor

        # 信頼度による調整（信頼度が低いほど時間がかかる）
        confidence_factor = self._calculate_confidence_factor(fix_suggestion.confidence)
        adjusted_time *= confidence_factor

        # 時間を範囲で表現
        return self._format_time_range(adjusted_time)

    def _parse_time_string(self, time_string: str) -> float:
        """時間文字列を分単位の数値に変換"""
        # "10分", "1時間", "2-3時間" などの形式をパース
        time_string = time_string.lower()

        # 範囲の場合は平均を取る
        range_match = re.search(r"(\d+)-(\d+)", time_string)
        if range_match:
            min_time = int(range_match.group(1))
            max_time = int(range_match.group(2))
            base_value = (min_time + max_time) / 2
        else:
            # 単一の値を抽出
            number_match = re.search(r"(\d+)", time_string)
            if number_match:
                base_value = int(number_match.group(1))
            else:
                return 30.0  # デフォルト値

        # 単位を判定
        if "時間" in time_string or "hour" in time_string:
            return base_value * 60  # 時間を分に変換
        elif "日" in time_string or "day" in time_string:
            return base_value * 60 * 8  # 日を分に変換（8時間/日）
        else:
            return base_value  # 分として扱う

    def _calculate_base_time(self, fix_suggestion: FixSuggestion) -> float:
        """修正内容から基本時間を計算"""
        total_time = 0.0

        # コード変更の数による基本時間
        change_count = len(fix_suggestion.code_changes)
        if change_count == 0:
            total_time += self.base_times["config_change"]
        else:
            total_time += change_count * self.base_times["file_modification"]

        # 修正内容から操作タイプを推定
        description = fix_suggestion.description.lower()

        if "install" in description or "dependency" in description:
            total_time += self.base_times["dependency_install"]
        elif "build" in description or "compile" in description:
            total_time += self.base_times["build"]
        elif "test" in description:
            total_time += self.base_times["test"]
        elif "deploy" in description:
            total_time += self.base_times["deployment"]

        return max(total_time, 5.0)  # 最小5分

    def _calculate_complexity_factor(self, fix_suggestion: FixSuggestion) -> float:
        """複雑度係数を計算"""
        if not fix_suggestion.code_changes:
            return 1.0

        total_factor = 0.0
        for code_change in fix_suggestion.code_changes:
            file_path = code_change.file_path
            file_ext = Path(file_path).suffix.lower()

            # ファイルタイプによる複雑度
            factor = self.complexity_factors.get(file_ext, 1.0)

            # コード変更の行数による調整
            old_lines = len(code_change.old_code.split("\n")) if code_change.old_code else 1
            new_lines = len(code_change.new_code.split("\n")) if code_change.new_code else 1
            line_factor = 1.0 + (max(old_lines, new_lines) - 1) * 0.1

            total_factor += factor * line_factor

        return total_factor / len(fix_suggestion.code_changes)

    def _calculate_context_factor(self, context: dict[str, Any]) -> float:
        """コンテキストによる時間調整係数を計算"""
        factor = 1.0

        # 環境による調整
        if context.get("environment") == "production":
            factor *= 1.5  # 本番環境では慎重に作業

        # プロジェクトサイズによる調整
        project_size = context.get("project_size", "medium")
        if project_size == "large":
            factor *= 1.3
        elif project_size == "small":
            factor *= 0.8

        # チーム経験による調整
        team_experience = context.get("team_experience", "medium")
        if team_experience == "high":
            factor *= 0.8
        elif team_experience == "low":
            factor *= 1.4

        return factor

    def _calculate_confidence_factor(self, confidence: float) -> float:
        """信頼度による時間調整係数を計算"""
        # 信頼度が低いほど調査・試行錯誤に時間がかかる
        if confidence >= 0.9:
            return 1.0
        elif confidence >= 0.8:
            return 1.2
        elif confidence >= 0.7:
            return 1.5
        elif confidence >= 0.5:
            return 2.0
        else:
            return 3.0

    def _format_time_range(self, minutes: float) -> str:
        """分単位の時間を適切な範囲文字列に変換"""
        # 範囲の幅を20%に設定
        min_time = minutes * 0.8
        max_time = minutes * 1.2

        if max_time < 60:
            # 分単位
            return f"{int(min_time)}-{int(max_time)}分"
        elif max_time < 480:  # 8時間未満
            # 時間単位
            min_hours = min_time / 60
            max_hours = max_time / 60
            if min_hours < 1:
                return f"{int(min_time)}分-{max_hours:.1f}時間"
            else:
                return f"{min_hours:.1f}-{max_hours:.1f}時間"
        else:
            # 日単位
            min_days = min_time / (60 * 8)
            max_days = max_time / (60 * 8)
            return f"{min_days:.1f}-{max_days:.1f}日"
