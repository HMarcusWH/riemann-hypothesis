"""Fresh alternate-kernel qualification of shortlisted exact local proofs.
This is a research receipt, never the canonical production acceptance gate.
"""
import argparse,sys,os
from pathlib import Path
from r2_common import *
from verify_candidates import SUCCESS
def run(repo,work,validation,historical,checker_code,out):
    out.mkdir(parents=True,exist_ok=False)
    review=read(validation/"review.json")
    selected=[r for r in review["results"] if r["status"]==SUCCESS and r.get("actual_local_kernel_proof")][:2]
    result={"schema":"OPICA_R2_ALTERNATE_KERNEL_V1","results":[],"status":"NO_ELIGIBLE_LOCAL_PROOF",**CLAIMS}
    try:
        if not selected:return
        check_pin(historical,LOCK["historical"])
        need(git(checker_code,"rev-parse","HEAD")==LOCK["checker"]["head"],"Checker support source pin differs")
        support=historical/"research/RHRC/integration/opica_support_port"
        code=checker_code/"verification/opica-v436"
        sys.path.insert(0,str(support));sys.path.insert(0,str(code))
        from check_candidate import PRIMITIVES
        from independent_port import import_roots
        from common import CHECKER_HEAD,RUNTIME_SHA,RUNTIME_BYTES,clean_env,clean_checkout,file_inventory,verify_file_inventory,sha,git as checker_git,run as bounded
        from independent_38 import acceptance
        env=compiler_env()
        bootdir=out/"bootstrap"
        b=command([sys.executable,str(code/"bootstrap_checker.py"),"--work",bootdir],repo,env,out/"bootstrap.log",seconds=4200)
        need(b["status"]=="PASS","Fresh alternate checker build failed")
        boot=read(bootdir/"BOOTSTRAP_RECEIPT.json")
        need(boot["status"]=="PASS" and boot["source_head"]==CHECKER_HEAD and boot["runtime_archive_sha256"]==RUNTIME_SHA and boot["runtime_archive_bytes"]==RUNTIME_BYTES,"Alternate checker bootstrap identity")
        runtime=Path(boot["runtime"]).resolve();checker=Path(boot["source"]).resolve()
        binary=Path(boot["tools"]["con-leche"]["path"]).resolve()
        clean_checkout(checker,CHECKER_HEAD)
        need(binary==checker/".lake/build/bin/con-leche" and sha(binary)==boot["tools"]["con-leche"]["sha256"],"Checker binary changed")
        source_inventory=read(Path(boot["source_inventory"]));runtime_inventory=read(Path(boot["runtime_inventory"]))
        need(filehash(Path(boot["source_inventory"]))==boot["source_inventory_sha256"] and filehash(Path(boot["runtime_inventory"]))==boot["runtime_inventory_sha256"],"Checker inventory bytes differ")
        need({n:sha(checker/n) for n in checker_git(checker,"ls-files").splitlines()}==source_inventory,"Checker source differs")
        verify_file_inventory(runtime,runtime_inventory)
        lean=Path(subprocess.check_output(["lake","env","which","lean"],cwd=repo,env=env,text=True).strip())
        prefix=Path(subprocess.check_output([lean,"--print-prefix"],cwd=repo,env=env,text=True).strip())
        lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=repo,env=env,text=True).strip()
        paths,pathreceipt=import_roots(repo,lp,prefix/"lib/lean")
        write(out/"import-roots.json",pathreceipt)
        # Same independently verified negative controls as the historical port.
        env2=clean_env(runtime,1)
        fixture=out/"fixture";fixture.mkdir()
        f=fixture/"ClosureControl.lean";f.write_text("namespace ClosureControl\naxiom uncheckedLeaf : False\ntheorem selectedRoot : False := uncheckedLeaf\ntheorem unrelatedRoot : True := True.intro\nend ClosureControl\n")
        bounded("fixture_compile",[runtime/"bin/lean","--root="+str(fixture),"-o",fixture/"ClosureControl.olean",f],cwd=fixture,env=env2,output=out,timeout=120,memory_mib=2048)
        args=[binary,"--verified","--jobs=1","--progress=30s","--olean","--search-path="+str(fixture)+os.pathsep+str(runtime/"lib/lean")]
        _,good=bounded("control_unused_axiom",[*args,"--constant=ClosureControl.unrelatedRoot","ClosureControl"],cwd=fixture,env=env2,output=out,timeout=300,memory_mib=2048);acceptance(good,1)
        _,bad=bounded("control_transitive_axiom",[*args,"--constant=ClosureControl.selectedRoot","ClosureControl"],cwd=fixture,env=env2,output=out,timeout=300,memory_mib=2048,expected=2)
        need("not implemented yet: non-standard axiom (ClosureControl.uncheckedLeaf)" in bad and "con-leche: accepted " not in bad,"Axiom control failed")
        _,bad=bounded("control_missing_root",[*args,"--constant=ClosureControl.absentRoot","ClosureControl"],cwd=fixture,env=env2,output=out,timeout=300,memory_mib=2048,expected=3)
        need("the constant ClosureControl.absentRoot is not in the import closure" in bad and "con-leche: accepted " not in bad,"Missing-root control failed")
        result["negative_controls"]="PASS"
        def verify(module,root,roots,label):
            folders=[Path(p).resolve() for p in roots]
            inventories={str(p):digest(file_inventory(p)) for p in folders}
            names=list(PRIMITIVES)+[root]
            need(len(names)==len(set(names)),"Alternate root identity")
            _,log=bounded(label,[binary,"--verified","--jobs=1","--progress=30s","--olean","--search-path="+os.pathsep.join(map(str,folders)),*["--constant="+n for n in names],module],cwd=out,env=env2,output=out,timeout=3000,memory_mib=10000)
            count=acceptance(log,len(names),complete_prelude=True)
            need({str(p):digest(file_inventory(p)) for p in folders}==inventories,"Alternate checker input objects changed")
            return {"status":"PASS_ALTERNATE_SELECTED_CLOSURE_ONLY","root":root,"accepted_declaration_records":count,"selected_roots":names,"object_inventory_digests":inventories}
        for r in selected:
            item={"id":r["id"],"target":r["target"],"status":"INCOMPLETE"}
            result["results"].append(item)
            try:
                candidate=validation/r["id"]
                for name,h in r["files"].items():need(filehash(candidate/name)==h,"Candidate object inventory drift")
                need((candidate/"OpicaConsumer.olean").is_file(),"Missing independently compiled consumer")
                roots=[candidate,work,*paths]
                item.update(verify("OpicaConsumer","OpicaConsumer.result",roots,"selected-"+r["id"][:16]))
                if review["mode"]=="native" and r["target"]["declaration"] in ("OPICAR2.C1Named","Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"):
                    # Terminal consumer is used only after the independent C1 proof,
                    # never as a retrieval input. No canonical claim promotion.
                    td=out/("terminal-"+r["id"][:16]);td.mkdir()
                    path=td/"R2Terminal.lean"
                    path.write_text("import OpicaConsumer\nimport Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure\nopen Lean Elab Command\ntheorem OPICAR2TerminalCandidate : RiemannHypothesis :=\n  Zeta23.OPICARound4.ArithmeticFrontier.riemannHypothesis_of_cofinal_moment_slice_bounds OpicaConsumer.result\nrun_cmd do\n  let a ← Lean.collectAxioms "+chr(96)+"OPICAR2TerminalCandidate\n  unless a.all (fun n => [\"propext\", \"Classical.choice\", \"Quot.sound\"].contains n.toString) do\n    throwError \"Terminal candidate contains unapproved axiom\"\n")
                    local={**env,"LEAN_PATH":os.pathsep.join(map(str,[td,*roots]))}
                    comp=command([lean,"--root="+str(td),"-DwarningAsError=true","-o",td/"R2Terminal.olean",path],repo,local,td/"build.log",seconds=600)
                    need(comp["status"]=="PASS","Terminal consumer compile failed")
                    stock=command([prefix/"bin/leanchecker","--fresh","--verbose","R2Terminal"],repo,local,td/"stock.log",seconds=900)
                    need(stock["status"]=="PASS","Terminal stock replay failed")
                    item["terminal_candidate"]=verify("R2Terminal","OPICAR2TerminalCandidate",[td,*roots],"terminal-check-"+r["id"][:16])
                    item["terminal_claim"]="CANDIDATE_ONLY_CANONICAL_PRODUCTION_REVIEW_REQUIRED"
            except Exception as ex:
                item["status"]="REJECTED_OR_INCOMPLETE";item["reason"]=str(ex)[:1500]
        verify_file_inventory(runtime,runtime_inventory);clean_checkout(checker,CHECKER_HEAD)
        need(sha(binary)==boot["tools"]["con-leche"]["sha256"] and {n:sha(checker/n) for n in checker_git(checker,"ls-files").splitlines()}==source_inventory,"Checker changed during validation")
        result["status"]="CHECKED_SELECTED_CLOSURES" if all(r["status"]=="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY" for r in result["results"]) else "INCOMPLETE_EXECUTION"
    except Exception as ex:result["status"]="INCOMPLETE_EXECUTION";result["reason"]=str(ex)[:1800]
    finally:write(out/"review.json",result)
def main():
    p=argparse.ArgumentParser()
    for k in ("repo","work","validation","historical","checker-code","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.repo,a.work,a.validation,a.historical,a.checker_code,a.out)
if __name__=="__main__":main()
