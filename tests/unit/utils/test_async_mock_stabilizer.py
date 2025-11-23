"""
非同期モック安定化システムのテスト
"""

import asyncio

import pytest

from tests.utils.async_mock_stabilizer import (
    AsyncMockContextManager,
    AsyncMockErrorHandler,
    AsyncMockStabilizer,
    create_stable_async_mock_with_error_handling,
    ensure_async_mock_cleanup,
    get_async_mock_stabilizer,
    stable_async_test_context,
)


class TestAsyncMockContextManager:
    """AsyncMockContextManagerのテスト"""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """コンテキストマネージャーのライフサイクルテスト"""
        async with AsyncMockContextManager() as manager:
            # モックを作成して登録
            mock = manager.create_stable_async_mock("test_mock", return_value="test")

            # モックが正常に動作することを確認
            result = await mock()
            assert result == "test"

            # マネージャーにモックが登録されていることを確認
            assert "test_mock" in manager._active_mocks

        # コンテキスト終了後、クリーンアップが実行されることを確認
        # (実際のクリーンアップは内部的に行われる)

    @pytest.mark.asyncio
    async def test_cycling_side_effect(self):
        """循環するside_effectのテスト"""
        async with AsyncMockContextManager() as manager:
            values = ["first", "second", "third"]
            mock = manager.create_stable_async_mock("cycling_mock", side_effect=values)

            # 値が順番に返されることを確認
            assert await mock() == "first"
            assert await mock() == "second"
            assert await mock() == "third"

            # リストの最後に達した後も最後の値が返されることを確認
            assert await mock() == "third"
            assert await mock() == "third"

    @pytest.mark.asyncio
    async def test_exception_side_effect(self):
        """例外を含むside_effectのテスト"""
        async with AsyncMockContextManager() as manager:
            test_exception = ValueError("Test error")
            mock = manager.create_stable_async_mock("exception_mock", side_effect=test_exception)

            # 例外が正しく発生することを確認
            with pytest.raises(ValueError, match="Test error"):
                await mock()


class TestAsyncMockErrorHandler:
    """AsyncMockErrorHandlerのテスト"""

    @pytest.mark.asyncio
    async def test_error_propagating_mock(self):
        """エラー伝播モックのテスト"""
        handler = AsyncMockErrorHandler()

        mock = handler.create_error_propagating_mock(ValueError, "Test error message")

        with pytest.raises(ValueError, match="Test error message"):
            await mock()

    @pytest.mark.asyncio
    async def test_timeout_mock(self):
        """タイムアウトモックのテスト"""
        handler = AsyncMockErrorHandler()

        mock = handler.create_timeout_mock(timeout_seconds=0.01)

        with pytest.raises(asyncio.TimeoutError):
            await mock()

    @pytest.mark.asyncio
    async def test_network_error_mock(self):
        """ネットワークエラーモックのテスト"""
        handler = AsyncMockErrorHandler()

        mock = handler.create_network_error_mock("Network failure")

        # aiohttp.ClientConnectorErrorが発生することを確認
        with pytest.raises(Exception):  # aiohttp依存を避けるため汎用的にテスト
            await mock()


class TestAsyncMockStabilizer:
    """AsyncMockStabilizerのテスト"""

    @pytest.mark.asyncio
    async def test_stable_provider_mock(self):
        """安定したプロバイダーモックのテスト"""
        stabilizer = AsyncMockStabilizer()

        async with stabilizer.stable_async_context():
            provider_mock = stabilizer.create_stable_provider_mock(
                "test_provider", custom_method={"return_value": "custom_result"}
            )

            # 基本メソッドが設定されていることを確認
            assert hasattr(provider_mock, "cleanup")
            assert hasattr(provider_mock, "validate_connection")
            assert hasattr(provider_mock, "analyze")

            # 基本メソッドが正常に動作することを確認
            await provider_mock.cleanup()
            connection_result = await provider_mock.validate_connection()
            assert connection_result is True

            analysis_result = await provider_mock.analyze()
            assert analysis_result == {"analysis": "test result"}

            # カスタムメソッドが正常に動作することを確認
            custom_result = await provider_mock.custom_method()
            assert custom_result == "custom_result"

    @pytest.mark.asyncio
    async def test_stable_integration_mock(self):
        """安定した統合モックのテスト"""
        stabilizer = AsyncMockStabilizer()

        async with stabilizer.stable_async_context():
            integration_mock = stabilizer.create_stable_integration_mock("test_integration")

            # 統合メソッドが設定されていることを確認
            assert hasattr(integration_mock, "initialize")
            assert hasattr(integration_mock, "cleanup")
            assert hasattr(integration_mock, "analyze_log")
            assert hasattr(integration_mock, "providers")

            # メソッドが正常に動作することを確認
            await integration_mock.initialize()
            await integration_mock.cleanup()

            log_result = await integration_mock.analyze_log()
            assert log_result == {"analysis": "test result"}

            # プロバイダーが設定されていることを確認
            assert "openai" in integration_mock.providers
            assert "anthropic" in integration_mock.providers

    @pytest.mark.asyncio
    async def test_async_stream_mock(self):
        """非同期ストリームモックのテスト"""
        stabilizer = AsyncMockStabilizer()

        chunks = ["chunk1", "chunk2", "chunk3"]
        stream_mock = stabilizer.create_async_stream_mock(chunks, chunk_delay=0.001)

        # ストリームが正常に動作することを確認
        stream = await stream_mock()
        collected_chunks = []

        async for chunk in stream:
            collected_chunks.append(chunk)

        assert collected_chunks == chunks

    @pytest.mark.asyncio
    async def test_async_context_manager_mock(self):
        """非同期コンテキストマネージャーモックのテスト"""
        stabilizer = AsyncMockStabilizer()

        async with stabilizer.stable_async_context():
            context_mock = stabilizer.create_async_context_manager_mock(enter_value="entered", exit_value=None)

            # コンテキストマネージャーとして使用できることを確認
            async with context_mock as entered_value:
                assert entered_value == "entered"


class TestGlobalFunctions:
    """グローバル関数のテスト"""

    @pytest.mark.asyncio
    async def test_stable_async_test_context(self):
        """安定した非同期テストコンテキストのテスト"""
        async with stable_async_test_context() as context:
            # コンテキストが正常に取得できることを確認
            assert context is not None

            # モックを作成して動作確認
            mock = context.create_stable_async_mock("test", return_value="success")
            result = await mock()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_create_stable_async_mock_with_error_handling(self):
        """エラーハンドリング付き安定モック作成のテスト"""
        # 正常な戻り値のテスト
        mock = create_stable_async_mock_with_error_handling(return_value="test")
        result = await mock()
        assert result == "test"

        # 例外発生のテスト
        exception_mock = create_stable_async_mock_with_error_handling(exception_on_call=ValueError("Test exception"))

        with pytest.raises(ValueError, match="Test exception"):
            await exception_mock()

    @pytest.mark.asyncio
    @ensure_async_mock_cleanup
    async def test_ensure_async_mock_cleanup_decorator(self):
        """非同期モッククリーンアップデコレータのテスト"""
        # デコレータが正常に動作することを確認
        # (実際のクリーンアップは内部的に行われる)
        mock = create_stable_async_mock_with_error_handling(return_value="decorated")
        result = await mock()
        assert result == "decorated"


class TestAsyncMockStabilizerIntegration:
    """AsyncMockStabilizerの統合テスト"""

    @pytest.mark.asyncio
    async def test_complex_async_scenario(self):
        """複雑な非同期シナリオのテスト"""
        stabilizer = get_async_mock_stabilizer()

        async with stabilizer.stable_async_context():
            # 複数のモックを作成
            provider_mock = stabilizer.create_stable_provider_mock("complex_provider")
            integration_mock = stabilizer.create_stable_integration_mock(
                "complex_integration", providers={"complex": provider_mock}
            )

            # 複雑な相互作用をテスト
            await integration_mock.initialize()

            # プロバイダーのメソッドを呼び出し
            await integration_mock.providers["complex"].validate_connection()
            analysis_result = await integration_mock.providers["complex"].analyze()

            # 統合レベルの分析を実行
            log_analysis = await integration_mock.analyze_log()

            # 結果を検証
            assert analysis_result == {"analysis": "test result"}
            assert log_analysis == {"analysis": "test result"}

            # クリーンアップ
            await integration_mock.cleanup()
            await integration_mock.providers["complex"].cleanup()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """エラーハンドリング統合テスト"""
        stabilizer = get_async_mock_stabilizer()

        # エラーを発生させるモックを作成
        error_mock = stabilizer.error_handler.create_error_propagating_mock(RuntimeError, "Integration test error")

        # エラーが正しく伝播されることを確認
        with pytest.raises(RuntimeError, match="Integration test error"):
            await error_mock()

    @pytest.mark.asyncio
    async def test_side_effects_with_fallback(self):
        """フォールバック付きside_effectsのテスト"""
        stabilizer = get_async_mock_stabilizer()

        async with stabilizer.stable_async_context() as context:
            mock = context.create_stable_async_mock("fallback_test")

            # フォールバック付きでside_effectsを設定
            effects = ["first", "second", ValueError("error")]
            stabilizer.setup_async_side_effects_with_fallback(mock, effects, fallback_value="fallback")

            # 順番に効果が適用されることを確認
            assert await mock() == "first"
            assert await mock() == "second"

            # 例外が発生することを確認
            with pytest.raises(ValueError, match="error"):
                await mock()

            # フォールバック値が返されることを確認
            assert await mock() == "fallback"
            assert await mock() == "fallback"
