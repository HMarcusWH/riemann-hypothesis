#!/usr/bin/env python3
"""Versioned V3 CURRENT-NATIVE candidate: write/check canonical state, never merge.

Provenance: V2 run 45051273111 (old native 200777...), 78 products,
29 changed paths; V3 pins bb7... current native main and preserves every
non-generated source and historical object. Successful output is PREPARED,
not formal proof acceptance, new OPICA theorem or an automatic patch merge.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

CONTROLLER_BASE = "e388dc7db892b2a4ae2e628bdc0113b1019ca7dd"
NATIVE_COMMIT = "bb7c8184a135b2823c6296917c5ac893bebf2a71"
NATIVE_TREE = "2b19357e1b65cc500f3e3a5b5d4df14601b02062"
V2_COMMIT = "200777fa9afa8c00a193c0070866d58791f54fdc"
V2_PATCH_SHA = "85f0ef7476af766125ddbf07b1abef3e42a122668f6ffacf43286374acbd27d2"
V2_PATCH_NAME = "native-canonical-preparation-v2/generated-state.patch"
V2_RECEIPT_NAME = "native-canonical-preparation-v2/canonical-operation.json"
V2_PRODUCTS_NAME = "native-canonical-preparation-v2/after-check-products.json"
V2_HISTORICAL_NAME = "native-canonical-preparation-v2/historical-storage-before.json"
SOURCE_COVERAGE = "research/RHRC/graph/generated/REPOSITORY_COVERAGE.json"
EXTRA_INDEX = "research/RHRC/graph/compiler/REGISTERED_DECLARATION_DEPENDENCIES.jsonl"
PROTECTED = (
 "research/RHRC/ffbbp/generated/history/RHKG_CANDIDATE_REDUCTION_ASSURANCE_v1_PR265.json",
 "research/RHRC/ool/generated/history/RHKG_OOL_PHASE_ATLAS_v1_PR266.json",
 "research/RHRC/ool/generated/history/RHKG_OOL_ROUTE_CONTACTS_v1_PR266.jsonl",
)
MAX_PATCH_BYTES = 100_000_000
MAX_FILE_BYTES = 100_000_000
class ReviewError(RuntimeError):pass

def check(ok, why):
    if not ok:raise ReviewError(why)
def git(repo,*args):
    return subprocess.run(["git","-C",str(repo),*args],check=True,capture_output=True,
                          text=True,timeout=120).stdout.strip()
def sha(data):
    return hashlib.sha256(data).hexdigest()
def obj_file(path):
    path=Path(path);check(path.is_file() and not path.is_symlink(),"Missing/linked source file "+str(path))
    return path.read_bytes()
def read_v2(zip_path):
    check(zip_path.is_file() and not zip_path.is_symlink(),"V2 archive missing/linked")
    with zipfile.ZipFile(zip_path) as z:
        names=z.namelist()
        check(len(names)==len(set(names)),"Duplicate V2 ZIP entry")
        check(len(names)<1000 and all(not x.startswith("/") and ".." not in Path(x).parts
                                       for x in names),"Unsafe V2 ZIP inventory")
        for name in (V2_PATCH_NAME,V2_RECEIPT_NAME,V2_PRODUCTS_NAME,V2_HISTORICAL_NAME):
            check(name in names, "V2 evidence missing "+name)
        patch=z.read(V2_PATCH_NAME)
        check(len(patch)<=MAX_PATCH_BYTES and sha(patch)==V2_PATCH_SHA,"V2 candidate patch digest changed")
        old=json.loads(z.read(V2_RECEIPT_NAME))
        products=json.loads(z.read(V2_PRODUCTS_NAME))
        historical=json.loads(z.read(V2_HISTORICAL_NAME))
    check(old.get("status")=="CANONICAL_CANDIDATE_PREPARED"
          and old.get("checked_commit")==V2_COMMIT
          and old.get("patch_sha256")==V2_PATCH_SHA
          and old.get("proof_acceptance") is False
          and len(old.get("changed_paths",[]))==29,"Original V2 result differs")
    hashes=products.get("hashes78")
    check(products.get("status")=="PASS_PRODUCT_HASHES_ONLY" or
          (isinstance(hashes,dict) and len(hashes)==78),
          "Invalid V2 products observation")
    check(isinstance(hashes,dict) and len(hashes)==78,"Old 78 product hashes absent")
    check(historical.get("result",{}).get("objects")==17,"Old 17 historical objects not reported")
    check(old["changed_paths"]==sorted(set(old["changed_paths"])),"V2 changed path list unsorted")
    return {"source_commit":V2_COMMIT,"changed_paths":old["changed_paths"],
            "after_check_hashes":hashes,"patch_sha256":V2_PATCH_SHA,
            "historical":historical["result"]}

def source_state(controller,native):
    check(git(controller,"rev-parse","HEAD:"+ "diagnostics/opica-canonical-v3/reconcile.py")
          ==git(controller,"hash-object",str(Path(__file__).resolve())),
          "Controller script differs from exact checked commit")
    check(subprocess.run(["git","-C",str(controller),"merge-base","--is-ancestor",
                          CONTROLLER_BASE,"HEAD"],capture_output=True).returncode==0,
          "Controller not based on reviewed CI repair")
    check(git(native,"rev-parse","HEAD")==NATIVE_COMMIT,"Native head is not current reviewed pin")
    check(git(native,"rev-parse","HEAD^{tree}")==NATIVE_TREE,"Native tree differs")
    check(git(native,"status","--porcelain","--untracked-files=no")=="",
          "Native worktree had modified inputs before canonical writer")
    check((native/"lean-toolchain").read_text().strip()=="leanprover/lean4:v4.33.0-rc2",
          "Native Lean toolchain differs")
    coverage=json.loads(obj_file(native/SOURCE_COVERAGE))
    products=coverage.get("declared_generated_products")
    check(type(products) is list and len(products)==77
          and len(set(products))==77,"Expected original 77 generated products missing")
    authorized=set(products)|{EXTRA_INDEX}
    check(len(authorized)==78,"Unreviewed current generated inventory")
    for path in authorized:
        check(path.startswith("research/RHRC/") and
              ("/generated/" in path or "/compiler/" in path),"Unreviewed generated path")
        check((native/path).is_file() and not (native/path).is_symlink(),
              "Missing/linked current generated path")
    for path in PROTECTED:
        check(path not in authorized,"Historical source placed in active generated set")
    return {"controller_head":git(controller,"rev-parse","HEAD"),
            "controller_tree":git(controller,"rev-parse","HEAD^{tree}"),
            "native_head":NATIVE_COMMIT,"native_tree":NATIVE_TREE,
            "authorized":sorted(authorized)}

def inventory(native,paths):
    result={}
    for path in paths:
        raw=obj_file(native/path)
        result[path]={"sha256":sha(raw),"bytes":len(raw)}
    return result

def launch(native,out,mode):
    argv=[sys.executable,"-B","research/RHRC/tools/materialize_derived_state.py","--"+mode]
    start=time.monotonic()
    with (out/(mode+".stdout.log")).open("xb") as so,(out/(mode+".stderr.log")).open("xb") as se:
        try:
            row=subprocess.run(argv,cwd=native,stdout=so,stderr=se,timeout=9000)
            code=row.returncode;error=None
        except subprocess.TimeoutExpired:
            code=None;error="TIMEOUT_9000_SECONDS"
    result={"mode":mode,"argv":argv,"exit_code":code,"error":error,
            "wall_seconds":round(time.monotonic()-start,3),
            "stdout_sha256":sha(obj_file(out/(mode+".stdout.log"))),
            "stderr_sha256":sha(obj_file(out/(mode+".stderr.log")))}
    (out/(mode+".result.json")).write_text(json.dumps(result,indent=2)+"\n")
    check(code==0 and error is None,"Canonical "+mode+" incomplete or rejected")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--controller",type=Path,required=True)
    p.add_argument("--native",type=Path,required=True)
    p.add_argument("--v2-archive",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    controller=a.controller.resolve();native=a.native.resolve()
    out=a.output.resolve()
    check(not out.exists() and not out.is_relative_to(native)
          and not out.is_relative_to(controller),"Fresh external evidence root required")
    out.mkdir(mode=0o700,parents=True)
    report={"schema":"OPICA_NATIVE_CANONICAL_V3_RECONCILIATION_V1",
            "status":"INCOMPLETE","authority":"GENERATED_CANDIDATE_ONLY",
            "proof_acceptance":False,"RH":"OPEN","Step4":"OPEN",
            "native_finalization":"NOT_RUN","full_11_lanes":"NOT_RUN",
            "commands":[],"errors":[]}
    try:
        state=source_state(controller,native)
        v2=read_v2(a.v2_archive.resolve())
        report.update(source=state,v2={"source_commit":v2["source_commit"],
                         "patch_sha256":v2["patch_sha256"],
                         "changed_paths":v2["changed_paths"],
                         "historical":v2["historical"]})
        before=inventory(native,state["authorized"])
        historical_before=inventory(native,PROTECTED)
        report["historical_before"]=historical_before
        report["authorized_generated_product_count"]=len(before)
        report["commands"].append(launch(native,out,"write"))
        written=inventory(native,state["authorized"])
        report["commands"].append(launch(native,out,"check"))
        checked=inventory(native,state["authorized"])
        check(written==checked,"Canonical write/check results differ")
        report["historical_after"]=inventory(native,PROTECTED)
        check(historical_before==report["historical_after"],"Protected 3 historical objects changed")
        changed=[x.split("\t",1) for x in git(native,"diff","--name-status","HEAD").splitlines()]
        check(all(len(x)==2 and x[0]=="M" and x[1] in state["authorized"]
                  for x in changed),"Canonical edited unexpected source or unapproved generated file")
        changed_paths=sorted(x[1] for x in changed)
        check(changed_paths==sorted(x for x in state["authorized"]
                                   if checked[x]!=before[x]),"Changed-byte inventory differs from git diff")
        subprocess.run(["git","-C",str(native),"diff","--check"],check=True,timeout=180)
        patch=subprocess.check_output(["git","-C",str(native),"diff","--binary","HEAD","--",
                                       *changed_paths],timeout=180) if changed_paths else b""
        check(len(patch)<=MAX_PATCH_BYTES,"V3 patch exceeds bounded evidence scope")
        (out/"generated-v3-review-only.patch").write_bytes(patch)
        v2_hashes=v2["after_check_hashes"]
        report["v2_comparison"]={
            "old_changed_path_count":len(v2["changed_paths"]),
            "new_changed_path_count":len(changed_paths),
            "paths_shared":sorted(set(v2["changed_paths"]) & set(changed_paths)),
            "old_paths_not_changed_now":sorted(set(v2["changed_paths"])-set(changed_paths)),
            "new_paths_absent_in_old":sorted(set(changed_paths)-set(v2["changed_paths"])),
            "same_hashes_as_v2":sorted(k for k in checked if
                      k in v2_hashes and checked[k]["sha256"]==v2_hashes[k]),
            "hash_compared_count":len(set(checked) & set(v2_hashes)),
            "identity_claim":"DIFFERENT_NATIVE_SOURCE_GENERATION_COMPARE_ONLY"
        }
        report["generated_after_write_check"]=checked
        report["changed_paths"]=changed_paths
        report["patch_sha256"]=sha(patch)
        report["status"]="V3_CURRENT_NATIVE_CANDIDATE_PREPARED_FOR_REVIEW"
        report["source_unchanged"]=True
        report["successor_human_review"]="PENDING"
        print(json.dumps({"status":report["status"],"new_changed_paths":len(changed_paths),
                          "review_only_patch_sha256":sha(patch),"proof_acceptance":False}),flush=True)
    except BaseException as e:
        report["status"]="V3_FAILED_OR_INCOMPLETE"
        report["errors"].append({"type":type(e).__name__,"message":str(e)[:1200]})
        print("V3_FAILED_OR_INCOMPLETE: "+str(e),file=sys.stderr,flush=True)
        raise
    finally:
        (out/"V3_CONTROLLER_RECEIPT.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
