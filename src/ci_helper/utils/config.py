"""
設定管理ユーティリティ

TOML設定ファイル、環境変数、デフォルト値の管理を行います。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    pass

import tomllib

from ..core.exceptions import ConfigurationError, SecurityError


class Config:
    """設定管理クラス

    優先順位:
    1. コマンドライン引数（呼び出し側で処理）
    2. 環境変数
    3. プロジェクト設定ファイル (ci-helper.toml)
    4. デフォルト値
    """

    # デフォルト設定
    DEFAULT_CONFIG: ClassVar[dict[str, Any]] = {
        "log_dir": ".ci-helper/logs",
        "cache_dir": ".ci-helper/cache",
        "reports_dir": ".ci-helper/reports",
        "context_lines": 3,
        "max_log_size_mb": 100,
        "max_cache_size_mb": 500,
        "act_image": "ghcr.io/catthehacker/ubuntu:full-24.04",
        "timeout_seconds": 1800,  # 30分
        "verbose": False,
        "save_logs": True,
    }

    # AI統合のデフォルト設定
    DEFAULT_AI_CONFIG: ClassVar[dict[str, Any]] = {
        "default_provider": "openai",
        "cache_enabled": True,
        "cache_ttl_hours": 24,
        "cache_max_size_mb": 100,
        "interactive_timeout": 300,
        "streaming_enabled": True,
        "security_checks_enabled": True,
        "cost_limits": {
            "monthly_usd": 50.0,
            "per_request_usd": 1.0,
        },
        "providers": {
            "openai": {
                "default_model": "gpt-4o",
                "available_models": ["gpt-4o", "gpt-4o-mini"],
                "timeout_seconds": 30,
                "max_retries": 3,
                "cost_per_input_token": 0.0025 / 1000,  # $2.50 per 1M tokens
                "cost_per_output_token": 0.01 / 1000,  # $10.00 per 1M tokens
            },
            "anthropic": {
                "default_model": "claude-3-5-sonnet-20241022",
                "available_models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                "timeout_seconds": 30,
                "max_retries": 3,
                "cost_per_input_token": 0.003 / 1000,  # $3.00 per 1M tokens
                "cost_per_output_token": 0.015 / 1000,  # $15.00 per 1M tokens
            },
            "local": {
                "default_model": "llama3.2",
                "available_models": ["llama3.2", "codellama"],
                "base_url": "http://localhost:11434",
                "timeout_seconds": 60,
                "max_retries": 2,
                "cost_per_input_token": 0.0,
                "cost_per_output_token": 0.0,
            },
        },
        "prompt_templates": {
            "analysis": "templates/analysis.txt",
            "fix_suggestion": "templates/fix.txt",
            "interactive": "templates/interactive.txt",
        },
    }

    def __init__(self, project_root: Path | None = None, validate_security: bool = True):
        """設定を初期化

        Args:
            project_root: プロジェクトルートディレクトリ（Noneの場合は現在のディレクトリ）
            validate_security: セキュリティ検証を有効にするかどうか
        """
        self.project_root = project_root or Path.cwd()
        self.config_file = self.project_root / "ci-helper.toml"
        self.validate_security = validate_security

        if validate_security:
            from ..core.security import SecurityValidator

            self.security_validator = SecurityValidator()

        # 設定を読み込み
        self._config = self._load_config()
        self._ai_config = self._load_ai_config()

    def _load_config(self) -> dict[str, Any]:
        """設定を読み込み、優先順位に従ってマージ"""
        config = self.DEFAULT_CONFIG.copy()

        # プロジェクト設定ファイルから読み込み
        if self.config_file.exists():
            try:
                with open(self.config_file, "rb") as f:
                    project_config = tomllib.load(f)

                # セキュリティ検証
                if self.validate_security:
                    self._validate_config_security(self.config_file)

                config.update(project_config.get("ci-helper", {}))
            except SecurityError:
                # セキュリティエラーは再発生
                raise
            except Exception as e:
                raise ConfigurationError(
                    f"設定ファイルの読み込みに失敗しました: {self.config_file}",
                    f"設定ファイルの構文を確認してください: {e}",
                ) from e

        # 環境変数から読み込み
        env_config = self._load_env_config()
        config.update(env_config)

        return config

    def _load_env_config(self) -> dict[str, Any]:
        """環境変数から設定を読み込み"""
        env_config: dict[str, Any] = {}

        # CI_HELPER_* 環境変数をチェック
        for key, default_value in self.DEFAULT_CONFIG.items():
            env_key = f"CI_HELPER_{key.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                # 型変換
                if isinstance(default_value, bool):
                    env_config[key] = env_value.lower() in ("true", "1", "yes", "on")
                elif isinstance(default_value, int):
                    try:
                        env_config[key] = int(env_value)
                    except ValueError as e:
                        raise ConfigurationError(
                            f"環境変数 {env_key} の値が無効です: {env_value}", "整数値を指定してください"
                        ) from e
                elif isinstance(default_value, str):
                    env_config[key] = env_value

        return env_config

    def _load_ai_config(self) -> dict[str, Any]:
        """AI設定を読み込み、優先順位に従ってマージ"""
        ai_config = self.DEFAULT_AI_CONFIG.copy()

        # プロジェクト設定ファイルからAI設定を読み込み
        if self.config_file.exists():
            try:
                with open(self.config_file, "rb") as f:
                    project_config = tomllib.load(f)

                # ai セクションがある場合は更新
                if "ai" in project_config:
                    ai_section = project_config["ai"]

                    # トップレベル設定を更新
                    for key in [
                        "default_provider",
                        "cache_enabled",
                        "cache_ttl_hours",
                        "cache_max_size_mb",
                        "interactive_timeout",
                        "streaming_enabled",
                        "security_checks_enabled",
                    ]:
                        if key in ai_section:
                            ai_config[key] = ai_section[key]

                    # cost_limits を更新
                    if "cost_limits" in ai_section:
                        ai_config["cost_limits"].update(ai_section["cost_limits"])

                    # providers を更新
                    if "providers" in ai_section:
                        for provider_name, provider_config in ai_section["providers"].items():
                            if provider_name in ai_config["providers"]:
                                ai_config["providers"][provider_name].update(provider_config)
                            else:
                                ai_config["providers"][provider_name] = provider_config

                    # prompt_templates を更新
                    if "prompt_templates" in ai_section:
                        ai_config["prompt_templates"].update(ai_section["prompt_templates"])

            except Exception as e:
                raise ConfigurationError(
                    f"AI設定の読み込みに失敗しました: {self.config_file}",
                    f"AI設定セクションの構文を確認してください: {e}",
                ) from e

        # 環境変数からAI設定を読み込み
        env_ai_config = self._load_ai_env_config()
        ai_config.update(env_ai_config)

        return ai_config

    def _load_ai_env_config(self) -> dict[str, Any]:
        """環境変数からAI設定を読み込み"""
        env_config: dict[str, Any] = {}

        # CI_HELPER_AI_* 環境変数をチェック
        ai_env_mappings = {
            "CI_HELPER_AI_PROVIDER": "default_provider",
            "CI_HELPER_AI_CACHE_ENABLED": "cache_enabled",
            "CI_HELPER_AI_STREAMING_ENABLED": "streaming_enabled",
            "CI_HELPER_AI_INTERACTIVE_TIMEOUT": "interactive_timeout",
        }

        for env_key, config_key in ai_env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                # 型変換
                if config_key in ["cache_enabled", "streaming_enabled"]:
                    env_config[config_key] = env_value.lower() in ("true", "1", "yes", "on")
                elif config_key == "interactive_timeout":
                    try:
                        env_config[config_key] = int(env_value)
                    except ValueError as e:
                        raise ConfigurationError(
                            f"環境変数 {env_key} の値が無効です: {env_value}", "整数値を指定してください"
                        ) from e
                else:
                    env_config[config_key] = env_value

        return env_config

    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得

        Args:
            key: 設定キー
            default: デフォルト値

        Returns:
            設定値
        """
        return self._config.get(key, default)

    def get_path(self, key: str) -> Path:
        """パス設定を絶対パスで取得

        Args:
            key: パス設定のキー

        Returns:
            絶対パス
        """
        path_str = self.get(key)
        if path_str is None:
            raise ConfigurationError(f"パス設定 '{key}' が見つかりません")

        path = Path(path_str)
        if not path.is_absolute():
            path = self.project_root / path

        return path

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        for key in ["log_dir", "cache_dir", "reports_dir"]:
            directory = self.get_path(key)
            directory.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """設定の妥当性をチェック"""
        # 必須設定のチェック - デフォルト値があるので基本的にNoneにはならない
        required_keys = ["log_dir", "cache_dir", "reports_dir"]
        for key in required_keys:
            value = self.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ConfigurationError(
                    f"必須設定 '{key}' が設定されていません",
                    f"ci-helper.tomlまたは環境変数 CI_HELPER_{key.upper()} を設定してください",
                )

        # 数値設定の範囲チェック
        timeout = self.get("timeout_seconds", self.DEFAULT_CONFIG["timeout_seconds"])
        if not isinstance(timeout, int | float) or timeout <= 0:
            raise ConfigurationError(f"タイムアウト設定が無効です: {timeout}", "正の整数を指定してください")

        max_log_size = self.get("max_log_size_mb", self.DEFAULT_CONFIG["max_log_size_mb"])
        if not isinstance(max_log_size, int | float) or max_log_size <= 0:
            raise ConfigurationError(f"最大ログサイズ設定が無効です: {max_log_size}", "正の整数を指定してください")

    def __getitem__(self, key: str) -> Any:
        """辞書風アクセスをサポート"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """in演算子をサポート"""
        return key in self._config

    def _validate_config_security(self, config_file: Path) -> None:
        """設定ファイルのセキュリティを検証

        Args:
            config_file: 設定ファイルのパス

        Raises:
            SecurityError: セキュリティ問題が検出された場合
        """
        if not hasattr(self, "security_validator"):
            return

        try:
            with open(config_file, encoding="utf-8") as f:
                content = f.read()

            # 設定ファイルのセキュリティ検証
            config_files = {str(config_file): content}
            validation_result = self.security_validator.validate_config_security(config_files)

            if not validation_result["overall_valid"]:
                # 重大な問題がある場合は例外を発生
                critical_issues = validation_result["critical_issues"]
                if critical_issues > 0:
                    raise SecurityError(
                        f"設定ファイル '{config_file}' に{critical_issues}件の重大なセキュリティ問題が検出されました",
                        "シークレットを環境変数に移動し、設定ファイルから削除してください",
                    )

        except SecurityError:
            raise
        except Exception:
            # セキュリティ検証自体のエラーは警告として扱う
            pass

    def validate_all_config_files(self) -> dict[str, Any]:
        """全ての設定ファイルのセキュリティを検証

        Returns:
            検証結果の辞書
        """
        if not hasattr(self, "security_validator"):
            return {
                "overall_valid": True,
                "message": "セキュリティ検証が無効になっています",
            }

        config_files = {}

        # ci-helper.toml
        if self.config_file.exists():
            with open(self.config_file, encoding="utf-8") as f:
                config_files[str(self.config_file)] = f.read()

        # .env ファイル
        env_file = self.project_root / ".env"
        if env_file.exists():
            with open(env_file, encoding="utf-8") as f:
                config_files[str(env_file)] = f.read()

        # .actrc ファイル
        actrc_file = self.project_root / ".actrc"
        if actrc_file.exists():
            with open(actrc_file, encoding="utf-8") as f:
                config_files[str(actrc_file)] = f.read()

        if not config_files:
            return {
                "overall_valid": True,
                "message": "検証対象の設定ファイルが見つかりませんでした",
            }

        return self.security_validator.validate_config_security(config_files)

    def get_secret_recommendations(self) -> list[str]:
        """シークレット管理の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        return [
            "シークレット管理のベストプラクティス:",
            "",
            "1. 環境変数の使用:",
            "   export OPENAI_API_KEY=your_api_key",
            "   export GITHUB_TOKEN=your_token",
            "",
            "2. .env ファイルの使用:",
            "   echo 'OPENAI_API_KEY=your_api_key' >> .env",
            "   echo '.env' >> .gitignore",
            "",
            "3. 設定ファイルでの参照:",
            "   [ci-helper]",
            "   # 良い例: 環境変数参照",
            "   api_key = '${OPENAI_API_KEY}'",
            "   # 悪い例: 直接記載",
            "   # api_key = 'sk-1234567890abcdef'",
            "",
            "4. act実行時の環境変数:",
            "   ci-helperは自動的に安全な環境変数のみをactに渡します",
        ]

    def get_project_root(self) -> Path:
        """プロジェクトルートディレクトリを取得

        Returns:
            プロジェクトルートディレクトリのパス
        """
        return self.project_root

    # AI設定関連のメソッド
    def get_ai_config(self, key: str = None, default: Any = None) -> Any:
        """AI設定値を取得

        Args:
            key: 設定キー（Noneの場合は全AI設定を返す）
            default: デフォルト値

        Returns:
            AI設定値
        """
        if key is None:
            return self._ai_config
        return self._ai_config.get(key, default)

    def get_ai_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        """指定されたAIプロバイダーの設定を取得

        Args:
            provider_name: プロバイダー名

        Returns:
            プロバイダー設定（存在しない場合はNone）
        """
        providers = self.get_ai_config("providers", {})
        return providers.get(provider_name)

    def get_available_ai_providers(self) -> list[str]:
        """利用可能なAIプロバイダー一覧を取得

        Returns:
            プロバイダー名のリスト
        """
        providers = self.get_ai_config("providers", {})
        return list(providers.keys())

    def get_default_ai_provider(self) -> str:
        """デフォルトAIプロバイダーを取得

        Returns:
            デフォルトプロバイダー名
        """
        return self.get_ai_config("default_provider", "openai")

    def is_ai_cache_enabled(self) -> bool:
        """AIキャッシュが有効かどうかを確認

        Returns:
            キャッシュが有効かどうか
        """
        return self.get_ai_config("cache_enabled", True)

    def is_ai_streaming_enabled(self) -> bool:
        """AIストリーミングが有効かどうかを確認

        Returns:
            ストリーミングが有効かどうか
        """
        return self.get_ai_config("streaming_enabled", True)

    def get_ai_cost_limits(self) -> dict[str, float]:
        """AIコスト制限を取得

        Returns:
            コスト制限の辞書
        """
        return self.get_ai_config("cost_limits", {})

    def get_ai_prompt_templates(self) -> dict[str, str]:
        """AIプロンプトテンプレートを取得

        Returns:
            プロンプトテンプレートの辞書
        """
        return self.get_ai_config("prompt_templates", {})

    def validate_ai_config(self) -> None:
        """AI設定の妥当性をチェック

        Raises:
            ConfigurationError: 設定が無効な場合
        """
        # デフォルトプロバイダーの存在確認
        default_provider = self.get_default_ai_provider()
        available_providers = self.get_available_ai_providers()

        if default_provider not in available_providers:
            raise ConfigurationError(
                f"デフォルトAIプロバイダー '{default_provider}' が設定されていません",
                f"利用可能なプロバイダー: {', '.join(available_providers)}",
            )

        # 各プロバイダー設定の検証
        for provider_name in available_providers:
            provider_config = self.get_ai_provider_config(provider_name)
            if not provider_config:
                continue

            # 必須フィールドの確認
            required_fields = ["default_model", "available_models"]
            for field in required_fields:
                if field not in provider_config:
                    raise ConfigurationError(
                        f"プロバイダー '{provider_name}' の設定に必須フィールド '{field}' がありません",
                        "設定ファイルを確認してください",
                    )

            # デフォルトモデルが利用可能モデルに含まれているかチェック
            default_model = provider_config.get("default_model")
            available_models = provider_config.get("available_models", [])

            if default_model not in available_models:
                raise ConfigurationError(
                    f"プロバイダー '{provider_name}' のデフォルトモデル '{default_model}' が利用可能モデルに含まれていません",
                    f"利用可能なモデル: {', '.join(available_models)}",
                )

        # コスト制限の検証
        cost_limits = self.get_ai_cost_limits()
        for limit_key, limit_value in cost_limits.items():
            if not isinstance(limit_value, (int, float)) or limit_value < 0:
                raise ConfigurationError(
                    f"コスト制限 '{limit_key}' の値が無効です: {limit_value}",
                    "正の数値を指定してください",
                )

    def get_ai_provider_api_key(self, provider_name: str) -> str | None:
        """環境変数からAIプロバイダーのAPIキーを取得

        Args:
            provider_name: プロバイダー名

        Returns:
            APIキー（存在しない場合はNone）
        """
        # プロバイダー別の環境変数名マッピング
        env_key_mappings = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "local": None,  # ローカルLLMはAPIキー不要
        }

        env_key = env_key_mappings.get(provider_name)
        if env_key is None:
            return None

        return os.getenv(env_key)

    def create_ai_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        """AIプロバイダーの完全な設定を作成

        Args:
            provider_name: プロバイダー名

        Returns:
            プロバイダー設定（APIキーが設定されていない場合はNone）
        """
        provider_config = self.get_ai_provider_config(provider_name)
        if not provider_config:
            return None

        # APIキーを取得
        api_key = self.get_ai_provider_api_key(provider_name)

        # ローカルLLM以外でAPIキーが必要
        if provider_name != "local" and not api_key:
            return None

        # 完全な設定を作成
        full_config = provider_config.copy()
        full_config["name"] = provider_name
        if api_key:
            full_config["api_key"] = api_key

        return full_config
