"""
修正テンプレート管理システム

パターンに対応する修正テンプレートの管理、読み込み、検証、選択機能を提供します。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import FixStep, FixSuggestion, FixTemplate, Pattern


class FixTemplateManager:
    """修正テンプレート管理クラス"""

    def __init__(self, template_directory: Path | str = "data/templates") -> None:
        """
        修正テンプレート管理システムを初期化

        Args:
            template_directory: テンプレートファイルが格納されているディレクトリ
        """
        self.template_directory = Path(template_directory)
        self._templates: dict[str, FixTemplate] = {}
        self._pattern_to_templates: dict[str, list[str]] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """テンプレートファイルを読み込み"""
        if not self.template_directory.exists():
            return

        # JSONファイルを検索して読み込み
        for template_file in self.template_directory.glob("*.json"):
            try:
                self._load_template_file(template_file)
            except Exception:
                # ログ出力は後で実装
                pass

    def _load_template_file(self, template_file: Path) -> None:
        """個別のテンプレートファイルを読み込み"""
        with template_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        templates_data = data.get("templates", [])
        for template_data in templates_data:
            try:
                template = self._parse_template_data(template_data)
                self._register_template(template)
            except Exception:
                pass

    def _parse_template_data(self, template_data: dict[str, Any]) -> FixTemplate:
        """テンプレートデータをFixTemplateオブジェクトに変換"""
        # 修正ステップを解析
        fix_steps: list[FixStep] = []
        for step_data in template_data.get("fix_steps", []):
            fix_step = FixStep(
                type=step_data["type"],
                description=step_data["description"],
                file_path=step_data.get("file_path"),
                action=step_data.get("action"),
                content=step_data.get("content"),
                command=step_data.get("command"),
                validation=step_data.get("validation"),
            )
            fix_steps.append(fix_step)

        return FixTemplate(
            id=template_data["id"],
            name=template_data["name"],
            description=template_data["description"],
            pattern_ids=template_data["pattern_ids"],
            fix_steps=fix_steps,
            risk_level=template_data["risk_level"],
            estimated_time=template_data["estimated_time"],
            success_rate=template_data["success_rate"],
            prerequisites=template_data.get("prerequisites", []),
            validation_steps=template_data.get("validation_steps", []),
        )

    def _register_template(self, template: FixTemplate) -> None:
        """テンプレートを登録"""
        self._templates[template.id] = template

        # パターンIDとテンプレートのマッピングを更新
        for pattern_id in template.pattern_ids:
            if pattern_id not in self._pattern_to_templates:
                self._pattern_to_templates[pattern_id] = []
            self._pattern_to_templates[pattern_id].append(template.id)

    def get_template_for_pattern(self, pattern: Pattern) -> FixTemplate | None:
        """パターンに対応するテンプレートを取得"""
        template_ids = self._pattern_to_templates.get(pattern.id, [])
        if not template_ids:
            return None

        # 最初に見つかったテンプレートを返す（後で優先度ベースの選択を実装）
        return self._templates.get(template_ids[0])

    def get_templates_for_pattern(self, pattern: Pattern) -> list[FixTemplate]:
        """パターンに対応するすべてのテンプレートを取得"""
        template_ids = self._pattern_to_templates.get(pattern.id, [])
        return [self._templates[template_id] for template_id in template_ids if template_id in self._templates]

    def get_template_by_id(self, template_id: str) -> FixTemplate | None:
        """IDでテンプレートを取得"""
        return self._templates.get(template_id)

    def customize_template(self, template: FixTemplate, context: dict[str, Any]) -> FixSuggestion:
        """テンプレートをコンテキストに応じてカスタマイズしてFixSuggestionを生成"""
        # コンテキスト変数を使用してテンプレートをカスタマイズ
        customized_steps: list[FixStep] = []
        for step in template.fix_steps:
            customized_step = self._customize_fix_step(step, context)
            customized_steps.append(customized_step)

        # FixSuggestionを作成
        description = self._substitute_variables(template.description, context)
        return FixSuggestion(
            title=template.name,
            description=description if description is not None else template.description,
            # code_changesは後で実装
            code_changes=[],
            # priorityはrisk_levelから推定
            priority=self._risk_level_to_priority(template.risk_level),
            estimated_effort=template.estimated_time,
            confidence=template.success_rate,
            references=[],
        )

    def _customize_fix_step(self, step: FixStep, context: dict[str, Any]) -> FixStep:
        """修正ステップをコンテキストに応じてカスタマイズ"""
        description = self._substitute_variables(step.description, context)
        return FixStep(
            type=step.type,
            description=description if description is not None else step.description,
            file_path=self._substitute_variables(step.file_path, context) if step.file_path else None,
            action=step.action,
            content=self._substitute_variables(step.content, context) if step.content else None,
            command=self._substitute_variables(step.command, context) if step.command else None,
            validation=self._substitute_variables(step.validation, context) if step.validation else None,
        )

    def _substitute_variables(self, text: str | None, context: dict[str, Any]) -> str | None:
        """テキスト内の変数を置換"""
        if not text:
            return text

        # {variable_name} 形式の変数を置換
        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return str(context.get(var_name, match.group(0)))

        return re.sub(r"\{([^}]+)\}", replace_var, text)

    def _risk_level_to_priority(self, risk_level: str) -> Any:
        """リスクレベルを優先度に変換"""
        # models.pyのPriorityを使用
        from .models import Priority

        risk_mapping = {
            "low": Priority.LOW,
            "medium": Priority.MEDIUM,
            "high": Priority.HIGH,
        }
        return risk_mapping.get(risk_level.lower(), Priority.MEDIUM)

    def validate_template(self, template: FixTemplate) -> bool:
        """テンプレートの妥当性を検証"""
        try:
            # 必須フィールドの検証
            if not template.id or not template.name:
                return False

            if not template.pattern_ids:
                return False

            if not template.fix_steps:
                return False

            # リスクレベルの検証
            valid_risk_levels = {"low", "medium", "high"}
            if template.risk_level.lower() not in valid_risk_levels:
                return False

            # 成功率の検証
            if not (0.0 <= template.success_rate <= 1.0):
                return False

            # 修正ステップの検証
            for step in template.fix_steps:
                if not self._validate_fix_step(step):
                    return False

            return True

        except Exception:
            return False

    def _validate_fix_step(self, step: FixStep) -> bool:
        """修正ステップの妥当性を検証"""
        # ステップタイプの検証
        valid_types = {"file_modification", "command", "config_change"}
        if step.type not in valid_types:
            return False

        # 説明の存在確認
        if not step.description:
            return False

        # タイプ別の必須フィールド検証
        if step.type == "file_modification":
            if not step.file_path or not step.action:
                return False
            valid_actions = {"append", "replace", "create", "delete"}
            if step.action not in valid_actions:
                return False

        elif step.type == "command":
            if not step.command:
                return False

        return True

    def get_all_templates(self) -> list[FixTemplate]:
        """すべてのテンプレートを取得"""
        return list(self._templates.values())

    def get_templates_by_risk_level(self, risk_level: str) -> list[FixTemplate]:
        """リスクレベルでテンプレートをフィルタリング"""
        return [template for template in self._templates.values() if template.risk_level.lower() == risk_level.lower()]

    def reload_templates(self) -> None:
        """テンプレートを再読み込み"""
        self._templates.clear()
        self._pattern_to_templates.clear()
        self._load_templates()
