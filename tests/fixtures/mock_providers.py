"""
AIプロバイダーのモック実装

このファイルは各AIプロバイダー（OpenAI、Anthropic、ローカル）のモック実装を提供します。
実際のAPI呼び出しを行わずにプロバイダー固有の動作をテストできます。
"""

from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List, AsyncIterator
from datetime import datetime

from tests.fixtures.ai_responses import (
    MOCK_OPENAI_RESPONSE,
    MOCK_ANTHROPIC_RESPONSE,
    MOCK_STREAMING_CHUNKS,
    create_mock_analysis_result
)


class MockOpenAIProvider:
    """
    OpenAI APIプロバイダーのモック実装
    
    OpenAIの実際のAPIレスポンス形式を模擬し、
    テスト環境でOpenAI固有の動作を再現します。
    """
    
    def __init__(self, api_key: str = "sk-test-key"):
        self.name = "openai"
        self.api_key = api_key
        self.default_model = "gpt-4o"
        self.available_models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        self.timeout_seconds = 30
        self.max_retries = 3
        
    async def initialize(self) -> None:
        """プロバイダーの初期化（モック）"""
        pass
        
    async def validate_connection(self) -> bool:
        """接続検証（モック）"""
        return True
        
    def count_tokens(self, text: str) -> int:
        """トークン数カウント（モック）"""
        # 簡易的な計算（実際のtiktokenより単純）
        return len(text.split()) * 1.3
        
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = None) -> float:
        """コスト見積もり（モック）"""
        model = model or self.default_model
        if "gpt-4o" in model:
            return (input_tokens * 0.00003 + output_tokens * 0.00006)
        else:
            return (input_tokens * 0.0000015 + output_tokens * 0.000002)
            
    async def analyze(self, prompt: str, context: str = "", model: str = None) -> Dict[str, Any]:
        """分析実行（モック）"""
        # OpenAI形式のレスポンスを返す
        response_data = MOCK_OPENAI_RESPONSE.copy()
        
        # 入力に基づいて動的にレスポンスを調整
        if "package.json" in context:
            response_data["choices"][0]["message"]["content"] = """# 依存関係エラーの分析

## 問題
package.jsonファイルが見つからないため、npm installが失敗しています。

## 修正提案
1. package.jsonファイルをプロジェクトルートに作成
2. 必要な依存関係を定義
3. GitHub Actionsワークフローを更新

## 信頼度: 95%"""
        
        return create_mock_analysis_result(
            summary=response_data["choices"][0]["message"]["content"],
            provider="openai",
            model=model or self.default_model
        )
        
    async def stream_analyze(self, prompt: str, context: str = "", model: str = None) -> AsyncIterator[str]:
        """ストリーミング分析（モック）"""
        for chunk in MOCK_STREAMING_CHUNKS:
            yield chunk
            
    async def cleanup(self) -> None:
        """クリーンアップ（モック）"""
        pass


class MockAnthropicProvider:
    """
    Anthropic APIプロバイダーのモック実装
    
    AnthropicのClaude APIの実際のレスポンス形式を模擬し、
    テスト環境でAnthropic固有の動作を再現します。
    """
    
    def __init__(self, api_key: str = "sk-ant-test-key"):
        self.name = "anthropic"
        self.api_key = api_key
        self.default_model = "claude-3-5-sonnet-20241022"
        self.available_models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
        self.timeout_seconds = 30
        self.max_retries = 3
        
    async def initialize(self) -> None:
        """プロバイダーの初期化（モック）"""
        pass
        
    async def validate_connection(self) -> bool:
        """接続検証（モック）"""
        return True
        
    def count_tokens(self, text: str) -> int:
        """トークン数カウント（モック）"""
        # Anthropic用の簡易計算
        return len(text.split()) * 1.2
        
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = None) -> float:
        """コスト見積もり（モック）"""
        model = model or self.default_model
        if "sonnet" in model:
            return (input_tokens * 0.000003 + output_tokens * 0.000015)
        else:  # haiku
            return (input_tokens * 0.00000025 + output_tokens * 0.00000125)
            
    async def analyze(self, prompt: str, context: str = "", model: str = None) -> Dict[str, Any]:
        """分析実行（モック）"""
        # Anthropic形式のレスポンスを返す
        response_data = MOCK_ANTHROPIC_RESPONSE.copy()
        
        # 入力に基づいて動的にレスポンスを調整
        if "timeout" in context.lower():
            response_data["content"][0]["text"] = """# タイムアウトエラーの分析

## 根本原因
データベース接続でタイムアウトが発生しています。

### 考えられる原因
1. ネットワーク遅延
2. データベースサーバーの負荷
3. 接続プールの枯渇

## 推奨対応
1. 接続タイムアウト値の調整
2. データベースインデックスの最適化
3. 接続プールサイズの増加

信頼度: 88%"""
        
        return create_mock_analysis_result(
            summary=response_data["content"][0]["text"],
            provider="anthropic",
            model=model or self.default_model
        )
        
    async def stream_analyze(self, prompt: str, context: str = "", model: str = None) -> AsyncIterator[str]:
        """ストリーミング分析（モック）"""
        # Anthropic風のストリーミングレスポンス
        anthropic_chunks = [
            "分析を開始します。",
            "\n\nログを詳細に検証中...",
            "\n\n## 発見された問題",
            "\n\n1. **主要エラー**: ",
            "データベース接続タイムアウト",
            "\n2. **副次的問題**: ",
            "認証システムの不具合",
            "\n\n## 推奨解決策",
            "\n\n### 即座の対応",
            "\n- 接続タイムアウト値を60秒に増加",
            "\n- データベース接続プールを再起動",
            "\n\n### 長期的改善",
            "\n- インデックス最適化の実施",
            "\n- 監視システムの強化",
            "\n\n分析完了。信頼度: 88%"
        ]
        
        for chunk in anthropic_chunks:
            yield chunk
            
    async def cleanup(self) -> None:
        """クリーンアップ（モック）"""
        pass


class MockLocalProvider:
    """
    ローカルLLMプロバイダーのモック実装
    
    Ollamaなどのローカル実行LLMの動作を模擬し、
    オフライン環境でのテストを可能にします。
    """
    
    def __init__(self, model_name: str = "llama2"):
        self.name = "local"
        self.model_name = model_name
        self.default_model = model_name
        self.available_models = ["llama2", "codellama", "mistral"]
        self.timeout_seconds = 60  # ローカルは時間がかかる場合がある
        self.max_retries = 1
        
    async def initialize(self) -> None:
        """プロバイダーの初期化（モック）"""
        pass
        
    async def validate_connection(self) -> bool:
        """接続検証（モック）"""
        return True
        
    def count_tokens(self, text: str) -> int:
        """トークン数カウント（モック）"""
        # ローカルモデル用の簡易計算
        return len(text.split())
        
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = None) -> float:
        """コスト見積もり（モック）"""
        # ローカル実行なのでコストは0
        return 0.0
        
    async def analyze(self, prompt: str, context: str = "", model: str = None) -> Dict[str, Any]:
        """分析実行（モック）"""
        # ローカルLLMらしい、やや簡潔なレスポンス
        local_response = """# ログ分析結果

## エラーの特定
ログを確認したところ、以下の問題が見つかりました：

- ファイル不足: package.jsonが見つからない
- テスト失敗: 認証関連のテストが失敗
- 接続問題: データベースへの接続でタイムアウト

## 修正案
1. package.jsonファイルを作成
2. 認証ロジックを確認
3. データベース設定を見直し

これらの修正により問題は解決できると思われます。"""
        
        return create_mock_analysis_result(
            summary=local_response,
            provider="local",
            model=model or self.default_model,
            confidence=0.75  # ローカルモデルは少し信頼度を下げる
        )
        
    async def stream_analyze(self, prompt: str, context: str = "", model: str = None) -> AsyncIterator[str]:
        """ストリーミング分析（モック）"""
        # ローカルLLMらしい、段階的なレスポンス
        local_chunks = [
            "ログを分析中",
            "...",
            "\n\nエラーを特定しました",
            "\n\n主な問題:",
            "\n- package.json不足",
            "\n- テスト失敗",
            "\n- DB接続エラー",
            "\n\n修正提案:",
            "\n1. ファイル作成",
            "\n2. テスト修正", 
            "\n3. 設定見直し",
            "\n\n完了"
        ]
        
        for chunk in local_chunks:
            yield chunk
            
    async def cleanup(self) -> None:
        """クリーンアップ（モック）"""
        pass


def create_mock_provider(provider_name: str, **kwargs) -> Mock:
    """
    指定されたプロバイダーのモックを作成
    
    Args:
        provider_name: プロバイダー名（openai, anthropic, local）
        **kwargs: プロバイダー固有の設定
        
    Returns:
        Mock: 指定されたプロバイダーのモック
    """
    provider_classes = {
        "openai": MockOpenAIProvider,
        "anthropic": MockAnthropicProvider,
        "local": MockLocalProvider
    }
    
    provider_class = provider_classes.get(provider_name, MockOpenAIProvider)
    return provider_class(**kwargs)


def create_provider_factory_mock() -> Mock:
    """
    プロバイダーファクトリーのモックを作成
    
    Returns:
        Mock: プロバイダーファクトリーのモック
    """
    factory_mock = Mock()
    
    def create_provider_side_effect(provider_name: str, config: Dict[str, Any]):
        return create_mock_provider(provider_name, **config)
    
    factory_mock.create_provider.side_effect = create_provider_side_effect
    factory_mock.get_available_providers.return_value = ["openai", "anthropic", "local"]
    factory_mock.validate_provider_config.return_value = True
    
    return factory_mock