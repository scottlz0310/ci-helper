"""
AIプロバイダーモジュール

OpenAI、Anthropic、ローカルLLMなど、複数のAIプロバイダーの実装を提供します。
"""

from __future__ import annotations

from .anthropic import AnthropicProvider

# プロバイダークラスのエクスポート
from .base import AIProvider, ProviderFactory, create_provider_config
from .local import LocalLLMProvider

# 具体的なプロバイダー
from .openai import OpenAIProvider

# プロバイダーを登録
ProviderFactory.register_provider("openai", OpenAIProvider)
ProviderFactory.register_provider("anthropic", AnthropicProvider)
ProviderFactory.register_provider("local", LocalLLMProvider)

__all__ = [
    "AIProvider",
    "AnthropicProvider",
    "LocalLLMProvider",
    "OpenAIProvider",
    "ProviderFactory",
    "create_provider_config",
]
