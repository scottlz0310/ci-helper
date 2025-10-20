"""
テストパフォーマンス監視ユーティリティ

このモジュールは、テスト実行のパフォーマンスメトリクスを収集・分析し、
CI/CDパイプラインでの品質保証を支援します。
"""

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil


@dataclass
class TestExecutionMetrics:
    """テスト実行メトリクス"""

    test_name: str
    execution_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error_message: str | None = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class PerformanceBenchmark:
    """パフォーマンスベンチマーク"""

    max_execution_time: float = 60.0  # 秒
    max_memory_usage_mb: float = 100.0  # MB
    max_cpu_usage_percent: float = 80.0  # %
    min_success_rate: float = 0.95  # 95%


class PerformanceMonitor:
    """テストパフォーマンス監視クラス"""

    def __init__(self, results_dir: Path = Path("test_results")):
        """
        パフォーマンス監視を初期化

        Args:
            results_dir: 結果保存ディレクトリ
        """
        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)
        self.metrics: list[TestExecutionMetrics] = []
        self.benchmark = PerformanceBenchmark()

    def run_test_with_monitoring(self, test_path: str, timeout: int = 120) -> TestExecutionMetrics:
        """
        テストを監視付きで実行

        Args:
            test_path: テストパス
            timeout: タイムアウト（秒）

        Returns:
            実行メトリクス
        """
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        start_time = time.time()
        cpu_samples = []

        # テスト実行
        try:
            result = subprocess.run(
                ["uv", "run", "pytest", test_path, "--tb=short", "-v"], capture_output=True, text=True, timeout=timeout
            )

            success = result.returncode == 0
            error_message = result.stderr if not success else None

        except subprocess.TimeoutExpired:
            success = False
            error_message = f"テストがタイムアウトしました（{timeout}秒）"
        except Exception as e:
            success = False
            error_message = str(e)

        end_time = time.time()
        execution_time = end_time - start_time

        # メモリ使用量を測定
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_usage = final_memory - initial_memory

        # CPU使用率を取得（概算）
        cpu_usage = process.cpu_percent()

        metrics = TestExecutionMetrics(
            test_name=test_path,
            execution_time=execution_time,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            success=success,
            error_message=error_message,
        )

        self.metrics.append(metrics)
        return metrics

    def run_test_suite_monitoring(self, test_paths: list[str]) -> list[TestExecutionMetrics]:
        """
        テストスイートを監視付きで実行

        Args:
            test_paths: テストパスのリスト

        Returns:
            実行メトリクスのリスト
        """
        suite_metrics = []

        for test_path in test_paths:
            print(f"実行中: {test_path}")
            metrics = self.run_test_with_monitoring(test_path)
            suite_metrics.append(metrics)

            # 結果を即座に保存
            self.save_metrics()

        return suite_metrics

    def analyze_performance(self) -> dict[str, Any]:
        """
        パフォーマンス分析を実行

        Returns:
            分析結果
        """
        if not self.metrics:
            return {"error": "メトリクスデータがありません"}

        # 基本統計
        execution_times = [m.execution_time for m in self.metrics]
        memory_usages = [m.memory_usage_mb for m in self.metrics]
        cpu_usages = [m.cpu_usage_percent for m in self.metrics]
        success_count = sum(1 for m in self.metrics if m.success)

        analysis = {
            "total_tests": len(self.metrics),
            "successful_tests": success_count,
            "success_rate": success_count / len(self.metrics),
            "execution_time": {
                "average": sum(execution_times) / len(execution_times),
                "max": max(execution_times),
                "min": min(execution_times),
                "total": sum(execution_times),
            },
            "memory_usage": {
                "average": sum(memory_usages) / len(memory_usages),
                "max": max(memory_usages),
                "min": min(memory_usages),
            },
            "cpu_usage": {"average": sum(cpu_usages) / len(cpu_usages), "max": max(cpu_usages), "min": min(cpu_usages)},
        }

        # ベンチマーク違反の検出
        violations = []

        if analysis["execution_time"]["max"] > self.benchmark.max_execution_time:
            violations.append(
                f"最大実行時間がベンチマークを超過: {analysis['execution_time']['max']:.2f}s > {self.benchmark.max_execution_time}s"
            )

        if analysis["memory_usage"]["max"] > self.benchmark.max_memory_usage_mb:
            violations.append(
                f"最大メモリ使用量がベンチマークを超過: {analysis['memory_usage']['max']:.2f}MB > {self.benchmark.max_memory_usage_mb}MB"
            )

        if analysis["success_rate"] < self.benchmark.min_success_rate:
            violations.append(
                f"成功率がベンチマークを下回る: {analysis['success_rate']:.2%} < {self.benchmark.min_success_rate:.2%}"
            )

        analysis["benchmark_violations"] = violations
        analysis["benchmark_passed"] = len(violations) == 0

        return analysis

    def save_metrics(self, filename: str | None = None) -> Path:
        """
        メトリクスをファイルに保存

        Args:
            filename: ファイル名（省略時は自動生成）

        Returns:
            保存されたファイルのパス
        """
        if filename is None:
            timestamp = int(time.time())
            filename = f"test_metrics_{timestamp}.json"

        filepath = self.results_dir / filename

        data = {
            "timestamp": time.time(),
            "benchmark": asdict(self.benchmark),
            "metrics": [asdict(m) for m in self.metrics],
            "analysis": self.analyze_performance(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath

    def load_metrics(self, filepath: Path) -> None:
        """
        メトリクスをファイルから読み込み

        Args:
            filepath: ファイルパス
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self.benchmark = PerformanceBenchmark(**data["benchmark"])
        self.metrics = [TestExecutionMetrics(**m) for m in data["metrics"]]

    def compare_with_baseline(self, baseline_filepath: Path) -> dict[str, Any]:
        """
        ベースラインとの比較

        Args:
            baseline_filepath: ベースラインファイルのパス

        Returns:
            比較結果
        """
        # 現在のメトリクスを保存
        current_analysis = self.analyze_performance()
        current_metrics = self.metrics.copy()

        # ベースラインを読み込み
        self.load_metrics(baseline_filepath)
        baseline_analysis = self.analyze_performance()

        # メトリクスを復元
        self.metrics = current_metrics

        # 比較結果を計算
        comparison = {
            "execution_time_change": {
                "average": current_analysis["execution_time"]["average"]
                - baseline_analysis["execution_time"]["average"],
                "max": current_analysis["execution_time"]["max"] - baseline_analysis["execution_time"]["max"],
                "percentage": (
                    (current_analysis["execution_time"]["average"] / baseline_analysis["execution_time"]["average"]) - 1
                )
                * 100,
            },
            "memory_usage_change": {
                "average": current_analysis["memory_usage"]["average"] - baseline_analysis["memory_usage"]["average"],
                "max": current_analysis["memory_usage"]["max"] - baseline_analysis["memory_usage"]["max"],
                "percentage": (
                    (current_analysis["memory_usage"]["average"] / baseline_analysis["memory_usage"]["average"]) - 1
                )
                * 100,
            },
            "success_rate_change": current_analysis["success_rate"] - baseline_analysis["success_rate"],
            "regression_detected": False,
        }

        # 回帰の検出
        regression_threshold = 0.2  # 20%の悪化で回帰とみなす

        if (
            comparison["execution_time_change"]["percentage"] > regression_threshold * 100
            or comparison["memory_usage_change"]["percentage"] > regression_threshold * 100
            or comparison["success_rate_change"] < -0.05
        ):  # 成功率5%以上の低下
            comparison["regression_detected"] = True

        comparison["current"] = current_analysis
        comparison["baseline"] = baseline_analysis

        return comparison

    def generate_report(self) -> str:
        """
        パフォーマンスレポートを生成

        Returns:
            レポート文字列
        """
        analysis = self.analyze_performance()

        report = f"""
# テストパフォーマンスレポート

## 概要
- 総テスト数: {analysis["total_tests"]}
- 成功テスト数: {analysis["successful_tests"]}
- 成功率: {analysis["success_rate"]:.2%}

## 実行時間
- 平均: {analysis["execution_time"]["average"]:.2f}秒
- 最大: {analysis["execution_time"]["max"]:.2f}秒
- 最小: {analysis["execution_time"]["min"]:.2f}秒
- 合計: {analysis["execution_time"]["total"]:.2f}秒

## メモリ使用量
- 平均: {analysis["memory_usage"]["average"]:.2f}MB
- 最大: {analysis["memory_usage"]["max"]:.2f}MB
- 最小: {analysis["memory_usage"]["min"]:.2f}MB

## CPU使用率
- 平均: {analysis["cpu_usage"]["average"]:.1f}%
- 最大: {analysis["cpu_usage"]["max"]:.1f}%
- 最小: {analysis["cpu_usage"]["min"]:.1f}%

## ベンチマーク結果
"""

        if analysis["benchmark_passed"]:
            report += "✅ 全てのベンチマークをクリア\n"
        else:
            report += "❌ ベンチマーク違反が検出されました:\n"
            for violation in analysis["benchmark_violations"]:
                report += f"  - {violation}\n"

        # 失敗したテストの詳細
        failed_tests = [m for m in self.metrics if not m.success]
        if failed_tests:
            report += "\n## 失敗したテスト\n"
            for test in failed_tests:
                report += f"- {test.test_name}: {test.error_message}\n"

        return report


def run_coverage_improvement_verification():
    """テストカバレッジ向上の検証を実行"""
    monitor = PerformanceMonitor()

    # 新規追加されたテストを実行
    new_tests = [
        "tests/unit/commands/test_analyze.py::TestAnalyzeInteractiveMode",
        "tests/unit/ai/test_integration.py::TestAIIntegrationCore",
        "tests/unit/ai/test_error_handler.py::TestErrorTypeHandling",
    ]

    print("新規テストのパフォーマンス検証を開始...")
    metrics = monitor.run_test_suite_monitoring(new_tests)

    # 結果を保存
    results_file = monitor.save_metrics("coverage_improvement_metrics.json")
    print(f"結果を保存しました: {results_file}")

    # レポートを生成
    report = monitor.generate_report()
    report_file = monitor.results_dir / "performance_report.md"
    report_file.write_text(report, encoding="utf-8")
    print(f"レポートを生成しました: {report_file}")

    # 分析結果を返す
    return monitor.analyze_performance()


if __name__ == "__main__":
    # スタンドアロン実行時のテスト
    results = run_coverage_improvement_verification()
    print(json.dumps(results, indent=2, ensure_ascii=False))
