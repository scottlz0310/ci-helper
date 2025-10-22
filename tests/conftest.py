"""
pytest設定と共有フィクスチャ

このファイルは全テストで共有されるフィクスチャとpytest設定を提供します。
テストの独立性と再現性を確保するため、適切なモックとテストデータを提供します。
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from ci_helper.utils.config import Config


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    一時ディレクトリを提供するフィクスチャ
    
    テスト実行時に一時的なディレクトリを作成し、テスト終了後に自動的にクリーンアップします。
    ファイル操作のテストで使用され、テスト間の独立性を保証します。
    
    Returns:
        Path: 一時ディレクトリのパス
    """
    with TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


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
    from ci_helper.ai.models import AIConfig, ProviderConfig

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
    mock_manager.get_usage_summary = Mock(return_value={
        "total_requests": 10,
        "total_cost": 0.50,
        "monthly_limit": 50.0,
        "usage_percentage": 1.0
    })

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
    from tests.fixtures.ai_responses import create_mock_analysis_result

    mock_manager = Mock()
    mock_manager.get_or_set = AsyncMock()
    mock_manager.invalidate_by_provider = AsyncMock()
    mock_manager.cleanup_cache = AsyncMock()
    mock_manager.get_cache_summary = Mock(return_value={
        "total_entries": 5,
        "cache_size_mb": 2.5,
        "hit_rate": 0.75,
        "oldest_entry": "2024-01-15T10:30:00Z"
    })
    
    # デフォルトでキャッシュミスを返す（テストで明示的に設定可能）
    mock_manager.get_or_set.return_value = None

    return mock_manager


@pytest.fixture
def mock_config(temp_dir):
    """analyzeコマンド用のモック設定"""
    from ci_helper.ai.models import AIConfig, ProviderConfig

    # Create a proper AIConfig object
    provider_config = ProviderConfig(
        name="openai",
        api_key="sk-test-key-123",
        default_model="gpt-4o",
        available_models=["gpt-4o", "gpt-4o-mini"],
    )

    ai_config = AIConfig(
        default_provider="openai",
        providers={"openai": provider_config},
        cache_enabled=True,
        cost_limits={"monthly_usd": 50.0},
        cache_dir=str(temp_dir / "cache"),
    )

    config = Mock(spec=Config)
    config.project_root = temp_dir
    config.get = Mock(return_value=None)
    config.get_ai_config = Mock(return_value=ai_config)
    config.get_available_ai_providers = Mock(return_value=["openai"])
    config.get_ai_provider_api_key = Mock(return_value="sk-test-key-123")
    config.get_default_ai_provider = Mock(return_value="openai")
    config.get_ai_provider_config = Mock(return_value=provider_config)
    config.get_path = Mock(return_value=temp_dir / "cache")
    config.__getitem__ = Mock(return_value=None)
    config.__contains__ = Mock(return_value=False)
    return config
