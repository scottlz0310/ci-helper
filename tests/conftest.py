"""
pytest設定と共有フィクスチャ
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from ci_helper.utils.config import Config


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """一時ディレクトリを提供するフィクスチャ"""
    with TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config(temp_dir: Path) -> Config:
    """テスト用の設定を提供するフィクスチャ"""
    return Config(project_root=temp_dir)


@pytest.fixture
def sample_workflow_dir(temp_dir: Path) -> Path:
    """サンプルワークフローディレクトリを作成するフィクスチャ"""
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
    """AI設定のモック"""
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
    """サンプルログ内容"""
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
    """AI分析テスト用のログファイル"""
    log_file = temp_dir / "ai_test.log"

    # テスト用ログファイルの内容を読み込み
    fixtures_dir = Path(__file__).parent / "fixtures" / "sample_logs"
    source_log = fixtures_dir / "ai_analysis_test.log"

    if source_log.exists():
        log_file.write_text(source_log.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # フォールバック用の基本的なログ内容
        log_file.write_text(
            """
STEP: Run tests
ERROR: Test failed
npm ERR! code ENOENT
AssertionError: Expected 200, got 404
""",
            encoding="utf-8",
        )

    return log_file


@pytest.fixture
def mock_ai_integration():
    """AI統合のモック"""
    from unittest.mock import AsyncMock

    mock_integration = Mock()
    mock_integration.initialize = AsyncMock()
    mock_integration.analyze_log = AsyncMock()
    mock_integration.stream_analyze_log = AsyncMock()
    mock_integration.start_interactive_session = AsyncMock()
    mock_integration.process_interactive_input = AsyncMock()
    mock_integration.close_interactive_session = AsyncMock()

    return mock_integration


@pytest.fixture
def mock_cost_manager():
    """コストマネージャーのモック"""
    mock_manager = Mock()
    mock_manager.estimate_request_cost = Mock()
    mock_manager.validate_request_cost = Mock()
    mock_manager.record_usage = Mock()
    mock_manager.check_limits = Mock()
    mock_manager.get_usage_summary = Mock()

    return mock_manager


@pytest.fixture
def mock_cache_manager():
    """キャッシュマネージャーのモック"""
    from unittest.mock import AsyncMock

    mock_manager = Mock()
    mock_manager.get_or_set = AsyncMock()
    mock_manager.invalidate_by_provider = AsyncMock()
    mock_manager.cleanup_cache = AsyncMock()
    mock_manager.get_cache_summary = Mock()

    return mock_manager


@pytest.fixture
def mock_config(temp_dir):
    """analyzeコマンド用のモック設定"""
    from src.ci_helper.ai.models import AIConfig, ProviderConfig

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
    config.get_path.return_value = temp_dir / "cache"
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
