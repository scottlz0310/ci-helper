"""
非同期モック統合修正のテスト

実際のテストで発生する非同期モック問題の修正例を示します。
"""

from unittest.mock import Mock, patch

import pytest

from tests.utils.mock_helpers import (
    create_stable_provider_mock,
    fix_integration_mock_for_async_cleanup,
    setup_provider_mock_with_async_cleanup,
)


class TestAsyncMockIntegrationFixes:
    """非同期モック統合修正のテスト"""

    @pytest.mark.asyncio
    async def test_provider_mock_with_async_cleanup(self):
        """プロバイダーモックの非同期クリーンアップテスト"""
        # 通常のMockを作成
        provider_mock = Mock()

        # 非同期クリーンアップメソッドを追加
        setup_provider_mock_with_async_cleanup(provider_mock)

        # cleanup メソッドが AsyncMock として動作することを確認
        await provider_mock.cleanup()
        provider_mock.cleanup.assert_called_once()

        # その他の非同期メソッドも動作することを確認
        result = await provider_mock.validate_connection()
        assert result is True

        analysis_result = await provider_mock.analyze("test prompt")
        assert analysis_result == {}

    def test_create_stable_provider_mock(self):
        """安定したプロバイダーモックの作成テスト"""
        provider_mock = create_stable_provider_mock(name="test_provider", model="test_model")

        # 基本属性が設定されていることを確認
        assert provider_mock.name == "test_provider"
        assert provider_mock.model == "test_model"

        # 非同期メソッドが設定されていることを確認
        assert hasattr(provider_mock, "cleanup")
        assert hasattr(provider_mock, "validate_connection")
        assert hasattr(provider_mock, "analyze")

    @pytest.mark.asyncio
    async def test_integration_mock_async_cleanup_fix(self):
        """AIIntegrationモックの非同期クリーンアップ修正テスト"""
        # AIIntegrationのモックを作成
        integration_mock = Mock()

        # プロバイダーを追加
        provider1 = Mock()
        provider2 = Mock()
        integration_mock.providers = {"openai": provider1, "anthropic": provider2}

        # 非同期クリーンアップを修正
        fix_integration_mock_for_async_cleanup(integration_mock)

        # 各プロバイダーのクリーンアップが動作することを確認
        await provider1.cleanup()
        await provider2.cleanup()

        # 統合オブジェクト自体のクリーンアップも動作することを確認
        await integration_mock.cleanup()

        provider1.cleanup.assert_called_once()
        provider2.cleanup.assert_called_once()
        integration_mock.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_realistic_ai_integration_scenario(self):
        """現実的なAI統合シナリオのテスト"""
        # 実際のテストでよく使われるパターンをシミュレート

        with patch("src.ci_helper.ai.integration.AIIntegration") as mock_ai_class:
            # AIIntegrationのインスタンスモックを作成
            mock_ai_integration = Mock()

            # プロバイダーを設定
            openai_provider = create_stable_provider_mock(name="openai")
            anthropic_provider = create_stable_provider_mock(name="anthropic")

            mock_ai_integration.providers = {"openai": openai_provider, "anthropic": anthropic_provider}

            # 統合モックを修正
            fix_integration_mock_for_async_cleanup(mock_ai_integration)

            # AIIntegrationクラスがモックインスタンスを返すように設定
            mock_ai_class.return_value = mock_ai_integration

            # 実際の使用をシミュレート
            ai_integration = mock_ai_class()

            # プロバイダーのクリーンアップが正常に動作することを確認
            for provider in ai_integration.providers.values():
                await provider.cleanup()

            # 統合オブジェクトのクリーンアップも動作することを確認
            await ai_integration.cleanup()

            # すべてのクリーンアップが呼ばれたことを確認
            openai_provider.cleanup.assert_called_once()
            anthropic_provider.cleanup.assert_called_once()
            mock_ai_integration.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_mock_with_custom_async_methods(self):
        """カスタム非同期メソッドを持つプロバイダーモックのテスト"""
        provider_mock = create_stable_provider_mock()

        # カスタム非同期メソッドを追加
        from tests.utils.mock_helpers import AsyncMockManager

        provider_mock.custom_async_method = AsyncMockManager.create_async_mock_with_return_value("custom_result")

        # カスタムメソッドが動作することを確認
        result = await provider_mock.custom_async_method()
        assert result == "custom_result"

        # 標準的なクリーンアップも動作することを確認
        await provider_mock.cleanup()
        provider_mock.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_mock_error_handling_in_cleanup(self):
        """クリーンアップ中の非同期モックエラーハンドリングテスト"""
        provider_mock = create_stable_provider_mock()

        # クリーンアップ時に例外を発生させるように設定
        from tests.utils.mock_helpers import AsyncMockManager

        cleanup_error = RuntimeError("Cleanup failed")
        provider_mock.cleanup = AsyncMockManager.create_async_mock_with_side_effect(cleanup_error)

        # 例外が正しく発生することを確認
        with pytest.raises(RuntimeError, match="Cleanup failed"):
            await provider_mock.cleanup()

        provider_mock.cleanup.assert_called_once()
