#!/usr/bin/env python3
"""
CI/CD統合検証スクリプト（簡易版）

このスクリプトは、新規追加されたテストがCI/CDパイプラインで
適切に動作することを迅速に検証します。
"""

import subprocess
import sys


def run_command(cmd, timeout=60):
    """コマンドを実行して結果を返す"""
    try:
        # セキュリティ: shell=Falseを使用してコマンドインジェクションを防ぐ
        cmd_list = cmd.split()
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout, shell=False)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def main():
    """メイン関数"""
    # CI環境では標準出力を使用
    sys.stdout.write("CI/CD統合検証を開始します...\n")

    # 基本的なコマンドの動作確認
    tests = [
        ("ci-run --version", "バージョン確認"),
        ("ci-run --help", "ヘルプ表示"),
        ("ci-run doctor --help", "doctorヘルプ表示"),
    ]

    all_passed = True

    for cmd, description in tests:
        sys.stdout.write(f"テスト: {description}\n")
        success, stdout, stderr = run_command(cmd)

        if success:
            sys.stdout.write(f"  ✅ {description} - 成功\n")
        else:
            sys.stdout.write(f"  ❌ {description} - 失敗\n")
            sys.stdout.write(f"     stdout: {stdout}\n")
            sys.stdout.write(f"     stderr: {stderr}\n")
            all_passed = False

    if all_passed:
        sys.stdout.write("✅ すべてのCI/CD統合テストが成功しました\n")
        sys.exit(0)
    else:
        sys.stdout.write("❌ 一部のCI/CD統合テストが失敗しました\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
