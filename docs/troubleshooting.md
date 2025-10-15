# トラブルシューティングガイド

このドキュメントでは、ci-helper の使用中に発生する可能性のある問題と、その解決方法について説明します。

## 一般的な問題

### 1. インストール関連の問題

#### Python バージョンエラー

**症状:**

```
ERROR: Python 3.12 or higher is required
```

**解決方法:**

```bash
# 現在のPythonバージョンを確認
python3 --version

# pyenvを使用してPython 3.12をインストール
curl https://pyenv.run | bash
pyenv install 3.12.0
pyenv global 3.12.0

# または、システムパッケージマネージャーを使用
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.12

# macOS (Homebrew)
brew install python@3.12
```

#### uv コマンドが見つからない

**症状:**

```
bash: uv: command not found
```

**解決方法:**

```bash
# uvをインストール
curl -LsSf https://astral.sh/uv/install.sh | sh

# PATHを更新
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# インストール確認
uv --version
```

#### ci-run コマンドが見つからない

**症状:**

```
bash: ci-run: command not found
```

**解決方法:**

```bash
# uvツールのパスを確認
uv tool list

# PATHにuvツールディレクトリを追加
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# または、再インストール
uv tool uninstall ci-helper
uv tool install git+https://github.com/scottlz0310/ci-helper.git
```

### 2. 依存関係の問題

#### act コマンドが見つからない

**症状:**

```
ERROR: act command not found
```

**解決方法:**

```bash
# macOS (Homebrew)
brew install act

# Linux (curl)
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows (Chocolatey)
choco install act-cli

# 手動インストール
# https://github.com/nektos/act/releases から適切なバイナリをダウンロード

# インストール確認
act --version
```

#### Docker デーモンが起動していない

**症状:**

```
ERROR: Cannot connect to the Docker daemon
```

**解決方法:**

```bash
# Docker デーモンを起動
sudo systemctl start docker

# 自動起動を有効化
sudo systemctl enable docker

# Docker Desktop (macOS/Windows)
# アプリケーションを起動

# ユーザーをDockerグループに追加
sudo usermod -aG docker $USER
newgrp docker

# 確認
docker run hello-world
```

### 3. 設定関連の問題

#### 設定ファイルの構文エラー

**症状:**

```
ERROR: Invalid TOML syntax in ci-helper.toml
```

**解決方法:**

```bash
# 設定ファイルの構文をチェック
python3 -c "import tomllib; tomllib.load(open('ci-helper.toml', 'rb'))"

# バックアップから復元
cp ci-helper.toml.backup ci-helper.toml

# 新しい設定ファイルを生成
ci-run init --force

# オンラインTOMLバリデーターを使用
# https://www.toml-lint.com/
```

#### 環境変数が認識されない

**症状:**

```
WARNING: Environment variable CI_HELPER_LOG_LEVEL not recognized
```

**解決方法:**

```bash
# 環境変数を確認
env | grep CI_HELPER

# 正しい形式で設定
export CI_HELPER_LOG_LEVEL=DEBUG
export CI_HELPER_SAVE_LOGS=true

# .envファイルを使用
echo "CI_HELPER_LOG_LEVEL=DEBUG" >> .env
echo "CI_HELPER_SAVE_LOGS=true" >> .env

# 設定の確認
ci-run doctor --verbose
```

### 4. ワークフロー実行の問題

#### ワークフローディレクトリが見つからない

**症状:**

```
ERROR: .github/workflows directory not found
```

**解決方法:**

```bash
# ディレクトリを作成
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
      - name: Hello World
        run: echo "Hello, World!"
EOF

# 確認
ci-run doctor
```

#### ワークフローファイルの構文エラー

**症状:**

```
ERROR: Invalid YAML syntax in workflow file
```

**解決方法:**

```bash
# YAML構文をチェック
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"

# オンラインYAMLバリデーターを使用
# https://www.yamllint.com/

# GitHub Actions構文をチェック
# https://github.com/rhymond/yaml-lint

# actでワークフローをリスト
act --list
```

#### Docker イメージのプル失敗

**症状:**

```
ERROR: Failed to pull Docker image
```

**解決方法:**

```bash
# 手動でイメージをプル
docker pull catthehacker/ubuntu:act-latest

# ネットワーク接続を確認
ping docker.io

# プロキシ設定（必要な場合）
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080

# 別のイメージを試す
# .actrcファイルを編集
echo "-P ubuntu-latest=ubuntu:latest" > .actrc
```

### 5. パフォーマンスの問題

#### メモリ不足

**症状:**

```
ERROR: Out of memory
```

**解決方法:**

```bash
# 古いログを削除
ci-run clean --older-than 7

# キャッシュサイズを制限
# ci-helper.tomlで設定
[cache]
max_size_mb = 200
auto_cleanup = true

# Dockerのメモリ制限を確認
docker system df
docker system prune

# システムメモリを確認
free -h
```

#### ディスク容量不足

**症状:**

```
ERROR: No space left on device
```

**解決方法:**

```bash
# ディスク使用量を確認
df -h
du -sh .ci-helper/

# 古いファイルを削除
ci-run clean --all

# Dockerの不要なデータを削除
docker system prune -a

# ログローテーションを設定
# ci-helper.tomlで設定
[logging]
max_log_files = 10
max_log_size_mb = 50
```

#### 実行が遅い

**症状:**
ワークフローの実行が異常に遅い

**解決方法:**

```bash
# 軽量なDockerイメージを使用
echo "-P ubuntu-latest=catthehacker/ubuntu:act-latest" > .actrc

# 不要なステップをスキップ
ci-run test --workflow test.yml --skip-steps "Setup Node.js"

# 並列実行を有効化
ci-run test --parallel

# キャッシュを活用
# ワークフローでactions/cacheを使用
```

### 6. セキュリティ関連の問題

#### シークレットが漏洩している

**症状:**

```
WARNING: Potential secret detected in logs
```

**解決方法:**

```bash
# ログ内のシークレットをスキャン
ci-run secrets scan .ci-helper/logs/act_20231215_103000.log

# 設定ファイル内のシークレットをチェック
ci-run secrets check

# シークレットマスキングを有効化
# ci-helper.tomlで設定
[security]
mask_secrets = true

# 環境変数を使用してシークレットを管理
echo "GITHUB_TOKEN=your_token_here" >> .env
```

#### 権限エラー

**症状:**

```
ERROR: Permission denied
```

**解決方法:**

```bash
# ファイル権限を確認
ls -la .ci-helper/

# 権限を修正
chmod -R 755 .ci-helper/

# Dockerグループの権限を確認
groups $USER

# Dockerグループに追加（必要な場合）
sudo usermod -aG docker $USER
newgrp docker
```

## 高度なトラブルシューティング

### デバッグモードの有効化

```bash
# 詳細ログを有効化
export CI_HELPER_LOG_LEVEL=DEBUG
ci-run --verbose doctor

# 特定のモジュールのデバッグ
export CI_HELPER_DEBUG_MODULES="ci_runner,log_extractor"
ci-run test --workflow test.yml
```

### ログファイルの分析

```bash
# 最新のログファイルを確認
ci-run logs --limit 1

# ログファイルの内容を表示
cat .ci-helper/logs/act_$(date +%Y%m%d)_*.log

# エラーパターンを検索
grep -i error .ci-helper/logs/*.log
grep -i "failed" .ci-helper/logs/*.log
```

### 設定の診断

```bash
# 設定の詳細を表示
ci-run doctor --verbose

# 設定ファイルの場所を確認
find . -name "ci-helper.toml" -o -name ".actrc"

# 環境変数を確認
env | grep CI_HELPER | sort
```

### ネットワーク問題の診断

```bash
# Docker Hubへの接続を確認
curl -I https://registry-1.docker.io/

# GitHub APIへの接続を確認
curl -I https://api.github.com/

# プロキシ設定を確認
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

## 問題報告

### バグレポートの作成

問題が解決しない場合は、以下の情報を含めてバグレポートを作成してください：

```bash
# システム情報を収集
ci-run doctor --verbose > system-info.txt

# バージョン情報
ci-run --version
uv --version
act --version
docker --version

# エラーログ
cp .ci-helper/logs/latest.log error.log

# 設定ファイル（シークレットを除く）
cp ci-helper.toml config-sample.toml
```

### GitHub Issues

バグレポートは以下のリポジトリに報告してください：
https://github.com/scottlz0310/ci-helper/issues

**テンプレート:**

```markdown
## 問題の説明

[問題の詳細な説明]

## 再現手順

1. [ステップ 1]
2. [ステップ 2]
3. [ステップ 3]

## 期待される動作

[期待される結果]

## 実際の動作

[実際の結果]

## 環境情報

- OS: [例: Ubuntu 22.04]
- Python: [例: 3.12.0]
- ci-helper: [例: 1.0.0]
- act: [例: 0.2.50]
- Docker: [例: 24.0.7]

## 追加情報

[ログファイル、設定ファイル、スクリーンショットなど]
```

## よくある質問 (FAQ)

### Q: ci-helper と act の違いは何ですか？

A: act は GitHub Actions をローカルで実行するツールです。ci-helper は act をラップして、より使いやすいインターフェース、ログ管理、失敗分析、AI 統合機能を提供します。

### Q: 既存の act の設定を使用できますか？

A: はい。ci-helper は既存の`.actrc`ファイルを尊重します。`ci-run init`を実行すると、既存の設定を保持しながら追加の設定ファイルを生成します。

### Q: Windows 環境でも動作しますか？

A: WSL2 環境での使用を推奨します。ネイティブ Windows 環境でも動作しますが、一部の機能に制限がある場合があります。

### Q: プライベートリポジトリで使用できますか？

A: はい。GitHub Actions と同様に、適切なアクセストークンを設定することでプライベートリポジトリでも使用できます。

### Q: 大きなワークフローでメモリ不足になります

A: キャッシュサイズの制限、古いログの削除、軽量な Docker イメージの使用を検討してください。詳細は「パフォーマンスの問題」セクションを参照してください。

## 関連リソース

- [GitHub Actions ドキュメント](https://docs.github.com/en/actions)
- [act プロジェクト](https://github.com/nektos/act)
- [Docker ドキュメント](https://docs.docker.com/)
- [uv ドキュメント](https://docs.astral.sh/uv/)
- [ci-helper GitHub リポジトリ](https://github.com/scottlz0310/ci-helper)
