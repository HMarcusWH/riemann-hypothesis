"""Bounded optional observations copied from the reviewed prior diagnostic.
Only the four smaps checkpoints change to include the late 1800s window.
"""
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import re
import threading
import time

SMAPS_CHECKPOINTS = (0, 2, 16, 50)

class InputFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise InputFailure(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def optional_read(path, limit=1 << 20):
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            return {"coverage": "TRUNCATED", "limit_bytes": limit,
                    "text": data[:limit].decode(errors="replace")}
        return {"coverage": "AVAILABLE", "text": data.decode(errors="replace")}
    except OSError as exc:
        return {"coverage": "UNAVAILABLE", "error_type": type(exc).__name__, "errno": exc.errno}


def host_details():
    release = os.uname().release
    configs = {}
    for path in ("/proc/config.gz", "/boot/config-" + release):
        try:
            opener = gzip.open if path.endswith(".gz") else open
            with opener(path, "rb") as stream:
                data = stream.read((2 << 20) + 1)
            require(len(data) <= 2 << 20, "Kernel configuration exceeds observation bound")
            selected = [line for line in data.decode().splitlines() if re.match(
                r"(?:# )?CONFIG_(?:MEMCG|CGROUPS|SWAP|PSI|STACKTRACE|SCHEDSTATS|PROC_PAGE_MONITOR|SQUASHFS|ZSTD).*", line)]
            configs[path] = {"coverage": "AVAILABLE", "selected_config_lines": selected}
        except (OSError, UnicodeError, InputFailure) as exc:
            configs[path] = {"coverage": "UNAVAILABLE", "error_type": type(exc).__name__}
    return {"utc": utc(), "kernel": release,
            "kernel_config": configs,
            "vm": {path: optional_read(path) for path in
                   ("/proc/sys/vm/swappiness", "/proc/sys/vm/page-cluster", "/proc/swaps")},
            "coverage_note": "Optional reads report denial/missing/truncation explicitly; unavailable is never zero"}


def cgroup_observations(membership):
    if membership.get("coverage") != "AVAILABLE":
        return {"coverage": "UNAVAILABLE", "reason": "process cgroup membership unreadable"}
    lines = [line[3:] for line in membership["text"].splitlines() if line.startswith("0::")]
    if len(lines) != 1 or ".." in Path(lines[0]).parts:
        return {"coverage": "UNAVAILABLE", "reason": "no unique safe unified cgroup path"}
    root = Path("/sys/fs/cgroup")
    actual = root / lines[0].lstrip("/")
    ancestors = [actual, *(p for p in actual.parents if p.is_relative_to(root))]
    rows = []
    for path in ancestors[:16]:
        row = {"path": str(path), "values": {name: optional_read(path / name) for name in
               ("memory.current", "memory.max", "memory.high", "memory.low", "memory.min",
                "memory.swap.current", "memory.swap.max", "memory.events", "memory.events.local", "cpu.stat")}}
        memory = optional_read(path / "memory.stat")
        if memory["coverage"] == "AVAILABLE":
            keys = {"anon", "file", "file_mapped", "inactive_file", "active_file", "pgscan", "pgsteal",
                    "pgscan_kswapd", "pgscan_direct", "pgsteal_kswapd", "pgsteal_direct",
                    "workingset_refault_file", "workingset_activate_file", "workingset_restore_file"}
            memory["selected_counters"] = {parts[0]: parts[1] for line in memory.pop("text").splitlines()
                                            if len(parts := line.split()) == 2 and parts[0] in keys}
        row["memory_stat"] = memory
        rows.append(row)
    return {"coverage": "COLLECTED_WITH_PER_FIELD_COVERAGE", "process_membership": lines[0],
            "ancestors": rows, "ancestor_limit": 16, "ancestors_truncated": len(ancestors) > 16,
            "scope": "Hierarchical counters can cover other processes; they are not child-only measurements"}


class SupplementalSampler:
    """Separate read-only observer; never patches or changes the original watchdog."""
    def __init__(self, output, process_name):
        self.output, self.process_name = output, process_name
        self.stop = threading.Event()
        self.result = {"status": "NOT_STARTED", "snapshots": 0, "initial_record_retries": 0,
                       "initial_record_retry_limit_seconds": 5}
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        self.result["status"] = "RUNNING"
        try:
            identity = None
            first_incomplete_record = None
            with (self.output / "optional-proc-observations.jsonl").open("x") as out:
                while not self.stop.is_set():
                    path = self.output / (self.process_name + ".process.json")
                    if path.exists():
                        # The frozen monitor's first open('x')/json.dump is not
                        # atomic. Later PID/status replacements are atomic.
                        try:
                            data = json.loads(path.read_text())
                        except (FileNotFoundError, json.JSONDecodeError) as exc:
                            if identity is not None:
                                raise
                            now = time.monotonic()
                            if first_incomplete_record is None:
                                first_incomplete_record = now
                            self.result["initial_record_retries"] += 1
                            self.result["initial_record_last_error_type"] = type(exc).__name__
                            self.result["initial_record_retry_elapsed_seconds"] = now - first_incomplete_record
                            require(now - first_incomplete_record < 5,
                                    "Initial optional-observer process record did not become readable in five seconds")
                            self.stop.wait(0.05)
                            continue
                        pid = data.get("pid")
                        if pid:
                            proc = Path("/proc") / str(pid)
                            try:
                                stat = (proc / "stat").read_text()
                                start = stat[stat.rfind(")") + 2:].split()[19]
                                observed = (pid, start)
                                if identity is None:
                                    identity = observed
                                if identity != observed:
                                    raise InputFailure("Optional sampler process identity changed")
                                tids = sorted((proc / "task").iterdir(), key=lambda p: int(p.name))
                                membership = optional_read(proc / "cgroup")
                                status = optional_read(proc / "status")
                                if status["coverage"] == "AVAILABLE":
                                    status["selected_lines"] = [line for line in status.pop("text").splitlines()
                                                                 if re.match(r"(?:State|Threads|Vm[A-Za-z]+|RssAnon|RssFile|RssShmem):", line)]
                                row = {"utc": utc(), "pid": pid, "start_ticks": start, "status": status,
                                       "smaps_rollup": (optional_read(proc / "smaps_rollup") if self.result["snapshots"] in SMAPS_CHECKPOINTS
                                                          else {"coverage": "NOT_SCHEDULED", "maximum_checkpoints": 4}),
                                       "cgroup": membership,
                                       "thread_count": len(tids), "thread_limit": 64,
                                       "threads_truncated": len(tids) > 64,
                                       "threads": [{"tid": int(p.name), "wchan": optional_read(p / "wchan"),
                                                    "stack": optional_read(p / "stack", 65536)} for p in tids[:64]],
                                       "cgroup_v2_hierarchy": cgroup_observations(membership)}
                                after = (proc / "stat").read_text()
                                after_start = after[after.rfind(")") + 2:].split()[19]
                                row["identity_after_reads"] = {"pid": pid, "start_ticks": after_start,
                                                                "unchanged": after_start == start}
                                require(after_start == start, "Optional sampler identity changed during reads")
                            except OSError as exc:
                                row = {"utc": utc(), "pid": pid, "coverage": "UNAVAILABLE",
                                       "error_type": type(exc).__name__, "errno": exc.errno}
                            encoded = json.dumps(row) + "\n"
                            if out.tell() + len(encoded.encode()) > 16 << 20:
                                self.result["status"] = "INCOMPLETE_SIZE_LIMIT"
                                return
                            out.write(encoded); out.flush()
                            self.result["snapshots"] += 1
                            if self.stop.wait(30):
                                break
                            continue
                    self.stop.wait(0.5)
            self.result["status"] = ("COLLECTION_COMPLETED_WITH_PER_FIELD_COVERAGE" if identity is not None
                                     else "UNAVAILABLE_NO_PROCESS_ID_OBSERVED")
        except Exception as exc:
            self.result.update(status="UNAVAILABLE", error_type=type(exc).__name__, error=str(exc))

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.result["status"] = "INCOMPLETE_OBSERVER_STOP"
        return self.result
