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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(content.strip())
        temp_file = Path(f.name)
    return temp_file


def test_analyze_command_help():
    """analyze コマンドのヘルプ表示テスト"""

    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True
        else:
            return False

    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def test_analyze_command_with_log_file():
    """ログファイルを指定した analyze コマンドのテスト"""

    # テスト用ログファイルを作成
    log_file = create_test_log_file()

    try:
        # APIキーが設定されているかチェック
        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

        if not has_api_key:
            # APIキーがない場合は、エラーが期待される
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--log", str(log_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # APIキーエラーが期待される
            if result.returncode != 0 and ("APIキー" in result.stderr or "API key" in result.stderr):
                return True
            else:
                return False
        else:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--log", str(log_file), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return True
            else:
                return False

    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False
    finally:
        # クリーンアップ
        try:
            log_file.unlink()
        except Exception:
            pass


def test_analyze_command_stats():
    """analyze コマンドの統計表示テスト"""

    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "ci_helper.cli", "analyze", "--stats"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # 統計表示は初回実行時は空でも正常
        if result.returncode == 0:
            return True
        else:
            return False

    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def test_analyze_command_invalid_options():
    """analyze コマンドの無効なオプションテスト"""

    test_cases = [
        {"name": "invalid provider", "args": ["--provider", "invalid_provider"], "expect_error": True},
        {"name": "non-existent log file", "args": ["--log", "/non/existent/file.log"], "expect_error": True},
        {"name": "invalid format", "args": ["--format", "invalid_format"], "expect_error": True},
    ]

    success_count = 0

    for test_case in test_cases:
        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "ci_helper.cli", "analyze"] + test_case["args"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if test_case["expect_error"]:
                if result.returncode != 0:
                    success_count += 1
                else:
                    pass
            else:
                if result.returncode == 0:
                    success_count += 1
                else:
                    pass

        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    return success_count == len(test_cases)


def main():
    """メイン関数"""

    # 環境情報を表示

    # テストを実行
    tests = [
        ("Help Command", test_analyze_command_help),
        ("Log File Analysis", test_analyze_command_with_log_file),
        ("Stats Display", test_analyze_command_stats),
        ("Invalid Options", test_analyze_command_invalid_options),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception:
            results.append((test_name, False))

    # 結果サマリー
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for _test_name, _success in results:
        pass

    if passed == total:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
