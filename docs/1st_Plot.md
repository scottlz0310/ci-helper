 `act` × `AI連携` のためのリポジトリ構成案を提案します。

---
## 📚 このリポジトリの目的
- AI開発プロセスにおいて、CI/CDパイプラインをローカルで反復的に検証できる環境を整備する。
- ワークフローファイルを直接検証するためのヘルパー。

### 現状の問題点
- 直接githubにpushしてactionsをトリガーしてから結果を待つ時間がかかり、開発フロー遅延の原因の一つ。
- その後エラーログをAIに渡して改善するというサイクルでは手動コピペなどが多く、作業の自動化が困難。
- github cliを用いたとしてもAI自体にログ抽出などの負荷がかかり改善にはつながらない。
- Docker環境+actをbrewなどでグローバルに導入すれば、CI検証をローカルで即座に再現することができるが、出力されるログが膨大で、そのままAIに渡すとコンテキスト制限があり解析が難しい。

### 改善案
- uv tool install git+http....を用いてツールとして配布し、どのフォルダでもワークフロー検証を呼び出せるようにする。
- 実行すれば失敗箇所を効率的に抽出してAIが理解しやすいMarkdown や JSON などの構造化形式に成形する仕組みを提供する。
- AIにコマンド起動を指示すれば実行、確認、修正までのサイクルが自動化できることを目指す。

## 🧱 リポジトリ構成案：`ci-helper`

```
ci-helper/
├── ci_run.py              # act実行 + ログ保存 + 失敗抽出 + AI連携のメインスクリプト
├── extract_failures.py    # act.log から失敗箇所を抽出するユーティリティ
├── format_for_ai.py       # AIに渡すための整形（Markdownなど）
├── error_handler.py       # エラーハンドリング（act/Docker未インストール等）
├── diff_analyzer.py       # ログ差分表示機能
├── .actrc                 # actの共通設定（Dockerイメージなど）
├── ci-helper.toml         # プロジェクト固有設定ファイル（テンプレート）
├── README.md              # 使い方・セットアップ手順
├── pyproject.toml         # uv tool install 対応（CLI化も可能）
└── tests/                 # スクリプトのユニットテスト（pytestで）
```

---

## 🧩 各ファイルの役割

### `ci_run.py`
- `act push` を実行（subprocess）
- ログを `act.log` に保存
- `extract_failures.py` を呼び出して失敗箇所抽出
- `format_for_ai.py` で整形して表示 or 保存
- `error_handler.py` でエラーハンドリング
- 将来的にはAI API連携もここに追加

### `extract_failures.py`
- `act.log` から `FAILURES` セクションを抽出
- `pytest` の失敗サマリを中心に抜き出す
- オプションで `--junitxml` にも対応可能
- 複数ワークフローの並列実行結果も処理

### `format_for_ai.py`
- 抽出した失敗ログをMarkdown形式に整形
- AIに渡すためのコンパクトな要約も生成可能
- 成功時の簡潔な出力オプション

### `error_handler.py`
- `act` コマンドの存在確認
- Docker デーモンの起動状態チェック
- `.github/workflows` ディレクトリの存在確認
- 適切なエラーメッセージとセットアップガイドの表示

### `diff_analyzer.py`
- 前回実行ログとの差分表示
- 改善・悪化の判定
- 変更履歴の管理

### `.actrc`
```bash
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-24.04
--container-architecture linux/amd64
--default-cache
```

### `ci-helper.toml`
```toml
# プロジェクト固有設定
[workflows]
target = ["test.yml", "build.yml"]  # 対象ワークフロー指定
parallel = true                      # 並列実行

[ai]
api_key = ""                        # AI API設定
model = "gpt-4"
max_tokens = 4000

[output]
format = "markdown"                 # markdown/json
verbose = false                     # 詳細出力
save_logs = true                    # ログ保存
```

### `pyproject.toml`
- `uv` でインストール可能な構成
- CLIツールとして `ci-run` コマンドを提供
- 依存関係管理（click, rich, pyyaml等）

---

## 🚀 実行イメージ

```bash
# インストール
uv tool install git+https://github.com/scottlz0310/ci-helper.git

# 基本実行
ci-run

# 特定ワークフロー指定
ci-run --workflow test.yml

# 差分表示
ci-run --diff

# AI連携（Phase 3）
ci-run --ai-analyze
```

これで、どのフォルダでも `.github/workflows` があれば、actを実行して失敗ログをAIに渡す準備が整います。

---

## 📋 段階的実装計画

### Phase 1: 基本機能
- [ ] `act` `docker`導入のためのドキュメント整備
- [ ] `act` 実行とログ抽出
- [ ] エラーハンドリング
- [ ] 基本的な整形機能

### Phase 2: 拡張機能
- [ ] 設定ファイル対応
- [ ] 差分表示機能
- [ ] 複数ワークフロー対応
- [ ] 詳細な出力オプション

### Phase 3: AI連携
- [ ] AI API統合
- [ ] 自動修正提案
- [ ] 学習機能（よくある失敗パターン）
