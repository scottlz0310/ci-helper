"""
ログ設定ユーティリティ

Richを使用した美しいログ出力を提供します。
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

# Rich tracebackを有効化
install(show_locals=True)

# グローバルコンソールインスタンス
console = Console()


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False
) -> logging.Logger:
    """ログ設定をセットアップ
    
    Args:
        level: ログレベル
        log_file: ログファイルパス（Noneの場合はファイル出力なし）
        verbose: 詳細ログを有効にするか
        
    Returns:
        設定されたロガー
    """
    # ログレベルの設定
    if verbose:
        level = "DEBUG"
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # ルートロガーの設定
    logger = logging.getLogger("ci_helper")
    logger.setLevel(log_level)
    
    # 既存のハンドラーをクリア
    logger.handlers.clear()
    
    # コンソールハンドラー（Rich使用）
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=verbose,
        markup=True,
        rich_tracebacks=True
    )
    console_handler.setLevel(log_level)
    
    # フォーマッターの設定
    formatter = logging.Formatter(
        "%(message)s",
        datefmt="[%X]"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラー（指定された場合）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # ファイルには詳細ログを出力
        
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "ci_helper") -> logging.Logger:
    """ロガーを取得
    
    Args:
        name: ロガー名
        
    Returns:
        ロガーインスタンス
    """
    return logging.getLogger(name)


# デフォルトロガーの設定
logger = setup_logging()