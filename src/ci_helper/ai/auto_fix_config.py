"""
自動修正設定システム

自動修正の動作設定、リスク許容度、バックアップポリシーの管理を提供します。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..core.exceptions import ConfigurationError
from ..utils.config import Config


class ValidationError(Exception):
    """検証エラー"""

    pass


class AutoFixConfigManager:
    """自動修正設定管理クラス"""

    def __init__(self, config: Config):
        """自動修正設定管理を初期化

        Args:
            config: メイン設定オブジェクト
        """
        self.config = config
        self.auto_fix_config_dir = self.config.project_root / ".ci-helper" / "auto_fix"
        self.auto_fix_config_file = self.auto_fix_config_dir / "config.json"

    def get_auto_fix_settings(self) -> dict[str, Any]:
        """自動修正設定を取得

        Returns:
            自動修正設定の辞書
        """
        return {
            "enabled": self.config.is_auto_fix_enabled(),
            "confidence_threshold": self.config.get_auto_fix_confidence_threshold(),
            "risk_tolerance": self.config.get_auto_fix_risk_tolerance(),
            "backup_policy": self.get_backup_policy(),
            "approval_settings": self.get_approval_settings(),
            "safety_checks": self.get_safety_checks(),
        }

    def get_backup_policy(self) -> dict[str, Any]:
        """バックアップポリシーを取得

        Returns:
            バックアップポリシーの辞書
        """
        return {
            "enabled": self.config.is_backup_before_fix_enabled(),
            "retention_days": self.config.get_backup_retention_days(),
            "backup_location": str(self.get_backup_directory()),
            "compression_enabled": True,
            "max_backup_size_mb": 100,
        }

    def get_approval_settings(self) -> dict[str, Any]:
        """承認設定を取得

        Returns:
            承認設定の辞書
        """
        risk_tolerance = self.config.get_auto_fix_risk_tolerance()

        # リスク許容度に基づく承認設定
        approval_settings = {
            "require_approval_for_high_risk": True,
            "require_approval_for_medium_risk": risk_tolerance == "low",
            "require_approval_for_low_risk": False,
            "auto_approve_threshold": self.config.get_auto_fix_confidence_threshold(),
            "timeout_seconds": 300,  # 5分
        }

        return approval_settings

    def get_safety_checks(self) -> dict[str, Any]:
        """安全性チェック設定を取得

        Returns:
            安全性チェック設定の辞書
        """
        return {
            "verify_before_apply": True,
            "dry_run_enabled": True,
            "rollback_on_failure": True,
            "validate_file_permissions": True,
            "check_git_status": True,
            "protected_files": self.get_protected_files(),
        }

    def get_protected_files(self) -> list[str]:
        """保護されたファイルのリストを取得

        Returns:
            保護されたファイルパターンのリスト
        """
        return [
            ".git/*",
            "*.key",
            "*.pem",
            "*.p12",
            ".env",
            "secrets/*",
            "private/*",
        ]

    def validate_fix_request(self, fix_request: dict[str, Any]) -> dict[str, Any]:
        """修正リクエストの妥当性を検証

        Args:
            fix_request: 修正リクエストの辞書

        Returns:
            検証結果の辞書
        """
        validation_result = {
            "valid": True,
            "can_auto_apply": False,
            "requires_approval": False,
            "risk_level": "unknown",
            "confidence": 0.0,
            "warnings": [],
            "errors": [],
        }

        try:
            # 必須フィールドの確認
            required_fields = ["confidence", "risk_level", "files_to_modify"]
            for field in required_fields:
                if field not in fix_request:
                    validation_result["errors"].append(f"必須フィールドが不足しています: {field}")

            if validation_result["errors"]:
                validation_result["valid"] = False
                return validation_result

            # 信頼度の検証
            confidence = fix_request["confidence"]
            if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
                validation_result["errors"].append(f"信頼度が無効です: {confidence}")
                validation_result["valid"] = False
                return validation_result

            validation_result["confidence"] = confidence

            # リスクレベルの検証
            risk_level = fix_request["risk_level"]
            valid_risk_levels = ["low", "medium", "high"]
            if risk_level not in valid_risk_levels:
                validation_result["errors"].append(f"無効なリスクレベルです: {risk_level}")
                validation_result["valid"] = False
                return validation_result

            validation_result["risk_level"] = risk_level

            # 自動適用可能性の判定
            auto_fix_enabled = self.config.is_auto_fix_enabled()
            confidence_threshold = self.config.get_auto_fix_confidence_threshold()

            if auto_fix_enabled and confidence >= confidence_threshold:
                validation_result["can_auto_apply"] = True

            # 承認要否の判定
            approval_settings = self.get_approval_settings()
            if risk_level == "high" and approval_settings["require_approval_for_high_risk"]:
                validation_result["requires_approval"] = True
            elif risk_level == "medium" and approval_settings["require_approval_for_medium_risk"]:
                validation_result["requires_approval"] = True
            elif risk_level == "low" and approval_settings["require_approval_for_low_risk"]:
                validation_result["requires_approval"] = True

            # ファイル保護チェック
            files_to_modify = fix_request.get("files_to_modify", [])
            protected_files = self.get_protected_files()

            for file_path in files_to_modify:
                if self._is_protected_file(file_path, protected_files):
                    validation_result["warnings"].append(f"保護されたファイルが含まれています: {file_path}")
                    validation_result["requires_approval"] = True

        except Exception as e:
            validation_result["errors"].append(f"検証中にエラーが発生しました: {e}")
            validation_result["valid"] = False

        return validation_result

    def create_fix_execution_plan(self, fix_request: dict[str, Any]) -> dict[str, Any]:
        """修正実行計画を作成

        Args:
            fix_request: 修正リクエストの辞書

        Returns:
            実行計画の辞書
        """
        validation_result = self.validate_fix_request(fix_request)

        if not validation_result["valid"]:
            raise ValidationError(
                "修正リクエストが無効です",
                f"エラー: {', '.join(validation_result['errors'])}",
            )

        execution_plan = {
            "fix_id": f"fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now().isoformat(),
            "validation_result": validation_result,
            "execution_steps": [],
            "backup_plan": None,
            "rollback_plan": None,
        }

        # バックアップ計画の作成
        if self.config.is_backup_before_fix_enabled():
            execution_plan["backup_plan"] = self._create_backup_plan(fix_request)

        # 実行ステップの作成
        execution_plan["execution_steps"] = self._create_execution_steps(fix_request)

        # ロールバック計画の作成
        execution_plan["rollback_plan"] = self._create_rollback_plan(fix_request)

        return execution_plan

    def save_auto_fix_settings(self, settings: dict[str, Any]) -> None:
        """自動修正設定を保存

        Args:
            settings: 保存する設定の辞書

        Raises:
            ConfigurationError: 保存に失敗した場合
        """
        # 設定の検証
        self._validate_auto_fix_settings(settings)

        # 設定ディレクトリを作成
        self.auto_fix_config_dir.mkdir(parents=True, exist_ok=True)

        # 設定データを作成
        config_data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "settings": settings,
        }

        try:
            with open(self.auto_fix_config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise ConfigurationError(
                f"自動修正設定の保存に失敗しました: {self.auto_fix_config_file}",
                f"ファイルの書き込み権限を確認してください: {e}",
            ) from e

    def load_auto_fix_settings(self) -> dict[str, Any]:
        """自動修正設定を読み込み

        Returns:
            自動修正設定の辞書
        """
        if not self.auto_fix_config_file.exists():
            return self.get_auto_fix_settings()  # デフォルト設定を返す

        try:
            with open(self.auto_fix_config_file, encoding="utf-8") as f:
                config_data = json.load(f)

            return config_data.get("settings", self.get_auto_fix_settings())

        except Exception as e:
            raise ConfigurationError(
                f"自動修正設定の読み込みに失敗しました: {self.auto_fix_config_file}",
                f"ファイルの形式を確認してください: {e}",
            ) from e

    def get_backup_directory(self) -> Path:
        """バックアップディレクトリを取得

        Returns:
            バックアップディレクトリのパス
        """
        return self.config.project_root / ".ci-helper" / "backups"

    def cleanup_old_backups(self) -> dict[str, Any]:
        """古いバックアップをクリーンアップ

        Returns:
            クリーンアップ結果の辞書
        """
        backup_dir = self.get_backup_directory()
        retention_days = self.config.get_backup_retention_days()
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        cleanup_result = {
            "cleaned_files": 0,
            "freed_space_mb": 0.0,
            "errors": [],
        }

        if not backup_dir.exists():
            return cleanup_result

        try:
            for backup_file in backup_dir.rglob("*"):
                if backup_file.is_file():
                    # ファイルの作成日時をチェック
                    file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                    if file_mtime < cutoff_date:
                        file_size_mb = backup_file.stat().st_size / (1024 * 1024)
                        backup_file.unlink()
                        cleanup_result["cleaned_files"] += 1
                        cleanup_result["freed_space_mb"] += file_size_mb

        except Exception as e:
            cleanup_result["errors"].append(f"クリーンアップ中にエラーが発生しました: {e}")

        return cleanup_result

    def _validate_auto_fix_settings(self, settings: dict[str, Any]) -> None:
        """自動修正設定の検証

        Args:
            settings: 検証する設定の辞書

        Raises:
            ValidationError: 設定が無効な場合
        """
        # 必須フィールドの確認
        required_fields = ["enabled", "confidence_threshold", "risk_tolerance"]
        for field in required_fields:
            if field not in settings:
                raise ValidationError(f"必須設定フィールドが不足しています: {field}")

        # 信頼度閾値の検証
        confidence_threshold = settings["confidence_threshold"]
        if not isinstance(confidence_threshold, (int, float)) or not (0.0 <= confidence_threshold <= 1.0):
            raise ValidationError(f"信頼度閾値が無効です: {confidence_threshold}")

        # リスク許容度の検証
        risk_tolerance = settings["risk_tolerance"]
        valid_risk_levels = ["low", "medium", "high"]
        if risk_tolerance not in valid_risk_levels:
            raise ValidationError(f"無効なリスク許容度です: {risk_tolerance}")

    def _is_protected_file(self, file_path: str, protected_patterns: list[str]) -> bool:
        """ファイルが保護されているかどうかをチェック

        Args:
            file_path: ファイルパス
            protected_patterns: 保護されたファイルパターンのリスト

        Returns:
            ファイルが保護されているかどうか
        """
        import fnmatch

        for pattern in protected_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def _create_backup_plan(self, fix_request: dict[str, Any]) -> dict[str, Any]:
        """バックアップ計画を作成

        Args:
            fix_request: 修正リクエストの辞書

        Returns:
            バックアップ計画の辞書
        """
        files_to_backup = fix_request.get("files_to_modify", [])
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return {
            "backup_id": backup_id,
            "files_to_backup": files_to_backup,
            "backup_location": str(self.get_backup_directory() / backup_id),
            "compression_enabled": True,
            "verify_backup": True,
        }

    def _create_execution_steps(self, fix_request: dict[str, Any]) -> list[dict[str, Any]]:
        """実行ステップを作成

        Args:
            fix_request: 修正リクエストの辞書

        Returns:
            実行ステップのリスト
        """
        steps = []

        # 1. 事前チェック
        steps.append(
            {
                "step": "pre_check",
                "description": "修正前の事前チェックを実行",
                "actions": [
                    "ファイル存在確認",
                    "権限チェック",
                    "Gitステータス確認",
                ],
            }
        )

        # 2. バックアップ作成
        if self.config.is_backup_before_fix_enabled():
            steps.append(
                {
                    "step": "create_backup",
                    "description": "修正対象ファイルのバックアップを作成",
                    "actions": [
                        "バックアップディレクトリ作成",
                        "ファイルコピー",
                        "バックアップ検証",
                    ],
                }
            )

        # 3. 修正適用
        steps.append(
            {
                "step": "apply_fix",
                "description": "修正を適用",
                "actions": fix_request.get("fix_steps", []),
            }
        )

        # 4. 検証
        steps.append(
            {
                "step": "verify_fix",
                "description": "修正結果を検証",
                "actions": [
                    "ファイル整合性チェック",
                    "構文チェック",
                    "機能テスト",
                ],
            }
        )

        return steps

    def _create_rollback_plan(self, fix_request: dict[str, Any]) -> dict[str, Any]:
        """ロールバック計画を作成

        Args:
            fix_request: 修正リクエストの辞書

        Returns:
            ロールバック計画の辞書
        """
        return {
            "enabled": True,
            "trigger_conditions": [
                "修正適用失敗",
                "検証失敗",
                "ユーザー要求",
            ],
            "rollback_steps": [
                "バックアップからファイル復元",
                "権限復元",
                "整合性チェック",
            ],
            "verification_steps": [
                "ファイル存在確認",
                "内容確認",
                "権限確認",
            ],
        }

    def get_risk_assessment_criteria(self) -> dict[str, Any]:
        """リスク評価基準を取得

        Returns:
            リスク評価基準の辞書
        """
        return {
            "low_risk": {
                "description": "設定ファイルの軽微な変更",
                "examples": [
                    "コメント追加",
                    "フォーマット修正",
                    "非重要な設定値変更",
                ],
                "auto_approve": True,
            },
            "medium_risk": {
                "description": "機能に影響する可能性のある変更",
                "examples": [
                    "依存関係の更新",
                    "環境変数の変更",
                    "ビルド設定の変更",
                ],
                "auto_approve": False,
            },
            "high_risk": {
                "description": "システムに重大な影響を与える可能性のある変更",
                "examples": [
                    "セキュリティ設定の変更",
                    "重要なファイルの削除",
                    "権限設定の変更",
                ],
                "auto_approve": False,
            },
        }
