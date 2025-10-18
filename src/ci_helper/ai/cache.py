"""
AIレスポンスキャッシュ

AI分析結果をキャッシュして、同じ内容の再分析時にコストと時間を節約します。
ハッシュベースのキー生成、TTL管理、サイズ制限などの機能を提供します。
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import aiofiles

from .exceptions import CacheError
from .models import AnalysisResult, AnalysisStatus


class ResponseCache:
    """AIレスポンスキャッシュクラス"""

    def __init__(
        self,
        cache_dir: Path,
        max_size_mb: int = 100,
        ttl_hours: int = 24,
        cleanup_interval_hours: int = 6,
    ):
        """レスポンスキャッシュを初期化

        Args:
            cache_dir: キャッシュディレクトリ
            max_size_mb: 最大キャッシュサイズ（MB）
            ttl_hours: キャッシュ有効期限（時間）
            cleanup_interval_hours: クリーンアップ実行間隔（時間）
        """
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self.ttl_hours = ttl_hours
        self.cleanup_interval_hours = cleanup_interval_hours

        # キャッシュディレクトリを作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # メタデータファイル
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()

        # 最後のクリーンアップ時刻
        self.last_cleanup = time.time()

    def _load_metadata(self) -> dict[str, any]:
        """キャッシュメタデータを読み込み"""
        if not self.metadata_file.exists():
            return {
                "entries": {},
                "total_size": 0,
                "created": time.time(),
                "last_cleanup": time.time(),
            }

        try:
            with open(self.metadata_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # メタデータファイルが破損している場合は新規作成
            return {
                "entries": {},
                "total_size": 0,
                "created": time.time(),
                "last_cleanup": time.time(),
            }

    async def _save_metadata(self) -> None:
        """キャッシュメタデータを保存"""
        try:
            async with aiofiles.open(self.metadata_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.metadata, indent=2, ensure_ascii=False))
        except Exception as e:
            raise CacheError(f"メタデータの保存に失敗しました: {e}")

    def get_cache_key(self, prompt: str, context: str, model: str, provider: str = "") -> str:
        """キャッシュキーを生成

        Args:
            prompt: プロンプト
            context: コンテキスト
            model: モデル名
            provider: プロバイダー名

        Returns:
            ハッシュベースのキャッシュキー
        """
        # キャッシュキーの要素を結合
        key_data = f"{provider}:{model}:{prompt}:{context}"

        # SHA256ハッシュを生成
        hash_obj = hashlib.sha256(key_data.encode("utf-8"))
        return hash_obj.hexdigest()

    async def get(self, cache_key: str) -> AnalysisResult | None:
        """キャッシュから結果を取得

        Args:
            cache_key: キャッシュキー

        Returns:
            キャッシュされた分析結果（存在しない場合はNone）
        """
        # 定期クリーンアップをチェック
        await self._check_cleanup()

        # メタデータから情報を取得
        if cache_key not in self.metadata["entries"]:
            return None

        entry = self.metadata["entries"][cache_key]

        # TTLチェック
        if self._is_expired(entry):
            await self._remove_entry(cache_key)
            return None

        # キャッシュファイルを読み込み
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            # ファイルが存在しない場合はメタデータからも削除
            await self._remove_entry(cache_key)
            return None

        try:
            async with aiofiles.open(cache_file, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

                # AnalysisResultオブジェクトを復元
                analysis_result = self._deserialize_analysis_result(data)
                analysis_result.cache_hit = True

                # アクセス時刻を更新
                entry["last_accessed"] = time.time()
                entry["access_count"] = entry.get("access_count", 0) + 1
                await self._save_metadata()

                return analysis_result

        except Exception as e:
            # ファイル読み込みエラーの場合はエントリを削除
            await self._remove_entry(cache_key)
            raise CacheError(f"キャッシュファイルの読み込みに失敗しました: {e}")

    async def set(self, cache_key: str, result: AnalysisResult, prompt: str = "", context: str = "") -> None:
        """結果をキャッシュに保存

        Args:
            cache_key: キャッシュキー
            result: 分析結果
            prompt: プロンプト（メタデータ用）
            context: コンテキスト（メタデータ用）
        """
        # キャッシュサイズをチェック
        await self._ensure_cache_size()

        # 分析結果をシリアライズ
        data = self._serialize_analysis_result(result)

        # キャッシュファイルに保存
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))

            # ファイルサイズを取得
            file_size = cache_file.stat().st_size

            # メタデータを更新
            current_time = time.time()
            self.metadata["entries"][cache_key] = {
                "created": current_time,
                "last_accessed": current_time,
                "access_count": 0,
                "size": file_size,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "context_hash": hashlib.sha256(context.encode("utf-8")).hexdigest()[:16],
                "provider": result.provider,
                "model": result.model,
            }

            self.metadata["total_size"] += file_size
            await self._save_metadata()

        except Exception as e:
            # 保存に失敗した場合はファイルを削除
            if cache_file.exists():
                cache_file.unlink()
            raise CacheError(f"キャッシュの保存に失敗しました: {e}")

    async def remove(self, cache_key: str) -> bool:
        """キャッシュエントリを削除

        Args:
            cache_key: キャッシュキー

        Returns:
            削除に成功したかどうか
        """
        return await self._remove_entry(cache_key)

    async def clear(self) -> None:
        """全キャッシュを削除"""
        try:
            # 全キャッシュファイルを削除
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "cache_metadata.json":
                    cache_file.unlink()

            # メタデータをリセット
            self.metadata = {
                "entries": {},
                "total_size": 0,
                "created": time.time(),
                "last_cleanup": time.time(),
            }
            await self._save_metadata()

        except Exception as e:
            raise CacheError(f"キャッシュのクリアに失敗しました: {e}")

    async def get_stats(self) -> dict[str, any]:
        """キャッシュ統計を取得

        Returns:
            キャッシュ統計情報
        """
        await self._check_cleanup()

        total_entries = len(self.metadata["entries"])
        total_size_mb = self.metadata["total_size"] / (1024 * 1024)

        # アクセス統計
        access_counts = [entry.get("access_count", 0) for entry in self.metadata["entries"].values()]
        avg_access = sum(access_counts) / len(access_counts) if access_counts else 0

        # プロバイダー別統計
        provider_stats = {}
        for entry in self.metadata["entries"].values():
            provider = entry.get("provider", "unknown")
            provider_stats[provider] = provider_stats.get(provider, 0) + 1

        # 古いエントリの数
        current_time = time.time()
        expired_count = sum(1 for entry in self.metadata["entries"].values() if self._is_expired(entry, current_time))

        return {
            "total_entries": total_entries,
            "total_size_mb": round(total_size_mb, 2),
            "max_size_mb": self.max_size_mb,
            "usage_percentage": round((total_size_mb / self.max_size_mb) * 100, 1),
            "average_access_count": round(avg_access, 1),
            "provider_breakdown": provider_stats,
            "expired_entries": expired_count,
            "ttl_hours": self.ttl_hours,
            "created": datetime.fromtimestamp(self.metadata["created"]).isoformat(),
            "last_cleanup": datetime.fromtimestamp(self.metadata["last_cleanup"]).isoformat(),
        }

    async def cleanup_expired(self) -> int:
        """期限切れエントリをクリーンアップ

        Returns:
            削除されたエントリ数
        """
        current_time = time.time()
        expired_keys = []

        # 期限切れエントリを特定
        for cache_key, entry in self.metadata["entries"].items():
            if self._is_expired(entry, current_time):
                expired_keys.append(cache_key)

        # 期限切れエントリを削除
        removed_count = 0
        for cache_key in expired_keys:
            if await self._remove_entry(cache_key):
                removed_count += 1

        # クリーンアップ時刻を更新
        self.metadata["last_cleanup"] = current_time
        self.last_cleanup = current_time
        await self._save_metadata()

        return removed_count

    async def _check_cleanup(self) -> None:
        """定期クリーンアップをチェック"""
        current_time = time.time()
        if current_time - self.last_cleanup > (self.cleanup_interval_hours * 3600):
            await self.cleanup_expired()

    async def _ensure_cache_size(self) -> None:
        """キャッシュサイズ制限を確保"""
        max_size_bytes = self.max_size_mb * 1024 * 1024

        while self.metadata["total_size"] > max_size_bytes:
            # 最も古いエントリを削除
            oldest_key = self._find_oldest_entry()
            if oldest_key:
                await self._remove_entry(oldest_key)
            else:
                break

    def _find_oldest_entry(self) -> str | None:
        """最も古いエントリを見つける"""
        if not self.metadata["entries"]:
            return None

        oldest_key = None
        oldest_time = float("inf")

        for cache_key, entry in self.metadata["entries"].items():
            last_accessed = entry.get("last_accessed", entry.get("created", 0))
            if last_accessed < oldest_time:
                oldest_time = last_accessed
                oldest_key = cache_key

        return oldest_key

    async def _remove_entry(self, cache_key: str) -> bool:
        """キャッシュエントリを削除"""
        try:
            # メタデータから削除
            if cache_key in self.metadata["entries"]:
                entry = self.metadata["entries"][cache_key]
                self.metadata["total_size"] -= entry.get("size", 0)
                del self.metadata["entries"][cache_key]

            # ファイルを削除
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()

            await self._save_metadata()
            return True

        except Exception:
            return False

    def _is_expired(self, entry: dict[str, any], current_time: float | None = None) -> bool:
        """エントリが期限切れかどうかをチェック"""
        if current_time is None:
            current_time = time.time()

        created_time = entry.get("created", 0)
        ttl_seconds = self.ttl_hours * 3600

        return (current_time - created_time) > ttl_seconds

    def _serialize_analysis_result(self, result: AnalysisResult) -> dict[str, any]:
        """AnalysisResultをシリアライズ"""
        return {
            "summary": result.summary,
            "root_causes": [
                {
                    "category": cause.category,
                    "description": cause.description,
                    "file_path": cause.file_path,
                    "line_number": cause.line_number,
                    "severity": cause.severity.value,
                    "confidence": cause.confidence,
                }
                for cause in result.root_causes
            ],
            "fix_suggestions": [
                {
                    "title": fix.title,
                    "description": fix.description,
                    "code_changes": [
                        {
                            "file_path": change.file_path,
                            "line_start": change.line_start,
                            "line_end": change.line_end,
                            "old_code": change.old_code,
                            "new_code": change.new_code,
                            "description": change.description,
                        }
                        for change in fix.code_changes
                    ],
                    "priority": fix.priority.value,
                    "estimated_effort": fix.estimated_effort,
                    "confidence": fix.confidence,
                    "references": fix.references,
                }
                for fix in result.fix_suggestions
            ],
            "related_errors": result.related_errors,
            "confidence_score": result.confidence_score,
            "analysis_time": result.analysis_time,
            "tokens_used": {
                "input_tokens": result.tokens_used.input_tokens,
                "output_tokens": result.tokens_used.output_tokens,
                "total_tokens": result.tokens_used.total_tokens,
                "estimated_cost": result.tokens_used.estimated_cost,
            }
            if result.tokens_used
            else None,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "provider": result.provider,
            "model": result.model,
        }

    def _deserialize_analysis_result(self, data: dict[str, any]) -> AnalysisResult:
        """シリアライズされたデータからAnalysisResultを復元"""
        from .models import CodeChange, FixSuggestion, Priority, RootCause, Severity, TokenUsage

        # RootCauseを復元
        root_causes = []
        for cause_data in data.get("root_causes", []):
            root_causes.append(
                RootCause(
                    category=cause_data["category"],
                    description=cause_data["description"],
                    file_path=cause_data.get("file_path"),
                    line_number=cause_data.get("line_number"),
                    severity=Severity(cause_data.get("severity", "medium")),
                    confidence=cause_data.get("confidence", 0.0),
                )
            )

        # FixSuggestionを復元
        fix_suggestions = []
        for fix_data in data.get("fix_suggestions", []):
            code_changes = []
            for change_data in fix_data.get("code_changes", []):
                code_changes.append(
                    CodeChange(
                        file_path=change_data["file_path"],
                        line_start=change_data["line_start"],
                        line_end=change_data["line_end"],
                        old_code=change_data["old_code"],
                        new_code=change_data["new_code"],
                        description=change_data["description"],
                    )
                )

            fix_suggestions.append(
                FixSuggestion(
                    title=fix_data["title"],
                    description=fix_data["description"],
                    code_changes=code_changes,
                    priority=Priority(fix_data.get("priority", "medium")),
                    estimated_effort=fix_data.get("estimated_effort", "不明"),
                    confidence=fix_data.get("confidence", 0.0),
                    references=fix_data.get("references", []),
                )
            )

        # TokenUsageを復元
        tokens_used = None
        if data.get("tokens_used"):
            token_data = data["tokens_used"]
            tokens_used = TokenUsage(
                input_tokens=token_data["input_tokens"],
                output_tokens=token_data["output_tokens"],
                total_tokens=token_data["total_tokens"],
                estimated_cost=token_data["estimated_cost"],
            )

        # AnalysisResultを復元
        return AnalysisResult(
            summary=data["summary"],
            root_causes=root_causes,
            fix_suggestions=fix_suggestions,
            related_errors=data.get("related_errors", []),
            confidence_score=data.get("confidence_score", 0.0),
            analysis_time=data.get("analysis_time", 0.0),
            tokens_used=tokens_used,
            status=AnalysisStatus(data.get("status", "completed")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
        )

    async def invalidate(self, cache_key: str) -> None:
        """キャッシュエントリを無効化

        Args:
            cache_key: キャッシュキー
        """
        await self._remove_entry(cache_key)

    async def clear_all(self) -> None:
        """全キャッシュをクリア"""
        await self.clear()

    def get_cache_stats(self) -> dict[str, any]:
        """キャッシュ統計を取得（同期版）

        Returns:
            キャッシュ統計
        """
        total_entries = len(self.metadata["entries"])
        total_size_bytes = self.metadata.get("total_size", 0)
        total_size_mb = total_size_bytes / (1024 * 1024)

        # 期限切れエントリをカウント
        current_time = time.time()
        expired_count = 0
        for entry in self.metadata["entries"].values():
            if self._is_expired(entry, current_time):
                expired_count += 1

        return {
            "total_entries": total_entries,
            "expired_entries": expired_count,
            "valid_entries": total_entries - expired_count,
            "total_size_mb": total_size_mb,
            "max_size_mb": self.max_size_mb,
            "usage_percentage": (total_size_mb / self.max_size_mb) * 100 if self.max_size_mb > 0 else 0,
            "ttl_hours": self.ttl_hours,
        }
