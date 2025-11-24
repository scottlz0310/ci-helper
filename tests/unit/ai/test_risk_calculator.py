"""
risk_calculator.py のテスト

リスクレベル計算と推定時間計算機能をテストします。
"""

import pytest
from ci_helper.ai.models import CodeChange, FixStep, FixSuggestion, FixTemplate, Priority
from ci_helper.ai.risk_calculator import RiskCalculator, TimeEstimator


class TestRiskCalculator:
    """RiskCalculator のテストクラス"""

    @pytest.fixture
    def risk_calculator(self):
        """RiskCalculator インスタンス"""
        return RiskCalculator()

    @pytest.fixture
    def sample_fix_suggestion(self):
        """サンプル修正提案"""
        code_change = CodeChange(
            file_path="src/main.py",
            line_start=10,
            line_end=15,
            old_code="old code",
            new_code="new code",
            description="Update main function",
        )

        return FixSuggestion(
            title="Fix main function",
            description="Update the main function to handle errors",
            code_changes=[code_change],
            priority=Priority.MEDIUM,
            confidence=0.8,
        )

    @pytest.fixture
    def sample_fix_template(self):
        """サンプル修正テンプレート"""
        fix_step = FixStep(
            type="file_modification",
            description="Update configuration",
            file_path="config.yaml",
            action="replace",
            content="new config",
        )

        return FixTemplate(
            id="template_1",
            name="Config Fix",
            description="Fix configuration issue",
            pattern_ids=["pattern_1"],
            fix_steps=[fix_step],
            risk_level="medium",
            estimated_time="10-15分",
            success_rate=0.85,
        )

    def test_init(self, risk_calculator):
        """初期化のテスト"""
        assert len(risk_calculator.critical_file_patterns) > 0
        assert len(risk_calculator.important_directory_patterns) > 0
        assert len(risk_calculator.high_risk_operations) > 0
        assert len(risk_calculator.medium_risk_operations) > 0

    def test_calculate_risk_level_low_risk(self, risk_calculator, sample_fix_suggestion):
        """低リスク修正提案のテスト"""
        # 低リスクの設定
        sample_fix_suggestion.confidence = 0.9
        sample_fix_suggestion.code_changes[0].file_path = "docs/README.md"
        sample_fix_suggestion.description = "Update documentation"

        risk_level = risk_calculator.calculate_risk_level(sample_fix_suggestion)

        assert risk_level == "low"

    def test_calculate_risk_level_medium_risk(self, risk_calculator, sample_fix_suggestion):
        """中リスク修正提案のテスト"""
        # 中リスクの設定
        sample_fix_suggestion.confidence = 0.7
        sample_fix_suggestion.code_changes[0].file_path = "src/config.py"
        sample_fix_suggestion.description = "Update configuration settings"

        risk_level = risk_calculator.calculate_risk_level(sample_fix_suggestion)

        assert risk_level == "medium"

    def test_calculate_risk_level_high_risk(self, risk_calculator, sample_fix_suggestion):
        """高リスク修正提案のテスト"""
        # 高リスクの設定
        sample_fix_suggestion.confidence = 0.4
        sample_fix_suggestion.code_changes[0].file_path = "package.json"
        sample_fix_suggestion.description = "Delete old dependencies and install new ones"

        risk_level = risk_calculator.calculate_risk_level(sample_fix_suggestion)

        assert risk_level == "high"

    def test_calculate_risk_level_with_template(self, risk_calculator, sample_fix_suggestion, sample_fix_template):
        """テンプレート付きリスク計算のテスト"""
        sample_fix_template.risk_level = "high"

        risk_level = risk_calculator.calculate_risk_level(sample_fix_suggestion, sample_fix_template)

        # テンプレートの高リスクが反映される
        assert risk_level in ["medium", "high"]

    def test_calculate_risk_level_with_context(self, risk_calculator, sample_fix_suggestion):
        """コンテキスト付きリスク計算のテスト"""
        context = {"environment": "production", "service_criticality": "high", "involves_database": True}

        risk_level = risk_calculator.calculate_risk_level(sample_fix_suggestion, context=context)

        # コンテキストによりリスクが上がる
        assert risk_level in ["medium", "high"]

    def test_get_base_risk_score(self, risk_calculator):
        """ベースリスクスコア取得のテスト"""
        assert risk_calculator._get_base_risk_score("low") == 0.2
        assert risk_calculator._get_base_risk_score("medium") == 0.5
        assert risk_calculator._get_base_risk_score("high") == 0.8
        assert risk_calculator._get_base_risk_score("unknown") == 0.5

    def test_calculate_file_risk_critical_file(self, risk_calculator, sample_fix_suggestion):
        """クリティカルファイルのリスク計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "package.json"

        risk_score = risk_calculator._calculate_file_risk(sample_fix_suggestion)

        assert risk_score > 0.0

    def test_calculate_file_risk_important_directory(self, risk_calculator, sample_fix_suggestion):
        """重要ディレクトリのリスク計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "src/main.py"

        risk_score = risk_calculator._calculate_file_risk(sample_fix_suggestion)

        assert risk_score > 0.0

    def test_calculate_file_risk_system_file(self, risk_calculator, sample_fix_suggestion):
        """システムファイルのリスク計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "/etc/hosts"

        risk_score = risk_calculator._calculate_file_risk(sample_fix_suggestion)

        assert risk_score > 0.0

    def test_calculate_file_risk_normal_file(self, risk_calculator, sample_fix_suggestion):
        """通常ファイルのリスク計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "docs/README.md"

        risk_score = risk_calculator._calculate_file_risk(sample_fix_suggestion)

        assert risk_score == 0.0

    def test_calculate_operation_risk_high_risk_operations(self, risk_calculator, sample_fix_suggestion):
        """高リスク操作のリスク計算テスト"""
        sample_fix_suggestion.description = "Delete old files and remove dependencies"
        sample_fix_suggestion.code_changes[0].new_code = "rm -rf old_files"

        risk_score = risk_calculator._calculate_operation_risk(sample_fix_suggestion)

        assert risk_score > 0.0

    def test_calculate_operation_risk_medium_risk_operations(self, risk_calculator, sample_fix_suggestion):
        """中リスク操作のリスク計算テスト"""
        sample_fix_suggestion.description = "Update and modify configuration"
        sample_fix_suggestion.code_changes[0].new_code = "chmod 644 config.yaml"

        risk_score = risk_calculator._calculate_operation_risk(sample_fix_suggestion)

        assert risk_score > 0.0

    def test_calculate_operation_risk_safe_operations(self, risk_calculator, sample_fix_suggestion):
        """安全な操作のリスク計算テスト"""
        sample_fix_suggestion.description = "Add documentation and comments"
        sample_fix_suggestion.code_changes[0].new_code = "# Add helpful comment"

        risk_score = risk_calculator._calculate_operation_risk(sample_fix_suggestion)

        assert risk_score == 0.0

    def test_calculate_scope_risk_single_file(self, risk_calculator, sample_fix_suggestion):
        """単一ファイル変更のスコープリスク計算テスト"""
        risk_score = risk_calculator._calculate_scope_risk(sample_fix_suggestion)

        assert risk_score == 0.05

    def test_calculate_scope_risk_multiple_files(self, risk_calculator, sample_fix_suggestion):
        """複数ファイル変更のスコープリスク計算テスト"""
        # 追加のコード変更を作成
        for i in range(4):  # 合計5ファイル
            code_change = CodeChange(
                file_path=f"src/file_{i}.py",
                line_start=1,
                line_end=5,
                old_code="old",
                new_code="new",
                description=f"Update file {i}",
            )
            sample_fix_suggestion.code_changes.append(code_change)

        risk_score = risk_calculator._calculate_scope_risk(sample_fix_suggestion)

        assert risk_score == 0.2

    def test_calculate_scope_risk_many_files(self, risk_calculator, sample_fix_suggestion):
        """多数ファイル変更のスコープリスク計算テスト"""
        # 追加のコード変更を作成（合計10ファイル）
        for i in range(9):
            code_change = CodeChange(
                file_path=f"src/file_{i}.py",
                line_start=1,
                line_end=5,
                old_code="old",
                new_code="new",
                description=f"Update file {i}",
            )
            sample_fix_suggestion.code_changes.append(code_change)

        risk_score = risk_calculator._calculate_scope_risk(sample_fix_suggestion)

        assert risk_score == 0.3

    def test_calculate_confidence_risk_high_confidence(self, risk_calculator):
        """高信頼度のリスク計算テスト"""
        risk_score = risk_calculator._calculate_confidence_risk(0.95)

        assert risk_score == 0.0

    def test_calculate_confidence_risk_medium_confidence(self, risk_calculator):
        """中信頼度のリスク計算テスト"""
        risk_score = risk_calculator._calculate_confidence_risk(0.75)

        assert risk_score == 0.1

    def test_calculate_confidence_risk_low_confidence(self, risk_calculator):
        """低信頼度のリスク計算テスト"""
        risk_score = risk_calculator._calculate_confidence_risk(0.3)

        assert risk_score == 0.3

    def test_calculate_context_risk_production(self, risk_calculator):
        """本番環境コンテキストのリスク計算テスト"""
        context = {"environment": "production"}

        risk_score = risk_calculator._calculate_context_risk(context)

        assert risk_score == 0.2

    def test_calculate_context_risk_high_criticality(self, risk_calculator):
        """高重要度サービスのリスク計算テスト"""
        context = {"service_criticality": "high"}

        risk_score = risk_calculator._calculate_context_risk(context)

        assert risk_score == 0.15

    def test_calculate_context_risk_database_involved(self, risk_calculator):
        """データベース関連のリスク計算テスト"""
        context = {"involves_database": True}

        risk_score = risk_calculator._calculate_context_risk(context)

        assert risk_score == 0.1

    def test_calculate_context_risk_combined(self, risk_calculator):
        """複合コンテキストのリスク計算テスト"""
        context = {"environment": "production", "service_criticality": "high", "involves_database": True}

        risk_score = risk_calculator._calculate_context_risk(context)

        # 最大0.3に制限される
        assert risk_score == 0.3

    def test_is_critical_file_package_json(self, risk_calculator):
        """package.jsonのクリティカルファイル判定テスト"""
        assert risk_calculator._is_critical_file("package.json") is True
        assert risk_calculator._is_critical_file("frontend/package.json") is True

    def test_is_critical_file_dockerfile(self, risk_calculator):
        """Dockerfileのクリティカルファイル判定テスト"""
        assert risk_calculator._is_critical_file("Dockerfile") is True
        assert risk_calculator._is_critical_file("docker/Dockerfile") is True

    def test_is_critical_file_workflow(self, risk_calculator):
        """GitHub Actionsワークフローのクリティカルファイル判定テスト"""
        assert risk_calculator._is_critical_file(".github/workflows/ci.yml") is True
        assert risk_calculator._is_critical_file(".github/workflows/deploy.yaml") is True

    def test_is_critical_file_normal_file(self, risk_calculator):
        """通常ファイルのクリティカルファイル判定テスト"""
        assert risk_calculator._is_critical_file("docs/README.md") is False
        assert risk_calculator._is_critical_file("tests/test_main.py") is False

    def test_is_important_directory_src(self, risk_calculator):
        """srcディレクトリの重要ディレクトリ判定テスト"""
        assert risk_calculator._is_important_directory("src/main.py") is True
        assert risk_calculator._is_important_directory("src/utils/helper.py") is True

    def test_is_important_directory_config(self, risk_calculator):
        """configディレクトリの重要ディレクトリ判定テスト"""
        assert risk_calculator._is_important_directory("config/app.yaml") is True
        assert risk_calculator._is_important_directory("config/database.json") is True

    def test_is_important_directory_normal(self, risk_calculator):
        """通常ディレクトリの重要ディレクトリ判定テスト"""
        assert risk_calculator._is_important_directory("docs/README.md") is False
        assert risk_calculator._is_important_directory("tests/test_main.py") is False

    def test_is_system_file_unix(self, risk_calculator):
        """Unixシステムファイルの判定テスト"""
        assert risk_calculator._is_system_file("/etc/hosts") is True
        assert risk_calculator._is_system_file("/usr/bin/python") is True
        assert risk_calculator._is_system_file("/var/log/app.log") is True

    def test_is_system_file_windows(self, risk_calculator):
        """Windowsシステムファイルの判定テスト"""
        assert risk_calculator._is_system_file("C:\\Windows\\System32\\cmd.exe") is True
        assert risk_calculator._is_system_file("C:\\Program Files\\App\\app.exe") is True

    def test_is_system_file_normal(self, risk_calculator):
        """通常ファイルのシステムファイル判定テスト"""
        assert risk_calculator._is_system_file("src/main.py") is False
        assert risk_calculator._is_system_file("config/app.yaml") is False

    def test_score_to_risk_level_low(self, risk_calculator):
        """低スコアのリスクレベル変換テスト"""
        assert risk_calculator._score_to_risk_level(0.2) == "low"
        assert risk_calculator._score_to_risk_level(0.39) == "low"

    def test_score_to_risk_level_medium(self, risk_calculator):
        """中スコアのリスクレベル変換テスト"""
        assert risk_calculator._score_to_risk_level(0.4) == "medium"
        assert risk_calculator._score_to_risk_level(0.69) == "medium"

    def test_score_to_risk_level_high(self, risk_calculator):
        """高スコアのリスクレベル変換テスト"""
        assert risk_calculator._score_to_risk_level(0.7) == "high"
        assert risk_calculator._score_to_risk_level(1.0) == "high"


class TestTimeEstimator:
    """TimeEstimator のテストクラス"""

    @pytest.fixture
    def time_estimator(self):
        """TimeEstimator インスタンス"""
        return TimeEstimator()

    @pytest.fixture
    def sample_fix_suggestion(self):
        """サンプル修正提案"""
        code_change = CodeChange(
            file_path="src/main.py",
            line_start=10,
            line_end=15,
            old_code="old code",
            new_code="new code",
            description="Update main function",
        )

        return FixSuggestion(
            title="Fix main function",
            description="Update the main function",
            code_changes=[code_change],
            confidence=0.8,
        )

    @pytest.fixture
    def sample_fix_template(self):
        """サンプル修正テンプレート"""
        return FixTemplate(
            id="template_1",
            name="Config Fix",
            description="Fix configuration issue",
            pattern_ids=["pattern_1"],
            fix_steps=[],
            risk_level="medium",
            estimated_time="15分",
            success_rate=0.85,
        )

    def test_init(self, time_estimator):
        """初期化のテスト"""
        assert len(time_estimator.base_times) > 0
        assert len(time_estimator.complexity_factors) > 0
        assert "file_modification" in time_estimator.base_times
        assert ".py" in time_estimator.complexity_factors

    def test_estimate_fix_time_with_template(self, time_estimator, sample_fix_suggestion, sample_fix_template):
        """テンプレート付き時間推定のテスト"""
        estimated_time = time_estimator.estimate_fix_time(sample_fix_suggestion, sample_fix_template)

        assert "分" in estimated_time or "時間" in estimated_time

    def test_estimate_fix_time_without_template(self, time_estimator, sample_fix_suggestion):
        """テンプレートなし時間推定のテスト"""
        estimated_time = time_estimator.estimate_fix_time(sample_fix_suggestion)

        assert "分" in estimated_time or "時間" in estimated_time

    def test_estimate_fix_time_with_context(self, time_estimator, sample_fix_suggestion):
        """コンテキスト付き時間推定のテスト"""
        context = {"environment": "production", "project_size": "large", "team_experience": "low"}

        estimated_time = time_estimator.estimate_fix_time(sample_fix_suggestion, context=context)

        assert "分" in estimated_time or "時間" in estimated_time

    def test_parse_time_string_minutes(self, time_estimator):
        """分単位時間文字列解析のテスト"""
        assert time_estimator._parse_time_string("15分") == 15.0
        assert time_estimator._parse_time_string("30 minutes") == 30.0

    def test_parse_time_string_hours(self, time_estimator):
        """時間単位時間文字列解析のテスト"""
        assert time_estimator._parse_time_string("2時間") == 120.0
        assert time_estimator._parse_time_string("1 hour") == 60.0

    def test_parse_time_string_days(self, time_estimator):
        """日単位時間文字列解析のテスト"""
        assert time_estimator._parse_time_string("1日") == 480.0  # 8時間 * 60分
        assert time_estimator._parse_time_string("2 days") == 960.0

    def test_parse_time_string_range(self, time_estimator):
        """範囲時間文字列解析のテスト"""
        assert time_estimator._parse_time_string("10-20分") == 15.0  # 平均
        assert time_estimator._parse_time_string("1-2時間") == 90.0  # 1.5時間 * 60分

    def test_parse_time_string_invalid(self, time_estimator):
        """無効な時間文字列解析のテスト"""
        assert time_estimator._parse_time_string("invalid") == 30.0  # デフォルト値

    def test_calculate_base_time_single_change(self, time_estimator, sample_fix_suggestion):
        """単一変更の基本時間計算テスト"""
        base_time = time_estimator._calculate_base_time(sample_fix_suggestion)

        assert base_time >= 5.0  # 最小5分

    def test_calculate_base_time_no_changes(self, time_estimator, sample_fix_suggestion):
        """変更なしの基本時間計算テスト"""
        sample_fix_suggestion.code_changes = []

        base_time = time_estimator._calculate_base_time(sample_fix_suggestion)

        assert base_time == time_estimator.base_times["config_change"]

    def test_calculate_base_time_with_install(self, time_estimator, sample_fix_suggestion):
        """インストール含む基本時間計算テスト"""
        sample_fix_suggestion.description = "Install new dependency"

        base_time = time_estimator._calculate_base_time(sample_fix_suggestion)

        assert base_time >= time_estimator.base_times["dependency_install"]

    def test_calculate_base_time_with_build(self, time_estimator, sample_fix_suggestion):
        """ビルド含む基本時間計算テスト"""
        sample_fix_suggestion.description = "Build the application"

        base_time = time_estimator._calculate_base_time(sample_fix_suggestion)

        assert base_time >= time_estimator.base_times["build"]

    def test_calculate_complexity_factor_python(self, time_estimator, sample_fix_suggestion):
        """Python ファイルの複雑度係数計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "src/main.py"

        factor = time_estimator._calculate_complexity_factor(sample_fix_suggestion)

        assert factor >= time_estimator.complexity_factors[".py"]

    def test_calculate_complexity_factor_typescript(self, time_estimator, sample_fix_suggestion):
        """TypeScript ファイルの複雑度係数計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "src/main.ts"

        factor = time_estimator._calculate_complexity_factor(sample_fix_suggestion)

        assert factor >= time_estimator.complexity_factors[".ts"]

    def test_calculate_complexity_factor_yaml(self, time_estimator, sample_fix_suggestion):
        """YAML ファイルの複雑度係数計算テスト"""
        sample_fix_suggestion.code_changes[0].file_path = "config.yaml"

        factor = time_estimator._calculate_complexity_factor(sample_fix_suggestion)

        assert factor <= 1.0  # YAMLは複雑度が低い

    def test_calculate_complexity_factor_no_changes(self, time_estimator, sample_fix_suggestion):
        """変更なしの複雑度係数計算テスト"""
        sample_fix_suggestion.code_changes = []

        factor = time_estimator._calculate_complexity_factor(sample_fix_suggestion)

        assert factor == 1.0

    def test_calculate_context_factor_production(self, time_estimator):
        """本番環境コンテキスト係数計算テスト"""
        context = {"environment": "production"}

        factor = time_estimator._calculate_context_factor(context)

        assert factor == 1.5

    def test_calculate_context_factor_large_project(self, time_estimator):
        """大規模プロジェクトコンテキスト係数計算テスト"""
        context = {"project_size": "large"}

        factor = time_estimator._calculate_context_factor(context)

        assert factor == 1.3

    def test_calculate_context_factor_low_experience(self, time_estimator):
        """低経験チームコンテキスト係数計算テスト"""
        context = {"team_experience": "low"}

        factor = time_estimator._calculate_context_factor(context)

        assert factor == 1.4

    def test_calculate_context_factor_high_experience(self, time_estimator):
        """高経験チームコンテキスト係数計算テスト"""
        context = {"team_experience": "high"}

        factor = time_estimator._calculate_context_factor(context)

        assert factor == 0.8

    def test_calculate_confidence_factor_high_confidence(self, time_estimator):
        """高信頼度の時間係数計算テスト"""
        factor = time_estimator._calculate_confidence_factor(0.95)

        assert factor == 1.0

    def test_calculate_confidence_factor_medium_confidence(self, time_estimator):
        """中信頼度の時間係数計算テスト"""
        factor = time_estimator._calculate_confidence_factor(0.75)

        assert factor == 1.5

    def test_calculate_confidence_factor_low_confidence(self, time_estimator):
        """低信頼度の時間係数計算テスト"""
        factor = time_estimator._calculate_confidence_factor(0.3)

        assert factor == 3.0

    def test_format_time_range_minutes(self, time_estimator):
        """分単位時間範囲フォーマットテスト"""
        result = time_estimator._format_time_range(30.0)

        assert "分" in result
        assert "-" in result

    def test_format_time_range_hours(self, time_estimator):
        """時間単位時間範囲フォーマットテスト"""
        result = time_estimator._format_time_range(120.0)  # 2時間

        assert "時間" in result
        assert "-" in result

    def test_format_time_range_days(self, time_estimator):
        """日単位時間範囲フォーマットテスト"""
        result = time_estimator._format_time_range(600.0)  # 10時間

        assert "日" in result
        assert "-" in result

    def test_format_time_range_mixed_units(self, time_estimator):
        """混合単位時間範囲フォーマットテスト"""
        result = time_estimator._format_time_range(45.0)  # 45分

        # 36分-54分 または 36分-0.9時間 のような形式
        assert ("分" in result) or ("時間" in result)
        assert "-" in result
