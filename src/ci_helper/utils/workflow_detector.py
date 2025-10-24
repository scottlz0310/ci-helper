"""
ワークフロー検出ユーティリティ

GitHub Actionsワークフローファイルを検出・解析する機能を提供します。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from rich.console import Console


class WorkflowInfo:
    """ワークフロー情報"""

    def __init__(self, file_path: Path, name: str, description: str = "", jobs: list[str] | None = None):
        self.file_path = file_path
        self.name = name
        self.description = description
        self.jobs = jobs or []
        self.filename = file_path.name

    def __str__(self) -> str:
        return f"{self.name} ({self.filename})"


class WorkflowDetector:
    """ワークフロー検出クラス"""

    def __init__(self, console: Console | None = None):
        """初期化

        Args:
            console: Rich Console インスタンス
        """
        self.console = console or Console()

    def find_workflows(self, project_root: Path | None = None) -> list[WorkflowInfo]:
        """ワークフローファイルを検出

        Args:
            project_root: プロジェクトルートディレクトリ

        Returns:
            検出されたワークフロー情報のリスト
        """
        if project_root is None:
            project_root = Path.cwd()

        workflows_dir = project_root / ".github" / "workflows"

        if not workflows_dir.exists():
            return []

        workflows = []

        # .yml と .yaml ファイルを検索
        for pattern in ["*.yml", "*.yaml"]:
            for workflow_file in workflows_dir.glob(pattern):
                try:
                    workflow_info = self._parse_workflow_file(workflow_file)
                    if workflow_info:
                        workflows.append(workflow_info)
                except Exception as e:
                    self.console.print(f"[yellow]警告: {workflow_file.name} の解析に失敗: {e}[/yellow]")

        # ファイル名でソート
        workflows.sort(key=lambda w: w.filename)

        return workflows

    def _parse_workflow_file(self, file_path: Path) -> WorkflowInfo | None:
        """ワークフローファイルを解析

        Args:
            file_path: ワークフローファイルのパス

        Returns:
            ワークフロー情報（解析失敗時は None）
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # YAMLとして解析
            try:
                workflow_data = yaml.safe_load(content)
            except yaml.YAMLError:
                # YAML解析に失敗した場合は正規表現で基本情報を抽出
                return self._parse_workflow_with_regex(file_path, content)

            if not isinstance(workflow_data, dict):
                return None

            # ワークフロー名を取得
            name = workflow_data.get("name", file_path.stem)

            # 説明を生成
            description = self._generate_description(workflow_data)

            # ジョブ一覧を取得
            jobs = []
            if "jobs" in workflow_data and isinstance(workflow_data["jobs"], dict):
                jobs = list(workflow_data["jobs"].keys())

            return WorkflowInfo(file_path=file_path, name=name, description=description, jobs=jobs)

        except Exception as e:
            self.console.print(f"[dim]デバッグ: {file_path.name} 解析エラー: {e}[/dim]")
            return None

    def _parse_workflow_with_regex(self, file_path: Path, content: str) -> WorkflowInfo | None:
        """正規表現でワークフローファイルを解析（YAML解析失敗時のフォールバック）

        Args:
            file_path: ワークフローファイルのパス
            content: ファイル内容

        Returns:
            ワークフロー情報
        """
        # name フィールドを検索
        name_match = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else file_path.stem

        # jobs セクションからジョブ名を抽出
        jobs = []
        jobs_section = re.search(r"^jobs:\s*\n((?:  \w+:.*\n?)*)", content, re.MULTILINE)
        if jobs_section:
            job_matches = re.findall(r"^  (\w+):", jobs_section.group(1), re.MULTILINE)
            jobs = job_matches

        # トリガーを検索して説明を生成
        on_match = re.search(r"^on:\s*\n((?:  .*\n?)*)", content, re.MULTILINE)
        description = "GitHub Actions ワークフロー"
        if on_match:
            on_content = on_match.group(1)
            if "push" in on_content:
                description += " (push時実行)"
            elif "pull_request" in on_content:
                description += " (PR時実行)"

        return WorkflowInfo(file_path=file_path, name=name, description=description, jobs=jobs)

    def _generate_description(self, workflow_data: dict) -> str:
        """ワークフローの説明を生成

        Args:
            workflow_data: ワークフローデータ

        Returns:
            説明文
        """
        description_parts = []

        # トリガー情報
        on_data = workflow_data.get("on", {})
        if isinstance(on_data, str):
            description_parts.append(f"{on_data}時実行")
        elif isinstance(on_data, dict):
            triggers = []
            if "push" in on_data:
                triggers.append("push")
            if "pull_request" in on_data:
                triggers.append("PR")
            if "schedule" in on_data:
                triggers.append("スケジュール")
            if "workflow_dispatch" in on_data:
                triggers.append("手動")

            if triggers:
                description_parts.append(f"{'/'.join(triggers)}時実行")
        elif isinstance(on_data, list):
            description_parts.append(f"{'/'.join(on_data)}時実行")

        # ジョブ数
        jobs = workflow_data.get("jobs", {})
        if isinstance(jobs, dict) and jobs:
            job_count = len(jobs)
            description_parts.append(f"{job_count}個のジョブ")

        return " | ".join(description_parts) if description_parts else "GitHub Actions ワークフロー"

    def get_workflow_choices(self, workflows: list[WorkflowInfo]) -> dict[str, WorkflowInfo]:
        """ワークフロー選択肢を生成

        Args:
            workflows: ワークフロー情報のリスト

        Returns:
            選択キーとワークフロー情報のマッピング
        """
        choices = {}

        for i, workflow in enumerate(workflows, 1):
            key = str(i)
            choices[key] = workflow

        return choices

    def display_workflows(self, workflows: list[WorkflowInfo]) -> None:
        """ワークフロー一覧を表示

        Args:
            workflows: ワークフロー情報のリスト
        """
        if not workflows:
            self.console.print("[yellow]ワークフローファイルが見つかりません[/yellow]")
            self.console.print(
                "[dim].github/workflows/ ディレクトリに .yml または .yaml ファイルを配置してください[/dim]"
            )
            return

        self.console.print(f"[bold]検出されたワークフロー ({len(workflows)}個):[/bold]")

        for i, workflow in enumerate(workflows, 1):
            self.console.print(f"  {i}. [cyan]{workflow.name}[/cyan]")
            self.console.print(f"     [dim]ファイル: {workflow.filename}[/dim]")
            if workflow.description:
                self.console.print(f"     [dim]{workflow.description}[/dim]")
            if workflow.jobs:
                jobs_str = ", ".join(workflow.jobs[:3])
                if len(workflow.jobs) > 3:
                    jobs_str += f" など{len(workflow.jobs)}個"
                self.console.print(f"     [dim]ジョブ: {jobs_str}[/dim]")
            self.console.print()
