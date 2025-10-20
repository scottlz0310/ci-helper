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
    print(f"実行中: {' '.join(cmd)}")
    start_time = time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        end_time = time.time()

        print(f"完了 ({end_time - start_time:.2f}秒): 終了コード {result.returncode}")
        return result
    except subprocess.TimeoutExpired:
        print(f"タイムアウト: {timeout}秒")
        return None


def verify_test_discovery():
    """新規テストがpytestで発見可能であることを確認"""
    print("\n=== テスト発見確認 ===")

    test_files = [
        "tests/unit/ai/test_integration.py",
        "tests/unit/ai/test_error_handler.py",
        "tests/unit/commands/test_analyze.py",
    ]

    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"❌ テストファイルが存在しません: {test_file}")
            return False
        print(f"✅ テストファイル確認: {test_file}")

    # pytestでテスト発見を確認
    result = run_command(["uv", "run", "pytest", "--collect-only", "-q"] + test_files)

    if result and result.returncode == 0:
        print("✅ 全てのテストがpytestで発見可能です")
        return True
    else:
        print("❌ テスト発見に失敗しました")
        return False


def verify_basic_test_execution():
    """基本的なテスト実行を確認"""
    print("\n=== 基本テスト実行確認 ===")

    # 軽量なテストを実行
    basic_tests = [
        "tests/unit/ai/test_integration.py::TestAIIntegrationCore::test_initialization_with_config",
        "tests/unit/test_config.py::TestConfigFileLoading::test_default_config",
    ]

    success_count = 0

    for test in basic_tests:
        result = run_command(["uv", "run", "pytest", test, "--tb=short"], timeout=30)

        if result and result.returncode == 0:
            print(f"✅ テスト成功: {test}")
            success_count += 1
        else:
            print(f"❌ テスト失敗: {test}")

    success_rate = success_count / len(basic_tests)
    print(f"\n基本テスト成功率: {success_rate:.1%} ({success_count}/{len(basic_tests)})")

    return success_rate >= 0.8  # 80%以上の成功率を要求


def verify_external_dependencies():
    """外部依存が最小化されていることを確認"""
    print("\n=== 外部依存確認 ===")

    test_files = ["tests/unit/ai/test_integration.py", "tests/unit/ai/test_error_handler.py"]

    forbidden_patterns = ["openai.OpenAI(", "anthropic.Anthropic(", "requests.get(", "requests.post("]

    for test_file in test_files:
        content = Path(test_file).read_text(encoding="utf-8")

        for pattern in forbidden_patterns:
            if pattern in content:
                print(f"❌ 実際のAPI呼び出しが検出されました: {test_file} - {pattern}")
                return False

    print("✅ 外部依存が適切にモック化されています")
    return True


def verify_coverage_integration():
    """カバレッジ統合を確認"""
    print("\n=== カバレッジ統合確認 ===")

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
        print("✅ カバレッジレポートが正常に生成されました")
        return True
    else:
        print("❌ カバレッジレポート生成に失敗しました")
        return False


def verify_parallel_execution():
    """並列実行互換性を確認"""
    print("\n=== 並列実行確認 ===")

    result = run_command(
        ["uv", "run", "pytest", "tests/unit/test_config.py::TestConfigFileLoading", "-n", "2", "--tb=short"], timeout=45
    )

    if result and result.returncode == 0:
        print("✅ 並列実行が正常に動作しました")
        return True
    else:
        print("❌ 並列実行に失敗しました")
        return False


def main():
    """メイン関数"""
    print("CI/CD統合検証を開始...")
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
        except Exception as e:
            print(f"❌ {check_name}でエラー: {e}")
            results[check_name] = False

    # 結果サマリー
    end_time = time.time()
    total_time = end_time - start_time

    print("\n=== 検証結果サマリー ===")
    print(f"総実行時間: {total_time:.2f}秒")

    passed_checks = sum(1 for result in results.values() if result)
    total_checks = len(results)

    for check_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{check_name}: {status}")

    success_rate = passed_checks / total_checks
    print(f"\n成功率: {success_rate:.1%} ({passed_checks}/{total_checks})")

    if success_rate >= 0.8:  # 80%以上で成功とみなす
        print("✅ CI/CD統合検証が成功しました")
        sys.exit(0)
    else:
        print("❌ CI/CD統合検証が失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
