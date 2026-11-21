"""Bounded process/file helpers for the separately labelled independent check."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from datetime import datetime, timezone

SCHEMA = "INDEPENDENT_KERNEL_OBJECT_COMBINED_PROOF_V1"
CHECKER_HEAD = "cd2eceab2e9b10404c663b468639c8aa99d0d1f2"
CHECKER_URL = "https://github.com/leanprover/con-leche.git"
RUNTIME_NAME = "lean-4.36.0-linux"
RUNTIME_URL = "https://github.com/leanprover/lean4/releases/download/v4.36.0/lean-4.36.0-linux.tar.zst"
RUNTIME_SHA = "2b7ab1ed8b92d2e6abfaf41344823b510064dbc9c0260cac73eb496ab2dea6eb"
RUNTIME_BYTES = 607649028
MODULAR_RUNNER_SHA = "cf300d15b9aa01d1a18094e669b89d7b375117df4cc03643990058d38d397639"

class Failure(RuntimeError):
    pass

def require(ok, message):
    if not ok:
        raise Failure(message)

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result

def read_json(path, max_bytes=256 << 20):
    path = Path(path)
    require(path.is_file() and 0 < path.stat().st_size <= max_bytes, "Missing/oversize JSON: " + str(path))
    return json.loads(path.read_text(), object_pairs_hook=pairs)

def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)

def clean_env(prefix=None, jobs=1):
    require(not any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_AUDIT", "DYLD_INSERT_LIBRARIES")),
            "Inherited dynamic-loader injection is forbidden")
    env = dict(os.environ)
    for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LAKE_CONFIG", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        env.pop(key, None)
    env["PATH"] = ((str(Path(prefix) / "bin") + os.pathsep) if prefix else "") + "/usr/local/bin:/usr/bin:/bin"
    env.update(LEAN_ABORT_ON_PANIC="1", LEAN_ABORT_ON_NONLINEAR="1", LEAN_NUM_THREADS=str(jobs))
    return env

def stop_group(process):
    if process is None:
        return
    # A leader may exit while a descendant is still alive in the same group.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()

def group_memory(group):
    rss = swap = 0
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        try:
            fields = (item / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) != group:
                continue
            rss += int(fields[21]) * os.sysconf("SC_PAGE_SIZE")
            for line in (item / "status").read_text().splitlines():
                if line.startswith("VmSwap:"):
                    swap += int(line.split()[1]) * 1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return rss, swap

def run(name, argv, *, cwd, env, output, timeout, memory_mib, expected=0, log_limit=64 << 20):
    output = Path(output)
    log = output / (name + ".log")
    require(not log.exists(), "Process log must be fresh: " + str(log))
    row = {"name": name, "command": list(map(str, argv)), "cwd": str(cwd), "status": "RUNNING",
           "expected_exit_code": expected, "log": str(log), "started_utc": utc(),
           "timeout_seconds": timeout, "rss_plus_swap_limit_bytes": memory_mib * 1024**2}
    started = last = time.monotonic()
    process = None
    peak_rss = peak_swap = peak_sum = 0
    try:
        with log.open("xb") as stream:
            process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            while process.poll() is None:
                rss, swap = group_memory(process.pid)
                peak_rss, peak_swap, peak_sum = max(peak_rss, rss), max(peak_swap, swap), max(peak_sum, rss + swap)
                require(rss + swap <= row["rss_plus_swap_limit_bytes"], name + ": memory budget exceeded")
                require(time.monotonic() - started <= timeout, name + ": timeout")
                require(log.stat().st_size <= log_limit, name + ": diagnostic limit exceeded")
                if time.monotonic() - last >= 30:
                    print(f"{name}: {time.monotonic()-started:.1f}s RSS={rss/2**30:.2f} GiB swap={swap/2**30:.2f} GiB", flush=True)
                    last = time.monotonic()
                time.sleep(0.25)
        # Stop descendants before the final diagnostic-size check and read.
        stop_group(process)
        require(log.stat().st_size <= log_limit, name + ": final diagnostic limit exceeded")
        require(process.returncode == expected, name + ": unexpected exit " + str(process.returncode))
        row["status"] = "PASS"
        return row, log.read_text(errors="replace")
    except BaseException as exc:
        row.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAIL",
                   failure=str(exc), exception_type=type(exc).__name__)
        raise
    finally:
        stop_group(process)
        row.update(exit_code=process.returncode if process else None, ended_utc=utc(),
                   elapsed_seconds=round(time.monotonic()-started, 3),
                   max_sampled_rss_bytes=peak_rss, max_sampled_swap_bytes=peak_swap,
                   max_sampled_rss_plus_swap_bytes=peak_sum)
        if log.exists():
            row["log_sha256"] = sha(log)
        write_json(output / (name + ".json"), row)

def git(repo, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=repo, env=clean_env(), timeout=120, text=True).strip()

def clean_checkout(repo, expected):
    require(git(repo, "rev-parse", "HEAD") == expected, "Source HEAD changed: " + str(repo))
    require(not git(repo, "diff", "HEAD", "--"), "Tracked source changed: " + str(repo))

def safe_relative(value):
    require(isinstance(value, str) and value and not value.startswith("/") and
            all(p not in ("", ".", "..") for p in value.split("/")), "Unsafe relative inventory path")
    return value

def file_inventory(root):
    root = Path(root).resolve()
    entries = {}
    for directory, dirs, names in os.walk(root):
        for name in dirs:
            path = Path(directory) / name
            require(not path.is_symlink(), "Directory symlink in runtime inventory: " + str(path))
        for name in names:
            path = Path(directory) / name
            require(path.is_file() and path.resolve().is_relative_to(root), "Unsafe runtime file: " + str(path))
            entries[path.relative_to(root).as_posix()] = {"sha256": sha(path), "bytes": path.stat().st_size,
                "symlink": os.readlink(path) if path.is_symlink() else None}
    return entries

def verify_file_inventory(root, inventory):
    actual = file_inventory(root)
    require(actual == inventory, "Runtime file set, bytes or symlink targets changed: " + str(root))
    return len(actual)
