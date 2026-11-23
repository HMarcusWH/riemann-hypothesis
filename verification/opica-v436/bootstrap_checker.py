#!/usr/bin/env python3
"""Fetch the pinned official runtime and freshly build the unchanged independent checker."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
import time
import urllib.request
import zstandard
from common import *

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=2400)
    p.add_argument("--memory-mib", type=int, default=10000)
    p.add_argument("--min-free-gib", type=int, default=6)
    args = p.parse_args()
    work = args.work.resolve()
    require(not work.exists() or not any(work.iterdir()), "Checker bootstrap work directory must be fresh")
    work.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": "OPICA20_PINNED_INDEPENDENT_CHECKER_BUILD_V1", "status": "RUNNING",
        "scope": "Fresh unchanged checker/reader executable build; no theorem claim or metatheory rebuild claim",
        "started_utc": utc(), "source_head": CHECKER_HEAD, "runtime_archive_sha256": RUNTIME_SHA,
        "runtime_archive_bytes": RUNTIME_BYTES, "runtime_url": RUNTIME_URL,
        "bootstrap_sha256": sha(Path(__file__)), "common_sha256": sha(Path(__file__).with_name("common.py"))}
    code = 1
    try:
        require(all(x > 0 for x in (args.timeout, args.memory_mib, args.min_free_gib)), "Invalid bootstrap budget")
        require(shutil.disk_usage(work).free >= args.min_free_gib * 2**30, "Insufficient free disk for independent tools")
        archive = work / (RUNTIME_NAME + ".tar.zst")
        h, size = hashlib.sha256(), 0
        started = last = time.monotonic()
        with urllib.request.urlopen(RUNTIME_URL, timeout=30) as source, archive.open("xb") as target:
            while data := source.read(4 << 20):
                size += len(data)
                require(size <= RUNTIME_BYTES and time.monotonic()-started <= 1200, "Runtime download size/time limit")
                h.update(data); target.write(data)
                if time.monotonic()-last >= 30:
                    print(f"Runtime download: {size} / {RUNTIME_BYTES} bytes", flush=True); last=time.monotonic()
        require(size == RUNTIME_BYTES and h.hexdigest() == RUNTIME_SHA, "Official runtime archive binding failed")
        require(zstandard.__version__ == "0.25.0", "Use the pinned zstandard 0.25.0 transport dependency")
        with archive.open("rb") as source:
            params = zstandard.get_frame_parameters(source.read(64))
            require(params.window_size <= 1 << 30, "Official runtime zstd frame exceeds 1 GiB window bound")
            source.seek(0)
            with zstandard.ZstdDecompressor(max_window_size=1 << 30).stream_reader(source) as decoded:
                with tarfile.open(fileobj=decoded, mode="r|") as tar:
                    seen, total = set(), 0
                    for member in tar:
                        name = member.name.rstrip("/")
                        safe_relative(name)
                        require(name == RUNTIME_NAME or name.startswith(RUNTIME_NAME + "/"), "Runtime archive path escaped prefix")
                        require(name not in seen, "Duplicate runtime archive member")
                        seen.add(name)
                        require(member.isdir() or member.isfile() or member.issym() or member.islnk(), "Special runtime archive member")
                        total += member.size
                        require(0 <= member.size <= 1 << 30 and total <= 5 << 30, "Runtime expanded-size limit")
                        tar.extract(member, work, filter="data")
        runtime, source = work / RUNTIME_NAME, work / "con-leche"
        inventory = file_inventory(runtime)
        require(len(inventory) > 1000 and "lib/lean/libleanshared.so" in inventory, "Incomplete official runtime")
        write_json(work / "RUNTIME_FILES.json", inventory)
        env = clean_env(runtime, jobs=2)
        run("git_init", ["git", "init", source], cwd=work, env=env, output=work, timeout=60, memory_mib=512)
        run("git_remote", ["git", "-C", source, "remote", "add", "origin", CHECKER_URL], cwd=work, env=env,
            output=work, timeout=60, memory_mib=512)
        run("git_fetch", ["git", "-C", source, "fetch", "--depth=1", "origin", CHECKER_HEAD], cwd=work,
            env=env, output=work, timeout=300, memory_mib=1024)
        run("git_checkout", ["git", "-C", source, "checkout", "--detach", CHECKER_HEAD], cwd=work,
            env=env, output=work, timeout=60, memory_mib=512)
        clean_checkout(source, CHECKER_HEAD)
        require((source / "lean-toolchain").read_text().strip() == "leanprover/lean4:v4.36.0", "Checker toolchain pin changed")
        source_files = {name: sha(source / name) for name in git(source, "ls-files").splitlines()}
        write_json(work / "CHECKER_SOURCE_FILES.json", source_files)
        row, text = run("build_checker", [runtime / "bin/lake", "--no-cache", "--wfail", "build", "con-leche", "olean-compare"],
            cwd=source, env=env, output=work, timeout=args.timeout, memory_mib=args.memory_mib)
        require("Build completed successfully" in text, "Checker build success marker absent")
        clean_checkout(source, CHECKER_HEAD)
        require(source_files == {name: sha(source / name) for name in git(source, "ls-files").splitlines()}, "Checker source changed during build")
        verify_file_inventory(runtime, inventory)
        tools = {}
        for name in ("con-leche", "olean-compare"):
            path = source / ".lake/build/bin" / name
            require(path.is_file() and path.stat().st_size > 0, "Fresh tool absent")
            tools[name] = {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}
        receipt.update(status="PASS", runtime=str(runtime), source=str(source), source_tree=git(source,"rev-parse","HEAD^{tree}"),
            runtime_inventory=str(work/"RUNTIME_FILES.json"), runtime_inventory_sha256=sha(work/"RUNTIME_FILES.json"),
            source_inventory=str(work/"CHECKER_SOURCE_FILES.json"), source_inventory_sha256=sha(work/"CHECKER_SOURCE_FILES.json"),
            tools=tools, build=row, archive=str(archive), host_system_libraries_and_hardware_trusted=True)
        code = 0
    except BaseException as exc:
        receipt.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAIL", failure=str(exc), exception_type=type(exc).__name__)
        print(str(exc), flush=True)
        if isinstance(exc, KeyboardInterrupt): code=130
    finally:
        receipt.update(ended_utc=utc(), exit_code=code)
        write_json(work / "BOOTSTRAP_RECEIPT.json", receipt)
        print(receipt["status"] + ": pinned independent checker bootstrap", flush=True)
    return code

if __name__ == "__main__":
    raise SystemExit(main())
