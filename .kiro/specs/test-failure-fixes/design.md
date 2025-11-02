# テスト失敗修復 - 設計書

## 概要

この設計書は、CI-Helperプロジェクトにおけるpytestテストスイートの失敗を体系的に解決するためのアプローチを定義します。現在118個のテスト失敗と31個のエラーが発生しており、主な原因は欠損クラス、設定の互換性問題、モックインフラストラクチャの不安定性、テストフィクスチャの不足です。

## アーキテクチャ

### 全体アーキテクチャ

```
テスト修復システム
├── クラス依存関係解決層
│   ├── 欠損クラス検出器
│   ├── クラス定義生成器
│   └── インポート修復器
├── 設定互換性層
│   ├── AIConfig互換性アダプター
│   ├── 辞書ライクアクセス実装
│   └── モック互換性マネージャー
├── モックインフラストラクチャ層
│   ├── Rich Promptモック修復器
│   ├── 非同期モック管理器
│   └── ファイル操作モック安定化器
└── テストフィクスチャ管理層
    ├── フィクスチャファイル検証器
    ├── テストデータ生成器
    └── パターンデータ提供器
```

### 設計原則

1. **段階的修復**: 依存関係の問題から順次解決
2. **後方互換性**: 既存のテストコードを可能な限り保持
3. **最小限の変更**: 必要最小限の修正で最大の効果
4. **検証可能性**: 各修復段階で検証可能な成果物

## コンポーネントと インターフェース

### 1. クラス依存関係解決システム

#### MissingClassResolver

```python
class MissingClassResolver:
    """欠損クラスの検出と解決を担当"""

    def detect_missing_classes(self, test_results: TestResults) -> List[MissingClass]
    def resolve_performance_optimizer(self) -> None
    def resolve_japanese_error_handler(self) -> None
    def resolve_enhanced_analysis_formatter(self) -> None
    def resolve_ai_config_manager(self) -> None
    def resolve_failure_type_enum(self) -> None
```

**設計判断**: 各欠損クラスに対して専用の解決メソッドを提供することで、個別の問題に対する細かい制御が可能になります。

#### ClassDefinitionGenerator

```python
class ClassDefinitionGenerator:
    """必要なクラス定義を生成"""

    def generate_performance_optimizer(self) -> str
    def generate_japanese_error_handler(self) -> str
    def generate_enhanced_analysis_formatter(self) -> str
    def generate_ai_config_manager(self) -> str
    def generate_failure_type_enum(self) -> str
```

### 2. 設定互換性システム

#### AIConfigCompatibilityAdapter

```python
class AIConfigCompatibilityAdapter:
    """AIConfigオブジェクトの辞書ライクアクセスを提供"""

    def __init__(self, config_data: Dict[str, Any])
    def get(self, key: str, default: Any = None) -> Any
    def __getitem__(self, key: str) -> Any
    def __iter__(self) -> Iterator[str]
    def __contains__(self, key: str) -> bool
    def keys(self) -> KeysView[str]
    def values(self) -> ValuesView[Any]
    def items(self) -> ItemsView[str, Any]
```

**設計判断**: 既存のテストコードが期待する辞書インターフェースを完全に実装することで、テストコードの変更を最小限に抑えます。

### 3. モックインフラストラクチャ安定化システム

#### MockStabilizer

```python
class MockStabilizer:
    """モックオブジェクトの安定性を確保"""

    def stabilize_rich_prompt_mocks(self, mock_obj: Mock) -> None
    def fix_method_call_expectations(self, mock_obj: Mock, expected_calls: int) -> None
    def setup_async_mock_context(self, mock_obj: AsyncMock) -> None
    def ensure_file_operation_consistency(self, mock_obj: Mock) -> None
```

#### RichPromptMockFixer

```python
class RichPromptMockFixer:
    """Rich Promptモッキングの問題を修正"""

    def fix_stop_iteration_errors(self, mock_prompt: Mock) -> None
    def setup_proper_side_effects(self, mock_prompt: Mock, responses: List[str]) -> None
    def handle_prompt_interruption(self, mock_prompt: Mock) -> None
```

### 4. テストフィクスチャ管理システム

#### TestFixtureManager

```python
class TestFixtureManager:
    """テストフィクスチャの管理と提供"""

    def ensure_sample_log_files(self) -> None
    def provide_config_examples(self) -> Dict[str, Any]
    def setup_pattern_test_data(self) -> None
    def create_error_scenario_fixtures(self) -> None
```

#### FixtureValidator

```python
class FixtureValidator:
    """フィクスチャファイルの存在と整合性を検証"""

    def validate_log_fixtures(self) -> ValidationResult
    def validate_config_fixtures(self) -> ValidationResult
    def validate_pattern_fixtures(self) -> ValidationResult
    def validate_error_fixtures(self) -> ValidationResult
```

## データモデル

### MissingClass

```python
@dataclass
class MissingClass:
    name: str
    module_path: str
    import_statement: str
    test_files_affected: List[str]
    error_message: str
    resolution_priority: int
```

### ConfigCompatibilityIssue

```python
@dataclass
class ConfigCompatibilityIssue:
    config_object: str
    expected_interface: str
    missing_methods: List[str]
    affected_tests: List[str]
    fix_strategy: str
```

### MockStabilityIssue

```python
@dataclass
class MockStabilityIssue:
    mock_object: str
    issue_type: str  # "stop_iteration", "call_count", "async_context", "file_ops"
    error_details: str
    affected_tests: List[str]
    fix_approach: str
```

### FixtureAvailabilityIssue

```python
@dataclass
class FixtureAvailabilityIssue:
    fixture_type: str  # "log_files", "config_examples", "pattern_data", "error_scenarios"
    missing_files: List[str]
    expected_location: str
    affected_tests: List[str]
    generation_required: bool
```

## エラーハンドリング

### エラー分類システム

1. **クラス依存関係エラー**
   - NameError: クラスが見つからない
   - ImportError: モジュールが見つからない
   - AttributeError: クラス属性が見つからない

2. **設定互換性エラー**
   - AttributeError: 辞書メソッドが見つからない
   - TypeError: 期待されるインターフェースと異なる
   - KeyError: 設定キーが見つからない

3. **モック安定性エラー**
   - StopIteration: イテレータの予期しない終了
   - AssertionError: モック呼び出し回数の不一致
   - RuntimeError: 非同期コンテキストの問題

4. **フィクスチャ可用性エラー**
   - FileNotFoundError: テストファイルが見つからない
   - ValueError: フィクスチャデータの形式が不正
   - PermissionError: ファイルアクセス権限の問題

### エラー復旧戦略

```python
class TestFailureRecoveryStrategy:
    """テスト失敗からの復旧戦略"""

    def create_recovery_plan(self, failures: List[TestFailure]) -> RecoveryPlan
    def prioritize_fixes(self, issues: List[Issue]) -> List[Issue]
    def validate_fix_safety(self, fix: Fix) -> SafetyAssessment
    def apply_fix_with_rollback(self, fix: Fix) -> FixResult
```

## テスト戦略

### 修復検証テスト

1. **クラス解決テスト**

   ```python
   def test_performance_optimizer_resolution():
       """PerformanceOptimizerクラスが正しく解決されることを確認"""

   def test_japanese_error_handler_resolution():
       """JapaneseErrorHandlerクラスが正しく解決されることを確認"""
   ```

2. **設定互換性テスト**

   ```python
   def test_ai_config_dict_interface():
       """AIConfigが辞書インターフェースを提供することを確認"""

   def test_config_mock_compatibility():
       """設定オブジェクトがモックフレームワークと互換性があることを確認"""
   ```

3. **モック安定性テスト**

   ```python
   def test_rich_prompt_mock_stability():
       """Rich Promptモックが安定して動作することを確認"""

   def test_async_mock_context_management():
       """非同期モックが適切にコンテキストを管理することを確認"""
   ```

4. **フィクスチャ可用性テスト**

   ```python
   def test_sample_log_files_availability():
       """サンプルログファイルが利用可能であることを確認"""

   def test_pattern_test_data_completeness():
       """パターンテストデータが完全であることを確認"""
   ```

### テスト実行戦略

1. **段階的テスト実行**
   - Phase 1: クラス依存関係テスト
   - Phase 2: 設定互換性テスト
   - Phase 3: モック安定性テスト
   - Phase 4: フィクスチャ可用性テスト
   - Phase 5: 統合テスト

2. **失敗分析とフィードバック**

   ```python
   class TestFailureAnalyzer:
       def analyze_remaining_failures(self) -> AnalysisReport
       def identify_regression_risks(self) -> List[Risk]
       def suggest_further_improvements(self) -> List[Improvement]
   ```

## 実装計画

### Phase 1: クラス依存関係解決 (優先度: 高)

- 欠損クラスの特定と最小限の実装
- インポート文の修正
- 基本的なクラス構造の提供

### Phase 2: 設定互換性改善 (優先度: 高)

- AIConfigアダプターの実装
- 辞書ライクインターフェースの提供
- モック互換性の確保

### Phase 3: モックインフラストラクチャ安定化 (優先度: 中)

- Rich Promptモックの修正
- 非同期モック管理の改善
- ファイル操作モックの安定化

### Phase 4: テストフィクスチャ整備 (優先度: 中)

- 必要なフィクスチャファイルの作成
- テストデータの生成
- フィクスチャ検証システムの実装

### Phase 5: 統合テストと検証 (優先度: 低)

- 全体的なテスト実行
- 残存問題の分析
- 継続的改善の仕組み

## パフォーマンス考慮事項

### テスト実行時間の最適化

- 並列テスト実行のサポート
- フィクスチャの遅延読み込み
- キャッシュ機能の活用

### メモリ使用量の管理

- 大きなテストデータの効率的な管理
- モックオブジェクトのライフサイクル管理
- ガベージコレクションの最適化

## セキュリティ考慮事項

### テストデータの安全性

- 機密情報を含まないテストデータの使用
- テスト環境での適切な権限管理
- 一時ファイルの安全な処理

### モック設定の検証

- モックオブジェクトの適切な分離
- テスト間でのデータ漏洩防止
- セキュリティ関連テストの保護

## 監視とメトリクス

### 修復成功率の測定

```python
class RepairMetrics:
    def track_class_resolution_success_rate(self) -> float
    def measure_config_compatibility_improvement(self) -> float
    def monitor_mock_stability_enhancement(self) -> float
    def assess_fixture_availability_completeness(self) -> float
```

### 継続的改善

- テスト失敗パターンの分析
- 修復効果の長期追跡
- 新しい問題の早期発見

この設計により、CI-Helperプロジェクトのテストスイートを段階的かつ体系的に修復し、安定したテスト環境を構築することができます。
