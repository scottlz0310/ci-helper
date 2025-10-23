"""
修正検証フレームワーク

このモジュールは、テスト修正後の自動検証システムを提供します。
構文チェック、テスト実行、回帰テストの自動化を行い、
修正結果レポートを生成します。
"""

import ast
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class FixVerificationResult:
    """修正検証結果"""

    test_file: str
    test_name: str
    fix_type: str
    syntax_valid: bool
    test_passes: bool
    no_regression: bool
    execution_time: float
    error_message: str | None = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def overall_success(self) -> bool:
        """全体的な成功判定"""
        return self.syntax_valid and self.test_passes and self.no_regression


@dataclass
class FixSummary:
    """修正サマリー"""

    total_fixes: int
    successful_fixes: int
    failed_fixes: int
    syntax_errors: int
    test_failures: int
    regressions: int
    success_rate: float
    average_execution_time: float


class FixVerificationFramework:
    """修正検証フレームワーク"""

    def __init__(self, results_dir: Path = Path("test_results")):
        """
        修正検証フレームワークを初期化

        Args:
            results_dir: 結果保存ディレクトリ
        """
        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)
        self.verification_results: list[FixVerificationResult] = []

    def verify_syntax(self, file_path: Path) -> tuple[bool, str | None]:
        """
        Pythonファイルの構文チェック

        Args:
            file_path: チェック対象ファイルのパス

        Returns:
            (構文が正しいか, エラーメッセージ)
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                source_code = f.read()

            # ASTを使用して構文チェック
            ast.parse(source_code, filename=str(file_path))
            return True, None

        except SyntaxError as e:
            error_msg = f"構文エラー: {e.msg} (行 {e.lineno})"
            return False, error_msg
        except Exception as e:
            error_msg = f"ファイル読み込みエラー: {e!s}"
            return False, error_msg

    def run_specific_test(self, test_path: str, timeout: int = 60) -> tuple[bool, str | None, float]:
        """
        特定のテストを実行

        Args:
            test_path: テストパス（例: "tests/unit/test_example.py::TestClass::test_method"）
            timeout: タイムアウト（秒）

        Returns:
            (テストが成功したか, エラーメッセージ, 実行時間)
        """
        start_time = time.time()

        try:
            # pytestを使用してテストを実行
            result = subprocess.run(
                ["uv", "run", "pytest", test_path, "-v", "--tb=short"], capture_output=True, text=True, timeout=timeout
            )

            execution_time = time.time() - start_time
            success = result.returncode == 0
            error_message = result.stderr if not success else None

            return success, error_message, execution_time

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return False, f"テストがタイムアウトしました（{timeout}秒）", execution_time
        except Exception as e:
            execution_time = time.time() - start_time
            return False, str(e), execution_time

    def run_regression_tests(self, affected_area: str, timeout: int = 120) -> tuple[bool, str | None]:
        """
        回帰テストを実行

        Args:
            affected_area: 影響を受ける可能性のある領域（例: "ai", "commands", "core"）
            timeout: タイムアウト（秒）

        Returns:
            (回帰がないか, エラーメッセージ)
        """
        try:
            # 影響を受ける可能性のあるテストを実行
            test_patterns = self._get_regression_test_patterns(affected_area)

            for pattern in test_patterns:
                result = subprocess.run(
                    ["uv", "run", "pytest", pattern, "-x", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0:
                    return False, f"回帰テスト失敗: {pattern}\n{result.stderr}"

            return True, None

        except subprocess.TimeoutExpired:
            return False, f"回帰テストがタイムアウトしました（{timeout}秒）"
        except Exception as e:
            return False, str(e)

    def _get_regression_test_patterns(self, affected_area: str) -> list[str]:
        """
        影響を受ける領域に基づいて回帰テストパターンを取得

        Args:
            affected_area: 影響を受ける領域

        Returns:
            テストパターンのリスト
        """
        patterns = {
            "ai": ["tests/unit/ai/", "tests/integration/test_ai_integration.py"],
            "commands": ["tests/unit/commands/", "tests/integration/test_command_integration.py"],
            "core": ["tests/unit/test_*.py", "tests/integration/test_e2e_workflow.py"],
            "mock": ["tests/unit/", "tests/integration/"],
            "async": ["tests/unit/ai/", "tests/integration/test_ai_*.py"],
            "fixtures": ["tests/unit/", "tests/integration/"],
        }

        return patterns.get(affected_area, ["tests/unit/", "tests/integration/"])

    def verify_fix(
        self, test_file: str, test_name: str, fix_type: str, affected_area: str = "core"
    ) -> FixVerificationResult:
        """
        修正の包括的な検証

        Args:
            test_file: テストファイルパス
            test_name: テスト名
            fix_type: 修正タイプ
            affected_area: 影響を受ける領域

        Returns:
            検証結果
        """
        # 1. 構文チェック
        file_path = Path(test_file)
        syntax_valid, syntax_error = self.verify_syntax(file_path)

        # 2. テスト実行チェック
        if syntax_valid:
            test_passes, test_error, execution_time = self.run_specific_test(f"{test_file}::{test_name}")
        else:
            test_passes = False
            test_error = syntax_error
            execution_time = 0.0

        # 3. 回帰テストチェック
        if test_passes:
            no_regression, regression_error = self.run_regression_tests(affected_area)
        else:
            no_regression = False
            regression_error = "テスト実行失敗のため回帰テストをスキップ"

        # エラーメッセージの統合
        error_messages = []
        if syntax_error:
            error_messages.append(f"構文エラー: {syntax_error}")
        if test_error:
            error_messages.append(f"テストエラー: {test_error}")
        if regression_error:
            error_messages.append(f"回帰エラー: {regression_error}")

        combined_error = " | ".join(error_messages) if error_messages else None

        result = FixVerificationResult(
            test_file=test_file,
            test_name=test_name,
            fix_type=fix_type,
            syntax_valid=syntax_valid,
            test_passes=test_passes,
            no_regression=no_regression,
            execution_time=execution_time,
            error_message=combined_error,
        )

        self.verification_results.append(result)
        return result

    def verify_multiple_fixes(self, fixes: list[dict[str, str]]) -> list[FixVerificationResult]:
        """
        複数の修正を一括検証

        Args:
            fixes: 修正情報のリスト
                   各要素は {"test_file": str, "test_name": str, "fix_type": str, "affected_area": str}

        Returns:
            検証結果のリスト
        """
        results = []

        for fix in fixes:
            result = self.verify_fix(
                test_file=fix["test_file"],
                test_name=fix["test_name"],
                fix_type=fix["fix_type"],
                affected_area=fix.get("affected_area", "core"),
            )

            results.append(result)

            # 結果を即座に保存
            self.save_verification_results()

            # 成功/失敗の即座のフィードバック

            if not result.overall_success and result.error_message:
                pass

        return results

    def generate_fix_summary(self) -> FixSummary:
        """
        修正サマリーを生成

        Returns:
            修正サマリー
        """
        if not self.verification_results:
            return FixSummary(0, 0, 0, 0, 0, 0, 0.0, 0.0)

        total_fixes = len(self.verification_results)
        successful_fixes = sum(1 for r in self.verification_results if r.overall_success)
        failed_fixes = total_fixes - successful_fixes
        syntax_errors = sum(1 for r in self.verification_results if not r.syntax_valid)
        test_failures = sum(1 for r in self.verification_results if not r.test_passes)
        regressions = sum(1 for r in self.verification_results if not r.no_regression)
        success_rate = successful_fixes / total_fixes if total_fixes > 0 else 0.0

        execution_times = [r.execution_time for r in self.verification_results if r.execution_time > 0]
        average_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0

        return FixSummary(
            total_fixes=total_fixes,
            successful_fixes=successful_fixes,
            failed_fixes=failed_fixes,
            syntax_errors=syntax_errors,
            test_failures=test_failures,
            regressions=regressions,
            success_rate=success_rate,
            average_execution_time=average_execution_time,
        )

    def generate_verification_report(self) -> str:
        """
        修正検証レポートを生成

        Returns:
            レポート文字列
        """
        summary = self.generate_fix_summary()

        report = f"""# テスト修正検証レポート

## 概要
- 総修正数: {summary.total_fixes}
- 成功修正数: {summary.successful_fixes}
- 失敗修正数: {summary.failed_fixes}
- 成功率: {summary.success_rate:.2%}
- 平均実行時間: {summary.average_execution_time:.2f}秒

## 詳細統計
- 構文エラー: {summary.syntax_errors}件
- テスト実行失敗: {summary.test_failures}件
- 回帰検出: {summary.regressions}件

## 修正結果詳細
"""

        # 成功した修正
        successful_fixes = [r for r in self.verification_results if r.overall_success]
        if successful_fixes:
            report += "\n### ✅ 成功した修正\n"
            for result in successful_fixes:
                report += f"- {result.test_file}::{result.test_name} ({result.fix_type})\n"
                report += f"  実行時間: {result.execution_time:.2f}秒\n"

        # 失敗した修正
        failed_fixes = [r for r in self.verification_results if not r.overall_success]
        if failed_fixes:
            report += "\n### ❌ 失敗した修正\n"
            for result in failed_fixes:
                report += f"- {result.test_file}::{result.test_name} ({result.fix_type})\n"
                if result.error_message:
                    report += f"  エラー: {result.error_message}\n"

        # 修正タイプ別統計
        fix_types = {}
        for result in self.verification_results:
            fix_type = result.fix_type
            if fix_type not in fix_types:
                fix_types[fix_type] = {"total": 0, "success": 0}
            fix_types[fix_type]["total"] += 1
            if result.overall_success:
                fix_types[fix_type]["success"] += 1

        if fix_types:
            report += "\n### 修正タイプ別統計\n"
            for fix_type, stats in fix_types.items():
                success_rate = stats["success"] / stats["total"] * 100
                report += f"- {fix_type}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)\n"

        return report

    def save_verification_results(self, filename: str | None = None) -> Path:
        """
        検証結果をファイルに保存

        Args:
            filename: ファイル名（省略時は自動生成）

        Returns:
            保存されたファイルのパス
        """
        if filename is None:
            timestamp = int(time.time())
            filename = f"fix_verification_results_{timestamp}.json"

        filepath = self.results_dir / filename

        data = {
            "timestamp": time.time(),
            "summary": asdict(self.generate_fix_summary()),
            "results": [asdict(r) for r in self.verification_results],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath

    def load_verification_results(self, filepath: Path) -> None:
        """
        検証結果をファイルから読み込み

        Args:
            filepath: ファイルパス
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self.verification_results = [FixVerificationResult(**r) for r in data["results"]]

    def get_failed_fixes(self) -> list[FixVerificationResult]:
        """
        失敗した修正のリストを取得

        Returns:
            失敗した修正のリスト
        """
        return [r for r in self.verification_results if not r.overall_success]

    def get_regression_fixes(self) -> list[FixVerificationResult]:
        """
        回帰を引き起こした修正のリストを取得

        Returns:
            回帰を引き起こした修正のリスト
        """
        return [r for r in self.verification_results if not r.no_regression]


def run_comprehensive_fix_verification():
    """包括的な修正検証を実行"""
    framework = FixVerificationFramework()

    # 修正されたテストの例（実際の修正に合わせて更新）
    fixes_to_verify = [
        {
            "test_file": "tests/unit/commands/test_cache_command.py",
            "test_name": "test_list_cached_images_success",
            "fix_type": "mock_alignment",
            "affected_area": "commands",
        },
        {
            "test_file": "tests/unit/ai/test_exceptions.py",
            "test_name": "test_token_limit_error_initialization",
            "fix_type": "exception_init",
            "affected_area": "ai",
        },
        {
            "test_file": "tests/unit/ai/test_integration.py",
            "test_name": "test_async_resource_cleanup",
            "fix_type": "async_cleanup",
            "affected_area": "ai",
        },
    ]

    framework.verify_multiple_fixes(fixes_to_verify)

    # 結果を保存
    framework.save_verification_results("comprehensive_fix_verification.json")

    # レポートを生成
    report = framework.generate_verification_report()
    report_file = framework.results_dir / "fix_verification_report.md"
    report_file.write_text(report, encoding="utf-8")

    # サマリーを返す
    return framework.generate_fix_summary()


if __name__ == "__main__":
    # スタンドアロン実行時のテスト
    summary = run_comprehensive_fix_verification()
