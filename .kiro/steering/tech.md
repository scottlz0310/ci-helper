# 技術スタック

## コア技術

- **言語**: Python 3.12+
- **CLIフレームワーク**: Click（マルチコマンドグループ構造）
- **パッケージマネージャー**: uv
- **配布方法**: グローバルCLI利用のための`uv tool install`

## 主要依存関係

- **act**: ローカルGitHub Actionsランナー（外部依存）
- **Docker**: act実行用のコンテナランタイム
- **Click**: コマンド構造用のCLIフレームワーク
- **Rich**: 拡張ターミナル出力とフォーマット
- **TOML**: 設定ファイル解析
- **tiktoken**: AIモデル用のトークンカウント
- **pytest**: テストフレームワーク

## 外部ツール

- **act**: ローカルCI実行のためにグローバルインストールが必要
- **Docker**: actがコンテナ内でワークフローを実行するために必要
- **Git**: リポジトリ操作とワークフロー検出用

## ビルド・開発コマンド

### インストール

```bash
# リポジトリからインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 開発用インストール
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper
uv sync
uv pip install -e .
```

### テスト

```bash
# 全テスト実行
pytest

# カバレッジ付きで実行
pytest --cov=ci_helper --cov-report=html

# 特定のテストファイル実行
pytest tests/unit/test_extract_failures.py
```

### コード品質

```bash
# リントとフォーマット
ruff check
ruff format

# 型チェック
mypy src/ci_helper
```

### 開発環境セットアップ

```bash
# 開発依存関係のインストール
uv sync

# pre-commitフックのインストール
pre-commit install

# 全ファイルでpre-commit実行
pre-commit run --all-files
```

## アーキテクチャパターン

- **コマンドパターン**: 各CLIコマンドは独立したモジュール
- **プラグインアーキテクチャ**: AIプロバイダー用のモジュラー設計
- **設定階層**: CLIオプション > 環境変数 > 設定ファイル
- **エラーハンドリング**: ユーザーガイダンス付きの包括的エラー復旧
- **Async/Await**: AI API呼び出しと並行処理用（フェーズ3）

## セキュリティプラクティス

- APIキーは環境変数からのみ取得
- ログと出力でのシークレットフィルタリング
- 入力検証とサニタイゼーション
- 安全な一時ファイル処理

## 開発規約

- **コメント**: 日本語で記述
- **ドキュメント**: 日本語で作成
- **変数名**: 英語（Pythonの慣例に従う）
- **関数・クラス名**: 英語（Pythonの慣例に従う）
- **設定ファイル**: 日本語コメント付き
