# 非同期モック使用ガイド

このガイドでは、CI-Helperプロジェクトでの非同期モック問題を解決するためのユーティリティの使用方法を説明します。

## 問題の概要

CI-Helperプロジェクトのテストスイートでは、以下のような非同期モック関連の問題が発生していました：

1. **"object Mock can't be used in 'await' expression"** - 通常のMockオブジェクトを非同期コンテキストで使用
2. **StopIteration エラー** - AsyncMockのside_effectが適切に設定されていない
3. **未完了のコルーチン** - AsyncMockが返すコルーチンが適切に処理されていない

## 解決策

`tests/utils/mock_helpers.py` に以下のユーティリティクラスと関数を追加しました：

### 1. AsyncMockManager

非同期モックの作成と管理を担当するクラスです。

```python
from tests.utils.mock_helpers import AsyncMockManager

# 戻り値を持つAsyncMockを作成
mock = AsyncMockManager.create_async_mock_with_return_value("test_result")
result = await mock()  # "test_result"が返される

# 例外を発生させるAsyncMockを作成
error_mock = AsyncMockManager.create_async_mock_with_side_effect(ValueError("test error"))
# await error_mock()  # ValueError が発生

# 非同期イテレータのモックを作成
stream_mock = AsyncMockManager.create_async_iterator_mock(["chunk1", "chunk2"])
async for chunk in await stream_mock():
    print(chunk)  # "chunk1", "chunk2" が順番に出力
```

### 2. AsyncMockStabilizer

非同期モックの安定性を確保するためのユーティリティです。

```python
from tests.utils.mock_helpers import AsyncMockStabilizer

# AsyncMockのside_effectを安定化（StopIterationエラーを防ぐ）
mock = AsyncMock()
values = ["value1", "value2"]
AsyncMockStabilizer.fix_async_mock_side_effects(mock, values)

# 値が順番に返され、最後の値が繰り返される
assert await mock() == "value1"
assert await mock() == "value2"
assert await mock() == "value2"  # 最後の値が繰り返される
```

### 3. プロバイダーモック用ユーティリティ

AI プロバイダーのモックで発生する非同期クリーンアップ問題を解決します。

```python
from tests.utils.mock_helpers import (
    setup_provider_mock_with_async_cleanup,
    create_stable_provider_mock,
    fix_integration_mock_for_async_cleanup
)

# 通常のMockを非同期対応に変換
provider_mock = Mock()
setup_provider_mock_with_async_cleanup(provider_mock)
await provider_mock.cleanup()  # 正常に動作

# 最初から安定したプロバイダーモックを作成
stable_provider = create_stable_provider_mock(name="openai", model="gpt-4")
await stable_provider.cleanup()
await stable_provider.validate_connection()
```

## 実際の使用例

### テストでのプロバイダーモック修正

**修正前（問題のあるコード）:**

```python
@pytest.mark.asyncio
async def test_ai_integration():
    with patch("src.ci_helper.ai.integration.AIIntegration") as mock_ai_class:
        mock_ai_integration = Mock()
        mock_ai_integration.providers = {
            "openai": Mock(),  # 問題: 通常のMockを使用
            "anthropic": Mock()
        }
        mock_ai_class.return_value = mock_ai_integration
        
        ai_integration = mock_ai_class()
        # await ai_integration.cleanup()  # エラー: "object Mock can't be used in 'await' expression"
```

**修正後（正しいコード）:**

```python
from tests.utils.mock_helpers import create_stable_provider_mock, fix_integration_mock_for_async_cleanup

@pytest.mark.asyncio
async def test_ai_integration():
    with patch("src.ci_helper.ai.integration.AIIntegration") as mock_ai_class:
        mock_ai_integration = Mock()
        mock_ai_integration.providers = {
            "openai": create_stable_provider_mock(name="openai"),
            "anthropic": create_stable_provider_mock(name="anthropic")
        }
        
        # 統合モックを非同期対応に修正
        fix_integration_mock_for_async_cleanup(mock_ai_integration)
        mock_ai_class.return_value = mock_ai_integration
        
        ai_integration = mock_ai_class()
        await ai_integration.cleanup()  # 正常に動作
```

### AsyncMockのside_effect安定化

**修正前（StopIterationエラーが発生）:**

```python
mock = AsyncMock()
mock.side_effect = ["value1", "value2"]
# 3回目の呼び出しでStopIterationエラーが発生する可能性
```

**修正後（安定した動作）:**

```python
from tests.utils.mock_helpers import AsyncMockStabilizer

mock = AsyncMock()
values = ["value1", "value2"]
AsyncMockStabilizer.fix_async_mock_side_effects(mock, values)
# 何回呼び出しても最後の値が繰り返される
```

## ベストプラクティス

1. **プロバイダーモックには常に `create_stable_provider_mock` を使用**
2. **AIIntegrationモックには `fix_integration_mock_for_async_cleanup` を適用**
3. **AsyncMockのside_effectには `AsyncMockStabilizer.fix_async_mock_side_effects` を使用**
4. **非同期イテレータには `AsyncMockManager.create_async_iterator_mock` を使用**

## トラブルシューティング

### よくあるエラーと解決方法

1. **"object Mock can't be used in 'await' expression"**
   - 解決方法: `setup_provider_mock_with_async_cleanup()` を使用してMockを非同期対応に変換

2. **"StopIteration" エラー**
   - 解決方法: `AsyncMockStabilizer.fix_async_mock_side_effects()` を使用してside_effectを安定化

3. **"coroutine was never awaited" 警告**
   - 解決方法: `AsyncMockStabilizer.ensure_async_mock_cleanup()` を使用してクリーンアップ

## 参考

- `tests/unit/utils/test_async_mock_helpers.py` - 基本的な非同期モック機能のテスト
- `tests/unit/utils/test_async_mock_integration_fixes.py` - 統合修正のテスト例
