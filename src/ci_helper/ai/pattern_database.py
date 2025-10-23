"""
パターンデータベース管理システム

CI失敗パターンの読み込み、管理、検証機能を提供します。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Pattern

logger = logging.getLogger(__name__)


class PatternDatabase:
    """パターンデータベース管理クラス

    CI失敗パターンの読み込み、管理、検証を行います。
    """

    def __init__(self, data_directory: Path | str = "data/patterns"):
        """パターンデータベースを初期化

        Args:
            data_directory: パターンデータファイルが格納されているディレクトリ
        """
        self.data_directory = Path(data_directory)
        self.patterns: dict[str, Pattern] = {}
        # 新しいパターンファイル構造をサポート
        self.pattern_files = [
            "ci_patterns.json",
            "build_patterns.json",
            "dependency_patterns.json",
            "test_patterns.json",
            "action_patterns.json",
        ]
        # カスタムパターンファイル
        self.custom_pattern_files = ["custom/user_patterns.json", "custom/learned_patterns.json"]
        # 後方互換性のための既存ファイル
        self.legacy_pattern_file = Path("test_data") / "failure_patterns.json"
        self._loaded = False

    async def load_patterns(self) -> None:
        """パターンデータベースを読み込み"""
        if self._loaded:
            return

        logger.info("パターンデータベースを読み込み中: %s", self.data_directory)

        try:
            # 新しいパターンファイル構造を読み込み
            patterns_loaded = await self._load_new_pattern_files()

            # カスタムパターンファイルを読み込み
            custom_patterns_loaded = await self._load_custom_pattern_files()

            # 後方互換性: 既存のlegacyファイルがあれば読み込み
            legacy_patterns_loaded = await self._load_legacy_pattern_file()

            total_loaded = patterns_loaded + custom_patterns_loaded + legacy_patterns_loaded

            if total_loaded == 0:
                logger.warning("パターンファイルが見つかりません。デフォルトパターンを作成します。")
                await self._create_default_patterns()
            else:
                logger.info("パターンを %d 個読み込みました", len(self.patterns))
                self._loaded = True

        except Exception as e:
            logger.error("パターンデータベースの読み込みに失敗: %s", e)
            # フォールバック: デフォルトパターンを作成
            await self._create_default_patterns()

    async def _load_new_pattern_files(self) -> int:
        """新しいパターンファイル構造を読み込み

        Returns:
            読み込んだパターン数
        """
        patterns_loaded = 0

        for pattern_file in self.pattern_files:
            file_path = self.data_directory / pattern_file
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)

                    if "patterns" in data:
                        for pattern_data in data["patterns"]:
                            pattern = self._convert_new_pattern_format(pattern_data)
                            if self._validate_pattern(pattern):
                                self.patterns[pattern.id] = pattern
                                patterns_loaded += 1
                            else:
                                logger.warning("無効なパターンをスキップ: %s", pattern_data.get("id", "unknown"))

                    logger.info(
                        "パターンファイル %s から %d 個のパターンを読み込み",
                        pattern_file,
                        len(data.get("patterns", [])),
                    )

                except Exception as e:
                    logger.error("パターンファイル %s の読み込みに失敗: %s", pattern_file, e)
            else:
                logger.debug("パターンファイルが存在しません: %s", file_path)

        return patterns_loaded

    async def _load_custom_pattern_files(self) -> int:
        """カスタムパターンファイルを読み込み

        Returns:
            読み込んだパターン数
        """
        patterns_loaded = 0

        for pattern_file in self.custom_pattern_files:
            file_path = self.data_directory / pattern_file
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)

                    if "patterns" in data:
                        for pattern_data in data["patterns"]:
                            pattern = self._convert_new_pattern_format(pattern_data)
                            if self._validate_pattern(pattern):
                                self.patterns[pattern.id] = pattern
                                patterns_loaded += 1
                            else:
                                logger.warning(
                                    "無効なカスタムパターンをスキップ: %s", pattern_data.get("id", "unknown")
                                )

                    logger.info(
                        "カスタムパターンファイル %s から %d 個のパターンを読み込み",
                        pattern_file,
                        len(data.get("patterns", [])),
                    )

                except Exception as e:
                    logger.error("カスタムパターンファイル %s の読み込みに失敗: %s", pattern_file, e)
            else:
                logger.debug("カスタムパターンファイルが存在しません: %s", file_path)

        return patterns_loaded

    async def _load_legacy_pattern_file(self) -> int:
        """既存のlegacyパターンファイルを読み込み（後方互換性）

        Returns:
            読み込んだパターン数
        """
        patterns_loaded = 0

        if self.legacy_pattern_file.exists():
            try:
                with open(self.legacy_pattern_file, encoding="utf-8") as f:
                    data = json.load(f)

                # 既存のパターンデータを新しい形式に変換
                for pattern_id, pattern_data in data.items():
                    pattern = self._convert_legacy_pattern(pattern_id, pattern_data)
                    if self._validate_pattern(pattern):
                        self.patterns[pattern_id] = pattern
                        patterns_loaded += 1
                    else:
                        logger.warning("無効なlegacyパターンをスキップ: %s", pattern_id)

                logger.info("legacyパターンファイルから %d 個のパターンを読み込み", patterns_loaded)

            except Exception as e:
                logger.error("legacyパターンファイルの読み込みに失敗: %s", e)

        return patterns_loaded

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """日時文字列をdatetimeオブジェクトに変換（タイムゾーン対応）

        Args:
            datetime_str: ISO形式の日時文字列

        Returns:
            datetimeオブジェクト
        """
        try:
            # "Z"をUTC timezone指定に変換
            if datetime_str.endswith("Z"):
                datetime_str = datetime_str[:-1] + "+00:00"

            # ISO形式でパース
            dt = datetime.fromisoformat(datetime_str)

            # タイムゾーン情報がない場合はUTCとして扱う
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)

            # ローカル時間に変換
            return dt.astimezone().replace(tzinfo=None)

        except Exception:
            # パースに失敗した場合は現在時刻を返す
            return datetime.now()

    def _convert_new_pattern_format(self, pattern_data: dict[str, Any]) -> Pattern:
        """新しいパターンファイル形式からPatternオブジェクトを作成

        Args:
            pattern_data: パターンデータ辞書

        Returns:
            Patternオブジェクト
        """
        return Pattern(
            id=pattern_data["id"],
            name=pattern_data["name"],
            category=pattern_data["category"],
            regex_patterns=pattern_data["regex_patterns"],
            keywords=pattern_data["keywords"],
            context_requirements=pattern_data["context_requirements"],
            confidence_base=pattern_data["confidence_base"],
            success_rate=pattern_data["success_rate"],
            created_at=self._parse_datetime(pattern_data["created_at"]),
            updated_at=self._parse_datetime(pattern_data["updated_at"]),
            user_defined=pattern_data.get("user_defined", False),
            auto_generated=pattern_data.get("auto_generated", False),
            source=pattern_data.get("source", "manual"),
            occurrence_count=pattern_data.get("occurrence_count", 0),
        )

    def _convert_legacy_pattern(self, pattern_id: str, pattern_data: dict[str, Any]) -> Pattern:
        """既存のパターンデータを新しいPattern形式に変換

        Args:
            pattern_id: パターンID
            pattern_data: 既存のパターンデータ

        Returns:
            変換されたPatternオブジェクト
        """
        # 既存データから正規表現パターンを抽出
        regex_patterns = []
        if "error_signature" in pattern_data:
            regex_patterns.append(pattern_data["error_signature"])

        # キーワードを抽出（例から推測）
        keywords = []
        if "examples" in pattern_data:
            for example in pattern_data["examples"]:
                # 例からキーワードを抽出
                keywords.extend(example.split())

        # カテゴリを推測
        category = self._infer_category(pattern_data.get("pattern_name", ""), pattern_data.get("description", ""))

        return Pattern(
            id=pattern_id,
            name=pattern_data.get("pattern_name", pattern_id),
            category=category,
            regex_patterns=regex_patterns,
            keywords=list(set(keywords)),  # 重複を除去
            context_requirements=[],
            confidence_base=0.8,  # デフォルト信頼度
            success_rate=0.9,  # デフォルト成功率
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=False,
        )

    def _infer_category(self, name: str, description: str) -> str:
        """パターン名と説明からカテゴリを推測

        Args:
            name: パターン名
            description: パターン説明

        Returns:
            推測されたカテゴリ
        """
        text = f"{name} {description}".lower()

        if "mock" in text or "モック" in text:
            return "test_mock"
        elif "exception" in text or "例外" in text:
            return "exception"
        elif "async" in text or "非同期" in text:
            return "async"
        elif "attribute" in text or "属性" in text:
            return "attribute"
        elif "fixture" in text or "フィクスチャ" in text:
            return "test_fixture"
        elif "permission" in text or "権限" in text:
            return "permission"
        elif "network" in text or "ネットワーク" in text:
            return "network"
        elif "config" in text or "設定" in text:
            return "configuration"
        elif "build" in text or "ビルド" in text:
            return "build"
        elif "test" in text or "テスト" in text:
            return "test"
        else:
            return "general"

    def _validate_pattern(self, pattern: Pattern) -> bool:
        """パターンの妥当性を検証

        Args:
            pattern: 検証するパターン

        Returns:
            妥当な場合True
        """
        try:
            # 必須フィールドの確認
            if not pattern.id or not pattern.name:
                logger.warning("パターンIDまたは名前が空です: %s", pattern.id)
                return False

            # 正規表現パターンの確認
            if not pattern.regex_patterns and not pattern.keywords:
                logger.warning("正規表現パターンまたはキーワードが必要です: %s", pattern.id)
                return False

            # 正規表現の構文チェック
            import re

            for regex_pattern in pattern.regex_patterns:
                try:
                    re.compile(regex_pattern)
                except re.error as e:
                    logger.warning("無効な正規表現パターン '%s': %s", regex_pattern, e)
                    return False

            # 信頼度の範囲チェック
            if not 0.0 <= pattern.confidence_base <= 1.0:
                logger.warning("信頼度が範囲外です: %s", pattern.confidence_base)
                return False

            if not 0.0 <= pattern.success_rate <= 1.0:
                logger.warning("成功率が範囲外です: %s", pattern.success_rate)
                return False

            return True

        except Exception as e:
            logger.warning("パターン検証中にエラー: %s", e)
            return False

    async def _create_default_patterns(self) -> None:
        """デフォルトのCI失敗パターンを作成"""
        logger.info("デフォルトパターンを作成中...")

        default_patterns = {
            "docker_permission_denied": Pattern(
                id="docker_permission_denied",
                name="Docker権限エラー",
                category="permission",
                regex_patterns=[
                    r"permission denied.*docker",
                    r"Got permission denied while trying to connect to the Docker daemon",
                ],
                keywords=["permission", "denied", "docker", "daemon"],
                context_requirements=["docker", "act"],
                confidence_base=0.9,
                success_rate=0.95,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
            ),
            "setup_uv_permission": Pattern(
                id="setup_uv_permission",
                name="setup-uv権限エラー",
                category="permission",
                regex_patterns=[
                    r"setup-uv.*permission denied",
                    r"Error: Failed to install uv.*permission",
                ],
                keywords=["setup-uv", "permission", "denied", "install", "uv"],
                context_requirements=["github", "actions"],
                confidence_base=0.85,
                success_rate=0.9,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
            ),
            "dependency_not_found": Pattern(
                id="dependency_not_found",
                name="依存関係不足エラー",
                category="dependency",
                regex_patterns=[
                    r"ModuleNotFoundError: No module named",
                    r"ImportError: cannot import name",
                    r"Package .* not found",
                ],
                keywords=["module", "not", "found", "import", "error", "package"],
                context_requirements=[],
                confidence_base=0.8,
                success_rate=0.85,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
            ),
            "network_timeout": Pattern(
                id="network_timeout",
                name="ネットワークタイムアウト",
                category="network",
                regex_patterns=[
                    r"TimeoutError.*connection",
                    r"Read timed out",
                    r"Connection timeout",
                ],
                keywords=["timeout", "connection", "network", "read"],
                context_requirements=[],
                confidence_base=0.75,
                success_rate=0.7,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
            ),
            "config_file_missing": Pattern(
                id="config_file_missing",
                name="設定ファイル不足",
                category="configuration",
                regex_patterns=[
                    r"FileNotFoundError.*config",
                    r"No such file or directory.*\.toml",
                    r"Configuration file .* not found",
                ],
                keywords=["file", "not", "found", "config", "configuration", "toml"],
                context_requirements=[],
                confidence_base=0.8,
                success_rate=0.9,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_defined=False,
            ),
        }

        self.patterns.update(default_patterns)
        logger.info("デフォルトパターンを %d 個作成しました", len(default_patterns))
        self._loaded = True

        # パターンファイルに保存
        await self.save_patterns()

    async def save_patterns(self) -> None:
        """パターンデータベースをファイルに保存"""
        try:
            # ディレクトリが存在しない場合は作成
            self.data_directory.mkdir(parents=True, exist_ok=True)
            (self.data_directory / "custom").mkdir(parents=True, exist_ok=True)

            # カテゴリ別にパターンを分類
            patterns_by_category = {}
            user_patterns = []
            learned_patterns = []

            for pattern in self.patterns.values():
                if pattern.user_defined and pattern.source == "user":
                    user_patterns.append(pattern)
                elif pattern.auto_generated or pattern.source == "learning":
                    learned_patterns.append(pattern)
                else:
                    # 組み込みパターンはカテゴリ別に分類（読み取り専用として扱う）
                    if pattern.category not in patterns_by_category:
                        patterns_by_category[pattern.category] = []
                    patterns_by_category[pattern.category].append(pattern)

            # ユーザー定義パターンを保存
            if user_patterns:
                await self._save_custom_patterns(user_patterns, "custom/user_patterns.json")

            # 学習済みパターンを保存
            if learned_patterns:
                await self._save_custom_patterns(learned_patterns, "custom/learned_patterns.json")

            logger.info(
                "パターンデータベースを保存しました (ユーザー: %d, 学習済み: %d)",
                len(user_patterns),
                len(learned_patterns),
            )

        except Exception as e:
            logger.error("パターンデータベースの保存に失敗: %s", e)
            raise

    async def _save_custom_patterns(self, patterns: list[Pattern], filename: str) -> None:
        """カスタムパターンをファイルに保存

        Args:
            patterns: 保存するパターンのリスト
            filename: 保存先ファイル名
        """
        file_path = self.data_directory / filename

        pattern_data = {
            "patterns": [
                {
                    "id": pattern.id,
                    "name": pattern.name,
                    "category": pattern.category,
                    "regex_patterns": pattern.regex_patterns,
                    "keywords": pattern.keywords,
                    "context_requirements": pattern.context_requirements,
                    "confidence_base": pattern.confidence_base,
                    "success_rate": pattern.success_rate,
                    "created_at": pattern.created_at.isoformat(),
                    "updated_at": pattern.updated_at.isoformat(),
                    "user_defined": pattern.user_defined,
                    "auto_generated": pattern.auto_generated,
                    "source": pattern.source,
                    "occurrence_count": pattern.occurrence_count,
                }
                for pattern in patterns
            ],
            "metadata": {
                "description": "ユーザー定義パターン" if "user" in filename else "学習済みパターン",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "pattern_count": len(patterns),
            },
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pattern_data, f, ensure_ascii=False, indent=4)

        logger.info("カスタムパターンを保存しました: %s (%d個)", filename, len(patterns))

    def get_pattern(self, pattern_id: str) -> Pattern | None:
        """指定されたIDのパターンを取得

        Args:
            pattern_id: パターンID

        Returns:
            パターンオブジェクト、見つからない場合はNone
        """
        return self.patterns.get(pattern_id)

    def get_patterns_by_category(self, category: str) -> list[Pattern]:
        """指定されたカテゴリのパターンを取得

        Args:
            category: カテゴリ名

        Returns:
            パターンのリスト
        """
        return [pattern for pattern in self.patterns.values() if pattern.category == category]

    def get_all_patterns(self) -> list[Pattern]:
        """すべてのパターンを取得

        Returns:
            パターンのリスト
        """
        return list(self.patterns.values())

    def add_pattern(self, pattern: Pattern) -> bool:
        """新しいパターンを追加

        Args:
            pattern: 追加するパターン

        Returns:
            成功した場合True
        """
        if not self._validate_pattern(pattern):
            return False

        self.patterns[pattern.id] = pattern
        logger.info("パターンを追加しました: %s", pattern.id)
        return True

    def update_pattern(self, pattern: Pattern) -> bool:
        """既存のパターンを更新

        Args:
            pattern: 更新するパターン

        Returns:
            成功した場合True
        """
        if pattern.id not in self.patterns:
            logger.warning("更新対象のパターンが見つかりません: %s", pattern.id)
            return False

        if not self._validate_pattern(pattern):
            return False

        pattern.updated_at = datetime.now()
        self.patterns[pattern.id] = pattern
        logger.info("パターンを更新しました: %s", pattern.id)
        return True

    def remove_pattern(self, pattern_id: str) -> bool:
        """パターンを削除

        Args:
            pattern_id: 削除するパターンID

        Returns:
            成功した場合True
        """
        if pattern_id not in self.patterns:
            logger.warning("削除対象のパターンが見つかりません: %s", pattern_id)
            return False

        del self.patterns[pattern_id]
        logger.info("パターンを削除しました: %s", pattern_id)
        return True

    def search_patterns(self, query: str) -> list[Pattern]:
        """パターンを検索

        Args:
            query: 検索クエリ

        Returns:
            マッチしたパターンのリスト
        """
        query_lower = query.lower()
        results = []

        for pattern in self.patterns.values():
            # 名前、カテゴリ、キーワードで検索
            if (
                query_lower in pattern.name.lower()
                or query_lower in pattern.category.lower()
                or any(query_lower in keyword.lower() for keyword in pattern.keywords)
            ):
                results.append(pattern)

        return results

    def get_statistics(self) -> dict[str, Any]:
        """パターンデータベースの統計情報を取得

        Returns:
            統計情報の辞書
        """
        if not self.patterns:
            return {"total_patterns": 0, "categories": {}, "user_defined": 0}

        categories = {}
        user_defined_count = 0

        for pattern in self.patterns.values():
            # カテゴリ別集計
            if pattern.category not in categories:
                categories[pattern.category] = 0
            categories[pattern.category] += 1

            # ユーザー定義パターン数
            if pattern.user_defined:
                user_defined_count += 1

        return {
            "total_patterns": len(self.patterns),
            "categories": categories,
            "user_defined": user_defined_count,
            "built_in": len(self.patterns) - user_defined_count,
        }

    def is_loaded(self) -> bool:
        """パターンデータベースが読み込み済みかどうか

        Returns:
            読み込み済みの場合True
        """
        return self._loaded
