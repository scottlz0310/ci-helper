いいですね！**ci-helper**にピッタリはまりそうです。
「ケースベース推論（CBR）＋軽量モデル（任意）＋反復検証」の仕組みを、いまのプロジェクトに**段階的に取り込める設計**で提案します。コードも最小構成でサクッと動くプロトタイプを添えておきます。

---

## 提案アーキテクチャ（シンプル版）

```
act (CI 実行)
  └─> ログ収集 (ci-helper)
        ├─ パターンマッチ (regex/ルール)
        ├─ 既存ケース検索 (CBRのケースDB)
        ├─ 修正アクション生成
        │     ├─ ルールベース
        │     └─ [任意] 軽量LLM補完 (Ollama)
        ├─ パッチ適用 / コマンド実行
        └─ 結果記録 (成功/失敗・指標) → ケースDBに蓄積
```

### コンポーネント分割

- `patterns/`：正規表現とヒント（ルールファイル、YAML/JSON）
- `cases/`：履歴DB（JSONL/SQLite）。**エラー→修正案→結果**を一体で記録
- `actions/`：修正アクションの実装（例：`pip install`, `pytest -q`, ファイルパッチ適用）
- `advisors/llm_ollama.py`：曖昧ケースに限り、Ollamaに軽く聞く（オプション）
- `runner/`：再テスト実行・成否判定
- `score/`：ケース成功率スコアリング（優先度調整）

---

## データスキーマ（JSON例）

```json
{
  "id": "case-2025-10-18-001",
  "timestamp": "2025-10-18T12:34:56Z",
  "ci_context": {
    "workflow": ".github/workflows/test.yml",
    "job": "pytest",
    "commit": "abc123",
    "env": {"PYTHON_VERSION": "3.11"}
  },
  "error": {
    "raw": "E   ModuleNotFoundError: No module named 'packaging'\n...",
    "pattern_id": "py.modulenotfound",
    "extracted": {"module": "packaging"}
  },
  "proposal": {
    "source": "rule",  // rule | cbr | llm
    "actions": [
      {"type": "pip_install", "args": ["packaging"]},
      {"type": "run_cmd", "args": ["pytest", "-q"]}
    ]
  },
  "result": {
    "status": "success", // success | fail
    "metrics": {"tests_passed": 120, "tests_failed": 0}
  }
}
```

> ポイント：**「error」「proposal」「result」を必ず1レコードにまとめて保存**。これが反復学習の質を上げます。

---

## 初期パターン辞書（YAML）

```yaml
# patterns/python.yml
- id: py.modulenotfound
  regex: "ModuleNotFoundError: No module named '(?P<module>[a-zA-Z0-9_\\-]+)'"
  hints:
    - "requirements.txt に依存追加"
    - "pip install {module}"
  actions:
    - type: pip_install
      args: ["{module}"]
    - type: run_cmd
      args: ["pytest", "-q"]

- id: py.syntaxerror
  regex: "SyntaxError: (?P<detail>.+)"
  hints:
    - "flake8/ruff 実行で構文エラー検出・修正箇所特定"
  actions:
    - type: run_cmd
      args: ["ruff", "check", "--fix", "."]
    - type: run_cmd
      args: ["pytest", "-q"]

- id: py.assertion
  regex: "AssertionError: (?P<message>.+)"
  hints:
    - "失敗テストを抽出し、対象関数・期待値の差分確認"
  actions:
    - type: run_cmd
      args: ["pytest", "-q", "-k", "last_failed"]
```

---

## 最小プロトタイプ（Pythonスクリプト）

> 目的：ログからパターン抽出→アクション実行→結果記録（CBRケース保存）
> 依存：`pyyaml`（YAML読み込み）、`subprocess`。LLMは未使用でOK。

```python
#!/usr/bin/env python3
# file: ci_helper_proto.py
import re, json, time, uuid, subprocess
from pathlib import Path
import yaml

PATTERN_DIR = Path("patterns")
CASES_DIR = Path("cases")
CASES_DIR.mkdir(exist_ok=True)

def load_patterns():
    rules = []
    for f in PATTERN_DIR.glob("*.yml"):
        rules.extend(yaml.safe_load(f.read_text()))
    return rules

def match_error(log_text, rules):
    for r in rules:
        m = re.search(r["regex"], log_text, re.MULTILINE)
        if m:
            return r, m.groupdict()
    return None, {}

def format_actions(actions, extracted):
    fmt = []
    for a in actions:
        args = [arg.format(**extracted) for arg in a.get("args", [])]
        fmt.append({"type": a["type"], "args": args})
    return fmt

def run_action(action):
    if action["type"] == "pip_install":
        cmd = ["python", "-m", "pip", "install"] + action["args"]
    elif action["type"] == "run_cmd":
        cmd = action["args"]
    else:
        return False, f"Unknown action {action['type']}"
    print("RUN:", " ".join(cmd))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = (res.returncode == 0)
        return ok, res.stdout + "\n" + res.stderr
    except Exception as e:
        return False, str(e)

def save_case(record):
    case_id = f"case-{time.strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
    record["id"] = case_id
    path = CASES_DIR / f"{case_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print("Saved:", path)

def main():
    rules = load_patterns()
    # 例: actのログファイルを読み取る
    log_path = Path("artifacts/act.log")
    if not log_path.exists():
        print("log not found:", log_path)
        return
    log_text = log_path.read_text()

    rule, extracted = match_error(log_text, rules)
    if not rule:
        print("no pattern matched")
        return

    actions = format_actions(rule["actions"], extracted)
    action_outputs = []
    result_status = "success"
    for a in actions:
        ok, out = run_action(a)
        action_outputs.append({"action": a, "ok": ok, "output": out})
        if not ok:
            result_status = "fail"
            break

    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ci_context": {"workflow": ".github/workflows/test.yml", "job": "pytest"},
        "error": {
            "raw": log_text[-2000:],  # 末尾抜粋
            "pattern_id": rule["id"],
            "extracted": extracted,
        },
        "proposal": {"source": "rule", "actions": actions},
        "result": {"status": result_status, "metrics": {}},
        "diagnostics": action_outputs,
    }
    save_case(record)

if __name__ == "__main__":
    main()
```

> まずは**ルールだけで回す**のがコツ。十分効くパターンが多いです。曖昧ケースが残ったら、そこでOllamaを足せばOK。

---

## 反復学習（優先度の自動調整）

シンプルに始めるなら、**成功率ベースのウェイト**で十分です。

- メタ情報テーブル（`stats.json`）を持つ：

  ```json
  { "py.modulenotfound": {"success": 12, "fail": 3} }
  ```

- ルール選択時に、`success/(success+fail)`を重みとして優先度を更新。
- 新しいパターンがヒットしない場合のみ、**Ollama補完**にフォールバック。

---

## Ollama補完（任意）

曖昧なケースのみ、軽量モデルで分類＋ヒント生成：

```bash
ollama run mistral "
You are a CI log triager. Classify the error and propose minimal fix.
LOG:
$(tail -n 200 artifacts/act.log)
"
```

> ここで出た提案を**ケースDBに記録**して、次回以降は「cbr由来の提案」として再利用できます。

---

## ci-helperへの統合アイデア

- **CLIサブコマンド**：`ci-helper triage --log artifacts/act.log --apply`
- **GitHub Actions向け**：ワークフロー内の`post`ステップで`ci-helper`を実行し、失敗時のみ起動。
- **ケースの可視化**：`cases/`をHTMLで一覧化（成功率、最近の失敗、再現性など）。

---

## 次の一歩（軽めでOK）

1. `patterns/python.yml` をプロジェクトに追加
2. 上のプロトタイプを `tools/ci_helper_proto.py` として実行
3. `act`実行後のログを `artifacts/act.log` に保存して試す
4. 効いたら、`cases/`が溜まっていくのを確認

必要なら、**既存のci-helper構成に合わせて**モジュール分割・CLI化までやります。
菅原さんの使い方（xdistやローカル・WSL併用）にも合わせて最適化できます。

---

他にも追加したいパターン（pytestの`-n logical`での並列特有の落ち方や、Windows/WSLのパス問題など）があれば、列挙してくれれば**ルール案**までまとめます。

# 総評と追加案

この提案、とても良く練られていますね！CI失敗の自動修正という難しい課題に対して、実践的で段階的なアプローチを取っています。いくつかの観点からフィードバックします。

## 👍 特に優れている点

**1. 段階的アプローチ**
ルール→CBR→LLMという優先順位が賢明です。多くのCI失敗は定型的なので、80%はルールで解決できるはず。

**2. データ設計**
`error`→`proposal`→`result`を1レコードで保存する設計が秀逸。機械学習的な改善がやりやすく、デバッグもしやすい。

**3. 軽量な依存関係**
YAML + subprocess だけで動くプロトタイプは、実際に試しやすい。

## ⚠️ 検討すべき課題

### セキュリティリスク

```python
# 自動実行は危険が伴います
subprocess.run(cmd, ...)  # ← インジェクション対策必須
```

**対策案：**

- アクションの**ホワイトリスト**を厳格に
- `pip install` は `requirements.txt` のパッケージ名検証
- ファイル書き込みは対象ディレクトリ制限（`.git/` への書き込み禁止など）
- **dry-run モード**を最初は必須に

### 並行実行の考慮

pytest の `-n logical` や複数ジョブでの競合：

```yaml
# patterns/python.yml に追加提案
- id: py.pytest_xdist_worker_crash
  regex: "gw\\d+ \\[\\d+%\\] worker '.*' crashed while running"
  hints:
    - "xdist ワーカー数を減らす"
    - "共有リソースのロック確認"
  actions:
    - type: run_cmd
      args: ["pytest", "-n", "2", "-q"]  # ワーカー数削減
```

### ケース検索の効率化

ケース数が増えた時の対策：

```python
# 類似度検索の追加提案
from difflib import SequenceMatcher

def find_similar_cases(error_text, cases_dir, top_k=3):
    """エラー文字列の類似度でケースを検索"""
    scores = []
    for case_file in cases_dir.glob("*.json"):
        case = json.loads(case_file.read_text())
        similarity = SequenceMatcher(
            None,
            error_text,
            case["error"]["raw"]
        ).ratio()
        scores.append((similarity, case))
    return sorted(scores, reverse=True)[:top_k]
```

## 💡 追加アイデア

### 1. コンフリクト検出

複数の修正案が競合する場合：

```python
def detect_conflicts(actions):
    """依存関係の競合を検出"""
    pip_installs = [a for a in actions if a["type"] == "pip_install"]
    if len(pip_installs) > 1:
        # requirements.txt と照合して互換性確認
        pass
```

### 2. ロールバック機能

```python
# アクション実行前にスナップショット
snapshot = {
    "requirements": Path("requirements.txt").read_text(),
    "git_diff": subprocess.run(["git", "diff"], capture_output=True)
}
# 失敗時に復元
```

### 3. 信頼度スコア

```python
record = {
    # ...
    "confidence": {
        "pattern_match": 0.95,  # regex マッチの確信度
        "cbr_similarity": 0.87,  # 類似ケースとの距離
        "success_rate": 0.80,   # 過去の成功率
    }
}
# confidence が低い場合は人間承認を求める
```

### 4. Windows/WSL対応パターン

```yaml
- id: path.windows_wsl_mismatch
  regex: "FileNotFoundError.*\\\\.*C:\\\\Users"
  hints:
    - "WSL内でWindowsパス使用"
    - "wslpath でパス変換"
  actions:
    - type: run_cmd
      args: ["wslpath", "-u", "{path}"]
```

## 🎯 実装の優先順位（提案）

### フェーズ1（1-2週間）

- [ ] パターン辞書を5-10個作成（頻出エラー）
- [ ] プロトタイプを **dry-run モード**で実行
- [ ] `cases/` の蓄積開始

### フェーズ2（2-3週間）

- [ ] セーフガード実装（ホワイトリスト、サンドボックス）
- [ ] GitHub Actions統合
- [ ] ケース可視化HTML

### フェーズ3（1-2ヶ月）

- [ ] CBR検索の実装
- [ ] Ollama補完（オプション）
- [ ] 成功率フィードバックループ

## 📝 コード改善提案

プロトタイプに安全機構を追加：

```python
# セーフガード付き実行
ALLOWED_COMMANDS = {
    "pip_install": ["python", "-m", "pip", "install"],
    "pytest": ["pytest"],
    "ruff": ["ruff"],
}

def run_action_safe(action, dry_run=True):
    if action["type"] not in ALLOWED_COMMANDS:
        return False, f"Forbidden action: {action['type']}"

    cmd_base = ALLOWED_COMMANDS[action["type"]]
    cmd = cmd_base + action["args"]

    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return True, "dry-run mode"

    # 実際の実行...
```

---

**総評：** 非常に実践的で、段階的に導入できる優れた設計です。セキュリティ対策と dry-run から始めれば、リスクを最小化しながら価値を早期に実証できます。

具体的なパターン（pytest特有のエラーやWSL問題など）を追加したい場合は、エラーログの例を見せてもらえれば、正規表現とアクションをすぐ書けますよ！
