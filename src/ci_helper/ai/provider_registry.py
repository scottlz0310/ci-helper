"""
AIプロバイダー登録

利用可能なAIプロバイダーを自動的に登録し、ファクトリーで利用できるようにします。
"""

from __future__ import annotations

from .providers.anthropic import AnthropicProvider
from .providers.base import ProviderFactory
from .providers.local import LocalLLMProvider
from .providers.openai import OpenAIProvider


def register_all_providers() -> None:
    """すべての利用可能なプロバイダーを登録"""

    # OpenAI プロバイダーを登録
    ProviderFactory.register_provider("openai", OpenAIProvider)

    # Anthropic プロバイダーを登録
    ProviderFactory.register_provider("anthropic", AnthropicProvider)

    # ローカルLLM プロバイダーを登録
    ProviderFactory.register_provider("local", LocalLLMProvider)


# モジュールインポート時に自動登録
register_all_providers()
