"""
AI統合モジュール

ci-helperのAI分析機能を提供するモジュールです。
複数のAIプロバイダーに対応し、セキュアで効率的なAI統合を実現します。
"""

from __future__ import annotations

__version__ = "1.0.0"

# 主要クラスのエクスポート
# プロバイダーを自動登録
from . import provider_registry
from .config_manager import AIConfigManager
from .exceptions import (
    AIError,
    APIKeyError,
    ConfigurationError,
    NetworkError,
    ProviderError,
    RateLimitError,
    TokenLimitError,
)
from .models import AIConfig, AnalysisResult, AnalyzeOptions, InteractiveSession, ProviderConfig, TokenUsage, UsageStats

# 実装済み
from .prompts import PromptManager
from .providers.anthropic import AnthropicProvider
from .providers.base import AIProvider, ProviderFactory
from .providers.local import LocalLLMProvider
from .providers.openai import OpenAIProvider

# 後で実装される
# from .integration import AIIntegration
# from .cache import ResponseCache
# from .cost_tracker import CostTracker

__all__ = [
    # 基底クラス
    "AIProvider",
    "ProviderFactory",
    # プロバイダー実装
    "OpenAIProvider",
    "AnthropicProvider",
    "LocalLLMProvider",
    # 設定管理
    "AIConfigManager",
    # プロンプト管理
    "PromptManager",
    # データモデル
    "AnalysisResult",
    "AnalyzeOptions",
    "ProviderConfig",
    "AIConfig",
    "TokenUsage",
    "UsageStats",
    "InteractiveSession",
    # 例外
    "AIError",
    "ProviderError",
    "APIKeyError",
    "RateLimitError",
    "TokenLimitError",
    "NetworkError",
    "ConfigurationError",
    # 後で追加される
    # "AIIntegration",
    # "ResponseCache",
    # "CostTracker",
]
