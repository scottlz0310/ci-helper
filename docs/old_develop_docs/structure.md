# プロジェクト構造

## リポジトリ構成

```
ci-helper/
├── src/ci_helper/           # メインパッケージソース
│   ├── cli.py              # CLIエントリーポイント（Clickグループ）
│   ├── commands/           # 個別CLIコマンド
│   ├── core/               # コアビジネスロジック
│   ├── ai/                 # AI統合（フェーズ3）
│   └── utils/              # 共有ユーティリティ
├── config/                 # 設定テンプレート
├── docs/                   # ドキュメント
├── tests/                  # テストスイート
└── .github/workflows/      # CI/CDパイプライン
```

## ソースコード構造

### `src/ci_helper/`
標準的なPythonパッケージレイアウトに従うメインパッケージ：

- **`cli.py`**: Clickグループを使用したマルチコマンドCLIエントリーポイント
- **`commands/`**: 各CLIサブコマンドを独立したモジュールとして配置
  - `init.py` - セットアップと設定生成
  - `doctor.py` - 環境検証
  - `test.py` - メインCI実行コマンド
  - `logs.py` - ログ管理と表示
  - `clean.py` - キャッシュとクリーンアップ操作
  - `analyze.py` - AI分析（フェーズ3）

### `core/` - ビジネスロジック
- **`ci_run.py`**: Act実行とプロセス管理
- **`extract_failures.py`**: ログ解析と失敗抽出
- **`format_for_ai.py`**: AI消費用の出力フォーマット
- **`log_compressor.py`**: ログ圧縮と最適化
- **`token_counter.py`**: AIモデル用のトークンカウント
- **`error_handler.py`**: 包括的エラーハンドリング
- **`diff_analyzer.py`**: ログ比較と差分解析
- **`cache_manager.py`**: ファイルとログのキャッシュ

### `ai/` - AI統合（フェーズ3）
- **`integration.py`**: メインAI統合ロジック
- **`providers/`**: 個別AIプロバイダー実装
- **`prompts.py`**: プロンプトテンプレートと管理

### `utils/` - 共有ユーティリティ
- **`config.py`**: 設定ファイル処理
- **`logger.py`**: ログ設定と管理
- **`validators.py`**: 入力検証ユーティリティ

## 設定構造

### 生成ファイル（`ci-run init`経由）
- **`.actrc`**: DockerイメージとActの設定
- **`ci-helper.toml`**: プロジェクト固有の設定
- **`.env.example`**: 環境変数テンプレート

### 設定階層
1. コマンドライン引数（最高優先度）
2. 環境変数
3. `ci-helper.toml`設定ファイル
4. デフォルト値（最低優先度）

## 出力構造

### ログディレクトリ: `.ci-helper/`
```
.ci-helper/
├── logs/                   # 実行ログ
│   ├── act_TIMESTAMP.log   # 生のact出力
│   └── index.json          # ログメタデータ
├── cache/                  # キャッシュデータ
└── reports/                # 生成レポート
```

## テスト構造

### `tests/`
- **`unit/`**: 個別モジュールテスト
- **`integration/`**: モジュール間統合テスト
- **`fixtures/`**: テストデータとサンプルファイル
- **`conftest.py`**: Pytest設定と共有フィクスチャ

## ドキュメント構造

### `docs/`
- **`setup.md`**: インストールとセットアップガイド
- **`usage.md`**: 使用例とチュートリアル
- **`configuration.md`**: 設定リファレンス
- **`troubleshooting.md`**: よくある問題と解決策
- **`examples.md`**: 実際の使用例
- **`api-reference.md`**: 内部API ドキュメント

## 命名規則

- **ファイル**: Pythonモジュール用のsnake_case
- **クラス**: PascalCase
- **関数・変数**: snake_case
- **定数**: UPPER_SNAKE_CASE
- **CLIコマンド**: ケバブケース（`ci-run`、`ci_run`ではない）
- **設定キー**: TOMLファイル内でsnake_case

## インポート構成

- 標準ライブラリのインポートを最初に
- サードパーティのインポートを次に
- ローカルインポートを最後に
- 各グループ内でアルファベット順
- パッケージモジュールには絶対インポートを使用

## 日本語開発規約

- **コメント**: すべて日本語で記述
- **ドキュメント**: 日本語で作成（README、設計書、仕様書等）
- **コミットメッセージ**: 日本語で記述
- **変数名・関数名**: 英語（Pythonの慣例に従う）
- **設定ファイル**: 日本語コメント付き
- **エラーメッセージ**: 日本語で表示（可能な限り）
