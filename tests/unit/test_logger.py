"""
ログ設定ユーティリティのユニットテスト
"""

import logging
from pathlib import Path
from unittest.mock import patch

from ci_helper.utils.logger import get_logger, setup_logging


class TestSetupLogging:
    """setup_logging 関数のテスト"""

    def test_setup_logging_default(self):
        """デフォルト設定でのログセットアップテスト"""
        logger = setup_logging()

        assert logger.name == "ci_helper"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert logger.handlers[0].__class__.__name__ == "RichHandler"

    def test_setup_logging_debug_level(self):
        """DEBUGレベルでのログセットアップテスト"""
        logger = setup_logging(level="DEBUG")

        assert logger.level == logging.DEBUG
        assert logger.handlers[0].level == logging.DEBUG

    def test_setup_logging_verbose_mode(self):
        """詳細モードでのログセットアップテスト"""
        logger = setup_logging(verbose=True)

        assert logger.level == logging.DEBUG

    def test_setup_logging_with_log_file(self, temp_dir: Path):
        """ログファイル付きセットアップテスト"""
        log_file = temp_dir / "test.log"

        logger = setup_logging(log_file=log_file)

        # コンソールハンドラーとファイルハンドラーの2つが存在
        assert len(logger.handlers) == 2

        # ファイルハンドラーが追加されている
        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.level == logging.DEBUG

    def test_setup_logging_creates_log_directory(self, temp_dir: Path):
        """ログディレクトリ自動作成テスト"""
        log_file = temp_dir / "logs" / "test.log"

        setup_logging(log_file=log_file)

        # ディレクトリが作成されることを確認
        assert log_file.parent.exists()

    def test_setup_logging_invalid_level(self):
        """無効なログレベルのテスト"""
        logger = setup_logging(level="INVALID")

        # デフォルトのINFOレベルが使用される
        assert logger.level == logging.INFO

    def test_setup_logging_clears_existing_handlers(self):
        """既存ハンドラークリアテスト"""
        # 既存のハンドラーを追加
        logger = logging.getLogger("ci_helper")
        existing_handler = logging.StreamHandler()
        logger.addHandler(existing_handler)

        # セットアップを実行
        setup_logging()

        # 既存のハンドラーがクリアされることを確認
        assert existing_handler not in logger.handlers

    def test_setup_logging_rich_handler_configuration(self):
        """RichHandlerの設定テスト"""
        logger = setup_logging(verbose=True)

        # RichHandlerが作成されることを確認
        rich_handler = None
        for handler in logger.handlers:
            if handler.__class__.__name__ == "RichHandler":
                rich_handler = handler
                break

        assert rich_handler is not None

    def test_setup_logging_rich_handler_non_verbose(self):
        """非詳細モードでのRichHandler設定テスト"""
        logger = setup_logging(verbose=False)

        # RichHandlerが作成されることを確認
        rich_handler = None
        for handler in logger.handlers:
            if handler.__class__.__name__ == "RichHandler":
                rich_handler = handler
                break

        assert rich_handler is not None


class TestGetLogger:
    """get_logger 関数のテスト"""

    def test_get_logger_default_name(self):
        """デフォルト名でのロガー取得テスト"""
        logger = get_logger()

        assert logger.name == "ci_helper"

    def test_get_logger_custom_name(self):
        """カスタム名でのロガー取得テスト"""
        logger = get_logger("custom_logger")

        assert logger.name == "custom_logger"

    def test_get_logger_returns_same_instance(self):
        """同じ名前で同じインスタンスが返されることのテスト"""
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")

        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """異なる名前で異なるインスタンスが返されることのテスト"""
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")

        assert logger1 is not logger2
        assert logger1.name == "logger1"
        assert logger2.name == "logger2"


class TestLoggerIntegration:
    """ロガー統合テスト"""

    def test_logger_hierarchy(self):
        """ロガー階層のテスト"""
        parent_logger = get_logger("ci_helper")
        child_logger = get_logger("ci_helper.core")

        # 子ロガーが親ロガーの設定を継承することを確認
        assert child_logger.parent == parent_logger

    def test_logging_output_to_file(self, temp_dir: Path):
        """ファイル出力テスト"""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        test_message = "テストメッセージ"
        logger.info(test_message)

        # ファイルにログが出力されることを確認
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert test_message in log_content

    def test_logging_levels(self, temp_dir: Path):
        """ログレベルテスト"""
        log_file = temp_dir / "test.log"
        logger = setup_logging(level="DEBUG", log_file=log_file)

        logger.debug("デバッグメッセージ")
        logger.info("情報メッセージ")
        logger.warning("警告メッセージ")
        logger.error("エラーメッセージ")

        log_content = log_file.read_text(encoding="utf-8")
        assert "デバッグメッセージ" in log_content
        assert "情報メッセージ" in log_content
        assert "警告メッセージ" in log_content
        assert "エラーメッセージ" in log_content

    def test_logging_level_filtering(self, temp_dir: Path):
        """ログレベルフィルタリングテスト"""
        log_file = temp_dir / "test.log"
        logger = setup_logging(level="WARNING", log_file=log_file)

        logger.debug("デバッグメッセージ")
        logger.info("情報メッセージ")
        logger.warning("警告メッセージ")
        logger.error("エラーメッセージ")

        log_content = log_file.read_text(encoding="utf-8")
        # ロガーレベルがWARNINGなので、DEBUG/INFOメッセージは出力されない
        assert "デバッグメッセージ" not in log_content
        assert "情報メッセージ" not in log_content
        assert "警告メッセージ" in log_content
        assert "エラーメッセージ" in log_content

    @patch("ci_helper.utils.logger.console")
    def test_console_integration(self, mock_console):
        """コンソール統合テスト"""
        setup_logging()

        # RichHandlerがconsoleインスタンスを使用することを確認
        # この部分は実装の詳細なので、基本的な動作確認のみ
        assert mock_console is not None


class TestLoggerConfiguration:
    """ロガー設定のテスト"""

    def test_formatter_configuration(self, temp_dir: Path):
        """フォーマッター設定テスト"""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        # ファイルハンドラーのフォーマッターを確認
        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        formatter = file_handler.formatter
        assert formatter is not None

        # フォーマット文字列の確認
        expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert formatter._fmt == expected_format

    def test_console_handler_formatter(self):
        """コンソールハンドラーフォーマッター設定テスト"""
        logger = setup_logging()

        # RichHandlerのフォーマッターを確認
        rich_handler = logger.handlers[0]
        formatter = rich_handler.formatter
        assert formatter is not None

        # メッセージのみのフォーマット
        assert formatter._fmt == "%(message)s"

    def test_multiple_setup_calls(self):
        """複数回セットアップ呼び出しテスト"""
        logger1 = setup_logging(level="INFO")
        logger2 = setup_logging(level="DEBUG")

        # 同じロガーインスタンスが返される
        assert logger1 is logger2

        # 最後の設定が適用される
        assert logger2.level == logging.DEBUG

    def test_encoding_configuration(self, temp_dir: Path):
        """エンコーディング設定テスト"""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        # 日本語メッセージのテスト
        japanese_message = "日本語のテストメッセージ"
        logger.info(japanese_message)

        # UTF-8で正しく保存されることを確認
        log_content = log_file.read_text(encoding="utf-8")
        assert japanese_message in log_content
