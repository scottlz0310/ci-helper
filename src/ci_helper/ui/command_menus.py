"""コマンドメニュー定義

各コマンドの説明付きメニュー項目とサブメニューを定義します。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

from .menu_system import Menu, MenuItem

CommandHandler = Callable[..., Any]


class CommandMenuBuilder:
    """コマンドメニュービルダー

    CI-Helperの各コマンドに対応するメニュー項目とサブメニューを構築します。
    """

    def __init__(self, console: Console, command_handlers: dict[str, CommandHandler]):
        """コマンドメニュービルダーを初期化

        Args:
            console: Rich Console インスタンス
            command_handlers: コマンド名とハンドラー関数のマッピング

        """
        self.console = console
        self.command_handlers: dict[str, CommandHandler] = command_handlers

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
                MenuItem(
                    key="4",
                    title="ログ整形",
                    description="ログを様々な形式で整形します",
                    submenu=self._build_log_formatting_submenu(),
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
            self.console.print(f"[red]コマンド '{command}' が見つかりません[/red]")

        return action

    def _create_test_action(self) -> Callable[[], Any]:
        """テストアクションを作成（全ワークフロー）"""

        def action():
            if "test" in self.command_handlers:
                return self.command_handlers["test"]()
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
                msg = "[dim].github/workflows/ ディレクトリに .yml または .yaml ファイルを配置してください[/dim]"
                message = msg
                self.console.print(message)
                return False

            msg = "[bold green]実行するワークフローを選択してください:[/bold green]\n"
            message = msg
            self.console.print(message)
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
                message = (
                    f"[yellow]ワークフロー '{selected_workflow.name}' "
                    f"({workflow_filename}) でテストを実行します[/yellow]"
                )
                self.console.print(message)
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
            all_jobs: dict[str, list[Any]] = {}
            for workflow in workflows:
                for job in workflow.jobs:
                    if job not in all_jobs:
                        all_jobs[job] = []
                    all_jobs[job].append(workflow)

            if not all_jobs:
                self.console.print("[yellow]ジョブが見つかりません[/yellow]")
                return False

            self.console.print("[bold green]実行するジョブを選択してください:[/bold green]\n")

            job_choices: dict[str, str] = {}
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
                msg = f"[yellow]ジョブ '{selected_job}' でテストを実行します[/yellow]"
                message = msg
                self.console.print(message)
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
            self.console.print("[red]analyzeコマンドが見つかりません[/red]")

        return action

    def _create_analyze_interactive_action(self) -> Callable[[], Any]:
        """対話的AI分析アクションを作成"""

        def action():
            if "analyze_interactive" in self.command_handlers:
                return self.command_handlers["analyze_interactive"]()
            self.console.print("[yellow]対話的分析モードを開始します[/yellow]")
            # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_analyze_file_action(self) -> Callable[[], Any]:
        """特定ファイル分析アクションを作成"""

        def action():
            log_file = Prompt.ask(
                "[bold green]分析するログファイルのパスを入力してください[/bold green]",
                console=self.console,
            )

            if log_file and "analyze_file" in self.command_handlers:
                return self.command_handlers["analyze_file"](log_file)
            if log_file:
                message = f"[yellow]ログファイル '{log_file}' を分析します[/yellow]"
                self.console.print(message)
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                message = "[red]ログファイルパスが入力されませんでした[/red]"
                self.console.print(message)

        return action

    def _create_logs_latest_action(self) -> Callable[[], Any]:
        """最新ログ表示アクションを作成"""

        def action():
            if "logs_latest" in self.command_handlers:
                return self.command_handlers["logs_latest"]()
            self.console.print("[yellow]最新のログを表示します[/yellow]")
            # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_logs_compare_action(self) -> Callable[[], Any]:
        """ログ比較アクションを作成"""

        def action():
            log1 = Prompt.ask(
                "[bold green]比較する1つ目のログファイルを入力してください[/bold green]",
                console=self.console,
            )
            log2 = Prompt.ask(
                "[bold green]比較する2つ目のログファイルを入力してください[/bold green]",
                console=self.console,
            )

            if log1 and log2 and "logs_compare" in self.command_handlers:
                return self.command_handlers["logs_compare"](log1, log2)
            if log1 and log2:
                message = f"[yellow]'{log1}' と '{log2}' を比較します[/yellow]"
                self.console.print(message)
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                message = "[red]両方のログファイルパスを入力してください[/red]"
                self.console.print(message)

        return action

    def _create_secrets_list_action(self) -> Callable[[], Any]:
        """シークレット一覧アクションを作成"""

        def action():
            if "secrets_list" in self.command_handlers:
                return self.command_handlers["secrets_list"]()
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

            images: list[str] = []
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
            if images:
                timeout_min = timeout // 60
                text = f"[yellow]Dockerイメージをプルします（タイムアウト: {timeout_min}分）[/yellow]"
                msg = text
                message = msg
                self.console.print(message)
                for image in images:
                    self.console.print(f"  - {image}")
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                message = "[red]プルするイメージが選択されませんでした[/red]"
                self.console.print(message)

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
            self.console.print("[yellow]Dockerイメージをプルします[/yellow]")
            # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _create_interactive_init_action(self) -> Callable[[], Any]:
        """対話的初期設定アクションを作成"""

        def action():
            if "init_interactive" in self.command_handlers:
                return self.command_handlers["init_interactive"]()
            self.console.print("[green]対話的初期設定を開始します...[/green]")
            self.console.print("[dim]AIプロバイダーとモデルを選択できます[/dim]")
            # 実際の実装では適切なコマンドハンドラーを呼び出す

        return action

    def _build_log_formatting_submenu(self) -> Menu:
        """ログ整形サブメニューを構築"""
        return Menu(
            title="ログ整形メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="最新ログ整形",
                    description="最新の実行ログを様々な形式で整形",
                    submenu=self._build_latest_log_formatting_submenu(),
                ),
                MenuItem(
                    key="2",
                    title="特定ログ整形",
                    description="指定したログファイルを様々な形式で整形",
                    submenu=self._build_specific_log_formatting_submenu(),
                ),
                MenuItem(
                    key="3",
                    title="カスタム整形",
                    description="整形パラメータをカスタマイズ",
                    action=self._create_custom_format_action(),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_latest_log_formatting_submenu(self) -> Menu:
        """最新ログ整形サブメニューを構築"""
        return Menu(
            title="最新ログ整形メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="AI分析用フォーマット",
                    description="AI分析に最適化されたMarkdown形式で出力",
                    action=self._create_latest_log_format_action("ai"),
                ),
                MenuItem(
                    key="2",
                    title="人間可読フォーマット",
                    description="色付けされた構造化出力を生成",
                    action=self._create_latest_log_format_action("human"),
                ),
                MenuItem(
                    key="3",
                    title="JSON形式",
                    description="構造化されたJSONデータを出力",
                    action=self._create_latest_log_format_action("json"),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _build_specific_log_formatting_submenu(self) -> Menu:
        """特定ログ整形サブメニューを構築"""
        return Menu(
            title="特定ログ整形メニュー",
            items=[
                MenuItem(
                    key="1",
                    title="AI分析用フォーマット",
                    description="AI分析に最適化されたMarkdown形式で出力",
                    action=self._create_format_action("ai"),
                ),
                MenuItem(
                    key="2",
                    title="人間可読フォーマット",
                    description="色付けされた構造化出力を生成",
                    action=self._create_format_action("human"),
                ),
                MenuItem(
                    key="3",
                    title="JSON形式",
                    description="構造化されたJSONデータを出力",
                    action=self._create_format_action("json"),
                ),
            ],
            show_back=True,
            show_quit=True,
        )

    def _create_format_action(self, format_type: str) -> Callable[[], Any]:
        """ログ整形アクションを作成

        Args:
            format_type: フォーマット種別（ai, human, json）

        Returns:
            ログ整形実行関数

        """

        def action():
            # ログファイル選択機能を使用
            log_file = self._select_log_file()
            if log_file is None:
                # ユーザーがキャンセルした場合
                return False

            # 出力先選択
            output_choice = Prompt.ask(
                "[bold green]出力先を選択してください[/bold green]",
                choices=["console", "file"],
                default="console",
                console=self.console,
            )

            output_file = None
            if output_choice == "file":
                # セキュリティ機能を有効にしてファイル保存ユーティリティを使用
                from ..utils.file_save_utils import FileSaveManager

                file_manager = FileSaveManager(self.console, enable_security=True)
                output_file = file_manager.prompt_for_output_file(
                    format_type=format_type,
                    input_file=log_file,
                    default_dir=file_manager.get_default_output_directory(),
                )

                if not output_file:
                    self.console.print("[yellow]ファイル保存がキャンセルされました[/yellow]")
                    return False

                # 出力パスを検証
                is_valid, error_msg = file_manager.validate_output_path(output_file)
                if not is_valid:
                    self.console.print(f"[red]エラー: {error_msg}[/red]")
                    return False

            # フォーマット実行（メニューに戻る関数を提供）
            def return_to_menu():
                # メニューシステムに戻る処理は呼び出し元で処理される
                pass

            if "format_logs" in self.command_handlers:
                return self.command_handlers["format_logs"](
                    format_type=format_type,
                    input_file=log_file,
                    output_file=output_file,
                    return_to_menu_func=return_to_menu,
                )
            # 実装予定の処理を表示
            from ..utils.progress_display import get_progress_manager

            progress_manager = get_progress_manager(self.console)

            # 処理開始メッセージ
            progress_manager.show_processing_start_message(
                format_type=format_type,
                input_file=log_file,
                output_file=output_file,
            )

            # 模擬処理
            def mock_format_task():
                import time

                time.sleep(1)  # 処理時間をシミュレート
                return f"模擬整形結果: {format_type}形式"

            try:
                progress_manager.execute_with_progress(
                    task_func=mock_format_task,
                    task_description="ログを整形中...",
                    completion_description="整形完了",
                    input_file=log_file,
                )

                # 成功メッセージ
                progress_manager.show_success_message(
                    format_type=format_type,
                    output_file=output_file,
                    processing_time=1.0,
                )

                # メニューに戻るオプション
                progress_manager.show_menu_return_option(return_to_menu)

            except Exception as e:
                # ログ整形専用エラーハンドラーを使用
                from ..formatters.error_handler import LogFormattingErrorHandler

                error_handler = LogFormattingErrorHandler(self.console)

                error_context = error_handler.create_error_context(
                    format_type=format_type,
                    input_file=log_file,
                )

                error_handler.handle_formatting_error(e, error_context, verbose=False)

                # メニューに戻るオプション（エラー時も）
                progress_manager.show_menu_return_option(return_to_menu)

        return action

    def _create_custom_format_action(self) -> Callable[[], Any]:
        """カスタム整形アクションを作成

        Returns:
            カスタム整形実行関数

        """

        def action():
            self.console.print("[bold green]カスタム整形設定[/bold green]\n")

            # カスタム整形パラメータ設定画面を表示
            custom_options = self._show_custom_format_parameter_screen()

            if custom_options is None:
                # ユーザーがキャンセルした場合
                self.console.print("[yellow]カスタム整形がキャンセルされました[/yellow]")
                return False

            # ログファイル選択機能を使用
            log_file = self._select_log_file()
            # log_file が None の場合は最新ログを使用
            # 明示的にキャンセルされた場合は処理を中断

            # 出力先選択
            output_choice = Prompt.ask(
                "[bold green]出力先を選択してください[/bold green]",
                choices=["console", "file"],
                default="console",
                console=self.console,
            )

            output_file = None
            if output_choice == "file":
                # セキュリティ機能を有効にしてファイル保存ユーティリティを使用
                from ..utils.file_save_utils import FileSaveManager

                file_manager = FileSaveManager(self.console, enable_security=True)
                output_file = file_manager.prompt_for_output_file(
                    format_type=custom_options["format_type"],
                    input_file=log_file,
                    default_dir=file_manager.get_default_output_directory(),
                )

                if not output_file:
                    self.console.print("[yellow]ファイル保存がキャンセルされました[/yellow]")
                    return False

                # 出力パスを検証
                is_valid, error_msg = file_manager.validate_output_path(output_file)
                if not is_valid:
                    self.console.print(f"[red]エラー: {error_msg}[/red]")
                    return False

            # 設定確認画面を表示
            self._show_custom_format_confirmation(custom_options, log_file, output_file)

            # 最終確認
            if not Confirm.ask(
                "[bold yellow]この設定でログ整形を実行しますか？[/bold yellow]",
                console=self.console,
            ):
                self.console.print("[yellow]カスタム整形がキャンセルされました[/yellow]")
                return False

            # カスタム整形実行（メニューに戻る関数を提供）
            def return_to_menu():
                # メニューシステムに戻る処理は呼び出し元で処理される
                pass

            if "format_logs_custom" in self.command_handlers:
                return self.command_handlers["format_logs_custom"](
                    format_type=custom_options["format_type"],
                    detail_level=custom_options["detail_level"],
                    filter_errors=custom_options["filter_errors"],
                    input_file=log_file,
                    output_file=output_file,
                    return_to_menu_func=return_to_menu,
                    **custom_options["advanced_options"],
                )
            # 実装予定の処理を表示
            self._show_custom_format_execution_preview(custom_options, log_file, output_file, return_to_menu)

        return action

    def _create_cache_clear_action(self) -> Callable[[], Any]:
        """キャッシュクリアアクションを作成"""

        def action():
            prompt_text = "[bold red]キャッシュをクリアしますか？[/bold red]"
            if Confirm.ask(prompt_text, console=self.console):
                if "cache_clear" in self.command_handlers:
                    return self.command_handlers["cache_clear"]()
                self.console.print("[yellow]キャッシュをクリアします[/yellow]")
                # 実際の実装では適切なコマンドハンドラーを呼び出す
            else:
                self.console.print("[dim]キャッシュクリアがキャンセルされました[/dim]")

        return action

    def _create_latest_log_format_action(self, format_type: str) -> Callable[[], Any]:
        """最新ログ整形アクションを作成

        Args:
            format_type: フォーマット種別（ai, human, json）

        Returns:
            最新ログ整形実行関数

        """

        def action():
            # 出力先選択
            output_choice = Prompt.ask(
                "[bold green]出力先を選択してください[/bold green]",
                choices=["console", "file"],
                default="console",
                console=self.console,
            )

            output_file = None
            if output_choice == "file":
                # セキュリティ機能を有効にしてファイル保存ユーティリティを使用
                from ..utils.file_save_utils import FileSaveManager

                file_manager = FileSaveManager(self.console, enable_security=True)
                output_file = file_manager.prompt_for_output_file(
                    format_type=format_type,
                    input_file=None,  # 最新ログなので入力ファイルなし
                    default_dir=file_manager.get_default_output_directory(),
                )

                if not output_file:
                    self.console.print("[yellow]ファイル保存がキャンセルされました[/yellow]")
                    return False

                # 出力パスを検証
                is_valid, error_msg = file_manager.validate_output_path(output_file)
                if not is_valid:
                    self.console.print(f"[red]エラー: {error_msg}[/red]")
                    return False

            # 最新ログでフォーマット実行（log_file=Noneで最新ログを指定）
            def return_to_menu():
                # メニューシステムに戻る処理は呼び出し元で処理される
                pass

            if "format_logs" in self.command_handlers:
                return self.command_handlers["format_logs"](
                    format_type=format_type,
                    input_file=None,  # 最新ログを使用
                    output_file=output_file,
                    return_to_menu_func=return_to_menu,
                )
            # 実装予定の処理を表示
            from ..utils.progress_display import get_progress_manager

            progress_manager = get_progress_manager(self.console)

            # 処理開始メッセージ
            progress_manager.show_processing_start_message(
                format_type=format_type,
                input_file=None,  # 最新ログ
                output_file=output_file,
            )

            # 模擬処理
            def mock_format_task():
                import time

                time.sleep(0.8)  # 処理時間をシミュレート
                return f"模擬整形結果: 最新ログの{format_type}形式"

            try:
                progress_manager.execute_with_progress(
                    task_func=mock_format_task,
                    task_description="最新ログを整形中...",
                    completion_description="整形完了",
                    input_file=None,
                )

                # 成功メッセージ
                progress_manager.show_success_message(
                    format_type=format_type,
                    output_file=output_file,
                    processing_time=0.8,
                )

                # メニューに戻るオプション
                progress_manager.show_menu_return_option(return_to_menu)

            except Exception as e:
                # ログ整形専用エラーハンドラーを使用
                from ..formatters.error_handler import LogFormattingErrorHandler

                error_handler = LogFormattingErrorHandler(self.console)

                error_context = error_handler.create_error_context(
                    format_type=format_type,
                    input_file=None,  # 最新ログ
                )

                error_handler.handle_formatting_error(e, error_context, verbose=False)

                # メニューに戻るオプション（エラー時も）
                progress_manager.show_menu_return_option(return_to_menu)

        return action

    def _select_log_file(self) -> str | None:
        """ログファイル選択機能

        Returns:
            選択されたログファイルのパス（最新ログの場合はNone、キャンセル時は"CANCELLED"）

        """
        # ログ選択方式を選択
        log_choice = Prompt.ask(
            "[bold green]整形するログを選択してください[/bold green]",
            choices=["latest", "specific", "list"],
            default="latest",
            console=self.console,
        )

        if log_choice == "latest":
            # 最新ログを使用
            return None
        if log_choice == "specific":
            # カスタムファイルパス入力
            return self._input_custom_log_path()
        if log_choice == "list":
            # 利用可能なログファイル一覧から選択
            return self._select_from_log_list()

        return None

    def _input_custom_log_path(self) -> str | None:
        """カスタムファイルパス入力機能

        Returns:
            入力されたファイルパス（キャンセル時はNone）

        """
        log_file = Prompt.ask(
            "[bold green]ログファイルのパスを入力してください[/bold green]",
            console=self.console,
        )

        if not log_file:
            self.console.print("[yellow]ファイルパスが入力されませんでした[/yellow]")
            return None

        # ファイル存在チェック
        from pathlib import Path

        log_path = Path(log_file)
        if not log_path.exists():
            self.console.print(f"[red]エラー: ファイルが存在しません: {log_file}[/red]")

            # 利用可能なログファイルを提案
            self._show_available_logs_hint()

            # 再入力を促す
            retry = Confirm.ask(
                "[bold yellow]別のファイルパスを入力しますか？[/bold yellow]",
                console=self.console,
            )
            if retry:
                return self._input_custom_log_path()
            return None

        if not log_path.is_file():
            self.console.print(f"[red]エラー: 指定されたパスはファイルではありません: {log_file}[/red]")
            return None

        return str(log_path)

    def _select_from_log_list(self) -> str | None:
        """利用可能なログファイル一覧から選択

        Returns:
            選択されたログファイルのパス（キャンセル時はNone）

        """
        try:
            # LogManagerを使用してログ一覧を取得
            from ..core.log_manager import LogManager
            from ..utils.config import Config

            # 設定を取得（デフォルト設定を使用）
            config = Config()
            log_manager = LogManager(config)

            # ログ一覧を取得
            logs = log_manager.list_logs(limit=20)  # 最新20件まで表示

            if not logs:
                self.console.print("[yellow]利用可能なログファイルが見つかりません[/yellow]")
                self.console.print("[dim]ci-run test を実行してログを生成してください[/dim]")
                return None

            # ログ一覧を表示
            self.console.print("[bold green]利用可能なログファイル:[/bold green]\n")

            log_choices: dict[str, str] = {}
            for i, log_entry in enumerate(logs, 1):
                key = str(i)
                log_choices[key] = log_entry["log_file"]

                # タイムスタンプをフォーマット
                from datetime import datetime

                timestamp = datetime.fromisoformat(log_entry["timestamp"])
                formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

                # ステータス表示
                status = "✅" if log_entry["success"] else "❌"

                self.console.print(f"  {i}. [cyan]{log_entry['log_file']}[/cyan]")
                self.console.print(f"     [dim]{formatted_time} | {status} | {log_entry['total_duration']:.2f}秒[/dim]")

            self.console.print()

            # ユーザーに選択を促す
            selected_choice = Prompt.ask(
                "[bold green]ログファイルを選択してください（番号を入力）[/bold green]",
                choices=list(log_choices.keys()),
                console=self.console,
            )

            if selected_choice in log_choices:
                selected_log = log_choices[selected_choice]

                # フルパスを構築
                log_path = log_manager.log_dir / selected_log

                # ファイル存在チェック
                if not log_path.exists():
                    self.console.print(f"[red]エラー: 選択されたログファイルが存在しません: {selected_log}[/red]")
                    return None

                return str(log_path)
            self.console.print("[red]無効な選択です[/red]")
            return None

        except Exception as e:
            from ..core.exceptions import FileOperationError

            raise FileOperationError(
                f"ログファイル一覧の取得中にエラーが発生しました: {e}",
                "ログディレクトリの権限を確認するか、'ci-run logs' コマンドを試してください",
                operation="読み込み",
            ) from e

    def _show_available_logs_hint(self) -> None:
        """利用可能なログファイルのヒントを表示"""
        try:
            from ..core.log_manager import LogManager
            from ..utils.config import Config

            config = Config()
            log_manager = LogManager(config)
            logs = log_manager.list_logs(limit=5)  # 最新5件のみ表示

            if logs:
                self.console.print("\n[dim]利用可能なログファイル（最新5件）:[/dim]")
                for log_entry in logs:
                    log_path = log_manager.log_dir / log_entry["log_file"]
                    self.console.print(f"[dim]  - {log_path}[/dim]")
                self.console.print()
            else:
                self.console.print("\n[dim]利用可能なログファイルがありません[/dim]")
                self.console.print("[dim]ci-run test を実行してログを生成してください[/dim]\n")

        except Exception:
            # エラーが発生した場合は何も表示しない
            pass

    def _show_custom_format_parameter_screen(self) -> dict[str, Any] | None:
        """カスタム整形パラメータ設定画面を表示

        Returns:
            設定されたパラメータの辞書（キャンセル時はNone）

        """
        self.console.print("[bold cyan]📋 整形パラメータ設定[/bold cyan]\n")

        # 1. 出力形式選択
        self.console.print("[bold blue]1. 出力形式選択[/bold blue]")
        format_type = Prompt.ask(
            "[green]出力形式を選択してください[/green]",
            choices=["ai", "human", "json", "markdown"],
            default="ai",
            console=self.console,
        )

        # フォーマット別の説明を表示
        format_descriptions = {
            "ai": "AI分析に最適化されたMarkdown形式（コンテキスト強化、優先度付け）",
            "human": "色付けされた構造化出力（Rich ライブラリ使用）",
            "json": "構造化されたJSONデータ（プログラム処理用）",
            "markdown": "標準的なMarkdown形式（既存AIFormatter互換）",
        }
        self.console.print(f"[dim]選択: {format_descriptions[format_type]}[/dim]\n")

        # 2. 詳細レベル設定
        self.console.print("[bold blue]2. 詳細レベル設定[/bold blue]")
        detail_level = Prompt.ask(
            "[green]詳細レベルを選択してください[/green]",
            choices=["minimal", "normal", "detailed"],
            default="normal",
            console=self.console,
        )

        detail_descriptions = {
            "minimal": "最小限の情報のみ（エラーサマリーと重要な失敗のみ）",
            "normal": "標準的な詳細レベル（バランスの取れた情報量）",
            "detailed": "詳細な情報を含む（全コンテキスト、統計、推奨アクション）",
        }
        self.console.print(f"[dim]選択: {detail_descriptions[detail_level]}[/dim]\n")

        # 3. フィルタリングオプション
        self.console.print("[bold blue]3. フィルタリングオプション[/bold blue]")

        # エラーフィルタリング
        filter_errors = (
            Prompt.ask(
                "[green]エラーのみをフィルタリングしますか？[/green]",
                choices=["yes", "no"],
                default="no",
                console=self.console,
            )
            == "yes"
        )

        # 失敗数制限
        max_failures = None
        if not filter_errors:
            limit_failures = (
                Prompt.ask(
                    "[green]表示する失敗数を制限しますか？[/green]",
                    choices=["yes", "no"],
                    default="no",
                    console=self.console,
                )
                == "yes"
            )

            if limit_failures:
                max_failures = int(
                    Prompt.ask(
                        "[green]最大失敗表示数を入力してください[/green]",
                        default="10",
                        console=self.console,
                    ),
                )

        # 4. 高度なオプション（フォーマット固有）
        self.console.print("[bold blue]4. 高度なオプション[/bold blue]")
        advanced_options = self._configure_advanced_options(format_type, detail_level)

        # 設定をまとめる
        custom_options = {
            "format_type": format_type,
            "detail_level": detail_level,
            "filter_errors": filter_errors,
            "max_failures": max_failures,
            "advanced_options": advanced_options,
        }

        return custom_options

    def _configure_advanced_options(self, format_type: str, detail_level: str) -> dict[str, Any]:
        """フォーマット固有の高度なオプションを設定

        Args:
            format_type: 選択された出力形式
            detail_level: 選択された詳細レベル

        Returns:
            高度なオプションの辞書

        """
        advanced_options: dict[str, Any] = {}

        # フォーマット固有のオプション設定
        if format_type == "ai":
            # AI形式の高度なオプション
            include_context = (
                Prompt.ask(
                    "[green]コンテキスト情報を含めますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            include_suggestions = (
                Prompt.ask(
                    "[green]修正提案を含めますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            include_related_files = (
                Prompt.ask(
                    "[green]関連ファイル情報を含めますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            advanced_options.update(
                {
                    "include_context": include_context,
                    "include_suggestions": include_suggestions,
                    "include_related_files": include_related_files,
                },
            )

        elif format_type == "human":
            # 人間可読形式の高度なオプション
            show_success_jobs = (
                Prompt.ask(
                    "[green]成功したジョブも表示しますか？[/green]",
                    choices=["yes", "no"],
                    default="no",
                    console=self.console,
                )
                == "yes"
            )

            color_output = (
                Prompt.ask(
                    "[green]カラー出力を有効にしますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            show_details = detail_level != "minimal"

            advanced_options.update(
                {
                    "show_success_jobs": show_success_jobs,
                    "color_output": color_output,
                    "show_details": show_details,
                },
            )

        elif format_type == "json":
            # JSON形式の高度なオプション
            pretty_print = (
                Prompt.ask(
                    "[green]整形されたJSON出力にしますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            include_metadata = (
                Prompt.ask(
                    "[green]メタデータを含めますか？[/green]",
                    choices=["yes", "no"],
                    default="yes",
                    console=self.console,
                )
                == "yes"
            )

            advanced_options.update(
                {
                    "pretty_print": pretty_print,
                    "include_metadata": include_metadata,
                },
            )

        return advanced_options

    def _show_custom_format_confirmation(
        self,
        custom_options: dict[str, Any],
        log_file: str | None,
        output_file: str | None,
    ) -> None:
        """カスタム整形設定の確認画面を表示

        Args:
            custom_options: 設定されたカスタムオプション
            log_file: 入力ログファイル
            output_file: 出力ファイル

        """
        self.console.print("\n[bold cyan]📋 設定確認[/bold cyan]\n")

        # 基本設定
        self.console.print("[bold blue]基本設定:[/bold blue]")
        self.console.print(f"  出力形式: [cyan]{custom_options['format_type']}[/cyan]")
        self.console.print(f"  詳細レベル: [cyan]{custom_options['detail_level']}[/cyan]")

        # フィルタリング設定
        self.console.print("\n[bold blue]フィルタリング設定:[/bold blue]")
        filter_status = "有効" if custom_options["filter_errors"] else "無効"
        self.console.print(f"  エラーフィルタ: [cyan]{filter_status}[/cyan]")

        if custom_options.get("max_failures"):
            self.console.print(f"  最大失敗表示数: [cyan]{custom_options['max_failures']}[/cyan]")

        # 高度なオプション
        if custom_options["advanced_options"]:
            self.console.print("\n[bold blue]高度なオプション:[/bold blue]")
            for key, value in custom_options["advanced_options"].items():
                display_value = "有効" if value is True else "無効" if value is False else str(value)
                self.console.print(f"  {key}: [cyan]{display_value}[/cyan]")

        # 入出力設定
        self.console.print("\n[bold blue]入出力設定:[/bold blue]")
        if log_file:
            self.console.print(f"  入力ファイル: [cyan]{log_file}[/cyan]")
        else:
            self.console.print("  入力: [cyan]最新ログ[/cyan]")

        if output_file:
            self.console.print(f"  出力ファイル: [cyan]{output_file}[/cyan]")
        else:
            self.console.print("  出力: [cyan]コンソール[/cyan]")

        self.console.print()

    def _show_custom_format_execution_preview(
        self,
        custom_options: dict[str, Any],
        log_file: str | None,
        output_file: str | None,
        return_to_menu_func: Any | None = None,
    ) -> None:
        """カスタム整形実行のプレビューを表示（実装予定の処理）

        Args:
            custom_options: 設定されたカスタムオプション
            log_file: 入力ログファイル
            output_file: 出力ファイル
            return_to_menu_func: メニューに戻る関数

        """
        from ..utils.progress_display import get_progress_manager

        progress_manager = get_progress_manager(self.console)

        # 処理開始メッセージ
        progress_manager.show_processing_start_message(
            format_type=custom_options["format_type"],
            input_file=log_file,
            output_file=output_file,
            detail_level=custom_options["detail_level"],
            filter_errors=custom_options["filter_errors"],
            **custom_options["advanced_options"],
        )

        # 模擬処理
        def mock_custom_format_task():
            import time

            # カスタム設定に応じて処理時間を調整
            processing_time = 1.5 if custom_options["detail_level"] == "detailed" else 1.0
            time.sleep(processing_time)
            return f"模擬カスタム整形結果: {custom_options['format_type']}形式"

        try:
            progress_manager.execute_with_progress(
                task_func=mock_custom_format_task,
                task_description="カスタム設定でログを整形中...",
                completion_description="カスタム整形完了",
                input_file=log_file,
            )

            # 成功メッセージ（カスタム詳細情報付き）
            details: dict[str, Any] = {}
            if custom_options.get("max_failures"):
                details["max_failures"] = custom_options["max_failures"]

            progress_manager.show_success_message(
                format_type=custom_options["format_type"],
                output_file=output_file,
                processing_time=1.5 if custom_options["detail_level"] == "detailed" else 1.0,
                **details,
            )

            # メニューに戻るオプション
            progress_manager.show_menu_return_option(return_to_menu_func)

        except Exception as e:
            # ログ整形専用エラーハンドラーを使用
            from ..formatters.error_handler import LogFormattingErrorHandler

            error_handler = LogFormattingErrorHandler(self.console)

            error_context = error_handler.create_error_context(
                format_type=custom_options.get("format_type", "unknown"),
                input_file=log_file,
                output_file=output_file,
            )

            error_handler.handle_formatting_error(e, error_context, verbose=False)

            # メニューに戻るオプション（エラー時も）
            progress_manager.show_menu_return_option(return_to_menu_func)
