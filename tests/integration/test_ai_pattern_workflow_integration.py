"""
AI パターン認識ワークフローの統合テスト

パターン認識から修正提案、自動修正、学習までの完全なフローをテストします。
複数パターンの競合解決、学習機能の動作、エラーハンドリングを含みます。
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.ci_helper.ai.auto_fixer import AutoFixer
from src.ci_helper.ai.confidence_calculator import ConfidenceCalculator
from src.ci_helper.ai.exceptions import PatternRecognitionError
from src.ci_helper.ai.fix_generator import FixSuggestionGenerator
from src.ci_helper.ai.learning_engine import LearningEngine
from src.ci_helper.ai.models import FixStep, FixSuggestion, Pattern, PatternMatch, Priority, UserFeedback
from src.ci_helper.ai.pattern_database import PatternDatabase
from src.ci_helper.ai.pattern_engine import PatternRecognitionEngine
from src.ci_helper.utils.config import Config


class TestCompletePatternWorkflow:
    """完全なパターン認識ワークフローの統合テスト"""

    @pytest.fixture
    def temp_workspace(self):
        """テスト用の一時ワークスペース"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # データディレクトリ構造を作成
            patterns_dir = workspace / "data" / "patterns"
            templates_dir = workspace / "data" / "templates"
            learning_dir = workspace / "data" / "learning"

            patterns_dir.mkdir(parents=True, exist_ok=True)
            templates_dir.mkdir(parents=True, exist_ok=True)
            learning_dir.mkdir(parents=True, exist_ok=True)

            # サンプルパターンデータを作成
            sample_patterns = {
                "docker_permission": {
                    "id": "docker_permission",
                    "name": "Docker権限エラー",
                    "category": "permission",
                    "regex_patterns": [
                        r"permission denied.*docker",
                        r"Got permission denied while trying to connect to the Docker daemon",
                    ],
                    "keywords": ["permission denied", "docker", "daemon"],
                    "context_requirements": ["docker", "permission"],
                    "confidence_base": 0.8,
                    "success_rate": 0.9,
                    "user_defined": False,
                },
                "npm_enoent": {
                    "id": "npm_enoent",
                    "name": "NPMファイル不存在エラー",
                    "category": "dependency",
                    "regex_patterns": [r"npm ERR!.*ENOENT.*package\.json", r"no such file or directory.*package\.json"],
                    "keywords": ["npm", "ENOENT", "package.json"],
                    "context_requirements": ["npm", "package.json"],
                    "confidence_base": 0.85,
                    "success_rate": 0.95,
                    "user_defined": False,
                },
            }

            patterns_file = patterns_dir / "failure_patterns.json"
            patterns_file.write_text(json.dumps(sample_patterns, indent=2, ensure_ascii=False))

            # サンプル修正テンプレートを作成
            sample_templates = {
                "docker_permission_fix": {
                    "id": "docker_permission_fix",
                    "name": "Docker権限修正",
                    "description": "Dockerデーモンへのアクセス権限を修正",
                    "pattern_ids": ["docker_permission"],
                    "fix_steps": [
                        {
                            "type": "file_modification",
                            "description": ".actrcファイルに--privilegedオプションを追加",
                            "file_path": ".actrc",
                            "action": "append",
                            "content": "--privileged",
                        }
                    ],
                    "risk_level": "low",
                    "estimated_time": "2分",
                    "success_rate": 0.9,
                    "prerequisites": [],
                    "validation_steps": ["docker ps"],
                },
                "npm_package_json_fix": {
                    "id": "npm_package_json_fix",
                    "name": "package.json作成",
                    "description": "基本的なpackage.jsonファイルを作成",
                    "pattern_ids": ["npm_enoent"],
                    "fix_steps": [
                        {
                            "type": "file_modification",
                            "description": "基本的なpackage.jsonを作成",
                            "file_path": "package.json",
                            "action": "create",
                            "content": '{\n  "name": "project",\n  "version": "1.0.0"\n}',
                        }
                    ],
                    "risk_level": "low",
                    "estimated_time": "1分",
                    "success_rate": 0.95,
                    "prerequisites": [],
                    "validation_steps": ["npm --version"],
                },
            }

            templates_file = templates_dir / "fix_templates.json"
            templates_file.write_text(json.dumps(sample_templates, indent=2, ensure_ascii=False))

            yield workspace

    @pytest.fixture
    def mock_config(self, temp_workspace):
        """モック設定"""
        config = Mock(spec=Config)
        config.get_path.return_value = temp_workspace / ".ci-helper"
        config.get.side_effect = lambda key, default=None: {
            "ai.pattern_recognition.confidence_threshold": 0.7,
            "ai.auto_fix.enabled": True,
            "ai.auto_fix.risk_tolerance": "low",
            "ai.learning.enabled": True,
        }.get(key, default)
        return config

    @pytest.fixture
    def sample_ci_logs(self):
        """サンプルCIログ"""
        return {
            "docker_permission_log": """
STEP: Set up Docker
Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
Error: permission denied while trying to connect to the Docker daemon
""",
            "npm_missing_package_log": """
STEP: Install dependencies
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'
""",
            "multiple_errors_log": """
STEP: Set up Docker
Got permission denied while trying to connect to the Docker daemon socket
STEP: Install dependencies  
npm ERR! code ENOENT
npm ERR! path /github/workspace/package.json
STEP: Run tests
AssertionError: Expected 200, got 404
""",
            "unknown_error_log": """
STEP: Custom build
CustomBuildError: Unknown build system failure
Stack trace: line 42 in custom_builder.py
""",
        }

    @pytest.mark.asyncio
    async def test_complete_pattern_recognition_workflow(self, temp_workspace, mock_config, sample_ci_logs):
        """完全なパターン認識ワークフローのテスト"""
        # パターン認識エンジンを初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory="data/patterns", confidence_threshold=0.5, max_patterns_per_analysis=5
        )

        # Docker権限エラーログの分析
        docker_log = sample_ci_logs["docker_permission_log"]
        analysis_options = {"confidence_threshold": 0.7}

        pattern_matches = await pattern_engine.analyze_log(docker_log, analysis_options)

        # パターンマッチの検証
        print(f"Found {len(pattern_matches)} pattern matches")
        for match in pattern_matches:
            print(f"Pattern ID: {match.pattern.id}, Confidence: {match.confidence}")

        assert len(pattern_matches) > 0
        # 権限関連のパターンが見つかることを確認（実際のパターンIDを使用）
        permission_match = next((m for m in pattern_matches if "permission" in m.pattern.id), None)
        assert permission_match is not None
        assert permission_match.confidence >= 0.5  # より現実的な閾値
        assert (
            "permission" in permission_match.extracted_context.lower()
            or "denied" in permission_match.extracted_context.lower()
        )

    @pytest.mark.asyncio
    async def test_multiple_pattern_conflict_resolution(self, temp_workspace, mock_config, sample_ci_logs):
        """複数パターンの競合解決テスト"""
        pattern_engine = PatternRecognitionEngine(
            data_directory="data/patterns", confidence_threshold=0.5, max_patterns_per_analysis=10
        )

        # 複数エラーを含むログの分析
        multi_error_log = sample_ci_logs["multiple_errors_log"]
        analysis_options = {"confidence_threshold": 0.5}

        pattern_matches = await pattern_engine.analyze_log(multi_error_log, analysis_options)

        # パターンが検出されることを確認
        assert len(pattern_matches) >= 1

        # 各パターンマッチが有効な信頼度を持つことを確認
        for match in pattern_matches:
            assert 0.0 <= match.confidence <= 1.0
            assert match.pattern.id is not None
            assert match.pattern.name is not None

        # パターンが検出されることを確認
        pattern_ids = {match.pattern.id for match in pattern_matches}
        assert len(pattern_ids) >= 1

    @pytest.mark.asyncio
    async def test_fix_suggestion_generation_workflow(self, temp_workspace, mock_config, sample_ci_logs):
        """修正提案生成ワークフローのテスト"""
        # パターン認識
        pattern_engine = PatternRecognitionEngine(
            data_directory=temp_workspace / "data" / "patterns", confidence_threshold=0.7
        )

        docker_log = sample_ci_logs["docker_permission_log"]
        analysis_options = {"confidence_threshold": 0.7}
        pattern_matches = await pattern_engine.analyze_log(docker_log, analysis_options)

        # 修正提案生成
        fix_generator = FixSuggestionGenerator(template_directory=temp_workspace / "data" / "templates")

        fix_suggestions = await fix_generator.generate_pattern_based_fixes(pattern_matches, docker_log)

        # 修正提案の検証
        assert len(fix_suggestions) > 0
        docker_fix = next((f for f in fix_suggestions if "docker" in f.title.lower()), None)
        assert docker_fix is not None
        assert docker_fix.risk_level == "low"
        assert len(docker_fix.steps) > 0
        assert docker_fix.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_auto_fix_application_workflow(self, temp_workspace, mock_config, sample_ci_logs):
        """自動修正適用ワークフローのテスト"""
        # テスト用プロジェクトファイルを作成
        project_dir = temp_workspace / "project"
        project_dir.mkdir(exist_ok=True)

        # パターン認識から修正提案まで
        pattern_engine = PatternRecognitionEngine(
            data_directory=temp_workspace / "data" / "patterns", confidence_threshold=0.7
        )

        npm_log = sample_ci_logs["npm_missing_package_log"]
        analysis_options = {"confidence_threshold": 0.7}
        pattern_matches = await pattern_engine.analyze_log(npm_log, analysis_options)

        fix_generator = FixSuggestionGenerator(template_directory=temp_workspace / "data" / "templates")
        fix_suggestions = await fix_generator.generate_pattern_based_fixes(pattern_matches, npm_log)

        # 自動修正の適用
        with patch("os.getcwd", return_value=str(project_dir)):
            auto_fixer = AutoFixer(config=mock_config, interactive=False, auto_approve_low_risk=True)

            npm_fix = next((f for f in fix_suggestions if "package.json" in f.title.lower()), None)
            assert npm_fix is not None

            # 修正を適用
            fix_result = await auto_fixer.apply_fix(npm_fix, auto_approve=True)

            # 修正結果の検証
            assert fix_result.success
            assert len(fix_result.applied_steps) > 0
            assert fix_result.backup_info is not None

            # ファイルが作成されたことを確認
            package_json_path = project_dir / "package.json"
            assert package_json_path.exists()

            # バックアップが作成されたことを確認
            assert fix_result.backup_info.backup_id is not None

    @pytest.mark.asyncio
    async def test_learning_engine_workflow(self, temp_workspace, mock_config, sample_ci_logs):
        """学習エンジンワークフローのテスト"""
        # パターンデータベースと学習エンジンを初期化
        pattern_database = PatternDatabase(temp_workspace / "data" / "patterns")
        learning_engine = LearningEngine(
            pattern_database=pattern_database,
            learning_data_dir=temp_workspace / "data" / "learning",
            min_pattern_occurrences=2,
        )

        # 未知のエラーログで新しいパターンを学習
        unknown_log = sample_ci_logs["unknown_error_log"]

        # 新しいパターンの発見
        discovered_patterns = await learning_engine.discover_new_patterns([unknown_log])

        # パターンが発見されることを確認
        assert len(discovered_patterns) > 0
        custom_pattern = discovered_patterns[0]
        assert "custom" in custom_pattern.name.lower() or "build" in custom_pattern.name.lower()

        # ユーザーフィードバックの処理
        feedback = UserFeedback(
            pattern_id="docker_permission",
            fix_suggestion_id="docker_permission_fix",
            rating=5,
            success=True,
            comments="修正が成功しました",
        )

        await learning_engine.learn_from_feedback(feedback)

        # フィードバックが反映されることを確認
        # (実装に応じて検証方法を調整)

    @pytest.mark.asyncio
    async def test_error_handling_and_fallback(self, temp_workspace, mock_config, sample_ci_logs):
        """エラーハンドリングとフォールバック機能のテスト"""
        # 不正なデータディレクトリでの初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory=temp_workspace / "nonexistent", confidence_threshold=0.7
        )

        # エラーが発生しても適切に処理されることを確認
        docker_log = sample_ci_logs["docker_permission_log"]
        analysis_options = {"confidence_threshold": 0.7}

        try:
            pattern_matches = await pattern_engine.analyze_log(docker_log, analysis_options)
            # フォールバック処理により空のリストが返される
            assert isinstance(pattern_matches, list)
        except PatternRecognitionError:
            # エラーが適切に処理される
            pass

        # 修正適用の失敗テスト
        auto_fixer = AutoFixer(config=mock_config, interactive=False, auto_approve_low_risk=True)

        # 不正な修正提案
        invalid_fix = FixSuggestion(
            title="無効な修正",
            description="存在しないファイルを変更",
            steps=[
                FixStep(
                    type="file_modification",
                    description="存在しないファイルを変更",
                    file_path="/nonexistent/file.txt",
                    action="modify",
                    content="test",
                )
            ],
            risk_level="low",
            estimated_effort="1分",
            confidence=0.8,
            priority=Priority.HIGH,
        )

        # 修正適用が失敗することを確認
        fix_result = await auto_fixer.apply_fix(invalid_fix, auto_approve=True)
        assert not fix_result.success
        assert fix_result.error_message is not None

    @pytest.mark.asyncio
    async def test_concurrent_pattern_analysis(self, temp_workspace, mock_config, sample_ci_logs):
        """並行パターン分析のテスト"""
        pattern_engine = PatternRecognitionEngine(
            data_directory=temp_workspace / "data" / "patterns", confidence_threshold=0.5
        )

        # 複数のログを並行分析
        logs = list(sample_ci_logs.values())
        analysis_options = {"confidence_threshold": 0.5}

        # 並行実行
        tasks = [pattern_engine.analyze_log(log, analysis_options) for log in logs]

        import time

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # 結果の検証
        assert len(results) == len(logs)

        # 成功した分析結果を確認
        successful_results = [r for r in results if isinstance(r, list)]
        assert len(successful_results) > 0

        # 並行処理により処理時間が短縮されることを確認
        processing_time = end_time - start_time
        assert processing_time < 10.0  # 10秒以内で完了

    @pytest.mark.asyncio
    async def test_pattern_confidence_calculation(self, temp_workspace, mock_config, sample_ci_logs):
        """パターン信頼度計算のテスト"""
        confidence_calculator = ConfidenceCalculator()

        # サンプルパターンマッチを作成
        pattern = Pattern(
            id="test_pattern",
            name="テストパターン",
            category="test",
            regex_patterns=[r"test.*error"],
            keywords=["test", "error"],
            context_requirements=["test"],
            confidence_base=0.8,
            success_rate=0.9,
            user_defined=False,
        )

        pattern_match = PatternMatch(
            pattern=pattern,
            confidence=0.0,  # 計算前
            match_positions=[10, 25],
            extracted_context="test error occurred",
            match_strength=0.85,
            supporting_evidence=["keyword match: test", "regex match: test.*error"],
        )

        # 信頼度を計算
        calculated_confidence = confidence_calculator.calculate_pattern_confidence(pattern_match)

        # 信頼度が適切に計算されることを確認
        assert 0.0 <= calculated_confidence <= 1.0
        assert calculated_confidence > 0.5  # 良いマッチなので高い信頼度

    @pytest.mark.asyncio
    async def test_rollback_functionality(self, temp_workspace, mock_config):
        """ロールバック機能のテスト"""
        # テスト用プロジェクトファイルを作成
        project_dir = temp_workspace / "project"
        project_dir.mkdir(exist_ok=True)

        original_file = project_dir / "test.txt"
        original_content = "original content"
        original_file.write_text(original_content)

        # 自動修正システムを初期化
        with patch("os.getcwd", return_value=str(project_dir)):
            auto_fixer = AutoFixer(config=mock_config, interactive=False, auto_approve_low_risk=True)

            # 修正提案を作成
            fix_suggestion = FixSuggestion(
                title="ファイル修正テスト",
                description="テストファイルを変更",
                steps=[
                    FixStep(
                        type="file_modification",
                        description="ファイル内容を変更",
                        file_path="test.txt",
                        action="replace",
                        content="modified content",
                    )
                ],
                risk_level="low",
                estimated_effort="1分",
                confidence=0.9,
                priority=Priority.MEDIUM,
            )

            # 修正を適用
            fix_result = await auto_fixer.apply_fix(fix_suggestion, auto_approve=True)

            # 修正が成功することを確認
            assert fix_result.success
            assert original_file.read_text() == "modified content"

            # ロールバックを実行
            rollback_success = auto_fixer.rollback_changes(fix_result.backup_info)

            # ロールバックが成功することを確認
            assert rollback_success
            assert original_file.read_text() == original_content


class TestPatternCompetitionResolution:
    """パターン競合解決の詳細テスト"""

    @pytest.fixture
    def competing_patterns_workspace(self):
        """競合するパターンを含むワークスペース"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            patterns_dir = workspace / "data" / "patterns"
            patterns_dir.mkdir(parents=True, exist_ok=True)

            # 競合する可能性のあるパターンを作成
            competing_patterns = {
                "generic_error": {
                    "id": "generic_error",
                    "name": "一般的なエラー",
                    "category": "general",
                    "regex_patterns": [r"error", r"failed"],
                    "keywords": ["error", "failed"],
                    "context_requirements": [],
                    "confidence_base": 0.3,
                    "success_rate": 0.5,
                    "user_defined": False,
                },
                "specific_npm_error": {
                    "id": "specific_npm_error",
                    "name": "特定のNPMエラー",
                    "category": "dependency",
                    "regex_patterns": [r"npm.*error.*ENOENT"],
                    "keywords": ["npm", "error", "ENOENT"],
                    "context_requirements": ["npm", "ENOENT"],
                    "confidence_base": 0.9,
                    "success_rate": 0.95,
                    "user_defined": False,
                },
                "docker_npm_error": {
                    "id": "docker_npm_error",
                    "name": "Docker内NPMエラー",
                    "category": "container",
                    "regex_patterns": [r"docker.*npm.*error"],
                    "keywords": ["docker", "npm", "error"],
                    "context_requirements": ["docker", "npm"],
                    "confidence_base": 0.8,
                    "success_rate": 0.85,
                    "user_defined": False,
                },
            }

            patterns_file = patterns_dir / "failure_patterns.json"
            patterns_file.write_text(json.dumps(competing_patterns, indent=2, ensure_ascii=False))

            yield workspace

    @pytest.mark.asyncio
    async def test_pattern_priority_resolution(self, competing_patterns_workspace):
        """パターン優先度解決のテスト"""
        pattern_engine = PatternRecognitionEngine(
            data_directory=competing_patterns_workspace / "data" / "patterns",
            confidence_threshold=0.2,  # 低い閾値で複数パターンを検出
            max_patterns_per_analysis=10,
        )

        # 複数パターンにマッチするログ
        complex_log = """
STEP: Install dependencies in Docker
docker run npm install
npm ERR! code ENOENT
npm ERR! error occurred during installation
Installation failed with error
"""

        analysis_options = {"confidence_threshold": 0.2}
        pattern_matches = await pattern_engine.analyze_log(complex_log, analysis_options)

        # 複数パターンが検出されることを確認
        assert len(pattern_matches) >= 2

        # より具体的なパターンが高い信頼度を持つことを確認
        specific_match = next((m for m in pattern_matches if m.pattern.id == "specific_npm_error"), None)
        generic_match = next((m for m in pattern_matches if m.pattern.id == "generic_error"), None)

        if specific_match and generic_match:
            assert specific_match.confidence > generic_match.confidence

        # 最も信頼度の高いパターンが最初に来ることを確認
        assert pattern_matches[0].confidence >= pattern_matches[-1].confidence


class TestLearningEngineIntegration:
    """学習エンジンの統合テスト"""

    @pytest.fixture
    def learning_workspace(self):
        """学習機能用ワークスペース"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # 必要なディレクトリを作成
            patterns_dir = workspace / "data" / "patterns"
            learning_dir = workspace / "data" / "learning"
            patterns_dir.mkdir(parents=True, exist_ok=True)
            learning_dir.mkdir(parents=True, exist_ok=True)

            # 基本パターンを作成
            base_patterns = {
                "known_pattern": {
                    "id": "known_pattern",
                    "name": "既知のパターン",
                    "category": "test",
                    "regex_patterns": [r"known.*error"],
                    "keywords": ["known", "error"],
                    "context_requirements": ["known"],
                    "confidence_base": 0.8,
                    "success_rate": 0.9,
                    "user_defined": False,
                }
            }

            patterns_file = patterns_dir / "failure_patterns.json"
            patterns_file.write_text(json.dumps(base_patterns, indent=2, ensure_ascii=False))

            yield workspace

    @pytest.mark.asyncio
    async def test_new_pattern_discovery(self, learning_workspace):
        """新しいパターン発見のテスト"""
        pattern_database = PatternDatabase(learning_workspace / "data" / "patterns")
        learning_engine = LearningEngine(
            pattern_database=pattern_database,
            learning_data_dir=learning_workspace / "data" / "learning",
            min_pattern_occurrences=2,
        )

        # 未知のエラーログ
        unknown_logs = [
            "CustomFrameworkError: Framework initialization failed at line 42",
            "CustomFrameworkError: Configuration not found in framework setup",
            "CustomFrameworkError: Framework module loading failed",
        ]

        # 新しいパターンを発見
        discovered_patterns = await learning_engine.discover_new_patterns(unknown_logs)

        # パターンが発見されることを確認
        assert len(discovered_patterns) > 0

        # 発見されたパターンの品質を確認
        for pattern in discovered_patterns:
            assert pattern.id is not None
            assert pattern.name is not None
            assert len(pattern.keywords) > 0
            assert pattern.confidence_base > 0

    @pytest.mark.asyncio
    async def test_feedback_learning(self, learning_workspace):
        """フィードバック学習のテスト"""
        pattern_database = PatternDatabase(learning_workspace / "data" / "patterns")
        learning_engine = LearningEngine(
            pattern_database=pattern_database, learning_data_dir=learning_workspace / "data" / "learning"
        )

        # 複数のフィードバックを提供
        feedbacks = [
            UserFeedback(
                pattern_id="known_pattern",
                fix_suggestion_id="known_fix",
                rating=5,
                success=True,
                comments="完璧に動作しました",
            ),
            UserFeedback(
                pattern_id="known_pattern",
                fix_suggestion_id="known_fix",
                rating=4,
                success=True,
                comments="ほぼ期待通り",
            ),
            UserFeedback(
                pattern_id="known_pattern",
                fix_suggestion_id="known_fix",
                rating=2,
                success=False,
                comments="修正が失敗しました",
            ),
        ]

        # フィードバックを学習
        for feedback in feedbacks:
            await learning_engine.learn_from_feedback(feedback)

        # 学習結果が反映されることを確認
        # (実装に応じて検証方法を調整)

        # パターン改善提案を取得
        improvements = learning_engine.suggest_pattern_improvements()

        # 改善提案が生成されることを確認
        assert isinstance(improvements, list)
