"""
AI統合用のデータモデル

AI分析結果、設定、統計情報などを表現するデータクラスを定義します。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """エラーの重要度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Priority(Enum):
    """修正の優先度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AnalysisStatus(Enum):
    """分析ステータス"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"
    FALLBACK = "fallback"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class TokenUsage:
    """トークン使用量"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float

    @property
    def cost_per_token(self) -> float:
        """トークンあたりのコスト"""
        return self.estimated_cost / self.total_tokens if self.total_tokens > 0 else 0.0


@dataclass
class RootCause:
    """根本原因"""

    category: str  # エラーカテゴリ
    description: str  # 詳細説明
    file_path: str | None = None  # 関連ファイル
    line_number: int | None = None  # 行番号
    severity: Severity = Severity.MEDIUM  # 重要度
    confidence: float = 0.0  # 信頼度 (0.0-1.0)


@dataclass
class CodeChange:
    """コード変更"""

    file_path: str  # ファイルパス
    line_start: int  # 開始行
    line_end: int  # 終了行
    old_code: str  # 変更前のコード
    new_code: str  # 変更後のコード
    description: str  # 変更の説明


@dataclass
class FixSuggestion:
    """修正提案"""

    title: str  # 修正タイトル
    description: str  # 修正内容
    code_changes: list[CodeChange] = field(default_factory=list)  # コード変更
    priority: Priority = Priority.MEDIUM  # 優先度
    estimated_effort: str = "不明"  # 推定工数
    confidence: float = 0.0  # 信頼度 (0.0-1.0)
    references: list[str] = field(default_factory=list)  # 参考リンク

    # 詳細表示用の新しいフィールド
    background_reason: str = ""  # 修正提案の背景理由
    impact_assessment: str = ""  # 影響評価
    risk_level: str = "medium"  # リスクレベル (low/medium/high)
    estimated_time_minutes: int = 0  # 推定時間（分）
    safety_score: float = 0.5  # 安全性スコア (0.0-1.0)
    effectiveness_score: float = 0.5  # 効果スコア (0.0-1.0)
    prerequisites: list[str] = field(default_factory=list)  # 前提条件
    validation_steps: list[str] = field(default_factory=list)  # 検証ステップ


@dataclass
class AnalysisResult:
    """分析結果"""

    summary: str  # 分析サマリー
    root_causes: list[RootCause] = field(default_factory=list)  # 根本原因一覧
    fix_suggestions: list[FixSuggestion] = field(default_factory=list)  # 修正提案
    related_errors: list[str] = field(default_factory=list)  # 関連エラー
    confidence_score: float = 0.0  # 全体の信頼度スコア
    analysis_time: float = 0.0  # 分析時間（秒）
    tokens_used: TokenUsage | None = None  # 使用トークン数
    status: AnalysisStatus = AnalysisStatus.PENDING  # 分析ステータス
    timestamp: datetime = field(default_factory=datetime.now)  # 分析時刻
    provider: str = ""  # 使用したプロバイダー
    model: str = ""  # 使用したモデル
    cache_hit: bool = False  # キャッシュヒットかどうか
    fallback_reason: str | None = None  # フォールバック理由
    retry_available: bool = False  # リトライ可能かどうか
    retry_after: int | None = None  # リトライまでの秒数
    alternative_providers: list[str] = field(default_factory=list)  # 代替プロバイダー
    pattern_matches: list[PatternMatch] = field(default_factory=list)  # パターンマッチ結果
    # フォールバック機能用フィールド
    troubleshooting_steps: list[str] = field(default_factory=list)  # トラブルシューティングステップ
    manual_investigation_steps: list[str] = field(default_factory=list)  # 手動調査ステップ
    unknown_error_info: dict[str, Any] = field(default_factory=dict)  # 未知エラー情報
    pattern_match: PatternMatch | None = None  # 低信頼度パターンマッチ
    log_info: dict[str, Any] = field(default_factory=dict)  # ログ情報
    alternative_methods: list[str] = field(default_factory=list)  # 代替分析方法

    @property
    def has_high_confidence(self) -> bool:
        """高い信頼度を持つかどうか"""
        return self.confidence_score >= 0.8

    @property
    def critical_issues_count(self) -> int:
        """クリティカルな問題の数"""
        return sum(1 for cause in self.root_causes if cause.severity == Severity.CRITICAL)

    @property
    def urgent_fixes_count(self) -> int:
        """緊急修正の数"""
        return sum(1 for fix in self.fix_suggestions if fix.priority == Priority.URGENT)

    def model_dump(self) -> dict[str, Any]:
        """モデルを辞書形式でダンプ"""
        return {
            "summary": self.summary,
            "root_causes": [
                {
                    "category": cause.category,
                    "description": cause.description,
                    "file_path": cause.file_path,
                    "line_number": cause.line_number,
                    "severity": cause.severity.value,
                    "confidence": cause.confidence,
                }
                for cause in self.root_causes
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
                    "background_reason": fix.background_reason,
                    "impact_assessment": fix.impact_assessment,
                    "risk_level": fix.risk_level,
                    "estimated_time_minutes": fix.estimated_time_minutes,
                    "safety_score": fix.safety_score,
                    "effectiveness_score": fix.effectiveness_score,
                    "prerequisites": fix.prerequisites,
                    "validation_steps": fix.validation_steps,
                }
                for fix in self.fix_suggestions
            ],
            "pattern_matches": [
                {
                    "pattern_id": match.pattern.id,
                    "pattern_name": match.pattern.name,
                    "category": match.pattern.category,
                    "confidence": match.confidence,
                    "match_strength": match.match_strength,
                    "extracted_context": match.extracted_context,
                    "supporting_evidence": match.supporting_evidence,
                }
                for match in self.pattern_matches
            ],
            "related_errors": self.related_errors,
            "confidence_score": self.confidence_score,
            "analysis_time": self.analysis_time,
            "tokens_used": (
                {
                    "input_tokens": self.tokens_used.input_tokens,
                    "output_tokens": self.tokens_used.output_tokens,
                    "total_tokens": self.tokens_used.total_tokens,
                    "estimated_cost": self.tokens_used.estimated_cost,
                }
                if self.tokens_used
                else None
            ),
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "provider": self.provider,
            "model": self.model,
            "cache_hit": self.cache_hit,
            "fallback_reason": self.fallback_reason,
            "retry_available": self.retry_available,
            "retry_after": self.retry_after,
            "alternative_providers": self.alternative_providers,
        }


@dataclass
class ProviderConfig:
    """プロバイダー設定"""

    name: str  # プロバイダー名
    api_key: str  # APIキー
    base_url: str | None = None  # ベースURL
    default_model: str = ""  # デフォルトモデル
    available_models: list[str] = field(default_factory=list)  # 利用可能なモデル
    timeout_seconds: int = 30  # タイムアウト時間
    max_retries: int = 3  # 最大リトライ回数
    rate_limit_per_minute: int | None = None  # 分あたりのレート制限
    cost_per_input_token: float = 0.0  # 入力トークンあたりのコスト
    cost_per_output_token: float = 0.0  # 出力トークンあたりのコスト

    def __eq__(self, other: object) -> bool:
        """等価性比較"""
        if not isinstance(other, ProviderConfig):
            return False
        return (
            self.name == other.name
            and self.api_key == other.api_key
            and self.base_url == other.base_url
            and self.default_model == other.default_model
            and self.available_models == other.available_models
            and self.timeout_seconds == other.timeout_seconds
            and self.max_retries == other.max_retries
            and self.rate_limit_per_minute == other.rate_limit_per_minute
            and self.cost_per_input_token == other.cost_per_input_token
            and self.cost_per_output_token == other.cost_per_output_token
        )


@dataclass
class AIConfig:
    """AI統合設定"""

    default_provider: str  # デフォルトプロバイダー
    providers: dict[str, ProviderConfig] = field(default_factory=dict)  # プロバイダー設定
    cache_enabled: bool = True  # キャッシュ有効化
    cache_ttl_hours: int = 24  # キャッシュ有効期限（時間）
    cache_max_size_mb: int = 100  # キャッシュ最大サイズ（MB）
    cost_limits: dict[str, float] = field(default_factory=dict)  # コスト制限
    prompt_templates: dict[str, str] = field(default_factory=dict)  # プロンプトテンプレート
    interactive_timeout: int = 300  # 対話タイムアウト（秒）
    streaming_enabled: bool = True  # ストリーミング有効化
    security_checks_enabled: bool = True  # セキュリティチェック有効化
    cache_dir: str = ".ci-helper/cache"  # キャッシュディレクトリ

    # パターン認識設定
    pattern_recognition_enabled: bool = True  # パターン認識有効化
    pattern_confidence_threshold: float = 0.7  # パターン信頼度閾値
    pattern_database_path: str = "data/patterns"  # パターンデータベースパス
    custom_patterns_enabled: bool = True  # カスタムパターン有効化
    enabled_pattern_categories: list[str] = field(
        default_factory=lambda: ["permission", "network", "config", "dependency", "build", "test"]
    )  # 有効なパターンカテゴリ

    # 自動修正設定
    auto_fix_enabled: bool = False  # 自動修正有効化
    auto_fix_confidence_threshold: float = 0.8  # 自動修正信頼度閾値
    auto_fix_risk_tolerance: str = "low"  # リスク許容度 (low/medium/high)
    backup_retention_days: int = 30  # バックアップ保持日数
    backup_before_fix: bool = True  # 修正前バックアップ作成

    # 学習設定
    learning_enabled: bool = True  # 学習機能有効化
    feedback_collection_enabled: bool = True  # フィードバック収集有効化
    pattern_discovery_enabled: bool = True  # パターン発見有効化
    min_pattern_occurrences: int = 3  # パターン認識最小出現回数

    # 高度な設定
    max_pattern_matches: int = 10  # 最大パターンマッチ数
    pattern_cache_enabled: bool = True  # パターンキャッシュ有効化
    pattern_cache_ttl_hours: int = 6  # パターンキャッシュ有効期限（時間）
    auto_pattern_update_enabled: bool = True  # 自動パターン更新有効化
    fallback_analysis_enabled: bool = True  # フォールバック分析有効化

    # デバッグ設定
    debug_pattern_matching: bool = False  # パターンマッチングデバッグ
    log_pattern_performance: bool = False  # パターン性能ログ
    verbose_error_reporting: bool = False  # 詳細エラーレポート

    def __eq__(self, other: object) -> bool:
        """等価性比較"""
        if not isinstance(other, AIConfig):
            return False
        return (
            self.default_provider == other.default_provider
            and self.providers == other.providers
            and self.cache_enabled == other.cache_enabled
            and self.cache_ttl_hours == other.cache_ttl_hours
            and self.cache_max_size_mb == other.cache_max_size_mb
            and self.cost_limits == other.cost_limits
            and self.prompt_templates == other.prompt_templates
            and self.interactive_timeout == other.interactive_timeout
            and self.streaming_enabled == other.streaming_enabled
            and self.security_checks_enabled == other.security_checks_enabled
            and self.cache_dir == other.cache_dir
            and (self.pattern_recognition_enabled == other.pattern_recognition_enabled)
            and (self.pattern_confidence_threshold == other.pattern_confidence_threshold)
            and self.pattern_database_path == other.pattern_database_path
            and self.custom_patterns_enabled == other.custom_patterns_enabled
            and (self.enabled_pattern_categories == other.enabled_pattern_categories)
            and self.auto_fix_enabled == other.auto_fix_enabled
            and (self.auto_fix_confidence_threshold == other.auto_fix_confidence_threshold)
            and (self.auto_fix_risk_tolerance == other.auto_fix_risk_tolerance)
            and self.backup_retention_days == other.backup_retention_days
            and self.backup_before_fix == other.backup_before_fix
            and self.learning_enabled == other.learning_enabled
            and (self.feedback_collection_enabled == other.feedback_collection_enabled)
            and (self.pattern_discovery_enabled == other.pattern_discovery_enabled)
            and (self.min_pattern_occurrences == other.min_pattern_occurrences)
            and self.max_pattern_matches == other.max_pattern_matches
            and self.pattern_cache_enabled == other.pattern_cache_enabled
            and self.pattern_cache_ttl_hours == other.pattern_cache_ttl_hours
            and (self.auto_pattern_update_enabled == other.auto_pattern_update_enabled)
            and (self.fallback_analysis_enabled == other.fallback_analysis_enabled)
            and self.debug_pattern_matching == other.debug_pattern_matching
            and self.log_pattern_performance == other.log_pattern_performance
            and self.verbose_error_reporting == other.verbose_error_reporting
        )

    def get_path(self, path_name: str) -> Path:
        """パスを取得"""
        if path_name == "cache_dir":
            return Path(self.cache_dir)
        elif path_name == "pattern_database_path":
            return Path(self.pattern_database_path)
        return Path("")

    def validate_config(self) -> list[str]:
        """設定の検証を行い、エラーメッセージのリストを返す"""
        errors = []

        # 信頼度閾値の検証
        if not 0.0 <= self.pattern_confidence_threshold <= 1.0:
            errors.append(
                f"pattern_confidence_threshold must be between 0.0 and 1.0, got {self.pattern_confidence_threshold}"
            )

        if not 0.0 <= self.auto_fix_confidence_threshold <= 1.0:
            errors.append(
                f"auto_fix_confidence_threshold must be between 0.0 and 1.0, got {self.auto_fix_confidence_threshold}"
            )

        # リスク許容度の検証
        valid_risk_levels = ["low", "medium", "high"]
        if self.auto_fix_risk_tolerance not in valid_risk_levels:
            errors.append(
                f"auto_fix_risk_tolerance must be one of {valid_risk_levels}, got '{self.auto_fix_risk_tolerance}'"
            )

        # パターンカテゴリの検証
        valid_categories = ["permission", "network", "config", "dependency", "build", "test"]
        invalid_categories = [cat for cat in self.enabled_pattern_categories if cat not in valid_categories]
        if invalid_categories:
            errors.append(f"Invalid pattern categories: {invalid_categories}. Valid categories are: {valid_categories}")

        # 数値範囲の検証
        if self.backup_retention_days < 1:
            errors.append(f"backup_retention_days must be at least 1, got {self.backup_retention_days}")

        if self.min_pattern_occurrences < 1:
            errors.append(f"min_pattern_occurrences must be at least 1, got {self.min_pattern_occurrences}")

        if self.max_pattern_matches < 1:
            errors.append(f"max_pattern_matches must be at least 1, got {self.max_pattern_matches}")

        if self.pattern_cache_ttl_hours < 1:
            errors.append(f"pattern_cache_ttl_hours must be at least 1, got {self.pattern_cache_ttl_hours}")

        return errors

    def is_valid(self) -> bool:
        """設定が有効かどうかを判定"""
        return len(self.validate_config()) == 0

    def get_default_config(self) -> AIConfig:
        """デフォルト設定を取得"""
        return AIConfig(
            default_provider="openai",
            providers={},
            cache_enabled=True,
            cache_ttl_hours=24,
            cache_max_size_mb=100,
            cost_limits={},
            prompt_templates={},
            interactive_timeout=300,
            streaming_enabled=True,
            security_checks_enabled=True,
            cache_dir=".ci-helper/cache",
            pattern_recognition_enabled=True,
            pattern_confidence_threshold=0.7,
            pattern_database_path="data/patterns",
            custom_patterns_enabled=True,
            enabled_pattern_categories=["permission", "network", "config", "dependency", "build", "test"],
            auto_fix_enabled=False,
            auto_fix_confidence_threshold=0.8,
            auto_fix_risk_tolerance="low",
            backup_retention_days=30,
            backup_before_fix=True,
            learning_enabled=True,
            feedback_collection_enabled=True,
            pattern_discovery_enabled=True,
            min_pattern_occurrences=3,
            max_pattern_matches=10,
            pattern_cache_enabled=True,
            pattern_cache_ttl_hours=6,
            auto_pattern_update_enabled=True,
            fallback_analysis_enabled=True,
            debug_pattern_matching=False,
            log_pattern_performance=False,
            verbose_error_reporting=False,
        )

    def merge_with_defaults(self) -> AIConfig:
        """デフォルト値とマージした設定を返す（後方互換性のため）"""
        default_config = self.get_default_config()

        # 既存の値を保持し、未設定の場合のみデフォルト値を使用
        merged_config = AIConfig(
            default_provider=self.default_provider or default_config.default_provider,
            providers=self.providers or default_config.providers,
            cache_enabled=self.cache_enabled,
            cache_ttl_hours=self.cache_ttl_hours,
            cache_max_size_mb=self.cache_max_size_mb,
            cost_limits=self.cost_limits or default_config.cost_limits,
            prompt_templates=self.prompt_templates or default_config.prompt_templates,
            interactive_timeout=self.interactive_timeout,
            streaming_enabled=self.streaming_enabled,
            security_checks_enabled=self.security_checks_enabled,
            cache_dir=self.cache_dir or default_config.cache_dir,
            pattern_recognition_enabled=self.pattern_recognition_enabled,
            pattern_confidence_threshold=self.pattern_confidence_threshold,
            pattern_database_path=self.pattern_database_path or default_config.pattern_database_path,
            custom_patterns_enabled=self.custom_patterns_enabled,
            enabled_pattern_categories=self.enabled_pattern_categories or default_config.enabled_pattern_categories,
            auto_fix_enabled=self.auto_fix_enabled,
            auto_fix_confidence_threshold=self.auto_fix_confidence_threshold,
            auto_fix_risk_tolerance=self.auto_fix_risk_tolerance or default_config.auto_fix_risk_tolerance,
            backup_retention_days=self.backup_retention_days,
            backup_before_fix=self.backup_before_fix,
            learning_enabled=self.learning_enabled,
            feedback_collection_enabled=self.feedback_collection_enabled,
            pattern_discovery_enabled=self.pattern_discovery_enabled,
            min_pattern_occurrences=self.min_pattern_occurrences,
            max_pattern_matches=self.max_pattern_matches,
            pattern_cache_enabled=self.pattern_cache_enabled,
            pattern_cache_ttl_hours=self.pattern_cache_ttl_hours,
            auto_pattern_update_enabled=self.auto_pattern_update_enabled,
            fallback_analysis_enabled=self.fallback_analysis_enabled,
            debug_pattern_matching=self.debug_pattern_matching,
            log_pattern_performance=self.log_pattern_performance,
            verbose_error_reporting=self.verbose_error_reporting,
        )

        return merged_config


@dataclass
class UsageRecord:
    """使用記録"""

    timestamp: datetime
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    analysis_type: str  # "analysis", "fix_suggestion", "interactive"
    success: bool


class WarningLevel(Enum):
    """警告レベル"""

    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostEstimate:
    """コスト推定"""

    input_tokens: int
    estimated_cost: float
    provider: str
    model: str
    output_tokens: int = 0
    estimated_output_tokens: int = 0  # 推定出力トークン数（エイリアス）
    confidence: float = 1.0  # 推定の信頼度

    def __post_init__(self) -> None:
        """初期化後の処理"""
        # estimated_output_tokensが指定されている場合はoutput_tokensに設定
        if self.estimated_output_tokens > 0 and self.output_tokens == 0:
            self.output_tokens = self.estimated_output_tokens

    @property
    def total_tokens(self) -> int:
        """総トークン数"""
        return self.input_tokens + self.output_tokens


@dataclass
class UsageStats:
    """使用統計"""

    total_requests: int = 0
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    successful_requests: int = 0
    failed_requests: int = 0
    average_tokens_per_request: float = 0.0
    average_cost_per_request: float = 0.0
    provider_breakdown: dict[str, int] = field(default_factory=dict)
    model_breakdown: dict[str, int] = field(default_factory=dict)
    daily_usage: dict[str, float] = field(default_factory=dict)  # 日付 -> コスト

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


@dataclass
class LimitStatus:
    """制限ステータス"""

    provider: str
    current_usage: float
    limit: float
    remaining: float
    reset_time: datetime | None = None
    warning_threshold: float = 0.8  # 警告しきい値

    @property
    def is_near_limit(self) -> bool:
        """制限に近いかどうか"""
        return (self.current_usage / self.limit) >= self.warning_threshold

    @property
    def is_over_limit(self) -> bool:
        """制限を超過しているかどうか"""
        return self.current_usage >= self.limit

    @property
    def usage_percentage(self) -> float:
        """使用率（パーセント）"""
        return (self.current_usage / self.limit) * 100 if self.limit > 0 else 0.0

    @property
    def within_limits(self) -> bool:
        """制限内かどうか（後方互換性のため）"""
        return not self.is_over_limit

    @property
    def warning_level(self) -> WarningLevel:
        """警告レベル"""
        if self.is_over_limit:
            return WarningLevel.CRITICAL
        elif self.is_near_limit:
            return WarningLevel.WARNING
        else:
            return WarningLevel.NONE


@dataclass
class InteractiveSession:
    """対話セッション"""

    session_id: str
    start_time: datetime
    last_activity: datetime
    provider: str
    model: str
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    total_tokens_used: int = 0
    total_cost: float = 0.0
    is_active: bool = True

    def add_message(self, role: str, content: str, tokens: int = 0, cost: float = 0.0) -> None:
        """メッセージを追加"""
        self.conversation_history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(),
                "tokens": tokens,
                "cost": cost,
            }
        )
        self.total_tokens_used += tokens
        self.total_cost += cost
        self.last_activity = datetime.now()

    @property
    def duration_minutes(self) -> float:
        """セッション継続時間（分）"""
        return (self.last_activity - self.start_time).total_seconds() / 60

    @property
    def message_count(self) -> int:
        """メッセージ数"""
        return len(self.conversation_history)


@dataclass
class Pattern:
    """エラーパターン定義"""

    id: str  # パターンID
    name: str  # パターン名
    category: str  # カテゴリ（permission/network/config等）
    regex_patterns: list[str]  # 正規表現パターン
    keywords: list[str]  # キーワードリスト
    context_requirements: list[str]  # コンテキスト要件
    confidence_base: float  # 基本信頼度
    success_rate: float  # 過去の成功率
    created_at: datetime  # 作成日時
    updated_at: datetime  # 更新日時
    user_defined: bool = False  # ユーザー定義フラグ
    auto_generated: bool = False  # 自動生成フラグ
    source: str = "manual"  # パターンの作成元
    occurrence_count: int = 0  # 発生回数（学習用）


@dataclass
class PatternMatch:
    """パターンマッチ結果"""

    pattern: Pattern  # マッチしたパターン
    confidence: float  # 信頼度スコア
    match_positions: list[int]  # マッチ位置
    extracted_context: str  # 抽出されたコンテキスト
    match_strength: float  # マッチ強度
    supporting_evidence: list[str]  # 裏付け証拠


@dataclass
class FixStep:
    """修正ステップ"""

    type: str  # ステップタイプ（file_modification/command/config_change）
    description: str  # ステップ説明
    file_path: str | None = None  # 対象ファイルパス
    action: str | None = None  # アクション（append/replace/create）
    content: str | None = None  # 変更内容
    command: str | None = None  # 実行コマンド
    validation: str | None = None  # 検証方法


@dataclass
class FixTemplate:
    """修正テンプレート"""

    id: str  # テンプレートID
    name: str  # テンプレート名
    description: str  # 説明
    pattern_ids: list[str]  # 対応パターンID
    fix_steps: list[FixStep]  # 修正ステップ
    risk_level: str  # リスクレベル
    estimated_time: str  # 推定時間
    success_rate: float  # 成功率
    prerequisites: list[str] = field(default_factory=list)  # 前提条件
    validation_steps: list[str] = field(default_factory=list)  # 検証ステップ


@dataclass
class FixResult:
    """修正結果"""

    success: bool  # 成功フラグ
    applied_steps: list[FixStep]  # 適用されたステップ
    backup_info: BackupInfo | None = None  # バックアップ情報
    error_message: str | None = None  # エラーメッセージ
    verification_passed: bool = False  # 検証結果
    rollback_available: bool = False  # ロールバック可能フラグ


@dataclass
class BackupFile:
    """バックアップファイル"""

    original_path: str  # 元のファイルパス
    backup_path: str  # バックアップファイルパス
    checksum: str  # チェックサム


@dataclass
class BackupInfo:
    """バックアップ情報"""

    backup_id: str  # バックアップID
    created_at: datetime  # 作成日時
    files: list[BackupFile]  # バックアップファイル
    description: str  # 説明


@dataclass
class UserFeedback:
    """ユーザーフィードバック"""

    pattern_id: str  # パターンID
    fix_suggestion_id: str  # 修正提案ID
    rating: int  # 評価（1-5）
    success: bool  # 修正成功フラグ
    comments: str | None = None  # コメント
    timestamp: datetime = field(default_factory=datetime.now)  # 分析時刻


@dataclass
class LearningData:
    """学習データ"""

    id: str  # 学習データID
    error_log: str  # エラーログ
    pattern_id: str | None = None  # 関連パターンID
    user_feedback: UserFeedback | None = None  # ユーザーフィードバック
    success_rate: float = 0.0  # 成功率
    occurrence_count: int = 1  # 発生回数
    last_seen: datetime = field(default_factory=datetime.now)  # 最終確認日時
    created_at: datetime = field(default_factory=datetime.now)  # 作成日時
    updated_at: datetime = field(default_factory=datetime.now)  # 更新日時
    category: str = "unknown"  # カテゴリ
    confidence_adjustments: list[float] = field(default_factory=list)  # 信頼度調整履歴


@dataclass
class PatternImprovement:
    """パターン改善提案"""

    pattern_id: str  # 対象パターンID
    improvement_type: str  # 改善タイプ（regex_update/keyword_add/confidence_adjust）
    description: str  # 改善内容の説明
    suggested_changes: dict[str, Any]  # 提案される変更内容
    confidence: float  # 改善提案の信頼度
    supporting_data: list[str]  # 裏付けデータ
    created_at: datetime = field(default_factory=datetime.now)  # 作成日時


@dataclass
class BatchFixResult:
    """一括修正結果"""

    total_fixes: int  # 総修正数
    successful_fixes: int  # 成功した修正数
    failed_fixes: int  # 失敗した修正数
    fix_results: list[FixResult]  # 個別修正結果
    overall_success: bool  # 全体の成功フラグ
    execution_time: float  # 実行時間（秒）
    rollback_info: list[BackupInfo] = field(default_factory=list)  # ロールバック情報


@dataclass
class PatternAnalysisOptions:
    """パターン分析オプション"""

    confidence_threshold: float = 0.7  # 信頼度閾値
    enabled_categories: list[str] = field(default_factory=list)  # 有効カテゴリ
    max_patterns: int = 10  # 最大パターン数
    include_low_confidence: bool = False  # 低信頼度パターンを含める
    context_window: int = 5  # コンテキストウィンドウサイズ（行数）


@dataclass
class PatternAnalysisResult:
    """パターン分析結果"""

    matches: list[PatternMatch]  # パターンマッチ結果
    total_patterns_checked: int  # チェックしたパターン総数
    analysis_time: float  # 分析時間（秒）
    confidence_distribution: dict[str, int]  # 信頼度分布
    category_breakdown: dict[str, int]  # カテゴリ別内訳
    best_match: PatternMatch | None = None  # 最良マッチ


@dataclass
class PatternSuggestion:
    """パターン提案"""

    suggested_pattern: Pattern  # 提案パターン
    confidence: float  # 提案の信頼度
    supporting_logs: list[str]  # 裏付けログ
    similar_patterns: list[Pattern]  # 類似パターン
    creation_reason: str  # 作成理由


@dataclass
class AnalyzeOptions:
    """分析オプション"""

    log_file: str | None = None  # ログファイルパス
    provider: str | None = None  # プロバイダー指定
    model: str | None = None  # モデル指定
    custom_prompt: str | None = None  # カスタムプロンプト
    generate_fixes: bool = False  # 修正提案生成
    interactive_mode: bool = False  # 対話モード
    use_cache: bool = True  # キャッシュ使用
    streaming: bool = True  # ストリーミング
    output_format: str = "markdown"  # 出力形式
    max_tokens: int | None = None  # 最大トークン数
    temperature: float = 0.1  # 温度パラメータ
    timeout_seconds: int = 30  # タイムアウト
    force_ai_analysis: bool = False  # AI分析を強制実行（フォールバックを無視）
    pattern_analysis_options: PatternAnalysisOptions = field(
        default_factory=PatternAnalysisOptions
    )  # パターン分析オプション
