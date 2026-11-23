#!/usr/bin/env python3
"""Fresh same-4.36-pin native bridge candidate, never original-pin closure."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from common import (require, read_json, write_json, sha, clean_env, clean_checkout,
                    file_inventory, verify_file_inventory, git, run, CHECKER_HEAD,
                    RUNTIME_SHA, RUNTIME_BYTES)
from qualify import REPO, source, PUBLIC_ROOTS, ALLOWED
from independent_38 import ROOTS, acceptance, packages, mounted_readonly

HERE=Path(__file__).resolve().parent
BRIDGE=HERE/"native_bridge"
NATIVE_HEAD="7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9"
NATIVE_TREE="9248b76d7aff60aab3bb775c4be9750dc6006003"
NATIVE_URL="https://github.com/HMarcusWH/zeta-23-lean.git"
ORIGINAL_GATE="acb5b817a6b174bf0fff35da9957a28b914ab888"
MATHLIB="fc4f59e577feb1a4956671bc04ac18aaaf8cd842"
PIN="leanprover/lean4:v4.36.0"
TOPIC="refs/heads/research/opica-community-v436-supplier-qualification-20261123"
MODULES=("ReceiverAudit","ClaimFingerprint","BoundaryFlatCharacterization","NativeValidated","ImportGuard","MainClosedBridge")
NATIVE_ROOTS=(
    "Zeta23.OPICARound19.ReceiverAudit.exactReceiver",
    "Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_reflexive",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_is_native",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive",
    "Zeta23.OPICARound20.even_zero_bound_of_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.riemannHypothesis_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.finite_negative_boundary_flat_witness_refutes_c1",
    "Zeta23.OPICARound20.Closed.step4C1",
    "Zeta23.OPICARound20.Closed.literalC1",
    "Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity",
)
COMBINED=ROOTS+NATIVE_ROOTS

def blob_oid(path):
    raw=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()

def bridge_contract():
    contract=read_json(BRIDGE/"SOURCE.json")
    require(contract["historical_gate_commit"]==ORIGINAL_GATE and
            set(contract["source_blobs"])=={n+".lean" for n in MODULES},"Original bridge inventory differs")
    require(all(blob_oid(BRIDGE/name)==oid for name,oid in contract["source_blobs"].items()),
            "Original bridge source bytes differ")
    path=BRIDGE/"SELECTED_ROOT_INVENTORY.json"
    require(blob_oid(path)==contract["selected_inventory_blob"],"Original root inventory bytes differ")
    inv=read_json(path)
    require(inv["ordered_roots"]==list(COMBINED) and inv["mathematical_roots"]==list(PUBLIC_ROOTS)+list(NATIVE_ROOTS)
            and len(COMBINED)==len(set(COMBINED))==50,"Exact original 50-root set differs")
    return contract

def named_axioms(text, roots):
    require(not re.search(r"\bsorryAx\b|(?:^|\n).*?\berror:",text),"Compiler error or sorryAx")
    rows=re.findall(r"(?m)^'([^'\n]+)' (?:depends on axioms:\s*\[([^\]]*)\]|does not depend on any axioms)[ \t]*(?=\n|$)",text)
    result={}
    for name,raw in rows:
        require(name in roots and name not in result,"Unexpected/duplicate axiom report: "+name)
        values=[x.strip() for x in raw.split(",") if x.strip()]
        require(len(values)==len(set(values)) and set(values)<=ALLOWED,"Unapproved axiom: "+name)
        result[name]=sorted(values)
    require(set(result)==set(roots),"Incomplete named axiom reports")
    return result

def verify(args):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("RUNNER_ENVIRONMENT")=="self-hosted" and
            os.environ.get("GITHUB_REPOSITORY")=="HMarcusWH/riemann-hypothesis" and
            os.environ.get("GITHUB_REF")==TOPIC and os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and
            args.head==os.environ.get("GITHUB_SHA"),"Dedicated reviewed candidate execution required")
    output=args.output.resolve()
    require(not output.exists() and not output.is_relative_to(REPO),"Fresh external candidate directory required")
    output.mkdir(parents=True)
    report={"schema":"OPICA_COMMUNITY_V436_COMBINED_NATIVE_CANDIDATE_V1","status":"INCOMPLETE",
            "supplier_head":args.head,"native_head":NATIVE_HEAD,"native_tree":NATIVE_TREE,
            "compiler":PIN,"mathlib":MATHLIB,"root_count":50,"roots":list(COMBINED),"stages":[],
            "native_original_pin_transfer":"NOT_ESTABLISHED","original_30_plus_7":"NOT_RUN",
            "proof_acceptance":False,"RH":"OPEN","C1":"OPEN","Step4":"OPEN"}
    def save():write_json(output/"RECEIPT.json",report)
    mounts=[];save()
    try:
        original=source();require(original["head"]==args.head,"Supplier head differs")
        report["bridge_source"]=bridge_contract()
        prior=read_json(args.supplier_receipt/"RECEIPT.json")
        require(prior["status"]=="PASS_INDEPENDENT_COMMUNITY_SUPPLIER_38_ONLY" and prior["source"]==original and
                prior["roots"]==list(ROOTS) and prior["proof_acceptance"] is False and
                prior["head"]==args.head and all(x["status"]=="PASS" for x in prior["mount_cleanup"]),
                "Actual preceding supplier qualification required")
        before=read_json(args.supplier_receipt/"OBJECT_INVENTORY.json")
        require(sha(args.supplier_receipt/"OBJECT_INVENTORY.json")==prior["object_inventory_sha256"],
                "Supplier object inventory digest differs")
        for p,inventory in before.items():verify_file_inventory(p,inventory)
        boot=read_json(args.checker_work/"BOOTSTRAP_RECEIPT.json")
        require(boot["status"]=="PASS" and boot["source_head"]==CHECKER_HEAD and
                boot["runtime_archive_sha256"]==RUNTIME_SHA and boot["runtime_archive_bytes"]==RUNTIME_BYTES,
                "Fresh independently pinned checker required")
        runtime=Path(boot["runtime"]).resolve();checker_source=Path(boot["source"]).resolve()
        checker=Path(boot["tools"]["con-leche"]["path"]).resolve()
        require(checker==checker_source/".lake/build/bin/con-leche" and
                sha(checker)==boot["tools"]["con-leche"]["sha256"]==prior["checker_binary_sha256"] and
                sha(runtime/"bin/lean")==prior["stock_compiler_sha256"],"Supplier checker/runtime binding differs")
        clean_checkout(checker_source,CHECKER_HEAD)
        checker_sources=read_json(Path(boot["source_inventory"]))
        require(sha(Path(boot["source_inventory"]))==boot["source_inventory_sha256"] and
                {n:sha(checker_source/n) for n in git(checker_source,"ls-files").splitlines()}==checker_sources,
                "Checker source inventory differs")
        runtime_files=read_json(Path(boot["runtime_inventory"]))
        require(sha(Path(boot["runtime_inventory"]))==boot["runtime_inventory_sha256"],"Runtime manifest differs")
        verify_file_inventory(runtime,runtime_files)
        deps=packages();require(deps==prior["package_pins"],"Supplier package pins changed")
        env=clean_env(runtime,2)
        native=output/"native-source"
        # Fixed public repository and commit; never a caller-controlled ref.
        subprocess.run(["git","init",str(native)],check=True,timeout=30,env=env)
        subprocess.run(["git","-C",str(native),"remote","add","origin",NATIVE_URL],check=True,timeout=30,env=env)
        subprocess.run(["git","-C",str(native),"fetch","--depth=1","--no-tags","origin",NATIVE_HEAD],check=True,timeout=900,env=env)
        subprocess.run(["git","-C",str(native),"checkout","--detach","FETCH_HEAD"],check=True,timeout=300,env=env)
        clean_checkout(native,NATIVE_HEAD)
        require(git(native,"rev-parse","HEAD^{tree}")==NATIVE_TREE,"Pinned native source tree differs")
        # The only native edits permitted are the new compiler/dependency pins and
        # unchanged, separately reviewed bridge modules. No native proof rewrites.
        lake=native/"lakefile.toml"
        original_lake=lake.read_text()
        old_pin="51e6992efd06126df61a496bebf8f49482a4e129"
        require(original_lake.count(old_pin)==1,"Native dependency anchor differs")
        lake.write_text(original_lake.replace(old_pin,MATHLIB)+'\n[[lean_lib]]\nname = "OPICAStep4"\n')
        (native/"lean-toolchain").write_text(PIN+"\n")
        lock=read_json(REPO/"lake-manifest.json")
        require(lock["name"]=="tree" and lock["packagesDir"]==".lake/packages","Supplier Lake lock differs")
        lock["name"]="Zeta23"
        write_json(native/"lake-manifest.json",lock)
        (native/".lake").mkdir(exist_ok=True)
        require(not (native/".lake/packages").exists(),"Fresh native dependency path required")
        # Use one actual Mathlib object environment, not incompatible copied oleans.
        (native/".lake/packages").symlink_to(REPO/".lake/packages",target_is_directory=True)
        (native/"OPICAStep4").mkdir()
        for mod in MODULES:
            shutil.copyfile(BRIDGE/(mod+".lean"),native/"OPICAStep4"/(mod+".lean"))
        allowed={"lean-toolchain","lakefile.toml","lake-manifest.json"}|{"OPICAStep4/"+m+".lean" for m in MODULES}
        initial={p:sha(native/p) for p in sorted(allowed)}
        def check_native():
            require(git(native,"rev-parse","HEAD")==NATIVE_HEAD and git(native,"rev-parse","HEAD^{tree}")==NATIVE_TREE,
                    "Native revision changed")
            tracked=set(git(native,"diff","--name-only","HEAD").splitlines())
            untracked=set(git(native,"ls-files","--others","--exclude-standard").splitlines())
            require(tracked|untracked==allowed and all(sha(native/p)==s for p,s in initial.items()),
                    "Unexpected native source mutation")
            require((native/".lake/packages").resolve()==(REPO/".lake/packages").resolve(),
                    "Shared Mathlib object root differs")
        check_native()
        report["native_candidate_inputs"]=initial;report["stages"].append("EXACT_NATIVE_AND_BRIDGE_SOURCE_PREPARED");save()
        run("native_only_build",[runtime/"bin/lake","--no-cache","build","OPICAStep4.NativeValidated"],
            cwd=native,env=env,output=output,timeout=10800,memory_mib=100000)
        check_native()
        require((native/".lake/build/lib/lean/OPICAStep4/NativeValidated.olean").is_file(),"Native-only build object missing")
        raw=subprocess.check_output([str(runtime/"bin/lake"),"env","printenv","LEAN_PATH"],cwd=native,env=env,text=True,timeout=120).strip()
        native_roots=[Path(p).resolve() for p in raw.split(os.pathsep) if p]
        native_objects=(native/".lake/build/lib/lean").resolve();supplier_objects=(REPO/".lake/build/lib/lean").resolve()
        core=(runtime/"lib/lean").resolve()
        if core not in native_roots:native_roots.append(core)
        require(set(native_roots)==(set(map(Path,before))-{supplier_objects})|{native_objects} and len(native_roots)==len(set(native_roots)),
                "Native import roots are not the exact shared object environment")
        # Check all supplier and Mathlib bytes again; no mutation by Lake allowed.
        for p,inventory in before.items():verify_file_inventory(p,inventory)
        native_inventory=file_inventory(native_objects)
        collisions=set(native_inventory)&set(before[str(supplier_objects)])
        require(not any(x.endswith((".olean",".olean.private",".olean.server")) for x in collisions),
                "Supplier/native module collision")
        strict=clean_env(runtime,2);strict["LEAN_PATH"]=os.pathsep.join(map(str,native_roots))
        # Compile the original native-only receiving/fingerprint modules strictly.
        for mod in MODULES[:4]:
            run("native_strict_"+mod,[runtime/"bin/lean","--root="+str(native),"-DwarningAsError=true",native/"OPICAStep4"/(mod+".lean")],
                cwd=native,env=strict,output=output,timeout=1800,memory_mib=60000)
        stock=runtime/"bin/leanchecker";require(stock.is_file(),"Official stock checker absent")
        run("native_fresh_stock",[stock,"--fresh","--verbose","OPICAStep4.NativeValidated"],
            cwd=native,env=strict,output=output,timeout=10800,memory_mib=100000)
        report["stages"].append("NATIVE_ONLY_COMPILER_AND_STOCK_REPLAY_PASS");save()
        combined_objects=output/"combined-objects";(combined_objects/"OPICAStep4").mkdir(parents=True)
        roots=[combined_objects,native_objects,supplier_objects]+[p for p in native_roots if p!=native_objects]
        require(len(roots)==len(set(roots)),"Duplicate combined object roots")
        combined_env=clean_env(runtime,2);combined_env["LEAN_PATH"]=os.pathsep.join(map(str,roots))
        for mod in MODULES[4:]:
            run("strict_"+mod,[runtime/"bin/lean","--root="+str(native),"-DwarningAsError=true",
                    "-o",combined_objects/"OPICAStep4"/(mod+".olean"),native/"OPICAStep4"/(mod+".lean")],
                cwd=native,env=combined_env,output=output,timeout=14400,memory_mib=100000)
        require("OPICA20_NEW_NAMES_ABSENT" in (output/"strict_ImportGuard.log").read_text(),
                "Missing actual preexisting-name rejection control")
        audit=output/"CombinedAudit.lean"
        audit.write_text("import OPICAStep4.MainClosedBridge\n"+"\n".join("#print axioms "+n for n in (*PUBLIC_ROOTS,*NATIVE_ROOTS))+"\n")
        _,log=run("combined_named_axioms",[runtime/"bin/lean","--root="+str(output),"-DwarningAsError=true",audit],
                   cwd=output,env=combined_env,output=output,timeout=14400,memory_mib=100000)
        report["axioms"]=named_axioms(log,(*PUBLIC_ROOTS,*NATIVE_ROOTS))
        run("combined_fresh_stock",[stock,"--fresh","--verbose","OPICAStep4.MainClosedBridge"],
            cwd=native,env=combined_env,output=output,timeout=14400,memory_mib=100000)
        report["stages"].append("COMBINED_50_ROOT_COMPILER_AXIOMS_AND_STOCK_REPLAY_PASS");save()
        # Verify the same 50 roots with the independent checker under read-only views.
        inventories={str(p):file_inventory(p) for p in roots}
        write_json(output/"COMBINED_OBJECT_INVENTORY.json",inventories)
        view=output/"views";view.mkdir();identities={}
        for index,p in enumerate(roots):
            dest=view/str(index);dest.mkdir()
            subprocess.run(["sudo","-n","mount","--bind",str(p),str(dest)],check=True,timeout=60)
            mounts.append(dest)
            subprocess.run(["sudo","-n","mount","-o","remount,bind,ro",str(dest)],check=True,timeout=60)
            identities[str(dest)]=mounted_readonly(dest)
        search=os.pathsep.join(map(str,mounts))
        _,log=run("selected_50_proof",[checker,"--verified","--jobs=1","--progress=30s","--olean",
                    "--search-path="+search,*["--constant="+n for n in COMBINED],"OPICAStep4.MainClosedBridge"],
                    cwd=output,env=env,output=output,timeout=14400,memory_mib=100000)
        report["accepted_declaration_records"]=acceptance(log,50,complete_prelude=True)
        require(all(mounted_readonly(p)==identities[str(p)] for p in mounts),"Read-only object view changed")
        for p,inventory in inventories.items():verify_file_inventory(p,inventory)
        for p,inventory in before.items():verify_file_inventory(p,inventory)
        clean_checkout(checker_source,CHECKER_HEAD)
        require(sha(checker)==prior["checker_binary_sha256"] and
                {n:sha(checker_source/n) for n in git(checker_source,"ls-files").splitlines()}==checker_sources,
                "Checker source or executable changed")
        verify_file_inventory(runtime,runtime_files)
        check_native();require(source()==original and packages()==deps and bridge_contract()==report["bridge_source"],
                               "Combined inputs changed during execution")
        report["stages"].append("EXACT_50_ROOT_INDEPENDENT_PROOF_AND_FINAL_INTEGRITY_PASS")
        report["status"]="PASS_SAME_436_PIN_COMBINED_CANDIDATE_ONLY"
        code=0
    except BaseException as exc:
        report.update(status="INCOMPLETE_OR_REJECTED",failure=str(exc)[:1800],exception_type=type(exc).__name__)
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
        report["mount_cleanup"]=cleanup;save()
        print(json.dumps({k:report[k] for k in ("status","root_count","proof_acceptance","RH")}),flush=True)
    return code

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--head",required=True)
    p.add_argument("--checker-work",type=Path,required=True)
    p.add_argument("--supplier-receipt",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    sys.exit(verify(p.parse_args()))
