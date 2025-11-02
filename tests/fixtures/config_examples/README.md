# 設定例ファイル

このディレクトリには、CI-Helperのテストで使用される設定ファイルの例が含まれています。

## ファイル構成

### TOML設定ファイル

| ファイル名 | 説明 | 用途 |
|-----------|------|------|
| `basic_ci_helper.toml` | 基本的なCI-Helper設定 | 基本機能のテスト |
| `ai_enabled_ci_helper.toml` | AI機能を有効にした設定 | AI統合テスト |
| `minimal_ci_helper.toml` | 最小限の設定 | 最小構成テスト |
| `multi_provider_ci_helper.toml` | 複数プロバイダー対応設定 | マルチプロバイダーテスト |
| `invalid_ci_helper.toml` | 無効な設定 | エラーハンドリングテスト |
| `pattern_recognition_ci_helper.toml` | パターン認識機能有効設定 | パターン認識テスト |
| `auto_fix_ci_helper.toml` | 自動修正機能有効設定 | 自動修正テスト |
| `learning_enabled_ci_helper.toml` | 学習機能有効設定 | 学習機能テスト |

### JSON設定ファイル

| ファイル名 | 説明 | 用途 |
|-----------|------|------|
| `ai_config.json` | AI設定のJSON形式 | AI設定テスト |
| `test_config.json` | テスト用設定 | テスト環境設定 |
| `performance_test_config.json` | パフォーマンステスト用設定 | パフォーマンステスト |
| `error_configs.json` | エラーテスト用設定 | エラーシナリオテスト |

### 環境変数ファイル

| ファイル名 | 説明 | 用途 |
|-----------|------|------|
| `.env.example` | 環境変数設定例 | 環境変数テスト |
| `.env.test` | テスト用環境変数 | テスト実行時の環境設定 |

### Act設定ファイル

| ファイル名 | 説明 | 用途 |
|-----------|------|------|
| `.actrc.example` | Act設定例 | Act設定テスト |
| `.actrc.basic` | 基本的なAct設定 | 基本Act機能テスト |
| `.actrc.privileged` | 権限付きAct設定 | 権限が必要なテスト |

## 使用方法

### Python コードでの使用

```python
from tests.fixtures.config_loader import load_toml_config, load_json_config

# TOML設定を読み込み
config = load_toml_config("basic_ci_helper.toml")

# JSON設定を読み込み
ai_config = load_json_config("ai_config.json")
```

### pytest フィクスチャでの使用

```python
import pytest
from tests.fixtures.test_config_fixtures import basic_config_data

def test_config_loading(basic_config_data):
    assert "ci-helper" in basic_config_data
    assert basic_config_data["ci-helper"]["verbose"] is False
```

### テストでの設定ファイルコピー

```python
import shutil
from tests.fixtures.config_loader import get_config_file_path

def test_with_config_file(temp_dir):
    # 設定ファイルをテスト環境にコピー
    config_source = get_config_file_path("basic_ci_helper.toml")
    config_dest = temp_dir / "ci-helper.toml"
    shutil.copy(config_source, config_dest)

    # テストを実行
    # ...
```

## 設定ファイルの特徴

### 基本設定 (`basic_ci_helper.toml`)

- AI機能なし
- 基本的なログ設定
- Act設定

### AI有効設定 (`ai_enabled_ci_helper.toml`)

- OpenAI、Anthropic プロバイダー設定
- キャッシュ機能有効
- コスト制限設定

### 最小設定 (`minimal_ci_helper.toml`)

- 必要最小限の設定のみ
- デフォルト値に依存

### マルチプロバイダー設定 (`multi_provider_ci_helper.toml`)

- OpenAI、Anthropic、Local プロバイダー
- 詳細なプロンプトテンプレート設定

## セキュリティ注意事項

- すべての設定ファイルはテスト用のダミーデータを使用
- 実際のAPIキーは含まれていません
- 本番環境では環境変数を使用してください

## 設定ファイルの追加

新しい設定例を追加する場合:

1. 適切なファイル名で設定ファイルを作成
2. `config_loader.py` に定数を追加
3. `test_config_fixtures.py` にフィクスチャを追加
4. このREADMEを更新

## トラブルシューティング

### ファイルが見つからない場合

```python
from tests.fixtures.config_loader import list_available_configs

# 利用可能な設定ファイルを確認
configs = list_available_configs()
print(configs)
```

### 設定ファイルの検証

```python
from ci_helper.utils.config import Config

# 設定ファイルを検証
config = Config(project_root=temp_dir)
config.validate()
config.validate_ai_config()
```
