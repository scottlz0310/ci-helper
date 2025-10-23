#!/usr/bin/env python3
"""
CI/CD統合検証スクリプト（簡易版）

このスクリプトは、新規追加されたテストがCI/CDパイプラインで
適切に動作することを迅速に検証します。
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, timeout=60):
    """コマンドを実行して結果を返す"""
    time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        time.time()

        return result
    except subprocess.TimeoutExpired:
        return None


def verify_test_discovery():
    """新規テストがpytestで発見可能であることを確認"""

    test_files = [
        "tests/unit/ai/test_integration.py",
        "tests/unit/ai/test_error_handler.py",
        "tests/unit/commands/test_analyze.py",
    ]

    for test_file in test_files:
        if not Path(test_file).exists():
            return False

    # pytestでテスト発見を確認
    result = run_command(["uv", "run", "pytest", "--collect-only", "-q", *test_files])

    if result and result.returncode == 0:
        return True
    else:
        return False


def verify_basic_test_execution():
    """基本的なテスト実行を確認"""

    # 軽量なテストを実行
    basic_tests = [
        "tests/unit/ai/test_integration.py::TestAIIntegrationCore::test_initialization_with_config",
        "tests/unit/test_config.py::TestConfigFileLoading::test_default_config",
    ]

    success_count = 0

    for test in basic_tests:
        result = run_command(["uv", "run", "pytest", test, "--tb=short"], timeout=30)

        if result and result.returncode == 0:
            success_count += 1
        else:
            pass

    success_rate = success_count / len(basic_tests)

    return success_rate >= 0.8  # 80%以上の成功率を要求


def verify_external_dependencies():
    """外部依存が最小化されていることを確認"""

    test_files = ["tests/unit/ai/test_integration.py", "tests/unit/ai/test_error_handler.py"]

    forbidden_patterns = ["openai.OpenAI(", "anthropic.Anthropic(", "requests.get(", "requests.post("]

    for test_file in test_files:
        content = Path(test_file).read_text(encoding="utf-8")

        for pattern in forbidden_patterns:
            if pattern in content:
                return False

    return True


def verify_coverage_integration():
    """カバレッジ統合を確認"""

    result = run_command(
        [
            "uv",
            "run",
            "pytest",
            "tests/unit/test_config.py::TestConfigFileLoading::test_default_config",
            "--cov=ci_helper.utils.config",
            "--cov-report=term",
        ],
        timeout=30,
    )

    if result and result.returncode == 0 and "%" in result.stdout:
        return True
    else:
        return False


def verify_parallel_execution():
    """並列実行互換性を確認"""

    result = run_command(
        ["uv", "run", "pytest", "tests/unit/test_config.py::TestConfigFileLoading", "-n", "2", "--tb=short"], timeout=45
    )

    if result and result.returncode == 0:
        return True
    else:
        return False


def main():
    """メイン関数"""
    start_time = time.time()

    checks = [
        ("テスト発見", verify_test_discovery),
        ("基本テスト実行", verify_basic_test_execution),
        ("外部依存確認", verify_external_dependencies),
        ("カバレッジ統合", verify_coverage_integration),
        ("並列実行", verify_parallel_execution),
    ]

    results = {}

    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception:
            results[check_name] = False

    # 結果サマリー
    end_time = time.time()
    end_time - start_time

    passed_checks = sum(1 for result in results.values() if result)
    total_checks = len(results)

    for _check_name, _result in results.items():
        pass

    success_rate = passed_checks / total_checks

    if success_rate >= 0.8:  # 80%以上で成功とみなす
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
