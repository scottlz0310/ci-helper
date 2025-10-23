"""
AI APIレスポンスのモックデータ

このファイルはAI API（OpenAI、Anthropic等）のレスポンスを模擬するテストデータを提供します。
実際のAPI呼び出しを行わずにAI機能をテストするために使用されます。
"""

from datetime import datetime
from typing import Any

# OpenAI APIレスポンスのモック
MOCK_OPENAI_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1699000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": """# CI/CD分析結果

## 概要
テストの実行中にnpmパッケージが見つからないエラーが発生しています。

## 根本原因
1. **依存関係の問題**: package.jsonファイルが見つからない
2. **ワークスペース設定**: GitHub Actionsのワークスペース設定に問題がある可能性

## 修正提案
1. package.jsonファイルの存在確認
2. npm installステップの追加
3. ワークディレクトリの設定確認

## 信頼度
85% - 一般的なNode.jsプロジェクトのエラーパターンです。
""",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 150, "completion_tokens": 200, "total_tokens": 350},
}

# Anthropic APIレスポンスのモック
MOCK_ANTHROPIC_RESPONSE = {
    "id": "msg_test123",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": """# CI/CD失敗分析

## 問題の特定
ログを分析した結果、以下の問題が特定されました：

### 主要エラー
- ファイルシステムエラー: package.jsonが見つからない
- 認証エラー: テストでの認証失敗
- タイムアウトエラー: データベース接続タイムアウト

### 推奨対応
1. **即座に対応**: package.jsonの配置確認
2. **中期対応**: 認証システムの見直し
3. **長期対応**: データベース接続の最適化

信頼度: 90%
""",
        }
    ],
    "model": "claude-3-5-sonnet-20241022",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 180, "output_tokens": 220},
}

# ストリーミングレスポンスのモック
MOCK_STREAMING_CHUNKS = [
    "分析を開始します...",
    "\n\n## エラーの特定",
    "\n\nログを確認した結果、以下のエラーが見つかりました：",
    "\n\n1. **ファイル不足エラー**",
    "\n   - package.jsonが見つからない",
    "\n   - 原因: ワークスペース設定の問題",
    "\n\n2. **テスト失敗**",
    "\n   - 認証テストが失敗",
    "\n   - データベース接続タイムアウト",
    "\n\n## 修正提案",
    "\n\n### 即座に対応すべき項目",
    "\n1. package.jsonファイルの配置確認",
    "\n2. npm installステップの追加",
    "\n\n### 中長期的な改善",
    "\n1. 認証システムの見直し",
    "\n2. データベース接続の最適化",
    "\n\n分析完了。信頼度: 85%",
]

# エラーレスポンスのモック
MOCK_ERROR_RESPONSES = {
    "api_key_error": {
        "error": {
            "message": "Invalid API key provided",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_api_key",
        }
    },
    "rate_limit_error": {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error",
            "param": None,
            "code": "rate_limit_exceeded",
        }
    },
    "token_limit_error": {
        "error": {
            "message": "Token limit exceeded",
            "type": "invalid_request_error",
            "param": "messages",
            "code": "context_length_exceeded",
        }
    },
}

# 修正提案のモック
MOCK_FIX_SUGGESTIONS = [
    {
        "title": "package.jsonファイルの追加",
        "description": "プロジェクトルートにpackage.jsonファイルを作成します",
        "file_path": "package.json",
        "line_number": None,
        "original_code": None,
        "suggested_code": """{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "test": "jest"
  },
  "dependencies": {}
}""",
        "priority": "HIGH",
        "estimated_effort": "5分",
        "confidence": 0.95,
    },
    {
        "title": "npm installステップの追加",
        "description": "GitHub Actionsワークフローにnpm installステップを追加します",
        "file_path": ".github/workflows/test.yml",
        "line_number": 12,
        "original_code": "      - name: Run tests\n        run: npm test",
        "suggested_code": """      - name: Install dependencies
        run: npm install
      - name: Run tests
        run: npm test""",
        "priority": "HIGH",
        "estimated_effort": "2分",
        "confidence": 0.90,
    },
]

# 対話セッションのモック
MOCK_INTERACTIVE_RESPONSES = {
    "/help": """利用可能なコマンド:
/help - このヘルプを表示
/analyze - 詳細分析を実行
/fix - 修正提案を生成
/exit - セッションを終了""",
    "/analyze": """詳細分析を実行中...

追加の分析結果:
- エラーの発生頻度: 過去7日間で3回
- 影響範囲: テストスイート全体
- 類似エラー: 他のプロジェクトでも同様の問題が報告されています

推奨アクション:
1. 緊急度: 高 - package.json問題の即座の修正
2. 緊急度: 中 - CI/CDパイプラインの見直し""",
    "/fix": """修正提案を生成中...

以下の修正を提案します:

1. **package.json作成** (優先度: 高)
   - 実行時間: 5分
   - 成功確率: 95%

2. **ワークフロー修正** (優先度: 高)
   - 実行時間: 10分
   - 成功確率: 90%

これらの修正を適用しますか？ (y/n)""",
    "default": "申し訳ありませんが、その質問は理解できませんでした。/help でコマンド一覧を確認してください。",
}


def create_mock_analysis_result(
    summary: str = "テスト分析結果", confidence: float = 0.85, provider: str = "openai", model: str = "gpt-4o"
) -> dict[str, Any]:
    """
    分析結果のモックデータを作成

    Args:
        summary: 分析結果の要約
        confidence: 信頼度スコア
        provider: AIプロバイダー名
        model: 使用モデル名

    Returns:
        Dict[str, Any]: 分析結果のモックデータ
    """
    return {
        "summary": summary,
        "root_causes": [
            {
                "category": "dependency_error",
                "description": "package.jsonファイルが見つからない",
                "severity": "HIGH",
                "confidence": 0.95,
            },
            {"category": "test_failure", "description": "認証テストの失敗", "severity": "MEDIUM", "confidence": 0.80},
        ],
        "fix_suggestions": MOCK_FIX_SUGGESTIONS,
        "related_errors": ["npm ERR! code ENOENT", "AssertionError: Expected status code 401, got 200"],
        "confidence_score": confidence,
        "analysis_time": 2.5,
        "tokens_used": {"input_tokens": 150, "output_tokens": 200, "total_tokens": 350, "estimated_cost": 0.0175},
        "status": "COMPLETED",
        "provider": provider,
        "model": model,
        "timestamp": datetime.now().isoformat(),
        "cache_hit": False,
    }


def create_mock_streaming_response(chunks: list[str] | None = None) -> list[str]:
    """
    ストリーミングレスポンスのモックデータを作成

    Args:
        chunks: カスタムチャンクリスト（Noneの場合はデフォルトを使用）

    Returns:
        List[str]: ストリーミングチャンクのリスト
    """
    return chunks if chunks is not None else MOCK_STREAMING_CHUNKS


def create_mock_error_response(error_type: str) -> dict[str, Any]:
    """
    エラーレスポンスのモックデータを作成

    Args:
        error_type: エラータイプ（api_key_error, rate_limit_error, token_limit_error）

    Returns:
        Dict[str, Any]: エラーレスポンスのモックデータ
    """
    return MOCK_ERROR_RESPONSES.get(error_type, MOCK_ERROR_RESPONSES["api_key_error"])
