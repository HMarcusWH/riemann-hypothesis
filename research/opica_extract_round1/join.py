"""Compose evidence, not proof terms; every missing premise remains explicit."""
import argparse, json, pathlib
from scan import PIN, need, write
def read(p):return json.loads(p.read_text()) if p.is_file() else None
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();i=a.inputs
    # GitHub artifact names carry exact run/head identity; this is a research
    # summary of files from this run, never a qualification receipt.
    def find(name,part):
        found=[x for x in i.rglob(name) if part in str(x)]
        need(len(found)<=1,"ambiguous artifact: "+name)
        return read(found[0]) if found else None
    cuts=find("source-cuts.json","source-cuts")
    graph=find("original-dependencies.json","original-proof-graph")
    native=find("native-retrieval.json","extraction-native")
    if native is None:native=find("native-retrieval-base.json","extraction-native")
    principal=find("principal-receipt.json","extraction-principal")
    cross=find("cross-world-retrieval.json","extraction-cross-world")
    energy=find("energy-receipt.json","extraction-native")
    nr=find("adapter-receipt.json","extraction-native")
    er=find("adapter-receipt.json","external-small-adapter")
    statuses={"source":bool(cuts and cuts.get("nodes")),"original_export":bool(graph and graph.get("raw_sha256")==PIN["original"]["solution"]["raw_sha256"]),
              "native_types":bool(native and native.get("targets")),"native_adapter":bool(nr and nr.get("status")=="PASS_LOCAL_PIN_NORMALIZATION_ONLY"),
              "external_adapter":bool(er and er.get("status")=="PASS_LOCAL_PIN_NORMALIZATION_ONLY"),
              "principal_conditional_cut":bool(principal and principal.get("status")=="PASS_CONDITIONAL_PRINCIPAL_CUT_ONLY"),
              "energy_conditional_bridge":bool(energy and energy.get("status")=="PASS_LOCAL_PIN_NORMALIZATION_ONLY"),
              "cross_world_search":bool(cross and cross.get("status")=="RESEARCH_QUERIES_EXECUTED_NOT_PROOF")}
    norm=statuses["native_adapter"] and statuses["external_adapter"] and nr["shared_source_sha256"]==er["shared_source_sha256"]
    gmap={x["name"]:x for x in (graph or {}).get("roots",[])} if statuses["original_export"] else {}
    cmap={x["name"]:x for x in (cuts or {}).get("nodes",[])}
    leads=[]
    for row in PIN["catalog"]:
        name=row["name"];g=gmap.get(name,{});c=cmap.get(name,{})
        if row["role"].endswith("_EXCLUDED") or row["role"].endswith("DEFINITION"):continue
        leads.append({"name":name,"role":row["role"],"purpose":row["reason"],"source_current":c.get("current",{}).get("status","NOT_RUN"),
                      "original_dependency_status":g.get("closure",{}).get("status",g.get("status","NOT_RUN")),
                      "closure_declarations":g.get("closure",{}).get("declarations"),
                      "actual_type_references":g.get("type_dependencies",{}).get("constants"),
                      "excluded_dependencies":g.get("excluded_dependencies"),
                      "admission":"RESEARCH_LEAD_ONLY_NOT_APPROVED_CONSTANT"})
    ranked=[x for x in leads if x["original_dependency_status"]=="COMPLETE" and x["excluded_dependencies"]==[] and set(gmap[x["name"]]["closure"]["axioms"])<=set(PIN["allowed_axioms"])]
    ranked.sort(key=lambda x:(x["closure_declarations"],x["name"]))
    result={"schema":"OPICA_CROSS_REPO_R1_RESEARCH_JOIN","status":"EVIDENCE_AVAILABLE_NOT_CLOSURE" if all(statuses.values()) else "PARTIAL_RESEARCH_EVIDENCE",
            "available":statuses,"shared_normalization_both_pins":norm,"cross_pin_kernel_equality":"NOT_ESTABLISHED",
            "ranked_leads":ranked,"all_leads":leads,
            "cross_world_queries":[{"label":x["label"],"status":x["status"],"plans":len(x.get("plans",[]))} for x in (cross or {}).get("queries",[])],
            "cross_world_frontier":(cross or {}).get("premise_frontier",[]),
            "native_targets":[{"name":x["target"],"type_sha256":x["type_sha256"],"disposition":x["disposition"],"nontrivial_plans":sum(p["kind"]=="UNVERIFIED_COMPOSITION" for p in x["plans"])} for x in (native or {}).get("targets",[])],
            "remaining":[
             {"id":"PRINCIPAL_LEVEL","target":"(Level.cyc PChar.one).Gm = Deduction.G","needs":"literal principal-level singleton and exact source identity"},
             {"id":"PRINCIPAL_HOST","target":"VWinAt principal 401 and matching HostExW","needs":"retain growing auxiliary fields; derive restricted window, not specialize away assumptions"},
             {"id":"CONNECTEDNESS","target":"principal TopG instance, complete tied family","needs":"extract actual shape/HypsAlt and row/geometry producer premises"},
             {"id":"POWER_WINDOWS","target":"OneSidedWindows Deduction.G","needs":"construct cofinal complete real windows; exponent slack and constants fixed before horizon"},
             {"id":"NATIVE_POSITIVE_ENERGY","target":"cofinal literalGEnergy subpower","needs":"formalize conditional paper power-window integral bridge; no inverse implication"},
             {"id":"NATIVE_C1","target":"original quartic-detector C1","needs":"prove actual source-to-detector transfer without RH or zero-free endpoint"},
             {"id":"SIGNED_ROUTE","target":"ACTUAL_UPPER/P303/N20","needs":"source-specific signed cutoff/removals, spent partners, no substitution of scalar estimate"}
            ],"external_approved_proof_constants":[],"proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"}
    write(a.output,result)
    print(json.dumps({"status":result["status"],"available":statuses,"ranked_leads":len(ranked),"proof_acceptance":False}))
if __name__=="__main__":main()
