# カバレッジ維持ガイド

## 概要

このドキュメントは、CI-Helperプロジェクトにおけるコードカバレッジの長期的な維持と改善のための指針を提供します。70%以上のカバレッジを持続的に維持し、新機能追加時にもカバレッジが低下しないようにするための戦略を説明します。

## カバレッジ維持の基本戦略

### 1. 継続的監視

#### CI/CDでのカバレッジチェック

```yaml
# .github/workflows/test.yml
name: Test and Coverage
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run tests with coverage
        run: |
          uv run pytest --cov=ci_helper --cov-report=xml --cov-fail-under=70

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

#### ローカル開発でのカバレッジ確認

```bash
# 基本的なカバレッジ確認
uv run pytest --cov=ci_helper --cov-report=term-missing

# HTMLレポートの生成
uv run pytest --cov=ci_helper --cov-report=html
open htmlcov/index.html

# 特定の閾値でのテスト
uv run pytest --cov=ci_helper --cov-fail-under=70
```

### 2. 新機能開発時のカバレッジ戦略

#### 機能追加前のベースライン確立

```bash
# 現在のカバレッジを記録
uv run pytest --cov=ci_helper --cov-report=json
cp coverage.json baseline_coverage.json
```

#### 新機能のテスト要件

新しい機能を追加する際は、以下の基準を満たすテストを作成する：

```python
# 新機能: パターン学習機能
class PatternLearner:
    def learn_from_feedback(self, feedback_data):
        """フィードバックからパターンを学習"""
        pass

    def update_pattern_weights(self, pattern_id, weight_delta):
        """パターンの重みを更新"""
        pass

# 対応するテスト（最低限の要件）
class TestPatternLearner:
    def test_learn_from_valid_feedback(self):
        """有効なフィードバックからの学習テスト"""
        learner = PatternLearner()
        feedback = {"pattern_id": "test", "success": True, "confidence": 0.8}

        result = learner.learn_from_feedback(feedback)

        assert result.patterns_updated > 0
        assert result.learning_score > 0.5

    def test_learn_from_invalid_feedback(self):
        """無効なフィードバックのエラーハンドリング"""
        learner = PatternLearner()

        with pytest.raises(InvalidFeedbackError):
            learner.learn_from_feedback({"invalid": "data"})

    def test_update_pattern_weights_boundary_values(self):
        """パターン重み更新の境界値テスト"""
        learner = PatternLearner()

        # 最大値での更新
        result = learner.update_pattern_weights("test", 1.0)
        assert result.new_weight <= 1.0

        # 最小値での更新
        result = learner.update_pattern_weights("test", -1.0)
        assert result.new_weight >= 0.0
```

### 3. カバレッジ低下の早期検出

#### プルリクエスト時のカバレッジ差分チェック

```python
# scripts/check_coverage_diff.py
import json
import sys

def check_coverage_diff(baseline_file, current_file, threshold=-2.0):
    """カバレッジの差分をチェック"""
    with open(baseline_file) as f:
        baseline = json.load(f)

    with open(current_file) as f:
        current = json.load(f)

    baseline_total = baseline['totals']['percent_covered']
    current_total = current['totals']['percent_covered']

    diff = current_total - baseline_total

    if diff < threshold:
        print(f"❌ カバレッジが{abs(diff):.1f}%低下しました")
        print(f"ベースライン: {baseline_total:.1f}%")
        print(f"現在: {current_total:.1f}%")

        # 低下したモジュールを特定
        for filename, current_data in current['files'].items():
            if filename in baseline['files']:
                baseline_coverage = baseline['files'][filename]['summary']['percent_covered']
                current_coverage = current_data['summary']['percent_covered']
                module_diff = current_coverage - baseline_coverage

                if module_diff < -5.0:  # 5%以上の低下
                    print(f"  📉 {filename}: {module_diff:.1f}%")

        sys.exit(1)
    else:
        print(f"✅ カバレッジ: {current_total:.1f}% (変化: {diff:+.1f}%)")

if __name__ == "__main__":
    check_coverage_diff("baseline_coverage.json", "coverage.json")
```

## モジュール別カバレッジ管理

### 1. 優先度別カバレッジ目標

```python
# coverage_targets.py
COVERAGE_TARGETS = {
    # 高優先度: ビジネスロジック
    "src/ci_helper/ai/pattern_engine.py": 85,
    "src/ci_helper/ai/fix_generator.py": 80,
    "src/ci_helper/ai/risk_calculator.py": 80,

    # 中優先度: 設定・管理
    "src/ci_helper/ai/auto_fix_config.py": 70,
    "src/ci_helper/ai/settings_manager.py": 70,
    "src/ci_helper/ai/custom_pattern_manager.py": 65,

    # 低優先度: ユーティリティ
    "src/ci_helper/formatters/streaming_formatter.py": 50,
    "src/ci_helper/utils/log_compressor.py": 45,

    # 除外対象: 主にデータ構造
    "src/ci_helper/ai/models.py": 30,
    "src/ci_helper/cli.py": 40,  # CLIエントリーポイント
}

def check_module_coverage(coverage_data):
    """モジュール別カバレッジ目標の達成状況をチェック"""
    issues = []

    for module_path, target in COVERAGE_TARGETS.items():
        if module_path in coverage_data['files']:
            actual = coverage_data['files'][module_path]['summary']['percent_covered']
            if actual < target:
                issues.append({
                    'module': module_path,
                    'target': target,
                    'actual': actual,
                    'gap': target - actual
                })

    return issues
```

### 2. カバレッジ改善の優先順位付け

```python
def prioritize_coverage_improvements(coverage_data, targets):
    """カバレッジ改善の優先順位を計算"""
    improvements = []

    for module_path, target in targets.items():
        if module_path in coverage_data['files']:
            file_data = coverage_data['files'][module_path]
            actual = file_data['summary']['percent_covered']

            if actual < target:
                # 影響度スコアの計算
                lines_of_code = file_data['summary']['num_statements']
                coverage_gap = target - actual

                # 優先度 = (コード行数 × カバレッジ不足) / 100
                priority_score = (lines_of_code * coverage_gap) / 100

                improvements.append({
                    'module': module_path,
                    'priority_score': priority_score,
                    'lines_of_code': lines_of_code,
                    'coverage_gap': coverage_gap,
                    'current_coverage': actual,
                    'target_coverage': target
                })

    # 優先度スコア順にソート
    return sorted(improvements, key=lambda x: x['priority_score'], reverse=True)
```

## テスト品質の維持

### 1. テストコードの品質メトリクス

```python
# scripts/analyze_test_quality.py
import ast
import os
from pathlib import Path

class TestQualityAnalyzer:
    def __init__(self, test_directory="tests"):
        self.test_directory = Path(test_directory)

    def analyze_test_file(self, file_path):
        """テストファイルの品質を分析"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        metrics = {
            'test_methods': 0,
            'assertions': 0,
            'mocks': 0,
            'fixtures': 0,
            'docstrings': 0,
            'lines_of_code': len(content.splitlines())
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    metrics['test_methods'] += 1
                    if ast.get_docstring(node):
                        metrics['docstrings'] += 1

                # フィクスチャの検出
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Name) and
                        decorator.id == 'fixture'):
                        metrics['fixtures'] += 1

            # アサーションの検出
            elif isinstance(node, ast.Assert):
                metrics['assertions'] += 1

            # モックの検出
            elif (isinstance(node, ast.Call) and
                  isinstance(node.func, ast.Name) and
                  'mock' in node.func.id.lower()):
                metrics['mocks'] += 1

        return metrics

    def calculate_quality_score(self, metrics):
        """テスト品質スコアを計算"""
        if metrics['test_methods'] == 0:
            return 0

        # 各メトリクスの重み付けスコア
        assertion_ratio = metrics['assertions'] / metrics['test_methods']
        docstring_ratio = metrics['docstrings'] / metrics['test_methods']

        # 品質スコア (0-100)
        score = (
            min(assertion_ratio * 20, 40) +  # アサーション密度 (最大40点)
            docstring_ratio * 30 +           # ドキュメント率 (最大30点)
            min(metrics['fixtures'] * 5, 20) + # フィクスチャ使用 (最大20点)
            min(metrics['mocks'] * 2, 10)    # モック使用 (最大10点)
        )

        return min(score, 100)
```

### 2. テストの重複検出

```python
def detect_duplicate_tests(test_directory):
    """重複するテストロジックを検出"""
    test_files = list(Path(test_directory).rglob("test_*.py"))

    # テストメソッドの類似度を計算
    similar_tests = []

    for file1 in test_files:
        for file2 in test_files:
            if file1 >= file2:  # 同じペアを2回チェックしない
                continue

            similarity = calculate_test_similarity(file1, file2)
            if similarity > 0.8:  # 80%以上の類似度
                similar_tests.append({
                    'file1': file1,
                    'file2': file2,
                    'similarity': similarity
                })

    return similar_tests

def calculate_test_similarity(file1, file2):
    """2つのテストファイルの類似度を計算"""
    # 簡単な実装例（実際はより高度なアルゴリズムを使用）
    with open(file1) as f1, open(file2) as f2:
        content1 = set(f1.read().split())
        content2 = set(f2.read().split())

    intersection = len(content1 & content2)
    union = len(content1 | content2)

    return intersection / union if union > 0 else 0
```

## 自動化とツール

### 1. カバレッジレポートの自動生成

```python
# scripts/generate_coverage_report.py
import subprocess
import json
from datetime import datetime
from pathlib import Path

def generate_comprehensive_coverage_report():
    """包括的なカバレッジレポートを生成"""

    # カバレッジデータの収集
    subprocess.run([
        "uv", "run", "pytest",
        "--cov=ci_helper",
        "--cov-report=json",
        "--cov-report=html",
        "--cov-report=term"
    ])

    # JSONデータの読み込み
    with open("coverage.json") as f:
        coverage_data = json.load(f)

    # レポートの生成
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_coverage": coverage_data["totals"]["percent_covered"],
        "total_lines": coverage_data["totals"]["num_statements"],
        "covered_lines": coverage_data["totals"]["covered_lines"],
        "missing_lines": coverage_data["totals"]["missing_lines"],
        "modules": []
    }

    # モジュール別詳細
    for filename, file_data in coverage_data["files"].items():
        module_info = {
            "name": filename,
            "coverage": file_data["summary"]["percent_covered"],
            "lines": file_data["summary"]["num_statements"],
            "missing_lines": file_data["missing_lines"],
            "priority": get_module_priority(filename)
        }
        report["modules"].append(module_info)

    # 優先度順にソート
    report["modules"].sort(key=lambda x: (x["priority"], -x["coverage"]))

    # レポートファイルの保存
    report_path = Path("coverage_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Markdownレポートの生成
    generate_markdown_report(report)

    return report

def generate_markdown_report(report_data):
    """Markdownフォーマットのレポートを生成"""
    markdown = f"""# カバレッジレポート

生成日時: {report_data['timestamp']}

## 全体サマリー

- **全体カバレッジ**: {report_data['overall_coverage']:.1f}%
- **総行数**: {report_data['total_lines']:,}
- **カバー済み行数**: {report_data['covered_lines']:,}
- **未カバー行数**: {report_data['missing_lines']:,}

## モジュール別詳細

| モジュール | カバレッジ | 行数 | 優先度 | 状態 |
|-----------|-----------|------|--------|------|
"""

    for module in report_data["modules"]:
        status = "✅" if module["coverage"] >= 70 else "⚠️" if module["coverage"] >= 50 else "❌"
        markdown += f"| {module['name']} | {module['coverage']:.1f}% | {module['lines']} | {module['priority']} | {status} |\n"

    markdown += f"""
## 改善提案

### 高優先度（即座に対応）
"""

    high_priority_modules = [m for m in report_data["modules"]
                           if m["priority"] == "high" and m["coverage"] < 70]

    for module in high_priority_modules[:5]:  # 上位5つ
        markdown += f"- **{module['name']}**: {module['coverage']:.1f}% → 目標80%\n"

    with open("coverage_report.md", "w", encoding="utf-8") as f:
        f.write(markdown)

def get_module_priority(filename):
    """モジュールの優先度を判定"""
    if any(keyword in filename for keyword in ["pattern_engine", "fix_generator", "risk_calculator"]):
        return "high"
    elif any(keyword in filename for keyword in ["config", "settings", "manager"]):
        return "medium"
    else:
        return "low"
```

### 2. 定期的なカバレッジ監視

```bash
#!/bin/bash
# scripts/weekly_coverage_check.sh

echo "🔍 週次カバレッジチェックを開始..."

# 現在のカバレッジを測定
uv run pytest --cov=ci_helper --cov-report=json --quiet

# 前週のデータと比較
if [ -f "weekly_coverage_history.json" ]; then
    python scripts/compare_weekly_coverage.py
else
    echo "📊 初回実行: ベースラインを作成中..."
fi

# 履歴に追加
python scripts/update_coverage_history.py

# レポート生成
python scripts/generate_coverage_report.py

echo "✅ 週次カバレッジチェック完了"
echo "📄 詳細レポート: coverage_report.md"
```

## トラブルシューティング

### 1. カバレッジが突然低下した場合

```python
def diagnose_coverage_drop(baseline_file, current_file):
    """カバレッジ低下の原因を診断"""

    with open(baseline_file) as f:
        baseline = json.load(f)
    with open(current_file) as f:
        current = json.load(f)

    print("🔍 カバレッジ低下の診断結果:")

    # 1. 新しく追加されたファイル（カバレッジなし）
    new_files = set(current['files'].keys()) - set(baseline['files'].keys())
    if new_files:
        print(f"\n📁 新規追加ファイル（テストなし）:")
        for file in new_files:
            coverage = current['files'][file]['summary']['percent_covered']
            print(f"  - {file}: {coverage:.1f}%")

    # 2. カバレッジが大幅に低下したファイル
    print(f"\n📉 カバレッジ低下ファイル:")
    for filename in baseline['files']:
        if filename in current['files']:
            old_coverage = baseline['files'][filename]['summary']['percent_covered']
            new_coverage = current['files'][filename]['summary']['percent_covered']
            diff = new_coverage - old_coverage

            if diff < -10:  # 10%以上の低下
                print(f"  - {filename}: {old_coverage:.1f}% → {new_coverage:.1f}% ({diff:.1f}%)")

    # 3. 削除されたファイル
    deleted_files = set(baseline['files'].keys()) - set(current['files'].keys())
    if deleted_files:
        print(f"\n🗑️ 削除されたファイル:")
        for file in deleted_files:
            print(f"  - {file}")
```

### 2. テストが通らない場合の対処

```python
def fix_failing_tests():
    """失敗するテストの自動修正を試行"""

    # テスト実行して失敗を収集
    result = subprocess.run([
        "uv", "run", "pytest", "--tb=short", "-v"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ テスト失敗を検出:")
        print(result.stdout)

        # よくある失敗パターンの自動修正
        if "ImportError" in result.stdout:
            print("🔧 インポートエラーの修正を試行...")
            fix_import_errors()

        if "AssertionError" in result.stdout:
            print("🔧 アサーションエラーの分析...")
            analyze_assertion_errors(result.stdout)

        if "fixture" in result.stdout:
            print("🔧 フィクスチャエラーの修正を試行...")
            fix_fixture_errors()

def fix_import_errors():
    """インポートエラーの自動修正"""
    # __init__.py ファイルの確認と作成
    test_dirs = Path("tests").rglob("*/")
    for test_dir in test_dirs:
        if test_dir.is_dir():
            init_file = test_dir / "__init__.py"
            if not init_file.exists():
                init_file.touch()
                print(f"  ✅ 作成: {init_file}")
```

## まとめ

このガイドに従うことで：

1. **持続的なカバレッジ維持**: 70%以上のカバレッジを長期的に維持
2. **品質重視の開発**: カバレッジ数値だけでなく、テストの品質も向上
3. **効率的な改善**: 優先度に基づいた戦略的なテスト追加
4. **自動化による負荷軽減**: 手動チェックを最小限に抑制

新機能開発時は必ずこのガイドを参照し、カバレッジの維持と向上を継続してください。
