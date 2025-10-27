# パターン認識テストデータ

このディレクトリには、CI-Helperのパターン認識エンジンをテストするための包括的なテストデータが含まれています。

## ファイル構成

### 1. comprehensive_patterns.json

- **目的**: 基本的なパターン認識機能のテスト
- **内容**: 25個の包括的なエラーパターン
- **カテゴリ**: permission, dependency, network, config, build, test, system, ci_cd, database, syntax, filesystem, test_mock, async, attribute, test_fixture, type, value, key, index, math
- **用途**: 基本的なパターンマッチング精度のテスト

### 2. test_log_samples.json

- **目的**: パターンマッチングの精度テスト
- **内容**: 30個の実際のログサンプル
- **特徴**: 各サンプルに期待されるパターンIDと信頼度が設定済み
- **用途**: パターン認識の精度検証

### 3. pattern_matching_test_cases.json

- **目的**: パターンマッチングのエッジケースとコーナーケースのテスト
- **内容**: 20個のテストケース
- **テストタイプ**:
  - positive: マッチするはずのケース
  - negative: マッチしないはずのケース
- **難易度**: easy, medium, hard
- **用途**: パターンマッチングアルゴリズムの堅牢性テスト

### 4. edge_case_patterns.json

- **目的**: エラーハンドリングと堅牢性のテスト
- **内容**: 15個のエッジケースパターン
- **特徴**:
  - 空の正規表現
  - 無効な正規表現
  - 極端に長いパターン
  - Unicode文字
  - 特殊文字
- **用途**: パターン認識エンジンのエラーハンドリングテスト

### 5. performance_test_data.json

- **目的**: 性能とスケーラビリティのテスト
- **内容**: 10個の性能テストデータセット
- **テストサイズ**: 小規模から大規模まで
- **メトリクス**: 処理時間、メモリ使用量、精度、並行処理能力
- **用途**: パターン認識エンジンの性能ベンチマーク

## 使用方法

### 基本的なパターンマッチングテスト

```python
import json
from pathlib import Path

# パターンデータを読み込み
with open("tests/fixtures/pattern_test_data/comprehensive_patterns.json") as f:
    pattern_data = json.load(f)

# ログサンプルを読み込み
with open("tests/fixtures/pattern_test_data/test_log_samples.json") as f:
    log_samples = json.load(f)

# パターン認識エンジンでテスト
for sample in log_samples["log_samples"]:
    log_content = sample["log_content"]
    expected_patterns = sample["expected_pattern_ids"]
    expected_confidence = sample["expected_confidence"]
    
    # パターン認識を実行
    matches = pattern_engine.analyze_log(log_content)
    
    # 結果を検証
    assert len(matches) > 0
    assert matches[0].pattern.id in expected_patterns
    assert matches[0].confidence >= expected_confidence * 0.9  # 10%の許容誤差
```

### エッジケーステスト

```python
# エッジケースパターンを読み込み
with open("tests/fixtures/pattern_test_data/edge_case_patterns.json") as f:
    edge_cases = json.load(f)

# 無効な正規表現パターンのテスト
for pattern_data in edge_cases["edge_case_patterns"]:
    if pattern_data["id"] == "invalid_regex_pattern":
        # パターンエンジンがクラッシュしないことを確認
        try:
            pattern = Pattern(**pattern_data)
            matches = pattern_engine.match_patterns("test log", [pattern])
            # エラーが発生しても適切に処理されることを確認
        except Exception as e:
            # 予期されるエラーハンドリング
            assert "regex" in str(e).lower()
```

### 性能テスト

```python
import time

# 性能テストデータを読み込み
with open("tests/fixtures/pattern_test_data/performance_test_data.json") as f:
    perf_data = json.load(f)

for dataset in perf_data["performance_datasets"]:
    if dataset["id"] == "large_dataset":
        log_content = dataset["sample_log"]
        expected_time_ms = dataset["expected_processing_time_ms"]
        
        # 処理時間を測定
        start_time = time.time()
        matches = pattern_engine.analyze_log(log_content)
        end_time = time.time()
        
        processing_time_ms = (end_time - start_time) * 1000
        
        # 性能要件を満たすことを確認
        assert processing_time_ms <= expected_time_ms * 1.2  # 20%の許容誤差
```

## テストカテゴリ

### 1. 機能テスト

- 基本的なパターンマッチング
- 複数パターンの競合解決
- 信頼度計算
- コンテキスト要件の処理

### 2. 精度テスト

- 正確なパターン識別
- 偽陽性の回避
- 偽陰性の最小化
- 信頼度の適切な計算

### 3. 堅牢性テスト

- 無効な入力の処理
- エラーハンドリング
- メモリ制限下での動作
- 並行処理の安全性

### 4. 性能テスト

- 処理速度
- メモリ使用量
- スケーラビリティ
- 並行処理能力

## ベンチマーク基準

### 処理時間

- **優秀**: 100KB あたり 100ms 未満
- **良好**: 100KB あたり 500ms 未満
- **許容**: 100KB あたり 1000ms 未満
- **改善要**: 100KB あたり 1000ms 超過

### メモリ使用量

- **優秀**: 1MB ログあたり 50MB 未満
- **良好**: 1MB ログあたり 100MB 未満
- **許容**: 1MB ログあたり 200MB 未満
- **改善要**: 1MB ログあたり 200MB 超過

### 精度

- **優秀**: 95% 超
- **良好**: 90% 超
- **許容**: 85% 超
- **改善要**: 85% 未満

## 拡張方法

新しいテストケースを追加する場合：

1. 適切なJSONファイルに新しいエントリを追加
2. 必要なフィールドをすべて設定
3. テストの目的と期待される結果を明確に記述
4. 既存のテストとの整合性を確認

## 注意事項

- テストデータは実際のプロダクション環境のログを模擬していますが、機密情報は含まれていません
- 性能テストの結果は実行環境に依存します
- エッジケースのテストでは意図的に無効なデータが含まれています
- Unicode文字を含むテストデータは適切なエンコーディング（UTF-8）で保存されています

## 更新履歴

- 2024-10-27: 初期バージョン作成
  - 包括的なパターンセット（25パターン）
  - ログサンプル（30サンプル）
  - テストケース（20ケース）
  - エッジケース（15ケース）
  - 性能テストデータ（10データセット）
