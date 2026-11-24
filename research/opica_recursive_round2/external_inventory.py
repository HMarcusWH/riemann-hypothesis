"""Only authenticated original-export rows and compiled principal interfaces.
External rows are research-only until same-pin reconstruction and validation."""
from r2_common import *
from search import api

def load_external(harvest):
    report=read(harvest/"harvest.json");receipts=report["artifact_receipts"];rows=[];rejected=[]
    eh=api()[0]
    def get(key,name):
        if key not in receipts:return None
        p=harvest/"inputs"/key/name
        need(filehash(p)==receipts[key]["entries"][name]["sha256"],"Harvested artifact member drift")
        return read(p)
    def add(name,expr,world,axioms,dependencies,**extra):
        try:
            need(not forbidden(name) and not any(forbidden(n) for n in dependencies),"Endpoint dependency")
            need(set(axioms)<=ALLOWED,"Unapproved axiom")
            rows.append({"declaration":name,"module":world,"world":world,"type_expression":expr,"type_sha256":eh(expr),"axioms":axioms,"dependencies":dependencies,"proof_constants":[],**extra})
        except Exception as ex:rejected.append({"declaration":name,"world":world,"reason":str(ex)[:800]})
    graph=get("original","original-dependencies.json")
    if graph:
        mining=LOCK["evidence"]["mining"];actual=receipts["original"]
        need(actual["head"]==mining["head"] and actual["run"]==mining["run"] and actual["attempt"]==mining["attempt"] and actual["producer_job"]==mining["job"] and actual["artifact_name"]==mining["artifact_name"],"Original mining producer evidence differs")
        root=HERE.parent.parent
        need(git(root,"rev-parse",mining["head"]+"^{tree}")==mining["tree"],"Original mining tree differs")
        for f in mining["unchanged_controller_components"]:
            path="research/opica_extract_round1/"+f
            need(git(root,"rev-parse",mining["head"]+":"+path)==git(root,"rev-parse",LOCK["controller"]["parent"]+":"+path),"Mining source component changed: "+f)
        from reuse_mining import verify_graph
        verify_graph(graph)
        spec=R1_PIN["original"]["solution"];transport=graph["download"]
        need(graph["schema"]=="OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1" and graph["mode"]=="solution" and graph["proof_acceptance"] is False,"Wrong original graph")
        need(graph["raw_sha256"]==spec["raw_sha256"] and transport["compressed_sha256"]==spec["compressed_sha256"] and transport["observed_raw_sha256"]==spec["raw_sha256"] and transport["zstd_exit"]==0 and not transport["feed_errors"],"Original export byte authentication differs")
        for r in graph["roots"]:
            cl=r.get("closure",{})
            if (r.get("kind")=="thm" and r.get("role","").startswith(("CONDITIONAL_","PRODUCER_","DISCOVERED_")) and cl.get("status")=="COMPLETE" and cl.get("membership") and r.get("type_status")=="ORIGINAL_EXPORT_EXPR_CONVERTED" and not r.get("excluded_dependencies")):
                add(r["name"],r["type_expression"],"ORIGINAL_EXPORT",cl["axioms"],cl.get("endpoint_like_dependencies",[]),closure_count=cl["declarations"],membership=cl["membership"],admission="ORIGINAL_AUTHENTICATED_EXPORT_RESEARCH_ONLY")
            else:rejected.append({"declaration":r["name"],"world":"ORIGINAL_EXPORT","reason":"INELIGIBLE_OR_INCOMPLETE_GRAPH_ROOT"})
    principal=get("principal","principal-receipt.json")
    if principal:
        spec=LOCK["evidence"]["old_principal"]
        need(receipts["principal"]["artifact_id"]==spec["artifact"] and receipts["principal"]["zip_sha256"]==spec["archive_sha256"],"Old principal evidence identity")
        root=HERE.parent.parent
        old=next(x["head"] for x in LOCK["runs"] if x["key"]=="external")
        new=LOCK["controller"]["parent"]
        for f in spec["unchanged_controller_components"]:
            path="research/opica_extract_round1/"+f
            need(git(root,"rev-parse",old+":"+path)==git(root,"rev-parse",new+":"+path),"Principal controller component changed: "+f)
        need(principal["status"]=="PASS_CONDITIONAL_PRINCIPAL_CUT_ONLY" and principal["head"]==R1_PIN["original"]["head"] and principal["proof_acceptance"] is False,"Principal receipt differs")
        need(principal["shared_source_sha256"]==filehash(R1/"Common.lean"),"Principal shared-source bytes differ")
        for r in principal["rows"]:
            add(r["name"],r["type_expression"],"ORIGINAL_COMPILER_ADAPTER",r["axioms"],r["dependency_names"],source_module="OPICAExtractionPrincipal",admission="ORIGINAL_PIN_COMPILER_ONLY")
            if rows and rows[-1]["declaration"]==r["name"]:rows[-1]["proof_constants"]=r["proof_constants"]
    return rows,rejected


def principal_goals(rows):
    from cross_search import peel,subdag
    eh=api()[0]
    by={r["declaration"]:r for r in rows}
    ns="OPICAExtractionR1."
    n=ns+"principal_ramp_windows_of_connected"
    m=ns+"principal_ramp_windows_of_topG_vwin"
    out=[]
    def add(label,expr,row):
        d="OPICAR2Original."+label
        h=eh(expr)
        out.append({"id":digest([d,h]),"label":label,"declaration":d,"module":"OPICAR2PrincipalTargets","expression":expr,"type_sha256":h,"proof_constants":row["proof_constants"],"world":"ORIGINAL_QUERY"})
    if n in by:
        r=by[n];e=r["type_expression"];bs,last=peel(e)
        need(len(bs)==1,"PrincipalConnected interface binder count drift")
        add("PrincipalConnectedNamed",subdag(e,int(e["nodes"][bs[0][1]][3])),r)
        add("RampWindowsNamed",subdag(e,last),r)
    host=ns+"principal_connected_of_topG_host"
    if host in by:
        r=by[host];e=r["type_expression"];bs,_=peel(e)
        need(len(bs)==2,"Principal host interface binder count drift")
        add("PrincipalHostNamed",subdag(e,int(e["nodes"][bs[1][1]][3])),r)
    if m in by:
        r=by[m];e=r["type_expression"];bs,_=peel(e)
        need(len(bs)==2,"TopG/VWinAt interface binder count drift")
        for label,(_,i) in zip(("TopGNamed","PrincipalVWinNamed"),bs):
            add(label,subdag(e,int(e["nodes"][i][3])),r)
    return out

def external_frontier(row,slot):
    # A syntactically closed expression is only a research question; actual
    # Prop checking and definition registration are mandatory at common pin.
    from cross_search import peel,subdag
    eh=api()[0];bs,_=peel(row["type_expression"])
    need(0<=slot<len(bs),"External binder index differs")
    e,i=bs[slot]
    expr=subdag(e,int(e["nodes"][i][3]))
    h=eh(expr)
    # Require no loose bound variables using an explicit binder-depth walk.
    from cross_search import children
    stack=[(int(expr["root"]),0)];seen=set()
    while stack:
        idx,depth=stack.pop()
        if (idx,depth) in seen:continue
        seen.add((idx,depth));n=expr["nodes"][idx]
        need(len(seen)<=100000,"External binder budget")
        if n[0]=="bvar":need(int(n[1])<depth,"DEPENDENT_BINDER_REQUIRES_CONTEXT_OR_INSTANTIATION")
        for k in children(n):
            d=depth+(1 if (n[0] in ("forall","lam") and k==4) or (n[0]=="let" and k==4) else 0)
            stack.append((int(n[k]),d))
    key=digest([row["world"],row["declaration"],row["type_sha256"],slot]);mod="OPICAR2ExternalFrontier"+key[:24]
    return {"id":key,"label":row["declaration"]+" premise "+str(slot),"declaration":mod+".goal","module":mod,"expression":expr,"type_sha256":h,"proof_constants":row["proof_constants"],"world":"ORIGINAL_QUERY","origin":{"owner":row["declaration"],"slot":slot,"name":mod+".goal","source_module":row.get("source_module"),"world":row["world"],"contextual":False,"compiler_prop_check":"PENDING_COMMON_PIN"}}
