"""セキュリティとシークレット管理

ログ内のシークレット検出、フィルタリング、および安全な環境変数管理を提供します。
"""

from __future__ import annotations

import os
import re
from typing import Any, TypedDict

from ..core.exceptions import SecurityError


class SecretStatus(TypedDict):
    """個々のシークレット状態を表す辞書構造"""

    key: str
    description: str
    configured: bool


class SecretValidationResult(TypedDict):
    """シークレット検証の結果構造"""

    valid: bool
    missing_secrets: list[SecretStatus]
    available_secrets: list[SecretStatus]
    recommendations: list[str]


class SecretSummaryEntry(TypedDict):
    """サマリー中のシークレット項目"""

    description: str
    configured: bool


class SecretSummary(TypedDict):
    """シークレット設定サマリー"""

    required_secrets: dict[str, SecretSummaryEntry]
    optional_secrets: dict[str, SecretSummaryEntry]
    total_configured: int
    total_missing: int


class SecretDetector:
    """シークレット検出とフィルタリングクラス"""

    def __init__(self) -> None:
        """シークレット検出器を初期化"""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """シークレット検出パターンをコンパイル"""
        # 一般的なシークレットパターン
        self.secret_patterns = {
            "api_key": [
                # 一般的なAPIキーパターン
                re.compile(r"(?i)api[_-]?key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)apikey['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{32,})['\"]?", re.MULTILINE),
            ],
            "token": [
                # トークンパターン
                re.compile(r"(?i)token['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{20,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)access[_-]?token['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{20,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)auth[_-]?token['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{20,})['\"]?", re.MULTILINE),
            ],
            "password": [
                # パスワードパターン
                re.compile(r"(?i)password['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)passwd['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)pwd['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?", re.MULTILINE),
            ],
            "secret": [
                # シークレットパターン
                re.compile(r"(?i)secret['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?", re.MULTILINE),
                re.compile(r"(?i)client[_-]?secret['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?", re.MULTILINE),
            ],
            "github_token": [
                # GitHub特有のトークン
                re.compile(r"ghp_[a-zA-Z0-9]{36}", re.MULTILINE),
                re.compile(r"gho_[a-zA-Z0-9]{36}", re.MULTILINE),
                re.compile(r"ghu_[a-zA-Z0-9]{36}", re.MULTILINE),
                re.compile(r"ghs_[a-zA-Z0-9]{36}", re.MULTILINE),
                re.compile(r"ghr_[a-zA-Z0-9]{76}", re.MULTILINE),
            ],
            "aws_key": [
                # AWS認証情報
                re.compile(r"AKIA[0-9A-Z]{16}", re.MULTILINE),
                re.compile(
                    r"(?i)aws[_-]?access[_-]?key[_-]?id['\"]?\s*[:=]\s*['\"]?([A-Z0-9]{20})['\"]?",
                    re.MULTILINE,
                ),
                re.compile(
                    r"(?i)aws[_-]?secret[_-]?access[_-]?key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?",
                    re.MULTILINE,
                ),
            ],
            "private_key": [
                # 秘密鍵
                re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----", re.MULTILINE),
                re.compile(r"-----BEGIN RSA PRIVATE KEY-----", re.MULTILINE),
                re.compile(r"-----BEGIN EC PRIVATE KEY-----", re.MULTILINE),
                re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----", re.MULTILINE),
            ],
            "database_url": [
                # データベースURL
                re.compile(r"(?i)(mysql|postgresql|postgres|mongodb)://[^:\s]+:[^@\s]+@[^/\s]+/[^\s]*", re.MULTILINE),
                re.compile(r"(?i)database[_-]?url['\"]?\s*[:=]\s*['\"]?([^'\"\s]+://[^'\"\s]+)['\"]?", re.MULTILINE),
            ],
            "jwt": [
                # JWT トークン
                re.compile(r"eyJ[a-zA-Z0-9_\-]*\.eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*", re.MULTILINE),
            ],
        }

        # 環境変数名パターン（これらが設定ファイルに含まれていたら警告）
        self.env_var_patterns = [
            re.compile(r"(?i)[A-Z_]*API[_-]?KEY[A-Z_]*", re.MULTILINE),
            re.compile(r"(?i)[A-Z_]*TOKEN[A-Z_]*", re.MULTILINE),
            re.compile(r"(?i)[A-Z_]*SECRET[A-Z_]*", re.MULTILINE),
            re.compile(r"(?i)[A-Z_]*PASSWORD[A-Z_]*", re.MULTILINE),
            re.compile(r"(?i)[A-Z_]*PRIVATE[_-]?KEY[A-Z_]*", re.MULTILINE),
        ]

        # 除外パターン（偽陽性を避けるため）
        self.exclude_patterns = [
            re.compile(r"(?i)example", re.MULTILINE),
            re.compile(r"(?i)placeholder", re.MULTILINE),
            re.compile(r"(?i)your[_-]?api[_-]?key", re.MULTILINE),
            re.compile(r"(?i)insert[_-]?your", re.MULTILINE),
            re.compile(r"(?i)replace[_-]?with", re.MULTILINE),
            re.compile(r"(?i)xxx+", re.MULTILINE),
            re.compile(r"\*{3,}", re.MULTILINE),
        ]

    def detect_secrets(self, content: str) -> list[dict[str, Any]]:
        """コンテンツ内のシークレットを検出

        Args:
            content: 検査対象のコンテンツ

        Returns:
            検出されたシークレット情報のリスト

        """
        detected_secrets: list[dict[str, Any]] = []

        for secret_type, patterns in self.secret_patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(content)
                for match in matches:
                    # 除外パターンをチェック
                    if self._is_excluded(match.group(0)):
                        continue

                    # シークレット情報を記録
                    secret_info = {
                        "type": secret_type,
                        "value": match.group(1) if match.groups() else match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "line_number": content[: match.start()].count("\n") + 1,
                        "context": self._get_match_context(content, match),
                    }
                    detected_secrets.append(secret_info)

        return detected_secrets

    def _is_excluded(self, text: str) -> bool:
        """除外パターンに該当するかチェック

        Args:
            text: チェック対象のテキスト

        Returns:
            除外対象の場合True

        """
        for pattern in self.exclude_patterns:
            if pattern.search(text):
                return True
        return False

    def _get_match_context(self, content: str, match: re.Match[str], context_lines: int = 2) -> str:
        """マッチした箇所の前後のコンテキストを取得

        Args:
            content: 全体のコンテンツ
            match: マッチオブジェクト
            context_lines: 前後に取得する行数

        Returns:
            コンテキスト文字列

        """
        lines = content.splitlines()
        match_line = content[: match.start()].count("\n")

        start_line = max(0, match_line - context_lines)
        end_line = min(len(lines), match_line + context_lines + 1)

        context_lines_list: list[str] = []
        for i in range(start_line, end_line):
            prefix = ">" if i == match_line else " "
            context_lines_list.append(f"{prefix} {i + 1:3d}: {lines[i]}")

        return "\n".join(context_lines_list)

    def sanitize_content(self, content: str, replacement: str = "[REDACTED]") -> str:
        """コンテンツ内のシークレットをサニタイズ

        Args:
            content: サニタイズ対象のコンテンツ
            replacement: 置換文字列

        Returns:
            サニタイズされたコンテンツ

        """
        sanitized_content = content

        for secret_type, patterns in self.secret_patterns.items():
            for pattern in patterns:
                matches = list(pattern.finditer(sanitized_content))
                # 後ろから置換して位置がずれないようにする
                for match in reversed(matches):
                    if not self._is_excluded(match.group(0)):
                        # シークレット部分のみを置換
                        if match.groups():
                            # グループがある場合は最初のグループ（シークレット値）を置換
                            match.group(1)
                            sanitized_content = (
                                sanitized_content[: match.start(1)]
                                + f"{replacement}_{secret_type.upper()}"
                                + sanitized_content[match.end(1) :]
                            )
                        else:
                            # グループがない場合は全体を置換
                            sanitized_content = (
                                sanitized_content[: match.start()]
                                + f"{replacement}_{secret_type.upper()}"
                                + sanitized_content[match.end() :]
                            )

        return sanitized_content

    def validate_config_file(self, config_content: str, file_path: str) -> list[dict[str, Any]]:
        """設定ファイル内のシークレット記載をチェック

        Args:
            config_content: 設定ファイルの内容
            file_path: ファイルパス

        Returns:
            検出された問題のリスト

        Raises:
            SecurityError: 重大なセキュリティ問題が検出された場合

        """
        issues: list[dict[str, Any]] = []

        # シークレットの直接記載をチェック
        detected_secrets = self.detect_secrets(config_content)
        for secret in detected_secrets:
            issues.append(
                {
                    "type": "secret_in_config",
                    "severity": "critical",
                    "message": f"設定ファイルに{secret['type']}が直接記載されています",
                    "file_path": file_path,
                    "line_number": secret["line_number"],
                    "context": secret["context"],
                    "recommendation": "環境変数を使用してシークレットを管理してください",
                },
            )

        # 環境変数名の不適切な使用をチェック
        for pattern in self.env_var_patterns:
            matches = pattern.finditer(config_content)
            for match in matches:
                # 環境変数参照の形式（${VAR}や$VAR）でない場合は警告
                context = config_content[max(0, match.start() - 10) : match.end() + 10]
                if not re.search(r"[\$\{]", context):
                    line_number = config_content[: match.start()].count("\n") + 1
                    issues.append(
                        {
                            "type": "potential_secret_var",
                            "severity": "warning",
                            "message": f"シークレット関連の変数名が設定ファイルに含まれています: {match.group(0)}",
                            "file_path": file_path,
                            "line_number": line_number,
                            "context": self._get_match_context(config_content, match),
                            "recommendation": "環境変数参照の形式（${VAR_NAME}）を使用してください",
                        },
                    )

        # 重大な問題がある場合は例外を発生
        critical_issues = [issue for issue in issues if issue["severity"] == "critical"]
        if critical_issues:
            raise SecurityError(
                f"設定ファイル '{file_path}' に重大なセキュリティ問題が検出されました",
                "シークレットを環境変数に移動し、設定ファイルから削除してください",
            )

        return issues


class EnvironmentSecretManager:
    """環境変数ベースのシークレット管理クラス"""

    def __init__(self) -> None:
        """シークレット管理器を初期化"""
        self.required_secrets = {
            # AI プロバイダー用
            "OPENAI_API_KEY": "OpenAI API キー",
            "ANTHROPIC_API_KEY": "Anthropic API キー",
            "GOOGLE_API_KEY": "Google AI API キー",
            # GitHub用
            "GITHUB_TOKEN": "GitHub Personal Access Token",
            # その他
            "CI_HELPER_API_KEY": "ci-helper API キー（将来の機能用）",
        }

        self.optional_secrets = {
            "CI_HELPER_LOG_LEVEL": "ログレベル設定",
            "CI_HELPER_CACHE_DIR": "カスタムキャッシュディレクトリ",
            "CI_HELPER_MAX_LOG_SIZE": "最大ログサイズ",
        }

    def get_secret(self, key: str, required: bool = False) -> str | None:
        """環境変数からシークレットを安全に取得

        Args:
            key: 環境変数名
            required: 必須の場合True

        Returns:
            シークレット値（見つからない場合はNone）

        Raises:
            SecurityError: 必須のシークレットが見つからない場合

        """
        value = os.getenv(key)

        if required and not value:
            raise SecurityError(
                f"必須の環境変数 '{key}' が設定されていません",
                f"export {key}=your_secret_value を実行して設定してください",
            )

        return value

    def validate_secrets(self, required_keys: list[str] | None = None) -> SecretValidationResult:
        """必要なシークレットが設定されているかチェック

        Args:
            required_keys: チェック対象のキーリスト（Noneの場合は全ての必須キー）

        Returns:
            検証結果の辞書

        """
        if required_keys is None:
            required_keys = list(self.required_secrets.keys())

        validation_result: SecretValidationResult = {
            "valid": True,
            "missing_secrets": [],
            "available_secrets": [],
            "recommendations": [],
        }

        for key in required_keys:
            value = os.getenv(key)
            if value:
                validation_result["available_secrets"].append(
                    {"key": key, "description": self.required_secrets.get(key, "不明"), "configured": True},
                )
            else:
                validation_result["missing_secrets"].append(
                    {"key": key, "description": self.required_secrets.get(key, "不明"), "configured": False},
                )
                validation_result["valid"] = False

        # 推奨事項を生成
        if validation_result["missing_secrets"]:
            validation_result["recommendations"].extend(
                [
                    "環境変数を設定してください:",
                    *[f"  export {secret['key']}=your_value" for secret in validation_result["missing_secrets"]],
                    "",
                    "または .env ファイルを作成してください:",
                    *[f"  {secret['key']}=your_value" for secret in validation_result["missing_secrets"]],
                ],
            )

        return validation_result

    def prepare_act_environment(self, additional_vars: dict[str, str] | None = None) -> dict[str, str]:
        """act実行用の環境変数を準備

        Args:
            additional_vars: 追加の環境変数

        Returns:
            act実行用の環境変数辞書

        """
        env_vars: dict[str, str] = {}

        # 現在の環境変数をコピー（シークレット以外）
        for key, value in os.environ.items():
            # シークレット関連の環境変数は明示的に許可されたもののみ渡す
            if self._is_safe_env_var(key):
                env_vars[key] = value

        # 必要なシークレットを追加
        for key in self.required_secrets:
            secret_value = os.getenv(key)
            if secret_value is None:
                continue
            if secret_value == "":
                continue
            env_vars[key] = secret_value

        # オプションの設定を追加
        for key in self.optional_secrets:
            optional_value = os.getenv(key)
            if optional_value is None:
                continue
            if optional_value == "":
                continue
            env_vars[key] = optional_value

        # 追加の変数をマージ
        if additional_vars:
            env_vars.update(additional_vars)

        return env_vars

    def _is_safe_env_var(self, key: str) -> bool:
        """環境変数が安全に渡せるかチェック

        Args:
            key: 環境変数名

        Returns:
            安全な場合True

        """
        # 一般的なシステム環境変数は安全
        safe_prefixes = [
            "PATH",
            "HOME",
            "USER",
            "SHELL",
            "TERM",
            "LANG",
            "LC_",
            "TZ",
            "PWD",
            "OLDPWD",
            "TMPDIR",
            "TEMP",
            "TMP",
        ]

        # CI/CD関連の環境変数も安全
        ci_prefixes = ["CI", "GITHUB_", "RUNNER_", "ACTIONS_"]

        # 開発ツール関連
        dev_prefixes = ["NODE_", "NPM_", "YARN_", "PYTHON", "PIP_", "UV_"]

        for prefix in safe_prefixes + ci_prefixes + dev_prefixes:
            if key.startswith(prefix):
                return True

        # 明示的に許可されたシークレット
        if key in self.required_secrets or key in self.optional_secrets:
            return True

        # その他のシークレット関連は除外
        secret_indicators = ["KEY", "TOKEN", "SECRET", "PASSWORD", "PASS"]
        for indicator in secret_indicators:
            if indicator in key.upper():
                return False

        return True

    def get_secret_summary(self) -> SecretSummary:
        """現在のシークレット設定状況のサマリーを取得

        Returns:
            シークレット設定状況の辞書

        """
        summary: SecretSummary = {
            "required_secrets": {},
            "optional_secrets": {},
            "total_configured": 0,
            "total_missing": 0,
        }

        # 必須シークレットをチェック
        for key, description in self.required_secrets.items():
            is_configured = bool(os.getenv(key))
            summary["required_secrets"][key] = {
                "description": description,
                "configured": is_configured,
            }
            if is_configured:
                summary["total_configured"] += 1
            else:
                summary["total_missing"] += 1

        # オプションシークレットをチェック
        for key, description in self.optional_secrets.items():
            is_configured = bool(os.getenv(key))
            summary["optional_secrets"][key] = {
                "description": description,
                "configured": is_configured,
            }

        return summary


class SecurityValidator:
    """統合セキュリティ検証クラス"""

    def __init__(self) -> None:
        """セキュリティ検証器を初期化"""
        self.secret_detector = SecretDetector()
        self.secret_manager = EnvironmentSecretManager()

    def validate_log_content(self, log_content: str) -> dict[str, Any]:
        """ログコンテンツのセキュリティ検証

        Args:
            log_content: ログの内容

        Returns:
            検証結果の辞書

        """
        detected_secrets = self.secret_detector.detect_secrets(log_content)
        sanitized_content = self.secret_detector.sanitize_content(log_content)
        log_recommendations = self._get_log_security_recommendations(detected_secrets)

        return {
            "has_secrets": len(detected_secrets) > 0,
            "secret_count": len(detected_secrets),
            "detected_secrets": detected_secrets,
            "sanitized_content": sanitized_content,
            "recommendations": log_recommendations,
        }

    def validate_config_security(self, config_files: dict[str, str]) -> dict[str, Any]:
        """設定ファイルのセキュリティ検証

        Args:
            config_files: ファイルパス -> コンテンツのマッピング

        Returns:
            検証結果の辞書

        """
        all_issues = []
        file_results = {}

        for file_path, content in config_files.items():
            try:
                issues = self.secret_detector.validate_config_file(content, file_path)
                file_results[file_path] = {
                    "valid": not any(issue["severity"] == "critical" for issue in issues),
                    "issues": issues,
                }
                all_issues.extend(issues)
            except SecurityError as e:
                file_results[file_path] = {
                    "valid": False,
                    "error": str(e),
                    "issues": [],
                }

        overall_valid = all(result["valid"] for result in file_results.values())
        critical_issues = sum(1 for issue in all_issues if issue["severity"] == "critical")
        warning_issues = sum(1 for issue in all_issues if issue["severity"] == "warning")
        config_recommendations = self._get_config_security_recommendations(all_issues)

        return {
            "overall_valid": overall_valid,
            "total_issues": len(all_issues),
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "file_results": file_results,
            "recommendations": config_recommendations,
        }

    def _get_log_security_recommendations(self, detected_secrets: list[dict[str, Any]]) -> list[str]:
        """ログセキュリティの推奨事項を生成

        Args:
            detected_secrets: 検出されたシークレットのリスト

        Returns:
            推奨事項のリスト

        """
        if not detected_secrets:
            return ["ログにシークレットは検出されませんでした。"]

        recommendations = [
            "ログにシークレットが検出されました。以下の対策を実施してください:",
            "",
            "1. 環境変数の使用:",
            "   - シークレットは環境変数で管理してください",
            "   - GitHub Actions では secrets コンテキストを使用してください",
            "",
            "2. ログ出力の制御:",
            "   - デバッグ出力でシークレットを表示しないでください",
            "   - echo や print でシークレットを出力しないでください",
            "",
            "3. 既存のシークレットの対処:",
            "   - 検出されたシークレットは無効化してください",
            "   - 新しいシークレットを生成してください",
        ]

        # 検出されたシークレットタイプ別の推奨事項
        secret_types = {secret["type"] for secret in detected_secrets}
        if "github_token" in secret_types:
            recommendations.extend(
                [
                    "",
                    "GitHub Token の対処:",
                    "   - 該当するトークンを GitHub で無効化してください",
                    "   - 新しい Personal Access Token を生成してください",
                ],
            )

        if "aws_key" in secret_types:
            recommendations.extend(
                [
                    "",
                    "AWS 認証情報の対処:",
                    "   - AWS IAM でアクセスキーを無効化してください",
                    "   - 新しいアクセスキーを生成してください",
                ],
            )

        return recommendations

    def _get_config_security_recommendations(self, issues: list[dict[str, Any]]) -> list[str]:
        """設定セキュリティの推奨事項を生成

        Args:
            issues: 検出された問題のリスト

        Returns:
            推奨事項のリスト

        """
        if not issues:
            return ["設定ファイルにセキュリティ問題は検出されませんでした。"]

        recommendations = [
            "設定ファイルにセキュリティ問題が検出されました。以下の対策を実施してください:",
            "",
            "1. シークレットの環境変数化:",
            "   - 設定ファイルからシークレットを削除してください",
            "   - 環境変数または .env ファイルを使用してください",
            "",
            "2. 設定ファイルの例:",
            "   # 悪い例",
            "   api_key = 'sk-1234567890abcdef'",
            "",
            "   # 良い例",
            "   api_key = '${OPENAI_API_KEY}'",
            "",
            "3. .env ファイルの管理:",
            "   - .env ファイルを .gitignore に追加してください",
            "   - .env.example ファイルでテンプレートを提供してください",
        ]

        return recommendations
