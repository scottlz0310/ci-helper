"""
AI統合フォールバック機能

AI分析が失敗した場合の代替手段を提供し、部分的な結果の保存、
自動リトライ、従来のログ表示などのフォールバック機能を実装します。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from ..core.models import ExecutionResult
from ..utils.config import Config
from .exceptions import NetworkError, ProviderError, RateLimitError
from .models import AnalysisResult, AnalysisStatus, AnalyzeOptions

logger = logging.getLogger(__name__)


class FallbackHandler:
    """AI統合フォールバック機能

    AI分析が失敗した場合の代替手段を提供します。
    """

    def __init__(self, config: Config):
        """フォールバック機能を初期化

        Args:
            config: メイン設定オブジェクト
        """
        self.config = config
        self.fallback_dir = config.get_path("cache_dir") / "ai" / "fallback"
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        self.retry_attempts: dict[str, int] = {}
        self.partial_results: dict[str, dict[str, Any]] = {}

    async def handle_analysis_failure(
        self, error: Exception, log_content: str, options: AnalyzeOptions, operation_id: str | None = None
    ) -> AnalysisResult:
        """AI分析失敗時のフォールバック処理

        Args:
            error: 発生したエラー
            log_content: 分析対象のログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            フォールバック分析結果
        """
        logger.info("AI分析失敗のフォールバック処理を開始: %s", type(error).__name__)

        # 操作IDを生成
        if not operation_id:
            operation_id = f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # エラータイプに応じた処理
        if isinstance(error, RateLimitError):
            return await self._handle_rate_limit_fallback(error, log_content, options, operation_id)
        elif isinstance(error, NetworkError):
            return await self._handle_network_fallback(error, log_content, options, operation_id)
        elif isinstance(error, ProviderError):
            return await self._handle_provider_fallback(error, log_content, options, operation_id)
        else:
            return await self._handle_generic_fallback(error, log_content, options, operation_id)

    async def _handle_rate_limit_fallback(
        self, error: RateLimitError, log_content: str, options: AnalyzeOptions, operation_id: str
    ) -> AnalysisResult:
        """レート制限エラーのフォールバック処理

        Args:
            error: レート制限エラー
            log_content: ログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            フォールバック結果
        """
        logger.info("レート制限フォールバック処理: %s", error.provider)

        # 部分的な結果を保存
        await self._save_partial_result(
            operation_id,
            {
                "error_type": "rate_limit",
                "provider": error.provider,
                "log_content": log_content,
                "options": options.__dict__,
                "retry_after": error.retry_after,
                "reset_time": error.reset_time.isoformat() if error.reset_time else None,
            },
        )

        # 従来のログ表示を実行
        traditional_analysis = await self._perform_traditional_analysis(log_content)

        # フォールバック結果を作成
        return AnalysisResult(
            summary=f"レート制限のため従来の分析を実行しました。{error.retry_after or 60}秒後にAI分析を再試行できます。",
            root_causes=traditional_analysis.get("root_causes", []),
            fix_suggestions=[],
            related_errors=traditional_analysis.get("related_errors", []),
            confidence_score=0.3,  # 従来分析の信頼度は低め
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FALLBACK,
            timestamp=datetime.now(),
            provider="fallback",
            model="traditional",
            cache_hit=False,
            fallback_reason=f"レート制限 ({error.provider})",
            retry_available=True,
            retry_after=error.retry_after,
        )

    async def _handle_network_fallback(
        self, error: NetworkError, log_content: str, options: AnalyzeOptions, operation_id: str
    ) -> AnalysisResult:
        """ネットワークエラーのフォールバック処理

        Args:
            error: ネットワークエラー
            log_content: ログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            フォールバック結果
        """
        logger.info("ネットワークエラーフォールバック処理 (試行回数: %d)", error.retry_count)

        # 自動リトライの実行
        if error.retry_count < 3:
            logger.info("ネットワークエラーの自動リトライを実行します...")
            retry_result = await self._attempt_auto_retry(error, log_content, options, operation_id)
            if retry_result:
                return retry_result

        # 部分的な結果を保存
        await self._save_partial_result(
            operation_id,
            {
                "error_type": "network",
                "log_content": log_content,
                "options": options.__dict__,
                "retry_count": error.retry_count,
            },
        )

        # 従来のログ表示を実行
        traditional_analysis = await self._perform_traditional_analysis(log_content)

        return AnalysisResult(
            summary="ネットワークエラーのため従来の分析を実行しました。接続を確認後、再試行してください。",
            root_causes=traditional_analysis.get("root_causes", []),
            fix_suggestions=[],
            related_errors=traditional_analysis.get("related_errors", []),
            confidence_score=0.3,
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FALLBACK,
            timestamp=datetime.now(),
            provider="fallback",
            model="traditional",
            cache_hit=False,
            fallback_reason="ネットワークエラー",
            retry_available=True,
            retry_after=30,
        )

    async def _handle_provider_fallback(
        self, error: ProviderError, log_content: str, options: AnalyzeOptions, operation_id: str
    ) -> AnalysisResult:
        """プロバイダーエラーのフォールバック処理

        Args:
            error: プロバイダーエラー
            log_content: ログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            フォールバック結果
        """
        logger.info("プロバイダーエラーフォールバック処理: %s", error.provider)

        # 代替プロバイダーの提案
        alternative_providers = self._suggest_alternative_providers(error.provider)

        # 部分的な結果を保存
        await self._save_partial_result(
            operation_id,
            {
                "error_type": "provider",
                "failed_provider": error.provider,
                "log_content": log_content,
                "options": options.__dict__,
                "alternative_providers": alternative_providers,
            },
        )

        # 従来のログ表示を実行
        traditional_analysis = await self._perform_traditional_analysis(log_content)

        suggestion_text = "従来の分析を実行しました。"
        if alternative_providers:
            suggestion_text += f" 代替プロバイダー: {', '.join(alternative_providers)}"

        return AnalysisResult(
            summary=f"{error.provider}プロバイダーでエラーが発生しました。{suggestion_text}",
            root_causes=traditional_analysis.get("root_causes", []),
            fix_suggestions=[],
            related_errors=traditional_analysis.get("related_errors", []),
            confidence_score=0.3,
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FALLBACK,
            timestamp=datetime.now(),
            provider="fallback",
            model="traditional",
            cache_hit=False,
            fallback_reason=f"プロバイダーエラー ({error.provider})",
            retry_available=True,
            alternative_providers=alternative_providers,
        )

    async def _handle_generic_fallback(
        self, error: Exception, log_content: str, options: AnalyzeOptions, operation_id: str
    ) -> AnalysisResult:
        """汎用エラーのフォールバック処理

        Args:
            error: 発生したエラー
            log_content: ログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            フォールバック結果
        """
        logger.info("汎用エラーフォールバック処理: %s", type(error).__name__)

        # 部分的な結果を保存
        await self._save_partial_result(
            operation_id,
            {
                "error_type": "generic",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "log_content": log_content,
                "options": options.__dict__,
            },
        )

        # 従来のログ表示を実行
        traditional_analysis = await self._perform_traditional_analysis(log_content)

        return AnalysisResult(
            summary=f"AI分析中にエラーが発生しました ({type(error).__name__})。従来の分析を実行しました。",
            root_causes=traditional_analysis.get("root_causes", []),
            fix_suggestions=[],
            related_errors=traditional_analysis.get("related_errors", []),
            confidence_score=0.3,
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FALLBACK,
            timestamp=datetime.now(),
            provider="fallback",
            model="traditional",
            cache_hit=False,
            fallback_reason=f"予期しないエラー ({type(error).__name__})",
            retry_available=True,
        )

    async def _attempt_auto_retry(
        self, error: NetworkError, log_content: str, options: AnalyzeOptions, operation_id: str
    ) -> AnalysisResult | None:
        """自動リトライを実行

        Args:
            error: ネットワークエラー
            log_content: ログ内容
            options: 分析オプション
            operation_id: 操作ID

        Returns:
            リトライ成功時の結果、失敗時はNone
        """
        # リトライ回数を初期化
        if operation_id not in self.retry_attempts:
            self.retry_attempts[operation_id] = 0

        # 最大リトライ回数をチェック
        if self.retry_attempts[operation_id] >= 3:
            logger.info("最大リトライ回数に達しました (3回)")
            return None

        self.retry_attempts[operation_id] += 1

        retry_delay = min(2**error.retry_count, 30)  # 指数バックオフ、最大30秒

        logger.info("自動リトライを %d秒後に実行します (試行 %d/3)", retry_delay, self.retry_attempts[operation_id])
        await asyncio.sleep(retry_delay)

        try:
            # ここで実際のAI分析を再試行する必要があるが、
            # この関数は統合クラスの外部にあるため、
            # 実際の実装では統合クラスのメソッドを呼び出す必要がある
            # 今回はNoneを返してフォールバック処理を続行
            logger.info("自動リトライは統合クラスで実装される必要があります")
            return None

        except Exception as retry_error:
            logger.warning("自動リトライに失敗: %s", retry_error)
            return None

    async def _perform_traditional_analysis(self, log_content: str) -> dict[str, Any]:
        """従来のログ分析を実行

        Args:
            log_content: ログ内容

        Returns:
            従来の分析結果
        """
        logger.info("従来のログ分析を実行中...")

        try:
            # 既存のログ抽出機能を使用
            from ..core.log_extractor import LogExtractor
            from ..core.models import Failure, FailureType, JobResult, WorkflowResult

            # 簡易的な失敗を作成
            failure = Failure(
                type=FailureType.ERROR,
                message="フォールバック分析",
                file_path=None,
                line_number=None,
                context_before=[],
                context_after=[],
                stack_trace=log_content[:1000] if log_content else None,  # 最初の1000文字のみ
            )

            # 簡易的なジョブ結果を作成
            job_result = JobResult(
                name="fallback_job",
                success=False,
                duration=0.0,
                failures=[failure],
                steps=[],
            )

            # 簡易的なワークフロー結果を作成
            workflow_result = WorkflowResult(
                name="fallback_workflow",
                success=False,
                jobs=[job_result],
                duration=0.0,
            )

            execution_result = ExecutionResult(
                success=False,
                workflows=[workflow_result],
                total_duration=0.0,
                log_path=None,
                timestamp=datetime.now(),
            )

            # 失敗抽出を実行
            extractor = LogExtractor(context_lines=3)
            failures = extractor.extract_failures(log_content)

            # 根本原因を特定
            root_causes = []
            related_errors = []

            for failure in failures:
                root_causes.append(
                    {
                        "category": failure.type.value,
                        "description": failure.message,
                        "file_path": failure.file_path,
                        "line_number": failure.line_number,
                        "severity": "high" if failure.type in [FailureType.ERROR, FailureType.ASSERTION] else "medium",
                    }
                )

                # Add context from before and after
                if failure.context_before:
                    related_errors.extend(failure.context_before)
                if failure.context_after:
                    related_errors.extend(failure.context_after)

            return {
                "summary": f"従来のログ分析を実行しました。{len(failures)}個の失敗を検出しました。",
                "errors": list(set(related_errors)),  # 重複を除去
                "patterns": [cause["category"] for cause in root_causes],
                "suggestions": [
                    f"{cause['category']}エラーを確認してください: {cause['description']}" for cause in root_causes
                ],
                "root_causes": root_causes,
                "related_errors": list(set(related_errors)),
                "failure_count": len(failures),
                "analysis_method": "traditional",
            }

        except Exception as e:
            logger.error("従来のログ分析に失敗: %s", e)
            return {
                "summary": "ログ分析中にエラーが発生しました。",
                "errors": [],
                "patterns": ["unknown"],
                "suggestions": ["ログ内容を確認してください"],
                "root_causes": [
                    {
                        "category": "unknown",
                        "description": "ログ分析中にエラーが発生しました",
                        "file_path": None,
                        "line_number": None,
                        "severity": "medium",
                    }
                ],
                "related_errors": [],
                "failure_count": 0,
                "analysis_method": "error",
            }

    async def _save_partial_result(self, operation_id: str, data: dict[str, Any]) -> None:
        """部分的な結果を保存

        Args:
            operation_id: 操作ID
            data: 保存するデータ
        """
        try:
            result_file = self.fallback_dir / f"{operation_id}.json"

            # タイムスタンプを追加
            data["timestamp"] = datetime.now().isoformat()
            data["operation_id"] = operation_id

            # JSONファイルに保存
            with result_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # メモリにも保存
            self.partial_results[operation_id] = data

            logger.info("部分的な結果を保存しました: %s", result_file)

        except Exception as e:
            logger.error("部分的な結果の保存に失敗: %s", e)

    def _suggest_alternative_providers(self, failed_provider: str) -> list[str]:
        """代替プロバイダーを提案

        Args:
            failed_provider: 失敗したプロバイダー名

        Returns:
            代替プロバイダーのリスト
        """
        all_providers = ["openai", "anthropic", "local"]
        alternatives = [p for p in all_providers if p != failed_provider]

        # 利用可能性に基づいて並び替え（実際の実装では設定を確認）
        priority_order = {
            "openai": 1,
            "anthropic": 2,
            "local": 3,
        }

        alternatives.sort(key=lambda x: priority_order.get(x, 99))
        return alternatives

    async def load_partial_result(self, operation_id: str) -> dict[str, Any] | None:
        """部分的な結果を読み込み

        Args:
            operation_id: 操作ID

        Returns:
            保存された部分的な結果、存在しない場合はNone
        """
        # メモリから確認
        if operation_id in self.partial_results:
            return self.partial_results[operation_id]

        # ファイルから読み込み
        try:
            result_file = self.fallback_dir / f"{operation_id}.json"
            if result_file.exists():
                with result_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.partial_results[operation_id] = data
                    return data
        except Exception as e:
            logger.error("部分的な結果の読み込みに失敗: %s", e)

        return None

    async def retry_from_partial_result(self, operation_id: str) -> dict[str, Any] | None:
        """部分的な結果からリトライ情報を取得

        Args:
            operation_id: 操作ID

        Returns:
            リトライ情報、存在しない場合はNone
        """
        partial_result = await self.load_partial_result(operation_id)
        if not partial_result:
            return None

        return {
            "log_content": partial_result.get("log_content"),
            "options": partial_result.get("options"),
            "error_type": partial_result.get("error_type"),
            "failed_provider": partial_result.get("failed_provider"),
            "alternative_providers": partial_result.get("alternative_providers", []),
            "retry_after": partial_result.get("retry_after"),
            "timestamp": partial_result.get("timestamp"),
            "retry_info": partial_result.get("retry_info", {}),
        }

    def cleanup_old_partial_results(self, max_age_days: int = 7) -> int:
        """古い部分的な結果をクリーンアップ

        Args:
            max_age_days: 保持する最大日数

        Returns:
            削除されたファイル数
        """
        try:
            deleted_count = 0
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)

            for result_file in self.fallback_dir.glob("*.json"):
                if result_file.stat().st_mtime < cutoff_time:
                    result_file.unlink()
                    deleted_count += 1

                    # メモリからも削除
                    operation_id = result_file.stem
                    if operation_id in self.partial_results:
                        del self.partial_results[operation_id]

            logger.info("古い部分的な結果を %d個削除しました", deleted_count)
            return deleted_count

        except Exception as e:
            logger.error("部分的な結果のクリーンアップに失敗: %s", e)
            return 0

    def get_fallback_statistics(self) -> dict[str, Any]:
        """フォールバック統計を取得

        Returns:
            フォールバック統計情報
        """
        try:
            total_files = len(list(self.fallback_dir.glob("*.json")))
            memory_results = len(self.partial_results)

            # リトライ統計の計算
            total_operations = len(self.retry_attempts)
            total_retries = sum(self.retry_attempts.values())
            average_retries = total_retries / total_operations if total_operations > 0 else 0.0

            # エラータイプ別の統計
            error_types = {}
            for data in self.partial_results.values():
                error_type = data.get("error_type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1

            return {
                "total_operations": total_operations,
                "total_retries": total_retries,
                "average_retries": average_retries,
                "partial_results_count": memory_results,
                "total_fallback_results": total_files,
                "memory_cached_results": memory_results,
                "error_type_breakdown": error_types,
                "fallback_directory": str(self.fallback_dir),
            }

        except Exception as e:
            logger.error("フォールバック統計の取得に失敗: %s", e)
            return {}

    def __str__(self) -> str:
        """文字列表現"""
        partial_count = len(self.partial_results)
        return f"FallbackHandler(partial_results={partial_count})"
