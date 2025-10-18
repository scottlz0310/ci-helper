"""
コスト管理機能のテスト

コストトラッカー、使用統計、制限チェックなどをテストします。
"""

from datetime import datetime, timedelta

import pytest

from src.ci_helper.ai.cost_manager import CostManager
from src.ci_helper.ai.cost_tracker import CostTracker
from src.ci_helper.ai.exceptions import CostLimitError
from src.ci_helper.ai.models import CostEstimate, LimitStatus, UsageStats, WarningLevel


class TestCostTracker:
    """コストトラッカーのテスト"""

    @pytest.fixture
    def storage_path(self, temp_dir):
        """ストレージパス"""
        return temp_dir / "cost_data.json"

    @pytest.fixture
    def cost_tracker(self, storage_path):
        """コストトラッカー"""
        return CostTracker(storage_path)

    def test_cost_tracker_initialization(self, cost_tracker, storage_path):
        """コストトラッカー初期化のテスト"""
        assert cost_tracker.storage_path == storage_path
        assert isinstance(cost_tracker.usage_data, dict)

    def test_record_usage(self, cost_tracker):
        """使用量記録のテスト"""
        cost_tracker.record_usage(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=0.0075,
        )

        # データが記録されているか確認
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in cost_tracker.usage_data
        assert "openai" in cost_tracker.usage_data[today]
        assert "gpt-4o" in cost_tracker.usage_data[today]["openai"]

        usage = cost_tracker.usage_data[today]["openai"]["gpt-4o"]
        assert usage["input_tokens"] == 1000
        assert usage["output_tokens"] == 500
        assert usage["cost"] == 0.0075
        assert usage["requests"] == 1

    def test_record_multiple_usage(self, cost_tracker):
        """複数回の使用量記録テスト"""
        # 1回目
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)
        # 2回目
        cost_tracker.record_usage("openai", "gpt-4o", 800, 400, 0.006)

        today = datetime.now().strftime("%Y-%m-%d")
        usage = cost_tracker.usage_data[today]["openai"]["gpt-4o"]

        # 累積されているか確認
        assert usage["input_tokens"] == 1800
        assert usage["output_tokens"] == 900
        assert usage["cost"] == 0.0135
        assert usage["requests"] == 2

    def test_get_daily_usage(self, cost_tracker):
        """日次使用量取得のテスト"""
        # テストデータを記録
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)
        cost_tracker.record_usage("anthropic", "claude-3-5-sonnet-20241022", 800, 600, 0.009)

        today = datetime.now()
        usage = cost_tracker.get_daily_usage(today.year, today.month, today.day)

        assert isinstance(usage, UsageStats)
        assert usage.total_cost == 0.0165  # 0.0075 + 0.009
        assert usage.total_requests == 2
        assert usage.total_input_tokens == 1800
        assert usage.total_output_tokens == 1100

    def test_get_monthly_usage(self, cost_tracker):
        """月次使用量取得のテスト"""
        # 複数日のデータを作成
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # 今日のデータ
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)

        # 昨日のデータ（手動で追加）
        yesterday_key = yesterday.strftime("%Y-%m-%d")
        cost_tracker.usage_data[yesterday_key] = {
            "openai": {
                "gpt-4o": {
                    "input_tokens": 800,
                    "output_tokens": 400,
                    "cost": 0.006,
                    "requests": 1,
                }
            }
        }

        monthly_usage = cost_tracker.get_monthly_usage(today.year, today.month)

        assert isinstance(monthly_usage, UsageStats)
        assert monthly_usage.total_cost == 0.0135  # 0.0075 + 0.006
        assert monthly_usage.total_requests == 2

    def test_get_provider_usage(self, cost_tracker):
        """プロバイダー別使用量取得のテスト"""
        # 複数プロバイダーのデータを記録
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)
        cost_tracker.record_usage("openai", "gpt-4o-mini", 2000, 800, 0.0012)
        cost_tracker.record_usage("anthropic", "claude-3-5-sonnet-20241022", 800, 600, 0.009)

        openai_usage = cost_tracker.get_provider_usage("openai")
        anthropic_usage = cost_tracker.get_provider_usage("anthropic")

        assert openai_usage.total_cost == 0.0087  # 0.0075 + 0.0012
        assert openai_usage.total_requests == 2
        assert anthropic_usage.total_cost == 0.009
        assert anthropic_usage.total_requests == 1

    def test_save_and_load_usage_data(self, cost_tracker):
        """使用量データの保存と読み込みテスト"""
        # データを記録
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)

        # 保存
        cost_tracker.save_usage_data()

        # 新しいインスタンスで読み込み
        new_tracker = CostTracker(cost_tracker.storage_path)

        # データが復元されているか確認
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in new_tracker.usage_data
        assert new_tracker.usage_data[today]["openai"]["gpt-4o"]["cost"] == 0.0075

    def test_cleanup_old_data(self, cost_tracker):
        """古いデータのクリーンアップテスト"""
        # 古いデータを作成
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        cost_tracker.usage_data[old_date] = {"openai": {"gpt-4o": {"cost": 0.01, "requests": 1}}}

        # 現在のデータも追加
        cost_tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)

        # クリーンアップ（90日より古いデータを削除）
        cleaned_count = cost_tracker.cleanup_old_data(days=90)

        assert cleaned_count == 1
        assert old_date not in cost_tracker.usage_data

        # 現在のデータは残っている
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in cost_tracker.usage_data


class TestCostManager:
    """コストマネージャーのテスト"""

    @pytest.fixture
    def cost_limits(self):
        """コスト制限設定"""
        return {
            "monthly_usd": 50.0,
            "daily_usd": 5.0,
            "per_request_usd": 1.0,
            "openai": 1.0,  # プロバイダー別制限
        }

    @pytest.fixture
    def cost_manager(self, temp_dir, cost_limits):
        """コストマネージャー"""
        return CostManager(
            storage_path=temp_dir / "cost_data.json",
            cost_limits=cost_limits,
        )

    def test_cost_manager_initialization(self, cost_manager, cost_limits):
        """コストマネージャー初期化のテスト"""
        assert cost_manager.cost_limits == cost_limits
        assert isinstance(cost_manager.tracker, CostTracker)

    def test_estimate_request_cost(self, cost_manager):
        """リクエストコスト推定のテスト"""
        estimate = cost_manager.estimate_request_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )

        assert isinstance(estimate, dict)
        assert estimate["provider"] == "openai"
        assert estimate["model"] == "gpt-4o"
        assert estimate["input_tokens"] == 1000
        assert estimate["output_tokens"] == 500
        assert estimate["estimated_cost"] > 0

    def test_check_limits_within_limits(self, cost_manager):
        """制限内での制限チェックテスト"""
        # 少量の使用量を記録
        cost_manager.tracker.record_usage("openai", "gpt-4o", 100, 50, 0.001)

        status = cost_manager.check_limits("openai")

        assert isinstance(status, LimitStatus)
        assert status.within_limits is True
        assert status.warning_level == WarningLevel.NONE

    def test_check_limits_approaching_limit(self, cost_manager):
        """制限接近時の制限チェックテスト"""
        # 月間制限の80%を使用
        cost_manager.tracker.record_usage("openai", "gpt-4o", 100000, 50000, 40.0)

        status = cost_manager.check_limits("openai")

        assert status.within_limits is True
        assert status.warning_level == WarningLevel.WARNING

    def test_check_limits_exceeded(self, cost_manager):
        """制限超過時の制限チェックテスト"""
        # 月間制限を超過
        cost_manager.tracker.record_usage("openai", "gpt-4o", 200000, 100000, 60.0)

        status = cost_manager.check_limits("openai")

        assert status.within_limits is False
        assert status.warning_level == WarningLevel.CRITICAL

    def test_validate_request_cost_within_limit(self, cost_manager):
        """リクエストコスト検証（制限内）のテスト"""
        estimate = CostEstimate(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            estimated_output_tokens=500,
            estimated_cost=0.5,  # 制限内
        )

        # 例外が発生しないことを確認
        cost_manager.validate_request_cost(estimate)

    def test_validate_request_cost_exceeds_limit(self, cost_manager):
        """リクエストコスト検証（制限超過）のテスト"""
        estimate = CostEstimate(
            provider="openai",
            model="gpt-4o",
            input_tokens=100000,
            estimated_output_tokens=50000,
            estimated_cost=1.5,  # 制限超過
        )

        with pytest.raises(CostLimitError):
            cost_manager.validate_request_cost(estimate)

    def test_get_usage_summary(self, cost_manager):
        """使用量サマリー取得のテスト"""
        # テストデータを記録
        cost_manager.tracker.record_usage("openai", "gpt-4o", 1000, 500, 0.0075)
        cost_manager.tracker.record_usage("anthropic", "claude-3-5-sonnet-20241022", 800, 600, 0.009)

        summary = cost_manager.get_usage_summary()

        assert "summary" in summary
        assert "breakdown" in summary
        assert "top_providers" in summary
        assert "period_days" in summary

        # サマリー
        assert summary["summary"]["total_cost"] == 0.0165
        assert summary["summary"]["total_requests"] == 2

        # プロバイダー別サマリー
        assert "openai" in [provider for provider, _ in summary["top_providers"]]
        assert "anthropic" in [provider for provider, _ in summary["top_providers"]]

    def test_get_cost_optimization_suggestions(self, cost_manager):
        """コスト最適化提案取得のテスト"""
        # 高コストなモデルの使用を記録（gpt-4が総コストの50%以上になるように）
        cost_manager.tracker.record_usage("openai", "gpt-4", 10000, 5000, 1.5)  # 高コスト
        cost_manager.tracker.record_usage("openai", "gpt-4o-mini", 1000, 500, 0.1)  # 低コスト

        # 多数のリクエストを記録してキャッシュ推奨を発生させる
        for i in range(60):
            cost_manager.tracker.record_usage("openai", "gpt-4o", 100, 50, 0.01)

        suggestions = cost_manager.get_cost_optimization_suggestions()

        assert isinstance(suggestions, list)
        # 何らかの提案が生成されることを確認（具体的な内容は実装に依存）
        # キャッシュ推奨は確実に生成される
        assert len(suggestions) > 0

    def test_calculate_warning_level(self, cost_manager):
        """警告レベル計算のテスト"""
        # 制限の50%使用
        assert cost_manager._calculate_warning_level(25.0, 50.0) == WarningLevel.NONE

        # 制限の80%使用
        assert cost_manager._calculate_warning_level(40.0, 50.0) == WarningLevel.WARNING

        # 制限の95%使用
        assert cost_manager._calculate_warning_level(47.5, 50.0) == WarningLevel.CRITICAL

        # 制限超過
        assert cost_manager._calculate_warning_level(60.0, 50.0) == WarningLevel.CRITICAL

    def test_record_and_check_usage(self, cost_manager):
        """使用量記録と制限チェックの統合テスト"""
        # 使用量を記録
        cost_manager.record_usage(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=0.0075,
        )

        # 制限チェック
        status = cost_manager.check_limits("openai")

        assert not status.is_over_limit
        assert status.current_usage == 0.0075

        # 使用統計の確認
        stats = cost_manager.tracker.get_provider_usage("openai")
        assert stats.total_cost == 0.0075
        assert stats.total_requests == 1
