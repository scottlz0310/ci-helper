# 技術スタック

## コア技術

- **言語**: Python 3.12+
- **CLI フレームワーク**: Click or Typer
- **パッケージマネージャー**: uv
- **配布方法**: グローバル CLI 利用のための`uv tool install`

## 主要依存関係

- **act**: ローカル GitHub Actions ランナー（外部依存）
- **Docker**: act 実行用のコンテナランタイム
- **Click**: コマンド構造用の CLI フレームワーク
- **Rich**: 拡張ターミナル出力とフォーマット
- **TOML**: 設定ファイル解析
- **tiktoken**: AI モデル用のトークンカウント
- **pytest**: テストフレームワーク

## 外部ツール

- **act**: ローカル CI 実行のためにグローバルインストールが必要
- **Docker**: act がコンテナ内でワークフローを実行するために必要
- **Git**: リポジトリ操作とワークフロー検出用

## Python 実行ルール（重要）

**⚠️ 必須ルール: `python3` コマンドの使用禁止**

- **禁止**: `python3` コマンドの直接使用
- **必須**: すべての Python 実行は `uv run` を使用
- **理由**: 依存関係の一貫性とプロジェクト環境の分離を保証

### 正しい実行方法

```bash
# ❌ 禁止 - python3 の直接使用
python3 -m ci_helper.cli --help
python3 test_script.py
python3 -m pytest

# ✅ 正しい - uv run を使用
uv run python -m ci_helper.cli --help
uv run python test_script.py
uv run pytest
```

## ビルド・開発コマンド

### インストール

```bash
# リポジトリからインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 開発用インストール
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper
uv sync
```

### テスト

```bash
# 全テスト実行
uv run pytest

# カバレッジ付きで実行
uv run pytest --cov=ci_helper --cov-report=html

# 特定のテストファイル実行
uv run pytest tests/unit/test_extract_failures.py
```

### コード品質

```bash
# リントとフォーマット
uv run ruff check
uv run ruff format

# 型チェック
uv run mypy src/ci_helper
```

### 開発環境セットアップ

```bash
# 開発依存関係のインストール
uv sync

# pre-commitフックのインストール
uv run pre-commit install

# 全ファイルでpre-commit実行
uv run pre-commit run --all-files

# 特定のフックのみ実行
uv run pre-commit run ruff
uv run pre-commit run mypy
```

### アプリケーション実行

```bash
# CLI実行
uv run python -m ci_helper.cli --help
uv run python -m ci_helper.cli doctor
uv run python -m ci_helper.cli init

# 開発用スクリプト実行
uv run python scripts/setup.py
uv run python -c "import ci_helper; print(ci_helper.__version__)"
```

## アーキテクチャパターン

- **コマンドパターン**: 各 CLI コマンドは独立したモジュール
- **プラグインアーキテクチャ**: AI プロバイダー用のモジュラー設計
- **設定階層**: CLI オプション > 環境変数 > 設定ファイル
- **エラーハンドリング**: ユーザーガイダンス付きの包括的エラー復旧
- **Async/Await**: AI API 呼び出しと並行処理用（フェーズ 3）

## セキュリティプラクティス

- API キーは環境変数からのみ取得
- ログと出力でのシークレットフィルタリング
- 入力検証とサニタイゼーション
- 安全な一時ファイル処理

## 開発規約

### コーディング規約

- **コメント**: 日本語で記述
- **ドキュメント**: 日本語で作成
- **変数名**: 英語（Python の慣例に従う）
- **関数・クラス名**: 英語（Python の慣例に従う）
- **設定ファイル**: 日本語コメント付き

### 実行環境規約

- **Python 実行**: 必ず `uv run python` を使用（`python3` 禁止）
- **パッケージ管理**: `uv` のみ使用（`pip` 直接使用禁止）
- **仮想環境**: `uv` が自動管理（手動での `venv` 作成禁止）
- **依存関係**: `pyproject.toml` で一元管理

### 禁止事項

- ❌ `python3` コマンドの直接使用
- ❌ `pip install` の直接使用
- ❌ 手動での仮想環境作成（`python -m venv`）
- ❌ システム Python への直接インストール

### 推奨事項

- ✅ すべての Python 実行は `uv run python` 経由
- ✅ 依存関係追加は `uv add <package>` 使用
- ✅ 開発依存関係は `uv add --dev <package>` 使用
- ✅ スクリプト実行は `uv run <script>` 使用
