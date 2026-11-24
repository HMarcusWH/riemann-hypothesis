#!/usr/bin/env python3
"""Exact community-supplier independent selected proof closure; NOT native C1.

The old combined checker helper and pinned runtime bootstrap are preserved as
separate copied tools. No old accepted proof counts or proof receipts are reused.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from common import (CHECKER_HEAD, RUNTIME_SHA, RUNTIME_BYTES, clean_env,
                    clean_checkout, file_inventory, verify_file_inventory,
                    require, run, read_json, write_json, sha, git)
from qualify import REPO, source, PUBLIC_ROOTS, check_public_axiom_log

PRIMITIVES=("Nat.add","Nat.sub","Nat.mul","Nat.pow","Nat.gcd","Nat.div","Nat.mod",
            "Nat.beq","Nat.ble","Nat.land","Nat.lor","Nat.xor","Nat.shiftLeft","Nat.shiftRight",
            "String.ofList","Char.ofNat","List","eagerReduce","Nat","String","String.mk","Char",
            "optParam","autoParam","semiOutParam","outParam")
ROOTS=("Quot","Quot.mk","Quot.lift","Quot.ind",*PUBLIC_ROOTS,
       "propext","Quot.sound","Classical.choice",*PRIMITIVES)

def acceptance(text, root_count, *, complete_prelude=False):
    verdicts=re.findall(r"(?m)^con-leche: accepted ([0-9]+) declarations \(--verified\)\s*$",text)
    emits=re.findall(r"con-leche: read: emitting records from ([0-9]+) constants\b",text)
    parses=re.findall(r"con-leche: parse done: ([0-9]+) fold records — the file's ([0-9]+), ([0-9]+) built-in prelude records synthesised",text)
    checks=re.findall(r"con-leche: check done: ([0-9]+) declarations\b",text)
    require(len(verdicts)==1 and emits==[str(root_count)] and len(parses)==1
            and checks==[parses[0][0]] and int(verdicts[0])==int(parses[0][1])>0,
            "Incomplete or contradictory independent checker accounting")
    if complete_prelude:
        require(parses[0][0]==parses[0][1] and parses[0][2]=="0",
                "Required explicit primitive roots were not emitted")
    require(not re.search(r"not implemented yet:|internal error:|check failed|PANIC|uncaught exception",text),
            "Contradictory independent checker failure diagnostic")
    return int(verdicts[0])

def packages():
    d=read_json(REPO/"lake-manifest.json")
    require(d["packagesDir"]==".lake/packages","Unexpected package root")
    result={}
    for row in d["packages"]:
        name, rev=row["name"], row["rev"]
        require(re.fullmatch(r"[A-Za-z0-9_-]+",name) and re.fullmatch(r"[0-9a-f]{40}",rev)
                and name not in result,"Invalid package pin")
        p=REPO/".lake/packages"/name
        clean_checkout(p,rev)
        require(not git(p,"status","--porcelain","--untracked-files=all"),"Dirty package source: "+name)
        result[name]={"commit":rev,"tree":git(p,"rev-parse","HEAD^{tree}")}
    require(len(result)==9 and result["mathlib"]["commit"]=="fc4f59e577feb1a4956671bc04ac18aaaf8cd842",
            "Exact nine dependency pins required")
    return result

def mounted_readonly(path):
    lines=subprocess.check_output(["findmnt","--noheadings","--output","TARGET,OPTIONS",
                                   "--target",str(path)],text=True,timeout=15).strip().splitlines()
    require(len(lines)==1,"Ambiguous reader mount")
    target, options=lines[0].split(None,1)
    require(Path(target)==path and "ro" in options.split(","),"Reader mount not read-only")
    st=path.stat()
    return {"mountpoint":str(path),"options":options,"device":st.st_dev,"inode":st.st_ino}

def verify(args):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and
            os.environ.get("RUNNER_ENVIRONMENT")=="self-hosted" and
            os.environ.get("GITHUB_REPOSITORY")=="HMarcusWH/riemann-hypothesis" and
            os.environ.get("GITHUB_REF")=="refs/heads/research/opica-community-v436-supplier-qualification-20261123" and
            os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and
            args.head==os.environ.get("GITHUB_SHA"),"Explicit dedicated reviewed supplier workflow required")
    output=args.output.resolve()
    require(not output.exists() and not output.is_relative_to(REPO),"Fresh external output required")
    output.mkdir(parents=True)
    report={"schema":"OPICA_COMMUNITY_V436_INDEPENDENT_38_V1","status":"INCOMPLETE",
            "head":args.head,"roots":list(ROOTS),"root_count":len(ROOTS),"stages":[],
            "proof_acceptance":False,"native_combined_50_roots":"NOT_RUN",
            "original_30_plus_7":"NOT_RUN","RH":"OPEN","C1":"OPEN","Step4":"OPEN"}
    def save(): write_json(output/"RECEIPT.json",report)
    mounts=[]
    try:
        require(len(ROOTS)==len(set(ROOTS))==38,"Exact 38 distinct roots required")
        original=source()
        require(original["head"]==args.head,"Reviewed source mismatch")
        report["source"]=original
        report["public_axioms"]=check_public_axiom_log(args.axiom_log)
        report["axiom_log_sha256"]=sha(args.axiom_log)
        deps=packages()
        bootstrap=read_json(args.checker_work/"BOOTSTRAP_RECEIPT.json")
        require(bootstrap["status"]=="PASS" and bootstrap["source_head"]==CHECKER_HEAD
                and bootstrap["runtime_archive_sha256"]==RUNTIME_SHA
                and bootstrap["runtime_archive_bytes"]==RUNTIME_BYTES,"Pinned checker bootstrap absent")
        runtime=Path(bootstrap["runtime"]).resolve()
        checker_source=Path(bootstrap["source"]).resolve()
        binary=Path(bootstrap["tools"]["con-leche"]["path"]).resolve()
        require(binary==checker_source/".lake/build/bin/con-leche"
                and sha(binary)==bootstrap["tools"]["con-leche"]["sha256"],"Checker binary binding differs")
        clean_checkout(checker_source,CHECKER_HEAD)
        source_files=read_json(Path(bootstrap["source_inventory"]))
        require(sha(Path(bootstrap["source_inventory"]))==bootstrap["source_inventory_sha256"]
                and {n:sha(checker_source/n) for n in git(checker_source,"ls-files").splitlines()}==source_files,
                "Checker source inventory differs")
        runtime_inventory=read_json(Path(bootstrap["runtime_inventory"]))
        require(sha(Path(bootstrap["runtime_inventory"]))==bootstrap["runtime_inventory_sha256"],
                "Runtime inventory digest differs")
        verify_file_inventory(runtime,runtime_inventory)
        env=clean_env(runtime,1)
        require("version 4.36.0" in subprocess.check_output([str(runtime/"bin/lean"),"--version"],
                    env=env,text=True,timeout=30),"Wrong stock compiler")
        raw=subprocess.check_output([str(runtime/"bin/lake"),"env","printenv","LEAN_PATH"],
                                    cwd=REPO,env=env,text=True,timeout=120).strip()
        roots=[Path(p).resolve() for p in raw.split(os.pathsep) if p]
        core=(runtime/"lib/lean").resolve()
        if core not in roots: roots.append(core)
        expected={core,(REPO/".lake/build/lib/lean").resolve(),
                  *[(REPO/".lake/packages"/n/".lake/build/lib/lean").resolve() for n in deps]}
        require(len(roots)==len(set(roots)) and set(roots)==expected,"Unexpected compiler import roots")
        require((REPO/".lake/build/lib/lean/Main.olean").is_file(),"Fresh Main object missing")
        report.update(checker_source_head=CHECKER_HEAD,checker_binary_sha256=sha(binary),
                      stock_compiler_sha256=sha(runtime/"bin/lean"),package_pins=deps)
        inventory={str(p):file_inventory(p) for p in roots}
        write_json(output/"OBJECT_INVENTORY.json",inventory)
        report["object_inventory_sha256"]=sha(output/"OBJECT_INVENTORY.json")
        report["stages"].append("SOURCE_TYPES_AXIOMS_CHECKER_AND_OBJECT_BINDINGS_PASS")
        save()
        view=output/"views";view.mkdir()
        identities={}
        for i,p in enumerate(roots):
            dest=view/str(i);dest.mkdir()
            subprocess.run(["sudo","-n","mount","--bind",str(p),str(dest)],check=True,timeout=60)
            mounts.append(dest)
            subprocess.run(["sudo","-n","mount","-o","remount,bind,ro",str(dest)],check=True,timeout=60)
            identities[str(dest)]=mounted_readonly(dest)
        search=os.pathsep.join(str(p) for p in mounts)
        report["read_only_views"]=identities
        # Actual independent checker controls: unused axiom accepted, transitive
        # nonstandard axiom rejected, missing root rejected.
        fixture=output/"fixture";fixture.mkdir()
        f=fixture/"ClosureControl.lean"
        f.write_text("namespace ClosureControl\naxiom uncheckedLeaf : False\ntheorem selectedRoot : False := uncheckedLeaf\ntheorem unrelatedRoot : True := True.intro\nend ClosureControl\n")
        run("fixture_compile",[runtime/"bin/lean","--root="+str(fixture),"-o",fixture/"ClosureControl.olean",f],
            cwd=fixture,env=env,output=output,timeout=120,memory_mib=2048)
        base=[binary,"--verified","--jobs=1","--progress=30s","--olean",
              "--search-path="+str(fixture)+os.pathsep+str(mounts[roots.index(core)])]
        _,good=run("control_unused_axiom",[*base,"--constant=ClosureControl.unrelatedRoot","ClosureControl"],
                   cwd=fixture,env=env,output=output,timeout=300,memory_mib=2048)
        acceptance(good,1)
        _,bad=run("control_transitive_axiom",[*base,"--constant=ClosureControl.selectedRoot","ClosureControl"],
                  cwd=fixture,env=env,output=output,timeout=300,memory_mib=2048,expected=2)
        require("not implemented yet: non-standard axiom (ClosureControl.uncheckedLeaf)" in bad
                and "con-leche: accepted " not in bad,"Transitive custom axiom control failed")
        _,bad=run("control_missing_root",[*base,"--constant=ClosureControl.absentRoot","ClosureControl"],
                  cwd=fixture,env=env,output=output,timeout=300,memory_mib=2048,expected=3)
        require("the constant ClosureControl.absentRoot is not in the import closure" in bad
                and "con-leche: accepted " not in bad,"Missing root control failed")
        report["stages"].append("INDEPENDENT_CHECKER_NEGATIVE_CONTROLS_PASS");save()
        _,log=run("selected_38_proof",[binary,"--verified","--jobs=1","--progress=30s","--olean",
                   "--search-path="+search,*["--constant="+n for n in ROOTS],"Main"],
                  cwd=output,env=env,output=output,timeout=14400,memory_mib=50000)
        count=acceptance(log,38,complete_prelude=True)
        report["accepted_declaration_records"]=count
        report["stages"].append("SELECTED_38_TRANSITIVE_PROOF_REPLAY_PASS");save()
        require(all(mounted_readonly(p)==identities[str(p)] for p in mounts),"Reader mount changed")
        require({str(p):file_inventory(p) for p in roots}==inventory,"Compiler objects changed")
        require(packages()==deps and source()==original,"Supplier or dependency source changed")
        clean_checkout(checker_source,CHECKER_HEAD)
        require(sha(binary)==report["checker_binary_sha256"] and
                {n:sha(checker_source/n) for n in git(checker_source,"ls-files").splitlines()}==source_files,
                "Checker source/binary changed")
        verify_file_inventory(runtime,runtime_inventory)
        report["stages"].append("FINAL_INPUT_INTEGRITY_PASS")
        report["status"]="PASS_INDEPENDENT_COMMUNITY_SUPPLIER_38_ONLY"
        code=0
    except BaseException as exc:
        report.update(status="INCOMPLETE_OR_REJECTED",failure=str(exc)[:1500],exception_type=type(exc).__name__)
        code=2
    finally:
        cleanup=[]
        for p in reversed(mounts):
            try:
                subprocess.run(["sudo","-n","umount",str(p)],check=True,timeout=60)
                cleanup.append({"path":str(p),"status":"PASS"})
            except Exception as exc:
                cleanup.append({"path":str(p),"status":"FAIL","error":str(exc)[:300]})
                report["status"]="INCOMPLETE_OR_REJECTED";code=2
        report["mount_cleanup"]=cleanup
        save()
        print(json.dumps({k:report[k] for k in ("status","root_count","proof_acceptance","RH")}),flush=True)
    return code

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checker-work",required=True,type=Path)
    p.add_argument("--axiom-log",required=True,type=Path)
    p.add_argument("--head",required=True)
    p.add_argument("--output",required=True,type=Path)
    sys.exit(verify(p.parse_args()))
