"""
ローカルLLM プロバイダー実装

Ollama APIを使用したローカルLLM分析機能を提供します。
Llama 3.2、CodeLlamaなどのモデルに対応し、ローカル環境でのAI分析を実現します。
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import ClassVar

import aiohttp

from ..exceptions import NetworkError, ProviderError, TokenLimitError
from ..models import AnalysisResult, AnalyzeOptions, ProviderConfig
from .base import AIProvider


class LocalLLMProvider(AIProvider):
    """ローカルLLM（Ollama）プロバイダー"""

    # モデル別のトークン制限（推定値）
    MODEL_LIMITS: ClassVar[dict[str, int]] = {
        "llama3.2": 128000,
        "llama3.1": 128000,
        "codellama": 16384,
        "mistral": 32768,
        "phi3": 128000,
    }

    def __init__(self, config: ProviderConfig):
        """ローカルLLMプロバイダーを初期化

        Args:
            config: プロバイダー設定
        """
        super().__init__(config)
        # base_urlが"auto"の場合は自動検出
        if config.base_url == "auto":
            self.base_url = self._detect_ollama_url()
        else:
            self.base_url = config.base_url or "http://localhost:11434"
        self._session: aiohttp.ClientSession | None = None

    def _detect_ollama_url(self) -> str:
        """実行環境に応じてOllama URLを検出
        
        Returns:
            検出されたOllama URL
        """
        import platform
        import subprocess
        
        # WSL環境を検出
        if platform.system() == "Linux":
            try:
                # /proc/versionでWSLを確認
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower() or "wsl" in f.read().lower():
                        # WSLの場合、デフォルトゲートウェイを取得
                        result = subprocess.run(
                            ["ip", "route", "show", "default"],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            # "default via 172.20.176.1 dev eth0"のような出力からIPを抽出
                            parts = result.stdout.split()
                            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                                gateway_ip = parts[2]
                                return f"http://{gateway_ip}:11434"
            except Exception:
                pass
        
        # デフォルトはlocalhost
        return "http://localhost:11434"
    
    async def initialize(self) -> None:
        """プロバイダーを初期化

        Raises:
            ProviderError: 初期化に失敗した場合
        """
        try:
            # HTTP セッションを作成
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

            # 接続テスト
            await self.validate_connection()

        except Exception as e:
            # 初期化に失敗した場合はセッションをクリーンアップ
            if self._session:
                await self._session.close()
                self._session = None
            raise ProviderError("local", f"ローカルLLM プロバイダーの初期化に失敗しました: {e}") from e

    async def validate_connection(self) -> bool:
        """接続を検証

        Returns:
            接続が有効かどうか

        Raises:
            ProviderError: 接続検証に失敗した場合
        """
        if not self._session:
            raise ProviderError("local", "HTTP セッションが初期化されていません")

        try:
            # Ollama サーバーの状態を確認
            async with self._session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    # 利用可能なモデルがあるかチェック
                    models = data.get("models", [])
                    available_model_names = [model["name"] for model in models]

                    # 設定されたデフォルトモデルが利用可能かチェック
                    if self.config.default_model not in available_model_names:
                        # モデルが見つからない場合は警告だが接続は有効
                        pass

                    return True
                else:
                    raise ProviderError("local", f"Ollama サーバーからエラー応答: {response.status}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"Ollama サーバーへの接続に失敗しました: {e}") from e
        except Exception as e:
            raise ProviderError("local", f"ローカルLLM 接続検証に失敗しました: {e}") from e

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
        """
        if not self._session:
            await self.initialize()

        model = self.get_model(options.model)
        start_time = time.time()

        # トークン制限チェック（簡易）
        input_tokens = self.count_tokens(f"{prompt}\n{context}", model)
        max_tokens = self.MODEL_LIMITS.get(model, 32768)

        if input_tokens > max_tokens * 0.8:  # 80%を超えたら警告
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # Ollama API呼び出し
            payload = {
                "model": model,
                "prompt": f"{prompt}\n\n{context}",
                "stream": False,
                "options": {
                    "temperature": options.temperature,
                    "num_predict": options.max_tokens or 4000,
                },
            }

            async with self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ProviderError("local", f"Ollama API エラー: {response.status} - {error_text}")

                data = await response.json()
                content = data.get("response", "")

                # 分析結果を構築
                analysis_time = time.time() - start_time

                # トークン使用量を推定（Ollamaは詳細な使用量を返さない）
                output_tokens = self.count_tokens(content, model)
                token_usage = self.create_token_usage(input_tokens, output_tokens, model)

                # 分析結果をパース
                analysis_result = self._parse_analysis_result(content)
                analysis_result.analysis_time = analysis_time
                analysis_result.tokens_used = token_usage
                analysis_result.provider = "local"
                analysis_result.model = model

                return analysis_result

        except aiohttp.ClientError as e:
            raise NetworkError(f"Ollama サーバーへの接続に失敗しました: {e}") from e
        except Exception as e:
            raise ProviderError("local", f"ローカルLLM 分析に失敗しました: {e}") from e

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
        """
        if not self._session:
            await self.initialize()

        model = self.get_model(options.model)

        # トークン制限チェック
        input_tokens = self.count_tokens(f"{prompt}\n{context}", model)
        max_tokens = self.MODEL_LIMITS.get(model, 32768)

        if input_tokens > max_tokens * 0.8:
            raise TokenLimitError(input_tokens, max_tokens, model)

        try:
            # ストリーミング API呼び出し
            payload = {
                "model": model,
                "prompt": f"{prompt}\n\n{context}",
                "stream": True,
                "options": {
                    "temperature": options.temperature,
                    "num_predict": options.max_tokens or 4000,
                },
            }

            async with self._session.post(
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ProviderError("local", f"Ollama API エラー: {response.status} - {error_text}")

                # ストリーミングレスポンスを処理
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            if "response" in data:
                                yield data["response"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except aiohttp.ClientError as e:
            raise NetworkError(f"Ollama サーバーへの接続に失敗しました: {e}") from e
        except Exception as e:
            raise ProviderError("local", f"ローカルLLM ストリーミング分析に失敗しました: {e}") from e

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        """コストを推定

        Args:
            input_tokens: 入力トークン数
            output_tokens: 出力トークン数
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            推定コスト（USD）- ローカルLLMは無料なので0.0
        """
        return 0.0  # ローカルLLMは無料

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """テキストのトークン数をカウント

        Args:
            text: カウント対象のテキスト
            model: モデル名（指定されない場合はデフォルトモデル）

        Returns:
            トークン数
        """
        # ローカルLLMの場合、正確なトークナイザーが利用できないことが多いため
        # 文字数ベースで推定
        return len(text) // 4

    def get_available_models(self) -> list[str]:
        """利用可能なモデル一覧を取得

        Returns:
            モデル名のリスト
        """
        return self.config.available_models

    async def get_installed_models(self) -> list[str]:
        """Ollamaにインストールされているモデル一覧を取得

        Returns:
            インストール済みモデル名のリスト

        Raises:
            ProviderError: モデル一覧の取得に失敗した場合
        """
        if not self._session:
            await self.initialize()

        try:
            async with self._session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    return [model["name"] for model in models]
                else:
                    raise ProviderError("local", f"モデル一覧の取得に失敗しました: {response.status}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"Ollama サーバーへの接続に失敗しました: {e}") from e
        except Exception as e:
            raise ProviderError("local", f"モデル一覧の取得に失敗しました: {e}") from e

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
            confidence_score=0.7,  # ローカルLLMは少し低めの信頼度
        )

    async def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        if self._session:
            await self._session.close()
            self._session = None
