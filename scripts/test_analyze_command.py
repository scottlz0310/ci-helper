#!/usr/bin/env python3
"""
analyze コマンドの実環境テスト

ci-run analyze コマンドが実際の環境で正常に動作することを確認します。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def create_test_log_file() -> Path:
    """テスト用のログファイルを作成"""
    content = """
=== CI/CD Test Failure Log ===
2024-01-15 10:30:45 [INFO] Starting test execution
2024-01-15 10:30:46 [INFO] Running pytest tests
2024-01-15 10:30:47 [ERROR] Test failed: test_user_authentication
2024-01-15 10:30:47 [ERROR] AssertionError: Expected status code 200, got 401
2024-01-15 10:30:47 [ERROR] File: tests/test_auth.py, Line: 45
2024-01-15 10:30:47 [ERROR] Function: test_login_with_valid_credentials
2024-01-15 10:30:48 [INFO] Test execution completed with 1 failure

=== Build Error ===
2024-01-15 10:31:00 [ERROR] Build failed
2024-01-15 10:31:00 [ERROR] SyntaxError: invalid syntax
2024-01-15 10:31:00 [ERROR] File: src/main.py, Line: 23
2024-01-15 10:31:00 [ERROR] Missing closing parenthesis
"""

    temp_file = Path(tempfile.mktemp(suffix=".log"))
    temp_file.write_text(content.strip())
    return temp_file


def test_analyze_command_help():
    """analyze コマンドのヘルプ表示テスト"""
    print("Testing: ci-run analyze --help")

    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✓ Help command succeeded")
            print("Help output preview:")
            print(result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
            return True
        else:
            print(f"✗ Help command failed with exit code {result.returncode}")
            print("STDERR:", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("✗ Help command timed out")
        return False
    except Exception as e:
        print(f"✗ Help command error: {e}")
        return False


def test_analyze_command_with_log_file():
    """ログファイルを指定した analyze コマンドのテスト"""
    print("\nTesting: ci-run analyze --log <file>")

    # テスト用ログファイルを作成
    log_file = create_test_log_file()

    try:
        # APIキーが設定されているかチェック
        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

        if not has_api_key:
            print("⚠ No API keys found, testing with --dry-run equivalent")
            # APIキーがない場合は、エラーが期待される
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--log", str(log_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # APIキーエラーが期待される
            if result.returncode != 0 and ("APIキー" in result.stderr or "API key" in result.stderr):
                print("✓ Expected API key error occurred")
                return True
            else:
                print(f"✗ Unexpected result: exit_code={result.returncode}")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                return False
        else:
            print("✓ API keys found, testing actual analysis")
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--log", str(log_file), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                print("✓ Analysis command succeeded")
                print("Output preview:")
                print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)
                return True
            else:
                print(f"✗ Analysis command failed with exit code {result.returncode}")
                print("STDERR:", result.stderr)
                return False

    except subprocess.TimeoutExpired:
        print("✗ Analysis command timed out")
        return False
    except Exception as e:
        print(f"✗ Analysis command error: {e}")
        return False
    finally:
        # クリーンアップ
        try:
            log_file.unlink()
        except Exception:
            pass


def test_analyze_command_stats():
    """analyze コマンドの統計表示テスト"""
    print("\nTesting: ci-run analyze --stats")

    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--stats"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # 統計表示は初回実行時は空でも正常
        if result.returncode == 0:
            print("✓ Stats command succeeded")
            print("Stats output:")
            print(result.stdout)
            return True
        else:
            print(f"✗ Stats command failed with exit code {result.returncode}")
            print("STDERR:", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("✗ Stats command timed out")
        return False
    except Exception as e:
        print(f"✗ Stats command error: {e}")
        return False


def test_analyze_command_invalid_options():
    """analyze コマンドの無効なオプションテスト"""
    print("\nTesting: ci-run analyze with invalid options")

    test_cases = [
        {"name": "invalid provider", "args": ["--provider", "invalid_provider"], "expect_error": True},
        {"name": "non-existent log file", "args": ["--log", "/non/existent/file.log"], "expect_error": True},
        {"name": "invalid format", "args": ["--format", "invalid_format"], "expect_error": True},
    ]

    success_count = 0

    for test_case in test_cases:
        print(f"  Testing: {test_case['name']}")

        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze"] + test_case["args"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if test_case["expect_error"]:
                if result.returncode != 0:
                    print(f"    ✓ Expected error occurred (exit code: {result.returncode})")
                    success_count += 1
                else:
                    print("    ✗ Expected error but command succeeded")
            else:
                if result.returncode == 0:
                    print("    ✓ Command succeeded as expected")
                    success_count += 1
                else:
                    print(f"    ✗ Command failed unexpectedly (exit code: {result.returncode})")

        except subprocess.TimeoutExpired:
            print("    ✗ Command timed out")
        except Exception as e:
            print(f"    ✗ Command error: {e}")

    return success_count == len(test_cases)


def main():
    """メイン関数"""
    print("=== CI Helper Analyze Command Real Environment Test ===")
    print()

    # 環境情報を表示
    print("Environment:")
    print(f"  Python: {sys.version}")
    print(f"  Working directory: {os.getcwd()}")
    print(f"  OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else 'Not set'}")
    print(f"  ANTHROPIC_API_KEY: {'Set' if os.getenv('ANTHROPIC_API_KEY') else 'Not set'}")
    print()

    # テストを実行
    tests = [
        ("Help Command", test_analyze_command_help),
        ("Log File Analysis", test_analyze_command_with_log_file),
        ("Stats Display", test_analyze_command_stats),
        ("Invalid Options", test_analyze_command_invalid_options),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        print("-" * 50)

        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

        print()

    # 結果サマリー
    print("=== Test Results Summary ===")
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"  {status}: {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed ({passed / total * 100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
