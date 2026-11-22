#!/usr/bin/env python3
"""Validate completed 30+7 receipts from a single pinned execution.

This is receipt governance, NOT a replacement for Lean, con-leche or the
trusted original verifier. Never promote an artifact merely because it exists.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from policy import PolicyError, read_json, profile, source_identity, require, sha256

MODULAR_STAGES = 30
INDEPENDENT_STAGES = 7
PILOT_INTEGRITY_FILE = "PILOT_POST_INTEGRITY.json"
PILOT_INTEGRITY_SCHEMA = "OPICA_LONGRUN_PILOT_POST_INTEGRITY_V1"
MOUNTINFO_LIMIT = 1 << 20


def collection_mount_guard(work: Path, *, mountinfo: Path = Path("/proc/self/mountinfo")) -> dict:
    """Refuse traversal while a mount remains within a recursively collected subtree.

    The injectable input is only for bounded local fixtures. The workflow CLI
    always uses the actual process mountinfo; this does not unmount anything.
    """
    record = {"schema": "OPICA_LONGRUN_COLLECTION_MOUNT_GUARD_V1",
              "status": "REFUSED", "proof_acceptance": False,
              "mountinfo_byte_cap": MOUNTINFO_LIMIT, "blocked_mount_targets": [],
              "scope": "Collection safety only; original proof dispositions remain unchanged"}
    try:
        require(work.is_dir() and not work.is_symlink(), "Evidence work root missing or linked")
        roots = [work / name for name in
                 ("native/bootstrap-logs", "verification", "independent-verification")]
        require(all(not path.is_symlink() for path in roots), "Evidence subtree root is linked")
        roots = [path.resolve(strict=False) for path in roots]
        record["evidence_roots"] = [str(path) for path in roots]
        with mountinfo.open("rb") as stream:
            raw = stream.read(MOUNTINFO_LIMIT + 1)
        require(len(raw) <= MOUNTINFO_LIMIT, "Mount inventory exceeded finite bound")
        text = raw.decode("utf-8", errors="strict")
        require(bool(text) and text.endswith("\n"), "Incomplete mount inventory")
        record["mountinfo_bytes"] = len(raw)
        entries = text.splitlines()
        record["mountinfo_entries"] = len(entries)
        for line in entries:
            fields = line.split(" ")
            require(len(fields) >= 10 and all(fields) and fields.count("-") == 1,
                    "Malformed mount inventory entry")
            separator = fields.index("-")
            require(separator >= 6 and len(fields) == separator+4,
                    "Incomplete mount inventory fields")
            require(fields[0].isdigit() and fields[1].isdigit(), "Invalid mount identity")
            require(re.fullmatch(r"[0-9]+:[0-9]+", fields[2]) is not None,
                    "Invalid mount device identity")
            encoded = fields[4]
            require(re.search(r"\\(?!040|011|012|134)", encoded) is None,
                    "Unknown mountpoint escape")
            decoded = re.sub(r"\\(040|011|012|134)",
                             lambda m: chr(int(m.group(1), 8)), encoded)
            target = Path(decoded)
            require(target.is_absolute() and ".." not in target.parts, "Unsafe mountpoint path")
            canonical = target.resolve(strict=False)
            if any(canonical == root or root in canonical.parents for root in roots):
                record["blocked_mount_targets"].append({
                    "mount_id": fields[0], "target": decoded, "canonical_target": str(canonical)})
        require(not record["blocked_mount_targets"], "Mounted subtree remains beneath evidence collection root")
        record["status"] = "PASS_NO_MOUNTED_EVIDENCE_SUBTREE"
    except BaseException as err:
        record.update(error_type=type(err).__name__, error=str(err))
    record["recorded_utc"] = datetime.now(timezone.utc).isoformat()
    return record


def save_collection_mount_guard(work: Path) -> int:
    record = collection_mount_guard(work)
    # Existing custody records are evidence, never silently overwritten.
    with (work / "LONGRUN_COLLECTION_GUARD.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(json.dumps(record, sort_keys=True), flush=True)
    return 0 if record["status"] == "PASS_NO_MOUNTED_EVIDENCE_SUBTREE" else 2


def evaluate(work: Path, *, mode: str, checked_head: str, independent_outcome: str) -> dict:
    p = profile()
    source = source_identity(checked_head)
    modular_path = work / "verification/MODULAR_GATE_RECEIPT.json"
    longrun_path = work / "verification/LONGRUN_CONTROLLER_RECEIPT.json"
    independent_path = work / "independent-verification/INDEPENDENT_RECEIPT.json"
    result = {
        "schema": "OPICA_LONGRUN_WORKFLOW_DISPOSITION_V1",
        "status": "NOT_ESTABLISHED",
        "mode": mode, "checked_head": checked_head, "checked_tree": source["tree"],
        "profile_sha256": source["profile_sha256"],
        "modular_receipt": "NOT_PRESENT", "independent_receipt": "NOT_PRESENT",
        "modular_stage_results": [], "independent_stage_results": [],
        "source_sha256": source["original_source_manifest_sha256"],
        "original_round19_25_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
        "rh_status": "OPEN", "proof_acceptance": False,
        "report_utc": datetime.now(timezone.utc).isoformat(),
    }
    if not modular_path.is_file() or not longrun_path.is_file():
        result["failure"] = "Required modular/longrun receipt absent"
        return result
    modular = read_json(modular_path)
    adapter = read_json(longrun_path)
    result["modular_receipt"] = sha256(modular_path)
    result["adapter_receipt"] = sha256(longrun_path)
    result["modular_stage_results"] = [x.get("status") for x in modular.get("stages", [])]
    if (adapter.get("checked_head") != checked_head or adapter.get("checked_tree") != source["tree"]
            or adapter.get("execution_mode") != mode or adapter.get("longrun_profile_sha256") != source["profile_sha256"]
            or adapter.get("modular_receipt_sha256") != result["modular_receipt"]):
        result["failure"] = "Controller/receipt/source identity mismatch"
        return result
    statuses = result["modular_stage_results"]
    if mode == "pilot_stage20":
        post_path = work / "verification" / PILOT_INTEGRITY_FILE
        if not post_path.is_file() or post_path.is_symlink():
            result["failure"] = "Separate pilot post-integrity receipt absent or linked"
            return result
        post = read_json(post_path)
        post_hash = sha256(post_path)
        result["pilot_post_integrity_receipt"] = post_hash
        if (len(statuses) == MODULAR_STAGES
                and statuses[:20] == ["PASS"]*20
                and statuses[20:] == ["NOT_RUN"]*10
                and modular.get("status") == "PILOT_STAGE20_COMPLETE"
                and adapter.get("pilot_completed") is True
                and adapter.get("modular_pass") is False
                and adapter.get("pilot_post_integrity_pass") is True
                and adapter.get("pilot_post_integrity_sha256") == post_hash
                and modular.get("pilot_post_integrity_sha256") == post_hash
                and modular.get("pilot_post_integrity") == post
                and post.get("schema") == PILOT_INTEGRITY_SCHEMA
                and post.get("status") == "PASS"
                and post.get("proof_acceptance") is False
                and post.get("production_stage30_status") == "NOT_RUN"
                and post.get("primary_execution") == modular.get("pilot_execution_outcome")
                and post.get("primary_execution", {}).get("exit_code") == 0
                and post.get("original_modular_source_sha256") == adapter.get("original_modular_source_sha256")
                and not independent_path.exists()
                and independent_outcome in ("skipped", "not_run_by_pilot")):
            result["status"] = "PILOT_COMPLETE_NO_PROOF_AUTHORITY"
        else:
            result["failure"] = "Pilot first20 execution or separate post-integrity did not pass with matching custody"
        return result
    if mode != "full":
        result["failure"] = "Unrecognized execution mode"
        return result
    if (len(statuses) != MODULAR_STAGES or any(v != "PASS" for v in statuses)
            or modular.get("status") != "PASS" or adapter.get("modular_pass") is not True):
        result["failure"] = "Original all-30 modular gate did not pass"
        return result
    if not independent_path.is_file():
        result["failure"] = "Independent 7-stage receipt absent"
        return result
    independent = read_json(independent_path)
    result["independent_receipt"] = sha256(independent_path)
    results = [r.get("status") for r in independent.get("stages", [])]
    result["independent_stage_results"] = results
    if (len(results) != INDEPENDENT_STAGES or any(v != "PASS" for v in results)
            or independent.get("status") != "PASS" or independent_outcome != "success"):
        result["failure"] = "All seven independent stages did not pass"
        return result
    if modular.get("prior_round19_25_stage_gate") != "NOT_RUN_OR_BLOCKED_UNCHANGED":
        result["failure"] = "Prior gate authority has been silently promoted"
        return result
    # The actual gate receipts, not this validator, provide theorem/kernel evidence.
    result["status"] = "COMPLETE_30_PLUS_7_RECEIPTS_REQUIRE_RESEARCH_REVIEW"
    result["receipts_complete"] = True
    result["proof_acceptance"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--head")
    parser.add_argument("--mode", choices=("pilot_stage20", "full"))
    parser.add_argument("--independent-outcome")
    parser.add_argument("--collection-mount-guard", action="store_true")
    args = parser.parse_args()
    if args.collection_mount_guard:
        if any(x is not None for x in (args.head, args.mode, args.independent_outcome)):
            parser.error("Collection guard cannot be combined with proof-disposition arguments")
        return save_collection_mount_guard(args.work)
    if any(x is None for x in (args.head, args.mode, args.independent_outcome)):
        parser.error("Disposition requires --head, --mode and --independent-outcome")
    args.work.mkdir(parents=True, exist_ok=True)
    out = args.work / "LONGRUN_WORKFLOW_DISPOSITION.json"
    if out.exists():
        parser.error("Disposition path must not be overwritten")
    try:
        record = evaluate(args.work, mode=args.mode, checked_head=args.head,
                          independent_outcome=args.independent_outcome)
        code = 0 if record["status"] in (
            "PILOT_COMPLETE_NO_PROOF_AUTHORITY",
            "COMPLETE_30_PLUS_7_RECEIPTS_REQUIRE_RESEARCH_REVIEW") else 2
    except BaseException as e:
        record = {"schema": "OPICA_LONGRUN_WORKFLOW_DISPOSITION_V1",
                  "status": "FAILED_OR_UNAVAILABLE", "error_type": type(e).__name__,
                  "error": str(e), "proof_acceptance": False, "rh_status": "OPEN"}
        code = 2
    out.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "proof_acceptance": False}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
