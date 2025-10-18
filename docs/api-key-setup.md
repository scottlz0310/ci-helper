# APIキー設定ガイド

## 概要

ci-helper AI統合機能を使用するには、使用するAIプロバイダーのAPIキーが必要です。このガイドでは、各プロバイダーのAPIキー取得方法と安全な設定方法を説明します。

## OpenAI APIキーの取得と設定

### 1. OpenAI APIキーの取得

1. [OpenAI Platform](https://platform.openai.com/)にアクセス
2. アカウントを作成またはログイン
3. 右上のメニューから「API keys」を選択
4. 「Create new secret key」をクリック
5. キー名を入力（例：`ci-helper-integration`）
6. 「Create secret key」をクリック
7. 表示されたAPIキーをコピー（**一度しか表示されません**）

### 2. OpenAI APIキーの設定

#### 方法1: 環境変数（推奨）

```bash
# 一時的な設定
export OPENAI_API_KEY="sk-proj-your-openai-api-key-here"

# 永続的な設定（~/.bashrc または ~/.zshrc に追加）
echo 'export OPENAI_API_KEY="sk-proj-your-openai-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

#### 方法2: .envファイル

プロジェクトルートに`.env`ファイルを作成：

```bash
# .env
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
```

**重要**: `.env`ファイルを`.gitignore`に追加してください：

```bash
echo ".env" >> .gitignore
```

### 3. 設定の確認

```bash
ci-run doctor --ai
```

## Anthropic APIキーの取得と設定

### 1. Anthropic APIキーの取得

1. [Anthropic Console](https://console.anthropic.com/)にアクセス
2. アカウントを作成またはログイン
3. 左メニューから「API Keys」を選択
4. 「Create Key」をクリック
5. キー名を入力（例：`ci-helper-integration`）
6. 「Create Key」をクリック
7. 表示されたAPIキーをコピー

### 2. Anthropic APIキーの設定

#### 方法1: 環境変数（推奨）

```bash
# 一時的な設定
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key-here"

# 永続的な設定
echo 'export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

#### 方法2: .envファイル

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
```

## ローカルLLM (Ollama) の設定

### 1. Ollamaのインストール

#### Linux/macOS

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Windows

[Ollama公式サイト](https://ollama.ai/download)からインストーラーをダウンロード

### 2. モデルのダウンロード

```bash
# 推奨モデル
ollama pull llama3.2          # 汎用的な分析
ollama pull codellama         # コード特化
ollama pull mistral           # 軽量で高速

# 利用可能なモデルの確認
ollama list
```

### 3. Ollamaの設定

#### デフォルト設定（推奨）

Ollamaがデフォルトポート（11434）で動作している場合、追加設定は不要です。

#### カスタム設定

```bash
# カスタムURL（必要に応じて）
export OLLAMA_BASE_URL="http://localhost:11434"

# リモートOllamaサーバー
export OLLAMA_BASE_URL="http://your-server:11434"
```

### 4. 動作確認

```bash
# Ollamaサービスの確認
ollama serve

# 別ターミナルでテスト
ollama run llama3.2 "Hello, how are you?"
```

## 複数プロバイダーの設定

すべてのプロバイダーを設定することで、用途に応じて使い分けできます：

```bash
# .env ファイルの例
OPENAI_API_KEY=sk-proj-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
OLLAMA_BASE_URL=http://localhost:11434
```

## セキュリティのベストプラクティス

### 1. APIキーの保護

#### ✅ 推奨される方法

- 環境変数を使用
- `.env`ファイルを使用し、`.gitignore`に追加
- APIキーファイルの権限を制限（`chmod 600 .env`）

#### ❌ 避けるべき方法

- 設定ファイル（`ci-helper.toml`）にAPIキーを記載
- ソースコードにAPIキーをハードコード
- APIキーをGitリポジトリにコミット

### 2. APIキーの権限管理

#### OpenAI

- 必要最小限の権限のみを付与
- 使用量制限を設定
- 定期的にキーをローテーション

#### Anthropic

- プロジェクト単位でキーを分離
- 使用量監視を有効化
- 不要になったキーは即座に削除

### 3. 監査とモニタリング

```bash
# 使用統計の定期確認
ci-run analyze --stats

# セキュリティチェック
ci-run doctor --security
```

## トラブルシューティング

### APIキーが認識されない

#### 症状

```
❌ OpenAI APIキーが設定されていません
```

#### 解決方法

1. 環境変数の確認：

   ```bash
   echo $OPENAI_API_KEY
   ```

2. `.env`ファイルの確認：

   ```bash
   cat .env | grep OPENAI_API_KEY
   ```

3. シェルの再読み込み：

   ```bash
   source ~/.bashrc  # または ~/.zshrc
   ```

### APIキーが無効

#### 症状

```
❌ OpenAI API認証に失敗しました: Invalid API key
```

#### 解決方法

1. APIキーの形式を確認（OpenAI: `sk-proj-...`, Anthropic: `sk-ant-...`）
2. APIキーの有効性をWebコンソールで確認
3. 新しいAPIキーを生成して再設定

### レート制限エラー

#### 症状

```
❌ レート制限に達しました (リセット時刻: 14:30)
```

#### 解決方法

1. 使用量制限を確認
2. 別のプロバイダーを使用
3. 時間をおいて再実行

### Ollama接続エラー

#### 症状

```
❌ Ollama APIへの接続に失敗しました
```

#### 解決方法

1. Ollamaサービスの確認：

   ```bash
   ollama serve
   ```

2. ポートの確認：

   ```bash
   curl http://localhost:11434/api/version
   ```

3. ファイアウォール設定の確認

## 設定の確認

すべての設定が完了したら、以下のコマンドで確認できます：

```bash
# AI環境の総合チェック
ci-run doctor --ai

# 利用可能なプロバイダーの確認
ci-run analyze --help

# テスト分析の実行
ci-run analyze --provider openai --log path/to/test.log
```

## よくある質問

### Q: 複数のAPIキーを設定する必要がありますか？

A: いいえ。使用したいプロバイダーのAPIキーのみ設定すれば十分です。

### Q: APIキーの使用量はどこで確認できますか？

A: 各プロバイダーのWebコンソールまたは`ci-run analyze --stats`で確認できます。

### Q: APIキーを間違って公開してしまいました

A: 即座に該当のAPIキーを無効化し、新しいキーを生成してください。

### Q: 会社のプロキシ環境で使用できますか？

A: はい。プロキシ設定を環境変数で指定できます：

```bash
export HTTPS_PROXY=http://proxy.company.com:8080
export HTTP_PROXY=http://proxy.company.com:8080
```

### Q: オフライン環境で使用できますか？

A: ローカルLLM（Ollama）を使用することで、インターネット接続なしで利用できます。

## サポート

APIキー設定で問題が発生した場合：

1. このガイドのトラブルシューティングセクションを確認
2. `ci-run doctor --ai --verbose`で詳細な診断を実行
3. [トラブルシューティングガイド](troubleshooting.md)を参照
4. GitHubのIssueで報告
