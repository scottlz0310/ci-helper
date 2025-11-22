#!/usr/bin/env python3
"""
CI/CDテスト実行スクリプト

このスクリプトは、CI/CD環境でのテスト実行を最適化し、
パフォーマンス監視と品質保証を提供します。
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# プロジェクトルートをPythonパスに追加（標準ライブラリインポート後に配置）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ローカルインポート（パス設定後）
from tests.utils.performance_monitor import PerformanceMonitor  # noqa: E402


def run_command(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """
    コマンドを実行

    Args:
        cmd: 実行するコマンド
        timeout: タイムアウト（秒）

    Returns:
        実行結果
    """
    time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=project_root)

        time.time()

        if result.returncode != 0:
            pass

        return result

    except subprocess.TimeoutExpired:
        raise


def run_unit_tests(coverage: bool = True, parallel: bool = True) -> bool:
    """
    ユニットテストを実行

    Args:
        coverage: カバレッジ測定を有効にするか
        parallel: 並列実行を有効にするか

    Returns:
        成功したかどうか
    """

    cmd = ["uv", "run", "pytest", "tests/unit/"]

    if coverage:
        cmd.extend(
            [
                "--cov=ci_helper",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-report=json:coverage.json",
            ]
        )

    if parallel:
        cmd.extend(["-n", "logical"])

    cmd.extend(["-v", "--tb=short"])

    result = run_command(cmd)
    return result.returncode == 0


def run_integration_tests() -> bool:
    """
    統合テストを実行

    Returns:
        成功したかどうか
    """

    cmd = ["uv", "run", "pytest", "tests/integration/", "-v", "--tb=short", "-m", "not slow"]

    result = run_command(cmd)
    return result.returncode == 0


def run_performance_tests() -> dict:
    """
    パフォーマンステストを実行

    Returns:
        パフォーマンス結果
    """

    monitor = PerformanceMonitor(Path("test_results"))

    # 重要なテストモジュールを監視付きで実行
    critical_tests = [
        "tests/unit/commands/test_analyze.py::TestAnalyzeInteractiveMode::test_interactive_session_start",
        "tests/unit/ai/test_integration.py::TestAIIntegrationCore::test_initialization_with_config",
        "tests/unit/ai/test_error_handler.py::TestErrorTypeHandling::test_api_key_error_handling",
    ]

    monitor.run_test_suite_monitoring(critical_tests)

    # 結果を保存
    monitor.save_metrics("ci_performance_metrics.json")

    # レポートを生成
    report = monitor.generate_report()
    report_file = Path("test_results") / "ci_performance_report.md"
    report_file.write_text(report, encoding="utf-8")

    return monitor.analyze_performance()


def check_coverage_targets() -> bool:
    """
    カバレッジ目標の達成を確認

    Returns:
        目標を達成したかどうか
    """

    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        return False

    with open(coverage_file) as f:
        coverage_data = json.load(f)

    # 目標カバレッジ
    targets = {
        "src/ci_helper/commands/analyze.py": 15,  # 現在9%から向上目標
        "src/ci_helper/ai/integration.py": 15,  # 現在11%から向上目標
        "src/ci_helper/ai/error_handler.py": 25,  # 現在23%から向上目標
    }

    all_targets_met = True

    for file_path, target_coverage in targets.items():
        if file_path in coverage_data["files"]:
            actual_coverage = coverage_data["files"][file_path]["summary"]["percent_covered"]

            if actual_coverage < target_coverage:
                all_targets_met = False
            else:
                pass
        else:
            all_targets_met = False

    # 全体カバレッジも確認
    total_coverage = coverage_data["totals"]["percent_covered"]
    total_target = 20.0  # 現在20%から向上目標

    if total_coverage >= total_target:
        pass
    else:
        all_targets_met = False

    return all_targets_met


def run_linting_and_formatting() -> bool:
    """
    リンティングとフォーマットチェックを実行

    Returns:
        成功したかどうか
    """

    # Ruffチェック
    ruff_check = run_command(["uv", "run", "ruff", "check", "src/", "tests/"])
    if ruff_check.returncode != 0:
        return False

    # Ruffフォーマットチェック
    ruff_format = run_command(["uv", "run", "ruff", "format", "--check", "src/", "tests/"])
    if ruff_format.returncode != 0:
        return False

    # basedpyright型チェック
    basedpyright_check = run_command(["uv", "run", "basedpyright", "src/ci_helper"])
    if basedpyright_check.returncode != 0:
        return False

    return True


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="CI/CDテスト実行スクリプト")
    parser.add_argument("--skip-unit", action="store_true", help="ユニットテストをスキップ")
    parser.add_argument("--skip-integration", action="store_true", help="統合テストをスキップ")
    parser.add_argument("--skip-performance", action="store_true", help="パフォーマンステストをスキップ")
    parser.add_argument("--skip-linting", action="store_true", help="リンティングをスキップ")
    parser.add_argument("--no-coverage", action="store_true", help="カバレッジ測定を無効化")
    parser.add_argument("--no-parallel", action="store_true", help="並列実行を無効化")
    parser.add_argument("--fast", action="store_true", help="高速モード（最小限のテストのみ）")

    args = parser.parse_args()

    start_time = time.time()

    success = True

    # 高速モードの場合は最小限のテストのみ
    if args.fast:
        args.skip_integration = True
        args.skip_performance = True
        args.no_parallel = True

    # リンティング・フォーマットチェック
    if not args.skip_linting:
        if not run_linting_and_formatting():
            success = False

    # ユニットテスト
    if not args.skip_unit:
        if not run_unit_tests(coverage=not args.no_coverage, parallel=not args.no_parallel):
            success = False

    # 統合テスト
    if not args.skip_integration:
        if not run_integration_tests():
            success = False

    # パフォーマンステスト
    if not args.skip_performance:
        try:
            performance_results = run_performance_tests()
            if not performance_results.get("benchmark_passed", False):
                success = False
        except Exception:
            success = False

    # カバレッジ目標確認
    if not args.no_coverage and not args.skip_unit:
        if not check_coverage_targets():
            success = False

    # 結果サマリー
    end_time = time.time()
    end_time - start_time

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
