"""
feedback コマンドの実装

AI分析結果に対するフィードバックを収集し、学習システムに反映します。
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

console = Console()


@click.command()
@click.option(
    "--analysis-id",
    help="フィードバック対象の分析ID",
)
@click.option(
    "--rating",
    type=click.IntRange(1, 5),
    help="分析結果の評価（1-5）",
)
@click.pass_context
def feedback(ctx: click.Context, analysis_id: str | None, rating: int | None) -> None:
    """AI分析結果にフィードバックを提供

    分析結果の精度向上のため、フィードバックを収集します。
    収集されたフィードバックは学習システムに反映され、
    将来の分析精度が向上します。

    \b
    使用例:
      ci-run feedback                    # 対話的にフィードバック
      ci-run feedback --rating 5         # 評価のみ提供
    """
    from ..utils.config import Config

    config: Config = ctx.obj["config"]

    # 学習が有効か確認
    if not config.get_ai_config("learning_enabled", False):
        console.print("[yellow]学習機能が無効です。[/yellow]")
        console.print("ci-helper.tomlで learning_enabled = true に設定してください。")
        return

    # 対話的にフィードバックを収集
    if not analysis_id:
        analysis_id = Prompt.ask("分析ID（最新の場合はEnter）", default="latest")

    if not rating:
        console.print("\n分析結果の評価（1-5）:")
        console.print("  1 - 全く役に立たなかった")
        console.print("  2 - あまり役に立たなかった")
        console.print("  3 - まあまあ役に立った")
        console.print("  4 - 役に立った")
        console.print("  5 - 非常に役に立った")
        rating = IntPrompt.ask("\n評価", choices=["1", "2", "3", "4", "5"], default=3)

    # コメント収集
    has_comment = Confirm.ask("\nコメントを追加しますか？", default=False)
    comment = ""
    if has_comment:
        comment = Prompt.ask("コメント")

    # 正確性の評価
    was_accurate = Confirm.ask("\n分析結果は正確でしたか？", default=True)

    # フィードバックをJSONファイルに保存
    try:
        import json
        from datetime import datetime

        # フィードバックディレクトリを作成
        feedback_dir = config.get_path("cache_dir") / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        # フィードバックデータを作成
        feedback_data = {
            "pattern_id": analysis_id,
            "rating": rating,
            "success": was_accurate,
            "comments": comment if comment else None,
            "timestamp": datetime.now().isoformat(),
        }

        # ファイルに保存
        feedback_file = feedback_dir / f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with feedback_file.open("w", encoding="utf-8") as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=2)

        console.print("\n[green]✓ フィードバックを記録しました。ありがとうございます！[/green]")
        console.print("[dim]このフィードバックは将来の分析精度向上に活用されます。[/dim]")
        console.print(f"[dim]保存先: {feedback_file}[/dim]")

    except Exception as e:
        console.print(f"[red]フィードバックの記録に失敗しました: {e}[/red]")
