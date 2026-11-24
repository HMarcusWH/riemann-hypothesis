"""Construct a local research epoch from exact native source, never foreign objects."""
import argparse,os,subprocess
from pathlib import Path
from r2_common import *

SUPPORT="research/RHRC/integration/opica_support_port/"
def prepare(native,historical,harvest,output):
    native=native.resolve();historical=historical.resolve();harvest=harvest.resolve()
    check_pin(native,LOCK["native"]);check_pin(historical,LOCK["historical"])
    h=read(harvest/"harvest.json");need(h["proof_acceptance"] is False,"Harvest cannot grant authority")
    spec=read(historical/SUPPORT/"PORT_CONTRACT.json")
    roots=[n for row in spec["historical_package_roots"] for n in row["receipt_roots"]]
    need(len(roots)==len(set(roots))==167,"Historical root population differs")
    rows=spec["candidate_modules"];need(len(rows)==24,"Historical module population differs")
    accepted=[];status="HISTORICAL_SUPPORT_NOT_YET_QUALIFIED"
    receipt=h["artifact_receipts"].get("historical")
    if receipt:
        p=harvest/"inputs/historical/reviewed-old-cross-pin-type-comparison.json"
        need(filehash(p)==receipt["entries"][p.name]["sha256"],"Historical comparison bytes differ")
        r=read(p)
        source=r["source"]
        need(source["checked_commit"]==LOCK["historical"]["head"] and source["checked_tree"]==LOCK["historical"]["tree"],"Historical source receipt drift")
        review=r["review_controller"];pin=LOCK["historical_review"]
        need(review["checked_commit"]==pin["head"] and review["checked_tree"]==pin["tree"] and r["reviewed_old_evidence"] is True,"Historical review controller identity")
        need(r["schema"]=="OPICA_SUPPORT_CROSS_PIN_TYPE_COMPARISON_V2" and r["status"]=="PASS_RELOCATION_AWARE_ROOT_TYPE_DAGS_AND_AXIOMS_ONLY" and r["root_count"]==r["normalized_type_matches"]==167 and r["exact_type_matches"]+r["relocation_type_matches"]==167 and len(r["raw_type_differences"])==len(r["relocation_matches"])==r["relocation_type_matches"] and not r["type_differences"] and not r["axiom_differences"],"Historical relocation comparison not complete")
        need(r["proof_acceptance"] is False and source["roots"]==roots,"Historical source root set differs")
        # Verify the sealed source on the original historical branch before copying.
        subprocess.run(["python3","-B",str(historical/SUPPORT/"check_candidate.py")],cwd=historical,check=True,timeout=900,env=compiler_env())
        for row in spec["existing_native_modules"]:
            need(filehash(native/row["path"])==row["sha256"],"Inherited native dimension module differs")
        for row in rows:
            rel=row["path"];src=historical/rel;dst=native/rel
            need(rel.startswith("Zeta23/OPICASupport/") and rel.endswith(".lean") and not dst.exists(),"Source overlay collision")
            need(src.is_file() and not src.is_symlink() and filehash(src)==row["ported_sha256"],"Historical source hash drift")
            dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes());accepted.append({"path":rel,"sha256":filehash(dst),"module":row["module"]})
        paths=[x["path"] for x in accepted]
        subprocess.run(["git","-C",str(native),"add","--",*paths],check=True)
        diff=git(native,"diff","--cached","--name-status","--no-renames").splitlines()
        need(set(diff)=={"A\t"+p for p in paths},"Unexpected local source delta")
        env={**os.environ,"GIT_AUTHOR_NAME":"OPICA research epoch","GIT_AUTHOR_EMAIL":"opica-epoch@invalid.example","GIT_COMMITTER_NAME":"OPICA research epoch","GIT_COMMITTER_EMAIL":"opica-epoch@invalid.example","GIT_AUTHOR_DATE":"2026-11-24T00:00:00Z","GIT_COMMITTER_DATE":"2026-11-24T00:00:00Z"}
        tree=git(native,"write-tree")
        commit=subprocess.check_output(["git","-C",str(native),"commit-tree",tree,"-p",LOCK["native"]["head"],"-m","OPICA R2 exact historical source overlay; research only"],env=env,text=True).strip()
        subprocess.run(["git","-C",str(native),"checkout","--detach",commit],check=True)
        need(not git(native,"status","--porcelain","--untracked-files=all"),"Local epoch checkout dirty")
        status="HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH"
    pin={**LOCK["native"],"head":git(native,"rev-parse","HEAD"),"tree":git(native,"rev-parse","HEAD^{tree}")}
    report={"schema":"OPICA_R2_LOCAL_RESEARCH_EPOCH_V1","native":pin,"base":LOCK["native"],"historical":LOCK["historical"],"historical_status":status,"overlay":accepted,"historical_roots":roots if accepted else [],"historical_modules":[x["module"] for x in rows+spec["existing_native_modules"]] if accepted else [],"canonical_production_admission":"NOT_ESTABLISHED",**CLAIMS}
    write(output,report);return report
def main():
    p=argparse.ArgumentParser()
    for k in ("native","historical","harvest","output"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();prepare(a.native,a.historical,a.harvest,a.output)
if __name__=="__main__":main()
