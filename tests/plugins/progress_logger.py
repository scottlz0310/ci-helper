from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import IO, Any

import pytest

try:  # pragma: no cover - Windows互換
    import resource
except ImportError:  # pragma: no cover - Windows互換
    resource = None  # type: ignore[assignment]


_PROGRESS_LOG_PATH = os.environ.get("CI_HELPER_PROGRESS_LOG")
_PROGRESS_META_PATH = os.environ.get("CI_HELPER_PROGRESS_META")
_PROGRESS_COMMAND = os.environ.get("CI_HELPER_PROGRESS_COMMAND") or " ".join(sys.argv)
_PROGRESS_RUN_ID = os.environ.get("CI_HELPER_PROGRESS_RUN_ID")
_PROGRESS_FSYNC = os.environ.get("CI_HELPER_PROGRESS_FSYNC", "1").lower() not in {"0", "false", "no"}
if not _PROGRESS_META_PATH and _PROGRESS_LOG_PATH:
    _PROGRESS_META_PATH = str(Path(_PROGRESS_LOG_PATH).with_suffix(".meta.json"))
_SESSION_MONO_START = time.monotonic()
_LOG_STATE: dict[str, IO[str] | None] = {"handle": None}
_LOG_LOCK = threading.Lock()


def _progress_enabled() -> bool:
    return bool(_PROGRESS_LOG_PATH)


def _ensure_log_open() -> None:
    if _LOG_STATE["handle"] or not _progress_enabled():
        return

    path = Path(_PROGRESS_LOG_PATH)  # type: ignore[arg-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_STATE["handle"] = path.open("a", encoding="utf-8")


def _write_event(event: str, payload: dict[str, Any]) -> None:
    if not _progress_enabled():
        return

    _ensure_log_open()
    handle = _LOG_STATE["handle"]
    if handle is None:
        return

    entry: dict[str, Any] = {
        "ts": datetime.now().isoformat(),
        "event": event,
        "run_id": _PROGRESS_RUN_ID,
    }
    entry.update(payload)

    line = json.dumps(entry, ensure_ascii=False)
    with _LOG_LOCK:
        handle.write(line + "\n")
        handle.flush()
        if _PROGRESS_FSYNC:
            os.fsync(handle.fileno())


def _resource_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if resource is not None:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        snapshot["rss_mb"] = round(usage.ru_maxrss / 1024, 3)
        snapshot["user_cpu"] = round(usage.ru_utime, 4)
        snapshot["sys_cpu"] = round(usage.ru_stime, 4)
    try:
        snapshot["open_fds"] = len(os.listdir("/proc/self/fd"))
    except OSError:
        snapshot["open_fds"] = None
    return snapshot


def _metadata_args(args: Iterable[str] | None) -> list[str]:
    if args is None:
        return [str(arg) for arg in sys.argv[1:]]
    return [str(arg) for arg in args]


def _write_metadata(args: Iterable[str] | None = None) -> None:
    if not _PROGRESS_META_PATH:
        return

    data = {
        "created_at": datetime.now().isoformat(),
        "run_id": _PROGRESS_RUN_ID,
        "command": _PROGRESS_COMMAND,
        "python": sys.version,
        "pytest": pytest.__version__,
        "platform": platform.platform(),
        "args": _metadata_args(args),
    }

    path = Path(_PROGRESS_META_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pytest_configure(config: pytest.Config) -> None:
    if not _progress_enabled():
        return

    try:
        args = config.invocation_params.args
    except AttributeError:
        args = None
    _write_metadata(args)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    if not _progress_enabled():
        return

    _write_metadata(session.config.invocation_params.args)
    _write_event(
        "session_start",
        {
            "command": _PROGRESS_COMMAND,
            "total_tests": session.testscollected,
            "platform": platform.platform(),
        },
    )


def pytest_runtest_logstart(
    nodeid: str,
    location: tuple[str, int, str],
) -> None:
    if not _progress_enabled():
        return

    _write_event(
        "test_start",
        {
            "nodeid": nodeid,
            "location": list(location),
            "resources": _resource_snapshot(),
        },
    )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if not _progress_enabled():
        return

    payload: dict[str, Any] = {
        "nodeid": report.nodeid,
        "phase": report.when,
        "outcome": report.outcome,
        "duration": round(report.duration, 4),
        "resources": _resource_snapshot(),
        "worker": os.environ.get("PYTEST_XDIST_WORKER"),
    }
    if report.failed:
        failure_text = getattr(report, "longreprtext", None)
        if failure_text:
            payload["failure"] = failure_text[-2000:]

    _write_event("test_report", payload)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _progress_enabled():
        return

    failed = getattr(session, "testsfailed", None)
    _write_event(
        "session_finish",
        {
            "exitstatus": exitstatus,
            "duration": round(time.monotonic() - _SESSION_MONO_START, 3),
            "failed": failed,
        },
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    _ = config  # 引数未使用のlint回避
    handle = _LOG_STATE["handle"]
    if handle:
        handle.close()
        _LOG_STATE["handle"] = None
