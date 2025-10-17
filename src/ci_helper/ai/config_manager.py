"""
AI設定管理

AI統合機能の設定管理を行うヘルパークラスです。
既存のConfigクラスと連携してAI固有の設定を管理します。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from ..utils.config import Config
from .exceptions import ConfigurationError
from .models import AIConfig, ProviderConfig
from .providers.base import create_provider_config


class AIConfigManager:
    """AI設定管理クラス"""

    def __init__(self, config: Config):
        """AI設定管理を初期化

        Args:
            config: メインの設定オブジェクト
        """
        self.config = config

    def get_ai_config(self) -> AIConfig:
        """AI設定を取得

        Returns:
            AI設定オブジェクト

        Raises:
            ConfigurationError: 設定が無効な場合
        """
        # AI設定の妥当性をチェック
        self.config.validate_ai_config()

        # プロバイダー設定を作成
        providers = {}
        for provider_name in self.config.get_available_ai_providers():
            provider_config = self._create_provider_config(provider_name)
            if provider_config:
                providers[provider_name] = provider_config

        # AI設定オブジェクトを作成
        return AIConfig(
            default_provider=self.config.get_default_ai_provider(),
            providers=providers,
            cache_enabled=self.config.is_ai_cache_enabled(),
            cache_ttl_hours=self.config.get_ai_config("cache_ttl_hours", 24),
            cache_max_size_mb=self.config.get_ai_config("cache_max_size_mb", 100),
            cost_limits=self.config.get_ai_cost_limits(),
            prompt_templates=self.config.get_ai_prompt_templates(),
            interactive_timeout=self.config.get_ai_config("interactive_timeout", 300),
            streaming_enabled=self.config.is_ai_streaming_enabled(),
            security_checks_enabled=self.config.get_ai_config("security_checks_enabled", True),
        )

    def _create_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """プロバイダー設定を作成

        Args:
            provider_name: プロバイダー名

        Returns:
            プロバイダー設定（作成できない場合はNone）
        """
        full_config = self.config.create_ai_provider_config(provider_name)
        if not full_config:
            return None

        return create_provider_config(
            name=full_config["name"],
            api_key=full_config.get("api_key", ""),
            default_model=full_config["default_model"],
            available_models=full_config["available_models"],
            base_url=full_config.get("base_url"),
            timeout_seconds=full_config.get("timeout_seconds", 30),
            max_retries=full_config.get("max_retries", 3),
            rate_limit_per_minute=full_config.get("rate_limit_per_minute"),
            cost_per_input_token=full_config.get("cost_per_input_token", 0.0),
            cost_per_output_token=full_config.get("cost_per_output_token", 0.0),
        )

    def get_available_providers(self) -> List[str]:
        """利用可能なプロバイダー一覧を取得

        Returns:
            プロバイダー名のリスト
        """
        available_providers = []
        for provider_name in self.config.get_available_ai_providers():
            if self._is_provider_configured(provider_name):
                available_providers.append(provider_name)
        return available_providers

    def _is_provider_configured(self, provider_name: str) -> bool:
        """プロバイダーが設定されているかどうかを確認

        Args:
            provider_name: プロバイダー名

        Returns:
            設定されているかどうか
        """
        return self.config.create_ai_provider_config(provider_name) is not None

    def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """指定されたプロバイダーの設定を取得

        Args:
            provider_name: プロバイダー名

        Returns:
            プロバイダー設定（存在しない場合はNone）
        """
        return self._create_provider_config(provider_name)

    def validate_provider_setup(self, provider_name: str) -> Dict[str, any]:
        """プロバイダーのセットアップを検証

        Args:
            provider_name: プロバイダー名

        Returns:
            検証結果
        """
        result = {
            "provider": provider_name,
            "configured": False,
            "api_key_set": False,
            "config_valid": False,
            "issues": [],
            "recommendations": [],
        }

        # プロバイダー設定の存在確認
        provider_config = self.config.get_ai_provider_config(provider_name)
        if not provider_config:
            result["issues"].append(f"プロバイダー '{provider_name}' の設定が見つかりません")
            result["recommendations"].append(f"ci-helper.toml に [ai.providers.{provider_name}] セクションを追加してください")
            return result

        result["configured"] = True

        # APIキーの確認（ローカルLLM以外）
        if provider_name != "local":
            api_key = self.config.get_ai_provider_api_key(provider_name)
            if api_key:
                result["api_key_set"] = True
            else:
                env_key = self._get_api_key_env_name(provider_name)
                result["issues"].append(f"APIキーが設定されていません")
                result["recommendations"].append(f"環境変数 {env_key} を設定してください")

        # 設定の妥当性確認
        try:
            # デフォルトモデルの確認
            default_model = provider_config.get("default_model")
            available_models = provider_config.get("available_models", [])
            
            if not default_model:
                result["issues"].append("デフォルトモデルが設定されていません")
            elif default_model not in available_models:
                result["issues"].append(f"デフォルトモデル '{default_model}' が利用可能モデルに含まれていません")
            
            if not available_models:
                result["issues"].append("利用可能モデルが設定されていません")

            result["config_valid"] = len(result["issues"]) == 0

        except Exception as e:
            result["issues"].append(f"設定の検証中にエラーが発生しました: {e}")

        return result

    def _get_api_key_env_name(self, provider_name: str) -> str:
        """プロバイダーのAPIキー環境変数名を取得

        Args:
            provider_name: プロバイダー名

        Returns:
            環境変数名
        """
        env_mappings = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        return env_mappings.get(provider_name, f"{provider_name.upper()}_API_KEY")

    def get_setup_recommendations(self) -> List[str]:
        """AI設定のセットアップ推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        recommendations = [
            "AI統合機能のセットアップ:",
            "",
            "1. APIキーの設定:",
        ]

        # 各プロバイダーのAPIキー設定方法を追加
        for provider_name in ["openai", "anthropic"]:
            env_key = self._get_api_key_env_name(provider_name)
            recommendations.extend([
                f"   # {provider_name.title()}",
                f"   export {env_key}=your_api_key_here",
            ])

        recommendations.extend([
            "",
            "2. 設定ファイル (ci-helper.toml):",
            "   [ai]",
            "   default_provider = \"openai\"",
            "   cache_enabled = true",
            "",
            "   [ai.providers.openai]",
            "   default_model = \"gpt-4o\"",
            "",
            "3. 使用方法:",
            "   ci-run analyze                    # 最新のログを分析",
            "   ci-run analyze --provider openai  # プロバイダー指定",
            "   ci-run analyze --interactive      # 対話モード",
        ])

        return recommendations

    def create_sample_config(self) -> str:
        """サンプル設定ファイルの内容を生成

        Returns:
            サンプル設定ファイルの内容
        """
        return """# AI統合設定
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
streaming_enabled = true

# コスト制限
[ai.cost_limits]
monthly_usd = 50.0
per_request_usd = 1.0

# OpenAI設定
[ai.providers.openai]
default_model = "gpt-4o"
available_models = ["gpt-4o", "gpt-4o-mini"]
timeout_seconds = 30
max_retries = 3

# Anthropic設定
[ai.providers.anthropic]
default_model = "claude-3-5-sonnet-20241022"
available_models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
timeout_seconds = 30
max_retries = 3

# ローカルLLM設定
[ai.providers.local]
default_model = "llama3.2"
available_models = ["llama3.2", "codellama"]
base_url = "http://localhost:11434"
timeout_seconds = 60
max_retries = 2

# プロンプトテンプレート
[ai.prompt_templates]
analysis = "templates/analysis.txt"
fix_suggestion = "templates/fix.txt"
interactive = "templates/interactive.txt"
"""