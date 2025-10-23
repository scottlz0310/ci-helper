"""
パターン認識フォールバック機能

パターン認識が失敗した場合の代替手段を提供し、
未知のエラーに対する適切な処理とトラブルシューティングガイダンスを実装します。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import AnalysisError
from .models import AnalysisResult, AnalysisStatus, FixSuggestion, Pattern, PatternMatch, RootCause

logger = logging.getLogger(__name__)


class PatternRecognitionError(AnalysisError):
    """パターン認識エラー"""

    def __init__(self, message: str, log_path: str | None = None, confidence: float = 0.0):
        super().__init__(message, log_path)
        self.confidence = confidence


class UnknownErrorDetector:
    """未知エラー検出器

    既知のパターンにマッチしない新しいエラータイプを検出し、
    学習データとして収集します。
    """

    def __init__(self, data_directory: Path | str = "data/learning"):
        """未知エラー検出器を初期化

        Args:
            data_directory: 学習データディレクトリ
        """
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.unknown_errors_file = self.data_directory / "unknown_errors.json"
        self.error_patterns_file = self.data_directory / "potential_patterns.json"

    def detect_unknown_error(self, log_content: str, failed_patterns: list[Pattern]) -> dict[str, Any]:
        """未知のエラータイプを検出

        Args:
            log_content: ログ内容
            failed_patterns: 失敗したパターンのリスト

        Returns:
            未知エラーの情報
        """
        logger.info("未知エラーの検出を開始...")

        # エラーの特徴を抽出
        error_features = self._extract_error_features(log_content)

        # エラーカテゴリを推測
        error_category = self._infer_error_category(log_content, error_features)

        # 潜在的なパターンを生成
        potential_pattern = self._generate_potential_pattern(log_content, error_features, error_category)

        # 未知エラー情報を作成
        unknown_error_info = {
            "timestamp": datetime.now().isoformat(),
            "log_content_hash": hash(log_content),
            "log_length": len(log_content),
            "error_features": error_features,
            "error_category": error_category,
            "failed_patterns": [p.id for p in failed_patterns],
            "potential_pattern": potential_pattern,
            "occurrence_count": 1,
        }

        # 既存の未知エラーと比較
        existing_error = self._find_similar_unknown_error(unknown_error_info)
        if existing_error:
            existing_error["occurrence_count"] += 1
            existing_error["last_seen"] = datetime.now().isoformat()
            logger.info("既存の未知エラーの発生回数を更新: %s", existing_error["error_category"])
        else:
            # 新しい未知エラーとして保存
            self._save_unknown_error(unknown_error_info)
            logger.info("新しい未知エラーを検出: %s", error_category)

        return unknown_error_info

    def _extract_error_features(self, log_content: str) -> dict[str, Any]:
        """ログからエラーの特徴を抽出

        Args:
            log_content: ログ内容

        Returns:
            エラーの特徴
        """
        features = {
            "error_keywords": [],
            "file_paths": [],
            "line_numbers": [],
            "stack_traces": [],
            "command_outputs": [],
            "exit_codes": [],
            "timestamps": [],
        }

        lines = log_content.split("\n")

        for line in lines:
            line_lower = line.lower()

            # エラーキーワードを検出
            error_keywords = [
                "error",
                "failed",
                "failure",
                "exception",
                "traceback",
                "denied",
                "timeout",
                "not found",
                "invalid",
                "missing",
                "permission",
                "access",
                "connection",
                "network",
                "ssl",
            ]

            for keyword in error_keywords:
                if keyword in line_lower and keyword not in features["error_keywords"]:
                    features["error_keywords"].append(keyword)

            # ファイルパスを検出
            file_path_pattern = r"(?:/[^/\s]+)+\.[a-zA-Z0-9]+"
            file_matches = re.findall(file_path_pattern, line)
            features["file_paths"].extend(file_matches)

            # 行番号を検出
            line_number_pattern = r"line\s+(\d+)|:(\d+):"
            line_matches = re.findall(line_number_pattern, line)
            for match in line_matches:
                line_num = match[0] or match[1]
                if line_num:
                    features["line_numbers"].append(int(line_num))

            # 終了コードを検出
            exit_code_pattern = r"exit\s+code\s+(\d+)|returned\s+(\d+)"
            exit_matches = re.findall(exit_code_pattern, line_lower)
            for match in exit_matches:
                exit_code = match[0] or match[1]
                if exit_code:
                    features["exit_codes"].append(int(exit_code))

            # スタックトレースを検出
            if "traceback" in line_lower or "at " in line_lower:
                features["stack_traces"].append(line.strip())

            # コマンド出力を検出
            if line.strip().startswith("$") or line.strip().startswith(">"):
                features["command_outputs"].append(line.strip())

        # 重複を除去
        for key in features:
            if isinstance(features[key], list):
                features[key] = list(set(features[key]))

        return features

    def _infer_error_category(self, log_content: str, error_features: dict[str, Any]) -> str:
        """エラーカテゴリを推測

        Args:
            log_content: ログ内容
            error_features: エラーの特徴

        Returns:
            推測されたエラーカテゴリ
        """
        log_lower = log_content.lower()
        keywords = error_features.get("error_keywords", [])

        # カテゴリ判定ルール
        category_rules = {
            "permission_error": ["permission", "denied", "access", "forbidden"],
            "network_error": ["timeout", "connection", "network", "ssl", "certificate"],
            "dependency_error": ["not found", "missing", "import", "module", "package"],
            "configuration_error": ["config", "configuration", "invalid", "malformed"],
            "build_error": ["compile", "build", "make", "cmake", "gcc", "clang"],
            "test_error": ["test", "assertion", "failed", "expect"],
            "docker_error": ["docker", "container", "image", "registry"],
            "git_error": ["git", "repository", "commit", "branch", "merge"],
            "syntax_error": ["syntax", "parse", "invalid syntax", "unexpected"],
            "runtime_error": ["runtime", "execution", "segmentation", "core dump"],
        }

        # キーワードベースの判定
        for category, category_keywords in category_rules.items():
            if any(keyword in keywords for keyword in category_keywords):
                return category
            if any(keyword in log_lower for keyword in category_keywords):
                return category

        # 終了コードベースの判定
        exit_codes = error_features.get("exit_codes", [])
        if exit_codes:
            if 1 in exit_codes:
                return "general_error"
            elif 2 in exit_codes:
                return "usage_error"
            elif 126 in exit_codes:
                return "permission_error"
            elif 127 in exit_codes:
                return "command_not_found"
            elif 130 in exit_codes:
                return "interrupted_error"

        return "unknown_error"

    def _generate_potential_pattern(
        self, log_content: str, error_features: dict[str, Any], error_category: str
    ) -> dict[str, Any]:
        """潜在的なパターンを生成

        Args:
            log_content: ログ内容
            error_features: エラーの特徴
            error_category: エラーカテゴリ

        Returns:
            潜在的なパターン情報
        """
        # エラーメッセージを抽出
        error_lines = []
        for line in log_content.split("\n"):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in error_features.get("error_keywords", [])):
                error_lines.append(line.strip())

        # 正規表現パターンを生成
        regex_patterns = []
        for line in error_lines[:3]:  # 最初の3つのエラー行のみ
            # 特殊文字をエスケープし、変数部分を正規表現に変換
            escaped_line = re.escape(line)
            # 数字を正規表現に変換
            pattern = re.sub(r"\\d+", r"\\d+", escaped_line)
            # ファイルパスを正規表現に変換
            pattern = re.sub(r"/[^/\\s]+", r"/[^/\\s]+", pattern)
            regex_patterns.append(pattern)

        # キーワードを抽出
        keywords = error_features.get("error_keywords", [])[:5]  # 最初の5つのキーワード

        return {
            "id": f"auto_generated_{error_category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": f"自動生成パターン: {error_category}",
            "category": error_category,
            "regex_patterns": regex_patterns,
            "keywords": keywords,
            "confidence_base": 0.6,  # 自動生成パターンの基本信頼度
            "auto_generated": True,
            "source_log_hash": hash(log_content),
            "created_at": datetime.now().isoformat(),
        }

    def _find_similar_unknown_error(self, unknown_error_info: dict[str, Any]) -> dict[str, Any] | None:
        """類似の未知エラーを検索

        Args:
            unknown_error_info: 未知エラー情報

        Returns:
            類似のエラー情報、見つからない場合はNone
        """
        if not self.unknown_errors_file.exists():
            return None

        try:
            with self.unknown_errors_file.open("r", encoding="utf-8") as f:
                existing_errors = json.load(f)

            for existing_error in existing_errors:
                # カテゴリが同じかチェック
                if existing_error["error_category"] != unknown_error_info["error_category"]:
                    continue

                # キーワードの類似度をチェック
                existing_keywords = set(existing_error["error_features"].get("error_keywords", []))
                new_keywords = set(unknown_error_info["error_features"].get("error_keywords", []))

                if existing_keywords and new_keywords:
                    similarity = len(existing_keywords & new_keywords) / len(existing_keywords | new_keywords)
                    if similarity > 0.7:  # 70%以上の類似度
                        return existing_error

        except Exception as e:
            logger.error("未知エラーの検索中にエラー: %s", e)

        return None

    def _save_unknown_error(self, unknown_error_info: dict[str, Any]) -> None:
        """未知エラーを保存

        Args:
            unknown_error_info: 未知エラー情報
        """
        try:
            existing_errors = []
            if self.unknown_errors_file.exists():
                with self.unknown_errors_file.open("r", encoding="utf-8") as f:
                    existing_errors = json.load(f)

            existing_errors.append(unknown_error_info)

            with self.unknown_errors_file.open("w", encoding="utf-8") as f:
                json.dump(existing_errors, f, ensure_ascii=False, indent=2)

            logger.info("未知エラーを保存しました: %s", self.unknown_errors_file)

        except Exception as e:
            logger.error("未知エラーの保存に失敗: %s", e)

    def get_frequent_unknown_errors(self, min_occurrences: int = 3) -> list[dict[str, Any]]:
        """頻繁に発生する未知エラーを取得

        Args:
            min_occurrences: 最小発生回数

        Returns:
            頻繁な未知エラーのリスト
        """
        if not self.unknown_errors_file.exists():
            return []

        try:
            with self.unknown_errors_file.open("r", encoding="utf-8") as f:
                unknown_errors = json.load(f)

            frequent_errors = [error for error in unknown_errors if error.get("occurrence_count", 1) >= min_occurrences]

            # 発生回数でソート
            frequent_errors.sort(key=lambda x: x.get("occurrence_count", 1), reverse=True)
            return frequent_errors

        except Exception as e:
            logger.error("頻繁な未知エラーの取得に失敗: %s", e)
            return []


class PatternFallbackHandler:
    """パターン認識フォールバック機能

    パターン認識が失敗した場合の代替手段を提供し、
    トラブルシューティングガイダンスと未知エラーの学習機能を実装します。
    """

    def __init__(self, data_directory: Path | str = "data/learning", learning_engine=None):
        """パターンフォールバック機能を初期化

        Args:
            data_directory: 学習データディレクトリ
            learning_engine: 学習エンジン（オプション）
        """
        self.data_directory = Path(data_directory)
        self.unknown_error_detector = UnknownErrorDetector(data_directory)
        self.troubleshooting_guides = self._load_troubleshooting_guides()
        self.learning_engine = learning_engine

    def handle_pattern_recognition_failure(
        self,
        log_content: str,
        failed_patterns: list[Pattern],
        confidence_threshold: float,
        error: Exception | None = None,
    ) -> AnalysisResult:
        """パターン認識失敗時のフォールバック処理

        Args:
            log_content: ログ内容
            failed_patterns: 失敗したパターンのリスト
            confidence_threshold: 信頼度閾値
            error: 発生したエラー

        Returns:
            フォールバック分析結果
        """
        logger.info("パターン認識フォールバック処理を開始...")

        # 未知エラーを検出
        unknown_error_info = self.unknown_error_detector.detect_unknown_error(log_content, failed_patterns)

        # 学習エンジンに未知エラー情報を送信（非同期処理は呼び出し元で実行）
        if self.learning_engine:
            try:
                # 非同期処理は後で実行するためにフラグを設定
                unknown_error_info["_needs_learning_processing"] = True
                logger.info("未知エラー情報を学習処理用にマークしました")
            except Exception as e:
                logger.warning("学習エンジンへの未知エラー送信準備に失敗: %s", e)

        # エラーカテゴリに基づくフォールバック提案を生成
        fallback_suggestions = self._generate_fallback_suggestions(unknown_error_info, log_content)

        # トラブルシューティングガイダンスを生成
        troubleshooting_steps = self._generate_troubleshooting_guidance(unknown_error_info, log_content)

        # 手動調査ステップを生成
        manual_investigation_steps = self._generate_manual_investigation_steps(unknown_error_info, log_content)

        # フォールバック分析結果を作成
        return AnalysisResult(
            summary=f"パターン認識に失敗しました。{unknown_error_info['error_category']}の可能性があります。",
            root_causes=[
                RootCause(
                    category=unknown_error_info["error_category"],
                    description="未知のエラーパターンが検出されました",
                    confidence=0.3,
                )
            ],
            fix_suggestions=fallback_suggestions,
            related_errors=unknown_error_info["error_features"]["error_keywords"],
            confidence_score=0.3,  # フォールバック結果の信頼度は低め
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FALLBACK,
            timestamp=datetime.now(),
            provider="fallback",
            model="pattern_fallback",
            cache_hit=False,
            fallback_reason="パターン認識失敗",
            troubleshooting_steps=troubleshooting_steps,
            manual_investigation_steps=manual_investigation_steps,
            unknown_error_info=unknown_error_info,
        )

    def handle_low_confidence_patterns(
        self, pattern_matches: list[PatternMatch], confidence_threshold: float, log_content: str
    ) -> AnalysisResult:
        """信頼度が閾値を下回る場合の処理

        Args:
            pattern_matches: パターンマッチ結果
            confidence_threshold: 信頼度閾値
            log_content: ログ内容

        Returns:
            低信頼度パターンの分析結果
        """
        logger.info("低信頼度パターンの処理を開始...")

        # 最も信頼度の高いパターンを選択
        best_match = max(pattern_matches, key=lambda m: m.confidence) if pattern_matches else None

        if not best_match:
            # パターンマッチが全くない場合
            return self.handle_pattern_recognition_failure(log_content, [], confidence_threshold)

        # 手動調査ステップを生成
        manual_steps = self._generate_manual_investigation_steps_for_pattern(best_match, log_content)

        # 信頼度向上のための提案を生成
        confidence_improvement_suggestions = self._generate_confidence_improvement_suggestions(best_match, log_content)

        return AnalysisResult(
            summary=f"パターン '{best_match.pattern.name}' が検出されましたが、信頼度が低いです ({best_match.confidence:.2f} < {confidence_threshold})。",
            root_causes=[
                RootCause(
                    category=best_match.pattern.category,
                    description=best_match.pattern.name,
                    confidence=best_match.confidence,
                )
            ],
            fix_suggestions=confidence_improvement_suggestions,
            related_errors=[best_match.extracted_context],
            confidence_score=best_match.confidence,
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.LOW_CONFIDENCE,
            timestamp=datetime.now(),
            provider="fallback",
            model="low_confidence_handler",
            cache_hit=False,
            fallback_reason=f"信頼度不足 ({best_match.confidence:.2f})",
            manual_investigation_steps=manual_steps,
            pattern_match=best_match,
        )

    def handle_malformed_log(self, log_content: str, error: Exception) -> AnalysisResult:
        """不正な形式のログファイルに対する堅牢な処理

        Args:
            log_content: ログ内容
            error: 発生したエラー

        Returns:
            堅牢な処理結果
        """
        logger.info("不正な形式のログファイルの処理を開始...")

        # ログの基本情報を抽出
        log_info = self._analyze_log_structure(log_content)

        # 修復可能性を評価
        repair_suggestions = self._generate_log_repair_suggestions(log_info, error)

        # 代替分析方法を提案
        alternative_methods = self._suggest_alternative_analysis_methods(log_info)

        return AnalysisResult(
            summary=f"ログファイルの形式に問題があります: {error!s}",
            root_causes=[
                RootCause(
                    category="log_format_error",
                    description="ログファイルの形式が不正です",
                    confidence=0.9,
                )
            ],
            fix_suggestions=repair_suggestions,
            related_errors=[str(error)],
            confidence_score=0.2,
            analysis_time=0.0,
            tokens_used=None,
            status=AnalysisStatus.FAILED,
            timestamp=datetime.now(),
            provider="fallback",
            model="log_repair_handler",
            cache_hit=False,
            fallback_reason="ログ形式エラー",
            log_info=log_info,
            alternative_methods=alternative_methods,
        )

    def _generate_fallback_suggestions(
        self, unknown_error_info: dict[str, Any], log_content: str
    ) -> list[FixSuggestion]:
        """エラーカテゴリに基づくフォールバック提案を生成

        Args:
            unknown_error_info: 未知エラー情報
            log_content: ログ内容

        Returns:
            フォールバック修正提案のリスト
        """
        category = unknown_error_info["error_category"]
        suggestions = []

        # カテゴリ別の一般的な修正提案
        category_suggestions = {
            "permission_error": [
                {
                    "title": "権限設定の確認",
                    "description": "ファイルやディレクトリの権限を確認してください",
                    "steps": [
                        "ls -la でファイル権限を確認",
                        "chmod コマンドで権限を修正",
                        "sudo が必要な場合は管理者権限で実行",
                    ],
                    "risk_level": "low",
                    "time_estimate": "5分",
                }
            ],
            "network_error": [
                {
                    "title": "ネットワーク接続の確認",
                    "description": "ネットワーク接続とプロキシ設定を確認してください",
                    "steps": [
                        "ping コマンドでネットワーク接続を確認",
                        "プロキシ設定を確認",
                        "ファイアウォール設定を確認",
                    ],
                    "risk_level": "low",
                    "time_estimate": "10分",
                }
            ],
            "dependency_error": [
                {
                    "title": "依存関係の確認",
                    "description": "必要なパッケージやライブラリがインストールされているか確認してください",
                    "steps": [
                        "package.json や requirements.txt を確認",
                        "npm install や pip install を実行",
                        "バージョン互換性を確認",
                    ],
                    "risk_level": "medium",
                    "time_estimate": "15分",
                }
            ],
        }

        # カテゴリに対応する提案を取得
        category_fixes = category_suggestions.get(category, [])

        for fix_data in category_fixes:
            suggestion = FixSuggestion(
                title=fix_data["title"],
                description=fix_data["description"],
                risk_level=fix_data["risk_level"],
                estimated_effort=fix_data["time_estimate"],
                confidence=0.4,  # フォールバック提案の信頼度
                validation_steps=fix_data["steps"],
            )
            suggestions.append(suggestion)

        # 一般的な提案を追加
        general_suggestion = FixSuggestion(
            title="ログの詳細確認",
            description="ログファイル全体を確認して追加情報を探してください",
            risk_level="low",
            estimated_effort="10分",
            confidence=0.3,
            validation_steps=[
                "ログファイル全体を確認",
                "エラーメッセージの前後の行を確認",
                "関連するログファイルを確認",
                "公式ドキュメントを参照",
            ],
        )
        suggestions.append(general_suggestion)

        return suggestions

    def _generate_troubleshooting_guidance(self, unknown_error_info: dict[str, Any], log_content: str) -> list[str]:
        """トラブルシューティングガイダンスを生成

        Args:
            unknown_error_info: 未知エラー情報
            log_content: ログ内容

        Returns:
            トラブルシューティングステップのリスト
        """
        category = unknown_error_info["error_category"]
        keywords = unknown_error_info["error_features"]["error_keywords"]

        steps = [
            "1. エラーメッセージを詳細に確認してください",
            f"2. 検出されたキーワード ({', '.join(keywords[:3])}) に注目してください",
            "3. 関連するドキュメントを参照してください",
        ]

        # カテゴリ別の追加ステップ
        category_steps = {
            "permission_error": [
                "4. ファイル権限とディレクトリ権限を確認してください",
                "5. 実行ユーザーの権限を確認してください",
            ],
            "network_error": [
                "4. ネットワーク接続を確認してください",
                "5. プロキシやファイアウォール設定を確認してください",
            ],
            "dependency_error": [
                "4. 必要な依存関係がインストールされているか確認してください",
                "5. バージョン互換性を確認してください",
            ],
            "configuration_error": [
                "4. 設定ファイルの構文を確認してください",
                "5. 必要な設定項目が全て設定されているか確認してください",
            ],
        }

        if category in category_steps:
            steps.extend(category_steps[category])

        steps.extend(
            [
                f"{len(steps) + 1}. 問題が解決しない場合は、コミュニティフォーラムで質問してください",
                f"{len(steps) + 2}. 必要に応じて専門家に相談してください",
            ]
        )

        return steps

    def _generate_manual_investigation_steps(self, unknown_error_info: dict[str, Any], log_content: str) -> list[str]:
        """手動調査ステップを生成

        Args:
            unknown_error_info: 未知エラー情報
            log_content: ログ内容

        Returns:
            手動調査ステップのリスト
        """
        steps = [
            "1. ログファイル全体を確認し、エラーの前後の文脈を把握してください",
            "2. エラーが発生した具体的な操作やコマンドを特定してください",
            "3. 同様のエラーが過去に発生していないか確認してください",
        ]

        # エラーの特徴に基づく調査ステップ
        error_features = unknown_error_info["error_features"]

        if error_features.get("file_paths"):
            steps.append("4. 関連するファイルパスが存在し、アクセス可能か確認してください")

        if error_features.get("exit_codes"):
            exit_codes = error_features["exit_codes"]
            steps.append(f"5. 終了コード ({', '.join(map(str, exit_codes))}) の意味を調べてください")

        if error_features.get("command_outputs"):
            steps.append("6. 失敗したコマンドを手動で実行して詳細なエラー情報を取得してください")

        steps.extend(
            [
                f"{len(steps) + 1}. 環境変数や設定ファイルに問題がないか確認してください",
                f"{len(steps) + 2}. 最小限の再現手順を作成してください",
                f"{len(steps) + 3}. 公式ドキュメントやIssueトラッカーで類似の問題を検索してください",
            ]
        )

        return steps

    def _generate_manual_investigation_steps_for_pattern(
        self, pattern_match: PatternMatch, log_content: str
    ) -> list[str]:
        """特定のパターンに対する手動調査ステップを生成

        Args:
            pattern_match: パターンマッチ結果
            log_content: ログ内容

        Returns:
            手動調査ステップのリスト
        """
        pattern = pattern_match.pattern

        steps = [
            f"1. パターン '{pattern.name}' の詳細を確認してください",
            f"2. 信頼度が低い理由を分析してください (現在: {pattern_match.confidence:.2f})",
            "3. マッチした証拠を詳細に確認してください:",
        ]

        # 裏付け証拠を追加
        for i, evidence in enumerate(pattern_match.supporting_evidence[:3], 4):
            steps.append(f"   - {evidence}")

        steps.extend(
            [
                f"{len(steps) + 1}. パターンの前提条件が満たされているか確認してください",
                f"{len(steps) + 2}. 類似のパターンと比較してください",
                f"{len(steps) + 3}. 追加のコンテキスト情報を収集してください",
            ]
        )

        return steps

    def _generate_confidence_improvement_suggestions(
        self, pattern_match: PatternMatch, log_content: str
    ) -> list[FixSuggestion]:
        """信頼度向上のための提案を生成

        Args:
            pattern_match: パターンマッチ結果
            log_content: ログ内容

        Returns:
            信頼度向上提案のリスト
        """
        suggestions = []

        # 追加情報収集の提案
        info_gathering = FixSuggestion(
            title="追加情報の収集",
            description="パターンマッチの信頼度を向上させるために追加情報を収集してください",
            risk_level="low",
            estimated_effort="15分",
            confidence=0.6,
            validation_steps=[
                "より詳細なログを有効にして再実行",
                "関連するログファイルを確認",
                "環境情報を収集",
                "再現手順を詳細に記録",
            ],
        )
        suggestions.append(info_gathering)

        # パターン検証の提案
        pattern_verification = FixSuggestion(
            title="パターン検証",
            description="検出されたパターンが正しいかどうかを検証してください",
            risk_level="low",
            estimated_effort="20分",
            confidence=0.5,
            validation_steps=[
                f"パターン '{pattern_match.pattern.name}' の説明を確認",
                "マッチした部分が実際にエラーの原因か確認",
                "他の可能性を排除",
                "専門家に相談",
            ],
        )
        suggestions.append(pattern_verification)

        return suggestions

    def _analyze_log_structure(self, log_content: str) -> dict[str, Any]:
        """ログの構造を分析

        Args:
            log_content: ログ内容

        Returns:
            ログ構造の分析結果
        """
        lines = log_content.split("\n")

        return {
            "total_lines": len(lines),
            "non_empty_lines": len([line for line in lines if line.strip()]),
            "encoding_issues": self._detect_encoding_issues(log_content),
            "line_length_stats": {
                "max": max(len(line) for line in lines) if lines else 0,
                "avg": sum(len(line) for line in lines) / len(lines) if lines else 0,
            },
            "suspected_truncation": self._detect_truncation(lines),
            "format_consistency": self._analyze_format_consistency(lines),
        }

    def _detect_encoding_issues(self, log_content: str) -> list[str]:
        """エンコーディング問題を検出

        Args:
            log_content: ログ内容

        Returns:
            検出された問題のリスト
        """
        issues = []

        # 不正な文字を検出
        if "�" in log_content:
            issues.append("不正な文字が検出されました (エンコーディング問題の可能性)")

        # 制御文字を検出
        control_chars = sum(1 for char in log_content if ord(char) < 32 and char not in "\n\r\t")
        if control_chars > 0:
            issues.append(f"制御文字が {control_chars} 個検出されました")

        return issues

    def _detect_truncation(self, lines: list[str]) -> bool:
        """ログの切り詰めを検出

        Args:
            lines: ログの行リスト

        Returns:
            切り詰められている可能性があるかどうか
        """
        if not lines:
            return False

        # 最後の行が不完全かチェック
        last_line = lines[-1].strip()
        if last_line and not last_line.endswith((".", "!", "?", ":", ";")):
            return True

        # 急激な終了パターンをチェック
        if len(lines) > 10:
            recent_lines = lines[-10:]
            if all(len(line.strip()) < 10 for line in recent_lines):
                return True

        return False

    def _analyze_format_consistency(self, lines: list[str]) -> dict[str, Any]:
        """ログ形式の一貫性を分析

        Args:
            lines: ログの行リスト

        Returns:
            形式一貫性の分析結果
        """
        # タイムスタンプパターンを検出
        timestamp_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}:\d{2}:\d{2}",  # HH:MM:SS
            r"\[\d{4}-\d{2}-\d{2}",  # [YYYY-MM-DD
        ]

        timestamp_lines = 0
        for line in lines[:100]:  # 最初の100行をチェック
            if any(re.search(pattern, line) for pattern in timestamp_patterns):
                timestamp_lines += 1

        return {
            "has_timestamps": timestamp_lines > 0,
            "timestamp_consistency": timestamp_lines / min(len(lines), 100) if lines else 0,
            "suspected_format": self._guess_log_format(lines[:10]),
        }

    def _guess_log_format(self, sample_lines: list[str]) -> str:
        """ログ形式を推測

        Args:
            sample_lines: サンプル行

        Returns:
            推測されたログ形式
        """
        formats = {
            "github_actions": ["##[", "::"],
            "docker": ["STEP", "RUN", "COPY"],
            "npm": ["npm ERR!", "npm WARN"],
            "python": ["Traceback", 'File "', "line "],
            "generic": [],
        }

        for format_name, keywords in formats.items():
            if format_name == "generic":
                continue
            if any(any(keyword in line for keyword in keywords) for line in sample_lines):
                return format_name

        return "generic"

    def _generate_log_repair_suggestions(self, log_info: dict[str, Any], error: Exception) -> list[FixSuggestion]:
        """ログ修復提案を生成

        Args:
            log_info: ログ情報
            error: 発生したエラー

        Returns:
            ログ修復提案のリスト
        """
        suggestions = []

        # エンコーディング問題の修復
        if log_info.get("encoding_issues"):
            encoding_fix = FixSuggestion(
                title="エンコーディング問題の修復",
                description="ログファイルのエンコーディング問題を修復してください",
                risk_level="low",
                estimated_effort="5分",
                confidence=0.7,
                validation_steps=[
                    "ログファイルのエンコーディングを確認",
                    "UTF-8で再保存",
                    "不正な文字を除去",
                ],
            )
            suggestions.append(encoding_fix)

        # 切り詰め問題の対処
        if log_info.get("suspected_truncation"):
            truncation_fix = FixSuggestion(
                title="ログ切り詰め問題の対処",
                description="ログが切り詰められている可能性があります",
                risk_level="medium",
                estimated_effort="10分",
                confidence=0.6,
                validation_steps=[
                    "完全なログファイルを取得",
                    "ログローテーション設定を確認",
                    "より詳細なログレベルを設定",
                ],
            )
            suggestions.append(truncation_fix)

        return suggestions

    def _suggest_alternative_analysis_methods(self, log_info: dict[str, Any]) -> list[str]:
        """代替分析方法を提案

        Args:
            log_info: ログ情報

        Returns:
            代替分析方法のリスト
        """
        methods = [
            "1. ログファイルを手動で確認",
            "2. grep コマンドでエラーキーワードを検索",
            "3. ログを小さなチャンクに分割して分析",
        ]

        suspected_format = log_info.get("format_consistency", {}).get("suspected_format")
        if suspected_format and suspected_format != "generic":
            methods.append(f"4. {suspected_format} 専用のログ解析ツールを使用")

        methods.extend(
            [
                "5. 元のCI実行環境で直接確認",
                "6. 関連するドキュメントを参照",
            ]
        )

        return methods

    def _load_troubleshooting_guides(self) -> dict[str, Any]:
        """トラブルシューティングガイドを読み込み

        Returns:
            トラブルシューティングガイド
        """
        # 基本的なトラブルシューティングガイドを定義
        # 実際の実装では外部ファイルから読み込むことも可能
        return {
            "permission_error": {
                "description": "権限関連のエラー",
                "common_causes": ["ファイル権限不足", "ディレクトリアクセス権限不足", "実行権限不足"],
                "solutions": ["chmod で権限変更", "sudo で実行", "所有者変更"],
            },
            "network_error": {
                "description": "ネットワーク関連のエラー",
                "common_causes": ["接続タイムアウト", "DNS解決失敗", "プロキシ設定問題"],
                "solutions": ["ネットワーク接続確認", "プロキシ設定確認", "DNS設定確認"],
            },
            "dependency_error": {
                "description": "依存関係のエラー",
                "common_causes": ["パッケージ未インストール", "バージョン不整合", "依存関係循環"],
                "solutions": ["パッケージインストール", "バージョン確認", "依存関係解決"],
            },
        }

    def get_unknown_error_statistics(self) -> dict[str, Any]:
        """未知エラーの統計情報を取得

        Returns:
            統計情報
        """
        return {
            "total_unknown_errors": len(self.unknown_error_detector.get_frequent_unknown_errors(min_occurrences=1)),
            "frequent_unknown_errors": len(self.unknown_error_detector.get_frequent_unknown_errors(min_occurrences=3)),
            "data_directory": str(self.data_directory),
        }
