"""Actual elaborated dependency index of published Lean export, not a kernel.

NDJSON v3.1.0. Only dependency edges retained (16 bytes/expression), never
execute supplier source. Structural inductive/mutual/quotient edges are a
conservative enlargement, not a claim of minimal proof size.
"""
import argparse, array, hashlib, json, mmap, pathlib, shutil, struct, subprocess, threading, time, urllib.request
from scan import PIN, need, write
REC=struct.Struct("<IIII")
DECLS={"axiom","def","thm","opaque","quot"}
EXPR={"bvar","sort","const","app","lam","forallE","letE","proj","natVal","strVal","mdata"}
class Index:
    def __init__(self,folder,cap):
        self.folder=folder;self.cap=cap;self.parents=array.array("I",[0]);self.parts=[""]
        self.decls={};self.nexpr=0;self.nlevels=1;self.meta=None;self.bytes=0;self.lines=0
        self.file=(folder/"expr.edges").open("xb",buffering=1024*1024)
        self.want={x["name"] for x in PIN["catalog"]}|{"riemannHypothesis","LFunction_ne_zero_of_half_lt_re"}
        self.leaves={x.split(".")[-1] for x in self.want};self.selected={};self.hash=hashlib.sha256()
    def name(self,i):
        parts=[]
        while i:
            a=self.parts[i]
            parts.append(str(a) if isinstance(a,int) or "." not in a else "«"+a+"»")
            i=self.parents[i]
        return ".".join(reversed(parts))
    def n(self,i):
        need(type(i) is int and 0<=i<len(self.parts),"bad name reference");return i
    def e(self,i):
        need(type(i) is int and 0<=i<self.nexpr and i<0xfffffffe,"bad expression reference");return i+1
    def lev(self,i):
        need(type(i) is int and 0<=i<self.nlevels,"bad level reference")
    def decl(self,kind,p,group=()):
        name=self.n(p["name"]);need(name and name not in self.decls,"duplicate declaration")
        t=self.e(p["type"]);v=self.e(p["value"]) if "value" in p else 0
        ns=set(group)|set(p.get("all",[]))|set(p.get("ctors",[]))
        if "induct" in p:ns.add(p["induct"])
        es=[]
        for q in p.get("rules",[]):
            ns.add(q["ctor"]);es.append(self.e(q["rhs"]))
        ns.discard(name)
        self.decls[name]=(kind,t,v,tuple(self.n(i) for i in sorted(ns)),tuple(es))
        if self.parts[name] in self.leaves:
            full=self.name(name)
            if full in self.want:
                need(full not in self.selected,"ambiguous selected name")
                self.selected[full]=(name,p)
    def row(self,j):
        need(isinstance(j,dict),"not JSON object")
        if "meta" in j:
            need(self.meta is None and self.lines==1 and j["meta"]["format"]["version"]=="3.1.0","unexpected export format")
            self.meta=j["meta"];return
        need(self.meta is not None,"missing header")
        if "in" in j:
            need(j["in"]==len(self.parts),"nonconsecutive name index")
            k=set(j)-{"in"};need(k in ({"str"},{"num"}),"unknown name record")
            a=j[next(iter(k))];self.parents.append(self.n(a["pre"]));self.parts.append(a.get("str",a.get("i")));return
        if "il" in j:
            need(j["il"]==self.nlevels,"nonconsecutive level index")
            k=set(j)-{"il"};need(len(k)==1,"unknown level record");k=k.pop();a=j[k]
            if k=="succ":self.lev(a)
            elif k in ("max","imax"):
                need(len(a)==2,"bad level");self.lev(a[0]);self.lev(a[1])
            elif k=="param":self.n(a)
            else:raise RuntimeError("unknown level tag "+k)
            self.nlevels+=1;return
        if "ie" in j:
            need(j["ie"]==self.nexpr,"nonconsecutive expression index")
            k=set(j)-{"ie"};need(len(k)==1 and next(iter(k)) in EXPR,"unknown expression tag")
            k=k.pop();a=j[k];name=0;xs=[]
            if k=="const":
                name=self.n(a["name"])+1
                for u in a["us"]:self.lev(u)
            elif k=="app":xs=[a["fn"],a["arg"]]
            elif k in ("lam","forallE"):self.n(a["name"]);xs=[a["type"],a["body"]]
            elif k=="letE":self.n(a["name"]);xs=[a["type"],a["value"],a["body"]]
            elif k=="proj":name=self.n(a["typeName"])+1;xs=[a["struct"]]
            elif k=="mdata":xs=[a["expr"]]
            elif k=="sort":self.lev(a)
            ee=[self.e(x) for x in xs];ee += [0]*(3-len(ee))
            self.file.write(REC.pack(name,*ee));self.nexpr+=1
            if self.nexpr%1000000==0:
                need(self.nexpr*REC.size<=self.cap and shutil.disk_usage(self.folder).free>2*1024**3,"INDEX_RESOURCE_EXHAUSTED")
            return
        need(len(j)==1,"unknown multi-key declaration")
        k,p=next(iter(j.items()))
        if k in DECLS:self.decl(k,p)
        elif k=="inductive":
            group=[q["name"] for s in ("types","ctors","recs") for q in p[s]]
            for s in ("types","ctors","recs"):
                for q in p[s]:self.decl(s,q,group)
        else:raise RuntimeError("unknown declaration tag "+k)
    def consume(self,raw,expected_bytes,expected_hash):
        try:
            for line in raw:
                self.lines+=1;self.bytes+=len(line)
                need(self.bytes<=expected_bytes,"uncompressed size exceeds pin")
                self.hash.update(line);self.row(json.loads(line))
                if self.lines%10000000==0:print("INDEX_PROGRESS",self.lines,self.bytes,self.nexpr,len(self.decls),flush=True)
            need(self.bytes==expected_bytes and self.hash.hexdigest()==expected_hash,"raw export digest/size mismatch")
            need(self.meta is not None and self.nexpr and self.decls,"empty export")
        finally:self.file.close()
    def direct(self,mp,start,limit=2000000):
        stack=[start] if start else [];seen=set();ns=set();status="COMPLETE"
        while stack:
            x=stack.pop()
            if x in seen:continue
            if len(seen)>=limit:status="BUDGET_EXHAUSTED";break
            seen.add(x)
            a,b,c,d=REC.unpack_from(mp,(x-1)*REC.size)
            if a:ns.add(a-1)
            stack.extend(z for z in (b,c,d) if z)
        return {"status":status,"expression_nodes":len(seen),"constants":sorted(self.name(z) for z in ns)}
    def closure(self,mp,root,limit,seconds):
        seen=bytearray((self.nexpr+7)//8);decls=set();missing=set();axioms=set();stack=[-root-1];count=0;start=time.monotonic();status="COMPLETE"
        while stack:
            x=stack.pop()
            if x<0:
                n=-x-1
                if n in decls or n in missing:continue
                p=self.decls.get(n)
                if p is None:missing.add(n);continue
                decls.add(n);kind,t,v,group,es=p
                if kind=="axiom":axioms.add(n)
                stack.extend(z for z in (t,v,*es) if z)
                stack.extend(-z-1 for z in group)
                if kind=="quot":stack.extend(-z-1 for z in self.quot_names if z!=n)
            else:
                i=x-1;idx=i>>3;bit=1<<(i&7)
                if seen[idx]&bit:continue
                seen[idx]|=bit;count+=1
                a,b,c,d=REC.unpack_from(mp,i*REC.size)
                if a:stack.append(-a)
                stack.extend(z for z in (b,c,d) if z)
                if count>=limit or (count%262144==0 and time.monotonic()-start>seconds):
                    status="BUDGET_EXHAUSTED";break
        selected_inside=sorted(k for k,(i,_) in self.selected.items() if i in decls)
        return {"status":status if not missing else "UNRESOLVED_REFERENCES_OR_"+status,
                "declarations":len(decls),"expression_nodes":count,"missing_count":len(missing),
                "missing_sample":sorted(self.name(z) for z in list(missing)[:30]),"axioms":sorted(self.name(z) for z in axioms),
                "selected_roots_reached":selected_inside,"seconds":round(time.monotonic()-start,3)}
    def report(self,mode,limit,seconds):
        self.quot_names=[n for n,(k,*_) in self.decls.items() if k=="quot"]
        roles={r["name"]:r["role"] for r in PIN["catalog"]}
        # Also refuse the original internal RH endpoint and headline aliases,
        # not only the currently synchronized Main declaration.
        excluded={k for k,v in roles.items() if v.endswith("_EXCLUDED")}|{"LFunction_ne_zero_of_half_lt_re","riemannHypothesis","UpperTheory.FinalTheorems.riemannHypothesis","riemannZeta_eq_zero_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive"}
        with (self.folder/"expr.edges").open("rb") as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mp:
            out=[]
            for name in sorted(self.want):
                if name not in self.selected:
                    out.append({"name":name,"status":"NOT_PRESENT_IN_EXPORT","role":roles.get(name,"ENDPOINT_EXCLUDED")});continue
                idx,p=self.selected[name];kind,t,v,group,es=self.decls[idx]
                row={"name":name,"role":roles.get(name,"ENDPOINT_EXCLUDED"),"kind":kind,
                     "exact_declaration_record":p,"type_dependencies":self.direct(mp,t),
                     "value_dependencies":self.direct(mp,v),"structural_names":[self.name(z) for z in group],
                     "closure":self.closure(mp,idx,limit,seconds)}
                row["status"]="INDEXED"
                row["excluded_dependencies"]=[x for x in row["closure"]["selected_roots_reached"] if x in excluded]
                out.append(row);print("ROOT",name,row["closure"]["status"],row["closure"]["declarations"],flush=True)
        candidates=[x for x in out if x.get("status")=="INDEXED" and x["role"].startswith(("CONDITIONAL_","PRODUCER_")) and x["closure"]["status"]=="COMPLETE" and not x["excluded_dependencies"] and set(x["closure"]["axioms"])<=set(PIN["allowed_axioms"])]
        candidates.sort(key=lambda x:(x["closure"]["declarations"],x["name"]))
        return {"schema":"OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1","mode":mode,"meta":self.meta,
                "raw_sha256":self.hash.hexdigest(),"raw_bytes":self.bytes,"names":len(self.parts),"expressions":self.nexpr,"declarations":len(self.decls),
                "roots":out,"ranked_complete_closure_leads":[{"name":x["name"],"role":x["role"],"declarations":x["closure"]["declarations"]} for x in candidates],
                "scope":"ELABORATED_DEPENDENCY_EDGES_WITH_CONSERVATIVE_STRUCTURAL_GROUPS_NOT_A_KERNEL_CHECK",
                "proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"}
def remote(index,spec):
    # Stream compressed bytes directly to zstd; do not materialize either large archive.
    with (index.folder/"zstd.stderr").open("wb") as err:
        proc=subprocess.Popen(["zstd","-d","-c","--long=30"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,start_new_session=True)
        errors=[];stats={}
        def feed():
            try:
                h=hashlib.sha256();n=0
                with urllib.request.urlopen(spec["url"],timeout=120) as src,proc.stdin as dst:
                    while True:
                        b=src.read(1024*1024)
                        if not b:break
                        n+=len(b);h.update(b)
                        need(n<=spec.get("compressed_bytes",200*1024**2),"compressed size limit")
                        dst.write(b)
                stats.update(compressed_bytes=n,compressed_sha256=h.hexdigest())
                if "compressed_sha256" in spec:
                    need(n==spec["compressed_bytes"] and h.hexdigest()==spec["compressed_sha256"],"compressed artifact mismatch")
            except BaseException as ex:
                errors.append(str(ex))
                try:proc.stdin.close()
                except Exception:pass
        t=threading.Thread(target=feed,daemon=True);t.start()
        try:
            index.consume(proc.stdout,spec["raw_bytes"],spec["raw_sha256"])
            t.join(timeout=180);need(not t.is_alive() and not errors,"download/decompression failed: "+str(errors))
            need(proc.wait(timeout=120)==0,"zstd failure")
            return stats
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
def main():
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=("challenge","solution"),required=True);p.add_argument("--output",type=pathlib.Path,required=True);p.add_argument("--scratch",type=pathlib.Path,required=True);p.add_argument("--closure-budget",type=int,default=100000000);p.add_argument("--root-seconds",type=int,default=300)
    a=p.parse_args();need(a.closure_budget>0 and a.root_seconds>0,"invalid budget");a.scratch.mkdir(parents=True,exist_ok=False)
    try:
        ix=Index(a.scratch,10*1024**3)
        ix.want.update(["UpperTheory.FinalTheorems.riemannHypothesis","riemannZeta_eq_zero_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive"])
        ix.leaves={x.split(".")[-1] for x in ix.want}
        st=remote(ix,PIN["original"][a.mode]);report=ix.report(a.mode,a.closure_budget,a.root_seconds);report["download"]=st
        if a.mode=="solution":
            essential=("riemannHypothesis","LFunction_ne_zero_of_half_lt_re","Deduction.G","UpperTheory.Top.TopG","UpperTheory.Top.VWinAt")
            report["missing_essential_roots"]=[n for n in essential if not any(x["name"]==n and x["status"]=="INDEXED" for x in report["roots"])]
            report["root_coverage"]="PARTIAL_ROOT_COVERAGE" if report["missing_essential_roots"] else "ESSENTIAL_ROOTS_INDEXED"
        else:
            need(any(x["name"]=="riemannHypothesis" and x["status"]=="INDEXED" for x in report["roots"]),"challenge root missing")
            report["scope"]="AUTHENTICATED_CHALLENGE_PARSER_SMOKE_NOT_SUPPLIER"
        write(a.output,report)
        print(json.dumps({"status":"AUTHENTICATED_EXPORT_INDEX_COMPLETE","mode":a.mode,"declarations":report["declarations"],"expressions":report["expressions"],"ranked":len(report["ranked_complete_closure_leads"]),"proof_acceptance":False}))
    except BaseException as ex:
        if not a.output.exists():write(a.output,{"schema":"OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1","status":"INCOMPLETE_OR_REJECTED","mode":a.mode,"reason":str(ex)[:2000],"proof_acceptance":False,"C1":"OPEN"})
        print("INDEX_FAILURE",repr(ex),flush=True);raise
    finally:
        shutil.rmtree(a.scratch)
if __name__=="__main__":main()
