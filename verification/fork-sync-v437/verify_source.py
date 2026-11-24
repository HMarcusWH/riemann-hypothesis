"""Exact source sync preflight. Read-only; never grants proof authority."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PIN = pathlib.Path(__file__).with_name("SOURCE_PIN.json")
def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
def require(ok, message):
    if not ok:
        raise SystemExit(message)
def main():
    p = json.loads(PIN.read_text())
    require(p["schema"] == "OPICA_COMMUNITY_SYNC_V437_SOURCE_V1", "bad schema")
    head = git("rev-parse", "HEAD")
    if len(sys.argv) != 2:
        raise SystemExit("Supply the exact checked head SHA")
    require(head == sys.argv[1], "head mismatch")
    for path, sha in (p["upstream_root_objects"] | p["frozen_fork_objects"]).items():
        require(git("rev-parse", f"HEAD:{path}") == sha, f"object mismatch: {path}")
    actual = sorted(x.name for x in (ROOT / ".github/workflows").iterdir())
    require(actual == sorted(p["allowed_workflow_files"]), "unexpected active workflow inventory")
    require((ROOT / "lean-toolchain").read_text().strip() == p["toolchain"], "wrong toolchain")
    lock = json.loads((ROOT / "lake-manifest.json").read_text())
    require([x["rev"] for x in lock["packages"] if x["name"] == "mathlib"] == [p["mathlib"]], "wrong Mathlib")
    require(p["claim"] == "SOURCE_IDENTITY_AND_CHALLENGE_REHEARSAL_ONLY", "claim escalation")
    require(p["full_supplier_proof"] == "NOT_RUN" and p["native_c1"] == "OPEN" and p["independent_native_step4"] == "OPEN", "claim escalation")
    print(json.dumps({"head": head, "upstream": p["upstream_commit"], "src_tree": p["upstream_root_objects"]["src"], "status": "SOURCE_IDENTITY_PASS_NOT_PROOF", "full_supplier_proof": "NOT_RUN", "C1": "OPEN", "independent_step4": "OPEN"}))
if __name__ == "__main__":
    main()
