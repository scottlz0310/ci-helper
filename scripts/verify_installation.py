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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        else:
            return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def check_file_exists(file_path: str, description: str) -> bool:
    """ファイルの存在を確認"""
    if Path(file_path).exists():
        return True
    else:
        return False


def main() -> int:
    """メイン検証プロセス"""

    checks: list[bool] = []

    # 基本コマンドの確認
    checks.append(run_command(["ci-run", "--version"], "ci-run バージョン確認"))

    checks.append(run_command(["ci-run", "--help"], "ci-run ヘルプ表示"))

    # 各サブコマンドのヘルプ確認
    subcommands = ["init", "doctor", "test", "logs", "clean", "secrets"]
    for cmd in subcommands:
        checks.append(run_command(["ci-run", cmd, "--help"], f"ci-run {cmd} ヘルプ表示"))

    # 依存関係の確認
    dependencies: list[tuple[list[str], str]] = [
        (["python3", "--version"], "Python バージョン確認"),
        (["uv", "--version"], "uv バージョン確認"),
    ]

    for dependency in dependencies:
        cmd, desc = dependency  # type: ignore[assignment]
        checks.append(run_command(cmd, desc))  # type: ignore[arg-type]

    # オプション: act と Docker の確認（失敗しても続行）
    optional_deps: list[tuple[list[str], str]] = [
        (["act", "--version"], "act バージョン確認（オプション）"),
        (["docker", "--version"], "Docker バージョン確認（オプション）"),
    ]

    for optional_dep in optional_deps:
        cmd, desc = optional_dep  # type: ignore[assignment]
        run_command(cmd, desc)  # type: ignore[arg-type]  # 結果は checks に含めない

    # 重要なファイルの確認
    important_files: list[tuple[str, str]] = [
        ("README.md", "README ファイル"),
        ("LICENSE", "ライセンス ファイル"),
        ("pyproject.toml", "プロジェクト設定ファイル"),
        ("src/ci_helper/__init__.py", "メインパッケージ"),
        ("src/ci_helper/cli.py", "CLI エントリーポイント"),
    ]

    for file_path, desc in important_files:
        checks.append(check_file_exists(file_path, desc))

    # 結果のサマリー
    passed = sum(checks)
    total = len(checks)

    if passed == total:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
