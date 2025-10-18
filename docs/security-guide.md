# セキュリティガイド

## 概要

ci-helper AI統合機能を安全に使用するためのセキュリティガイドです。APIキーの管理、ログの保護、設定のセキュリティについて説明します。

## APIキーのセキュリティ

### ✅ 推奨される方法

#### 1. 環境変数の使用

```bash
# 一時的な設定
export OPENAI_API_KEY="sk-proj-your-key"
export ANTHROPIC_API_KEY="sk-ant-your-key"

# 永続的な設定（~/.bashrc または ~/.zshrc）
echo 'export OPENAI_API_KEY="sk-proj-your-key"' >> ~/.bashrc
```

#### 2. .envファイルの使用

```bash
# プロジェクトルートに.envファイルを作成
cat > .env << 'EOF'
OPENAI_API_KEY=sk-proj-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
EOF

# 権限を制限
chmod 600 .env

# .gitignoreに追加（重要！）
echo ".env" >> .gitignore
```

#### 3. システムキーリングの使用（高度）

```bash
# macOS Keychain
security add-generic-password -a "$USER" -s "ci-helper-openai" -w "sk-proj-your-key"

# Linux Secret Service
secret-tool store --label="CI Helper OpenAI" service ci-helper account openai
```

### ❌ 避けるべき方法

#### 設定ファイルへの直接記載

```toml
# ❌ 絶対にやってはいけない
[ai.providers.openai]
api_key = "sk-proj-your-key"  # 危険！
```

#### ソースコードへのハードコード

```python
# ❌ 絶対にやってはいけない
API_KEY = "sk-proj-your-key"  # 危険！
```

#### 平文ファイルでの保存

```bash
# ❌ 避けるべき
echo "sk-proj-your-key" > api_key.txt  # 危険！
```

## APIキーの管理

### APIキーの生成

#### OpenAI

1. [OpenAI Platform](https://platform.openai.com/api-keys)にアクセス
2. 「Create new secret key」をクリック
3. 適切な名前を設定（例：`ci-helper-production`）
4. 必要最小限の権限を設定
5. 使用量制限を設定

#### Anthropic

1. [Anthropic Console](https://console.anthropic.com/keys)にアクセス
2. 「Create Key」をクリック
3. 適切な名前を設定
4. 使用量制限を設定

### APIキーのローテーション

#### 定期的なローテーション（推奨：3ヶ月ごと）

```bash
# 1. 新しいAPIキーを生成
# 2. 環境変数を更新
export OPENAI_API_KEY="新しいキー"

# 3. 動作確認
ci-run doctor --ai

# 4. 古いキーを無効化（Webコンソールで）
```

#### 緊急時のローテーション

```bash
# APIキーが漏洩した場合の緊急対応
# 1. 即座に古いキーを無効化
# 2. 新しいキーを生成
# 3. 全ての環境で更新
# 4. ログを確認して不正使用をチェック
```

### 使用量の監視

#### 定期的な使用量チェック

```bash
# ci-helperでの使用統計確認
ci-run analyze --stats

# プロバイダーのWebコンソールでの確認
# - OpenAI: https://platform.openai.com/usage
# - Anthropic: https://console.anthropic.com/usage
```

#### 異常な使用量の検出

- 予期しない大量のリクエスト
- 通常と異なる時間帯での使用
- 未知のIPアドレスからのアクセス

## ログのセキュリティ

### シークレットのマスキング

#### 自動マスキング機能

```toml
# ci-helper.toml
[ai.security]
mask_secrets = true  # デフォルトで有効
```

#### マスキング対象

- APIキー（OpenAI、Anthropic等）
- アクセストークン
- パスワード
- 秘密鍵
- データベース接続文字列

#### カスタムマスキングパターン

```toml
# ci-helper.toml
[ai.security]
custom_patterns = [
    "password=\\w+",
    "token=\\w+",
    "secret=\\w+"
]
```

### ログファイルの保護

#### ファイル権限の設定

```bash
# ログディレクトリの権限を制限
chmod 700 .ci-helper/logs/
chmod 600 .ci-helper/logs/*.log
```

#### ログの暗号化（高セキュリティ環境）

```bash
# ログファイルの暗号化
gpg --symmetric --cipher-algo AES256 .ci-helper/logs/sensitive.log

# 復号化
gpg --decrypt sensitive.log.gpg > sensitive.log
```

### ログの共有

#### 安全な共有方法

```bash
# 1. シークレットがマスクされていることを確認
ci-run logs --show latest --mask-secrets

# 2. 必要な部分のみを抽出
grep -A 10 -B 10 "ERROR" log_file.log > error_excerpt.log

# 3. 手動でのダブルチェック
# 4. セキュアなチャネルでの共有（暗号化メール等）
```

#### 避けるべき共有方法

- 平文でのメール送信
- パブリックなチャットツール
- 未暗号化のファイル共有サービス
- バージョン管理システムへのコミット

## ネットワークセキュリティ

### HTTPS通信の確保

#### SSL証明書の検証

```toml
# ci-helper.toml
[ai.security]
verify_ssl = true  # 必須
```

#### 許可ドメインの制限

```toml
# ci-helper.toml
[ai.security]
allowed_domains = [
    "api.openai.com",
    "api.anthropic.com"
]
```

### プロキシ環境での設定

#### 企業プロキシの設定

```bash
# プロキシ設定
export HTTPS_PROXY=http://proxy.company.com:8080
export HTTP_PROXY=http://proxy.company.com:8080

# 証明書の設定（必要に応じて）
export REQUESTS_CA_BUNDLE=/path/to/company-ca.pem
```

#### プロキシ認証

```bash
# 認証付きプロキシ
export HTTPS_PROXY=http://username:password@proxy.company.com:8080
```

## アクセス制御

### ファイルシステムの権限

#### 設定ファイルの保護

```bash
# 設定ファイルの権限を制限
chmod 600 ci-helper.toml
chmod 600 .env

# ディレクトリの権限設定
chmod 700 .ci-helper/
```

#### 実行権限の管理

```bash
# ci-helperの実行権限を特定ユーザーに制限
sudo chown root:ci-helper-group /usr/local/bin/ci-run
sudo chmod 750 /usr/local/bin/ci-run
```

### ユーザー権限の分離

#### 専用ユーザーでの実行（推奨）

```bash
# ci-helper専用ユーザーの作成
sudo useradd -m -s /bin/bash ci-helper-user

# 必要最小限の権限を付与
sudo usermod -aG docker ci-helper-user  # Dockerアクセスのみ
```

## 監査とログ

### セキュリティ監査

#### 定期的なセキュリティチェック

```bash
# セキュリティ設定の確認
ci-run doctor --security

# 設定ファイルのセキュリティスキャン
ci-run security scan --config

# ログファイルのシークレットスキャン
ci-run security scan --logs
```

#### 監査ログの記録

```toml
# ci-helper.toml
[security.audit]
enable_audit_log = true
audit_log_path = ".ci-helper/audit.log"
log_api_calls = true
log_file_access = true
```

### インシデント対応

#### セキュリティインシデントの検出

- 異常なAPI使用量
- 不正なファイルアクセス
- 設定ファイルの改ざん
- 未知のIPからのアクセス

#### インシデント対応手順

1. **即座の対応**
   - APIキーの無効化
   - アクセスの遮断
   - 影響範囲の特定

2. **調査**
   - ログの分析
   - 侵入経路の特定
   - 被害範囲の評価

3. **復旧**
   - セキュリティホールの修正
   - 新しいAPIキーの生成
   - システムの復旧

4. **事後対応**
   - インシデントレポートの作成
   - 再発防止策の実装
   - セキュリティポリシーの見直し

## コンプライアンス

### データ保護規制への対応

#### GDPR対応

- 個人データの最小化
- データ処理の透明性
- データ削除権への対応

#### 企業ポリシーへの準拠

- データ分類の実装
- アクセス制御の強化
- 監査証跡の保持

### セキュリティ基準への準拠

#### ISO 27001対応

- 情報セキュリティ管理システム
- リスク評価と管理
- 継続的改善

#### SOC 2対応

- セキュリティ制御の実装
- 可用性の確保
- 処理の完全性

## ベストプラクティス

### 開発環境

#### 開発用APIキーの分離

```bash
# 開発環境用の制限されたAPIキー
export OPENAI_API_KEY="sk-proj-dev-limited-key"

# 本番環境とは別のプロジェクト/組織を使用
```

#### テスト環境でのモック使用

```bash
# 本物のAPIを使わずにモックを使用
ci-run analyze --provider mock --log test.log
```

### 本番環境

#### 最小権限の原則

- 必要最小限のAPIアクセス権限
- 制限されたファイルシステムアクセス
- ネットワークアクセスの制限

#### 定期的なセキュリティレビュー

- 月次のAPIキー監査
- 四半期のセキュリティ設定レビュー
- 年次のペネトレーションテスト

### チーム運用

#### セキュリティ教育

- APIキー管理の研修
- インシデント対応の訓練
- セキュリティ意識の向上

#### 責任の明確化

- セキュリティ責任者の指名
- インシデント対応チームの編成
- エスカレーション手順の整備

## トラブルシューティング

### よくあるセキュリティ問題

#### APIキーが漏洩した場合

```bash
# 1. 即座にキーを無効化
# 2. 新しいキーを生成
# 3. 全ての環境で更新
# 4. 使用ログを確認
ci-run analyze --stats --detailed
```

#### 設定ファイルがコミットされた場合

```bash
# 1. Gitからファイルを削除
git rm --cached ci-helper.toml
git commit -m "Remove config file with secrets"

# 2. .gitignoreに追加
echo "ci-helper.toml" >> .gitignore

# 3. APIキーをローテーション
```

### セキュリティ診断

#### 自動セキュリティチェック

```bash
# 包括的なセキュリティチェック
ci-run doctor --security --verbose

# 特定項目のチェック
ci-run security check --api-keys
ci-run security check --file-permissions
ci-run security check --network-config
```

このセキュリティガイドに従うことで、ci-helper AI統合機能を安全に使用できます。セキュリティは継続的なプロセスであり、定期的な見直しと改善が重要です。
