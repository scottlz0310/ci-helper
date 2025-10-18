"""
analyze コマンドの実装

AI分析機能を提供し、CI/CDの失敗ログを分析して根本原因の特定と修正提案を行います。
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

if TYPE_CHECKING:
    from ..ai.models import AnalysisResult

from ..ai.integration import AIIntegration
from ..ai.models import AnalyzeOptions
from ..core.error_handler import ErrorHandler
from ..core.exceptions import CIHelperError
from ..core.log_manager import LogManager
from ..utils.config import Config

console = Console()


@click.command()
@click.option(
    "--log",
    "log_file",
    type=click.Path(exists=True, path_type=Path),
    help="分析するログファイルのパス（指定しない場合は最新のログを使用）",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local"], case_sensitive=False),
    help="使用するAIプロバイダー（設定ファイルの値を上書き）",
)
@click.option(
    "--model",
    help="使用するAIモデル（例: gpt-4o, claude-3-sonnet）",
)
@click.option(
    "--prompt",
    "custom_prompt",
    help="カスタムプロンプトを追加",
)
@click.option(
    "--fix",
    is_flag=True,
    help="修正提案を生成し、適用の確認を行う",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="対話的なAIデバッグモードを開始",
)
@click.option(
    "--streaming/--no-streaming",
    default=None,
    help="ストリーミングレスポンスの有効/無効（設定ファイルの値を上書き）",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="AIレスポンスキャッシュの使用（デフォルト: 有効）",
)
@click.option(
    "--stats",
    is_flag=True,
    help="AI使用統計を表示",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "table"], case_sensitive=False),
    default="markdown",
    help="出力形式（デフォルト: markdown）",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="詳細な実行情報を表示",
)
@click.option(
    "--retry",
    "retry_operation_id",
    help="失敗した操作をリトライ（操作IDを指定）",
)
@click.pass_context
def analyze(
    ctx: click.Context,
    log_file: Path | None,
    provider: str | None,
    model: str | None,
    custom_prompt: str | None,
    fix: bool,
    interactive: bool,
    streaming: bool | None,
    cache: bool,
    stats: bool,
    output_format: str,
    verbose: bool,
    retry_operation_id: str | None,
) -> None:
    """CI/CDの失敗ログをAIで分析

    指定されたログファイルまたは最新のテスト実行結果をAIが分析し、
    根本原因の特定と修正提案を提供します。

    \b
    使用例:
      ci-run analyze                           # 最新のログを分析
      ci-run analyze --log path/to/log         # 特定のログファイルを分析
      ci-run analyze --provider openai         # OpenAIプロバイダーを使用
      ci-run analyze --model gpt-4o            # 特定のモデルを使用
      ci-run analyze --fix                     # 修正提案を生成
      ci-run analyze --interactive             # 対話モードで分析
      ci-run analyze --stats                   # 使用統計を表示
    """
    try:
        # コンテキストから設定を取得
        config: Config = ctx.obj["config"]
        console: Console = ctx.obj["console"]

        # 統計表示のみの場合
        if stats:
            _display_stats(config, console)
            return

        # 環境の事前検証
        validation_result = _validate_analysis_environment(config, console)
        if not validation_result:
            console.print("\n[red]環境設定を修正してから再試行してください。[/red]")

            # フォールバック機能の提案
            _suggest_fallback_options(console, log_file)

            # より詳細なエラー情報を提供
            console.print("\n[dim]詳細なヘルプ: ci-run analyze --help[/dim]")
            sys.exit(1)

        # AI統合の初期化
        ai_integration = AIIntegration(config)

        # リトライ操作の場合
        if retry_operation_id:
            asyncio.run(_handle_retry_operation(ai_integration, retry_operation_id, console))
            return

        # 非同期実行
        asyncio.run(
            _run_analysis(
                ai_integration=ai_integration,
                log_file=log_file,
                provider=provider,
                model=model,
                custom_prompt=custom_prompt,
                fix=fix,
                interactive=interactive,
                streaming=streaming,
                use_cache=cache,
                output_format=output_format,
                verbose=verbose,
                console=console,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]分析がキャンセルされました。[/yellow]")
        console.print("[dim]部分的な結果が保存されている場合があります。[/dim]")
        sys.exit(130)
    except CIHelperError as e:
        # CI Helper固有のエラーを詳細に処理
        _handle_ci_helper_error(e, console, verbose)

        # フォールバック機能の提案
        _suggest_fallback_options(console, log_file)

        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)
    except Exception as e:
        # AI固有のエラーハンドリング
        _handle_analysis_error(e, console, verbose)

        # フォールバック機能の提案
        _suggest_fallback_options(console, log_file)

        # 一般的なエラーハンドリング
        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)


async def _run_analysis(
    ai_integration: AIIntegration,
    log_file: Path | None,
    provider: str | None,
    model: str | None,
    custom_prompt: str | None,
    fix: bool,
    interactive: bool,
    streaming: bool | None,
    use_cache: bool,
    output_format: str,
    verbose: bool,
    console: Console,
) -> None:
    """AI分析の実行

    Args:
        ai_integration: AI統合インスタンス
        log_file: 分析するログファイル
        provider: AIプロバイダー
        model: AIモデル
        custom_prompt: カスタムプロンプト
        fix: 修正提案フラグ
        interactive: 対話モードフラグ
        streaming: ストリーミングフラグ
        use_cache: キャッシュ使用フラグ
        output_format: 出力形式
        verbose: 詳細表示フラグ
        console: Richコンソール
    """
    try:
        # AI統合の初期化
        await ai_integration.initialize()

        # ログファイルの決定
        if log_file is None:
            log_file = _get_latest_log_file(ai_integration.config)

        if log_file is None:
            console.print("[red]分析するログファイルが見つかりません。[/red]")
            console.print("まず `ci-run test` を実行してログを生成してください。")
            return

        # ログ内容の読み込み
        log_content = _read_log_file(log_file)

        # 分析オプションの構築
        from ..ai.models import AnalyzeOptions

        options = AnalyzeOptions(
            provider=provider,
            model=model,
            custom_prompt=custom_prompt,
            streaming=streaming if streaming is not None else True,
            use_cache=use_cache,
            generate_fixes=fix,
            output_format=output_format,
        )

        # 対話モードの場合
        if interactive:
            await _run_interactive_mode(ai_integration, log_content, options, console)
            return

        # 通常の分析モード
        await _run_standard_analysis(ai_integration, log_content, options, verbose, console)

    except Exception as e:
        # より詳細なエラーハンドリング
        console.print("\n[red]分析処理中にエラーが発生しました:[/red]")
        _handle_analysis_error(e, console, verbose)

        # 部分的な結果の保存を試行
        try:
            await _save_partial_analysis_state(ai_integration, log_content, options, e)
            console.print("[dim]部分的な状態が保存されました。後でリトライできます。[/dim]")
        except Exception:
            pass  # 部分保存の失敗は無視

        raise


async def _run_standard_analysis(
    ai_integration: AIIntegration,
    log_content: str,
    options: AnalyzeOptions,
    verbose: bool,
    console: Console,
) -> None:
    """標準分析モードの実行

    Args:
        ai_integration: AI統合インスタンス
        log_content: ログ内容
        options: 分析オプション
        verbose: 詳細表示フラグ
        console: Richコンソール
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 分析タスクの開始
        task = progress.add_task("AI分析を実行中...", total=None)

        try:
            # AI分析の実行
            result = await ai_integration.analyze_log(log_content, options)

            progress.update(task, description="分析完了")
            progress.stop()

            # 結果の表示
            _display_analysis_result(result, options.output_format, console)

            # 修正提案の処理
            if options.generate_fixes and result.fix_suggestions:
                await _handle_fix_suggestions(ai_integration, result, console)

        except Exception as e:
            progress.stop()
            # AI固有のエラーハンドリング
            _handle_analysis_error(e, console, False)
            raise


async def _run_interactive_mode(
    ai_integration: AIIntegration,
    log_content: str,
    options: AnalyzeOptions,
    console: Console,
) -> None:
    """対話モードの実行

    Args:
        ai_integration: AI統合インスタンス
        log_content: ログ内容
        options: 分析オプション
        console: Richコンソール
    """
    console.print(Panel.fit("🤖 対話的AIデバッグモードを開始します", style="blue"))
    console.print("終了するには '/exit' と入力してください。")
    console.print("利用可能なコマンドは '/help' で確認できます。")
    console.print()

    # 対話セッションの開始
    session = await ai_integration.start_interactive_session(log_content, options)

    try:
        while session.is_active:
            try:
                # ユーザー入力の取得
                user_input = console.input("[bold blue]> [/bold blue]")

                if not user_input.strip():
                    continue

                # AI応答の処理
                async for response_chunk in ai_integration.process_interactive_input(session.session_id, user_input):
                    console.print(response_chunk, end="")

                console.print()  # 改行

            except Exception as e:
                # 個別の対話エラーを処理（セッションは継続）
                console.print(f"\n[red]対話中にエラーが発生しました:[/red] {e}")

                # エラータイプに応じた詳細なガイダンス
                from ..ai.exceptions import NetworkError, RateLimitError, TokenLimitError

                if isinstance(e, RateLimitError):
                    console.print(
                        f"[yellow]レート制限に達しました。{e.retry_after or 60}秒後に再試行してください。[/yellow]"
                    )
                elif isinstance(e, NetworkError):
                    console.print("[yellow]ネットワークエラーです。接続を確認してください。[/yellow]")
                elif isinstance(e, TokenLimitError):
                    console.print("[yellow]入力が長すぎます。より短い質問を試してください。[/yellow]")
                else:
                    console.print("[yellow]一時的なエラーの可能性があります。[/yellow]")

                console.print("[blue]💡 対話を続けるか、'/exit' で終了してください。[/blue]")
                console.print("[dim]ヒント: '/help' で利用可能なコマンドを確認できます[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]対話セッションを終了します。[/yellow]")
    except Exception as e:
        console.print(f"\n[red]対話セッションでエラーが発生しました:[/red] {e}")
        _handle_analysis_error(e, console, False)
    finally:
        try:
            await ai_integration.close_interactive_session(session.session_id)
        except Exception:
            # セッション終了エラーは無視（既に終了している可能性）
            pass


async def _handle_fix_suggestions(
    ai_integration: AIIntegration,
    result: AnalysisResult,
    console: Console,
) -> None:
    """修正提案の処理

    Args:
        ai_integration: AI統合インスタンス
        result: 分析結果
        console: Richコンソール
    """
    console.print("\n[bold green]修正提案が生成されました:[/bold green]")

    for i, suggestion in enumerate(result.fix_suggestions, 1):
        console.print(f"\n[bold]修正案 {i}:[/bold]")
        console.print(f"ファイル: {suggestion.file_path}")
        console.print(f"説明: {suggestion.description}")

        # 修正の適用確認
        if click.confirm(f"修正案 {i} を適用しますか？"):
            try:
                await ai_integration.apply_fix(suggestion)
                console.print(f"[green]修正案 {i} を適用しました。[/green]")
            except Exception as e:
                console.print(f"[red]修正案 {i} の適用に失敗しました:[/red] {e}")

                # 修正失敗の詳細なガイダンス
                console.print("[blue]💡 修正失敗の対処法:[/blue]")
                console.print("  • ファイルの権限を確認してください")
                console.print("  • ファイルが他のプロセスで使用されていないか確認")
                console.print("  • 手動で修正を適用することも可能です")
                console.print("  • バックアップから復元: [cyan]ci-run analyze --restore-backup[/cyan]")

                # 続行するかユーザーに確認
                if i < len(result.fix_suggestions):
                    continue_applying = click.confirm("他の修正案の適用を続けますか？")
                    if not continue_applying:
                        console.print("[yellow]修正案の適用を中止しました。[/yellow]")
                        break


def _display_analysis_result(result: AnalysisResult, output_format: str, console: Console) -> None:
    """分析結果の表示

    Args:
        result: 分析結果
        output_format: 出力形式
        console: Richコンソール
    """
    if output_format == "json":
        import json
        from dataclasses import asdict

        console.print(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    elif output_format == "table":
        _display_result_as_table(result, console)
    else:  # markdown
        _display_result_as_markdown(result, console)


def _display_result_as_markdown(result: AnalysisResult, console: Console) -> None:
    """分析結果をMarkdown形式で表示

    Args:
        result: 分析結果
        console: Richコンソール
    """
    # フォールバック情報を最初に表示
    _display_fallback_info(result, console)

    console.print(Panel.fit("🔍 AI分析結果", style="blue"))
    console.print()

    # 要約
    if result.summary:
        console.print("[bold]要約:[/bold]")
        console.print(result.summary)
        console.print()

    # 根本原因
    if result.root_causes:
        console.print("[bold]根本原因:[/bold]")
        for i, cause in enumerate(result.root_causes, 1):
            console.print(f"{i}. {cause.description}")
            if cause.file_path:
                console.print(f"   ファイル: {cause.file_path}")
            if cause.line_number:
                console.print(f"   行番号: {cause.line_number}")
        console.print()

    # 修正提案
    if result.fix_suggestions:
        console.print("[bold]修正提案:[/bold]")
        for i, fix in enumerate(result.fix_suggestions, 1):
            console.print(f"{i}. {fix.title}")
            console.print(f"   {fix.description}")
        console.print()

    # 関連エラー
    if result.related_errors:
        console.print("[bold]関連エラー:[/bold]")
        for error in result.related_errors[:5]:  # 最初の5個のみ表示
            console.print(f"- {error}")
        if len(result.related_errors) > 5:
            console.print(f"... 他 {len(result.related_errors) - 5} 個")
        console.print()

    # 統計情報
    console.print("[dim]統計情報:[/dim]")
    console.print(f"[dim]信頼度: {result.confidence_score:.1%}[/dim]")
    console.print(f"[dim]分析時間: {result.analysis_time:.2f}秒[/dim]")
    console.print(f"[dim]プロバイダー: {result.provider}[/dim]")
    console.print(f"[dim]モデル: {result.model}[/dim]")
    if result.tokens_used:
        console.print(f"[dim]使用トークン: {result.tokens_used.total_tokens:,}[/dim]")
        console.print(f"[dim]推定コスト: ${result.tokens_used.estimated_cost:.4f}[/dim]")
    if result.cache_hit:
        console.print("[dim]キャッシュヒット: はい[/dim]")


def _display_result_as_table(result: AnalysisResult, console: Console) -> None:
    """分析結果をテーブル形式で表示

    Args:
        result: 分析結果
        console: Richコンソール
    """
    from rich.table import Table

    table = Table(title="AI分析結果")
    table.add_column("項目", style="cyan")
    table.add_column("内容", style="white")

    if result.summary:
        table.add_row("要約", result.summary)
    if result.root_causes:
        root_causes_text = "\n".join(f"{i}. {cause.description}" for i, cause in enumerate(result.root_causes, 1))
        table.add_row("根本原因", root_causes_text)
    if result.fix_suggestions:
        suggestions_text = "\n".join(f"{i}. {fix.title}" for i, fix in enumerate(result.fix_suggestions, 1))
        table.add_row("修正提案", suggestions_text)

    console.print(table)


def _display_stats(config: Config, console: Console) -> None:
    """AI使用統計の表示

    Args:
        config: 設定オブジェクト
        console: Richコンソール
    """
    try:
        from ..ai.cost_manager import CostManager

        storage_path = config.get_path("cache_dir") / "ai" / "usage.json"
        cost_manager = CostManager(storage_path, config.get_ai_cost_limits())
        stats = cost_manager.get_monthly_usage(datetime.now().year, datetime.now().month)

        console.print(Panel.fit("📊 AI使用統計", style="blue"))
        console.print()

        # 月間統計
        if stats.get("monthly_usage"):
            monthly = stats["monthly_usage"]
            console.print("[bold]今月の使用量:[/bold]")
            console.print(f"総トークン数: {monthly.get('total_tokens', 0):,}")
            console.print(f"総コスト: ${monthly.get('total_cost', 0):.4f}")
            console.print(f"リクエスト数: {monthly.get('request_count', 0)}")
            console.print()

        # プロバイダー別統計
        if stats.get("by_provider"):
            console.print("[bold]プロバイダー別使用量:[/bold]")
            for provider, data in stats["by_provider"].items():
                console.print(f"{provider}: {data.get('total_tokens', 0):,} トークン, ${data.get('total_cost', 0):.4f}")

    except Exception as e:
        console.print(f"[red]統計情報の取得に失敗しました: {e}[/red]")


def _get_latest_log_file(config: Config) -> Path | None:
    """最新のログファイルを取得

    Args:
        config: 設定オブジェクト

    Returns:
        最新のログファイルのパス（見つからない場合はNone）
    """
    try:
        log_manager = LogManager(config)
        logs = log_manager.list_logs()
        if logs:
            return logs[0].file_path  # 最新のログ
        return None
    except Exception:
        return None


def _read_log_file(log_file: Path) -> str:
    """ログファイルの内容を読み込み

    Args:
        log_file: ログファイルのパス

    Returns:
        ログファイルの内容

    Raises:
        CIHelperError: ファイル読み込みに失敗した場合
    """
    try:
        return log_file.read_text(encoding="utf-8")
    except Exception as e:
        raise CIHelperError(f"ログファイルの読み込みに失敗しました: {e}") from e


async def _handle_retry_operation(ai_integration: AIIntegration, operation_id: str, console: Console) -> None:
    """失敗した操作をリトライ

    Args:
        ai_integration: AI統合インスタンス
        operation_id: 操作ID
        console: コンソール
    """
    try:
        console.print(f"[blue]操作 {operation_id} をリトライしています...[/blue]")

        # AI統合を初期化
        await ai_integration.initialize()

        # リトライを実行
        result = await ai_integration.retry_failed_operation(operation_id)

        if result:
            console.print("[green]✓ リトライが成功しました[/green]")
            _display_analysis_result(result, "markdown", console)
        else:
            console.print(f"[red]✗ 操作 {operation_id} のリトライに失敗しました[/red]")
            console.print("[yellow]操作IDが見つからないか、リトライ情報が利用できません。[/yellow]")

    except Exception as e:
        console.print(f"[red]✗ リトライ中にエラーが発生しました: {e}[/red]")

        # フォールバック提案を表示
        suggestions = await ai_integration.get_fallback_suggestions(e)
        if suggestions:
            console.print("\n[yellow]提案:[/yellow]")
            for i, suggestion in enumerate(suggestions, 1):
                console.print(f"  {i}. {suggestion}")


def _display_fallback_info(result: AnalysisResult, console: Console) -> None:
    """フォールバック情報を表示

    Args:
        result: 分析結果
        console: コンソール
    """
    if result.status.value != "fallback":
        return

    # フォールバック理由を表示
    if result.fallback_reason:
        console.print(f"\n[yellow]フォールバック理由: {result.fallback_reason}[/yellow]")

    # リトライ情報を表示
    if result.retry_available:
        if result.retry_after:
            console.print(f"[blue]💡 {result.retry_after}秒後にリトライできます[/blue]")
        else:
            console.print("[blue]💡 すぐにリトライできます[/blue]")

    # 代替プロバイダー情報を表示
    if result.alternative_providers:
        providers_text = ", ".join(result.alternative_providers)
        console.print(f"[blue]💡 代替プロバイダー: {providers_text}[/blue]")

    # 操作IDを表示（リトライ用）
    operation_id = f"fallback_{result.timestamp.strftime('%Y%m%d_%H%M%S')}"
    console.print(f"[dim]操作ID: {operation_id}[/dim]")
    console.print("[dim]リトライするには: ci-run analyze --retry {operation_id}[/dim]")


def _handle_ci_helper_error(error: CIHelperError, console: Console, verbose: bool) -> None:
    """CI Helper固有のエラーを処理

    Args:
        error: CI Helperエラー
        console: Richコンソール
        verbose: 詳細表示フラグ
    """
    from ..core.exceptions import ConfigurationError, DependencyError, ValidationError, WorkflowNotFoundError

    if isinstance(error, ConfigurationError):
        console.print(f"[red]設定エラー:[/red] {error.message}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • ci-run init で設定ファイルを再生成")
        console.print("  • ci-helper.toml の [ai] セクションを確認")
        console.print("  • 環境変数でAPIキーを設定")

    elif isinstance(error, DependencyError):
        console.print(f"[red]依存関係エラー:[/red] {error.message}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • ci-run doctor で環境をチェック")
        console.print("  • 必要な依存関係をインストール")

    elif isinstance(error, ValidationError):
        console.print(f"[red]入力検証エラー:[/red] {error.message}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • 入力パラメータを確認")
        console.print("  • ci-run analyze --help でオプションを確認")

    elif isinstance(error, WorkflowNotFoundError):
        console.print(f"[red]ワークフローエラー:[/red] {error.message}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • ci-run test でログを生成")
        console.print("  • --log オプションで特定のログファイルを指定")

    else:
        console.print(f"[red]CI Helperエラー:[/red] {error.message}")
        if error.suggestion:
            console.print(f"[blue]💡 解決方法:[/blue] {error.suggestion}")

    # 詳細表示モードの場合は追加情報を表示
    if verbose and hasattr(error, "details") and error.details:
        console.print(f"\n[dim]詳細: {error.details}[/dim]")


def _handle_analysis_error(error: Exception, console: Console, verbose: bool) -> None:
    """分析エラーの処理

    AI固有のエラーに対してユーザーフレンドリーなメッセージを表示します。

    Args:
        error: 発生したエラー
        console: Richコンソール
        verbose: 詳細表示フラグ
    """
    from ..ai.exceptions import (
        APIKeyError,
        ConfigurationError,
        NetworkError,
        ProviderError,
        RateLimitError,
        TokenLimitError,
    )

    if isinstance(error, APIKeyError):
        console.print(f"[red]APIキーエラー ({error.provider}):[/red] {error.message}")
        if error.suggestion:
            console.print(f"[yellow]解決方法:[/yellow] {error.suggestion}")
        console.print("\n[blue]APIキー設定ガイド:[/blue]")
        console.print(f"1. {error.provider.upper()}_API_KEY 環境変数を設定")
        console.print("2. ci-helper.toml の [ai.providers] セクションを確認")

    elif isinstance(error, RateLimitError):
        console.print(f"[red]レート制限エラー ({error.provider}):[/red] {error.message}")
        if error.retry_after:
            console.print(f"[yellow]{error.retry_after}秒後に再試行してください[/yellow]")
        elif error.reset_time:
            console.print(f"[yellow]制限リセット時刻: {error.reset_time.strftime('%H:%M:%S')}[/yellow]")
        console.print("[blue]💡 ヒント:[/blue] より小さなモデルを使用するか、入力を短縮してください")

    elif isinstance(error, TokenLimitError):
        console.print(f"[red]トークン制限エラー:[/red] {error.message}")
        console.print(f"[yellow]使用トークン:[/yellow] {error.used_tokens:,} / {error.limit:,}")
        console.print(f"[yellow]モデル:[/yellow] {error.model}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • より大きなコンテキストウィンドウを持つモデルを使用")
        console.print("  • ログファイルを分割して分析")
        console.print("  • --no-cache オプションで古いキャッシュを回避")

    elif isinstance(error, NetworkError):
        console.print(f"[red]ネットワークエラー:[/red] {error.message}")
        if error.retry_count > 0:
            console.print(f"[yellow]リトライ回数:[/yellow] {error.retry_count}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • インターネット接続を確認")
        console.print("  • プロキシ設定を確認")
        console.print("  • しばらく待ってから再試行")

    elif isinstance(error, ConfigurationError):
        console.print(f"[red]設定エラー:[/red] {error.message}")
        if error.config_key:
            console.print(f"[yellow]設定キー:[/yellow] {error.config_key}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • ci-helper.toml の [ai] セクションを確認")
        console.print("  • ci-run doctor で環境をチェック")
        console.print("  • ci-run init で設定を再生成")

    elif isinstance(error, ProviderError):
        console.print(f"[red]プロバイダーエラー ({error.provider}):[/red] {error.message}")
        if error.details:
            console.print(f"[yellow]詳細:[/yellow] {error.details}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • 別のプロバイダーを試す (--provider オプション)")
        console.print("  • APIキーと設定を確認")
        console.print("  • プロバイダーのサービス状況を確認")

    else:
        # 一般的なエラー
        console.print(f"[red]分析中にエラーが発生しました:[/red] {error}")
        console.print("[blue]💡 解決方法:[/blue]")
        console.print("  • --verbose フラグで詳細情報を確認")
        console.print("  • ci-run doctor で環境をチェック")
        console.print("  • 問題が続く場合は GitHub Issues で報告")

    # 詳細表示モードの場合はスタックトレースを表示
    if verbose:
        console.print("\n[dim]詳細なエラー情報:[/dim]")
        console.print_exception()


def _suggest_fallback_options(console: Console, log_file: Path | None) -> None:
    """フォールバックオプションの提案

    AI分析が失敗した場合の代替手段を提案します。

    Args:
        console: Richコンソール
        log_file: 分析対象のログファイル
    """
    console.print("\n[blue]💡 代替手段:[/blue]")

    # ログファイル関連の代替手段
    if log_file and log_file.exists():
        console.print(f"  📄 ログファイルを直接確認: [cyan]{log_file}[/cyan]")
        console.print("  📋 従来のログ表示: [cyan]ci-run logs --show latest[/cyan]")
    else:
        console.print("  🔄 新しいテストを実行: [cyan]ci-run test[/cyan]")
        console.print("  📋 過去のログを確認: [cyan]ci-run logs[/cyan]")

    # 環境・設定関連の代替手段
    console.print("  🔍 環境チェック: [cyan]ci-run doctor[/cyan]")
    console.print("  ⚙️  設定を再生成: [cyan]ci-run init[/cyan]")

    # AI関連の代替手段
    console.print("  🤖 別のプロバイダーを試す:")
    console.print("    • OpenAI: [cyan]ci-run analyze --provider openai[/cyan]")
    console.print("    • Anthropic: [cyan]ci-run analyze --provider anthropic[/cyan]")
    console.print("    • ローカルLLM: [cyan]ci-run analyze --provider local[/cyan]")

    # トラブルシューティング
    console.print("  🧹 トラブルシューティング:")
    console.print("    • キャッシュをクリア: [cyan]ci-run clean --cache-only[/cyan]")
    console.print("    • 古いログを削除: [cyan]ci-run clean --logs-only[/cyan]")
    console.print("    • 全てをリセット: [cyan]ci-run clean --all[/cyan]")

    console.print("\n[dim]📚 詳細なヘルプ: ci-run analyze --help[/dim]")
    console.print("[dim]🐛 問題が続く場合は GitHub Issues で報告してください[/dim]")


async def _save_partial_analysis_state(
    ai_integration: AIIntegration, log_content: str, options: AnalyzeOptions, error: Exception
) -> None:
    """部分的な分析状態を保存

    Args:
        ai_integration: AI統合インスタンス
        log_content: ログ内容
        options: 分析オプション
        error: 発生したエラー
    """
    try:
        from datetime import datetime

        operation_id = f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # フォールバックハンドラーを使用して部分的な結果を保存
        if hasattr(ai_integration, "fallback_handler"):
            await ai_integration.fallback_handler._save_partial_result(
                operation_id,
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "log_content": log_content[:1000],  # 最初の1000文字のみ保存
                    "options": {
                        "provider": options.provider,
                        "model": options.model,
                        "output_format": options.output_format,
                    },
                    "retry_available": True,
                },
            )
    except Exception:
        # 部分保存の失敗は無視
        pass


def _validate_analysis_environment(config: Config, console: Console) -> bool:
    """分析環境の事前検証

    AI分析を実行する前に環境が適切に設定されているかチェックします。

    Args:
        config: 設定オブジェクト
        console: Richコンソール

    Returns:
        環境が有効かどうか
    """
    issues = []
    warnings = []

    # AI設定の存在確認
    try:
        ai_config = config.get_ai_config()
        if not ai_config:
            issues.append("AI設定が見つかりません")
        elif isinstance(ai_config, dict) and not ai_config:
            issues.append("AI設定が空です")
    except Exception as e:
        issues.append(f"AI設定の読み込みに失敗しました: {e}")

    # プロバイダーの確認
    try:
        available_providers = config.get_available_ai_providers()
        if not available_providers:
            issues.append("利用可能なAIプロバイダーがありません")
        else:
            # APIキーの確認
            for provider in available_providers:
                if provider != "local":  # ローカルLLMはAPIキー不要
                    try:
                        api_key = config.get_ai_provider_api_key(provider)
                        if not api_key:
                            issues.append(f"{provider}のAPIキーが設定されていません")
                        elif len(api_key) < 10:  # 最小長チェック
                            warnings.append(f"{provider}のAPIキーが短すぎる可能性があります")
                    except Exception as e:
                        issues.append(f"{provider}のAPIキー取得に失敗: {e}")
    except Exception as e:
        issues.append(f"プロバイダー情報の取得に失敗しました: {e}")

    # 警告がある場合は表示（エラーではない）
    if warnings:
        console.print("[yellow]⚠️  警告:[/yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")

    # 問題がある場合は詳細なエラー表示
    if issues:
        console.print("[red]❌ 環境設定に問題があります:[/red]")
        for i, issue in enumerate(issues, 1):
            console.print(f"  {i}. {issue}")

        console.print("\n[blue]💡 段階的な解決方法:[/blue]")
        console.print("  1️⃣  [cyan]ci-run doctor[/cyan] で詳細な環境チェック")
        console.print("  2️⃣  [cyan]ci-run init[/cyan] で設定ファイルを再生成")
        console.print("  3️⃣  APIキーを環境変数に設定:")
        console.print("     • OpenAI: [cyan]export OPENAI_API_KEY=your_key[/cyan]")
        console.print("     • Anthropic: [cyan]export ANTHROPIC_API_KEY=your_key[/cyan]")
        console.print("  4️⃣  設定ファイルの [ai] セクションを確認")

        console.print("\n[dim]💡 ヒント: ローカルLLMを使用する場合はAPIキーは不要です[/dim]")
        return False

    return True
