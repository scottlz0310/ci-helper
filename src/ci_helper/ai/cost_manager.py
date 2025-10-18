"""
コスト管理

AI使用コストの高レベル管理機能を提供します。
コスト表示、警告、制限チェック、推奨事項などの機能を含みます。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .cost_tracker import CostTracker
from .exceptions import ConfigurationError
from .models import LimitStatus


class CostManager:
    """コスト管理クラス"""

    def __init__(
        self,
        storage_path: Path,
        cost_limits: dict[str, float] | None = None,
        warning_threshold: float = 0.8,
    ):
        """コストマネージャーを初期化

        Args:
            storage_path: 使用データの保存パス
            cost_limits: コスト制限の辞書
            warning_threshold: 警告しきい値（0.0-1.0）
        """
        self.storage_path = storage_path
        self.cost_limits = cost_limits or {}
        self.warning_threshold = warning_threshold

        self.tracker = CostTracker(storage_path, cost_limits)

    async def record_ai_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        analysis_type: str = "analysis",
        success: bool = True,
    ) -> None:
        """AI使用量を記録

        Args:
            provider: プロバイダー名
            model: モデル名
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            cost: コスト（USD）
            analysis_type: 分析タイプ
            success: 成功したかどうか
        """
        await self.tracker.record_usage_async(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            analysis_type=analysis_type,
            success=success,
        )

    def estimate_request_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int | None = None,
    ) -> dict[str, Any]:
        """リクエストコストを推定し、詳細情報を返す

        Args:
            provider: プロバイダー名
            model: モデル名
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数（推定）

        Returns:
            コスト推定の詳細情報
        """
        estimated_cost = self.tracker.estimate_request_cost(provider, model, input_tokens, output_tokens)

        # 制限チェック
        limit_status = self.tracker.check_limits(provider)

        # 推定後の使用量
        estimated_usage_after = limit_status.current_usage + estimated_cost

        # 警告レベルを判定
        warning_level = self._get_warning_level(estimated_usage_after, limit_status.limit)

        return {
            "estimated_cost": estimated_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens or int(input_tokens * 0.5),
            "provider": provider,
            "model": model,
            "current_usage": limit_status.current_usage,
            "limit": limit_status.limit,
            "usage_after_request": estimated_usage_after,
            "remaining_budget": limit_status.remaining - estimated_cost,
            "warning_level": warning_level,
            "can_proceed": estimated_usage_after <= limit_status.limit,
        }

    def check_usage_limits(self, provider: str) -> dict[str, Any]:
        """使用制限をチェックし、詳細情報を返す

        Args:
            provider: プロバイダー名

        Returns:
            制限チェックの詳細情報
        """
        limit_status = self.tracker.check_limits(provider)
        warning_level = self._get_warning_level(limit_status.current_usage, limit_status.limit)

        return {
            "provider": provider,
            "current_usage": limit_status.current_usage,
            "limit": limit_status.limit,
            "remaining": limit_status.remaining,
            "usage_percentage": limit_status.usage_percentage,
            "warning_level": warning_level,
            "is_near_limit": limit_status.is_near_limit,
            "is_over_limit": limit_status.is_over_limit,
            "reset_time": limit_status.reset_time.isoformat() if limit_status.reset_time else None,
            "days_until_reset": self._days_until_reset(limit_status.reset_time) if limit_status.reset_time else None,
        }

    def get_usage_summary(self, days: int = 30) -> dict[str, Any]:
        """使用サマリーを取得

        Args:
            days: 対象日数

        Returns:
            使用サマリー
        """
        stats = self.tracker.get_usage_stats(days)
        cost_breakdown = self.tracker.get_cost_breakdown(days)
        trends = self.tracker.get_usage_trends(days)

        return {
            "period_days": days,
            "summary": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "success_rate": stats.success_rate,
                "total_cost": stats.total_cost,
                "total_tokens": stats.total_tokens,
                "average_cost_per_request": stats.average_cost_per_request,
                "average_tokens_per_request": stats.average_tokens_per_request,
            },
            "breakdown": cost_breakdown,
            "trends": trends,
            "top_providers": self._get_top_items(stats.provider_breakdown),
            "top_models": self._get_top_items(stats.model_breakdown),
        }

    def get_monthly_report(self, year: int | None = None, month: int | None = None) -> dict[str, Any]:
        """月間レポートを取得

        Args:
            year: 年（指定されない場合は現在年）
            month: 月（指定されない場合は現在月）

        Returns:
            月間レポート
        """
        if year is None or month is None:
            now = datetime.now()
            year = year or now.year
            month = month or now.month

        stats = self.tracker.get_monthly_usage(year, month)

        # 月間制限との比較
        monthly_limits = {}
        for provider in stats.provider_breakdown.keys():
            limit_status = self.tracker.check_limits(provider)
            monthly_limits[provider] = {
                "limit": limit_status.limit,
                "usage": limit_status.current_usage,
                "percentage": limit_status.usage_percentage,
            }

        return {
            "year": year,
            "month": month,
            "stats": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "success_rate": stats.success_rate,
                "total_cost": stats.total_cost,
                "total_tokens": stats.total_tokens,
            },
            "provider_breakdown": stats.provider_breakdown,
            "model_breakdown": stats.model_breakdown,
            "daily_usage": stats.daily_usage,
            "limits": monthly_limits,
        }

    def get_cost_warnings(self) -> list[dict[str, Any]]:
        """コスト警告を取得

        Returns:
            警告のリスト
        """
        warnings = []

        # 各プロバイダーの制限をチェック
        providers = set()
        for record in self.tracker.usage_data["records"]:
            providers.add(record["provider"])

        for provider in providers:
            limit_status = self.tracker.check_limits(provider)
            warning_level = self._get_warning_level(limit_status.current_usage, limit_status.limit)

            if warning_level in ["warning", "critical"]:
                warnings.append(
                    {
                        "provider": provider,
                        "level": warning_level,
                        "current_usage": limit_status.current_usage,
                        "limit": limit_status.limit,
                        "usage_percentage": limit_status.usage_percentage,
                        "message": self._get_warning_message(provider, warning_level, limit_status),
                    }
                )

        return warnings

    def get_cost_recommendations(self) -> list[str]:
        """コスト最適化の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        recommendations = []

        # 最近30日の使用統計を取得
        stats = self.tracker.get_usage_stats(30)
        cost_breakdown = self.tracker.get_cost_breakdown(30)

        # 成功率が低い場合
        if stats.success_rate < 0.9:
            recommendations.append(
                f"成功率が{stats.success_rate:.1%}と低いです。エラーの原因を調査してコストの無駄を削減できます"
            )

        # 高コストなモデルの使用
        model_costs = cost_breakdown.get("model_breakdown", {})
        if model_costs:
            most_expensive_model = max(model_costs.keys(), key=lambda m: model_costs[m])
            if model_costs[most_expensive_model] > stats.total_cost * 0.5:
                recommendations.append(
                    f"モデル '{most_expensive_model}' が総コストの50%以上を占めています。"
                    "より安価なモデルの使用を検討してください"
                )

        # 使用量の急増
        trends = self.tracker.get_usage_trends(30)
        if trends.get("cost_trend") == "増加" and trends.get("cost_change_per_day", 0) > 1.0:
            recommendations.append("使用コストが急増しています。使用パターンを見直すことをお勧めします")

        # キャッシュの活用
        if stats.total_requests > 50:
            recommendations.append("キャッシュ機能を有効にすることで、同じ分析の再実行コストを削減できます")

        # 一般的な推奨事項
        if not recommendations:
            recommendations.extend(
                [
                    "現在のコスト使用は適切な範囲内です",
                    "定期的な使用量の確認でコストを管理できます",
                    "プロンプトの最適化でトークン使用量を削減できる可能性があります",
                ]
            )

        return recommendations

    def _get_warning_level(self, current_usage: float, limit: float) -> str:
        """警告レベルを取得"""
        if limit == float("inf"):
            return "none"

        usage_ratio = current_usage / limit

        if usage_ratio >= 1.0:
            return "critical"
        elif usage_ratio >= self.warning_threshold:
            return "warning"
        elif usage_ratio >= 0.5:
            return "info"
        else:
            return "none"

    def _get_warning_message(self, provider: str, level: str, limit_status: LimitStatus) -> str:
        """警告メッセージを生成"""
        if level == "critical":
            return f"{provider}の月間制限（${limit_status.limit:.2f}）を超過しています"
        elif level == "warning":
            return f"{provider}の月間制限の{limit_status.usage_percentage:.0f}%を使用しています"
        else:
            return f"{provider}の使用量が増加しています"

    def _days_until_reset(self, reset_time: datetime) -> int:
        """リセットまでの日数を計算"""
        now = datetime.now()
        delta = reset_time - now
        return max(0, delta.days)

    def _get_top_items(self, breakdown: dict[str, int], limit: int = 5) -> list[tuple[str, int]]:
        """上位アイテムを取得"""
        sorted_items = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:limit]

    async def export_cost_report(self, export_path: Path, export_format: str = "json") -> None:
        """コストレポートをエクスポート

        Args:
            export_path: エクスポート先パス
            format: エクスポート形式
        """
        # 包括的なレポートを作成
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary_30_days": self.get_usage_summary(30),
            "monthly_report": self.get_monthly_report(),
            "warnings": self.get_cost_warnings(),
            "recommendations": self.get_cost_recommendations(),
            "limits": {provider: self.check_usage_limits(provider) for provider in self.cost_limits.keys()},
        }

        if export_format.lower() == "json":
            import json

            import aiofiles

            async with aiofiles.open(export_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            raise ConfigurationError(f"サポートされていないエクスポート形式: {export_format}")

    def set_cost_limit(self, provider: str, limit: float) -> None:
        """コスト制限を設定

        Args:
            provider: プロバイダー名
            limit: 制限値（USD）
        """
        limit_key = f"{provider}_monthly_usd"
        self.cost_limits[limit_key] = limit
        self.tracker.cost_limits = self.cost_limits

    def get_cost_limits(self) -> dict[str, float]:
        """設定されているコスト制限を取得

        Returns:
            コスト制限の辞書
        """
        return self.cost_limits.copy()

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        analysis_type: str = "analysis",
        success: bool = True,
    ) -> None:
        """使用量を記録（同期版）

        Args:
            provider: プロバイダー名
            model: モデル名
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            cost: コスト（USD）
            analysis_type: 分析タイプ
            success: 成功したかどうか
        """
        # 同期的に記録
        self.tracker.record_usage(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            analysis_type=analysis_type,
            success=success,
        )

    def check_limits(self, provider: str) -> LimitStatus:
        """使用制限をチェック

        Args:
            provider: プロバイダー名

        Returns:
            制限ステータス
        """
        return self.tracker.check_limits(provider)

    def get_cost_optimization_suggestions(self) -> list[str]:
        """コスト最適化の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        return self.get_cost_recommendations()

    def validate_request_cost(self, estimate: CostEstimate) -> None:
        """リクエストコストを検証し、制限を超過している場合は例外を発生

        Args:
            estimate: コスト推定結果

        Raises:
            CostLimitError: コスト制限を超過している場合
        """
        from .exceptions import CostLimitError

        provider = estimate.provider
        if provider in self.cost_limits:
            limit = self.cost_limits[provider]
            from datetime import datetime

            now = datetime.now()
            current_usage = self.tracker.get_monthly_usage(now.year, now.month).total_cost

            if current_usage + estimate.estimated_cost > limit:
                raise CostLimitError(
                    current_cost=current_usage + estimate.estimated_cost, limit=limit, provider=estimate.provider
                )

    def _calculate_warning_level(self, current_usage: float, limit: float) -> str:
        """警告レベルを計算

        Args:
            current_usage: 現在の使用量
            limit: 制限値

        Returns:
            警告レベル
        """
        from .models import WarningLevel

        if limit == float("inf") or limit <= 0:
            return WarningLevel.NONE

        usage_ratio = current_usage / limit

        if usage_ratio >= 1.0:
            return WarningLevel.CRITICAL
        elif usage_ratio >= 0.9:
            return WarningLevel.CRITICAL
        elif usage_ratio >= self.warning_threshold:
            return WarningLevel.WARNING
        else:
            return WarningLevel.NONE
