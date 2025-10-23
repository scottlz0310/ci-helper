# AI統合機能 トラブルシューティングガイド

## 概要

このガイドでは、ci-helper AI統合機能でよく発生する問題とその解決方法を説明します。問題が発生した場合は、まず該当するセクションを確認してください。

## 診断コマンド

問題の特定には以下の診断コマンドが有用です：

```bash
# AI環境の総合チェック
ci-run doctor --ai

# 詳細な診断情報
ci-run doctor --ai --verbose

# セキュリティチェック
ci-run doctor --security

# 使用統計の確認
ci-run analyze --stats
```

## APIキー関連の問題

### 問題1: APIキーが設定されていない

#### 症状

```
❌ OpenAI APIキーが設定されていません
設定方法: export OPENAI_API_KEY="sk-proj-..."
```

#### 原因

- 環境変数が設定されていない
- `.env`ファイルが存在しない、または読み込まれていない

#### 解決方法

1. **環境変数の確認**

   ```bash
   echo $OPENAI_API_KEY
   echo $ANTHROPIC_API_KEY
   ```

2. **環境変数の設定**

   ```bash
   export OPENAI_API_KEY="sk-proj-your-key-here"
   export ANTHROPIC_API_KEY="sk-ant-your-key-here"
   ```

3. **永続的な設定**

   ```bash
   # ~/.bashrc または ~/.zshrc に追加
   echo 'export OPENAI_API_KEY="sk-proj-your-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. **.envファイルの作成**

   ```bash
   # プロジェクトルートに作成
   cat > .env << EOF
   OPENAI_API_KEY=sk-proj-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   EOF

   # .gitignoreに追加
   echo ".env" >> .gitignore
   ```

### 問題2: APIキーが無効

#### 症状

```
❌ OpenAI API認証に失敗しました: Invalid API key provided
```

#### 原因

- APIキーが間違っている
- APIキーが無効化されている
- APIキーの形式が正しくない

#### 解決方法

1. **APIキーの形式確認**
   - OpenAI: `sk-proj-` で始まる
   - Anthropic: `sk-ant-` で始まる

2. **APIキーの再生成**
   - [OpenAI Platform](https://platform.openai.com/api-keys)
   - [Anthropic Console](https://console.anthropic.com/keys)

3. **新しいキーでの再設定**

   ```bash
   export OPENAI_API_KEY="新しいAPIキー"
   ci-run doctor --ai
   ```

### 問題3: APIキーが設定ファイルに記載されている

#### 症状

```
⚠️  セキュリティ警告: 設定ファイルにAPIキーが含まれています
ci-helper.tomlからAPIキーを削除し、環境変数を使用してください
```

#### 解決方法

1. **設定ファイルからAPIキーを削除**

   ```bash
   # ci-helper.tomlを編集してAPIキー行を削除
   sed -i '/api_key/d' ci-helper.toml
   ```

2. **環境変数に移行**

   ```bash
   export OPENAI_API_KEY="削除したAPIキー"
   ```

## 接続とネットワークの問題

### 問題4: ネットワーク接続エラー

#### 症状

```
❌ AI APIへの接続に失敗しました: Connection timeout
```

#### 原因

- インターネット接続の問題
- プロキシ設定の問題
- ファイアウォールによるブロック
- APIサーバーの一時的な障害

#### 解決方法

1. **インターネット接続の確認**

   ```bash
   ping google.com
   curl -I https://api.openai.com
   ```

2. **プロキシ設定**

   ```bash
   export HTTPS_PROXY=http://proxy.company.com:8080
   export HTTP_PROXY=http://proxy.company.com:8080
   ```

3. **ファイアウォール設定の確認**
   - 443ポート（HTTPS）が開いているか確認
   - 企業ネットワークの場合、IT部門に相談

4. **代替プロバイダーの使用**

   ```bash
   ci-run analyze --provider anthropic  # OpenAIが使えない場合
   ci-run analyze --provider local      # ローカルLLMを使用
   ```

### 問題5: Ollama接続エラー

#### 症状

```
❌ Ollama APIへの接続に失敗しました: Connection refused
```

#### 原因

- Ollamaサービスが起動していない
- ポート設定の問題
- モデルがダウンロードされていない

#### 解決方法

1. **Ollamaサービスの確認**

   ```bash
   # サービスの起動
   ollama serve

   # 別ターミナルで動作確認
   curl http://localhost:11434/api/version
   ```

2. **モデルの確認**

   ```bash
   # インストール済みモデルの確認
   ollama list

   # モデルのダウンロード
   ollama pull llama3.2
   ```

3. **ポート設定の確認**

   ```bash
   # カスタムポートの場合
   export OLLAMA_BASE_URL="http://localhost:11434"
   ```

## レート制限とコストの問題

### 問題6: レート制限エラー

#### 症状

```
❌ レート制限に達しました (リセット時刻: 14:30)
リクエスト数: 3000/3000 (1時間あたり)
```

#### 原因

- APIの使用量制限に達した
- 短時間での大量リクエスト

#### 解決方法

1. **制限リセットまで待機**

   ```bash
   # 制限リセット時刻まで待機
   echo "制限は14:30にリセットされます"
   ```

2. **別のプロバイダーを使用**

   ```bash
   ci-run analyze --provider anthropic  # OpenAIの制限時
   ci-run analyze --provider local      # 制限なし
   ```

3. **使用量の最適化**

   ```bash
   # より小さなログファイルで分析
   head -n 1000 large.log > small.log
   ci-run analyze --log small.log
   ```

### 問題7: コスト制限エラー

#### 症状

```
❌ 月間コスト制限に達しました ($50.00 / $50.00)
このリクエストはスキップされます
```

#### 解決方法

1. **制限の調整**

   ```toml
   # ci-helper.toml
   [ai.cost_limits]
   monthly_usd = 100.0  # 制限を増加
   ```

2. **コスト効率の良いモデルを使用**

   ```bash
   ci-run analyze --model gpt-4o-mini     # より安価
   ci-run analyze --model claude-3-5-haiku  # より安価
   ```

3. **ローカルLLMの使用**

   ```bash
   ci-run analyze --provider local  # コストなし
   ```

## トークン制限の問題

### 問題8: トークン制限エラー

#### 症状

```
❌ ログファイルが大きすぎます (150,000 tokens > 128,000 limit)
モデル: gpt-4o (制限: 128,000 tokens)
```

#### 解決方法

1. **ログファイルの分割**

   ```bash
   # ログを分割
   split -l 1000 large.log part_
   ci-run analyze --log part_aa
   ```

2. **重要な部分のみ抽出**

   ```bash
   # エラー部分のみ抽出
   grep -A 10 -B 10 "ERROR\|FAILED" large.log > errors.log
   ci-run analyze --log errors.log
   ```

3. **長文対応モデルの使用**

   ```bash
   ci-run analyze --provider anthropic --model claude-3-5-sonnet-20241022
   ```

## キャッシュの問題

### 問題9: キャッシュが効かない

#### 症状

- 同じログファイルでも毎回API呼び出しが発生
- キャッシュヒット率が低い

#### 原因

- キャッシュが無効化されている
- ログ内容に微細な差異がある
- キャッシュディレクトリの権限問題

#### 解決方法

1. **キャッシュ設定の確認**

   ```toml
   # ci-helper.toml
   [ai]
   cache_enabled = true
   cache_ttl_hours = 24
   ```

2. **キャッシュディレクトリの確認**

   ```bash
   ls -la .ci-helper/cache/ai/
   ```

3. **権限の修正**

   ```bash
   chmod -R 755 .ci-helper/cache/
   ```

### 問題10: キャッシュ容量エラー

#### 症状

```
⚠️  AIキャッシュが容量制限に達しました (100MB)
古いエントリを削除しています...
```

#### 解決方法

1. **キャッシュクリア**

   ```bash
   ci-run clean --ai-cache
   ```

2. **容量制限の調整**

   ```toml
   # ci-helper.toml
   [ai.cache]
   max_size_mb = 200  # 制限を増加
   ```

## 対話モードの問題

### 問題11: 対話セッションが応答しない

#### 症状

- 対話モードで入力しても応答がない
- セッションがハング状態

#### 解決方法

1. **タイムアウト設定の確認**

   ```toml
   # ci-helper.toml
   [ai]
   interactive_timeout = 300  # 5分
   ```

2. **セッションの強制終了**

   ```bash
   # Ctrl+C で中断
   # または /exit コマンド
   ```

3. **ログの確認**

   ```bash
   CI_HELPER_LOG_LEVEL=DEBUG ci-run analyze --interactive --verbose
   ```

## パフォーマンスの問題

### 問題12: 分析が遅い

#### 症状

- AI分析に異常に時間がかかる
- タイムアウトが頻発

#### 解決方法

1. **ログサイズの最適化**

   ```bash
   # ログを圧縮
   gzip large.log
   ci-run analyze --log large.log.gz
   ```

2. **高速モデルの使用**

   ```bash
   ci-run analyze --model gpt-4o-mini
   ci-run analyze --model claude-3-5-haiku
   ```

3. **並列処理の無効化**

   ```toml
   # ci-helper.toml
   [ai]
   parallel_requests = false
   ```

## 設定の問題

### 問題13: 設定ファイルが読み込まれない

#### 症状

- 設定ファイルの変更が反映されない
- デフォルト設定が使用される

#### 解決方法

1. **設定ファイルの場所確認**

   ```bash
   # プロジェクトルートに配置
   ls -la ci-helper.toml
   ```

2. **設定ファイルの構文確認**

   ```bash
   # TOML構文チェック
   python -c "import tomllib; tomllib.load(open('ci-helper.toml', 'rb'))"
   ```

3. **設定の優先順位確認**

   ```bash
   # 環境変数が設定ファイルより優先される
   unset CI_HELPER_AI_PROVIDER
   ```

## 一般的なデバッグ手順

### ステップ1: 基本診断

```bash
ci-run doctor --ai --verbose
```

### ステップ2: 環境変数確認

```bash
env | grep -E "(OPENAI|ANTHROPIC|OLLAMA|CI_HELPER)"
```

### ステップ3: 設定ファイル確認

```bash
cat ci-helper.toml | grep -A 20 "\[ai\]"
```

### ステップ4: ログ確認

```bash
CI_HELPER_LOG_LEVEL=DEBUG ci-run analyze --verbose 2>&1 | tee debug.log
```

### ステップ5: 最小構成でテスト

```bash
# 最小のログファイルでテスト
echo "ERROR: Test error" > test.log
ci-run analyze --log test.log --provider openai --model gpt-4o-mini
```

## サポートとヘルプ

### 問題が解決しない場合

1. **詳細な診断情報を収集**

   ```bash
   ci-run doctor --ai --verbose > diagnosis.txt
   CI_HELPER_LOG_LEVEL=DEBUG ci-run analyze --verbose 2>&1 > debug.log
   ```

2. **GitHubでIssueを作成**
   - 問題の詳細な説明
   - 実行したコマンド
   - エラーメッセージ
   - 診断情報（`diagnosis.txt`）
   - 環境情報（OS、Pythonバージョン等）

3. **コミュニティサポート**
   - [GitHub Discussions](https://github.com/scottlz0310/ci-helper/discussions)
   - [トラブルシューティングガイド](troubleshooting.md)

### 緊急時の回避策

AI機能が完全に使用できない場合の代替手段：

```bash
# 従来のログ表示に戻る
ci-run test --format markdown

# ログの手動分析
ci-run logs --show latest --format json | jq '.failures'

# 外部ツールとの連携
ci-run test --format json | curl -X POST -d @- https://your-ai-service.com/analyze
```

このトラブルシューティングガイドで問題が解決しない場合は、遠慮なくサポートにお問い合わせください。
