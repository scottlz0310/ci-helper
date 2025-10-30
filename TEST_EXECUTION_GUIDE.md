# テスト実行ガイド（WSLクラッシュ対策）

WSLがクラッシュする問題に対処するため、複数のテスト実行方法と詳細なログ機能を提供しています。

## 問題の背景

pytestの実行中にWSL自体が落ちる問題が発生しています。考えられる原因:

1. **メモリ不足**: 並列実行とカバレッジ収集による大量メモリ消費
2. **リソースリーク**: 非同期処理（aiohttp等）のクリーンアップ不足
3. **プロセス過多**: pytest-xdistの並列実行による過負荷

## 実行方法

### 1. 最小限モード（推奨：問題調査用）

最も安全な実行方法です。並列実行とカバレッジを無効化します。

```bash
./run_tests_minimal.sh
```

**特徴:**
- 並列実行なし（単一プロセス）
- カバレッジ収集なし
- 詳細ログ出力
- リソース使用量が最小

**使用時:**
- WSLクラッシュの原因を特定したい
- どのテストでクラッシュするか調査したい
- メモリが限られている環境

### 2. 安全モード（監視付き）

リソース監視とログを有効にした実行方法です。

```bash
# デフォルト（ワーカー数2で並列実行）
./run_tests_safe.sh

# ワーカー数を指定
PYTEST_WORKERS=1 ./run_tests_safe.sh

# カバレッジを無効化
PYTEST_EXTRA_OPTS="--no-cov" ./run_tests_safe.sh

# メモリ制限を設定（MB単位、例：4GB）
PYTEST_MEMORY_LIMIT=4096 ./run_tests_safe.sh
```

**特徴:**
- リソース監視（5秒間隔でメモリ/CPU記録）
- 詳細なログ出力
- dmesgの差分チェック
- 並列実行数を制御可能

**使用時:**
- リソース使用状況を監視したい
- クラッシュ直前の状態を記録したい
- 段階的にテストを実行したい

### 3. 通常モード

pyproject.tomlの設定を使用した通常実行です。

```bash
# UVを使用（推奨）
uv run pytest

# 直接実行
python3 -m pytest
```

**注意:** この方法はWSLクラッシュが解決するまで推奨しません。

## ログファイル

実行後、以下のログファイルが `test_logs/` ディレクトリに生成されます:

```
test_logs/
├── pytest_YYYYMMDD_HHMMSS.log        # 完全な実行ログ
├── resources_YYYYMMDD_HHMMSS.log     # リソース使用状況（CSV形式）
├── dmesg_YYYYMMDD_HHMMSS.log.before  # 実行前のdmesg
├── dmesg_YYYYMMDD_HHMMSS.log.after   # 実行後のdmesg
└── dmesg_YYYYMMDD_HHMMSS.log.diff    # dmesgの差分
```

### ログの分析方法

#### 1. リソースログの確認

```bash
# リソース使用状況を確認
cat test_logs/resources_*.log

# メモリ使用率が高い時刻を抽出
awk -F',' '$2 > 80 {print}' test_logs/resources_*.log
```

#### 2. クラッシュ時のdmesg確認

```bash
# カーネルエラーをチェック
cat test_logs/dmesg_*.log.diff

# Out of Memoryエラーを検索
grep -i "out of memory\|oom" test_logs/dmesg_*.log.diff
```

#### 3. どのテストで失敗したか確認

```bash
# 最後に実行されたテストを確認
grep -E "test_.*\.py::" test_logs/pytest_*.log | tail -20

# FAILEDテストを抽出
grep "FAILED" test_logs/pytest_*.log
```

## トラブルシューティング

### WSLが落ちる場合

1. **最小限モードで実行**
   ```bash
   ./run_tests_minimal.sh
   ```

2. **特定のテストのみ実行**
   ```bash
   # 単一ファイル
   uv run pytest tests/unit/test_specific.py -v

   # 単一テスト
   uv run pytest tests/unit/test_specific.py::test_function -v
   ```

3. **メモリを確認**
   ```bash
   # 実行前
   free -h

   # 実行中（別ターミナル）
   watch -n 1 free -h
   ```

4. **dmesgをリアルタイム監視**
   ```bash
   # 別ターミナルで実行
   dmesg -w
   ```

### メモリ不足エラー

メモリ使用量を抑えるオプション:

```bash
# ワーカー数を1に制限
PYTEST_WORKERS=1 ./run_tests_safe.sh

# カバレッジを無効化
PYTEST_EXTRA_OPTS="--no-cov" ./run_tests_safe.sh

# 最小限モード
./run_tests_minimal.sh
```

### テストが途中で止まる

タイムアウト設定を調整:

```bash
# タイムアウトを延長（秒単位）
uv run pytest --timeout=600
```

## デバッグ情報の収集

問題を報告する際は、以下の情報を収集してください:

```bash
# システム情報
uname -a > debug_info.txt
free -h >> debug_info.txt
ulimit -a >> debug_info.txt

# Python環境
python3 --version >> debug_info.txt
uv --version >> debug_info.txt
uv pip list >> debug_info.txt

# 最新のログファイルをコピー
cp test_logs/pytest_*.log ./
cp test_logs/dmesg_*.diff ./
```

## 環境変数リファレンス

| 変数名 | 説明 | デフォルト | 例 |
|--------|------|-----------|-----|
| `PYTEST_WORKERS` | 並列ワーカー数 | 2 | `PYTEST_WORKERS=1` |
| `PYTEST_MAXFAIL` | 最大失敗数 | 10 | `PYTEST_MAXFAIL=5` |
| `PYTEST_EXTRA_OPTS` | 追加オプション | - | `PYTEST_EXTRA_OPTS="--no-cov -k test_basic"` |
| `PYTEST_MEMORY_LIMIT` | メモリ制限(MB) | - | `PYTEST_MEMORY_LIMIT=4096` |

## 推奨実行フロー

1. **初回実行**: 最小限モードで全体像を把握
   ```bash
   ./run_tests_minimal.sh 2>&1 | tee first_run.log
   ```

2. **問題箇所の特定**: ログから失敗箇所を確認
   ```bash
   grep -A 5 "FAILED\|ERROR" test_logs/pytest_minimal_*.log
   ```

3. **個別テスト**: 問題のあるテストを個別実行
   ```bash
   uv run pytest tests/unit/problematic_test.py -v --log-cli-level=DEBUG
   ```

4. **段階的拡大**: 少しずつワーカー数を増やして実行
   ```bash
   PYTEST_WORKERS=1 ./run_tests_safe.sh
   PYTEST_WORKERS=2 ./run_tests_safe.sh
   ```

## 補足情報

### pyproject.tomlの設定

デフォルトの設定は以下の通りです:
- 並列実行: `logical` (CPU数に応じた自動設定)
- カバレッジ: 有効
- タイムアウト: 300秒

### pytest_minimal.iniの設定

最小限モードの設定:
- 並列実行: 無効
- カバレッジ: 無効
- ログレベル: INFO
- ファイルログ: 有効

## 参考リンク

- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [WSL2 memory issues](https://github.com/microsoft/WSL/issues/)
