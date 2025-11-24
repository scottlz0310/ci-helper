"""
pytest設定と共有フィクスチャ

このファイルは全テストで共有されるフィクスチャとpytest設定を提供します。
テストの独立性と再現性を確保するため、適切なモックとテストデータを提供します。
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

import pytest
from ci_helper.utils.config import Config


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    テスト環境のセットアップ

    並列テスト実行時のリソース競合を防ぐため、テスト環境を適切に設定します。
    セッション開始時に一度だけ実行され、全テストで共有されます。
    """
    import os
    import tempfile

    # テスト専用の一時ディレクトリを設定
    original_tmpdir = os.environ.get("TMPDIR")
    test_tmpdir = tempfile.mkdtemp(prefix="ci_helper_test_session_")
    os.environ["TMPDIR"] = test_tmpdir

    # テスト用の環境変数を設定
    os.environ["CI_HELPER_TEST_MODE"] = "1"
    os.environ["CI_HELPER_LOG_LEVEL"] = "WARNING"

    yield

    # クリーンアップ
    if original_tmpdir:
        os.environ["TMPDIR"] = original_tmpdir
    else:
        os.environ.pop("TMPDIR", None)
    os.environ.pop("CI_HELPER_TEST_MODE", None)
    os.environ.pop("CI_HELPER_LOG_LEVEL", None)

    # テスト用一時ディレクトリをクリーンアップ
    import shutil

    try:
        shutil.rmtree(test_tmpdir, ignore_errors=True)
    except Exception:
        pass  # クリーンアップエラーは無視


@pytest.fixture
def isolated_test_resources(monkeypatch):
    """
    テストリソースの分離（オプション）

    並列テスト実行時にリソース競合が発生する可能性があるテストで使用します。
    このフィクスチャを明示的に使用するテストのみが分離されます。
    """
    import os
    import uuid

    # テスト固有の識別子を生成
    test_id = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"

    # 環境変数でテスト識別子を設定
    monkeypatch.setenv("CI_HELPER_TEST_ID", test_id)

    # ログファイルの競合を避けるため、テスト固有のログディレクトリを設定
    monkeypatch.setenv("CI_HELPER_LOG_DIR", f".ci-helper-test-{test_id}/logs")

    # キャッシュディレクトリの競合を避ける
    monkeypatch.setenv("CI_HELPER_CACHE_DIR", f".ci-helper-test-{test_id}/cache")

    yield test_id

    # テスト終了後のクリーンアップ
    import shutil

    for cleanup_dir in [f".ci-helper-test-{test_id}"]:
        try:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
        except Exception:
            pass  # クリーンアップエラーは無視


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    一時ディレクトリを提供するフィクスチャ

    テスト実行時に一時的なディレクトリを作成し、テスト終了後に自動的にクリーンアップします。
    ファイル操作のテストで使用され、テスト間の独立性を保証します。
    並列テスト実行時の競合を避けるため、プロセス固有の一意なディレクトリを作成します。

    Returns:
        Path: 一時ディレクトリのパス
    """
    import os
    import uuid

    # 並列テスト実行時の競合を避けるため、プロセス固有の一意なディレクトリを作成
    unique_suffix = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    with TemporaryDirectory(prefix=f"ci_helper_test_{unique_suffix}_") as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def stable_file_operations():
    """
    安定したファイル操作環境を提供するフィクスチャ

    ファイル操作のモックを一貫した動作に修正し、テスト間での状態分離を確保します。
    並行テスト実行時の競合状態を防ぎ、テストの再現性を確保します。

    Returns:
        FileOperationMockStabilizer: 設定済みのファイル操作スタビライザー
    """
    from tests.utils.file_operation_mock_stabilizer import FileOperationMockStabilizer

    stabilizer = FileOperationMockStabilizer()
    try:
        stabilizer.setup_all_mocks()
        yield stabilizer
    finally:
        stabilizer.cleanup_mocks()


@pytest.fixture
def isolated_filesystem():
    """
    分離されたファイルシステム環境を提供するフィクスチャ

    実際のファイルシステムに影響を与えずにファイル操作をテストできる
    分離された環境を提供します。

    Returns:
        Path: 分離されたファイルシステムのルートパス
    """
    from tests.utils.file_operation_mock_stabilizer import isolated_file_system

    with isolated_file_system(use_real_temp_dir=True) as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_config(temp_dir: Path) -> Config:
    """
    テスト用の設定を提供するフィクスチャ

    一時ディレクトリをプロジェクトルートとする設定オブジェクトを作成します。
    設定関連のテストで使用され、実際の設定ファイルに影響を与えません。

    Args:
        temp_dir: 一時ディレクトリのパス

    Returns:
        Config: テスト用設定オブジェクト
    """
    return Config(project_root=temp_dir)


@pytest.fixture
def sample_workflow_dir(temp_dir: Path) -> Path:
    """
    サンプルワークフローディレクトリを作成するフィクスチャ

    GitHub Actionsワークフローファイルを含むディレクトリ構造を作成します。
    CI/CD関連のテストで使用され、実際のワークフローファイルの構造を模擬します。

    Args:
        temp_dir: 一時ディレクトリのパス

    Returns:
        Path: ワークフローディレクトリのパス
    """
    workflow_dir = temp_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)

    # サンプルワークフローファイルを作成
    sample_workflow = workflow_dir / "test.yml"
    sample_workflow.write_text("""
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Running tests"
""")

    return workflow_dir


# AI関連のフィクスチャ


@pytest.fixture
def mock_ai_config():
    """
    AI設定のモック

    AI機能のテストで使用する標準的な設定オブジェクトを提供します。
    実際のAPIキーを使用せず、テスト環境で安全に実行できます。

    Returns:
        AIConfig: テスト用AI設定オブジェクト
    """
    from src.ci_helper.ai.models import AIConfig, ProviderConfig

    return AIConfig(
        default_provider="openai",
        providers={
            "openai": ProviderConfig(
                name="openai",
                api_key="sk-test-key",
                default_model="gpt-4o",
                available_models=["gpt-4o", "gpt-4o-mini"],
                timeout_seconds=30,
                max_retries=3,
            )
        },
        cache_enabled=True,
        cache_ttl_hours=24,
        cache_max_size_mb=100,
        cost_limits={"monthly_usd": 50.0, "per_request_usd": 1.0},
        interactive_timeout=300,
        streaming_enabled=True,
        security_checks_enabled=True,
        cache_dir=".ci-helper/cache",
    )


@pytest.fixture
def mock_openai_response():
    """OpenAI APIレスポンスのモック"""
    from tests.fixtures.ai_responses import MOCK_OPENAI_RESPONSE

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = MOCK_OPENAI_RESPONSE["choices"][0]["message"]["content"]
    mock_response.usage.prompt_tokens = MOCK_OPENAI_RESPONSE["usage"]["prompt_tokens"]
    mock_response.usage.completion_tokens = MOCK_OPENAI_RESPONSE["usage"]["completion_tokens"]
    return mock_response


@pytest.fixture
def mock_anthropic_response():
    """Anthropic APIレスポンスのモック"""
    from tests.fixtures.ai_responses import MOCK_ANTHROPIC_RESPONSE

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = MOCK_ANTHROPIC_RESPONSE["content"][0]["text"]
    mock_response.usage.input_tokens = MOCK_ANTHROPIC_RESPONSE["usage"]["input_tokens"]
    mock_response.usage.output_tokens = MOCK_ANTHROPIC_RESPONSE["usage"]["output_tokens"]
    return mock_response


@pytest.fixture
def sample_log_content():
    """
    サンプルログ内容

    CI/CDの失敗ログを模擬したテストデータを提供します。
    ログ解析機能のテストで使用され、実際のCI失敗パターンを再現します。

    Returns:
        str: サンプルログの内容
    """
    return """
STEP: Run tests
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'

FAILURES:
test_user_authentication.py::test_login_with_invalid_credentials FAILED
AssertionError: Expected status code 401, got 200

test_database_connection.py::test_connection_timeout FAILED
TimeoutError: Database connection timed out after 30 seconds
"""


@pytest.fixture
def ai_test_log_file(temp_dir):
    """
    AI分析テスト用のログファイル

    AI分析機能のテストで使用するサンプルログファイルを作成します。
    実際のCI/CD失敗パターンを模擬したログ内容を提供します。

    Args:
        temp_dir: 一時ディレクトリフィクスチャ

    Returns:
        Path: 作成されたログファイルのパス
    """
    from tests.fixtures.sample_logs import get_log_by_type

    log_file = temp_dir / "ai_test.log"

    # 基本的なテスト失敗ログを使用
    log_content = get_log_by_type("basic_test_failure")
    log_file.write_text(log_content, encoding="utf-8")

    return log_file


@pytest.fixture
def mock_ai_integration():
    """
    AI統合のモック

    AIIntegrationクラスの完全なモックを提供します。
    全てのメソッドが適切にモック化され、テスト時に実際のAI APIを呼び出しません。

    Returns:
        Mock: AI統合のモックオブジェクト
    """
    from unittest.mock import AsyncMock

    from tests.fixtures.ai_responses import create_mock_analysis_result

    mock_integration = Mock()
    mock_integration.initialize = AsyncMock()
    mock_integration.analyze_log = AsyncMock()
    mock_integration.stream_analyze_log = AsyncMock()
    mock_integration.start_interactive_session = AsyncMock()
    mock_integration.process_interactive_input = AsyncMock()
    mock_integration.close_interactive_session = AsyncMock()
    mock_integration.apply_fix = AsyncMock()
    mock_integration.generate_fix_suggestions = AsyncMock()

    # デフォルトの戻り値を設定
    mock_integration.analyze_log.return_value = create_mock_analysis_result()

    return mock_integration


@pytest.fixture
def mock_cost_manager():
    """
    コストマネージャーのモック

    AI使用コストの管理機能をモック化します。
    実際のコスト計算や制限チェックを行わずにテストできます。

    Returns:
        Mock: コストマネージャーのモックオブジェクト
    """
    mock_manager = Mock()
    mock_manager.estimate_request_cost = Mock(return_value=0.01)
    mock_manager.validate_request_cost = Mock(return_value=True)
    mock_manager.record_usage = Mock()
    mock_manager.check_limits = Mock(return_value={"over_limit": False, "usage_percentage": 25.0})
    mock_manager.get_usage_summary = Mock(
        return_value={"total_requests": 10, "total_cost": 0.50, "monthly_limit": 50.0, "usage_percentage": 1.0}
    )

    return mock_manager


@pytest.fixture
def mock_cache_manager():
    """
    キャッシュマネージャーのモック

    AI分析結果のキャッシュ機能をモック化します。
    実際のファイルI/Oを行わずにキャッシュ動作をテストできます。

    Returns:
        Mock: キャッシュマネージャーのモックオブジェクト
    """
    from unittest.mock import AsyncMock

    mock_manager = Mock()
    mock_manager.get_or_set = AsyncMock()
    mock_manager.invalidate_by_provider = AsyncMock()
    mock_manager.cleanup_cache = AsyncMock()
    mock_manager.get_cache_summary = Mock(
        return_value={
            "total_entries": 5,
            "cache_size_mb": 2.5,
            "hit_rate": 0.75,
            "oldest_entry": "2024-01-15T10:30:00Z",
        }
    )

    # デフォルトでキャッシュミスを返す（テストで明示的に設定可能）
    mock_manager.get_or_set.return_value = None

    return mock_manager


@pytest.fixture
def mock_config(temp_dir):
    """analyzeコマンド用のモック設定"""
    # get_ai_config() should return a dictionary, not an AIConfig object
    ai_config_dict = {
        "default_provider": "openai",
        "providers": {
            "openai": {
                "base_url": None,
                "default_model": "gpt-4o",
                "available_models": ["gpt-4o", "gpt-4o-mini"],
                "timeout_seconds": 30,
                "max_retries": 3,
                "rate_limit_per_minute": None,
                "cost_per_input_token": 0.0,
                "cost_per_output_token": 0.0,
            }
        },
        "cache_enabled": True,
        "cost_limits": {"monthly_usd": 50.0},
        "cache_dir": str(temp_dir / "cache"),
    }

    # get_ai_provider_config() should also return a dictionary
    provider_config_dict = {
        "base_url": None,
        "default_model": "gpt-4o",
        "available_models": ["gpt-4o", "gpt-4o-mini"],
        "timeout_seconds": 30,
        "max_retries": 3,
        "rate_limit_per_minute": None,
        "cost_per_input_token": 0.0,
        "cost_per_output_token": 0.0,
    }

    config = Mock(spec=Config)
    config.project_root = temp_dir
    config.get = Mock(return_value=None)
    config.get_ai_config = Mock(return_value=ai_config_dict)
    config.get_available_ai_providers = Mock(return_value=["openai"])
    config.get_ai_provider_api_key = Mock(return_value="sk-test-key-123")
    config.get_default_ai_provider = Mock(return_value="openai")
    config.get_ai_provider_config = Mock(return_value=provider_config_dict)
    config.get_path = Mock(return_value=temp_dir / "cache")
    config.__getitem__ = Mock(return_value=None)
    config.__contains__ = Mock(return_value=False)
    return config


@pytest.fixture
def mock_console():
    """
    Rich Console オブジェクトのモック

    analyzeコマンドのテストで使用するRich Consoleのモックを提供します。
    実際のコンソール出力を行わず、テスト環境で安全に実行できます。
    Rich内部の問題を避けるため、実際のConsoleインスタンスを使用しますが、
    出力は無効化されています。

    Returns:
        Console: テスト用Consoleオブジェクト
    """
    from rich.console import Console

    # Use a real Console instance instead of a Mock to avoid Rich internal issues
    return Console(file=Mock(), force_terminal=False, no_color=True)


@pytest.fixture
async def async_ai_integration_with_cleanup(mock_config, mock_ai_config):
    """
    非同期リソースクリーンアップ付きのAIIntegration

    aiohttp.ClientSessionなどの非同期リソースを適切にクリーンアップする
    AIIntegrationフィクスチャを提供します。

    Args:
        mock_config: モック設定オブジェクト
        mock_ai_config: モックAI設定オブジェクト

    Yields:
        AIIntegration: 適切にセットアップされたAIIntegrationインスタンス
    """
    from ci_helper.ai.integration import AIIntegration

    integration = AIIntegration(mock_config)
    integration.ai_config = mock_ai_config
    integration._initialized = True

    # 必要なコンポーネントをモック化
    integration.prompt_manager = Mock()
    integration.cache_manager = Mock()
    integration.cache_manager.cache_result = AsyncMock()
    integration.cost_manager = Mock()
    integration.cost_manager.check_usage_limits.return_value = {"over_limit": False, "usage_percentage": 10.0}
    integration.cost_manager.record_ai_usage = AsyncMock()

    # 非同期メソッドをAsyncMockで設定
    integration.error_handler = Mock()
    integration.error_handler.handle_error_with_retry = AsyncMock()
    integration.fallback_handler = Mock()
    integration.fallback_handler.handle_analysis_failure = AsyncMock()
    integration.session_manager = Mock()
    integration.fix_generator = Mock()
    integration.fix_applier = Mock()

    # モックプロバイダーを設定（cleanup メソッド付き）
    mock_provider = Mock()
    mock_provider.name = "openai"
    mock_provider.config = mock_ai_config.providers["openai"]
    mock_provider.count_tokens.return_value = 100
    mock_provider.estimate_cost.return_value = 0.01
    mock_provider.cleanup = AsyncMock()  # 非同期クリーンアップメソッド

    integration.providers = {"openai": mock_provider}

    try:
        yield integration
    finally:
        # テスト終了時に必ずクリーンアップを実行
        try:
            await integration.cleanup()
        except Exception as e:
            # クリーンアップエラーは警告として記録
            import logging

            logging.warning(f"テスト終了時のクリーンアップに失敗: {e}")
