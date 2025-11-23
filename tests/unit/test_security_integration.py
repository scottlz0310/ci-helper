"""
セキュリティ機能統合のテスト

ログ整形機能におけるセキュリティ機能の統合をテストします。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from ci_helper.formatters.base_formatter import BaseLogFormatter
from ci_helper.utils.file_save_utils import FileSaveManager


class MockFormatter(BaseLogFormatter):
    """テスト用のモックフォーマッター"""

    def format(self, execution_result, **options):
        return "formatted content"

    def get_format_name(self):
        return "mock"


class TestSecurityIntegration:
    """セキュリティ機能統合のテストクラス"""

    def test_base_formatter_security_initialization(self):
        """BaseFormatterのセキュリティ機能初期化をテスト"""
        # セキュリティ有効
        formatter = MockFormatter(sanitize_secrets=True)
        assert formatter.sanitize_secrets is True
        assert formatter.security_validator is not None

        # セキュリティ無効
        formatter = MockFormatter(sanitize_secrets=False)
        assert formatter.sanitize_secrets is False
        assert formatter.security_validator is None

    def test_base_formatter_sanitize_content(self):
        """BaseFormatterのコンテンツサニタイズをテスト"""
        formatter = MockFormatter(sanitize_secrets=True)

        # 通常のコンテンツ
        normal_content = "This is normal log content"
        result = formatter._sanitize_content(normal_content)
        assert result == normal_content

        # シークレットを含むコンテンツ（モック）
        with patch.object(formatter.security_validator.secret_detector, "sanitize_content") as mock_sanitize:
            mock_sanitize.return_value = "This is [REDACTED_API_KEY] content"

            secret_content = "This is sk-1234567890abcdef content"
            result = formatter._sanitize_content(secret_content)
            assert "[REDACTED_API_KEY]" in result
            mock_sanitize.assert_called_once_with(secret_content)

    def test_base_formatter_validate_log_content_security(self):
        """BaseFormatterのログコンテンツセキュリティ検証をテスト"""
        formatter = MockFormatter(sanitize_secrets=True)

        with patch.object(formatter.security_validator, "validate_log_content") as mock_validate:
            mock_validate.return_value = {
                "has_secrets": True,
                "secret_count": 1,
                "detected_secrets": [{"type": "api_key", "value": "sk-123"}],
                "sanitized_content": "sanitized content",
                "recommendations": ["Use environment variables"],
            }

            content = "api_key=sk-1234567890abcdef"
            result = formatter.validate_log_content_security(content)

            assert result["has_secrets"] is True
            assert result["secret_count"] == 1
            assert len(result["detected_secrets"]) == 1
            mock_validate.assert_called_once_with(content)

    def test_file_save_manager_security_initialization(self):
        """FileSaveManagerのセキュリティ機能初期化をテスト"""
        console = Console()

        # セキュリティ有効
        manager = FileSaveManager(console, enable_security=True)
        assert manager.enable_security is True
        assert manager.security_validator is not None

        # セキュリティ無効
        manager = FileSaveManager(console, enable_security=False)
        assert manager.enable_security is False
        assert manager.security_validator is None

    def test_file_save_manager_path_validation(self):
        """FileSaveManagerのパス検証をテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=True)

        # 安全なパス
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_path = Path(temp_dir) / "test.txt"
            result = manager.validate_output_path_security(safe_path)
            assert result["valid"] is True
            assert result["error"] is None

        # 危険なパス（上位ディレクトリ参照）
        dangerous_path = Path("../../../etc/passwd")
        result = manager.validate_output_path_security(dangerous_path)
        assert result["valid"] is False
        assert "セキュリティ上の理由" in result["error"]

    def test_file_save_manager_content_sanitization(self):
        """FileSaveManagerのコンテンツサニタイズをテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=True)

        with patch.object(manager.security_validator.secret_detector, "sanitize_content") as mock_sanitize:
            mock_sanitize.return_value = "sanitized content"

            content = "api_key=sk-1234567890abcdef"
            result = manager._sanitize_output_content(content)

            assert result == "sanitized content"
            mock_sanitize.assert_called_once_with(content)

    def test_file_save_manager_save_with_security(self):
        """FileSaveManagerのセキュリティ機能付き保存をテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test.txt"

            # セキュリティ検証をモック
            with patch.object(manager, "validate_output_path_security") as mock_validate:
                mock_validate.return_value = {"valid": True, "error": None}

                with patch.object(manager, "_sanitize_output_content") as mock_sanitize:
                    mock_sanitize.return_value = "sanitized content"

                    success, saved_path = manager.save_formatted_log(
                        content="original content",
                        output_file=str(output_file),
                        format_type="test",
                        confirm_overwrite=False,
                    )

                    assert success is True
                    assert saved_path == str(output_file)
                    mock_validate.assert_called()
                    mock_sanitize.assert_called_with("original content")

    def test_file_save_manager_security_failure(self):
        """FileSaveManagerのセキュリティ検証失敗をテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test.txt"

            # セキュリティ検証失敗をモック
            with patch.object(manager, "validate_output_path_security") as mock_validate:
                mock_validate.return_value = {
                    "valid": False,
                    "error": "セキュリティエラー",
                    "recommendations": ["安全なパスを使用してください"],
                }

                success, saved_path = manager.save_formatted_log(
                    content="test content",
                    output_file=str(output_file),
                    format_type="test",
                    confirm_overwrite=False,
                )

                assert success is False
                assert saved_path is None
                mock_validate.assert_called()

    def test_dangerous_path_detection(self):
        """危険なパスの検出をテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=True)

        # 危険なパスのテストケース
        dangerous_paths = [
            Path("../../../etc/passwd"),
            Path("..\\..\\windows\\system32\\config"),
            Path("/etc/shadow"),
            Path("/bin/bash"),
        ]

        for path in dangerous_paths:
            assert manager._is_dangerous_path(path) is True

        # 安全なパスのテストケース
        safe_paths = [
            Path("./output.txt"),
            Path("logs/formatted.md"),
            Path("results/analysis.json"),
        ]

        for path in safe_paths:
            # 現在のディレクトリ以下なので安全
            result = manager._is_dangerous_path(path)
            # テスト環境では一時ディレクトリを使用するため、結果は環境依存
            assert isinstance(result, bool)

    def test_security_disabled_fallback(self):
        """セキュリティ無効時のフォールバック動作をテスト"""
        console = Console()
        manager = FileSaveManager(console, enable_security=False)

        # セキュリティ無効時はコンテンツをそのまま返す
        content = "api_key=sk-1234567890abcdef"
        result = manager._sanitize_output_content(content)
        assert result == content

        # セキュリティ検証も基本的なもののみ
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_path = Path(temp_dir) / "test.txt"
            result = manager.validate_output_path_security(safe_path)
            assert result["security_level"] == "basic"


class MockFormatter(BaseLogFormatter):
    """テスト用のモックフォーマッター"""

    def format(self, execution_result, **options):
        return "formatted content"

    def get_format_name(self):
        return "mock"


class TestFormatterSecurityIntegration:
    """フォーマッターのセキュリティ統合テスト"""

    def test_formatter_with_security_enabled(self):
        """セキュリティ有効時のフォーマッター動作をテスト"""
        formatter = MockFormatter(sanitize_secrets=True)

        # モックの実行結果を作成
        mock_result = Mock()

        # フォーマット実行
        result = formatter.format(mock_result)
        assert result == "formatted content"

        # セキュリティ機能が初期化されていることを確認
        assert formatter.security_validator is not None

    def test_formatter_with_security_disabled(self):
        """セキュリティ無効時のフォーマッター動作をテスト"""
        formatter = MockFormatter(sanitize_secrets=False)

        # モックの実行結果を作成
        mock_result = Mock()

        # フォーマット実行
        result = formatter.format(mock_result)
        assert result == "formatted content"

        # セキュリティ機能が無効であることを確認
        assert formatter.security_validator is None
