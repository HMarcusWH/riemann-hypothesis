#!/usr/bin/env python3
"""Reinterpret an ORIGINAL byte-verified diagnostic log, without changing its status."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from runner import phase_markers, Refusal  # exact repaired parser, no proof operation

DEFAULT_EXPECTED = "0ee6413ccb845c6532fe8efac97fff8cf7138df7e93a0bedec9109de8385f190"


def reparse(raw: bytes, expected_sha: str = DEFAULT_EXPECTED) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ValueError("Original diagnostic log digest differs")
    phases = phase_markers(raw.decode("utf-8", errors="strict"))
    return {
        "schema": "OPICA_CORRECTED_HISTORICAL_OBSERVATION_V1",
        "status": "CORRECTED_OBSERVATION_ONLY",
        "raw_log_sha256": digest,
        "raw_log_bytes": len(raw),
        "phase_markers": phases["markers"],
        "core_seconds": phases["core_seconds"],
        "finalize_seconds": phases["finalize_seconds"],
        "complete": phases["header_and_completion_observed"],
        "old_workflow_disposition": "FAILURE_UNCHANGED",
        "production_modular_gate": "NOT_RUN",
        "production_independent_gate": "NOT_RUN",
        "proof_acceptance": False,
        "rh_status": "OPEN",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--expected-sha256", default=DEFAULT_EXPECTED)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error("Output must not exist; never overwrite an original receipt")
    result = reparse(args.log.read_bytes(), args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "core_seconds": result["core_seconds"],
                      "finalize_seconds": result["finalize_seconds"], "proof_acceptance": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
