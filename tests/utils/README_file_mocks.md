# ファイル操作モック安定化機能

このディレクトリには、テスト間でのファイル操作の一貫性を確保し、並行テスト実行時の競合状態を防ぐためのファイル操作モック安定化機能が含まれています。

## 主要コンポーネント

### 1. FileOperationMockStabilizer

`file_operation_mock_stabilizer.py` - メインの安定化クラス

- **機能**: ファイル操作のモックを一貫した動作に修正
- **対象**: `builtins.open`, `pathlib.Path`, `tempfile`, `shutil`
- **特徴**: スレッドセーフ、テスト間分離、包括的なファイルシステムモック

### 2. SimpleFileMockStabilizer

`simple_file_mock_stabilizer.py` - 軽量版の安定化クラス

- **機能**: 基本的なファイル操作モック
- **対象**: `builtins.open`, `tempfile`
- **特徴**: pytestの内部動作に干渉しない最小限の機能

### 3. ヘルパー関数

`file_mock_helpers.py` - 便利なヘルパー関数とテンプレート

- **機能**: 簡単にファイル操作モックを使用するためのユーティリティ
- **特徴**: よく使用されるファイルセット、デコレータ、コンテキストマネージャー

## 使用方法

### 基本的な使用方法

```python
from tests.utils.file_operation_mock_stabilizer import stable_file_mocks

def test_file_operations():
    with stable_file_mocks() as stabilizer:
        # ファイルを作成
        stabilizer.create_test_file("/test/file.txt", "content")
        
        # ファイルの存在確認
        assert stabilizer.mock_fs.file_exists("/test/file.txt")
        
        # ファイル内容の確認
        assert stabilizer.mock_fs.read_file("/test/file.txt") == "content"
```

### デコレータを使用した方法

```python
from tests.utils.file_operation_mock_stabilizer import with_stable_file_operations

@with_stable_file_operations(use_mock_fs=True)
def test_with_decorator():
    # ファイル操作が自動的に安定化される
    with open("/mock/test.txt", "w") as f:
        f.write("test content")
    
    with open("/mock/test.txt", "r") as f:
        content = f.read()
        assert content == "test content"
```

### フィクスチャを使用した方法

```python
def test_with_fixture(stable_file_operations):
    # conftest.pyで定義されたフィクスチャを使用
    stable_file_operations.create_test_file("/test/file.txt", "content")
    assert stable_file_operations.mock_fs.file_exists("/test/file.txt")
```

### ヘルパー関数を使用した方法

```python
from tests.utils.file_mock_helpers import mock_file_operations, COMMON_TEST_FILES

def test_with_helpers():
    with mock_file_operations(COMMON_TEST_FILES) as mocks:
        # 事前定義されたファイルセットを使用
        assert "ci-helper.toml" in mocks["files"]
        assert "package.json" in mocks["files"]
```

## 対応するファイル操作

### builtins.open

- 読み込みモード (`r`, `rb`)
- 書き込みモード (`w`, `wb`, `a`, `ab`)
- コンテキストマネージャー (`with` 文)

### pathlib.Path

- `mkdir()` - ディレクトリ作成
- `exists()` - 存在確認
- `is_file()` - ファイル判定
- `is_dir()` - ディレクトリ判定
- `read_text()` - テキスト読み込み
- `write_text()` - テキスト書き込み

### tempfile

- `mkdtemp()` - 一時ディレクトリ作成
- `NamedTemporaryFile()` - 一時ファイル作成
- `TemporaryDirectory()` - 一時ディレクトリコンテキスト

### shutil

- `rmtree()` - ディレクトリ削除
- `copy2()` - ファイルコピー

## 特徴

### テスト間分離

各テストは独立したファイルシステム状態を持ち、他のテストに影響しません。

```python
def test_isolation_1():
    with stable_file_mocks() as stabilizer:
        stabilizer.create_test_file("/shared/file.txt", "test1")
        # このファイルは他のテストには見えない

def test_isolation_2():
    with stable_file_mocks() as stabilizer:
        # 前のテストのファイルは存在しない
        assert not stabilizer.mock_fs.file_exists("/shared/file.txt")
```

### スレッドセーフティ

並行テスト実行時でも安全に動作します。

```python
def test_concurrent_operations():
    with stable_file_mocks() as stabilizer:
        def worker(thread_id):
            stabilizer.create_test_file(f"/test/file_{thread_id}.txt", f"content_{thread_id}")
        
        # 複数スレッドで同時実行
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
```

### エラー一貫性

実際のファイルシステムと同様のエラー動作を提供します。

```python
def test_error_consistency():
    with stable_file_mocks() as stabilizer:
        # 存在しないファイルの読み込み
        with pytest.raises(FileNotFoundError):
            stabilizer.mock_fs.read_file("/nonexistent/file.txt")
```

## 実世界のシナリオ例

### ログ管理システムのテスト

```python
def test_log_manager():
    with stable_file_mocks() as stabilizer:
        # ログディレクトリを作成
        log_dir = "/mock/logs"
        stabilizer.create_test_directory(log_dir)
        
        # LogManagerを初期化
        config = Mock()
        config.get_path.return_value = Path(log_dir)
        log_manager = LogManager(config)
        
        # ログを保存
        execution_result = create_sample_execution_result()
        log_path = log_manager.save_execution_log(execution_result, "log content")
        
        # ログファイルが作成されたことを確認
        assert stabilizer.mock_fs.file_exists(str(log_path))
```

### 設定ファイル管理のテスト

```python
def test_config_management():
    with stable_file_mocks() as stabilizer:
        # 設定ディレクトリを作成
        config_dir = "/mock/config"
        stabilizer.create_test_directory(config_dir)
        
        # デフォルト設定を作成
        default_config = f"{config_dir}/default.json"
        stabilizer.create_test_file(default_config, '{"key": "default_value"}')
        
        # ユーザー設定を作成
        user_config = f"{config_dir}/user.json"
        stabilizer.create_test_file(user_config, '{"key": "user_value"}')
        
        # 設定の読み込みと更新をテスト
        assert stabilizer.mock_fs.file_exists(default_config)
        assert stabilizer.mock_fs.file_exists(user_config)
```

## トラブルシューティング

### よくある問題

1. **PermissionError: Permission denied: '/mock'**
   - 原因: pathlibモックが設定されていない
   - 解決: `FileOperationMockStabilizer`を使用する

2. **AttributeError: **enter****
   - 原因: モックファイルオブジェクトのコンテキストマネージャーが正しく設定されていない
   - 解決: 最新版の安定化機能を使用する

3. **FileNotFoundError in concurrent tests**
   - 原因: 各スレッドが独立したモックコンテキストを使用している
   - 解決: 共有のモックコンテキストを使用する

### デバッグのヒント

```python
def test_debug_file_operations():
    with stable_file_mocks() as stabilizer:
        # ファイルシステムの状態を確認
        print("Files:", stabilizer.mock_fs.list_files())
        print("Directories:", stabilizer.mock_fs.directories)
        
        # ファイル操作をテスト
        stabilizer.create_test_file("/debug/test.txt", "debug content")
        print("File exists:", stabilizer.mock_fs.file_exists("/debug/test.txt"))
        print("File content:", stabilizer.mock_fs.read_file("/debug/test.txt"))
```

## 貢献

新しいファイル操作のサポートや機能改善の提案は歓迎します。テストを追加する際は、以下の点を考慮してください：

1. **テスト間分離**: 各テストが独立して実行できること
2. **スレッドセーフティ**: 並行実行時の安全性
3. **エラー一貫性**: 実際のファイルシステムと同様のエラー動作
4. **パフォーマンス**: テスト実行時間への影響を最小限に抑える

## 関連ファイル

- `tests/conftest.py` - グローバルフィクスチャ定義
- `tests/unit/utils/test_file_operation_mock_stabilizer.py` - 安定化機能のテスト
- `tests/unit/utils/test_file_operation_integration_example.py` - 統合例とテスト
