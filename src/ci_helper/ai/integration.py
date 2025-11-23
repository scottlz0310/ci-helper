"""AI統合メインロジック

ci-helperのAI分析機能の中核となるクラスです。
複数のAIプロバイダーを統合し、ログ分析、修正提案、対話モードを提供します。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.models import FailureType
from ..utils.config import Config
from .cache_manager import CacheManager
from .config_manager import AIConfigManager
from .cost_manager import CostManager
from .error_handler import AIErrorHandler

if TYPE_CHECKING:
    from .models import FixSuggestion

from .exceptions import (
    AIError,
    APIKeyError,
    ConfigurationError,
    CostLimitError,
    NetworkError,
    ProviderError,
    RateLimitError,
    TokenLimitError,
)
from .fallback_handler import FallbackHandler
from .fix_applier import FixApplier, FixSuggestionsSummary, RollbackResult
from .fix_generator import FixSuggestionGenerator
from .interactive_session import InteractiveSessionManager
from .models import AIConfig, AnalysisResult, AnalysisStatus, AnalyzeOptions, InteractiveSession, ProviderConfig
from .prompts import PromptManager
from .providers.base import AIProvider, ProviderFactory

logger = logging.getLogger(__name__)


class AIIntegration:
    """AI統合メインクラス

    複数のAIプロバイダーを統合し、ログ分析、修正提案、対話モードを提供します。
    """

    def __init__(self, config: Config | dict[str, Any] | AIConfig):
        """AI統合を初期化

        Args:
            config: 設定オブジェクト（Config、dict、またはAIConfig）

        """
        # 設定オブジェクトの型に応じて処理
        if isinstance(config, dict):
            # 辞書の場合はAIConfigオブジェクトに変換
            config_dict: dict[str, Any] = config
            ai_section: dict[str, Any] = config_dict.get("ai", {})
            providers_data: dict[str, dict[str, Any]] = ai_section.get("providers", {})

            providers: dict[str, ProviderConfig] = {}
            for name, provider_data in providers_data.items():
                providers[name] = ProviderConfig(
                    name=name,
                    api_key=provider_data.get("api_key", ""),
                    base_url=provider_data.get("base_url"),
                    default_model=provider_data.get("default_model", ""),
                    available_models=provider_data.get("available_models", []),
                    timeout_seconds=provider_data.get("timeout_seconds", 30),
                    max_retries=provider_data.get("max_retries", 3),
                )

            self.ai_config = AIConfig(
                default_provider=ai_section.get("default_provider", "openai"),
                providers=providers,
                cache_enabled=ai_section.get("cache_enabled", True),
                cache_ttl_hours=ai_section.get("cache_ttl_hours", 24),
                cache_max_size_mb=ai_section.get("cache_max_size_mb", 100),
                cost_limits=ai_section.get("cost_limits", {}),
                prompt_templates=ai_section.get("prompts", {}),
                interactive_timeout=ai_section.get("interactive_timeout", 300),
            )

            # 仮のConfigオブジェクトを作成
            from pathlib import Path

            from ci_helper.utils.config import Config

            self.config = Config(project_root=Path.cwd())
            # 辞書から作成した場合はAIConfigManagerを作成しない
            self.ai_config_manager = None

        elif isinstance(config, AIConfig):
            # AIConfigオブジェクトの場合
            self.ai_config = config
            # 仮のConfigオブジェクトを作成
            from pathlib import Path

            from ci_helper.utils.config import Config

            self.config = Config(project_root=Path.cwd())
            # AIConfigが直接渡された場合はAIConfigManagerを作成しない
            self.ai_config_manager = None

        else:
            # Configオブジェクトの場合
            self.config = config
            # AIConfigManagerを作成
            self.ai_config_manager = AIConfigManager(self.config)
            # AI設定はinitialize()で読み込む
            self.ai_config = None

        # 他のコンポーネントを初期化

        if hasattr(self, "config"):
            self.error_handler = AIErrorHandler(self.config)
            self.fallback_handler = FallbackHandler(self.config)
        else:
            # テスト用の最小限の初期化
            self.error_handler = None
            self.fallback_handler = None

        self.prompt_manager: PromptManager | None = None
        self.cache_manager: CacheManager | None = None
        self.cost_manager: CostManager | None = None
        self.fix_generator: FixSuggestionGenerator | None = None
        self.fix_applier: FixApplier | None = None
        self.providers: dict[str, AIProvider] = {}
        self.active_sessions: dict[str, InteractiveSession] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """AI統合システムを初期化

        設定の読み込み、プロバイダーの初期化、キャッシュとコスト管理の設定を行います。

        Raises:
            ConfigurationError: 設定が無効な場合
            ProviderError: プロバイダーの初期化に失敗した場合

        """
        if self._initialized:
            return

        logger.info("AI統合システムを初期化中...")

        try:
            # AI設定を読み込み（まだ設定されていない場合のみ）
            if self.ai_config is None and self.ai_config_manager is not None:
                self.ai_config = self.ai_config_manager.get_ai_config()

            # AI設定が初期化されているかチェック
            if self.ai_config is None:
                raise ConfigurationError("AI設定が初期化されていません")

            # プロンプト管理を初期化
            self.prompt_manager = PromptManager()

            # セッション管理を初期化
            self.session_manager = InteractiveSessionManager(self.prompt_manager)

            # コマンドプロセッサーを初期化
            from .interactive_commands import InteractiveCommandProcessor

            self.session_manager.command_processor = InteractiveCommandProcessor(self.session_manager)

            # 修正提案生成器を初期化
            self.fix_generator = FixSuggestionGenerator(self.prompt_manager)

            # 修正適用器を初期化
            self.fix_applier = FixApplier(self.config, interactive=True)

            # パターン認識エンジンを初期化
            from .pattern_engine import PatternRecognitionEngine

            pattern_data_dir = Path("data/patterns")
            self.pattern_engine = PatternRecognitionEngine(
                data_directory=pattern_data_dir,
                confidence_threshold=0.7,  # デフォルト信頼度閾値
            )

            # キャッシュ管理を初期化
            if self.ai_config.cache_enabled:
                cache_dir = self.config.get_path("cache_dir") / "ai"
                self.cache_manager = CacheManager(
                    cache_dir=cache_dir,
                    enabled=True,
                    max_size_mb=self.ai_config.cache_max_size_mb,
                    ttl_hours=self.ai_config.cache_ttl_hours,
                )

            # コスト管理を初期化
            cost_storage_path = self.config.get_path("cache_dir") / "ai" / "usage.json"
            self.cost_manager = CostManager(storage_path=cost_storage_path, cost_limits=self.ai_config.cost_limits)

            # 利用可能なプロバイダーを初期化
            await self._initialize_providers()

            # パターン認識エンジンを初期化
            if hasattr(self, "pattern_engine"):
                await self.pattern_engine.initialize()

            self._initialized = True
            logger.info("AI統合システムの初期化完了 (プロバイダー: %d個)", len(self.providers))

        except AIError:
            # AI固有のエラーはそのまま再発生
            raise
        except Exception as e:
            logger.error("AI統合システムの初期化に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise ConfigurationError(f"AI統合システムの初期化に失敗しました: {error_info['message']}") from e
            raise ConfigurationError(f"AI統合システムの初期化に失敗しました: {e}") from e

    async def _initialize_providers(self) -> None:
        """利用可能なプロバイダーを初期化"""
        if not self.ai_config:
            raise ConfigurationError("AI設定が初期化されていません")

        first_error = None  # 最初のエラーを記録

        for provider_name, provider_config in self.ai_config.providers.items():
            try:
                # プロバイダーを作成
                provider = ProviderFactory.create_provider(provider_name, provider_config)

                # プロバイダーを初期化
                await provider.initialize()

                # 接続を検証
                if await provider.validate_connection():
                    self.providers[provider_name] = provider
                    logger.info("プロバイダー '%s' を初期化しました", provider_name)
                else:
                    logger.warning("プロバイダー '%s' の接続検証に失敗しました", provider_name)

            except ConfigurationError as e:
                # 最初のエラーを記録
                if first_error is None:
                    first_error = e
                # 設定エラーは警告を出して次に進む
                logger.warning("プロバイダー '%s' の設定エラー: %s", provider_name, e)
            except (APIKeyError, RateLimitError, ProviderError) as e:
                # 最初のエラーを記録
                if first_error is None:
                    first_error = e
                # APIキーエラーやレート制限エラーは警告を出して次に進む
                # （テスト環境ではモックされていないプロバイダーがある可能性がある）
                logger.warning("プロバイダー '%s' の初期化に失敗: %s", provider_name, e)
            except Exception as e:
                # 最初のエラーを記録
                if first_error is None:
                    first_error = e
                logger.warning("プロバイダー '%s' の初期化に失敗: %s", provider_name, e)

        if not self.providers:
            # 全てのプロバイダーが失敗した場合、最初のエラーを再発生
            if first_error:
                raise first_error
            if self.ai_config.default_provider:
                raise ProviderError(
                    self.ai_config.default_provider,
                    f"デフォルトプロバイダー '{self.ai_config.default_provider}' が設定されていないか、初期化に失敗しました",
                )
            raise ProviderError("", "利用可能なAIプロバイダーがありません")

    async def analyze_log(self, log_content: str, options: AnalyzeOptions) -> AnalysisResult:
        """ログを分析してAI結果を返す

        Args:
            log_content: 分析対象のログ内容
            options: 分析オプション

        Returns:
            分析結果

        Raises:
            AIError: 分析に失敗した場合
            ConfigurationError: 設定が無効な場合

        """
        if not self._initialized:
            await self.initialize()

        start_time = datetime.now()

        try:
            # プロバイダーを選択
            provider = self._select_provider(options.provider)

            # ログ内容を前処理
            formatted_log = await self._preprocess_log(log_content)

            # パターン認識を実行（フォールバック機能付き）
            pattern_analysis_result = None
            if hasattr(self, "pattern_engine") and self.pattern_engine:
                try:
                    pattern_analysis_result = await self.pattern_engine.analyze_with_fallback(formatted_log)
                    if pattern_analysis_result.pattern_matches:
                        logger.info(
                            "パターン認識で %d 個のパターンを検出",
                            len(pattern_analysis_result.pattern_matches),
                        )
                    elif pattern_analysis_result.status == AnalysisStatus.FALLBACK:
                        logger.info("パターン認識フォールバック処理を実行")
                    elif pattern_analysis_result.status == AnalysisStatus.LOW_CONFIDENCE:
                        logger.info("低信頼度パターンを検出")
                except Exception as pattern_error:
                    logger.warning("パターン認識中にエラー: %s", pattern_error)
                    # 不正な形式のログファイルの場合の処理
                    if "format" in str(pattern_error).lower() or "encoding" in str(pattern_error).lower():
                        pattern_analysis_result = self.pattern_engine.handle_malformed_log(formatted_log, pattern_error)

            # キャッシュをチェック
            cached_result = None
            if options.use_cache and self.cache_manager:
                try:
                    model = options.model or provider.config.default_model
                    cached_result = await self.cache_manager.get_cached_result(
                        prompt=options.custom_prompt or "default",
                        context=formatted_log,
                        model=model,
                        provider=provider.name,
                    )

                    if cached_result:
                        logger.info("キャッシュされた分析結果を使用")
                        cached_result.cache_hit = True
                        return cached_result
                except Exception as cache_error:
                    # キャッシュ読み込みエラーは警告を出すが継続する
                    logger.warning("キャッシュ読み込みに失敗しました: %s", cache_error)

            # パターン認識がフォールバック結果を提供した場合はそれを返す
            if (
                pattern_analysis_result
                and pattern_analysis_result.status in [AnalysisStatus.FALLBACK, AnalysisStatus.LOW_CONFIDENCE]
                and not options.force_ai_analysis
            ):
                logger.info("パターン認識フォールバック結果を返します")
                pattern_analysis_result.analysis_time = (datetime.now() - start_time).total_seconds()
                return pattern_analysis_result

            # プロンプトを生成
            prompt = self._generate_analysis_prompt(formatted_log, options)

            # コスト推定と制限チェック
            await self._check_cost_limits(provider, prompt, formatted_log, options)

            # AI分析を実行
            result = await self._execute_analysis(provider, prompt, formatted_log, options)

            # 分析時間を記録
            analysis_time = (datetime.now() - start_time).total_seconds()
            result.analysis_time = analysis_time
            result.provider = provider.name
            result.model = options.model or provider.config.default_model
            result.status = AnalysisStatus.COMPLETED

            # パターン認識結果を追加
            if pattern_analysis_result and pattern_analysis_result.pattern_matches:
                # パターンマッチ結果をAnalysisResultに保存
                result.pattern_matches = pattern_analysis_result.pattern_matches

                # パターン情報をサマリーに追加
                pattern_info: list[str] = []
                for match in pattern_analysis_result.pattern_matches:
                    pattern_info.append(f"- {match.pattern.name} (信頼度: {match.confidence:.1%})")

                if pattern_info:
                    pattern_summary = "\n\n## 検出されたパターン\n" + "\n".join(pattern_info)
                    result.summary += pattern_summary

            # 使用量を記録
            if result.tokens_used and self.cost_manager:
                await self.cost_manager.record_ai_usage(
                    provider=provider.name,
                    model=result.model,
                    input_tokens=result.tokens_used.input_tokens,
                    output_tokens=result.tokens_used.output_tokens,
                    cost=result.tokens_used.estimated_cost,
                    analysis_type="analysis",
                )

            # 結果をキャッシュ
            if self.cache_manager:
                try:
                    await self.cache_manager.cache_result(
                        prompt=options.custom_prompt or "default",
                        context=formatted_log,
                        model=result.model,
                        provider=provider.name,
                        result=result,
                    )
                except Exception as cache_error:
                    # キャッシュ書き込みエラーは警告を出すが継続する
                    logger.warning("キャッシュ書き込みに失敗しました: %s", cache_error)

            logger.info(
                "ログ分析完了 (時間: %.2f秒, トークン: %d)",
                analysis_time,
                result.tokens_used.total_tokens if result.tokens_used else 0,
            )
            return result

        except (TokenLimitError, CostLimitError, APIKeyError, RateLimitError, NetworkError, ProviderError):
            # 特定のAIエラーはそのまま再発生（テスト用）
            raise
        except Exception as e:
            logger.error("ログ分析中にエラーが発生: %s", e)
            # エラーハンドラーでエラーを処理
            error_info = {"message": str(e), "can_retry": False, "auto_retry": False}
            if self.error_handler:
                error_info = await self.error_handler.handle_error_with_retry(e, "analyze_log")

            # フォールバック処理を実行
            if error_info.get("can_retry", False) and not error_info.get("auto_retry", False):
                # 手動リトライが可能な場合はフォールバック結果を返す
                if self.fallback_handler:
                    return await self.fallback_handler.handle_analysis_failure(e, log_content, options)

            # その他の場合はエラー結果を作成
            if self.error_handler:
                return self.error_handler.create_fallback_result(str(error_info["message"]), start_time)
            # 簡易的なフォールバック結果
            return AnalysisResult(
                summary=f"エラーが発生しました: {error_info['message']}",
                status=AnalysisStatus.FAILED,
                analysis_time=(datetime.now() - start_time).total_seconds(),
            )

    async def stream_analyze(self, log_content: str, options: AnalyzeOptions) -> AsyncIterator[str]:
        """ストリーミング分析を実行

        Args:
            log_content: 分析対象のログ内容
            options: 分析オプション

        Yields:
            分析結果の部分文字列

        Raises:
            AIError: 分析に失敗した場合

        """
        if not self._initialized:
            await self.initialize()

        if not options.streaming:
            # ストリーミングが無効な場合は通常の分析を実行
            result = await self.analyze_log(log_content, options)
            yield result.summary
            return

        try:
            # プロバイダーを選択
            provider = self._select_provider(options.provider)

            # ログ内容を前処理
            formatted_log = await self._preprocess_log(log_content)

            # プロンプトを生成
            prompt = self._generate_analysis_prompt(formatted_log, options)

            # コスト推定と制限チェック
            await self._check_cost_limits(provider, prompt, formatted_log, options)

            # ストリーミング分析を実行
            try:
                async for chunk in provider.stream_analyze(prompt, formatted_log, options):
                    yield chunk
            except NotImplementedError:
                # プロバイダーがストリーミングをサポートしていない場合
                result = await provider.analyze(prompt, formatted_log, options)
                yield result.summary

        except Exception as e:
            logger.error("ストリーミング分析中にエラーが発生: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                yield f"エラー: {error_info['message']}"
            else:
                yield f"エラー: {e}"

    async def start_interactive_session(self, initial_log: str, options: AnalyzeOptions) -> InteractiveSession:
        """対話的なAIセッションを開始

        Args:
            initial_log: 初期ログ内容
            options: 分析オプション

        Returns:
            対話セッション

        Raises:
            AIError: セッション開始に失敗した場合

        """
        try:
            if not self._initialized:
                await self.initialize()

            # プロバイダーを選択
            provider = self._select_provider(options.provider)
            model = options.model or provider.config.default_model

            # セッション管理を使用してセッションを作成
            session = self.session_manager.create_session(
                provider=provider.name,
                model=model,
                initial_context=initial_log,
                options=options,
            )

            # セッションを登録
            self.active_sessions[session.session_id] = session

            # 初期ログに対して処理を実行（タイムアウトやメモリエラーをテストするため）
            if initial_log:
                if callable(getattr(self.session_manager, "process_input", None)):
                    try:
                        await self.session_manager.process_input(session.session_id, initial_log, options)
                    except (TimeoutError, MemoryError) as e:
                        # タイムアウトやメモリエラーは致命的なので AIError として再発生
                        raise AIError(f"セッション初期化中にエラーが発生しました: {e}") from e

            logger.info("対話セッション開始: %s", session.session_id)
            return session

        except AIError:
            # 既にAIErrorの場合はそのまま再発生
            raise
        except Exception as e:
            logger.error("対話セッション開始に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"対話セッションの開始に失敗しました: {error_info['message']}") from e
            raise AIError(f"対話セッションの開始に失敗しました: {e}") from e

    async def generate_fix_suggestions(
        self,
        analysis_result: AnalysisResult,
        log_content: str,
        project_context: dict[str, Any] | None = None,
    ) -> list[FixSuggestion]:
        """分析結果から修正提案を生成

        Args:
            analysis_result: AI分析結果
            log_content: 元のログ内容
            project_context: プロジェクトコンテキスト

        Returns:
            修正提案のリスト

        Raises:
            AIError: 修正提案生成に失敗した場合

        """
        if not self._initialized:
            await self.initialize()

        if not self.fix_generator:
            raise ConfigurationError("修正提案生成器が初期化されていません")

        try:
            logger.info("修正提案を生成中...")
            suggestions = self.fix_generator.generate_fix_suggestions(analysis_result, log_content, project_context)

            # 分析結果に修正提案を追加
            analysis_result.fix_suggestions = suggestions

            logger.info("修正提案を %d 個生成しました", len(suggestions))
            return suggestions

        except Exception as e:
            logger.error("修正提案の生成に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"修正提案の生成に失敗しました: {error_info['message']}") from e
            raise AIError(f"修正提案の生成に失敗しました: {e}") from e

    async def apply_fix_suggestions(
        self,
        fix_suggestions: list[FixSuggestion],
        auto_approve: bool = False,
        interactive: bool = True,
    ) -> FixSuggestionsSummary:
        """修正提案を適用

        Args:
            fix_suggestions: 修正提案のリスト
            auto_approve: 自動承認フラグ
            interactive: 対話モード

        Returns:
            適用結果の辞書

        Raises:
            AIError: 修正適用に失敗した場合

        """
        if not self._initialized:
            await self.initialize()

        if not self.fix_applier:
            raise ConfigurationError("修正適用器が初期化されていません")

        try:
            logger.info("修正提案の適用を開始...")

            # 対話モードを設定
            self.fix_applier.interactive = interactive

            # 修正を適用
            result = self.fix_applier.apply_fix_suggestions(fix_suggestions, auto_approve)

            # 使用統計を記録
            if self.cost_manager and result["applied_count"] > 0:
                await self.cost_manager.record_ai_usage(
                    provider="fix_applier",
                    model="auto_fix",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    analysis_type="fix_application",
                )

            logger.info(
                "修正適用完了 - 適用: %d, スキップ: %d, 失敗: %d",
                result["applied_count"],
                result["skipped_count"],
                result["failed_count"],
            )

            return result

        except Exception as e:
            logger.error("修正適用に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"修正適用に失敗しました: {error_info['message']}") from e
            raise AIError(f"修正適用に失敗しました: {e}") from e

    async def analyze_and_fix(
        self,
        log_content: str,
        options: AnalyzeOptions,
        apply_fixes: bool = False,
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """ログ分析と修正提案生成・適用を一括実行

        Args:
            log_content: 分析対象のログ内容
            options: 分析オプション
            apply_fixes: 修正を自動適用するかどうか
            auto_approve: 自動承認フラグ

        Returns:
            分析と修正の結果

        Raises:
            AIError: 処理に失敗した場合

        """
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("ログ分析と修正処理を開始...")

            # 1. ログを分析
            analysis_result = await self.analyze_log(log_content, options)

            # 2. 修正提案を生成
            fix_suggestions = await self.generate_fix_suggestions(analysis_result, log_content)

            result: dict[str, Any] = {
                "analysis": analysis_result,
                "fix_suggestions": fix_suggestions,
                "fix_application": None,
            }

            # 3. 修正を適用（オプション）
            if apply_fixes and fix_suggestions:
                application_result = await self.apply_fix_suggestions(
                    fix_suggestions,
                    auto_approve,
                    interactive=not auto_approve,
                )
                result["fix_application"] = application_result

            logger.info("ログ分析と修正処理が完了")
            return result

        except Exception as e:
            logger.error("ログ分析と修正処理に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"ログ分析と修正処理に失敗しました: {error_info['message']}") from e
            raise AIError(f"ログ分析と修正処理に失敗しました: {e}") from e

    def rollback_fixes(self, backup_paths: list[str]) -> RollbackResult:
        """修正をロールバック

        Args:
            backup_paths: バックアップファイルパスのリスト

        Returns:
            ロールバック結果

        Raises:
            AIError: ロールバックに失敗した場合

        """
        if not self.fix_applier:
            raise ConfigurationError("修正適用器が初期化されていません")

        try:
            logger.info("修正のロールバックを開始...")
            result = self.fix_applier.rollback_fixes(backup_paths)
            logger.info("修正のロールバックが完了")
            return result

        except Exception as e:
            logger.error("修正のロールバックに失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"修正のロールバックに失敗しました: {error_info['message']}") from e
            raise AIError(f"修正のロールバックに失敗しました: {e}") from e

    def _select_provider(self, provider_name: str | None = None) -> AIProvider:
        """使用するプロバイダーを選択

        Args:
            provider_name: 指定されたプロバイダー名

        Returns:
            選択されたプロバイダー

        Raises:
            ProviderError: プロバイダーが見つからない場合

        """
        if not self.providers:
            raise ProviderError("", "利用可能なAIプロバイダーがありません")

        # プロバイダーが指定されている場合
        if provider_name:
            if provider_name not in self.providers:
                available = ", ".join(self.providers.keys())
                raise ProviderError(
                    provider_name,
                    f"指定されたプロバイダー '{provider_name}' は利用できません",
                    f"利用可能なプロバイダー: {available}",
                )
            return self.providers[provider_name]

        # デフォルトプロバイダーを使用
        if self.ai_config and self.ai_config.default_provider in self.providers:
            return self.providers[self.ai_config.default_provider]

        # 最初に利用可能なプロバイダーを使用
        return next(iter(self.providers.values()))

    async def _preprocess_log(self, log_content: str) -> str:
        """ログ内容を前処理

        Args:
            log_content: 元のログ内容

        Returns:
            前処理されたログ内容

        """
        # 簡単な前処理（実際のAIFormatterの実装に合わせて調整）
        # AIFormatterは ExecutionResult を期待するため、ここでは簡単な処理のみ
        return log_content.strip()

    def _generate_analysis_prompt(self, log_content: str, options: AnalyzeOptions) -> str:
        """分析用プロンプトを生成

        Args:
            log_content: ログ内容
            options: 分析オプション

        Returns:
            生成されたプロンプト

        """
        if not self.prompt_manager:
            raise ConfigurationError("プロンプト管理が初期化されていません")

        # エラータイプを検出
        error_type_str = self._detect_error_type(log_content)

        # FailureTypeに変換
        try:
            error_type = FailureType(error_type_str)
        except ValueError:
            error_type = FailureType.UNKNOWN

        # 基本プロンプトを取得
        base_prompt = self.prompt_manager.get_analysis_prompt(error_type, log_content)

        # カスタムプロンプトを追加
        if options.custom_prompt:
            base_prompt += f"\n\n追加指示: {options.custom_prompt}"

        # 修正提案が必要な場合
        if options.generate_fixes:
            # 仮の分析結果を作成してfix promptを取得
            dummy_result = AnalysisResult(summary="分析中...")
            fix_prompt = self.prompt_manager.get_fix_prompt(dummy_result, log_content)
            base_prompt += f"\n\n{fix_prompt}"

        return base_prompt

    def _detect_error_type(self, log_content: str) -> str:
        """ログ内容からエラータイプを検出

        Args:
            log_content: ログ内容

        Returns:
            検出されたエラータイプ

        """
        # 簡単なパターンマッチングでエラータイプを検出
        # より具体的なパターンを先にチェック
        log_lower = log_content.lower()

        if "syntax" in log_lower or "syntaxerror" in log_lower:
            return "syntax_error"
        if "import" in log_lower and "error" in log_lower:
            return "import_error"
        if "timeout" in log_lower:
            return "timeout_error"
        if "build" in log_lower and ("fail" in log_lower or "error" in log_lower):
            return "build_failure"
        if "test" in log_lower and ("fail" in log_lower or "error" in log_lower):
            return "test_failure"
        return "general_error"

    async def _check_cost_limits(
        self,
        provider: AIProvider,
        prompt: str,
        context: str,
        options: AnalyzeOptions,
    ) -> None:
        """コスト制限をチェック

        Args:
            provider: 使用するプロバイダー
            prompt: プロンプト
            context: コンテキスト
            options: 分析オプション

        Raises:
            AIError: コスト制限を超過している場合

        """
        if not self.cost_manager:
            return

        # 入力トークン数を推定
        input_text = f"{prompt}\n\n{context}"
        input_tokens = provider.count_tokens(input_text, options.model)

        # 出力トークン数を推定（入力の50%と仮定）
        estimated_output_tokens = int(input_tokens * 0.5)

        # コストを推定
        estimated_cost = provider.estimate_cost(input_tokens, estimated_output_tokens, options.model)

        # 制限をチェック
        limit_check = self.cost_manager.check_usage_limits(provider.name)

        if limit_check.get("over_limit", False):
            raise AIError(f"コスト制限を超過しています (推定: ${estimated_cost:.4f})")

        if limit_check.get("near_limit", False):
            logger.warning("コスト制限に近づいています (使用率: %.1f%%)", limit_check.get("usage_percentage", 0))

    async def _execute_analysis(
        self,
        provider: AIProvider,
        prompt: str,
        context: str,
        options: AnalyzeOptions,
    ) -> AnalysisResult:
        """AI分析を実行

        Args:
            provider: 使用するプロバイダー
            prompt: プロンプト
            context: コンテキスト
            options: 分析オプション

        Returns:
            分析結果

        """
        try:
            result = await provider.analyze(prompt, context, options)
            result.status = AnalysisStatus.COMPLETED
            return result
        except AIError:
            # AI固有のエラーはそのまま再発生
            raise
        except Exception as e:
            logger.error("AI分析の実行に失敗: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"AI分析の実行に失敗しました: {error_info['message']}") from e
            raise AIError(f"AI分析の実行に失敗しました: {e}") from e

    async def get_usage_stats(self) -> dict[str, Any]:
        """使用統計を取得

        Returns:
            使用統計情報

        """
        if not self.cost_manager:
            return {}

        stats_dict = self.cost_manager.get_usage_summary()

        summary = stats_dict.get("summary", {})
        return {
            "total_requests": summary.get("total_requests", 0),
            "total_cost": summary.get("total_cost", 0.0),
            "success_rate": summary.get("success_rate", 0.0),
            "provider_breakdown": stats_dict.get("top_providers", {}),
            "model_breakdown": stats_dict.get("top_models", {}),
            "active_sessions": len(self.active_sessions),
            "cache_enabled": self.ai_config.cache_enabled if self.ai_config else False,
            "available_providers": list(self.providers.keys()),
        }

    async def retry_failed_operation(self, operation_id: str) -> AnalysisResult | None:
        """失敗した操作をリトライ

        Args:
            operation_id: 操作ID

        Returns:
            リトライ結果、失敗時はNone

        """
        if not self._initialized:
            await self.initialize()

        try:
            # 部分的な結果からリトライ情報を取得
            if not self.fallback_handler:
                return None
            retry_info = await self.fallback_handler.retry_from_partial_result(operation_id)
            if not retry_info:
                logger.warning("操作ID %s のリトライ情報が見つかりません", operation_id)
                return None

            # リトライ用のオプションを再構築
            options_dict = retry_info.get("options", {})
            options = AnalyzeOptions(
                provider=options_dict.get("provider"),
                model=options_dict.get("model"),
                custom_prompt=options_dict.get("custom_prompt"),
                generate_fixes=options_dict.get("generate_fixes", False),
                streaming=options_dict.get("streaming", False),
                use_cache=options_dict.get("use_cache", True),
            )

            # 代替プロバイダーがある場合は使用
            alternative_providers = retry_info.get("alternative_providers", [])
            if alternative_providers and retry_info.get("failed_provider"):
                options.provider = alternative_providers[0]
                logger.info("代替プロバイダー %s でリトライします", options.provider)

            # ログ分析をリトライ
            log_content = retry_info.get("log_content", "")
            result = await self.analyze_log(log_content, options)

            logger.info("操作 %s のリトライが成功しました", operation_id)
            return result

        except Exception as e:
            logger.error("操作 %s のリトライに失敗: %s", operation_id, e)
            return None

    async def get_fallback_suggestions(self, error: Exception) -> list[str]:
        """フォールバック時の提案を取得

        Args:
            error: 発生したエラー

        Returns:
            提案のリスト

        """
        suggestion_lines: list[str] = []

        if isinstance(error, RateLimitError):
            suggestion_lines.extend(
                [
                    f"{error.retry_after or 60}秒後に再試行してください",
                    "より低いレート制限のモデルを使用してください",
                    "プロバイダーのプランをアップグレードしてください",
                ],
            )
        elif isinstance(error, ProviderError):
            current_provider_name = error.provider
            alternatives: list[str] = []
            for name in self.providers.keys():  # Ensure type-safe iteration
                if name != current_provider_name:
                    alternatives.append(name)

            if alternatives:
                suggestion_lines.append(f"代替プロバイダーを試してください: {', '.join(alternatives)}")
            suggestion_lines.extend(
                [
                    "APIキーと設定を確認してください",
                    "プロバイダーのサービス状況を確認してください",
                ],
            )
        else:
            suggestion_lines.extend(
                [
                    "コマンドを再実行してください",
                    "設定を確認してください",
                    "--verbose オプションで詳細ログを確認してください",
                ],
            )

        return suggestion_lines

    async def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        logger.info("AI統合システムをクリーンアップ中...")

        # プロバイダーをクリーンアップ
        for provider in self.providers.values():
            try:
                # cleanupメソッドが存在し、コルーチン関数である場合のみ呼び出す
                if hasattr(provider, "cleanup"):
                    await provider.cleanup()
            except Exception as e:
                logger.warning("プロバイダーのクリーンアップに失敗: %s", e)

        # アクティブセッションをクリア
        self.active_sessions.clear()

        # 古いフォールバック結果をクリーンアップ
        try:
            if self.fallback_handler:
                self.fallback_handler.cleanup_old_partial_results()
        except Exception as e:
            logger.warning("フォールバック結果のクリーンアップに失敗: %s", e)

        # パターン認識エンジンをクリーンアップ
        if hasattr(self, "pattern_engine") and self.pattern_engine:
            try:
                await self.pattern_engine.cleanup()
            except Exception as e:
                logger.warning("パターン認識エンジンのクリーンアップに失敗: %s", e)

        logger.info("AI統合システムのクリーンアップ完了")

    async def process_interactive_input(self, session_id: str, user_input: str) -> AsyncIterator[str]:
        """対話セッションでのユーザー入力を処理

        Args:
            session_id: セッションID
            user_input: ユーザー入力

        Yields:
            AI応答のチャンク

        Raises:
            AIError: セッションが見つからない場合

        """
        if session_id not in self.active_sessions:
            raise AIError(f"セッション {session_id} が見つかりません")

        session = self.active_sessions[session_id]

        try:
            # セッション管理を使用して対話処理
            if hasattr(self, "session_manager"):
                # コマンド処理の確認
                if self.session_manager.command_processor.is_command(user_input):
                    result = await self.session_manager.command_processor.process_command(session_id, user_input)
                    if result.get("should_display"):
                        yield result["output"]
                    if result.get("should_exit"):
                        session.is_active = False
                    return

                # 通常のAI応答処理
                prompt = self.session_manager.generate_interactive_prompt(session_id, user_input)
                provider = self._select_provider(session.provider)

                async for chunk in provider.stream_analyze(prompt, session.model, options=AnalyzeOptions()):
                    yield chunk

        except Exception as e:
            logger.error("対話入力処理中にエラー: %s", e)
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                yield f"エラーが発生しました: {error_info['message']}"
            else:
                yield f"エラーが発生しました: {e}"

    async def close_interactive_session(self, session_id: str) -> bool:
        """対話セッションを終了

        Args:
            session_id: セッションID

        Returns:
            成功した場合True

        """
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        session.is_active = False

        # セッション管理を使用してクリーンアップ
        if hasattr(self, "session_manager"):
            self.session_manager.close_session(session_id)

        del self.active_sessions[session_id]
        logger.info("対話セッション %s を終了しました", session_id)
        return True

    async def apply_fix(self, fix_suggestion: FixSuggestion) -> None:
        """修正提案を適用

        Args:
            fix_suggestion: 修正提案オブジェクト

        Raises:
            AIError: 修正適用に失敗した場合

        """
        if not self.fix_applier:
            raise AIError("修正適用器が初期化されていません")

        try:
            self.fix_applier.apply_fix([fix_suggestion])
        except Exception as e:
            if self.error_handler:
                error_info = self.error_handler.process_error(e)
                raise AIError(f"修正の適用に失敗しました: {error_info['message']}") from e
            raise AIError(f"修正の適用に失敗しました: {e}") from e

    def __str__(self) -> str:
        """文字列表現"""
        provider_count = len(self.providers)
        session_count = len(self.active_sessions)
        return f"AIIntegration(providers={provider_count}, sessions={session_count})"

    def __repr__(self) -> str:
        """詳細な文字列表現"""
        return (
            f"AIIntegration("
            f"initialized={self._initialized}, "
            f"providers={list(self.providers.keys())}, "
            f"active_sessions={len(self.active_sessions)}, "
            f"cache_enabled={self.ai_config.cache_enabled if self.ai_config else False}"
            f")"
        )
