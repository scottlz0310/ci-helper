# ci-helper プロジェクト計画書 v2.1

`act` × `AI連携` のためのリポジトリ構成案（マルチコマンドCLI統一版）

---

## 📚 このリポジトリの目的

- AI開発プロセスにおいて、CI/CDパイプラインをローカルで反復的に検証できる環境を整備する
- ワークフローファイルを直接検証し、失敗箇所をAIが理解しやすい形式で提供する
- CI検証から修正までのサイクルを自動化し、開発者の生産性を向上させる

---

## 🔍 現状の問題点

1. **時間的な非効率性**
   - GitHub に push して Actions をトリガーしてから結果を待つ時間がかかる
   - フィードバックループが遅く、開発フローの遅延の原因

2. **手動作業の多さ**
   - エラーログを AI に渡す際の手動コピペが煩雑
   - GitHub CLI を使っても、ログ抽出作業自体の負荷が大きい

3. **ローカル検証の課題**
   - `act` でローカル検証は可能だが、ログが膨大
   - そのまま AI に渡すとコンテキスト制限に引っかかる
   - 重要な失敗箇所の特定が困難

---

## 💡 改善案

1. **ツールとしての配布**: `uv tool install` で任意のプロジェクトから利用可能に
2. **構造化された出力**: 失敗箇所を効率的に抽出し、AI が理解しやすい Markdown/JSON 形式に整形
3. **自動化サイクル**: コマンド一つで実行→確認→AI分析→修正提案のサイクルを実現
4. **トークン制限対策**: ログの圧縮・要約機能でコンテキスト制限を回避
5. **セキュリティ重視**: API キーなどの機密情報を安全に管理

---

## 🧱 リポジトリ構成

```
ci-helper/
├── src/
│   └── ci_helper/
│       ├── __init__.py
│       ├── cli.py                  # CLIエントリーポイント（マルチコマンド）
│       ├── commands/               # 各サブコマンドの実装
│       │   ├── __init__.py
│       │   ├── init.py            # initコマンド
│       │   ├── doctor.py          # doctorコマンド
│       │   ├── test.py            # testコマンド（メイン）
│       │   ├── logs.py            # logsコマンド
│       │   ├── clean.py           # cleanコマンド
│       │   └── analyze.py         # analyzeコマンド（Phase 3）
│       ├── core/
│       │   ├── __init__.py
│       │   ├── ci_run.py          # act実行のメインロジック
│       │   ├── extract_failures.py # ログから失敗箇所を抽出
│       │   ├── format_for_ai.py   # AI用の整形（Markdown/JSON）
│       │   ├── log_compressor.py  # ログ圧縮・要約機能
│       │   ├── token_counter.py   # トークン数カウント
│       │   ├── error_handler.py   # エラーハンドリング
│       │   ├── diff_analyzer.py   # ログ差分表示
│       │   └── cache_manager.py   # ログキャッシュ管理
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── integration.py     # AI API統合（Phase 3）
│       │   ├── providers/         # 各プロバイダー実装
│       │   │   ├── __init__.py
│       │   │   ├── openai.py
│       │   │   ├── anthropic.py
│       │   │   └── local.py
│       │   └── prompts.py         # プロンプトテンプレート
│       └── utils/
│           ├── __init__.py
│           ├── config.py          # 設定ファイル読み込み
│           ├── logger.py          # ロギング設定
│           └── validators.py      # 入力検証
├── config/
│   ├── .actrc.example             # act設定テンプレート
│   ├── ci-helper.toml.example     # プロジェクト設定テンプレート
│   └── .env.example               # 環境変数テンプレート
├── docs/
│   ├── setup.md                   # セットアップ詳細ガイド
│   ├── usage.md                   # 使用方法
│   ├── configuration.md           # 設定ファイル詳細
│   ├── troubleshooting.md         # トラブルシューティング
│   ├── examples.md                # 使用例
│   └── api-reference.md           # API リファレンス
├── tests/
│   ├── unit/
│   │   ├── test_extract_failures.py
│   │   ├── test_format_for_ai.py
│   │   ├── test_log_compressor.py
│   │   ├── test_token_counter.py
│   │   └── test_error_handler.py
│   ├── integration/
│   │   ├── test_ci_run.py
│   │   └── test_ai_integration.py
│   ├── fixtures/
│   │   ├── sample_act.log
│   │   ├── sample_workflows/
│   │   │   ├── test.yml
│   │   │   └── build.yml
│   │   └── expected_outputs/
│   │       ├── failure_extract.md
│   │       └── compressed.json
│   └── conftest.py
├── .github/
│   └── workflows/
│       ├── test.yml               # CI/CDパイプライン
│       └── release.yml            # リリース自動化
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml                 # uv tool install 対応
└── CHANGELOG.md
```

---

## 🧩 各モジュールの詳細

### `cli.py`
マルチコマンドCLIのエントリーポイント（Click Group使用）

```python
import click
from ci_helper.commands import init, doctor, test, logs, clean

@click.group()
@click.version_option()
def cli():
    """ci-helper: ローカルCI検証とAI連携ツール"""
    pass

# Phase 1 で提供するコマンド
cli.add_command(init.init)
cli.add_command(doctor.doctor)
cli.add_command(test.test)
cli.add_command(logs.logs)
cli.add_command(clean.clean)

# Phase 3 で追加するコマンド（条件付き）
# if AI_ENABLED:
#     from ci_helper.commands import analyze
#     cli.add_command(analyze.analyze)
```

### `commands/test.py`
メインのCI実行コマンド

```python
@click.command()
@click.option('--workflow', '-w', multiple=True, help='対象ワークフロー')
@click.option('--verbose', '-v', is_flag=True, help='詳細出力')
@click.option('--format', type=click.Choice(['markdown', 'json']),
              default='markdown', help='出力形式')
@click.option('--dry-run', is_flag=True, help='ログ解析のみ')
@click.option('--log', type=click.Path(exists=True), help='既存ログを解析')
@click.option('--diff', is_flag=True, help='前回との差分表示')
@click.option('--save/--no-save', default=True, help='ログ保存')
def test(**kwargs):
    """CI/CDワークフローをローカルで実行"""
    # 実装
```

### Phase別コマンド構成

#### Phase 1 コマンド
- `init`: 設定ファイルのテンプレート生成
- `doctor`: 環境チェック（act, Docker確認）
- `test`: act実行＋ログ抽出（メイン機能）
- `logs`: 過去のログ一覧表示
- `clean`: キャッシュクリア

#### Phase 3 コマンド
- `analyze`: AI分析コマンド（新規追加）

### `core/ci_run.py`
- `act` コマンドの実行（subprocess）
- ログを `.ci-helper/logs/act_TIMESTAMP.log` に保存
- タイムアウト制御
- `extract_failures.py` を呼び出して失敗抽出
- `format_for_ai.py` で整形
- `error_handler.py` でエラーハンドリング

### `core/extract_failures.py`
- `act.log` から `FAILURES` セクションを抽出
- pytest の失敗サマリ、スタックトレース、アサーションエラーを特定
- カスタム抽出パターン対応（正規表現）
- コンテキストライン（エラー前後N行）の取得
- 複数ワークフロー・ジョブの並列処理

### `core/log_compressor.py`
- 重要度によるログフィルタリング（ERROR > WARN > INFO）
- 重複行の削除
- 大量のスタックトレースの要約
- トークン数を基準にした圧縮
- 要約アルゴリズム（テキスト圧縮）

### `core/token_counter.py`
- トークン数のカウント（tiktoken使用）
- モデル別のトークン制限チェック
- 推定コスト計算
- 制限超過時の警告

### `core/format_for_ai.py`
- Markdown 形式での整形
  - 構造化されたエラーサマリ
  - コードブロックの適切な配置
  - セクション分け
- JSON 形式での出力（API連携用）
- プロバイダー非依存の抽象化

### `core/error_handler.py`
包括的なエラーハンドリング：
- `act` コマンドの存在確認
- Docker デーモンの起動状態チェック
- `.github/workflows` ディレクトリの存在確認
- Docker イメージのpullエラー対応
- ディスク容量不足の検出
- ネットワークエラー処理
- 権限エラー（Dockerソケットアクセス等）
- act実行タイムアウト
- 設定ファイルの構文エラー
- 適切なエラーメッセージとセットアップガイドの表示

### `core/diff_analyzer.py`
- 前回実行ログとの差分表示（unified diff）
- 新規エラー・解消済みエラーの分類
- 改善・悪化の判定と統計
- 変更履歴の管理（SQLite or JSON）

### `core/cache_manager.py`
- ログファイルのキャッシュ管理
- 古いログの自動削除
- ログのインデックス作成
- クイックサーチ機能

### `ai/integration.py` (Phase 3)
- 複数AIプロバイダー対応（OpenAI / Anthropic / ローカルLLM）
- プロンプトテンプレート管理
- ストリーミングレスポンス対応
- リトライロジック
- レート制限対応
- 修正提案の生成と適用

---

## ⚙️ 設定ファイル

### `.actrc.example`
```bash
# Docker設定
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-24.04
--container-architecture linux/amd64

# パフォーマンス
--default-cache

# ネットワーク
--use-gitignore=true

# ボリューム
--bind
```

### `ci-helper.toml.example`
```toml
[project]
name = "ci-helper"
version = "1.0.0"

[workflows]
# 対象ワークフロー指定（空の場合は全て）
target = ["test.yml", "build.yml"]
parallel = true
timeout = 600  # タイムアウト設定（秒）

[act]
platform = "ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-24.04"
container_arch = "linux/amd64"
secrets = ["NPM_TOKEN", "AWS_ACCESS_KEY"]  # 環境変数から取得
env_file = ".env.act"  # act用の環境変数ファイル
use_gitignore = true
bind = true

[ai]
# セキュリティ: API keyは環境変数から読み込む
# CI_HELPER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY など
provider = "openai"  # openai / anthropic / local / ollama
model = "gpt-4"
max_tokens = 4000
temperature = 0.1
retry_count = 3
timeout = 30
stream = true

[output]
format = "markdown"  # markdown / json / html
verbose = false
save_logs = true
log_dir = ".ci-helper/logs"
keep_logs = 10  # 保持するログファイル数

[extraction]
include_success = false  # 成功したステップも含めるか
context_lines = 5        # エラー前後の行数
max_log_size = 100000    # 最大ログサイズ（文字数）

# カスタム抽出パターン
patterns = [
    "ERROR:",
    "FAILED",
    "AssertionError",
    "TypeError",
    "SyntaxError"
]

# 除外パターン
exclude_patterns = [
    "DeprecationWarning",
    "DEBUG:"
]

[compression]
enabled = true
strategy = "smart"  # smart / aggressive / minimal
preserve_errors = true
max_tokens = 3000  # 圧縮後の目標トークン数

[diff]
enabled = true
show_context = true
ignore_timestamps = true

[cache]
enabled = true
max_size_mb = 100
cleanup_days = 30
```

### `.env.example`
```bash
# AI API Keys（実際の値は .env に記載し、.gitignore に追加）
# 優先順位: CI_HELPER_API_KEY > プロバイダー固有のキー
CI_HELPER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Act用のシークレット
NPM_TOKEN=
AWS_ACCESS_KEY=
AWS_SECRET_KEY=

# オプション設定
CI_HELPER_LOG_LEVEL=INFO
CI_HELPER_DEBUG=false
```

---

## 🚀 使用方法

### インストール
```bash
# uvでインストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 開発版インストール
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper
uv pip install -e .
```

### 初期設定（Phase 1）
```bash
# 設定ファイルの生成
ci-run init

# 依存関係と環境の確認
ci-run doctor

# ヘルプ表示
ci-run --help
ci-run test --help
```

### 基本実行（Phase 1）
```bash
# デフォルト実行（全ワークフロー）
ci-run test

# 特定ワークフロー指定
ci-run test --workflow test.yml

# 複数ワークフロー
ci-run test -w test.yml -w build.yml

# 詳細出力
ci-run test --verbose

# JSON形式で出力
ci-run test --format json

# 前回との差分表示
ci-run test --diff

# ドライラン（actを実行せず既存ログを解析）
ci-run test --dry-run --log .ci-helper/logs/act_20250101_120000.log

# ログ保存せずに実行
ci-run test --no-save
```

### ユーティリティコマンド（Phase 1）
```bash
# 過去のログ一覧表示
ci-run logs

# 特定ログの表示
ci-run logs --show 5  # 5番目のログを表示

# キャッシュクリア
ci-run clean

# 古いログのみ削除
ci-run clean --logs-only
```

### Phase 2 で追加される機能
Phase 2では `test` コマンドに以下のオプションが追加されます：

```bash
# ファイル監視モード（変更時に自動実行）
ci-run test --watch

# 特定のジョブのみ実行
ci-run test --job test-python-3.11

# HTMLレポート生成
ci-run test --report html --output report.html

# 対話モード
ci-run test --interactive
```

### Phase 3 で追加される機能（AI連携）
Phase 3では新しい `analyze` コマンドが追加されます：

```bash
# 最新のテスト結果をAI分析
ci-run analyze

# 特定のログファイルを分析
ci-run analyze --log .ci-helper/logs/act_20250101_120000.log

# プロバイダー指定
ci-run analyze --provider anthropic --model claude-sonnet-4

# カスタムプロンプト
ci-run analyze --prompt "このエラーの根本原因を特定してください"

# 自動修正提案を生成
ci-run analyze --fix

# AI対話モード
ci-run analyze --interactive

# テストと分析を連続実行
ci-run test && ci-run analyze
```

---

## 📊 CLI コマンド体系（全フェーズ）

### Phase 1 で提供されるコマンド

| コマンド | 説明 | 主なオプション |
|---------|------|--------------|
| `ci-run init` | 設定ファイル生成 | なし |
| `ci-run doctor` | 環境チェック | `--verbose` |
| `ci-run test` | CI実行（メイン） | `--workflow`, `--verbose`, `--format`, `--dry-run`, `--log`, `--diff`, `--save` |
| `ci-run logs` | ログ一覧・表示 | `--show`, `--filter` |
| `ci-run clean` | キャッシュクリア | `--logs-only`, `--all` |

### Phase 2 で追加されるオプション

| コマンド | 追加オプション | 説明 |
|---------|--------------|------|
| `ci-run test` | `--watch` | ファイル監視モード |
| | `--job TEXT` | 特定ジョブのみ実行 |
| | `--report TYPE` | レポート生成（html/pdf） |
| | `--output PATH` | 出力先指定 |
| | `--interactive` | 対話モード |

### Phase 3 で追加されるコマンド

| コマンド | 説明 | 主なオプション |
|---------|------|--------------|
| `ci-run analyze` | AI分析（新規） | `--log`, `--provider`, `--model`, `--prompt`, `--fix`, `--interactive` |

---

## 📋 段階的実装計画

### Phase 1: コア機能（MVP）
**目標**: ローカルでのCI検証とログ抽出の基本機能

#### CLI実装
- [ ] マルチコマンド構造のセットアップ（Click Group）
- [ ] `init` コマンド実装
- [ ] `doctor` コマンド実装
- [ ] `test` コマンド実装（メイン機能）
  - [ ] `--workflow` オプション
  - [ ] `--verbose` オプション
  - [ ] `--format` オプション（markdown/json）
  - [ ] `--dry-run` オプション
  - [ ] `--log` オプション
  - [ ] `--diff` オプション
  - [ ] `--save/--no-save` オプション
- [ ] `logs` コマンド実装
- [ ] `clean` コマンド実装

#### コア機能
- [ ] プロジェクト構造のセットアップ
- [ ] `act` と Docker の導入ドキュメント整備
- [ ] 基本的な `act` 実行機能
- [ ] ログ保存とファイル管理
- [ ] 失敗箇所の抽出ロジック
- [ ] Markdown形式での基本的な整形
- [ ] 包括的なエラーハンドリング
- [ ] **トークン数カウント機能**（AI連携の準備）
- [ ] 設定ファイル読み込み機能
- [ ] ユニットテストの作成
- [ ] README とドキュメント整備

**完了条件**:
- `ci-run test` コマンドで act が実行でき、失敗箇所が整形されて表示される
- `ci-run doctor` で環境チェックができる
- トークン数が表示され、AI に渡す準備ができている

**提供されるコマンド**:
```bash
ci-run init
ci-run doctor
ci-run test [--workflow] [--verbose] [--format] [--dry-run] [--log] [--diff] [--save/--no-save]
ci-run logs
ci-run clean
```

---

### Phase 2: 出力最適化と拡張機能
**目標**: AI に渡すための最適化と利便性の向上

#### CLI拡張
- [ ] `test` コマンドへのオプション追加
  - [ ] `--watch` オプション
  - [ ] `--job` オプション
  - [ ] `--report` オプション
  - [ ] `--output` オプション
  - [ ] `--interactive` オプション

#### コア機能
- [ ] ログ圧縮・要約機能の実装
- [ ] 複数の圧縮戦略（smart / aggressive / minimal）
- [ ] カスタム抽出パターンの対応
- [ ] 差分表示機能の強化
- [ ] 変更履歴の管理
- [ ] キャッシュ管理機能
- [ ] 詳細な設定オプション
- [ ] 複数ワークフロー・ジョブの並列実行
- [ ] **AI用出力フォーマットの抽象化**（プロバイダー非依存）
- [ ] JSON出力とAPI連携準備
- [ ] ウォッチモード実装
- [ ] インタラクティブモード実装
- [ ] HTMLレポート生成
- [ ] パフォーマンス最適化
- [ ] 統合テストの作成

**完了条件**:
- ログが効率的に圧縮され、トークン制限内に収まる
- 差分表示で改善・悪化が一目でわかる
- 様々な出力形式に対応
- ファイル監視で自動実行が可能

**提供されるコマンド（Phase 1 + 追加オプション）**:
```bash
ci-run test [--watch] [--job TEXT] [--report TYPE] [--output PATH] [--interactive]
```

---

### Phase 3: AI統合
**目標**: AI による自動分析と修正提案

#### CLI拡張
- [ ] 新しい `analyze` コマンドの実装
  - [ ] `--log` オプション
  - [ ] `--provider` オプション
  - [ ] `--model` オプション
  - [ ] `--prompt` オプション
  - [ ] `--fix` オプション
  - [ ] `--interactive` オプション

#### AI機能
- [ ] AI API統合基盤の構築
- [ ] 複数プロバイダー対応
  - [ ] OpenAI (GPT-5 codex, GPT-5)
  - [ ] Anthropic (Claude Sonnet 4.5)
  - [ ] ローカルLLM (Ollama等)
- [ ] プロンプトテンプレート管理
- [ ] ストリーミングレスポンス対応
- [ ] エラー分析と根本原因特定
- [ ] 修正提案の生成
- [ ] 修正の自動適用機能（オプション）
- [ ] 対話モード（AIとの会話でデバッグ）
- [ ] 学習機能（よくある失敗パターンのデータベース）
- [ ] フィードバックループ
- [ ] コスト管理と使用統計
- [ ] AIレスポンスのキャッシュ
- [ ] セキュリティ強化
- [ ] E2Eテストの作成

**完了条件**:
- `ci-run analyze` で自動的にエラー分析と修正提案が得られる
- 複数のAIプロバイダーが利用可能
- 対話的なデバッグが可能

**提供されるコマンド（Phase 1 + Phase 2 + 新規）**:
```bash
ci-run analyze [--log PATH] [--provider TEXT] [--model TEXT] [--prompt TEXT] [--fix] [--interactive]
```

---

### Phase 4: 拡張機能（将来的な展望）
- [ ] Web UI / ローカルダッシュボード（`ci-run serve` コマンド）
- [ ] GitHub Actions統合（実行結果の比較）
- [ ] プラグインシステム
- [ ] カスタム抽出ロジックの追加
- [ ] 統計機能（失敗率、実行時間の推移）（`ci-run stats` コマンド）
- [ ] チーム機能（共有設定、ナレッジベース）
- [ ] CI/CD プラットフォーム対応拡張（GitLab CI等）

---

## 🧪 テスト戦略

### ユニットテスト
- 各モジュールの個別機能をテスト
- pytest + pytest-cov でカバレッジ80%以上を目標
- モックを使用した外部依存の分離
- 各CLIコマンドの単体テスト
- pytest-xdistによる並列実行への対応

### 統合テスト
- 実際のワークフローファイルを使用
- act の実行から出力までの一連の流れをテスト
- 様々なエラーパターンの検証
- コマンド間の連携テスト

### E2Eテスト（Phase 3）
- AI連携を含む完全なワークフローのテスト
- 複数のプロバイダーでの動作確認

### CI/CD
- GitHub Actions でプッシュごとに自動テスト
- 複数のPythonバージョンでテスト（3.12, 3.13, 3.14）
- コードスタイルチェック（ruff check, ruff format）
- 型チェック（mypy）

---

## 🔒 セキュリティ考慮事項

### API キーの管理
- ✅ **環境変数からの読み込みを優先**
  - `CI_HELPER_API_KEY`（共通）
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`（プロバイダー固有）
- ✅ `.env` ファイルのサポート（`.gitignore` 必須）
- ✅ 設定ファイルには API キーを**絶対に記載しない**
- ⚠️ README とドキュメントに明確な警告を記載

### シークレットの取り扱い
- act 実行時のシークレットは環境変数経由
- ログにシークレットが含まれないようフィルタリング
- 共有時のサニタイズ機能

### 依存関係のセキュリティ
- 定期的な依存関係の更新
- Dependabot の有効化
- 脆弱性スキャン

---

## 📖 ドキュメント構成

### `docs/setup.md`
- act のインストール方法（macOS, Linux, Windows）
- Docker のインストールと設定
- uv のインストール
- ci-helper のインストール
- 初期設定手順

### `docs/usage.md`
- 基本的な使い方
- 各コマンドの詳細説明（Phase別）
- 設定ファイルのカスタマイズ
- ベストプラクティス

### `docs/configuration.md`
- 設定ファイルの完全リファレンス
- 各オプションの詳細説明
- 設定例

### `docs/troubleshooting.md`
- よくあるエラーと解決方法
  - act がインストールされていない
  - Docker が起動していない
  - 権限エラー
  - ディスク容量不足
  - ネットワークエラー
  - タイムアウト
- デバッグ方法
- FAQ

### `docs/examples.md`
- 実際の使用例（Phase別）
- 様々なワークフローでの適用例
- CI設定のベストプラクティス

### `docs/api-reference.md`
- 各モジュールの API リファレンス
- 内部アーキテクチャ
- 拡張ポイント

---

## 🤝 コントリビューション

### 開発環境のセットアップ
```bash
# リポジトリのクローン
git clone https://github.com/scottlz0310/ci-helper.git
cd ci-helper

# 依存関係のインストール
uv sync

# pre-commit フックのインストール
pre-commit install

# テスト実行
pytest

# カバレッジ確認
pytest --cov=ci_helper --cov-report=html
```

### コーディング規約
- PEP 8 に準拠
- 行長120文字
- Ruff でリント、フォーマット
- 型ヒントの使用（mypy でチェック）
- Docstring の記載（Google スタイル）

### プルリクエスト
- 機能追加・バグ修正は別ブランチで作業
- テストを必ず追加
- ドキュメントを更新
- コミットメッセージは明確に

---

## 📊 成功指標（KPI）

### Phase 1
- ✅ 基本機能の動作
- ✅ 全コマンドの実装完了
- ✅ テストカバレッジ 80% 以上
- ✅ ドキュメント完成度

### Phase 2
- ✅ ログ圧縮率（元のサイズの30%以下）
- ✅ トークン削減率（70%削減目標）
- ✅ 処理速度（10秒以内）
- ✅ 新機能の実用性

### Phase 3
- ✅ AI分析の精度
- ✅ 修正提案の実用性
- ✅ ユーザー満足度
- ✅ コスト効率

---

## 🎯 まとめ

このプロジェクトは段階的に実装することで、各フェーズで実用的な価値を提供しながら、最終的にはAI統合による完全自動化されたCI検証・修正サイクルを実現します。

**マルチコマンドCLI設計**により、機能の追加が容易で、各Phaseでの提供範囲が明確になります。Phase 1で`test`コマンドのMVPを完成させ、Phase 2で機能を拡張し、Phase 3で新しい`analyze`コマンドを追加するという段階的なアプローチを採用します。

セキュリティ、パフォーマンス、拡張性を重視した設計により、長期的に保守可能で実用的なツールを目指します。
