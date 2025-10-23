# コード品質ルール（AI 用コンテキスト）

## 目的

- コード品質を自動で担保し、レビュー負荷を減らす
- Ruff を中心に統一し、Black や isort は使用しない
- 柔軟性を確保しつつ、基本方針を明示
- AI はこのルールを参考に.pre-commit-config.yaml を作成すること

---

## 基本方針

- **フォーマット**: Ruff Format を使用（Black は使用禁止）
- **Lint**: Ruff Check（E, F, I, B, UP, S, T）
- **型チェック**: MyPy（必要に応じて）
- **セキュリティ**: Bandit（必要に応じて）、Safety は CI または手動
- **テスト**: pytest は pre-commit では必須ではない（CI で実施）
- 行末空白文字チェック
- 大きなファイルチェック
- マージコンフリクトチェック

---

## Ruff 設定ポリシー

- `line-length = 120`
- `quote-style = "double"`
- `select = ["E", "F", "I", "B", "UP", "S"]`
- `ignore = ["E501"]`（長い行は Ruff Format に任せる）

---

## pre-commit 実行順序

1. Ruff Check（--fix）
2. Ruff Format
3. MyPy（必要に応じて）
4. Bandit（必要に応じて）
5. YAML/JSON 構文チェック
6. pytest（任意、CI で必須）

---

## AI 提案に関するルール

- すべてのコードは Ruff Format 準拠で出力すること
- Black や isort の使用を提案しないこと
- pytest や Safety は「ケースバイケース」で提案すること
- pre-push フックは使用しない（CI で代替）

---

## 柔軟な項目

- pytest 実行タイミング（ローカル or CI）
- Safety 実行タイミング（CI 推奨）
