#!/usr/bin/env python3
"""
パターンデータベース検証スクリプト

このスクリプトは、パターンデータベースの整合性と構造を検証します。
"""

import json
import re
from pathlib import Path


def validate_pattern_structure(pattern: dict) -> list[str]:
    """個別パターンの構造を検証"""
    errors = []
    required_fields = [
        "id",
        "name",
        "category",
        "regex_patterns",
        "keywords",
        "context_requirements",
        "confidence_base",
        "success_rate",
        "created_at",
        "updated_at",
        "user_defined",
        "auto_generated",
        "source",
        "occurrence_count",
    ]

    for field in required_fields:
        if field not in pattern:
            errors.append(f"必須フィールド '{field}' が不足しています")

    # 信頼度の範囲チェック
    if "confidence_base" in pattern:
        if not 0.0 <= pattern["confidence_base"] <= 1.0:
            errors.append(f"confidence_base は 0.0-1.0 の範囲である必要があります: {pattern['confidence_base']}")

    # 成功率の範囲チェック
    if "success_rate" in pattern:
        if not 0.0 <= pattern["success_rate"] <= 1.0:
            errors.append(f"success_rate は 0.0-1.0 の範囲である必要があります: {pattern['success_rate']}")

    # 正規表現の検証
    if "regex_patterns" in pattern:
        for regex in pattern["regex_patterns"]:
            try:
                re.compile(regex)
            except re.error as e:
                errors.append(f"無効な正規表現 '{regex}': {e}")

    return errors


def validate_pattern_database() -> dict[str, list[str]]:
    """パターンデータベース全体を検証"""
    pattern_dir = Path("data/patterns")
    validation_results = {}
    all_pattern_ids: set[str] = set()

    # パターンファイルを検証
    pattern_files = [
        "ci_patterns.json",
        "build_patterns.json",
        "dependency_patterns.json",
        "test_patterns.json",
        "action_patterns.json",
    ]

    for file_name in pattern_files:
        file_path = pattern_dir / file_name
        errors = []

        if not file_path.exists():
            errors.append(f"ファイルが存在しません: {file_path}")
            validation_results[file_name] = errors
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if "patterns" not in data:
                errors.append("'patterns' キーが見つかりません")
                validation_results[file_name] = errors
                continue

            # 各パターンを検証
            for i, pattern in enumerate(data["patterns"]):
                pattern_errors = validate_pattern_structure(pattern)
                if pattern_errors:
                    errors.extend([f"パターン {i}: {error}" for error in pattern_errors])

                # パターンIDの重複チェック
                if "id" in pattern:
                    if pattern["id"] in all_pattern_ids:
                        errors.append(f"重複するパターンID: {pattern['id']}")
                    else:
                        all_pattern_ids.add(pattern["id"])

        except json.JSONDecodeError as e:
            errors.append(f"JSON解析エラー: {e}")
        except Exception as e:
            errors.append(f"予期しないエラー: {e}")

        validation_results[file_name] = errors

    # パターンインデックスファイルの検証
    index_file = pattern_dir / "pattern_index.json"
    if index_file.exists():
        try:
            with open(index_file, encoding="utf-8") as f:
                index_data = json.load(f)

            # インデックスファイルの整合性チェック
            index_errors = []
            if "categories" in index_data:
                indexed_patterns = set()
                for category, info in index_data["categories"].items():
                    if "patterns" in info:
                        indexed_patterns.update(info["patterns"])

                # インデックスされていないパターンをチェック
                missing_in_index = all_pattern_ids - indexed_patterns
                if missing_in_index:
                    index_errors.append(f"インデックスに含まれていないパターン: {missing_in_index}")

                # 存在しないパターンがインデックスされていないかチェック
                extra_in_index = indexed_patterns - all_pattern_ids
                if extra_in_index:
                    index_errors.append(f"存在しないパターンがインデックスされています: {extra_in_index}")

            validation_results["pattern_index.json"] = index_errors

        except Exception as e:
            validation_results["pattern_index.json"] = [f"インデックスファイルエラー: {e}"]

    return validation_results


def main():
    """メイン関数"""
    print("パターンデータベース検証を開始します...")

    results = validate_pattern_database()

    total_errors = 0
    for file_name, errors in results.items():
        if errors:
            print(f"\n❌ {file_name}:")
            for error in errors:
                print(f"  - {error}")
            total_errors += len(errors)
        else:
            print(f"✅ {file_name}: 検証成功")

    print(f"\n検証完了: {total_errors} 個のエラーが見つかりました")

    if total_errors == 0:
        print("🎉 パターンデータベースは正常です！")
        return 0
    else:
        print("⚠️  エラーを修正してください")
        return 1


if __name__ == "__main__":
    exit(main())
