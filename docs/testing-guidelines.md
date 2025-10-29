# テストガイドライン

## 概要

このドキュメントは、CI-Helperプロジェクトにおける効果的なテスト追加とカバレッジ維持のためのガイドラインを提供します。実際のコード品質向上に寄与するテストの作成方法と、持続可能なテスト戦略について説明します。

## 基本原則

### 1. ビジネスロジック優先

**✅ 推奨**: ビジネスロジックとコア機能のテスト

```python
# 良い例: リスク計算アルゴリズムのテスト
def test_calculate_risk_with_high_confidence():
    calculator = RiskCalculator()
    result = calculator.calculate_risk(
        confidence=0.9,
        complexity=0.5,
        impact=0.8
    )
    assert result.level == RiskLevel.MEDIUM
    assert 0.4 <= result.score <= 0.6
```

**❌ 避けるべき**: 単純なゲッター/セッターのテスト

```python
# 悪い例: 意味のないプロパティテスト
def test_get_name():
    obj = SomeClass("test")
    assert obj.name == "test"  # 価値の低いテスト
```

### 2. 実際の機能検証

テストは単にコードを実行するだけでなく、実際の機能を検証する必要があります。

**✅ 推奨**: 機能の正確性を検証

```python
def test_pattern_matching_accuracy():
    manager = CustomPatternManager()
    manager.register_pattern("build_failure", r"Error: Build failed")
    
    # 実際のログメッセージでテスト
    log_message = "Error: Build failed at step 3"
    matches = manager.find_matches(log_message)
    
    assert len(matches) == 1
    assert matches[0].pattern_name == "build_failure"
    assert matches[0].confidence > 0.8
```

### 3. エラーハンドリングの重視

エラー条件とエッジケースのテストを含める。

```python
def test_config_loading_with_invalid_file():
    config = AutoFixConfig()
    
    with pytest.raises(ConfigurationError) as exc_info:
        config.load_from_file("nonexistent.toml")
    
    assert "Configuration file not found" in str(exc_info.value)
    assert config.use_defaults()  # フォールバック動作を確認
```

## モック戦略

### 1. 外部依存関係のモック

外部システム（ファイルI/O、ネットワーク、時間）は適切にモックする。

```python
@patch('pathlib.Path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
def test_settings_persistence(mock_file, mock_exists):
    mock_exists.return_value = True
    
    manager = SettingsManager()
    settings = manager.load_settings()
    
    assert settings["key"] == "value"
    mock_file.assert_called_once()
```

### 2. 時間依存のテスト

時間に依存するテストは`time.time()`をモックする。

```python
@patch('time.time')
def test_cache_expiration(mock_time):
    # 初期時刻を設定
    mock_time.return_value = 1000
    
    cache = ResponseCache(ttl=300)  # 5分のTTL
    cache.set("key", "value")
    
    # 6分後をシミュレート
    mock_time.return_value = 1360
    
    assert cache.get("key") is None  # 期限切れ
```

### 3. AI APIのモック

AI APIレスポンスは予測可能な形でモックする。

```python
@patch('ci_helper.ai.providers.openai.OpenAIProvider.generate_response')
def test_fix_generation(mock_generate):
    mock_generate.return_value = {
        "suggestion": "Add missing import statement",
        "confidence": 0.85,
        "steps": ["Add 'import os' at the top of the file"]
    }
    
    generator = FixGenerator()
    result = generator.generate_fix("ImportError: No module named 'os'")
    
    assert result.confidence == 0.85
    assert "import os" in result.steps[0]
```

## テストの構造化

### 1. テストクラスの組織化

機能ごとにテストクラスを分割し、明確な命名規則を使用する。

```python
class TestAutoFixConfig:
    """自動修正設定のテストクラス"""
    
    def test_load_valid_config(self):
        """有効な設定ファイルの読み込みテスト"""
        pass
    
    def test_load_invalid_config(self):
        """無効な設定ファイルのエラーハンドリングテスト"""
        pass
    
    def test_default_values_application(self):
        """デフォルト値の適用テスト"""
        pass

class TestAutoFixConfigValidation:
    """設定検証機能のテストクラス"""
    
    def test_validate_confidence_threshold(self):
        """信頼度閾値の検証テスト"""
        pass
```

### 2. フィクスチャの活用

共通のテストデータはフィクスチャとして定義する。

```python
@pytest.fixture
def sample_config():
    """テスト用の設定データ"""
    return {
        "auto_fix": {
            "enabled": True,
            "confidence_threshold": 0.8,
            "backup_enabled": True
        },
        "patterns": {
            "custom_patterns_file": "patterns.json"
        }
    }

@pytest.fixture
def mock_pattern_manager():
    """モックされたパターンマネージャー"""
    manager = Mock(spec=CustomPatternManager)
    manager.find_matches.return_value = []
    return manager
```

## カバレッジ目標と優先度

### 1. モジュール別カバレッジ目標

| 優先度 | モジュールタイプ | 目標カバレッジ | 例 |
|--------|------------------|----------------|-----|
| 高 | ビジネスロジック | 80%以上 | risk_calculator.py, pattern_improvement.py |
| 中 | 設定・管理 | 60%以上 | auto_fix_config.py, settings_manager.py |
| 低 | ユーティリティ | 40%以上 | log_compressor.py, streaming_formatter.py |

### 2. テスト追加の優先順位

1. **ゼロカバレッジモジュール**: 最優先で基本テストを追加
2. **低カバレッジの重要モジュール**: ビジネスロジック部分を重点的に
3. **エラーハンドリング**: 例外処理とエッジケースのテスト
4. **統合テスト**: コンポーネント間の相互作用

## パフォーマンス考慮事項

### 1. テスト実行時間の管理

- 単体テストは1秒以内で完了すること
- 重いI/O操作はモックを使用すること
- 統合テストは必要最小限に留めること

```python
def test_large_log_processing():
    """大きなログファイルの処理テスト"""
    # 実際のファイルではなく、メモリ上のデータを使用
    large_log_data = "ERROR: " * 10000
    
    start_time = time.time()
    result = process_log_data(large_log_data)
    execution_time = time.time() - start_time
    
    assert execution_time < 1.0  # 1秒以内
    assert result.error_count == 10000
```

### 2. メモリ使用量の監視

```python
def test_memory_usage_during_processing():
    """処理中のメモリ使用量テスト"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # 大量データの処理
    processor = LogProcessor()
    processor.process_large_dataset(generate_test_data(size=1000))
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # メモリ増加が100MB以下であることを確認
    assert memory_increase < 100 * 1024 * 1024
```

## 品質保証

### 1. テストの可読性

```python
def test_risk_calculation_for_high_impact_low_confidence_scenario():
    """
    高影響度・低信頼度シナリオでのリスク計算テスト
    
    期待される動作:
    - 影響度が高い場合、信頼度が低くてもMEDIUMリスクとなる
    - リスクスコアは0.6-0.8の範囲になる
    """
    # Given: 高影響度・低信頼度の条件
    calculator = RiskCalculator()
    
    # When: リスク計算を実行
    result = calculator.calculate_risk(
        confidence=0.3,  # 低信頼度
        complexity=0.5,
        impact=0.9       # 高影響度
    )
    
    # Then: 期待される結果を検証
    assert result.level == RiskLevel.MEDIUM
    assert 0.6 <= result.score <= 0.8
    assert result.factors["impact"] == 0.9
```

### 2. テストの保守性

```python
class TestConstants:
    """テスト用定数"""
    DEFAULT_CONFIDENCE_THRESHOLD = 0.8
    MAX_PROCESSING_TIME = 1.0
    SAMPLE_ERROR_MESSAGE = "ImportError: No module named 'missing_module'"

def test_fix_generation_with_standard_error():
    """標準的なエラーメッセージでの修正生成テスト"""
    generator = FixGenerator()
    
    result = generator.generate_fix(TestConstants.SAMPLE_ERROR_MESSAGE)
    
    assert result.confidence >= TestConstants.DEFAULT_CONFIDENCE_THRESHOLD
    assert len(result.steps) > 0
```

## 継続的改善

### 1. カバレッジ監視

```bash
# カバレッジレポートの生成
uv run pytest --cov=ci_helper --cov-report=html --cov-report=term

# カバレッジ目標の確認
uv run pytest --cov=ci_helper --cov-fail-under=70
```

### 2. テスト品質メトリクス

定期的に以下のメトリクスを確認する：

- **カバレッジ率**: 全体で70%以上を維持
- **テスト実行時間**: 2分以内を維持
- **テスト成功率**: 99%以上を維持
- **テストコードの重複**: 最小限に抑制

### 3. レビューチェックリスト

新しいテストを追加する際のチェックリスト：

- [ ] ビジネスロジックを適切に検証しているか
- [ ] エラーケースを含んでいるか
- [ ] 外部依存関係を適切にモックしているか
- [ ] テスト名が機能を明確に表現しているか
- [ ] テストが独立して実行可能か
- [ ] 実行時間が適切か（1秒以内）
- [ ] アサーションが具体的で意味があるか

## ベストプラクティス

### 1. テストデータの管理

```python
# tests/fixtures/sample_data.py
class SampleData:
    """テスト用サンプルデータ"""
    
    VALID_CONFIG = {
        "auto_fix": {"enabled": True, "confidence_threshold": 0.8}
    }
    
    INVALID_CONFIG = {
        "auto_fix": {"enabled": "invalid_boolean"}
    }
    
    SAMPLE_LOG_ENTRIES = [
        "INFO: Application started",
        "ERROR: Database connection failed",
        "WARNING: Deprecated API usage detected"
    ]
```

### 2. エラーメッセージのテスト

```python
def test_configuration_error_messages():
    """設定エラーメッセージの内容テスト"""
    config = AutoFixConfig()
    
    with pytest.raises(ConfigurationError) as exc_info:
        config.validate({"confidence_threshold": 1.5})  # 無効な値
    
    error_message = str(exc_info.value)
    assert "confidence_threshold" in error_message
    assert "0.0 and 1.0" in error_message  # 有効範囲の説明
    assert "1.5" in error_message  # 実際の値
```

### 3. 統合テストの設計

```python
def test_end_to_end_fix_generation_workflow():
    """修正生成の完全なワークフローテスト"""
    # 実際のコンポーネントを使用（重要な統合ポイントのみ）
    pattern_manager = CustomPatternManager()
    fix_generator = FixGenerator()
    
    # テストデータの準備
    error_log = "ImportError: No module named 'requests'"
    
    # ワークフローの実行
    patterns = pattern_manager.find_matches(error_log)
    fix_suggestion = fix_generator.generate_fix(error_log, patterns)
    
    # 結果の検証
    assert fix_suggestion is not None
    assert fix_suggestion.confidence > 0.5
    assert "pip install requests" in fix_suggestion.description
```

## まとめ

このガイドラインに従うことで：

1. **効果的なテスト**: ビジネス価値のあるテストを作成
2. **持続可能なカバレッジ**: 長期的にカバレッジを維持
3. **高品質なコード**: テストを通じてコード品質を向上
4. **開発効率**: 適切なテスト戦略で開発速度を向上

新しいテストを追加する際は、このガイドラインを参考にして、実際のコード品質向上に寄与するテストを作成してください。
