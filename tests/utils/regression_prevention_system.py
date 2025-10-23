"""
回帰防止システム

このモジュールは、修正されたテストの回帰テスト作成、
継続的監視システムの設定、テスト失敗パターンの文書化を行います。
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TestFailurePattern:
    """テスト失敗パターン"""

    pattern_id: str
    pattern_name: str
    description: str
    error_signature: str
    fix_strategy: str
    examples: list[str]
    frequency: int = 0
    last_occurrence: str | None = None

    def __post_init__(self):
        if self.last_occurrence is None:
            self.last_occurrence = datetime.now().isoformat()


@dataclass
class RegressionTest:
    """回帰テスト定義"""

    test_id: str
    original_failure: str
    test_file: str
    test_name: str
    fix_type: str
    verification_logic: str
    expected_behavior: str
    created_at: str
    last_run: str | None = None
    status: str = "active"  # active, disabled, deprecated

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


@dataclass
class MonitoringAlert:
    """監視アラート"""

    alert_id: str
    test_name: str
    alert_type: str  # failure, regression, performance
    severity: str  # low, medium, high, critical
    message: str
    timestamp: str
    resolved: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class RegressionPreventionSystem:
    """回帰防止システム"""

    def __init__(self, data_dir: Path = Path("test_data")):
        """
        回帰防止システムを初期化

        Args:
            data_dir: データ保存ディレクトリ
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)

        # データベース初期化
        self.db_path = self.data_dir / "regression_prevention.db"
        self._init_database()

        # パターンデータベース
        self.patterns_file = self.data_dir / "failure_patterns.json"
        self.failure_patterns: dict[str, TestFailurePattern] = {}
        self._load_failure_patterns()

        # 回帰テストデータベース
        self.regression_tests: dict[str, RegressionTest] = {}
        self._load_regression_tests()

        # 監視設定
        self.monitoring_config = {
            "alert_threshold": 0.95,  # 95%以上の成功率を維持
            "performance_threshold": 1.2,  # 実行時間が20%以上増加でアラート
            "notification_channels": ["console", "file"],
            "monitoring_frequency": "every_commit",
        }

    def _init_database(self):
        """データベースを初期化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # テスト実行履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    execution_time REAL,
                    success BOOLEAN,
                    error_message TEXT,
                    timestamp TEXT,
                    commit_hash TEXT
                )
            """)

            # 回帰検出履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regression_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    regression_type TEXT,
                    detected_at TEXT,
                    resolved_at TEXT,
                    resolution_method TEXT
                )
            """)

            # アラート履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE,
                    test_name TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    timestamp TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            """)

            conn.commit()

    def _load_failure_patterns(self):
        """失敗パターンを読み込み"""
        if self.patterns_file.exists():
            with open(self.patterns_file, encoding="utf-8") as f:
                data = json.load(f)
                self.failure_patterns = {k: TestFailurePattern(**v) for k, v in data.items()}
        else:
            # デフォルトパターンを作成
            self._create_default_patterns()

    def _create_default_patterns(self):
        """デフォルトの失敗パターンを作成"""
        default_patterns = {
            "mock_mismatch": TestFailurePattern(
                pattern_id="mock_mismatch",
                pattern_name="モック不一致",
                description="モックの期待値と実際の呼び出しが一致しない",
                error_signature="AssertionError.*assert_called.*with",
                fix_strategy="実際の実装に合わせてモック期待値を更新",
                examples=["mock_subprocess_run.assert_called_once_with", "mock_api_call.assert_called_with"],
            ),
            "exception_init": TestFailurePattern(
                pattern_id="exception_init",
                pattern_name="例外初期化エラー",
                description="例外クラスの初期化時に必須引数が不足",
                error_signature="TypeError.*missing.*required.*argument",
                fix_strategy="必須引数を追加して例外を正しく初期化",
                examples=["TokenLimitError(5000, 4000, 'gpt-4o')", "RateLimitError(retry_after=60)"],
            ),
            "async_cleanup": TestFailurePattern(
                pattern_id="async_cleanup",
                pattern_name="非同期リソースクリーンアップ",
                description="非同期リソースが適切にクリーンアップされない",
                error_signature="RuntimeError.*Event loop is closed",
                fix_strategy="async withコンテキストマネージャーを使用",
                examples=["async with aiohttp.ClientSession() as session:", "await integration.cleanup()"],
            ),
            "attribute_error": TestFailurePattern(
                pattern_id="attribute_error",
                pattern_name="属性エラー",
                description="存在しない属性やメソッドへのアクセス",
                error_signature="AttributeError.*has no attribute",
                fix_strategy="正しい属性名やメソッド名を使用",
                examples=["AnalysisStatus.COMPLETED_WITH_FALLBACK", "datetime.strftime()"],
            ),
            "fixture_missing": TestFailurePattern(
                pattern_id="fixture_missing",
                pattern_name="フィクスチャ不足",
                description="テストに必要なフィクスチャやファイルが存在しない",
                error_signature="FileNotFoundError|fixture.*not found",
                fix_strategy="必要なフィクスチャファイルを作成",
                examples=[
                    "tests/fixtures/sample_logs/ai_analysis_test.log",
                    "tests/fixtures/sample_logs/complex_failure.log",
                ],
            ),
        }

        self.failure_patterns = default_patterns
        self._save_failure_patterns()

    def _save_failure_patterns(self):
        """失敗パターンを保存"""
        data = {k: asdict(v) for k, v in self.failure_patterns.items()}
        with open(self.patterns_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_regression_tests(self):
        """回帰テストを読み込み"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regression_tests'")

            if not cursor.fetchone():
                # 回帰テストテーブルを作成
                cursor.execute("""
                    CREATE TABLE regression_tests (
                        test_id TEXT PRIMARY KEY,
                        original_failure TEXT,
                        test_file TEXT,
                        test_name TEXT,
                        fix_type TEXT,
                        verification_logic TEXT,
                        expected_behavior TEXT,
                        created_at TEXT,
                        last_run TEXT,
                        status TEXT DEFAULT 'active'
                    )
                """)
                conn.commit()

            # 回帰テストを読み込み
            cursor.execute("SELECT * FROM regression_tests WHERE status = 'active'")
            for row in cursor.fetchall():
                test_id = row[0]
                self.regression_tests[test_id] = RegressionTest(
                    test_id=row[0],
                    original_failure=row[1],
                    test_file=row[2],
                    test_name=row[3],
                    fix_type=row[4],
                    verification_logic=row[5],
                    expected_behavior=row[6],
                    created_at=row[7],
                    last_run=row[8],
                    status=row[9],
                )

    def analyze_failure_pattern(self, error_message: str, test_name: str) -> str | None:
        """
        エラーメッセージから失敗パターンを分析

        Args:
            error_message: エラーメッセージ
            test_name: テスト名

        Returns:
            マッチしたパターンID（なければNone）
        """
        import re

        for pattern_id, pattern in self.failure_patterns.items():
            if re.search(pattern.error_signature, error_message, re.IGNORECASE):
                # パターンの頻度を更新
                pattern.frequency += 1
                pattern.last_occurrence = datetime.now().isoformat()
                self._save_failure_patterns()

                return pattern_id

        return None

    def create_regression_test(
        self, original_failure: str, test_file: str, test_name: str, fix_type: str
    ) -> RegressionTest:
        """
        回帰テストを作成

        Args:
            original_failure: 元の失敗内容
            test_file: テストファイル
            test_name: テスト名
            fix_type: 修正タイプ

        Returns:
            作成された回帰テスト
        """
        test_id = f"{test_file}::{test_name}::{fix_type}"

        # 検証ロジックを生成
        verification_logic = self._generate_verification_logic(fix_type)

        # 期待される動作を定義
        expected_behavior = self._define_expected_behavior(fix_type, original_failure)

        regression_test = RegressionTest(
            test_id=test_id,
            original_failure=original_failure,
            test_file=test_file,
            test_name=test_name,
            fix_type=fix_type,
            verification_logic=verification_logic,
            expected_behavior=expected_behavior,
            created_at=datetime.now().isoformat(),
        )

        # データベースに保存
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO regression_tests
                (test_id, original_failure, test_file, test_name, fix_type,
                 verification_logic, expected_behavior, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
                (
                    regression_test.test_id,
                    regression_test.original_failure,
                    regression_test.test_file,
                    regression_test.test_name,
                    regression_test.fix_type,
                    regression_test.verification_logic,
                    regression_test.expected_behavior,
                    regression_test.created_at,
                ),
            )
            conn.commit()

        self.regression_tests[test_id] = regression_test
        return regression_test

    def _generate_verification_logic(self, fix_type: str) -> str:
        """
        修正タイプに基づいて検証ロジックを生成

        Args:
            fix_type: 修正タイプ

        Returns:
            検証ロジック
        """
        verification_templates = {
            "mock_alignment": """
# モック呼び出しの検証
def verify_mock_alignment():
    # モックが正しいパラメータで呼び出されることを確認
    assert mock_object.call_count == expected_count
    assert mock_object.call_args == expected_args
            """,
            "exception_init": """
# 例外初期化の検証
def verify_exception_init():
    # 例外が正しい引数で初期化されることを確認
    try:
        raise ExceptionClass(required_arg1, required_arg2)
    except ExceptionClass as e:
        assert hasattr(e, 'required_attribute')
            """,
            "async_cleanup": """
# 非同期リソースクリーンアップの検証
async def verify_async_cleanup():
    # リソースが適切にクリーンアップされることを確認
    async with ResourceManager() as resource:
        # リソース使用
        pass
    # リソースが自動的にクリーンアップされることを確認
    assert resource.is_closed()
            """,
            "attribute_error": """
# 属性アクセスの検証
def verify_attribute_access():
    # 正しい属性にアクセスできることを確認
    obj = TargetClass()
    assert hasattr(obj, 'correct_attribute')
    assert callable(getattr(obj, 'correct_method'))
            """,
            "fixture_missing": """
# フィクスチャ存在の検証
def verify_fixture_exists():
    # 必要なフィクスチャファイルが存在することを確認
    fixture_path = Path('tests/fixtures/required_file.txt')
    assert fixture_path.exists()
    assert fixture_path.is_file()
            """,
        }

        return verification_templates.get(fix_type, "# カスタム検証ロジックが必要")

    def _define_expected_behavior(self, fix_type: str, original_failure: str) -> str:
        """
        期待される動作を定義

        Args:
            fix_type: 修正タイプ
            original_failure: 元の失敗内容

        Returns:
            期待される動作の説明
        """
        behavior_templates = {
            "mock_alignment": "モックオブジェクトが実際の実装と一致するパラメータで呼び出される",
            "exception_init": "例外クラスが必要な引数で正しく初期化される",
            "async_cleanup": "非同期リソースがコンテキストマネージャーで適切に管理される",
            "attribute_error": "正しい属性名とメソッド名でオブジェクトにアクセスできる",
            "fixture_missing": "テストに必要なフィクスチャファイルが存在し、アクセス可能である",
        }

        base_behavior = behavior_templates.get(fix_type, "修正後の動作が正常に機能する")
        return f"{base_behavior}\n\n元の失敗: {original_failure}"

    def record_test_execution(
        self,
        test_name: str,
        execution_time: float,
        success: bool,
        error_message: str | None = None,
        commit_hash: str | None = None,
    ):
        """
        テスト実行結果を記録

        Args:
            test_name: テスト名
            execution_time: 実行時間
            success: 成功したか
            error_message: エラーメッセージ
            commit_hash: コミットハッシュ
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO test_history
                (test_name, execution_time, success, error_message, timestamp, commit_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (test_name, execution_time, success, error_message, datetime.now().isoformat(), commit_hash),
            )
            conn.commit()

    def detect_regression(
        self, test_name: str, current_success_rate: float, current_performance: float
    ) -> list[MonitoringAlert]:
        """
        回帰を検出

        Args:
            test_name: テスト名
            current_success_rate: 現在の成功率
            current_performance: 現在のパフォーマンス

        Returns:
            検出されたアラートのリスト
        """
        alerts = []

        # 成功率の回帰チェック
        if current_success_rate < self.monitoring_config["alert_threshold"]:
            alert = MonitoringAlert(
                alert_id=f"success_rate_{test_name}_{int(time.time())}",
                test_name=test_name,
                alert_type="regression",
                severity="high",
                message=f"成功率が閾値を下回りました: {current_success_rate:.2%} < {self.monitoring_config['alert_threshold']:.2%}",
                timestamp=datetime.now().isoformat(),
            )
            alerts.append(alert)

        # パフォーマンスの回帰チェック
        baseline_performance = self._get_baseline_performance(test_name)
        if (
            baseline_performance
            and current_performance > baseline_performance * self.monitoring_config["performance_threshold"]
        ):
            alert = MonitoringAlert(
                alert_id=f"performance_{test_name}_{int(time.time())}",
                test_name=test_name,
                alert_type="performance",
                severity="medium",
                message=f"実行時間が基準値を超過: {current_performance:.2f}s > {baseline_performance * self.monitoring_config['performance_threshold']:.2f}s",
                timestamp=datetime.now().isoformat(),
            )
            alerts.append(alert)

        # アラートをデータベースに保存
        for alert in alerts:
            self._save_alert(alert)

        return alerts

    def _get_baseline_performance(self, test_name: str) -> float | None:
        """
        ベースラインパフォーマンスを取得

        Args:
            test_name: テスト名

        Returns:
            ベースライン実行時間（なければNone）
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT AVG(execution_time)
                FROM test_history
                WHERE test_name = ? AND success = 1
                AND timestamp > datetime('now', '-30 days')
            """,
                (test_name,),
            )

            result = cursor.fetchone()
            return result[0] if result and result[0] else None

    def _save_alert(self, alert: MonitoringAlert):
        """
        アラートをデータベースに保存

        Args:
            alert: 保存するアラート
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO alert_history
                (alert_id, test_name, alert_type, severity, message, timestamp, resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    alert.alert_id,
                    alert.test_name,
                    alert.alert_type,
                    alert.severity,
                    alert.message,
                    alert.timestamp,
                    alert.resolved,
                ),
            )
            conn.commit()

    def generate_failure_patterns_documentation(self) -> str:
        """
        テスト失敗パターンの文書化を生成

        Returns:
            失敗パターン文書
        """
        doc = """# テスト失敗パターン文書

このドキュメントは、プロジェクトで発生したテスト失敗パターンと
その修正方法を記録しています。

## 失敗パターン一覧

"""

        # パターンを頻度順でソート
        sorted_patterns = sorted(self.failure_patterns.values(), key=lambda p: p.frequency, reverse=True)

        for pattern in sorted_patterns:
            doc += f"""### {pattern.pattern_name} ({pattern.pattern_id})

**説明**: {pattern.description}

**エラーシグネチャ**: `{pattern.error_signature}`

**修正戦略**: {pattern.fix_strategy}

**発生頻度**: {pattern.frequency}回

**最終発生**: {pattern.last_occurrence}

**修正例**:
```python
{chr(10).join(pattern.examples)}
```

---

"""

        return doc

    def generate_monitoring_report(self) -> str:
        """
        監視レポートを生成

        Returns:
            監視レポート
        """
        # 最近のアラートを取得
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM alert_history
                WHERE timestamp > datetime('now', '-7 days')
                ORDER BY timestamp DESC
            """)
            recent_alerts = cursor.fetchall()

        report = f"""# テスト監視レポート

## 監視設定
- 成功率閾値: {self.monitoring_config["alert_threshold"]:.2%}
- パフォーマンス閾値: {self.monitoring_config["performance_threshold"]:.1f}x
- 監視頻度: {self.monitoring_config["monitoring_frequency"]}

## 最近のアラート（過去7日間）
"""

        if recent_alerts:
            for alert in recent_alerts:
                status = "✅ 解決済み" if alert[7] else "⚠️ 未解決"
                severity_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(alert[4], "⚪")

                report += f"""
### {severity_icon} {alert[3]} - {alert[2]} ({status})
- **テスト**: {alert[1]}
- **メッセージ**: {alert[5]}
- **発生時刻**: {alert[6]}
"""
        else:
            report += "\n✅ 過去7日間にアラートは発生していません。\n"

        # 回帰テスト統計
        active_regression_tests = len([t for t in self.regression_tests.values() if t.status == "active"])
        report += f"""
## 回帰テスト統計
- アクティブな回帰テスト: {active_regression_tests}件
- 総回帰テスト: {len(self.regression_tests)}件
"""

        return report

    def setup_continuous_monitoring(self, critical_tests: list[str]) -> dict[str, Any]:
        """
        継続的監視を設定

        Args:
            critical_tests: 重要なテストのリスト

        Returns:
            監視設定
        """
        monitoring_config = {
            "monitored_tests": critical_tests,
            "alert_threshold": self.monitoring_config["alert_threshold"],
            "performance_threshold": self.monitoring_config["performance_threshold"],
            "notification_channels": self.monitoring_config["notification_channels"],
            "monitoring_frequency": self.monitoring_config["monitoring_frequency"],
            "setup_timestamp": datetime.now().isoformat(),
        }

        # 設定を保存
        config_file = self.data_dir / "monitoring_config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(monitoring_config, f, indent=2, ensure_ascii=False)

        return monitoring_config


def setup_regression_prevention():
    """回帰防止システムのセットアップ"""
    system = RegressionPreventionSystem()

    # 重要なテストを定義
    critical_tests = [
        "tests/unit/commands/test_cache_command.py::test_list_cached_images_success",
        "tests/unit/ai/test_integration.py::test_async_resource_cleanup",
        "tests/unit/ai/test_exceptions.py::test_token_limit_error_initialization",
        "tests/integration/test_ai_e2e_comprehensive.py::test_comprehensive_ai_workflow",
        "tests/integration/test_ci_cd_integration.py::test_test_coverage_improvement_verification",
    ]

    # 継続的監視を設定
    system.setup_continuous_monitoring(critical_tests)

    # 失敗パターン文書を生成
    patterns_doc = system.generate_failure_patterns_documentation()
    patterns_file = system.data_dir / "failure_patterns_documentation.md"
    patterns_file.write_text(patterns_doc, encoding="utf-8")

    # 監視レポートを生成
    monitoring_report = system.generate_monitoring_report()
    report_file = system.data_dir / "monitoring_report.md"
    report_file.write_text(monitoring_report, encoding="utf-8")

    return system


if __name__ == "__main__":
    # スタンドアロン実行時のセットアップ
    system = setup_regression_prevention()
