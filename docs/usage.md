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

ci-helper にはAI統合機能が含まれており、CI/CDの失敗ログを自動的に分析できます。

### AI分析の基本使用方法

```bash
# 最新のテスト結果をAI分析
ci-run analyze

# 特定のログファイルを分析
ci-run analyze --log .ci-helper/logs/act_20241019_120000.log

# プロバイダーとモデルを指定
ci-run analyze --provider anthropic --model claude-3-5-sonnet-20241022

# 修正提案を生成
ci-run analyze --fix

# 対話モードで詳細分析
ci-run analyze --interactive
```

### AI機能のセットアップ

```bash
# APIキーを設定
export OPENAI_API_KEY="sk-proj-your-openai-key"
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-key"

# AI環境をチェック
ci-run doctor --ai

# 使用統計を確認
ci-run analyze --stats
```

### AI統合ワークフロー例

```bash
# 1. テストを実行
ci-run test --workflow test.yml

# 2. 失敗した場合、AI分析を実行
ci-run analyze --fix

# 3. 対話モードで詳細調査
ci-run analyze --interactive

# 4. 修正を適用して再テスト
ci-run test --workflow test.yml
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
