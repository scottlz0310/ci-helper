"""
AI APIレスポンスのモックデータ

テスト用のAI APIレスポンスサンプルを提供します。
"""

from datetime import datetime

# OpenAI APIレスポンスのモック
MOCK_OPENAI_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1699999999,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": """# CI/CD失敗分析結果

## 概要
複数のエラーが検出されました。主な問題は依存関係の不足とテストの失敗です。

## 根本原因

### 1. 依存関係エラー
- **カテゴリ**: dependency
- **説明**: package.jsonが見つかりません
- **ファイル**: package.json
- **重要度**: HIGH

### 2. テスト失敗
- **カテゴリ**: test
- **説明**: 認証テストが失敗しています
- **ファイル**: test_user_authentication.py
- **行番号**: 42
- **重要度**: MEDIUM

## 修正提案

### 1. package.jsonの作成
- **優先度**: HIGH
- **推定工数**: 5分
- **信頼度**: 90%
- **説明**: プロジェクトルートにpackage.jsonファイルを作成してください

### 2. 認証テストの修正
- **優先度**: MEDIUM
- **推定工数**: 15分
- **信頼度**: 85%
- **説明**: 期待値と実際の値を確認してテストを修正してください

## 関連エラー
- ENOENT
- AssertionError
- TimeoutError

## 信頼度スコア
85%""",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 500,
        "completion_tokens": 300,
        "total_tokens": 800,
    },
}

# Anthropic APIレスポンスのモック
MOCK_ANTHROPIC_RESPONSE = {
    "id": "msg_test123",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": """# CI/CD失敗分析結果（Claude分析）

## 分析サマリー
Claudeによる詳細な分析結果です。複数の問題が特定されました。

## 検出された問題

### 依存関係の問題
- package.jsonファイルが存在しません
- npm installが実行できない状態です

### テストの失敗
- 認証関連のテストで期待値と異なる結果が返されています
- データベース接続のタイムアウトが発生しています

## 推奨される修正手順

1. **package.jsonの作成**
   - プロジェクトルートに適切なpackage.jsonを配置
   - 必要な依存関係を定義

2. **テストの修正**
   - 認証テストの期待値を確認
   - データベース接続のタイムアウト設定を調整

## 信頼度
この分析の信頼度は90%です。""",
        }
    ],
    "model": "claude-3-5-sonnet-20241022",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {
        "input_tokens": 500,
        "output_tokens": 250,
    },
}

# ローカルLLM（Ollama）レスポンスのモック
MOCK_LOCAL_LLM_RESPONSE = {
    "model": "llama3.2",
    "created_at": "2024-01-01T12:00:00Z",
    "response": """ローカルLLMによる分析結果:

エラーログを分析した結果、以下の問題が見つかりました：

1. ファイルが見つからないエラー (ENOENT)
   - package.jsonが存在しません
   - 解決策: package.jsonファイルを作成してください

2. テストの失敗
   - 認証テストで予期しない結果
   - 解決策: テストの期待値を確認してください

3. データベース接続タイムアウト
   - 30秒でタイムアウト
   - 解決策: 接続設定を確認してください

推奨される対応順序:
1. package.jsonの作成 (優先度: 高)
2. テストの修正 (優先度: 中)
3. DB設定の確認 (優先度: 中)""",
    "done": True,
    "context": [1, 2, 3],
    "total_duration": 2500000000,
    "load_duration": 500000000,
    "prompt_eval_count": 100,
    "prompt_eval_duration": 1000000000,
    "eval_count": 150,
    "eval_duration": 1000000000,
}

# ストリーミングレスポンスのモック
MOCK_STREAMING_CHUNKS = [
    {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": 1699999999,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": "# CI/CD"},
                "finish_reason": None,
            }
        ],
    },
    {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": 1699999999,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "失敗分析"},
                "finish_reason": None,
            }
        ],
    },
    {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": 1699999999,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "結果\n\n"},
                "finish_reason": None,
            }
        ],
    },
    {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": 1699999999,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "複数のエラーが"},
                "finish_reason": None,
            }
        ],
    },
    {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": 1699999999,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "検出されました。"},
                "finish_reason": "stop",
            }
        ],
    },
]

# エラーレスポンスのモック
MOCK_ERROR_RESPONSES = {
    "rate_limit": {
        "error": {
            "message": "Rate limit reached for requests",
            "type": "rate_limit_error",
            "param": None,
            "code": "rate_limit_exceeded",
        }
    },
    "invalid_api_key": {
        "error": {
            "message": "Incorrect API key provided",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_api_key",
        }
    },
    "token_limit": {
        "error": {
            "message": "This model's maximum context length is 4097 tokens",
            "type": "invalid_request_error",
            "param": "messages",
            "code": "context_length_exceeded",
        }
    },
    "server_error": {
        "error": {
            "message": "The server had an error while processing your request",
            "type": "server_error",
            "param": None,
            "code": "server_error",
        }
    },
}

# 使用統計のモックデータ
MOCK_USAGE_STATS = {
    "daily": {
        "date": "2024-01-01",
        "total_requests": 15,
        "total_cost": 0.125,
        "total_input_tokens": 7500,
        "total_output_tokens": 3750,
        "by_provider": {
            "openai": {
                "requests": 10,
                "cost": 0.08,
                "input_tokens": 5000,
                "output_tokens": 2500,
            },
            "anthropic": {
                "requests": 5,
                "cost": 0.045,
                "input_tokens": 2500,
                "output_tokens": 1250,
            },
        },
    },
    "monthly": {
        "year": 2024,
        "month": 1,
        "total_requests": 450,
        "total_cost": 3.75,
        "total_input_tokens": 225000,
        "total_output_tokens": 112500,
        "by_provider": {
            "openai": {
                "requests": 300,
                "cost": 2.4,
                "input_tokens": 150000,
                "output_tokens": 75000,
            },
            "anthropic": {
                "requests": 150,
                "cost": 1.35,
                "input_tokens": 75000,
                "output_tokens": 37500,
            },
        },
    },
}

# キャッシュデータのモック
MOCK_CACHE_DATA = {
    "cache_key_123": {
        "result": {
            "summary": "キャッシュされた分析結果",
            "root_causes": [],
            "fix_suggestions": [],
            "confidence_score": 0.8,
            "provider": "openai",
            "model": "gpt-4o",
            "cost": 0.005,
        },
        "timestamp": datetime.now().isoformat(),
        "ttl_hours": 24,
    }
}

# 設定ファイルのモック
MOCK_AI_CONFIG = {
    "default_provider": "openai",
    "cache_enabled": True,
    "cache_ttl_hours": 24,
    "interactive_timeout": 300,
    "providers": {
        "openai": {
            "api_key": "sk-test-key-123",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "available_models": ["gpt-4o", "gpt-4o-mini", "gpt-4"],
            "timeout_seconds": 30,
            "max_retries": 3,
        },
        "anthropic": {
            "api_key": "sk-ant-test-key-123",
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-3-5-sonnet-20241022",
            "available_models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            "timeout_seconds": 30,
            "max_retries": 3,
        },
        "local": {
            "api_key": "",
            "base_url": "http://localhost:11434",
            "default_model": "llama3.2",
            "available_models": ["llama3.2", "codellama"],
            "timeout_seconds": 60,
            "max_retries": 2,
        },
    },
    "cost_limits": {
        "monthly_usd": 50.0,
        "daily_usd": 5.0,
        "per_request_usd": 1.0,
    },
    "prompts": {
        "analysis": "templates/analysis.txt",
        "fix_suggestion": "templates/fix.txt",
        "interactive": "templates/interactive.txt",
    },
}

# プロンプトテンプレートのモック
MOCK_PROMPT_TEMPLATES = {
    "analysis": """あなたはCI/CDエラー分析の専門家です。以下のログを分析して、根本原因と修正提案を提供してください。

ログ内容:
{log_content}

以下の形式で回答してください:
1. 概要
2. 根本原因
3. 修正提案
4. 関連エラー
5. 信頼度スコア""",
    "fix_suggestion": """以下の分析結果に基づいて、具体的な修正提案を生成してください。

分析結果:
{analysis_result}

各修正提案には以下を含めてください:
- タイトル
- 詳細説明
- 優先度
- 推定工数
- 信頼度""",
    "interactive": """あなたはCI/CDトラブルシューティングのアシスタントです。
ユーザーと対話しながら問題を解決してください。

初期ログ:
{initial_log}

会話履歴:
{conversation_history}

ユーザーの質問に対して、建設的で実用的な回答を提供してください。""",
}
