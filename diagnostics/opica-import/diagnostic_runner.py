#!/usr/bin/env python3
"""Reproduce the stock guard import's inputs and observe its phases, without acceptance.

This deliberately does not instantiate ModularGate or write a modular-stage
receipt. It uses the immutable bootstrap's source/runtime checks and the exact
unmodified process monitor. Four native-only modules are freshly compiled with
the old compile_module flags; no guard or closed theorem object is constructed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

BASE_HEAD = "2d54e707ab9ac8a50c2ed3cb2fd72b4171cb21bf"
SUPPLIER_SRC_TREE = "24df20b62d9976ccd20da819bc20b16f808f0fdd"
PROBE_SHA = "4e760679e151cd67287a5f3d8a97818aeeda4da9ae77295bfa8d1bc0bcc87526"
MOUNTED_MANIFEST_SHA = "4b2a2b978e16e54c663fd5c19f4cab3cd8d5a6d5a0141468efefdc6f07d1e411"
STORE_ARCHIVE_SHA = "953bab5386a7849527a11960f80a2fab427c49c637d6e94cc75788dd8f40196b"
SOURCE_HASHES = {
    "opica-step4/modular/verify_modular.py": "7953a9d18c63c6567595533b9028a6f176599fe1fbca65c0f84773e1211267b9",
    "opica-step4/modular/monitored_process.py": "37cc7e705d660745bc0a6b2dc556a38761c1460c6e7e30fd9597ccae40ca0709",
    "opica-step4/portable_gate/verify_combined.py": "a01ac482dd59444b2313dc525b63d22036de892a3076a23a06c80514d7df78ca",
    "opica-step4/portable_gate/GATE_SPEC.json": "771b194e8330a6844705178a5bc4cfc09ece629c9a2c88031e1bb74615640862",
    "opica-step4/native_bootstrap/bootstrap_native.py": "1a9e8c7643bf122c7b855433f47460462501ac1ecefaefe54c6b459ea7443b66",
    "opica-step4/native_bootstrap/runtime_files.json": "550bbf7a1fc8e2549ecf2d122ff5bfa2007f71d78e3ce1dba42d02fb1ae72793",
    "opica-step4/native_bootstrap/native_sources.json": "3b6faeca7c42978a5e183f8d33bd921af2dc99f058ba4e4724d2397c271d3ae6",
    "opica-step4/native_bootstrap/lake-manifest.json": "391f2a0f7147306be70a47338cb31829e652981b9db028af02e475b73368c5f4",
    "opica-step4/native_bootstrap/trusted_objects.json.gz": "a60772ae619d879d58690a3318f9b791e91826d10be5bb09ae4a07923797ab60",
    "lean-toolchain": "3aac669c7a910ec2389f4e4f921b605adf6ebf2d1e0c9b9cd0be4d33f3f5db71",
    "lake-manifest.json": "fee57ee9ed399d0a638ca955e5ad40a37a36eeb9b6dfd9f5964114fa7bbe4774",
    "lakefile.toml": "32af981ad33964a949f3e4d1e188e4afd0f85fecf6bf86e8ed133f00f16727ca",
}
CANONICAL = {
    "OPICAStep4.ReceiverAudit": ("99810c3fd20182630ec6b0fcaf6e67c6be3ec0b04171371ba5d723b2dcc4745b", "a8d58f99a73a4dbddad42d4d92b2be978b143cc37bd3bc71eaf5d7616d71b4c4"),
    "OPICAStep4.ClaimFingerprint": ("255a46d2926e713ad5d41083ef9f818b7e415d89c8a96d63540486d73a56fd56", "a9d5350b6d7745321beba7ec5d224291e246333c92b38dbc31ccf0fe2276dac6"),
    "OPICAStep4.BoundaryFlatCharacterization": ("e19bfb13fcb523930617aae99c9d1190cccb1ec3915feae610f7195c68bbef61", "8ce812f279c80945ba2727e0dea9a9a0a15627e0d8b1b272e44f5fa7e2d045ca"),
    "OPICAStep4.NativeValidated": ("490d4dedfbf28088dbb85f3567c9acc93401b15a19d23e5399eea79bd32e03cf", "155327653a0033e12f456ed602d69f89c1277f678a5904a09db25a53bd248fa3"),
}
OVERRIDE_KEYS = ("LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
                 "DYLD_LIBRARY_PATH", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
                 "LAKE_CONFIG", "ELAN_TOOLCHAIN", "LEAN_PLUGIN_PATH")
RESOURCE_KEYS = ("PATH", "LD_LIBRARY_PATH", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
                 "LEAN_NUM_THREADS", "LEAN_ABORT_ON_PANIC")


class InputFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise InputFailure(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def reject_overrides(env):
    present = [key for key in OVERRIDE_KEYS if env.get(key)]
    require(not present, "Unreviewed loader/import override keys: " + ", ".join(present))


class Bindings:
    """Current byte/path identities, with a separate final integrity comparison."""
    def __init__(self):
        self.rows = {}

    def add(self, path, expected=None, size=None):
        path = Path(path).absolute()
        require(path.is_file(), "Required input/product is missing: " + str(path))
        actual = digest(path)
        require(expected is None or actual == expected, "SHA256 mismatch: " + str(path))
        require(size is None or path.stat().st_size == size, "Size mismatch: " + str(path))
        row = {"path": str(path), "resolved": str(path.resolve()),
               "sha256": actual, "bytes": path.stat().st_size}
        require(str(path) not in self.rows or self.rows[str(path)] == row,
                "Input changed between bindings: " + str(path))
        self.rows[str(path)] = row
        return actual

    def verify(self):
        failures = []
        for row in self.rows.values():
            path = Path(row["path"])
            try:
                same = (str(path.resolve()) == row["resolved"] and
                        path.stat().st_size == row["bytes"] and digest(path) == row["sha256"])
                if not same:
                    failures.append({"path": str(path), "error": "identity changed"})
            except OSError as exc:
                failures.append({"path": str(path), "error_type": type(exc).__name__})
        return {"status": "PASS" if not failures else "FAIL", "files": len(self.rows),
                "failures": failures}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(argv, cwd):
    result = subprocess.run(list(map(str, argv)), cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    require(result.returncode == 0, "Read-only inspection failed: " + repr(argv) + "\n" + result.stderr[-2000:])
    return result.stdout.strip()


def source_inputs(supplier, bindings):
    for relative, expected in SOURCE_HASHES.items():
        bindings.add(supplier / relative, expected)
    git = lambda *args: inspect(["git", "-C", supplier, *args], supplier)
    head = git("rev-parse", "HEAD")
    require(git("rev-parse", "HEAD:src") == SUPPLIER_SRC_TREE, "Original supplier source tree changed")
    git("merge-base", "--is-ancestor", BASE_HEAD, "HEAD")
    for line in git("diff", "--name-status", BASE_HEAD, "HEAD").splitlines():
        fields = line.split("\t")
        require(len(fields) == 2 and fields[0] == "A" and
                (fields[1].startswith("diagnostics/opica-import/") or
                 fields[1] == ".github/workflows/opica-import-diagnostic.yml"),
                "Diagnostic commit changes an existing source or an unreviewed path")
    require(not git("status", "--porcelain", "--untracked-files=no"),
            "Tracked supplier checkout is dirty")
    bundle = supplier / "opica-step4/native_bootstrap"
    # Executable helpers are imported only after their byte identities passed.
    boot = load_module("opica_diagnostic_frozen_bootstrap", bundle / "bootstrap_native.py")
    monitor = load_module("opica_diagnostic_frozen_monitor", supplier / "opica-step4/modular/monitored_process.py")
    return boot, monitor, {"head": head, "base": BASE_HEAD, "src_tree": SUPPLIER_SRC_TREE}


def validate_native_receipt(data, boot, runtime, frozen, native, native_lib, bindings):
    expected = {"schema": 1, "status": "PASS", "exit_code": 0,
                "native_head": boot.NATIVE_HEAD, "native_tree": boot.NATIVE_TREE,
                "common_mathlib_rev": boot.MATHLIB, "source_unchanged": True,
                "c1_closed": False, "rh_closed": False, **runtime}
    require(all(data.get(key) == value for key, value in expected.items()),
            "Native 572-module build receipt identity/status mismatch")
    rows = data.get("modules")
    require(isinstance(rows, list) and len(rows) == 572, "Native receipt must cover 572 modules")
    names = [row.get("module") for row in rows]
    require(len(set(names)) == 572 and set(names) == set(frozen["modules"]),
            "Native receipt closure differs from frozen source inventory")
    for row in rows:
        name = row["module"]
        source = native / boot.module_path(name)
        obj = native_lib / boot.module_path(name, ".olean")
        require(row.get("preexisting_object") is False and row.get("source_unchanged") is True,
                "Native receipt lacks fresh unchanged provenance: " + name)
        require(row.get("source_path") == str(source) and row.get("object_path") == str(obj),
                "Native receipt belongs to different input paths: " + name)
        require(row.get("process", {}).get("status") == "PASS" and
                row.get("process", {}).get("exit_code") == 0, "Native compile did not pass: " + name)
        require(row.get("source_sha256") == frozen["modules"][name], "Frozen source hash mismatch: " + name)
        bindings.add(source, row["source_sha256"])
        bindings.add(obj, row.get("object_sha256"))
        require(isinstance(row.get("object_sha256"), str), "Missing native object identity")
        for suffix, side in row.get("sidecars", {}).items():
            require(suffix in (".olean.private", ".olean.server", ".ir", ".ilean"), "Unknown native sidecar")
            extra = native_lib / boot.module_path(name, suffix)
            require(side.get("path") == str(extra), "Native sidecar path differs")
            bindings.add(extra, side["sha256"])


def mount_state(store, image):
    raw = inspect(["findmnt", "--json", "--target", store, "--output", "TARGET,SOURCE,FSTYPE,OPTIONS"], store)
    rows = json.loads(raw).get("filesystems", [])
    require(len(rows) == 1, "Mounted store has no unique mount record")
    row = rows[0]
    require(Path(row["target"]).resolve() == store and row["fstype"] == "squashfs" and
            "ro" in row["options"].split(","), "Store is not the exact read-only SquashFS mount")
    source = row["source"]
    require(bool(re.fullmatch(r"/dev/loop[0-9]+", source)), "Store is not backed by the expected loop image")
    backing = Path("/sys/class/block") / Path(source).name / "loop/backing_file"
    require(Path(backing.read_text().strip()).resolve() == image,
            "Mounted loop device does not point to the recorded image")
    stat = image.stat()
    return {**row, "image": str(image), "image_device": stat.st_dev, "image_inode": stat.st_ino,
            "image_bytes": stat.st_size, "image_mtime_ns": stat.st_mtime_ns}


def validate_store(args, bindings):
    store = args.mounted_store
    bindings.add(args.mounted_receipt)
    bindings.add(args.store_receipt)
    verified = json.loads(args.mounted_receipt.read_text())
    receipt = json.loads(args.store_receipt.read_text())
    require(verified.get("status") == "PASS" and verified.get("files") == 350374 and
            verified.get("manifest_sha256") == MOUNTED_MANIFEST_SHA,
            "Full mounted-file verification receipt missing or wrong")
    require(receipt.get("status") == "VERIFIED_ARCHIVE_REPACKED" and
            receipt.get("proof_validity_established") is False and receipt.get("production_supplier") is True and
            receipt.get("archive_sha256") == STORE_ARCHIVE_SHA and receipt.get("files") == 350374 and
            receipt.get("expanded_bytes") == 99269509951 and
            receipt.get("mounted_manifest_sha256") == MOUNTED_MANIFEST_SHA,
            "Original supplier store receipt identity mismatch")
    command = receipt.get("mksquashfs_command", [])
    require(command.count("-b") == 1 and command[command.index("-b") + 1] == "64K",
            "Diagnostic requires the same 64KiB SquashFS block size")
    require(args.store_receipt.name.endswith(".receipt.json"), "Unexpected store receipt filename")
    image = args.store_receipt.with_name(args.store_receipt.name[:-len(".receipt.json")])
    manifest = image.with_name(image.name + ".files.sha256")
    bindings.add(manifest, MOUNTED_MANIFEST_SHA)
    require(image.is_file() and image.stat().st_size == receipt.get("image_bytes"), "Recorded image size differs")
    state = mount_state(store, image)
    main_sha = None
    count = 0
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, "Malformed original mounted manifest")
        relative = Path(match[2])
        require(not relative.is_absolute() and ".." not in relative.parts, "Unsafe manifest path")
        count += 1
        if relative.as_posix() == "Main.olean":
            require(main_sha is None, "Duplicate Main object")
            main_sha = match[1]
    require(count == 350374 and main_sha is not None, "Mounted manifest count or Main object differs")
    bindings.add(store / "Main.olean", main_sha)
    return {"mount": state, "full_verification_receipt": str(args.mounted_receipt),
            "manifest_sha256": MOUNTED_MANIFEST_SHA, "files": count,
            "image_sha256_from_repack_receipt": receipt["image_sha256"],
            "all_file_hashes_recomputed_by_this_runner": False,
            "trust_boundary": "Fresh workflow full-file verification and unchanged read-only mounted image; hashes establish custody, not proof correctness"}


def checked_environment(boot, rt, root, allowed):
    env = boot.lake_env(rt, root, 2)
    roots = list(dict.fromkeys((root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
                              for p in env.get("LEAN_PATH", "").split(os.pathsep) if p))
    require(roots and set(roots) <= allowed, "Lake exposed an unregistered import root")
    require(Path(boot.inspect([rt / "lean", "--print-prefix"], root, env)).resolve() == rt.parent,
            "Selected Lean prefix differs from byte-verified stock runtime")
    return env, roots


def require_resolution(module, roots, expected, boot):
    relative = boot.module_path(module, ".olean")
    found = next((root / relative for root in roots if (root / relative).is_file()), None)
    require(found is not None and found.resolve() == expected.resolve(), "Import shadowing/missing module: " + module)


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
                                       "smaps_rollup": (optional_read(proc / "smaps_rollup") if self.result["snapshots"] in (0, 2, 6, 16)
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


def run(args):
    reject_overrides(os.environ)
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    require(not args.output.exists(), "Diagnostic output must be a fresh directory")
    require(not args.output.is_relative_to(args.supplier), "Diagnostic output must be outside supplier source")
    args.output.mkdir(parents=True)
    result = {"schema": "OPICA_STOCK_IMPORT_PHASE_DIAGNOSTIC_V1", "started_utc": utc(),
              "status": "PREPARING", "mode": args.mode, "proof_acceptance": False,
              "step4": "OPEN", "c1": "OPEN", "rh": "OPEN",
              "modular_stage_acceptance": False, "independent_checker_run": False,
              "no_guard_or_closed_object_created": False, "processes": []}
    bindings = Bindings()
    exit_code = 2
    store_before = None
    try:
        boot, monitor, result["supplier"] = source_inputs(args.supplier, bindings)
        bindings.add(Path(__file__))
        bindings.add(args.probe_source, PROBE_SHA)
        rt = args.native_work / "lean-4.33.1-linux/bin"
        native = args.native_work / "native-source"
        integration = args.native_work / "integration"
        native_lib = integration / ".lake/build/lib/lean"
        bundle = args.supplier / "opica-step4/native_bootstrap"
        _, _, frozen = boot.verify_native(native)
        runtime = boot.verify_runtime(rt)
        runtime_manifest = json.loads((bundle / "runtime_files.json").read_text())
        require(len(runtime_manifest["files"]) == 26, "Runtime manifest must contain 26 entries")
        for row in runtime_manifest["files"]:
            bindings.add(rt.parent / row["path"], row["sha256"], row["bytes"])
        result["runtime"] = runtime
        manifest = json.loads((bundle / "lake-manifest.json").read_text())
        require(len(manifest["packages"]) == 9, "Expected exact nine common dependencies")
        bindings.add(integration / "lake-manifest.json", SOURCE_HASHES["opica-step4/native_bootstrap/lake-manifest.json"])
        bindings.add(integration / "lean-toolchain", SOURCE_HASHES["lean-toolchain"])
        bindings.add(integration / "lakefile.toml")
        require((integration / ".lake/packages").resolve() == args.trusted_packages and
                (args.supplier / ".lake/packages").resolve() == args.trusted_packages and
                (args.supplier / ".lake/build/lib/lean").resolve() == args.mounted_store,
                "Package/store bindings differ from explicitly selected paths")
        result["packages"] = boot.verify_package_sources(args.trusted_packages, manifest)
        with gzip.open(bundle / "trusted_objects.json.gz", "rt") as stream:
            references = json.load(stream)
        require(len(references["objects"]) == references["count"] == 20354,
                "Frozen dependency object inventory differs")
        for row in references["objects"]:
            path = args.trusted_packages / row["package"] / ".lake/build/lib/lean" / row["path"]
            bindings.add(path, row["sha256"], row["bytes"])
        result["dependency_reference_objects"] = {k: v for k, v in references.items() if k != "objects"}
        receipt_path = integration / "NATIVE_COMMON_PIN_BUILD.json"
        bindings.add(receipt_path)
        receipt = json.loads(receipt_path.read_text())
        validate_native_receipt(receipt, boot, runtime, frozen, native, native_lib, bindings)
        result["native_build"] = {"receipt": str(receipt_path), "sha256": digest(receipt_path), "modules": 572,
                                  "scope": "Fresh conditional receiver inputs; no closed theorem claim"}
        result["store"] = validate_store(args, bindings)
        store_before = result["store"]["mount"]
        sources, canonical = args.output / "sources", args.output / "canonical-lib"
        sources.mkdir(); canonical.mkdir()
        package_roots = {args.trusted_packages / row["name"] / ".lake/build/lib/lean" for row in manifest["packages"]}
        allowed = {native_lib, rt.parent / "lib/lean", *package_roots}
        canonical_env, roots = checked_environment(boot, rt, integration, allowed)
        require(native_lib in roots, "Native root missing from canonical environment")
        require(all(not p.is_relative_to(args.supplier) for p in roots), "Canonical path enters supplier")
        canonical_roots = list(dict.fromkeys([canonical, *roots, rt.parent / "lib/lean"]))
        canonical_env["LEAN_PATH"] = os.pathsep.join(map(str, canonical_roots))
        for name in frozen["modules"]:
            require_resolution(name, canonical_roots, native_lib / boot.module_path(name, ".olean"), boot)
        for name in manifest["packages"]:
            require(not (args.trusted_packages / name["name"] / ".lake/build/lib/lean/Zeta23").exists(),
                    "Trusted dependency root shadows native namespace")
        result["canonical_environment"] = {k: canonical_env[k] for k in RESOURCE_KEYS if k in canonical_env}

        def execute(name, command, cwd, env):
            row, text = monitor.run(name, command, cwd=cwd, env=env, output=args.output,
                                    timeout=600, memory_mib=50000)
            result["processes"].append({"name": name, "status": row["status"],
                                        "record": str(args.output / (name + ".process.json"))})
            require(row["status"] == "PASS", "Diagnostic preparation process did not finish: " + name)
            return row, text

        comparisons = {}
        for name, (source_sha, round24_sha) in CANONICAL.items():
            relative = boot.module_path(name)
            original = args.supplier / "opica-step4/portable_gate" / relative
            bindings.add(original, source_sha)
            source = sources / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, source)
            bindings.add(source, source_sha)
            obj = canonical / boot.module_path(name, ".olean")
            obj.parent.mkdir(parents=True, exist_ok=True)
            execute("compile_" + name.replace(".", "_"), [rt / "lean", "-j2", "-DwarningAsError=true",
                    "-DrelaxedAutoImplicit=false", "-DmaxHeartbeats=1600000", relative,
                    "-o", obj, "-i", canonical / boot.module_path(name, ".ilean")], sources, canonical_env)
            require(obj.is_file() and (canonical / boot.module_path(name, ".ilean")).is_file(),
                    "Missing fresh canonical compiler product")
            for suffix in (".olean", ".olean.private", ".olean.server", ".ir", ".ilean"):
                path = canonical / boot.module_path(name, suffix)
                if path.exists():
                    bindings.add(path)
            comparisons[name] = {"fresh_sha256": digest(obj), "round24_sha256": round24_sha,
                                  "identical": digest(obj) == round24_sha}
        result["canonical_object_reproduction"] = comparisons
        probe = sources / "ImportPhaseProbe.lean"
        shutil.copyfile(args.probe_source, probe); bindings.add(probe, PROBE_SHA)
        build = args.output / "probe-build"; build.mkdir()
        cfile, olean, executable = build / "ImportPhaseProbe.c", build / "ImportPhaseProbe.olean", build / "import_phase_probe"
        # Exactly the locally checked stock compiler/leanc invocation; no plugin.
        execute("compile_probe", [rt / "lean", "-c", cfile, "-o", olean, probe], sources, canonical_env)
        bindings.add(cfile); bindings.add(olean)
        execute("link_probe", [rt / "leanc", "-O3", "-o", executable, cfile], build, canonical_env)
        bindings.add(executable)
        result["probe"] = {"source_sha256": PROBE_SHA, "executable_sha256": digest(executable),
                            "selection": "exact-guard", "mode": args.mode}
        combined_env, external_roots = checked_environment(boot, rt, args.supplier,
                                                           {args.mounted_store, rt.parent / "lib/lean", *package_roots})
        require(args.mounted_store in external_roots, "Original supplier root missing")
        combined_roots = list(dict.fromkeys([canonical, *external_roots, native_lib, rt.parent / "lib/lean"]))
        combined_env["LEAN_PATH"] = os.pathsep.join(map(str, combined_roots))
        for name in CANONICAL:
            require_resolution(name, combined_roots, canonical / boot.module_path(name, ".olean"), boot)
        require_resolution("Main", combined_roots, args.mounted_store / "Main.olean", boot)
        require_resolution("Lean", combined_roots, rt.parent / "lib/lean/Lean.olean", boot)
        for name in frozen["modules"]:
            require_resolution(name, combined_roots, native_lib / boot.module_path(name, ".olean"), boot)
        result["combined_environment"] = {k: combined_env[k] for k in RESOURCE_KEYS if k in combined_env}
        write_json(args.output / "HOST_BEFORE.json", host_details())
        write_json(args.output / "INPUT_BINDINGS.json", {"files": list(bindings.rows.values())})
        name = "stock_import_" + args.mode
        sampler = SupplementalSampler(args.output, name)
        sampler.thread.start()
        try:
            row, log = monitor.run(name, [executable, "exact-guard", args.mode], cwd=sources,
                                   env=combined_env, output=args.output, timeout=600, memory_mib=50000)
        finally:
            result["optional_process_evidence"] = sampler.finish()
            write_json(args.output / "HOST_AFTER.json", host_details())
        result["probe_execution"] = row
        result["phase_markers"] = [line for line in log.splitlines() if line.startswith("IMPORT_DIAGNOSTIC ")]
        complete = (row["status"] == "PASS" and
                    sum("DIAGNOSTIC_COMPLETE no_proof_validity_established" in line for line in result["phase_markers"]) == 1 and
                    sum("HEADER_MATCH modules=" in line for line in result["phase_markers"]) == 1)
        result["status"] = "DIAGNOSTIC_EXECUTION_COMPLETED" if complete else "DIAGNOSTIC_INCOMPLETE_OR_FAILED"
        exit_code = 0 if complete else 3
    except Exception as exc:
        result.update(status="INPUT_OR_PREPARATION_FAILED", error_type=type(exc).__name__, error=str(exc))
    finally:
        result["final_integrity"] = bindings.verify()
        if result["final_integrity"]["status"] != "PASS":
            result["status"] = "INPUT_INTEGRITY_FAILED"; exit_code = 2
        if store_before is not None:
            try:
                store_after = mount_state(args.mounted_store, Path(store_before["image"]))
                require(store_before == store_after, "Mounted supplier identity changed during diagnostic")
                result["final_store_mount_identity"] = "UNCHANGED"
            except Exception as exc:
                result.update(status="STORE_IDENTITY_FAILED", final_store_error=str(exc)); exit_code = 2
        forbidden = [str(p) for pattern in ("ImportGuard.*", "MainClosedBridge.*") for p in args.output.rglob(pattern)]
        result["no_guard_or_closed_object_created"] = not forbidden
        if forbidden:
            result.update(status="FORBIDDEN_PROOF_OUTPUT", forbidden_outputs=forbidden); exit_code = 2
        result.update(completed_utc=utc(), exit_code=exit_code,
                      scope="Resource and stock-import phase observations only; no proof or gate acceptance")
        write_json(args.output / "INPUT_BINDINGS.json", {"files": list(bindings.rows.values())})
        write_json(args.output / "DIAGNOSTIC_RESULT.json", result)
        print(json.dumps({"status": result["status"], "output": str(args.output), "proof_acceptance": False}))
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("supplier", "native-work", "trusted-packages", "mounted-store", "mounted-receipt",
                 "store-receipt", "probe-source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mode", choices=("split", "stock"), default="split")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
