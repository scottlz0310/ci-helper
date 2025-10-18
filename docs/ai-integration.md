# AI統合機能ガイド

## 概要

ci-helper AI統合機能は、CI/CDの失敗ログを自動的にAIが分析し、根本原因の特定と修正提案を提供する機能です。複数のAIプロバイダーに対応し、セキュアなAPIキー管理と効率的なトークン使用を実現します。

## 対応AIプロバイダー

### OpenAI

- **モデル**: GPT-4o, GPT-4o-mini
- **特徴**: 高精度な分析、豊富な知識ベース
- **推奨用途**: 複雑なエラー分析、詳細な修正提案

### Anthropic

- **モデル**: Claude 3.5 Sonnet, Claude 3.5 Haiku
- **特徴**: 安全性重視、長文処理に優れる
- **推奨用途**: セキュリティ関連エラー、大きなログファイル

### ローカルLLM

- **対応**: Ollama経由でのローカルモデル
- **特徴**: プライバシー保護、コスト削減
- **推奨用途**: 機密プロジェクト、頻繁な分析

## セットアップ

### 1. APIキーの設定

#### OpenAI

```bash
export OPENAI_API_KEY="sk-your-openai-api-key"
```

#### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key"
```

#### ローカルLLM (Ollama)

```bash
# Ollamaのインストール
curl -fsSL https://ollama.ai/install.sh | sh

# モデルのダウンロード
ollama pull llama3.2

# 環境変数設定（オプション）
export OLLAMA_BASE_URL="http://localhost:11434"
```

### 2. 設定ファイルの更新

`ci-helper.toml`にAI設定を追加：

```toml
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
interactive_timeout = 300

[ai.providers.openai]
default_model = "gpt-4o"
available_models = ["gpt-4o", "gpt-4o-mini"]
timeout_seconds = 30
max_retries = 3

[ai.providers.anthropic]
default_model = "claude-3-5-sonnet-20241022"
available_models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
timeout_seconds = 30
max_retries = 3

[ai.cost_limits]
monthly_usd = 50.0
per_request_usd = 1.0
```

## 基本的な使用方法

### 最新のテスト結果を分析

```bash
ci-run analyze
```

### 特定のログファイルを分析

```bash
ci-run analyze --log .ci-helper/logs/act_20241019_120000.log
```

### プロバイダーとモデルを指定

```bash
ci-run analyze --provider anthropic --model claude-3-5-sonnet-20241022
```

### 修正提案を生成

```bash
ci-run analyze --fix
```

### 対話モードで詳細分析

```bash
ci-run analyze --interactive
```

## 高度な使用方法

### カスタムプロンプトの使用

```bash
ci-run analyze --prompt "このエラーの根本原因を特定し、段階的な修正手順を提案してください"
```

### キャッシュを無視して新しい分析

```bash
ci-run analyze --no-cache
```

### 使用統計の確認

```bash
ci-run analyze --stats
```

### 複数の分析オプションを組み合わせ

```bash
ci-run analyze --provider openai --model gpt-4o --fix --interactive
```

## 対話モードの使用方法

対話モードでは、AIと会話しながら段階的に問題を解決できます：

```bash
ci-run analyze --interactive
```

### 対話コマンド

- `/help` - 利用可能なコマンドを表示
- `/exit` - 対話セッションを終了
- `/stats` - 現在のセッションの統計を表示
- `/clear` - 会話履歴をクリア

### 対話例

```
> ci-run analyze --interactive

AI分析を開始します...

🤖 このエラーはPythonのimportエラーのようですね。具体的には...

💬 このエラーが発生する他の原因はありますか？

🤖 はい、他にも以下のような原因が考えられます...

💬 /exit
対話セッションを終了します。
```

## 修正提案と自動適用

### 修正提案の生成

```bash
ci-run analyze --fix
```

AIが生成する修正提案には以下が含まれます：

- 修正の概要と理由
- 変更前後のコード差分
- 推定工数と優先度
- 関連する修正項目

### 自動修正の適用

修正提案が表示された後、個別に承認して適用できます：

```
修正提案 1/3: requirements.txtの依存関係更新
優先度: 高
推定工数: 5分

--- requirements.txt
+++ requirements.txt
@@ -1,3 +1,3 @@
 click>=8.0.0
-requests==2.25.0
+requests>=2.28.0
 rich>=10.0.0

この修正を適用しますか？ [y/N/s(skip)/q(quit)]: y
✅ 修正を適用しました（バックアップ: requirements.txt.backup.20241019_120000）
```

### バックアップとロールバック

- 修正適用前に自動的にバックアップが作成されます
- バックアップファイル名: `{original_file}.backup.{timestamp}`
- 手動でのロールバック: `cp file.backup.timestamp file`

## コスト管理

### 使用統計の確認

```bash
ci-run analyze --stats
```

出力例：

```
📊 AI使用統計 (2024年10月)

プロバイダー別使用量:
  OpenAI (GPT-4o):
    - リクエスト数: 45回
    - 入力トークン: 125,000
    - 出力トークン: 15,000
    - 推定コスト: $8.50

  Anthropic (Claude 3.5 Sonnet):
    - リクエスト数: 12回
    - 入力トークン: 45,000
    - 出力トークン: 8,000
    - 推定コスト: $3.20

合計推定コスト: $11.70 / $50.00 (月間制限)
```

### コスト制限の設定

設定ファイルでコスト制限を設定できます：

```toml
[ai.cost_limits]
monthly_usd = 50.0      # 月間制限
per_request_usd = 1.0   # 1回あたりの制限
```

制限に近づくと警告が表示されます：

```
⚠️  月間使用量が制限の80%に達しました ($40.00 / $50.00)
⚠️  このリクエストの推定コスト: $0.85
```

## キャッシュ機能

### キャッシュの仕組み

- 同じログ内容の分析結果は自動的にキャッシュされます
- キャッシュキーは「ログ内容 + プロバイダー + モデル」のハッシュ
- デフォルトの有効期限は24時間

### キャッシュ設定

```toml
[ai]
cache_enabled = true
cache_ttl_hours = 24
```

### キャッシュの管理

```bash
# キャッシュを無視して新しい分析
ci-run analyze --no-cache

# キャッシュクリア
ci-run clean --ai-cache
```

## セキュリティ

### APIキーの安全な管理

1. **環境変数を使用**: 設定ファイルにAPIキーを記載しない
2. **.envファイル**: プロジェクトルートの`.env`ファイルに記載し、`.gitignore`に追加
3. **権限管理**: APIキーファイルの権限を適切に設定 (`chmod 600 .env`)

### ログのサニタイズ

- APIキーやシークレットは自動的にマスクされます
- ログ共有時も機密情報は保護されます

### 設定ファイルのセキュリティチェック

```bash
ci-run doctor --security
```

## トラブルシューティング

### よくある問題と解決方法

#### APIキーエラー

```
❌ OpenAI APIキーが設定されていません
```

**解決方法**:

1. 環境変数を設定: `export OPENAI_API_KEY="sk-..."`
2. `.env`ファイルに記載: `OPENAI_API_KEY=sk-...`
3. APIキーの有効性を確認

#### レート制限エラー

```
❌ レート制限に達しました (リセット時刻: 14:30)
```

**解決方法**:

1. 時間をおいて再実行
2. 別のプロバイダーを使用
3. より小さなログファイルで分析

#### ネットワークエラー

```
❌ AI APIへの接続に失敗しました
```

**解決方法**:

1. インターネット接続を確認
2. プロキシ設定を確認
3. ファイアウォール設定を確認
4. `--provider local`でローカルLLMを使用

#### トークン制限エラー

```
❌ ログファイルが大きすぎます (150,000 tokens > 128,000 limit)
```

**解決方法**:

1. ログファイルを分割
2. 重要な部分のみを抽出
3. Claude 3.5 Sonnetなど長文対応モデルを使用

### デバッグモード

詳細なログを確認したい場合：

```bash
CI_HELPER_LOG_LEVEL=DEBUG ci-run analyze --verbose
```

## ベストプラクティス

### 効率的な使用方法

1. **キャッシュを活用**: 同じエラーの再分析時はキャッシュが使用されます
2. **適切なモデル選択**:
   - 簡単なエラー: GPT-4o-mini, Claude 3.5 Haiku
   - 複雑なエラー: GPT-4o, Claude 3.5 Sonnet
3. **対話モードの活用**: 複雑な問題は対話モードで段階的に解決

### コスト最適化

1. **ログの前処理**: 不要な情報を除去してからAI分析
2. **キャッシュの活用**: 同じエラーの再分析を避ける
3. **適切なモデル選択**: 用途に応じてコスト効率の良いモデルを選択

### セキュリティ

1. **APIキー管理**: 環境変数または`.env`ファイルを使用
2. **ログの確認**: 共有前にAPIキーがマスクされていることを確認
3. **定期的な更新**: APIキーを定期的にローテーション

## 設定リファレンス

完全な設定オプションについては、[設定リファレンス](configuration.md#ai-settings)を参照してください。

## サポート

問題が発生した場合：

1. [トラブルシューティングガイド](troubleshooting.md#ai-integration)を確認
2. `ci-run doctor --ai`で環境をチェック
3. GitHubのIssueで報告
