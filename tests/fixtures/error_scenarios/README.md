# エラーシナリオフィクスチャ

このディレクトリには、CI-Helperシステムで発生する可能性のある様々なエラーシナリオのテストデータが含まれています。

## ファイル構成

### ネットワークエラー (`network_errors.json`)

- タイムアウトエラー
- 接続エラー
- DNS解決エラー
- SSL証明書エラー
- レート制限エラー

### 設定エラー (`configuration_errors.json`)

- APIキー未設定
- 無効なAPIキー形式
- サポートされていないプロバイダー
- 無効なモデル名
- 設定ファイル破損
- 設定ファイル権限エラー

### AI処理エラー (`ai_processing_errors.json`)

- トークン制限超過
- コスト制限超過
- モデル過負荷
- コンテンツポリシー違反
- 不正な形式のレスポンス
- ストリーミング中断

### ファイルシステムエラー (`file_system_errors.json`)

- ログファイル未発見
- ログアクセス権限拒否
- ディスク容量不足
- キャッシュファイル破損
- 設定ディレクトリ未発見
- 読み取り専用ファイルシステム

### CI実行エラー (`ci_execution_errors.json`)

- act未インストール
- Docker未起動
- ワークフローファイル未発見
- 無効なワークフロー構文
- act実行タイムアウト
- コンテナプル失敗
- システムリソース不足

### キャッシュエラー (`cache_errors.json`)

- キャッシュディレクトリ作成失敗
- キャッシュサイズ制限超過
- キャッシュエントリ期限切れ
- キャッシュ書き込み権限拒否
- キャッシュ破損検出
- 同時キャッシュアクセス競合

### 対話セッションエラー (`interactive_session_errors.json`)

- セッションタイムアウト
- セッションメモリオーバーフロー
- 無効なユーザー入力
- セッション状態破損
- 同時セッション制限
- セッション認証失敗

### パターン認識エラー (`pattern_recognition_errors.json`)

- パターンデータベース未発見
- 無効なパターン構文
- パターンマッチングタイムアウト
- パターン信頼度不足
- パターンエンジン初期化失敗
- パターン学習データ破損

### セキュリティエラー (`security_errors.json`)

- ログ内シークレット検出
- 安全でないファイルパス
- APIキー露出リスク
- 安全でないキャッシュ権限
- 信頼できない設定ソース
- 権限昇格試行

## 使用方法

### テストでの使用例

```python
import json
from pathlib import Path

def load_error_scenario(category: str, scenario_name: str) -> dict:
    """エラーシナリオデータを読み込む"""
    fixture_path = Path(__file__).parent / f"error_scenarios/{category}.json"
    with open(fixture_path) as f:
        data = json.load(f)
    return data[f"{category.replace('_', '_')}_scenarios"][scenario_name]

# 使用例
network_timeout = load_error_scenario("network_errors", "timeout_error")
config_missing_key = load_error_scenario("configuration_errors", "missing_api_key")
```

### フィクスチャとしての使用

```python
@pytest.fixture
def network_timeout_scenario():
    """ネットワークタイムアウトシナリオ"""
    return load_error_scenario("network_errors", "timeout_error")

def test_network_timeout_handling(network_timeout_scenario):
    """ネットワークタイムアウトのハンドリングテスト"""
    error_type = network_timeout_scenario["error_type"]
    error_message = network_timeout_scenario["error_message"]
    # テスト実装...
```

## データ構造

各エラーシナリオは以下の構造を持ちます：

```json
{
  "error_type": "例外クラス名",
  "error_message": "エラーメッセージ",
  "context": {
    "key": "value",
    "詳細な状況情報": "..."
  },
  "expected_behavior": "期待される動作",
  "recovery_strategy": "復旧戦略"
}
```

## 拡張方法

新しいエラーシナリオを追加する場合：

1. 適切なカテゴリのJSONファイルに追加
2. 新しいカテゴリが必要な場合は新しいJSONファイルを作成
3. このREADMEファイルを更新
4. 対応するテストケースを作成

## 注意事項

- 実際のAPIキーやシークレットは含めないでください
- テスト用のダミーデータのみを使用してください
- エラーメッセージは実際のシステムで発生するものに近づけてください
- 復旧戦略は実装可能で現実的なものにしてください
