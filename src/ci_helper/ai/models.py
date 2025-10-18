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
                }
                for fix in self.fix_suggestions
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

    def get_path(self, path_name: str) -> Path:
        """パスを取得"""
        if path_name == "cache_dir":
            return Path(self.cache_dir)
        return Path("")


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

    def __post_init__(self):
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
