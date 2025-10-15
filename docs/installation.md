# インストールガイド

このドキュメントでは、ci-helper のインストール方法と初期セットアップについて詳しく説明します。

## システム要件

### 必須要件

- **Python**: 3.12 以上
- **オペレーティングシステム**: Linux, macOS, Windows (WSL 推奨)
- **メモリ**: 最小 2GB、推奨 4GB 以上
- **ディスク容量**: 最小 500MB、推奨 2GB 以上

### 依存ツール

#### 1. uv (Python パッケージマネージャー)

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Homebrew (macOS)
brew install uv

# pip経由
pip install uv
```

#### 2. act (ローカル GitHub Actions 実行)

```bash
# macOS (Homebrew)
brew install act

# Linux (curl)
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows (Chocolatey)
choco install act-cli

# Windows (Scoop)
scoop install act

# GitHub Releases (手動)
# https://github.com/nektos/act/releases から適切なバイナリをダウンロード
```

#### 3. Docker

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io
sudo systemctl start docker
sudo systemctl enable docker

# CentOS/RHEL
sudo yum install docker
sudo systemctl start docker
sudo systemctl enable docker

# macOS
# Docker Desktop for Mac をダウンロード・インストール
# https://www.docker.com/products/docker-desktop

# Windows
# Docker Desktop for Windows をダウンロード・インストール
# https://www.docker.com/products/docker-desktop
```

## インストール方法

### 方法 1: uv ツールとしてインストール（推奨）

```bash
# GitHubリポジトリから直接インストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 特定のバージョンをインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git@v1.0.0

# インストール確認
ci-run --version
```

### 方法 2: 開発用インストール

```bash
# リポジトリをクローン
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper

# 依存関係をインストール
uv sync

# 開発モードでインストール
uv tool install --editable .

# または、直接実行
uv run python -m ci_helper.cli --help
```

### 方法 3: PyPI からインストール（将来対応予定）

```bash
# PyPIパッケージが公開された後
uv tool install ci-helper
```

## 初期セットアップ

### 1. 環境確認

```bash
# 依存関係をチェック
ci-run doctor

# 詳細な診断情報を表示
ci-run doctor --verbose
```

### 2. 設定ファイル生成

```bash
# プロジェクトディレクトリで実行
cd /path/to/your/project
ci-run init

# 強制的に上書き
ci-run init --force
```

生成されるファイル：

- `.actrc`: act 設定ファイル
- `ci-helper.toml`: プロジェクト設定
- `.env.example`: 環境変数テンプレート

### 3. 設定のカスタマイズ

#### ci-helper.toml の編集

```toml
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
```

#### .actrc の編集

```bash
# Dockerイメージの設定
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-20.04=catthehacker/ubuntu:act-20.04
-P ubuntu-18.04=catthehacker/ubuntu:act-18.04

# ボリュームマウント
--container-daemon-socket /var/run/docker.sock

# 環境変数
--env-file .env
```

#### 環境変数の設定

```bash
# .env ファイルを作成（.env.example をコピー）
cp .env.example .env

# 必要な環境変数を設定
echo "CI_HELPER_LOG_LEVEL=INFO" >> .env
echo "CI_HELPER_SAVE_LOGS=true" >> .env
```

## プラットフォーム別セットアップ

### Linux (Ubuntu/Debian)

```bash
# 必要なパッケージをインストール
sudo apt-get update
sudo apt-get install -y curl git python3 python3-pip docker.io

# uvをインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# actをインストール
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Dockerを設定
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 新しいシェルセッションを開始
newgrp docker

# ci-helperをインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git
```

### macOS

```bash
# Homebrewをインストール（未インストールの場合）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 必要なツールをインストール
brew install uv act docker

# Docker Desktopを起動
open -a Docker

# ci-helperをインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git
```

### Windows (WSL2 推奨)

```bash
# WSL2でUbuntuを使用
wsl --install -d Ubuntu

# WSL内でLinuxの手順に従う
# Docker Desktop for Windowsを使用する場合は、WSL統合を有効化
```

## 検証とテスト

### インストール確認

```bash
# バージョン確認
ci-run --version

# ヘルプ表示
ci-run --help

# 環境チェック
ci-run doctor
```

### サンプルプロジェクトでテスト

```bash
# テスト用ディレクトリを作成
mkdir ci-helper-test
cd ci-helper-test

# 初期化
ci-run init

# サンプルワークフローを作成
mkdir -p .github/workflows
cat > .github/workflows/test.yml << EOF
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Hello World
        run: echo "Hello, ci-helper!"
EOF

# テスト実行
ci-run test
```

## トラブルシューティング

### よくある問題

#### 1. Python バージョンエラー

```bash
# Pythonバージョンを確認
python3 --version

# 3.12以上が必要
# pyenvを使用してPythonをアップグレード
curl https://pyenv.run | bash
pyenv install 3.12.0
pyenv global 3.12.0
```

#### 2. uv コマンドが見つからない

```bash
# PATHを確認
echo $PATH

# uvのパスを追加
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### 3. Docker 権限エラー

```bash
# Dockerグループに追加
sudo usermod -aG docker $USER

# 再ログインまたは
newgrp docker

# 権限を確認
docker run hello-world
```

#### 4. act 実行エラー

```bash
# actの設定を確認
act --list

# Dockerイメージを事前にプル
docker pull catthehacker/ubuntu:act-latest

# .actrcファイルを確認
cat .actrc
```

### ログとデバッグ

```bash
# 詳細ログを有効化
export CI_HELPER_LOG_LEVEL=DEBUG
ci-run doctor --verbose

# ログファイルを確認
ls -la .ci-helper/logs/
cat .ci-helper/logs/latest.log
```

## アップデート

### ツールのアップデート

```bash
# ci-helperをアップデート
uv tool upgrade ci-helper

# または、再インストール
uv tool uninstall ci-helper
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 依存ツールのアップデート
brew upgrade act  # macOS
sudo apt-get update && sudo apt-get upgrade act  # Linux
```

### 設定の移行

```bash
# 設定をバックアップ
cp ci-helper.toml ci-helper.toml.backup

# 新しい設定テンプレートを生成
ci-run init --force

# 必要に応じて設定をマージ
```

## 次のステップ

インストールが完了したら、以下のドキュメントを参照してください：

- [使用方法ガイド](usage.md)
- [設定リファレンス](configuration.md)
- [トラブルシューティング](troubleshooting.md)
- [開発者ガイド](development.md)
