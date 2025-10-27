"""
修正テンプレート検証のユニットテスト

修正テンプレートの妥当性検証とカスタマイズ機能をテストします。
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.ci_helper.ai.fix_templates import FixTemplateManager
from src.ci_helper.ai.models import FixStep, FixTemplate, Pattern, Priority


class TestFixTemplateManager:
    """修正テンプレート管理のテスト"""

    @pytest.fixture
    def temp_template_dir(self):
        """一時テンプレートディレクトリ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_template_data(self):
        """サンプルテンプレートデータ"""
        return {
            "templates": [
                {
                    "id": "docker_permission_fix",
                    "name": "Docker権限エラー修正",
                    "description": "Docker権限エラーを修正するため、.actrcファイルに--privilegedフラグを追加します",
                    "pattern_ids": ["docker_permission_denied"],
                    "fix_steps": [
                        {
                            "type": "file_modification",
                            "description": ".actrcファイルに--privilegedフラグを追加",
                            "file_path": ".actrc",
                            "action": "append",
                            "content": "\n--privileged",
                        }
                    ],
                    "risk_level": "low",
                    "estimated_time": "2分",
                    "success_rate": 0.95,
                    "prerequisites": ["Dockerがインストールされていること"],
                    "validation_steps": ["docker --version で確認"],
                },
                {
                    "id": "npm_package_fix",
                    "name": "NPMパッケージ不足修正",
                    "description": "不足しているNPMパッケージをインストールします",
                    "pattern_ids": ["npm_package_not_found"],
                    "fix_steps": [
                        {
                            "type": "command",
                            "description": "NPMパッケージをインストール",
                            "command": "npm install {package_name}",
                        }
                    ],
                    "risk_level": "medium",
                    "estimated_time": "5分",
                    "success_rate": 0.85,
                    "prerequisites": ["Node.jsとnpmがインストールされていること"],
                    "validation_steps": ["npm list {package_name} で確認"],
                },
            ]
        }

    @pytest.fixture
    def sample_pattern(self):
        """テスト用パターン"""
        from datetime import datetime

        return Pattern(
            id="docker_permission_denied",
            name="Docker権限拒否",
            category="permission",
            regex_patterns=[r"permission\s+denied.*docker"],
            keywords=["permission", "denied", "docker"],
            context_requirements=["docker", "socket"],
            confidence_base=0.8,
            success_rate=0.9,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.fixture
    def template_manager_with_data(self, temp_template_dir, sample_template_data):
        """テンプレートデータを含むテンプレート管理インスタンス"""
        # テンプレートファイルを作成
        template_file = temp_template_dir / "test_templates.json"
        with template_file.open("w", encoding="utf-8") as f:
            json.dump(sample_template_data, f, ensure_ascii=False, indent=2)

        return FixTemplateManager(temp_template_dir)

    def test_load_templates_success(self, template_manager_with_data):
        """テンプレート読み込み成功のテスト"""
        manager = template_manager_with_data

        # テンプレートが読み込まれていることを確認
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 2

        # 特定のテンプレートが存在することを確認
        docker_template = manager.get_template_by_id("docker_permission_fix")
        assert docker_template is not None
        assert docker_template.name == "Docker権限エラー修正"
        assert docker_template.risk_level == "low"
        assert docker_template.success_rate == 0.95

        npm_template = manager.get_template_by_id("npm_package_fix")
        assert npm_template is not None
        assert npm_template.name == "NPMパッケージ不足修正"
        assert npm_template.risk_level == "medium"

    def test_get_template_for_pattern(self, template_manager_with_data, sample_pattern):
        """パターンに対応するテンプレート取得のテスト"""
        manager = template_manager_with_data

        template = manager.get_template_for_pattern(sample_pattern)

        assert template is not None
        assert template.id == "docker_permission_fix"
        assert "docker_permission_denied" in template.pattern_ids

    def test_get_templates_for_pattern(self, template_manager_with_data, sample_pattern):
        """パターンに対応するすべてのテンプレート取得のテスト"""
        manager = template_manager_with_data

        templates = manager.get_templates_for_pattern(sample_pattern)

        assert len(templates) == 1
        assert templates[0].id == "docker_permission_fix"

    def test_customize_template(self, template_manager_with_data, sample_pattern):
        """テンプレートカスタマイズのテスト"""
        manager = template_manager_with_data

        template = manager.get_template_for_pattern(sample_pattern)
        assert template is not None

        # カスタマイズ用のコンテキスト
        context = {
            "package_name": "express",
            "file_path": "/custom/path/.actrc",
            "user_name": "testuser",
        }

        # テンプレートをカスタマイズ
        fix_suggestion = manager.customize_template(template, context)

        # カスタマイズされた修正提案を確認
        assert fix_suggestion.title == template.name
        assert fix_suggestion.estimated_effort == template.estimated_time
        assert fix_suggestion.confidence == template.success_rate

        # 優先度が正しく変換されていることを確認
        assert fix_suggestion.priority == Priority.LOW  # risk_level "low" -> Priority.LOW

    def test_validate_template_success(self, template_manager_with_data):
        """テンプレート検証成功のテスト"""
        manager = template_manager_with_data

        template = manager.get_template_by_id("docker_permission_fix")
        assert template is not None

        is_valid = manager.validate_template(template)
        assert is_valid is True

    def test_validate_template_failure(self, template_manager_with_data):
        """テンプレート検証失敗のテスト"""
        manager = template_manager_with_data

        # 不正なテンプレートを作成
        invalid_template = FixTemplate(
            id="",  # 空のID（不正）
            name="",  # 空の名前（不正）
            description="テスト",
            pattern_ids=[],  # 空のパターンID（不正）
            fix_steps=[],  # 空の修正ステップ（不正）
            risk_level="invalid",  # 不正なリスクレベル
            estimated_time="5分",
            success_rate=1.5,  # 範囲外の成功率（不正）
        )

        is_valid = manager.validate_template(invalid_template)
        assert is_valid is False

    def test_validate_fix_step_success(self, template_manager_with_data):
        """修正ステップ検証成功のテスト"""
        manager = template_manager_with_data

        # 有効なファイル変更ステップ
        valid_file_step = FixStep(
            type="file_modification",
            description="ファイルを変更",
            file_path="test.txt",
            action="append",
            content="test content",
        )

        is_valid = manager._validate_fix_step(valid_file_step)
        assert is_valid is True

        # 有効なコマンドステップ
        valid_command_step = FixStep(
            type="command",
            description="コマンドを実行",
            command="npm install",
        )

        is_valid = manager._validate_fix_step(valid_command_step)
        assert is_valid is True

    def test_validate_fix_step_failure(self, template_manager_with_data):
        """修正ステップ検証失敗のテスト"""
        manager = template_manager_with_data

        # 不正なタイプ
        invalid_type_step = FixStep(
            type="invalid_type",
            description="不正なタイプ",
        )

        is_valid = manager._validate_fix_step(invalid_type_step)
        assert is_valid is False

        # 説明なし
        no_description_step = FixStep(
            type="file_modification",
            description="",
            file_path="test.txt",
            action="append",
        )

        is_valid = manager._validate_fix_step(no_description_step)
        assert is_valid is False

        # ファイル変更で必須フィールドなし
        incomplete_file_step = FixStep(
            type="file_modification",
            description="ファイル変更",
            # file_path と action が不足
        )

        is_valid = manager._validate_fix_step(incomplete_file_step)
        assert is_valid is False

        # 不正なアクション
        invalid_action_step = FixStep(
            type="file_modification",
            description="ファイル変更",
            file_path="test.txt",
            action="invalid_action",
        )

        is_valid = manager._validate_fix_step(invalid_action_step)
        assert is_valid is False

        # コマンドステップでコマンドなし
        no_command_step = FixStep(
            type="command",
            description="コマンド実行",
            # command が不足
        )

        is_valid = manager._validate_fix_step(no_command_step)
        assert is_valid is False

    def test_get_templates_by_risk_level(self, template_manager_with_data):
        """リスクレベル別テンプレート取得のテスト"""
        manager = template_manager_with_data

        # 低リスクテンプレート
        low_risk_templates = manager.get_templates_by_risk_level("low")
        assert len(low_risk_templates) == 1
        assert low_risk_templates[0].id == "docker_permission_fix"

        # 中リスクテンプレート
        medium_risk_templates = manager.get_templates_by_risk_level("medium")
        assert len(medium_risk_templates) == 1
        assert medium_risk_templates[0].id == "npm_package_fix"

        # 高リスクテンプレート（存在しない）
        high_risk_templates = manager.get_templates_by_risk_level("high")
        assert len(high_risk_templates) == 0

    def test_variable_substitution(self, template_manager_with_data):
        """変数置換のテスト"""
        manager = template_manager_with_data

        # 変数を含むテキスト
        text_with_variables = "Install package {package_name} in {directory} for user {user_name}"

        context = {
            "package_name": "express",
            "directory": "/home/user",
            "user_name": "testuser",
        }

        # 変数を置換
        substituted = manager._substitute_variables(text_with_variables, context)

        assert substituted == "Install package express in /home/user for user testuser"

    def test_variable_substitution_missing_variable(self, template_manager_with_data):
        """存在しない変数の置換テスト"""
        manager = template_manager_with_data

        text_with_missing_var = "Install {package_name} and {missing_variable}"

        context = {
            "package_name": "express",
        }

        # 存在しない変数はそのまま残る
        substituted = manager._substitute_variables(text_with_missing_var, context)

        assert substituted == "Install express and {missing_variable}"

    def test_risk_level_to_priority_conversion(self, template_manager_with_data):
        """リスクレベルから優先度への変換テスト"""
        manager = template_manager_with_data

        # 各リスクレベルの変換を確認
        assert manager._risk_level_to_priority("low") == Priority.LOW
        assert manager._risk_level_to_priority("medium") == Priority.MEDIUM
        assert manager._risk_level_to_priority("high") == Priority.HIGH

        # 大文字小文字の違いも処理される
        assert manager._risk_level_to_priority("LOW") == Priority.LOW
        assert manager._risk_level_to_priority("Medium") == Priority.MEDIUM

        # 不正な値はデフォルト（MEDIUM）になる
        assert manager._risk_level_to_priority("invalid") == Priority.MEDIUM

    def test_empty_template_directory(self, temp_template_dir):
        """空のテンプレートディレクトリのテスト"""
        manager = FixTemplateManager(temp_template_dir)

        # テンプレートが存在しないことを確認
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 0

        # 存在しないパターンでテンプレート取得
        pattern = Pattern(
            id="nonexistent_pattern",
            name="存在しないパターン",
            category="test",
            regex_patterns=[],
            keywords=[],
            context_requirements=[],
            confidence_base=0.5,
            success_rate=0.5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        template = manager.get_template_for_pattern(pattern)
        assert template is None

        templates = manager.get_templates_for_pattern(pattern)
        assert len(templates) == 0

    def test_nonexistent_template_directory(self):
        """存在しないテンプレートディレクトリのテスト"""
        nonexistent_dir = Path("/nonexistent/directory")
        manager = FixTemplateManager(nonexistent_dir)

        # エラーが発生せず、空の状態で初期化されることを確認
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 0

    def test_invalid_json_template_file(self, temp_template_dir):
        """不正なJSONテンプレートファイルのテスト"""
        # 不正なJSONファイルを作成
        invalid_json_file = temp_template_dir / "invalid.json"
        invalid_json_file.write_text("{ invalid json content", encoding="utf-8")

        # エラーが発生せず、無視されることを確認
        manager = FixTemplateManager(temp_template_dir)
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 0

    def test_template_file_without_templates_key(self, temp_template_dir):
        """templatesキーがないテンプレートファイルのテスト"""
        # templatesキーがないJSONファイルを作成
        invalid_structure = {"other_key": "value"}
        template_file = temp_template_dir / "no_templates_key.json"
        with template_file.open("w", encoding="utf-8") as f:
            json.dump(invalid_structure, f)

        # エラーが発生せず、無視されることを確認
        manager = FixTemplateManager(temp_template_dir)
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 0

    def test_reload_templates(self, temp_template_dir, sample_template_data):
        """テンプレート再読み込みのテスト"""
        # 最初は空のディレクトリ
        manager = FixTemplateManager(temp_template_dir)
        assert len(manager.get_all_templates()) == 0

        # テンプレートファイルを追加
        template_file = temp_template_dir / "new_templates.json"
        with template_file.open("w", encoding="utf-8") as f:
            json.dump(sample_template_data, f, ensure_ascii=False, indent=2)

        # 再読み込み
        manager.reload_templates()

        # テンプレートが読み込まれていることを確認
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 2

    def test_multiple_template_files(self, temp_template_dir):
        """複数のテンプレートファイルのテスト"""
        # 最初のテンプレートファイル
        template_data_1 = {
            "templates": [
                {
                    "id": "template_1",
                    "name": "テンプレート1",
                    "description": "テスト用テンプレート1",
                    "pattern_ids": ["pattern_1"],
                    "fix_steps": [
                        {
                            "type": "file_modification",
                            "description": "ファイル変更1",
                            "file_path": "file1.txt",
                            "action": "create",
                            "content": "content1",
                        }
                    ],
                    "risk_level": "low",
                    "estimated_time": "1分",
                    "success_rate": 0.9,
                }
            ]
        }

        # 2番目のテンプレートファイル
        template_data_2 = {
            "templates": [
                {
                    "id": "template_2",
                    "name": "テンプレート2",
                    "description": "テスト用テンプレート2",
                    "pattern_ids": ["pattern_2"],
                    "fix_steps": [
                        {
                            "type": "command",
                            "description": "コマンド実行2",
                            "command": "echo test2",
                        }
                    ],
                    "risk_level": "medium",
                    "estimated_time": "3分",
                    "success_rate": 0.8,
                }
            ]
        }

        # ファイルを作成
        template_file_1 = temp_template_dir / "templates_1.json"
        template_file_2 = temp_template_dir / "templates_2.json"

        with template_file_1.open("w", encoding="utf-8") as f:
            json.dump(template_data_1, f, ensure_ascii=False, indent=2)

        with template_file_2.open("w", encoding="utf-8") as f:
            json.dump(template_data_2, f, ensure_ascii=False, indent=2)

        # テンプレート管理を初期化
        manager = FixTemplateManager(temp_template_dir)

        # 両方のテンプレートが読み込まれていることを確認
        all_templates = manager.get_all_templates()
        assert len(all_templates) == 2

        template_ids = {template.id for template in all_templates}
        assert "template_1" in template_ids
        assert "template_2" in template_ids

    def test_template_with_multiple_patterns(self, temp_template_dir):
        """複数パターンに対応するテンプレートのテスト"""
        template_data = {
            "templates": [
                {
                    "id": "multi_pattern_template",
                    "name": "複数パターンテンプレート",
                    "description": "複数のパターンに対応するテンプレート",
                    "pattern_ids": ["pattern_1", "pattern_2", "pattern_3"],
                    "fix_steps": [
                        {
                            "type": "file_modification",
                            "description": "共通の修正",
                            "file_path": "common.txt",
                            "action": "create",
                            "content": "common fix",
                        }
                    ],
                    "risk_level": "low",
                    "estimated_time": "2分",
                    "success_rate": 0.85,
                }
            ]
        }

        template_file = temp_template_dir / "multi_pattern.json"
        with template_file.open("w", encoding="utf-8") as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)

        manager = FixTemplateManager(temp_template_dir)

        # 各パターンでテンプレートが取得できることを確認
        for pattern_id in ["pattern_1", "pattern_2", "pattern_3"]:
            pattern = Pattern(
                id=pattern_id,
                name=f"パターン{pattern_id}",
                category="test",
                regex_patterns=[],
                keywords=[],
                context_requirements=[],
                confidence_base=0.5,
                success_rate=0.5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            template = manager.get_template_for_pattern(pattern)
            assert template is not None
            assert template.id == "multi_pattern_template"

    def test_customize_fix_step(self, template_manager_with_data):
        """修正ステップのカスタマイズテスト"""
        manager = template_manager_with_data

        original_step = FixStep(
            type="file_modification",
            description="Install {package_name} in {directory}",
            file_path="{config_file}",
            action="append",
            content="package={package_name}",
            command=None,
            validation="Check {package_name} installation",
        )

        context = {
            "package_name": "express",
            "directory": "/home/user",
            "config_file": "package.json",
        }

        customized_step = manager._customize_fix_step(original_step, context)

        assert customized_step.description == "Install express in /home/user"
        assert customized_step.file_path == "package.json"
        assert customized_step.content == "package=express"
        assert customized_step.validation == "Check express installation"
        assert customized_step.type == original_step.type
        assert customized_step.action == original_step.action
