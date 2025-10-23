# パターン認識トラブルシューティングガイド

## 概要

このガイドでは、CI-Helperのパターン認識機能で発生する可能性のある問題と、その解決方法について説明します。

## 一般的な問題と解決方法

### 1. パターン認識が動作しない

#### 症状

- `ci-run analyze` を実行してもパターンマッチ結果が表示されない
- 「パターン認識エンジンが無効です」というメッセージが表示される

#### 原因と解決方法

**原因1: パターン認識が無効化されている**

```bash
# 設定を確認
ci-run config show | grep pattern_recognition

# パターン認識を有効化
ci-run config set ai.pattern_recognition.enabled true
```

**原因2: パターンデータベースが見つからない**

```bash
# パターンデータベースの存在確認
ls -la data/patterns/

# パターンデータベースを再初期化
ci-run init-patterns --force
```

**原因3: 設定ファイルの問題**

```bash
# 設定ファイルの構文チェック
ci-run config validate

# デフォルト設定にリセット
ci-run config reset --section ai.pattern_recognition
```

### 2. 信頼度が常に低い

#### 症状

- すべてのパターンマッチで信頼度が60%未満
- 「信頼度が閾値を下回ります」というメッセージが頻出

#### 原因と解決方法

**原因1: 信頼度閾値が高すぎる**

```bash
# 現在の閾値を確認
ci-run config get ai.pattern_recognition.confidence_threshold

# 閾値を下げる（例：0.6に設定）
ci-run config set ai.pattern_recognition.confidence_threshold 0.6
```

**原因2: ログの品質が低い**

```bash
# ログの詳細度を上げる
ci-run test --verbose

# より詳細なログを生成
ci-run test --log-level debug
```

**原因3: パターンデータベースが古い**

```bash
# パターンデータベースを更新
ci-run update-patterns

# 学習データを反映
ci-run apply-learning-data
```

### 3. 誤検出（偽陽性）が多い

#### 症状

- 関係のないエラーがマッチしてしまう
- 間違った修正提案が表示される

#### 原因と解決方法

**原因1: パターンが汎用的すぎる**

```bash
# 問題のあるパターンを特定
ci-run analyze --debug-patterns

# 特定のパターンを無効化
ci-run disable-pattern --pattern-id problematic_pattern_id
```

**原因2: コンテキスト要件が不十分**

```bash
# カスタムパターンでコンテキスト要件を追加
# data/patterns/custom/user_patterns.json を編集

# パターンを再読み込み
ci-run reload-patterns
```

**原因3: キーワードフィルタリングが不十分**

```bash
# より厳密なキーワードを設定
ci-run edit-pattern --pattern-id pattern_id --add-keyword "specific_keyword"
```

### 4. 見逃し（偽陰性）が多い

#### 症状

- 明らかなエラーパターンが検出されない
- 既知のエラーに対してパターンマッチしない

#### 原因と解決方法

**原因1: パターンが具体的すぎる**

```bash
# 未マッチのエラーを確認
ci-run analyze --show-unmatched-errors

# 新しいパターンを作成
ci-run create-pattern --from-error "error_text_here"
```

**原因2: 正規表現の問題**

```bash
# 正規表現をテスト
ci-run test-regex --pattern "your_regex" --text "error_text"

# パターンの正規表現を修正
ci-run edit-pattern --pattern-id pattern_id --regex "new_regex"
```

**原因3: カテゴリが無効化されている**

```bash
# 有効なカテゴリを確認
ci-run config get ai.pattern_recognition.enabled_categories

# カテゴリを有効化
ci-run enable-category --category missing_category
```

### 5. 修正提案が表示されない

#### 症状

- パターンは検出されるが修正提案が生成されない
- 「修正テンプレートが見つかりません」というエラー

#### 原因と解決方法

**原因1: 修正テンプレートが存在しない**

```bash
# テンプレートの存在確認
ci-run list-templates --pattern-id pattern_id

# テンプレートを作成
ci-run create-template --pattern-id pattern_id
```

**原因2: テンプレートファイルが破損**

```bash
# テンプレートファイルを検証
ci-run validate-templates

# テンプレートを再初期化
ci-run init-templates --force
```

**原因3: パターンとテンプレートの関連付けが不正**

```bash
# 関連付けを確認
ci-run show-pattern-template-mapping

# 関連付けを修正
ci-run link-pattern-template --pattern-id pattern_id --template-id template_id
```

## 自動修正の問題

### 1. 自動修正が実行されない

#### 症状

- `--fix` オプションを使用しても修正が適用されない
- 「自動修正は無効です」というメッセージ

#### 解決方法

```bash
# 自動修正設定を確認
ci-run config show | grep auto_fix

# 自動修正を有効化
ci-run config set ai.auto_fix.enabled true

# 信頼度閾値を確認・調整
ci-run config set ai.auto_fix.confidence_threshold 0.8
```

### 2. 修正が失敗する

#### 症状

- 修正処理中にエラーが発生
- ファイルが変更されない

#### 解決方法

```bash
# ファイル権限を確認
ls -la target_file

# バックアップディレクトリの権限確認
ls -la .ci-helper/backups/

# 手動で修正をテスト
ci-run test-fix --template-id template_id --dry-run
```

### 3. ロールバックが必要

#### 症状

- 修正により問題が悪化
- 元の状態に戻したい

#### 解決方法

```bash
# 利用可能なバックアップを確認
ci-run list-backups

# 特定のバックアップから復元
ci-run rollback --backup-id backup_id

# 最新のバックアップから復元
ci-run rollback --latest
```

## パフォーマンスの問題

### 1. 分析が遅い

#### 症状

- パターン認識に時間がかかりすぎる
- 大きなログファイルで処理が止まる

#### 解決方法

```bash
# ログファイルサイズを制限
ci-run analyze --max-log-size 10MB

# 特定のカテゴリのみ有効化
ci-run analyze --categories permission,network

# 並列処理を有効化
ci-run config set ai.pattern_recognition.parallel_processing true
```

### 2. メモリ使用量が多い

#### 症状

- システムメモリが不足
- プロセスが強制終了される

#### 解決方法

```bash
# メモリ使用量を制限
ci-run config set ai.pattern_recognition.max_memory_mb 512

# ログを分割して処理
ci-run analyze --chunk-size 1000

# 不要なパターンを無効化
ci-run disable-category --category unused_category
```

## 設定の問題

### 1. 設定ファイルが見つからない

#### 症状

- 「設定ファイルが見つかりません」エラー
- デフォルト設定が使用される

#### 解決方法

```bash
# 設定ファイルを作成
ci-run init --create-config

# 設定ファイルの場所を確認
ci-run config show-path

# 設定ファイルをコピー
cp ci-helper.toml.example ci-helper.toml
```

### 2. 設定値が反映されない

#### 症状

- 設定を変更しても動作が変わらない
- 古い設定値が使用される

#### 解決方法

```bash
# 設定キャッシュをクリア
ci-run config clear-cache

# 設定を再読み込み
ci-run config reload

# 設定の優先順位を確認
ci-run config show-sources
```

## ログとデバッグ

### デバッグモードの有効化

```bash
# 詳細なデバッグ情報を表示
ci-run analyze --debug

# 特定のコンポーネントのデバッグ
ci-run analyze --debug-component pattern_matcher

# ログレベルを設定
ci-run config set logging.level DEBUG
```

### ログファイルの確認

```bash
# ログファイルの場所を確認
ci-run logs --show-path

# 最新のログを表示
ci-run logs --tail 100

# エラーログのみ表示
ci-run logs --level ERROR
```

### 診断情報の収集

```bash
# システム診断を実行
ci-run doctor --pattern-recognition

# 設定診断
ci-run doctor --config

# パターンデータベース診断
ci-run doctor --patterns
```

## エラーメッセージ別対処法

### "Pattern database not found"

**原因**: パターンデータベースファイルが存在しない

**解決方法**:

```bash
# パターンデータベースを初期化
ci-run init-patterns

# 手動でパターンファイルを確認
ls -la data/patterns/
```

### "Invalid pattern format"

**原因**: パターンファイルの JSON 形式が不正

**解決方法**:

```bash
# JSON構文をチェック
ci-run validate-patterns --file data/patterns/custom/user_patterns.json

# JSONファイルを修正
# エラー箇所を特定して修正
```

### "Template not found for pattern"

**原因**: パターンに対応する修正テンプレートが存在しない

**解決方法**:

```bash
# 対応するテンプレートを作成
ci-run create-template --pattern-id pattern_id

# または既存テンプレートとリンク
ci-run link-pattern-template --pattern-id pattern_id --template-id existing_template_id
```

### "Confidence threshold not met"

**原因**: パターンマッチの信頼度が設定された閾値を下回る

**解決方法**:

```bash
# 閾値を下げる
ci-run config set ai.pattern_recognition.confidence_threshold 0.6

# またはパターンの信頼度を向上
ci-run improve-pattern --pattern-id pattern_id
```

### "Permission denied during fix application"

**原因**: 修正対象ファイルへの書き込み権限がない

**解決方法**:

```bash
# ファイル権限を確認
ls -la target_file

# 権限を変更
chmod u+w target_file

# または sudo で実行
sudo ci-run analyze --fix
```

### "Backup creation failed"

**原因**: バックアップディレクトリの作成または書き込みに失敗

**解決方法**:

```bash
# バックアップディレクトリを手動作成
mkdir -p .ci-helper/backups

# 権限を設定
chmod 755 .ci-helper/backups

# ディスク容量を確認
df -h
```

## 高度なトラブルシューティング

### 1. パターンマッチングアルゴリズムの調整

```bash
# マッチング感度を調整
ci-run config set ai.pattern_recognition.match_sensitivity 0.8

# 正規表現エンジンを変更
ci-run config set ai.pattern_recognition.regex_engine "re2"

# キーワード重み付けを調整
ci-run config set ai.pattern_recognition.keyword_weight 0.3
```

### 2. カスタムフィルターの作成

```bash
# ノイズフィルターを追加
ci-run add-noise-filter --pattern "irrelevant_pattern"

# コンテキストフィルターを設定
ci-run set-context-filter --require "build_context" --exclude "test_context"
```

### 3. パフォーマンス最適化

```bash
# パターンキャッシュを有効化
ci-run config set ai.pattern_recognition.enable_cache true

# インデックスを再構築
ci-run rebuild-pattern-index

# 不要なパターンを削除
ci-run cleanup-patterns --unused-only
```

## 予防策とベストプラクティス

### 1. 定期的なメンテナンス

```bash
# 週次：パターンデータベースの最適化
ci-run optimize-patterns

# 月次：学習データの統合
ci-run consolidate-learning-data

# 四半期：パターンの精度評価
ci-run evaluate-pattern-accuracy
```

### 2. バックアップ戦略

```bash
# パターンデータベースのバックアップ
ci-run backup-patterns --output patterns_backup.json

# 設定ファイルのバックアップ
cp ci-helper.toml ci-helper.toml.backup

# 学習データのバックアップ
ci-run backup-learning-data --output learning_backup.json
```

### 3. 監視とアラート

```bash
# パターン認識精度の監視
ci-run monitor-accuracy --threshold 0.8

# エラー率の監視
ci-run monitor-errors --max-rate 0.1

# パフォーマンス監視
ci-run monitor-performance --max-time 30s
```

## サポートとヘルプ

### 1. ヘルプコマンド

```bash
# 一般的なヘルプ
ci-run help pattern-recognition

# 特定のコマンドのヘルプ
ci-run analyze --help

# 設定オプションのヘルプ
ci-run config help ai.pattern_recognition
```

### 2. 診断レポートの生成

```bash
# 包括的な診断レポート
ci-run generate-diagnostic-report --output diagnostic_report.txt

# パターン認識専用レポート
ci-run generate-pattern-report --detailed
```

### 3. コミュニティサポート

- GitHub Issues: バグ報告と機能要求
- ディスカッション: 使用方法の質問
- Wiki: 詳細なドキュメント
- Slack/Discord: リアルタイムサポート

### 4. 問題報告時の情報

問題を報告する際は、以下の情報を含めてください：

```bash
# システム情報
ci-run --version
uname -a

# 設定情報（機密情報は除く）
ci-run config show --safe

# エラーログ
ci-run logs --level ERROR --last 24h

# 診断情報
ci-run doctor --all
```

## よくある質問（FAQ）

### Q: パターン認識の精度を向上させるには？

A: 以下の方法を試してください：

- フィードバック機能を積極的に使用
- カスタムパターンでプロジェクト固有のエラーに対応
- 学習機能を有効にして継続的改善
- 不要なパターンを無効化してノイズを削減

### Q: 自動修正が危険ではないか？

A: 以下の安全機能があります：

- 修正前の自動バックアップ
- リスクレベル別の承認フロー
- 修正後の検証チェック
- 失敗時の自動ロールバック

### Q: カスタムパターンの作成が難しい

A: 以下のツールを活用してください：

- パターン作成ウィザード: `ci-run create-pattern --wizard`
- 既存エラーからの自動生成: `ci-run generate-pattern --from-log`
- テンプレートの使用: `ci-run use-pattern-template`

### Q: 大量のログファイルで処理が遅い

A: パフォーマンス最適化オプションを使用：

- ログサイズ制限: `--max-log-size`
- 並列処理: `--parallel`
- カテゴリ限定: `--categories`
- チャンク処理: `--chunk-size`

## 関連ドキュメント

- [パターン認識機能使用ガイド](pattern-recognition-guide.md)
- [カスタムパターン作成ガイド](custom-pattern-guide.md)
- [AI設定リファレンス](ai-configuration.md)
- [CI-Helper使用方法](usage.md)
- [技術詳細](technical-details.md)
