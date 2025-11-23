"""analyze コマンドの実装

AI分析機能を提供し、CI/CDの失敗ログを分析して根本原因の特定と修正提案を行います。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

if TYPE_CHECKING:
    from types import TracebackType

    from ci_helper.ai.models import AnalysisResult, AnalyzeOptions, FixSuggestion, InteractiveSession
    from ci_helper.utils.config import Config

from ci_helper.ai.exceptions import (
    APIKeyError,
    ConfigurationError,
    NetworkError,
    ProviderError,
    RateLimitError,
    SecurityError,
    TokenLimitError,
)
from ci_helper.ai.integration import AIIntegration
from ci_helper.core.error_handler import ErrorHandler
from ci_helper.core.exceptions import CIHelperError
from ci_helper.core.japanese_messages import JapaneseErrorHandler
from ci_helper.core.log_manager import LogManager
from ci_helper.ui.enhanced_formatter import EnhancedAnalysisFormatter

CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.6
TEXT_TRUNCATE_LENGTH = 30
CONTEXT_PREVIEW_LENGTH = 100
MAX_FILES_DISPLAY = 3
MAX_AUTO_WAIT_SECONDS = 120

logger = logging.getLogger(__name__)

console = Console()


class AnalysisErrorContext:
    """分析エラーのコンテキスト管理."""

    def __init__(self, console: Console, operation_name: str, *, verbose: bool = False) -> None:
        """初期化.

        Args:
            console: Richコンソール
            operation_name: 操作名
            verbose: 詳細表示フラグ.

        """
        self.console = console
        self.operation_name = operation_name
        self.verbose = verbose
        self.start_time = datetime.now(UTC)
        self.error_count = 0

    def __enter__(self) -> Self:
        """コンテキスト開始."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """コンテキスト終了."""
        if exc_type is not None:
            self.error_count += 1
            duration = (datetime.now(UTC) - self.start_time).total_seconds()

            # エラー統計をログに記録
            logger.error("操作 '%s' が %.2f秒後にエラーで終了: %s", self.operation_name, duration, exc_val)

        return False  # エラーを再発生させる

    def log_progress(self, message: str) -> None:
        """進捗をログに記録."""
        elapsed = (datetime.now(UTC) - self.start_time).total_seconds()
        if self.verbose:
            self.console.print(f"[dim][{elapsed:.1f}s] {message}[/dim]")


@click.command()
@click.option(
    "--log",
    "log_file",
    type=click.Path(exists=True, path_type=Path),
    help="分析するログファイルのパス(指定しない場合は最新のログを使用)",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local"], case_sensitive=False),
    help="使用するAIプロバイダー(設定ファイルの値を上書き)",
)
@click.option(
    "--model",
    help="使用するAIモデル(例: gpt-4o, claude-3-sonnet)",
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
    help="ストリーミングレスポンスの有効/無効(設定ファイルの値を上書き)",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="AIレスポンスキャッシュの使用(デフォルト: 有効)",
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
    help="出力形式(デフォルト: markdown)",
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
    help="失敗した操作をリトライ(操作IDを指定)",
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
    r"""CI/CDの失敗ログをAIで分析.

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
    # デフォルトのコンソールを初期化（エラーハンドリング用）
    console = Console()
    config: Config | None = None

    try:
        # コンテキストから設定を取得
        config = ctx.obj["config"]
        if config is None:
            raise CIHelperError("設定が読み込まれていません")

        if "console" in ctx.obj:
            console = ctx.obj["console"]

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

        # 分析設定の作成
        analysis_config = AnalysisConfig(
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
        )

        # 非同期実行
        asyncio.run(
            _run_analysis(
                ai_integration=ai_integration,
                config=analysis_config,
                console=console,
            ),
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]分析がキャンセルされました。[/yellow]")
        console.print("[dim]部分的な結果が保存されている場合があります。[/dim]")
        sys.exit(130)
    except CIHelperError as e:
        # 日本語エラーハンドラーを使用
        japanese_handler = JapaneseErrorHandler()
        error_info = japanese_handler.handle_error(e, "analyze コマンド実行中")

        console.print(f"[red]❌ {error_info['message']}[/red]")

        if error_info["suggestion"]:
            console.print(f"[blue]💡 解決方法:[/blue] {error_info['suggestion']}")

        if error_info["recovery_steps"]:
            console.print("[blue]📋 復旧手順:[/blue]")
            for i, step in enumerate(error_info["recovery_steps"], 1):
                console.print(f"  {i}. {step}")

        # フォールバック機能の提案
        _suggest_fallback_options(console, log_file)

        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)
    except Exception as e:
        # 日本語エラーハンドラーを使用
        japanese_handler = JapaneseErrorHandler()
        error_info = japanese_handler.handle_error(e, "AI分析実行中")

        console.print(f"[red]❌ {error_info['message']}[/red]")

        # AI固有のエラーハンドリング（詳細）
        _handle_analysis_error(e, console, verbose)

        # 自動復旧の提案と実行
        recovery_choice = _offer_interactive_recovery(console)

        if recovery_choice == "auto":
            console.print("\n[blue]🔄 自動復旧を準備中...[/blue]")
            console.print("[yellow]自動復旧は次回のコマンド実行時に利用可能です[/yellow]")
            console.print("[cyan]ci-run analyze --retry auto[/cyan] で自動復旧を試行できます")

            # 復旧情報を保存（同期的に実行）
            try:
                recovery_info = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "options": {
                        "provider": provider,
                        "model": model,
                        "custom_prompt": custom_prompt,
                        "fix": fix,
                        "interactive": interactive,
                        "streaming": streaming,
                        "cache": cache,
                        "output_format": output_format,
                        "verbose": verbose,
                    },
                    "log_file": str(log_file) if log_file else None,
                }

                # 復旧情報をファイルに保存
                if config:
                    recovery_dir = config.get_path("cache_dir") / "recovery"
                    recovery_dir.mkdir(parents=True, exist_ok=True)
                    recovery_file = recovery_dir / "last_error.json"

                    import json

                    with recovery_file.open("w", encoding="utf-8") as f:
                        json.dump(recovery_info, f, ensure_ascii=False, indent=2)

                    console.print(f"[dim]復旧情報を保存しました: {recovery_file}[/dim]")

            except Exception as save_error:
                console.print(f"[yellow]⚠️  復旧情報の保存に失敗: {save_error}[/yellow]")

        elif recovery_choice == "manual":
            # 手動対処のガイダンスを表示
            _suggest_fallback_options(console, log_file)

        # recovery_choice == "skip" の場合はそのまま終了

        # 一般的なエラーハンドリング
        ErrorHandler.handle_error(e, verbose)
        sys.exit(1)


@dataclass
class AnalysisConfig:
    """分析設定。"""

    log_file: Path | None
    provider: str | None
    model: str | None
    custom_prompt: str | None
    fix: bool
    interactive: bool
    streaming: bool | None
    use_cache: bool
    output_format: str
    verbose: bool


async def _run_analysis(
    ai_integration: AIIntegration,
    config: AnalysisConfig,
    console: Console,
) -> None:
    """AI分析の実行.

    Args:
        ai_integration: AI統合インスタンス
        config: 分析設定
        console: Richコンソール

    """
    log_file = config.log_file
    provider = config.provider
    model = config.model
    custom_prompt = config.custom_prompt
    fix = config.fix
    interactive = config.interactive
    streaming = config.streaming
    use_cache = config.use_cache
    output_format = config.output_format
    verbose = config.verbose
    # 変数を初期化して例外ブロックでの未定義エラーを防ぐ
    log_content = ""
    options: AnalyzeOptions | None = None

    try:
        # AI統合の初期化
        await ai_integration.initialize()

        # ログファイルの決定
        if log_file is None and ai_integration.config:
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
            force_ai_analysis=True,  # プロバイダー指定時はAI分析を強制
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

        # 自動復旧を提案（非対話的）
        console.print("\n[blue]💡 自動復旧オプション:[/blue]")
        console.print("  コマンドを再実行すると自動復旧を試行できます")
        console.print("  [cyan]ci-run analyze --retry auto[/cyan]")

        raise
    finally:
        # リソースをクリーンアップ
        try:
            # プロバイダーのリソースを解放
            if ai_integration.providers:
                for p in ai_integration.providers.values():
                    # 型チェックを回避するためにAnyとして扱う
                    provider_obj: Any = p
                    if provider_obj and hasattr(provider_obj, "cleanup"):
                        await provider_obj.cleanup()
        except Exception:
            pass


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
                _display_fix_suggestions(result, console)

                # 修正適用の確認
                # テスト環境やCI環境では適切にハンドリング
                fixes_applied = await _handle_fix_application(ai_integration, result, console)

                # 修正が拒否された場合は終了コード1で終了
                if not fixes_applied:
                    console.print("\n[yellow]修正が適用されませんでした。[/yellow]")
                    sys.exit(1)

        except Exception as e:
            progress.stop()
            # AI固有のエラーハンドリング
            _handle_analysis_error(e, console, verbose=False)
            raise


async def _run_interactive_mode(
    ai_integration: AIIntegration,
    log_content: str,
    options: AnalyzeOptions,
    console: Console,
) -> None:
    """対話モードの実行.

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
                await _process_interactive_turn(ai_integration, session, console)
            except Exception as e:
                _handle_interactive_error(e, console)
    except KeyboardInterrupt:
        console.print("\n[yellow]対話セッションを終了します。[/yellow]")
    except Exception as e:
        console.print(f"\n[red]対話セッションでエラーが発生しました:[/red] {e}")
        _handle_analysis_error(e, console, verbose=False)
    finally:
        with contextlib.suppress(Exception):
            await ai_integration.close_interactive_session(session.session_id)


async def _process_interactive_turn(
    ai_integration: AIIntegration,
    session: InteractiveSession,
    console: Console,
) -> None:
    """対話の1ターンを処理."""
    # ユーザー入力の取得
    user_input = console.input("[bold blue]> [/bold blue]")

    if not user_input.strip():
        return

    # AI応答の処理
    async for response_chunk in ai_integration.process_interactive_input(session.session_id, user_input):
        console.print(response_chunk, end="")

    console.print()  # 改行


def _handle_interactive_error(e: Exception, console: Console) -> None:
    """対話エラーの処理."""
    # 個別の対話エラーを処理。セッションは継続します。
    console.print(f"\n[red]対話中にエラーが発生しました:[/red] {e}")

    # エラータイプに応じた詳細なガイダンス
    if isinstance(e, RateLimitError):
        _handle_interactive_rate_limit(e, console)
    elif isinstance(e, NetworkError):
        _handle_interactive_network_error(console)
    elif isinstance(e, TokenLimitError):
        _handle_interactive_token_limit(console)
    else:
        _handle_interactive_generic_error(console)

    # 対話継続のオプション
    console.print("\n[blue]🔄 対話オプション:[/blue]")
    console.print("  [green]/retry[/green] - 最後の質問を再試行")
    console.print("  [yellow]/help[/yellow] - 利用可能なコマンドを表示")
    console.print("  [red]/exit[/red] - 対話セッションを終了")

    # エラー統計の更新
    console.print(f"[dim]エラー発生時刻: {datetime.now(UTC).strftime('%H:%M:%S')}[/dim]")


def _handle_interactive_rate_limit(e: RateLimitError, console: Console) -> None:
    """レート制限エラーの処理."""
    retry_time = e.retry_after or 60
    console.print(f"[yellow]⏱️  レート制限に達しました。{retry_time}秒後に再試行してください。[/yellow]")

    # 短時間の場合は自動待機を提案
    if retry_time <= MAX_AUTO_WAIT_SECONDS:
        console.print("[blue]💡 自動待機しますか? (y/n)[/blue]")


def _handle_interactive_network_error(console: Console) -> None:
    """ネットワークエラーの処理."""
    console.print("[yellow]🌐 ネットワークエラーです。接続を確認してください。[/yellow]")
    console.print("[blue]💡 復旧手順:[/blue]")
    console.print("  1. インターネット接続を確認")
    console.print("  2. プロキシ設定を確認")
    console.print("  3. '/retry' で再試行")


def _handle_interactive_token_limit(console: Console) -> None:
    """トークン制限エラーの処理."""
    console.print("[yellow]📊 入力が長すぎます。より短い質問を試してください。[/yellow]")
    console.print("[blue]💡 対処法:[/blue]")
    console.print("  • 質問を短縮する")
    console.print("  • '/summarize' で要約を依頼")
    console.print("  • '/model smaller' で小さなモデルに変更")


def _handle_interactive_generic_error(console: Console) -> None:
    """一般的なエラーの処理."""
    console.print("[yellow]⚠️  一時的なエラーの可能性があります。[/yellow]")
    console.print("[blue]💡 対処法:[/blue]")
    console.print("  • '/retry' で再試行")
    console.print("  • '/provider switch' で別のプロバイダーに変更")
    console.print("  • '/reset' でセッションをリセット")


def _display_fix_suggestions(result: AnalysisResult, console: Console) -> None:
    """修正提案の表示.

    Args:
        result: 分析結果
        console: Richコンソール

    """
    console.print("\n[bold green]修正提案が生成されました:[/bold green]")

    for i, suggestion in enumerate(result.fix_suggestions, 1):
        console.print(f"\n[bold]修正案 {i}:[/bold]")
        console.print(f"タイトル: {suggestion.title}")
        console.print(f"説明: {suggestion.description}")

        # コード変更がある場合はファイルパスを表示
        if suggestion.code_changes:
            files = {change.file_path for change in suggestion.code_changes}
            console.print(f"対象ファイル: {', '.join(files)}")

        console.print(f"優先度: {suggestion.priority.value}")
        console.print(f"推定作業時間: {suggestion.estimated_effort}")
        console.print(f"信頼度: {suggestion.confidence:.1%}")


async def _handle_fix_application(
    ai_integration: AIIntegration,
    result: AnalysisResult,
    console: Console,
) -> bool:
    """修正提案の適用処理.

    Args:
        ai_integration: AI統合インスタンス
        result: 分析結果
        console: Richコンソール

    Returns:
        bool: 少なくとも1つの修正が適用された場合True、そうでなければFalse

    """
    console.print("\n[bold yellow]修正提案を適用しますか?[/bold yellow]")

    applied_count = 0
    user_rejected = False

    for i, suggestion in enumerate(result.fix_suggestions, 1):
        try:
            # 修正の適用確認
            if click.confirm(f"修正案 {i} ({suggestion.title}) を適用しますか?"):
                try:
                    await ai_integration.apply_fix(suggestion)
                    console.print(f"[green]修正案 {i} を適用しました。[/green]")
                    applied_count += 1
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
                        try:
                            continue_applying = click.confirm("他の修正案の適用を続けますか？")
                            if not continue_applying:
                                console.print("[yellow]修正案の適用を中止しました。[/yellow]")
                                user_rejected = True
                                break
                        except (EOFError, KeyboardInterrupt, click.exceptions.Abort):
                            console.print("[yellow]修正案の適用を中止しました。[/yellow]")
                            break
            else:
                console.print(f"[yellow]修正案 {i} をスキップしました。[/yellow]")
                user_rejected = True
        except (EOFError, KeyboardInterrupt, click.exceptions.Abort):
            # 入力が利用できない場合(テスト環境など)やユーザーがキャンセルした場合
            console.print("\n[dim]対話的入力が利用できません。修正提案のみ表示されました。[/dim]")
            # 入力が利用できない場合は拒否とは見なさない
            break

    # 修正が適用されたか、またはユーザーが明示的に拒否していない場合は成功
    return applied_count > 0 or not user_rejected


def _display_analysis_result(result: AnalysisResult, output_format: str, console: Console) -> None:
    """分析結果の表示。

    Args:
        result: 分析結果
        output_format: 出力形式
        console: Richコンソール

    """
    # 拡張フォーマッターを使用
    formatter = EnhancedAnalysisFormatter(console, language="ja")

    if output_format in ["enhanced", "markdown", "json", "table"]:
        formatter.format_analysis_result(result, output_format)
    # フォールバック: 従来の表示方式
    elif output_format == "json":
        import json
        from dataclasses import asdict

        console.print(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    elif output_format == "table":
        _display_result_as_table(result, console)
    else:  # markdown
        display_result_as_markdown(result, console)


def display_result_as_markdown(result: AnalysisResult, console: Console) -> None:
    """分析結果をMarkdown形式で表示。

    Args:
        result: 分析結果
        console: Richコンソール

    """
    # フォールバック情報を最初に表示
    _display_fallback_info(result, console)

    console.print(Panel.fit("🔍 AI分析結果", style="blue"))
    console.print()

    # パターン認識結果を表示(新機能)
    _display_pattern_recognition_results(result, console)

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
            # 信頼度を表示(新機能)
            if hasattr(cause, "confidence") and cause.confidence > 0:
                console.print(f"   信頼度: {cause.confidence:.1%}")
        console.print()

    # 修正提案(詳細表示に拡張)
    if result.fix_suggestions:
        _display_detailed_fix_suggestions(result.fix_suggestions, console)

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
    """分析結果をテーブル形式で表示。

    Args:
        result: 分析結果
        console: Richコンソール

    """
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
    """AI使用統計の表示。

    Args:
        config: 設定オブジェクト
        console: Richコンソール

    """
    try:
        from ..ai.cost_manager import CostManager

        storage_path = config.get_path("cache_dir") / "ai" / "usage.json"
        cost_manager = CostManager(storage_path, config.get_ai_cost_limits())
        stats = cost_manager.get_monthly_report(datetime.now(UTC).year, datetime.now(UTC).month)

        console.print(Panel.fit("📊 AI使用統計", style="blue"))
        console.print()

        # 月間統計
        if stats.get("stats"):
            monthly = stats["stats"]
            console.print("[bold]今月の使用量:[/bold]")
            console.print(f"総トークン数: {monthly.get('total_tokens', 0):,}")
            console.print(f"総コスト: ${monthly.get('total_cost', 0):.4f}")
            console.print(f"リクエスト数: {monthly.get('total_requests', 0)}")
            console.print(f"成功率: {monthly.get('success_rate', 0):.1%}")
            console.print()

        # プロバイダー別統計
        if stats.get("provider_breakdown"):
            console.print("[bold]プロバイダー別使用量:[/bold]")
            for provider, data in stats["provider_breakdown"].items():
                if isinstance(data, dict):
                    data_dict = cast("dict[str, Any]", data)
                    console.print(
                        f"{provider}: {data_dict.get('total_tokens', 0):,} トークン, ${data_dict.get('total_cost', 0):.4f}",
                    )
                else:
                    console.print(f"{provider}: {data:,} 回使用")

    except Exception as e:
        console.print(f"[red]統計情報の取得に失敗しました: {e}[/red]")


def _get_latest_log_file(config: Config) -> Path | None:
    """最新のログファイルを取得。

    Args:
        config: 設定オブジェクト

    Returns:
        最新のログファイルのパス(見つからない場合はNone)

    """
    try:
        log_manager = LogManager(config)
        logs: list[dict[str, Any]] = log_manager.list_logs()
        if logs:
            log_dir = config.get_path("log_dir")
            log_filename = logs[0].get("log_file") or logs[0].get("file_path")
            if log_filename:
                return log_dir / log_filename
        return None
    except Exception as e:
        logger.debug("Failed to get latest log: %s", e)
        return None


def _read_log_file(log_file: Path) -> str:
    """ログファイルの内容を読み込み。

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
        msg = f"ログファイルの読み込みに失敗しました: {e}"
        raise CIHelperError(msg) from e


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


def _display_pattern_recognition_results(result: AnalysisResult, console: Console) -> None:
    """パターン認識結果を詳細表示。

    Args:
        result: 分析結果
        console: Richコンソール

    """
    # パターンマッチ情報がある場合のみ表示
    pattern_matches = getattr(result, "pattern_matches", None)
    if not pattern_matches:
        return

    console.print(Panel.fit("🎯 検出されたパターン", style="green"))
    console.print()

    _display_pattern_table(pattern_matches, console)
    console.print()

    # 詳細なパターンマッチ情報を表示
    for i, match in enumerate(pattern_matches[:3], 1):  # 上位3つのみ詳細表示
        _display_single_pattern_detail(i, match, console)


def _display_pattern_table(pattern_matches: list[Any], console: Console) -> None:
    """パターンマッチテーブルを表示。"""
    pattern_table = Table(title="パターン認識結果", show_header=True, header_style="bold green")
    pattern_table.add_column("パターン名", style="cyan", width=25)
    pattern_table.add_column("カテゴリ", style="yellow", width=12)
    pattern_table.add_column("信頼度", style="green", width=10)
    pattern_table.add_column("マッチ理由", style="white", width=35)

    for match in pattern_matches:
        # 信頼度を色分け
        confidence_color = (
            "green"
            if match.confidence >= CONFIDENCE_HIGH
            else "yellow"
            if match.confidence >= CONFIDENCE_MEDIUM
            else "red"
        )
        confidence_text = f"[{confidence_color}]{match.confidence:.1%}[/{confidence_color}]"

        # マッチ理由を構築
        match_reasons: list[str] = []
        if hasattr(match, "supporting_evidence") and match.supporting_evidence:
            match_reasons.extend(match.supporting_evidence[:2])  # 最初の2つの証拠のみ
        if not match_reasons:
            match_reasons = ["パターンマッチ検出"]

        reason_text = ", ".join(match_reasons)
        if len(reason_text) > TEXT_TRUNCATE_LENGTH:
            reason_text = reason_text[: TEXT_TRUNCATE_LENGTH - 3] + "..."

        pattern_table.add_row(match.pattern.name, match.pattern.category, confidence_text, reason_text)

    console.print(pattern_table)


def _display_single_pattern_detail(index: int, match: Any, console: Console) -> None:
    """個別のパターン詳細を表示。"""
    console.print(f"[bold cyan]パターン {index}: {match.pattern.name}[/bold cyan]")
    console.print(f"  カテゴリ: {match.pattern.category}")
    console.print(f"  信頼度: {match.confidence:.1%}")

    if hasattr(match, "extracted_context") and match.extracted_context:
        context_preview = match.extracted_context[:CONTEXT_PREVIEW_LENGTH]
        if len(match.extracted_context) > CONTEXT_PREVIEW_LENGTH:
            context_preview += "..."
        console.print(f"  コンテキスト: [dim]{context_preview}[/dim]")

    if hasattr(match, "supporting_evidence") and match.supporting_evidence:
        console.print("  検出根拠:")
        for evidence in match.supporting_evidence[:3]:  # 最初の3つの証拠
            console.print(f"    • {evidence}")

    console.print()


def _display_detailed_fix_suggestions(fix_suggestions: list[FixSuggestion], console: Console) -> None:
    """修正提案を詳細表示。

    Args:
        fix_suggestions: 修正提案のリスト
        console: Richコンソール

    """
    console.print("[bold]修正提案:[/bold]")

    # 修正提案をランキング形式で表示
    for i, fix in enumerate(fix_suggestions, 1):
        _display_single_fix_suggestion(i, fix, console)

    # 修正提案のランキング表示(効果と安全性による)
    if len(fix_suggestions) > 1:
        _display_fix_suggestions_ranking(fix_suggestions, console)


def _display_single_fix_suggestion(index: int, fix: FixSuggestion, console: Console) -> None:
    """個別の修正提案を表示。"""
    _display_fix_header(index, fix, console)
    _display_fix_metrics(fix, console)
    _display_fix_details(fix, console)


def _display_fix_header(index: int, fix: FixSuggestion, console: Console) -> None:
    """修正提案のヘッダーを表示。"""
    priority_colors = {"urgent": "red", "high": "yellow", "medium": "blue", "low": "dim"}
    priority = getattr(fix, "priority", "medium")
    priority_val: Any = priority
    priority_str = priority_val.value if hasattr(priority_val, "value") else str(priority_val)
    priority_color = priority_colors.get(priority_str.lower(), "blue")

    console.print(f"\n[bold {priority_color}]修正案 {index}: {fix.title}[/bold {priority_color}]")
    console.print(f"  説明: {fix.description}")


def _display_fix_metrics(fix: FixSuggestion, console: Console) -> None:
    """修正提案のメトリクスを表示。"""
    if hasattr(fix, "confidence") and fix.confidence > 0:
        if fix.confidence >= CONFIDENCE_HIGH:
            confidence_color = "green"
        elif fix.confidence >= CONFIDENCE_MEDIUM:
            confidence_color = "yellow"
        else:
            confidence_color = "red"
        console.print(f"  信頼度: [{confidence_color}]{fix.confidence:.1%}[/{confidence_color}]")

    if hasattr(fix, "background_reason") and fix.background_reason:
        console.print(f"  [bold cyan]背景理由:[/bold cyan] {fix.background_reason}")

    if hasattr(fix, "impact_assessment") and fix.impact_assessment:
        console.print(f"  [bold yellow]影響評価:[/bold yellow] {fix.impact_assessment}")

    _display_risk_and_time_details(fix, console)


def _display_fix_details(fix: FixSuggestion, console: Console) -> None:
    """修正提案の詳細を表示。"""
    if hasattr(fix, "code_changes") and fix.code_changes:
        files = {change.file_path for change in fix.code_changes}
        console.print(f"  影響ファイル: {', '.join(list(files)[:MAX_FILES_DISPLAY])}")
        if len(files) > MAX_FILES_DISPLAY:
            console.print(f"    ... 他 {len(files) - MAX_FILES_DISPLAY} ファイル")

    if hasattr(fix, "prerequisites") and fix.prerequisites:
        console.print("  [bold magenta]前提条件:[/bold magenta]")
        for prereq in fix.prerequisites[:3]:
            console.print(f"    • {prereq}")

    if hasattr(fix, "validation_steps") and fix.validation_steps:
        console.print("  [bold green]検証ステップ:[/bold green]")
        for step in fix.validation_steps[:3]:
            console.print(f"    • {step}")

    if hasattr(fix, "references") and fix.references:
        console.print("  参考:")
        for ref in fix.references[:2]:
            console.print(f"    • {ref}")


def _display_risk_and_time_details(fix_suggestion: FixSuggestion, console: Console) -> None:
    """リスク評価と推定時間の詳細表示

    Args:
        fix_suggestion: 修正提案
        console: Richコンソール

    """
    # リスクレベルの表示
    risk_level = getattr(fix_suggestion, "risk_level", "medium")
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}
    risk_color = risk_colors.get(risk_level, "yellow")
    console.print(f"  リスクレベル: [{risk_color}]{risk_level.upper()}[/{risk_color}]")

    # 推定時間の詳細表示
    estimated_time_minutes = getattr(fix_suggestion, "estimated_time_minutes", 0)
    if estimated_time_minutes > 0:
        if estimated_time_minutes < 60:
            time_str = f"{estimated_time_minutes}分"
        else:
            hours = estimated_time_minutes // 60
            minutes = estimated_time_minutes % 60
            time_str = f"{hours}時間{minutes}分" if minutes > 0 else f"{hours}時間"
        console.print(f"  推定時間: {time_str}")
    elif hasattr(fix_suggestion, "estimated_effort") and fix_suggestion.estimated_effort != "不明":
        console.print(f"  推定時間: {fix_suggestion.estimated_effort}")

    # 効果と安全性のスコア表示
    effectiveness_score = getattr(fix_suggestion, "effectiveness_score", 0.0)
    safety_score = getattr(fix_suggestion, "safety_score", 0.0)

    if effectiveness_score > 0 or safety_score > 0:
        # 小さなテーブルでスコアを表示
        score_table = Table(show_header=False, box=None, padding=(0, 1))
        score_table.add_column("項目", style="dim")
        score_table.add_column("スコア", style="bold")

        if effectiveness_score > 0:
            eff_color = "green" if effectiveness_score >= 0.8 else "yellow" if effectiveness_score >= 0.6 else "red"
            score_table.add_row("効果", f"[{eff_color}]{effectiveness_score:.1%}[/{eff_color}]")

        if safety_score > 0:
            safety_color = "green" if safety_score >= 0.8 else "yellow" if safety_score >= 0.6 else "red"
            score_table.add_row("安全性", f"[{safety_color}]{safety_score:.1%}[/{safety_color}]")

        console.print("  評価スコア:")
        console.print(score_table)


def _display_fix_suggestions_ranking(fix_suggestions: list[FixSuggestion], console: Console) -> None:
    """修正提案のランキング表示（効果と安全性による）

    Args:
        fix_suggestions: 修正提案のリスト
        console: Richコンソール

    """
    console.print("\n[bold blue]修正提案ランキング (効果・安全性順):[/bold blue]")

    ranking_table = Table(show_header=True, header_style="bold blue")
    ranking_table.add_column("順位", style="cyan", width=4)
    ranking_table.add_column("修正案", style="white", width=25)
    ranking_table.add_column("効果", style="green", width=8)
    ranking_table.add_column("安全性", style="yellow", width=8)
    ranking_table.add_column("リスク", style="red", width=8)
    ranking_table.add_column("総合評価", style="blue", width=10)

    # 修正提案をスコアでソート
    scored_fixes: list[tuple[FixSuggestion, float, float, float, float]] = []
    for fix in fix_suggestions:
        effectiveness = getattr(fix, "effectiveness_score", getattr(fix, "confidence", 0.5))
        safety = getattr(fix, "safety_score", 1.0 - _calculate_risk_score(fix))
        risk_score = _calculate_risk_score(fix)
        overall = effectiveness * 0.4 + safety * 0.4 + (1.0 - risk_score) * 0.2

        scored_fixes.append((fix, effectiveness, safety, risk_score, overall))

    # 総合評価でソート（降順）
    scored_fixes.sort(key=lambda x: x[4], reverse=True)

    for i, (fix, effectiveness, safety, risk_score, overall) in enumerate(scored_fixes[:5], 1):
        # 色分け
        eff_color = "green" if effectiveness >= 0.8 else "yellow" if effectiveness >= 0.6 else "red"
        safety_color = "green" if safety >= 0.8 else "yellow" if safety >= 0.6 else "red"
        risk_color = "green" if risk_score <= 0.3 else "yellow" if risk_score <= 0.6 else "red"
        overall_color = "green" if overall >= 0.8 else "yellow" if overall >= 0.6 else "red"

        ranking_table.add_row(
            str(i),
            fix.title[:22] + "..." if len(fix.title) > 25 else fix.title,
            f"[{eff_color}]{effectiveness:.1%}[/{eff_color}]",
            f"[{safety_color}]{safety:.1%}[/{safety_color}]",
            f"[{risk_color}]{risk_score:.1%}[/{risk_color}]",
            f"[{overall_color}]{overall:.1%}[/{overall_color}]",
        )

    console.print(ranking_table)

    # 推奨修正案の表示
    if scored_fixes:
        best_fix = scored_fixes[0][0]
        console.print(f"\n[bold green]🎯 推奨修正案: {best_fix.title}[/bold green]")

        # 推奨理由を表示
        reasons: list[str] = []
        if scored_fixes[0][1] >= 0.8:  # 効果が高い
            reasons.append("高い効果が期待できます")
        if scored_fixes[0][2] >= 0.8:  # 安全性が高い
            reasons.append("安全性が高く低リスクです")
        if scored_fixes[0][3] <= 0.3:  # リスクが低い
            reasons.append("実装リスクが低いです")

        if reasons:
            console.print(f"  理由: {', '.join(reasons)}")

    console.print()


def _calculate_risk_score(fix_suggestion: FixSuggestion) -> float:
    """修正提案のリスクスコアを計算

    Args:
        fix_suggestion: 修正提案

    Returns:
        リスクスコア (0.0-1.0, 高いほどリスキー)

    """
    risk_score = 0.0

    # リスクレベルによる直接的なリスク（新機能）
    risk_level = getattr(fix_suggestion, "risk_level", "medium")
    risk_level_scores = {"low": 0.2, "medium": 0.5, "high": 0.8}
    risk_score += risk_level_scores.get(risk_level, 0.5)

    # 優先度によるリスク
    priority_risks = {"urgent": 0.8, "high": 0.6, "medium": 0.3, "low": 0.1}
    priority = getattr(fix_suggestion, "priority", "medium")
    if hasattr(priority, "value"):
        priority = cast("Any", priority).value
    risk_score += priority_risks.get(str(priority).lower(), 0.3) * 0.3  # 重み付けを調整

    # ファイル変更数によるリスク
    if hasattr(fix_suggestion, "code_changes") and fix_suggestion.code_changes:
        file_count = len({change.file_path for change in fix_suggestion.code_changes})
        risk_score += min(file_count * 0.05, 0.2)  # 重み付けを調整

    # 推定時間によるリスク
    estimated_time_minutes = getattr(fix_suggestion, "estimated_time_minutes", 0)
    if estimated_time_minutes > 0:
        # 長時間の作業ほどリスクが高い
        time_risk = min(estimated_time_minutes / 480.0, 0.3)  # 8時間で最大リスク
        risk_score += time_risk

    return min(risk_score, 1.0)


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


def _handle_analysis_error(error: Exception, console: Console, verbose: bool) -> None:
    """分析エラーの処理

    AI固有のエラーに対してユーザーフレンドリーなメッセージを表示します。

    Args:
        error: 発生したエラー
        console: Richコンソール
        verbose: 詳細表示フラグ

    """
    # エラーの重要度を判定
    error_severity = _determine_error_severity(error)
    severity_color = _get_severity_color(error_severity)

    # エラーヘッダーを表示
    console.print(f"\n[{severity_color}]{'=' * 60}[/{severity_color}]")
    console.print(f"[{severity_color}]🚨 AI分析エラーが発生しました[/{severity_color}]")
    console.print(f"[{severity_color}]{'=' * 60}[/{severity_color}]")

    if isinstance(error, APIKeyError):
        _handle_api_key_error_enhanced(error, console, verbose)

    elif isinstance(error, RateLimitError):
        _handle_rate_limit_error_enhanced(error, console, verbose)

    elif isinstance(error, TokenLimitError):
        _handle_token_limit_error_enhanced(error, console, verbose)

    elif isinstance(error, NetworkError):
        _handle_network_error_enhanced(error, console, verbose)

    elif isinstance(error, ConfigurationError):
        _handle_configuration_error_enhanced(error, console, verbose)

    elif isinstance(error, ProviderError):
        _handle_provider_error_enhanced(error, console, verbose)

    else:
        _handle_generic_error_enhanced(error, console, verbose)

    # 共通のフッター情報を表示
    _display_error_footer(error, console, verbose)


def _determine_error_severity(error: Exception) -> str:
    """エラーの重要度を判定

    Args:
        error: 発生したエラー

    Returns:
        エラーの重要度 (critical, high, medium, low)

    """
    if isinstance(error, APIKeyError | SecurityError | ConfigurationError):
        return "critical"
    if isinstance(error, RateLimitError | NetworkError):
        return "medium"
    if isinstance(error, ProviderError | TokenLimitError):
        return "high"
    return "low"


def _get_severity_color(severity: str) -> str:
    """重要度に応じた色を取得

    Args:
        severity: エラーの重要度

    Returns:
        Rich用の色名

    """
    colors = {
        "critical": "bright_red",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
    }
    return colors.get(severity, "white")


def _handle_api_key_error_enhanced(error: APIKeyError, console: Console, verbose: bool) -> None:
    """APIキーエラーの拡張処理"""
    console.print(f"\n[bright_red]🔑 APIキーエラー ({error.provider})[/bright_red]")
    console.print(f"[red]{error.message}[/red]")

    # 環境変数名を決定
    env_var_name = f"{error.provider.upper()}_API_KEY"
    if error.provider == "openai":
        env_var_name = "OPENAI_API_KEY"
    elif error.provider == "anthropic":
        env_var_name = "ANTHROPIC_API_KEY"

    console.print("\n[blue]📋 段階的解決手順:[/blue]")
    console.print(f"  1️⃣  環境変数を設定: [cyan]export {env_var_name}=your_api_key[/cyan]")
    console.print("  2️⃣  APIキーの有効性を確認")
    console.print(f"  3️⃣  {error.provider}ダッシュボードで権限を確認")
    console.print("  4️⃣  設定後にコマンドを再実行")

    # プロバイダー固有の追加情報
    if error.provider == "openai":
        console.print("\n[dim]💡 OpenAI APIキー取得: https://platform.openai.com/api-keys[/dim]")
        console.print("[dim]💡 使用制限確認: https://platform.openai.com/usage[/dim]")
    elif error.provider == "anthropic":
        console.print("[dim]💡 Anthropic APIキー取得: https://console.anthropic.com/[/dim]")

    # 代替手段の提案
    console.print("\n[green]🔄 代替手段:[/green]")
    console.print("  • 別のプロバイダーを試す: [cyan]--provider local[/cyan]")
    console.print("  • 従来のログ表示: [cyan]ci-run logs --show latest[/cyan]")


def _handle_rate_limit_error_enhanced(error: RateLimitError, console: Console, verbose: bool) -> None:
    """レート制限エラーの拡張処理"""
    console.print(f"\n[yellow]⏱️  レート制限エラー ({error.provider})[/yellow]")
    console.print(f"[yellow]{error.message}[/yellow]")

    # 待機時間の表示
    if error.retry_after:
        minutes, seconds = divmod(error.retry_after, 60)
        if minutes > 0:
            console.print(f"[blue]⏰ 待機時間: {minutes}分{seconds}秒[/blue]")
        else:
            console.print(f"[blue]⏰ 待機時間: {seconds}秒[/blue]")
    elif error.reset_time:
        console.print(f"[blue]⏰ 制限リセット: {error.reset_time.strftime('%H:%M:%S')}[/blue]")

    console.print("\n[blue]📋 対処方法:[/blue]")
    console.print("  1️⃣  しばらく待ってから再試行")
    console.print("  2️⃣  より小さなモデルを使用: [cyan]--model gpt-4o-mini[/cyan]")
    console.print("  3️⃣  入力を短縮または分割")
    console.print("  4️⃣  プランのアップグレードを検討")

    # 自動リトライの提案
    if error.retry_after and error.retry_after <= 300:  # 5分以内
        console.print("\n[green]🔄 自動リトライが利用可能です[/green]")
        console.print("[dim]コマンドを再実行すると自動的に待機してリトライします[/dim]")


def _handle_token_limit_error_enhanced(error: TokenLimitError, console: Console, verbose: bool) -> None:
    """トークン制限エラーの拡張処理"""
    console.print("\n[red]📊 トークン制限エラー[/red]")
    console.print(f"[red]{error.message}[/red]")

    # トークン使用量の詳細表示
    usage_percentage = (error.used_tokens / error.limit) * 100
    console.print("\n[yellow]📈 トークン使用状況:[/yellow]")
    console.print(f"  使用量: {error.used_tokens:,} / {error.limit:,} ({usage_percentage:.1f}%)")
    console.print(f"  モデル: {error.model}")
    console.print(f"  超過量: {error.used_tokens - error.limit:,} トークン")

    # 削減提案の計算
    reduction_needed = ((error.used_tokens - error.limit) / error.used_tokens) * 100
    console.print("\n[blue]📋 解決方法:[/blue]")
    console.print(f"  1️⃣  入力を約{reduction_needed:.1f}%削減")
    console.print("  2️⃣  より大きなモデルを使用: [cyan]--model gpt-4-turbo[/cyan]")
    console.print("  3️⃣  ログを要約してから分析")
    console.print("  4️⃣  複数の小さなチャンクに分割")

    # 自動圧縮の提案
    console.print("\n[green]🗜️  自動圧縮機能が利用可能です[/green]")
    console.print("[dim]--compress オプションで自動的にログを圧縮できます[/dim]")


def _handle_network_error_enhanced(error: NetworkError, console: Console, verbose: bool) -> None:
    """ネットワークエラーの拡張処理"""
    console.print("\n[yellow]🌐 ネットワークエラー[/yellow]")
    console.print(f"[yellow]{error.message}[/yellow]")

    if error.retry_count > 0:
        console.print(f"[blue]🔄 リトライ回数: {error.retry_count}/3[/blue]")

    console.print("\n[blue]📋 診断手順:[/blue]")
    console.print("  1️⃣  インターネット接続を確認")
    console.print("  2️⃣  プロキシ設定を確認")
    console.print("  3️⃣  ファイアウォール設定を確認")
    console.print("  4️⃣  DNS設定を確認")

    # 接続テストの提案
    console.print("\n[green]🔍 接続テスト:[/green]")
    console.print("  • OpenAI: [cyan]curl -I https://api.openai.com[/cyan]")
    console.print("  • Anthropic: [cyan]curl -I https://api.anthropic.com[/cyan]")

    # 自動リトライ情報
    if error.retry_count < 3:
        retry_delay = min(2**error.retry_count, 60)
        console.print(f"\n[green]🔄 自動リトライ: {retry_delay}秒後に実行されます[/green]")


def _handle_configuration_error_enhanced(error: ConfigurationError, console: Console, verbose: bool) -> None:
    """設定エラーの拡張処理"""
    console.print("\n[red]⚙️  設定エラー[/red]")
    console.print(f"[red]{error.message}[/red]")

    if error.config_key:
        console.print(f"[yellow]🔑 問題のある設定キー: {error.config_key}[/yellow]")

    console.print("\n[blue]📋 設定修復手順:[/blue]")
    console.print("  1️⃣  設定ファイルを確認: [cyan]ci-helper.toml[/cyan]")
    console.print("  2️⃣  環境変数を確認: [cyan]env | grep CI_HELPER[/cyan]")
    console.print("  3️⃣  環境診断を実行: [cyan]ci-run doctor[/cyan]")
    console.print("  4️⃣  設定を再生成: [cyan]ci-run init[/cyan]")

    # 設定例の表示
    console.print("\n[green]📝 設定例:[/green]")
    console.print("[dim][ai][/dim]")
    console.print('[dim]default_provider = "openai"[/dim]')
    console.print("[dim]cache_enabled = true[/dim]")


def _handle_provider_error_enhanced(error: ProviderError, console: Console, verbose: bool) -> None:
    """プロバイダーエラーの拡張処理"""
    console.print(f"\n[red]🔌 プロバイダーエラー ({error.provider})[/red]")
    console.print(f"[red]{error.message}[/red]")

    if error.details:
        console.print(f"[yellow]📋 詳細: {error.details}[/yellow]")

    console.print("\n[blue]📋 解決手順:[/blue]")
    console.print("  1️⃣  プロバイダー設定を確認")
    console.print("  2️⃣  APIキーの有効性を確認")
    console.print("  3️⃣  サービス状況を確認")
    console.print("  4️⃣  別のプロバイダーを試す")

    # 代替プロバイダーの提案
    alternatives: list[str] = []
    if error.provider != "openai":
        alternatives.append("openai")
    if error.provider != "anthropic":
        alternatives.append("anthropic")
    if error.provider != "local":
        alternatives.append("local")

    if alternatives:
        console.print("\n[green]🔄 代替プロバイダー:[/green]")
        for alt in alternatives:
            console.print(f"  • {alt}: [cyan]--provider {alt}[/cyan]")

    # サービス状況確認リンク
    status_urls = {
        "openai": "https://status.openai.com/",
        "anthropic": "https://status.anthropic.com/",
    }
    if error.provider in status_urls:
        console.print(f"\n[dim]🔍 サービス状況: {status_urls[error.provider]}[/dim]")


def _handle_generic_error_enhanced(error: Exception, console: Console, verbose: bool) -> None:
    """汎用エラーの拡張処理"""
    error_type = type(error).__name__
    console.print(f"\n[red]❌ 予期しないエラー ({error_type})[/red]")
    console.print(f"[red]{error}[/red]")

    console.print("\n[blue]📋 トラブルシューティング:[/blue]")
    console.print("  1️⃣  詳細ログで確認: [cyan]--verbose[/cyan]")
    console.print("  2️⃣  環境を診断: [cyan]ci-run doctor[/cyan]")
    console.print("  3️⃣  キャッシュをクリア: [cyan]ci-run clean[/cyan]")
    console.print("  4️⃣  設定をリセット: [cyan]ci-run init[/cyan]")

    # バグレポートの提案
    console.print("\n[green]🐛 バグレポート:[/green]")
    console.print("  問題が続く場合は GitHub Issues で報告してください")
    console.print("  [cyan]https://github.com/scottlz0310/ci-helper/issues[/cyan]")


def _display_error_footer(error: Exception, console: Console, verbose: bool) -> None:
    """エラー表示のフッター情報"""
    console.print(f"\n[dim]{'─' * 60}[/dim]")

    # エラー発生時刻
    console.print(f"[dim]⏰ エラー発生時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

    # エラータイプ
    console.print(f"[dim]🏷️  エラータイプ: {type(error).__name__}[/dim]")

    # 詳細表示モードの場合はエラー詳細を表示
    if verbose:
        console.print("\n[dim]📊 詳細なエラー情報:[/dim]")
        console.print(f"[dim]エラーメッセージ: {error!s}[/dim]")
        if hasattr(error, "__traceback__") and error.__traceback__:
            import traceback

            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            console.print(f"[dim]{tb_str}[/dim]")

    # ヘルプ情報
    console.print("\n[blue]💡 追加ヘルプ:[/blue]")
    console.print("  • コマンドヘルプ: [cyan]ci-run analyze --help[/cyan]")
    console.print("  • 環境診断: [cyan]ci-run doctor[/cyan]")
    console.print("  • 設定ガイド: [cyan]ci-run init[/cyan]")

    console.print(f"[dim]{'─' * 60}[/dim]")


def _suggest_fallback_options(console: Console, log_file: Path | None) -> None:
    """フォールバックオプションの提案

    AI分析が失敗した場合の代替手段を提案します。

    Args:
        console: Richコンソール
        log_file: 分析対象のログファイル

    """
    from rich.panel import Panel

    # フォールバックオプションをテーブル形式で表示
    console.print(Panel.fit("🔄 利用可能な代替手段", style="blue"))

    # 即座に実行可能な代替手段
    immediate_table = Table(title="🚀 即座に実行可能", show_header=True, header_style="bold blue")
    immediate_table.add_column("方法", style="cyan", width=20)
    immediate_table.add_column("コマンド", style="green", width=35)
    immediate_table.add_column("説明", style="white", width=25)

    # ログファイル関連の代替手段
    if log_file and log_file.exists():
        immediate_table.add_row("📄 ログ直接確認", f"cat {log_file}", "ログファイルを直接表示")
        immediate_table.add_row("📋 従来ログ表示", "ci-run logs --show latest", "整形されたログ表示")
    else:
        immediate_table.add_row("🔄 新規テスト実行", "ci-run test", "新しいログを生成")
        immediate_table.add_row("📋 過去ログ確認", "ci-run logs", "既存のログ一覧表示")

    # 環境診断
    immediate_table.add_row("🔍 環境診断", "ci-run doctor", "システム環境をチェック")

    console.print(immediate_table)

    # AI代替プロバイダー
    ai_table = Table(title="🤖 AI代替プロバイダー", show_header=True, header_style="bold yellow")
    ai_table.add_column("プロバイダー", style="cyan", width=15)
    ai_table.add_column("コマンド", style="green", width=40)
    ai_table.add_column("特徴", style="white", width=25)

    ai_table.add_row("OpenAI", "ci-run analyze --provider openai", "高精度、多機能")
    ai_table.add_row("Anthropic", "ci-run analyze --provider anthropic", "長文対応、安全性重視")
    ai_table.add_row("ローカルLLM", "ci-run analyze --provider local", "プライベート、無料")

    console.print(ai_table)

    # トラブルシューティング
    troubleshoot_table = Table(title="🧹 トラブルシューティング", show_header=True, header_style="bold red")
    troubleshoot_table.add_column("問題", style="cyan", width=20)
    troubleshoot_table.add_column("解決コマンド", style="green", width=35)
    troubleshoot_table.add_column("効果", style="white", width=25)

    troubleshoot_table.add_row("キャッシュ問題", "ci-run clean --cache-only", "AIキャッシュをクリア")
    troubleshoot_table.add_row("古いログ問題", "ci-run clean --logs-only", "古いログファイルを削除")
    troubleshoot_table.add_row("設定問題", "ci-run init", "設定ファイルを再生成")
    troubleshoot_table.add_row("全体リセット", "ci-run clean --all", "全データをクリア")

    console.print(troubleshoot_table)

    # 段階的復旧手順
    console.print(Panel.fit("📋 段階的復旧手順", style="green"))
    console.print("[bold green]1. 基本診断[/bold green]")
    console.print("   [cyan]ci-run doctor[/cyan] - 環境の基本チェック")
    console.print()
    console.print("[bold green]2. 設定確認[/bold green]")
    console.print("   [cyan]ci-run init[/cyan] - 設定ファイルの再生成")
    console.print()
    console.print("[bold green]3. 代替プロバイダー[/bold green]")
    console.print("   [cyan]ci-run analyze --provider local[/cyan] - ローカルLLMを試す")
    console.print()
    console.print("[bold green]4. 従来手法[/bold green]")
    console.print("   [cyan]ci-run logs --show latest[/cyan] - 従来のログ表示")

    # 緊急時の連絡先
    console.print(Panel.fit("🆘 緊急時の対応", style="red"))
    console.print("[bold red]問題が解決しない場合:[/bold red]")
    console.print("  📧 GitHub Issues: [cyan]https://github.com/scottlz0310/ci-helper/issues[/cyan]")
    console.print("  📚 ドキュメント: [cyan]https://github.com/scottlz0310/ci-helper/docs[/cyan]")
    console.print("  🔍 詳細ヘルプ: [cyan]ci-run analyze --help[/cyan]")

    # 自動復旧の提案
    console.print(Panel.fit("🤖 自動復旧オプション", style="blue"))
    console.print("[bold blue]自動復旧を試しますか？[/bold blue]")
    console.print("  Y: 基本的な修復を自動実行")
    console.print("  N: 手動で対処")
    console.print("  H: 詳細ヘルプを表示")

    # ユーザー入力を受け付ける場合の準備（実装は別途）
    console.print("\n[dim]💡 ヒント: 上記のコマンドをコピーして実行してください[/dim]")


async def _save_partial_analysis_state(
    ai_integration: AIIntegration,
    log_content: str,
    options: AnalyzeOptions | None,
    error: Exception,
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
        if ai_integration.fallback_handler:
            from ..ai.fallback_handler import PartialResultData

            partial_data: PartialResultData = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "log_content": log_content[:1000],  # 最初の1000文字のみ保存
            }

            if options:
                partial_data["options"] = {
                    "provider": options.provider,
                    "model": options.model,
                    "output_format": options.output_format,
                }

            await ai_integration.fallback_handler.save_partial_result(
                operation_id,
                partial_data,
            )
    except Exception:
        # 部分保存の失敗は無視
        pass


def _offer_interactive_recovery(console: Console) -> str:
    """対話的な復旧オプションを提供

    Args:
        console: Richコンソール

    Returns:
        ユーザーの選択 ('auto', 'manual', 'skip')

    """
    from rich.panel import Panel
    from rich.prompt import Prompt

    console.print(Panel.fit("🤖 自動復旧オプション", style="blue"))
    console.print("[bold blue]どのように対処しますか？[/bold blue]")
    console.print("  [green]A[/green] - 自動復旧を試行")
    console.print("  [yellow]M[/yellow] - 手動で対処")
    console.print("  [red]S[/red] - スキップして終了")

    choice = Prompt.ask("選択してください", choices=["A", "M", "S", "a", "m", "s"], default="A").upper()

    choice_map = {"A": "auto", "M": "manual", "S": "skip"}

    return choice_map.get(choice, "auto")


def _validate_analysis_environment(config: Config, console: Console) -> bool:
    """分析環境の事前検証

    AI分析を実行する前に環境が適切に設定されているかチェックします。

    Args:
        config: 設定オブジェクト
        console: Richコンソール

    Returns:
        環境が有効かどうか

    """
    issues: list[str] = []
    warnings: list[str] = []

    # AI設定の存在確認
    try:
        ai_config = config.get_ai_config()
        if not ai_config:
            warnings.append("AI設定が見つかりません（デフォルト設定を使用します）")
        elif isinstance(ai_config, dict) and not ai_config:
            warnings.append("AI設定が空です（デフォルト設定を使用します）")
    except Exception:
        warnings.append("AI設定の読み込みに失敗しました（デフォルト設定を使用します）")

    # 利用可能なプロバイダーの確認
    try:
        available_providers = config.get_available_ai_providers()
        if not available_providers:
            issues.append("利用可能なAIプロバイダーが見つかりません")
    except Exception:
        warnings.append("利用可能なプロバイダーの取得に失敗しました")

    # デフォルトプロバイダーの確認
    try:
        default_provider = config.get_default_ai_provider()
        if default_provider and default_provider != "local":
            # デフォルトプロバイダーのAPIキーのみチェック
            try:
                api_key = config.get_ai_provider_api_key(default_provider)
                if not api_key:
                    issues.append(f"{default_provider}のAPIキーが設定されていません")
                elif len(api_key) < 10:
                    warnings.append(f"{default_provider}のAPIキーが短すぎる可能性があります")
            except Exception:
                issues.append(f"{default_provider}のAPIキー取得に失敗しました")
    except Exception:
        warnings.append("デフォルトプロバイダーの取得に失敗しました")

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

        # デフォルトプロバイダーを取得
        try:
            default_provider = config.get_default_ai_provider()
        except Exception:
            default_provider = "openai"

        console.print("\n[blue]💡 段階的な解決方法:[/blue]")
        console.print("  1️⃣  APIキーを環境変数に設定:")
        if default_provider == "openai":
            console.print("     [cyan]export OPENAI_API_KEY=your_key[/cyan]")
        elif default_provider == "anthropic":
            console.print("     [cyan]export ANTHROPIC_API_KEY=your_key[/cyan]")
        else:
            console.print(f"     [cyan]export {default_provider.upper()}_API_KEY=your_key[/cyan]")
        console.print("  2️⃣  または別のプロバイダーを使用:")
        console.print("     [cyan]ci-run analyze --provider local[/cyan] (APIキー不要)")
        console.print("  3️⃣  [cyan]ci-run init[/cyan] で設定ファイルを再生成")
        console.print("  4️⃣  [cyan]ci-run doctor[/cyan] で詳細な環境チェック")
        return False

    return True
