"""
AIレスポンスキャッシュのテスト

キャッシュ機能、TTL管理、サイズ制限などをテストします。
"""

import time

import pytest

from src.ci_helper.ai.cache import ResponseCache
from src.ci_helper.ai.cache_manager import CacheManager
from src.ci_helper.ai.models import AnalysisResult, AnalysisStatus, TokenUsage


class TestResponseCache:
    """レスポンスキャッシュのテスト"""

    @pytest.fixture
    def cache_dir(self, temp_dir):
        """キャッシュディレクトリ"""
        return temp_dir / "cache"

    @pytest.fixture
    def response_cache(self, cache_dir):
        """レスポンスキャッシュ"""
        return ResponseCache(
            cache_dir=cache_dir,
            max_size_mb=10,
            ttl_hours=24,
            cleanup_interval_hours=6,
        )

    @pytest.fixture
    def sample_analysis_result(self):
        """サンプル分析結果"""
        return AnalysisResult(
            summary="テスト分析結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002),
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
        )

    def test_cache_initialization(self, response_cache, cache_dir):
        """キャッシュ初期化のテスト"""
        assert response_cache.cache_dir == cache_dir
        assert response_cache.max_size_mb == 10
        assert response_cache.ttl_hours == 24
        assert cache_dir.exists()

    def test_generate_cache_key(self, response_cache):
        """キャッシュキー生成のテスト"""
        key1 = response_cache.get_cache_key("prompt1", "context1", "gpt-4o")
        key2 = response_cache.get_cache_key("prompt1", "context1", "gpt-4o")
        key3 = response_cache.get_cache_key("prompt2", "context1", "gpt-4o")

        # 同じ内容なら同じキー
        assert key1 == key2

        # 異なる内容なら異なるキー
        assert key1 != key3

        # キーの形式確認（ハッシュ値）
        assert len(key1) == 64  # SHA256ハッシュ

    @pytest.mark.asyncio
    async def test_set_and_get_cache(self, response_cache, sample_analysis_result):
        """キャッシュ設定と取得のテスト"""
        cache_key = "test_key_123"

        # キャッシュに保存
        await response_cache.set(cache_key, sample_analysis_result)

        # キャッシュから取得
        cached_result = await response_cache.get(cache_key)

        assert cached_result is not None
        assert cached_result.summary == sample_analysis_result.summary
        assert cached_result.confidence_score == sample_analysis_result.confidence_score
        assert cached_result.provider == sample_analysis_result.provider

    @pytest.mark.asyncio
    async def test_get_nonexistent_cache(self, response_cache):
        """存在しないキャッシュの取得テスト"""
        result = await response_cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, response_cache, sample_analysis_result):
        """キャッシュ有効期限のテスト"""
        # TTLを1秒に設定
        response_cache.ttl_hours = 1 / 3600  # 1秒

        cache_key = "expiring_key"
        await response_cache.set(cache_key, sample_analysis_result)

        # すぐに取得（有効）
        result = await response_cache.get(cache_key)
        assert result is not None

        # 少し待ってから取得（期限切れ）
        time.sleep(1.1)
        result = await response_cache.get(cache_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, response_cache, sample_analysis_result):
        """キャッシュ無効化のテスト"""
        cache_key = "test_key_invalidate"

        # キャッシュに保存
        await response_cache.set(cache_key, sample_analysis_result)
        assert await response_cache.get(cache_key) is not None

        # 無効化
        await response_cache.invalidate(cache_key)
        assert await response_cache.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_clear_all_cache(self, response_cache, sample_analysis_result):
        """全キャッシュクリアのテスト"""
        # 複数のキャッシュを保存
        await response_cache.set("key1", sample_analysis_result)
        await response_cache.set("key2", sample_analysis_result)

        # 全てクリア
        await response_cache.clear_all()

        # 全て削除されていることを確認
        assert await response_cache.get("key1") is None
        assert await response_cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, response_cache, sample_analysis_result):
        """キャッシュ統計のテスト"""
        # 初期状態
        stats = response_cache.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["total_size_mb"] == 0.0

        # キャッシュを追加（同期的に）
        cache_key = "stats_test_key"
        cache_file = response_cache.cache_dir / f"{cache_key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # 正しいsetメソッドを使用してキャッシュに保存
        await response_cache.set(cache_key, sample_analysis_result, "test prompt", "test context")

        # 統計を取得
        stats = response_cache.get_cache_stats()
        assert stats["total_entries"] == 1
        assert stats["total_size_mb"] > 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self, response_cache, sample_analysis_result):
        """期限切れエントリのクリーンアップテスト"""
        # 期限切れのキャッシュを作成
        cache_key = "expired_key"

        # 正しいsetメソッドを使用してキャッシュに保存
        await response_cache.set(cache_key, sample_analysis_result, "test prompt", "test context")

        # メタデータを手動で期限切れに設定
        import time

        expired_time = time.time() - (25 * 3600)  # 25時間前
        response_cache.metadata["entries"][cache_key]["created"] = expired_time
        response_cache.metadata["entries"][cache_key]["last_accessed"] = expired_time
        await response_cache._save_metadata()

        # クリーンアップ実行
        cleaned_count = await response_cache.cleanup_expired()

        assert cleaned_count == 1
        cache_file = response_cache.cache_dir / f"{cache_key}.json"
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, cache_dir):
        """キャッシュサイズ制限のテスト"""
        # 非常に小さなサイズ制限を設定
        small_cache = ResponseCache(cache_dir=cache_dir, max_size_mb=0.001)  # 1KB

        # 大きなデータを作成
        large_result = AnalysisResult(
            summary="非常に長い分析結果" * 1000,  # 大きなデータ
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.5,
            tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002),
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
        )

        # サイズ制限を超える場合の動作確認（古いエントリが削除される）
        await small_cache.set("large_key", large_result)

        # 手動でサイズ制限チェックを実行
        await small_cache._ensure_cache_size()

        # キャッシュサイズが制限内に収まっていることを確認
        stats = small_cache.get_cache_stats()
        assert stats["total_size_mb"] <= small_cache.max_size_mb


class TestCacheManager:
    """キャッシュマネージャーのテスト"""

    @pytest.fixture
    def cache_manager(self, temp_dir):
        """キャッシュマネージャー"""
        return CacheManager(cache_dir=temp_dir / "cache")

    @pytest.fixture
    def sample_analysis_result(self):
        """サンプル分析結果"""
        return AnalysisResult(
            summary="マネージャーテスト結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.9,
            analysis_time=2.0,
            tokens_used=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300, estimated_cost=0.005),
            status=AnalysisStatus.COMPLETED,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
        )

    def test_cache_manager_initialization(self, cache_manager):
        """キャッシュマネージャー初期化のテスト"""
        assert cache_manager.cache is not None
        assert cache_manager.cache_dir.exists()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_manager, sample_analysis_result):
        """キャッシュミス時の動作テスト"""

        async def mock_compute_function():
            return sample_analysis_result

        result = await cache_manager.get_or_set(
            prompt="テストプロンプト",
            context="テストコンテキスト",
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
            compute_func=mock_compute_function,
        )

        assert result == sample_analysis_result

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_manager, sample_analysis_result):
        """キャッシュヒット時の動作テスト"""
        # 最初にキャッシュに保存
        cache_key = cache_manager.cache.get_cache_key(
            "テストプロンプト", "テストコンテキスト", "claude-3-5-sonnet-20241022", "anthropic"
        )
        await cache_manager.cache.set(cache_key, sample_analysis_result)

        # compute_funcは呼ばれないはず
        async def mock_compute_function():
            pytest.fail("compute_func should not be called on cache hit")

        result = await cache_manager.get_or_set(
            prompt="テストプロンプト",
            context="テストコンテキスト",
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
            compute_func=mock_compute_function,
        )

        assert result.summary == sample_analysis_result.summary

    @pytest.mark.asyncio
    async def test_invalidate_by_provider(self, cache_manager, sample_analysis_result):
        """プロバイダー別キャッシュ無効化のテスト"""
        # 異なるプロバイダーのキャッシュを作成
        openai_result = AnalysisResult(
            summary="OpenAI結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.8,
            analysis_time=1.0,
            tokens_used=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.002),
            status=AnalysisStatus.COMPLETED,
            provider="openai",
            model="gpt-4o",
        )

        anthropic_result = AnalysisResult(
            summary="Anthropic結果",
            root_causes=[],
            fix_suggestions=[],
            related_errors=[],
            confidence_score=0.9,
            analysis_time=2.0,
            tokens_used=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300, estimated_cost=0.005),
            status=AnalysisStatus.COMPLETED,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
        )

        # キャッシュに保存
        await cache_manager.cache.set("openai_key", openai_result)
        await cache_manager.cache.set("anthropic_key", anthropic_result)

        # OpenAIのキャッシュのみ無効化
        await cache_manager.invalidate_by_provider("openai")

        # OpenAIのキャッシュは削除され、Anthropicのキャッシュは残る
        assert await cache_manager.cache.get("openai_key") is None
        assert await cache_manager.cache.get("anthropic_key") is not None

    @pytest.mark.asyncio
    async def test_get_cache_summary(self, cache_manager):
        """キャッシュサマリー取得のテスト"""
        summary = await cache_manager.get_cache_stats()

        assert "total_entries" in summary
        assert "total_size_mb" in summary
        assert "provider_breakdown" in summary
        assert isinstance(summary["provider_breakdown"], dict)

    @pytest.mark.asyncio
    async def test_cleanup_cache(self, cache_manager):
        """キャッシュクリーンアップのテスト"""
        # テスト用のキャッシュファイルを作成
        test_file = cache_manager.cache_dir / "test_cleanup.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"test": "data"}', encoding="utf-8")

        # クリーンアップ実行
        result = await cache_manager.cleanup_cache()

        assert "removed_entries" in result
        assert "success" in result
        assert isinstance(result["removed_entries"], int)
        assert isinstance(result["success"], bool)
