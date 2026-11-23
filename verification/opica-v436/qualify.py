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
PUBLIC_ROOTS=("riemannHypothesis","riemannZeta_eq_zero_re","LFunction_ne_zero_of_half_lt_re",
              "LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive")
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
    need(j["selected_public_roots"]==list(PUBLIC_ROOTS) and
         j["independent_checker_commit"]=="cd2eceab2e9b10404c663b468639c8aa99d0d1f2" and
         j["independent_runtime_sha256"]=="2b7ab1ed8b92d2e6abfaf41344823b510064dbc9c0260cac73eb496ab2dea6eb" and
         j["independent_selected_root_count"]==38,
         "Independent supplier proof scope differs")
    need(json.loads((REPO/"comparator.json").read_text())["theorem_names"]==list(PUBLIC_ROOTS),
         "Comparator public root inventory differs")
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
    need(not git("status","--porcelain","--untracked-files=all"),
         "Tracked or untracked source drift")
    ignored=git("ls-files","--others","--ignored","--exclude-standard","--","src","verification/opica-v436")
    need(not any(p.endswith((".lean",".lean.in",".py",".toml",".json")) for p in ignored.splitlines()),
         "Ignored source provider present")
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

def _named_axiom_report(text, name):
    need("sorryAx" not in text and "error:" not in text,
         "Lean error or admitted proof in log")
    # Lean pretty prints long lists over multiple lines. Keep the exact
    # declaration boundary and reject duplicate or truncated reports.
    label=r"(?:'"+re.escape(name)+r"'|"+re.escape(name)+r")"
    pattern=r"(?m)^"+label+r" (?:depends on axioms:\s*\[([^\]]*)\]|relies on axioms:\s*\[([^\]]*)\]|does not depend on any axioms)[ \t]*(?=\n|$)"
    matches=list(re.finditer(pattern,text))
    need(len(matches)==1,"Exact named Lean axiom report missing or ambiguous: "+name)
    raw=matches[0].group(1) or matches[0].group(2) or ""
    values=[s.strip() for s in raw.split(",") if s.strip()]
    need(len(values)==len(set(values)) and set(values)<=ALLOWED,
         "Unexpected or duplicate axiom: "+name)
    return sorted(values)

def check_axiom_log(log:Path):
    names=_named_axiom_report(log.read_text(),"OPICACommunityV436.suppliedRH")
    return {"schema":"OPICA_COMMUNITY_V436_AXIOM_INSPECTION_V1",
            "status":"AXIOM_REPORT_ALLOWED_ONLY",
            "reported_axioms":names,
            "proof_acceptance":False,"complete_supplier_replay":False,
            "full_50_roots":False,"RH":"OPEN"}

def check_public_axiom_log(log:Path):
    text=log.read_text()
    wrapper=check_axiom_log(log)
    result={name:_named_axiom_report(text,name) for name in PUBLIC_ROOTS}
    return {"schema":"OPICA_COMMUNITY_V436_PUBLIC_AXIOMS_V1","roots":result,
            "wrapper":wrapper,"proof_acceptance":False,"RH":"OPEN"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--axiom-log",type=Path)
    a=p.parse_args()
    need(not a.output.exists(),"Output path exists")
    q=source()
    if a.axiom_log:
        q["compiler_axioms"]=check_axiom_log(a.axiom_log)
        q["public_axioms"]=check_public_axiom_log(a.axiom_log)
        q["status"]="INGRESS_TYPE_COMPILED_PENDING_FULL_CERTIFICATE"
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(q,indent=2)+"\n")
    print(json.dumps({"status":q["status"],"proof_acceptance":False,"RH":"OPEN"}))
if __name__=="__main__":main()
