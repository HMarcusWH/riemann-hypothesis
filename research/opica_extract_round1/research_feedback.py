"""Post-green research handoff: exact receipts, new leads, failure taxonomy."""
import argparse,json,pathlib
from scan import PIN,need,write
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();attempts=[];cross=None;lanes={}
    for path in sorted(a.inputs.rglob("*.json")):
        if path.name not in {"validation.json","cross-world-retrieval.json","source-cuts.json","principal-receipt.json","energy-receipt.json","adapter-receipt.json","original-dependencies.json"}:continue
        x=json.loads(path.read_text())
        key=str(path.relative_to(a.inputs));lanes[key]=x.get("status",x.get("schema"))
        if path.name=="validation.json":
            need(x["proof_acceptance"] is False,"unexpected authority")
            attempts.extend({"id":r["id"],"mode":r["mode"],"label":r["label"],"status":r["status"],"reason":r.get("reason"),"dependencies":r.get("dependency_count"),"premise_count":len(r.get("premises",[]))} for r in x["results"])
        elif path.name=="cross-world-retrieval.json":cross=x
    verified=[r for r in attempts if r["status"]=="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"]
    failures=[r for r in attempts if r not in verified]
    result={"schema":"OPICA_R1_POST_GREEN_RESEARCH_FEEDBACK","status":"REVIEW_REQUIRED","lane_evidence":lanes,
            "formally_checked_local_candidates":verified,"failed_or_incomplete_candidates":failures,
            "next_search_frontier":(cross or {}).get("premise_frontier",[]),
            "upstream":["Specialize TopG to PrincipalConnected and discharge host/connectedness premises.","Revisit row/geometry suppliers using actual dependency unions."],
            "downstream":["Transport actual cofinal literal windows to energy; do not invert this implication.","DirectEnergyToC1 remains OPEN; investigate native moment, pole and signed arithmetic constraints."],
            "falsification":["Reject endpoint and axiom dependencies, mismatched definitions and weakened horizon/parity.","Separate conditional local proof from unconditional arithmetic closure; no cross-pin receipt transfer.","Compare closure unions only within authenticated export epoch."],
            "next_round_authority":"REVIEWED_REGISTRY_UPDATE_REQUIRED; no automated promotion",
            "C1":"OPEN","independent_step4":"OPEN","proof_acceptance":False}
    write(a.output,result);print(json.dumps({"status":result["status"],"local_candidates":len(verified),"failed_or_open":len(failures),"proof_acceptance":False}))
if __name__=="__main__":main()
