#!/bin/bash
# 安全なテスト実行スクリプト（WSLクラッシュ対策）
# 詳細なログとリソース監視を行いながらpytestを実行

set -euo pipefail

# ログディレクトリの設定
LOG_DIR="test_logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/pytest_${TIMESTAMP}.log"
RESOURCE_LOG="${LOG_DIR}/resources_${TIMESTAMP}.log"
DMESG_LOG="${LOG_DIR}/dmesg_${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

# 色付き出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}"
}

# 初期システム状態の記録
log_info "=== テスト実行開始 ==="
log_info "タイムスタンプ: ${TIMESTAMP}"
log_info "ログファイル: ${LOG_FILE}"
log_info "リソースログ: ${RESOURCE_LOG}"

# システム情報の記録
{
    echo "=== システム情報 ==="
    echo "日時: $(date)"
    echo ""
    echo "=== カーネル情報 ==="
    uname -a
    echo ""
    echo "=== メモリ情報 ==="
    free -h
    echo ""
    echo "=== ulimit設定 ==="
    ulimit -a
    echo ""
    echo "=== Pythonバージョン ==="
    python3 --version
    echo ""
    echo "=== uvバージョン ==="
    uv --version
    echo ""
} | tee -a "${LOG_FILE}"

# dmesgの初期状態を保存
dmesg > "${DMESG_LOG}.before" 2>&1 || log_warn "dmesg取得失敗"

# リソース監視を開始
monitor_resources() {
    local interval=5
    log_info "リソース監視を開始 (${interval}秒間隔)"

    {
        echo "時刻,メモリ使用率(%),使用メモリ(MB),空きメモリ(MB),CPU平均(%),プロセス数"
        while true; do
            # メモリ情報
            mem_info=$(free -m | awk 'NR==2 {printf "%.1f,%d,%d", ($3/$2)*100, $3, $4}')
            # CPU負荷
            cpu_load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
            # プロセス数
            proc_count=$(ps aux | wc -l)

            echo "$(date +%H:%M:%S),${mem_info},${cpu_load},${proc_count}"
            sleep "${interval}"
        done
    } >> "${RESOURCE_LOG}" 2>&1 &

    MONITOR_PID=$!
    log_info "リソース監視PID: ${MONITOR_PID}"
}

# クリーンアップ関数
cleanup() {
    local exit_code=$?

    log_info "=== クリーンアップ開始 ==="

    # リソース監視を停止
    if [ -n "${MONITOR_PID:-}" ]; then
        log_info "リソース監視を停止 (PID: ${MONITOR_PID})"
        kill "${MONITOR_PID}" 2>/dev/null || true
        wait "${MONITOR_PID}" 2>/dev/null || true
    fi

    # 最終的なシステム状態を記録
    {
        echo ""
        echo "=== 最終メモリ状態 ==="
        free -h
        echo ""
        echo "=== プロセス情報 ==="
        ps aux | grep -E "pytest|python" | grep -v grep || echo "関連プロセスなし"
    } | tee -a "${LOG_FILE}"

    # dmesgの差分を保存
    dmesg > "${DMESG_LOG}.after" 2>&1 || log_warn "dmesg取得失敗"
    if [ -f "${DMESG_LOG}.before" ] && [ -f "${DMESG_LOG}.after" ]; then
        diff "${DMESG_LOG}.before" "${DMESG_LOG}.after" > "${DMESG_LOG}.diff" 2>&1 || true
        if [ -s "${DMESG_LOG}.diff" ]; then
            log_warn "dmesgに新しいエントリがあります: ${DMESG_LOG}.diff"
        fi
    fi

    # 終了コードに応じたメッセージ
    if [ ${exit_code} -eq 0 ]; then
        log_info "=== テスト実行完了（成功） ==="
    else
        log_error "=== テスト実行完了（失敗: ${exit_code}） ==="
    fi

    log_info "詳細ログ: ${LOG_FILE}"
    log_info "リソースログ: ${RESOURCE_LOG}"
    log_info "dmesg差分: ${DMESG_LOG}.diff"

    return ${exit_code}
}

# SIGINTやSIGTERMでもクリーンアップ
trap cleanup EXIT INT TERM

# リソース監視開始
monitor_resources

# pytest実行オプション
PYTEST_OPTS=(
    # 並列実行を制限（デフォルトはlogical=CPU数、メモリ節約のため制限）
    "-n" "${PYTEST_WORKERS:-2}"

    # より詳細なログ出力
    "-v"
    "--tb=long"

    # ログ出力を有効化
    "--log-cli-level=INFO"

    # タイムアウト設定（デフォルト300秒を維持）
    "--timeout=300"
    "--timeout-method=thread"

    # 失敗時の最大数
    "--maxfail=${PYTEST_MAXFAIL:-10}"

    # カバレッジ（メモリ使用を抑えるため無効化も可能）
    "--cov=ci_helper"
    "--cov-report=term-missing"
    "--cov-report=html:htmlcov"

    # ワーニングを表示（問題の早期発見）
    "-W" "default"
)

# 環境変数で追加オプションを指定可能
if [ -n "${PYTEST_EXTRA_OPTS:-}" ]; then
    log_info "追加オプション: ${PYTEST_EXTRA_OPTS}"
    PYTEST_OPTS+=( ${PYTEST_EXTRA_OPTS} )
fi

# メモリ使用量の制限（オプション）
if [ -n "${PYTEST_MEMORY_LIMIT:-}" ]; then
    log_warn "メモリ制限: ${PYTEST_MEMORY_LIMIT}MB"
    ulimit -v $((PYTEST_MEMORY_LIMIT * 1024))
fi

log_info "=== pytest実行開始 ==="
log_info "実行コマンド: uv run pytest ${PYTEST_OPTS[*]}"

# pytest実行
set +e  # エラーでも継続してクリーンアップを実行
uv run pytest "${PYTEST_OPTS[@]}" 2>&1 | tee -a "${LOG_FILE}"
PYTEST_EXIT_CODE=${PIPESTATUS[0]}
set -e

log_info "pytest終了コード: ${PYTEST_EXIT_CODE}"

# 終了コードを保存して、cleanupで使用
exit ${PYTEST_EXIT_CODE}
