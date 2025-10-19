# 実環境での動作確認ガイド

このドキュメントでは、ci-helper AI統合機能の実環境での動作確認方法について説明します。

## 概要

実環境テストは以下の要件を満たすために実施されます：

- **要件 1.1**: 実際のAPIキーを使用したE2E動作確認
- **要件 2.1, 2.2**: 各プロバイダー（OpenAI、Anthropic、ローカルLLM）での動作確認
- **要件 11.1**: 大きなログファイルでのパフォーマンステスト
- **要件 11.1**: エラーシナリオでの復旧動作確認

## 事前準備

### 1. APIキーの設定

実環境テストを実行するには、以下のAPIキーが必要です：

```bash
# OpenAI APIキー（推奨）
export OPENAI_API_KEY="sk-..."

# Anthropic APIキー（オプション）
export ANTHROPIC_API_KEY="sk-ant-..."

# 汎用APIキー（オプション）
export CI_HELPER_API_KEY="..."
```

### 2. ローカルLLMの設定（オプション）

Ollamaを使用してローカルLLMをテストする場合：

```bash
# Ollamaのインストール
curl -fsSL https://ollama.ai/install.sh | sh

# モデルのダウンロード
ollama pull llama3.2
ollama pull codellama

# サービスの開始
ollama serve
```

### 3. 依存関係の確認

```bash
# 必要なパッケージがインストールされていることを確認
uv run python -c "import openai, anthropic, aiohttp; print('All dependencies available')"
```

## テストの実行

### 基本的な実行

```bash
# 全プロバイダーでのテスト（APIキーが必要）
uv run python scripts/real_environment_test.py --verbose

# 特定のプロバイダーのみテスト
uv run python scripts/real_environment_test.py --provider openai --verbose

# API呼び出しをスキップしてテスト構造のみ確認
uv run python scripts/real_environment_test.py --skip-api-tests --verbose
```

### コマンドラインオプション

- `--provider {openai,anthropic,local}`: 特定のプロバイダーのみテスト
- `--verbose`: 詳細なログを出力
- `--skip-api-tests`: 実際のAPI呼び出しを伴うテストをスキップ

## テスト項目

### 1. 基本初期化テスト

**テスト名**: `basic_ai_integration_initialization`

**目的**: AI統合システムの基本的な初期化が正常に動作することを確認

**検証項目**:

- AI統合オブジェクトの作成
- プロバイダーの初期化
- 設定の読み込み

### 2. プロバイダー別分析テスト

**テスト名**: `provider_analysis_{provider_name}`

**目的**: 各プロバイダーでの基本的な分析機能が動作することを確認

**検証項目**:

- ログ分析の実行
- 結果の取得
- トークン使用量の記録
- コスト計算

### 3. ストリーミング分析テスト

**テスト名**: `streaming_analysis_{provider_name}`

**目的**: ストリーミング機能が正常に動作することを確認

**検証項目**:

- ストリーミングレスポンスの受信
- チャンクの処理
- 応答時間の測定

### 4. 大容量ログパフォーマンステスト

**テスト名**: `large_log_performance`

**目的**: 大きなログファイルでのパフォーマンスを確認

**検証項目**:

- 大容量ログ（約50KB）の処理
- 処理時間の測定
- メモリ効率の確認
- トークン制限の処理

### 5. 対話セッションテスト

**テスト名**: `interactive_session`

**目的**: 対話的なAIデバッグモードが動作することを確認

**検証項目**:

- セッションの作成
- 対話の実行
- セッションの終了

### 6. キャッシュ機能テスト

**テスト名**: `cache_functionality`

**目的**: AIレスポンスキャッシュが正常に動作することを確認

**検証項目**:

- キャッシュの保存
- キャッシュからの読み込み
- 処理速度の向上

### 7. コスト管理テスト

**テスト名**: `cost_management`

**目的**: コスト管理機能が正常に動作することを確認

**検証項目**:

- 使用量の記録
- コスト計算
- 統計情報の更新

### 8. エラー復旧シナリオテスト

**テスト名**: `error_recovery_scenarios`

**目的**: 各種エラーシナリオでの復旧動作を確認

**検証項目**:

- 無効なプロバイダー指定時の処理
- 空のログ内容での処理
- トークン制限超過時の処理

## 結果の確認

### テスト結果ファイル

テスト実行後、以下のファイルが生成されます：

```
/tmp/ci_helper_real_test_XXXXXX/
├── real_environment_test_results.json  # 詳細な結果データ
└── real_environment_test_report.md     # 人間が読みやすいレポート
```

### 結果の解釈

#### 成功基準

- **基本初期化**: 100%成功
- **プロバイダー分析**: 利用可能なプロバイダーで80%以上成功
- **パフォーマンス**: 50KB以下のログを60秒以内で処理
- **エラー復旧**: 全シナリオで適切なエラーハンドリング

#### 一般的な問題と対処法

**APIキーエラー**:

```
Error: OpenAI APIキーが無効です
```

→ 環境変数 `OPENAI_API_KEY` を確認

**レート制限エラー**:

```
Error: openaiのレート制限に達しました
```

→ しばらく待ってから再実行、または別のプロバイダーを使用

**ネットワークエラー**:

```
Error: 接続エラー
```

→ インターネット接続とプロキシ設定を確認

**トークン制限エラー**:

```
Error: トークン制限を超過しました
```

→ より小さなモデルを使用、またはログを圧縮

## 継続的な監視

### 定期実行

実環境テストを定期的に実行するためのcronジョブ例：

```bash
# 毎日午前2時に実行
0 2 * * * cd /path/to/ci-helper && uv run python scripts/real_environment_test.py --skip-api-tests > /var/log/ci-helper-test.log 2>&1
```

### CI/CDパイプラインでの実行

GitHub Actionsでの実行例：

```yaml
name: Real Environment Test
on:
  schedule:
    - cron: '0 2 * * *'  # 毎日午前2時
  workflow_dispatch:

jobs:
  real-env-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install uv
        run: pip install uv
      - name: Run real environment test
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          uv run python scripts/real_environment_test.py --verbose
```

## トラブルシューティング

### よくある問題

1. **ImportError**: 依存関係が不足している

   ```bash
   uv sync
   ```

2. **Permission Error**: スクリプトの実行権限がない

   ```bash
   chmod +x scripts/real_environment_test.py
   ```

3. **Timeout Error**: ネットワークが遅い

   ```bash
   # タイムアウト値を増やして再実行
   export CI_HELPER_TIMEOUT=120
   ```

### デバッグモード

詳細なデバッグ情報を取得する場合：

```bash
# Pythonのデバッグモードで実行
PYTHONPATH=src python -u scripts/real_environment_test.py --verbose

# ログレベルを最大にして実行
export CI_HELPER_LOG_LEVEL=DEBUG
uv run python scripts/real_environment_test.py --verbose
```

## セキュリティ考慮事項

### APIキーの管理

- APIキーは環境変数でのみ管理
- 設定ファイルには記載しない
- ログファイルにAPIキーが含まれないよう注意

### テストデータ

- 実際の機密データは使用しない
- テスト用のサンプルログのみ使用
- 結果ファイルに機密情報が含まれていないか確認

## パフォーマンス最適化

### 推奨設定

実環境での最適なパフォーマンスを得るための推奨設定：

```toml
[ai]
cache_enabled = true
cache_ttl_hours = 24
cache_max_size_mb = 100

[ai.providers.openai]
default_model = "gpt-4o-mini"  # コスト効率重視
timeout_seconds = 30
max_retries = 3

[ai.cost_limits]
monthly_usd = 50.0
per_request_usd = 5.0
```

### 監視指標

- **応答時間**: 小さなログ（<5KB）で10秒以内
- **処理速度**: 1KB/秒以上
- **成功率**: 95%以上
- **コスト効率**: $0.01/分析以下

## まとめ

実環境テストは、AI統合機能の品質と信頼性を確保するための重要なプロセスです。定期的な実行により、以下を確保できます：

- 実際の使用環境での動作確認
- パフォーマンスの継続的な監視
- エラー処理の妥当性確認
- コスト管理の有効性確認

テスト結果に基づいて、必要に応じて設定の調整や機能の改善を行ってください。
