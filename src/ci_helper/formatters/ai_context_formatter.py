"""AI消費用コンテキスト強化フォーマッター

AI分析に最適化されたMarkdown形式でCI実行結果をフォーマットします。
失敗の優先度付け、詳細なコンテキスト情報、修正提案を含む高品質な出力を提供します。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from ..core.models import ExecutionResult, Failure

from ..core.models import FailureType
from .base_formatter import BaseLogFormatter
from .streaming_formatter import StreamingFailureInfo, StreamingFormatterMixin


class FailureTypeConfigEntry(TypedDict):
    """失敗タイプ設定"""

    icon: str
    priority: int
    category: str


class FixSuggestionDetail(TypedDict):
    """修正提案の詳細"""

    title: str
    description: str
    steps: list[str]


class AIContextFormatter(StreamingFormatterMixin, BaseLogFormatter):
    """AI分析に最適化されたコンテキスト強化フォーマッター

    このフォーマッターは以下の特徴を持ちます：
    - 失敗の優先度付けによる重要な問題の強調
    - 詳細なコンテキスト情報の提供
    - 修正提案セクションの自動生成
    - 関連ファイル情報の整理
    """

    def __init__(self, sanitize_secrets: bool = True):
        """フォーマッターを初期化

        Args:
            sanitize_secrets: シークレットのサニタイズを有効にするかどうか

        """
        super().__init__(sanitize_secrets)

        # 失敗タイプ別のアイコンと優先度
        self.failure_type_config: dict[FailureType, FailureTypeConfigEntry] = {
            FailureType.ASSERTION: {"icon": "❌", "priority": 100, "category": "テスト失敗"},
            FailureType.ERROR: {"icon": "🚨", "priority": 90, "category": "実行エラー"},
            FailureType.BUILD_FAILURE: {"icon": "🔨", "priority": 85, "category": "ビルド失敗"},
            FailureType.TIMEOUT: {"icon": "⏰", "priority": 80, "category": "タイムアウト"},
            FailureType.TEST_FAILURE: {"icon": "🧪", "priority": 75, "category": "テスト失敗"},
            FailureType.UNKNOWN: {"icon": "❓", "priority": 50, "category": "不明なエラー"},
        }

    def format(self, execution_result: ExecutionResult, **options: Any) -> str:
        """AI消費用に最適化されたMarkdownを生成

        Args:
            execution_result: CI実行結果
            **options: フォーマットオプション
                - max_failures: 表示する最大失敗数（デフォルト: 10）
                - include_context: コンテキスト情報を含めるか（デフォルト: True）
                - include_suggestions: 修正提案を含めるか（デフォルト: True）
                - include_related_files: 関連ファイル情報を含めるか（デフォルト: True）
                - detail_level: 詳細レベル（minimal/normal/detailed）
                - verbose_level: 詳細レベル（detail_levelのエイリアス、後方互換性のため）
                - filter_errors: エラーのみをフィルタリングするか

        Returns:
            AI消費用に最適化されたMarkdown文字列

        """
        # verbose_level を detail_level にマッピング（後方互換性のため）
        if "verbose_level" in options and "detail_level" not in options:
            options = dict(options)  # コピーを作成
            options["detail_level"] = options.pop("verbose_level")

        # オプションの検証と正規化
        validated_options = self.validate_options(**options)

        # AI Context Formatter固有のデフォルト値設定
        validated_options.setdefault("detail_level", "normal")
        validated_options.setdefault("filter_errors", False)
        validated_options.setdefault("max_failures", None)

        # オプションの処理
        max_failures = validated_options.get("max_failures") or 10
        include_context = validated_options.get("include_context", True)
        include_suggestions = validated_options.get("include_suggestions", True)
        include_related_files = validated_options.get("include_related_files", True)
        detail_level = validated_options.get("detail_level", "normal")
        validated_options.get("filter_errors", False)

        # 詳細レベルに基づく調整
        if detail_level == "minimal":
            max_failures = min(max_failures if max_failures is not None else 5, 5)
            include_context = False
            include_related_files = False
        elif detail_level == "detailed":
            max_failures = max_failures if max_failures is not None else 20
            include_context = True
            include_suggestions = True
            include_related_files = True

        sections: list[str] = []

        # クイックサマリー（最重要情報を最初に）
        sections.append(self._format_quick_summary(execution_result))

        # クリティカル失敗（優先度順）
        if not execution_result.success:
            sections.append(
                self._format_critical_failures(
                    execution_result,
                    max_failures=max_failures,
                    include_context=include_context,
                ),
            )

        # 修正提案セクション
        if include_suggestions and not execution_result.success:
            sections.append(self._format_suggested_fixes(execution_result))

        # 関連ファイル情報
        if include_related_files and not execution_result.success:
            sections.append(self._format_related_files(execution_result))

        # 詳細なコンテキスト分析
        sections.append(self._format_context_analysis(execution_result))

        # 完全なログ情報（最後に配置）
        sections.append(self._format_full_logs(execution_result))

        # セクションを結合
        markdown_content = "\n\n---\n\n".join(filter(None, sections))

        # シークレットのサニタイズ
        if self.sanitize_secrets:
            markdown_content = self._sanitize_content(markdown_content)

        return markdown_content

    def get_format_name(self) -> str:
        """フォーマット名を取得"""
        return "ai"

    def get_description(self) -> str:
        """フォーマットの説明を取得"""
        return "AI分析に最適化されたコンテキスト強化Markdown形式"

    def get_supported_options(self) -> list[str]:
        """サポートされているオプション一覧を取得"""
        return [
            "max_failures",
            "include_context",
            "include_suggestions",
            "include_related_files",
            "detail_level",
            "verbose_level",  # 後方互換性のため
            "filter_errors",
        ]

    def _format_quick_summary(self, execution_result: ExecutionResult) -> str:
        """クイックサマリーを生成（AI分析用の最重要情報）"""
        status_icon = "✅" if execution_result.success else "❌"
        status_text = "成功" if execution_result.success else "失敗"

        # 実行時間の分析
        total_duration = execution_result.total_duration or 0.0
        duration_text = f"{total_duration:.1f}秒"
        if total_duration > 300:  # 5分以上
            duration_text += " ⚠️ 長時間実行"
        elif total_duration > 60:  # 1分以上
            duration_text += " ⏱️ やや長時間"

        # 失敗の概要
        failure_summary = ""
        if not execution_result.success:
            critical_failures = self._prioritize_failures(execution_result.all_failures)[:3]
            failure_types = [f.type.value for f in critical_failures]
            failure_summary = f"\n**主要な失敗タイプ**: {', '.join(set(failure_types))}"

        # ワークフロー情報
        failed_workflows = [w for w in execution_result.workflows if not w.success]
        workflow_info = f"**ワークフロー**: {len(execution_result.workflows)}個"
        if failed_workflows:
            workflow_info += f" (失敗: {len(failed_workflows)}個)"

        return f"""# 🎯 CI実行結果クイックサマリー

**ステータス**: {status_icon} {status_text}
**実行時間**: {duration_text}
{workflow_info}
**総失敗数**: {execution_result.total_failures}件{failure_summary}

**実行時刻**: {execution_result.timestamp.strftime("%Y-%m-%d %H:%M:%S")}"""

    def _format_critical_failures(
        self,
        execution_result: ExecutionResult,
        max_failures: int = 10,
        include_context: bool = True,
    ) -> str:
        """クリティカルな失敗を優先度順に詳細整形"""
        if execution_result.success:
            return ""

        # 失敗を優先度順にソート
        prioritized_failures = self._prioritize_failures(execution_result.all_failures)
        top_failures = prioritized_failures[:max_failures] if max_failures else prioritized_failures

        sections: list[str] = ["## 🚨 クリティカル失敗 (修正必須)"]

        if max_failures and len(prioritized_failures) > max_failures:
            sections.append(f"*注意: 全{len(prioritized_failures)}件の失敗のうち、上位{max_failures}件を表示*")

        for i, failure in enumerate(top_failures, 1):
            # 失敗が発生したワークフローとジョブを特定
            workflow_name, job_name = self._find_failure_location(failure, execution_result)
            sections.append(self._format_single_failure_detailed(failure, i, workflow_name, job_name, include_context))

        return "\n\n".join(sections)

    def _format_single_failure_detailed(
        self,
        failure: Failure,
        failure_num: int,
        workflow_name: str,
        job_name: str,
        include_context: bool = True,
    ) -> str:
        """単一の失敗を詳細に整形"""
        config = self.failure_type_config.get(failure.type, self.failure_type_config[FailureType.UNKNOWN])
        icon = config["icon"]
        category = config["category"]

        sections = [f"### {failure_num}. {icon} {category}: {failure.type.value.upper()}"]

        # 基本情報
        sections.append(f"**場所**: {workflow_name} → {job_name}")

        # ファイル情報
        if failure.file_path:
            location = f"`{failure.file_path}`"
            if failure.line_number:
                location += f" (行 {failure.line_number})"
            sections.append(f"**ファイル**: {location}")

        # エラーメッセージ（重要度に応じて強調）
        sections.append("**エラーメッセージ**:")
        sections.append(f"```\n{failure.message}\n```")

        # コードコンテキスト（前後の行）
        if include_context and (failure.context_before or failure.context_after):
            sections.append(self._format_code_context(failure))

        # 根本原因分析
        root_cause = self._analyze_root_cause(failure)
        if root_cause:
            sections.append(f"**根本原因分析**: {root_cause}")

        # スタックトレース（要約版）
        if failure.stack_trace:
            sections.append("**スタックトレース**:")
            sections.append(f"```\n{self._summarize_stack_trace(failure.stack_trace)}\n```")

        return "\n".join(sections)

    def _format_code_context(self, failure: Failure) -> str:
        """コードコンテキストを整形"""
        if not (failure.context_before or failure.context_after):
            return ""

        sections = ["**コードコンテキスト**:"]

        # 行番号を計算
        start_line = (failure.line_number or 1) - len(failure.context_before)

        context_lines = ["```python"]

        # 前のコンテキスト
        for i, line in enumerate(failure.context_before):
            line_num = start_line + i
            context_lines.append(f"{line_num:4d} | {line}")

        # エラー行（推定）
        if failure.line_number:
            context_lines.append(f"{failure.line_number:4d} | {failure.message}  # ❌ ERROR HERE")

        # 後のコンテキスト
        for i, line in enumerate(failure.context_after):
            line_num = (failure.line_number or 1) + i + 1
            context_lines.append(f"{line_num:4d} | {line}")

        context_lines.append("```")
        sections.extend(context_lines)

        return "\n".join(sections)

    def _format_suggested_fixes(self, execution_result: ExecutionResult) -> str:
        """修正提案セクションを生成"""
        if execution_result.success:
            return ""

        sections = ["## 💡 修正提案"]

        # 失敗を分析して修正提案を生成
        prioritized_failures = self._prioritize_failures(execution_result.all_failures)[:5]

        suggestions: list[FixSuggestionDetail] = []
        for failure in prioritized_failures:
            suggestion = self._generate_fix_suggestion(failure)
            if suggestion:
                suggestions.append(suggestion)

        if suggestions:
            sections.append("### 具体的な修正手順")
            for i, suggestion in enumerate(suggestions, 1):
                sections.append(f"**{i}. {suggestion['title']}**")
                sections.append(f"- {suggestion['description']}")
                steps = suggestion["steps"]
                if steps:
                    sections.append("- 手順:")
                    for step in steps:
                        sections.append(f"  - {step}")
                sections.append("")
        else:
            sections.append("自動的な修正提案を生成できませんでした。ログの詳細を確認してください。")

        return "\n".join(sections)

    def _format_related_files(self, execution_result: ExecutionResult) -> str:
        """関連ファイル情報を整形"""
        if execution_result.success:
            return ""

        # 失敗に関連するファイルを収集
        related_files: set[str] = set()
        for failure in execution_result.all_failures:
            if failure.file_path:
                related_files.add(failure.file_path)

        if not related_files:
            return ""

        sections = ["## 📁 関連ファイル情報"]

        # ファイルタイプ別に分類
        file_categories: dict[str, list[str]] = {
            "テストファイル": [],
            "設定ファイル": [],
            "ソースコード": [],
            "その他": [],
        }

        for file_path in sorted(related_files):
            category = self._categorize_file(file_path)
            file_categories[category].append(file_path)

        for category, files in file_categories.items():
            if files:
                sections.append(f"### {category}")
                for file_path in files:
                    failure_count = sum(1 for f in execution_result.all_failures if f.file_path == file_path)
                    sections.append(f"- `{file_path}` ({failure_count}件の失敗)")

        return "\n".join(sections)

    def _format_context_analysis(self, execution_result: ExecutionResult) -> str:
        """詳細なコンテキスト分析を生成"""
        sections: list[str] = ["## 📊 コンテキスト分析"]

        # 実行環境情報
        sections.append("### 実行環境")
        sections.append(f"- 総実行時間: {execution_result.total_duration:.2f}秒")
        sections.append(f"- ワークフロー数: {len(execution_result.workflows)}")

        total_jobs = sum(len(w.jobs) for w in execution_result.workflows)
        successful_jobs = sum(1 for w in execution_result.workflows for j in w.jobs if j.success)
        sections.append(f"- 総ジョブ数: {total_jobs} (成功: {successful_jobs}, 失敗: {total_jobs - successful_jobs})")

        # 失敗パターン分析
        if not execution_result.success:
            sections.append("### 失敗パターン分析")
            failure_patterns = self._analyze_failure_patterns(execution_result.all_failures)
            for pattern, count in failure_patterns.items():
                sections.append(f"- {pattern}: {count}件")

        return "\n".join(sections)

    def _format_full_logs(self, execution_result: ExecutionResult) -> str:
        """完全なログ情報を整形（最後に配置）"""
        sections: list[str] = ["## 📋 完全なログ情報"]

        for workflow in execution_result.workflows:
            workflow_icon = "✅" if workflow.success else "❌"
            sections.append(f"### {workflow_icon} ワークフロー: {workflow.name}")
            sections.append(f"- 実行時間: {workflow.duration:.2f}秒")
            sections.append(f"- ステータス: {'成功' if workflow.success else '失敗'}")

            if workflow.jobs:
                sections.append("#### ジョブ詳細")
                for job in workflow.jobs:
                    job_icon = "✅" if job.success else "❌"
                    failure_info = f" ({len(job.failures)}件の失敗)" if job.failures else ""
                    sections.append(f"- {job_icon} **{job.name}**: {job.duration:.2f}秒{failure_info}")

        return "\n".join(sections)

    def _prioritize_failures(self, failures: Sequence[Failure]) -> list[Failure]:
        """失敗を優先度順にソート"""

        def calculate_priority_score(failure: Failure) -> int:
            """失敗の優先度スコアを計算"""
            # 基本優先度（失敗タイプ別）
            config = self.failure_type_config.get(failure.type, self.failure_type_config[FailureType.UNKNOWN])
            base_priority = config["priority"]

            # 追加スコア
            additional_score = 0

            # ファイル情報があるものを優先
            if failure.file_path:
                additional_score += 20

            # 行番号があるものを優先
            if failure.line_number:
                additional_score += 15

            # スタックトレースがあるものを優先
            if failure.stack_trace:
                additional_score += 10

            # コンテキスト情報があるものを優先
            if failure.context_before or failure.context_after:
                additional_score += 5

            return base_priority + additional_score

        return sorted(failures, key=calculate_priority_score, reverse=True)

    def _find_failure_location(self, failure: Failure, execution_result: ExecutionResult) -> tuple[str, str]:
        """失敗が発生したワークフローとジョブを特定"""
        for workflow in execution_result.workflows:
            for job in workflow.jobs:
                if failure in job.failures:
                    return workflow.name, job.name
        return "不明", "不明"

    def _analyze_root_cause(self, failure: Failure) -> str | None:
        """失敗の根本原因を分析"""
        message = failure.message.lower()

        # よくあるパターンのマッチング
        patterns = {
            r"assertion.*failed|assert.*error": "アサーション失敗 - 期待値と実際の値が一致しません",
            r"file.*not.*found|no such file": "ファイルが見つかりません - パスを確認してください",
            r"permission.*denied|access.*denied": "権限エラー - ファイルまたはディレクトリのアクセス権限を確認してください",
            r"timeout|timed.*out": "タイムアウト - 処理時間が制限を超えました",
            r"connection.*refused|connection.*failed": "接続エラー - ネットワークまたはサービスの状態を確認してください",
            r"import.*error|module.*not.*found": "モジュールエラー - 依存関係のインストールを確認してください",
            r"syntax.*error": "構文エラー - コードの文法を確認してください",
            r"name.*error|undefined": "名前エラー - 変数または関数の定義を確認してください",
        }

        for pattern, cause in patterns.items():
            if re.search(pattern, message):
                return cause

        return None

    def _generate_fix_suggestion(self, failure: Failure) -> FixSuggestionDetail | None:
        """失敗に対する修正提案を生成"""
        message = failure.message.lower()

        # 失敗タイプ別の修正提案
        suggestions: dict[FailureType, FixSuggestionDetail] = {
            FailureType.ASSERTION: {
                "title": "アサーション失敗の修正",
                "description": "期待値と実際の値を確認し、テストロジックまたは実装を修正してください",
                "steps": [
                    "失敗したアサーションの期待値を確認",
                    "実際の値がなぜ異なるのかを調査",
                    "テストケースまたは実装コードを修正",
                ],
            },
            FailureType.BUILD_FAILURE: {
                "title": "ビルド失敗の修正",
                "description": "依存関係やビルド設定を確認してください",
                "steps": [
                    "依存関係のバージョンを確認",
                    "ビルド設定ファイルをチェック",
                    "必要なパッケージがインストールされているか確認",
                ],
            },
            FailureType.TIMEOUT: {
                "title": "タイムアウトの修正",
                "description": "処理時間を短縮するか、タイムアウト設定を調整してください",
                "steps": [
                    "処理のボトルネックを特定",
                    "不要な処理を削除または最適化",
                    "必要に応じてタイムアウト値を増加",
                ],
            },
        }

        base_suggestion = suggestions.get(failure.type)
        if not base_suggestion:
            return None

        suggestion: FixSuggestionDetail = {
            "title": base_suggestion["title"],
            "description": base_suggestion["description"],
            "steps": list(base_suggestion["steps"]),
        }

        # メッセージ内容に基づく具体的な提案を追加
        if "file not found" in message and failure.file_path:
            suggestion["steps"].insert(0, f"ファイル `{failure.file_path}` の存在を確認")

        if "permission denied" in message:
            suggestion["steps"].insert(0, "ファイルまたはディレクトリの権限を確認")

        return suggestion

    def _categorize_file(self, file_path: str) -> str:
        """ファイルをカテゴリ別に分類"""
        file_path_lower = file_path.lower()

        if any(pattern in file_path_lower for pattern in ["test", "spec", "__test__"]):
            return "テストファイル"
        if any(pattern in file_path_lower for pattern in [".yml", ".yaml", ".json", ".toml", ".ini", "config"]):
            return "設定ファイル"
        if any(file_path_lower.endswith(ext) for ext in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go"]):
            return "ソースコード"
        return "その他"

    def _analyze_failure_patterns(self, failures: Sequence[Failure]) -> dict[str, int]:
        """失敗パターンを分析"""
        patterns: dict[str, int] = {}

        for failure in failures:
            # 失敗タイプ別の集計
            failure_type = failure.type.value
            patterns[f"{failure_type}エラー"] = patterns.get(f"{failure_type}エラー", 0) + 1

            # ファイル拡張子別の集計
            if failure.file_path:
                ext = failure.file_path.split(".")[-1] if "." in failure.file_path else "unknown"
                pattern_key = f"{ext}ファイルでの失敗"
                patterns[pattern_key] = patterns.get(pattern_key, 0) + 1

        return patterns

    def _summarize_stack_trace(self, stack_trace: str) -> str:
        """スタックトレースを要約"""
        lines = stack_trace.split("\n")

        # 最初の数行と最後の数行のみを保持
        if len(lines) <= 10:
            return stack_trace

        summary_lines: list[str] = []
        summary_lines.extend(lines[:3])  # 最初の3行
        summary_lines.append("... (中略) ...")
        summary_lines.extend(lines[-3:])  # 最後の3行

        return "\n".join(summary_lines)

    def _format_with_streaming(self, execution_result: ExecutionResult, log_path: Path, **options: Any) -> str:
        """ストリーミング処理でAI消費用フォーマット実行

        Args:
            execution_result: CI実行結果
            log_path: ログファイルパス
            **options: フォーマットオプション

        Returns:
            フォーマット結果

        """
        from .streaming_formatter import ChunkedLogProcessor

        # チャンク処理器を初期化
        processor = ChunkedLogProcessor(self.performance_optimizer)

        # ストリーミングで失敗情報を抽出
        streaming_failures: list[StreamingFailureInfo] = []
        for failure_info in processor.extract_failures_streaming(log_path):
            streaming_failures.append(failure_info)

        # 抽出した失敗情報をExecutionResultに統合
        if streaming_failures:
            # 既存の失敗情報と統合
            enhanced_result = self._enhance_execution_result_with_streaming_data(execution_result, streaming_failures)
        else:
            enhanced_result = execution_result

        # 通常のフォーマット処理を実行
        return self.format(enhanced_result, **options)

    def _enhance_execution_result_with_streaming_data(
        self,
        execution_result: ExecutionResult,
        streaming_failures: list[StreamingFailureInfo],
    ) -> ExecutionResult:
        """ストリーミングデータでExecutionResultを強化

        Args:
            execution_result: 元のCI実行結果
            streaming_failures: ストリーミングで抽出した失敗情報

        Returns:
            強化されたExecutionResult

        """
        # 新しい失敗情報を既存のものと統合
        # 実装は簡略化版（実際にはより詳細な統合処理が必要）

        # ストリーミングで見つかった追加の失敗情報があれば
        # ExecutionResultに追加する処理をここに実装
        # 現在は元のexecution_resultをそのまま返す

        return execution_result
