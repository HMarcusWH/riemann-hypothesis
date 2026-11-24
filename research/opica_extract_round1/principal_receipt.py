"""Parse actual source-pinned Lean compiler outputs; not a native proof receipt."""
import argparse, hashlib, json, pathlib
from scan import PIN, need, textgit, write
from adapter_receipt import read_axioms,COMMON
ROOTS=["OPICAExtractionR1.principal_ramp_windows_of_topG_vwin","OPICAExtractionR1.principal_ramp_windows_of_topG_host","OPICAExtractionR1.principal_vwin_of_all"]
NAMES=ROOTS+["OPICAExtractionR1.principal_kept_singleton","OPICAExtractionR1.principal_level_eq_discreteG"]
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--work",type=pathlib.Path,required=True)
    a=p.parse_args();w=a.work
    need(textgit(a.repo,"rev-parse","HEAD")==PIN["original"]["head"],"original source pin mismatch")
    axs=read_axioms((w/"principal.log").read_text(),NAMES)
    common=read_axioms((w/"common.log").read_text(),COMMON)
    rows={}
    for line in (w/"principal-audit.log").read_text().splitlines():
        if line.startswith("OPICA_R1_PRINCIPAL\t"):
            row=json.loads(line.split("\t",1)[1]);n=row["name"]
            need(n in ROOTS and n not in rows and set(row["axioms"])==set(axs[n]),"principal compiler row mismatch")
            need(len(row["dependency_names"])==len(set(row["dependency_names"])) and n in row["dependency_names"],"principal dependency inventory")
            rows[n]=row
    need(set(rows)==set(ROOTS),"missing principal compiler types")
    write(w/"principal-receipt.json",{"schema":"OPICA_R1_ORIGINAL_PRINCIPAL_TYPES_V1","status":"PASS_CONDITIONAL_PRINCIPAL_CUT_ONLY","head":PIN["original"]["head"],"tree":textgit(a.repo,"rev-parse","HEAD^{tree}"),"shared_source_sha256":hashlib.sha256((w/"OPICAExtractionCommon.lean").read_bytes()).hexdigest(),"axioms":axs|common,"rows":list(rows.values()),"proof_acceptance":False,"C1":"OPEN","unconditional_windows":"OPEN"})
    print(json.dumps({"status":"PASS_CONDITIONAL_PRINCIPAL_CUT_ONLY","actual_types":len(rows),"dependency_counts":{n:len(x["dependency_names"]) for n,x in rows.items()},"proof_acceptance":False}))
if __name__=="__main__":main()
