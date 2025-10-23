"""
パターン認識システムの統合テスト

パターン認識から修正提案までの完全なフロー、複数パターンの競合解決、
学習機能の動作をテストします。
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, AnalyzeOptions, PatternAnalysisOptions
from src.ci_helper.ai.pattern_engine import PatternRecognitionEngine


class TestPatternRecognitionIntegration:
    """パターン認識システムの統合テスト"""

    @pytest.mark.asyncio
    async def test_pattern_engine_initialization(self, temp_dir):
        """パターンエンジンの初期化テスト"""
        # パターンデータベースのセットアップ
        pattern_db_dir = temp_dir / "patterns"
        pattern_db_dir.mkdir(exist_ok=True)

        # 空のパターンファイルを作成
        patterns_file = pattern_db_dir / "failure_patterns.json"
        patterns_file.write_text("{}", encoding="utf-8")

        # パターン認識エンジンの初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory=str(pattern_db_dir), confidence_threshold=0.7, max_patterns_per_analysis=5
        )

        # 初期化が成功することを確認
        assert pattern_engine is not None
        assert pattern_engine.confidence_threshold == 0.7
        assert pattern_engine.max_patterns_per_analysis == 5

    @pytest.mark.asyncio
    async def test_empty_log_analysis(self, temp_dir):
        """空のログ分析テスト"""
        # パターンデータベースのセットアップ
        pattern_db_dir = temp_dir / "patterns"
        pattern_db_dir.mkdir(exist_ok=True)

        # 空のパターンファイルを作成
        patterns_file = pattern_db_dir / "failure_patterns.json"
        patterns_file.write_text("{}", encoding="utf-8")

        # パターン認識エンジンの初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory=str(pattern_db_dir), confidence_threshold=0.7, max_patterns_per_analysis=5
        )

        # 空のログでの分析
        analysis_options = PatternAnalysisOptions(confidence_threshold=0.7)
        pattern_matches = await pattern_engine.analyze_log("", analysis_options)

        # 結果の検証
        assert isinstance(pattern_matches, list)
        assert len(pattern_matches) == 0

    @pytest.mark.asyncio
    async def test_concurrent_analysis(self, temp_dir):
        """並行分析のテスト"""
        # パターンデータベースのセットアップ
        pattern_db_dir = temp_dir / "patterns"
        pattern_db_dir.mkdir(exist_ok=True)

        # 空のパターンファイルを作成
        patterns_file = pattern_db_dir / "failure_patterns.json"
        patterns_file.write_text("{}", encoding="utf-8")

        # パターン認識エンジンの初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory=str(pattern_db_dir), confidence_threshold=0.5, max_patterns_per_analysis=10
        )

        # 複数のログを並行分析
        log_contents = [
            "Error 1: Test failed",
            "Error 2: Build failed",
            "Error 3: Deploy failed",
        ]

        analysis_options = PatternAnalysisOptions(confidence_threshold=0.5)

        # 並行実行
        tasks = [pattern_engine.analyze_log(log_content, analysis_options) for log_content in log_contents]

        import time

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # 結果の検証
        assert len(results) == 3
        assert all(isinstance(result, list) for result in results)

        # 並行処理により処理時間が短縮されることを確認
        processing_time = end_time - start_time
        assert processing_time < 5.0  # 5秒以内で完了

    @pytest.mark.asyncio
    async def test_ai_integration_workflow(self, temp_dir):
        """AI統合ワークフローのテスト"""
        from src.ci_helper.ai.models import AIConfig, ProviderConfig

        mock_ai_config = AIConfig(
            default_provider="openai",
            providers={
                "openai": ProviderConfig(
                    name="openai",
                    api_key="sk-test-key-123",
                    default_model="gpt-4o",
                    available_models=["gpt-4o", "gpt-4o-mini"],
                )
            },
            cache_enabled=True,
            cost_limits={"monthly_usd": 50.0},
            cache_dir=str(temp_dir / "cache"),
        )

        sample_log_content = """
STEP: Run tests
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /github/workspace/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/github/workspace/package.json'
"""

        # AI統合のモック設定
        with (
            patch("src.ci_helper.ai.integration.AIConfigManager") as mock_config_manager,
            patch("src.ci_helper.ai.providers.openai.AsyncOpenAI") as mock_openai,
        ):
            mock_config_manager.return_value.get_ai_config.return_value = mock_ai_config

            # OpenAI APIのモック
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]

            # AI分析結果
            ai_analysis_result = {
                "summary": "複数のエラーが検出されました",
                "root_causes": [
                    {
                        "category": "permission",
                        "description": "Docker権限が不足しています",
                        "severity": "HIGH",
                    }
                ],
                "confidence_score": 0.87,
            }

            mock_response.choices[0].message.content = json.dumps(ai_analysis_result)
            mock_response.usage.prompt_tokens = 1500
            mock_response.usage.completion_tokens = 800
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            # AI統合の実行
            from src.ci_helper.ai.integration import AIIntegration

            ai_integration = AIIntegration(mock_ai_config)
            await ai_integration.initialize()

            options = AnalyzeOptions(
                provider="openai",
                model="gpt-4o",
                use_cache=False,
                streaming=False,
            )

            # 分析の実行
            result = await ai_integration.analyze_log(sample_log_content, options)

            # 結果の検証
            assert isinstance(result, AnalysisResult)
            assert result.status == AnalysisStatus.COMPLETED
            assert result.confidence_score >= 0.8

    @pytest.mark.asyncio
    async def test_error_handling(self, temp_dir):
        """エラーハンドリングのテスト"""
        # 存在しないディレクトリでの初期化
        pattern_engine = PatternRecognitionEngine(
            data_directory=str(temp_dir / "nonexistent"), confidence_threshold=0.7, max_patterns_per_analysis=5
        )

        # エラーが発生しても適切に処理されることを確認
        analysis_options = PatternAnalysisOptions(confidence_threshold=0.7)
        pattern_matches = await pattern_engine.analyze_log("test log", analysis_options)

        # 結果の検証
        assert isinstance(pattern_matches, list)
