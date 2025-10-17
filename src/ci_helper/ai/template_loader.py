"""
プロンプトテンプレートローダー

外部ファイルからプロンプトテンプレートを読み込み、管理する機能を提供します。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from .exceptions import ConfigurationError


class TemplateLoader:
    """プロンプトテンプレートローダー"""

    def __init__(self, template_dir: Path | None = None):
        """テンプレートローダーを初期化

        Args:
            template_dir: テンプレートディレクトリのパス
        """
        self.template_dir = template_dir or Path("templates")

    def load_template_file(self, template_name: str) -> str:
        """テンプレートファイルを読み込み

        Args:
            template_name: テンプレート名（拡張子なし）

        Returns:
            テンプレート内容

        Raises:
            ConfigurationError: ファイルが見つからない場合
        """
        template_path = self.template_dir / f"{template_name}.txt"

        if not template_path.exists():
            raise ConfigurationError(f"テンプレートファイルが見つかりません: {template_path}")

        try:
            with open(template_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise ConfigurationError(f"テンプレートファイルの読み込みに失敗しました: {e}") from e

    def load_templates_from_config(self, config_path: Path) -> dict[str, str]:
        """設定ファイルからテンプレートを読み込み

        Args:
            config_path: 設定ファイルのパス

        Returns:
            テンプレートの辞書

        Raises:
            ConfigurationError: 設定ファイルの読み込みに失敗した場合
        """
        if not config_path.exists():
            raise ConfigurationError(f"設定ファイルが見つかりません: {config_path}")

        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)

            templates = {}

            # [ai.prompt_templates] セクションから読み込み
            if "ai" in config and "prompt_templates" in config["ai"]:
                template_config = config["ai"]["prompt_templates"]

                for template_name, template_path in template_config.items():
                    if isinstance(template_path, str):
                        # ファイルパスの場合
                        if template_path.startswith("templates/"):
                            # 相対パスの場合は絶対パスに変換
                            full_path = config_path.parent / template_path
                        else:
                            full_path = Path(template_path)

                        if full_path.exists():
                            with open(full_path, encoding="utf-8") as tf:
                                templates[template_name] = tf.read()
                    else:
                        # 直接テンプレート内容が記載されている場合
                        templates[template_name] = str(template_path)

            return templates

        except Exception as e:
            raise ConfigurationError(f"設定ファイルからのテンプレート読み込みに失敗しました: {e}") from e

    def save_template(self, template_name: str, content: str) -> None:
        """テンプレートをファイルに保存

        Args:
            template_name: テンプレート名
            content: テンプレート内容

        Raises:
            ConfigurationError: 保存に失敗した場合
        """
        try:
            # テンプレートディレクトリを作成
            self.template_dir.mkdir(parents=True, exist_ok=True)

            template_path = self.template_dir / f"{template_name}.txt"
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(content)

        except Exception as e:
            raise ConfigurationError(f"テンプレートの保存に失敗しました: {e}") from e

    def list_available_templates(self) -> list[str]:
        """利用可能なテンプレートファイル一覧を取得

        Returns:
            テンプレート名のリスト
        """
        if not self.template_dir.exists():
            return []

        templates = []
        for template_file in self.template_dir.glob("*.txt"):
            templates.append(template_file.stem)

        return sorted(templates)

    def template_exists(self, template_name: str) -> bool:
        """テンプレートファイルが存在するかチェック

        Args:
            template_name: テンプレート名

        Returns:
            存在するかどうか
        """
        template_path = self.template_dir / f"{template_name}.txt"
        return template_path.exists()

    def get_template_info(self, template_name: str) -> dict[str, any]:
        """テンプレートの情報を取得

        Args:
            template_name: テンプレート名

        Returns:
            テンプレート情報

        Raises:
            ConfigurationError: テンプレートが見つからない場合
        """
        template_path = self.template_dir / f"{template_name}.txt"

        if not template_path.exists():
            raise ConfigurationError(f"テンプレートが見つかりません: {template_name}")

        try:
            stat = template_path.stat()
            content = self.load_template_file(template_name)

            return {
                "name": template_name,
                "path": str(template_path),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "lines": len(content.splitlines()),
                "variables": self._extract_variables(content),
            }

        except Exception as e:
            raise ConfigurationError(f"テンプレート情報の取得に失敗しました: {e}") from e

    def _extract_variables(self, content: str) -> list[str]:
        """テンプレート内の変数を抽出

        Args:
            content: テンプレート内容

        Returns:
            変数名のリスト
        """
        import re

        return list(set(re.findall(r"\{(\w+)\}", content)))

    def create_sample_templates(self) -> None:
        """サンプルテンプレートを作成

        Raises:
            ConfigurationError: 作成に失敗した場合
        """
        sample_templates = {
            "custom_analysis": """カスタム分析プロンプトのサンプルです。

## 分析対象
{context}

## 分析結果
[ここに分析結果を記載]
""",
            "custom_fix": """カスタム修正提案プロンプトのサンプルです。

## 問題
{analysis_result}

## 修正提案
[ここに修正提案を記載]
""",
        }

        for name, content in sample_templates.items():
            self.save_template(name, content)
