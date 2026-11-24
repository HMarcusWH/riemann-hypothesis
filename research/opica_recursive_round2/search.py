"""Bounded typed backward search and a non-authoritative AND/OR obligation graph."""
from collections import deque
from types import SimpleNamespace
import sys
from r2_common import *
sys.path.insert(0,str(R1))
from cross_search import head,peel,subdag,name

def api():
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.composition_search import retrieve
    from research.RHRC.integration.opica_composition.contracts import SearchBudget,GrammarProfile
    from research.RHRC.integration.opica_composition.proposals import used_constant_ids,validate_plan
    return expression_hash,retrieve,SearchBudget,GrammarProfile,used_constant_ids,validate_plan

def row_id(row):
    return digest([row["world"],row["declaration"],row["type_sha256"]])
def target_head(expression):
    return head(expression,peel(expression)[1])
def rank_menu(rows,goal,cap):
    h=target_head(goal["expression"]);const={name(n[1]) for n in goal["expression"]["nodes"] if n[0]=="const" and n[1][0]!="num"}
    def key(row):
        # Exact terminal-head matches first, then shared compiler constants.
        # Counts are computational priorities, not logical implications.
        return (target_head(row["type_expression"])!=h,
                -len(const&set(row.get("type_constants",[]))),
                len(row.get("dependencies",[])) or row.get("closure_count",10**9),
                row["declaration"],row["world"])
    filtered=[r for r in rows if r["declaration"]!=goal["declaration"] and not forbidden(r["declaration"])]
    # The real proposer identifies a constant by declaration name, so never
    # put two semantic worlds under the same name in a single query.
    ordered=[];seen=set()
    for r in sorted(filtered,key=key):
        if r["declaration"] not in seen:ordered.append(r);seen.add(r["declaration"])
    return ordered[:cap],max(0,len(ordered)-cap)
def query(goal,rows,mode):
    eh,retrieve,SearchBudget,GrammarProfile,used,validate=api()
    need(eh(goal["expression"])==goal["type_sha256"],"Goal type digest differs")
    rows=[r for r in rows if mode=="mixed" or r["world"]=="NATIVE_COMPILER"]
    menu,omitted=rank_menu(rows,goal,BUDGET["menu_roots"])
    ids={row_id(r):r["declaration"] for r in menu}
    forbidden_names=sorted({r["declaration"] for r in rows if forbidden(r["declaration"])}|{goal["declaration"]})
    spec=SimpleNamespace(allowed_constants=ids,expected_type_hash=goal["type_sha256"],declaration=goal["declaration"],forbidden_constants=forbidden_names)
    budget=SearchBudget(candidates=BUDGET["candidates_per_goal"],term_nodes=BUDGET["search_states"],term_depth=BUDGET["term_depth"],wall_seconds=BUDGET["search_seconds"],heartbeats=800000)
    found,complete,provenance=retrieve(SimpleNamespace(statements=menu),spec,GrammarProfile(forbidden_names,[]),budget,goal["expression"],proof_constants=goal.get("proof_constants",[]))
    table={row_id(r):r for r in menu};plans=[]
    for f in found:
        plan=f["term_plan"];validate(plan,budget);const=sorted(used(plan))
        need(set(const)<=set(table),"Search plan uses undeclared constant")
        sources=[{**{k:v for k,v in table[c].items() if k not in ("dependencies","membership","type_text","value_constants","conclusion_text","outer_telescope")},"id":c} for c in const]
        # Proof plans (including direct exact theorem matches) are actual
        # proposer results, never the old bare-seed inventory entries.
        worlds=sorted({r["world"] for r in sources})
        ident=digest([goal["declaration"],goal["type_sha256"],plan,const])
        plans.append({"id":ident,"label":goal["label"],"target":{"declaration":goal["declaration"],"module":goal["module"],"kind":"value","origin":goal.get("origin"),"world":goal.get("world","NATIVE_QUERY")},"expected_expression":goal["expression"],"expected_type_sha256":goal["type_sha256"],"plan":plan,"sources":sources,"worlds":worlds,"proof_acceptance":False})
    return {"goal":goal["id"],"mode":mode,"selected_menu":sorted(ids.values()),"omitted_menu_roots":omitted,"provenance":provenance,"bounded_complete":complete and not omitted,"plans":plans,"status":"CANDIDATES_NOT_PROOFS" if plans else "NO_MATCH_IN_ENUMERATED_SCOPE" if complete and not omitted else "INCOMPLETE_SEARCH_SCOPE"}
def premise_owners(goal,rows):
    h=target_head(goal["expression"])
    if h is None:return []
    result=[]
    for r in rows:
        if target_head(r["type_expression"])!=h or r["declaration"]==goal["declaration"]:continue
        if r["world"]=="NATIVE_COMPILER":
            slots=[b["position"] for b in r.get("outer_telescope",[]) if b["domain_is_prop"] and not b["typeclass_binder"]]
        else:
            slots=[i for i,(e,j) in enumerate(peel(r["type_expression"])[0]) if e["nodes"][j][2]=="default"]
        if slots:result.append((r,slots))
    return sorted(result,key=lambda a:(len(a[1]),len(a[0].get("dependencies",[])),a[0]["declaration"]))[:BUDGET["frontier_alternatives"]]
def explore(roots,rows,register):
    """Every generated native goal is compiled before entering the queue.
    Head contacts are hypotheses about relevance, not implication edges.
    The original search engine recursively instantiates dependent binders.
    Contextual frontier goals retain their entire earlier telescope.
    """
    q=deque((g,0) for g in roots);nodes={};queries=[];edges=[];failures=[];truncation=[]
    while q and len(nodes)<BUDGET["goals"]:
        goal,depth=q.popleft();key=goal["id"]
        if key in nodes:continue
        nodes[key]={**goal,"depth":depth,"authority":"OPEN_RESEARCH_GOAL"}
        for mode in ("native","mixed"):
            if mode=="native" and goal.get("world")=="ORIGINAL_QUERY":continue
            if mode=="mixed" and not any(r["world"]!="NATIVE_COMPILER" for r in rows):continue
            try:queries.append(query(goal,rows,mode))
            except Exception as ex:failures.append({"goal":key,"mode":mode,"reason":str(ex)[:1200]})
        if depth>=BUDGET["frontier_depth"]:
            truncation.append({"goal":key,"reason":"FRONTIER_DEPTH_CAP"});continue
        for row,slots in premise_owners(goal,rows):
            children=[];missing=[]
            for slot in slots:
                if len(q)+len(nodes)>=2*BUDGET["goals"]:
                    missing.append({"slot":slot,"reason":"FRONTIER_QUEUE_CAP"});continue
                try:
                    child=register(row,slot)
                    children.append(child["id"])
                    if child["id"] not in nodes:q.append((child,depth+1))
                except Exception as ex:
                    missing.append({"slot":slot,"reason":str(ex)[:800]})
            edges.append({"parent":key,"supplier":row["declaration"],"all_prop_premises":children,"unregistered_premises":missing,"kind":"AND_HEAD_CONTACT_REQUIRES_UNIFIER_AND_KERNEL","proof_authority":False})
    if q:truncation.append({"reason":"GOAL_CAP","unvisited":[g["id"] for g,_ in q]})
    return {"schema":"OPICA_R2_TYPED_OBLIGATION_GRAPH_V1","roots":[g["id"] for g in roots],"nodes":list(nodes.values()),"edges":edges,"queries":queries,"failures":failures,"truncation":truncation,"proof_acceptance":False}
def select(graph,mode,limit):
    # Fairly interleave goals, then alternatives. No seed-only proposal.
    groups={}
    for q in graph["queries"]:
        for plan in q["plans"]:
            ext=any(w!="NATIVE_COMPILER" for w in plan["worlds"]) or plan["target"].get("world")=="ORIGINAL_QUERY"
            if (mode=="mixed")!=ext:continue
            groups.setdefault(q["goal"],{})[plan["id"]]=plan
    queue=[list(x.values()) for x in groups.values()];selected=[]
    while queue and len(selected)<limit:
        rest=[]
        for group in queue:
            if len(selected)<limit:selected.append(group.pop(0))
            if group:rest.append(group)
        queue=rest
    return selected,sum(len(x) for x in queue)
