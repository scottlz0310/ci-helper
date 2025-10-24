"""
カスタムパターン管理

ユーザー定義パターンの作成、管理、インポート/エクスポート機能を提供します。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.config import Config
from .exceptions import ConfigurationError, ValidationError
from .models import Pattern


class CustomPatternManager:
    """カスタムパターン管理クラス"""

    def __init__(self, config: Config):
        """カスタムパターン管理を初期化

        Args:
            config: メイン設定オブジェクト
        """
        self.config = config
        self.custom_patterns_dir = self.config.get_pattern_database_path() / "custom"
        self.custom_patterns_file = self.custom_patterns_dir / "user_patterns.json"

    def create_custom_pattern(
        self,
        name: str,
        category: str,
        regex_patterns: list[str],
        keywords: list[str],
        context_requirements: list[str] | None = None,
        confidence_base: float = 0.7,
    ) -> Pattern:
        """カスタムパターンを作成

        Args:
            name: パターン名
            category: カテゴリ
            regex_patterns: 正規表現パターンのリスト
            keywords: キーワードのリスト
            context_requirements: コンテキスト要件のリスト
            confidence_base: 基本信頼度

        Returns:
            作成されたPatternオブジェクト

        Raises:
            ValidationError: パターンが無効な場合
        """
        # パターンの検証
        self._validate_pattern_data(name, category, regex_patterns, keywords, confidence_base)

        # パターンIDを生成
        pattern_id = f"custom_{uuid.uuid4().hex[:8]}"

        # Patternオブジェクトを作成
        pattern = Pattern(
            id=pattern_id,
            name=name,
            category=category,
            regex_patterns=regex_patterns,
            keywords=keywords,
            context_requirements=context_requirements or [],
            confidence_base=confidence_base,
            success_rate=0.0,  # 新規パターンは成功率0から開始
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_defined=True,
        )

        # パターンを保存
        self._save_custom_pattern(pattern)

        return pattern

    def load_custom_patterns(self) -> list[Pattern]:
        """カスタムパターンを読み込み

        Returns:
            カスタムパターンのリスト
        """
        if not self.custom_patterns_file.exists():
            return []

        try:
            with open(self.custom_patterns_file, encoding="utf-8") as f:
                patterns_data = json.load(f)

            patterns = []
            for pattern_data in patterns_data.get("patterns", []):
                pattern = Pattern(
                    id=pattern_data["id"],
                    name=pattern_data["name"],
                    category=pattern_data["category"],
                    regex_patterns=pattern_data["regex_patterns"],
                    keywords=pattern_data["keywords"],
                    context_requirements=pattern_data.get("context_requirements", []),
                    confidence_base=pattern_data.get("confidence_base", 0.7),
                    success_rate=pattern_data.get("success_rate", 0.0),
                    created_at=datetime.fromisoformat(pattern_data["created_at"]),
                    updated_at=datetime.fromisoformat(pattern_data["updated_at"]),
                    user_defined=pattern_data.get("user_defined", True),
                )
                patterns.append(pattern)

            return patterns

        except Exception as e:
            raise ConfigurationError(
                f"カスタムパターンの読み込みに失敗しました: {self.custom_patterns_file}",
                f"ファイルの形式を確認してください: {e}",
            ) from e

    def update_custom_pattern(self, pattern_id: str, **updates: Any) -> Pattern:
        """カスタムパターンを更新

        Args:
            pattern_id: パターンID
            **updates: 更新する項目

        Returns:
            更新されたPatternオブジェクト

        Raises:
            ValidationError: パターンが見つからない場合
        """
        patterns = self.load_custom_patterns()
        pattern_to_update = None

        for pattern in patterns:
            if pattern.id == pattern_id:
                pattern_to_update = pattern
                break

        if pattern_to_update is None:
            raise ValidationError(
                f"カスタムパターンが見つかりません: {pattern_id}",
                "存在するパターンIDを指定してください",
            )

        # 更新可能な項目のみ処理
        updatable_fields = ["name", "category", "regex_patterns", "keywords", "context_requirements", "confidence_base"]

        for field, value in updates.items():
            if field in updatable_fields:
                setattr(pattern_to_update, field, value)

        # 更新日時を設定
        pattern_to_update.updated_at = datetime.now()

        # 更新されたパターンを検証
        self._validate_pattern_object(pattern_to_update)

        # パターンリストを保存
        self._save_all_custom_patterns(patterns)

        return pattern_to_update

    def delete_custom_pattern(self, pattern_id: str) -> bool:
        """カスタムパターンを削除

        Args:
            pattern_id: パターンID

        Returns:
            削除が成功したかどうか
        """
        patterns = self.load_custom_patterns()
        original_count = len(patterns)

        # 指定されたIDのパターンを除外
        patterns = [p for p in patterns if p.id != pattern_id]

        if len(patterns) == original_count:
            return False  # パターンが見つからなかった

        # 更新されたパターンリストを保存
        self._save_all_custom_patterns(patterns)
        return True

    def export_patterns(self, output_file: Path, pattern_ids: list[str] | None = None) -> None:
        """パターンをエクスポート

        Args:
            output_file: 出力ファイルパス
            pattern_ids: エクスポートするパターンIDのリスト（Noneの場合は全て）

        Raises:
            ConfigurationError: エクスポートに失敗した場合
        """
        patterns = self.load_custom_patterns()

        # 指定されたパターンのみフィルタリング
        if pattern_ids is not None:
            patterns = [p for p in patterns if p.id in pattern_ids]

        # エクスポート用データを作成
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
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
                }
                for pattern in patterns
            ],
        }

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise ConfigurationError(
                f"パターンのエクスポートに失敗しました: {output_file}",
                f"ファイルの書き込み権限を確認してください: {e}",
            ) from e

    def import_patterns(self, import_file: Path, overwrite: bool = False) -> list[Pattern]:
        """パターンをインポート

        Args:
            import_file: インポートファイルパス
            overwrite: 既存パターンを上書きするかどうか

        Returns:
            インポートされたPatternオブジェクトのリスト

        Raises:
            ConfigurationError: インポートに失敗した場合
        """
        if not import_file.exists():
            raise ConfigurationError(
                f"インポートファイルが見つかりません: {import_file}",
                "ファイルパスを確認してください",
            )

        try:
            with open(import_file, encoding="utf-8") as f:
                import_data = json.load(f)

        except Exception as e:
            raise ConfigurationError(
                f"インポートファイルの読み込みに失敗しました: {import_file}",
                f"JSONファイルの形式を確認してください: {e}",
            ) from e

        # インポートデータの検証
        if "patterns" not in import_data:
            raise ConfigurationError(
                "インポートファイルにパターンデータが含まれていません",
                "正しいエクスポートファイルを指定してください",
            )

        # 既存パターンを読み込み
        existing_patterns = self.load_custom_patterns()
        existing_ids = {p.id for p in existing_patterns}

        imported_patterns = []
        for pattern_data in import_data["patterns"]:
            try:
                # パターンIDの重複チェック
                pattern_id = pattern_data["id"]
                if pattern_id in existing_ids and not overwrite:
                    # 新しいIDを生成
                    pattern_id = f"imported_{uuid.uuid4().hex[:8]}"

                pattern = Pattern(
                    id=pattern_id,
                    name=pattern_data["name"],
                    category=pattern_data["category"],
                    regex_patterns=pattern_data["regex_patterns"],
                    keywords=pattern_data["keywords"],
                    context_requirements=pattern_data.get("context_requirements", []),
                    confidence_base=pattern_data.get("confidence_base", 0.7),
                    success_rate=pattern_data.get("success_rate", 0.0),
                    created_at=datetime.fromisoformat(pattern_data["created_at"]),
                    updated_at=datetime.now(),  # インポート時に更新
                    user_defined=True,  # インポートされたパターンはユーザー定義扱い
                )

                # パターンを検証
                self._validate_pattern_object(pattern)
                imported_patterns.append(pattern)

            except Exception:
                # 個別パターンのエラーは警告として扱い、処理を継続
                continue

        # インポートされたパターンを既存パターンに追加
        if overwrite:
            # 上書きモードの場合、同じIDのパターンを置換
            updated_patterns = []
            imported_ids = {p.id for p in imported_patterns}

            for existing_pattern in existing_patterns:
                if existing_pattern.id not in imported_ids:
                    updated_patterns.append(existing_pattern)

            updated_patterns.extend(imported_patterns)
        else:
            # 追加モードの場合、既存パターンに追加
            updated_patterns = existing_patterns + imported_patterns

        # 更新されたパターンリストを保存
        self._save_all_custom_patterns(updated_patterns)

        return imported_patterns

    def validate_pattern_integration(self, patterns: list[Pattern]) -> dict[str, Any]:
        """パターンの統合検証

        Args:
            patterns: 検証するパターンのリスト

        Returns:
            検証結果の辞書
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "pattern_count": len(patterns),
            "category_distribution": {},
            "duplicate_names": [],
            "conflicting_patterns": [],
        }

        # カテゴリ分布を計算
        for pattern in patterns:
            category = pattern.category
            validation_result["category_distribution"][category] = (
                validation_result["category_distribution"].get(category, 0) + 1
            )

        # 重複名をチェック
        names = [p.name for p in patterns]
        seen_names = set()
        for name in names:
            if name in seen_names:
                validation_result["duplicate_names"].append(name)
            seen_names.add(name)

        # パターンの競合をチェック
        for i, pattern1 in enumerate(patterns):
            for _j, pattern2 in enumerate(patterns[i + 1 :], i + 1):
                if self._patterns_conflict(pattern1, pattern2):
                    validation_result["conflicting_patterns"].append(
                        {
                            "pattern1": pattern1.name,
                            "pattern2": pattern2.name,
                            "reason": "類似した正規表現パターン",
                        }
                    )

        # 警告とエラーを設定
        if validation_result["duplicate_names"]:
            validation_result["warnings"].append(
                f"重複するパターン名があります: {', '.join(validation_result['duplicate_names'])}"
            )

        if validation_result["conflicting_patterns"]:
            validation_result["warnings"].append(
                f"{len(validation_result['conflicting_patterns'])}件のパターン競合が検出されました"
            )

        # 有効性を判定
        validation_result["valid"] = len(validation_result["errors"]) == 0

        return validation_result

    def _validate_pattern_data(
        self,
        name: str,
        category: str,
        regex_patterns: list[str],
        keywords: list[str],
        confidence_base: float,
    ) -> None:
        """パターンデータの検証

        Args:
            name: パターン名
            category: カテゴリ
            regex_patterns: 正規表現パターンのリスト
            keywords: キーワードのリスト
            confidence_base: 基本信頼度

        Raises:
            ValidationError: データが無効な場合
        """
        if not name or not isinstance(name, str):
            raise ValidationError("パターン名は空でない文字列である必要があります")

        if not category or not isinstance(category, str):
            raise ValidationError("カテゴリは空でない文字列である必要があります")

        if not isinstance(regex_patterns, list) or not regex_patterns:
            raise ValidationError("正規表現パターンは空でないリストである必要があります")

        if not isinstance(keywords, list) or not keywords:
            raise ValidationError("キーワードは空でないリストである必要があります")

        if not isinstance(confidence_base, (int, float)) or not (0.0 <= confidence_base <= 1.0):
            raise ValidationError("基本信頼度は0.0から1.0の間の数値である必要があります")

        # 正規表現の妥当性をチェック
        import re

        for pattern in regex_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValidationError(f"無効な正規表現パターンです: {pattern} - {e}") from e

    def _validate_pattern_object(self, pattern: Pattern) -> None:
        """Patternオブジェクトの検証

        Args:
            pattern: 検証するPatternオブジェクト

        Raises:
            ValidationError: パターンが無効な場合
        """
        self._validate_pattern_data(
            pattern.name,
            pattern.category,
            pattern.regex_patterns,
            pattern.keywords,
            pattern.confidence_base,
        )

    def _save_custom_pattern(self, pattern: Pattern) -> None:
        """単一のカスタムパターンを保存

        Args:
            pattern: 保存するPatternオブジェクト
        """
        patterns = self.load_custom_patterns()
        patterns.append(pattern)
        self._save_all_custom_patterns(patterns)

    def _save_all_custom_patterns(self, patterns: list[Pattern]) -> None:
        """全てのカスタムパターンを保存

        Args:
            patterns: 保存するPatternオブジェクトのリスト

        Raises:
            ConfigurationError: 保存に失敗した場合
        """
        # ディレクトリを作成
        self.custom_patterns_dir.mkdir(parents=True, exist_ok=True)

        # パターンデータを作成
        patterns_data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
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
                }
                for pattern in patterns
            ],
        }

        try:
            with open(self.custom_patterns_file, "w", encoding="utf-8") as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise ConfigurationError(
                f"カスタムパターンの保存に失敗しました: {self.custom_patterns_file}",
                f"ファイルの書き込み権限を確認してください: {e}",
            ) from e

    def _patterns_conflict(self, pattern1: Pattern, pattern2: Pattern) -> bool:
        """2つのパターンが競合するかどうかをチェック

        Args:
            pattern1: パターン1
            pattern2: パターン2

        Returns:
            競合するかどうか
        """
        # 同じカテゴリで類似したキーワードを持つ場合は競合とみなす
        if pattern1.category == pattern2.category:
            common_keywords = set(pattern1.keywords) & set(pattern2.keywords)
            if len(common_keywords) > 0:
                return True

        return False
