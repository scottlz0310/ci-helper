"""
拡張フォーマッター

分析結果の表示形式を改善し、修正提案の説明をより分かりやすくし、
エラーメッセージの日本語化を提供します。
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..ai.models import AnalysisResult, FixSuggestion, PatternMatch, Priority


class EnhancedAnalysisFormatter:
    """拡張分析結果フォーマッター"""

    def __init__(self, console: Console, language: str = "ja"):
        """
        Args:
            console: Richコンソール
            language: 表示言語（ja/en）
        """
        self.console = console
        self.language = language
        self.messages = self._load_messages()

    def _load_messages(self) -> dict[str, str]:
        """言語別メッセージを読み込み"""
        if self.language == "ja":
            return {
                "analysis_result": "🔍 AI分析結果",
                "pattern_recognition": "🎯 検出されたパターン",
                "summary": "要約",
                "root_causes": "根本原因",
                "fix_suggestions": "修正提案",
                "related_errors": "関連エラー",
                "statistics": "統計情報",
                "confidence": "信頼度",
                "analysis_time": "分析時間",
                "provider": "プロバイダー",
                "model": "モデル",
                "tokens_used": "使用トークン",
                "estimated_cost": "推定コスト",
                "cache_hit": "キャッシュヒット",
                "pattern_name": "パターン名",
                "category": "カテゴリ",
                "match_reason": "マッチ理由",
                "fix_title": "修正案",
                "description": "説明",
                "priority": "優先度",
                "estimated_effort": "推定作業時間",
                "risk_level": "リスクレベル",
                "auto_applicable": "自動適用可能",
                "affected_files": "影響ファイル",
                "prerequisites": "前提条件",
                "validation_steps": "検証ステップ",
                "background_reason": "背景理由",
                "impact_assessment": "影響評価",
                "effectiveness": "効果",
                "safety": "安全性",
                "overall_rating": "総合評価",
                "recommended_fix": "推奨修正案",
                "high": "高",
                "medium": "中",
                "low": "低",
                "urgent": "緊急",
                "yes": "はい",
                "no": "いいえ",
                "seconds": "秒",
                "minutes": "分",
                "hours": "時間",
                "fallback_reason": "フォールバック理由",
                "retry_available": "リトライ可能",
                "alternative_providers": "代替プロバイダー",
                "operation_id": "操作ID",
                "retry_command": "リトライコマンド",
            }
        else:  # English
            return {
                "analysis_result": "🔍 AI Analysis Result",
                "pattern_recognition": "🎯 Detected Patterns",
                "summary": "Summary",
                "root_causes": "Root Causes",
                "fix_suggestions": "Fix Suggestions",
                "related_errors": "Related Errors",
                "statistics": "Statistics",
                "confidence": "Confidence",
                "analysis_time": "Analysis Time",
                "provider": "Provider",
                "model": "Model",
                "tokens_used": "Tokens Used",
                "estimated_cost": "Estimated Cost",
                "cache_hit": "Cache Hit",
                "pattern_name": "Pattern Name",
                "category": "Category",
                "match_reason": "Match Reason",
                "fix_title": "Fix",
                "description": "Description",
                "priority": "Priority",
                "estimated_effort": "Estimated Effort",
                "risk_level": "Risk Level",
                "auto_applicable": "Auto Applicable",
                "affected_files": "Affected Files",
                "prerequisites": "Prerequisites",
                "validation_steps": "Validation Steps",
                "background_reason": "Background Reason",
                "impact_assessment": "Impact Assessment",
                "effectiveness": "Effectiveness",
                "safety": "Safety",
                "overall_rating": "Overall Rating",
                "recommended_fix": "Recommended Fix",
                "high": "High",
                "medium": "Medium",
                "low": "Low",
                "urgent": "Urgent",
                "yes": "Yes",
                "no": "No",
                "seconds": "sec",
                "minutes": "min",
                "hours": "hr",
                "fallback_reason": "Fallback Reason",
                "retry_available": "Retry Available",
                "alternative_providers": "Alternative Providers",
                "operation_id": "Operation ID",
                "retry_command": "Retry Command",
            }

    def format_analysis_result(self, result: AnalysisResult, output_format: str = "enhanced") -> None:
        """分析結果を拡張フォーマットで表示

        Args:
            result: 分析結果
            output_format: 出力形式（enhanced/markdown/json/table）
        """
        if output_format == "json":
            self._format_as_json(result)
        elif output_format == "table":
            self._format_as_table(result)
        elif output_format == "markdown":
            self._format_as_markdown(result)
        else:  # enhanced
            self._format_as_enhanced(result)

    def _format_as_enhanced(self, result: AnalysisResult) -> None:
        """拡張フォーマットで表示"""
        # ヘッダー
        self.console.print(Panel.fit(self.messages["analysis_result"], style="blue bold"))
        self.console.print()

        # フォールバック情報（該当する場合）
        self._display_fallback_info(result)

        # パターン認識結果
        self._display_pattern_recognition_enhanced(result)

        # 要約セクション
        if result.summary:
            self._display_summary_enhanced(result.summary)

        # 根本原因セクション
        if result.root_causes:
            self._display_root_causes_enhanced(result.root_causes)

        # 修正提案セクション（拡張版）
        if result.fix_suggestions:
            self._display_fix_suggestions_enhanced(result.fix_suggestions)

        # 関連エラー
        if result.related_errors:
            self._display_related_errors_enhanced(result.related_errors)

        # 統計情報
        self._display_statistics_enhanced(result)

    def _display_pattern_recognition_enhanced(self, result: AnalysisResult) -> None:
        """パターン認識結果の拡張表示"""
        pattern_matches = getattr(result, "pattern_matches", None)
        if not pattern_matches:
            return

        self.console.print(Panel.fit(self.messages["pattern_recognition"], style="green"))
        self.console.print()

        # パターンマッチテーブル
        pattern_table = Table(show_header=True, header_style="bold green", box=None)
        pattern_table.add_column("🎯", style="cyan", width=3)
        pattern_table.add_column(self.messages["pattern_name"], style="cyan", width=25)
        pattern_table.add_column(self.messages["category"], style="yellow", width=12)
        pattern_table.add_column(self.messages["confidence"], style="green", width=10)
        pattern_table.add_column(self.messages["match_reason"], style="white", width=30)

        for i, match in enumerate(pattern_matches[:5], 1):  # 上位5つ
            # 信頼度の色分け
            confidence_color = "green" if match.confidence >= 0.8 else "yellow" if match.confidence >= 0.6 else "red"
            confidence_text = f"[{confidence_color}]{match.confidence:.1%}[/{confidence_color}]"

            # マッチ理由の構築
            reasons = []
            if hasattr(match, "supporting_evidence") and match.supporting_evidence:
                reasons.extend(match.supporting_evidence[:2])
            if not reasons:
                reasons = ["パターンマッチ検出" if self.language == "ja" else "Pattern matched"]

            reason_text = ", ".join(reasons)
            if len(reason_text) > 25:
                reason_text = reason_text[:22] + "..."

            pattern_table.add_row(
                f"{i}",
                match.pattern.name,
                match.pattern.category,
                confidence_text,
                reason_text,
            )

        self.console.print(pattern_table)
        self.console.print()

        # 詳細情報（上位3つ）
        for i, match in enumerate(pattern_matches[:3], 1):
            self._display_single_pattern_detail(match, i)

    def _display_single_pattern_detail(self, match: PatternMatch, index: int) -> None:
        """単一パターンの詳細表示"""
        title = (
            f"パターン {index}: {match.pattern.name}"
            if self.language == "ja"
            else f"Pattern {index}: {match.pattern.name}"
        )
        self.console.print(f"[bold cyan]{title}[/bold cyan]")

        # 基本情報
        category_text = (
            f"カテゴリ: {match.pattern.category}" if self.language == "ja" else f"Category: {match.pattern.category}"
        )
        confidence_text = (
            f"信頼度: {match.confidence:.1%}" if self.language == "ja" else f"Confidence: {match.confidence:.1%}"
        )

        self.console.print(f"  {category_text}")
        self.console.print(f"  {confidence_text}")

        # コンテキスト情報
        if hasattr(match, "extracted_context") and match.extracted_context:
            context_preview = match.extracted_context[:80]
            if len(match.extracted_context) > 80:
                context_preview += "..."
            context_label = "コンテキスト" if self.language == "ja" else "Context"
            self.console.print(f"  {context_label}: [dim]{context_preview}[/dim]")

        # 検出根拠
        if hasattr(match, "supporting_evidence") and match.supporting_evidence:
            evidence_label = "検出根拠" if self.language == "ja" else "Evidence"
            self.console.print(f"  {evidence_label}:")
            for evidence in match.supporting_evidence[:3]:
                self.console.print(f"    • {evidence}")

        self.console.print()

    def _display_summary_enhanced(self, summary: str) -> None:
        """要約の拡張表示"""
        summary_panel = Panel(
            summary,
            title=f"📋 {self.messages['summary']}",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(summary_panel)
        self.console.print()

    def _display_root_causes_enhanced(self, root_causes: list[Any]) -> None:
        """根本原因の拡張表示"""
        self.console.print(f"[bold red]🔍 {self.messages['root_causes']}:[/bold red]")
        self.console.print()

        for i, cause in enumerate(root_causes, 1):
            # 原因の重要度に応じた色分け
            if hasattr(cause, "confidence") and cause.confidence:
                if cause.confidence >= 0.8:
                    cause_color = "red"
                elif cause.confidence >= 0.6:
                    cause_color = "yellow"
                else:
                    cause_color = "blue"
            else:
                cause_color = "white"

            self.console.print(f"[{cause_color}]{i}. {cause.description}[/{cause_color}]")

            # 詳細情報
            if hasattr(cause, "file_path") and cause.file_path:
                file_label = "ファイル" if self.language == "ja" else "File"
                self.console.print(f"   {file_label}: [cyan]{cause.file_path}[/cyan]")

            if hasattr(cause, "line_number") and cause.line_number:
                line_label = "行番号" if self.language == "ja" else "Line"
                self.console.print(f"   {line_label}: [cyan]{cause.line_number}[/cyan]")

            if hasattr(cause, "confidence") and cause.confidence > 0:
                self.console.print(f"   {self.messages['confidence']}: [green]{cause.confidence:.1%}[/green]")

            self.console.print()

    def _display_fix_suggestions_enhanced(self, fix_suggestions: list[FixSuggestion]) -> None:
        """修正提案の拡張表示"""
        self.console.print(f"[bold green]🔧 {self.messages['fix_suggestions']}:[/bold green]")
        self.console.print()

        # 修正提案ランキングテーブル
        if len(fix_suggestions) > 1:
            self._display_fix_ranking_table(fix_suggestions)

        # 各修正提案の詳細
        for i, fix in enumerate(fix_suggestions, 1):
            self._display_single_fix_enhanced(fix, i)

        # 推奨修正案の表示
        if fix_suggestions:
            self._display_recommended_fix(fix_suggestions)

    def _display_fix_ranking_table(self, fix_suggestions: list[FixSuggestion]) -> None:
        """修正提案ランキングテーブル"""
        ranking_label = (
            "修正提案ランキング (効果・安全性順)"
            if self.language == "ja"
            else "Fix Suggestions Ranking (by Effectiveness & Safety)"
        )
        self.console.print(f"[bold blue]{ranking_label}:[/bold blue]")

        ranking_table = Table(show_header=True, header_style="bold blue", box=None)
        ranking_table.add_column("順位" if self.language == "ja" else "Rank", style="cyan", width=4)
        ranking_table.add_column(self.messages["fix_title"], style="white", width=25)
        ranking_table.add_column(self.messages["effectiveness"], style="green", width=8)
        ranking_table.add_column(self.messages["safety"], style="yellow", width=8)
        ranking_table.add_column(self.messages["risk_level"], style="red", width=8)
        ranking_table.add_column(self.messages["overall_rating"], style="blue", width=10)

        # 修正提案をスコアでソート
        scored_fixes = self._score_fix_suggestions(fix_suggestions)

        for i, (fix, effectiveness, safety, risk_score, overall) in enumerate(scored_fixes[:5], 1):
            # 色分け
            eff_color = "green" if effectiveness >= 0.8 else "yellow" if effectiveness >= 0.6 else "red"
            safety_color = "green" if safety >= 0.8 else "yellow" if safety >= 0.6 else "red"
            risk_color = "green" if risk_score <= 0.3 else "yellow" if risk_score <= 0.6 else "red"
            overall_color = "green" if overall >= 0.8 else "yellow" if overall >= 0.6 else "red"

            title_display = fix.title[:22] + "..." if len(fix.title) > 25 else fix.title

            ranking_table.add_row(
                str(i),
                title_display,
                f"[{eff_color}]{effectiveness:.1%}[/{eff_color}]",
                f"[{safety_color}]{safety:.1%}[/{safety_color}]",
                f"[{risk_color}]{risk_score:.1%}[/{risk_color}]",
                f"[{overall_color}]{overall:.1%}[/{overall_color}]",
            )

        self.console.print(ranking_table)
        self.console.print()

    def _display_single_fix_enhanced(self, fix: FixSuggestion, index: int) -> None:
        """単一修正提案の拡張表示"""
        # 優先度に応じた色分け
        priority_colors = {"urgent": "red", "high": "yellow", "medium": "blue", "low": "dim"}
        priority_str = fix.priority.value if hasattr(fix.priority, "value") else str(fix.priority)
        priority_color = priority_colors.get(priority_str.lower(), "blue")

        title = f"修正案 {index}: {fix.title}" if self.language == "ja" else f"Fix {index}: {fix.title}"
        self.console.print(f"[bold {priority_color}]{title}[/bold {priority_color}]")

        # 基本情報
        self.console.print(f"  {self.messages['description']}: {fix.description}")

        # 信頼度表示
        if hasattr(fix, "confidence") and fix.confidence > 0:
            confidence_color = "green" if fix.confidence >= 0.8 else "yellow" if fix.confidence >= 0.6 else "red"
            self.console.print(
                f"  {self.messages['confidence']}: [{confidence_color}]{fix.confidence:.1%}[/{confidence_color}]"
            )

        # 背景理由（新機能）
        if hasattr(fix, "background_reason") and fix.background_reason:
            reason_label = "背景理由" if self.language == "ja" else "Background"
            self.console.print(f"  [bold cyan]{reason_label}:[/bold cyan] {fix.background_reason}")

        # 影響評価（新機能）
        if hasattr(fix, "impact_assessment") and fix.impact_assessment:
            impact_label = "影響評価" if self.language == "ja" else "Impact"
            self.console.print(f"  [bold yellow]{impact_label}:[/bold yellow] {fix.impact_assessment}")

        # リスクと時間の詳細
        self._display_risk_and_time_details_enhanced(fix)

        # 影響ファイル
        if hasattr(fix, "code_changes") and fix.code_changes:
            files = {change.file_path for change in fix.code_changes if change.file_path}
            if files:
                files_list = list(files)[:3]
                files_text = ", ".join(files_list)
                if len(files) > 3:
                    more_text = (
                        f"... 他 {len(files) - 3} ファイル" if self.language == "ja" else f"... {len(files) - 3} more"
                    )
                    files_text += f" {more_text}"
                self.console.print(f"  {self.messages['affected_files']}: {files_text}")

        # 前提条件
        if hasattr(fix, "prerequisites") and fix.prerequisites:
            prereq_label = "前提条件" if self.language == "ja" else "Prerequisites"
            self.console.print(f"  [bold magenta]{prereq_label}:[/bold magenta]")
            for prereq in fix.prerequisites[:3]:
                self.console.print(f"    • {prereq}")

        # 検証ステップ
        if hasattr(fix, "validation_steps") and fix.validation_steps:
            validation_label = "検証ステップ" if self.language == "ja" else "Validation"
            self.console.print(f"  [bold green]{validation_label}:[/bold green]")
            for step in fix.validation_steps[:3]:
                self.console.print(f"    • {step}")

        # 参考リンク
        if hasattr(fix, "references") and fix.references:
            ref_label = "参考" if self.language == "ja" else "References"
            self.console.print(f"  {ref_label}:")
            for ref in fix.references[:2]:
                self.console.print(f"    • {ref}")

        self.console.print()

    def _display_risk_and_time_details_enhanced(self, fix: FixSuggestion) -> None:
        """リスクと時間の詳細表示"""
        # リスクレベル
        risk_level = getattr(fix, "risk_level", "medium")
        risk_colors = {"low": "green", "medium": "yellow", "high": "red"}
        risk_color = risk_colors.get(risk_level, "yellow")
        risk_text = self.messages.get(risk_level, risk_level)
        self.console.print(f"  {self.messages['risk_level']}: [{risk_color}]{risk_text.upper()}[/{risk_color}]")

        # 推定時間
        if hasattr(fix, "estimated_time_minutes") and fix.estimated_time_minutes > 0:
            time_str = self._format_time_duration(fix.estimated_time_minutes)
            self.console.print(f"  {self.messages['estimated_effort']}: {time_str}")
        elif fix.estimated_effort != "不明":
            self.console.print(f"  {self.messages['estimated_effort']}: {fix.estimated_effort}")

        # 自動適用可能性
        auto_applicable = getattr(fix, "auto_applicable", False)
        auto_text = self.messages["yes"] if auto_applicable else self.messages["no"]
        auto_color = "green" if auto_applicable else "red"
        self.console.print(f"  {self.messages['auto_applicable']}: [{auto_color}]{auto_text}[/{auto_color}]")

        # 効果と安全性のスコア
        effectiveness_score = getattr(fix, "effectiveness_score", 0.0)
        safety_score = getattr(fix, "safety_score", 0.0)

        if effectiveness_score > 0 or safety_score > 0:
            score_table = Table(show_header=False, box=None, padding=(0, 1))
            score_table.add_column("項目" if self.language == "ja" else "Metric", style="dim")
            score_table.add_column("スコア" if self.language == "ja" else "Score", style="bold")

            if effectiveness_score > 0:
                eff_color = "green" if effectiveness_score >= 0.8 else "yellow" if effectiveness_score >= 0.6 else "red"
                score_table.add_row(
                    self.messages["effectiveness"], f"[{eff_color}]{effectiveness_score:.1%}[/{eff_color}]"
                )

            if safety_score > 0:
                safety_color = "green" if safety_score >= 0.8 else "yellow" if safety_score >= 0.6 else "red"
                score_table.add_row(self.messages["safety"], f"[{safety_color}]{safety_score:.1%}[/{safety_color}]")

            eval_label = "評価スコア" if self.language == "ja" else "Evaluation"
            self.console.print(f"  {eval_label}:")
            self.console.print(score_table)

    def _display_recommended_fix(self, fix_suggestions: list[FixSuggestion]) -> None:
        """推奨修正案の表示"""
        if not fix_suggestions:
            return

        scored_fixes = self._score_fix_suggestions(fix_suggestions)
        if not scored_fixes:
            return

        best_fix = scored_fixes[0][0]
        recommended_label = "推奨修正案" if self.language == "ja" else "Recommended Fix"
        self.console.print(f"[bold green]🎯 {recommended_label}: {best_fix.title}[/bold green]")

        # 推奨理由
        reasons = []
        effectiveness, safety, risk_score, overall = scored_fixes[0][1:]

        if effectiveness >= 0.8:
            reasons.append("高い効果が期待できます" if self.language == "ja" else "High effectiveness expected")
        if safety >= 0.8:
            reasons.append("安全性が高く低リスクです" if self.language == "ja" else "High safety, low risk")
        if risk_score <= 0.3:
            reasons.append("実装リスクが低いです" if self.language == "ja" else "Low implementation risk")

        if reasons:
            reason_label = "理由" if self.language == "ja" else "Reason"
            self.console.print(f"  {reason_label}: {', '.join(reasons)}")

        self.console.print()

    def _display_related_errors_enhanced(self, related_errors: list[str]) -> None:
        """関連エラーの拡張表示"""
        self.console.print(f"[bold yellow]⚠️  {self.messages['related_errors']}:[/bold yellow]")

        # エラーを重要度でソート
        sorted_errors = self._sort_errors_by_importance(related_errors)

        for i, error in enumerate(sorted_errors[:5], 1):  # 上位5つ
            # エラーの重要度を判定
            importance = self._calculate_error_importance(error)
            if importance >= 0.8:
                error_color = "red"
                icon = "🔴"
            elif importance >= 0.6:
                error_color = "yellow"
                icon = "🟡"
            else:
                error_color = "blue"
                icon = "🔵"

            # エラーメッセージを短縮
            display_error = error[:80] + "..." if len(error) > 80 else error
            self.console.print(f"  {icon} [{error_color}]{display_error}[/{error_color}]")

        if len(related_errors) > 5:
            more_count = len(related_errors) - 5
            more_text = f"... 他 {more_count} 個" if self.language == "ja" else f"... {more_count} more"
            self.console.print(f"  [dim]{more_text}[/dim]")

        self.console.print()

    def _display_statistics_enhanced(self, result: AnalysisResult) -> None:
        """統計情報の拡張表示"""
        stats_table = Table(title=f"📊 {self.messages['statistics']}", show_header=False, box=None)
        stats_table.add_column("項目" if self.language == "ja" else "Item", style="cyan")
        stats_table.add_column("値" if self.language == "ja" else "Value", style="white")

        # 信頼度
        confidence_color = (
            "green" if result.confidence_score >= 0.8 else "yellow" if result.confidence_score >= 0.6 else "red"
        )
        stats_table.add_row(
            self.messages["confidence"], f"[{confidence_color}]{result.confidence_score:.1%}[/{confidence_color}]"
        )

        # 分析時間
        time_str = f"{result.analysis_time:.2f} {self.messages['seconds']}"
        stats_table.add_row(self.messages["analysis_time"], time_str)

        # プロバイダーとモデル
        stats_table.add_row(self.messages["provider"], result.provider)
        stats_table.add_row(self.messages["model"], result.model)

        # トークン使用量とコスト
        if result.tokens_used:
            stats_table.add_row(self.messages["tokens_used"], f"{result.tokens_used.total_tokens:,}")
            stats_table.add_row(self.messages["estimated_cost"], f"${result.tokens_used.estimated_cost:.4f}")

        # キャッシュヒット
        cache_text = self.messages["yes"] if result.cache_hit else self.messages["no"]
        cache_color = "green" if result.cache_hit else "dim"
        stats_table.add_row(self.messages["cache_hit"], f"[{cache_color}]{cache_text}[/{cache_color}]")

        self.console.print(stats_table)
        self.console.print()

    def _display_fallback_info(self, result: AnalysisResult) -> None:
        """フォールバック情報の表示"""
        if result.status.value != "fallback":
            return

        fallback_panel = Panel(
            self._build_fallback_content(result),
            title="⚠️  フォールバック情報" if self.language == "ja" else "⚠️  Fallback Information",
            title_align="left",
            border_style="yellow",
            padding=(1, 2),
        )
        self.console.print(fallback_panel)
        self.console.print()

    def _build_fallback_content(self, result: AnalysisResult) -> str:
        """フォールバック情報の内容を構築"""
        content_lines = []

        if hasattr(result, "fallback_reason") and result.fallback_reason:
            reason_label = "理由" if self.language == "ja" else "Reason"
            content_lines.append(f"{reason_label}: {result.fallback_reason}")

        if hasattr(result, "retry_available") and result.retry_available:
            if hasattr(result, "retry_after") and result.retry_after:
                retry_text = (
                    f"{result.retry_after}秒後にリトライできます"
                    if self.language == "ja"
                    else f"Retry available in {result.retry_after} seconds"
                )
            else:
                retry_text = "すぐにリトライできます" if self.language == "ja" else "Retry available now"
            content_lines.append(f"💡 {retry_text}")

        if hasattr(result, "alternative_providers") and result.alternative_providers:
            providers_text = ", ".join(result.alternative_providers)
            alt_label = "代替プロバイダー" if self.language == "ja" else "Alternative providers"
            content_lines.append(f"💡 {alt_label}: {providers_text}")

        # 操作ID
        operation_id = f"fallback_{result.timestamp.strftime('%Y%m%d_%H%M%S')}"
        content_lines.append(f"{self.messages['operation_id']}: {operation_id}")

        retry_cmd = f"ci-run analyze --retry {operation_id}"
        content_lines.append(f"{self.messages['retry_command']}: {retry_cmd}")

        return "\n".join(content_lines)

    def _format_as_json(self, result: AnalysisResult) -> None:
        """JSON形式で表示"""
        from dataclasses import asdict

        json_data = asdict(result)
        self.console.print(json.dumps(json_data, indent=2, ensure_ascii=False, default=str))

    def _format_as_table(self, result: AnalysisResult) -> None:
        """テーブル形式で表示"""
        table = Table(title=self.messages["analysis_result"])
        table.add_column("項目" if self.language == "ja" else "Item", style="cyan")
        table.add_column("内容" if self.language == "ja" else "Content", style="white")

        if result.summary:
            table.add_row(self.messages["summary"], result.summary)

        if result.root_causes:
            causes_text = "\n".join(f"{i}. {cause.description}" for i, cause in enumerate(result.root_causes, 1))
            table.add_row(self.messages["root_causes"], causes_text)

        if result.fix_suggestions:
            suggestions_text = "\n".join(f"{i}. {fix.title}" for i, fix in enumerate(result.fix_suggestions, 1))
            table.add_row(self.messages["fix_suggestions"], suggestions_text)

        self.console.print(table)

    def _format_as_markdown(self, result: AnalysisResult) -> None:
        """Markdown形式で表示（従来の実装を使用）"""
        # 既存のMarkdown表示機能を呼び出し
        from ..commands.analyze import _display_result_as_markdown

        _display_result_as_markdown(result, self.console)

    def _score_fix_suggestions(
        self, fix_suggestions: list[FixSuggestion]
    ) -> list[Tuple[FixSuggestion, float, float, float, float]]:
        """修正提案をスコア付けしてソート"""
        scored_fixes = []

        for fix in fix_suggestions:
            effectiveness = getattr(fix, "effectiveness_score", getattr(fix, "confidence", 0.5))
            safety = getattr(fix, "safety_score", 1.0 - self._calculate_risk_score(fix))
            risk_score = self._calculate_risk_score(fix)
            overall = effectiveness * 0.4 + safety * 0.4 + (1.0 - risk_score) * 0.2

            scored_fixes.append((fix, effectiveness, safety, risk_score, overall))

        # 総合評価でソート（降順）
        scored_fixes.sort(key=lambda x: x[4], reverse=True)
        return scored_fixes

    def _calculate_risk_score(self, fix_suggestion: FixSuggestion) -> float:
        """修正提案のリスクスコアを計算"""
        risk_score = 0.0

        # リスクレベルによる基本スコア
        risk_level = getattr(fix_suggestion, "risk_level", "medium")
        risk_level_scores = {"low": 0.2, "medium": 0.5, "high": 0.8}
        risk_score += risk_level_scores.get(risk_level, 0.5)

        # 優先度によるリスク
        priority = getattr(fix_suggestion, "priority", Priority.MEDIUM)
        priority_str = priority.value if hasattr(priority, "value") else str(priority)
        priority_risks = {"urgent": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
        risk_score += priority_risks.get(priority_str.lower(), 0.3) * 0.3

        # ファイル変更数によるリスク
        if hasattr(fix_suggestion, "code_changes") and fix_suggestion.code_changes:
            file_count = len({change.file_path for change in fix_suggestion.code_changes if change.file_path})
            risk_score += min(file_count * 0.05, 0.2)

        return min(risk_score, 1.0)

    def _sort_errors_by_importance(self, errors: list[str]) -> list[str]:
        """エラーを重要度でソート"""
        scored_errors = [(error, self._calculate_error_importance(error)) for error in errors]
        scored_errors.sort(key=lambda x: x[1], reverse=True)
        return [error for error, _ in scored_errors]

    def _calculate_error_importance(self, error: str) -> float:
        """エラーの重要度を計算"""
        importance = 0.0
        error_lower = error.lower()

        # 重要なキーワードによる重み付け
        critical_keywords = ["critical", "fatal", "error", "failed", "exception"]
        warning_keywords = ["warning", "warn"]
        info_keywords = ["info", "debug", "trace"]

        for keyword in critical_keywords:
            if keyword in error_lower:
                importance += 0.8
                break

        for keyword in warning_keywords:
            if keyword in error_lower:
                importance += 0.5
                break

        for keyword in info_keywords:
            if keyword in error_lower:
                importance += 0.2
                break

        # エラーの長さによる重み付け
        if len(error) > 100:
            importance += 0.1

        return min(importance, 1.0)

    def _format_time_duration(self, minutes: int) -> str:
        """時間を適切な単位でフォーマット"""
        if minutes < 60:
            return f"{minutes} {self.messages['minutes']}"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes > 0:
                return f"{hours} {self.messages['hours']} {remaining_minutes} {self.messages['minutes']}"
            else:
                return f"{hours} {self.messages['hours']}"


class ProgressReporter:
    """進捗レポーター"""

    def __init__(self, console: Console, language: str = "ja"):
        self.console = console
        self.language = language

    def create_analysis_progress(self) -> Progress:
        """分析進捗バーを作成"""
        if self.language == "ja":
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            )
        else:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            )

    def show_step_progress(self, step_name: str, current: int, total: int) -> None:
        """ステップ進捗を表示"""
        percentage = (current / total) * 100 if total > 0 else 0

        if self.language == "ja":
            self.console.print(f"[blue]📋 {step_name}: {current}/{total} ({percentage:.1f}%)[/blue]")
        else:
            self.console.print(f"[blue]📋 {step_name}: {current}/{total} ({percentage:.1f}%)[/blue]")


def create_enhanced_formatter(console: Console, language: str = "ja") -> EnhancedAnalysisFormatter:
    """拡張フォーマッターを作成

    Args:
        console: Richコンソール
        language: 表示言語（ja/en）

    Returns:
        拡張フォーマッター
    """
    return EnhancedAnalysisFormatter(console, language)
