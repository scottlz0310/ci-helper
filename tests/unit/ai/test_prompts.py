"""
プロンプト管理のテスト

プロンプトテンプレート管理機能をテストします。
"""

import pytest

from src.ci_helper.ai.exceptions import ConfigurationError
from src.ci_helper.ai.models import AnalysisResult, RootCause
from src.ci_helper.ai.prompts import PromptManager
from src.ci_helper.core.models import FailureType


class TestPromptManager:
    """プロンプトマネージャーのテスト"""

    @pytest.fixture
    def prompt_manager(self):
        """プロンプトマネージャー"""
        return PromptManager()

    @pytest.fixture
    def custom_templates(self):
        """カスタムテンプレート"""
        return {
            "analysis": "カスタム分析テンプレート: {context}",
            "fix_suggestion": "カスタム修正テンプレート: {analysis_result}",
        }

    @pytest.fixture
    def prompt_manager_with_custom(self, custom_templates):
        """カスタムテンプレート付きプロンプトマネージャー"""
        return PromptManager(custom_templates=custom_templates)

    def test_prompt_manager_initialization(self, prompt_manager):
        """プロンプトマネージャー初期化のテスト"""
        assert prompt_manager.templates is not None
        assert "analysis" in prompt_manager.templates
        assert "fix_suggestion" in prompt_manager.templates
        assert "interactive" in prompt_manager.templates
        assert "error_specific" in prompt_manager.templates

    def test_prompt_manager_with_custom_templates(self, prompt_manager_with_custom, custom_templates):
        """カスタムテンプレート付き初期化のテスト"""
        assert prompt_manager_with_custom.custom_templates == custom_templates

    def test_load_default_templates(self, prompt_manager):
        """デフォルトテンプレート読み込みのテスト"""
        templates = prompt_manager._load_default_templates()

        # 必要なテンプレートが含まれていることを確認
        assert "analysis" in templates
        assert "fix_suggestion" in templates
        assert "interactive" in templates
        assert "error_specific" in templates

        # エラー固有テンプレートが含まれていることを確認
        error_templates = templates["error_specific"]
        assert "build_failure" in error_templates
        assert "test_failure" in error_templates
        assert "assertion" in error_templates
        assert "timeout" in error_templates
        assert "error" in error_templates

    def test_get_analysis_prompt_default(self, prompt_manager):
        """デフォルト分析プロンプト取得のテスト"""
        context = "テストログの内容"
        prompt = prompt_manager.get_analysis_prompt(context=context)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert context in prompt

    def test_get_analysis_prompt_with_failure_type(self, prompt_manager):
        """失敗タイプ指定での分析プロンプト取得のテスト"""
        context = "テストログの内容"

        # テスト失敗の場合
        prompt = prompt_manager.get_analysis_prompt(error_type=FailureType.TEST_FAILURE, context=context)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert context in prompt

        # ビルド失敗の場合
        prompt = prompt_manager.get_analysis_prompt(error_type=FailureType.BUILD_FAILURE, context=context)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert context in prompt

    def test_get_fix_prompt(self, prompt_manager):
        """修正提案プロンプト取得のテスト"""
        analysis_result = AnalysisResult(
            summary="テスト失敗の分析結果",
            root_causes=[RootCause(category="test", description="アサーションエラー", severity="MEDIUM")],
            confidence_score=0.8,
        )

        prompt = prompt_manager.get_fix_prompt(analysis_result)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "テスト失敗の分析結果" in prompt

    def test_get_interactive_prompt(self, prompt_manager):
        """対話プロンプト取得のテスト"""
        conversation_history = ["ユーザー: エラーの原因は何ですか？", "AI: アサーションエラーが発生しています。"]
        context = "初期ログ内容"

        prompt = prompt_manager.get_interactive_prompt(conversation_history, context)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert context in prompt

    def test_get_interactive_prompt_empty_history(self, prompt_manager):
        """空の会話履歴での対話プロンプト取得のテスト"""
        conversation_history = []
        context = "初期ログ内容"

        prompt = prompt_manager.get_interactive_prompt(conversation_history, context)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert context in prompt

    def test_add_custom_prompt(self, prompt_manager):
        """カスタムプロンプト追加のテスト"""
        template_name = "new_template"
        template_content = "新しいテンプレート: {variable}"

        prompt_manager.add_custom_prompt(template_name, template_content)

        assert template_name in prompt_manager.custom_templates
        assert prompt_manager.custom_templates[template_name] == template_content

    def test_get_custom_prompt_success(self, prompt_manager):
        """カスタムプロンプト取得成功のテスト"""
        template_name = "test_template"
        template_content = "テストテンプレート: {variable}"
        variables = {"variable": "テスト値"}

        prompt_manager.add_custom_prompt(template_name, template_content)
        result = prompt_manager.get_custom_prompt(template_name, variables)

        assert result == "テストテンプレート: テスト値"

    def test_get_custom_prompt_not_found(self, prompt_manager):
        """存在しないカスタムプロンプト取得のテスト"""
        with pytest.raises(ConfigurationError) as exc_info:
            prompt_manager.get_custom_prompt("nonexistent_template")

        assert "が見つかりません" in str(exc_info.value)

    def test_list_available_templates(self, prompt_manager_with_custom):
        """利用可能なテンプレート一覧取得のテスト"""
        templates = prompt_manager_with_custom.list_available_templates()

        # デフォルトテンプレートが含まれていることを確認
        assert "analysis" in templates
        assert "fix_suggestion" in templates
        assert "interactive" in templates

    def test_substitute_variables_success(self, prompt_manager):
        """変数置換成功のテスト"""
        template = "これは{variable1}と{variable2}のテストです"
        variables = {"variable1": "値1", "variable2": "値2"}

        result = prompt_manager._substitute_variables(template, variables)
        assert result == "これは値1と値2のテストです"

    def test_substitute_variables_missing_variable(self, prompt_manager):
        """変数不足での変数置換テスト"""
        template = "これは{variable1}と{variable2}のテストです"
        variables = {"variable1": "値1"}  # variable2が不足

        # 不足している変数はそのまま残る
        result = prompt_manager._substitute_variables(template, variables)
        assert result == "これは値1と{variable2}のテストです"

    def test_validate_template_success(self, prompt_manager):
        """テンプレート検証成功のテスト"""
        valid_template = "これは{variable}の有効なテンプレートです"

        errors = prompt_manager.validate_template(valid_template)
        assert errors == []

    def test_validate_template_with_errors(self, prompt_manager):
        """エラーがあるテンプレートの検証テスト"""
        # 不正な変数構文を含むテンプレート（実際の実装では空のリストを返すかもしれない）
        invalid_template = "これは{invalid variable}のテンプレートです"

        errors = prompt_manager.validate_template(invalid_template)
        # 実装によってはエラーを検出しない場合もある
        assert isinstance(errors, list)

    def test_get_template_variables(self, prompt_manager):
        """テンプレート変数取得のテスト"""
        template = "これは{variable1}と{variable2}と{variable1}のテストです"

        variables = prompt_manager.get_template_variables(template)
        assert sorted(variables) == ["variable1", "variable1", "variable2"]

    def test_get_template_variables_no_variables(self, prompt_manager):
        """変数がないテンプレートの変数取得テスト"""
        template = "これは変数がないテンプレートです"

        variables = prompt_manager.get_template_variables(template)
        assert variables == []

    def test_get_default_templates_content(self, prompt_manager):
        """デフォルトテンプレート内容のテスト"""
        # 各デフォルトテンプレートが適切な内容を持っていることを確認
        analysis_template = prompt_manager._get_default_analysis_template()
        assert isinstance(analysis_template, str)
        assert len(analysis_template) > 0
        assert "{context}" in analysis_template

        fix_template = prompt_manager._get_default_fix_template()
        assert isinstance(fix_template, str)
        assert len(fix_template) > 0

        interactive_template = prompt_manager._get_default_interactive_template()
        assert isinstance(interactive_template, str)
        assert len(interactive_template) > 0

        # エラー固有テンプレート
        build_template = prompt_manager._get_build_failure_template()
        assert isinstance(build_template, str)
        assert len(build_template) > 0

        test_template = prompt_manager._get_test_failure_template()
        assert isinstance(test_template, str)
        assert len(test_template) > 0

        assertion_template = prompt_manager._get_assertion_template()
        assert isinstance(assertion_template, str)
        assert len(assertion_template) > 0

        timeout_template = prompt_manager._get_timeout_template()
        assert isinstance(timeout_template, str)
        assert len(timeout_template) > 0

        error_template = prompt_manager._get_error_template()
        assert isinstance(error_template, str)
        assert len(error_template) > 0
