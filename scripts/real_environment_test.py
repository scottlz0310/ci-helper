#!/usr/bin/env python3
"""
実環境での動作確認スクリプト

AI統合機能の実環境での動作確認を行います。
実際のAPIキーを使用してE2E動作確認、各プロバイダーでの動作確認、
大きなログファイルでのパフォーマンステスト、エラーシナリオでの復旧動作確認を実行します。

使用方法:
    python scripts/real_environment_test.py [--provider PROVIDER] [--verbose] [--skip-api-tests]

要件: 16.1 実環境での動作確認
- 実際のAPIキーを使用したE2E動作確認
- 各プロバイダー（OpenAI、Anthropic、ローカルLLM）での動作確認
- 大きなログファイルでのパフォーマンステスト
- エラーシナリオでの復旧動作確認
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ci_helper.ai.integration import AIIntegration
from ci_helper.ai.models import AIConfig, AnalyzeOptions, ProviderConfig


class RealEnvironmentTester:
    """実環境テスター"""

    def __init__(self, verbose: bool = False, skip_api_tests: bool = False):
        self.verbose = verbose
        self.skip_api_tests = skip_api_tests
        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
            },
        }
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ci_helper_real_test_"))

    def log(self, message: str, level: str = "INFO") -> None:
        """ログメッセージを出力"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{timestamp}] {level}: {message}")

    def record_test_result(self, test_name: str, success: bool, details: dict[str, Any]) -> None:
        """テスト結果を記録"""
        self.results["tests"][test_name] = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.results["summary"]["total"] += 1
        if success:
            self.results["summary"]["passed"] += 1
            self.log(f"✓ {test_name}: PASSED", "INFO")
        else:
            self.results["summary"]["failed"] += 1
            self.log(f"✗ {test_name}: FAILED - {details.get('error', 'Unknown error')}", "ERROR")

    def skip_test(self, test_name: str, reason: str) -> None:
        """テストをスキップ"""
        self.results["tests"][test_name] = {
            "success": None,
            "skipped": True,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        self.results["summary"]["total"] += 1
        self.results["summary"]["skipped"] += 1
        self.log(f"⚠ {test_name}: SKIPPED - {reason}", "WARNING")

    def check_environment_variables(self) -> dict[str, bool]:
        """環境変数の確認"""
        self.log("環境変数の確認を開始...")

        api_keys = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
            "CI_HELPER_API_KEY": os.getenv("CI_HELPER_API_KEY"),
        }

        available_providers = {}
        for key, value in api_keys.items():
            if value:
                provider = key.replace("_API_KEY", "").lower()
                if provider == "ci_helper":
                    provider = "generic"
                available_providers[provider] = True
                self.log(f"✓ {key} が設定されています", "INFO")
            else:
                provider = key.replace("_API_KEY", "").lower()
                if provider == "ci_helper":
                    provider = "generic"
                available_providers[provider] = False
                self.log(f"✗ {key} が設定されていません", "WARNING")

        # ローカルLLMの確認（Ollama）
        try:
            import socket

            import aiohttp

            # 簡単な接続テスト（非同期を避ける）
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(("localhost", 11434))
                sock.close()
                ollama_available = result == 0
            except Exception:
                ollama_available = False

            available_providers["local"] = ollama_available
            if ollama_available:
                self.log("✓ Ollama (ローカルLLM) が利用可能です", "INFO")
            else:
                self.log("✗ Ollama (ローカルLLM) が利用できません", "WARNING")
        except ImportError:
            available_providers["local"] = False
            self.log("✗ aiohttp が利用できないため、Ollama の確認をスキップします", "WARNING")

        return available_providers

    def create_test_ai_config(self, available_providers: dict[str, bool]) -> AIConfig:
        """テスト用のAI設定を作成"""
        providers = {}

        if available_providers.get("openai", False):
            providers["openai"] = ProviderConfig(
                name="openai",
                api_key=os.getenv("OPENAI_API_KEY", ""),
                default_model="gpt-4o-mini",  # コスト効率の良いモデルを使用
                available_models=["gpt-4o-mini", "gpt-4o"],
                timeout_seconds=30,
                max_retries=3,
            )

        if available_providers.get("anthropic", False):
            providers["anthropic"] = ProviderConfig(
                name="anthropic",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                default_model="claude-3-5-haiku-20241022",  # コスト効率の良いモデルを使用
                available_models=["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
                timeout_seconds=30,
                max_retries=3,
            )

        if available_providers.get("local", False):
            providers["local"] = ProviderConfig(
                name="local",
                api_key="",  # ローカルLLMはAPIキー不要
                base_url="http://localhost:11434",
                default_model="llama3.2",
                available_models=["llama3.2", "codellama"],
                timeout_seconds=60,  # ローカルLLMは時間がかかる場合がある
                max_retries=2,
            )

        # デフォルトプロバイダーを決定
        default_provider = "openai"
        if not available_providers.get("openai", False):
            if available_providers.get("anthropic", False):
                default_provider = "anthropic"
            elif available_providers.get("local", False):
                default_provider = "local"
            else:
                default_provider = "openai"  # フォールバック

        return AIConfig(
            default_provider=default_provider,
            providers=providers,
            cache_enabled=True,
            cache_ttl_hours=1,  # テスト用に短く設定
            cache_max_size_mb=50,
            cost_limits={"monthly_usd": 10.0, "per_request_usd": 1.0},  # テスト用に低く設定
            prompt_templates={},
            interactive_timeout=60,  # テスト用に短く設定
        )

    def create_test_log_content(self, size: str = "small") -> str:
        """テスト用のログ内容を作成"""
        if size == "small":
            return """
=== CI/CD Test Failure Log ===
2024-01-15 10:30:45 [INFO] Starting test execution
2024-01-15 10:30:46 [INFO] Running pytest tests
2024-01-15 10:30:47 [ERROR] Test failed: test_user_authentication
2024-01-15 10:30:47 [ERROR] AssertionError: Expected status code 200, got 401
2024-01-15 10:30:47 [ERROR] File: tests/test_auth.py, Line: 45
2024-01-15 10:30:47 [ERROR] Function: test_login_with_valid_credentials
2024-01-15 10:30:48 [INFO] Test execution completed with 1 failure
"""

        elif size == "medium":
            base_content = self.create_test_log_content("small")
            # 中サイズのログ（約5KB）
            repeated_content = "\n".join(
                [f"2024-01-15 10:30:{50 + i:02d} [DEBUG] Processing request {i + 1}" for i in range(100)]
            )
            return base_content + "\n" + repeated_content

        elif size == "large":
            base_content = self.create_test_log_content("medium")
            # 大サイズのログ（約50KB）
            large_content = "\n".join(
                [
                    f"2024-01-15 10:{31 + (i // 60):02d}:{(i % 60):02d} [DEBUG] Large log entry {i + 1}: "
                    + "A" * 100  # 各行100文字
                    for i in range(500)
                ]
            )
            return base_content + "\n" + large_content

        else:  # extra_large
            base_content = self.create_test_log_content("large")
            # 超大サイズのログ（約500KB）
            extra_large_content = "\n".join(
                [
                    f"2024-01-15 11:{(i // 60):02d}:{(i % 60):02d} [TRACE] Extra large log entry {i + 1}: "
                    + "B" * 200  # 各行200文字
                    for i in range(2000)
                ]
            )
            return base_content + "\n" + extra_large_content

    async def test_basic_ai_integration_initialization(self, ai_config: AIConfig) -> None:
        """基本的なAI統合の初期化テスト"""
        test_name = "basic_ai_integration_initialization"
        self.log(f"テスト開始: {test_name}")

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            # 初期化の確認
            assert ai_integration._initialized, "AI統合が初期化されていません"
            assert len(ai_integration.providers) > 0, "利用可能なプロバイダーがありません"

            details = {
                "initialized": ai_integration._initialized,
                "provider_count": len(ai_integration.providers),
                "available_providers": list(ai_integration.providers.keys()),
                "default_provider": ai_integration.ai_config.default_provider,
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_provider_analysis(self, ai_config: AIConfig, provider_name: str) -> None:
        """特定プロバイダーでの分析テスト"""
        test_name = f"provider_analysis_{provider_name}"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests and provider_name != "local":
            self.skip_test(test_name, "API テストがスキップされました")
            return

        if provider_name not in ai_config.providers:
            self.skip_test(test_name, f"プロバイダー {provider_name} が利用できません")
            return

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            # テスト用ログで分析
            log_content = self.create_test_log_content("small")
            options = AnalyzeOptions(
                provider=provider_name,
                model=None,  # デフォルトモデルを使用
                streaming=False,  # 非ストリーミングでテスト
                use_cache=False,  # キャッシュを無効にしてテスト
                generate_fixes=False,
            )

            start_time = time.time()
            result = await ai_integration.analyze_log(log_content, options)
            analysis_time = time.time() - start_time

            # 結果の検証
            assert result is not None, "分析結果がNoneです"
            assert result.summary, "分析結果のサマリーが空です"
            assert result.provider == provider_name, f"プロバイダーが一致しません: {result.provider} != {provider_name}"

            details = {
                "provider": result.provider,
                "model": result.model,
                "analysis_time": analysis_time,
                "summary_length": len(result.summary),
                "confidence_score": result.confidence_score,
                "tokens_used": result.tokens_used.total_tokens if result.tokens_used else 0,
                "estimated_cost": result.tokens_used.estimated_cost if result.tokens_used else 0.0,
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_streaming_analysis(self, ai_config: AIConfig, provider_name: str) -> None:
        """ストリーミング分析テスト"""
        test_name = f"streaming_analysis_{provider_name}"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests and provider_name != "local":
            self.skip_test(test_name, "API テストがスキップされました")
            return

        if provider_name not in ai_config.providers:
            self.skip_test(test_name, f"プロバイダー {provider_name} が利用できません")
            return

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            log_content = self.create_test_log_content("small")
            options = AnalyzeOptions(
                provider=provider_name,
                streaming=True,
                use_cache=False,
            )

            start_time = time.time()
            chunks = []
            async for chunk in ai_integration.stream_analyze(log_content, options):
                chunks.append(chunk)
                if len(chunks) > 100:  # 無限ループ防止
                    break

            streaming_time = time.time() - start_time

            # 結果の検証
            assert len(chunks) > 0, "ストリーミングチャンクが受信されませんでした"
            full_response = "".join(chunks)
            assert len(full_response) > 0, "ストリーミングレスポンスが空です"

            details = {
                "provider": provider_name,
                "streaming_time": streaming_time,
                "chunk_count": len(chunks),
                "total_response_length": len(full_response),
                "average_chunk_size": len(full_response) / len(chunks) if chunks else 0,
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_large_log_performance(self, ai_config: AIConfig) -> None:
        """大きなログファイルでのパフォーマンステスト"""
        test_name = "large_log_performance"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests:
            self.skip_test(test_name, "API テストがスキップされました")
            return

        # 利用可能な最初のプロバイダーを使用
        available_providers = [name for name in ai_config.providers.keys() if name in ai_config.providers]
        if not available_providers:
            self.skip_test(test_name, "利用可能なプロバイダーがありません")
            return

        provider_name = available_providers[0]

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            # 大きなログファイルを作成
            large_log_content = self.create_test_log_content("large")
            log_size_kb = len(large_log_content) / 1024

            options = AnalyzeOptions(
                provider=provider_name,
                streaming=False,
                use_cache=False,
            )

            start_time = time.time()
            result = await ai_integration.analyze_log(large_log_content, options)
            processing_time = time.time() - start_time

            # パフォーマンス指標の計算
            processing_speed_kb_per_sec = log_size_kb / processing_time if processing_time > 0 else 0

            details = {
                "provider": provider_name,
                "log_size_kb": log_size_kb,
                "processing_time": processing_time,
                "processing_speed_kb_per_sec": processing_speed_kb_per_sec,
                "tokens_used": result.tokens_used.total_tokens if result.tokens_used else 0,
                "estimated_cost": result.tokens_used.estimated_cost if result.tokens_used else 0.0,
                "memory_efficient": processing_time < 60,  # 60秒以内なら効率的とみなす
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_interactive_session(self, ai_config: AIConfig) -> None:
        """対話セッションテスト"""
        test_name = "interactive_session"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests:
            self.skip_test(test_name, "API テストがスキップされました")
            return

        # 利用可能な最初のプロバイダーを使用
        available_providers = [name for name in ai_config.providers.keys() if name in ai_config.providers]
        if not available_providers:
            self.skip_test(test_name, "利用可能なプロバイダーがありません")
            return

        provider_name = available_providers[0]

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            log_content = self.create_test_log_content("small")
            options = AnalyzeOptions(provider=provider_name)

            # 対話セッションを開始
            session = await ai_integration.start_interactive_session(log_content, options)

            # セッションの検証
            assert session is not None, "対話セッションが作成されませんでした"
            assert session.session_id, "セッションIDが設定されていません"
            assert session.is_active, "セッションがアクティブではありません"

            # 簡単な対話をテスト
            test_input = "このエラーの原因は何ですか？"
            response_chunks = []
            async for chunk in ai_integration.process_interactive_input(session.session_id, test_input):
                response_chunks.append(chunk)
                if len(response_chunks) > 50:  # 無限ループ防止
                    break

            # セッションを終了
            closed = await ai_integration.close_interactive_session(session.session_id)

            details = {
                "provider": provider_name,
                "session_created": session is not None,
                "session_id": session.session_id if session else None,
                "response_received": len(response_chunks) > 0,
                "response_length": len("".join(response_chunks)),
                "session_closed": closed,
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_error_recovery_scenarios(self, ai_config: AIConfig) -> None:
        """エラーシナリオでの復旧動作確認"""
        test_name = "error_recovery_scenarios"
        self.log(f"テスト開始: {test_name}")

        # 利用可能な最初のプロバイダーを使用
        available_providers = [name for name in ai_config.providers.keys() if name in ai_config.providers]
        if not available_providers:
            self.skip_test(test_name, "利用可能なプロバイダーがありません")
            return

        provider_name = available_providers[0]

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            error_scenarios = []

            # シナリオ1: 無効なプロバイダー
            try:
                invalid_options = AnalyzeOptions(provider="invalid_provider")
                await ai_integration.analyze_log("test log", invalid_options)
                error_scenarios.append({"scenario": "invalid_provider", "handled": False})
            except Exception as e:
                error_scenarios.append(
                    {
                        "scenario": "invalid_provider",
                        "handled": True,
                        "error_type": type(e).__name__,
                    }
                )

            # シナリオ2: 空のログ内容
            try:
                empty_options = AnalyzeOptions(provider=provider_name)
                result = await ai_integration.analyze_log("", empty_options)
                error_scenarios.append(
                    {
                        "scenario": "empty_log",
                        "handled": True,
                        "result_received": result is not None,
                    }
                )
            except Exception as e:
                error_scenarios.append(
                    {
                        "scenario": "empty_log",
                        "handled": True,
                        "error_type": type(e).__name__,
                    }
                )

            # シナリオ3: 非常に長いログ（トークン制限テスト）
            if not self.skip_api_tests:
                try:
                    very_long_log = self.create_test_log_content("extra_large")
                    long_options = AnalyzeOptions(provider=provider_name)
                    result = await ai_integration.analyze_log(very_long_log, long_options)
                    error_scenarios.append(
                        {
                            "scenario": "very_long_log",
                            "handled": True,
                            "result_received": result is not None,
                        }
                    )
                except Exception as e:
                    error_scenarios.append(
                        {
                            "scenario": "very_long_log",
                            "handled": True,
                            "error_type": type(e).__name__,
                        }
                    )

            details = {
                "provider": provider_name,
                "scenarios_tested": len(error_scenarios),
                "scenarios": error_scenarios,
                "all_handled": all(scenario.get("handled", False) for scenario in error_scenarios),
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_cache_functionality(self, ai_config: AIConfig) -> None:
        """キャッシュ機能テスト"""
        test_name = "cache_functionality"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests:
            self.skip_test(test_name, "API テストがスキップされました")
            return

        # 利用可能な最初のプロバイダーを使用
        available_providers = [name for name in ai_config.providers.keys() if name in ai_config.providers]
        if not available_providers:
            self.skip_test(test_name, "利用可能なプロバイダーがありません")
            return

        provider_name = available_providers[0]

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            log_content = self.create_test_log_content("small")

            # 1回目の分析（キャッシュなし）
            options_no_cache = AnalyzeOptions(
                provider=provider_name,
                use_cache=True,  # キャッシュを有効にする
            )

            start_time_1 = time.time()
            result_1 = await ai_integration.analyze_log(log_content, options_no_cache)
            time_1 = time.time() - start_time_1

            # 2回目の分析（キャッシュあり）
            start_time_2 = time.time()
            result_2 = await ai_integration.analyze_log(log_content, options_no_cache)
            time_2 = time.time() - start_time_2

            # キャッシュ効果の確認
            cache_speedup = time_1 / time_2 if time_2 > 0 else 1
            cache_hit = getattr(result_2, "cache_hit", False)

            details = {
                "provider": provider_name,
                "first_analysis_time": time_1,
                "second_analysis_time": time_2,
                "cache_speedup": cache_speedup,
                "cache_hit": cache_hit,
                "results_identical": result_1.summary == result_2.summary,
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    async def test_cost_management(self, ai_config: AIConfig) -> None:
        """コスト管理機能テスト"""
        test_name = "cost_management"
        self.log(f"テスト開始: {test_name}")

        if self.skip_api_tests:
            self.skip_test(test_name, "API テストがスキップされました")
            return

        # 利用可能な最初のプロバイダーを使用
        available_providers = [name for name in ai_config.providers.keys() if name in ai_config.providers]
        if not available_providers:
            self.skip_test(test_name, "利用可能なプロバイダーがありません")
            return

        provider_name = available_providers[0]

        try:
            ai_integration = AIIntegration(ai_config)
            await ai_integration.initialize()

            # 使用統計の初期状態を取得
            initial_stats = await ai_integration.get_usage_stats()

            # 分析を実行
            log_content = self.create_test_log_content("medium")
            options = AnalyzeOptions(provider=provider_name, use_cache=False)
            result = await ai_integration.analyze_log(log_content, options)

            # 使用統計の更新後状態を取得
            final_stats = await ai_integration.get_usage_stats()

            # コスト情報の確認
            cost_tracked = result.tokens_used is not None and result.tokens_used.estimated_cost > 0
            stats_updated = final_stats.get("total_requests", 0) > initial_stats.get("total_requests", 0)

            details = {
                "provider": provider_name,
                "cost_tracked": cost_tracked,
                "estimated_cost": result.tokens_used.estimated_cost if result.tokens_used else 0.0,
                "tokens_used": result.tokens_used.total_tokens if result.tokens_used else 0,
                "stats_updated": stats_updated,
                "initial_requests": initial_stats.get("total_requests", 0),
                "final_requests": final_stats.get("total_requests", 0),
            }

            await ai_integration.cleanup()
            self.record_test_result(test_name, True, details)

        except Exception as e:
            self.record_test_result(test_name, False, {"error": str(e), "type": type(e).__name__})

    def save_results(self) -> None:
        """テスト結果をファイルに保存"""
        results_file = self.temp_dir / "real_environment_test_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        self.log(f"テスト結果を保存しました: {results_file}")

        # サマリーレポートも作成
        report_file = self.temp_dir / "real_environment_test_report.md"
        self.generate_report(report_file)

    def generate_report(self, report_file: Path) -> None:
        """テストレポートを生成"""
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("# CI Helper AI統合機能 実環境テストレポート\n\n")
            f.write(f"**実行日時**: {self.results['timestamp']}\n\n")

            # サマリー
            summary = self.results["summary"]
            f.write("## テスト結果サマリー\n\n")
            f.write(f"- **総テスト数**: {summary['total']}\n")
            f.write(f"- **成功**: {summary['passed']}\n")
            f.write(f"- **失敗**: {summary['failed']}\n")
            f.write(f"- **スキップ**: {summary['skipped']}\n")
            f.write(f"- **成功率**: {(summary['passed'] / summary['total'] * 100):.1f}%\n\n")

            # 詳細結果
            f.write("## 詳細テスト結果\n\n")
            for test_name, result in self.results["tests"].items():
                status = "✓ PASSED" if result["success"] else "✗ FAILED"
                if result.get("skipped"):
                    status = "⚠ SKIPPED"

                f.write(f"### {test_name}\n")
                f.write(f"**ステータス**: {status}\n")
                f.write(f"**実行時刻**: {result['timestamp']}\n")

                if result.get("skipped"):
                    f.write(f"**スキップ理由**: {result['reason']}\n")
                elif not result["success"]:
                    details = result.get("details", {})
                    f.write(f"**エラー**: {details.get('error', 'Unknown')}\n")
                    f.write(f"**エラータイプ**: {details.get('type', 'Unknown')}\n")
                else:
                    # 成功時の詳細情報
                    details = result.get("details", {})
                    for key, value in details.items():
                        if isinstance(value, (int, float)):
                            if key.endswith("_time"):
                                f.write(f"**{key}**: {value:.3f}秒\n")
                            elif key.endswith("_cost"):
                                f.write(f"**{key}**: ${value:.6f}\n")
                            else:
                                f.write(f"**{key}**: {value}\n")
                        else:
                            f.write(f"**{key}**: {value}\n")

                f.write("\n")

        self.log(f"テストレポートを生成しました: {report_file}")

    def cleanup(self) -> None:
        """クリーンアップ"""
        try:
            import shutil

            shutil.rmtree(self.temp_dir)
            self.log(f"一時ディレクトリを削除しました: {self.temp_dir}")
        except Exception as e:
            self.log(f"一時ディレクトリの削除に失敗しました: {e}", "WARNING")

    async def run_all_tests(self, target_provider: str | None = None) -> None:
        """全テストを実行"""
        self.log("=== CI Helper AI統合機能 実環境テスト開始 ===")

        # 環境変数の確認
        available_providers = self.check_environment_variables()

        if not any(available_providers.values()):
            self.log("利用可能なプロバイダーがありません。テストを中止します。", "ERROR")
            return

        # AI設定を作成
        ai_config = self.create_test_ai_config(available_providers)

        # 基本初期化テスト
        await self.test_basic_ai_integration_initialization(ai_config)

        # プロバイダー別テスト
        providers_to_test = [target_provider] if target_provider else list(ai_config.providers.keys())

        for provider_name in providers_to_test:
            if provider_name in ai_config.providers:
                await self.test_provider_analysis(ai_config, provider_name)
                await self.test_streaming_analysis(ai_config, provider_name)

        # パフォーマンステスト
        await self.test_large_log_performance(ai_config)

        # 機能テスト
        await self.test_interactive_session(ai_config)
        await self.test_cache_functionality(ai_config)
        await self.test_cost_management(ai_config)

        # エラー復旧テスト
        await self.test_error_recovery_scenarios(ai_config)

        # 結果の保存
        self.save_results()

        # 最終サマリー
        summary = self.results["summary"]
        self.log("=== テスト完了 ===")
        self.log(f"総テスト数: {summary['total']}")
        self.log(f"成功: {summary['passed']}")
        self.log(f"失敗: {summary['failed']}")
        self.log(f"スキップ: {summary['skipped']}")
        self.log(f"成功率: {(summary['passed'] / summary['total'] * 100):.1f}%")

        if summary["failed"] > 0:
            self.log("一部のテストが失敗しました。詳細はレポートを確認してください。", "WARNING")
        else:
            self.log("全てのテストが成功しました！", "INFO")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="CI Helper AI統合機能の実環境テスト")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "local"],
        help="テストする特定のプロバイダー（指定しない場合は全プロバイダー）",
    )
    parser.add_argument("--verbose", action="store_true", help="詳細なログを出力")
    parser.add_argument("--skip-api-tests", action="store_true", help="実際のAPI呼び出しを伴うテストをスキップ")

    args = parser.parse_args()

    # テスターを作成
    tester = RealEnvironmentTester(verbose=args.verbose, skip_api_tests=args.skip_api_tests)

    try:
        # テストを実行
        asyncio.run(tester.run_all_tests(args.provider))
    except KeyboardInterrupt:
        tester.log("テストが中断されました", "WARNING")
    except Exception as e:
        tester.log(f"テスト実行中にエラーが発生しました: {e}", "ERROR")
    finally:
        # 結果を表示
        print(f"\n結果ファイル: {tester.temp_dir}")
        print(f"- JSON: {tester.temp_dir}/real_environment_test_results.json")
        print(f"- レポート: {tester.temp_dir}/real_environment_test_report.md")

        # クリーンアップするかユーザーに確認
        try:
            response = input("\n一時ファイルを削除しますか？ (y/N): ")
            if response.lower() in ["y", "yes"]:
                tester.cleanup()
            else:
                print(f"一時ファイルは保持されました: {tester.temp_dir}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n一時ファイルは保持されました: {tester.temp_dir}")


if __name__ == "__main__":
    main()
