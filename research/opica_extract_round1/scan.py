"""Exact source cut inventory. Lexical references are NOT proof dependencies."""
import argparse, hashlib, json, pathlib, re, subprocess
HERE=pathlib.Path(__file__).resolve().parent
PIN=json.loads((HERE/"CONTRACT.json").read_text())
def need(x,msg):
    if not x: raise RuntimeError(msg)
def git(repo,*a):
    return subprocess.check_output(["git","-C",str(repo),*a])
def textgit(repo,*a): return git(repo,*a).decode().strip()
def write(path,x):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f: json.dump(x,f,ensure_ascii=False,indent=2);f.write("\n")
def extract(repo,ref,path,selector):
    try:
        blob=textgit(repo,"rev-parse",ref+":"+path)
        raw=git(repo,"show",ref+":"+path)
    except subprocess.CalledProcessError:
        return {"path":path,"status":"MISSING_PATH"}
    actual=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    need(actual==blob,"source object mismatch")
    lines=raw.decode().splitlines()
    pattern=r"^\s*(?:private\s+)?(?:theorem|lemma|def|abbrev)\s+"+re.escape(selector)+r"(?=\s|:|\(|\{)"
    hits=[i for i,l in enumerate(lines) if re.match(pattern,l)]
    if len(hits)!=1:return {"path":path,"blob":blob,"status":"UNRESOLVED_DECLARATION","matches":[i+1 for i in hits]}
    i=hits[0];end=i+1
    while end<len(lines) and not re.match(r"^(?:\s*(?:private\s+)?(?:theorem|lemma|def|abbrev|structure|instance|namespace|end)\s|-- =====)",lines[end]):
        end+=1
    body="\n".join(lines[i:end]).strip()
    return {"path":path,"blob":blob,"status":"EXTRACTED","line":i+1,"last_line":end,
            "source":body,"source_sha256":hashlib.sha256(body.encode()).hexdigest()}
def campaign(repo,out):
    s=PIN["supplier"];o=PIN["original"]
    need(textgit(repo,"rev-parse",s["head"]+"^{tree}")==s["tree"],"supplier tree drift")
    need(textgit(repo,"rev-parse","HEAD:src")==s["src_tree"],"current source changed")
    need(textgit(repo,"rev-parse",o["head"])==o["head"],"original absent")
    nodes=[]
    for row in PIN["catalog"]:
        a=extract(repo,o["head"],row["original"],row["selector"])
        b=extract(repo,s["head"],row["current"],row["selector"])
        nodes.append({"name":row["name"],"role":row["role"],"purpose":row["reason"],"original":a,"current":b,
                      "same_source_text":a.get("source_sha256") is not None and a.get("source_sha256")==b.get("source_sha256")})
    edges=[]
    for a in nodes:
        for b in nodes:
            if a is b:continue
            for epoch in ("original","current"):
                if re.search(r"(?<![\w.])"+re.escape(b["name"])+r"(?![\w.])",a[epoch].get("source","")):
                    edges.append({"from":a["name"],"to":b["name"],"epoch":epoch,"kind":"LEXICAL_MENTION_ONLY"})
    for name in ("Deduction.G","UpperTheory.Top.TopG","UpperTheory.Top.VWinAt","UpperTheory.Comparison₂.core_gm"):
        need(next(x for x in nodes if x["name"]==name)["current"]["status"]=="EXTRACTED","essential current cut not found: "+name)
    write(out,{"schema":"OPICA_R1_SOURCE_CUTS","nodes":nodes,"lexical_edges":edges,"supplier":s,"original":o["head"],
              "proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"})
    print(json.dumps({"status":"PINNED_SOURCE_CUTS_EXTRACTED","nodes":len(nodes),"original_resolved":sum(x["original"]["status"]=="EXTRACTED" for x in nodes),"current_resolved":sum(x["current"]["status"]=="EXTRACTED" for x in nodes),"lexical_edges":len(edges),"proof_acceptance":False}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();campaign(a.repo,a.output)
