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
import sys
from policy import PolicyError, read_json, profile, source_identity, require, sha256

MODULAR_STAGES = 30
INDEPENDENT_STAGES = 7


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
        if (len(statuses) == MODULAR_STAGES
                and statuses[:20] == ["PASS"]*20
                and statuses[20:] == ["NOT_RUN"]*10
                and modular.get("status") == "PILOT_STAGE20_COMPLETE"
                and adapter.get("pilot_completed") is True
                and adapter.get("modular_pass") is False
                and not independent_path.exists()
                and independent_outcome in ("skipped", "not_run_by_pilot")):
            result["status"] = "PILOT_COMPLETE_NO_PROOF_AUTHORITY"
        else:
            result["failure"] = "Pilot did not complete the exact first 20 original stages"
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
    parser.add_argument("--head", required=True)
    parser.add_argument("--mode", choices=("pilot_stage20", "full"), required=True)
    parser.add_argument("--independent-outcome", required=True)
    args = parser.parse_args()
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
