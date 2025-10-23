# CI-Helper プロジェクト概要

## プロダクト定義

`act`を使用したローカルCI/CDパイプライン検証とAI統合機能を提供するCLIツール。GitHub Actionsワークフローをローカルで実行し、失敗を分析してAI駆動の修正提案を提供することで、CI/CDフィードバックループを分単位から秒単位に短縮する。

## コアバリュー

- **ローカルCI検証**: GitHubにプッシュせずにワークフローをローカル実行
- **インテリジェントなログ処理**: AI消費用の失敗情報抽出とフォーマット
- **自動エラー解析**: AI駆動によるCI失敗の分析と修正提案
- **開発者生産性**: 問題解決時間を30分から5分に短縮（目標）

## 対象ユーザー

- GitHub Actionsワークフローを使用する開発者
- CI/CD開発サイクルの最適化を求めるチーム
- CI設定の迅速な反復が必要なプロジェクト

## 主要機能

### 実装済み（✅）

- マルチコマンドCLIインターフェース（`ci-run`）
- 環境セットアップの検証（`doctor`コマンド）
- ローカルワークフロー実行（`test`コマンド）
- 包括的なログ記録と管理（`logs`コマンド）
- AI対応出力フォーマット（Markdown/JSON）
- ログ比較と差分解析
- 安全なシークレット管理
- AI統合アーキテクチャ（OpenAI、Anthropic、Local対応）
- コスト管理とキャッシュ機能
- 設定管理システム
- エラーハンドリング

### 改善が必要（🔧）

- 環境検証が厳しすぎる（全プロバイダーのAPIキーを要求）
- ローカルLLMプロバイダーの初期化エラー
- 実用的な分析結果の不足

### 計画中（📋）

- パターン認識エンジン（よくあるCI失敗パターンの自動検出）
- 具体的修正提案システム（テンプレートベース）
- 自動修正機能（バックアップ・ロールバック付き）
- 学習機能（新しいエラーパターンの自動学習）

## 理想的なワークフロー

```bash
# 1. ローカルでCI実行
ci-run test
# ❌ Job 'test' failed

# 2. AI分析
ci-run analyze
# 🤖 根本原因: setup-uvアクションで権限不足
# 🤖 修正提案: .actrcに--privilegedを追加
# 🤖 信頼度: 95% | 推定時間: 2分

# 3. 自動修正（オプション）
ci-run analyze --fix
# ✅ .actrcを更新しました
# 💡 ci-run testで再実行してください
```

## 技術アーキテクチャ

### コアコンポーネント

```
src/ci_helper/
├── cli.py                    # CLIエントリーポイント
├── commands/                 # コマンド実装
│   ├── init.py              # 初期化
│   ├── doctor.py            # 環境検証
│   ├── test.py              # ワークフロー実行
│   ├── analyze.py           # AI分析
│   ├── logs.py              # ログ管理
│   └── clean.py             # クリーンアップ
├── ai/                      # AI統合
│   ├── integration.py       # メイン統合ロジック
│   ├── providers/           # プロバイダー実装
│   ├── prompts.py           # プロンプト管理
│   ├── cache.py             # レスポンスキャッシュ
│   ├── cost_tracker.py      # コスト管理
│   └── interactive_session.py # 対話モード
└── utils/                   # ユーティリティ
    ├── config.py            # 設定管理
    ├── logger.py            # ログ記録
    └── security.py          # セキュリティ
```

### 計画中のコンポーネント

```
src/ci_helper/ai/
├── pattern_engine.py        # パターン認識エンジン
├── fix_templates.py         # 修正テンプレート
├── auto_fixer.py           # 自動修正機能
└── learning_engine.py      # 学習機能

data/
├── patterns.json           # エラーパターンDB
└── fix_templates.json      # 修正テンプレートDB
```

## 改善計画

### フェーズ1: パターン認識エンジン（2週間）

- 失敗パターンデータベースの構築
- ログ解析エンジンの改善
- パターンマッチング機能（正規表現ベース）
- 信頼度計算アルゴリズム

### フェーズ2: 具体的修正提案（2週間）

- 修正提案テンプレートシステム
- 設定ファイル解析機能
- 影響範囲評価機能
- リスクレベル判定

### フェーズ3: 自動修正機能（2週間）

- 設定ファイル自動更新機能
- バックアップ・ロールバック機能
- 修正結果の検証機能
- ユーザー承認システム

### フェーズ4: 学習機能（2週間）

- エラーパターン学習システム
- ユーザーフィードバック収集
- パターンデータベース更新機能
- 継続的改善システム

## データモデル

### FixSuggestion（修正提案）

```python
@dataclass
class FixSuggestion:
    title: str                    # 修正タイトル
    description: str              # 詳細説明
    steps: List[str]              # 修正手順
    files_to_modify: List[str]    # 変更対象ファイル
    risk_level: str               # low/medium/high
    time_estimate: str            # 推定時間
    confidence: float             # 信頼度（0.0-1.0）
    auto_applicable: bool         # 自動適用可能か
```

### Pattern（エラーパターン）

```python
@dataclass
class Pattern:
    name: str                     # パターン名
    regex: str                    # 検出用正規表現
    keywords: List[str]           # キーワード
    solution_template: str        # 修正テンプレート名
    confidence: float             # 信頼度
    category: str                 # カテゴリ（permission/network/config等）
```

## 設定拡張

```toml
[ai.analysis]
enable_pattern_recognition = true
enable_auto_fix = true
confidence_threshold = 0.8
backup_before_fix = true

[ai.patterns]
data_file = ".ci-helper/patterns.json"
learning_enabled = true
user_feedback_enabled = true
```

## 成功指標

### 定量的指標

- 問題解決時間: 30分 → 5分（83%短縮）
- 修正成功率: 手動60% → 自動95%
- 再発防止率: 90%削減（学習機能により）

### 定性的指標

- 開発者の満足度向上
- CI/CD失敗への恐怖心軽減
- 学習効果による継続的改善

## リスク管理

### 技術リスク

- **自動修正の誤動作**: バックアップ機能で対応
- **パターン認識の精度**: 信頼度閾値で制御
- **設定ファイル破損**: 検証機能で事前チェック

### 運用リスク

- **過度な自動化**: ユーザー確認オプション提供
- **学習データの品質**: フィードバック機能で改善

## 実装優先度

1. **高**: パターン認識エンジン（即効性）
2. **中**: 自動修正機能（利便性）
3. **低**: 学習機能（長期改善）

## 開発ガイドライン

- **プロジェクト言語**: 日本語
- **ドキュメント**: すべて日本語で作成
- **コードコメント**: 日本語で記述
- **設計書・仕様書**: 日本語で作成
- **コミュニケーション**: 日本語を基本とする

## 次のステップ

1. 環境検証の緩和（指定プロバイダーのみチェック）
2. パターン認識エンジンの詳細設計
3. パターンデータベースの初期データ収集
4. プロトタイプ実装開始
5. ユーザーテスト計画策定

---

**CI-Helperは、CI/CD失敗の「診断ツール」から「自動修復ツール」へと進化します。**
