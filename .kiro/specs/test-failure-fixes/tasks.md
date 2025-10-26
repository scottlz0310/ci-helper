# テスト失敗修復 - 実装計画

## 概要

CI-Helperプロジェクトのpytestテストスイートで発生している119個の失敗と31個のエラーを体系的に修復するための実装計画です。主な問題は欠損クラス、設定互換性、モックインフラストラクチャ、テストフィクスチャの不足です。

## 実装タスク

### Phase 1: クラス依存関係解決（最優先）

- [x] 1. PerformanceOptimizerクラスのインポート修正
  - `src/ci_helper/ai/pattern_engine.py`でPerformanceOptimizerのインポートを追加
  - 既存の`src/ci_helper/utils/performance_optimizer.py`または`src/ci_helper/ai/performance_optimizer.py`から適切にインポート
  - _要件: 1.1_

- [x] 2. EnhancedAnalysisFormatterクラスのインポート修正
  - `src/ci_helper/commands/analyze.py`でEnhancedAnalysisFormatterのインポートを追加
  - 既存の`src/ci_helper/ui/enhanced_formatter.py`から適切にインポート
  - _要件: 1.3_

- [x] 3. AIConfigManagerクラスの作成または修正
  - `src/ci_helper/ai/integration.py`でAIConfigManagerクラスを作成または既存クラスをインポート
  - テストで期待されるAIConfigManagerクラスを提供
  - _要件: 1.4_

- [x] 4. FailureType.SYNTAX列挙値の追加
  - `src/ci_helper/core/models.py`のFailureTypeにSYNTAX値を追加
  - テストで使用されているFailureType.SYNTAXを利用可能にする
  - _要件: 1.5_

### Phase 2: 設定オブジェクト互換性改善

- [ ] 5. AIConfigクラスの辞書ライクアクセス実装
  - `src/ci_helper/ai/models.py`のAIConfigクラスに`get()`メソッドを追加
  - `__getitem__`、`__iter__`、`__contains__`メソッドを実装
  - 既存のテストコードとの互換性を確保
  - _要件: 2.1, 2.2_

- [ ] 6. AIConfig互換性アダプターの実装
  - AIConfigオブジェクトが辞書として使用できるようにアダプターパターンを実装
  - テストでのモック互換性を確保
  - _要件: 2.3, 2.4_

### Phase 3: モックインフラストラクチャ安定化

- [ ] 7. Rich Promptモックの修正
  - StopIterationエラーを引き起こすモック設定を修正
  - `tests/integration/test_menu_command_integration.py`等のPrompt.askモックを安定化
  - 適切なside_effectsとreturn_valueを設定
  - _要件: 3.1_

- [ ] 8. メソッド呼び出し期待値の修正
  - AssertionErrorを引き起こすモック呼び出し回数の不一致を修正
  - `assert_called_once()`等の期待値を実際の呼び出しパターンに合わせて調整
  - _要件: 3.2_

- [ ]* 9. 非同期モック管理の改善
  - 非同期コンテキストでのモック動作を安定化
  - AsyncMockの適切な設定と管理
  - _要件: 3.3_

- [ ]* 10. ファイル操作モックの一貫性確保
  - ファイルシステム操作のモックを一貫した動作に修正
  - テスト間でのファイル状態の分離を確保
  - _要件: 3.4_

### Phase 4: テストフィクスチャ整備

- [ ] 11. サンプルログファイルの作成
  - `tests/fixtures/sample_logs/`ディレクトリにテスト用ログファイルを作成
  - FileNotFoundErrorを解決するために必要なフィクスチャファイルを提供
  - _要件: 4.1_

- [ ] 12. 設定例データの提供
  - テストで期待される設定データファイルを作成
  - 有効な設定例をテストフィクスチャとして提供
  - _要件: 4.2_

- [ ]* 13. パターンテストデータの整備
  - パターン認識テスト用のデータファイルを作成
  - エラーパターンのテストケースを包括的に提供
  - _要件: 4.3_

- [ ]* 14. エラーシナリオフィクスチャの作成
  - 様々なエラーシナリオのテストデータを作成
  - エラーハンドリングテスト用のフィクスチャを提供
  - _要件: 4.4_

### Phase 5: テスト実行信頼性向上

- [ ] 15. フォーマッターテストの修正
  - `tests/unit/formatters/test_formatter_architecture.py`の期待値を実際の実装に合わせて修正
  - BaseLogFormatterのデフォルト動作を正しく反映
  - _要件: 5.1_

- [ ] 16. ログ選択テストの修正
  - `tests/unit/commands/test_analyze.py`のget_latest_log_file関数の期待値を修正
  - 実際の実装動作に合わせてテストを調整
  - _要件: 5.2_

- [ ] 17. JSON出力一貫性テストの修正
  - タイムスタンプの違いによるテスト失敗を修正
  - 動的な値（generated_at等）を除外した比較に変更
  - _要件: 5.3_

- [ ]* 18. エラーハンドリングテストの改善
  - エラーメッセージの期待値を実際の実装に合わせて修正
  - エラーハンドリングの一貫性を確保
  - _要件: 5.4_

### Phase 6: 統合テスト修復

- [ ] 19. AI統合テストの修復
  - AIConfigManagerの不在によるテスト失敗を修正
  - AI統合システムの初期化エラーを解決
  - _要件: 5.1, 5.2_

- [ ] 20. パターン認識テストの修復
  - PerformanceOptimizerの不在によるパターン認識テスト失敗を修正
  - パターンエンジンの初期化を正常化
  - _要件: 5.1, 5.3_

- [ ]* 21. メニューシステムテストの安定化
  - StopIterationエラーによるメニューテスト失敗を修正
  - ユーザー入力モックの適切な設定
  - _要件: 5.4_

## 実装順序と依存関係

1. **Phase 1（クラス依存関係解決）** を最初に完了 - 他のすべてのフェーズの前提条件
2. **Phase 2（設定互換性）** をPhase 1の後に実装 - AI統合テストの前提条件
3. **Phase 3（モック安定化）** を並行して実装 - テスト実行の安定性向上
4. **Phase 4（フィクスチャ整備）** を並行して実装 - テストデータの提供
5. **Phase 5（テスト信頼性）** をPhase 1-4の後に実装 - 個別テストの修正
6. **Phase 6（統合テスト）** を最後に実装 - 全体的な統合の確認

## 成功指標

- pytest実行時の失敗数を119個から0個に削減
- エラー数を31個から0個に削減
- 全テストの成功率を100%に到達
- テスト実行の安定性と再現性を確保

## 注意事項

- 各タスクは段階的に実装し、実装後に関連テストを実行して効果を確認
- 既存のコード構造を可能な限り保持し、最小限の変更で最大の効果を目指す
- オプションタスク（*マーク）は、コア機能の修復後に必要に応じて実装
