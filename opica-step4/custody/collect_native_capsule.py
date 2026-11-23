#!/usr/bin/env python3
"""Additive native-object custody capsule; no compiler or proof acceptance.

The existing evidence collector and mathematical gates are not changed. Only
the 572 native and four authored bootstrap-audit receipt products are copied.
Runtime, supplier and dependency payloads are bound by immutable references.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import zipfile

NATIVE_HEAD = "7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9"
NATIVE_TREE = "9248b76d7aff60aab3bb775c4be9750dc6006003"
SOURCE_TREE = "24df20b62d9976ccd20da819bc20b16f808f0fdd"
MATHLIB = "0df444a360eaa60ab8c11dca51a86af692955474"
COMPILER = "Lean (version 4.33.1, x86_64-unknown-linux-gnu, commit 819816b2e0a3bf405af45ae5c7af2491d8f5bee6, Release)"
BUNDLE_HASHES = {
    "native_sources.json": "3b6faeca7c42978a5e183f8d33bd921af2dc99f058ba4e4724d2397c271d3ae6",
    "runtime_files.json": "550bbf7a1fc8e2549ecf2d122ff5bfa2007f71d78e3ce1dba42d02fb1ae72793",
    "lake-manifest.json": "391f2a0f7147306be70a47338cb31829e652981b9db028af02e475b73368c5f4",
    "trusted_objects.json.gz": "a60772ae619d879d58690a3318f9b791e91826d10be5bb09ae4a07923797ab60",
}
NATIVE_LIB = PurePosixPath("native/integration/.lake/build/lib/lean")
NATIVE_SOURCE = PurePosixPath("native/native-source")
RECEIPT = "native/integration/NATIVE_COMMON_PIN_BUILD.json"
SIDECARS = (".ilean", ".olean.private", ".olean.server", ".ir")
AUTHORED = {
    "OPICAStep4.ReceiverAudit": "99810c3fd20182630ec6b0fcaf6e67c6be3ec0b04171371ba5d723b2dcc4745b",
    "OPICAStep4.ClaimFingerprint": "255a46d2926e713ad5d41083ef9f818b7e415d89c8a96d63540486d73a56fd56",
    "OPICAStep4.BoundaryFlatCharacterization": "e19bfb13fcb523930617aae99c9d1190cccb1ec3915feae610f7195c68bbef61",
    "OPICAStep4.NativeBootstrapAudit": "3c24abab1c4347f2ea82c1a78cd131d6fd9feeb9d7286b752ce2200e736a8f38",
}
MAX_METADATA = 8 << 20
CHUNK = 1 << 20


class CustodyError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CustodyError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse_json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def module_path(name, suffix):
    require(isinstance(name, str) and re.fullmatch(r"(?:Zeta23|OPICAStep4)(?:\.[A-Za-z_][A-Za-z_0-9]*)+", name),
            "Invalid receipt module name")
    return PurePosixPath(*name.split(".")).with_suffix(suffix)


@contextmanager
def regular_file(root, relative):
    """Descriptor-relative opens reject final and ancestor symlinks, including races."""
    relative = PurePosixPath(relative)
    require(not relative.is_absolute() and relative.parts and
            all(part not in ("", ".", "..") for part in relative.parts), "Unsafe relative path")
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "Required path is not a regular file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                yield stream
        finally:
            os.close(fd)
    finally:
        os.close(descriptor)


def identity(stream):
    value = os.fstat(stream.fileno())
    return {"device": value.st_dev, "inode": value.st_ino, "bytes": value.st_size,
            "mtime_ns": value.st_mtime_ns, "ctime_ns": value.st_ctime_ns}


def limited_hash(stream, limit):
    result, count = hashlib.sha256(), 0
    while block := stream.read(CHUNK):
        count += len(block)
        require(count <= limit, "File exceeds its declared byte bound")
        result.update(block)
    return result.hexdigest(), count


def metadata(root, relative, bindings, expected=None):
    with regular_file(root, relative) as stream:
        before = identity(stream)
        require(before["bytes"] <= MAX_METADATA, "Metadata exceeds fixed 8MiB limit: " + str(relative))
        data = stream.read(MAX_METADATA + 1)
        require(len(data) <= MAX_METADATA and identity(stream) == before, "Metadata changed during read")
    actual = sha_bytes(data)
    require(expected is None or actual == expected, "Reference metadata SHA256 mismatch: " + str(relative))
    bindings.append({"root": str(root), "path": str(relative), "sha256": actual, "identity": before})
    return data


def make_plan(work, receipt, inventory, runtime):
    expected = {"schema": 1, "status": "PASS", "exit_code": 0, "native_head": NATIVE_HEAD,
                "native_tree": NATIVE_TREE, "common_mathlib_rev": MATHLIB,
                "compiler_version": COMPILER, "source_unchanged": True,
                "c1_closed": False, "rh_closed": False,
                "runtime_manifest_sha256": BUNDLE_HASHES["runtime_files.json"]}
    require(all(receipt.get(k) == value for k, value in expected.items()), "Fresh native build receipt identity/status mismatch")
    runtime_files = {row["path"]: row["sha256"] for row in runtime["files"]}
    require(len(runtime_files) == 26, "Runtime manifest must have 26 distinct files")
    for field, path in (("compiler_sha256", "bin/lean"), ("lake_sha256", "bin/lake"),
                        ("kernel_checker_sha256", "bin/leanchecker")):
        require(receipt.get(field) == runtime_files[path], "Native receipt runtime identity differs: " + field)
    expected_sources = inventory["modules"]
    rows = receipt.get("modules")
    require(len(expected_sources) == 572 and inventory.get("module_count") == 572 and
            isinstance(rows, list) and len(rows) == 572, "Expected exact 572-module native closure")
    names = [row.get("module") for row in rows]
    require(len(set(names)) == 572 and set(names) == set(expected_sources), "Duplicate, missing or extra native module")
    audit_rows = receipt.get("audit_modules")
    consumer = receipt.get("audit_consumer")
    require(isinstance(audit_rows, list) and len(audit_rows) == 3 and isinstance(consumer, dict),
            "Expected three authored audit modules and one bootstrap audit consumer")
    authored = [*audit_rows, consumer]
    require(len({row.get("module") for row in authored}) == 4 and
            {row.get("module") for row in authored} == set(AUTHORED) and
            consumer.get("module") == "OPICAStep4.NativeBootstrapAudit", "Authored bootstrap audit inventory differs")
    plan = []
    for row in sorted([*rows, *authored], key=lambda item: item["module"]):
        name = row["module"]
        role = "native_dependency" if name in expected_sources else "authored_bootstrap_audit"
        source_sha = expected_sources[name] if name in expected_sources else AUTHORED[name]
        source_root = NATIVE_SOURCE if name in expected_sources else PurePosixPath("native/integration")
        require(row.get("preexisting_object") is False and row.get("source_unchanged") is True and
                row.get("process", {}).get("status") == "PASS" and row.get("process", {}).get("exit_code") == 0,
                "Receipt does not establish fresh unchanged compilation: " + name)
        require(row.get("source_sha256") == source_sha and
                row.get("source_path") == str(work / source_root / module_path(name, ".lean")),
                "Native source path/hash differs from frozen closure: " + name)
        require(row.get("object_path") == str(work / NATIVE_LIB / module_path(name, ".olean")),
                "Native object path is substituted: " + name)
        sidecars = row.get("sidecars")
        expected_sidecars = set(SIDECARS) if name == "Zeta23.FromPNTPlus.EulerMaclaurin" else {".ilean"}
        require(isinstance(sidecars, dict) and set(sidecars) == expected_sidecars,
                "Required receipt sidecar set differs from the frozen bootstrap profile: " + name)
        products = {".olean": row["object_sha256"]}
        for suffix, side in sidecars.items():
            require(side.get("path") == str(work / NATIVE_LIB / module_path(name, suffix)),
                    "Native sidecar path is substituted: " + name + suffix)
            products[suffix] = side.get("sha256")
        for suffix, expected_sha in products.items():
            require(valid_sha(expected_sha), "Missing or invalid product SHA256: " + name + suffix)
            relative = NATIVE_LIB / module_path(name, suffix)
            plan.append({"module": name, "role": role, "suffix": suffix, "path": str(relative),
                         "archive_path": "objects/" + str(module_path(name, suffix)),
                         "expected_sha256": expected_sha, "source_sha256": source_sha,
                         "status": "NOT_INSPECTED", "archived": False})
    return plan


def inspect_products(work, plan, max_member, max_total):
    known_total, missing_sizes = 0, 0
    planned = {row["path"] for row in plan}
    problems = []
    for row in plan:
        try:
            with regular_file(work, row["path"]) as stream:
                before = identity(stream); row["identity"] = before
                known_total += before["bytes"]
                if before["bytes"] > max_member:
                    row["status"] = "OVERSIZE_MEMBER"; continue
                actual, count = limited_hash(stream, before["bytes"])
                row["observed_sha256"] = actual
                require(count == before["bytes"] and identity(stream) == before, "Object changed during inspection")
                row["status"] = "READY" if actual == row["expected_sha256"] else "HASH_MISMATCH"
        except FileNotFoundError:
            row["status"] = "MISSING"; missing_sizes += 1
        except (OSError, CustodyError) as exc:
            row.update(status="UNSAFE_OR_UNREADABLE", error_type=type(exc).__name__, error=str(exc))
            if "identity" not in row: missing_sizes += 1
    # A receipt cannot silently omit a produced private/server/IR sidecar.
    for name in sorted({row["module"] for row in plan}):
        for suffix in SIDECARS:
            relative = str(NATIVE_LIB / module_path(name, suffix))
            if relative in planned: continue
            try:
                with regular_file(work, relative):
                    problems.append({"path": relative, "status": "UNDECLARED_PRODUCED_SIDECAR"})
            except FileNotFoundError:
                pass
            except (OSError, CustodyError) as exc:
                problems.append({"path": relative, "status": "UNSAFE_UNDECLARED_PATH", "error_type": type(exc).__name__})
    if known_total > max_total:
        problems.append({"status": "OVERSIZE_TOTAL", "known_present_bytes": known_total, "limit_bytes": max_total})
    by_role = {}
    for role in ("native_dependency", "authored_bootstrap_audit"):
        rows = [row for row in plan if row["role"] == role]
        known = sum(row["identity"]["bytes"] for row in rows if "identity" in row)
        unknown = sum("identity" not in row for row in rows)
        by_role[role] = {"required_files": len(rows), "known_present_bytes": known,
                         "required_total_bytes": known if unknown == 0 else None, "unknown_size_files": unknown}
    return {"required_files": len(plan), "known_present_bytes": known_total, "by_role": by_role,
            "required_total_bytes": known_total if missing_sizes == 0 else None,
            "unknown_size_files": missing_sizes, "problems": problems}


def copy_product(target, work, row, max_member):
    with regular_file(work, row["path"]) as stream:
        require(identity(stream) == row["identity"], "Object identity changed since preflight")
        actual, count = hashlib.sha256(), 0
        with target.open(row["archive_path"], "w", force_zip64=True) as destination:
            while block := stream.read(CHUNK):
                count += len(block)
                require(count <= max_member and count <= row["identity"]["bytes"], "Object grew while collecting")
                destination.write(block); actual.update(block)
        require(count == row["identity"]["bytes"] and actual.hexdigest() == row["expected_sha256"] and
                identity(stream) == row["identity"], "Object bytes/identity drifted while collecting")
    row.update(status="ARCHIVED_PENDING_READBACK", archived=True, archived_bytes=count)


def verify_roundtrip(archive, plan, embedded):
    with zipfile.ZipFile(archive) as source:
        expected = {row["archive_path"] for row in plan} | set(embedded)
        require(len(source.namelist()) == len(expected) and set(source.namelist()) == expected,
                "Archive member set differs from exact custody inventory")
        for row in plan:
            require(source.getinfo(row["archive_path"]).file_size == row["identity"]["bytes"],
                    "Archived object size differs")
            with source.open(row["archive_path"]) as stream:
                actual, count = limited_hash(stream, row["identity"]["bytes"])
            require(count == row["identity"]["bytes"] and actual == row["expected_sha256"],
                    "Archived object readback mismatch")
            row["status"] = "ARCHIVED_AND_VERIFIED"
        for name, data in embedded.items():
            require(source.read(name) == data, "Archived metadata readback mismatch: " + name)


def collect(work, output, bundle, source_binding, max_member, max_total):
    require(max_member > 0 and max_total > 0, "Explicit byte budgets must be positive")
    work, bundle, output = Path(work).resolve(), Path(bundle).resolve(), Path(output).absolute()
    require(work.is_dir() and bundle.is_dir(), "Input work/bundle directory missing")
    require(not output.exists() and not output.is_symlink(), "Output directory must be fresh")
    require(output.resolve() == output, "Output has a symlink ancestor")
    output.mkdir(parents=True)
    report = {"schema": "OPICA_NATIVE_OBJECT_CUSTODY_V1", "started_utc": datetime.now(timezone.utc).isoformat(),
              "status": "PREPARING", "custody_complete": False, "proof_acceptance": False,
              "step4": "OPEN", "rh": "OPEN", "source": source_binding,
              "max_member_bytes": max_member, "max_receipt_product_bytes": max_total,
              "objects": [], "metadata_bindings": [], "archive": None,
              "scope": "Exact 572-native-module plus four-authored-audit receipt custody only; no compiler, mathematical gate, native release, or joint acceptance"}
    plan, embedded, bindings = [], {}, report["metadata_bindings"]
    partial = output / "native-objects.partial.zip"
    try:
        for name, expected in BUNDLE_HASHES.items():
            embedded["references/" + name] = metadata(bundle, name, bindings, expected)
        inventory = parse_json(embedded["references/native_sources.json"])
        runtime = parse_json(embedded["references/runtime_files.json"])
        build = metadata(work, RECEIPT, bindings)
        embedded["metadata/NATIVE_COMMON_PIN_BUILD.json"] = build
        receipt = parse_json(build)
        plan = make_plan(work, receipt, inventory, runtime)
        report["objects"] = plan
        report["scope_counts"] = {"native_modules": 572, "native_files": sum(row["role"] == "native_dependency" for row in plan),
                                  "authored_audit_modules": 4, "authored_audit_files": sum(row["role"] == "authored_bootstrap_audit" for row in plan),
                                  "total_files": len(plan)}
        require(report["scope_counts"]["native_files"] == 1147 and
                report["scope_counts"]["authored_audit_files"] == 8 and len(plan) == 1155,
                "Frozen build receipt must describe exactly 1,147 native plus 8 authored audit products")
        report["measurement"] = inspect_products(work, plan, max_member, max_total)
        gate_context = {}
        for label, relative in (("modular", "verification/MODULAR_GATE_RECEIPT.json"),
                                ("independent", "independent-verification/INDEPENDENT_RECEIPT.json"),
                                ("mounted_supplier", "mounted-store-verified.json"),
                                ("supplier_repack", "proof-store.sqfs.receipt.json")):
            try:
                content = metadata(work, relative, bindings)
                data = parse_json(content)
                gate_context[label] = {"status": data.get("status", "UNKNOWN"), "path": relative, "sha256": sha_bytes(content)}
                embedded["context/" + relative.replace("/", "_")] = content
            except FileNotFoundError:
                gate_context[label] = {"status": "NOT_PRESENT", "path": relative}
        report["context"] = gate_context
        validated_path = "verification/NATIVE_VALIDATED_INPUTS.json"
        try:
            validated_bytes = metadata(work, validated_path, bindings)
            validated = parse_json(validated_bytes)
            native_objects = {row["module"]: row for row in plan if row["role"] == "native_dependency" and row["suffix"] == ".olean"}
            validated_rows = validated.get("modules", [])
            require(validated.get("count") == 572 and len(validated_rows) == 572 and
                    len({row.get("module") for row in validated_rows}) == 572 and
                    {row.get("module") for row in validated_rows} == set(native_objects),
                    "Gate-validated native inventory is incomplete or substituted")
            for row in validated_rows:
                planned = native_objects[row["module"]]
                require(row.get("object") == str(work / planned["path"]) and
                        row.get("object_sha256") == planned["expected_sha256"] and
                        row.get("source_sha256") == planned["source_sha256"],
                        "Gate-validated native object differs from fresh build/capsule")
            embedded["context/NATIVE_VALIDATED_INPUTS.json"] = validated_bytes
            report["gate_native_input_binding"] = "MATCHED_572_CURRENT_OBJECTS"
        except FileNotFoundError:
            report["gate_native_input_binding"] = "NOT_PRESENT_NO_GATE_INPUT_BINDING"
        try:
            with regular_file(work, "evidence.zip") as stream:
                before = identity(stream)
                archive_sha, count = limited_hash(stream, before["bytes"])
                require(count == before["bytes"] and identity(stream) == before, "Original evidence archive changed")
            bindings.append({"root": str(work), "path": "evidence.zip", "sha256": archive_sha, "identity": before})
            report["original_evidence_archive"] = {"path": "evidence.zip", "sha256": archive_sha,
                                                   "bytes": count, "payload_archived": False}
        except FileNotFoundError:
            report["original_evidence_archive"] = {"status": "NOT_PRESENT", "payload_archived": False}
        references = {"native_source": {"repository": "https://github.com/HMarcusWH/zeta-23-lean",
                        "commit": NATIVE_HEAD, "tree": NATIVE_TREE, "inventory_sha256": BUNDLE_HASHES["native_sources.json"]},
                      "supplier_source_tree": SOURCE_TREE,
                      "supplier_objects": {"base_url": "https://huggingface.co/datasets/JackMcCarthy/riemann-hypothesis-build/resolve/9036e64326acf4acfae159b96664e9708445c1d1",
                        "archive": "oleans.tar.zst", "archive_bytes": 28638044751,
                        "archive_sha256": "953bab5386a7849527a11960f80a2fab427c49c637d6e94cc75788dd8f40196b",
                        "manifest": "olean-manifest.sha256", "manifest_sha256": "fb3609ad73a17102e6e3e2346c5358a9c0957bcf5945442a7e5ffaa00c441ff5",
                        "files": 350374, "payload_archived": False},
                      "runtime": {"archive_url": runtime["archive_url"], "archive_sha256": runtime["archive_sha256"],
                                  "manifest_sha256": BUNDLE_HASHES["runtime_files.json"], "payload_archived": False},
                      "dependencies": {"manifest_sha256": BUNDLE_HASHES["lake-manifest.json"],
                                       "reference_objects_sha256": BUNDLE_HASHES["trusted_objects.json.gz"], "payload_archived": False},
                      "authored_bootstrap_audit_source_sha256": AUTHORED,
                      "original_collector_still_required": "Canonical proof-run modules, future guard/closed objects, complete gate receipts/logs and independent checks are not supplied by this bootstrap-object capsule",
                      "reference_scope": "Immutable identities and retrieval references; no assumption that a hash proves logical correctness"}
        embedded["metadata/REFERENCES.json"] = json_bytes(references)
        report["references"] = references
        require(all(row["status"] == "READY" for row in plan) and not report["measurement"]["problems"],
                "Native objects are missing, unsafe, changed, undeclared, or exceed explicit budgets")
        report["disk_free_bytes_before_archive"] = shutil.disk_usage(output).free
        report["required_storage_budget_bytes"] = report["measurement"]["known_present_bytes"] + sum(map(len, embedded.values())) + (4 << 20)
        require(report["disk_free_bytes_before_archive"] >= report["required_storage_budget_bytes"],
                "Insufficient free disk for bounded uncompressed custody archive")
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as target:
            for row in plan:
                try:
                    copy_product(target, work, row, max_member)
                except (OSError, CustodyError) as exc:
                    row.update(status="DRIFTED_OR_UNREADABLE_DURING_COLLECTION", error_type=type(exc).__name__, error=str(exc))
                    raise
            for binding in bindings:
                with regular_file(Path(binding["root"]), binding["path"]) as stream:
                    require(identity(stream) == binding["identity"] and
                            limited_hash(stream, binding["identity"]["bytes"])[0] == binding["sha256"],
                            "Metadata/evidence changed during collection: " + binding["path"])
            for row in plan:
                with regular_file(work, row["path"]) as stream:
                    if identity(stream) != row["identity"]:
                        row["status"] = "DRIFTED_AFTER_COLLECTION"
                        raise CustodyError("Receipt product identity changed after collection: " + row["path"])
            index = {"schema": "OPICA_NATIVE_CUSTODY_CONTENT_INDEX_V1", "scope_counts": report["scope_counts"],
                     "objects": [{key: row[key] for key in ("module", "role", "suffix", "archive_path", "expected_sha256", "source_sha256", "archived_bytes")} for row in plan],
                     "proof_acceptance": False, "required_external_check": "Final external custody receipt and archive readback; mathematical/production gates remain separate"}
            embedded["metadata/CUSTODY_INDEX.json"] = json_bytes(index)
            for name, content in embedded.items():
                target.writestr(name, content)
        verify_roundtrip(partial, plan, embedded)
        complete = output / "native-objects.zip"
        with partial.open("rb") as stream:
            archive_sha, _ = limited_hash(stream, partial.stat().st_size)
        # Exclusive hard-link publication never replaces a concurrent output.
        os.link(partial, complete)
        partial.unlink()
        report.update(status="COMPLETE_BUILD_RECEIPT_CUSTODY_ONLY", custody_complete=True,
                      archive={"path": str(complete), "bytes": complete.stat().st_size, "sha256": archive_sha,
                               "objects": len(plan), "roundtrip": "PASS", "compression": "ZIP_STORED"})
    except Exception as exc:
        report.update(status="INCOMPLETE_BUILD_RECEIPT_CUSTODY", error_type=type(exc).__name__, error=str(exc))
        if partial.exists():
            with partial.open("rb") as stream:
                partial_sha, _ = limited_hash(stream, partial.stat().st_size)
            report["archive"] = {"path": str(partial), "bytes": partial.stat().st_size,
                                 "sha256": partial_sha, "complete": False, "roundtrip": "NOT_ACCEPTED"}
    report["completed_utc"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = 0 if report["custody_complete"] else 2
    with (output / "CUSTODY_MANIFEST.json").open("xb") as stream:
        stream.write(json_bytes(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--supplier", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-member-mib", type=int, required=True)
    parser.add_argument("--max-total-mib", type=int, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.head), "Exact full supplier head required")
    supplier = args.supplier.resolve()
    def git(*values):
        return subprocess.check_output(["git", "-C", supplier, *values], text=True, timeout=60).strip()
    require(git("rev-parse", "HEAD") == args.head and git("rev-parse", "HEAD:src") == SOURCE_TREE,
            "Supplier head or original source tree differs")
    require(not git("status", "--porcelain", "--untracked-files=no"), "Tracked supplier source is dirty")
    binding = {"head": args.head, "tree": git("rev-parse", "HEAD^{tree}"), "src_tree": SOURCE_TREE,
               "collector_sha256": sha_bytes(Path(__file__).read_bytes())}
    result = collect(args.work, args.output, supplier / "opica-step4/native_bootstrap", binding,
                     args.max_member_mib << 20, args.max_total_mib << 20)
    print(json.dumps({key: result[key] for key in ("status", "custody_complete", "proof_acceptance", "exit_code", "archive")}))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
