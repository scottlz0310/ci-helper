"""
ユーザー承認システム

リスクレベルに応じた承認フローと修正内容のプレビュー表示機能を提供します。
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .models import FixSuggestion, FixTemplate, PatternMatch

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """リスクレベル"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalDecision(Enum):
    """承認決定"""

    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    QUIT = "quit"


class ApprovalResult:
    """承認結果"""

    def __init__(self, decision: ApprovalDecision, reason: str = "", timestamp: datetime | None = None):
        self.decision = decision
        self.reason = reason
        self.timestamp = timestamp or datetime.now()

    @property
    def approved(self) -> bool:
        """承認されたかどうか"""
        return self.decision == ApprovalDecision.APPROVED


class UserApprovalSystem:
    """ユーザー承認システム

    リスクレベルに応じた承認フローを管理し、
    修正内容の詳細なプレビューを提供します。
    """

    def __init__(self, interactive: bool = True, auto_approve_low_risk: bool = False):
        """承認システムを初期化

        Args:
            interactive: 対話モード
            auto_approve_low_risk: 低リスク修正の自動承認
        """
        self.interactive = interactive
        self.auto_approve_low_risk = auto_approve_low_risk
        self.console = Console()

        # 承認履歴
        self.approval_history: list[dict[str, Any]] = []

    async def request_approval(
        self,
        fix_suggestion: FixSuggestion,
        pattern_match: PatternMatch | None = None,
        fix_template: FixTemplate | None = None,
    ) -> ApprovalResult:
        """修正提案の承認を要求

        Args:
            fix_suggestion: 修正提案
            pattern_match: パターンマッチ結果（オプション）
            fix_template: 修正テンプレート（オプション）

        Returns:
            承認結果
        """
        # リスクレベルを判定
        risk_level = self._assess_risk_level(fix_suggestion, pattern_match, fix_template)

        # 自動承認チェック
        if self._should_auto_approve(risk_level, fix_suggestion):
            result = ApprovalResult(
                ApprovalDecision.APPROVED,
                f"自動承認 (リスクレベル: {risk_level.value}, 信頼度: {fix_suggestion.confidence:.1%})",
            )
            self._record_approval(fix_suggestion, result, risk_level)
            return result

        # 対話モードでない場合は拒否
        if not self.interactive:
            result = ApprovalResult(ApprovalDecision.REJECTED, "非対話モードのため承認を拒否")
            self._record_approval(fix_suggestion, result, risk_level)
            return result

        # 修正内容のプレビューを表示
        self._display_fix_preview(fix_suggestion, pattern_match, fix_template, risk_level)

        # ユーザーからの入力を取得
        result = await self._get_user_decision(fix_suggestion, risk_level)
        self._record_approval(fix_suggestion, result, risk_level)

        return result

    def _assess_risk_level(
        self,
        fix_suggestion: FixSuggestion,
        pattern_match: PatternMatch | None = None,
        fix_template: FixTemplate | None = None,
    ) -> RiskLevel:
        """修正提案のリスクレベルを評価

        Args:
            fix_suggestion: 修正提案
            pattern_match: パターンマッチ結果
            fix_template: 修正テンプレート

        Returns:
            リスクレベル
        """
        # テンプレートにリスクレベルが定義されている場合はそれを使用
        if fix_template and hasattr(fix_template, "risk_level"):
            try:
                return RiskLevel(fix_template.risk_level.lower())
            except ValueError:
                pass

        # 信頼度ベースの評価
        if fix_suggestion.confidence >= 0.9:
            base_risk = RiskLevel.LOW
        elif fix_suggestion.confidence >= 0.7:
            base_risk = RiskLevel.MEDIUM
        else:
            base_risk = RiskLevel.HIGH

        # ファイル変更の影響度を考慮
        high_risk_files = {
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
            ".actrc",
            ".github/workflows",
        }

        medium_risk_files = {"README.md", ".gitignore", "LICENSE", "ci-helper.toml", ".env"}

        for change in fix_suggestion.code_changes:
            if change.file_path:
                file_name = change.file_path.split("/")[-1]
                file_path = change.file_path

                # 高リスクファイルの変更
                if any(file_name == high_risk or file_path.startswith(high_risk) for high_risk in high_risk_files):
                    return RiskLevel.HIGH

                # 中リスクファイルの変更
                if any(
                    file_name == medium_risk or file_path.startswith(medium_risk) for medium_risk in medium_risk_files
                ):
                    if base_risk == RiskLevel.LOW:
                        base_risk = RiskLevel.MEDIUM

        # 変更量を考慮
        total_changes = sum(len(change.new_code.splitlines()) for change in fix_suggestion.code_changes)
        if total_changes > 50:  # 50行以上の変更
            if base_risk == RiskLevel.LOW:
                base_risk = RiskLevel.MEDIUM
            elif base_risk == RiskLevel.MEDIUM:
                base_risk = RiskLevel.HIGH

        return base_risk

    def _should_auto_approve(self, risk_level: RiskLevel, fix_suggestion: FixSuggestion) -> bool:
        """自動承認すべきかどうかを判定

        Args:
            risk_level: リスクレベル
            fix_suggestion: 修正提案

        Returns:
            自動承認すべきかどうか
        """
        # 低リスクの自動承認設定
        if self.auto_approve_low_risk and risk_level == RiskLevel.LOW:
            return True

        # 非常に高い信頼度の場合は低リスクなら自動承認
        if risk_level == RiskLevel.LOW and fix_suggestion.confidence >= 0.95:
            return True

        return False

    def _display_fix_preview(
        self,
        fix_suggestion: FixSuggestion,
        pattern_match: PatternMatch | None,
        fix_template: FixTemplate | None,
        risk_level: RiskLevel,
    ) -> None:
        """修正内容のプレビューを表示

        Args:
            fix_suggestion: 修正提案
            pattern_match: パターンマッチ結果
            fix_template: 修正テンプレート
            risk_level: リスクレベル
        """
        self.console.print()

        # ヘッダー情報
        risk_color = {RiskLevel.LOW: "green", RiskLevel.MEDIUM: "yellow", RiskLevel.HIGH: "red"}[risk_level]

        header_table = Table(show_header=False, box=None, padding=(0, 1))
        header_table.add_column("Label", style="bold")
        header_table.add_column("Value")

        header_table.add_row("🔧 修正提案:", fix_suggestion.title)
        header_table.add_row("📊 信頼度:", f"{fix_suggestion.confidence:.1%}")
        header_table.add_row("⚠️  リスクレベル:", Text(risk_level.value.upper(), style=f"bold {risk_color}"))
        header_table.add_row("⏱️  推定時間:", fix_suggestion.estimated_effort)

        if pattern_match:
            header_table.add_row("🎯 検出パターン:", pattern_match.pattern.name)
            header_table.add_row("🔍 パターン信頼度:", f"{pattern_match.confidence:.1%}")

        self.console.print(Panel(header_table, title="修正提案の詳細", border_style=risk_color))

        # 説明
        if fix_suggestion.description:
            self.console.print(Panel(fix_suggestion.description, title="説明", border_style="blue"))

        # コード変更のプレビュー
        if fix_suggestion.code_changes:
            self.console.print("\n📝 変更内容:")

            for i, change in enumerate(fix_suggestion.code_changes, 1):
                self.console.print(f"\n{i}. ファイル: [bold cyan]{change.file_path}[/bold cyan]")

                if change.description:
                    self.console.print(f"   説明: {change.description}")

                # 変更前のコード
                if change.old_code.strip():
                    self.console.print("   [red]変更前:[/red]")
                    syntax = Syntax(
                        change.old_code,
                        lexer=self._get_lexer_for_file(change.file_path),
                        theme="monokai",
                        line_numbers=True,
                    )
                    self.console.print(syntax)

                # 変更後のコード
                if change.new_code.strip():
                    self.console.print("   [green]変更後:[/green]")
                    syntax = Syntax(
                        change.new_code,
                        lexer=self._get_lexer_for_file(change.file_path),
                        theme="monokai",
                        line_numbers=True,
                    )
                    self.console.print(syntax)

        # 前提条件と検証ステップ
        if fix_template:
            if fix_template.prerequisites:
                self.console.print(
                    Panel(
                        "\n".join(f"• {prereq}" for prereq in fix_template.prerequisites),
                        title="前提条件",
                        border_style="yellow",
                    )
                )

            if fix_template.validation_steps:
                self.console.print(
                    Panel(
                        "\n".join(f"• {step}" for step in fix_template.validation_steps),
                        title="検証ステップ",
                        border_style="cyan",
                    )
                )

    async def _get_user_decision(self, fix_suggestion: FixSuggestion, risk_level: RiskLevel) -> ApprovalResult:
        """ユーザーの決定を取得

        Args:
            fix_suggestion: 修正提案
            risk_level: リスクレベル

        Returns:
            承認結果
        """
        # リスクレベルに応じたプロンプト
        if risk_level == RiskLevel.HIGH:
            prompt = "\n⚠️  [bold red]高リスク修正[/bold red]です。慎重に検討してください。"
        elif risk_level == RiskLevel.MEDIUM:
            prompt = "\n⚠️  [bold yellow]中リスク修正[/bold yellow]です。"
        else:
            prompt = "\n✅ [bold green]低リスク修正[/bold green]です。"

        self.console.print(prompt)

        options_text = (
            "\n選択肢:\n"
            "  [bold green]y[/bold green] / [bold green]yes[/bold green]    - 修正を適用\n"
            "  [bold red]n[/bold red] / [bold red]no[/bold red]     - 修正を拒否\n"
            "  [bold yellow]s[/bold yellow] / [bold yellow]skip[/bold yellow]   - この修正をスキップ\n"
            "  [bold blue]p[/bold blue] / [bold blue]preview[/bold blue] - 詳細プレビューを再表示\n"
            "  [bold magenta]q[/bold magenta] / [bold magenta]quit[/bold magenta]    - 修正プロセスを終了"
        )

        self.console.print(options_text)

        while True:
            try:
                response = input("\n決定を入力してください: ").lower().strip()

                if response in ["y", "yes"]:
                    return ApprovalResult(ApprovalDecision.APPROVED, "ユーザーが承認")
                elif response in ["n", "no"]:
                    return ApprovalResult(ApprovalDecision.REJECTED, "ユーザーが拒否")
                elif response in ["s", "skip"]:
                    return ApprovalResult(ApprovalDecision.SKIPPED, "ユーザーがスキップ")
                elif response in ["p", "preview"]:
                    # プレビューを再表示
                    self._display_fix_preview(fix_suggestion, None, None, risk_level)
                    continue
                elif response in ["q", "quit"]:
                    return ApprovalResult(ApprovalDecision.QUIT, "ユーザーが終了を選択")
                else:
                    self.console.print("[red]無効な入力です。y, n, s, p, q のいずれかを入力してください。[/red]")

            except KeyboardInterrupt:
                return ApprovalResult(ApprovalDecision.QUIT, "ユーザーが中断 (Ctrl+C)")
            except EOFError:
                return ApprovalResult(ApprovalDecision.REJECTED, "入力エラー (EOF)")

    def _get_lexer_for_file(self, file_path: str) -> str:
        """ファイルパスから適切なシンタックスハイライト用レクサーを取得

        Args:
            file_path: ファイルパス

        Returns:
            レクサー名
        """
        if file_path.endswith(".py"):
            return "python"
        elif file_path.endswith((".yml", ".yaml")):
            return "yaml"
        elif file_path.endswith(".json"):
            return "json"
        elif file_path.endswith(".toml"):
            return "toml"
        elif file_path.endswith((".sh", ".bash")):
            return "bash"
        elif file_path.endswith(".md"):
            return "markdown"
        elif file_path.endswith((".js", ".ts")):
            return "javascript"
        elif file_path.endswith(".dockerfile") or "Dockerfile" in file_path:
            return "dockerfile"
        else:
            return "text"

    def _record_approval(self, fix_suggestion: FixSuggestion, result: ApprovalResult, risk_level: RiskLevel) -> None:
        """承認結果を記録

        Args:
            fix_suggestion: 修正提案
            result: 承認結果
            risk_level: リスクレベル
        """
        record = {
            "timestamp": result.timestamp,
            "suggestion_title": fix_suggestion.title,
            "confidence": fix_suggestion.confidence,
            "risk_level": risk_level.value,
            "decision": result.decision.value,
            "reason": result.reason,
            "changes_count": len(fix_suggestion.code_changes),
        }

        self.approval_history.append(record)
        logger.debug("承認結果を記録: %s", record)

    def get_approval_summary(self) -> dict[str, Any]:
        """承認履歴のサマリーを取得

        Returns:
            承認履歴サマリー
        """
        if not self.approval_history:
            return {
                "total_requests": 0,
                "approved": 0,
                "rejected": 0,
                "skipped": 0,
                "quit": 0,
                "approval_rate": 0.0,
                "risk_breakdown": {},
                "recent_decisions": [],
            }

        decisions = [record["decision"] for record in self.approval_history]
        risk_levels = [record["risk_level"] for record in self.approval_history]

        return {
            "total_requests": len(self.approval_history),
            "approved": decisions.count("approved"),
            "rejected": decisions.count("rejected"),
            "skipped": decisions.count("skipped"),
            "quit": decisions.count("quit"),
            "approval_rate": decisions.count("approved") / len(decisions) if decisions else 0.0,
            "risk_breakdown": {
                "low": risk_levels.count("low"),
                "medium": risk_levels.count("medium"),
                "high": risk_levels.count("high"),
            },
            "recent_decisions": self.approval_history[-10:],  # 最新10件
        }

    def set_auto_approve_policy(self, low_risk: bool = False, medium_risk: bool = False) -> None:
        """自動承認ポリシーを設定

        Args:
            low_risk: 低リスク修正の自動承認
            medium_risk: 中リスク修正の自動承認
        """
        self.auto_approve_low_risk = low_risk
        # 中リスクの自動承認は現在未実装（安全性のため）
        if medium_risk:
            logger.warning("中リスク修正の自動承認は安全性のため現在サポートされていません")
