"""
非同期モック安定化システム

非同期コンテキストでのモック動作を安定化し、
AsyncMockの適切な設定と管理を提供します。
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

logger = logging.getLogger(__name__)


class AsyncMockContextManager:
    """非同期モックのコンテキスト管理を担当するクラス"""

    def __init__(self):
        self._active_mocks: dict[str, AsyncMock] = {}
        self._cleanup_tasks: list[asyncio.Task] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup_all()

    async def cleanup_all(self):
        """すべてのアクティブなモックをクリーンアップ"""
        # 実行中のタスクをキャンセル
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # モックオブジェクトのクリーンアップ
        for mock_name, mock_obj in self._active_mocks.items():
            try:
                await self._cleanup_single_mock(mock_obj)
            except Exception as e:
                logger.warning(f"モック {mock_name} のクリーンアップ中にエラー: {e}")

        self._active_mocks.clear()
        self._cleanup_tasks.clear()

    async def _cleanup_single_mock(self, mock_obj: AsyncMock):
        """単一のAsyncMockをクリーンアップ"""
        if hasattr(mock_obj, "_mock_return_value"):
            return_value = mock_obj._mock_return_value
            if asyncio.iscoroutine(return_value):
                try:
                    return_value.close()
                except (RuntimeError, StopIteration):
                    pass

    def register_mock(self, name: str, mock_obj: AsyncMock):
        """モックを登録して管理対象に追加"""
        self._active_mocks[name] = mock_obj

    def create_stable_async_mock(
        self,
        name: str,
        return_value: Any = None,
        side_effect: Any = None,
        spec: Any = None,
    ) -> AsyncMock:
        """安定したAsyncMockを作成"""
        mock_obj = AsyncMock(spec=spec)

        if return_value is not None:
            mock_obj.return_value = return_value

        if side_effect is not None:
            if isinstance(side_effect, Exception):
                mock_obj.side_effect = side_effect
            elif isinstance(side_effect, list):
                # リストの場合は循環させて StopIteration を防ぐ
                mock_obj.side_effect = self._create_cycling_side_effect(side_effect)
            else:
                mock_obj.side_effect = side_effect

        self.register_mock(name, mock_obj)
        return mock_obj

    def _create_cycling_side_effect(self, values: list[Any]) -> Callable:
        """循環するside_effectを作成してStopIterationを防ぐ"""
        if not values:
            values = [None]

        async def cycling_effect(*args, **kwargs):
            # インデックスを循環させる
            if not hasattr(cycling_effect, "_index"):
                cycling_effect._index = 0

            if cycling_effect._index < len(values):
                result = values[cycling_effect._index]
                cycling_effect._index += 1
            else:
                # リストの最後に達したら最後の値を繰り返す
                result = values[-1]

            # 例外の場合は発生させる
            if isinstance(result, Exception):
                raise result

            return result

        return cycling_effect


class AsyncMockErrorHandler:
    """非同期モックのエラーハンドリングを改善するクラス"""

    @staticmethod
    def create_error_propagating_mock(
        exception_type: type, error_message: str = "Mock error", **mock_kwargs
    ) -> AsyncMock:
        """エラーを適切に伝播するAsyncMockを作成"""
        mock = AsyncMock(**mock_kwargs)

        async def error_side_effect(*args, **kwargs):
            raise exception_type(error_message)

        mock.side_effect = error_side_effect
        return mock

    @staticmethod
    def create_timeout_mock(timeout_seconds: float = 1.0, **mock_kwargs) -> AsyncMock:
        """タイムアウトエラーを発生させるAsyncMockを作成"""
        mock = AsyncMock(**mock_kwargs)

        async def timeout_side_effect(*args, **kwargs):
            await asyncio.sleep(timeout_seconds)
            raise TimeoutError("Mock timeout")

        mock.side_effect = timeout_side_effect
        return mock

    @staticmethod
    def create_network_error_mock(error_message: str = "Network error", **mock_kwargs) -> AsyncMock:
        """ネットワークエラーを発生させるAsyncMockを作成"""
        import aiohttp

        mock = AsyncMock(**mock_kwargs)

        async def network_error_side_effect(*args, **kwargs):
            raise aiohttp.ClientConnectorError(Mock(), Mock())

        mock.side_effect = network_error_side_effect
        return mock


class AsyncMockStabilizer:
    """非同期モックの安定性を向上させるメインクラス"""

    def __init__(self):
        self.context_manager = AsyncMockContextManager()
        self.error_handler = AsyncMockErrorHandler()

    @asynccontextmanager
    async def stable_async_context(self):
        """安定した非同期コンテキストを提供"""
        async with self.context_manager:
            yield self.context_manager

    def create_stable_provider_mock(self, provider_name: str = "test_provider", **provider_methods) -> Mock:
        """安定したプロバイダーモックを作成"""
        provider_mock = Mock()

        # 基本的な非同期メソッドを設定
        provider_mock.cleanup = self.context_manager.create_stable_async_mock(
            f"{provider_name}_cleanup", return_value=None
        )

        provider_mock.validate_connection = self.context_manager.create_stable_async_mock(
            f"{provider_name}_validate", return_value=True
        )

        provider_mock.analyze = self.context_manager.create_stable_async_mock(
            f"{provider_name}_analyze", return_value={"analysis": "test result"}
        )

        # カスタムメソッドを追加
        for method_name, config in provider_methods.items():
            if isinstance(config, dict):
                provider_mock.__setattr__(
                    method_name,
                    self.context_manager.create_stable_async_mock(f"{provider_name}_{method_name}", **config),
                )
            else:
                provider_mock.__setattr__(method_name, config)

        return provider_mock

    def create_stable_integration_mock(
        self, integration_name: str = "test_integration", providers: dict[str, Mock] | None = None
    ) -> Mock:
        """安定したAI統合モックを作成"""
        integration_mock = Mock()

        # プロバイダー辞書を設定
        if providers is None:
            providers = {
                "openai": self.create_stable_provider_mock("openai"),
                "anthropic": self.create_stable_provider_mock("anthropic"),
            }

        integration_mock.providers = providers

        # 統合レベルの非同期メソッドを設定
        integration_mock.initialize = self.context_manager.create_stable_async_mock(
            f"{integration_name}_initialize", return_value=None
        )

        integration_mock.cleanup = self.context_manager.create_stable_async_mock(
            f"{integration_name}_cleanup", return_value=None
        )

        integration_mock.analyze_log = self.context_manager.create_stable_async_mock(
            f"{integration_name}_analyze_log", return_value={"analysis": "test result"}
        )

        return integration_mock

    def patch_async_method_with_error_handling(
        self, target: str, exception_type: type, error_message: str = "Test error", **patch_kwargs
    ):
        """エラーハンドリング付きで非同期メソッドをパッチ"""
        error_mock = self.error_handler.create_error_propagating_mock(exception_type, error_message)
        return patch(target, new=error_mock, **patch_kwargs)

    def setup_async_side_effects_with_fallback(
        self, mock_obj: AsyncMock, effects: list[Any], fallback_value: Any = None
    ):
        """フォールバック付きでside_effectsを設定"""
        if not effects:
            effects = [fallback_value]

        async def safe_side_effect(*args, **kwargs):
            if not hasattr(safe_side_effect, "_call_count"):
                safe_side_effect._call_count = 0

            if safe_side_effect._call_count < len(effects):
                effect = effects[safe_side_effect._call_count]
                safe_side_effect._call_count += 1
            else:
                effect = fallback_value

            if isinstance(effect, Exception):
                raise effect
            elif callable(effect):
                result = effect(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                return effect

        mock_obj.side_effect = safe_side_effect

    def create_async_stream_mock(self, chunks: list[str], chunk_delay: float = 0.01) -> AsyncMock:
        """非同期ストリームモックを作成"""
        mock = AsyncMock()

        async def stream_generator():
            for chunk in chunks:
                await asyncio.sleep(chunk_delay)
                yield chunk

        mock.return_value = stream_generator()
        self.context_manager.register_mock("stream_mock", mock)
        return mock

    def create_async_context_manager_mock(
        self, enter_value: Any = None, exit_value: Any = None, **mock_kwargs
    ) -> AsyncMock:
        """非同期コンテキストマネージャーモックを作成"""
        mock = AsyncMock(**mock_kwargs)

        mock.__aenter__ = self.context_manager.create_stable_async_mock(
            "context_enter", return_value=enter_value or mock
        )

        mock.__aexit__ = self.context_manager.create_stable_async_mock("context_exit", return_value=exit_value)

        return mock


# グローバルインスタンス
_global_stabilizer = AsyncMockStabilizer()


def get_async_mock_stabilizer() -> AsyncMockStabilizer:
    """グローバルなAsyncMockStabilizerインスタンスを取得"""
    return _global_stabilizer


@asynccontextmanager
async def stable_async_test_context():
    """テスト用の安定した非同期コンテキスト"""
    async with _global_stabilizer.stable_async_context() as context:
        yield context


def create_stable_async_mock_with_error_handling(
    return_value: Any = None, side_effect: Any = None, exception_on_call: Exception | None = None, **mock_kwargs
) -> AsyncMock:
    """エラーハンドリング付きの安定したAsyncMockを作成"""
    stabilizer = get_async_mock_stabilizer()

    if exception_on_call:
        return stabilizer.error_handler.create_error_propagating_mock(
            type(exception_on_call), str(exception_on_call), **mock_kwargs
        )

    return stabilizer.context_manager.create_stable_async_mock(
        "test_mock", return_value=return_value, side_effect=side_effect, **mock_kwargs
    )


def patch_with_stable_async_mock(
    target: str,
    return_value: Any = None,
    side_effect: Any = None,
    exception_on_call: Exception | None = None,
    **patch_kwargs,
):
    """安定したAsyncMockでパッチを適用"""
    mock = create_stable_async_mock_with_error_handling(
        return_value=return_value, side_effect=side_effect, exception_on_call=exception_on_call
    )
    return patch(target, new=mock, **patch_kwargs)


def ensure_async_mock_cleanup(test_func):
    """テスト関数に非同期モッククリーンアップを追加するデコレータ"""
    if not asyncio.iscoroutinefunction(test_func):
        raise ValueError("ensure_async_mock_cleanup can only be used with async functions")

    async def wrapper(*args, **kwargs):
        async with stable_async_test_context():
            return await test_func(*args, **kwargs)

    return wrapper


class AsyncMockValidator:
    """非同期モックの状態を検証するクラス"""

    @staticmethod
    def validate_async_mock_calls(mock_obj: AsyncMock, expected_calls: int = None):
        """AsyncMockの呼び出し状態を検証"""
        if expected_calls is not None:
            actual_calls = mock_obj.call_count
            if actual_calls != expected_calls:
                logger.warning(f"AsyncMock call count mismatch: expected {expected_calls}, got {actual_calls}")

    @staticmethod
    def validate_async_mock_side_effects(mock_obj: AsyncMock):
        """AsyncMockのside_effectが適切に設定されているか検証"""
        if hasattr(mock_obj, "side_effect") and mock_obj.side_effect:
            if isinstance(mock_obj.side_effect, list):
                # リストの場合、空でないことを確認
                if not mock_obj.side_effect:
                    logger.warning("AsyncMock has empty side_effect list")

    @staticmethod
    def validate_async_context_manager(mock_obj: AsyncMock):
        """非同期コンテキストマネージャーとしての設定を検証"""
        required_methods = ["__aenter__", "__aexit__"]
        for method in required_methods:
            if not hasattr(mock_obj, method):
                logger.warning(f"AsyncMock missing {method} for context manager usage")


# 便利な関数エイリアス
create_stable_provider_mock = lambda **kwargs: get_async_mock_stabilizer().create_stable_provider_mock(**kwargs)
create_stable_integration_mock = lambda **kwargs: get_async_mock_stabilizer().create_stable_integration_mock(**kwargs)
create_async_stream_mock = lambda chunks, **kwargs: get_async_mock_stabilizer().create_async_stream_mock(
    chunks, **kwargs
)


# 便利な関数エイリアス
def create_stable_provider_mock(**kwargs):
    """安定したプロバイダーモックを作成する便利関数"""
    return get_async_mock_stabilizer().create_stable_provider_mock(**kwargs)


def create_stable_integration_mock(**kwargs):
    """安定した統合モックを作成する便利関数"""
    return get_async_mock_stabilizer().create_stable_integration_mock(**kwargs)


def create_async_stream_mock(chunks, **kwargs):
    """非同期ストリームモックを作成する便利関数"""
    return get_async_mock_stabilizer().create_async_stream_mock(chunks, **kwargs)
