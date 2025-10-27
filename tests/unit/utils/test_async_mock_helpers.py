"""
非同期モックヘルパーのテスト

AsyncMockManagerとAsyncMockStabilizerの動作を検証します。
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from tests.utils.mock_helpers import (
    AsyncMockManager,
    AsyncMockStabilizer,
    create_async_mock_with_stable_behavior,
    patch_async_method_with_stable_mock,
    setup_stable_async_mock,
)


class TestAsyncMockManager:
    """AsyncMockManagerのテスト"""

    def test_create_async_mock_with_return_value(self):
        """戻り値を持つAsyncMockの作成テスト"""
        expected_value = "test_result"
        mock = AsyncMockManager.create_async_mock_with_return_value(expected_value)

        assert isinstance(mock, AsyncMock)
        assert mock.return_value == expected_value

    @pytest.mark.asyncio
    async def test_async_mock_with_return_value_execution(self):
        """戻り値を持つAsyncMockの実行テスト"""
        expected_value = "test_result"
        mock = AsyncMockManager.create_async_mock_with_return_value(expected_value)

        result = await mock()
        assert result == expected_value

    def test_create_async_mock_with_exception_side_effect(self):
        """例外を発生させるAsyncMockの作成テスト"""
        test_exception = ValueError("test error")
        mock = AsyncMockManager.create_async_mock_with_side_effect(test_exception)

        assert isinstance(mock, AsyncMock)
        assert mock.side_effect == test_exception

    @pytest.mark.asyncio
    async def test_async_mock_with_exception_side_effect_execution(self):
        """例外を発生させるAsyncMockの実行テスト"""
        test_exception = ValueError("test error")
        mock = AsyncMockManager.create_async_mock_with_side_effect(test_exception)

        with pytest.raises(ValueError, match="test error"):
            await mock()

    def test_create_async_mock_with_list_side_effect(self):
        """リストのside_effectを持つAsyncMockの作成テスト"""
        values = ["value1", "value2", "value3"]
        mock = AsyncMockManager.create_async_mock_with_side_effect(values)

        assert isinstance(mock, AsyncMock)
        # side_effectがリストの場合、AsyncMockは内部でlist_iteratorを作成する
        assert hasattr(mock, "side_effect")

    @pytest.mark.asyncio
    async def test_async_mock_with_list_side_effect_execution(self):
        """リストのside_effectを持つAsyncMockの実行テスト"""
        values = ["value1", "value2", "value3"]
        mock = AsyncMockManager.create_async_mock_with_side_effect(values)

        # 順番に値が返されることを確認
        assert await mock() == "value1"
        assert await mock() == "value2"
        assert await mock() == "value3"

    @pytest.mark.asyncio
    async def test_async_iterator_mock(self):
        """非同期イテレータモックのテスト"""
        values = ["chunk1", "chunk2", "chunk3"]
        mock = AsyncMockManager.create_async_iterator_mock(values)

        result = []
        async for item in await mock():
            result.append(item)

        assert result == values

    @pytest.mark.asyncio
    async def test_async_context_manager_setup(self):
        """非同期コンテキストマネージャーのセットアップテスト"""
        mock = AsyncMock()
        return_value = "context_value"

        AsyncMockManager.setup_async_context_manager(mock, return_value)

        async with mock as ctx:
            assert ctx == return_value

    def test_create_coroutine_mock(self):
        """コルーチンモックの作成テスト"""
        return_value = "coroutine_result"
        mock = AsyncMockManager.create_coroutine_mock(return_value)

        assert isinstance(mock, Mock)
        assert asyncio.iscoroutine(mock.return_value)

    @pytest.mark.asyncio
    async def test_coroutine_mock_execution(self):
        """コルーチンモックの実行テスト"""
        return_value = "coroutine_result"
        mock = AsyncMockManager.create_coroutine_mock(return_value)

        result = await mock.return_value
        assert result == return_value


class TestAsyncMockStabilizer:
    """AsyncMockStabilizerのテスト"""

    @pytest.mark.asyncio
    async def test_fix_async_mock_side_effects_with_values(self):
        """値のリストでAsyncMockのside_effectを修正するテスト"""
        mock = AsyncMock()
        values = ["value1", "value2"]

        AsyncMockStabilizer.fix_async_mock_side_effects(mock, values)

        # 値が順番に返されることを確認
        assert await mock() == "value1"
        assert await mock() == "value2"
        # 最後の値が繰り返されることを確認
        assert await mock() == "value2"
        assert await mock() == "value2"

    @pytest.mark.asyncio
    async def test_fix_async_mock_side_effects_empty_list(self):
        """空のリストでAsyncMockのside_effectを修正するテスト"""
        mock = AsyncMock()
        values = []

        AsyncMockStabilizer.fix_async_mock_side_effects(mock, values)

        # 空のリストの場合はNoneが返されることを確認
        assert await mock() is None
        assert await mock() is None

    @pytest.mark.asyncio
    async def test_create_stable_async_stream(self):
        """安定した非同期ストリームの作成テスト"""
        chunks = ["chunk1", "chunk2", "chunk3"]
        mock = AsyncMockStabilizer.create_stable_async_stream(chunks)

        result = []
        async for chunk in await mock():
            result.append(chunk)

        assert result == chunks

    def test_ensure_async_mock_cleanup(self):
        """AsyncMockのクリーンアップテスト"""
        mock = AsyncMock()

        # クリーンアップが例外を発生させないことを確認
        AsyncMockStabilizer.ensure_async_mock_cleanup(mock)

        # コルーチンを持つモックのクリーンアップテスト
        async def test_coroutine():
            return "test"

        mock._mock_return_value = test_coroutine()
        AsyncMockStabilizer.ensure_async_mock_cleanup(mock)


class TestAsyncMockHelperFunctions:
    """非同期モックヘルパー関数のテスト"""

    @pytest.mark.asyncio
    async def test_setup_stable_async_mock_with_return_value(self):
        """戻り値でAsyncMockを安定化するテスト"""
        mock = AsyncMock()
        return_value = "stable_result"

        setup_stable_async_mock(mock, return_value=return_value)

        result = await mock()
        assert result == return_value

    @pytest.mark.asyncio
    async def test_setup_stable_async_mock_with_side_effect(self):
        """side_effectでAsyncMockを安定化するテスト"""
        mock = AsyncMock()
        side_effect = ["value1", "value2"]

        setup_stable_async_mock(mock, side_effect=side_effect)

        assert await mock() == "value1"
        assert await mock() == "value2"
        # 最後の値が繰り返されることを確認
        assert await mock() == "value2"

    @pytest.mark.asyncio
    async def test_create_async_mock_with_stable_behavior(self):
        """安定した動作を持つAsyncMockの作成テスト"""
        return_value = "stable_value"
        mock = create_async_mock_with_stable_behavior(return_value=return_value)

        result = await mock()
        assert result == return_value

    @pytest.mark.asyncio
    async def test_create_async_mock_with_context_manager(self):
        """コンテキストマネージャーとしてのAsyncMock作成テスト"""
        mock = create_async_mock_with_stable_behavior(return_value="context_result", is_context_manager=True)

        async with mock as ctx:
            assert ctx == mock

    @pytest.mark.asyncio
    async def test_patch_async_method_with_stable_mock(self):
        """非同期メソッドの安定したモックパッチテスト"""

        class TestClass:
            async def async_method(self):
                return "original"

        obj = TestClass()
        return_value = "mocked"

        mock = patch_async_method_with_stable_mock(obj, "async_method", return_value=return_value)

        result = await obj.async_method()
        assert result == return_value
        assert isinstance(mock, AsyncMock)


class TestAsyncMockIntegration:
    """非同期モックの統合テスト"""

    @pytest.mark.asyncio
    async def test_complex_async_mock_scenario(self):
        """複雑な非同期モックシナリオのテスト"""
        # 複数の非同期操作を含むシナリオ

        # 1. 戻り値を持つモック
        mock1 = create_async_mock_with_stable_behavior(return_value="result1")

        # 2. side_effectを持つモック
        mock2 = create_async_mock_with_stable_behavior(side_effect=["result2", "result3"])

        # 3. コンテキストマネージャーモック
        mock3 = create_async_mock_with_stable_behavior(return_value="context_result", is_context_manager=True)

        # すべてのモックが正常に動作することを確認
        assert await mock1() == "result1"
        assert await mock2() == "result2"
        assert await mock2() == "result3"
        assert await mock2() == "result3"  # 最後の値が繰り返される

        async with mock3 as ctx:
            assert ctx == mock3

    @pytest.mark.asyncio
    async def test_async_mock_error_handling(self):
        """非同期モックのエラーハンドリングテスト"""
        # 例外を発生させるモック
        test_exception = RuntimeError("async error")
        mock = create_async_mock_with_stable_behavior(side_effect=test_exception)

        with pytest.raises(RuntimeError, match="async error"):
            await mock()

    @pytest.mark.asyncio
    async def test_async_stream_mock_integration(self):
        """非同期ストリームモックの統合テスト"""
        chunks = ["start", "middle", "end"]
        stream_mock = AsyncMockStabilizer.create_stable_async_stream(chunks)

        collected_chunks = []
        async for chunk in await stream_mock():
            collected_chunks.append(chunk)

        assert collected_chunks == chunks
