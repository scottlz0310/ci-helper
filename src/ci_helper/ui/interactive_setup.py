"""
対話的初期設定

AIモデル選択とAPIキー検証を含む対話的な初期設定機能を提供します。
"""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ..utils.ai_validator import SUPPORTED_PROVIDERS, AIProviderValidator, ValidationResult


class InteractiveSetup:
    """対話的初期設定クラス"""

    def __init__(self, console: Console | None = None):
        """初期化

        Args:
            console: Rich Console インスタンス
        """
        self.console = console or Console()
        self.validator = AIProviderValidator(self.console)
        self.selected_providers: list[str] = []
        self.selected_models: dict[str, str] = {}
        self.validation_results: dict[str, ValidationResult] = {}

    async def run_interactive_setup(self) -> dict[str, Any]:
        """対話的初期設定を実行

        Returns:
            設定情報の辞書
        """
        self.console.print(
            Panel(Text("CI-Helper 対話的初期設定", style="bold magenta"), expand=False, border_style="magenta")
        )
        self.console.print()

        # ステップ1: 環境変数の確認
        self._show_environment_status()

        # ステップ2: AIプロバイダーの検証
        await self._validate_providers()

        # ステップ3: プロバイダーとモデルの選択
        self._select_providers_and_models()

        # ステップ4: 追加設定
        additional_config = self._configure_additional_settings()

        # ステップ5: 設定の確認
        config = self._build_configuration(additional_config)
        self._show_configuration_summary(config)

        if Confirm.ask("\n[bold green]この設定でci-helper.tomlを生成しますか？[/bold green]"):
            return config
        else:
            self.console.print("[yellow]設定をキャンセルしました。[/yellow]")
            return {}

    def _show_environment_status(self) -> None:
        """環境変数の状況を表示"""
        self.console.print("[bold blue]📋 環境変数の確認[/bold blue]\n")

        # GitHub トークンの確認
        github_tokens = ["GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN"]
        github_token_found = None

        for token_name in github_tokens:
            if token_name in os.environ:
                github_token_found = token_name
                break

        if github_token_found:
            self.console.print(f"[green]✓[/green] GitHub トークン: {github_token_found}")
        else:
            self.console.print("[yellow]⚠[/yellow] GitHub トークンが見つかりません")
            self.console.print("  [dim]GitHub Actionsの実行には必要です[/dim]")

        # AIプロバイダーのAPIキー確認
        for _provider_name, provider_info in SUPPORTED_PROVIDERS.items():
            if provider_info.requires_api_key:
                api_key_exists = bool(os.getenv(provider_info.api_key_env))
                if api_key_exists:
                    self.console.print(
                        f"[green]✓[/green] {provider_info.display_name} APIキー: {provider_info.api_key_env}"
                    )
                else:
                    self.console.print(f"[dim]○[/dim] {provider_info.display_name} APIキー: 未設定")

        self.console.print()

    async def _validate_providers(self) -> None:
        """AIプロバイダーを検証"""
        self.console.print("[bold blue]🤖 AIプロバイダーの検証中...[/bold blue]\n")

        # すべてのプロバイダーを検証
        self.validation_results = await self.validator.validate_all_providers()

        # 結果を表示
        for provider_name, result in self.validation_results.items():
            provider_info = SUPPORTED_PROVIDERS[provider_name]

            if result.is_valid:
                self.console.print(f"[green]✓[/green] {provider_info.display_name} - 利用可能")
                if result.available_models:
                    models_preview = ", ".join(result.available_models[:2])
                    if len(result.available_models) > 2:
                        models_preview += f" など{len(result.available_models)}個"
                    self.console.print(f"  [dim]モデル: {models_preview}[/dim]")
            else:
                self.console.print(f"[red]✗[/red] {provider_info.display_name} - 利用不可")
                if result.error_message:
                    self.console.print(f"  [red]{result.error_message}[/red]")
                if result.warning_message:
                    self.console.print(f"  [yellow]{result.warning_message}[/yellow]")

        self.console.print()

    def _select_providers_and_models(self) -> None:
        """プロバイダーとモデルを選択"""
        self.console.print("[bold blue]🎯 AIプロバイダーとモデルの選択[/bold blue]\n")

        # 利用可能なプロバイダーを取得
        available_providers = [name for name, result in self.validation_results.items() if result.is_valid]

        if not available_providers:
            self.console.print("[red]利用可能なAIプロバイダーがありません。[/red]")
            self.console.print("[yellow]APIキーを設定してから再実行してください。[/yellow]")
            return

        # デフォルトプロバイダーの選択
        self.console.print("デフォルトのAIプロバイダーを選択してください：")

        provider_choices = []
        provider_display = {}

        for provider_name in available_providers:
            provider_info = SUPPORTED_PROVIDERS[provider_name]
            choice_key = str(len(provider_choices) + 1)
            provider_choices.append(choice_key)
            provider_display[choice_key] = provider_name

            self.console.print(f"  {choice_key}. {provider_info.display_name}")

            # 推奨マークを表示
            if provider_name == "openai":
                self.console.print("     [dim]（推奨: 高品質で安定）[/dim]")
            elif provider_name == "anthropic":
                self.console.print("     [dim]（高品質、長文対応）[/dim]")
            elif provider_name == "local":
                self.console.print("     [dim]（無料、プライベート）[/dim]")

        default_choice = "1" if "1" in provider_choices else provider_choices[0]
        selected_choice = Prompt.ask(
            "\n[bold green]選択してください[/bold green]", choices=provider_choices, default=default_choice
        )

        default_provider = provider_display[selected_choice]
        self.selected_providers = [default_provider]

        # デフォルトモデルの選択
        self._select_model_for_provider(default_provider, is_default=True)

        # 追加プロバイダーの選択
        remaining_providers = [p for p in available_providers if p != default_provider]

        if remaining_providers and Confirm.ask("\n[bold blue]他のプロバイダーも設定しますか？[/bold blue]"):
            for provider_name in remaining_providers:
                provider_info = SUPPORTED_PROVIDERS[provider_name]
                if Confirm.ask(f"{provider_info.display_name} を追加しますか？"):
                    self.selected_providers.append(provider_name)
                    self._select_model_for_provider(provider_name)

    def _select_model_for_provider(self, provider_name: str, is_default: bool = False) -> None:
        """特定のプロバイダーのモデルを選択"""
        provider_info = SUPPORTED_PROVIDERS[provider_name]
        result = self.validation_results[provider_name]

        available_models = result.available_models if result.available_models else provider_info.available_models

        if len(available_models) <= 1:
            # モデルが1つしかない場合は自動選択
            selected_model = available_models[0] if available_models else provider_info.default_model
            self.selected_models[provider_name] = selected_model

            prefix = "デフォルト" if is_default else ""
            self.console.print(f"[dim]{prefix}モデル: {selected_model}[/dim]")
            return

        # 複数のモデルがある場合は選択
        prefix = "デフォルト" if is_default else provider_info.display_name
        self.console.print(f"\n{prefix}モデルを選択してください：")

        model_choices = []
        model_display = {}

        for i, model in enumerate(available_models, 1):
            choice_key = str(i)
            model_choices.append(choice_key)
            model_display[choice_key] = model

            self.console.print(f"  {choice_key}. {model}")

            # 推奨マークを表示
            if model == provider_info.default_model:
                self.console.print("     [dim]（推奨）[/dim]")
            elif "mini" in model.lower() or "haiku" in model.lower():
                self.console.print("     [dim]（高速・低コスト）[/dim]")
            elif "4o" in model or "opus" in model.lower():
                self.console.print("     [dim]（高性能）[/dim]")

        # デフォルト選択を決定
        default_choice = "1"
        for choice, model in model_display.items():
            if model == provider_info.default_model:
                default_choice = choice
                break

        selected_choice = Prompt.ask(
            "[bold green]選択してください[/bold green]", choices=model_choices, default=default_choice
        )

        selected_model = model_display[selected_choice]
        self.selected_models[provider_name] = selected_model

    def _configure_additional_settings(self) -> dict[str, Any]:
        """追加設定を行う"""
        self.console.print("\n[bold blue]⚙️ 追加設定[/bold blue]\n")

        config = {}

        # キャッシュ設定
        cache_enabled = Confirm.ask("AIレスポンスのキャッシュを有効にしますか？", default=True)
        config["cache_enabled"] = cache_enabled

        if cache_enabled:
            cache_ttl = Prompt.ask("キャッシュの有効期限（時間）", default="24")
            try:
                config["cache_ttl_hours"] = int(cache_ttl)
            except ValueError:
                config["cache_ttl_hours"] = 24

        # コスト制限設定
        if Confirm.ask("月間コスト制限を設定しますか？", default=True):
            monthly_limit = Prompt.ask("月間コスト制限（USD）", default="50.0")
            try:
                config["monthly_usd"] = float(monthly_limit)
            except ValueError:
                config["monthly_usd"] = 50.0

            per_request_limit = Prompt.ask("1回あたりのコスト制限（USD）", default="1.0")
            try:
                config["per_request_usd"] = float(per_request_limit)
            except ValueError:
                config["per_request_usd"] = 1.0

        return config

    def _build_configuration(self, additional_config: dict[str, Any]) -> dict[str, Any]:
        """設定を構築"""
        if not self.selected_providers:
            return {}

        default_provider = self.selected_providers[0]

        config = {
            "ai": {
                "default_provider": default_provider,
                "cache_enabled": additional_config.get("cache_enabled", True),
                "cache_ttl_hours": additional_config.get("cache_ttl_hours", 24),
                "providers": {},
                "cost_limits": {
                    "monthly_usd": additional_config.get("monthly_usd", 50.0),
                    "per_request_usd": additional_config.get("per_request_usd", 1.0),
                },
            }
        }

        # プロバイダー設定を追加
        for provider_name in self.selected_providers:
            provider_info = SUPPORTED_PROVIDERS[provider_name]
            result = self.validation_results[provider_name]

            selected_model = self.selected_models.get(provider_name, provider_info.default_model)
            available_models = result.available_models if result.available_models else provider_info.available_models

            provider_config = {
                "default_model": selected_model,
                "available_models": available_models,
                "timeout_seconds": 30,
                "max_retries": 3,
            }

            # ローカルLLMの場合は追加設定
            if provider_name == "local":
                # WSL環境を検出して適切なURLを設定
                default_url = "auto"  # 自動検出を示す特殊値
                provider_config["base_url"] = os.getenv("OLLAMA_BASE_URL", default_url)
                provider_config["timeout_seconds"] = 60

            config["ai"]["providers"][provider_name] = provider_config

        return config

    def _show_configuration_summary(self, config: dict[str, Any]) -> None:
        """設定の概要を表示"""
        if not config:
            return

        self.console.print("\n[bold blue]📋 設定概要[/bold blue]\n")

        ai_config = config.get("ai", {})

        # 基本設定
        table = Table(show_header=False, box=None)
        table.add_column("項目", style="cyan", width=20)
        table.add_column("値", style="white")

        table.add_row("デフォルトプロバイダー", ai_config.get("default_provider", "未設定"))
        table.add_row("キャッシュ", "有効" if ai_config.get("cache_enabled") else "無効")
        table.add_row("キャッシュ有効期限", f"{ai_config.get('cache_ttl_hours', 24)}時間")

        cost_limits = ai_config.get("cost_limits", {})
        table.add_row("月間コスト制限", f"${cost_limits.get('monthly_usd', 50.0)}")
        table.add_row("1回あたり制限", f"${cost_limits.get('per_request_usd', 1.0)}")

        self.console.print(table)

        # プロバイダー設定
        providers_config = ai_config.get("providers", {})
        if providers_config:
            self.console.print("\n[bold]設定されたプロバイダー:[/bold]")
            for provider_name, provider_config in providers_config.items():
                provider_info = SUPPORTED_PROVIDERS[provider_name]
                self.console.print(f"• {provider_info.display_name}")
                self.console.print(f"  [dim]モデル: {provider_config.get('default_model')}[/dim]")
                available_count = len(provider_config.get("available_models", []))
                self.console.print(f"  [dim]利用可能: {available_count}個のモデル[/dim]")

    def generate_toml_content(self, config: dict[str, Any]) -> str:
        """TOML形式の設定内容を生成"""
        if not config:
            return ""

        lines = [
            "# ci-helper configuration file",
            "# Generated by interactive setup",
            "",
            "[ci-helper]",
            'log_dir = ".ci-helper/logs"',
            'cache_dir = ".ci-helper/cache"',
            'reports_dir = ".ci-helper/reports"',
            "context_lines = 3",
            "max_log_size_mb = 100",
            "max_cache_size_mb = 500",
            'act_image = "ghcr.io/catthehacker/ubuntu:full-24.04"',
            "timeout_seconds = 1800",
            "verbose = false",
            "save_logs = true",
            "",
            '# 注意: base_urlに"auto"を設定すると、WSL環境では自動的にWindowsホストのIPを検出します',
            "",
        ]

        ai_config = config.get("ai", {})

        # AI基本設定
        lines.extend(
            [
                "[ai]",
                f'default_provider = "{ai_config.get("default_provider", "openai")}"',
                f"cache_enabled = {str(ai_config.get('cache_enabled', True)).lower()}",
                f"cache_ttl_hours = {ai_config.get('cache_ttl_hours', 24)}",
                "",
            ]
        )

        # プロバイダー設定
        providers_config = ai_config.get("providers", {})
        for provider_name, provider_config in providers_config.items():
            lines.extend(
                [
                    f"[ai.providers.{provider_name}]",
                    f'default_model = "{provider_config.get("default_model")}"',
                ]
            )

            # available_models を配列として出力
            available_models = provider_config.get("available_models", [])
            if available_models:
                models_str = '", "'.join(available_models)
                lines.append(f'available_models = ["{models_str}"]')

            lines.extend(
                [
                    f"timeout_seconds = {provider_config.get('timeout_seconds', 30)}",
                    f"max_retries = {provider_config.get('max_retries', 3)}",
                ]
            )

            # ローカルLLMの場合は base_url を追加
            if provider_name == "local" and "base_url" in provider_config:
                base_url = provider_config["base_url"]
                lines.append(f'base_url = "{base_url}"  # "auto" で自動検出、または直接URLを指定')

            lines.append("")

        # コスト制限設定
        cost_limits = ai_config.get("cost_limits", {})
        if cost_limits:
            lines.extend(
                [
                    "[ai.cost_limits]",
                    f"monthly_usd = {cost_limits.get('monthly_usd', 50.0)}",
                    f"per_request_usd = {cost_limits.get('per_request_usd', 1.0)}",
                    "",
                ]
            )

        return "\n".join(lines)
