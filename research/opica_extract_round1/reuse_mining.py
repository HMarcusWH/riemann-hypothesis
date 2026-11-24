"""Review-only reuse of the exact successful compact-index producer."""
import argparse, hashlib, json, pathlib
from scan import PIN, need, textgit, write
HEAD="ea038dc8f3e86121ddea43213bf3bbeb015b23f3"
TREE="07c57bad8c54cf84d795fe3192fc15d8f82f1b87"
RUN=45472802058
JOB=138745091804
REPO="HMarcusWH/riemann-hypothesis"
WORKFLOW=".github/workflows/opica-extraction-r1.yml"
COMPONENTS=("CONTRACT.json","scan.py","export_graph.py","index_checkpoint.py")

def identity(repo,run,job):
    need(run["id"]==RUN and run["head_sha"]==HEAD and run["run_attempt"]==1 and run["event"]=="pull_request","Wrong mining run/head/attempt")
    need(run["repository"]["full_name"]==REPO and run["head_repository"]["full_name"]==REPO and run["path"].split("@")[0]==WORKFLOW,"Wrong mining workflow/repository")
    need(any(x["number"]==13 and x["head"]["sha"]==HEAD for x in run["pull_requests"]),"Wrong mining PR")
    need(job["id"]==JOB and job["run_id"]==RUN and job["name"]=="verified-export-mining" and job["status"]=="completed" and job["conclusion"]=="success","Exact mining producer did not pass")
    need(textgit(repo,"rev-parse",HEAD+"^{tree}")==TREE,"Wrong mining source tree")
    components={}
    for f in COMPONENTS:
        p="research/opica_extract_round1/"+f
        oid=textgit(repo,"rev-parse",HEAD+":"+p)
        need(textgit(repo,"rev-parse","HEAD:"+p)==oid and textgit(repo,"hash-object",p)==oid,"Mining source changed: "+p)
        components[p]=oid
    return components

def verify_graph(g):
    s=PIN["original"]["solution"]
    need(g.get("schema")=="OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1" and g.get("mode")=="solution" and g.get("proof_acceptance") is False and g.get("C1")=="OPEN" and g.get("independent_step4")=="OPEN","Wrong graph scope")
    need(g["raw_sha256"]==s["raw_sha256"] and abs(g["raw_bytes"]-s["raw_bytes"])<=s.get("raw_size_slack",0),"Wrong raw export")
    d=g["download"]
    need(d["url"]==s["url"] and d["compressed_sha256"]==s["compressed_sha256"] and abs(d["compressed_bytes"]-s["compressed_bytes"])<=s.get("compressed_size_slack",0),"Wrong compressed export")
    need(d["observed_raw_sha256"]==g["raw_sha256"] and d["observed_raw_bytes"]==g["raw_bytes"] and d["zstd_exit"]==0 and d["feed_errors"]==[] and d["feed_thread_alive"] is False and d["http_status"]==200 and "index_failure" not in d,"Incomplete transport")
    need(d["resources"]["format"]=="OPICA_EXPR_COMPACT_V2" and g["roots"] and g["expressions"]>0 and g["declarations"]>0,"Incomplete graph")
    names=[r["name"] for r in g["roots"]]
    need(len(names)==len(set(names)),"Duplicate roots")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("repo","run","job"):p.add_argument("--"+k,type=pathlib.Path,required=True)
    p.add_argument("--graph",type=pathlib.Path);p.add_argument("--receipt",type=pathlib.Path)
    p.add_argument("--identity-only",action="store_true")
    a=p.parse_args()
    components=identity(a.repo,json.loads(a.run.read_bytes()),json.loads(a.job.read_bytes()))
    if a.identity_only:
        print("EXACT_PREDECESSOR_MINING_JOB_AND_SOURCE_PASS")
    else:
        need(a.graph is not None and a.receipt is not None and a.graph.is_file() and not a.graph.is_symlink() and 0<a.graph.stat().st_size<=768<<20,"Invalid graph input")
        raw=a.graph.read_bytes();g=json.loads(raw);verify_graph(g)
        result={"schema":"OPICA_R1_UNCHANGED_MINING_REUSE_V1","status":"AUTHENTICATED_PREDECESSOR_MINING_REUSE","producer":{"repository":REPO,"head":HEAD,"tree":TREE,"run":RUN,"attempt":1,"job":JOB,"artifact_name":"extraction-original-proof-graph-f413bc3030c20617988aca46556cabda6373a4a0"},"review_controller":{"head":textgit(a.repo,"rev-parse","HEAD"),"tree":textgit(a.repo,"rev-parse","HEAD^{tree}")},"unchanged_component_oids":components,"graph_sha256":hashlib.sha256(raw).hexdigest(),"root_coverage":g.get("root_coverage"),"root_count":len(g["roots"]),"proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"}
        write(a.receipt,result);print(json.dumps(result),flush=True)
