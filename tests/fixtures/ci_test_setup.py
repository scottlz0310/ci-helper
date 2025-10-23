"""
CI/CD環境でのテスト設定

GitHub ActionsやCI/CD環境でのAIテスト実行用の設定とヘルパー関数を提供します。
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class MockAIProvider:
    """CI/CD環境用のモックAIプロバイダー"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.call_count = 0
        self.responses = []

    async def analyze(self, prompt: str, context: str, options):
        """モック分析"""
        self.call_count += 1

        # 決定論的なレスポンスを返す
        response = {
            "summary": f"Mock analysis by {self.provider_name}",
            "root_causes": [
                {
                    "category": "test",
                    "description": "Mock root cause analysis",
                    "severity": "MEDIUM",
                }
            ],
            "fix_suggestions": [
                {
                    "title": "Mock fix suggestion",
                    "description": "This is a mock fix suggestion for CI testing",
                    "priority": "MEDIUM",
                    "confidence": 0.8,
                }
            ],
            "confidence_score": 0.85,
            "provider": self.provider_name,
            "model": "mock-model",
            "cost": 0.001,
        }

        self.responses.append(response)
        return response

    async def stream_analyze(self, prompt: str, context: str, options):
        """モックストリーミング分析"""
        chunks = ["Mock", " streaming", " analysis", " result"]
        for chunk in chunks:
            yield chunk


def setup_ci_environment():
    """CI/CD環境のセットアップ"""
    # CI環境の検出
    is_ci = any(
        os.getenv(var)
        for var in ["CI", "CONTINUOUS_INTEGRATION", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "BUILDKITE"]
    )

    if is_ci:
        # CI環境では実際のAI APIを使用しない
        os.environ["CI_HELPER_AI_MOCK_MODE"] = "true"
        os.environ["CI_HELPER_AI_CACHE_ENABLED"] = "false"

        # モック用のAPIキーを設定
        os.environ["OPENAI_API_KEY"] = "mock-openai-key-for-ci"
        os.environ["ANTHROPIC_API_KEY"] = "mock-anthropic-key-for-ci"

    return is_ci


def create_mock_ai_responses():
    """CI用のモックAIレスポンスを作成"""
    return {
        "openai": {
            "choices": [{"message": {"content": "CI Mock Analysis: The test failures indicate dependency issues."}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
        },
        "anthropic": {
            "content": [{"text": "CI Mock Analysis: Multiple issues detected in the CI pipeline."}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        },
    }


@pytest.fixture(scope="session", autouse=True)
def ci_setup():
    """CI環境の自動セットアップ"""
    is_ci = setup_ci_environment()

    if is_ci:
        # CI環境では全てのAI呼び出しをモック化
        with patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai:
            with patch("src.ci_helper.ai.providers.anthropic.AsyncAnthropic") as mock_anthropic:
                # モッククライアントの設定
                mock_responses = create_mock_ai_responses()

                mock_openai_client = Mock()
                mock_openai_client.chat.completions.create.return_value = Mock(**mock_responses["openai"])
                mock_openai.return_value = mock_openai_client

                mock_anthropic_client = Mock()
                mock_anthropic_client.messages.create.return_value = Mock(**mock_responses["anthropic"])
                mock_anthropic.return_value = mock_anthropic_client

                yield {"is_ci": True, "mocked": True}
    else:
        yield {"is_ci": False, "mocked": False}


class CITestHelper:
    """CI/CDテスト用のヘルパークラス"""

    @staticmethod
    def skip_if_no_api_key(provider: str):
        """APIキーがない場合はテストをスキップ"""
        key_env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        env_var = key_env_vars.get(provider)
        if not env_var:
            return pytest.mark.skip(f"Unknown provider: {provider}")

        api_key = os.getenv(env_var)
        if not api_key or api_key.startswith("mock-"):
            return pytest.mark.skip(f"No real API key for {provider}")

        return lambda func: func

    @staticmethod
    def requires_real_api():
        """実際のAPI呼び出しが必要なテストをマーク"""
        is_ci = os.getenv("CI") is not None
        mock_mode = os.getenv("CI_HELPER_AI_MOCK_MODE") == "true"

        if is_ci or mock_mode:
            return pytest.mark.skip("Requires real API calls")

        return lambda func: func

    @staticmethod
    def create_test_log_file(temp_dir: Path, content: str | None = None) -> Path:
        """テスト用ログファイルを作成"""
        if content is None:
            content = """
STEP: Run tests
ERROR: Test failed
npm ERR! code ENOENT
AssertionError: Expected 200, got 404
Process completed with exit code 1
"""

        log_file = temp_dir / "test.log"
        log_file.write_text(content, encoding="utf-8")
        return log_file

    @staticmethod
    def create_test_config_file(temp_dir: Path, config_content: str | None = None) -> Path:
        """テスト用設定ファイルを作成"""
        if config_content is None:
            config_content = """
[ai]
default_provider = "openai"
cache_enabled = false

[ai.providers.openai]
default_model = "gpt-4o-mini"
timeout_seconds = 10
max_retries = 1
"""

        config_file = temp_dir / "ci-helper.toml"
        config_file.write_text(config_content, encoding="utf-8")
        return config_file


# CI環境でのテスト用デコレータ
def ci_safe_test(func):
    """CI環境で安全に実行できるテスト用デコレータ"""

    def wrapper(*args, **kwargs):
        # CI環境では実際のAPI呼び出しを避ける
        if os.getenv("CI") or os.getenv("CI_HELPER_AI_MOCK_MODE") == "true":
            with patch("src.ci_helper.ai.integration.AIIntegration") as mock_ai:
                mock_instance = Mock()
                mock_instance.analyze_log.return_value = {
                    "summary": "CI safe mock analysis",
                    "confidence_score": 0.8,
                }
                mock_ai.return_value = mock_instance
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper


# パフォーマンステスト用の設定
PERFORMANCE_TEST_LIMITS = {
    "max_analysis_time": 10.0,  # 秒
    "max_memory_usage": 100,  # MB
    "max_concurrent_requests": 5,
}


def measure_performance(func):
    """パフォーマンス測定デコレータ"""
    import time

    import psutil

    def wrapper(*args, **kwargs):
        # メモリ使用量の測定開始
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 実行時間の測定開始
        start_time = time.time()

        try:
            result = func(*args, **kwargs)

            # 測定終了
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB

            execution_time = end_time - start_time
            memory_used = end_memory - start_memory

            # パフォーマンス制限のチェック
            if execution_time > PERFORMANCE_TEST_LIMITS["max_analysis_time"]:
                pytest.fail(
                    f"Execution time {execution_time:.2f}s exceeds limit {PERFORMANCE_TEST_LIMITS['max_analysis_time']}s"
                )

            if memory_used > PERFORMANCE_TEST_LIMITS["max_memory_usage"]:
                pytest.fail(
                    f"Memory usage {memory_used:.2f}MB exceeds limit {PERFORMANCE_TEST_LIMITS['max_memory_usage']}MB"
                )

            return result

        except Exception:
            end_time = time.time()
            execution_time = end_time - start_time
            raise

    return wrapper
