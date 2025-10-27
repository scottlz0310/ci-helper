"""
AI設定テンプレート

テスト用のAI設定ファイルテンプレートを提供します。

Note: 実際の設定ファイル例は tests/fixtures/config_examples/ ディレクトリにあります。
このファイルは文字列テンプレートを提供し、config_loader.py が実際のファイルを読み込みます。
"""

# 基本的なAI設定テンプレート
BASIC_AI_CONFIG_TOML = """
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
interactive_timeout = 300

[ai.providers.openai]
default_model = "gpt-4o"
available_models = ["gpt-4o", "gpt-4o-mini"]
timeout_seconds = 30
max_retries = 3

[ai.cost_limits]
monthly_usd = 50.0
per_request_usd = 1.0

[ai.prompts]
analysis = "templates/analysis.txt"
fix_suggestion = "templates/fix.txt"
interactive = "templates/interactive.txt"
"""

# 複数プロバイダー設定テンプレート
MULTI_PROVIDER_CONFIG_TOML = """
[ai]
default_provider = "openai"
cache_enabled = true
cache_ttl_hours = 24
interactive_timeout = 300

[ai.providers.openai]
default_model = "gpt-4o"
available_models = ["gpt-4o", "gpt-4o-mini", "gpt-4"]
timeout_seconds = 30
max_retries = 3

[ai.providers.anthropic]
default_model = "claude-3-5-sonnet-20241022"
available_models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
timeout_seconds = 30
max_retries = 3

[ai.providers.local]
default_model = "llama3.2"
available_models = ["llama3.2", "codellama"]
timeout_seconds = 60
max_retries = 2

[ai.cost_limits]
monthly_usd = 100.0
daily_usd = 10.0
per_request_usd = 2.0

[ai.prompts]
analysis = "templates/analysis.txt"
fix_suggestion = "templates/fix.txt"
interactive = "templates/interactive.txt"
build_failure = "templates/build_failure.txt"
test_failure = "templates/test_failure.txt"
"""

# 最小設定テンプレート
MINIMAL_AI_CONFIG_TOML = """
[ai]
default_provider = "openai"

[ai.providers.openai]
default_model = "gpt-4o-mini"
"""

# 無効な設定テンプレート（テスト用）
INVALID_AI_CONFIG_TOML = """
[ai]
default_provider = "nonexistent"

[ai.providers.invalid]
# APIキーが設定されていない
default_model = "invalid-model"
"""

# 環境変数設定テンプレート
ENV_VARIABLES_TEMPLATE = {
    "OPENAI_API_KEY": "sk-test-openai-key-1234567890abcdef",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic-key-1234567890abcdef",
    "CI_HELPER_AI_PROVIDER": "openai",
    "CI_HELPER_AI_MODEL": "gpt-4o",
    "CI_HELPER_AI_CACHE_ENABLED": "true",
    "OLLAMA_BASE_URL": "http://localhost:11434",
}

# プロンプトテンプレートファイル
ANALYSIS_PROMPT_TEMPLATE = """あなたはCI/CDエラー分析の専門家です。以下のログを分析して、根本原因と修正提案を提供してください。

## 分析対象ログ
```
{log_content}
```

## 分析指針
1. エラーの種類を特定してください（依存関係、構文、テスト、ビルド、デプロイなど）
2. 根本原因を明確に説明してください
3. 具体的で実行可能な修正提案を提供してください
4. 優先度と推定工数を含めてください

## 出力形式
以下のMarkdown形式で回答してください：

# CI/CD失敗分析結果

## 概要
[簡潔な問題の概要]

## 根本原因
### 1. [原因1のタイトル]
- **カテゴリ**: [dependency/syntax/test/build/deploy/other]
- **説明**: [詳細な説明]
- **ファイル**: [関連ファイル名]
- **行番号**: [該当する場合]
- **重要度**: [CRITICAL/HIGH/MEDIUM/LOW]

## 修正提案
### 1. [修正提案1のタイトル]
- **優先度**: [URGENT/HIGH/MEDIUM/LOW]
- **推定工数**: [時間の見積もり]
- **信頼度**: [0-100%]
- **説明**: [具体的な修正手順]

## 関連エラー
- [関連するエラーキーワードのリスト]

## 信頼度スコア
[0-100%の数値]%
"""

FIX_SUGGESTION_PROMPT_TEMPLATE = """以下の分析結果に基づいて、具体的で実行可能な修正提案を生成してください。

## 分析結果
{analysis_result}

## 要求事項
1. 各修正提案は具体的で実行可能である必要があります
2. コードの変更が必要な場合は、具体的な変更内容を示してください
3. ファイルの作成や設定変更が必要な場合は、詳細な手順を提供してください
4. 優先度と推定工数を現実的に設定してください

## 出力形式
以下のMarkdown形式で回答してください：

# 修正提案

## 1. [修正提案1のタイトル]
- **優先度**: [URGENT/HIGH/MEDIUM/LOW]
- **推定工数**: [具体的な時間]
- **信頼度**: [0-100%]
- **影響範囲**: [変更の影響を受ける部分]

### 修正手順
1. [具体的な手順1]
2. [具体的な手順2]
3. [具体的な手順3]

### 変更内容
```[言語]
[具体的なコード変更]
```

### 検証方法
- [修正が正しく適用されたかを確認する方法]

## 2. [修正提案2のタイトル]
[同様の形式で続ける]
"""

INTERACTIVE_PROMPT_TEMPLATE = """あなたはCI/CDトラブルシューティングのアシスタントです。
ユーザーと対話しながら問題を解決してください。

## 初期ログ
```
{initial_log}
```

## 会話履歴
{conversation_history}

## 対話指針
1. ユーザーの質問に対して建設的で実用的な回答を提供してください
2. 必要に応じて追加情報を求めてください
3. 段階的な解決アプローチを提案してください
4. 技術的な説明は適切なレベルで行ってください

## 利用可能なコマンド
- `/help` - 利用可能なコマンドを表示
- `/analyze` - 詳細な分析を実行
- `/fix` - 修正提案を生成
- `/summary` - 現在の状況をまとめる
- `/exit` - セッションを終了

ユーザーの質問に対して、親切で専門的な回答を提供してください。
"""

BUILD_FAILURE_PROMPT_TEMPLATE = """あなたはビルド失敗の専門家です。以下のビルドログを分析してください。

## ビルドログ
```
{log_content}
```

## 分析観点
1. ビルドツール固有の問題（npm, gradle, maven, docker等）
2. 依存関係の問題
3. 設定ファイルの問題
4. 環境の問題

## 出力形式
# ビルド失敗分析

## 失敗の種類
[コンパイルエラー/依存関係エラー/設定エラー/環境エラー]

## 根本原因
[詳細な原因分析]

## 修正手順
1. [具体的な修正手順]
2. [検証方法]

## 予防策
[今後同様の問題を防ぐための提案]
"""

TEST_FAILURE_PROMPT_TEMPLATE = """あなたはテスト失敗の専門家です。以下のテストログを分析してください。

## テストログ
```
{log_content}
```

## 分析観点
1. テストフレームワーク固有の問題
2. アサーションエラーの詳細
3. テスト環境の問題
4. テストデータの問題

## 出力形式
# テスト失敗分析

## 失敗したテスト
[失敗したテストの一覧と詳細]

## 失敗の原因
[各テスト失敗の根本原因]

## 修正提案
### テストコードの修正
[必要なテストコードの変更]

### アプリケーションコードの修正
[必要なアプリケーションコードの変更]

## テスト改善提案
[テストの品質向上のための提案]
"""

# CI/CD環境でのテスト設定
CI_TEST_CONFIG = {
    "providers": {
        "mock_openai": {
            "api_key": "mock-key-for-ci",
            "default_model": "gpt-4o",
            "base_url": "http://mock-api.test",
        }
    },
    "cache_enabled": False,  # CIではキャッシュを無効化
    "cost_limits": {
        "monthly_usd": 0.0,  # CIではコスト制限を厳しく
        "per_request_usd": 0.0,
    },
}

# パフォーマンステスト用設定
PERFORMANCE_TEST_CONFIG = {
    "providers": {
        "fast_mock": {
            "api_key": "perf-test-key",
            "default_model": "gpt-4o-mini",
            "timeout_seconds": 5,  # 短いタイムアウト
            "max_retries": 1,  # 少ないリトライ
        }
    },
    "cache_enabled": True,
    "cache_ttl_hours": 1,  # 短いTTL
}

# エラーテスト用設定
ERROR_TEST_CONFIGS = {
    "invalid_api_key": {
        "providers": {
            "openai": {
                "api_key": "invalid-key",
                "default_model": "gpt-4o",
            }
        }
    },
    "missing_provider": {
        "default_provider": "nonexistent",
        "providers": {},
    },
    "invalid_model": {
        "providers": {
            "openai": {
                "api_key": "sk-test-key",
                "default_model": "nonexistent-model",
                "available_models": ["gpt-4o"],
            }
        }
    },
}
