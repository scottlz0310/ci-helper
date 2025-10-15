#!/usr/bin/env python3
"""
ci-helper インストール検証スクリプト

このスクリプトは、ci-helperが正しくインストールされ、
基本的な機能が動作することを確認します。
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """コマンドを実行し、結果を確認"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ {description} - 成功")
            return True
        else:
            print(f"❌ {description} - 失敗")
            print(f"   エラー: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - タイムアウト")
        return False
    except Exception as e:
        print(f"💥 {description} - 例外: {e}")
        return False


def check_file_exists(file_path: str, description: str) -> bool:
    """ファイルの存在を確認"""
    print(f"📁 {description}...")
    if Path(file_path).exists():
        print(f"✅ {description} - 存在")
        return True
    else:
        print(f"❌ {description} - 存在しない")
        return False


def main():
    """メイン検証プロセス"""
    print("🚀 ci-helper インストール検証を開始します\n")

    checks = []

    # 基本コマンドの確認
    checks.append(run_command(["ci-run", "--version"], "ci-run バージョン確認"))

    checks.append(run_command(["ci-run", "--help"], "ci-run ヘルプ表示"))

    # 各サブコマンドのヘルプ確認
    subcommands = ["init", "doctor", "test", "logs", "clean", "secrets"]
    for cmd in subcommands:
        checks.append(run_command(["ci-run", cmd, "--help"], f"ci-run {cmd} ヘルプ表示"))

    # 依存関係の確認
    dependencies = [
        (["python3", "--version"], "Python バージョン確認"),
        (["uv", "--version"], "uv バージョン確認"),
    ]

    for cmd, desc in dependencies:
        checks.append(run_command(cmd, desc))

    # オプション: act と Docker の確認（失敗しても続行）
    optional_deps = [
        (["act", "--version"], "act バージョン確認（オプション）"),
        (["docker", "--version"], "Docker バージョン確認（オプション）"),
    ]

    print("\n📋 オプション依存関係の確認:")
    for cmd, desc in optional_deps:
        run_command(cmd, desc)  # 結果は checks に含めない

    # 重要なファイルの確認
    important_files = [
        ("README.md", "README ファイル"),
        ("LICENSE", "ライセンス ファイル"),
        ("pyproject.toml", "プロジェクト設定ファイル"),
        ("src/ci_helper/__init__.py", "メインパッケージ"),
        ("src/ci_helper/cli.py", "CLI エントリーポイント"),
    ]

    print("\n📁 重要ファイルの確認:")
    for file_path, desc in important_files:
        checks.append(check_file_exists(file_path, desc))

    # 結果のサマリー
    print("\n📊 検証結果:")
    passed = sum(checks)
    total = len(checks)

    print(f"✅ 成功: {passed}/{total}")
    print(f"❌ 失敗: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 すべての検証が成功しました！")
        print("ci-helper は正常にインストールされています。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 個の検証が失敗しました。")
        print("インストールに問題がある可能性があります。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
