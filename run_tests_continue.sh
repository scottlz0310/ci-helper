#!/bin/bash
# 全テスト継続実行モード（エラーでも停止しない）
# 最小限のリソースで全テストを実行し、全体像を把握

set -euo pipefail

LOG_DIR="test_logs"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/pytest_continue_${TIMESTAMP}.log"

echo "=== 全テスト継続実行モード ==="
echo "ログファイル: ${LOG_FILE}"
echo ""
echo "初期メモリ状態:"
free -h
echo ""

# pytest実行（エラーでも全テスト継続）
# - 並列実行なし
# - カバレッジなし
# - maxfailなし（全テスト実行）
# - 詳細ログあり
uv run pytest \
    -c pytest_minimal.ini \
    --log-cli-level=INFO \
    -v \
    --tb=short \
    --continue-on-collection-errors \
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

# 統計情報を抽出
echo ""
echo "=== テスト結果サマリー ==="
grep -E "(passed|failed|error|skipped)" "${LOG_FILE}" | tail -5 || echo "サマリー情報が見つかりません"

exit ${EXIT_CODE}
