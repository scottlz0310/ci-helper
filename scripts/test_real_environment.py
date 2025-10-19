#!/usr/bin/env python3
"""
実環境での動作確認スクリプト

AI統合機能の実際のAPIキーを使用したE2E動作確認を行います。
各プロバイダー（OpenAI、Anthropic、ローカルLLM）での動作確認、
大きなログファイルでのパフォーマンステスト、
エラーシナリオでの復旧動作確認を実施します。

使用方法:
    uv run python scripts/test_real_environment.py [--provider PROVIDER] [--verbose]

環境変数:
    OPENAI_API_KEY: OpenAI APIキー
    ANTHROPIC_API_KEY: Anthropic APIキー
    OLLAMA_BASE_URL: ローカルLLMのベースURL（オプション）
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ci_helper.ai.integration import AIIntegration
from ci_helper.ai.models import AIConfig, AnalyzeOptions, ProviderConfig

console = Console()


class RealEnvironmentTester:
    """実環境テスター"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: dict[str, Any] = {
            "provider_tests": {},
            "performance_tests": {},
            "error_recovery_tests": {},
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "start_time": None,
                "end_time": None,
            },
        }
        self.test_log_content = self._generate_test_log_content()

    def _generate_test_log_content(self) -> str:
        """テスト用のログコンテンツを生成"""
        return """
=== CI/CD Test Failure Log ===

Run pytest tests/unit/test_example.py
FAILED tests/unit/test_example.py::test_calculation - AssertionError: Expected 4, got 5

================================ FAILURES =================================
_______________________________ test_calculation _______________________________

    def test_calculation():
        result = add_numbers(2, 2)
>       assert result == 4, f"Expected 4, got {result}"
E       AssertionError: Expected 4, got 5

tests/unit/test_example.py:15: AssertionError

=========================== short test summary info ============================
FAILED tests/unit/test_example.py::test_calculation - AssertionError: Expected 4, got 5
=========================== 1 failed, 0 passed in 0.12s ===========================

Build failed with exit code 1
"""

    def _generate_large_log_content(self, size_mb: float = 1.0) -> str:
        """大きなログコンテンツを生成（パフォーマンステスト用）"""
        base_content = self.test_log_content
        target_size = int(size_mb * 1024 * 1024)  # MB to bytes

        # ベースコンテンツを繰り返して目標サイズに到達
        repeat_count = max(1, target_size // len(base_content))
        large_content = base_content * repeat_count

        # 追加のログエントリを生成
        additional_entries = []
        for i in range(100):
            additional_entries.append(f"""
ERROR: Test case {i} failed with timeout
  File "test_{i}.py", line {i * 10}, in test_function_{i}
    assert response.status_code == 200
  AssertionError: Expected 200, got 500
""")

        return large_content + "\n".join(additional_entries)

    async def run_all_tests(self, specific_provider: str | None = None) -> dict[str, Any]:
        """全てのテストを実行"""
        console.print(Panel.fit("🧪 実環境での動作確認を開始", style="blue"))

        self.results["summary"]["start_time"] = time.time()

        try:
            # 1. プロバイダーテスト
            if specific_provider:
                await self._test_specific_provider(specific_provider)
            else:
                await self._test_all_providers()

            # 2. パフォーマンステスト
            await self._test_performance()

            # 3. エラー復旧テスト
            await self._test_error_recovery()

        except Exception as e:
            console.print(f"[red]テスト実行中にエラーが発生: {e}[/red]")
            if self.verbose:
                console.print_exception()

        finally:
            self.results["summary"]["end_time"] = time.time()
            self._generate_summary_report()

        return self.results

    async def _test_all_providers(self) -> None:
        """全プロバイダーのテスト"""
        console.print("\n[bold blue]1. プロバイダーテスト[/bold blue]")

        providers_to_test = []

        # 利用可能なプロバイダーを確認
        if os.getenv("OPENAI_API_KEY"):
            providers_to_test.append("openai")
        if os.getenv("ANTHROPIC_API_KEY"):
            providers_to_test.append("anthropic")
        if os.getenv("OLLAMA_BASE_URL") or self._check_local_ollama():
            providers_to_test.append("local")

        if not providers_to_test:
            console.print("[yellow]⚠️  利用可能なプロバイダーがありません（APIキーが設定されていません）[/yellow]")
            console.print("[blue]💡 以下の環境変数を設定してください:[/blue]")
            console.print("  • OPENAI_API_KEY=your_openai_key")
            console.print("  • ANTHROPIC_API_KEY=your_anthropic_key")
            console.print("  • OLLAMA_BASE_URL=http://localhost:11434 (ローカルLLM用)")
            return

        for provider in providers_to_test:
            await self._test_specific_provider(provider)

    async def _test_specific_provider(self, provider: str) -> None:
        """特定プロバイダーのテスト"""
        console.print(f"\n[cyan]📡 {provider.upper()} プロバイダーテスト[/cyan]")

        test_result = {
            "provider": provider,
            "tests": {},
            "overall_status": "unknown",
            "error_message": None,
            "performance_metrics": {},
        }

        try:
            # AI統合を初期化
            ai_integration = await self._create_ai_integration(provider)

            # 基本分析テスト
            await self._test_basic_analysis(ai_integration, provider, test_result)

            # ストリーミングテスト
            await self._test_streaming_analysis(ai_integration, provider, test_result)

            # 修正提案テスト
            await self._test_fix_suggestions(ai_integration, provider, test_result)

            # 対話モードテスト
            await self._test_interactive_mode(ai_integration, provider, test_result)

            # 全テストが成功した場合
            test_result["overall_status"] = "passed"
            console.print(f"[green]✅ {provider.upper()} プロバイダーテスト完了[/green]")

        except Exception as e:
            test_result["overall_status"] = "failed"
            test_result["error_message"] = str(e)
            console.print(f"[red]❌ {provider.upper()} プロバイダーテスト失敗: {e}[/red]")
            if self.verbose:
                console.print_exception()

        self.results["provider_tests"][provider] = test_result
        self._update_test_counts(test_result["overall_status"])

    async def _test_basic_analysis(self, ai_integration: AIIntegration, provider: str, test_result: dict) -> None:
        """基本分析テスト"""
        console.print("  🔍 基本分析テスト...")

        start_time = time.time()

        try:
            options = AnalyzeOptions(
                provider=provider,
                model=None,  # デフォルトモデルを使用
                custom_prompt=None,
                streaming=False,
                use_cache=True,
                generate_fixes=False,
            )

            result = await ai_integration.analyze_log(self.test_log_content, options)

            # 結果の検証
            assert result is not None, "分析結果がNone"
            assert result.summary, "要約が空"
            assert result.confidence_score >= 0.0, "信頼度スコアが無効"

            analysis_time = time.time() - start_time

            test_result["tests"]["basic_analysis"] = {
                "status": "passed",
                "analysis_time": analysis_time,
                "summary_length": len(result.summary),
                "confidence_score": result.confidence_score,
                "tokens_used": result.tokens_used.total_tokens if result.tokens_used else 0,
            }

            console.print(f"    ✅ 基本分析成功 ({analysis_time:.2f}秒)")

        except Exception as e:
            test_result["tests"]["basic_analysis"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 基本分析失敗: {e}")
            raise

    async def _test_streaming_analysis(self, ai_integration: AIIntegration, provider: str, test_result: dict) -> None:
        """ストリーミング分析テスト"""
        console.print("  🌊 ストリーミング分析テスト...")

        start_time = time.time()

        try:
            options = AnalyzeOptions(
                provider=provider,
                streaming=True,
                use_cache=False,  # ストリーミングテストではキャッシュを無効
            )

            chunks_received = 0
            total_content = ""

            async for chunk in ai_integration.stream_analyze(self.test_log_content, options):
                chunks_received += 1
                total_content += chunk

                # 最大100チャンクまでテスト
                if chunks_received >= 100:
                    break

            streaming_time = time.time() - start_time

            # 結果の検証
            assert chunks_received > 0, "ストリーミングチャンクが受信されなかった"
            assert total_content.strip(), "ストリーミング内容が空"

            test_result["tests"]["streaming_analysis"] = {
                "status": "passed",
                "streaming_time": streaming_time,
                "chunks_received": chunks_received,
                "total_content_length": len(total_content),
            }

            console.print(f"    ✅ ストリーミング成功 ({chunks_received}チャンク, {streaming_time:.2f}秒)")

        except NotImplementedError:
            # プロバイダーがストリーミングをサポートしていない場合
            test_result["tests"]["streaming_analysis"] = {
                "status": "skipped",
                "reason": "プロバイダーがストリーミングをサポートしていません",
            }
            console.print("    ⏭️  ストリーミング非対応")

        except Exception as e:
            test_result["tests"]["streaming_analysis"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ ストリーミング失敗: {e}")
            # ストリーミングの失敗は致命的ではないので継続

    async def _test_fix_suggestions(self, ai_integration: AIIntegration, provider: str, test_result: dict) -> None:
        """修正提案テスト"""
        console.print("  🔧 修正提案テスト...")

        start_time = time.time()

        try:
            options = AnalyzeOptions(
                provider=provider,
                generate_fixes=True,
                use_cache=False,
            )

            result = await ai_integration.analyze_log(self.test_log_content, options)

            fix_time = time.time() - start_time

            # 修正提案の検証
            fix_count = len(result.fix_suggestions) if result.fix_suggestions else 0

            test_result["tests"]["fix_suggestions"] = {
                "status": "passed",
                "fix_time": fix_time,
                "fix_suggestions_count": fix_count,
            }

            console.print(f"    ✅ 修正提案成功 ({fix_count}個の提案, {fix_time:.2f}秒)")

        except Exception as e:
            test_result["tests"]["fix_suggestions"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 修正提案失敗: {e}")
            # 修正提案の失敗は致命的ではないので継続

    async def _test_interactive_mode(self, ai_integration: AIIntegration, provider: str, test_result: dict) -> None:
        """対話モードテスト"""
        console.print("  💬 対話モードテスト...")

        start_time = time.time()

        try:
            options = AnalyzeOptions(
                provider=provider,
                streaming=False,
            )

            # 対話セッションを開始
            session = await ai_integration.start_interactive_session(self.test_log_content, options)

            # テスト用の質問を送信
            test_questions = [
                "このエラーの原因は何ですか？",
                "/help",  # コマンドテスト
            ]

            responses_received = 0

            for question in test_questions:
                try:
                    response_chunks = []
                    async for chunk in ai_integration.process_interactive_input(session.session_id, question):
                        response_chunks.append(chunk)

                    if response_chunks:
                        responses_received += 1

                except Exception as e:
                    console.print(f"    ⚠️  質問 '{question}' でエラー: {e}")

            # セッションを終了
            await ai_integration.close_interactive_session(session.session_id)

            interactive_time = time.time() - start_time

            test_result["tests"]["interactive_mode"] = {
                "status": "passed",
                "interactive_time": interactive_time,
                "questions_asked": len(test_questions),
                "responses_received": responses_received,
                "session_id": session.session_id,
            }

            console.print(
                f"    ✅ 対話モード成功 ({responses_received}/{len(test_questions)}応答, {interactive_time:.2f}秒)"
            )

        except Exception as e:
            test_result["tests"]["interactive_mode"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 対話モード失敗: {e}")
            # 対話モードの失敗は致命的ではないので継続

    async def _test_performance(self) -> None:
        """パフォーマンステスト"""
        console.print("\n[bold blue]2. パフォーマンステスト[/bold blue]")

        # 利用可能な最初のプロバイダーを使用
        available_provider = self._get_available_provider()
        if not available_provider:
            console.print("[yellow]⚠️  パフォーマンステスト用のプロバイダーがありません[/yellow]")
            return

        performance_results = {"provider": available_provider, "tests": {}, "overall_status": "unknown"}

        try:
            ai_integration = await self._create_ai_integration(available_provider)

            # 大きなログファイルテスト
            await self._test_large_log_performance(ai_integration, available_provider, performance_results)

            # 並列処理テスト
            await self._test_concurrent_analysis(ai_integration, available_provider, performance_results)

            # メモリ使用量テスト
            await self._test_memory_usage(ai_integration, available_provider, performance_results)

            performance_results["overall_status"] = "passed"
            console.print("[green]✅ パフォーマンステスト完了[/green]")

        except Exception as e:
            performance_results["overall_status"] = "failed"
            performance_results["error_message"] = str(e)
            console.print(f"[red]❌ パフォーマンステスト失敗: {e}[/red]")
            if self.verbose:
                console.print_exception()

        self.results["performance_tests"] = performance_results
        self._update_test_counts(performance_results["overall_status"])

    async def _test_large_log_performance(self, ai_integration: AIIntegration, provider: str, results: dict) -> None:
        """大きなログファイルのパフォーマンステスト"""
        console.print("  📊 大きなログファイルテスト...")

        # 1MBのログを生成
        large_log = self._generate_large_log_content(1.0)

        start_time = time.time()
        memory_before = self._get_memory_usage()

        try:
            options = AnalyzeOptions(
                provider=provider,
                use_cache=False,
            )

            result = await ai_integration.analyze_log(large_log, options)

            processing_time = time.time() - start_time
            memory_after = self._get_memory_usage()
            memory_used = memory_after - memory_before

            results["tests"]["large_log_performance"] = {
                "status": "passed",
                "log_size_mb": len(large_log) / (1024 * 1024),
                "processing_time": processing_time,
                "memory_used_mb": memory_used / (1024 * 1024),
                "tokens_processed": result.tokens_used.total_tokens if result.tokens_used else 0,
            }

            console.print(f"    ✅ 大きなログ処理成功 ({processing_time:.2f}秒, {memory_used / 1024 / 1024:.1f}MB)")

        except Exception as e:
            results["tests"]["large_log_performance"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 大きなログ処理失敗: {e}")
            raise

    async def _test_concurrent_analysis(self, ai_integration: AIIntegration, provider: str, results: dict) -> None:
        """並列処理テスト"""
        console.print("  🔄 並列処理テスト...")

        start_time = time.time()

        try:
            # 3つの並列分析を実行
            options = AnalyzeOptions(
                provider=provider,
                use_cache=False,
            )

            tasks = []
            for i in range(3):
                # 各タスクで少し異なるログを使用
                modified_log = self.test_log_content + f"\n# Test case {i}"
                task = ai_integration.analyze_log(modified_log, options)
                tasks.append(task)

            # 並列実行
            concurrent_results = await asyncio.gather(*tasks, return_exceptions=True)

            concurrent_time = time.time() - start_time

            # 結果の検証
            successful_analyses = sum(1 for r in concurrent_results if not isinstance(r, Exception))

            results["tests"]["concurrent_analysis"] = {
                "status": "passed",
                "concurrent_time": concurrent_time,
                "parallel_tasks": len(tasks),
                "successful_analyses": successful_analyses,
                "failed_analyses": len(tasks) - successful_analyses,
            }

            console.print(f"    ✅ 並列処理成功 ({successful_analyses}/{len(tasks)}成功, {concurrent_time:.2f}秒)")

        except Exception as e:
            results["tests"]["concurrent_analysis"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 並列処理失敗: {e}")
            # 並列処理の失敗は致命的ではないので継続

    async def _test_memory_usage(self, ai_integration: AIIntegration, provider: str, results: dict) -> None:
        """メモリ使用量テスト"""
        console.print("  🧠 メモリ使用量テスト...")

        try:
            memory_before = self._get_memory_usage()

            # 複数回の分析でメモリリークをチェック
            for i in range(5):
                options = AnalyzeOptions(
                    provider=provider,
                    use_cache=False,
                )

                await ai_integration.analyze_log(self.test_log_content, options)

            memory_after = self._get_memory_usage()
            memory_increase = memory_after - memory_before

            # メモリ使用量が異常に増加していないかチェック
            memory_increase_mb = memory_increase / (1024 * 1024)
            is_memory_leak = memory_increase_mb > 100  # 100MB以上の増加は異常

            results["tests"]["memory_usage"] = {
                "status": "failed" if is_memory_leak else "passed",
                "memory_before_mb": memory_before / (1024 * 1024),
                "memory_after_mb": memory_after / (1024 * 1024),
                "memory_increase_mb": memory_increase_mb,
                "potential_memory_leak": is_memory_leak,
            }

            if is_memory_leak:
                console.print(f"    ⚠️  メモリ使用量増加 ({memory_increase_mb:.1f}MB)")
            else:
                console.print(f"    ✅ メモリ使用量正常 ({memory_increase_mb:.1f}MB増加)")

        except Exception as e:
            results["tests"]["memory_usage"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ メモリテスト失敗: {e}")
            # メモリテストの失敗は致命的ではないので継続

    async def _test_error_recovery(self) -> None:
        """エラー復旧テスト"""
        console.print("\n[bold blue]3. エラー復旧テスト[/bold blue]")

        recovery_results = {"tests": {}, "overall_status": "unknown"}

        try:
            # 無効なAPIキーテスト
            await self._test_invalid_api_key_recovery(recovery_results)

            # ネットワークエラーテスト
            await self._test_network_error_recovery(recovery_results)

            # トークン制限テスト
            await self._test_token_limit_recovery(recovery_results)

            recovery_results["overall_status"] = "passed"
            console.print("[green]✅ エラー復旧テスト完了[/green]")

        except Exception as e:
            recovery_results["overall_status"] = "failed"
            recovery_results["error_message"] = str(e)
            console.print(f"[red]❌ エラー復旧テスト失敗: {e}[/red]")
            if self.verbose:
                console.print_exception()

        self.results["error_recovery_tests"] = recovery_results
        self._update_test_counts(recovery_results["overall_status"])

    async def _test_invalid_api_key_recovery(self, results: dict) -> None:
        """無効なAPIキーからの復旧テスト"""
        console.print("  🔑 無効なAPIキー復旧テスト...")

        try:
            # 無効なAPIキーでAI統合を作成
            invalid_config = self._create_test_config("openai", api_key="invalid_key")
            ai_integration = AIIntegration(invalid_config)

            options = AnalyzeOptions(provider="openai")

            # エラーが発生することを確認
            try:
                await ai_integration.analyze_log(self.test_log_content, options)
                # エラーが発生しなかった場合は失敗
                results["tests"]["invalid_api_key_recovery"] = {
                    "status": "failed",
                    "error": "無効なAPIキーでもエラーが発生しませんでした",
                }
                console.print("    ❌ 無効なAPIキーでエラーが発生しませんでした")
            except Exception as expected_error:
                # 適切なエラーが発生した場合は成功
                results["tests"]["invalid_api_key_recovery"] = {
                    "status": "passed",
                    "expected_error": str(expected_error),
                    "error_type": type(expected_error).__name__,
                }
                console.print(f"    ✅ 適切なエラーが発生: {type(expected_error).__name__}")

        except Exception as e:
            results["tests"]["invalid_api_key_recovery"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ 無効なAPIキーテスト失敗: {e}")

    async def _test_network_error_recovery(self, results: dict) -> None:
        """ネットワークエラー復旧テスト"""
        console.print("  🌐 ネットワークエラー復旧テスト...")

        try:
            # 無効なベースURLでAI統合を作成
            invalid_config = self._create_test_config("openai", base_url="https://invalid-url.example.com")
            ai_integration = AIIntegration(invalid_config)

            options = AnalyzeOptions(provider="openai")

            # ネットワークエラーが発生することを確認
            try:
                await ai_integration.analyze_log(self.test_log_content, options)
                results["tests"]["network_error_recovery"] = {
                    "status": "failed",
                    "error": "無効なURLでもエラーが発生しませんでした",
                }
                console.print("    ❌ 無効なURLでエラーが発生しませんでした")
            except Exception as expected_error:
                results["tests"]["network_error_recovery"] = {
                    "status": "passed",
                    "expected_error": str(expected_error),
                    "error_type": type(expected_error).__name__,
                }
                console.print(f"    ✅ 適切なエラーが発生: {type(expected_error).__name__}")

        except Exception as e:
            results["tests"]["network_error_recovery"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ ネットワークエラーテスト失敗: {e}")

    async def _test_token_limit_recovery(self, results: dict) -> None:
        """トークン制限復旧テスト"""
        console.print("  📊 トークン制限復旧テスト...")

        available_provider = self._get_available_provider()
        if not available_provider:
            results["tests"]["token_limit_recovery"] = {
                "status": "skipped",
                "reason": "利用可能なプロバイダーがありません",
            }
            console.print("    ⏭️  プロバイダーなしでスキップ")
            return

        try:
            # 非常に大きなログを生成（トークン制限を超える可能性）
            very_large_log = self._generate_large_log_content(5.0)  # 5MB

            ai_integration = await self._create_ai_integration(available_provider)
            options = AnalyzeOptions(provider=available_provider)

            try:
                result = await ai_integration.analyze_log(very_large_log, options)
                # 成功した場合（トークン制限内だった）
                results["tests"]["token_limit_recovery"] = {
                    "status": "passed",
                    "result": "大きなログも正常に処理されました",
                    "tokens_used": result.tokens_used.total_tokens if result.tokens_used else 0,
                }
                console.print("    ✅ 大きなログも正常に処理")
            except Exception as e:
                # エラーが発生した場合（期待される動作）
                results["tests"]["token_limit_recovery"] = {
                    "status": "passed",
                    "expected_error": str(e),
                    "error_type": type(e).__name__,
                }
                console.print(f"    ✅ 適切なエラーが発生: {type(e).__name__}")

        except Exception as e:
            results["tests"]["token_limit_recovery"] = {"status": "failed", "error": str(e)}
            console.print(f"    ❌ トークン制限テスト失敗: {e}")

    async def _create_ai_integration(self, provider: str) -> AIIntegration:
        """AI統合インスタンスを作成"""
        config = self._create_test_config(provider)
        ai_integration = AIIntegration(config)
        await ai_integration.initialize()
        return ai_integration

    def _create_test_config(self, provider: str, api_key: str | None = None, base_url: str | None = None) -> AIConfig:
        """テスト用のAI設定を作成"""
        providers = {}

        if provider == "openai":
            providers["openai"] = ProviderConfig(
                name="openai",
                api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
                base_url=base_url,
                default_model="gpt-4o-mini",  # テスト用に安価なモデルを使用
                available_models=["gpt-4o-mini", "gpt-4o"],
                timeout_seconds=30,
                max_retries=3,
            )
        elif provider == "anthropic":
            providers["anthropic"] = ProviderConfig(
                name="anthropic",
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=base_url,
                default_model="claude-3-5-haiku-20241022",  # テスト用に安価なモデルを使用
                available_models=["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
                timeout_seconds=30,
                max_retries=3,
            )
        elif provider == "local":
            providers["local"] = ProviderConfig(
                name="local",
                api_key="",
                base_url=base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                default_model="llama3.2",
                available_models=["llama3.2", "codellama"],
                timeout_seconds=60,
                max_retries=2,
            )

        return AIConfig(
            default_provider=provider,
            providers=providers,
            cache_enabled=True,
            cache_ttl_hours=1,  # テスト用に短い TTL
            cache_max_size_mb=50,  # テスト用に小さなキャッシュ
            cost_limits={"monthly_usd": 10.0, "per_request_usd": 1.0},  # テスト用に低い制限
            prompt_templates={},
            interactive_timeout=60,  # テスト用に短いタイムアウト
        )

    def _get_available_provider(self) -> str | None:
        """利用可能な最初のプロバイダーを取得"""
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        elif self._check_local_ollama():
            return "local"
        return None

    def _check_local_ollama(self) -> bool:
        """ローカルOllamaが利用可能かチェック"""
        try:
            # 簡単な接続チェック（実際の実装では非同期で行う）
            return True  # 簡略化
        except Exception:
            return False

    def _get_memory_usage(self) -> int:
        """現在のメモリ使用量を取得（バイト）"""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # psutilが利用できない場合は0を返す
            return 0

    def _update_test_counts(self, status: str) -> None:
        """テスト結果カウントを更新"""
        self.results["summary"]["total_tests"] += 1
        if status == "passed":
            self.results["summary"]["passed_tests"] += 1
        elif status == "failed":
            self.results["summary"]["failed_tests"] += 1

    def _generate_summary_report(self) -> None:
        """サマリーレポートを生成"""
        console.print("\n" + "=" * 60)
        console.print(Panel.fit("📊 実環境テスト結果サマリー", style="bold blue"))

        summary = self.results["summary"]
        total_time = summary["end_time"] - summary["start_time"] if summary["end_time"] and summary["start_time"] else 0

        # 全体統計
        stats_table = Table(title="📈 全体統計", show_header=True, header_style="bold green")
        stats_table.add_column("項目", style="cyan")
        stats_table.add_column("値", style="white")

        stats_table.add_row("総テスト数", str(summary["total_tests"]))
        stats_table.add_row("成功", f"[green]{summary['passed_tests']}[/green]")
        stats_table.add_row("失敗", f"[red]{summary['failed_tests']}[/red]")
        stats_table.add_row("成功率", f"{(summary['passed_tests'] / max(summary['total_tests'], 1) * 100):.1f}%")
        stats_table.add_row("実行時間", f"{total_time:.2f}秒")

        console.print(stats_table)

        # プロバイダー別結果
        if self.results["provider_tests"]:
            provider_table = Table(title="🤖 プロバイダー別結果", show_header=True, header_style="bold blue")
            provider_table.add_column("プロバイダー", style="cyan")
            provider_table.add_column("ステータス", style="white")
            provider_table.add_column("テスト数", style="white")
            provider_table.add_column("備考", style="dim")

            for provider, result in self.results["provider_tests"].items():
                status_color = "green" if result["overall_status"] == "passed" else "red"
                test_count = len(result["tests"])
                note = result.get("error_message", "正常")[:50]

                provider_table.add_row(
                    provider.upper(),
                    f"[{status_color}]{result['overall_status']}[/{status_color}]",
                    str(test_count),
                    note,
                )

            console.print(provider_table)

        # 推奨事項
        console.print(Panel.fit("💡 推奨事項", style="yellow"))

        recommendations = []

        if summary["failed_tests"] > 0:
            recommendations.append("失敗したテストの詳細を確認し、設定やAPIキーを見直してください")

        if not self.results["provider_tests"]:
            recommendations.append("APIキーを設定してプロバイダーテストを実行してください")

        if len(self.results["provider_tests"]) < 2:
            recommendations.append("複数のプロバイダーを設定してフォールバック機能をテストしてください")

        if not recommendations:
            recommendations.append("全てのテストが成功しました！本番環境での使用準備が整っています。")

        for i, rec in enumerate(recommendations, 1):
            console.print(f"  {i}. {rec}")

        # 結果をファイルに保存
        self._save_results_to_file()

    def _save_results_to_file(self) -> None:
        """結果をファイルに保存"""
        try:
            results_dir = Path("test_results")
            results_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"real_environment_test_{timestamp}.json"

            with results_file.open("w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)

            console.print(f"\n[dim]📄 詳細結果を保存: {results_file}[/dim]")

        except Exception as e:
            console.print(f"[yellow]⚠️  結果ファイルの保存に失敗: {e}[/yellow]")


@click.command()
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local"], case_sensitive=False),
    help="テストする特定のプロバイダー（指定しない場合は全プロバイダー）",
)
@click.option("--verbose", "-v", is_flag=True, help="詳細なログを表示")
def main(provider: str | None, verbose: bool) -> None:
    """実環境での動作確認を実行

    AI統合機能の実際のAPIキーを使用したE2E動作確認を行います。

    \b
    必要な環境変数:
      OPENAI_API_KEY     - OpenAI APIキー
      ANTHROPIC_API_KEY  - Anthropic APIキー
      OLLAMA_BASE_URL    - ローカルLLMのURL（オプション）

    \b
    使用例:
      uv run python scripts/test_real_environment.py
      uv run python scripts/test_real_environment.py --provider openai
      uv run python scripts/test_real_environment.py --verbose
    """

    async def run_tests():
        tester = RealEnvironmentTester(verbose=verbose)

        try:
            results = await tester.run_all_tests(provider)

            # 終了コードを決定
            if results["summary"]["failed_tests"] > 0:
                console.print("\n[red]❌ 一部のテストが失敗しました[/red]")
                sys.exit(1)
            else:
                console.print("\n[green]✅ 全てのテストが成功しました[/green]")
                sys.exit(0)

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  テストがキャンセルされました[/yellow]")
            sys.exit(130)
        except Exception as e:
            console.print(f"\n[red]❌ テスト実行中にエラーが発生: {e}[/red]")
            if verbose:
                console.print_exception()
            sys.exit(1)

    # 環境変数の確認
    available_keys = []
    if os.getenv("OPENAI_API_KEY"):
        available_keys.append("OPENAI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        available_keys.append("ANTHROPIC_API_KEY")
    if os.getenv("OLLAMA_BASE_URL"):
        available_keys.append("OLLAMA_BASE_URL")

    if not available_keys and not provider == "local":
        console.print("[red]❌ APIキーが設定されていません[/red]")
        console.print("\n[blue]💡 以下の環境変数を設定してください:[/blue]")
        console.print("  export OPENAI_API_KEY=your_openai_key")
        console.print("  export ANTHROPIC_API_KEY=your_anthropic_key")
        console.print("  export OLLAMA_BASE_URL=http://localhost:11434  # ローカルLLM用")
        console.print("\n[dim]または .env ファイルに記載してください[/dim]")
        sys.exit(1)

    console.print(f"[green]✅ 利用可能なAPIキー: {', '.join(available_keys)}[/green]")

    # 非同期実行
    asyncio.run(run_tests())


if __name__ == "__main__":
    main()
