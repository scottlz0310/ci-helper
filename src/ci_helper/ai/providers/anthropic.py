"""
Anthropic プロバイダー実装

Anthropic Claude APIを使用したAI分析機能を提供します。
Claude 3.5 Sonnet、Claude 3.5 Haikuなどのモデルに対応し、ストリーミングとコスト管理をサポートします。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from ..exceptions import APIKeyError, ProviderError, RateLimitError, TokenLimitError
from ..models import AnalysisResult, AnalyzeOptions, ProviderConfig
from .base import AIProvider


class AnthropicProvider(AIProvider):
    """Anthropic Claude APIプロバイダー"""

    # モデル別のトークン制限
    MODEL_LIMITS: Dict[str, int] = {
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-haiku-20241022": 200000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
    }

    # モデル別の料金（USD per 1K tokens）
    MODEL_COSTS: Dict[str, Dict[str, float]] = {
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-5-haiku-20241022": {"input": 0.00025, "output": 0.00125},
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    }

    def __init__(self, config: ProviderConfig):
        """Anthropicプロバイダーを初期化

        Args:
            config: プロバイダー設定
        """
        super().__init__(config)
        self._client: AsyncAnthropic | None = None

    async def initialize(self) -> None:
        """プロバイダーを初期化

        Raises:
            APIKeyError: APIキーが無効な場合
            ProviderError: 初期化に失敗した場合
        """
        if not self.config.api_key:
            raise APIKeyError("anthropic", "Anthropic APIキーが設定されていません")

        try:
            # Anthropic クライアントを初期化
            self._client = AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )

            # 接続テスト
            await self.validate_connection()

        except Exception as e:
            raise ProviderError("anthropic", f"Anthropic プロバイダーの初期化に失敗しました: {e}") from e

    async def validate_connection(self) -> bool:
        """接続を検証

        Returns:
            接続が有効かどうか

        Raises:
            ProviderError: 接続検証に失敗した場合
        """
        if not self._client:
            raise ProviderError("anthropic", "Anthropic クライアントが初期化されていません")

        try:
            # 簡単なテストリクエストを送信
            response = await self._client.messages.create(
                model=self.config.default_model,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hello"}],
            )
            return response is not None

        except anthropic.AuthenticationError as e:
            raise APIKeyError("anthropic", f"Anthropic APIキーが無効です: {e}") from e
        except anthropic.RateLimitError as e:
            raise RateLimitError("anthropic") from e
        except Exception as e:
            raise ProviderError("anthropic", f"Anthropic 接続検証に失敗しました: {e}") from e

    async def analyze(self, prompt: str, context: str, options: AnalyzeOptions) -> AnalysisResult:
        """ログを分析してAI結果を返す

        Args:
            prompt: 分析用プロンプト
            context: 分析対象のログコンテンツ
            options: 分析オプション

        Returns:
            分析結果

        Raises:
            ProviderError: 分析に失敗した場合
            TokenLimitError: トークン制限を超過した場合
            RateLimitError: レート制限に達した場合
        """
        if not self._client:
            await self.initialize()

        model = self.get_model(options.model)
        start_time = time.time()

        # トークン制限チェック
        input_tokens = self.count_tokens(f"{prompt}\n{context}", model)
        max_tokens = self.MODEL_LIMITS.get(model, 200000)

        if input_tokens > max_tokens * 0.8:  # 80%を超えたら警告
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # Anthropic API呼び出し
            response = await self._client.messages.create(
                model=model,
                max_tokens=options.max_tokens or 4000,
                temperature=options.temperature,
                system=prompt,
                messages=[{"role": "user", "content": context}],
            )

            # 分析結果を構築
            analysis_time = time.time() - start_time
            content = ""

            # レスポンスからテキストを抽出
            for content_block in response.content:
                if hasattr(content_block, "text"):
                    content += content_block.text

            # トークン使用量を取得
            usage = response.usage
            token_usage = None
            if usage:
                token_usage = self.create_token_usage(usage.input_tokens, usage.output_tokens, model)

            # 分析結果をパース
            analysis_result = self._parse_analysis_result(content)
            analysis_result.analysis_time = analysis_time
            analysis_result.tokens_used = token_usage
            analysis_result.provider = "anthropic"
            analysis_result.model = model

            return analysis_result

        except anthropic.AuthenticationError as e:
            raise APIKeyError("anthropic", f"Anthropic APIキーが無効です: {e}") from e
        except anthropic.RateLimitError as e:
            raise RateLimitError("anthropic") from e
        except anthropic.BadRequestError as e:
            if "maximum context length" in str(e).lower():
                raise TokenLimitError(input_tokens, max_tokens, model) from e
            raise ProviderError("anthropic", f"Anthropic API リクエストエラー: {e}") from e
        except Exception as e:
            raise ProviderError("anthropic", f"Anthropic 分析に失敗しました: {e}") from e

    async def stream_analyze(self, prompt: str, context: str, options: AnalyzeOptions) -> AsyncIterator[str]:
        """ストリーミング分析を実行

        Args:
            prompt: 分析用プロンプト
            context: 分析対象のログコンテンツ
            options: 分析オプション

        Yields:
            分析結果の部分文字列

        Raises:
            ProviderError: 分析に失敗した場合
            TokenLimitError: トークン制限を超過した場合
            RateLimitError: レート制限に達した場合
        """
        if not self._client:
            await self.initialize()

        model = self.get_model(options.model)

        # トークン制限チェック
        input_tokens = self.count_tokens(f"{prompt}\n{context}", model)
        max_tokens = self.MODEL_LIMITS.get(model, 200000)

        if input_tokens > max_tokens * 0.8:
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # ストリーミング API呼び出し
            async with self._client.messages.stream(
                model=model,
                max_tokens=options.max_tokens or 4000,
                temperature=options.temperature,
                system=prompt,
                messages=[{"role": "user", "content": context}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.AuthenticationError as e:
            raise APIKeyError("anthropic", f"Anthropic APIキーが無効です: {e}") from e
        except anthropic.RateLimitError as e:
            raise RateLimitError("anthropic") from e
        except anthropic.BadRequestError as e:
            if "maximum context length" in str(e).lower():
                raise TokenLimitError(input_tokens, max_tokens, model) from e
            raise ProviderError("anthropic", f"Anthropic API リクエストエラー: {e}") from e
        except Exception as e:
            raise ProviderError("anthropic", f"Anthropic ストリーミング分析に失敗しました: {e}") from e

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        """コストを推定

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            推定コスト（USD）
        """
        model_name = model or self.config.default_model
        costs = self.MODEL_COSTS.get(model_name, {"input": 0.003, "output": 0.015})

        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]

        return input_cost + output_cost

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """テキストのトークン数をカウント

        Args:
            text: カウント対象のテキスト
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            トークン数
        """
        # Anthropicは独自のトークナイザーを使用するが、
        # 簡易的にtiktokenで推定（Claude 3はGPT-4と似たトークナイザー）
        try:
            import tiktoken

            # cl100k_baseエンコーディングを使用（Claude 3系で近似）
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))

        except ImportError:
            # tiktokenが利用できない場合は文字数ベースで推定
            return len(text) // 4

    def get_available_models(self) -> list[str]:
        """利用可能なモデル一覧を取得

        Returns:
            モデル名のリスト
        """
        return self.config.available_models

    def _parse_analysis_result(self, content: str) -> AnalysisResult:
        """分析結果をパースしてAnalysisResultオブジェクトを作成

        Args:
            content: AI分析結果のテキスト

        Returns:
            パースされた分析結果
        """
        # 簡単な実装 - 実際にはより詳細なパースが必要
        return AnalysisResult(
            summary=content[:500] + "..." if len(content) > 500 else content,
            confidence_score=0.8,  # デフォルト値
        )

    async def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        if self._client:
            await self._client.close()
            self._client = None
