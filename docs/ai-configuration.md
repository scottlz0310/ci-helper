# AI統合機能 設定リファレンス

## 概要

このドキュメントでは、ci-helper AI統合機能の詳細な設定オプションについて説明します。設定は`ci-helper.toml`ファイルの`[ai]`セクションで行います。

## 基本設定

### デフォルト設定例

```toml
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
interactive_timeout = 300
parallel_requests = false
```

### 設定項目

#### `default_provider`

- **型**: 文字列
- **デフォルト**: `"openai"`
- **選択肢**: `"openai"`, `"anthropic"`, `"local"`
- **説明**: デフォルトで使用するAIプロバイダー

```toml
[ai]
default_provider = "anthropic"  # Anthropicをデフォルトに
```

#### `cache_enabled`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: AIレスポンスのキャッシュ機能を有効にするか

```toml
[ai]
cache_enabled = false  # キャッシュを無効化
```

#### `cache_ttl_hours`

- **型**: 整数
- **デフォルト**: `24`
- **単位**: 時間
- **説明**: キャッシュの有効期限

```toml
[ai]
cache_ttl_hours = 48  # 48時間キャッシュを保持
```

#### `interactive_timeout`

- **型**: 整数
- **デフォルト**: `300`
- **単位**: 秒
- **説明**: 対話モードでのタイムアウト時間

```toml
[ai]
interactive_timeout = 600  # 10分のタイムアウト
```

#### `parallel_requests`

- **型**: ブール値
- **デフォルト**: `false`
- **説明**: 複数のAIリクエストを並列実行するか

```toml
[ai]
parallel_requests = true  # 並列実行を有効化
```

## プロバイダー設定

### OpenAI設定

```toml
[ai.providers.openai]
default_model = "gpt-4o"
available_models = ["gpt-4o", "gpt-4o-mini"]
timeout_seconds = 30
max_retries = 3
base_url = "https://api.openai.com/v1"  # オプション
```

#### OpenAI設定項目

##### `default_model`

- **型**: 文字列
- **デフォルト**: `"gpt-4o"`
- **説明**: デフォルトで使用するOpenAIモデル

**利用可能なモデル**:

- `gpt-4o`: 最新の高性能モデル
- `gpt-4o-mini`: コスト効率の良いモデル
- `gpt-4-turbo`: 高性能モデル（レガシー）
- `gpt-3.5-turbo`: 軽量モデル（レガシー）

##### `available_models`

- **型**: 文字列配列
- **説明**: 使用可能なモデルのリスト

##### `timeout_seconds`

- **型**: 整数
- **デフォルト**: `30`
- **説明**: APIリクエストのタイムアウト時間

##### `max_retries`

- **型**: 整数
- **デフォルト**: `3`
- **説明**: 失敗時の最大リトライ回数

##### `base_url`

- **型**: 文字列
- **デフォルト**: `"https://api.openai.com/v1"`
- **説明**: OpenAI APIのベースURL（プロキシ使用時等）

### Anthropic設定

```toml
[ai.providers.anthropic]
default_model = "claude-3-5-sonnet-20241022"
available_models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022"
]
timeout_seconds = 30
max_retries = 3
base_url = "https://api.anthropic.com"  # オプション
```

#### Anthropic設定項目

##### `default_model`

- **型**: 文字列
- **デフォルト**: `"claude-3-5-sonnet-20241022"`
- **説明**: デフォルトで使用するAnthropicモデル

**利用可能なモデル**:

- `claude-3-5-sonnet-20241022`: 高性能モデル
- `claude-3-5-haiku-20241022`: 高速・軽量モデル
- `claude-3-opus-20240229`: 最高性能モデル（高コスト）

### ローカルLLM設定

```toml
[ai.providers.local]
default_model = "llama3.2"
available_models = ["llama3.2", "codellama", "mistral"]
timeout_seconds = 60
max_retries = 2
base_url = "http://localhost:11434"
```

#### ローカルLLM設定項目

##### `base_url`

- **型**: 文字列
- **デフォルト**: `"http://localhost:11434"`
- **説明**: OllamaサーバーのURL

##### `default_model`

- **型**: 文字列
- **デフォルト**: `"llama3.2"`
- **説明**: デフォルトで使用するローカルモデル

**推奨モデル**:

- `llama3.2`: 汎用的な分析に適している
- `codellama`: コード分析に特化
- `mistral`: 軽量で高速
- `deepseek-coder`: コード理解に優れる

## コスト管理設定

```toml
[ai.cost_limits]
monthly_usd = 50.0
per_request_usd = 1.0
warning_threshold = 0.8
```

### コスト設定項目

#### `monthly_usd`

- **型**: 浮動小数点数
- **デフォルト**: `50.0`
- **単位**: USD
- **説明**: 月間使用コストの上限

#### `per_request_usd`

- **型**: 浮動小数点数
- **デフォルト**: `1.0`
- **単位**: USD
- **説明**: 1回のリクエストあたりのコスト上限

#### `warning_threshold`

- **型**: 浮動小数点数
- **デフォルト**: `0.8`
- **範囲**: 0.0 - 1.0
- **説明**: 警告を表示する閾値（制限の何%で警告するか）

## キャッシュ設定

```toml
[ai.cache]
max_size_mb = 100
cleanup_threshold = 0.9
auto_cleanup = true
compression = true
```

### キャッシュ設定項目

#### `max_size_mb`

- **型**: 整数
- **デフォルト**: `100`
- **単位**: MB
- **説明**: キャッシュディレクトリの最大サイズ

#### `cleanup_threshold`

- **型**: 浮動小数点数
- **デフォルト**: `0.9`
- **範囲**: 0.0 - 1.0
- **説明**: 自動クリーンアップを開始する閾値

#### `auto_cleanup`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: 自動クリーンアップを有効にするか

#### `compression`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: キャッシュデータの圧縮を有効にするか

## プロンプト設定

```toml
[ai.prompts]
analysis = "templates/analysis.txt"
fix_suggestion = "templates/fix.txt"
interactive = "templates/interactive.txt"
build_failure = "templates/build_failure.txt"
test_failure = "templates/test_failure.txt"
```

### プロンプト設定項目

#### カスタムプロンプトテンプレート

各エラータイプに対して専用のプロンプトテンプレートを指定できます：

- `analysis`: 一般的な分析用プロンプト
- `fix_suggestion`: 修正提案用プロンプト
- `interactive`: 対話モード用プロンプト
- `build_failure`: ビルド失敗用プロンプト
- `test_failure`: テスト失敗用プロンプト

#### プロンプトテンプレートファイルの作成

```bash
# テンプレートディレクトリを作成
mkdir -p templates

# カスタム分析プロンプトを作成
cat > templates/analysis.txt << 'EOF'
あなたはCI/CDエラー分析の専門家です。
以下のログを分析し、以下の形式で回答してください：

## 問題の概要
[簡潔な問題の説明]

## 根本原因
[技術的な根本原因の詳細]

## 修正方法
[具体的な修正手順]

## 予防策
[今後同様の問題を防ぐ方法]

ログ内容:
{log_content}
EOF
```

## セキュリティ設定

```toml
[ai.security]
mask_secrets = true
allowed_domains = ["api.openai.com", "api.anthropic.com"]
verify_ssl = true
```

### セキュリティ設定項目

#### `mask_secrets`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: ログ内のシークレットを自動マスクするか

#### `allowed_domains`

- **型**: 文字列配列
- **説明**: 接続を許可するドメインのリスト

#### `verify_ssl`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: SSL証明書の検証を行うか

## 高度な設定

### ログ処理設定

```toml
[ai.log_processing]
max_tokens = 100000
compression_ratio = 0.3
preserve_errors = true
context_lines = 5
```

#### `max_tokens`

- **型**: 整数
- **デフォルト**: `100000`
- **説明**: AIに送信する最大トークン数

#### `compression_ratio`

- **型**: 浮動小数点数
- **デフォルト**: `0.3`
- **説明**: ログ圧縮の目標比率

#### `preserve_errors`

- **型**: ブール値
- **デフォルト**: `true`
- **説明**: エラー情報を優先的に保持するか

#### `context_lines`

- **型**: 整数
- **デフォルト**: `5`
- **説明**: エラー前後の文脈行数

### パフォーマンス設定

```toml
[ai.performance]
concurrent_requests = 2
request_delay_ms = 100
memory_limit_mb = 512
```

#### `concurrent_requests`

- **型**: 整数
- **デフォルト**: `2`
- **説明**: 同時実行するリクエスト数

#### `request_delay_ms`

- **型**: 整数
- **デフォルト**: `100`
- **単位**: ミリ秒
- **説明**: リクエスト間の遅延時間

#### `memory_limit_mb`

- **型**: 整数
- **デフォルト**: `512`
- **単位**: MB
- **説明**: AI処理で使用する最大メモリ

## 環境変数による設定上書き

設定ファイルの値は環境変数で上書きできます：

```bash
# プロバイダーの上書き
export CI_HELPER_AI_PROVIDER=anthropic

# モデルの上書き
export CI_HELPER_AI_MODEL=claude-3-5-sonnet-20241022

# キャッシュの無効化
export CI_HELPER_AI_CACHE_ENABLED=false

# コスト制限の上書き
export CI_HELPER_AI_MONTHLY_LIMIT=100.0

# タイムアウトの上書き
export CI_HELPER_AI_TIMEOUT=60
```

### 環境変数の命名規則

- プレフィックス: `CI_HELPER_AI_`
- セクション区切り: `_`
- 大文字で記述
- ブール値: `true`/`false`
- 配列: カンマ区切り

例：

```bash
# [ai.providers.openai] -> CI_HELPER_AI_PROVIDERS_OPENAI_
export CI_HELPER_AI_PROVIDERS_OPENAI_DEFAULT_MODEL=gpt-4o-mini

# [ai.cost_limits] -> CI_HELPER_AI_COST_LIMITS_
export CI_HELPER_AI_COST_LIMITS_MONTHLY_USD=25.0
```

## 設定の検証

### 設定ファイルの構文チェック

```bash
# TOML構文の検証
python3 -c "import tomllib; tomllib.load(open('ci-helper.toml', 'rb'))"

# ci-helperによる設定検証
ci-run doctor --ai --verbose
```

### 設定の表示

```bash
# 現在の設定を表示
ci-run config show --ai

# 特定のセクションのみ表示
ci-run config show --section ai.providers.openai
```

## 設定例

### 開発環境用設定

```toml
[ai]
default_provider = "local"
cache_enabled = true
cache_ttl_hours = 1
interactive_timeout = 600

[ai.providers.local]
default_model = "llama3.2"
base_url = "http://localhost:11434"
timeout_seconds = 120

[ai.cost_limits]
monthly_usd = 0.0  # ローカルLLMはコストなし
```

### 本番環境用設定

```toml
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
parallel_requests = true

[ai.providers.openai]
default_model = "gpt-4o-mini"  # コスト効率重視
timeout_seconds = 30
max_retries = 3

[ai.cost_limits]
monthly_usd = 100.0
per_request_usd = 2.0
warning_threshold = 0.8

[ai.cache]
max_size_mb = 500
auto_cleanup = true
```

### 高セキュリティ環境用設定

```toml
[ai]
default_provider = "local"  # 外部APIを使用しない
cache_enabled = false       # キャッシュを無効化

[ai.providers.local]
default_model = "llama3.2"
base_url = "http://localhost:11434"

[ai.security]
mask_secrets = true
verify_ssl = true
allowed_domains = []  # 外部接続を禁止
```

## トラブルシューティング

設定に関する問題が発生した場合：

1. **構文エラー**: TOML構文チェッカーで検証
2. **設定が反映されない**: 環境変数の確認
3. **パフォーマンス問題**: キャッシュとタイムアウト設定の調整
4. **コスト問題**: 制限値とモデル選択の見直し

詳細は[AI統合機能 トラブルシューティングガイド](ai-troubleshooting.md)を参照してください。
