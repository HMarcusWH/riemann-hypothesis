#!/usr/bin/env python3
"""Fail-closed, manual-only dedicated runner preflight; not the proof gate."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from policy import PolicyError, profile, source_identity, host_identity, require


def preflight(work: Path, head: str, selection: str, *, record_only: bool = False) -> dict:
    p = profile()
    require(selection == p["id"], "Unreviewed execution profile")
    require(not work.exists(), "Work directory must be fresh")
    require(work.is_absolute() and ".." not in work.parts, "Absolute clean work path required")
    require(not work.parent.is_symlink(), "Work parent must not be a symlink")
    source = source_identity(head, check_worktree=True)
    host = host_identity(p, work.parent)
    # Never create output or run a kernel before all authority checks succeed.
    if not record_only:
        work.mkdir(mode=0o700)
        require(work.stat().st_mode & 0o077 == 0, "Private work directory required")
    record = {
        "schema": "OPICA_LONGRUN_PREFLIGHT_V1",
        "status": "PASS_PREPARATION_ONLY", "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection": selection, "source": source, "host": host,
        "work": str(work), "proof_acceptance": False, "rh_status": "OPEN",
    }
    if not record_only:
        result = work / "LONGRUN_PREFLIGHT.json"
        with result.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
            stream.write("\n")
    return record


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--selection", required=True)
    a = p.parse_args()
    try:
        result = preflight(a.work, a.head, a.selection)
        print(json.dumps({"status": result["status"], "source": result["source"]["head"],
                          "profile": result["selection"], "proof_acceptance": False}))
        return 0
    except (PolicyError, OSError, ValueError) as error:
        print("LONGRUN_PREFLIGHT_REJECTED: " + str(error), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
