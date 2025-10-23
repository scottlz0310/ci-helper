"""
OpenAI プロバイダー実装

OpenAI APIを使用したAI分析機能を提供します。
GPT-4o、GPT-4o-miniなどのモデルに対応し、ストリーミングとコスト管理をサポートします。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import ClassVar

import aiohttp
import openai
from openai import AsyncOpenAI

from ..exceptions import APIKeyError, NetworkError, ProviderError, RateLimitError, TokenLimitError
from ..models import AnalysisResult, AnalyzeOptions, ProviderConfig
from .base import AIProvider


class OpenAIProvider(AIProvider):
    """OpenAI APIプロバイダー"""

    # モデル別のトークン制限
    MODEL_LIMITS: ClassVar[dict[str, int]] = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 4096,
        "gpt-3.5-turbo-16k": 16384,
    }

    # モデル別の料金（USD per 1K tokens）
    MODEL_COSTS: ClassVar[dict[str, dict[str, float]]] = {
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-32k": {"input": 0.06, "output": 0.12},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    }

    def __init__(self, config: ProviderConfig):
        """OpenAIプロバイダーを初期化

        Args:
            config: プロバイダー設定
        """
        super().__init__(config)
        self._client: AsyncOpenAI | None = None

    async def initialize(self) -> None:
        """プロバイダーを初期化

        Raises:
            ConfigurationError: APIキーが設定されていない場合
            APIKeyError: APIキーが無効な場合
            ProviderError: 初期化に失敗した場合
        """
        from ..exceptions import ConfigurationError

        if not self.config.api_key:
            raise ConfigurationError("OpenAI APIキーが設定されていません", "openai.api_key")

        try:
            # OpenAI クライアントを初期化
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                max_retries=self.config.max_retries,
            )

            # 接続テスト
            await self.validate_connection()

        except (APIKeyError, RateLimitError, ConfigurationError, ProviderError):
            # 既知のエラータイプはそのまま再発生
            raise
        except Exception as e:
            raise ProviderError("openai", f"OpenAI プロバイダーの初期化に失敗しました: {e}") from e

    async def validate_connection(self) -> bool:
        """接続を検証

        Returns:
            接続が有効かどうか

        Raises:
            ProviderError: 接続検証に失敗した場合
        """
        if not self._client:
            raise ProviderError("openai", "OpenAI クライアントが初期化されていません")

        try:
            # 簡単なテストリクエストを送信
            response = await self._client.chat.completions.create(
                model=self.config.default_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1,
            )
            return response is not None

        except openai.AuthenticationError as e:
            raise APIKeyError("openai", f"OpenAI APIキーが無効です: {e}") from e
        except openai.RateLimitError as e:
            raise RateLimitError("openai") from e
        except RateLimitError:
            # 既にカスタムRateLimitErrorの場合はそのまま再発生
            raise
        except Exception as e:
            raise ProviderError("openai", f"OpenAI 接続検証に失敗しました: {e}") from e

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
        max_tokens = self.MODEL_LIMITS.get(model, 8192)

        if input_tokens > max_tokens * 0.8:  # 80%を超えたら警告
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # OpenAI API呼び出し
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context},
                ],
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                timeout=options.timeout_seconds,
            )

            # 分析結果を構築
            analysis_time = time.time() - start_time
            content = response.choices[0].message.content or ""

            # トークン使用量を取得
            usage = response.usage
            token_usage = None
            if usage:
                token_usage = self.create_token_usage(usage.prompt_tokens, usage.completion_tokens, model)

            # 分析結果をパース（簡単な実装）
            analysis_result = self._parse_analysis_result(content)
            analysis_result.analysis_time = analysis_time
            analysis_result.tokens_used = token_usage
            analysis_result.provider = "openai"
            analysis_result.model = model

            return analysis_result

        except RateLimitError:
            # 既にカスタムRateLimitErrorの場合はそのまま再発生
            raise
        except openai.AuthenticationError as e:
            raise APIKeyError("openai", f"OpenAI APIキーが無効です: {e}") from e
        except openai.RateLimitError as e:
            raise RateLimitError("openai") from e
        except openai.BadRequestError as e:
            if "maximum context length" in str(e).lower():
                raise TokenLimitError(input_tokens, max_tokens, model) from e
            raise ProviderError("openai", f"OpenAI API リクエストエラー: {e}") from e
        except TimeoutError as e:
            raise NetworkError(f"ネットワークタイムアウト: {e}", retry_count=0) from e
        except (ConnectionError, openai.APIConnectionError, aiohttp.ClientConnectorError) as e:
            raise NetworkError(f"接続エラー: {e}", retry_count=0) from e
        except Exception as e:
            raise ProviderError("openai", f"OpenAI 分析に失敗しました: {e}") from e

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
        max_tokens = self.MODEL_LIMITS.get(model, 8192)

        if input_tokens > max_tokens * 0.8:
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # ストリーミング API呼び出し
            stream = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context},
                ],
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                timeout=options.timeout_seconds,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError:
            # 既にカスタムRateLimitErrorの場合はそのまま再発生
            raise
        except openai.AuthenticationError as e:
            raise APIKeyError("openai", f"OpenAI APIキーが無効です: {e}") from e
        except openai.RateLimitError as e:
            raise RateLimitError("openai") from e
        except openai.BadRequestError as e:
            if "maximum context length" in str(e).lower():
                raise TokenLimitError(input_tokens, max_tokens, model) from e
            raise ProviderError("openai", f"OpenAI API リクエストエラー: {e}") from e
        except TimeoutError as e:
            raise NetworkError(f"ネットワークタイムアウト: {e}", retry_count=0) from e
        except (ConnectionError, openai.APIConnectionError, aiohttp.ClientConnectorError) as e:
            raise NetworkError(f"接続エラー: {e}", retry_count=0) from e
        except Exception as e:
            raise ProviderError("openai", f"OpenAI ストリーミング分析に失敗しました: {e}") from e

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
        costs = self.MODEL_COSTS.get(model_name, {"input": 0.01, "output": 0.03})

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
        try:
            import tiktoken

            model_name = model or self.config.default_model

            # モデルに対応するエンコーダーを取得
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except KeyError:
                # 未知のモデルの場合はcl100k_baseエンコーディングを使用
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
        import re

        # マークダウン形式のレスポンスから要約を抽出
        summary = content.strip()

        # ## 分析結果の後の最初のテキストブロックを要約として抽出
        match = re.search(r"##\s*分析結果\s*\n+(.+?)(?:\n\n|$)", content, re.DOTALL)
        if match:
            summary = match.group(1).strip()
        else:
            # マッチしない場合は最初の500文字を使用
            summary = content[:500] + "..." if len(content) > 500 else content.strip()

        return AnalysisResult(
            summary=summary,
            confidence_score=0.8,  # デフォルト値
        )

    async def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        if self._client:
            await self._client.close()
            self._client = None
