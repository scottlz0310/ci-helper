#!/bin/bash
# pytest実行時にWSLがクラッシュしても調査用ログを確実に残すためのガードスクリプト

set -euo pipefail

if [ $# -gt 0 ]; then
    TEST_COMMAND=("$@")
else
    TEST_COMMAND=("./run_tests_continue.sh")
fi

# bashは配列全体を1要素に格納しないため、逐次展開で表示用文字列を生成
COMMAND_STRING=""
for token in "$@"; do
    COMMAND_STRING+="$(printf '%q ' "$token")"
done
if [ -z "$COMMAND_STRING" ]; then
    COMMAND_STRING="./run_tests_continue.sh"
else
    COMMAND_STRING=${COMMAND_STRING%% }  # 末尾スペース除去
fi

LOG_ROOT="${CI_HELPER_CRASH_ROOT:-test_logs/crash_dumps}"
mkdir -p "$LOG_ROOT"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="${LOG_ROOT}/run_${TIMESTAMP}"
mkdir -p "$RUN_DIR"

log_info() {
    echo "[crash-guard] $*"
}

log_warn() {
    echo "[crash-guard][warn] $*"
}

log_info "Artifact directory: ${RUN_DIR}"
log_info "Test command: ${COMMAND_STRING}"

export CI_HELPER_PROGRESS_LOG="${RUN_DIR}/pytest_progress.jsonl"
export CI_HELPER_PROGRESS_META="${RUN_DIR}/pytest_progress_meta.json"
export CI_HELPER_PROGRESS_RUN_ID="${TIMESTAMP}"
export CI_HELPER_PROGRESS_COMMAND="${COMMAND_STRING}"
export CI_HELPER_PROGRESS_FSYNC="${CI_HELPER_PROGRESS_FSYNC:-1}"

MONITOR_PIDS=()
TEST_EXIT_CODE=0
TEST_EXIT_CODE_SET=0
RESOURCE_INTERVAL=${CRASH_GUARD_RESOURCE_INTERVAL:-5}
PROCESS_INTERVAL=${CRASH_GUARD_PROCESS_INTERVAL:-15}

write_system_snapshot() {
    {
        echo "timestamp: $(date --iso-8601=seconds)"
        echo "command: ${COMMAND_STRING}"
        echo "working_dir: $(pwd)"
        echo "shell: ${SHELL}"
        echo
        echo "=== uname -a ==="
        uname -a
        echo
        echo "=== /proc/version ==="
        cat /proc/version 2>/dev/null || true
        echo
        echo "=== free -h ==="
        free -h || true
        echo
        echo "=== df -h ==="
        df -h || true
        echo
        echo "=== ulimit -a ==="
        ulimit -a || true
        echo
        echo "=== python3 --version ==="
        python3 --version 2>&1 || echo "python3 not available"
        echo
        echo "=== uv --version ==="
        uv --version 2>&1 || echo "uv not available"
        echo
        echo "=== filtered environment ==="
        env | sort | grep -E "^(CI_HELPER|PYTEST|WSL|UV_|PYTHON|UV)" || true
    } > "${RUN_DIR}/system_snapshot.txt"
}

start_dmesg_monitor() {
    if ! command -v dmesg >/dev/null 2>&1; then
        log_warn "dmesg command not available; skipping kernel log follow"
        return
    fi

    local log_file="${RUN_DIR}/dmesg_follow.log"
    stdbuf -oL dmesg --follow --human >"${log_file}" 2>&1 &
    local pid=$!
    sleep 0.2
    if kill -0 "$pid" 2>/dev/null; then
        MONITOR_PIDS+=("$pid")
        log_info "dmesg monitor started (PID: ${pid})"
    else
        log_warn "Failed to start dmesg monitor; see ${log_file}"
    fi
}

start_resource_monitor() {
    local output="${RUN_DIR}/resource_timeseries.csv"
    {
        echo "timestamp,total_mem_mb,used_mem_mb,free_mem_mb,swap_used_mb,load_avg,pytest_workers"
        while true; do
            local stats
            stats=$(free -m | awk 'NR==2 {printf "%s,%s,%s", $2, $3, $4} NR==3 {printf ",%s", $3}')
            local load
            load=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)
            echo "$(date +%Y-%m-%dT%H:%M:%S),${stats},${load},${PYTEST_WORKERS:-0}"
            sleep "${RESOURCE_INTERVAL}"
        done
    } >>"${output}" 2>&1 &
    MONITOR_PIDS+=("$!")
    log_info "Resource monitor writing to ${output}"
}

start_process_monitor() {
    local output="${RUN_DIR}/process_snapshot.log"
    (
        while true; do
            {
                echo "==== $(date --iso-8601=seconds) ===="
                ps -eo pid,ppid,%mem,%cpu,rss,cmd --sort=-%mem | head -n 25
                echo
            } >>"${output}"
            sleep "${PROCESS_INTERVAL}"
        done
    ) &
    MONITOR_PIDS+=("$!")
    log_info "Process monitor writing to ${output}"
}

start_monitors() {
    start_dmesg_monitor
    start_resource_monitor
    start_process_monitor
}

stop_monitors() {
    for pid in "${MONITOR_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
}

print_quick_summary() {
    if [ -f "${RUN_DIR}/pytest_progress.jsonl" ]; then
        log_info "Last recorded tests:"
        tail -n 5 "${RUN_DIR}/pytest_progress.jsonl"
    fi
    if [ -f "${RUN_DIR}/resource_timeseries.csv" ]; then
        log_info "Recent resource samples:"
        tail -n 5 "${RUN_DIR}/resource_timeseries.csv"
    fi
}

cleanup() {
    local exit_code=$?
    if [ "${TEST_EXIT_CODE_SET}" -eq 1 ]; then
        exit_code=${TEST_EXIT_CODE}
    fi

    stop_monitors
    sync || true

    log_info "Exit code: ${exit_code}"
    log_info "Artifacts stored in ${RUN_DIR}"
}

trap cleanup EXIT INT TERM

write_system_snapshot
start_monitors

set +e
set +o pipefail
"${TEST_COMMAND[@]}" 2>&1 | tee "${RUN_DIR}/test_output.log"
TEST_EXIT_CODE=${PIPESTATUS[0]}
TEST_EXIT_CODE_SET=1
set -e
set -o pipefail

print_quick_summary

exit ${TEST_EXIT_CODE}
