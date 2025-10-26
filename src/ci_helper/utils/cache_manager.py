"""
キャッシュ管理ユーティリティ

フォーマット結果キャッシュの管理機能を提供します。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .performance_optimizer import PerformanceOptimizer


class CacheManager:
    """キャッシュ管理クラス

    フォーマット結果キャッシュの管理、統計表示、クリーンアップ機能を提供します。
    """

    def __init__(self, console: Console | None = None):
        """キャッシュマネージャーを初期化

        Args:
            console: Rich Console インスタンス
        """
        self.console = console or Console()
        self.optimizer = PerformanceOptimizer()

    def show_cache_statistics(self) -> None:
        """キャッシュ統計情報を表示"""
        stats = self.optimizer.cache.get_cache_statistics()

        # 統計情報テーブルを作成
        table = Table(title="📊 フォーマット結果キャッシュ統計")
        table.add_column("項目", style="cyan")
        table.add_column("値", style="green")

        table.add_row("総エントリ数", f"{stats['total_entries']:,}件")
        table.add_row("総サイズ", f"{stats['total_size_mb']:.2f} MB")
        table.add_row("ヒット率", f"{stats['hit_rate']:.1f}%")
        table.add_row("キャッシュディレクトリ", str(stats["cache_dir"]))

        self.console.print(table)

        # 最適化統計も表示
        opt_stats = self.optimizer.get_optimization_stats()

        opt_table = Table(title="⚡ パフォーマンス最適化統計")
        opt_table.add_column("項目", style="cyan")
        opt_table.add_column("値", style="green")

        opt_table.add_row("メモリ制限", f"{opt_stats['memory_limit_mb']} MB")
        opt_table.add_row("チャンクサイズ", f"{opt_stats['chunk_size_kb']} KB")

        processing_status = opt_stats["processing_status"]
        opt_table.add_row("処理中ファイル数", f"{processing_status['active_processes']}件")

        self.console.print(opt_table)

    def clear_cache(self, confirm: bool = True) -> int:
        """キャッシュをクリア

        Args:
            confirm: 確認プロンプトを表示するかどうか

        Returns:
            削除されたエントリ数
        """
        if confirm:
            from rich.prompt import Confirm

            stats = self.optimizer.cache.get_cache_statistics()
            self.console.print(
                f"[yellow]現在のキャッシュ: {stats['total_entries']}件 ({stats['total_size_mb']:.2f} MB)[/yellow]"
            )

            if not Confirm.ask("キャッシュをクリアしますか？", console=self.console):
                self.console.print("[dim]キャッシュクリアがキャンセルされました[/dim]")
                return 0

        cleared_count = self.optimizer.cache.clear_cache()

        if cleared_count > 0:
            self.console.print(f"[green]✅ キャッシュをクリアしました: {cleared_count}件[/green]")
        else:
            self.console.print("[dim]クリアするキャッシュエントリがありませんでした[/dim]")

        return cleared_count

    def cleanup_expired_cache(self, max_age_hours: int = 24) -> int:
        """期限切れキャッシュをクリーンアップ

        Args:
            max_age_hours: 最大保持時間（時間）

        Returns:
            削除されたエントリ数
        """
        # 現在の実装では期限切れチェックは FormatResultCache 内で自動実行
        # ここでは手動でクリーンアップを実行

        stats_before = self.optimizer.cache.get_cache_statistics()

        # 強制的にクリーンアップを実行
        self.optimizer.cache._cleanup_cache_if_needed()

        stats_after = self.optimizer.cache.get_cache_statistics()

        cleaned_count = stats_before["total_entries"] - stats_after["total_entries"]

        if cleaned_count > 0:
            self.console.print(f"[green]期限切れキャッシュをクリーンアップしました: {cleaned_count}件[/green]")
        else:
            self.console.print("[dim]クリーンアップするキャッシュエントリがありませんでした[/dim]")

        return cleaned_count

    def show_processing_status(self) -> None:
        """現在の処理状況を表示"""
        status = self.optimizer.duplicate_preventer.get_processing_status()

        if status["active_processes"] == 0:
            self.console.print("[dim]現在処理中のファイルはありません[/dim]")
            return

        # 処理中ファイル一覧テーブル
        table = Table(title="🔄 処理中ファイル一覧")
        table.add_column("ファイル", style="cyan")
        table.add_column("開始時刻", style="yellow")
        table.add_column("経過時間", style="green")

        for process in status["processes"]:
            table.add_row(process["file"], process["start_time"], f"{process['duration_minutes']:.1f}分")

        self.console.print(table)

    def cleanup_expired_locks(self) -> int:
        """期限切れの処理ロックをクリーンアップ

        Returns:
            クリーンアップされたロック数
        """
        cleaned_count = self.optimizer.duplicate_preventer.cleanup_expired_locks()

        if cleaned_count > 0:
            self.console.print(f"[green]期限切れの処理ロックをクリーンアップしました: {cleaned_count}件[/green]")
        else:
            self.console.print("[dim]クリーンアップする処理ロックがありませんでした[/dim]")

        return cleaned_count

    def optimize_cache_size(self, target_size_mb: int = 50) -> dict[str, Any]:
        """キャッシュサイズを最適化

        Args:
            target_size_mb: 目標サイズ（MB）

        Returns:
            最適化結果
        """
        stats_before = self.optimizer.cache.get_cache_statistics()

        if stats_before["total_size_mb"] <= target_size_mb:
            self.console.print(
                f"[dim]キャッシュサイズは既に目標値以下です ({stats_before['total_size_mb']:.2f} MB)[/dim]"
            )
            return {
                "optimized": False,
                "size_before": stats_before["total_size_mb"],
                "size_after": stats_before["total_size_mb"],
                "entries_removed": 0,
            }

        # 新しいキャッシュインスタンスを作成（サイズ制限付き）
        from ..utils.performance_optimizer import FormatResultCache

        # 現在のキャッシュディレクトリを取得
        cache_dir = Path(stats_before["cache_dir"])

        # 新しいキャッシュインスタンス（サイズ制限付き）
        new_cache = FormatResultCache(cache_dir, target_size_mb)

        # クリーンアップを強制実行
        new_cache._cleanup_cache_if_needed()

        stats_after = new_cache.get_cache_statistics()

        result = {
            "optimized": True,
            "size_before": stats_before["total_size_mb"],
            "size_after": stats_after["total_size_mb"],
            "entries_removed": stats_before["total_entries"] - stats_after["total_entries"],
        }

        self.console.print("[green]キャッシュサイズを最適化しました[/green]")
        self.console.print(f"[dim]サイズ: {result['size_before']:.2f} MB → {result['size_after']:.2f} MB[/dim]")
        self.console.print(f"[dim]削除エントリ: {result['entries_removed']}件[/dim]")

        return result

    def get_cache_recommendations(self) -> list[str]:
        """キャッシュ最適化の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        stats = self.optimizer.cache.get_cache_statistics()
        recommendations = []

        # サイズベースの推奨事項
        if stats["total_size_mb"] > 100:
            recommendations.append("キャッシュサイズが大きくなっています。定期的なクリーンアップを推奨します。")

        # ヒット率ベースの推奨事項
        if stats["hit_rate"] < 30:
            recommendations.append(
                "キャッシュヒット率が低いです。同じファイルを繰り返し処理することでヒット率が向上します。"
            )
        elif stats["hit_rate"] > 80:
            recommendations.append("キャッシュが効果的に機能しています。")

        # エントリ数ベースの推奨事項
        if stats["total_entries"] > 1000:
            recommendations.append(
                "キャッシュエントリ数が多くなっています。古いエントリのクリーンアップを検討してください。"
            )

        # 処理状況ベースの推奨事項
        processing_status = self.optimizer.duplicate_preventer.get_processing_status()
        if processing_status["active_processes"] > 5:
            recommendations.append("多数のファイルが同時処理中です。システムリソースの使用量を監視してください。")

        if not recommendations:
            recommendations.append("キャッシュは適切に動作しています。")

        return recommendations

    def show_recommendations(self) -> None:
        """キャッシュ最適化の推奨事項を表示"""
        recommendations = self.get_cache_recommendations()

        self.console.print("\n[bold cyan]💡 キャッシュ最適化の推奨事項[/bold cyan]")
        for i, recommendation in enumerate(recommendations, 1):
            self.console.print(f"[dim]{i}.[/dim] {recommendation}")


def get_cache_manager(console: Console | None = None) -> CacheManager:
    """キャッシュマネージャーのインスタンスを取得

    Args:
        console: Rich Console インスタンス

    Returns:
        キャッシュマネージャーインスタンス
    """
    return CacheManager(console)
