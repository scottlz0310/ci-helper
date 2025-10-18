"""
analyze コマンドの実装

AI分析機能を提供し、CI/CDの失敗ログを分析して根本原因の特定と修正提案を行います。
"""

from __future__ import annotations

import asyncio
import sys
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
        sys.exit(130)
    except CIHelperError as e:
        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)
    except Exception as e:
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
        console.print(f"[red]分析中にエラーが発生しました: {e}[/red]")
        if verbose:
            console.print_exception()
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

        except Exception:
            progress.stop()
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
            # ユーザー入力の取得
            user_input = console.input("[bold blue]> [/bold blue]")

            if not user_input.strip():
                continue

            # AI応答の処理
            async for response_chunk in ai_integration.process_interactive_input(session.session_id, user_input):
                console.print(response_chunk, end="")

            console.print()  # 改行

    except KeyboardInterrupt:
        console.print("\n[yellow]対話セッションを終了します。[/yellow]")
    finally:
        await ai_integration.close_interactive_session(session.session_id)


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
                console.print(f"[red]修正案 {i} の適用に失敗しました: {e}[/red]")


def _display_analysis_result(result: AnalysisResult, output_format: str, console: Console) -> None:
    """分析結果の表示

    Args:
        result: 分析結果
        output_format: 出力形式
        console: Richコンソール
    """
    if output_format == "json":
        import json

        console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
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
    if result.root_cause:
        table.add_row("根本原因", result.root_cause)
    if result.recommendations:
        recommendations_text = "\n".join(f"{i}. {rec}" for i, rec in enumerate(result.recommendations, 1))
        table.add_row("推奨事項", recommendations_text)

    console.print(table)


def _display_stats(config: Config, console: Console) -> None:
    """AI使用統計の表示

    Args:
        config: 設定オブジェクト
        console: Richコンソール
    """
    try:
        from ..ai.cost_manager import CostManager

        cost_manager = CostManager(config)
        stats = cost_manager.get_usage_statistics()

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
