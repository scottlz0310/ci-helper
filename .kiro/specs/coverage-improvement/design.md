# 設計書

## 概要

CI-Helperプロジェクトのコードカバレッジを66%から70%以上に向上させるための包括的なテスト追加戦略。効率的なカバレッジ向上と実際のコード品質改善を両立させる設計。

## アーキテクチャ

### テスト追加戦略

```
カバレッジ向上戦略
├── 1. 既存テスト修正（即効性）
│   └── test_cache.py の失敗テスト修正
├── 2. ゼロカバレッジモジュール対応（高効果）
│   ├── auto_fix_config.py (153行)
│   ├── settings_manager.py (116行)
│   └── custom_pattern_manager.py (160行)
├── 3. 低カバレッジモジュール改善（中効果）
│   ├── risk_calculator.py (16% → 50%)
│   ├── pattern_improvement.py (18% → 40%)
│   └── feedback_collector.py (23% → 45%)
└── 4. テストガイドライン確立（持続性）
    ├── ビジネスロジック優先
    ├── モック戦略
    └── 保守性重視
```

### 優先度付けアルゴリズム

```python
def calculate_test_priority(module):
    impact_score = (
        lines_of_code * 0.3 +
        business_logic_complexity * 0.4 +
        usage_frequency * 0.2 +
        current_coverage_gap * 0.1
    )
    return impact_score
```

## コンポーネントと インターフェース

### 1. テスト修正コンポーネント

**目的**: 既存の失敗テストを修正してベースラインを安定化

```python
# tests/unit/ai/test_cache.py の修正
class TestResponseCache:
    def test_cache_expiration(self):
        # 時間モックを使用した適切なテスト実装
        with patch('time.time') as mock_time:
            # テストロジック
```

**設計決定**:

- `time.time()` のモックを使用してタイミング制御
- キャッシュの有効期限切れ動作を確実に検証
- 既存機能を壊さない修正

### 2. ゼロカバレッジモジュールテスト

#### 2.1 auto_fix_config.py テスト

**対象機能**:

- 設定ファイルの読み込み・検証
- デフォルト値の適用
- エラーハンドリング

```python
class TestAutoFixConfig:
    def test_load_valid_config(self):
        # 有効な設定ファイルの読み込みテスト
    
    def test_load_invalid_config(self):
        # 無効な設定ファイルのエラーハンドリングテスト
    
    def test_default_values(self):
        # デフォルト値の適用テスト
```

#### 2.2 settings_manager.py テスト

**対象機能**:

- 設定の永続化・取得
- 設定値の検証
- 設定の更新・削除

```python
class TestSettingsManager:
    def test_save_and_load_settings(self):
        # 設定の保存・読み込みテスト
    
    def test_setting_validation(self):
        # 設定値の検証テスト
    
    def test_setting_updates(self):
        # 設定の更新テスト
```

#### 2.3 custom_pattern_manager.py テスト

**対象機能**:

- パターンの登録・管理
- パターンマッチング
- パターンの永続化

```python
class TestCustomPatternManager:
    def test_register_pattern(self):
        # パターン登録テスト
    
    def test_pattern_matching(self):
        # パターンマッチングテスト
    
    def test_pattern_persistence(self):
        # パターン永続化テスト
```

### 3. 低カバレッジモジュール改善

#### 3.1 risk_calculator.py テスト拡張

**現在**: 16%カバレッジ（33/204行）
**目標**: 50%カバレッジ（102/204行）

**追加テスト領域**:

- リスク計算アルゴリズムの各分岐
- エッジケース（極値、境界値）
- エラー条件の処理

```python
class TestRiskCalculator:
    def test_calculate_risk_low_confidence(self):
        # 低信頼度でのリスク計算
    
    def test_calculate_risk_edge_cases(self):
        # 境界値でのリスク計算
    
    def test_risk_factors_weighting(self):
        # リスク要因の重み付けテスト
```

#### 3.2 pattern_improvement.py テスト拡張

**現在**: 18%カバレッジ（54/303行）
**目標**: 40%カバレッジ（121/303行）

**追加テスト領域**:

- パターン学習アルゴリズム
- パターン最適化ロジック
- 学習データの処理

#### 3.3 feedback_collector.py テスト拡張

**現在**: 23%カバレッジ（43/189行）
**目標**: 45%カバレッジ（85/189行）

**追加テスト領域**:

- フィードバック収集ワークフロー
- フィードバックデータの処理
- フィードバックの永続化

## データモデル

### テスト設定モデル

```python
@dataclass
class TestConfiguration:
    module_name: str
    current_coverage: float
    target_coverage: float
    priority: str  # 'high', 'medium', 'low'
    test_strategies: List[str]
    mock_requirements: List[str]
```

### カバレッジ追跡モデル

```python
@dataclass
class CoverageProgress:
    module_name: str
    baseline_coverage: float
    current_coverage: float
    target_coverage: float
    lines_added: int
    tests_added: int
    last_updated: datetime
```

## エラーハンドリング

### テスト実行エラー

```python
class TestExecutionError(Exception):
    """テスト実行中のエラー"""
    pass

class CoverageCalculationError(Exception):
    """カバレッジ計算エラー"""
    pass
```

### エラー処理戦略

1. **テスト失敗時**: 詳細なエラーメッセージとスタックトレース
2. **モック失敗時**: モック設定の検証とガイダンス
3. **カバレッジ測定失敗時**: 代替測定方法の提案

## テスト戦略

### モック戦略

```python
# 外部依存関係のモック
@patch('ci_helper.utils.config.load_config')
@patch('pathlib.Path.exists')
@patch('builtins.open')
def test_with_mocked_dependencies(self, mock_open, mock_exists, mock_load):
    # テストロジック
```

### テストデータ戦略

```python
# テストフィクスチャの活用
@pytest.fixture
def sample_config():
    return {
        'auto_fix': {
            'enabled': True,
            'confidence_threshold': 0.8
        }
    }
```

### パフォーマンステスト

```python
def test_performance_regression():
    start_time = time.time()
    # テスト対象の実行
    execution_time = time.time() - start_time
    assert execution_time < 1.0  # 1秒以内
```

## 実装フェーズ

### フェーズ1: 基盤修正（1日）

- 既存テスト失敗の修正
- テスト環境の安定化
- ベースラインカバレッジの確立

### フェーズ2: 高優先度モジュール（2-3日）

- auto_fix_config.py テスト追加
- settings_manager.py テスト追加
- risk_calculator.py テスト拡張

### フェーズ3: 中優先度モジュール（2-3日）

- custom_pattern_manager.py テスト追加
- pattern_improvement.py テスト拡張
- feedback_collector.py テスト拡張

### フェーズ4: 最終調整（1日）

- カバレッジ目標達成の確認
- テスト品質の検証
- ドキュメント更新

## 品質保証

### テスト品質メトリクス

```python
# テストの有効性を測定
def calculate_test_effectiveness(module_name):
    return {
        'coverage_increase': new_coverage - old_coverage,
        'test_to_code_ratio': test_lines / source_lines,
        'assertion_density': assertions / test_methods,
        'mock_usage_ratio': mocked_methods / total_methods
    }
```

### 継続的改善

1. **カバレッジ監視**: CI/CDでのカバレッジ追跡
2. **テスト品質レビュー**: 定期的なテストコードレビュー
3. **パフォーマンス監視**: テスト実行時間の追跡

## 設計決定の根拠

### なぜこの優先順位なのか

1. **auto_fix_config.py**: 設定管理は全システムの基盤
2. **settings_manager.py**: ユーザー設定の永続化は重要
3. **risk_calculator.py**: ビジネスロジックの信頼性が必要

### なぜこのテスト戦略なのか

1. **モック重視**: 外部依存を排除して安定性確保
2. **ビジネスロジック優先**: 実際の価値を提供する部分をテスト
3. **段階的実装**: リスクを最小化しながら確実に進行

## 成功指標

### 定量的指標

- カバレッジ: 66% → 70%以上
- テスト実行時間: 現在の1.5倍以内
- テスト追加数: 50-80個の新規テスト

### 定性的指標

- テストの可読性と保守性
- ビジネスロジックの検証度
- 将来の開発への影響
