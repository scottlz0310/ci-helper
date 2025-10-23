# 使用方法ガイド

このドキュメントでは、ci-helper の基本的な使用方法から高度な機能まで、実例を交えて説明します。

## 基本的なワークフロー

### 1. プロジェクトの初期化

```bash
# プロジェクトディレクトリに移動
cd /path/to/your/project

# ci-helperを初期化
ci-run init

# 生成されたファイルを確認
ls -la .actrc ci-helper.toml .env.example
```

### 2. 環境の確認

```bash
# 依存関係をチェック
ci-run doctor

# 詳細な診断情報を表示
ci-run doctor --verbose

# 特定の問題の解決ガイドを表示
ci-run doctor --guide act
ci-run doctor --guide docker
```

### 3. ワークフローの実行

```bash
# 全ワークフローを実行
ci-run test

# 特定のワークフローを実行
ci-run test --workflow test.yml
ci-run test -w lint.yml -w test.yml

# 詳細出力で実行
ci-run test --verbose
```

## コマンド詳細

### init コマンド

プロジェクトの初期設定を行います。

```bash
# 基本的な初期化
ci-run init

# 既存ファイルを強制上書き
ci-run init --force
```

**生成されるファイル:**

`.actrc`:

```bash
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-20.04=catthehacker/ubuntu:act-20.04
--container-daemon-socket /var/run/docker.sock
```

`ci-helper.toml`:

```toml
[logging]
level = "INFO"
save_logs = true

[act]
platform = "ubuntu-latest=catthehacker/ubuntu:act-latest"

[output]
default_format = "markdown"
```

`.env.example`:

```bash
# GitHub Actions シークレット
GITHUB_TOKEN=your_github_token_here

# カスタム環境変数
MY_SECRET=your_secret_here
```

### doctor コマンド

環境の健全性をチェックします。

```bash
# 基本チェック
ci-run doctor

# 詳細情報付きチェック
ci-run doctor --verbose

# 特定のガイドを表示
ci-run doctor --guide act
ci-run doctor --guide docker
ci-run doctor --guide workflows
```

**チェック項目:**

- act コマンドの存在とバージョン
- Docker デーモンの実行状態
- .github/workflows ディレクトリの存在
- ワークフローファイルの構文
- 設定ファイルの妥当性
- ディスク容量

### test コマンド

ワークフローをローカルで実行します。

#### 基本的な実行

```bash
# 全ワークフローを実行
ci-run test

# 特定のワークフローを実行
ci-run test --workflow ci.yml

# 複数のワークフローを実行
ci-run test -w test.yml -w lint.yml -w build.yml
```

#### 出力オプション

```bash
# 詳細出力
ci-run test --verbose

# AI用Markdown形式で出力
ci-run test --format markdown

# JSON形式で出力
ci-run test --format json

# ログを保存しない
ci-run test --no-save
```

#### 高度な機能

```bash
# 前回実行との差分を表示
ci-run test --diff

# 既存ログを解析（act実行なし）
ci-run test --dry-run --log .ci-helper/logs/act_20231215_103000.log

# 特定のジョブのみ実行
ci-run test --workflow test.yml --job unit-tests
```

### logs コマンド

実行ログを管理します。

```bash
# 実行履歴を表示
ci-run logs

# 最新5件のログを表示
ci-run logs --limit 5

# 特定のパターンでフィルタ
ci-run logs --filter "test"

# 詳細情報付きで表示
ci-run logs --format detailed
```

### secrets コマンド

シークレット管理を行います。

```bash
# 設定ファイル内のシークレットをチェック
ci-run secrets check

# ログファイル内のシークレットをスキャン
ci-run secrets scan .ci-helper/logs/act_20231215_103000.log

# 環境変数の検証
ci-run secrets validate
```

### clean コマンド

キャッシュとログをクリーンアップします。

```bash
# 対話的クリーンアップ
ci-run clean

# ログファイルのみ削除
ci-run clean --logs-only

# キャッシュファイルのみ削除
ci-run clean --cache-only

# 全データを削除
ci-run clean --all

# 7日より古いファイルを削除
ci-run clean --older-than 7

# 確認なしで実行
ci-run clean --all --yes
```

## 実用的な使用例

### 例 1: 基本的な CI/CD ワークフロー

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: pytest
```

```bash
# ワークフローをローカルで実行
ci-run test --workflow ci.yml --verbose

# 失敗した場合、AI用フォーマットで出力
ci-run test --workflow ci.yml --format markdown
```

### 例 2: 複数環境でのテスト

```yaml
# .github/workflows/matrix.yml
name: Matrix Test
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run tests
        run: python -m pytest
```

```bash
# マトリックスワークフローを実行
ci-run test --workflow matrix.yml

# 特定のPythonバージョンのみテスト
ci-run test --workflow matrix.yml --matrix python-version=3.12
```

### 例 3: ビルドとデプロイ

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build application
        run: |
          npm install
          npm run build
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: build-files
          path: dist/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v3
        with:
          name: build-files
      - name: Deploy to staging
        run: echo "Deploying to staging..."
```

```bash
# ビルドジョブのみ実行
ci-run test --workflow deploy.yml --job build

# 全体のワークフローを実行
ci-run test --workflow deploy.yml
```

### 例 4: 失敗の分析とデバッグ

```bash
# テストを実行して失敗を分析
ci-run test --workflow test.yml --format markdown > failures.md

# 前回実行との差分を確認
ci-run test --workflow test.yml --diff

# 既存のログを再分析
ci-run test --dry-run --log .ci-helper/logs/act_20231215_103000.log --format json
```

## 設定のカスタマイズ

### プロジェクト固有の設定

```toml
# ci-helper.toml
[logging]
level = "DEBUG"
save_logs = true
max_log_files = 100

[act]
platform = "ubuntu-latest=catthehacker/ubuntu:act-latest"
container_architecture = "linux/amd64"
default_branch = "main"
secrets_file = ".env"

[output]
default_format = "markdown"
token_limit = 8000
context_lines = 5
highlight_errors = true

[cache]
max_size_mb = 1000
auto_cleanup = true
retention_days = 14

[security]
mask_secrets = true
allowed_env_vars = ["CI", "GITHUB_*", "NODE_*"]
```

### 環境変数での設定

```bash
# ログレベルを設定
export CI_HELPER_LOG_LEVEL=DEBUG

# デフォルトフォーマットを設定
export CI_HELPER_DEFAULT_FORMAT=json

# act設定
export CI_HELPER_ACT_PLATFORM="ubuntu-latest=catthehacker/ubuntu:act-latest"

# セキュリティ設定
export CI_HELPER_MASK_SECRETS=true
```

## ワークフロー最適化のヒント

### 1. 効率的な Docker イメージの選択

```bash
# 軽量イメージを使用
-P ubuntu-latest=catthehacker/ubuntu:act-latest

# 特定のツールが必要な場合
-P ubuntu-latest=catthehacker/ubuntu:full-latest
```

### 2. キャッシュの活用

```yaml
# .github/workflows/optimized.yml
- name: Cache dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 3. 並列実行の最適化

```bash
# 複数のワークフローを並列実行
ci-run test -w test.yml -w lint.yml -w build.yml --parallel
```

### 4. ログサイズの管理

```toml
[logging]
max_log_size_mb = 50
compress_old_logs = true

[output]
truncate_long_lines = true
max_context_lines = 10
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. ワークフローが見つからない

```bash
# ワークフローファイルを確認
ls -la .github/workflows/

# doctorで診断
ci-run doctor --guide workflows
```

#### 2. Docker イメージのプル失敗

```bash
# 手動でイメージをプル
docker pull catthehacker/ubuntu:act-latest

# ネットワーク設定を確認
ci-run doctor --guide docker
```

#### 3. メモリ不足

```bash
# 古いログを削除
ci-run clean --older-than 7

# キャッシュサイズを制限
# ci-helper.tomlで設定
[cache]
max_size_mb = 200
```

#### 4. 権限エラー

```bash
# Dockerグループに追加
sudo usermod -aG docker $USER
newgrp docker

# ファイル権限を確認
ls -la .ci-helper/
```

### デバッグ手法

```bash
# 詳細ログを有効化
ci-run --verbose test --workflow problematic.yml

# ステップバイステップ実行
ci-run test --workflow test.yml --step-by-step

# 特定のステップのみ実行
ci-run test --workflow test.yml --step "Run tests"
```

## AI統合機能

ci-helper にはAI統合機能が含まれており、CI/CDの失敗ログを自動的に分析し、問題の原因特定と修正提案を提供します。

### AI分析の基本使用方法

#### 基本的なログ分析

```bash
# 最新のテスト結果をAI分析
ci-run analyze

# 特定のログファイルを分析
ci-run analyze --log .ci-helper/logs/act_20241019_120000.log

# 複数のログファイルを比較分析
ci-run analyze --log log1.txt --log log2.txt --compare
```

#### プロバイダーとモデルの選択

```bash
# OpenAI GPT-4を使用
ci-run analyze --provider openai --model gpt-4

# Anthropic Claudeを使用
ci-run analyze --provider anthropic --model claude-3-5-sonnet-20241022

# ローカルモデルを使用（Ollama）
ci-run analyze --provider local --model llama3.1
```

#### 分析オプション

```bash
# 修正提案を生成
ci-run analyze --fix

# 詳細な根本原因分析
ci-run analyze --deep-analysis

# セキュリティ問題に特化した分析
ci-run analyze --security-focus

# パフォーマンス問題の分析
ci-run analyze --performance-focus
```

### 対話モード

対話モードでは、AIとリアルタイムで会話しながら問題を解決できます。

```bash
# 対話モードを開始
ci-run analyze --interactive

# 特定のログで対話モード
ci-run analyze --log failure.log --interactive

# 修正提案付きで対話モード
ci-run analyze --interactive --fix
```

**対話モードの使用例:**

```
$ ci-run analyze --interactive

🤖 AI Assistant: ログを分析しました。テストの失敗原因を特定できます。

主な問題:
1. Python依存関係の競合
2. 環境変数の未設定
3. テストデータベースの接続エラー

どの問題から詳しく調べますか？ (1-3)

> 1

🤖 AI Assistant: 依存関係の競合について詳しく説明します...

修正方法を提案しますか？ (y/n)

> y

🤖 AI Assistant: 以下の修正を提案します:

1. requirements.txtの更新
2. 仮想環境の再構築
3. 依存関係の固定

実際のファイルを修正しますか？ (y/n)
```

### AI機能のセットアップ

#### APIキーの設定

```bash
# 環境変数で設定
export OPENAI_API_KEY="sk-proj-your-openai-key"
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-key"

# .envファイルで設定
echo "OPENAI_API_KEY=sk-proj-your-key" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-your-key" >> .env

# 設定ファイルで管理
ci-run config set ai.openai.api_key "sk-proj-your-key"
ci-run config set ai.anthropic.api_key "sk-ant-your-key"
```

#### AI環境の確認

```bash
# AI機能の動作確認
ci-run doctor --ai

# 利用可能なプロバイダーを確認
ci-run analyze --list-providers

# 利用可能なモデルを確認
ci-run analyze --list-models --provider openai

# 使用統計を確認
ci-run analyze --stats
```

### 高度な分析機能

#### カスタムプロンプト

```bash
# カスタムプロンプトファイルを使用
ci-run analyze --prompt-file custom_analysis.txt

# インラインプロンプト
ci-run analyze --prompt "このエラーの原因をセキュリティの観点から分析してください"
```

#### 分析結果の保存と共有

```bash
# 分析結果をファイルに保存
ci-run analyze --output analysis_report.md

# JSON形式で保存
ci-run analyze --output report.json --format json

# HTMLレポートを生成
ci-run analyze --output report.html --format html
```

#### バッチ分析

```bash
# 複数のログファイルを一括分析
ci-run analyze --batch .ci-helper/logs/*.log

# 日付範囲で分析
ci-run analyze --date-range "2024-01-01 to 2024-01-31"

# 失敗パターンの傾向分析
ci-run analyze --trend-analysis --days 30
```

### 実用的なAI統合ワークフロー

#### 基本的な問題解決フロー

```bash
# 1. テストを実行
ci-run test --workflow test.yml

# 2. 失敗した場合、即座にAI分析
ci-run analyze --auto-fix

# 3. 修正提案を確認して適用
ci-run analyze --apply-fixes

# 4. 修正後に再テスト
ci-run test --workflow test.yml --verify-fix
```

#### 継続的な改善ワークフロー

```bash
# 週次の失敗パターン分析
ci-run analyze --weekly-report

# 改善提案の生成
ci-run analyze --improvement-suggestions

# テスト品質の評価
ci-run analyze --quality-assessment
```

#### チーム共有ワークフロー

```bash
# チーム向けレポート生成
ci-run analyze --team-report --output team_analysis.md

# Slack通知付きで分析
ci-run analyze --notify-slack --channel "#ci-alerts"

# GitHub Issueとして問題を報告
ci-run analyze --create-issue --repo "owner/repo"
```

### AI分析の設定カスタマイズ

#### 設定ファイルでの詳細設定

```toml
# ci-helper.toml
[ai]
default_provider = "anthropic"
default_model = "claude-3-5-sonnet-20241022"
max_tokens = 4000
temperature = 0.1
timeout = 30

[ai.analysis]
include_context_lines = 10
focus_on_errors = true
generate_fixes = true
deep_analysis = false

[ai.prompts]
analysis_template = "templates/analysis.txt"
fix_template = "templates/fix.txt"
interactive_template = "templates/interactive.txt"

[ai.output]
default_format = "markdown"
include_metadata = true
highlight_code = true
generate_summary = true

[ai.cost_management]
max_monthly_cost = 50.0
warn_at_cost = 40.0
track_usage = true
```

#### 環境変数での設定

```bash
# AI機能の有効/無効
export CI_HELPER_AI_ENABLED=true

# デフォルトプロバイダー
export CI_HELPER_AI_PROVIDER=anthropic

# コスト制限
export CI_HELPER_AI_MAX_COST=50.0

# 分析の詳細レベル
export CI_HELPER_AI_ANALYSIS_DEPTH=deep
```

### トラブルシューティング

#### よくある問題

```bash
# APIキーが無効な場合
ci-run analyze --validate-keys

# 接続問題の診断
ci-run doctor --ai --verbose

# キャッシュの問題
ci-run clean --ai-cache

# 使用量制限に達した場合
ci-run analyze --check-limits
```

#### デバッグモード

```bash
# 詳細なデバッグ情報
ci-run analyze --debug

# API通信のログ
ci-run analyze --trace-api

# プロンプトの確認
ci-run analyze --show-prompt
```

詳細については以下のガイドを参照してください：

- [AI統合機能ガイド](ai-integration.md) - AI機能の詳細な使用方法
- [APIキー設定ガイド](api-key-setup.md) - APIキーの取得と設定方法
- [AI設定リファレンス](ai-configuration.md) - AI機能の詳細設定
- [AIトラブルシューティング](ai-troubleshooting.md) - AI機能の問題解決

## 次のステップ

- [設定リファレンス](configuration.md) - 詳細な設定オプション
- [トラブルシューティング](troubleshooting.md) - 問題解決ガイド
- [AI統合機能ガイド](ai-integration.md) - AI機能の使用方法
- [セキュリティガイド](security-guide.md) - セキュリティのベストプラクティス
- [API リファレンス](api-reference.md) - 内部 API 仕様
- [開発者ガイド](development.md) - 拡張とカスタマイズ
