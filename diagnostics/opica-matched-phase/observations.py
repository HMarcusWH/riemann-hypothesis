"""Bounded diagnostic observations; the four original smaps checkpoints are unchanged."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
import zipfile

SMAPS_CHECKPOINTS = (0, 2, 16, 50)

SIGNATURE_LIMITS = {
    "exact_roots": 13, "providers_and_signatures": 12000,
    "directory_entries": 1000000, "path_depth": 64, "relative_path_bytes": 1024,
    "signature_bytes": 1 << 20, "total_signature_bytes": 64 << 20,
    "metadata_bytes": 32 << 20, "archive_bytes": 96 << 20,
    "seconds": 300, "rss_plus_swap_mib": 1024, "address_space_bytes": 1 << 30,
    "log_bytes": 8 << 20,
}

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


def signature_identity(value):
    return {key: getattr(value, "st_" + key) for key in
            ("dev", "ino", "mode", "nlink", "size", "mtime_ns", "ctime_ns")}


def signature_relative(value):
    path = Path(value)
    require(isinstance(value, str) and value and not path.is_absolute() and
            path.as_posix() == value and ".." not in path.parts and "\\" not in value and
            len(path.parts) <= SIGNATURE_LIMITS["path_depth"] and
            len(value.encode()) <= SIGNATURE_LIMITS["relative_path_bytes"], "Unsafe signature/provider path")
    return path.parts


def signature_directory(path, allow_absent=False):
    """Open every absolute component without following symlinks, including ancestors."""
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)) and ".." not in path.parts,
            "Canonical absolute signature root required")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    walked = Path("/")
    try:
        for component in path.parts[1:]:
            walked /= component
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                if not allow_absent:
                    raise
                return None, {"status": "ABSENT_ROOT", "first_missing": str(walked),
                              "existing_parent": signature_identity(os.fstat(descriptor))}
            os.close(descriptor)
            descriptor = child
        result = descriptor
        descriptor = None
        return result, {"status": "PRESENT_ROOT", "identity": signature_identity(os.fstat(result))}
    finally:
        if descriptor is not None:
            os.close(descriptor)


def signature_open(root, relative):
    components = signature_relative(relative)
    current = os.dup(root)
    try:
        for component in components[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        result = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        try:
            require(stat.S_ISREG(os.fstat(result).st_mode), "Nonregular signature/provider")
        except BaseException:
            os.close(result)
            raise
        return result
    finally:
        os.close(current)


def signature_read_json(path, expected_sha256=None):
    path = Path(path)
    parent, _ = signature_directory(path.parent)
    try:
        descriptor = signature_open(parent, path.name)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "rb") as stream:
        before = signature_identity(os.fstat(stream.fileno()))
        require(before["size"] <= SIGNATURE_LIMITS["metadata_bytes"], "Signature metadata size limit")
        raw = stream.read(SIGNATURE_LIMITS["metadata_bytes"] + 1)
        require(len(raw) == before["size"] and
                before == signature_identity(os.fstat(stream.fileno())), "Signature metadata drift")
    if expected_sha256 is not None:
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Signature basis hash differs")
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate signature metadata key")
            result[key] = value
        return result
    result = json.loads(raw, object_pairs_hook=pairs)
    require(isinstance(result, dict), "Signature metadata must be an object")
    return result


def signature_write_json(path, value):
    path = Path(path)
    require(path.parent.resolve() == path.parent.absolute() and not path.is_symlink(),
            "Unsafe signature output path")
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    require(len(raw) <= SIGNATURE_LIMITS["metadata_bytes"], "Signature metadata size limit")
    pending = path.with_name(path.name + ".tmp")
    with pending.open("xb") as stream:
        stream.write(raw)
    pending.replace(path)


def validate_signature_basis(basis):
    require(basis["schema"] == "OPICA_CURRENT_SIGNATURE_PROVIDER_BASIS_V1" and
            basis["proof_acceptance"] is False and basis["limits"] == SIGNATURE_LIMITS,
            "Signature basis schema, authority or bounds differ")
    roots = basis["roots"]
    require(len(roots) == SIGNATURE_LIMITS["exact_roots"] and
            [row["index"] for row in roots] == list(range(len(roots))), "Exact ordered signature roots required")
    paths = [row["path"] for row in roots]
    require(len(paths) == len(set(paths)) and paths == basis["actual_import_roots"],
            "Signature root identity/order differs")
    total = 0
    for root in roots:
        providers = root["providers"]
        require(isinstance(providers, dict), "Signature providers must be a map")
        total += len(providers)
        require(total <= SIGNATURE_LIMITS["providers_and_signatures"], "Signature provider count limit")
        for name, row in providers.items():
            require(name and set(row) == {"ir", "olean"}, "Signature provider fields differ")
            signature_relative(name + ".ir.sig")
            require(row["ir"]["relative"] == name + ".ir" and
                    row["olean"]["relative"] == name + ".olean", "Unpaired signature provider")
            require(all(re.fullmatch(r"[0-9a-f]{64}", row[k]["sha256"]) for k in ("ir", "olean")),
                    "Invalid recorded provider hash")
    require(total == basis["recorded_ir_provider_count"], "Signature provider inventory count differs")
    return roots


class SignatureArchiveWriter:
    """A finite, seekable ZIP sink; even a partial archive stays within its cap."""
    def __init__(self, stream, tick):
        self.stream, self.tick = stream, tick

    def write(self, data):
        self.tick()
        require(self.stream.tell() + len(data) <= SIGNATURE_LIMITS["archive_bytes"],
                "Signature archive byte limit")
        return self.stream.write(data)

    def seek(self, offset, whence=0):
        value = self.stream.seek(offset, whence)
        require(0 <= value <= SIGNATURE_LIMITS["archive_bytes"], "Signature archive seek limit")
        return value

    def tell(self):
        return self.stream.tell()

    def flush(self):
        return self.stream.flush()


def capture_signatures(basis_path, expected_sha256, output, phase):
    """Capture current signature bytes only; never load Lean objects or confer proof authority."""
    import resource
    output = Path(output)
    require(phase in ("before", "after"), "Unknown signature capture phase")
    require(not output.exists() and not output.is_symlink() and
            output.parent.absolute() == output.parent.resolve(), "Signature capture output must be fresh and safe")
    output.mkdir(mode=0o700)
    started = time.monotonic()
    result = {"schema": "OPICA_CURRENT_SIGNATURE_CAPTURE_V1", "phase": phase, "started_utc": utc(),
              "status": "SIGNATURE_CAPTURE_RUNNING", "proof_acceptance": False,
              "basis_sha256": expected_sha256, "limits": dict(SIGNATURE_LIMITS), "roots": [],
              "address_space_limits_bytes": list(resource.getrlimit(resource.RLIMIT_AS)),
              "signature_count": 0, "signature_bytes": 0, "directory_entries": 0,
              "provider_hash_policy": "Reuse exact first19 recorded .ir/.olean hashes; original final rehash remains separately required",
              "scope": "Current before/after signature custody only; no historical signature equality, complete executable-sidecar coverage or continuous immutability"}
    signature_write_json(output / "CAPTURE.json", result)
    archive_path = output / "signatures.partial.zip"

    def tick():
        require(time.monotonic() - started <= SIGNATURE_LIMITS["seconds"], "Signature capture wall-time limit")

    def provider_identity(root_descriptor, relative):
        tick()
        descriptor = signature_open(root_descriptor, relative)
        try:
            return signature_identity(os.fstat(descriptor))
        finally:
            os.close(descriptor)

    try:
        basis = signature_read_json(basis_path, expected_sha256)
        roots = validate_signature_basis(basis)
        with archive_path.open("xb") as raw_archive:
            sink = SignatureArchiveWriter(raw_archive, tick)
            with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
                for root in roots:
                    tick()
                    descriptor, root_identity = signature_directory(root["path"], allow_absent=True)
                    row = {"index": root["index"], "path": root["path"], "root_identity": root_identity,
                           "providers": {}, "enumeration": "INCOMPLETE", "directory_count": 0}
                    result["roots"].append(row)
                    if descriptor is None:
                        require(not root["providers"] and root["recorded_inventory_entries"] == 0,
                                "A recorded provider root disappeared")
                        row.update(enumeration="COMPLETE_ABSENT_ROOT", signature_count=0,
                                   directory_identity_sha256=hashlib.sha256(b"").hexdigest())
                        continue
                    observed, directory_hashes = {}, []
                    try:
                        def walk(directory, parts):
                            tick()
                            require(len(parts) <= SIGNATURE_LIMITS["path_depth"], "Signature directory depth limit")
                            before = signature_identity(os.fstat(directory))
                            with os.scandir(directory) as entries:
                                for entry in entries:
                                    tick()
                                    result["directory_entries"] += 1
                                    require(result["directory_entries"] <= SIGNATURE_LIMITS["directory_entries"],
                                            "Signature directory-entry limit")
                                    relative = "/".join((*parts, entry.name))
                                    signature_relative(relative)
                                    identity = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                                    require(not stat.S_ISLNK(identity.st_mode), "Symlink inside signature import root")
                                    if stat.S_ISDIR(identity.st_mode):
                                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                                        dir_fd=directory)
                                        try:
                                            require(signature_identity(os.fstat(child)) == signature_identity(identity),
                                                    "Signature directory changed before opening")
                                            walk(child, (*parts, entry.name))
                                        finally:
                                            os.close(child)
                                    else:
                                        require(stat.S_ISREG(identity.st_mode), "Nonregular entry inside signature import root")
                                        if not relative.endswith(".ir.sig"):
                                            continue
                                        module = relative[:-len(".ir.sig")]
                                        require(module in root["providers"] and module not in observed,
                                                "Unknown, orphan or duplicate signature provider")
                                        require(identity.st_size <= SIGNATURE_LIMITS["signature_bytes"] and
                                                result["signature_bytes"] + identity.st_size <= SIGNATURE_LIMITS["total_signature_bytes"],
                                                "Signature raw-byte limit")
                                        require(result["signature_count"] < SIGNATURE_LIMITS["providers_and_signatures"],
                                                "Signature file-count limit")
                                        signature = signature_open(directory, entry.name)
                                        with os.fdopen(signature, "rb") as stream:
                                            before_file = signature_identity(os.fstat(stream.fileno()))
                                            require(before_file == signature_identity(identity), "Signature changed before read")
                                            data = stream.read(SIGNATURE_LIMITS["signature_bytes"] + 1)
                                            require(len(data) == before_file["size"] and
                                                    before_file == signature_identity(os.fstat(stream.fileno())),
                                                    "Signature bytes changed during read")
                                        member = "signatures/" + str(result["signature_count"]).zfill(5) + ".bin"
                                        archive.writestr(member, data)
                                        observed[module] = {"relative": relative, "bytes": len(data),
                                                            "sha256": hashlib.sha256(data).hexdigest(),
                                                            "identity": before_file, "archive_member": member}
                                        result["signature_count"] += 1
                                        result["signature_bytes"] += len(data)
                            require(before == signature_identity(os.fstat(directory)), "Directory changed during signature enumeration")
                            directory_hashes.append(hashlib.sha256(json.dumps(
                                {"relative": "/".join(parts), "identity": before}, sort_keys=True).encode()).digest())

                        walk(descriptor, ())
                        for module, provider in sorted(root["providers"].items()):
                            tick()
                            bound = {key: dict(value, identity=provider_identity(descriptor, value["relative"]))
                                     for key, value in provider.items()}
                            signature = observed.get(module)
                            if signature is None:
                                try:
                                    unexpected = signature_open(descriptor, module + ".ir.sig")
                                except FileNotFoundError:
                                    pass
                                else:
                                    os.close(unexpected)
                                    raise InputFailure("Signature appeared after enumeration")
                                row["providers"][module] = {"status": "ABSENT_SIGNATURE", "provider": bound}
                            else:
                                require(provider_identity(descriptor, signature["relative"]) == signature["identity"],
                                        "Signature identity changed after read")
                                row["providers"][module] = {"status": "PRESENT_SIGNATURE", "provider": bound,
                                                            "signature": signature}
                        current, current_identity = signature_directory(root["path"])
                        try:
                            require(current_identity == root_identity and
                                    signature_identity(os.fstat(descriptor)) == root_identity["identity"],
                                    "Signature root identity changed")
                        finally:
                            os.close(current)
                        row.update(enumeration="COMPLETE_PRESENT_ROOT", signature_count=len(observed),
                                   directory_count=len(directory_hashes),
                                   directory_identity_sha256=hashlib.sha256(b"".join(sorted(directory_hashes))).hexdigest())
                    finally:
                        os.close(descriptor)
        tick()
        require(archive_path.stat().st_size <= SIGNATURE_LIMITS["archive_bytes"], "Signature final archive size limit")
        expected_members = {p["signature"]["archive_member"]: p["signature"]
                            for row in result["roots"] for p in row["providers"].values()
                            if p["status"] == "PRESENT_SIGNATURE"}
        with zipfile.ZipFile(archive_path) as archive:
            require(set(archive.namelist()) == set(expected_members) and
                    len(archive.infolist()) == len(expected_members), "Signature archive inventory differs")
            for name, expected in expected_members.items():
                tick()
                data = archive.read(name)
                require(len(data) == expected["bytes"] and hashlib.sha256(data).hexdigest() == expected["sha256"],
                        "Signature archive readback differs")
        archive_path.rename(output / "signatures.zip")
        archive_path = output / "signatures.zip"
        with archive_path.open("rb") as stream:
            checksum = hashlib.sha256()
            while data := stream.read(1 << 20):
                tick()
                checksum.update(data)
        result["archive"] = {"name": archive_path.name, "bytes": archive_path.stat().st_size,
                             "sha256": checksum.hexdigest(), "readback": "PASS_EVERY_SIGNATURE"}
        result["status"] = "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY"
    except BaseException as exc:
        result.update(status="SIGNATURE_CAPTURE_FAILED_OR_INCOMPLETE", error_type=type(exc).__name__, error=str(exc))
        if archive_path.exists():
            result["partial_archive"] = {"name": archive_path.name, "bytes": archive_path.stat().st_size,
                                         "status": "NOT_ACCEPTED_AS_COMPLETE_CUSTODY"}
    finally:
        result.update(ended_utc=utc(), elapsed_seconds=time.monotonic() - started)
        signature_write_json(output / "CAPTURE.json", result)
    return result


def compare_signature_captures(before, after):
    require(before["status"] == after["status"] == "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY" and
            before["phase"] == "before" and after["phase"] == "after" and
            before["basis_sha256"] == after["basis_sha256"], "Signature captures are incomplete or unrelated")
    def projection(capture):
        roots = []
        for row in capture["roots"]:
            providers = {}
            for name, provider in row["providers"].items():
                value = {"status": provider["status"], "provider": provider["provider"]}
                if "signature" in provider:
                    value["signature"] = {k: v for k, v in provider["signature"].items() if k != "archive_member"}
                providers[name] = value
            roots.append({k: row[k] for k in ("index", "path", "root_identity", "enumeration", "directory_count",
                                              "directory_identity_sha256", "signature_count")})
            roots[-1]["providers"] = providers
        return roots
    require(projection(before) == projection(after), "Signature/provider/root identity, bytes or absence drifted")
    return {"status": "CURRENT_SIGNATURE_BYTES_AND_PROVIDER_IDENTITIES_STABLE", "proof_acceptance": False,
            "root_count": len(before["roots"]), "signature_count": before["signature_count"],
            "signature_bytes": before["signature_bytes"], "original_provider_byte_rehash": "SEPARATELY_REQUIRED",
            "historical_signature_equality": "NOT_ESTABLISHED", "continuous_immutability": "NOT_ESTABLISHED"}


def signature_main():
    import argparse
    import resource
    parser = argparse.ArgumentParser(description="Bounded current signature custody; no Lean execution")
    parser.add_argument("operation", choices=("signature-capture",))
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--basis-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{64}", args.basis_sha256) is not None, "Exact signature basis hash required")
    limit = SIGNATURE_LIMITS["address_space_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    result = capture_signatures(args.basis, args.basis_sha256, args.output, args.phase)
    print(json.dumps({key: result[key] for key in ("status", "phase", "proof_acceptance", "signature_count", "signature_bytes")}), flush=True)
    return 0 if result["status"] == "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(signature_main())
