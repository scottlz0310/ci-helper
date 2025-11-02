# ファイル操作モック安定化機能 使用ガイド

## 概要

ファイル操作モック安定化機能は、テスト間でのファイル状態の分離とファイル操作モックの一貫した動作を提供します。並行テスト実行時の競合状態を防ぎ、テストの再現性を確保します。

## 主な機能

### 1. ファイル状態の分離

- テスト間でファイルシステム状態が完全に分離される
- 並行テスト実行時の競合状態を防止
- テストの独立性と再現性を保証

### 2. 一貫したモック動作

- ファイル操作のモックが予測可能に動作
- エラーハンドリングの一貫性を確保
- 実際のファイルシステムとの動作の整合性

### 3. 簡単な使用方法

- コンテキストマネージャー、デコレータ、フィクスチャで利用可能
- 既存のテストコードへの統合が容易
- 最小限のコード変更で導入可能

## 使用方法

### 1. コンテキストマネージャーを使用

```python
from tests.utils.file_operation_mock_stabilizer import stable_file_mocks

def test_with_stable_mocks():
    with stable_file_mocks() as stabilizer:
        # ファイルを作成
        stabilizer.create_test_file("/test/file.txt", "test content")

        # ファイル存在確認
        assert stabilizer.mock_fs.file_exists("/test/file.txt")

        # ファイル内容確認
        assert stabilizer.mock_fs.read_file("/test/file.txt") == "test content"
```

### 2. デコレータを使用

```python
from tests.utils.file_operation_mock_stabilizer import with_stable_file_operations

@with_stable_file_operations(use_mock_fs=True)
def test_with_decorator():
    # デコレータによりファイル操作が安定化されている
    # 通常のファイル操作コードをテスト
    pass
```

### 3. フィクスチャを使用

```python
def test_with_fixture(stable_file_operations):
    # フィクスチャによりファイル操作が安定化されている
    stable_file_operations.create_test_file("/test/file.txt", "content")
    assert stable_file_operations.mock_fs.file_exists("/test/file.txt")
```

### 4. 分離されたファイルシステム

```python
from tests.utils.file_operation_mock_stabilizer import isolated_file_system

def test_with_isolated_filesystem():
    with isolated_file_system(use_real_temp_dir=True) as temp_dir:
        # 実際の一時ディレクトリを使用
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        assert test_file.exists()
    # コンテキスト終了後は自動的にクリーンアップされる
```

## 実用例

### ログ管理テストの改善

**従来の方法（問題あり）:**

```python
def test_log_operations():
    # 実際のファイルシステムを使用（テスト間で状態が共有される可能性）
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"
        log_file.write_text("log content")
        # テスト間での競合やクリーンアップの問題が発生する可能性
```

**改善された方法:**

```python
def test_log_operations():
    with stable_file_mocks() as stabilizer:
        # 完全に分離されたファイルシステム
        stabilizer.create_test_file("/logs/test.log", "log content")
        assert stabilizer.mock_fs.file_exists("/logs/test.log")
        # テスト終了後は自動的にクリーンアップ、他のテストに影響なし
```

### 並行テストでの安全性

```python
def test_concurrent_file_operations():
    with stable_file_mocks() as stabilizer:
        results = []
        errors = []

        def file_operation(thread_id):
            try:
                # スレッドセーフなファイル操作
                file_path = f"/test/file_{thread_id}.txt"
                stabilizer.create_test_file(file_path, f"content_{thread_id}")

                if stabilizer.mock_fs.file_exists(file_path):
                    results.append(thread_id)
            except Exception as e:
                errors.append(e)

        # 複数スレッドで並行実行
        threads = []
        for i in range(5):
            thread = threading.Thread(target=file_operation, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # エラーが発生しないことを確認
        assert len(errors) == 0
        assert len(results) == 5
```

### エラーハンドリングの一貫性

```python
def test_error_handling():
    with stable_file_mocks() as stabilizer:
        # 存在しないファイルへのアクセスは一貫してエラーになる
        with pytest.raises(FileNotFoundError):
            stabilizer.mock_fs.read_file("/nonexistent/file.txt")

        with pytest.raises(FileNotFoundError):
            stabilizer.mock_fs.write_file("/nonexistent/file.txt", "content")

        with pytest.raises(FileNotFoundError):
            stabilizer.mock_fs.delete_file("/nonexistent/file.txt")
```

## 既存テストの移行

### 1. tempfileを使用しているテストの移行

**移行前:**

```python
import tempfile
from pathlib import Path

def test_file_operations():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.txt"
        test_file.write_text("content")
        assert test_file.exists()
```

**移行後:**

```python
from tests.utils.file_operation_mock_stabilizer import stable_file_mocks

def test_file_operations():
    with stable_file_mocks() as stabilizer:
        stabilizer.create_test_file("/test/test.txt", "content")
        assert stabilizer.mock_fs.file_exists("/test/test.txt")
```

### 2. patch("builtins.open")を使用しているテストの移行

**移行前:**

```python
from unittest.mock import patch, mock_open

def test_file_reading():
    mock_file_content = "test content"
    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # ファイル読み込みテスト
        pass
```

**移行後:**

```python
from tests.utils.file_operation_mock_stabilizer import stable_file_mocks

def test_file_reading():
    with stable_file_mocks() as stabilizer:
        stabilizer.create_test_file("/test/file.txt", "test content")
        # ファイル読み込みテストが自動的に安定化される
        assert stabilizer.mock_fs.read_file("/test/file.txt") == "test content"
```

## ベストプラクティス

### 1. 適切なコンテキストの選択

- **実際のファイルが必要な場合**: `isolated_file_system(use_real_temp_dir=True)`
- **モックで十分な場合**: `stable_file_mocks()`
- **既存コードの最小変更**: デコレータまたはフィクスチャを使用

### 2. テスト分離の確保

```python
# 良い例: 各テストで独立したコンテキスト
def test_operation_1():
    with stable_file_mocks() as stabilizer:
        stabilizer.create_test_file("/test/file.txt", "content1")
        # テスト1の処理

def test_operation_2():
    with stable_file_mocks() as stabilizer:
        # test_operation_1のファイルは存在しない（完全に分離）
        stabilizer.create_test_file("/test/file.txt", "content2")
        # テスト2の処理
```

### 3. エラーテストの実装

```python
def test_permission_error():
    with stable_file_mocks() as stabilizer:
        # 権限エラーをシミュレート
        with patch.object(stabilizer.mock_fs, 'read_file',
                         side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                stabilizer.mock_fs.read_file("/protected/file.txt")
```

## トラブルシューティング

### 1. モックが期待通りに動作しない

**問題**: ファイル操作のモックが期待通りに動作しない

**解決策**:

- `stable_file_mocks()`コンテキスト内でファイルを事前に作成
- `stabilizer.create_test_file()`を使用してファイルを作成

### 2. テスト間でファイル状態が共有される

**問題**: テスト間でファイル状態が共有されてしまう

**解決策**:

- 各テストで独立した`stable_file_mocks()`コンテキストを使用
- グローバルな状態を避け、テストごとに新しいスタビライザーを作成

### 3. 並行テスト実行時の競合

**問題**: 並行テスト実行時にファイル操作で競合が発生

**解決策**:

- `stable_file_mocks()`を使用してモックファイルシステムを利用
- 実際のファイルシステムを使用する場合は`isolated_file_system()`を使用

## パフォーマンス考慮事項

### 1. モックファイルシステム vs 実際のファイルシステム

- **モックファイルシステム**: 高速、メモリ使用量少、完全な分離
- **実際のファイルシステム**: 実際の動作に近い、I/O操作のテストが可能

### 2. 大量のファイル操作

```python
def test_large_file_operations():
    with stable_file_mocks() as stabilizer:
        # 大量のファイル操作でもメモリ効率的
        for i in range(1000):
            stabilizer.create_test_file(f"/test/file_{i}.txt", f"content_{i}")

        # すべてのファイルが正しく作成されることを確認
        assert len(stabilizer.mock_fs.list_files()) == 1000
```

## まとめ

ファイル操作モック安定化機能を使用することで：

1. **テストの信頼性向上**: ファイル操作の一貫性とテスト間の分離を確保
2. **並行実行の安全性**: 並行テスト実行時の競合状態を防止
3. **開発効率の向上**: 簡単な導入と最小限のコード変更
4. **保守性の向上**: 予測可能なテスト動作と明確なエラーハンドリング

既存のテストコードを段階的に移行し、新しいテストでは積極的に活用することを推奨します。
