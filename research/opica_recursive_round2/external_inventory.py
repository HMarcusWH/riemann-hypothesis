"""Only authenticated original-export rows and compiled principal interfaces.
External rows are research-only until same-pin reconstruction and validation."""
from r2_common import *
from search import api

def complete_original_leads(graph,spec):
    """Rehash every compressed membership and check the exact ranked population.
    Numeric export declaration IDs are comparable ONLY within this raw export.
    Endpoint-like dependency names are not the full dependency inventory.
    """
    from cross_search import membership
    need((len(graph["roots"]),graph["declarations"],graph["expressions"])==
         (spec["expected_roots"],spec["expected_declarations"],spec["expected_expressions"]),"Completed graph census differs")
    eligible={}
    for r in graph["roots"]:
        c=r.get("closure",{})
        if r.get("kind")=="thm" and r.get("role","").startswith(("CONDITIONAL_","PRODUCER_","DISCOVERED_")) and c.get("status")=="COMPLETE" and c.get("membership") and r.get("type_status")=="ORIGINAL_EXPORT_EXPR_CONVERTED" and not r.get("excluded_dependencies"):
            need(not c["endpoint_like_dependencies"] and c["missing_count"]==0 and set(c["axioms"])<=ALLOWED,"Unqualified original lead")
            s=membership(c["membership"])
            need(len(s)==c["declarations"] and r["name"] not in eligible,"Original membership population differs")
            eligible[r["name"]]=s
    ranked=graph["ranked_complete_closure_leads"]
    need(set(eligible)==set(spec["complete_leads"])=={r["name"] for r in ranked} and len(ranked)==len(eligible),"Ranked lead identity differs")
    need(all(len(eligible[r["name"]])==r["declarations"] for r in ranked),"Ranked closure size differs")
    a=eligible["UpperTheory.V.vwinAt_of_joint"];b=eligible["UpperTheory.V.vwin_of_joint"]
    need(a<=b and len(b-a)==3,"Joint closure containment drift")
    return {"count":len(eligible),"sum":sum(map(len,eligible.values())),"union":len(set.union(*eligible.values())),
            "joint_window_subset_difference":len(b-a),"proof_acceptance":False}

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
        need(actual["artifact_id"]==mining["artifact"] and actual["zip_sha256"]==mining["archive_sha256"] and actual["entries"]["original-dependencies.json"]["sha256"]==mining["member_sha256"],"Exact completed export artifact differs")
        coverage=complete_original_leads(graph,mining)
        need(coverage["union"]==mining["complete_lead_union"] and coverage["sum"]==mining["complete_lead_sum"],"Original closure overlap census differs")
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
    from principal_suppliers import read_suppliers
    for module,r in read_suppliers(harvest/"principal-suppliers"):
        add(r["name"],r["type_expression"],"ORIGINAL_SUPPLIER_ADAPTER",r["axioms"],r["dependency_names"],source_module=module,admission="ORIGINAL_PIN_COMPILER_AND_FRESH_STOCK_ONLY")
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
    v=ns+"principal_vwin_of_all"
    if v in by:
        r=by[v];e=r["type_expression"];bs,_=peel(e)
        need(len(bs)==1,"VWin interface binder count drift")
        add("VWinNamed",subdag(e,int(e["nodes"][bs[0][1]][3])),r)
    joint=by.get("UpperTheory.V.vwin_of_joint")
    if joint:
        for slot in (0,1):out.append(external_frontier(joint,slot))
    return out

def scoped_expression(e,initial_depth=0):
    """Validate lexical scope, retaining de Bruijn levels under all binders."""
    from cross_search import children
    stack=[(int(e["root"]),initial_depth)];seen=set()
    while stack:
        i,d=stack.pop()
        if (i,d) in seen:continue
        need(0<=i<len(e["nodes"]) and d>=0,"Malformed premise DAG")
        seen.add((i,d));need(len(seen)<=100000,"External binder budget")
        n=e["nodes"][i]
        if n[0]=="bvar" and int(n[1])>=d:return False
        for k in children(n):
            dep=d+int((n[0] in ("forall","lam") and k==4) or (n[0]=="let" and k==4))
            child=int(n[k]);need(child<i,"Cyclic or unordered expression DAG")
            stack.append((child,dep))
    return True

def external_premise_expression(e,slot):
    """Mirror the native registerPremise telescope rule, without claiming
    Prop inference. The common-pin compiler must reconstruct/check it.
    """
    from cross_search import peel,subdag,Builder
    bs,_=peel(e)
    need(type(slot) is int and 0<=slot<len(bs),"External binder index differs")
    _,i=bs[slot]
    body=int(e["nodes"][i][3]);domain=subdag(e,body)
    if scoped_expression(domain):return domain,False
    b=Builder()
    domains=[]
    for _,j in bs[:slot]:
        r=e["nodes"][j]
        domains.append((r,b.clone(e,int(r[3]))))
    node=b.clone(e,body)
    for r,d in reversed(domains):
        node=b.add(["forall",r[1],r[2],str(d),str(node)])
    expr=b.finish(node)
    need(scoped_expression(expr),"Malformed contextual premise")
    return expr,True

def external_frontier(row,slot):
    # This remains a syntactic research question: actual Prop inference,
    # context reconstruction and equality are required at the common pin.
    eh=api()[0]
    expr,contextual=external_premise_expression(row["type_expression"],slot)
    h=eh(expr)
    key=digest([row["world"],row["declaration"],row["type_sha256"],slot]);mod="OPICAR2ExternalFrontier"+key[:24]
    return {"id":key,"label":row["declaration"]+" premise "+str(slot),"declaration":mod+".goal","module":mod,"expression":expr,"type_sha256":h,"proof_constants":row["proof_constants"],"world":"ORIGINAL_QUERY","origin":{"owner":row["declaration"],"slot":slot,"name":mod+".goal","source_module":row.get("source_module"),"world":row["world"],"contextual":contextual,"compiler_prop_check":"PENDING_COMMON_PIN"}}
