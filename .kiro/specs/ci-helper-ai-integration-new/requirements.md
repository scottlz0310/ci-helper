# AI統合機能 要件定義書

## 概要

ci-helper AI統合機能は、既存のci-helperツール（Phase 1完了済み）にAI分析機能を追加するものです。この機能により、CI/CDの失敗ログを自動的にAIが分析し、根本原因の特定と修正提案を提供します。複数のAIプロバイダーに対応し、セキュアなAPIキー管理と効率的なトークン使用を実現します。

## 用語集

- **CI Helper System**: ci-helperツールのAI統合機能システム全体
- **AI Provider**: OpenAI、Anthropic、ローカルLLMなどのAIサービス提供者
- **Analyze Command**: 新しく追加される`ci-run analyze`コマンド
- **Token Management**: AIモデルのトークン制限を考慮した入力最適化
- **Streaming Response**: AIからのリアルタイム応答受信
- **Fix Suggestion**: AIが提案する具体的な修正方法
- **Interactive Mode**: AIとの対話的なデバッグセッション

## 要件

### 要件1: AI分析コマンドの実装

**ユーザーストーリー:** 開発者として、CI失敗ログをAIに分析させたい。そうすることで、エラーの根本原因と修正方法を迅速に理解できる。

#### 受け入れ基準

1. WHEN ユーザーが`ci-run analyze`を実行する, THE CI Helper System SHALL 最新のテスト実行結果をAI分析する
2. WHEN ユーザーが`--log path/to/log`を指定する, THE CI Helper System SHALL 指定されたログファイルを分析する
3. WHEN ユーザーが`--provider openai`を指定する, THE CI Helper System SHALL 指定されたAIプロバイダーを使用する
4. IF AIプロバイダーが設定されていない, THEN THE CI Helper System SHALL 設定方法を案内するエラーメッセージを表示する

### 要件2: 複数AIプロバイダー対応

**ユーザーストーリー:** 開発者として、複数のAIプロバイダーから選択したい。そうすることで、コストや性能に応じて最適なAIサービスを使用できる。

#### 受け入れ基準

1. WHEN THE CI Helper System がOpenAI APIキーを検出する, THE CI Helper System SHALL OpenAIプロバイダーを利用可能にする
2. WHEN THE CI Helper System がAnthropic APIキーを検出する, THE CI Helper System SHALL Anthropicプロバイダーを利用可能にする
3. WHEN ユーザーが`--model gpt-4o`を指定する, THE CI Helper System SHALL 指定されたモデルを使用する
4. IF 指定されたプロバイダーまたはモデルが利用できない, THEN THE CI Helper System SHALL 利用可能な選択肢を表示する
5. THE CI Helper System SHALL ローカルLLM（Ollama等）への接続をサポートする

### 要件3: セキュアなAPIキー管理

**ユーザーストーリー:** 開発者として、APIキーを安全に管理したい。そうすることで、機密情報の漏洩リスクを最小化できる。

#### 受け入れ基準

1. WHEN THE CI Helper System がAPIキーを読み取る, THE CI Helper System SHALL 環境変数からのみ取得する
2. IF 設定ファイルにAPIキーが記載されている, THEN THE CI Helper System SHALL 警告を表示し実行を停止する
3. WHEN ログファイルにAPIキーが含まれる, THE CI Helper System SHALL 自動的にマスクして表示する
4. WHEN AIプロバイダーと通信する, THE CI Helper System SHALL 安全な接続（HTTPS）のみを使用する
5. THE CI Helper System SHALL APIキーをメモリ上で適切に管理し、不要になったら即座に削除する

### 要件4: インテリジェントなエラー分析

**ユーザーストーリー:** 開発者として、AIによる詳細なエラー分析が欲しい。そうすることで、単なるエラーメッセージ以上の洞察を得られる。

#### 受け入れ基準

1. WHEN AIがエラーを分析する, THE CI Helper System SHALL 根本原因、影響範囲、修正優先度を含む構造化された分析を提供する
2. WHEN 複数のエラーが存在する, THE CI Helper System SHALL 関連性と修正順序を分析する
3. WHEN AIが既知のパターンを検出する, THE CI Helper System SHALL 類似事例と解決策を参照する
4. WHEN 分析結果を表示する, THE CI Helper System SHALL 技術レベルに応じて詳細度を調整する

### 要件5: 修正提案と自動適用

**ユーザーストーリー:** 開発者として、AIからの具体的な修正提案が欲しい。そうすることで、迅速に問題を解決できる。

#### 受け入れ基準

1. WHEN ユーザーが`--fix`オプションを使用する, THE CI Helper System SHALL 具体的なコード修正案を生成する
2. WHEN 修正提案を表示する, THE CI Helper System SHALL 変更前後の差分を明確に示す
3. WHEN ユーザーが修正適用を承認する, THE CI Helper System SHALL 該当ファイルを自動的に更新する
4. IF 修正が複数ファイルに及ぶ, THEN THE CI Helper System SHALL 各ファイルごとに個別の承認を求める
5. WHEN 修正を適用する前に, THE CI Helper System SHALL 自動的にバックアップを作成する

### 要件6: 対話的AIデバッグモード

**ユーザーストーリー:** 開発者として、AIと対話しながらデバッグしたい。そうすることで、複雑な問題を段階的に解決できる。

#### 受け入れ基準

1. WHEN ユーザーが`--interactive`を指定する, THE CI Helper System SHALL 対話的なセッションを開始する
2. WHEN 対話中にユーザーが追加質問をする, THE CI Helper System SHALL 文脈を保持して回答する
3. WHEN ユーザーが`/help`を入力する, THE CI Helper System SHALL 利用可能なコマンドを表示する
4. WHEN ユーザーが`/exit`を入力する, THE CI Helper System SHALL 対話セッションを終了する
5. WHILE 対話セッション中, THE CI Helper System SHALL トークン使用量をリアルタイムで表示する

### 要件7: ストリーミングレスポンス対応

**ユーザーストーリー:** 開発者として、AIの応答をリアルタイムで見たい。そうすることで、長い分析でも進捗を確認できる。

#### 受け入れ基準

1. WHEN AIプロバイダーがストリーミングをサポートする, THE CI Helper System SHALL リアルタイムで応答を表示する
2. WHEN ストリーミング中にユーザーがCtrl+Cを押す, THE CI Helper System SHALL 優雅に中断し部分的な結果を保存する
3. WHEN ネットワークエラーが発生する, THE CI Helper System SHALL 自動的にリトライを実行する
4. WHILE ストリーミング表示中, THE CI Helper System SHALL 適切なプログレス表示を提供する

### 要件8: コスト管理と使用統計

**ユーザーストーリー:** 開発者として、AI使用コストを把握したい。そうすることで、予算内でサービスを利用できる。

#### 受け入れ基準

1. WHEN AI分析が実行完了する, THE CI Helper System SHALL 使用トークン数と推定コストを表示する
2. WHEN ユーザーが`ci-run analyze --stats`を実行する, THE CI Helper System SHALL 過去の使用統計を表示する
3. WHEN 月間使用量が設定された制限に近づく, THE CI Helper System SHALL 警告を表示する
4. WHEN 高コストな分析を実行する前に, THE CI Helper System SHALL 推定コストを表示し確認を求める

### 要件9: AIレスポンスキャッシュ

**ユーザーストーリー:** 開発者として、同じエラーの再分析時にコストを節約したい。そうすることで、効率的にAIサービスを利用できる。

#### 受け入れ基準

1. WHEN 同一のログ内容を分析する, THE CI Helper System SHALL キャッシュされた結果を使用する
2. WHEN キャッシュが古くなる, THE CI Helper System SHALL 自動的に新しい分析を実行する
3. WHEN ユーザーが`--no-cache`を指定する, THE CI Helper System SHALL キャッシュを無視して新しい分析を実行する
4. WHEN キャッシュサイズが制限を超える, THE CI Helper System SHALL 最も古いエントリを自動削除する

### 要件10: プロンプトテンプレート管理

**ユーザーストーリー:** 開発者として、AI分析の品質を向上させたい。そうすることで、より正確で有用な分析結果を得られる。

#### 受け入れ基準

1. WHEN THE CI Helper System がエラータイプを検出する, THE CI Helper System SHALL 適切な専用プロンプトテンプレートを使用する
2. WHEN ユーザーが`--prompt "カスタム指示"`を指定する, THE CI Helper System SHALL カスタムプロンプトを追加する
3. WHEN プロンプトテンプレートを更新する, THE CI Helper System SHALL 設定ファイルから読み込む
4. WHEN 新しいエラーパターンが検出される, THE CI Helper System SHALL 汎用プロンプトで対応する

### 要件11: エラーハンドリングと復旧

**ユーザーストーリー:** 開発者として、AI統合でエラーが発生しても適切に処理されることを期待する。そうすることで、安定したツール利用ができる。

#### 受け入れ基準

1. IF APIキーが無効である, THEN THE CI Helper System SHALL 明確なエラーメッセージと設定方法を表示する
2. IF API制限に達した, THEN THE CI Helper System SHALL 制限リセット時刻と代替手段を提案する
3. IF ネットワークエラーが発生した, THEN THE CI Helper System SHALL 自動リトライと手動再実行オプションを提供する
4. IF AI分析が失敗した, THEN THE CI Helper System SHALL 従来のログ表示にフォールバックする
5. WHEN タイムアウトが発生する, THE CI Helper System SHALL 部分的な結果を保存し後で継続できるようにする

### 要件12: 設定とカスタマイゼーション

**ユーザーストーリー:** 開発者として、AI統合機能をプロジェクトに合わせてカスタマイズしたい。そうすることで、最適な分析結果を得られる。

#### 受け入れ基準

1. WHEN 設定ファイルにAI設定セクションが存在する, THE CI Helper System SHALL それらの設定を読み込む
2. WHEN 環境変数でAI設定が指定されている, THE CI Helper System SHALL 設定ファイルより優先する
3. WHEN プロジェクト固有のプロンプトテンプレートが存在する, THE CI Helper System SHALL それを使用する
4. IF 設定が競合している, THEN THE CI Helper System SHALL 明確な優先順位に従って解決する

### 要件13: ファイル所有権とアクセス権限の保持

**ユーザーストーリー:** 開発者として、ci-helperを実行した後もファイルの所有権が変更されないことを期待する。そうすることで、プロジェクトファイルへの正常なアクセスを維持できる。

#### 受け入れ基準

1. WHEN ci-helperがDockerコンテナ内でactを実行する, THE CI Helper System SHALL ホストのファイル所有権を保持する
2. IF ファイルの所有権がdockerユーザーに変更された, THEN THE CI Helper System SHALL 自動的に元の所有者に復元する
3. WHEN ユーザーが`ci-run test`を実行した後, THE CI Helper System SHALL プロジェクトディレクトリ内のファイル所有権を確認し、必要に応じて修正する
4. THE CI Helper System SHALL 実行前後でファイル所有権の変更を検出し、警告を表示する
5. IF ファイル所有権の修正に失敗した, THEN THE CI Helper System SHALL 明確なエラーメッセージと手動修正方法を表示する
