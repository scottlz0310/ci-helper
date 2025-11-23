"""対話的メニューシステム

Rich ライブラリを使用した美しいメニュー表示とキーボードナビゲーション機能を提供します。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


@dataclass
class MenuItem:
    """メニュー項目の定義"""

    key: str  # 選択キー
    title: str  # 表示タイトル
    description: str  # 説明文
    action: Callable[[], Any] | None = None  # 実行する関数
    submenu: Menu | None = None  # サブメニュー
    enabled: bool = True  # 有効/無効フラグ


@dataclass
class Menu:
    """メニューの定義"""

    title: str  # メニュータイトル
    items: list[MenuItem]  # メニュー項目
    show_back: bool = False  # 戻るオプションを表示するか
    show_quit: bool = True  # 終了オプションを表示するか


class MenuSystem:
    """対話的メニューシステム

    Rich ライブラリを使用した美しいメニュー表示とキーボードナビゲーション機能を提供します。
    """

    def __init__(self, console: Console | None = None):
        """メニューシステムを初期化

        Args:
            console: Rich Console インスタンス（省略時は新規作成）

        """
        self.console = console or Console()
        self.menu_stack: list[Menu] = []
        self.running = False

    def show_menu(self, menu: Menu) -> None:
        """メニューを表示

        Args:
            menu: 表示するメニュー

        """
        # メニュータイトルを表示
        title_text = Text(menu.title, style="bold cyan")
        title_panel = Panel(title_text, expand=False, border_style="cyan")
        self.console.print(title_panel)
        self.console.print()

        # メニュー項目をテーブル形式で表示
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold yellow", width=4)
        table.add_column("Title", style="bold white")
        table.add_column("Description", style="dim")

        # 有効なメニュー項目を表示
        for item in menu.items:
            if item.enabled:
                key_style = "bold yellow" if item.enabled else "dim"
                title_style = "bold white" if item.enabled else "dim"
                desc_style = "dim" if item.enabled else "dim red"

                table.add_row(
                    f"[{key_style}]{item.key}[/{key_style}]",
                    f"[{title_style}]{item.title}[/{title_style}]",
                    f"[{desc_style}]{item.description}[/{desc_style}]",
                )

        # 戻るオプション
        if menu.show_back:
            table.add_row(
                "[bold yellow]b[/bold yellow]",
                "[bold white]戻る[/bold white]",
                "[dim]前のメニューに戻ります[/dim]",
            )

        # 終了オプション
        if menu.show_quit:
            table.add_row(
                "[bold red]q[/bold red]",
                "[bold white]終了[/bold white]",
                "[dim]プログラムを終了します[/dim]",
            )

        self.console.print(table)
        self.console.print()

    def get_user_choice(self, menu: Menu) -> str:
        """ユーザーの選択を取得

        Args:
            menu: 現在のメニュー

        Returns:
            ユーザーが選択したキー

        """
        # 有効な選択肢を収集
        valid_choices: list[str] = []
        for item in menu.items:
            if item.enabled:
                valid_choices.append(item.key.lower())

        if menu.show_back:
            valid_choices.append("b")
        if menu.show_quit:
            valid_choices.append("q")

        # ユーザー入力を取得
        while True:
            try:
                choice = Prompt.ask("[bold green]選択してください[/bold green]", console=self.console).lower().strip()

                if choice in valid_choices:
                    return choice
                self.console.print(f"[red]無効な選択です。有効な選択肢: {', '.join(valid_choices)}[/red]")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]操作がキャンセルされました。[/yellow]")
                return "q"
            except EOFError:
                return "q"

    def execute_menu_item(self, item: MenuItem) -> bool:
        """メニュー項目を実行

        Args:
            item: 実行するメニュー項目

        Returns:
            メニューを継続するかどうか（False で終了）

        """
        try:
            if item.submenu:
                # サブメニューを表示
                self.run_menu(item.submenu)
            elif item.action:
                # アクションを実行
                self.console.print(f"[green]実行中: {item.title}[/green]")
                self.console.print()

                result = item.action()

                # 結果を表示
                if result is not None:
                    self.console.print(f"[green]完了: {item.title}[/green]")
                else:
                    self.console.print("[green]実行完了[/green]")

                # 続行確認
                self.console.print()
                Prompt.ask("[dim]Enterキーを押してメニューに戻る[/dim]", default="", console=self.console)

            return True

        except KeyboardInterrupt:
            self.console.print("\n[yellow]操作がキャンセルされました。[/yellow]")
            return True
        except Exception as e:
            self.console.print(f"[red]エラーが発生しました: {e}[/red]")
            self.console.print()
            Prompt.ask("[dim]Enterキーを押してメニューに戻る[/dim]", default="", console=self.console)
            return True

    def run_menu(self, menu: Menu) -> None:
        """メニューを実行

        Args:
            menu: 実行するメニュー

        """
        self.menu_stack.append(menu)

        try:
            while True:
                # 画面をクリア（オプション）
                self.console.clear()

                # メニューを表示
                self.show_menu(menu)

                # ユーザーの選択を取得
                choice = self.get_user_choice(menu)

                # 選択に応じて処理
                if choice == "q":
                    # 終了
                    break
                if choice == "b" and menu.show_back:
                    # 戻る
                    break
                # メニュー項目を実行
                for item in menu.items:
                    if item.enabled and item.key.lower() == choice:
                        if not self.execute_menu_item(item):
                            return
                        break

        finally:
            self.menu_stack.pop()

    def start(self, main_menu: Menu) -> None:
        """メニューシステムを開始

        Args:
            main_menu: メインメニュー

        """
        self.running = True

        try:
            # ウェルカムメッセージ
            welcome_text = Text("CI-Helper 対話的メニュー", style="bold magenta")
            welcome_panel = Panel(welcome_text, expand=False, border_style="magenta", padding=(1, 2))
            self.console.print(welcome_panel)
            self.console.print()

            # メインメニューを実行
            self.run_menu(main_menu)

        except KeyboardInterrupt:
            self.console.print("\n[yellow]プログラムが中断されました。[/yellow]")
        except Exception as e:
            self.console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
        finally:
            self.running = False
            self.console.print("[dim]ありがとうございました。[/dim]")

    def is_running(self) -> bool:
        """メニューシステムが実行中かどうか

        Returns:
            実行中の場合 True

        """
        return self.running

    def get_current_menu(self) -> Menu | None:
        """現在のメニューを取得

        Returns:
            現在のメニュー（スタックが空の場合は None）

        """
        return self.menu_stack[-1] if self.menu_stack else None
