"""
フォーマッターアーキテクチャのテスト

基底フォーマッタークラス、フォーマッターマネージャー、既存AIFormatterとの統合をテストします。
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.ci_helper.core.models import ExecutionResult, Failure, FailureType, JobResult, WorkflowResult
from src.ci_helper.formatters import (
    BaseLogFormatter,
    FormatterManager,
    LegacyAIFormatterAdapter,
    get_formatter_manager,
    reset_formatter_manager,
)


class TestBaseLogFormatter:
    """基底フォーマッタークラスのテスト"""

    def test_abstract_methods(self):
        """抽象メソッドが正しく定義されているかテスト"""
        # BaseLogFormatterは抽象クラスなので直接インスタンス化できない
        with pytest.raises(TypeError):
            BaseLogFormatter()

    def test_sanitize_content_without_security(self):
        """セキュリティ無効時のサニタイズテスト"""

        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter(sanitize_secrets=False)
        content = "secret content"
        result = formatter._sanitize_content(content)
        assert result == content

    def test_validate_options_default(self):
        """デフォルトのオプション検証テスト"""

        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        options = {"key": "value"}
        result = formatter.validate_options(**options)
        # BaseLogFormatterのデフォルト実装では、サポートされているオプションのみを返す
        # "key"はサポートされていないオプションなので除外される
        assert result == {}

    def test_supports_option_default(self):
        """デフォルトのオプションサポートテスト"""

        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        assert formatter.supports_option("any_option") is True

    def test_get_supported_options_default(self):
        """デフォルトのサポートオプション一覧テスト"""

        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        formatter = TestFormatter()
        # BaseLogFormatterのデフォルト実装では基本的なオプションを返す
        expected_options = [
            "use_optimization",
            "max_memory_mb",
            "detail_level",
            "filter_errors",
        ]
        assert formatter.get_supported_options() == expected_options


class TestLegacyAIFormatterAdapter:
    """既存AIFormatterアダプターのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        adapter = LegacyAIFormatterAdapter()
        assert adapter.get_format_name() == "markdown"
        assert "互換性維持" in adapter.get_description()

    def test_format_markdown(self):
        """Markdownフォーマットテスト"""
        adapter = LegacyAIFormatterAdapter()

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[
                                Failure(
                                    type=FailureType.TEST_FAILURE,
                                    message="Test failed",
                                    file_path="test.py",
                                    line_number=10,
                                )
                            ],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        result = adapter.format(execution_result)
        assert "CI実行結果" in result
        assert "失敗" in result
        assert "test-workflow" in result

    def test_format_json(self):
        """JSONフォーマットテスト"""
        adapter = LegacyAIFormatterAdapter()

        execution_result = ExecutionResult(success=True, workflows=[], total_duration=0.0, timestamp=datetime.now())

        result = adapter.format(execution_result, format_type="json")
        assert result.startswith("{")
        assert "execution_summary" in result

    def test_validate_options(self):
        """オプション検証テスト"""
        adapter = LegacyAIFormatterAdapter()

        # 有効なオプション
        options = adapter.validate_options(format_type="markdown")
        assert options["format_type"] == "markdown"

        # 無効なオプション
        with pytest.raises(ValueError):
            adapter.validate_options(format_type="invalid")

    def test_supports_option(self):
        """オプションサポートテスト"""
        adapter = LegacyAIFormatterAdapter()
        assert adapter.supports_option("format_type") is True
        assert adapter.supports_option("unknown_option") is False

    def test_get_supported_options(self):
        """サポートオプション一覧テスト"""
        adapter = LegacyAIFormatterAdapter()
        options = adapter.get_supported_options()
        assert "format_type" in options


class TestFormatterManager:
    """フォーマッターマネージャーのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        reset_formatter_manager()

    def test_initialization(self):
        """初期化テスト"""
        manager = FormatterManager()
        formats = manager.list_available_formats()
        assert "markdown" in formats
        assert "ai" in formats

    def test_register_formatter(self):
        """フォーマッター登録テスト"""
        manager = FormatterManager()

        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        test_formatter = TestFormatter()
        manager.register_formatter("test", test_formatter)

        assert "test" in manager.list_available_formats()
        assert manager.get_formatter("test") is test_formatter

    def test_register_formatter_validation(self):
        """フォーマッター登録時の検証テスト"""
        manager = FormatterManager()

        # 空の名前
        with pytest.raises(ValueError):
            manager.register_formatter("", Mock())

        # 無効なフォーマッター
        with pytest.raises(ValueError):
            manager.register_formatter("test", "not_a_formatter")

        # 重複登録
        class TestFormatter(BaseLogFormatter):
            def format(self, execution_result, **options):
                return "test"

            def get_format_name(self):
                return "test"

        test_formatter = TestFormatter()
        manager.register_formatter("test", test_formatter)

        with pytest.raises(ValueError):
            manager.register_formatter("test", test_formatter)

    def test_unregister_formatter(self):
        """フォーマッター登録解除テスト"""
        manager = FormatterManager()

        # 存在するフォーマッターの解除
        manager.unregister_formatter("markdown")
        assert "markdown" not in manager.list_available_formats()

        # 存在しないフォーマッターの解除
        with pytest.raises(KeyError):
            manager.unregister_formatter("nonexistent")

    def test_get_formatter(self):
        """フォーマッター取得テスト"""
        manager = FormatterManager()

        # 存在するフォーマッター
        formatter = manager.get_formatter("markdown")
        assert isinstance(formatter, BaseLogFormatter)

        # 存在しないフォーマッター
        # FormatterManagerの実装ではLogFormattingErrorが発生する
        from src.ci_helper.core.exceptions import LogFormattingError

        with pytest.raises(LogFormattingError):
            manager.get_formatter("nonexistent")

    def test_has_formatter(self):
        """フォーマッター存在確認テスト"""
        manager = FormatterManager()

        assert manager.has_formatter("markdown") is True
        assert manager.has_formatter("nonexistent") is False

    def test_get_formatter_info(self):
        """フォーマッター情報取得テスト"""
        manager = FormatterManager()

        info = manager.get_formatter_info("markdown")
        assert info["name"] == "markdown"
        assert "description" in info
        assert "supported_options" in info
        assert "class_name" in info

    def test_format_log(self):
        """ログフォーマットテスト"""
        manager = FormatterManager()

        execution_result = ExecutionResult(success=True, workflows=[], total_duration=0.0, timestamp=datetime.now())

        result = manager.format_log(execution_result, "markdown")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_log_safe(self):
        """セーフログフォーマットテスト"""
        manager = FormatterManager()

        execution_result = ExecutionResult(success=True, workflows=[], total_duration=0.0, timestamp=datetime.now())

        # 存在するフォーマッター
        result, used_format = manager.format_log_safe(execution_result, "markdown")
        assert used_format == "markdown"
        assert isinstance(result, str)

        # 存在しないフォーマッター（フォールバック）
        result, used_format = manager.format_log_safe(execution_result, "nonexistent")
        assert used_format == "markdown"  # フォールバック先
        assert isinstance(result, str)

    def test_get_default_format(self):
        """デフォルトフォーマット取得テスト"""
        manager = FormatterManager()

        default_format = manager.get_default_format()
        assert default_format in ["ai", "markdown", "json"]
        assert manager.has_formatter(default_format)


class TestGlobalFormatterManager:
    """グローバルフォーマッターマネージャーのテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        reset_formatter_manager()

    def test_get_formatter_manager_singleton(self):
        """シングルトンパターンのテスト"""
        manager1 = get_formatter_manager()
        manager2 = get_formatter_manager()
        assert manager1 is manager2

    def test_reset_formatter_manager(self):
        """フォーマッターマネージャーリセットテスト"""
        manager1 = get_formatter_manager()
        reset_formatter_manager()
        manager2 = get_formatter_manager()
        assert manager1 is not manager2


class TestIntegrationWithExistingAIFormatter:
    """既存AIFormatterとの統合テスト"""

    def test_markdown_output_compatibility(self):
        """Markdown出力の互換性テスト"""
        manager = get_formatter_manager()

        execution_result = ExecutionResult(
            success=False,
            workflows=[
                WorkflowResult(
                    name="test-workflow",
                    success=False,
                    jobs=[
                        JobResult(
                            name="test-job",
                            success=False,
                            failures=[
                                Failure(
                                    type=FailureType.TEST_FAILURE,
                                    message="Test assertion failed",
                                    file_path="test.py",
                                    line_number=42,
                                )
                            ],
                            duration=5.0,
                        )
                    ],
                    duration=10.0,
                )
            ],
            total_duration=10.0,
            timestamp=datetime.now(),
        )

        # 新しいアーキテクチャ経由でフォーマット
        result = manager.format_log(execution_result, "markdown")

        # 期待される内容が含まれているかチェック
        assert "CI実行結果" in result
        assert "失敗" in result
        assert "test-workflow" in result
        assert "test-job" in result
        assert "Test assertion failed" in result
        assert "test.py" in result

    def test_json_output_compatibility(self):
        """JSON出力の互換性テスト"""
        import json

        manager = get_formatter_manager()

        execution_result = ExecutionResult(success=True, workflows=[], total_duration=5.0, timestamp=datetime.now())

        # JSON形式でフォーマット
        result = manager.format_log(execution_result, "markdown", format_type="json")

        # 有効なJSONかチェック
        parsed = json.loads(result)
        assert "execution_summary" in parsed
        assert "metrics" in parsed
        assert "workflows" in parsed
        assert "failures" in parsed

        # 基本的な内容チェック
        assert parsed["execution_summary"]["success"] is True
        assert parsed["execution_summary"]["total_duration"] == 5.0
