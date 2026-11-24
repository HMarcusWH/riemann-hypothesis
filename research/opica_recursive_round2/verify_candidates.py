"""R2 adapter of the existing R1 fixed evaluator, not a second prover.
R1 source files are untouched. The exact locally reconstructed research epoch
is substituted as an explicit pin; no checker or axiom gate is relaxed.
"""
import argparse,sys
from pathlib import Path
from r2_common import *
sys.path.insert(0,str(R1))
import candidate_validate as evaluator

SUCCESS="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"
def bounded(argv,cwd,env,log,seconds):
    r=command(argv,cwd,env,log,seconds,max_bytes=128<<20)
    return {**r,"log_sha256":r["sha256"]}
def validate(repo,engine,work,manifest,out,mode):
    native=manifest["native"]
    check_pin(engine,native)
    if mode=="native":check_pin(repo,native)
    else:
        need(git(repo,"rev-parse","HEAD")==R1_PIN["original"]["head"],"Wrong original common pin")
        need((repo/"lean-toolchain").read_text().strip()==R1_PIN["original"]["toolchain"],"Wrong original compiler")
    rows=manifest["selected" if mode=="native" else "resolved"]
    need(len(rows)<=BUDGET["attempts_"+mode],"Candidate budget exceeded")
    out.mkdir(parents=True,exist_ok=False)
    evaluator.PIN={**R1_PIN,"native":native}
    evaluator.command=bounded
    # R2 adds post-checks without changing the old endpoint checks.
    evaluator.SUFFIXES=evaluator.SUFFIXES|{"RiemannHypothesis","no_off_line_zero_of_cofinal_moment_slice_bounds","not_cofinal_moment_slice_bounds_of_off_line_zero"}
    evaluator.execute(repo,engine,work,manifest,out,mode,BUDGET["attempts_"+mode])
    raw=read(out/"validation.json");results=[]
    ids=[r["id"] for r in rows];observed=[r["id"] for r in raw["results"]]
    need(len(ids)==len(set(ids))==len(observed)==len(set(observed)) and set(ids)==set(observed),"Validation receipt ID bijection differs")
    for result,candidate in zip(raw["results"],rows):
        need(result["id"]==candidate["id"],"Validation result order differs")
        r={**result,"goal_id":candidate["goal_id"],"target":candidate["target"],"expected_type_sha256":candidate["expected_type_sha256"],"candidate_plan_sha256":digest(candidate["plan"])}
        if r["status"]==SUCCESS:
            from research.RHRC.integration.opica_composition.executor import parse_native
            folder=out/r["id"]
            for filename,marker in (("OpicaAttempt.log","OPICA_NATIVE"),("OpicaConsumer.log","OPICA_INDEPENDENT")):
                x=parse_native(folder/filename,marker)
                if any(forbidden(n) for n in x["constants"]) or not set(x["axioms"])<=ALLOWED:
                    r["status"]="R2_CIRCULAR_OR_AXIOM_DEPENDENCY_REJECTED";break
            if r["status"]==SUCCESS:
                r["actual_local_kernel_proof"]=True
                # These are binders of the proved literal statement, not a
                # claim that arbitrary external mathematical assumptions vanished.
                r["claim_scope"]="EXACT_LOCAL_TARGET_ONLY"
        results.append(r)
    need(len(results)==len(rows),"Missing candidate receipts")
    report={"schema":"OPICA_R2_VALIDATION_V1","mode":mode,"native":native,"results":results,**CLAIMS}
    write(out/"review.json",report);return report
def main():
    p=argparse.ArgumentParser()
    for k in ("repo","engine","work","manifest","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--mode",choices=("native","mixed"),required=True)
    a=p.parse_args();validate(a.repo.resolve(),a.engine.resolve(),a.work.resolve(),read(a.manifest),a.out.resolve(),a.mode)
if __name__=="__main__":main()
