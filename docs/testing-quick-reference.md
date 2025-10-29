# テストクイックリファレンス

## 概要

CI-Helperプロジェクトでのテスト作成・維持のためのクイックリファレンスガイド。日常的な開発作業で素早く参照できるよう、重要なポイントを簡潔にまとめています。

## 🚀 新しいテストを書く前のチェックリスト

- [ ] 既存のテストで同様の機能がカバーされていないか確認
- [ ] テスト対象がビジネスロジックか（単純なゲッター/セッターは避ける）
- [ ] 外部依存関係を特定し、モック戦略を決定
- [ ] エラーケースも含めてテストケースを設計
- [ ] テスト名が機能を明確に表現しているか確認

## 📝 テスト命名規則

```python
# ✅ 良い例: 機能と条件が明確
def test_calculate_risk_with_high_confidence_returns_low_risk():
    pass

def test_load_config_file_raises_error_when_file_not_found():
    pass

def test_pattern_matching_returns_empty_list_for_no_matches():
    pass

# ❌ 悪い例: 曖昧で何をテストしているか不明
def test_calculate():
    pass

def test_config():
    pass

def test_pattern():
    pass
```

## 🎯 モック使用の判断基準

| 対象 | モックする | 理由 |
|------|-----------|------|
| ファイルI/O | ✅ | 実行速度、テスト独立性 |
| ネットワーク通信 | ✅ | 外部依存、実行速度 |
| 時間関数 | ✅ | 予測可能性、再現性 |
| データベース | ✅ | テスト独立性、速度 |
| ビジネスロジック | ❌ | テスト対象そのもの |
| 標準ライブラリ | ❌ | 信頼性が高い |
| 単純なデータ構造 | ❌ | モックの価値が低い |

## 🔧 よく使うモックパターン

### ファイル操作のモック

```python
from unittest.mock import mock_open, patch

# ファイル読み込み
@patch('builtins.open', mock_open(read_data='{"key": "value"}'))
@patch('pathlib.Path.exists', return_value=True)
def test_file_loading(mock_exists, mock_file):
    # テストロジック
    pass

# ファイル書き込み
@patch('builtins.open', mock_open())
@patch('pathlib.Path.mkdir')
def test_file_writing(mock_mkdir, mock_file):
    # テストロジック
    pass
```

### 時間のモック

```python
@patch('time.time')
def test_time_dependent_function(mock_time):
    mock_time.return_value = 1000  # 固定時刻
    # テストロジック
    pass
```

### API呼び出しのモック

```python
@patch('httpx.post')
def test_api_call(mock_post):
    mock_post.return_value.json.return_value = {"result": "success"}
    mock_post.return_value.status_code = 200
    # テストロジック
    pass
```

## 📊 カバレッジ目標（モジュール別）

| 優先度 | カバレッジ目標 | 対象モジュール例 |
|--------|----------------|------------------|
| 🔴 高 | 80%以上 | pattern_engine.py, fix_generator.py, risk_calculator.py |
| 🟡 中 | 60%以上 | auto_fix_config.py, settings_manager.py, custom_pattern_manager.py |
| 🟢 低 | 40%以上 | streaming_formatter.py, log_compressor.py |

## ⚡ よく使うコマンド

```bash
# 基本的なテスト実行
uv run pytest

# カバレッジ付きテスト実行
uv run pytest --cov=ci_helper --cov-report=term-missing

# 特定のファイルのテスト
uv run pytest tests/unit/ai/test_risk_calculator.py

# 失敗したテストのみ再実行
uv run pytest --lf

# カバレッジ閾値チェック
uv run pytest --cov=ci_helper --cov-fail-under=70

# HTMLカバレッジレポート生成
uv run pytest --cov=ci_helper --cov-report=html
open htmlcov/index.html
```

## 🐛 よくある問題と解決方法

### 1. インポートエラー

```python
# 問題: ModuleNotFoundError
# 解決: __init__.py ファイルを確認・作成
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/ai/__init__.py
```

### 2. モックが効かない

```python
# 問題: モックが適用されない
# 原因: インポートのタイミング

# ❌ 悪い例
import ci_helper.utils.config
@patch('ci_helper.utils.config.load_file')  # 効かない

# ✅ 良い例
@patch('ci_helper.utils.config.load_file')
def test_function(mock_load):
    import ci_helper.utils.config  # テスト内でインポート
```

### 3. 時間依存のテストが不安定

```python
# 問題: 時間に依存するテストが時々失敗
# 解決: time.time() をモック

@patch('time.time')
def test_cache_expiration(mock_time):
    mock_time.return_value = 1000  # 固定時刻を使用
    # テストロジック
```

### 4. テストが遅い

```python
# 問題: テスト実行に時間がかかる
# 解決: 重い処理をモック

@patch('ci_helper.ai.expensive_operation')
def test_fast_version(mock_expensive):
    mock_expensive.return_value = "mocked_result"
    # 高速なテスト
```

## 📋 テストレビューチェックリスト

### コードレビュー時の確認項目

- [ ] テスト名が機能を明確に表現している
- [ ] 必要な外部依存関係がモックされている
- [ ] エラーケースのテストが含まれている
- [ ] アサーションが具体的で意味がある
- [ ] テストが独立して実行可能
- [ ] 実行時間が適切（1秒以内）
- [ ] テストコードが読みやすい

### 新機能追加時の確認項目

- [ ] 新機能のコアロジックがテストされている
- [ ] カバレッジが目標値を満たしている
- [ ] 既存テストが全て通る
- [ ] エラーハンドリングがテストされている
- [ ] 境界値・エッジケースがテストされている

## 🎨 テストコードのベストプラクティス

### 1. テストの構造化

```python
class TestRiskCalculator:
    """リスク計算機能のテストクラス"""
    
    def test_calculate_risk_with_valid_input(self):
        """有効な入力でのリスク計算テスト"""
        # Given: テスト条件の設定
        calculator = RiskCalculator()
        
        # When: テスト対象の実行
        result = calculator.calculate_risk(confidence=0.8, impact=0.6)
        
        # Then: 結果の検証
        assert result.level == RiskLevel.MEDIUM
        assert 0.4 <= result.score <= 0.8
```

### 2. フィクスチャの活用

```python
@pytest.fixture
def sample_config():
    """テスト用設定データ"""
    return {
        "auto_fix": {
            "enabled": True,
            "confidence_threshold": 0.8
        }
    }

def test_with_fixture(sample_config):
    """フィクスチャを使用したテスト"""
    config = AutoFixConfig(sample_config)
    assert config.is_enabled()
```

### 3. パラメータ化テスト

```python
@pytest.mark.parametrize("confidence,expected_risk", [
    (0.9, RiskLevel.LOW),
    (0.5, RiskLevel.MEDIUM),
    (0.2, RiskLevel.HIGH),
])
def test_risk_levels(confidence, expected_risk):
    """信頼度別リスクレベルのテスト"""
    calculator = RiskCalculator()
    result = calculator.calculate_risk(confidence=confidence)
    assert result.level == expected_risk
```

## 📈 カバレッジ改善のヒント

### 1. 未カバー行の特定

```bash
# 未カバー行を表示
uv run pytest --cov=ci_helper --cov-report=term-missing

# 特定モジュールの詳細
uv run pytest --cov=ci_helper.ai.risk_calculator --cov-report=term-missing
```

### 2. 効率的なテスト追加

```python
# 1つのテストで複数の分岐をカバー
def test_config_validation_comprehensive():
    """設定検証の包括的テスト"""
    config = AutoFixConfig()
    
    # 有効な設定
    assert config.validate({"confidence_threshold": 0.8}) is True
    
    # 無効な設定（複数パターン）
    invalid_configs = [
        {"confidence_threshold": 1.5},  # 範囲外
        {"confidence_threshold": "invalid"},  # 型エラー
        {},  # 必須項目なし
    ]
    
    for invalid_config in invalid_configs:
        with pytest.raises(ConfigurationError):
            config.validate(invalid_config)
```

## 🔍 デバッグのヒント

### 1. テスト失敗時の詳細表示

```bash
# 詳細なエラー情報
uv run pytest -v --tb=long

# 標準出力も表示
uv run pytest -s

# 最初の失敗で停止
uv run pytest -x
```

### 2. 特定のテストのデバッグ

```python
def test_debug_example():
    """デバッグ用のテスト例"""
    calculator = RiskCalculator()
    
    # デバッグ情報の出力
    print(f"Calculator state: {calculator.__dict__}")
    
    result = calculator.calculate_risk(confidence=0.8)
    
    # 詳細な検証
    assert result is not None, "Result should not be None"
    assert hasattr(result, 'level'), "Result should have level attribute"
    print(f"Result: {result}")
```

## 📚 関連ドキュメント

- [詳細なテストガイドライン](./testing-guidelines.md)
- [モック戦略ベストプラクティス](./mock-strategies.md)
- [カバレッジ維持ガイド](./coverage-maintenance.md)

---

**💡 ヒント**: このクイックリファレンスをブックマークして、テスト作成時に素早く参照してください。
