# WSLクラッシュ分析レポート

## 日時
2025-10-30 20:37頃

## 症状
pytestの実行中（30%進捗時点）にWSL全体がクラッシュし、再起動が必要になった。

## クラッシュ時の状況

### テスト進捗
- **完了**: 約640テスト / 2135テスト (30%)
- **実行時間**: 約1分58秒
- **クラッシュ箇所**: `tests/unit/ai/test_learning_engine.py::test_concurrent_learning_operations`

### システム状態
- **メモリ**: クラッシュ前に13GB / 23GB使用 (56%)
- **証拠**: dmesgに `system.journal corrupted or uncleanly shut down`

### ログファイル
- `test_logs/pytest_continue_20251030_203638.log` - 5031行で中断
- 853個のテスト結果（PASSED/FAILED/ERROR）を記録

## 根本原因

### 1. 非同期リソースリーク（主要原因）
**証拠:**
- ログ内に95個の `RuntimeError: Event loop is closed` エラー
- `Unclosed client session` 警告多数
- `AsyncClient.aclose()` の失敗

**問題コード箇所:**
```python
# httpx AsyncClient の不適切なクリーンアップ
RuntimeError: Event loop is closed
  File "httpx/_client.py", line 1985, in aclose
    await self._transport.aclose()
```

**影響:**
- 各テストで httpx セッションがリークし累積
- イベントループが閉じた後にクリーンアップを試行
- メモリとファイルディスクリプタが枯渇

### 2. 並行テストでのリソース競合
**クラッシュ直前のテスト:**
```
test_concurrent_learning_operations ERROR [ 30%]
```

このテストは複数の並行処理を実行し、リソースリークを加速させた可能性。

### 3. モックの不適切な使用
**証拠:**
```python
WARNING: プロバイダーのクリーンアップに失敗: object Mock can't be used in 'await' expression
```

モックオブジェクトが非同期関数として使用され、クリーンアップが失敗。

## 前回の実行との比較

### 最小限モード（成功）
- **設定**: `--maxfail=5` で5個失敗後に停止
- **結果**: 631 passed, 2 failed, 5 skipped, 3 errors
- **実行時間**: 63秒
- **メモリ**: 安定（3.9GB使用）
- **WSL**: クラッシュなし

### 全テスト継続モード（失敗）
- **設定**: 全テスト実行（エラーでも継続）
- **結果**: 30%で WSL クラッシュ
- **実行時間**: 約2分（クラッシュまで）
- **メモリ**: 13GB使用（56%）
- **WSL**: クラッシュ

**違いの理由:**
- 最小限モードは早期終了したため、リソースリークが限界に達しなかった
- 継続モードは30%まで進み、95個の非同期エラーが累積してシステムリソースを圧迫

## 修正が必要な箇所

### 優先度1: 非同期クリーンアップ

#### src/ci_helper/ai/integration.py
```python
async def cleanup(self):
    """AI統合システムのクリーンアップ"""
    # 問題: Mockオブジェクトをawaitしようとしている
    for provider in self.providers.values():
        await provider.cleanup()  # ← ここで失敗
```

**修正案:**
```python
async def cleanup(self):
    """AI統合システムのクリーンアップ"""
    for provider in self.providers.values():
        try:
            if hasattr(provider.cleanup, '__call__'):
                if asyncio.iscoroutinefunction(provider.cleanup):
                    await provider.cleanup()
                else:
                    provider.cleanup()
        except Exception as e:
            logger.warning(f"プロバイダーのクリーンアップに失敗: {e}")
```

#### httpx セッションのクリーンアップ

**問題箇所（推測）:**
```python
# OpenAI/Anthropic プロバイダーで httpx.AsyncClient が適切に閉じられていない
class OpenAIProvider:
    async def analyze(self, log_content):
        async with httpx.AsyncClient() as client:
            # ... 処理
            pass
        # イベントループが閉じた後にcloseが呼ばれる
```

**修正案:**
```python
class OpenAIProvider:
    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def cleanup(self):
        if self._client:
            await self._client.aclose()
            self._client = None
```

### 優先度2: テストのフィクスチャ修正

#### tests/conftest.py
```python
@pytest.fixture
async def async_ai_integration_with_cleanup(mock_config, mock_ai_config):
    integration = AIIntegration(mock_config)
    # ... setup

    # 問題: モックプロバイダーにAsyncMockが必要
    mock_provider.cleanup = AsyncMock()  # ← これが不足している

    try:
        yield integration
    finally:
        await integration.cleanup()  # ← 適切なクリーンアップ
```

### 優先度3: 並行テストの制限

#### pytest_minimal.ini
```ini
[pytest]
# 並行実行を完全に無効化
# -n オプションを削除
```

または

#### pyproject.toml
```toml
[tool.pytest.ini_options]
# 並行ワーカー数を制限
addopts = [
    "-n", "1",  # 並列数を1に制限
    # ...
]
```

## 推奨される対策

### 短期的対策（すぐ実装可能）

1. **特定のテストをスキップ**
   ```bash
   # 並行テストを除外
   uv run pytest -k "not concurrent" -v
   ```

2. **より低いワーカー数で実行**
   ```bash
   PYTEST_WORKERS=0 ./run_tests_safe.sh  # 並列なし
   ```

3. **テストを分割実行**
   ```bash
   # 統合テストを除外
   uv run pytest tests/unit -v

   # 統合テストのみ
   uv run pytest tests/integration -v
   ```

### 中期的対策（コード修正）

1. **非同期クリーンアップの修正**
   - すべてのプロバイダーの `cleanup()` メソッドを `AsyncMock` に
   - `httpx.AsyncClient` のライフサイクル管理を改善
   - イベントループのクローズ前に確実にクリーンアップ

2. **テストの分離強化**
   - 各テストで独立したイベントループを使用
   - `pytest-asyncio` の `asyncio_mode = "strict"` を検討
   - フィクスチャでのリソース管理を厳格化

3. **リソース監視の追加**
   - メモリ使用量の閾値を設定
   - ファイルディスクリプタ数を監視
   - 異常検知時に早期終了

### 長期的対策（アーキテクチャ改善）

1. **非同期セッションの一元管理**
   ```python
   # シングルトンパターンでセッション管理
   class SessionManager:
       _instance = None
       _client = None

       @classmethod
       async def get_client(cls):
           if cls._client is None:
               cls._client = httpx.AsyncClient()
           return cls._client

       @classmethod
       async def cleanup(cls):
           if cls._client:
               await cls._client.aclose()
               cls._client = None
   ```

2. **Context Manager の活用**
   ```python
   async with AIIntegration(config) as integration:
       result = await integration.analyze(log)
   # 自動的にクリーンアップ
   ```

3. **リソースプールの導入**
   - セッションを使い回す
   - 同時接続数を制限
   - タイムアウトを適切に設定

## テスト実行ガイドライン

### 安全な実行方法（WSLクラッシュ回避）

1. **単一プロセスで実行**
   ```bash
   ./run_tests_minimal.sh
   ```

2. **テストを分割**
   ```bash
   # ユニットテストのみ
   uv run pytest tests/unit -v --log-cli-level=INFO

   # 統合テストのみ（注意して実行）
   uv run pytest tests/integration -v --log-cli-level=INFO --maxfail=3
   ```

3. **問題のテストを特定**
   ```bash
   # learning_engine以外を実行
   uv run pytest -v --ignore=tests/unit/ai/test_learning_engine.py

   # learning_engineのみを実行（注意）
   uv run pytest tests/unit/ai/test_learning_engine.py -v --maxfail=1
   ```

4. **リソース監視しながら実行**
   ```bash
   # 別ターミナルで監視
   watch -n 1 'free -h && echo "" && ps aux | grep pytest | wc -l'

   # メインターミナルでテスト実行
   ./run_tests_safe.sh
   ```

### 避けるべき操作

1. ❌ 全テスト並列実行（WSLクラッシュのリスク大）
2. ❌ `test_concurrent_*` テストの連続実行
3. ❌ メモリ監視なしでの長時間実行
4. ❌ カバレッジ + 並列実行の組み合わせ

## 関連ファイル

### ログファイル
- `test_logs/pytest_continue_20251030_203638.log` - クラッシュ時のログ
- `test_logs/pytest_minimal_20251030_203206.log` - 成功時のログ（比較用）

### 設定ファイル
- `pytest_minimal.ini` - 最小限設定
- `pyproject.toml` - デフォルト設定
- `run_tests_continue.sh` - 全テスト実行スクリプト
- `run_tests_minimal.sh` - 安全な実行スクリプト

### 問題のあるテストファイル
- `tests/unit/ai/test_learning_engine.py` - クラッシュ箇所
- `tests/integration/test_ai_*.py` - 非同期エラー多発

### 修正が必要なソースファイル
- `src/ci_helper/ai/integration.py` - クリーンアップロジック
- `src/ci_helper/ai/providers/*.py` - 各プロバイダーのセッション管理
- `tests/conftest.py` - フィクスチャの非同期対応

## 次のステップ

1. ✅ WSLクラッシュの原因を特定（完了）
2. ⬜ 非同期クリーンアップコードを修正
3. ⬜ テストフィクスチャを修正
4. ⬜ 並行テストを制限または修正
5. ⬜ 修正後に段階的にテスト実行
6. ⬜ 全テストが安全に実行できることを確認

## 参考情報

### エラーメッセージの例
```
RuntimeError: Event loop is closed
  at asyncio/base_events.py:556, in _check_closed
```

### システムログ
```
system.journal corrupted or uncleanly shut down, renaming and replacing
```

### メモリ使用推移
- 開始時: 3.9GB / 23GB (17%)
- 10%時点: 8GB / 23GB (35%)（推測）
- 30%時点: 13GB / 23GB (56%)
- クラッシュ: メモリまたはFD枯渇

---

**作成日**: 2025-10-30
**作成者**: Claude Code
**ステータス**: 調査完了、修正待ち
