# モック戦略ベストプラクティス

## 概要

このドキュメントは、CI-Helperプロジェクトにおけるモック戦略のベストプラクティスを詳細に説明します。効果的なモックの使用により、テストの信頼性、実行速度、保守性を向上させることができます。

## モックの基本原則

### 1. モックすべきもの

**✅ モックすべき外部依存関係**:

- ファイルシステムI/O
- ネットワーク通信（API呼び出し）
- 時間依存の処理
- データベース操作
- 外部プロセス実行

**❌ モックすべきでないもの**:

- テスト対象のビジネスロジック
- 単純なデータ構造
- 標準ライブラリの基本機能（len, str等）

### 2. モック戦略の選択

```python
# 戦略1: unittest.mock.patch デコレータ
@patch('ci_helper.utils.config.load_config_file')
def test_config_loading(mock_load):
    mock_load.return_value = {"key": "value"}
    # テストロジック

# 戦略2: pytest fixture
@pytest.fixture
def mock_file_system(monkeypatch):
    def mock_exists(path):
        return path == "existing_file.toml"

    monkeypatch.setattr("pathlib.Path.exists", mock_exists)
    return mock_exists

# 戦略3: コンテキストマネージャー
def test_temporary_mock():
    with patch('time.time', return_value=1000):
        # 一時的なモック
        pass
```

## ファイルI/Oのモック

### 1. ファイル読み込みのモック

```python
from unittest.mock import mock_open, patch

def test_config_file_loading():
    """設定ファイル読み込みのモックテスト"""
    config_content = """
    [auto_fix]
    enabled = true
    confidence_threshold = 0.8
    """

    with patch('builtins.open', mock_open(read_data=config_content)):
        with patch('pathlib.Path.exists', return_value=True):
            config = AutoFixConfig()
            result = config.load_from_file("config.toml")

            assert result["auto_fix"]["enabled"] is True
            assert result["auto_fix"]["confidence_threshold"] == 0.8
```

### 2. ファイル書き込みのモック

```python
def test_settings_persistence():
    """設定永続化のモックテスト"""
    mock_file = mock_open()

    with patch('builtins.open', mock_file):
        with patch('pathlib.Path.mkdir'):
            manager = SettingsManager()
            manager.save_settings({"key": "value"})

            # ファイルが正しく開かれたことを確認
            mock_file.assert_called_once_with(
                manager.settings_file, 'w', encoding='utf-8'
            )

            # 書き込み内容を確認
            written_content = ''.join(
                call.args[0] for call in mock_file().write.call_args_list
            )
            assert '"key": "value"' in written_content
```

### 3. ディレクトリ操作のモック

```python
def test_cache_directory_creation():
    """キャッシュディレクトリ作成のモックテスト"""
    with patch('pathlib.Path.mkdir') as mock_mkdir:
        with patch('pathlib.Path.exists', return_value=False):
            cache = ResponseCache()
            cache.ensure_cache_directory()

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
```

## 時間依存処理のモック

### 1. 現在時刻のモック

```python
@patch('time.time')
def test_cache_expiration_timing(mock_time):
    """キャッシュ有効期限のタイミングテスト"""
    # 初期時刻: 2024-01-01 00:00:00
    mock_time.return_value = 1704067200

    cache = ResponseCache(ttl=300)  # 5分のTTL
    cache.set("key", "value")

    # 3分後: まだ有効
    mock_time.return_value = 1704067200 + 180
    assert cache.get("key") == "value"

    # 6分後: 期限切れ
    mock_time.return_value = 1704067200 + 360
    assert cache.get("key") is None
```

### 2. 日時処理のモック

```python
from datetime import datetime

@patch('ci_helper.utils.logger.datetime')
def test_log_timestamp_formatting(mock_datetime):
    """ログタイムスタンプフォーマットのテスト"""
    # 固定の日時を設定
    fixed_datetime = datetime(2024, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = fixed_datetime
    mock_datetime.strftime = datetime.strftime

    logger = Logger()
    log_entry = logger.create_log_entry("Test message")

    assert "2024-01-01 12:00:00" in log_entry
```

## ネットワーク通信のモック

### 1. HTTP APIのモック

```python
@patch('httpx.post')
def test_openai_api_call(mock_post):
    """OpenAI API呼び出しのモックテスト"""
    # APIレスポンスをモック
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Suggested fix: Add missing import"
            }
        }]
    }
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    provider = OpenAIProvider(api_key="test-key")
    result = provider.generate_response("Fix this error")

    assert "Add missing import" in result
    mock_post.assert_called_once()
```

### 2. 非同期HTTP呼び出しのモック

```python
@pytest.mark.asyncio
@patch('aiohttp.ClientSession.post')
async def test_async_api_call(mock_post):
    """非同期API呼び出しのモックテスト"""
    # 非同期レスポンスをモック
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"result": "success"})
    mock_response.status = 200

    mock_post.return_value.__aenter__.return_value = mock_response

    client = AsyncAPIClient()
    result = await client.make_request("test-endpoint")

    assert result["result"] == "success"
```

## 外部プロセスのモック

### 1. subprocess実行のモック

```python
@patch('subprocess.run')
def test_act_command_execution(mock_run):
    """actコマンド実行のモックテスト"""
    # 成功時のレスポンス
    mock_run.return_value = Mock(
        returncode=0,
        stdout="Job completed successfully",
        stderr=""
    )

    runner = ActRunner()
    result = runner.run_workflow("test.yml")

    assert result.success is True
    assert "completed successfully" in result.output

    # 実行されたコマンドを確認
    mock_run.assert_called_once()
    called_args = mock_run.call_args[0][0]
    assert "act" in called_args
    assert "test.yml" in called_args
```

### 2. 失敗ケースのモック

```python
@patch('subprocess.run')
def test_act_command_failure(mock_run):
    """actコマンド失敗のモックテスト"""
    # 失敗時のレスポンス
    mock_run.return_value = Mock(
        returncode=1,
        stdout="",
        stderr="Error: Workflow file not found"
    )

    runner = ActRunner()

    with pytest.raises(WorkflowExecutionError) as exc_info:
        runner.run_workflow("nonexistent.yml")

    assert "Workflow file not found" in str(exc_info.value)
```

## 複雑なオブジェクトのモック

### 1. クラスインスタンスのモック

```python
def test_pattern_manager_integration():
    """パターンマネージャー統合のモックテスト"""
    # PatternManagerのモック
    mock_manager = Mock(spec=CustomPatternManager)
    mock_manager.find_matches.return_value = [
        Mock(pattern_name="import_error", confidence=0.9),
        Mock(pattern_name="syntax_error", confidence=0.7)
    ]

    # FixGeneratorにモックを注入
    generator = FixGenerator(pattern_manager=mock_manager)
    result = generator.analyze_error("ImportError: missing module")

    assert len(result.matched_patterns) == 2
    assert result.matched_patterns[0].confidence == 0.9
```

### 2. 部分的なモック（spy）

```python
def test_cache_with_partial_mock():
    """キャッシュの部分的モックテスト"""
    cache = ResponseCache()

    # 特定のメソッドのみモック
    with patch.object(cache, '_serialize_key') as mock_serialize:
        mock_serialize.return_value = "mocked_key"

        cache.set("original_key", "value")

        # モックされたメソッドが呼ばれたことを確認
        mock_serialize.assert_called_once_with("original_key")

        # 実際のキャッシュ機能は動作することを確認
        assert cache.get("original_key") == "value"
```

## モックの検証パターン

### 1. 呼び出し回数の検証

```python
def test_api_retry_mechanism():
    """API再試行メカニズムのテスト"""
    with patch('httpx.post') as mock_post:
        # 最初の2回は失敗、3回目は成功
        mock_post.side_effect = [
            Mock(status_code=500),  # 1回目: サーバーエラー
            Mock(status_code=429),  # 2回目: レート制限
            Mock(status_code=200, json=lambda: {"result": "success"})  # 3回目: 成功
        ]

        client = APIClient(max_retries=3)
        result = client.make_request("test-endpoint")

        assert result["result"] == "success"
        assert mock_post.call_count == 3  # 3回呼び出されたことを確認
```

### 2. 引数の詳細検証

```python
def test_log_formatting_arguments():
    """ログフォーマット引数の詳細検証"""
    with patch('ci_helper.utils.logger.write_log') as mock_write:
        logger = Logger()
        logger.log_error("Test error", context={"file": "test.py", "line": 42})

        # 呼び出し引数の詳細検証
        mock_write.assert_called_once()
        call_args = mock_write.call_args

        assert call_args[0][0] == "ERROR"  # ログレベル
        assert "Test error" in call_args[0][1]  # メッセージ
        assert call_args[1]["context"]["file"] == "test.py"  # コンテキスト
```

## モックのトラブルシューティング

### 1. モックが効かない場合

```python
# 問題: インポートのタイミングでモックが効かない
# 悪い例
import ci_helper.utils.config  # この時点でモジュールが読み込まれる
from unittest.mock import patch

@patch('ci_helper.utils.config.load_file')  # 効かない
def test_config_loading(mock_load):
    pass

# 良い例
from unittest.mock import patch

@patch('ci_helper.utils.config.load_file')  # インポート前にパッチ
def test_config_loading(mock_load):
    import ci_helper.utils.config  # テスト内でインポート
    pass
```

### 2. モックの設定ミス

```python
def test_mock_configuration_issues():
    """モック設定の問題と解決方法"""

    # 問題1: return_valueとside_effectの混同
    with patch('some_function') as mock_func:
        # ❌ 間違い: 両方設定すると side_effect が優先される
        mock_func.return_value = "value"
        mock_func.side_effect = ["different_value"]

        # ✅ 正しい: どちらか一方を使用
        mock_func.return_value = "value"
        # または
        mock_func.side_effect = ["value1", "value2"]

    # 問題2: specの不適切な使用
    # ❌ 間違い: specなしでは存在しないメソッドも呼べてしまう
    mock_obj = Mock()
    mock_obj.nonexistent_method()  # エラーにならない

    # ✅ 正しい: specを使用して型安全性を確保
    mock_obj = Mock(spec=RealClass)
    # mock_obj.nonexistent_method()  # AttributeError が発生
```

## パフォーマンス考慮事項

### 1. モックの作成コスト

```python
# 重いモックは fixture で共有
@pytest.fixture(scope="session")
def expensive_mock():
    """セッション全体で共有される重いモック"""
    mock = Mock()
    # 複雑な設定...
    return mock

def test_with_shared_mock(expensive_mock):
    # 共有モックを使用
    pass
```

### 2. モックのリセット

```python
@pytest.fixture(autouse=True)
def reset_mocks():
    """各テスト後にモックをリセット"""
    yield
    # テスト後の処理
    Mock.reset_mock()
```

## まとめ

効果的なモック戦略により：

1. **テストの独立性**: 外部依存を排除し、テストを独立して実行可能
2. **実行速度の向上**: I/O操作やネットワーク通信を回避
3. **予測可能性**: 外部システムの状態に依存しない一貫した結果
4. **エラーケースのテスト**: 通常では再現困難な状況をシミュレート

このガイドラインに従って、適切なモック戦略を実装してください。
