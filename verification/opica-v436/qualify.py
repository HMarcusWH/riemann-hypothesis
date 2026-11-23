#!/usr/bin/env python3
"""Fail-closed source and axiom scope of community 4.36 ingress."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SRC="69b331ce0e429c7632dac6aa642e5875a50b1218"
BASE="1b894f7511841e6607bc0398cf2657526bbb29d9"
ALLOWED={"propext","Classical.choice","Quot.sound"}
class QualifyError(ValueError):pass

def need(ok,why):
    if not ok:raise QualifyError(why)
def git(*a):
    return subprocess.run(["git","-C",str(REPO),*a],check=True,capture_output=True,
                          text=True,timeout=120).stdout.strip()
def source():
    j=json.loads((HERE/"SOURCE_CONTRACT.json").read_text())
    need(j["schema"]=="OPICA_COMMUNITY_V436_SUPPLIER_CONTRACT_V1",
         "Wrong source contract")
    need(j["frozen_supplier_commit"]==BASE and
         j["frozen_supplier_src_tree"]==SRC,"Source certificate base changed")
    need(j["source_toolchain"]=="leanprover/lean4:v4.36.0",
         "Unexpected compiler")
    need(j["source_mathlib"]=="fc4f59e577feb1a4956671bc04ac18aaaf8cd842",
         "Unreviewed Mathlib pin")
    need(j["allowed_axioms"]==["propext","Classical.choice","Quot.sound"],
         "Axiom policy changed")
    need(j["proof_acceptance"] is False and j["RH"]=="OPEN",
         "Source contract claims RH")
    need(git("rev-parse",BASE+":src")==SRC and git("rev-parse","HEAD:src")==SRC,
         "Original supplier mathematics changed")
    need(git("rev-parse",BASE+":lean-toolchain")==
         git("rev-parse","HEAD:lean-toolchain") and
         (REPO/"lean-toolchain").read_text().strip()==j["source_toolchain"],
         "Source/toolchain changed")
    for s in ("lakefile.toml","lake-manifest.json","comparator.json"):
        need(git("rev-parse",BASE+":"+s)==git("rev-parse","HEAD:"+s),
             "Trusted supplier environment changed: "+s)
    need(not git("status","--porcelain","--untracked-files=no"),
         "Tracked source drift")
    code=(HERE/"Ingress.lean").read_text()
    need("public import Main" in code and
         "theorem suppliedRH : RiemannHypothesis := _root_.riemannHypothesis" in code,
         "Unsafe supplier endpoint replacement")
    need(not re.search(r"(?m)^\s*(axiom|sorry|unsafe\s+theorem|partial\s+theorem)\b",code),
         "Forbidden axiom/placeholder in supplier wrapper")
    need(git("hash-object",str(HERE/"Ingress.lean"))==
         git("rev-parse","HEAD:verification/opica-v436/Ingress.lean"),
         "Wrapper source drift")
    return {"schema":"OPICA_COMMUNITY_V436_SOURCE_INSPECTION_V1",
            "status":"PASS_SOURCE_ONLY","head":git("rev-parse","HEAD"),
            "tree":git("rev-parse","HEAD^{tree}"),
            "supplier_src_tree":SRC,
            "ingress_sha256":hashlib.sha256((HERE/"Ingress.lean").read_bytes()).hexdigest(),
            "proof_acceptance":False,"RH":"OPEN"}

def check_axiom_log(log:Path):
    text=log.read_text()
    # Fail closed if the Lean log contains no actual named axiom report.
    rows=[x for x in text.splitlines() if
          "OPICACommunityV436.suppliedRH" in x and "axiom" in x.lower()]
    need(len(rows)==1,"Exact Lean axiom line missing or ambiguous")
    row=rows[0]
    m=re.search(r"\[(.*?)\]",row)
    need(m is not None,"Lean axiom inventory not structured as a closed list")
    names={s.strip() for s in m.group(1).split(",") if s.strip()}
    need(names<=ALLOWED,"Unexpected axiom: "+str(names-ALLOWED))
    need("sorryAx" not in text and "error:" not in text,
         "Lean error or admitted proof in log")
    return {"schema":"OPICA_COMMUNITY_V436_AXIOM_INSPECTION_V1",
            "status":"AXIOM_REPORT_ALLOWED_ONLY",
            "reported_axioms":sorted(names),
            "proof_acceptance":False,"complete_supplier_replay":False,
            "full_50_roots":False,"RH":"OPEN"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--axiom-log",type=Path)
    a=p.parse_args()
    need(not a.output.exists(),"Output path exists")
    q=source()
    if a.axiom_log:
        q["compiler_axioms"]=check_axiom_log(a.axiom_log)
        q["status"]="INGRESS_TYPE_COMPILED_PENDING_FULL_CERTIFICATE"
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(q,indent=2)+"\n")
    print(json.dumps({"status":q["status"],"proof_acceptance":False,"RH":"OPEN"}))
if __name__=="__main__":main()
