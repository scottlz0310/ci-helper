# ci-helper

`act`を使用したローカル CI/CD パイプライン検証と AI 統合機能を提供する包括的な CLI ツールです。

## 概要

ci-helper は、GitHub Actions ワークフローをローカルで実行し、失敗を分析して AI 対応の出力を生成するツールです。従来の CI/CD フィードバックループの非効率性を解決し、開発者の生産性を向上させます。

### 主な特徴

- 🚀 **ローカル CI 検証**: GitHub にプッシュすることなく、`act`を使用してワークフローをローカル実行
- 🔍 **インテリジェントなログ解析**: 失敗情報の自動抽出と AI 消費用フォーマット
- 📊 **包括的なログ管理**: 実行履歴の保存、比較、差分表示
- 🛡️ **セキュリティ重視**: シークレット管理と自動サニタイゼーション
- 🎯 **AI 統合準備**: 複数の AI プロバイダーとの統合に対応

## インストール

### 前提条件

- Python 3.12 以上
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- [act](https://github.com/nektos/act) コマンド
- [Docker](https://www.docker.com/) デーモン

### uv を使用したインストール

```bash
# リポジトリからインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# インストール確認
ci-run --version
```

### 開発用インストール

```bash
# リポジトリをクローン
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper

# 依存関係をインストール
uv sync

# 開発モードで実行
uv run python -m ci_helper.cli --help
```

## クイックスタート

### 1. 環境セットアップ

```bash
# 初期設定ファイルを生成
ci-run init

# 環境依存関係をチェック
ci-run doctor
```

### 2. ワークフローの実行

```bash
# 全ワークフローを実行
ci-run test

# 特定のワークフローを実行
ci-run test --workflow test.yml

# 詳細出力で実行
ci-run test --verbose

# AI用フォーマットで出力
ci-run test --format markdown
ci-run test --format json
```

### 3. ログ管理

```bash
# 実行履歴を表示
ci-run logs

# 前回実行との差分を表示
ci-run test --diff

# 既存ログを解析（ドライラン）
ci-run test --dry-run --log path/to/log.txt
```

### 4. メンテナンス

```bash
# キャッシュをクリーンアップ
ci-run clean

# ログのみ削除
ci-run clean --logs-only

# 全データを削除
ci-run clean --all
```

## コマンドリファレンス

### `ci-run init`

設定ファイルテンプレートを生成します。

```bash
ci-run init [OPTIONS]
```

**オプション:**

- `--force`: 既存ファイルを上書き

**生成されるファイル:**

- `.actrc`: act 設定ファイル
- `ci-helper.toml`: プロジェクト設定
- `.env.example`: 環境変数テンプレート

### `ci-run doctor`

環境依存関係をチェックします。

```bash
ci-run doctor [OPTIONS]
```

**オプション:**

- `--verbose, -v`: 詳細な診断情報を表示
- `--guide GUIDE`: 特定の復旧ガイドを表示

**チェック項目:**

- act コマンドのインストール状態
- Docker デーモンの実行状態
- .github/workflows ディレクトリの存在
- 設定ファイルの状態

### `ci-run test`

CI/CD ワークフローをローカルで実行します。

```bash
ci-run test [OPTIONS]
```

**オプション:**

- `--workflow, -w WORKFLOW`: 実行するワークフローファイル（複数指定可能）
- `--verbose, -v`: 詳細な実行情報を表示
- `--format FORMAT`: 出力フォーマット（markdown, json）
- `--dry-run`: 既存ログを解析（act 実行なし）
- `--log LOG_FILE`: ドライラン用のログファイル
- `--diff`: 前回実行との差分を表示
- `--save/--no-save`: ログ保存の制御（デフォルト: 保存）

### `ci-run logs`

実行ログを管理・表示します。

```bash
ci-run logs [OPTIONS]
```

**オプション:**

- `--limit, -n NUMBER`: 表示するログ数の制限
- `--format FORMAT`: 出力フォーマット
- `--filter PATTERN`: ログファイル名のフィルタリング

### `ci-run secrets`

シークレット管理と検証を行います。

```bash
ci-run secrets [OPTIONS] COMMAND
```

**サブコマンド:**

- `check`: 設定ファイル内のシークレット検出
- `scan LOG_FILE`: ログファイル内のシークレット検出

### `ci-run clean`

キャッシュとログをクリーンアップします。

```bash
ci-run clean [OPTIONS]
```

**オプション:**

- `--logs-only`: ログファイルのみ削除
- `--cache-only`: キャッシュファイルのみ削除
- `--all`: 全データを削除
- `--older-than DAYS`: 指定日数より古いファイルのみ削除

## 設定

### 設定ファイル階層

設定は以下の優先順位で読み込まれます：

1. コマンドライン引数（最高優先度）
2. 環境変数（`CI_HELPER_*`）
3. プロジェクト設定ファイル（`ci-helper.toml`）
4. デフォルト値（最低優先度）

### 設定例

```toml
# ci-helper.toml

[logging]
level = "INFO"
save_logs = true
max_log_files = 50

[act]
platform = "ubuntu-latest=catthehacker/ubuntu:act-latest"
container_architecture = "linux/amd64"
default_branch = "main"

[output]
default_format = "markdown"
token_limit = 4000
context_lines = 3

[cache]
max_size_mb = 500
auto_cleanup = true
retention_days = 30

[security]
mask_secrets = true
allowed_env_vars = ["CI", "GITHUB_*"]
```

### 環境変数

```bash
# API設定
export CI_HELPER_LOG_LEVEL=DEBUG
export CI_HELPER_SAVE_LOGS=true

# act設定
export CI_HELPER_ACT_PLATFORM="ubuntu-latest=catthehacker/ubuntu:act-latest"

# セキュリティ設定
export CI_HELPER_MASK_SECRETS=true
```

## トラブルシューティング

### よくある問題

#### 1. act が見つからない

**エラー:** `act command not found`

**解決方法:**

```bash
# macOS (Homebrew)
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows (Chocolatey)
choco install act-cli
```

#### 2. Docker デーモンが起動していない

**エラー:** `Cannot connect to the Docker daemon`

**解決方法:**

```bash
# Docker Desktopを起動するか、systemdでDockerを開始
sudo systemctl start docker

# Docker Desktopの場合は、アプリケーションを起動
```

#### 3. ワークフローディレクトリが見つからない

**エラー:** `.github/workflows directory not found`

**解決方法:**

```bash
# ワークフローディレクトリを作成
mkdir -p .github/workflows

# サンプルワークフローを作成
cat > .github/workflows/test.yml << EOF
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Hello, World!"
EOF
```

#### 4. 権限エラー

**エラー:** `Permission denied`

**解決方法:**

```bash
# Dockerグループにユーザーを追加
sudo usermod -aG docker $USER

# 新しいシェルセッションを開始
newgrp docker
```

#### 5. メモリ不足

**エラー:** `Out of memory`

**解決方法:**

```bash
# 古いログを削除
ci-run clean --older-than 7

# キャッシュサイズを制限
# ci-helper.tomlで設定
[cache]
max_size_mb = 100
```

### デバッグ方法

#### 詳細ログの有効化

```bash
# 詳細モードで実行
ci-run --verbose doctor
ci-run --verbose test

# 環境変数で設定
export CI_HELPER_LOG_LEVEL=DEBUG
ci-run test
```

#### ログファイルの確認

```bash
# 最新のログを確認
ci-run logs --limit 1

# 特定のログファイルを表示
cat .ci-helper/logs/act_TIMESTAMP.log
```

#### 設定の確認

```bash
# 設定状態を確認
ci-run doctor --verbose

# 設定ファイルの検証
ci-run secrets check
```

## 開発

### 開発環境のセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper

# 開発依存関係をインストール
uv sync

# pre-commitフックをインストール
uv run pre-commit install
```

### テストの実行

```bash
# 全テストを実行
uv run pytest

# カバレッジ付きで実行
uv run pytest --cov=ci_helper --cov-report=html

# 特定のテストを実行
uv run pytest tests/unit/test_config.py
uv run pytest tests/integration/
```

### コード品質チェック

```bash
# リントとフォーマット
uv run ruff check
uv run ruff format

# 型チェック
uv run mypy src/ci_helper

# 全チェックを実行
uv run pre-commit run --all-files
```

### ビルドとパッケージング

```bash
# パッケージをビルド
uv build

# ローカルインストール
uv tool install .

# 開発モードでインストール
uv tool install --editable .
```

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

プロジェクトへの貢献を歓迎します！以下の手順に従ってください：

1. このリポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

### 貢献ガイドライン

- コードは日本語でコメントを記述
- テストを追加して機能をカバー
- pre-commit フックを使用してコード品質を維持
- 変更内容を明確に説明

## サポート

- 🐛 **バグレポート**: [Issues](https://github.com/scottlz0310/ci-helper/issues)
- 💡 **機能リクエスト**: [Issues](https://github.com/scottlz0310/ci-helper/issues)
- 📖 **ドキュメント**: [Wiki](https://github.com/scottlz0310/ci-helper/wiki)
- 💬 **ディスカッション**: [Discussions](https://github.com/scottlz0310/ci-helper/discussions)

## 関連プロジェクト

- [act](https://github.com/nektos/act) - ローカル GitHub Actions 実行
- [uv](https://github.com/astral-sh/uv) - 高速 Python パッケージマネージャー
- [GitHub Actions](https://github.com/features/actions) - CI/CD プラットフォーム
