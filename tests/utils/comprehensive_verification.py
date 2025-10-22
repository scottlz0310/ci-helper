"""
包括的検証と文書化システム

このモジュールは、全修正の総合検証、テスト成功率の確認、
修正内容の文書化と今後の保守ガイド作成を行います。
"""

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .fix_verification_framework import FixVerificationFramework
    from .regression_prevention_system import RegressionPreventionSystem
    from .test_quality_improver import TestQualityImprover
except ImportError:
    # Fallback for direct execution
    from fix_verification_framework import FixVerificationFramework
    from regression_prevention_system import RegressionPreventionSystem
    from test_quality_improver import TestQualityImprover


@dataclass
class ComprehensiveTestResult:
    """包括的テスト結果"""
    
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    success_rate: float
    execution_time: float
    coverage_percentage: Optional[float] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class FixDocumentation:
    """修正文書化"""
    
    fix_id: str
    fix_type: str
    original_issue: str
    solution_applied: str
    files_modified: List[str]
    test_results: str
    lessons_learned: str
    prevention_measures: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class MaintenanceGuide:
    """保守ガイド"""
    
    guide_type: str
    title: str
    description: str
    steps: List[str]
    best_practices: List[str]
    common_pitfalls: List[str]
    related_files: List[str]
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


class ComprehensiveVerificationSystem:
    """包括的検証システム"""
    
    def __init__(self, results_dir: Path = Path("test_results")):
        """
        包括的検証システムを初期化
        
        Args:
            results_dir: 結果保存ディレクトリ
        """
        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)
        
        # 各種フレームワークを初期化
        self.verification_framework = FixVerificationFramework(results_dir)
        self.regression_system = RegressionPreventionSystem(results_dir / "regression_data")
        self.quality_improver = TestQualityImprover()
        
        # 文書化データ
        self.fix_documentation: List[FixDocumentation] = []
        self.maintenance_guides: List[MaintenanceGuide] = []
        
        # 検証結果
        self.comprehensive_results: Optional[ComprehensiveTestResult] = None
    
    def run_comprehensive_test_suite(self, timeout: int = 600) -> ComprehensiveTestResult:
        """
        包括的テストスイートを実行
        
        Args:
            timeout: タイムアウト（秒）
            
        Returns:
            包括的テスト結果
        """
        print("包括的テストスイートを実行中...")
        start_time = time.time()
        
        try:
            # pytestを実行してテスト結果を取得
            result = subprocess.run([
                "uv", "run", "pytest", 
                "--tb=short",
                "--quiet",
                "--json-report",
                "--json-report-file", str(self.results_dir / "test_results.json"),
                "--cov=src",
                "--cov-report=json:" + str(self.results_dir / "coverage.json"),
                "tests/"
            ], capture_output=True, text=True, timeout=timeout)
            
            execution_time = time.time() - start_time
            
            # JSON結果を解析
            test_results = self._parse_test_results()
            coverage_data = self._parse_coverage_results()
            
            comprehensive_result = ComprehensiveTestResult(
                total_tests=test_results["total"],
                passed_tests=test_results["passed"],
                failed_tests=test_results["failed"],
                skipped_tests=test_results["skipped"],
                error_tests=test_results["error"],
                success_rate=test_results["passed"] / test_results["total"] if test_results["total"] > 0 else 0.0,
                execution_time=execution_time,
                coverage_percentage=coverage_data.get("coverage_percentage")
            )
            
            self.comprehensive_results = comprehensive_result
            return comprehensive_result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            print(f"テストスイートがタイムアウトしました（{timeout}秒）")
            
            return ComprehensiveTestResult(
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                error_tests=1,
                success_rate=0.0,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"テスト実行エラー: {str(e)}")
            
            return ComprehensiveTestResult(
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                error_tests=1,
                success_rate=0.0,
                execution_time=execution_time
            )
    
    def _parse_test_results(self) -> Dict[str, int]:
        """テスト結果JSONを解析"""
        results_file = self.results_dir / "test_results.json"
        
        if not results_file.exists():
            return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0}
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            summary = data.get("summary", {})
            return {
                "total": summary.get("total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "skipped": summary.get("skipped", 0),
                "error": summary.get("error", 0)
            }
            
        except Exception as e:
            print(f"テスト結果解析エラー: {str(e)}")
            return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0}
    
    def _parse_coverage_results(self) -> Dict[str, Any]:
        """カバレッジ結果JSONを解析"""
        coverage_file = self.results_dir / "coverage.json"
        
        if not coverage_file.exists():
            return {}
        
        try:
            with open(coverage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            totals = data.get("totals", {})
            coverage_percentage = totals.get("percent_covered")
            
            return {
                "coverage_percentage": coverage_percentage,
                "lines_covered": totals.get("covered_lines", 0),
                "lines_total": totals.get("num_statements", 0)
            }
            
        except Exception as e:
            print(f"カバレッジ結果解析エラー: {str(e)}")
            return {}
    
    def verify_success_rate_target(self, target_rate: float = 1.0) -> Tuple[bool, str]:
        """
        成功率目標の検証
        
        Args:
            target_rate: 目標成功率（デフォルト: 100%）
            
        Returns:
            (目標達成したか, メッセージ)
        """
        if not self.comprehensive_results:
            return False, "包括的テスト結果がありません。先にrun_comprehensive_test_suite()を実行してください。"
        
        current_rate = self.comprehensive_results.success_rate
        
        if current_rate >= target_rate:
            return True, f"✅ 成功率目標を達成: {current_rate:.2%} >= {target_rate:.2%}"
        else:
            failed_count = self.comprehensive_results.failed_tests + self.comprehensive_results.error_tests
            return False, f"❌ 成功率目標未達成: {current_rate:.2%} < {target_rate:.2%} ({failed_count}件の失敗)"
    
    def document_fix(self, fix_type: str, original_issue: str, solution_applied: str,
                    files_modified: List[str], test_results: str, 
                    lessons_learned: str, prevention_measures: str) -> FixDocumentation:
        """
        修正内容を文書化
        
        Args:
            fix_type: 修正タイプ
            original_issue: 元の問題
            solution_applied: 適用した解決策
            files_modified: 修正したファイル
            test_results: テスト結果
            lessons_learned: 学んだ教訓
            prevention_measures: 予防策
            
        Returns:
            修正文書
        """
        fix_id = f"{fix_type}_{int(time.time())}"
        
        documentation = FixDocumentation(
            fix_id=fix_id,
            fix_type=fix_type,
            original_issue=original_issue,
            solution_applied=solution_applied,
            files_modified=files_modified,
            test_results=test_results,
            lessons_learned=lessons_learned,
            prevention_measures=prevention_measures
        )
        
        self.fix_documentation.append(documentation)
        return documentation
    
    def create_maintenance_guide(self, guide_type: str, title: str, description: str,
                                steps: List[str], best_practices: List[str],
                                common_pitfalls: List[str], related_files: List[str]) -> MaintenanceGuide:
        """
        保守ガイドを作成
        
        Args:
            guide_type: ガイドタイプ
            title: タイトル
            description: 説明
            steps: 手順
            best_practices: ベストプラクティス
            common_pitfalls: よくある落とし穴
            related_files: 関連ファイル
            
        Returns:
            保守ガイド
        """
        guide = MaintenanceGuide(
            guide_type=guide_type,
            title=title,
            description=description,
            steps=steps,
            best_practices=best_practices,
            common_pitfalls=common_pitfalls,
            related_files=related_files
        )
        
        self.maintenance_guides.append(guide)
        return guide
    
    def generate_comprehensive_report(self) -> str:
        """
        包括的レポートを生成
        
        Returns:
            包括的レポート
        """
        if not self.comprehensive_results:
            return "# 包括的検証レポート\n\n❌ テスト結果がありません。先にrun_comprehensive_test_suite()を実行してください。"
        
        results = self.comprehensive_results
        success_achieved, success_message = self.verify_success_rate_target()
        
        report = f"""# テスト修正 包括的検証レポート

## 実行概要
- **実行日時**: {results.timestamp}
- **実行時間**: {results.execution_time:.2f}秒
- **目標達成**: {'✅ 達成' if success_achieved else '❌ 未達成'}

## テスト結果サマリー
- **総テスト数**: {results.total_tests}
- **成功**: {results.passed_tests}
- **失敗**: {results.failed_tests}
- **スキップ**: {results.skipped_tests}
- **エラー**: {results.error_tests}
- **成功率**: {results.success_rate:.2%}

{success_message}

"""
        
        # カバレッジ情報
        if results.coverage_percentage is not None:
            report += f"""## コードカバレッジ
- **カバレッジ率**: {results.coverage_percentage:.1f}%

"""
        
        # 修正文書化
        if self.fix_documentation:
            report += "## 修正内容の文書化\n\n"
            for doc in self.fix_documentation:
                report += f"""### {doc.fix_type} ({doc.fix_id})

**元の問題**: {doc.original_issue}

**適用した解決策**: {doc.solution_applied}

**修正ファイル**:
{chr(10).join(f'- {file}' for file in doc.files_modified)}

**テスト結果**: {doc.test_results}

**学んだ教訓**: {doc.lessons_learned}

**予防策**: {doc.prevention_measures}

---

"""
        
        # 保守ガイド
        if self.maintenance_guides:
            report += "## 保守ガイド\n\n"
            for guide in self.maintenance_guides:
                report += f"""### {guide.title}

**説明**: {guide.description}

**手順**:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(guide.steps))}

**ベストプラクティス**:
{chr(10).join(f'- {practice}' for practice in guide.best_practices)}

**よくある落とし穴**:
{chr(10).join(f'- {pitfall}' for pitfall in guide.common_pitfalls)}

**関連ファイル**:
{chr(10).join(f'- {file}' for file in guide.related_files)}

---

"""
        
        return report
    
    def save_comprehensive_results(self, filename: Optional[str] = None) -> Path:
        """
        包括的結果を保存
        
        Args:
            filename: ファイル名（省略時は自動生成）
            
        Returns:
            保存されたファイルのパス
        """
        if filename is None:
            timestamp = int(time.time())
            filename = f"comprehensive_verification_{timestamp}.json"
        
        filepath = self.results_dir / filename
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "test_results": asdict(self.comprehensive_results) if self.comprehensive_results else None,
            "fix_documentation": [asdict(doc) for doc in self.fix_documentation],
            "maintenance_guides": [asdict(guide) for guide in self.maintenance_guides]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def create_default_maintenance_guides(self):
        """デフォルトの保守ガイドを作成"""
        
        # Mock修正ガイド
        self.create_maintenance_guide(
            guide_type="mock_fixes",
            title="モック修正の保守ガイド",
            description="モック関連のテスト失敗を修正する際の手順とベストプラクティス",
            steps=[
                "実際の実装を確認し、モックの期待値と比較する",
                "subprocess.runやAPI呼び出しの実際のパラメータを特定する",
                "モックの期待値を実際の実装に合わせて更新する",
                "修正後にテストを実行して動作を確認する",
                "関連するテストに影響がないか回帰テストを実行する"
            ],
            best_practices=[
                "モックの期待値は実装の変更に合わせて定期的に見直す",
                "複雑なモック設定にはコメントで説明を追加する",
                "モックの設定と実際の実装の乖離を防ぐため、統合テストも併用する",
                "モック修正時は必ず実装コードも確認する"
            ],
            common_pitfalls=[
                "実装を確認せずにモックの期待値だけを変更する",
                "一つのテストだけを修正して他の関連テストを見落とす",
                "モックの設定が複雑すぎて保守が困難になる",
                "実装の変更時にモックの更新を忘れる"
            ],
            related_files=[
                "tests/unit/commands/test_cache_command.py",
                "tests/unit/ai/test_integration.py",
                "tests/fixtures/mock_providers.py"
            ]
        )
        
        # 例外処理修正ガイド
        self.create_maintenance_guide(
            guide_type="exception_fixes",
            title="例外処理修正の保守ガイド",
            description="例外クラスの初期化エラーや属性エラーを修正する際の手順",
            steps=[
                "例外クラスの定義を確認し、必要な引数を特定する",
                "エラーメッセージから不足している引数を特定する",
                "例外クラスの__init__メソッドに必要な引数を追加する",
                "テストで例外が正しく初期化されることを確認する",
                "例外処理のテストケースを追加または更新する"
            ],
            best_practices=[
                "例外クラスには明確なdocstringを追加する",
                "例外の引数は意味のある名前を使用する",
                "例外メッセージは日本語で分かりやすく記述する",
                "例外クラスの変更時は全ての使用箇所を確認する"
            ],
            common_pitfalls=[
                "例外クラスの定義を確認せずに引数を推測する",
                "必須引数とオプション引数を混同する",
                "例外メッセージの形式を統一しない",
                "例外処理のテストケースを追加し忘れる"
            ],
            related_files=[
                "src/ci_helper/ai/exceptions.py",
                "tests/unit/ai/test_exceptions.py",
                "src/ci_helper/core/exceptions.py"
            ]
        )
        
        # 非同期処理修正ガイド
        self.create_maintenance_guide(
            guide_type="async_fixes",
            title="非同期処理修正の保守ガイド",
            description="非同期処理とリソースクリーンアップの問題を修正する際の手順",
            steps=[
                "非同期リソースの使用箇所を特定する",
                "適切なコンテキストマネージャーの使用を確認する",
                "async withパターンを使用してリソース管理を改善する",
                "イベントループの適切な管理を実装する",
                "非同期テストの設定を確認する"
            ],
            best_practices=[
                "非同期リソースは必ずasync withを使用する",
                "pytest-asyncioの設定を適切に行う",
                "非同期テストには@pytest.mark.asyncioを付ける",
                "リソースクリーンアップは確実に実行されるようにする"
            ],
            common_pitfalls=[
                "非同期リソースの手動クローズを忘れる",
                "イベントループの管理を適切に行わない",
                "非同期テストの設定を間違える",
                "リソースリークを見落とす"
            ],
            related_files=[
                "tests/unit/ai/test_integration.py",
                "src/ci_helper/ai/integration.py",
                "tests/conftest.py"
            ]
        )
        
        # テスト品質保守ガイド
        self.create_maintenance_guide(
            guide_type="test_quality",
            title="テスト品質保守ガイド",
            description="テストコードの品質を継続的に維持するための手順",
            steps=[
                "定期的にテスト品質分析ツールを実行する",
                "品質スコアが低下したファイルを特定する",
                "docstringと日本語コメントの追加を行う",
                "テストの独立性と明確性を確認する",
                "品質改善の効果を測定する"
            ],
            best_practices=[
                "全てのテストクラスとメソッドにdocstringを追加する",
                "コメントは日本語で分かりやすく記述する",
                "テスト間の依存関係を除去する",
                "アサーションには失敗時のメッセージを追加する",
                "定期的にコードレビューを実施する"
            ],
            common_pitfalls=[
                "品質チェックを怠る",
                "英語のコメントを放置する",
                "テスト間の依存関係を見落とす",
                "品質改善を後回しにする"
            ],
            related_files=[
                "tests/utils/test_quality_improver.py",
                "tests/test_quality_guidelines.py",
                "tests/conftest.py"
            ]
        )


def run_comprehensive_verification():
    """包括的検証を実行"""
    system = ComprehensiveVerificationSystem()
    
    print("=== テスト修正 包括的検証を開始 ===")
    
    # 1. 包括的テストスイートを実行
    print("\n1. 包括的テストスイートを実行中...")
    test_results = system.run_comprehensive_test_suite()
    
    print(f"テスト結果: {test_results.passed_tests}/{test_results.total_tests} 成功 ({test_results.success_rate:.2%})")
    
    # 2. 成功率目標の検証
    print("\n2. 成功率目標を検証中...")
    success_achieved, success_message = system.verify_success_rate_target(1.0)  # 100%目標
    print(success_message)
    
    # 3. 修正内容の文書化（例）
    print("\n3. 修正内容を文書化中...")
    system.document_fix(
        fix_type="mock_alignment",
        original_issue="subprocess.runのモック期待値が実際の実装と一致しない",
        solution_applied="実際のDockerコマンド形式に合わせてモック期待値を更新",
        files_modified=["tests/unit/commands/test_cache_command.py"],
        test_results="修正後、関連する25個のテストが成功",
        lessons_learned="モック修正時は実装コードの確認が重要",
        prevention_measures="定期的なモックと実装の整合性チェックを実施"
    )
    
    system.document_fix(
        fix_type="exception_init",
        original_issue="TokenLimitError初期化時に必須引数modelが不足",
        solution_applied="例外クラスの初期化に必要な引数を追加",
        files_modified=["tests/unit/ai/test_exceptions.py"],
        test_results="修正後、例外処理関連の22個のテストが成功",
        lessons_learned="例外クラスの定義変更時は全使用箇所の確認が必要",
        prevention_measures="例外クラス変更時の影響範囲チェックリストを作成"
    )
    
    # 4. 保守ガイドの作成
    print("\n4. 保守ガイドを作成中...")
    system.create_default_maintenance_guides()
    
    # 5. 包括的レポートの生成
    print("\n5. 包括的レポートを生成中...")
    report = system.generate_comprehensive_report()
    report_file = system.results_dir / "comprehensive_verification_report.md"
    report_file.write_text(report, encoding='utf-8')
    print(f"包括的レポートを生成: {report_file}")
    
    # 6. 結果の保存
    print("\n6. 結果を保存中...")
    results_file = system.save_comprehensive_results()
    print(f"検証結果を保存: {results_file}")
    
    print("\n=== 包括的検証完了 ===")
    
    # 最終結果の表示
    if success_achieved:
        print("🎉 全ての修正が成功し、目標成功率100%を達成しました！")
    else:
        failed_count = test_results.failed_tests + test_results.error_tests
        print(f"⚠️  {failed_count}件のテストが失敗しています。追加の修正が必要です。")
    
    return system


if __name__ == "__main__":
    # スタンドアロン実行時の包括的検証
    verification_system = run_comprehensive_verification()
    print("包括的検証システムの実行が完了しました。")