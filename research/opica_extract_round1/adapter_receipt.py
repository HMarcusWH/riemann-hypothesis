"""Verify exact adapter compiler axiom reports; no cross-pin proof promotion."""
import argparse, hashlib, json, pathlib, re
from scan import PIN, need, write
COMMON=["OPICAExtractionR1.discreteG_eq_rampG","OPICAExtractionR1.windows_congr"]
NAMES={"native":["OPICAExtractionR1.native_literalG_eq_rampG","OPICAExtractionR1.native_windows_of_ramp_windows"],
       "external":["OPICAExtractionR1.external_G_eq_rampG","OPICAExtractionR1.external_windows_to_ramp"],
       "energy":["OPICAExtractionR1.rampG_continuousOn_pos","OPICAExtractionR1.window_energy_bound","OPICAExtractionR1.native_energy_of_ramp_windows","OPICAExtractionR1.native_energy_of_literal_windows","OPICAExtractionR1.native_c1_of_ramp_windows_of_direct_bridge"]}
def read_axioms(text,expected):
    need(not re.search(r"\bsorryAx\b|\berror:",text),"forbidden axiom or compiler error")
    matches=re.findall(r"(?m)^'([^'\n]+)' (?:depends on axioms:\s*\[([^\]]*)\]|does not depend on any axioms)[ \t]*(?=\n|$)",text)
    result={}
    for name,raw in matches:
        vals=[x.strip() for x in raw.split(",") if x.strip()]
        need(name in expected and name not in result and len(vals)==len(set(vals)) and set(vals)<=set(PIN["allowed_axioms"]),"unexpected axiom report")
        result[name]=vals
    need(set(result)==set(expected),"missing axiom reports: "+repr(set(expected)-set(result)))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--world",choices=("native","external","energy"),required=True);p.add_argument("--work",type=pathlib.Path,required=True)
    a=p.parse_args();w=a.work
    common=read_axioms((w/"common.log").read_text(),COMMON)
    other=read_axioms((w/(a.world+".log")).read_text(),NAMES[a.world])
    src=w/"OPICAExtractionCommon.lean"
    result={"schema":"OPICA_R1_ADAPTER_RECEIPT","world":a.world,"source":PIN["native" if a.world in ("native","energy") else "supplier"],"shared_source_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"axioms":common|other,"status":"PASS_LOCAL_PIN_NORMALIZATION_ONLY","cross_pin_kernel_equality":"NOT_ESTABLISHED","proof_acceptance":False,"C1":"OPEN"}
    write(w/("energy-receipt.json" if a.world=="energy" else "adapter-receipt.json"),result)
    print(json.dumps({"status":result["status"],"world":a.world,"axiom_rows":len(result["axioms"]),"proof_acceptance":False}))
