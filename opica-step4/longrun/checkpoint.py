#!/usr/bin/env python3
"""Seal and verify COMPLETE stage-boundary evidence, not an executable proof shortcut.

A checkpoint cannot prove a Lean theorem. It is never sufficient to skip a
mandatory kernel replay or accept a prior incomplete stage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
from policy import PolicyError, require, profile, source_identity, read_json, sha256

PHASES = {
    "modular19": (19, "NOT_RUN"),
    "stage20": (20, "PILOT_STAGE20_COMPLETE"),
    "modular30": (30, "PASS"),
    "independent7": (30, "PASS"),
}
MAX_MEMBERS = 50000
MAX_TOTAL_BYTES = 24 << 30


def check_stage_receipts(work: Path, phase: str) -> dict:
    require(phase in PHASES, "Unknown checkpoint phase")
    original = read_json(work/"verification/MODULAR_GATE_RECEIPT.json")
    stages = original.get("stages", [])
    require(len(stages) == 30, "Full original stage inventory required")
    n, expected_status = PHASES[phase]
    statuses = [r.get("status") for r in stages]
    require(statuses[:n] == ["PASS"]*n, "Required completed original stages missing")
    require(statuses[n:] == ["NOT_RUN"]*(30-n), "Later stage unexpectedly ran or was skipped")
    require(all(r.get("status") not in ("FAIL","INCOMPLETE","RUNNING")
                for r in stages), "Cannot seal failed/running original stage")
    if phase=="stage20":
        require(original.get("status") == "PILOT_STAGE20_COMPLETE", "Stage20 checkpoint must be actual completed pilot")
    elif phase in ("modular30","independent7"):
        require(original.get("status") == "PASS", "Only a full original modular PASS can be sealed")
    if phase=="independent7":
        independent=read_json(work/"independent-verification/INDEPENDENT_RECEIPT.json")
        require(independent.get("status") == "PASS"
                and len(independent.get("stages",[]))==7
                and all(s.get("status")=="PASS" for s in independent["stages"]),
                "Seven original independent PASS stages required")
    else:
        require(not (work/"independent-verification/INDEPENDENT_RECEIPT.json").exists(),
                "Incomplete checkpoint cannot claim an independent receipt")
    return {"modular": original.get("status"), "stages": statuses,
            "independent": "PASS" if phase=="independent7" else "NOT_RUN"}


def _safe_root(work: Path, name: str):
    root=work/name
    if not root.exists():
        return
    require(root.is_dir() and not root.is_symlink(), "Unsafe checkpoint input directory")
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Symlink in checkpoint input: " + str(path))
        st=path.lstat()
        require(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode),
                "Special input file in checkpoint: " + str(path))
        if stat.S_ISREG(st.st_mode):
            yield path


def inventory(work: Path, phase: str) -> list[dict]:
    dirs=["verification"] + (["independent-verification"] if phase=="independent7" else [])
    files = [p for root in dirs for p in _safe_root(work,root)]
    require(0 < len(files) <= MAX_MEMBERS, "Checkpoint inventory count outside bounded scope")
    records=[]
    total=0
    for file in files:
        rel=file.relative_to(work).as_posix()
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise PolicyError("Invalid checkpoint path")
        st=file.lstat()
        total+=st.st_size
        require(total<=MAX_TOTAL_BYTES,"Checkpoint evidence too large for this sealed scope")
        records.append({"path":rel, "bytes":st.st_size, "sha256":sha256(file)})
    return records


def seal(work: Path, phase: str, head: str, output: Path) -> dict:
    require(not output.exists(), "Checkpoint output must be fresh")
    require(output.parent == work/"checkpoints", "Checkpoint must live outside sealed roots")
    checked=check_stage_receipts(work, phase)
    source=source_identity(head)
    files=inventory(work,phase)
    r={
        "schema":"OPICA_COMPLETE_STAGE_BOUNDARY_SEAL_V1",
        "head":head,"tree":source["tree"],"profile_sha256":source["profile_sha256"],
        "phase":phase,"original_stage_statuses":checked["stages"],
        "original_modular_status":checked["modular"],
        "original_independent_status":checked["independent"],
        "files":files,"sealed_bytes":sum(row["bytes"] for row in files),
        "proof_acceptance":False,"stage_resume_authorized":False,
        "rh_status":"OPEN",
        "scope":"Evidence custody only. No kernel replay skipped. Seal digest must be fixed out-of-band.",
    }
    output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(r,stream,indent=2);stream.write("\n")
    return r


def verify(work: Path, path: Path, expected_sha: str, head: str) -> dict:
    require(re.fullmatch(r"[0-9a-f]{64}",expected_sha) is not None,"Exact out-of-band SHA256 required")
    require(sha256(path)==expected_sha,"Checkpoint seal bytes differ from selected digest")
    seal_data=read_json(path)
    require(seal_data.get("schema")=="OPICA_COMPLETE_STAGE_BOUNDARY_SEAL_V1","Unknown seal")
    require(seal_data.get("head")==head,"Wrong checkpoint commit")
    source=source_identity(head)
    require(seal_data["tree"]==source["tree"]
            and seal_data["profile_sha256"]==source["profile_sha256"],"Source/profile mismatch")
    phase=seal_data.get("phase")
    current=check_stage_receipts(work, phase)
    require(current["stages"]==seal_data["original_stage_statuses"]
            and current["modular"]==seal_data["original_modular_status"]
            and current["independent"]==seal_data["original_independent_status"],
            "Original verification stage-state changed")
    require(seal_data.get("stage_resume_authorized") is False
            and seal_data.get("proof_acceptance") is False,
            "Checkpoint cannot grant proof authority")
    actual=inventory(work,phase)
    require(actual==seal_data.get("files"),"Checkpoint artifact bytes/inventory changed")
    return {"status":"SEALED_EVIDENCE_VERIFIED_NOT_A_PROOF","phase":phase,
            "files":len(actual),"proof_acceptance":False,"resume_authorized":False}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("seal","verify"))
    p.add_argument("--work",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--phase",choices=tuple(PHASES))
    p.add_argument("--seal",type=Path,required=True)
    p.add_argument("--expected-sha256")
    a=p.parse_args()
    if a.mode=="seal":
        if not a.phase:p.error("--phase required for sealing")
        result=seal(a.work,a.phase,a.head,a.seal)
        print(json.dumps({"status":"SEALED_FOR_CUSTODY_ONLY","sha256":sha256(a.seal),
                          "files":len(result["files"]),"proof_acceptance":False}))
    else:
        if not a.expected_sha256:p.error("--expected-sha256 required for verification")
        print(json.dumps(verify(a.work,a.seal,a.expected_sha256,a.head)))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
