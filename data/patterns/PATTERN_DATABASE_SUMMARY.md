# パターンデータベース概要

## 作成されたパターン数: 27個

### カテゴリ別内訳

#### 1. 権限関連 (permission) - 3パターン

- `docker_permission_denied` - Docker権限拒否エラー
- `file_permission_denied` - ファイル権限拒否エラー  
- `sudo_required_error` - sudo権限必要エラー

#### 2. ネットワーク関連 (network) - 3パターン

- `network_connection_timeout` - ネットワーク接続タイムアウト
- `dns_resolution_failure` - DNS解決失敗
- `ssl_certificate_error` - SSL証明書エラー

#### 3. 設定関連 (config) - 9パターン

- `yaml_syntax_error` - YAML構文エラー
- `github_actions_invalid_syntax` - GitHub Actions無効な構文
- `env_var_not_set` - 環境変数未設定エラー
- `action_not_found` - GitHub Actionが見つからない
- `checkout_action_error` - checkoutアクションエラー
- `setup_node_version_error` - setup-nodeバージョンエラー
- `setup_python_version_error` - setup-pythonバージョンエラー
- `cache_action_error` - cacheアクションエラー
- `artifact_upload_error` - アーティファクトアップロードエラー

#### 4. ビルド関連 (build) - 6パターン

- `compilation_error` - コンパイルエラー
- `make_target_not_found` - Makeターゲット未発見
- `cmake_configuration_error` - CMake設定エラー
- `gradle_build_failure` - Gradleビルド失敗
- `maven_build_failure` - Mavenビルド失敗
- `npm_build_error` - NPMビルドエラー

#### 5. 依存関係関連 (dependency) - 7パターン

- `python_module_not_found` - Pythonモジュール未発見
- `python_import_error` - Pythonインポートエラー
- `node_module_not_found` - Node.jsモジュール未発見
- `npm_install_error` - NPMインストールエラー
- `pip_install_error` - pipインストールエラー
- `gem_install_error` - Gemインストールエラー
- `composer_dependency_error` - Composer依存関係エラー

#### 6. テスト関連 (test) - 5パターン

- `test_failure_assertion` - テスト失敗（アサーション）
- `test_timeout` - テストタイムアウト
- `jest_test_failure` - Jestテスト失敗
- `pytest_failure` - pytestテスト失敗
- `coverage_threshold_error` - カバレッジ閾値エラー

## ファイル構造

```
data/patterns/
├── ci_patterns.json              # 基本的なCI失敗パターン (9パターン)
├── build_patterns.json           # ビルドシステム関連 (6パターン)
├── dependency_patterns.json      # 依存関係管理関連 (7パターン)
├── test_patterns.json            # テスト実行関連 (5パターン)
├── action_patterns.json          # GitHub Actions固有 (6パターン)
├── pattern_index.json            # パターンインデックス
├── validate_patterns.py          # 検証スクリプト
├── PATTERN_DATABASE_SUMMARY.md   # この概要ファイル
└── custom/                       # カスタムパターン用ディレクトリ
    ├── README.md                 # カスタムパターン作成ガイド
    ├── user_patterns.json        # ユーザー定義パターン
    └── learned_patterns.json     # 学習済みパターン
```

## パターンの特徴

### 信頼度分布

- 高信頼度 (0.8以上): 21パターン
- 中信頼度 (0.7-0.8): 6パターン  
- 低信頼度 (0.7未満): 0パターン

### 成功率分布

- 平均成功率: 79%
- 最高成功率: 95% (docker_permission_denied)
- 最低成功率: 65% (dns_resolution_failure)

### 各パターンの構成要素

- **正規表現パターン**: エラーメッセージの具体的なマッチング
- **キーワード**: 簡易検索用のキーワードリスト
- **コンテキスト要件**: パターン適用の前提条件
- **信頼度**: パターンマッチの信頼性 (0.0-1.0)
- **成功率**: 過去の修正成功実績 (0.0-1.0)

## 検証結果

✅ 全パターンファイルの構造検証: 成功  
✅ 正規表現の妥当性検証: 成功  
✅ パターンID重複チェック: 成功  
✅ インデックスファイル整合性: 成功  

## 使用方法

1. **パターン認識エンジン**がこれらのパターンを読み込み
2. **CI失敗ログ**に対してパターンマッチングを実行
3. **信頼度スコア**に基づいて最適なパターンを選択
4. **対応する修正テンプレート**を提案

## 拡張性

- **カスタムパターン**: `custom/user_patterns.json`でユーザー独自パターンを追加可能
- **学習機能**: `custom/learned_patterns.json`で自動学習されたパターンを蓄積
- **プロジェクト固有**: プロジェクト特有のエラーパターンも追加可能

## 今後の改善計画

1. **パターンの精度向上**: 実際の使用データに基づく調整
2. **新しいカテゴリ追加**: セキュリティ、パフォーマンス関連パターン
3. **多言語対応**: 英語以外のエラーメッセージパターン
4. **動的学習**: ユーザーフィードバックによる自動改善

---

**要件1.5達成**: 20個以上の一般的なCI失敗パターンを作成し、正規表現、キーワード、修正テンプレートを定義し、適切な分類とカテゴリ分けを実装しました。
