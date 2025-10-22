"""
テスト品質向上マスタースクリプト

このスクリプトは、テスト修正の品質向上と回帰防止のための
全てのツールを統合して実行します。
"""

import sys
from pathlib import Path

# 必要なモジュールをインポート
try:
    from .fix_verification_framework import run_comprehensive_fix_verification
    from .regression_prevention_system import setup_regression_prevention
    from .test_quality_improver import improve_test_quality_batch
    from .comprehensive_verification import run_comprehensive_verification
except ImportError:
    # Fallback for direct execution
    from fix_verification_framework import run_comprehensive_fix_verification
    from regression_prevention_system import setup_regression_prevention
    from test_quality_improver import improve_test_quality_batch
    from comprehensive_verification import run_comprehensive_verification


def run_complete_quality_improvement():
    """完全なテスト品質向上プロセスを実行"""
    
    print("=" * 60)
    print("テスト品質向上と回帰防止システム")
    print("=" * 60)
    
    try:
        # ステップ1: 修正検証フレームワークの実行
        print("\n🔍 ステップ1: 修正検証フレームワークを実行中...")
        fix_summary = run_comprehensive_fix_verification()
        print(f"修正検証完了: {fix_summary.successful_fixes}/{fix_summary.total_fixes} 成功")
        
        # ステップ2: 回帰防止システムのセットアップ
        print("\n🛡️  ステップ2: 回帰防止システムをセットアップ中...")
        regression_system = setup_regression_prevention()
        print("回帰防止システムのセットアップ完了")
        
        # ステップ3: テストコード品質の改善
        print("\n📝 ステップ3: テストコード品質を改善中...")
        quality_reports = improve_test_quality_batch()
        average_score = sum(r.overall_score for r in quality_reports) / len(quality_reports) if quality_reports else 0
        print(f"品質改善完了: 平均品質スコア {average_score:.1f}/100")
        
        # ステップ4: 包括的検証と文書化
        print("\n📊 ステップ4: 包括的検証と文書化を実行中...")
        verification_system = run_comprehensive_verification()
        print("包括的検証と文書化完了")
        
        # 最終結果の表示
        print("\n" + "=" * 60)
        print("🎉 テスト品質向上プロセス完了")
        print("=" * 60)
        
        if verification_system.comprehensive_results:
            results = verification_system.comprehensive_results
            print(f"最終テスト成功率: {results.success_rate:.2%}")
            print(f"総テスト数: {results.total_tests}")
            print(f"成功: {results.passed_tests}, 失敗: {results.failed_tests}")
            
            if results.success_rate >= 1.0:
                print("✅ 目標成功率100%を達成しました！")
            else:
                print("⚠️  追加の修正が必要です。")
        
        print(f"\n📁 結果ファイル:")
        print(f"- 修正検証レポート: test_results/fix_verification_report.md")
        print(f"- 失敗パターン文書: test_results/regression_data/failure_patterns_documentation.md")
        print(f"- 品質レポート: test_results/test_quality_report.md")
        print(f"- 包括的検証レポート: test_results/comprehensive_verification_report.md")
        
        return True
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        print("詳細なエラー情報については、個別のツールを実行してください。")
        return False


def main():
    """メイン実行関数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "verify":
            print("修正検証フレームワークを実行中...")
            run_comprehensive_fix_verification()
            
        elif command == "regression":
            print("回帰防止システムをセットアップ中...")
            setup_regression_prevention()
            
        elif command == "quality":
            print("テストコード品質を改善中...")
            improve_test_quality_batch()
            
        elif command == "comprehensive":
            print("包括的検証を実行中...")
            run_comprehensive_verification()
            
        elif command == "all":
            print("全てのツールを実行中...")
            run_complete_quality_improvement()
            
        else:
            print(f"不明なコマンド: {command}")
            print_usage()
    else:
        # デフォルトは全実行
        run_complete_quality_improvement()


def print_usage():
    """使用方法を表示"""
    print("""
使用方法:
    python -m tests.utils.test_quality_master [command]

コマンド:
    verify        - 修正検証フレームワークのみ実行
    regression    - 回帰防止システムのセットアップのみ実行
    quality       - テストコード品質改善のみ実行
    comprehensive - 包括的検証のみ実行
    all           - 全てのツールを実行（デフォルト）

例:
    uv run python -m tests.utils.test_quality_master
    uv run python -m tests.utils.test_quality_master all
    uv run python -m tests.utils.test_quality_master verify
""")


if __name__ == "__main__":
    main()