"""
パターン認識設定管理

パターン認識、自動修正、学習機能の設定を管理するクラスを提供します。
"""

from __future__ import annotations

from typing import Any

from ..core.exceptions import ConfigurationError
from ..utils.config import Config
from .models import AIConfig, ProviderConfig


class PatternRecognitionConfigManager:
    """パターン認識設定管理クラス"""

    def __init__(self, config: Config):
        """設定管理を初期化

        Args:
            config: メイン設定オブジェクト
        """
        self.config = config

    def get_pattern_recognition_config(self) -> dict[str, Any]:
        """パターン認識設定を取得

        Returns:
            パターン認識設定の辞書
        """
        return {
            "enabled": self.config.is_pattern_recognition_enabled(),
            "confidence_threshold": self.config.get_pattern_confidence_threshold(),
            "database_path": str(self.config.get_pattern_database_path()),
            "custom_patterns_enabled": self.config.is_custom_patterns_enabled(),
            "enabled_categories": self.config.get_enabled_pattern_categories(),
        }

    def get_auto_fix_config(self) -> dict[str, Any]:
        """自動修正設定を取得

        Returns:
            自動修正設定の辞書
        """
        return {
            "enabled": self.config.is_auto_fix_enabled(),
            "confidence_threshold": self.config.get_auto_fix_confidence_threshold(),
            "risk_tolerance": self.config.get_auto_fix_risk_tolerance(),
            "backup_retention_days": self.config.get_backup_retention_days(),
            "backup_before_fix": self.config.is_backup_before_fix_enabled(),
        }

    def get_learning_config(self) -> dict[str, Any]:
        """学習設定を取得

        Returns:
            学習設定の辞書
        """
        return {
            "enabled": self.config.is_learning_enabled(),
            "feedback_collection_enabled": self.config.is_feedback_collection_enabled(),
            "pattern_discovery_enabled": self.config.is_pattern_discovery_enabled(),
            "min_pattern_occurrences": self.config.get_min_pattern_occurrences(),
        }

    def validate_pattern_category(self, category: str) -> bool:
        """パターンカテゴリの有効性を検証

        Args:
            category: パターンカテゴリ

        Returns:
            カテゴリが有効かどうか

        Raises:
            ConfigurationError: カテゴリが無効な場合
        """
        if not isinstance(category, str) or not category.strip():
            raise ConfigurationError(
                "パターンカテゴリが無効です",
                "空でない文字列を指定してください",
            )

        # 有効なカテゴリかチェック
        valid_categories = ["permission", "network", "config", "dependency", "build", "test", "security", "performance"]

        if category not in valid_categories:
            raise ConfigurationError(
                f"未知のパターンカテゴリです: {category}",
                f"有効なカテゴリ: {', '.join(valid_categories)}",
            )

        return self.config.is_pattern_category_enabled(category)

    def validate_confidence_threshold(self, threshold: float, threshold_type: str = "pattern") -> None:
        """信頼度閾値の有効性を検証

        Args:
            threshold: 信頼度閾値
            threshold_type: 閾値の種類 ("pattern" または "auto_fix")

        Raises:
            ConfigurationError: 閾値が無効な場合
        """
        if not isinstance(threshold, (int, float)):
            raise ConfigurationError(
                f"{threshold_type}信頼度閾値が無効です: {threshold}",
                "数値を指定してください",
            )

        if not (0.0 <= threshold <= 1.0):
            raise ConfigurationError(
                f"{threshold_type}信頼度閾値が範囲外です: {threshold}",
                "0.0から1.0の間の値を指定してください",
            )

    def validate_risk_tolerance(self, risk_tolerance: str) -> None:
        """リスク許容度の有効性を検証

        Args:
            risk_tolerance: リスク許容度

        Raises:
            ConfigurationError: リスク許容度が無効な場合
        """
        valid_levels = ["low", "medium", "high"]
        if risk_tolerance not in valid_levels:
            raise ConfigurationError(
                f"無効なリスク許容度です: {risk_tolerance}",
                f"有効な値: {', '.join(valid_levels)}",
            )

    def create_ai_config_from_settings(self) -> AIConfig:
        """現在の設定からAIConfigオブジェクトを作成

        Returns:
            AIConfigオブジェクト
        """
        ai_config_dict = self.config.get_ai_config()

        # プロバイダー設定を変換
        providers = {}
        for provider_name, provider_data in ai_config_dict.get("providers", {}).items():
            providers[provider_name] = ProviderConfig(
                name=provider_name,
                api_key=self.config.get_ai_provider_api_key(provider_name) or "",
                base_url=provider_data.get("base_url"),
                default_model=provider_data.get("default_model", ""),
                available_models=provider_data.get("available_models", []),
                timeout_seconds=provider_data.get("timeout_seconds", 30),
                max_retries=provider_data.get("max_retries", 3),
                rate_limit_per_minute=provider_data.get("rate_limit_per_minute"),
                cost_per_input_token=provider_data.get("cost_per_input_token", 0.0),
                cost_per_output_token=provider_data.get("cost_per_output_token", 0.0),
            )

        return AIConfig(
            default_provider=ai_config_dict.get("default_provider", "openai"),
            providers=providers,
            cache_enabled=ai_config_dict.get("cache_enabled", True),
            cache_ttl_hours=ai_config_dict.get("cache_ttl_hours", 24),
            cache_max_size_mb=ai_config_dict.get("cache_max_size_mb", 100),
            cost_limits=ai_config_dict.get("cost_limits", {}),
            prompt_templates=ai_config_dict.get("prompt_templates", {}),
            interactive_timeout=ai_config_dict.get("interactive_timeout", 300),
            streaming_enabled=ai_config_dict.get("streaming_enabled", True),
            security_checks_enabled=ai_config_dict.get("security_checks_enabled", True),
            cache_dir=ai_config_dict.get("cache_dir", ".ci-helper/cache"),
            pattern_recognition_enabled=ai_config_dict.get("pattern_recognition_enabled", True),
            pattern_confidence_threshold=ai_config_dict.get("pattern_confidence_threshold", 0.7),
            pattern_database_path=ai_config_dict.get("pattern_database_path", "data/patterns"),
            custom_patterns_enabled=ai_config_dict.get("custom_patterns_enabled", True),
            enabled_pattern_categories=ai_config_dict.get(
                "enabled_pattern_categories", ["permission", "network", "config", "dependency", "build", "test"]
            ),
            auto_fix_enabled=ai_config_dict.get("auto_fix_enabled", False),
            auto_fix_confidence_threshold=ai_config_dict.get("auto_fix_confidence_threshold", 0.8),
            auto_fix_risk_tolerance=ai_config_dict.get("auto_fix_risk_tolerance", "low"),
            backup_retention_days=ai_config_dict.get("backup_retention_days", 30),
            backup_before_fix=ai_config_dict.get("backup_before_fix", True),
            learning_enabled=ai_config_dict.get("learning_enabled", True),
            feedback_collection_enabled=ai_config_dict.get("feedback_collection_enabled", True),
            pattern_discovery_enabled=ai_config_dict.get("pattern_discovery_enabled", True),
            min_pattern_occurrences=ai_config_dict.get("min_pattern_occurrences", 3),
        )

    def save_pattern_categories(self, categories: list[str]) -> None:
        """パターンカテゴリ設定を保存

        Args:
            categories: 有効にするパターンカテゴリのリスト

        Raises:
            ConfigurationError: 保存に失敗した場合
        """
        # カテゴリの検証
        for category in categories:
            try:
                self.validate_pattern_category(category)
            except ConfigurationError:
                # カテゴリが無効でも、設定として保存は許可
                pass

        # 設定ファイルに保存する実装は、実際のファイル更新が必要
        # ここでは検証のみ実行
        if not isinstance(categories, list):
            raise ConfigurationError(
                "パターンカテゴリは配列で指定してください",
                "例: ['permission', 'network', 'config']",
            )

    def get_pattern_database_info(self) -> dict[str, Any]:
        """パターンデータベース情報を取得

        Returns:
            パターンデータベース情報の辞書
        """
        db_path = self.config.get_pattern_database_path()

        return {
            "path": str(db_path),
            "exists": db_path.exists(),
            "custom_patterns_enabled": self.config.is_custom_patterns_enabled(),
            "enabled_categories": self.config.get_enabled_pattern_categories(),
        }

    def ensure_pattern_directories(self) -> None:
        """パターン関連ディレクトリを作成

        Raises:
            ConfigurationError: ディレクトリ作成に失敗した場合
        """
        try:
            # パターンデータベースディレクトリ
            db_path = self.config.get_pattern_database_path()
            db_path.mkdir(parents=True, exist_ok=True)

            # カスタムパターンディレクトリ
            if self.config.is_custom_patterns_enabled():
                custom_path = db_path / "custom"
                custom_path.mkdir(parents=True, exist_ok=True)

            # 学習データディレクトリ
            if self.config.is_learning_enabled():
                learning_path = self.config.project_root / "data" / "learning"
                learning_path.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            raise ConfigurationError(
                "パターン関連ディレクトリの作成に失敗しました",
                f"エラー: {e}",
            ) from e


# Backward compatibility alias
AIConfigManager = PatternRecognitionConfigManager
