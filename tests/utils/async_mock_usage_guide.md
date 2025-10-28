# 非同期モック安定化システム使用ガイド

## 概要

非同期モック安定化システムは、非同期コンテキストでのモック動作を安定化し、AsyncMockの適切な設定と管理を提供します。

## 主な問題と解決策

### よくある問題

1. **"object Mock can't be used in 'await' expression"** - 通常のMockオブジェクトを非同期コンテキストで使用
2. **StopIteration エラー** - AsyncMockのside_effectが適切に設定されていない
3. **未完了のコルーチン** - AsyncMockが返すコルーチンが適切に処理されていない
4. **エラー伝播の問題** - 例外が期待通りに伝播されない

### 解決策

新しい非同期モック安定化システムを使用することで、これらの問題を自動的に解決できます。

## 基本的な使用方法

### 1. 安定したAsyncMockの作成

```python
from tests.utils.async_mock_stabilizer import create_stable_async_mock_with_error_handling

# 基本的なAsyncMock
mock = create_stable_async_mock_with_error_handling(return_value="test_result")
result = await mock()  # "test_result"

# 例外を発生させるAsyncMock
error_mock = create_stable_async_mock_with_error_handling(
    exception_on_call=ValueError("test error")
)
# await error_mock()  # ValueError が発生
```

### 2. 安定したテストコンテキスト

```python
from tests.utils.async_mock_stabilizer import stable_async_test_context

@pytest.mark.asyncio
async def test_with_stable_context():
    async with stable_async_test_context() as context:
        mock = context.create_stable_async_mock("test_mock", return_value="success")
        result = await mock()
        assert result == "success"
```

### 3. デコレータを使用したクリーンアップ

```python
from tests.utils.async_mock_stabilizer import ensure_async_mock_cleanup

@pytest.mark.asyncio
@ensure_async_mock_cleanup
async def test_with_automatic_cleanup():
    # テスト終了時に自動的にクリーンアップされる
    mock = create_stable_async_mock_with_error_handling(return_value="test")
    result = await mock()
    assert result == "test"
```

## 高度な使用方法

### 1. プロバイダーモックの作成

```python
from tests.utils.async_mock_stabilizer import create_stable_provider_mock

provider_mock = create_stable_provider_mock(
    "openai_provider",
    custom_analyze={"return_value": {"result": "analysis"}},
    custom_stream={"side_effect": ["chunk1", "chunk2"]}
)

# 基本メソッドが自動的に設定される
await provider_mock.cleanup()
connection_ok = await provider_mock.validate_connection()
analysis = await provider_mock.analyze()

# カスタムメソッドも使用可能
custom_result = await provider_mock.custom_analyze()
```

### 2. 統合モックの作成

```python
from tests.utils.async_mock_stabilizer import create_stable_integration_mock

integration_mock = create_stable_integration_mock(
    "ai_integration",
    providers={
        "openai": create_stable_provider_mock("openai"),
        "anthropic": create_stable_provider_mock("anthropic")
    }
)

await integration_mock.initialize()
result = await integration_mock.analyze_log("test log")
await integration_mock.cleanup()
```

### 3. エラーハンドリング付きパッチ

```python
from tests.utils.async_mock_stabilizer import patch_with_stable_async_mock

# TimeoutErrorを発生させるパッチ
with patch_with_stable_async_mock(
    "src.ci_helper.ai.providers.openai.AsyncOpenAI.chat.completions.create",
    exception_on_call=TimeoutError("Request timeout")
):
    # テストコード
    with pytest.raises(TimeoutError):
        await some_async_function()
```

### 4. 非同期ストリームモック

```python
from tests.utils.async_mock_stabilizer import create_async_stream_mock

chunks = ["chunk1", "chunk2", "chunk3"]
stream_mock = create_async_stream_mock(chunks, chunk_delay=0.01)

stream = await stream_mock()
collected = []
async for chunk in stream:
    collected.append(chunk)

assert collected == chunks
```

## 統合例

### AI統合テストの例

```python
import pytest
from tests.utils.async_mock_stabilizer import (
    get_async_mock_stabilizer,
    stable_async_test_context
)

class TestAIIntegrationWithStabilizer:
    
    @pytest.mark.asyncio
    async def test_ai_analysis_with_timeout_error(self):
        """タイムアウトエラーのテスト"""
        stabilizer = get_async_mock_stabilizer()
        
        async with stabilizer.stable_async_context() as context:
            # エラーを発生させるプロバイダーモックを作成
            provider_mock = stabilizer.create_stable_provider_mock(
                "openai_provider",
                analyze={"side_effect": TimeoutError("Request timeout")}
            )
            
            integration_mock = stabilizer.create_stable_integration_mock(
                "ai_integration",
                providers={"openai": provider_mock}
            )
            
            # タイムアウトエラーが正しく伝播されることを確認
            with pytest.raises(TimeoutError, match="Request timeout"):
                await integration_mock.providers["openai"].analyze()

    @pytest.mark.asyncio
    async def test_complex_async_workflow(self):
        """複雑な非同期ワークフローのテスト"""
        async with stable_async_test_context() as context:
            # 複数のモックを作成
            provider1 = context.create_stable_async_mock(
                "provider1_analyze", 
                return_value={"result": "analysis1"}
            )
            provider2 = context.create_stable_async_mock(
                "provider2_analyze",
                return_value={"result": "analysis2"}
            )
            
            # 順次実行
            result1 = await provider1()
            result2 = await provider2()
            
            # 結果を検証
            assert result1["result"] == "analysis1"
            assert result2["result"] == "analysis2"
```

## ベストプラクティス

### 1. 常にコンテキストマネージャーを使用

```python
# ✅ 推奨
async with stable_async_test_context() as context:
    mock = context.create_stable_async_mock("test", return_value="value")
    # テストコード

# ❌ 非推奨（クリーンアップが自動実行されない）
mock = create_stable_async_mock_with_error_handling(return_value="value")
```

### 2. 適切なエラーハンドリング

```python
# ✅ 推奨 - 具体的な例外を指定
mock = create_stable_async_mock_with_error_handling(
    exception_on_call=TimeoutError("Specific timeout message")
)

# ❌ 非推奨 - 汎用的すぎる例外
mock = create_stable_async_mock_with_error_handling(
    exception_on_call=Exception("Generic error")
)
```

### 3. side_effectsの適切な設定

```python
# ✅ 推奨 - 循環する値のリスト
stabilizer.setup_async_side_effects_with_fallback(
    mock, 
    effects=["first", "second", ValueError("error")],
    fallback_value="fallback"
)

# ❌ 非推奨 - 空のリスト（StopIterationの原因）
mock.side_effect = []
```

## トラブルシューティング

### よくあるエラーと対処法

1. **"RuntimeError: coroutine was never awaited"**
   - 解決策: `ensure_async_mock_cleanup`デコレータを使用

2. **"StopIteration"エラー**
   - 解決策: `setup_async_side_effects_with_fallback`を使用

3. **"Mock object has no attribute '**aenter**'"**
   - 解決策: `create_async_context_manager_mock`を使用

### デバッグのヒント

```python
# モックの状態を確認
from tests.utils.async_mock_stabilizer import AsyncMockValidator

validator = AsyncMockValidator()
validator.validate_async_mock_calls(mock, expected_calls=3)
validator.validate_async_mock_side_effects(mock)
validator.validate_async_context_manager(mock)
```

## 移行ガイド

### 既存のAsyncMockから移行

```python
# 旧方式
mock = AsyncMock()
mock.return_value = "test"
mock.side_effect = [ValueError("error")]

# 新方式
mock = create_stable_async_mock_with_error_handling(
    return_value="test",
    side_effect=[ValueError("error")]
)
```

### 既存のテストの更新

1. `@ensure_async_mock_cleanup`デコレータを追加
2. `stable_async_test_context`でテストをラップ
3. エラー発生モックを`create_stable_async_mock_with_error_handling`に置き換え

この安定化システムを使用することで、非同期テストの信頼性と保守性が大幅に向上します。
