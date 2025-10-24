"""
コマンドメニュー定義

各コマンドの説明付きメニュー項目とサブメニューを定義します。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

from .menu_system import Menu, MenuItem


class CommandMenuBuilder:
    """コマンドメニュービルダー

    CI-Helperの各コマンドに対応するメニュー項目とサブメニューを構築します。
    """

    def __init__(self, console: Console, command_handlers: dict[str, Callable]):
        """コマンドメニュービルダーを初期化

        Args:
            console: Rich Console インスタンス
            command_handlers: コマンド名とハンドラー関数のマッピング
        """
        self.console = console
        self.command_handlers = command_handlers

    def build_main_menu(self) -> Menu:
        """メインメニューを構築

        Returns:
            メインメニュー
        """
        return Menu(
            title="CI-Helper メインメニュー",
            items=[
                MenuItem(
                    key="1",
                    title="初期設定",
                    description="プロジェクトの初期設定を行います",
                    submenu=self._build_init_submenu(),
                ),
                MenuItem(
                    key="2",
                    title="環境チェック",
                    description="実行環境の依存関係をチェックします",
                    action=self._create_command_action("doctor"),
                ),
                MenuItem(
                    key="3",
                    title="CI/CDテスト",
                    description="ワークフローをローカルで実行します",
                    submenu=self._build_test_submenu(),
                ),
                MenuItem(
                    key="4",
                    title="AI分析",
                    description="CI失敗の根本原因をAI分析します",
                    submenu=self._build_analyze_submenu(),
                ),
                MenuItem(
                    key="5",
                    title="ログ管理",
                    description="実行ログを管理・表示します",
                    submenu=self._build_logs_submenu(),
                ),
                MenuItem(
                    key="6",
                    title="シークレット管理",
                    description="シークレットの管理と検証を行います",
                    submenu=self._build_secrets_submenu(),
                ),
                MenuItem(
                    key="7",
                    title="キャッシュ管理",
                    description="Dockerイメージの事前プルとキャッシュ管理",
                    submenu=self._build_cache_submenu(),
                ),
                MenuItem(
                    key="8",
                    title="クリーンアップ",
                    description="キャッシュとログをクリーンアップします",
                    action=self._create_command_action("clean"),
                ),
            ],
            show_quit=True,
        )

    def _build_init_submenu(self) -> Menu:
        """初期設定サブメニューを構築"""
        return Menu(
            title="初期設定メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="対話的初期設定（推奨）",
                    description="AIプロバイダーとモデルを選択して設定ファイルを生成",
                    action=self._create_interactive_init_action(),
                ),
                MenuItem(
                    key="2",
                    title="標準初期設定",
                    description="デフォルト設定でci-helper.tomlを生成します",
                    action=self._create_command_action("init"),
                ),
                MenuItem(
                    key="3",
                    title="環境セットアップ",
                    description="必要な依存関係をセットアップします",
                    action=self._create_command_action("setup"),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_test_submenu(self) -> Menu:
        """テストサブメニューを構築"""
        return Menu(
            title="CI/CDテストメニュー",
            items=[
                MenuItem(
                    key="1",
                    title="全ワークフロー実行",
                    description="すべてのワークフローを実行します",
                    action=self._create_test_action(),
                ),
                MenuItem(
                    key="2",
                    title="特定ワークフロー実行",
                    description="指定したワークフローのみを実行します",
                    action=self._create_test_workflow_action(),
                ),
                MenuItem(
                    key="3",
                    title="特定ジョブ実行",
                    description="指定したジョブのみを実行します",
                    action=self._create_test_job_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_analyze_submenu(self) -> Menu:
        """AI分析サブメニューを構築"""
        return Menu(
            title="AI分析メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="最新ログ分析",
                    description="最新の実行ログをAI分析します",
                    action=self._create_analyze_action(),
                ),
                MenuItem(
                    key="2",
                    title="対話的分析",
                    description="対話的なAIデバッグセッションを開始します",
                    action=self._create_analyze_interactive_action(),
                ),
                MenuItem(
                    key="3",
                    title="特定ログ分析",
                    description="指定したログファイルを分析します",
                    action=self._create_analyze_file_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_logs_submenu(self) -> Menu:
        """ログ管理サブメニューを構築"""
        return Menu(
            title="ログ管理メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="ログ一覧表示",
                    description="実行ログの一覧を表示します",
                    action=self._create_command_action("logs"),
                ),
                MenuItem(
                    key="2",
                    title="最新ログ表示",
                    description="最新のログを表示します",
                    action=self._create_logs_latest_action(),
                ),
                MenuItem(
                    key="3",
                    title="ログ比較",
                    description="2つのログを比較します",
                    action=self._create_logs_compare_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_secrets_submenu(self) -> Menu:
        """シークレット管理サブメニューを構築"""
        return Menu(
            title="シークレット管理メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="シークレット検証",
                    description="設定されたシークレットを検証します",
                    action=self._create_command_action("secrets"),
                ),
                MenuItem(
                    key="2",
                    title="シークレット一覧",
                    description="利用可能なシークレットを一覧表示します",
                    action=self._create_secrets_list_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_cache_submenu(self) -> Menu:
        """キャッシュ管理サブメニューを構築"""
        return Menu(
            title="キャッシュ管理メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="高速プル（推奨）",
                    description="最小限のイメージを素早くプルします",
                    action=self._create_cache_quick_pull_action(),
                ),
                MenuItem(
                    key="2",
                    title="カスタムプル",
                    description="イメージとタイムアウトを選択してプルします",
                    action=self._create_cache_pull_action(),
                ),
                MenuItem(
                    key="3",
                    title="キャッシュ状態表示",
                    description="キャッシュの状態を表示します",
                    action=self._create_command_action("cache"),
                ),
                MenuItem(
                    key="4",
                    title="キャッシュクリア",
                    description="キャッシュをクリアします",
                    action=self._create_cache_clear_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _create_command_action(self, command: str) -> Callable[[], Any]:
        """基本コマンドアクションを作成

        Args:
            command: 実行するコマンド名

        Returns:
            コマンド実行関数
        """

        def action():
            if command in self.command_handlers:
                return self.command_handlers[command]()
            else:
                self.console.print(f"[red]コマンド '{command}' が見つかりません[/red]")

        return action

    def _create_test_action(self) -> Callable[[], Any]:
        """テストアクションを作成（全ワークフロー）"""

        def action():
            if "test" in self.command_handlers:
                return self.command_handlers["test"]()
            else:
                self.console.print("[red]testコマンドが見つかりません[/red]")

        return action

    def _create_test_workflow_action(self) -> Callable[[], Any]:
        """特定ワークフローテストアクションを作成"""

        def action():
            from ..utils.workflow_detector import WorkflowDetector

            detector = WorkflowDetector(self.console)
            workflows = detector.find_workflows()

            if not workflows:
                self.console.print("[yellow]ワークフローファイルが見つかりません[/yellow]")
                self.console.print(
                    "[dim].github/workflows/ ディレクトリに .yml または .yaml ファイルを配置してください[/dim]"
                )
                return False

            self.console.print("[bold green]実行するワークフローを選択してください:[/bold green]\n")
            detector.display_workflows(workflows)

            choices = detector.get_workflow_choices(workflows)
            choice_keys = list(choices.keys())

            selected_choice = Prompt.ask(
                "[bold green]選択してください[/bold green]",
                choices=choice_keys,
                console=self.console,
            )

            if selected_choice in choices:
                selected_workflow = choices[selected_choice]
                workflow_filename = selected_workflow.filename

                if "test_workflow" in self.command_handlers:
                    return self.command_handlers["test_workflow"](workflow_filename)
                else:
                    self.console.print(
                        f"[yellow]ワークフロー '{selected_workflow.name}' ({workflow_filename}) でテストを実行します[/yellow]"
                    )
                    # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[red]無効な選択です[/red]")
                return False

        return action

    def _create_test_job_action(self) -> Callable[[], Any]:
        """特定ジョブテストアクションを作成"""

        def action():
            from ..utils.workflow_detector import WorkflowDetector

            detector = WorkflowDetector(self.console)
            workflows = detector.find_workflows()

            if not workflows:
                self.console.print("[yellow]ワークフローファイルが見つかりません[/yellow]")
                return False

            # 全ワークフローからジョブを収集
            all_jobs = {}
            for workflow in workflows:
                for job in workflow.jobs:
                    if job not in all_jobs:
                        all_jobs[job] = []
                    all_jobs[job].append(workflow)

            if not all_jobs:
                self.console.print("[yellow]ジョブが見つかりません[/yellow]")
                return False

            self.console.print("[bold green]実行するジョブを選択してください:[/bold green]\n")

            job_choices = {}
            for i, (job_name, job_workflows) in enumerate(all_jobs.items(), 1):
                key = str(i)
                job_choices[key] = job_name

                workflow_names = [w.name for w in job_workflows]
                workflows_str = ", ".join(workflow_names[:2])
                if len(workflow_names) > 2:
                    workflows_str += f" など{len(workflow_names)}個"

                self.console.print(f"  {i}. [cyan]{job_name}[/cyan]")
                self.console.print(f"     [dim]ワークフロー: {workflows_str}[/dim]")

            self.console.print()

            selected_choice = Prompt.ask(
                "[bold green]選択してください[/bold green]",
                choices=list(job_choices.keys()),
                console=self.console,
            )

            if selected_choice in job_choices:
                selected_job = job_choices[selected_choice]

                if "test_job" in self.command_handlers:
                    return self.command_handlers["test_job"](selected_job)
                else:
                    self.console.print(f"[yellow]ジョブ '{selected_job}' でテストを実行します[/yellow]")
                    # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[red]無効な選択です[/red]")
                return False

        return action

    def _create_analyze_action(self) -> Callable[[], Any]:
        """AI分析アクションを作成（最新ログ）"""

        def action():
            if "analyze" in self.command_handlers:
                return self.command_handlers["analyze"]()
            else:
                self.console.print("[red]analyzeコマンドが見つかりません[/red]")

        return action

    def _create_analyze_interactive_action(self) -> Callable[[], Any]:
        """対話的AI分析アクションを作成"""

        def action():
            if "analyze_interactive" in self.command_handlers:
                return self.command_handlers["analyze_interactive"]()
            else:
                self.console.print("[yellow]対話的分析モードを開始します[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_analyze_file_action(self) -> Callable[[], Any]:
        """特定ファイル分析アクションを作成"""

        def action():
            log_file = Prompt.ask(
                "[bold green]分析するログファイルのパスを入力してください[/bold green]", console=self.console
            )

            if log_file and "analyze_file" in self.command_handlers:
                return self.command_handlers["analyze_file"](log_file)
            elif log_file:
                self.console.print(f"[yellow]ログファイル '{log_file}' を分析します[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[red]ログファイルパスが入力されませんでした[/red]")

        return action

    def _create_logs_latest_action(self) -> Callable[[], Any]:
        """最新ログ表示アクションを作成"""

        def action():
            if "logs_latest" in self.command_handlers:
                return self.command_handlers["logs_latest"]()
            else:
                self.console.print("[yellow]最新のログを表示します[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_logs_compare_action(self) -> Callable[[], Any]:
        """ログ比較アクションを作成"""

        def action():
            log1 = Prompt.ask(
                "[bold green]比較する1つ目のログファイルを入力してください[/bold green]", console=self.console
            )
            log2 = Prompt.ask(
                "[bold green]比較する2つ目のログファイルを入力してください[/bold green]", console=self.console
            )

            if log1 and log2 and "logs_compare" in self.command_handlers:
                return self.command_handlers["logs_compare"](log1, log2)
            elif log1 and log2:
                self.console.print(f"[yellow]'{log1}' と '{log2}' を比較します[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[red]両方のログファイルパスを入力してください[/red]")

        return action

    def _create_secrets_list_action(self) -> Callable[[], Any]:
        """シークレット一覧アクションを作成"""

        def action():
            if "secrets_list" in self.command_handlers:
                return self.command_handlers["secrets_list"]()
            else:
                self.console.print("[yellow]利用可能なシークレットを一覧表示します[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_cache_pull_action(self) -> Callable[[], Any]:
        """キャッシュプルアクションを作成"""

        def action():
            # タイムアウト設定を確認
            timeout_choice = Prompt.ask(
                "[bold green]タイムアウト時間を選択してください[/bold green]",
                choices=["30", "60", "120", "custom"],
                default="60",
                console=self.console,
            )

            if timeout_choice == "custom":
                timeout_str = Prompt.ask(
                    "[bold green]タイムアウト時間（分）を入力してください[/bold green]",
                    default="60",
                    console=self.console,
                )
                try:
                    timeout = int(timeout_str) * 60
                except ValueError:
                    self.console.print("[red]無効な数値です。デフォルト（60分）を使用します[/red]")
                    timeout = 3600
            else:
                timeout = int(timeout_choice) * 60

            # イメージ選択
            image_choice = Prompt.ask(
                "[bold green]プルするイメージを選択してください[/bold green]",
                choices=["default", "minimal", "full", "custom"],
                default="default",
                console=self.console,
            )

            images = []
            if image_choice == "default":
                images = [
                    "ghcr.io/catthehacker/ubuntu:act-latest",
                    "ghcr.io/catthehacker/ubuntu:act-22.04",
                ]
            elif image_choice == "minimal":
                images = ["ghcr.io/catthehacker/ubuntu:act-latest"]
            elif image_choice == "full":
                images = [
                    "ghcr.io/catthehacker/ubuntu:act-latest",
                    "ghcr.io/catthehacker/ubuntu:act-22.04",
                    "ghcr.io/catthehacker/ubuntu:act-20.04",
                    "ghcr.io/catthehacker/ubuntu:full-latest",
                    "ghcr.io/catthehacker/ubuntu:full-22.04",
                ]
            elif image_choice == "custom":
                custom_image = Prompt.ask(
                    "[bold green]カスタムイメージ名を入力してください[/bold green]",
                    console=self.console,
                )
                if custom_image:
                    images = [custom_image]

            if images and "cache_pull" in self.command_handlers:
                return self.command_handlers["cache_pull"](images, timeout)
            elif images:
                self.console.print(f"[yellow]Dockerイメージをプルします（タイムアウト: {timeout // 60}分）[/yellow]")
                for image in images:
                    self.console.print(f"  - {image}")
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[red]プルするイメージが選択されませんでした[/red]")

        return action

    def _create_cache_quick_pull_action(self) -> Callable[[], Any]:
        """高速キャッシュプルアクションを作成"""

        def action():
            # 最小限のイメージで高速プル
            images = ["ghcr.io/catthehacker/ubuntu:act-latest"]
            timeout = 3600  # 60分

            self.console.print("[green]高速プルを開始します...[/green]")
            self.console.print(f"[dim]対象イメージ: {images[0]}[/dim]")
            self.console.print(f"[dim]タイムアウト: {timeout // 60}分[/dim]")

            if "cache_pull" in self.command_handlers:
                return self.command_handlers["cache_pull"](images, timeout)
            else:
                self.console.print("[yellow]Dockerイメージをプルします[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_interactive_init_action(self) -> Callable[[], Any]:
        """対話的初期設定アクションを作成"""

        def action():
            if "init_interactive" in self.command_handlers:
                return self.command_handlers["init_interactive"]()
            else:
                self.console.print("[green]対話的初期設定を開始します...[/green]")
                self.console.print("[dim]AIプロバイダーとモデルを選択できます[/dim]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_cache_clear_action(self) -> Callable[[], Any]:
        """キャッシュクリアアクションを作成"""

        def action():
            if Confirm.ask("[bold red]キャッシュをクリアしますか？[/bold red]", console=self.console):
                if "cache_clear" in self.command_handlers:
                    return self.command_handlers["cache_clear"]()
                else:
                    self.console.print("[yellow]キャッシュをクリアします[/yellow]")
                    # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[dim]キャッシュクリアがキャンセルされました[/dim]")

        return action
