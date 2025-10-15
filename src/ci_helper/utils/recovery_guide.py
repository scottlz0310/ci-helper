"""
エラー復旧ガイド

各種エラーに対する詳細な復旧手順を提供します。
"""

from __future__ import annotations

import platform

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


class RecoveryGuide:
    """エラー復旧ガイド"""

    @staticmethod
    def get_act_installation_guide() -> str:
        """act インストールガイドを取得"""
        system = platform.system().lower()

        if system == "darwin":  # macOS
            return """
# act インストール手順 (macOS)

## Homebrew を使用する場合 (推奨)
```bash
brew install act
```

## 手動インストール
1. GitHub Releases からダウンロード: https://github.com/nektos/act/releases
2. ダウンロードしたファイルを展開
3. 実行ファイルを /usr/local/bin に移動:
   ```bash
   sudo mv act /usr/local/bin/
   sudo chmod +x /usr/local/bin/act
   ```

## インストール確認
```bash
act --version
```
"""
        elif system == "linux":
            return """
# act インストール手順 (Linux)

## Ubuntu/Debian の場合
```bash
# GitHub CLI を使用してインストール
gh extension install https://github.com/nektos/act
```

## 手動インストール
1. GitHub Releases からダウンロード: https://github.com/nektos/act/releases
2. 適切なアーキテクチャのファイルをダウンロード
3. ファイルを展開して実行可能にする:
   ```bash
   tar -xzf act_Linux_x86_64.tar.gz
   sudo mv act /usr/local/bin/
   sudo chmod +x /usr/local/bin/act
   ```

## インストール確認
```bash
act --version
```
"""
        elif system == "windows":
            return """
# act インストール手順 (Windows)

## Chocolatey を使用する場合 (推奨)
```powershell
choco install act-cli
```

## Scoop を使用する場合
```powershell
scoop install act
```

## 手動インストール
1. GitHub Releases からダウンロード: https://github.com/nektos/act/releases
2. Windows用のzipファイルをダウンロード
3. ファイルを展開してPATHの通ったディレクトリに配置

## インストール確認
```powershell
act --version
```
"""
        else:
            return """
# act インストール手順

## 手動インストール
1. GitHub Releases からダウンロード: https://github.com/nektos/act/releases
2. お使いのOSとアーキテクチャに適したファイルをダウンロード
3. ファイルを展開してPATHの通ったディレクトリに配置

## インストール確認
```bash
act --version
```
"""

    @staticmethod
    def get_docker_installation_guide() -> str:
        """Docker インストールガイドを取得"""
        system = platform.system().lower()

        if system == "darwin":  # macOS
            return """
# Docker インストール手順 (macOS)

## Docker Desktop のインストール
1. Docker Desktop for Mac をダウンロード: https://www.docker.com/products/docker-desktop/
2. ダウンロードした .dmg ファイルを開く
3. Docker.app を Applications フォルダにドラッグ
4. Docker Desktop を起動

## Homebrew を使用する場合
```bash
brew install --cask docker
```

## 起動確認
- Docker Desktop が起動していることを確認
- メニューバーに Docker アイコンが表示される
- ターミナルで確認:
  ```bash
  docker --version
  docker info
  ```
"""
        elif system == "linux":
            return """
# Docker インストール手順 (Linux)

## Ubuntu/Debian の場合
```bash
# 古いバージョンを削除
sudo apt-get remove docker docker-engine docker.io containerd runc

# 必要なパッケージをインストール
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg lsb-release

# Docker の公式GPGキーを追加
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# リポジトリを追加
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker Engine をインストール
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# ユーザーを docker グループに追加
sudo usermod -aG docker $USER
```

## 起動確認
```bash
sudo systemctl start docker
sudo systemctl enable docker
docker --version
docker info
```
"""
        elif system == "windows":
            return """
# Docker インストール手順 (Windows)

## Docker Desktop のインストール
1. Docker Desktop for Windows をダウンロード: https://www.docker.com/products/docker-desktop/
2. インストーラーを実行
3. WSL 2 バックエンドを有効にする（推奨）
4. システムを再起動
5. Docker Desktop を起動

## 起動確認
- Docker Desktop が起動していることを確認
- システムトレイに Docker アイコンが表示される
- PowerShell で確認:
  ```powershell
  docker --version
  docker info
  ```
"""
        else:
            return """
# Docker インストール手順

お使いのオペレーティングシステムに応じて、Docker の公式ドキュメントを参照してください:
https://docs.docker.com/get-docker/

## 起動確認
```bash
docker --version
docker info
```
"""

    @staticmethod
    def get_workflow_setup_guide() -> str:
        """ワークフローセットアップガイドを取得"""
        return """
# GitHub Actions ワークフローセットアップ

## ディレクトリ構造の作成
```bash
mkdir -p .github/workflows
```

## サンプルワークフローファイルの作成

### 基本的なCI ワークフロー (.github/workflows/ci.yml)
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run tests
      run: npm test
    
    - name: Run linter
      run: npm run lint
```

### Python プロジェクト用ワークフロー (.github/workflows/python.yml)
```yaml
name: Python CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python -m pytest
```

## ワークフローファイルの確認
```bash
ls -la .github/workflows/
```
"""

    @staticmethod
    def get_disk_space_cleanup_guide() -> str:
        """ディスク容量クリーンアップガイドを取得"""
        return """
# ディスク容量クリーンアップガイド

## ci-helper のクリーンアップ
```bash
# ログファイルのみ削除
ci-run clean --logs-only

# すべてのキャッシュを削除
ci-run clean --all
```

## Docker のクリーンアップ
```bash
# 未使用のコンテナ、ネットワーク、イメージを削除
docker system prune -a

# 未使用のボリュームも削除
docker system prune -a --volumes
```

## 一般的なクリーンアップ (Linux/macOS)
```bash
# 一時ファイルの削除
sudo rm -rf /tmp/*

# ログファイルの削除
sudo journalctl --vacuum-time=7d  # 7日より古いログを削除
```

## 一般的なクリーンアップ (Windows)
```powershell
# 一時ファイルの削除
Remove-Item -Path $env:TEMP\\* -Recurse -Force

# ディスククリーンアップツールの実行
cleanmgr
```

## ディスク使用量の確認
```bash
# Linux/macOS
df -h
du -sh .ci-helper/

# Windows
dir /s .ci-helper
```
"""

    @staticmethod
    def get_troubleshooting_guide() -> str:
        """トラブルシューティングガイドを取得"""
        return """
# トラブルシューティングガイド

## よくある問題と解決方法

### 1. act コマンドが見つからない
**症状**: `act: command not found`
**解決方法**: act をインストールしてください
```bash
ci-run doctor  # 詳細な診断を実行
```

### 2. Docker デーモンが実行されていない
**症状**: `Cannot connect to the Docker daemon`
**解決方法**: Docker Desktop を起動してください

### 3. ワークフローファイルが見つからない
**症状**: `No workflow files found`
**解決方法**: 
- `.github/workflows/` ディレクトリを作成
- `.yml` または `.yaml` ファイルを配置

### 4. 権限エラー
**症状**: `Permission denied`
**解決方法**:
```bash
# Linux/macOS の場合
sudo chown -R $USER:$USER .ci-helper/
chmod -R 755 .ci-helper/
```

### 5. ネットワークエラー
**症状**: `Failed to pull Docker image`
**解決方法**:
- インターネット接続を確認
- プロキシ設定を確認
- Docker の設定を確認

### 6. メモリ不足
**症状**: `Out of memory` または実行が異常に遅い
**解決方法**:
- Docker Desktop のメモリ設定を増やす
- 不要なコンテナを停止: `docker stop $(docker ps -q)`

## ログの確認方法
```bash
# 詳細な診断情報を表示
ci-run doctor --verbose

# 最新のログを確認
ci-run logs

# 特定のログファイルを確認
cat .ci-helper/logs/act_TIMESTAMP.log
```

## サポートが必要な場合
1. `ci-run doctor --verbose` の出力を確認
2. エラーメッセージの全文を記録
3. 実行環境の情報を収集:
   - OS とバージョン
   - Docker のバージョン
   - act のバージョン
"""

    @staticmethod
    def display_recovery_guide(guide_type: str) -> None:
        """復旧ガイドを表示"""
        guides = {
            "act": RecoveryGuide.get_act_installation_guide(),
            "docker": RecoveryGuide.get_docker_installation_guide(),
            "workflows": RecoveryGuide.get_workflow_setup_guide(),
            "disk_space": RecoveryGuide.get_disk_space_cleanup_guide(),
            "troubleshooting": RecoveryGuide.get_troubleshooting_guide(),
        }

        if guide_type not in guides:
            console.print(f"[red]不明なガイドタイプ: {guide_type}[/red]")
            return

        markdown_content = guides[guide_type]
        markdown = Markdown(markdown_content)

        panel = Panel(
            markdown, title=f"[bold blue]復旧ガイド: {guide_type}[/bold blue]", border_style="blue", expand=False
        )

        console.print(panel)

    @staticmethod
    def get_quick_fixes() -> dict[str, list[str]]:
        """よくある問題のクイックフィックスを取得"""
        return {
            "act_not_found": [
                "act をインストール: brew install act (macOS) または GitHub Releases からダウンロード",
                "PATH に act が含まれていることを確認",
                "インストール後にターミナルを再起動",
            ],
            "docker_not_running": [
                "Docker Desktop を起動",
                "Docker サービスの状態を確認: sudo systemctl status docker (Linux)",
                "Docker Desktop の設定を確認",
            ],
            "no_workflows": [
                ".github/workflows ディレクトリを作成",
                "ワークフローファイル (.yml/.yaml) を配置",
                "ファイル名と拡張子を確認",
            ],
            "permission_denied": [
                "ファイルの所有者を確認: ls -la",
                "権限を修正: chmod 755 <file>",
                "sudo を使用して実行",
            ],
            "disk_space_low": [
                "ci-run clean を実行",
                "Docker の未使用リソースを削除: docker system prune",
                "一時ファイルを削除",
            ],
        }
