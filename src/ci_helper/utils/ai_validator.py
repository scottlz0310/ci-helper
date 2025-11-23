"""AI プロバイダーの検証ユーティリティ

APIキーの有効性チェックとプロバイダー情報を提供します。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import aiohttp
from rich.console import Console


@dataclass
class ProviderInfo:
    """AIプロバイダー情報"""

    name: str  # プロバイダー名
    display_name: str  # 表示名
    api_key_env: str  # APIキー環境変数名
    default_model: str  # デフォルトモデル
    available_models: list[str]  # 利用可能なモデル
    test_endpoint: str | None = None  # テスト用エンドポイント
    requires_api_key: bool = True  # APIキーが必要かどうか


# サポートされているAIプロバイダー
SUPPORTED_PROVIDERS = {
    "openai": ProviderInfo(
        name="openai",
        display_name="OpenAI",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        available_models=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        test_endpoint="https://api.openai.com/v1/models",
    ),
    "anthropic": ProviderInfo(
        name="anthropic",
        display_name="Anthropic (Claude)",
        api_key_env="ANTHROPIC_API_KEY",
        default_model="claude-3-5-sonnet-20241022",
        available_models=[
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        test_endpoint="https://api.anthropic.com/v1/messages",
    ),
    "local": ProviderInfo(
        name="local",
        display_name="ローカルLLM (Ollama)",
        api_key_env="",
        default_model="llama3.2",
        available_models=["llama3.2", "codellama", "mistral", "qwen2.5"],
        test_endpoint="http://localhost:11434/api/tags",
        requires_api_key=False,
    ),
}


@dataclass
class ValidationResult:
    """検証結果"""

    provider: str  # プロバイダー名
    is_valid: bool  # 有効かどうか
    api_key_found: bool  # APIキーが見つかったか
    api_key_valid: bool  # APIキーが有効か
    available_models: list[str]  # 利用可能なモデル
    error_message: str | None = None  # エラーメッセージ
    warning_message: str | None = None  # 警告メッセージ


class AIProviderValidator:
    """AIプロバイダーの検証クラス"""

    def __init__(self, console: Console | None = None):
        """初期化

        Args:
            console: Rich Console インスタンス

        """
        self.console = console or Console()

    def get_available_providers(self) -> dict[str, ProviderInfo]:
        """利用可能なプロバイダーを取得

        Returns:
            プロバイダー情報の辞書

        """
        return SUPPORTED_PROVIDERS.copy()

    def check_api_key_exists(self, provider: str) -> bool:
        """APIキーが環境変数に設定されているかチェック

        Args:
            provider: プロバイダー名

        Returns:
            APIキーが設定されている場合 True

        """
        if provider not in SUPPORTED_PROVIDERS:
            return False

        provider_info = SUPPORTED_PROVIDERS[provider]
        if not provider_info.requires_api_key:
            return True

        return bool(os.getenv(provider_info.api_key_env))

    async def validate_provider(self, provider: str) -> ValidationResult:
        """プロバイダーを検証

        Args:
            provider: プロバイダー名

        Returns:
            検証結果

        """
        if provider not in SUPPORTED_PROVIDERS:
            return ValidationResult(
                provider=provider,
                is_valid=False,
                api_key_found=False,
                api_key_valid=False,
                available_models=[],
                error_message=f"サポートされていないプロバイダー: {provider}",
            )

        provider_info = SUPPORTED_PROVIDERS[provider]

        # APIキーの存在確認
        api_key_found = self.check_api_key_exists(provider)

        if provider_info.requires_api_key and not api_key_found:
            return ValidationResult(
                provider=provider,
                is_valid=False,
                api_key_found=False,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message=f"{provider_info.api_key_env} 環境変数が設定されていません",
            )

        # API接続テスト
        if provider == "openai":
            return await self._validate_openai(provider_info)
        if provider == "anthropic":
            return await self._validate_anthropic(provider_info)
        if provider == "local":
            return await self._validate_local(provider_info)

        return ValidationResult(
            provider=provider,
            is_valid=True,
            api_key_found=api_key_found,
            api_key_valid=True,
            available_models=provider_info.available_models,
        )

    async def _validate_openai(self, provider_info: ProviderInfo) -> ValidationResult:
        """OpenAI APIを検証"""
        api_key = os.getenv(provider_info.api_key_env)

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    provider_info.test_endpoint,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response,
            ):
                if response.status == 200:
                    data = await response.json()
                    # 利用可能なモデルを取得
                    available_models: list[str] = []
                    if "data" in data:
                        for model in data["data"]:
                            model_id = model.get("id", "")
                            if any(supported in model_id for supported in ["gpt-4", "gpt-3.5"]):
                                available_models.append(model_id)

                    if not available_models:
                        available_models = provider_info.available_models

                    return ValidationResult(
                        provider=provider_info.name,
                        is_valid=True,
                        api_key_found=True,
                        api_key_valid=True,
                        available_models=available_models,
                    )
                if response.status == 401:
                    return ValidationResult(
                        provider=provider_info.name,
                        is_valid=False,
                        api_key_found=True,
                        api_key_valid=False,
                        available_models=provider_info.available_models,
                        error_message="APIキーが無効です",
                    )
                return ValidationResult(
                    provider=provider_info.name,
                    is_valid=False,
                    api_key_found=True,
                    api_key_valid=False,
                    available_models=provider_info.available_models,
                    error_message=f"API接続エラー (HTTP {response.status})",
                )

        except TimeoutError:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message="API接続タイムアウト",
                warning_message="ネットワーク接続を確認してください",
            )
        except Exception as e:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message=f"API接続エラー: {e!s}",
            )

    async def _validate_anthropic(self, provider_info: ProviderInfo) -> ValidationResult:
        """Anthropic APIを検証"""
        api_key = os.getenv(provider_info.api_key_env)

        try:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            # Anthropicは直接的なモデル一覧APIがないため、簡単なテストリクエストを送信
            test_data = {
                "model": provider_info.default_model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "test"}],
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    provider_info.test_endpoint,
                    headers=headers,
                    json=test_data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response,
            ):
                if response.status in [200, 400]:  # 400も有効（リクエスト形式の問題）
                    return ValidationResult(
                        provider=provider_info.name,
                        is_valid=True,
                        api_key_found=True,
                        api_key_valid=True,
                        available_models=provider_info.available_models,
                    )
                if response.status == 401:
                    return ValidationResult(
                        provider=provider_info.name,
                        is_valid=False,
                        api_key_found=True,
                        api_key_valid=False,
                        available_models=provider_info.available_models,
                        error_message="APIキーが無効です",
                    )
                return ValidationResult(
                    provider=provider_info.name,
                    is_valid=False,
                    api_key_found=True,
                    api_key_valid=False,
                    available_models=provider_info.available_models,
                    error_message=f"API接続エラー (HTTP {response.status})",
                )

        except TimeoutError:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message="API接続タイムアウト",
                warning_message="ネットワーク接続を確認してください",
            )
        except Exception as e:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message=f"API接続エラー: {e!s}",
            )

    async def _validate_local(self, provider_info: ProviderInfo) -> ValidationResult:
        """ローカルLLM (Ollama) を検証"""
        try:
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            test_endpoint = f"{ollama_url}/api/tags"

            async with aiohttp.ClientSession() as session:
                async with session.get(test_endpoint, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        # インストール済みモデルを取得
                        available_models: list[str] = []
                        if "models" in data:
                            for model in data["models"]:
                                model_name = model.get("name", "").split(":")[0]
                                if model_name and model_name not in available_models:
                                    available_models.append(model_name)

                        if not available_models:
                            return ValidationResult(
                                provider=provider_info.name,
                                is_valid=False,
                                api_key_found=True,
                                api_key_valid=True,
                                available_models=provider_info.available_models,
                                error_message="Ollamaにモデルがインストールされていません",
                                warning_message="ollama pull llama3.2 でモデルをインストールしてください",
                            )

                        return ValidationResult(
                            provider=provider_info.name,
                            is_valid=True,
                            api_key_found=True,
                            api_key_valid=True,
                            available_models=available_models,
                        )
                    return ValidationResult(
                        provider=provider_info.name,
                        is_valid=False,
                        api_key_found=True,
                        api_key_valid=False,
                        available_models=provider_info.available_models,
                        error_message=f"Ollama接続エラー (HTTP {response.status})",
                    )

        except TimeoutError:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message="Ollama接続タイムアウト",
                warning_message="Ollamaが起動していることを確認してください",
            )
        except Exception as e:
            return ValidationResult(
                provider=provider_info.name,
                is_valid=False,
                api_key_found=True,
                api_key_valid=False,
                available_models=provider_info.available_models,
                error_message=f"Ollama接続エラー: {e!s}",
                warning_message="Ollamaが起動していることを確認してください",
            )

    async def validate_all_providers(self) -> dict[str, ValidationResult]:
        """すべてのプロバイダーを検証

        Returns:
            プロバイダー名と検証結果のマッピング

        """
        results: dict[str, ValidationResult] = {}

        for provider_name in SUPPORTED_PROVIDERS:
            results[provider_name] = await self.validate_provider(provider_name)

        return results

    def display_validation_results(self, results: dict[str, ValidationResult]) -> None:
        """検証結果を表示

        Args:
            results: 検証結果の辞書

        """
        self.console.print("\n[bold blue]🤖 AIプロバイダー検証結果[/bold blue]\n")

        for provider_name, result in results.items():
            provider_info = SUPPORTED_PROVIDERS[provider_name]

            if result.is_valid:
                self.console.print(f"[green]✓[/green] {provider_info.display_name}")
                self.console.print(f"  [dim]利用可能なモデル: {len(result.available_models)}個[/dim]")
                if result.available_models:
                    models_str = ", ".join(result.available_models[:3])
                    if len(result.available_models) > 3:
                        models_str += f" など{len(result.available_models)}個"
                    self.console.print(f"  [dim]{models_str}[/dim]")
            else:
                self.console.print(f"[red]✗[/red] {provider_info.display_name}")
                if result.error_message:
                    self.console.print(f"  [red]{result.error_message}[/red]")
                if result.warning_message:
                    self.console.print(f"  [yellow]{result.warning_message}[/yellow]")

            self.console.print()
