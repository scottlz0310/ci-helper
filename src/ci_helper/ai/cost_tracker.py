"""
コスト管理と使用統計

AI使用量の記録、コスト計算、使用制限の管理を行います。
月間使用統計、プロバイダー別コスト、使用制限チェックなどの機能を提供します。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiofiles

from .exceptions import ConfigurationError
from .models import LimitStatus, UsageStats


class CostTracker:
    """コスト管理と使用統計クラス"""

    def __init__(
        self,
        storage_path: Path,
        cost_limits: dict[str, float] | None = None,
        auto_save: bool = True,
    ):
        """コストトラッカーを初期化

        Args:
            storage_path: 使用データの保存パス
            cost_limits: コスト制限の辞書
            auto_save: 自動保存を有効にするかどうか
        """
        self.storage_path = storage_path
        self.cost_limits = cost_limits or {}
        self.auto_save = auto_save

        # 使用データを読み込み
        self.usage_data = self._load_usage_data()

        # 保存パスのディレクトリを作成
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_usage_data(self) -> dict[str, Any]:
        """使用データを読み込み"""
        if not self.storage_path.exists():
            return {
                "records": [],
                "created": time.time(),
                "last_updated": time.time(),
                "version": "1.0",
            }

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # データファイルが破損している場合は新規作成
            return {
                "records": [],
                "created": time.time(),
                "last_updated": time.time(),
                "version": "1.0",
            }

    async def _save_usage_data(self) -> None:
        """使用データを保存"""
        if not self.auto_save:
            return

        try:
            self.usage_data["last_updated"] = time.time()
            async with aiofiles.open(self.storage_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.usage_data, indent=2, ensure_ascii=False))
        except Exception as e:
            raise ConfigurationError(f"使用データの保存に失敗しました: {e}")

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        analysis_type: str = "analysis",
        success: bool = True,
        timestamp: datetime | None = None,
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
            timestamp: タイムスタンプ（指定されない場合は現在時刻）
        """
        if timestamp is None:
            timestamp = datetime.now()

        # 日付文字列を生成
        date_str = timestamp.strftime("%Y-%m-%d")

        # 階層構造でデータを保存（テスト期待形式）
        if date_str not in self.usage_data:
            self.usage_data[date_str] = {}

        if provider not in self.usage_data[date_str]:
            self.usage_data[date_str][provider] = {}

        if model not in self.usage_data[date_str][provider]:
            self.usage_data[date_str][provider][model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "requests": 0,
                "analysis_type": analysis_type,
                "success": success,
            }

        # 累積データを更新
        model_data = self.usage_data[date_str][provider][model]
        model_data["input_tokens"] += input_tokens
        model_data["output_tokens"] += output_tokens
        model_data["cost"] += cost
        model_data["requests"] += 1

        # レコード形式でも保存（他のメソッドとの互換性のため）
        if "records" not in self.usage_data:
            self.usage_data["records"] = []

        record = {
            "timestamp": timestamp.isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "analysis_type": analysis_type,
            "success": success,
        }
        self.usage_data["records"].append(record)

        # 自動保存
        if self.auto_save:
            self.save_usage_data()

    async def record_usage_async(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        analysis_type: str = "analysis",
        success: bool = True,
        timestamp: datetime | None = None,
    ) -> None:
        """使用量を記録（非同期版）"""
        self.record_usage(provider, model, input_tokens, output_tokens, cost, analysis_type, success, timestamp)

    def get_monthly_usage(self, year: int, month: int) -> UsageStats:
        """月間使用統計を取得

        Args:
            year: 年
            month: 月

        Returns:
            月間使用統計
        """
        # 対象月の記録を抽出（レコード形式から）
        monthly_records = []
        record_dates = set()

        if "records" in self.usage_data:
            for record in self.usage_data["records"]:
                record_date = datetime.fromisoformat(record["timestamp"])
                if record_date.year == year and record_date.month == month:
                    monthly_records.append(record)
                    record_dates.add(record_date.strftime("%Y-%m-%d"))

        # 階層構造からも抽出（レコードにない日付のみ）
        for date_str, date_data in self.usage_data.items():
            if date_str in ["records", "created", "last_updated", "version"] or not isinstance(date_data, dict):
                continue

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj.year == year and date_obj.month == month and date_str not in record_dates:
                    # 階層データをレコード形式に変換
                    for provider, provider_data in date_data.items():
                        for model, model_data in provider_data.items():
                            # 複数リクエストがある場合は分割
                            requests = model_data.get("requests", 1)
                            for _ in range(requests):
                                record = {
                                    "timestamp": f"{date_str}T12:00:00",
                                    "provider": provider,
                                    "model": model,
                                    "input_tokens": model_data["input_tokens"] // requests,
                                    "output_tokens": model_data["output_tokens"] // requests,
                                    "total_tokens": (model_data["input_tokens"] + model_data["output_tokens"])
                                    // requests,
                                    "cost": model_data["cost"] / requests,
                                    "analysis_type": model_data.get("analysis_type", "analysis"),
                                    "success": model_data.get("success", True),
                                }
                                monthly_records.append(record)
            except ValueError:
                # 日付形式でない場合はスキップ
                continue

        return self._calculate_stats(monthly_records)

    def get_usage_stats(self, days: int = 30) -> UsageStats:
        """指定期間の使用統計を取得

        Args:
            days: 対象日数

        Returns:
            使用統計
        """
        # 対象期間の記録を抽出
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_records = []

        for record in self.usage_data["records"]:
            record_date = datetime.fromisoformat(record["timestamp"])
            if record_date >= cutoff_date:
                recent_records.append(record)

        return self._calculate_stats(recent_records)

    def _calculate_stats(self, records: list[dict[str, Any]]) -> UsageStats:
        """記録から統計を計算"""
        if not records:
            return UsageStats()

        total_requests = len(records)
        successful_requests = sum(1 for r in records if r["success"])
        failed_requests = total_requests - successful_requests

        total_tokens = sum(r["total_tokens"] for r in records)
        total_input_tokens = sum(r["input_tokens"] for r in records)
        total_output_tokens = sum(r["output_tokens"] for r in records)
        total_cost = sum(r["cost"] for r in records)

        # プロバイダー別統計
        provider_breakdown = {}
        for record in records:
            provider = record["provider"]
            provider_breakdown[provider] = provider_breakdown.get(provider, 0) + 1

        # モデル別統計
        model_breakdown = {}
        for record in records:
            model = record["model"]
            model_breakdown[model] = model_breakdown.get(model, 0) + 1

        # 日別使用量
        daily_usage = {}
        for record in records:
            date_str = record["timestamp"][:10]  # YYYY-MM-DD
            daily_usage[date_str] = daily_usage.get(date_str, 0.0) + record["cost"]

        # 平均値を計算
        avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0
        avg_cost_per_request = total_cost / total_requests if total_requests > 0 else 0

        return UsageStats(
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost=total_cost,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_tokens_per_request=avg_tokens_per_request,
            average_cost_per_request=avg_cost_per_request,
            provider_breakdown=provider_breakdown,
            model_breakdown=model_breakdown,
            daily_usage=daily_usage,
        )

    def check_limits(self, provider: str) -> LimitStatus:
        """使用制限をチェック

        Args:
            provider: プロバイダー名

        Returns:
            制限ステータス
        """
        # 月間制限をチェック
        current_date = datetime.now()

        # プロバイダー別の使用量を取得
        provider_cost = 0.0
        for record in self.usage_data["records"]:
            record_date = datetime.fromisoformat(record["timestamp"])
            if (
                record_date.year == current_date.year
                and record_date.month == current_date.month
                and record["provider"] == provider
            ):
                provider_cost += record["cost"]

        # 制限値を取得
        monthly_limit_key = f"{provider}_monthly_usd"
        if monthly_limit_key not in self.cost_limits:
            monthly_limit_key = "monthly_usd"

        limit = self.cost_limits.get(monthly_limit_key, float("inf"))
        remaining = max(0, limit - provider_cost)

        # 次月のリセット時刻を計算
        if current_date.month == 12:
            reset_time = datetime(current_date.year + 1, 1, 1)
        else:
            reset_time = datetime(current_date.year, current_date.month + 1, 1)

        return LimitStatus(
            provider=provider,
            current_usage=provider_cost,
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
        )

    def estimate_request_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int | None = None,
    ) -> float:
        """リクエストコストを推定

        Args:
            provider: プロバイダー名
            model: モデル名
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数（推定）

        Returns:
            推定コスト（USD）
        """
        # 出力トークン数が指定されていない場合は入力の50%と推定
        if output_tokens is None:
            output_tokens = int(input_tokens * 0.5)

        # プロバイダー別のコスト計算
        if provider == "openai":
            return self._estimate_openai_cost(model, input_tokens, output_tokens)
        elif provider == "anthropic":
            return self._estimate_anthropic_cost(model, input_tokens, output_tokens)
        elif provider == "local":
            return 0.0  # ローカルLLMは無料
        else:
            # 不明なプロバイダーの場合はOpenAIの料金で推定
            return self._estimate_openai_cost("gpt-4o", input_tokens, output_tokens)

    def _estimate_openai_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """OpenAIのコストを推定"""
        # モデル別の料金（USD per 1K tokens）
        costs = {
            "gpt-4o": {"input": 0.0025, "output": 0.01},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        }

        model_costs = costs.get(model, costs["gpt-4o"])
        input_cost = (input_tokens / 1000) * model_costs["input"]
        output_cost = (output_tokens / 1000) * model_costs["output"]

        return input_cost + output_cost

    def _estimate_anthropic_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Anthropicのコストを推定"""
        # モデル別の料金（USD per 1K tokens）
        costs = {
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-5-haiku-20241022": {"input": 0.00025, "output": 0.00125},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        }

        model_costs = costs.get(model, costs["claude-3-5-sonnet-20241022"])
        input_cost = (input_tokens / 1000) * model_costs["input"]
        output_cost = (output_tokens / 1000) * model_costs["output"]

        return input_cost + output_cost

    def get_cost_breakdown(self, days: int = 30) -> dict[str, Any]:
        """コスト内訳を取得

        Args:
            days: 対象日数

        Returns:
            コスト内訳
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_records = []

        for record in self.usage_data["records"]:
            record_date = datetime.fromisoformat(record["timestamp"])
            if record_date >= cutoff_date:
                recent_records.append(record)

        # プロバイダー別コスト
        provider_costs = {}
        for record in recent_records:
            provider = record["provider"]
            provider_costs[provider] = provider_costs.get(provider, 0.0) + record["cost"]

        # モデル別コスト
        model_costs = {}
        for record in recent_records:
            model = record["model"]
            model_costs[model] = model_costs.get(model, 0.0) + record["cost"]

        # 分析タイプ別コスト
        type_costs = {}
        for record in recent_records:
            analysis_type = record["analysis_type"]
            type_costs[analysis_type] = type_costs.get(analysis_type, 0.0) + record["cost"]

        total_cost = sum(record["cost"] for record in recent_records)

        return {
            "total_cost": total_cost,
            "period_days": days,
            "provider_breakdown": provider_costs,
            "model_breakdown": model_costs,
            "analysis_type_breakdown": type_costs,
            "record_count": len(recent_records),
        }

    async def export_usage_data(self, export_path: Path, export_format: str = "json") -> None:
        """使用データをエクスポート

        Args:
            export_path: エクスポート先パス
            format: エクスポート形式（json, csv）
        """
        if format.lower() == "json":
            async with aiofiles.open(export_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.usage_data, indent=2, ensure_ascii=False))
        elif format.lower() == "csv":
            await self._export_csv(export_path)
        else:
            raise ConfigurationError(f"サポートされていないエクスポート形式: {format}")

    async def _export_csv(self, export_path: Path) -> None:
        """CSV形式でエクスポート"""
        import csv
        import io

        # CSVデータを作成
        output = io.StringIO()
        writer = csv.writer(output)

        # ヘッダー
        writer.writerow(
            [
                "timestamp",
                "provider",
                "model",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cost",
                "analysis_type",
                "success",
            ]
        )

        # データ行
        for record in self.usage_data["records"]:
            writer.writerow(
                [
                    record["timestamp"],
                    record["provider"],
                    record["model"],
                    record["input_tokens"],
                    record["output_tokens"],
                    record["total_tokens"],
                    record["cost"],
                    record["analysis_type"],
                    record["success"],
                ]
            )

        # ファイルに書き込み
        async with aiofiles.open(export_path, "w", encoding="utf-8") as f:
            await f.write(output.getvalue())

    def get_usage_trends(self, days: int = 30) -> dict[str, Any]:
        """使用傾向を分析

        Args:
            days: 対象日数

        Returns:
            使用傾向の分析結果
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_records = []

        for record in self.usage_data["records"]:
            record_date = datetime.fromisoformat(record["timestamp"])
            if record_date >= cutoff_date:
                recent_records.append(record)

        if not recent_records:
            return {"message": "分析対象のデータがありません"}

        # 日別使用量の傾向
        daily_costs = {}
        daily_requests = {}

        for record in recent_records:
            date_str = record["timestamp"][:10]
            daily_costs[date_str] = daily_costs.get(date_str, 0.0) + record["cost"]
            daily_requests[date_str] = daily_requests.get(date_str, 0) + 1

        # 傾向分析
        dates = sorted(daily_costs.keys())
        if len(dates) >= 7:
            # 最初の週と最後の週を比較
            first_week_avg = sum(daily_costs.get(date, 0) for date in dates[:7]) / 7
            last_week_avg = sum(daily_costs.get(date, 0) for date in dates[-7:]) / 7

            cost_trend = "増加" if last_week_avg > first_week_avg else "減少"
            cost_change = abs(last_week_avg - first_week_avg)
        else:
            cost_trend = "不明"
            cost_change = 0.0

        return {
            "period_days": days,
            "total_days_with_usage": len(dates),
            "cost_trend": cost_trend,
            "cost_change_per_day": cost_change,
            "average_daily_cost": sum(daily_costs.values()) / len(dates) if dates else 0,
            "average_daily_requests": sum(daily_requests.values()) / len(dates) if dates else 0,
            "peak_usage_date": max(daily_costs.keys(), key=lambda d: daily_costs[d]) if daily_costs else None,
            "peak_usage_cost": max(daily_costs.values()) if daily_costs else 0,
        }

    def save_usage_data(self) -> None:
        """使用データを同期的に保存"""
        try:
            self.usage_data["last_updated"] = time.time()
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.usage_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise ConfigurationError(f"使用データの保存に失敗しました: {e}")

    def cleanup_old_data(self, days: int = 90) -> int:
        """古いデータをクリーンアップ

        Args:
            days: 保持する日数

        Returns:
            削除されたレコード数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_count = 0

        # レコード形式のデータをクリーンアップ
        if "records" in self.usage_data:
            original_count = len(self.usage_data["records"])
            self.usage_data["records"] = [
                record
                for record in self.usage_data["records"]
                if datetime.fromisoformat(record["timestamp"]) > cutoff_date
            ]
            cleaned_count += original_count - len(self.usage_data["records"])

        # 階層構造のデータもクリーンアップ
        dates_to_remove = []
        for date_str in self.usage_data.keys():
            if date_str in ["records", "created", "last_updated", "version"]:
                continue

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj < cutoff_date:
                    dates_to_remove.append(date_str)
            except ValueError:
                # 日付形式でない場合はスキップ
                continue

        # 古い日付のデータを削除
        for date_str in dates_to_remove:
            del self.usage_data[date_str]
            cleaned_count += 1

        if cleaned_count > 0 and self.auto_save:
            # 同期的に保存
            self.save_usage_data()

        return cleaned_count

    def get_daily_usage(self, year: int, month: int, day: int) -> UsageStats:
        """日次使用統計を取得

        Args:
            year: 年
            month: 月
            day: 日

        Returns:
            日次使用統計
        """
        target_date = datetime(year, month, day)
        daily_records = []

        for record in self.usage_data["records"]:
            record_date = datetime.fromisoformat(record["timestamp"])
            if record_date.date() == target_date.date():
                daily_records.append(record)

        return self._calculate_stats(daily_records)

    def get_provider_usage(self, provider: str) -> UsageStats:
        """プロバイダー別使用統計を取得

        Args:
            provider: プロバイダー名

        Returns:
            プロバイダー別使用統計
        """
        provider_records = [record for record in self.usage_data["records"] if record["provider"] == provider]

        return self._calculate_stats(provider_records)
