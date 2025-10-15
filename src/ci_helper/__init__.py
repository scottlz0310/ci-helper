"""
ci-helper: actを使用したローカルCI/CDパイプライン検証とAI統合機能を提供するCLIツール

このパッケージは、GitHub Actionsワークフローをローカルで実行し、
失敗を分析してAI対応の出力を生成する機能を提供します。
"""

__version__ = "0.1.0"
__author__ = "scottlz0310"
__email__ = "scottlz0310@users.noreply.github.com"

# パッケージレベルのエクスポート
from .cli import cli

__all__ = ["cli"]
