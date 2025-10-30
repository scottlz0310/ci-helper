#!/bin/bash
# 最小限のテスト実行（WSLクラッシュ対策）
# 並列実行なし、カバレッジなし、詳細ログあり

set -euo pipefail

LOG_DIR="test_logs"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/pytest_minimal_${TIMESTAMP}.log"

echo "=== 最小限モードでテスト実行 ==="
echo "ログファイル: ${LOG_FILE}"
echo ""
echo "初期メモリ状態:"
free -h
echo ""

# 最小限の設定でpytestを実行
# - 並列実行なし
# - カバレッジなし
# - 詳細ログあり
# - エラーでも継続実行（全テスト実行）
uv run pytest \
    -c pytest_minimal.ini \
    --log-cli-level=INFO \
    -v \
    2>&1 | tee "${LOG_FILE}"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "最終メモリ状態:"
free -h
echo ""

# dmesgの確認
echo "=== dmesgの最新ログ（最後の20行） ==="
dmesg | tail -20

echo ""
echo "終了コード: ${EXIT_CODE}"
echo "詳細ログ: ${LOG_FILE}"

exit ${EXIT_CODE}
