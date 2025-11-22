"""
キャッシュ管理

AIレスポンスキャッシュの高レベル管理機能を提供します。
キャッシュの有効化/無効化、統計表示、メンテナンス機能などを含みます。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

# ResponseCacheは遅延インポートしてテストのパッチが正しく適用されるようにする
from .models import AnalysisResult

if TYPE_CHECKING:
    from .cache import ResponseCache


class CacheManager:
    """キャッシュ管理クラス"""

    def __init__(
        self,
        cache_dir: Path,
        enabled: bool = True,
        max_size_mb: int = 100,
        ttl_hours: int = 24,
    ):
        """キャッシュマネージャーを初期化

        Args:
            cache_dir: キャッシュディレクトリ
            enabled: キャッシュ有効化フラグ
            max_size_mb: 最大キャッシュサイズ（MB）
            ttl_hours: キャッシュ有効期限（時間）
        """
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.max_size_mb = max_size_mb
        self.ttl_hours = ttl_hours

        self._cache = None
        if self.enabled:
            # 遅延インポート：テストのパッチが正しく適用されるようにする
            from .cache import ResponseCache

            self._cache = ResponseCache(
                cache_dir=cache_dir,
                max_size_mb=max_size_mb,
                ttl_hours=ttl_hours,
            )

    @property
    def cache(self) -> ResponseCache | None:
        """キャッシュインスタンスを取得"""
        return self._cache

    async def get_cached_result(
        self,
        prompt: str,
        context: str,
        model: str,
        provider: str = "",
    ) -> AnalysisResult | None:
        """キャッシュされた分析結果を取得

        Args:
            prompt: プロンプト
            context: コンテキスト
            model: モデル名
            provider: プロバイダー名

        Returns:
            キャッシュされた分析結果（存在しない場合はNone）
        """
        if not self.enabled or not self._cache:
            return None

        try:
            cache_key = self._cache.get_cache_key(prompt, context, model, provider)
            return await self._cache.get(cache_key)
        except Exception:
            # キャッシュエラーは無視して None を返す
            return None

    async def cache_result(
        self,
        prompt: str,
        context: str,
        model: str,
        provider: str,
        result: AnalysisResult,
    ) -> bool:
        """分析結果をキャッシュに保存

        Args:
            prompt: プロンプト
            context: コンテキスト
            model: モデル名
            provider: プロバイダー名
            result: 分析結果

        Returns:
            保存に成功したかどうか
        """
        if not self.enabled or not self._cache:
            return False

        try:
            cache_key = self._cache.get_cache_key(prompt, context, model, provider)
            await self._cache.set(cache_key, result, prompt, context)
            return True
        except Exception:
            # キャッシュエラーは無視
            return False

    async def get_cache_stats(self) -> dict[str, Any]:
        """キャッシュ統計を取得

        Returns:
            キャッシュ統計情報
        """
        if not self.enabled or not self._cache:
            return {
                "enabled": False,
                "message": "キャッシュが無効になっています",
            }

        try:
            stats = await self._cache.get_stats()
            stats["enabled"] = True
            return stats
        except Exception as e:
            return {
                "enabled": True,
                "error": f"統計の取得に失敗しました: {e}",
            }

    async def _is_valid_cache(self, cache_data: dict[str, Any]) -> bool:
        """キャッシュのクリーンアップを実行

        Returns:
            クリーンアップ結果
        """
        # この関数はまだ実装されていません。
        # キャッシュデータの有効性をチェックするロジックをここに追加します。
        return True

    async def cleanup_cache(self) -> dict[str, Any]:
        """キャッシュのクリーンアップを実行

        Returns:
            クリーンアップ結果
        """
        if not self.enabled or not self._cache:
            return {
                "enabled": False,
                "message": "キャッシュが無効になっています",
            }

        try:
            removed_count = await self._cache.cleanup_expired()
            return {
                "success": True,
                "removed_entries": removed_count,
                "message": f"{removed_count}件の期限切れエントリを削除しました",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"クリーンアップに失敗しました: {e}",
            }

    async def clear_cache(self) -> dict[str, Any]:
        """全キャッシュを削除

        Returns:
            削除結果
        """
        if not self.enabled or not self._cache:
            return {
                "enabled": False,
                "message": "キャッシュが無効になっています",
            }

        try:
            await self._cache.clear()
            return {
                "success": True,
                "message": "全キャッシュを削除しました",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"キャッシュの削除に失敗しました: {e}",
            }

    async def invalidate_cache_by_provider(self, provider: str) -> dict[str, Any]:
        """指定されたプロバイダーのキャッシュを無効化

        Args:
            provider: プロバイダー名

        Returns:
            無効化結果
        """
        if not self.enabled or not self._cache:
            return {
                "enabled": False,
                "message": "キャッシュが無効になっています",
            }

        try:
            # メタデータから該当するエントリを特定
            removed_count = 0
            entries_to_remove = []

            for cache_key, entry in self._cache.metadata["entries"].items():
                if entry.get("provider") == provider:
                    entries_to_remove.append(cache_key)

            # エントリを削除
            for cache_key in entries_to_remove:
                if await self._cache.remove(cache_key):
                    removed_count += 1

            return {
                "success": True,
                "removed_entries": removed_count,
                "message": f"プロバイダー '{provider}' の{removed_count}件のキャッシュを削除しました",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"キャッシュの無効化に失敗しました: {e}",
            }

    def enable_cache(self) -> None:
        """キャッシュを有効化"""
        if not self.enabled:
            self.enabled = True
            # 遅延インポート：テストのパッチが正しく適用されるようにする
            from .cache import ResponseCache

            self._cache = ResponseCache(
                cache_dir=self.cache_dir,
                max_size_mb=self.max_size_mb,
                ttl_hours=self.ttl_hours,
            )

    def disable_cache(self) -> None:
        """キャッシュを無効化"""
        self.enabled = False
        self._cache = None

    def is_cache_enabled(self) -> bool:
        """キャッシュが有効かどうかを確認

        Returns:
            キャッシュが有効かどうか
        """
        return self.enabled and self._cache is not None

    async def get_cache_recommendations(self) -> list[str]:
        """キャッシュ最適化の推奨事項を取得

        Returns:
            推奨事項のリスト
        """
        if not self.enabled or not self._cache:
            return [
                "キャッシュが無効になっています",
                "キャッシュを有効にすることで、同じ分析の再実行時間とコストを削減できます",
            ]

        try:
            stats = await self._cache.get_stats()
            recommendations = []

            # 使用率に基づく推奨
            usage_pct = stats.get("usage_percentage", 0)
            if usage_pct > 90:
                recommendations.append("キャッシュ使用率が90%を超えています。max_size_mbの増加を検討してください")
            elif usage_pct > 70:
                recommendations.append("キャッシュ使用率が70%を超えています。定期的なクリーンアップを推奨します")

            # アクセス頻度に基づく推奨
            avg_access = stats.get("average_access_count", 0)
            if avg_access < 1:
                recommendations.append("キャッシュのヒット率が低いようです。TTLの延長を検討してください")

            # 期限切れエントリに基づく推奨
            expired_count = stats.get("expired_entries", 0)
            if expired_count > 10:
                recommendations.append(
                    f"{expired_count}件の期限切れエントリがあります。クリーンアップを実行してください"
                )

            # 一般的な推奨事項
            if not recommendations:
                recommendations.extend(
                    [
                        "キャッシュは正常に動作しています",
                        "定期的なクリーンアップでパフォーマンスを維持できます",
                    ]
                )

            return recommendations

        except Exception:
            return ["キャッシュ統計の取得に失敗しました"]

    async def get_or_set(
        self,
        prompt: str,
        context: str,
        model: str,
        provider: str,
        compute_func,
    ) -> AnalysisResult:
        """キャッシュから取得するか、計算して保存

        Args:
            prompt: プロンプト
            context: コンテキスト
            model: モデル名
            provider: プロバイダー名
            compute_func: 計算関数

        Returns:
            分析結果
        """
        # キャッシュから取得を試行
        cached_result = await self.get_cached_result(prompt, context, model, provider)
        if cached_result is not None:
            return cached_result

        # キャッシュにない場合は計算
        result = await compute_func()

        # 結果をキャッシュに保存
        await self.cache_result(prompt, context, model, provider, result)

        return result

    async def invalidate_by_provider(self, provider: str) -> None:
        """プロバイダー別キャッシュ無効化（エイリアス）

        Args:
            provider: プロバイダー名
        """
        await self.invalidate_cache_by_provider(provider)
