#!/usr/bin/env python3
"""
修正テンプレートの検証スクリプト

このスクリプトは、修正テンプレートファイルの構造と整合性を検証します。
"""

import json
from pathlib import Path


def load_json_file(file_path: Path) -> dict:
    """JSONファイルを読み込む"""
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ エラー: {file_path} の読み込みに失敗: {e}")
        return {}


def validate_template_structure(template: dict, template_id: str) -> list[str]:
    """テンプレート構造を検証"""
    errors = []

    # 必須フィールドの確認
    required_fields = [
        "id",
        "name",
        "description",
        "pattern_ids",
        "fix_steps",
        "risk_level",
        "estimated_time",
        "success_rate",
        "prerequisites",
        "validation_steps",
    ]

    for field in required_fields:
        if field not in template:
            errors.append(f"必須フィールド '{field}' が不足")

    # IDの一致確認
    if template.get("id") != template_id:
        errors.append(f"テンプレートID不一致: {template.get('id')} != {template_id}")

    # リスクレベルの確認
    valid_risk_levels = ["low", "medium", "high"]
    if template.get("risk_level") not in valid_risk_levels:
        errors.append(f"無効なリスクレベル: {template.get('risk_level')}")

    # 成功率の確認
    success_rate = template.get("success_rate")
    if not isinstance(success_rate, (int, float)) or not (0.0 <= success_rate <= 1.0):
        errors.append(f"無効な成功率: {success_rate}")

    # fix_stepsの確認
    fix_steps = template.get("fix_steps", [])
    if not isinstance(fix_steps, list) or len(fix_steps) == 0:
        errors.append("fix_stepsが空または無効")
    else:
        for i, step in enumerate(fix_steps):
            if not isinstance(step, dict):
                errors.append(f"fix_steps[{i}]が辞書ではない")
                continue

            if "type" not in step:
                errors.append(f"fix_steps[{i}]にtypeが不足")
            elif step["type"] not in ["file_modification", "command", "config_change"]:
                errors.append(f"fix_steps[{i}]の無効なtype: {step['type']}")

            if "description" not in step:
                errors.append(f"fix_steps[{i}]にdescriptionが不足")

            if "validation" not in step:
                errors.append(f"fix_steps[{i}]にvalidationが不足")

    return errors


def validate_template_files() -> bool:
    """すべてのテンプレートファイルを検証"""
    templates_dir = Path(__file__).parent
    template_files = [
        "permission_fixes.json",
        "network_fixes.json",
        "config_fixes.json",
        "build_fixes.json",
        "dependency_fixes.json",
        "test_fixes.json",
    ]

    all_template_ids = set()
    all_pattern_ids = set()
    total_templates = 0
    total_errors = 0

    print("🔍 修正テンプレートファイルの検証を開始...")
    print()

    for file_name in template_files:
        file_path = templates_dir / file_name
        if not file_path.exists():
            print(f"❌ ファイルが見つかりません: {file_name}")
            total_errors += 1
            continue

        print(f"📄 {file_name} を検証中...")

        data = load_json_file(file_path)
        if not data:
            total_errors += 1
            continue

        templates = data.get("templates", [])
        file_errors = 0

        for template in templates:
            template_id = template.get("id", "unknown")
            total_templates += 1

            # 重複ID確認
            if template_id in all_template_ids:
                print(f"  ❌ 重複するテンプレートID: {template_id}")
                file_errors += 1
            else:
                all_template_ids.add(template_id)

            # パターンID収集
            pattern_ids = template.get("pattern_ids", [])
            all_pattern_ids.update(pattern_ids)

            # テンプレート構造検証
            errors = validate_template_structure(template, template_id)
            if errors:
                print(f"  ❌ テンプレート '{template_id}' のエラー:")
                for error in errors:
                    print(f"    - {error}")
                file_errors += len(errors)
            else:
                print(f"  ✅ テンプレート '{template_id}' は正常")

        if file_errors == 0:
            print(f"  ✅ {file_name} は正常 ({len(templates)}個のテンプレート)")
        else:
            print(f"  ❌ {file_name} に {file_errors}個のエラー")

        total_errors += file_errors
        print()

    # インデックスファイルの検証
    print("📋 template_index.json を検証中...")
    index_path = templates_dir / "template_index.json"
    if index_path.exists():
        index_data = load_json_file(index_path)
        if index_data:
            # テンプレート数の確認
            index_total = index_data.get("metadata", {}).get("total_templates", 0)
            if index_total != total_templates:
                print(f"  ❌ インデックスのテンプレート数不一致: {index_total} != {total_templates}")
                total_errors += 1

            # パターンマッピングの確認
            pattern_mapping = index_data.get("pattern_template_mapping", {})
            mapped_patterns = set(pattern_mapping.keys())

            missing_patterns = all_pattern_ids - mapped_patterns
            if missing_patterns:
                print(f"  ❌ マッピングされていないパターン: {missing_patterns}")
                total_errors += 1

            extra_patterns = mapped_patterns - all_pattern_ids
            if extra_patterns:
                print(f"  ⚠️  存在しないパターンのマッピング: {extra_patterns}")

            if total_errors == 0:
                print("  ✅ template_index.json は正常")
        else:
            total_errors += 1
    else:
        print("  ❌ template_index.json が見つかりません")
        total_errors += 1

    print()
    print("=" * 50)
    print("📊 検証結果:")
    print(f"  - 総テンプレート数: {total_templates}")
    print(f"  - ユニークなテンプレートID: {len(all_template_ids)}")
    print(f"  - 対応パターン数: {len(all_pattern_ids)}")
    print(f"  - 総エラー数: {total_errors}")

    if total_errors == 0:
        print("✅ すべてのテンプレートファイルが正常です！")
        return True
    else:
        print(f"❌ {total_errors}個のエラーが見つかりました。修正してください。")
        return False


def main():
    """メイン関数"""
    success = validate_template_files()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
