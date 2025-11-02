# パターン認識機能使用ガイド

## 概要

CI-Helperのパターン認識機能は、CI失敗ログを自動分析し、既知のエラーパターンを特定して具体的な修正提案を提供します。このガイドでは、パターン認識機能の使用方法と設定について説明します。

## 基本的な使用方法

### 1. パターン認識を有効にした分析

```bash
# 基本的な分析（パターン認識有効）
ci-run analyze

# 詳細な分析結果を表示
ci-run analyze --verbose

# 特定のログファイルを分析
ci-run analyze --log-file path/to/logfile.txt
```

### 2. 分析結果の確認

パターン認識が成功すると、以下の情報が表示されます：

```
🔍 パターン認識結果:
  ✅ Docker権限エラー (信頼度: 95%)
     カテゴリ: permission
     マッチ理由: 正規表現 "permission denied.*docker" にマッチ

🛠️  修正提案:
  1. .actrcファイルに--privilegedオプションを追加
     リスクレベル: 低
     推定時間: 2分
     成功率: 95%
```

### 3. 自動修正の実行

```bash
# 修正提案を確認してから適用
ci-run analyze --fix

# 低リスクの修正を自動適用
ci-run analyze --fix --auto-approve-low-risk

# 修正のプレビューのみ表示
ci-run analyze --fix --preview-only
```

## 設定オプション

### パターン認識設定

設定ファイル（`ci-helper.toml`）でパターン認識の動作をカスタマイズできます：

```toml
[ai.pattern_recognition]
# パターン認識を有効にする
enabled = true

# 信頼度の閾値（0.0-1.0）
confidence_threshold = 0.7

# パターンデータベースのパス
database_path = "data/patterns"

# カスタムパターンを有効にする
custom_patterns_enabled = true

# 有効にするパターンカテゴリ
enabled_categories = ["permission", "network", "config", "build", "dependency", "test"]

# 無効にするパターンカテゴリ
disabled_categories = []
```

### 自動修正設定

```toml
[ai.auto_fix]
# 自動修正を有効にする
enabled = false

# 自動修正の信頼度閾値
confidence_threshold = 0.8

# リスク許容度（low/medium/high）
risk_tolerance = "low"

# バックアップ保持日数
backup_retention_days = 30

# 自動承認するリスクレベル
auto_approve_risk_levels = ["low"]
```

## パターンカテゴリ

### Permission（権限）

- Docker権限エラー
- ファイル権限エラー
- sudo権限エラー

### Network（ネットワーク）

- 接続タイムアウト
- DNS解決失敗
- SSL証明書エラー

### Config（設定）

- YAML構文エラー
- GitHub Actions設定エラー
- 環境変数エラー

### Build（ビルド）

- コンパイルエラー
- Make/CMakeエラー
- 言語固有のビルドエラー

### Dependency（依存関係）

- パッケージ不足エラー
- バージョン競合エラー
- インストールエラー

### Test（テスト）

- テスト失敗
- テストタイムアウト
- カバレッジエラー

## 信頼度レベルの理解

### 信頼度スコア

- **90-100%**: 非常に高い信頼度。自動修正推奨
- **80-89%**: 高い信頼度。ユーザー確認後の修正推奨
- **70-79%**: 中程度の信頼度。慎重な検討が必要
- **60-69%**: 低い信頼度。手動調査推奨
- **60%未満**: 非常に低い信頼度。パターン認識失敗の可能性

### 信頼度に影響する要因

1. **パターンマッチの強度**: 正規表現やキーワードの一致度
2. **過去の成功率**: そのパターンの修正成功履歴
3. **コンテキストの明確さ**: エラー周辺の情報の充実度
4. **複数パターンの競合**: 他のパターンとの重複度

## コマンドラインオプション

### 基本オプション

```bash
# パターン認識を無効にして分析
ci-run analyze --no-pattern-recognition

# 特定のカテゴリのみ有効
ci-run analyze --categories permission,network

# 信頼度閾値を指定
ci-run analyze --confidence-threshold 0.8

# 詳細なマッチ情報を表示
ci-run analyze --show-match-details
```

### 修正関連オプション

```bash
# 修正提案のみ表示（適用しない）
ci-run analyze --fix --dry-run

# 特定のリスクレベルまで自動適用
ci-run analyze --fix --max-risk medium

# バックアップを作成せずに修正
ci-run analyze --fix --no-backup

# 修正後に検証を実行
ci-run analyze --fix --verify
```

## 出力形式

### 標準出力

デフォルトでは、人間が読みやすい形式で結果を表示します。

### JSON出力

```bash
# JSON形式で出力
ci-run analyze --output json

# ファイルに保存
ci-run analyze --output json --output-file analysis_result.json
```

JSON出力例：

```json
{
  "analysis_timestamp": "2024-01-01T12:00:00Z",
  "pattern_matches": [
    {
      "pattern_id": "docker_permission_denied",
      "pattern_name": "Docker権限エラー",
      "category": "permission",
      "confidence": 0.95,
      "match_positions": [123, 456],
      "extracted_context": "permission denied while trying to connect to the Docker daemon socket",
      "supporting_evidence": ["docker", "permission denied", "daemon socket"]
    }
  ],
  "fix_suggestions": [
    {
      "id": "docker_permission_fix",
      "title": "Docker権限エラーの修正",
      "description": ".actrcファイルに--privilegedオプションを追加",
      "risk_level": "low",
      "confidence": 0.95,
      "estimated_time": "2分",
      "auto_applicable": true,
      "steps": [
        {
          "type": "file_modification",
          "description": ".actrcファイルに--privilegedを追加",
          "file_path": ".actrc",
          "action": "append",
          "content": "--privileged"
        }
      ]
    }
  ]
}
```

## 学習機能

### フィードバックの提供

```bash
# 修正結果のフィードバック
ci-run feedback --pattern-id docker_permission_denied --success true --rating 5

# コメント付きフィードバック
ci-run feedback --pattern-id docker_permission_denied --success false --rating 2 --comment "修正が効果なし"
```

### 学習データの確認

```bash
# 学習統計の表示
ci-run stats --learning

# パターン別成功率の表示
ci-run stats --patterns
```

## ベストプラクティス

### 1. 段階的な導入

1. まずパターン認識のみを有効にして結果を確認
2. 信頼度の高い修正から手動で適用
3. 成功率を確認してから自動修正を有効化

### 2. 設定の調整

- プロジェクトの特性に応じて信頼度閾値を調整
- 不要なカテゴリは無効化してノイズを削減
- カスタムパターンでプロジェクト固有のエラーに対応

### 3. 安全な運用

- 重要なファイルは事前にバックアップ
- 本番環境での使用前にテスト環境で検証
- 高リスクの修正は必ず手動確認

### 4. 継続的改善

- フィードバック機能を積極的に活用
- 学習データを定期的に確認
- 新しいエラーパターンを発見したらカスタムパターンとして追加

## 制限事項

### 現在の制限

- 日本語エラーメッセージの認識精度が限定的
- 複雑な依存関係エラーの解析が困難
- プロジェクト固有の設定ファイルの自動検出が不完全

### 今後の改善予定

- 多言語エラーメッセージ対応
- より高度なコンテキスト解析
- プロジェクト構造の自動学習

## サポート

問題が発生した場合は、以下の情報と共にお問い合わせください：

- CI-Helperのバージョン
- 使用したコマンドとオプション
- エラーログの内容
- 設定ファイルの内容（機密情報は除く）

詳細なトラブルシューティングについては、[トラブルシューティングガイド](troubleshooting-pattern-recognition.md)を参照してください。
