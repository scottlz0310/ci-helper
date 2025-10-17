"""
AI統合モジュール

ci-helperのAI分析機能を提供するモジュールです。
複数のAIプロバイダーに対応し、セキュアで効率的なAI統合を実現します。
"""

from __future__ import annotations

__version__ = "1.0.0"

# 主要クラスのエクスポート
# プロバイダーを自動登録
# プロバイダーを自動登録
from . import provider_registry  # noqa: F401
from .cache import ResponseCache
from .cache_manager import CacheManager
from .config_manager import AIConfigManager
from .cost_manager import CostManager
from .cost_tracker import CostTracker
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
# from .cost_tracker import CostTracker

__all__ = [
    "AIConfig",
    # 設定管理
    "AIConfigManager",
    # 例外
    "AIError",
    # 基底クラス
    "AIProvider",
    "APIKeyError",
    # データモデル
    "AnalysisResult",
    "AnalyzeOptions",
    "AnthropicProvider",
    "CacheManager",
    "ConfigurationError",
    "CostManager",
    # コスト管理
    "CostTracker",
    "InteractiveSession",
    "LocalLLMProvider",
    "NetworkError",
    # プロバイダー実装
    "OpenAIProvider",
    # プロンプト管理
    "PromptManager",
    "ProviderConfig",
    "ProviderError",
    "ProviderFactory",
    "RateLimitError",
    # キャッシュ管理
    "ResponseCache",
    "TokenLimitError",
    "TokenUsage",
    "UsageStats",
    # 後で追加される
    # "AIIntegration",
]
