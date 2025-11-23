"""パフォーマンス監視ユーティリティ

ログ整形処理のパフォーマンスを監視・分析する機能を提供します。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from rich.console import Console
from rich.table import Table


class PerformanceMonitor:
    """パフォーマンス監視クラス

    メモリ使用量、処理時間、ファイルサイズなどを監視します。
    """

    def __init__(self, console: Console | None = None):
        """パフォーマンス監視を初期化

        Args:
            console: Rich Console インスタンス

        """
        self.console = console or Console()
        self.start_time: float | None = None
        self.start_memory: float | None = None
        self.peak_memory: float = 0.0
        self.file_size: int = 0
        self.processing_stats: dict[str, Any] = {}

    def start_monitoring(self, file_path: Path | None = None) -> None:
        """監視を開始

        Args:
            file_path: 処理対象ファイル（サイズ測定用）

        """
        self.start_time = time.time()

        # 初期メモリ使用量を記録
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            self.start_memory = memory_info.rss / (1024 * 1024)  # MB
            self.peak_memory = self.start_memory
        except Exception:
            self.start_memory = 0.0
            self.peak_memory = 0.0

        # ファイルサイズを記録
        if file_path and file_path.exists():
            self.file_size = file_path.stat().st_size
        else:
            self.file_size = 0

        # 統計情報を初期化
        self.processing_stats = {
            "start_time": datetime.now().isoformat(),
            "file_size": self.file_size,
            "start_memory_mb": self.start_memory,
        }

    def update_peak_memory(self) -> None:
        """ピークメモリ使用量を更新"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            current_memory = memory_info.rss / (1024 * 1024)  # MB
            self.peak_memory = max(self.peak_memory, current_memory)
        except Exception:
            pass

    def finish_monitoring(self) -> dict[str, Any]:
        """監視を終了し、結果を取得

        Returns:
            パフォーマンス統計情報

        """
        end_time = time.time()

        # 最終メモリ使用量を記録
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            end_memory = memory_info.rss / (1024 * 1024)  # MB
        except Exception:
            end_memory = 0.0

        # 処理時間を計算
        processing_time = end_time - (self.start_time or end_time)

        # 統計情報を更新
        self.processing_stats.update(
            {
                "end_time": datetime.now().isoformat(),
                "processing_time_seconds": processing_time,
                "start_memory_mb": self.start_memory or 0.0,
                "end_memory_mb": end_memory,
                "peak_memory_mb": self.peak_memory,
                "memory_increase_mb": end_memory - (self.start_memory or 0.0),
                "throughput_mb_per_second": (self.file_size / (1024 * 1024)) / max(processing_time, 0.001),
            },
        )

        return self.processing_stats

    def show_performance_summary(self, stats: dict[str, Any] | None = None) -> None:
        """パフォーマンス概要を表示

        Args:
            stats: 表示する統計情報（Noneの場合は現在の統計を使用）

        """
        if stats is None:
            stats = self.processing_stats

        # パフォーマンス概要テーブル
        table = Table(title="⚡ パフォーマンス概要")
        table.add_column("項目", style="cyan")
        table.add_column("値", style="green")

        # 処理時間
        processing_time = stats.get("processing_time_seconds", 0)
        table.add_row("処理時間", f"{processing_time:.2f}秒")

        # ファイルサイズ
        file_size_mb = stats.get("file_size", 0) / (1024 * 1024)
        table.add_row("ファイルサイズ", f"{file_size_mb:.2f} MB")

        # スループット
        throughput = stats.get("throughput_mb_per_second", 0)
        table.add_row("処理速度", f"{throughput:.2f} MB/秒")

        # メモリ使用量
        start_memory = stats.get("start_memory_mb", 0)
        peak_memory = stats.get("peak_memory_mb", 0)
        memory_increase = stats.get("memory_increase_mb", 0)

        table.add_row("開始時メモリ", f"{start_memory:.1f} MB")
        table.add_row("ピークメモリ", f"{peak_memory:.1f} MB")
        table.add_row("メモリ増加", f"{memory_increase:+.1f} MB")

        self.console.print(table)

        # パフォーマンス評価
        self._show_performance_evaluation(stats)

    def _show_performance_evaluation(self, stats: dict[str, Any]) -> None:
        """パフォーマンス評価を表示

        Args:
            stats: 統計情報

        """
        evaluations: list[str] = []

        # 処理速度の評価
        throughput = stats.get("throughput_mb_per_second", 0)
        if throughput > 10:
            evaluations.append("🚀 処理速度: 非常に高速")
        elif throughput > 5:
            evaluations.append("⚡ 処理速度: 高速")
        elif throughput > 1:
            evaluations.append("✅ 処理速度: 標準")
        else:
            evaluations.append("🐌 処理速度: 低速（最適化を検討）")

        # メモリ効率の評価
        memory_increase = stats.get("memory_increase_mb", 0)
        file_size_mb = stats.get("file_size", 0) / (1024 * 1024)

        if file_size_mb > 0:
            memory_ratio = memory_increase / file_size_mb
            if memory_ratio < 0.5:
                evaluations.append("💚 メモリ効率: 優秀")
            elif memory_ratio < 1.0:
                evaluations.append("💛 メモリ効率: 良好")
            elif memory_ratio < 2.0:
                evaluations.append("🧡 メモリ効率: 標準")
            else:
                evaluations.append("❤️ メモリ効率: 改善が必要")

        # 処理時間の評価
        processing_time = stats.get("processing_time_seconds", 0)
        if processing_time < 1:
            evaluations.append("⚡ 応答性: 即座")
        elif processing_time < 5:
            evaluations.append("✅ 応答性: 高速")
        elif processing_time < 30:
            evaluations.append("⏱️ 応答性: 標準")
        else:
            evaluations.append("🕐 応答性: 時間がかかる")

        if evaluations:
            self.console.print("\n[bold cyan]📊 パフォーマンス評価[/bold cyan]")
            for evaluation in evaluations:
                self.console.print(f"  {evaluation}")

    def get_optimization_recommendations(self, stats: dict[str, Any] | None = None) -> list[str]:
        """最適化推奨事項を取得

        Args:
            stats: 統計情報

        Returns:
            推奨事項のリスト

        """
        if stats is None:
            stats = self.processing_stats

        recommendations: list[str] = []

        # 処理速度ベースの推奨事項
        throughput = stats.get("throughput_mb_per_second", 0)
        if throughput < 1:
            recommendations.append("処理速度が低速です。ストリーミング処理の使用を検討してください。")
            recommendations.append("キャッシュ機能を有効にして重複処理を避けてください。")

        # メモリ使用量ベースの推奨事項
        memory_increase = stats.get("memory_increase_mb", 0)
        if memory_increase > 500:  # 500MB以上の増加
            recommendations.append("メモリ使用量が多いです。メモリ制限を設定してください。")
            recommendations.append("大きなファイルではストリーミング処理を使用してください。")

        # ファイルサイズベースの推奨事項
        file_size_mb = stats.get("file_size", 0) / (1024 * 1024)
        if file_size_mb > 50:  # 50MB以上
            recommendations.append("大きなファイルです。--max-memory オプションでメモリ制限を設定してください。")
            recommendations.append("--disable-optimization を使用しない限り、自動的に最適化が適用されます。")

        # 処理時間ベースの推奨事項
        processing_time = stats.get("processing_time_seconds", 0)
        if processing_time > 60:  # 1分以上
            recommendations.append("処理時間が長いです。キャッシュ機能を活用してください。")
            recommendations.append("不要な詳細レベルを避けて --verbose-level minimal を使用してください。")

        if not recommendations:
            recommendations.append("パフォーマンスは良好です。現在の設定を維持してください。")

        return recommendations

    def show_optimization_recommendations(self, stats: dict[str, Any] | None = None) -> None:
        """最適化推奨事項を表示

        Args:
            stats: 統計情報

        """
        recommendations = self.get_optimization_recommendations(stats)

        self.console.print("\n[bold cyan]💡 最適化推奨事項[/bold cyan]")
        for i, recommendation in enumerate(recommendations, 1):
            self.console.print(f"[dim]{i}.[/dim] {recommendation}")

    def compare_with_baseline(
        self,
        baseline_stats: dict[str, Any],
        current_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """ベースライン統計と比較

        Args:
            baseline_stats: ベースライン統計
            current_stats: 現在の統計（Noneの場合は現在の統計を使用）

        Returns:
            比較結果

        """
        if current_stats is None:
            current_stats = self.processing_stats

        comparison: dict[str, Any] = {}

        # 処理時間の比較
        baseline_time = baseline_stats.get("processing_time_seconds", 0)
        current_time = current_stats.get("processing_time_seconds", 0)
        if baseline_time > 0:
            time_improvement = (baseline_time - current_time) / baseline_time * 100
            comparison["time_improvement_percent"] = time_improvement

        # メモリ使用量の比較
        baseline_memory = baseline_stats.get("memory_increase_mb", 0)
        current_memory = current_stats.get("memory_increase_mb", 0)
        if baseline_memory > 0:
            memory_improvement = (baseline_memory - current_memory) / baseline_memory * 100
            comparison["memory_improvement_percent"] = memory_improvement

        # スループットの比較
        baseline_throughput = baseline_stats.get("throughput_mb_per_second", 0)
        current_throughput = current_stats.get("throughput_mb_per_second", 0)
        if baseline_throughput > 0:
            throughput_improvement = (current_throughput - baseline_throughput) / baseline_throughput * 100
            comparison["throughput_improvement_percent"] = throughput_improvement

        return comparison

    def show_comparison_results(self, comparison: dict[str, Any]) -> None:
        """比較結果を表示

        Args:
            comparison: 比較結果

        """
        table = Table(title="📈 パフォーマンス比較")
        table.add_column("項目", style="cyan")
        table.add_column("改善率", style="green")
        table.add_column("評価", style="yellow")

        # 処理時間の改善
        time_improvement = comparison.get("time_improvement_percent", 0)
        time_status = "🚀 大幅改善" if time_improvement > 20 else "✅ 改善" if time_improvement > 0 else "❌ 悪化"
        table.add_row("処理時間", f"{time_improvement:+.1f}%", time_status)

        # メモリ使用量の改善
        memory_improvement = comparison.get("memory_improvement_percent", 0)
        memory_status = "🚀 大幅改善" if memory_improvement > 20 else "✅ 改善" if memory_improvement > 0 else "❌ 悪化"
        table.add_row("メモリ効率", f"{memory_improvement:+.1f}%", memory_status)

        # スループットの改善
        throughput_improvement = comparison.get("throughput_improvement_percent", 0)
        throughput_status = (
            "🚀 大幅改善" if throughput_improvement > 20 else "✅ 改善" if throughput_improvement > 0 else "❌ 悪化"
        )
        table.add_row("処理速度", f"{throughput_improvement:+.1f}%", throughput_status)

        self.console.print(table)


class PerformanceProfiler:
    """パフォーマンスプロファイラー

    詳細なパフォーマンス分析を行います。
    """

    def __init__(self):
        """プロファイラーを初期化"""
        self.profiles: dict[str, dict[str, Any]] = {}

    def profile_formatter_performance(
        self,
        formatter_name: str,
        file_size: int,
        processing_time: float,
        memory_usage: float,
    ) -> None:
        """フォーマッターのパフォーマンスをプロファイル

        Args:
            formatter_name: フォーマッター名
            file_size: ファイルサイズ（バイト）
            processing_time: 処理時間（秒）
            memory_usage: メモリ使用量（MB）

        """
        if formatter_name not in self.profiles:
            self.profiles[formatter_name] = {
                "total_files": 0,
                "total_size": 0,
                "total_time": 0.0,
                "total_memory": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "min_memory": float("inf"),
                "max_memory": 0.0,
            }

        profile = self.profiles[formatter_name]
        profile["total_files"] += 1
        profile["total_size"] += file_size
        profile["total_time"] += processing_time
        profile["total_memory"] += memory_usage
        profile["min_time"] = min(profile["min_time"], processing_time)
        profile["max_time"] = max(profile["max_time"], processing_time)
        profile["min_memory"] = min(profile["min_memory"], memory_usage)
        profile["max_memory"] = max(profile["max_memory"], memory_usage)

    def get_formatter_statistics(self, formatter_name: str) -> dict[str, Any] | None:
        """フォーマッター統計を取得

        Args:
            formatter_name: フォーマッター名

        Returns:
            統計情報（存在しない場合はNone）

        """
        if formatter_name not in self.profiles:
            return None

        profile = self.profiles[formatter_name]

        if profile["total_files"] == 0:
            return None

        return {
            "total_files": profile["total_files"],
            "total_size_mb": profile["total_size"] / (1024 * 1024),
            "average_time": profile["total_time"] / profile["total_files"],
            "average_memory": profile["total_memory"] / profile["total_files"],
            "average_throughput": (profile["total_size"] / (1024 * 1024)) / profile["total_time"],
            "min_time": profile["min_time"],
            "max_time": profile["max_time"],
            "min_memory": profile["min_memory"],
            "max_memory": profile["max_memory"],
        }

    def compare_formatters(self) -> dict[str, Any]:
        """フォーマッター間のパフォーマンス比較

        Returns:
            比較結果

        """
        comparison: dict[str, Any] = {}

        for formatter_name in self.profiles:
            stats = self.get_formatter_statistics(formatter_name)
            if stats:
                comparison[formatter_name] = {
                    "average_time": stats["average_time"],
                    "average_memory": stats["average_memory"],
                    "average_throughput": stats["average_throughput"],
                    "total_files": stats["total_files"],
                }

        return comparison


def get_performance_monitor(console: Console | None = None) -> PerformanceMonitor:
    """パフォーマンス監視インスタンスを取得

    Args:
        console: Rich Console インスタンス

    Returns:
        パフォーマンス監視インスタンス

    """
    return PerformanceMonitor(console)
