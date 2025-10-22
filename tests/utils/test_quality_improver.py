"""
テストコード品質向上ツール

このモジュールは、修正されたテストコードの品質確保、
適切な日本語コメントの追加、テスト構造の改善と可読性向上を行います。
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class QualityIssue:
    """品質問題"""
    
    issue_type: str
    severity: str  # low, medium, high, critical
    line_number: int
    description: str
    suggestion: str
    example: Optional[str] = None


@dataclass
class QualityReport:
    """品質レポート"""
    
    file_path: str
    overall_score: float  # 0-100
    issues: List[QualityIssue]
    improvements: List[str]
    compliant_patterns: List[str]


class TestQualityImprover:
    """テストコード品質向上クラス"""
    
    def __init__(self):
        """品質向上ツールを初期化"""
        self.quality_rules = self._load_quality_rules()
        self.japanese_patterns = self._load_japanese_patterns()
        self.code_patterns = self._load_code_patterns()
    
    def _load_quality_rules(self) -> Dict[str, Any]:
        """品質ルールを読み込み"""
        return {
            "docstring_required": {
                "severity": "high",
                "description": "全てのテストクラスとメソッドにdocstringが必要",
                "pattern": r'(class Test\w+|def test_\w+).*?:(?!\s*""")',
                "suggestion": "日本語のdocstringを追加してください"
            },
            "japanese_comments": {
                "severity": "medium", 
                "description": "コメントは日本語で記述する必要がある",
                "pattern": r'#\s*[a-zA-Z]',
                "suggestion": "コメントを日本語で記述してください"
            },
            "test_independence": {
                "severity": "high",
                "description": "テストは他のテストに依存してはいけない",
                "pattern": r'(global\s+\w+|self\.\w+\s*=.*(?!setUp|tearDown))',
                "suggestion": "テスト間の依存関係を除去し、フィクスチャを使用してください"
            },
            "assertion_clarity": {
                "severity": "medium",
                "description": "アサーションは明確で理解しやすくする必要がある",
                "pattern": r'assert\s+[^,\n]*$',
                "suggestion": "アサーションにメッセージを追加してください"
            },
            "mock_proper_usage": {
                "severity": "medium",
                "description": "モックは適切に使用する必要がある",
                "pattern": r'Mock\(\)(?!\s*#)',
                "suggestion": "モックの用途を説明するコメントを追加してください"
            },
            "fixture_usage": {
                "severity": "low",
                "description": "共通のセットアップはフィクスチャを使用する",
                "pattern": r'def setUp\(self\)|def tearDown\(self\)',
                "suggestion": "pytestフィクスチャの使用を検討してください"
            }
        }
    
    def _load_japanese_patterns(self) -> Dict[str, str]:
        """日本語パターンを読み込み"""
        return {
            "test_class_docstring": '''"""
{class_name}のテストクラス

このクラスは{target_functionality}の動作を検証します。
各テストメソッドは独立して実行可能で、適切なフィクスチャを使用します。
"""''',
            "test_method_docstring": '''"""
{method_description}

{detailed_description}

Args:
    {args_description}

Expected:
    {expected_behavior}
"""''',
            "setup_comment": "# テスト用データのセットアップ",
            "execution_comment": "# テスト対象の実行",
            "verification_comment": "# 結果の検証",
            "cleanup_comment": "# リソースのクリーンアップ"
        }
    
    def _load_code_patterns(self) -> Dict[str, str]:
        """コードパターンを読み込み"""
        return {
            "proper_assertion": '''assert {condition}, "{failure_message}"''',
            "fixture_example": '''@pytest.fixture
def {fixture_name}():
    """
    {fixture_description}
    
    Returns:
        {return_description}
    """
    # フィクスチャの実装
    return {fixture_value}''',
            "mock_with_comment": '''# {mock_purpose}のモック
{mock_name} = Mock()
{mock_name}.{method_name}.return_value = {return_value}''',
            "test_structure": '''def test_{test_name}(self, {fixtures}):
    """
    {test_description}
    
    Args:
        {fixture_args}
    """
    # テスト用データのセットアップ
    {setup_code}
    
    # テスト対象の実行
    {execution_code}
    
    # 結果の検証
    {verification_code}'''
        }
    
    def analyze_test_file(self, file_path: Path) -> QualityReport:
        """
        テストファイルの品質を分析
        
        Args:
            file_path: 分析対象ファイル
            
        Returns:
            品質レポート
        """
        if not file_path.exists():
            return QualityReport(
                file_path=str(file_path),
                overall_score=0.0,
                issues=[QualityIssue(
                    issue_type="file_not_found",
                    severity="critical",
                    line_number=0,
                    description="ファイルが存在しません",
                    suggestion="ファイルパスを確認してください"
                )],
                improvements=[],
                compliant_patterns=[]
            )
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # ASTを使用してコード構造を分析
            tree = ast.parse(content)
            
            issues = []
            compliant_patterns = []
            
            # 各品質ルールをチェック
            for rule_name, rule in self.quality_rules.items():
                rule_issues = self._check_quality_rule(
                    rule_name, rule, content, lines, tree
                )
                issues.extend(rule_issues)
                
                if not rule_issues:
                    compliant_patterns.append(rule_name)
            
            # 全体スコアを計算
            overall_score = self._calculate_overall_score(issues, len(lines))
            
            # 改善提案を生成
            improvements = self._generate_improvements(issues, file_path)
            
            return QualityReport(
                file_path=str(file_path),
                overall_score=overall_score,
                issues=issues,
                improvements=improvements,
                compliant_patterns=compliant_patterns
            )
            
        except Exception as e:
            return QualityReport(
                file_path=str(file_path),
                overall_score=0.0,
                issues=[QualityIssue(
                    issue_type="analysis_error",
                    severity="critical",
                    line_number=0,
                    description=f"分析エラー: {str(e)}",
                    suggestion="ファイルの構文を確認してください"
                )],
                improvements=[],
                compliant_patterns=[]
            )
    
    def _check_quality_rule(self, rule_name: str, rule: Dict[str, Any], 
                           content: str, lines: List[str], tree: ast.AST) -> List[QualityIssue]:
        """
        品質ルールをチェック
        
        Args:
            rule_name: ルール名
            rule: ルール定義
            content: ファイル内容
            lines: 行のリスト
            tree: AST
            
        Returns:
            発見された問題のリスト
        """
        issues = []
        
        if rule_name == "docstring_required":
            issues.extend(self._check_docstring_requirement(tree, lines))
        elif rule_name == "japanese_comments":
            issues.extend(self._check_japanese_comments(lines))
        elif rule_name == "test_independence":
            issues.extend(self._check_test_independence(tree, lines))
        elif rule_name == "assertion_clarity":
            issues.extend(self._check_assertion_clarity(lines))
        elif rule_name == "mock_proper_usage":
            issues.extend(self._check_mock_usage(lines))
        elif rule_name == "fixture_usage":
            issues.extend(self._check_fixture_usage(tree, lines))
        
        return issues
    
    def _check_docstring_requirement(self, tree: ast.AST, lines: List[str]) -> List[QualityIssue]:
        """docstring要件をチェック"""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                # テストクラスまたはテストメソッドかチェック
                if (isinstance(node, ast.ClassDef) and node.name.startswith('Test')) or \
                   (isinstance(node, ast.FunctionDef) and node.name.startswith('test_')):
                    
                    # docstringの存在をチェック
                    has_docstring = (
                        node.body and 
                        isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)
                    )
                    
                    if not has_docstring:
                        node_type = "クラス" if isinstance(node, ast.ClassDef) else "メソッド"
                        issues.append(QualityIssue(
                            issue_type="missing_docstring",
                            severity="high",
                            line_number=node.lineno,
                            description=f"テスト{node_type} '{node.name}' にdocstringがありません",
                            suggestion=f"日本語のdocstringを追加してください",
                            example=self._generate_docstring_example(node)
                        ))
        
        return issues
    
    def _check_japanese_comments(self, lines: List[str]) -> List[QualityIssue]:
        """日本語コメントをチェック"""
        issues = []
        
        for i, line in enumerate(lines, 1):
            # コメント行を検出
            comment_match = re.search(r'#\s*(.+)', line)
            if comment_match:
                comment_text = comment_match.group(1).strip()
                
                # 英語のみのコメントかチェック（日本語文字が含まれていない）
                if comment_text and not any(ord(char) > 127 for char in comment_text):
                    # 特殊なコメント（TODO、FIXME等）は除外
                    if not re.match(r'^(TODO|FIXME|NOTE|XXX|HACK):', comment_text):
                        issues.append(QualityIssue(
                            issue_type="english_comment",
                            severity="medium",
                            line_number=i,
                            description=f"英語のコメント: '{comment_text}'",
                            suggestion="コメントを日本語で記述してください",
                            example=f"# {self._translate_to_japanese_example(comment_text)}"
                        ))
        
        return issues
    
    def _check_test_independence(self, tree: ast.AST, lines: List[str]) -> List[QualityIssue]:
        """テスト独立性をチェック"""
        issues = []
        
        # クラス変数やグローバル変数の使用をチェック
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and \
                       isinstance(target.value, ast.Name) and target.value.id == 'self':
                        # self.variable = value のパターン
                        if not target.attr.startswith('_'):  # プライベート変数は除外
                            issues.append(QualityIssue(
                                issue_type="test_dependency",
                                severity="high",
                                line_number=node.lineno,
                                description=f"インスタンス変数 'self.{target.attr}' の使用",
                                suggestion="フィクスチャを使用してテスト間の依存関係を除去してください",
                                example="@pytest.fixture\ndef test_data():\n    return {'key': 'value'}"
                            ))
        
        return issues
    
    def _check_assertion_clarity(self, lines: List[str]) -> List[QualityIssue]:
        """アサーションの明確性をチェック"""
        issues = []
        
        for i, line in enumerate(lines, 1):
            # assert文を検出
            assert_match = re.search(r'^\s*assert\s+(.+)$', line.strip())
            if assert_match:
                assertion = assert_match.group(1)
                
                # メッセージが含まれていないかチェック
                if ',' not in assertion or not re.search(r',\s*["\']', assertion):
                    issues.append(QualityIssue(
                        issue_type="unclear_assertion",
                        severity="medium",
                        line_number=i,
                        description=f"アサーションにメッセージがありません: {assertion}",
                        suggestion="失敗時のメッセージを追加してください",
                        example=f'assert {assertion}, "期待される動作の説明"'
                    ))
        
        return issues
    
    def _check_mock_usage(self, lines: List[str]) -> List[QualityIssue]:
        """モック使用をチェック"""
        issues = []
        
        for i, line in enumerate(lines, 1):
            # Mock()の使用を検出
            if re.search(r'Mock\(\)', line) and '#' not in line:
                issues.append(QualityIssue(
                    issue_type="undocumented_mock",
                    severity="medium",
                    line_number=i,
                    description="モックの用途が説明されていません",
                    suggestion="モックの目的を説明するコメントを追加してください",
                    example="# APIレスポンスのモック\nmock_response = Mock()"
                ))
        
        return issues
    
    def _check_fixture_usage(self, tree: ast.AST, lines: List[str]) -> List[QualityIssue]:
        """フィクスチャ使用をチェック"""
        issues = []
        
        # setUp/tearDownメソッドの使用をチェック
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ['setUp', 'tearDown']:
                issues.append(QualityIssue(
                    issue_type="old_style_setup",
                    severity="low",
                    line_number=node.lineno,
                    description=f"古いスタイルの{node.name}メソッドを使用",
                    suggestion="pytestフィクスチャの使用を検討してください",
                    example="@pytest.fixture\ndef setup_data():\n    return test_data"
                ))
        
        return issues
    
    def _generate_docstring_example(self, node: ast.AST) -> str:
        """docstringの例を生成"""
        if isinstance(node, ast.ClassDef):
            return f'''"""
{node.name}のテストクラス

このクラスは対象機能の動作を検証します。
各テストメソッドは独立して実行可能です。
"""'''
        else:
            return f'''"""
{node.name.replace('test_', '').replace('_', ' ')}のテスト

テストの詳細な説明をここに記述します。

Expected:
    期待される動作の説明
"""'''
    
    def _translate_to_japanese_example(self, english_text: str) -> str:
        """英語コメントの日本語例を生成"""
        translations = {
            "setup": "セットアップ",
            "test": "テスト",
            "check": "チェック",
            "verify": "検証",
            "create": "作成",
            "initialize": "初期化",
            "cleanup": "クリーンアップ",
            "mock": "モック",
            "fixture": "フィクスチャ"
        }
        
        japanese_text = english_text.lower()
        for eng, jpn in translations.items():
            japanese_text = japanese_text.replace(eng, jpn)
        
        return japanese_text
    
    def _calculate_overall_score(self, issues: List[QualityIssue], total_lines: int) -> float:
        """全体スコアを計算"""
        if not issues:
            return 100.0
        
        # 重要度による重み付け
        severity_weights = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 2
        }
        
        total_penalty = sum(severity_weights.get(issue.severity, 1) for issue in issues)
        
        # 行数に基づく正規化
        normalized_penalty = min(total_penalty / max(total_lines / 10, 1), 100)
        
        return max(0.0, 100.0 - normalized_penalty)
    
    def _generate_improvements(self, issues: List[QualityIssue], file_path: Path) -> List[str]:
        """改善提案を生成"""
        improvements = []
        
        # 問題の種類別に改善提案をグループ化
        issue_groups = {}
        for issue in issues:
            if issue.issue_type not in issue_groups:
                issue_groups[issue.issue_type] = []
            issue_groups[issue.issue_type].append(issue)
        
        # 各問題タイプに対する改善提案
        improvement_templates = {
            "missing_docstring": "全てのテストクラスとメソッドに日本語のdocstringを追加",
            "english_comment": "英語のコメントを日本語に変更",
            "test_dependency": "テスト間の依存関係を除去し、フィクスチャを使用",
            "unclear_assertion": "アサーションに失敗時のメッセージを追加",
            "undocumented_mock": "モックの用途を説明するコメントを追加",
            "old_style_setup": "setUp/tearDownをpytestフィクスチャに変更"
        }
        
        for issue_type, issue_list in issue_groups.items():
            if issue_type in improvement_templates:
                count = len(issue_list)
                improvements.append(f"{improvement_templates[issue_type]} ({count}箇所)")
        
        return improvements
    
    def improve_test_file(self, file_path: Path, auto_fix: bool = False) -> QualityReport:
        """
        テストファイルを改善
        
        Args:
            file_path: 改善対象ファイル
            auto_fix: 自動修正を行うか
            
        Returns:
            改善後の品質レポート
        """
        # まず現在の品質を分析
        initial_report = self.analyze_test_file(file_path)
        
        if auto_fix and initial_report.issues:
            # 自動修正を実行
            self._apply_auto_fixes(file_path, initial_report.issues)
            
            # 修正後の品質を再分析
            improved_report = self.analyze_test_file(file_path)
            return improved_report
        
        return initial_report
    
    def _apply_auto_fixes(self, file_path: Path, issues: List[QualityIssue]):
        """
        自動修正を適用
        
        Args:
            file_path: 修正対象ファイル
            issues: 修正する問題のリスト
        """
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # 行番号の降順でソートして、行番号のずれを防ぐ
        sorted_issues = sorted(issues, key=lambda x: x.line_number, reverse=True)
        
        for issue in sorted_issues:
            if issue.issue_type == "unclear_assertion" and issue.line_number <= len(lines):
                # アサーションメッセージを追加
                line = lines[issue.line_number - 1]
                if 'assert ' in line and ',' not in line:
                    # 簡単なメッセージを追加
                    assertion_part = line.split('assert ')[1].strip()
                    improved_line = line.replace(
                        assertion_part,
                        f'{assertion_part}, "期待される条件が満たされていません"'
                    )
                    lines[issue.line_number - 1] = improved_line
            
            elif issue.issue_type == "english_comment" and issue.line_number <= len(lines):
                # 英語コメントを日本語に変更（簡単な例）
                line = lines[issue.line_number - 1]
                if '# ' in line:
                    comment_part = line.split('# ')[1]
                    japanese_comment = self._translate_to_japanese_example(comment_part)
                    lines[issue.line_number - 1] = line.replace(comment_part, japanese_comment)
        
        # 修正されたコンテンツを保存
        improved_content = '\n'.join(lines)
        file_path.write_text(improved_content, encoding='utf-8')
    
    def generate_quality_report(self, reports: List[QualityReport]) -> str:
        """
        品質レポートを生成
        
        Args:
            reports: 品質レポートのリスト
            
        Returns:
            統合品質レポート
        """
        if not reports:
            return "# テストコード品質レポート\n\n分析対象のファイルがありません。"
        
        # 統計を計算
        total_files = len(reports)
        average_score = sum(r.overall_score for r in reports) / total_files
        total_issues = sum(len(r.issues) for r in reports)
        
        # 問題の種類別統計
        issue_type_counts = {}
        for report in reports:
            for issue in report.issues:
                issue_type_counts[issue.issue_type] = issue_type_counts.get(issue.issue_type, 0) + 1
        
        report_text = f"""# テストコード品質レポート

## 概要
- 分析ファイル数: {total_files}
- 平均品質スコア: {average_score:.1f}/100
- 総問題数: {total_issues}

## 品質スコア分布
"""
        
        # スコア分布
        score_ranges = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "0-59": 0}
        for report in reports:
            score = report.overall_score
            if score >= 90:
                score_ranges["90-100"] += 1
            elif score >= 80:
                score_ranges["80-89"] += 1
            elif score >= 70:
                score_ranges["70-79"] += 1
            elif score >= 60:
                score_ranges["60-69"] += 1
            else:
                score_ranges["0-59"] += 1
        
        for range_name, count in score_ranges.items():
            percentage = count / total_files * 100
            report_text += f"- {range_name}: {count}ファイル ({percentage:.1f}%)\n"
        
        # 問題タイプ別統計
        if issue_type_counts:
            report_text += "\n## 問題タイプ別統計\n"
            sorted_issues = sorted(issue_type_counts.items(), key=lambda x: x[1], reverse=True)
            for issue_type, count in sorted_issues:
                report_text += f"- {issue_type}: {count}件\n"
        
        # 改善が必要なファイル
        low_quality_files = [r for r in reports if r.overall_score < 70]
        if low_quality_files:
            report_text += "\n## 改善が必要なファイル\n"
            for report in sorted(low_quality_files, key=lambda x: x.overall_score):
                report_text += f"- {report.file_path} (スコア: {report.overall_score:.1f})\n"
                for improvement in report.improvements[:3]:  # 上位3つの改善提案
                    report_text += f"  - {improvement}\n"
        
        # 高品質なファイル
        high_quality_files = [r for r in reports if r.overall_score >= 90]
        if high_quality_files:
            report_text += "\n## 高品質なファイル\n"
            for report in sorted(high_quality_files, key=lambda x: x.overall_score, reverse=True):
                report_text += f"- {report.file_path} (スコア: {report.overall_score:.1f})\n"
        
        return report_text


def improve_test_quality_batch(test_directory: Path = Path("tests")) -> List[QualityReport]:
    """
    テストディレクトリの品質を一括改善
    
    Args:
        test_directory: テストディレクトリ
        
    Returns:
        品質レポートのリスト
    """
    improver = TestQualityImprover()
    reports = []
    
    # テストファイルを検索
    test_files = list(test_directory.rglob("test_*.py"))
    
    print(f"テスト品質改善を開始: {len(test_files)}ファイル")
    
    for test_file in test_files:
        print(f"分析中: {test_file}")
        
        # 品質分析
        report = improver.improve_test_file(test_file, auto_fix=False)
        reports.append(report)
        
        # 結果表示
        if report.overall_score >= 90:
            print(f"  ✅ 高品質 (スコア: {report.overall_score:.1f})")
        elif report.overall_score >= 70:
            print(f"  ⚠️  改善の余地あり (スコア: {report.overall_score:.1f})")
        else:
            print(f"  ❌ 要改善 (スコア: {report.overall_score:.1f})")
            for issue in report.issues[:3]:  # 上位3つの問題を表示
                print(f"    - {issue.description}")
    
    # 統合レポートを生成
    quality_report = improver.generate_quality_report(reports)
    report_file = Path("test_results") / "test_quality_report.md"
    report_file.parent.mkdir(exist_ok=True)
    report_file.write_text(quality_report, encoding='utf-8')
    print(f"品質レポートを生成: {report_file}")
    
    return reports


if __name__ == "__main__":
    # スタンドアロン実行時の品質改善
    reports = improve_test_quality_batch()
    print(f"品質改善完了: {len(reports)}ファイルを分析しました。")