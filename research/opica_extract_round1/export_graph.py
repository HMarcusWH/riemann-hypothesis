"""Actual elaborated dependency index of published Lean export, not a kernel.

NDJSON v3.1.0. Only dependency edges retained (16 bytes/expression), never
execute supplier source. Structural inductive/mutual/quotient edges are a
conservative enlargement, not a claim of minimal proof size.
"""
import argparse, array, base64, hashlib, json, mmap, pathlib, shutil, struct, subprocess, threading, time, urllib.request, zlib, os, sys
from scan import PIN, need, write
REC=struct.Struct("<IIII")
DECLS={"axiom","def","thm","opaque","quot"}
EXPR={"bvar","sort","const","app","lam","forallE","letE","proj","natVal","strVal","mdata"}
TAGS={n:i for i,n in enumerate(("bvar","sort","const","app","lam","forallE","letE","letNondep","proj","natVal","strVal","mdata"))}
KINDS={i:n for n,i in TAGS.items()}
MASK=(1<<28)-1
BINDERS=("default","implicit","strictImplicit","instImplicit")
DISCOVERY_HEADS={"UpperTheory.Top.TopG","UpperTheory.Top.VWin","UpperTheory.Top.VWinAt","Formalism.HC.ChebyshevInequalityAtWindowScale","Formalism.HC.ChebyshevInequalityOnWindows"}
EXCLUDED_SUFFIXES={"riemannHypothesis","rhOfAll","allChi","claimAll","critAll","riemannZeta_eq_zero_re","LFunction_ne_zero_of_half_lt_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive","zeroFreeAll_of_topG","zero_free_all_of_green_v_win","everyCharacter","everyCharacter_of_row","every_character_of_literature_of_vWin","zeroFree_of_rpow_window","formB","level_of_tiedWin","zeroFreeOn_of_tiedWin_cyc"}
class Index:
    def __init__(self,folder,cap):
        self.folder=folder;self.cap=cap;self.parents=array.array("I",[0]);self.parts=[""]
        self.decls={};self.nexpr=0;self.nlevels=1;self.meta=None;self.bytes=0;self.lines=0
        self.file=(folder/"expr.edges").open("xb",buffering=1024*1024)
        self.want={x["name"] for x in PIN["catalog"]}|{"riemannHypothesis","LFunction_ne_zero_of_half_lt_re"}
        self.levels=[["zero"]];self.us=[()];self.us_ids={():0};self.literals=[];self.lit_ids={}
        self.leaves={x.split(".")[-1] for x in self.want};self.selected={};self.hash=hashlib.sha256();self.verified_digest=None;self.root_cache={}
    def name(self,i):
        parts=[]
        while i:
            a=self.parts[i]
            parts.append(str(a) if isinstance(a,int) or "." not in a else "«"+a+"»")
            i=self.parents[i]
        return ".".join(reversed(parts))
    def n(self,i):
        need(type(i) is int and 0<=i<len(self.parts) and i<=MASK,"bad name reference");return i
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
            if k=="succ":self.lev(a);level=["succ",self.levels[a]]
            elif k in ("max","imax"):
                need(len(a)==2,"bad level");self.lev(a[0]);self.lev(a[1]);level=[k,self.levels[a[0]],self.levels[a[1]]]
            elif k=="param":self.n(a);level=["param",self.name_json(a)]
            else:raise RuntimeError("unknown level tag "+k)
            self.levels.append(level);self.nlevels+=1;return
        if "ie" in j:
            need(j["ie"]==self.nexpr,"nonconsecutive expression index")
            k=set(j)-{"ie"};need(len(k)==1 and next(iter(k)) in EXPR,"unknown expression tag")
            k=k.pop();a=j[k];p=0;b=c=d=0
            if k=="const":
                p=self.n(a["name"]);u=tuple(a["us"])
                for z in u:self.lev(z)
                if u not in self.us_ids:self.us_ids[u]=len(self.us);self.us.append(u)
                b=self.us_ids[u]
            elif k=="app":b,c=self.e(a["fn"]),self.e(a["arg"])
            elif k in ("lam","forallE"):p=self.n(a["name"]);b,c=self.e(a["type"]),self.e(a["body"]);d=BINDERS.index(a["binderInfo"])
            elif k=="letE":
                p=self.n(a["name"]);b,c,d=self.e(a["type"]),self.e(a["value"]),self.e(a["body"])
                k="letNondep" if a["nondep"] else "letE"
            elif k=="proj":p=self.n(a["typeName"]);b=self.e(a["struct"]);c=a["idx"]
            elif k=="mdata":b=self.e(a["expr"]) # export metadata is not native metadata; reject conversion
            elif k=="sort":self.lev(a);p=a
            elif k=="bvar":p=a
            elif k in ("natVal","strVal"):
                key=(k,a)
                if key not in self.lit_ids:self.lit_ids[key]=len(self.literals);self.literals.append(key)
                p=self.lit_ids[key]
            need(type(p) is int and 0<=p<=MASK,"compact index payload overflow")
            self.file.write(REC.pack((TAGS[k]<<28)|p,b,c,d));self.nexpr+=1
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
    def consume(self,raw,expected_bytes,expected_hash,slack=0):
        try:
            for line in raw:
                self.lines+=1;self.bytes+=len(line)
                need(self.bytes<=expected_bytes+slack,"uncompressed size exceeds reviewed cap")
                self.hash.update(line);self.row(json.loads(line))
                if self.lines%10000000==0:print("INDEX_PROGRESS",self.lines,self.bytes,self.nexpr,len(self.decls),flush=True)
            # Validate only after transport/decompressor exit has also been authenticated.
            self.actual_raw={"bytes":self.bytes,"sha256":self.hash.hexdigest()}
            need(abs(self.bytes-expected_bytes)<=slack and self.hash.hexdigest()==expected_hash,
                 "raw export mismatch expected="+str((expected_bytes,expected_hash))+" observed="+str((self.bytes,self.hash.hexdigest())))
            need(self.meta is not None and self.nexpr and self.decls,"empty export")
        finally:self.file.close()
    def name_json(self,i):
        stack=[]
        while i:
            a=self.parts[i];stack.append(("num",str(a)) if isinstance(a,int) else ("str",a));i=self.parents[i]
        result=["anonymous"]
        for tag,p in reversed(stack):result=[tag,result,p]
        return result
    def record(self,mp,x):
        a,b,c,d=REC.unpack_from(mp,(x-1)*REC.size)
        return KINDS[a>>28],a&MASK,b,c,d
    def edges(self,mp,x):
        k,p,b,c,d=self.record(mp,x)
        ns=[p] if k in ("const","proj") else []
        es=([b,c,d] if k in ("letE","letNondep") else [b,c] if k in ("app","lam","forallE") else [b] if k in ("proj","mdata") else [])
        return ns,[v for v in es if v]
    def type_dag(self,mp,start,limit=100000):
        # Reconstruct the actual original expression including universes,
        # binders, literals and projections. Do not invent compiler metadata.
        nodes=[];cache={};intern={};todo=[(start,False)];visits=0
        while todo:
            x,ready=todo.pop()
            if x in cache:continue
            k,p,b,c,d=self.record(mp,x);_,children=self.edges(mp,x)
            if not ready:
                visits+=1
                need(visits<=limit,"type DAG budget exhausted")
                todo.append((x,True));todo.extend((y,False) for y in reversed(children) if y not in cache);continue
            rr=lambda y:str(cache[y])
            if k=="bvar":row=["bvar",str(p)]
            elif k=="sort":row=["sort",self.levels[p]]
            elif k=="const":row=["const",self.name_json(p),[self.levels[u] for u in self.us[b]]]
            elif k=="app":row=["app",rr(b),rr(c)]
            elif k in ("lam","forallE"):row=["lam" if k=="lam" else "forall",self.name_json(p),BINDERS[d],rr(b),rr(c)]
            elif k in ("letE","letNondep"):row=["let",self.name_json(p),rr(b),rr(c),rr(d),k=="letNondep"]
            elif k=="proj":row=["proj",self.name_json(p),str(c),rr(b)]
            elif k in ("natVal","strVal"):row=["nat" if k=="natVal" else "string",str(self.literals[p][1])]
            else:raise RuntimeError("export metadata unsupported in portable exact DAG")
            key=json.dumps(row,ensure_ascii=False,separators=(",",":"))
            if key not in intern:intern[key]=len(nodes);nodes.append(row)
            cache[x]=intern[key]
        need(cache[start]==len(nodes)-1,"noncanonical root")
        return {"format":"LEAN_EXPR_DAG_V1","root":str(cache[start]),"nodes":nodes}
    def conclusion_head(self,mp,t):
        for _ in range(512):
            k,p,b,c,d=self.record(mp,t)
            if k=="forallE":t=c
            elif k=="app" or k=="mdata":t=b
            elif k=="const":return self.name(p)
            else:return None
        return None
    def discover(self,mp,limit=64):
        candidates=[]
        for n,(kind,t,v,group,es) in self.decls.items():
            if kind!="thm":continue
            head=self.conclusion_head(mp,t)
            if head not in DISCOVERY_HEADS:continue
            name=self.name(n)
            if name in self.want or name.startswith("_private.") or name.split(".")[-1] in EXCLUDED_SUFFIXES:continue
            candidates.append((name,n,head))
        candidates.sort(key=lambda q:(q[2],q[0]))
        # Bound each head separately so one populous family cannot consume the whole menu.
        counts={};chosen=[]
        for name,n,head in candidates:
            if counts.get(head,0)>=max(1,limit//len(DISCOVERY_HEADS)):continue
            counts[head]=counts.get(head,0)+1
            self.want.add(name)
            kind,t,v,group,es=self.decls[n]
            self.selected[name]=(n,{"name":n,"type":t-1,"value":v-1,"discovery_conclusion_head":head})
            chosen.append(name)
        return {"eligible_count":len(candidates),"selected_count":len(chosen),"selected":chosen,"complete":len(chosen)==len(candidates),"budget":limit}
    def direct(self,mp,start,limit=2000000):
        stack=[start] if start else [];seen=set();ns=set();status="COMPLETE"
        while stack:
            x=stack.pop()
            if x in seen:continue
            if len(seen)>=limit:status="BUDGET_EXHAUSTED";break
            seen.add(x)
            constants,children=self.edges(mp,x)
            ns.update(constants);stack.extend(children)
        return {"status":status,"expression_nodes":len(seen),"constants":sorted(self.name(z) for z in ns)}
    def closure(self,mp,root,limit,seconds):
        if root in self.root_cache:return self.root_cache[root]
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
                constants,children=self.edges(mp,x)
                stack.extend(-z-1 for z in constants)
                stack.extend(children)
                if count>=limit or (count%262144==0 and time.monotonic()-start>seconds):
                    status="BUDGET_EXHAUSTED";break
        selected_inside=sorted(k for k,(i,_) in self.selected.items() if i in decls)
        blocked=sorted(self.name(i) for i in decls if str(self.parts[i]) in EXCLUDED_SUFFIXES)
        membership=None
        if status=="COMPLETE" and not missing:
            # Export-local name IDs, little endian, exact sorted membership.
            raw=array.array("I",sorted(decls))
            if sys.byteorder!="little":raw.byteswap()
            membership={"encoding":"LE_U32_SORTED_ZLIB_BASE64_V1","count":len(raw),"sha256":hashlib.sha256(raw.tobytes()).hexdigest(),"data":base64.b64encode(zlib.compress(raw.tobytes(),6)).decode()}
        result={"status":status if not missing else "UNRESOLVED_REFERENCES_OR_"+status,"membership":membership,"endpoint_like_dependencies":blocked,
                "declarations":len(decls),"expression_nodes":count,"missing_count":len(missing),
                "missing_sample":sorted(self.name(z) for z in list(missing)[:30]),"axioms":sorted(self.name(z) for z in axioms),
                "selected_roots_reached":selected_inside,"seconds":round(time.monotonic()-start,3)}
        if membership:self.root_cache[root]=result
        return result
    def report(self,mode,limit,seconds):
        self.quot_names=[n for n,(k,*_) in self.decls.items() if k=="quot"]
        roles={r["name"]:r["role"] for r in PIN["catalog"]}
        # Also refuse the original internal RH endpoint and headline aliases,
        # not only the currently synchronized Main declaration.
        excluded={k for k,v in roles.items() if v.endswith("_EXCLUDED")}|{"LFunction_ne_zero_of_half_lt_re","riemannHypothesis","UpperTheory.FinalTheorems.riemannHypothesis","riemannZeta_eq_zero_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive"}
        with (self.folder/"expr.edges").open("rb") as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mp:
            discovery=self.discover(mp) if mode=="solution" else {"eligible_count":0,"selected_count":0,"selected":[],"complete":True}
            out=[]
            for name in sorted(self.want):
                if name not in self.selected:
                    out.append({"name":name,"status":"NOT_PRESENT_IN_EXPORT","role":roles.get(name,"ENDPOINT_EXCLUDED")});continue
                if getattr(self,"checkpoint",False):
                    from index_checkpoint import load_root
                    cached=load_root(self,name,limit,seconds)
                    if cached is not None:
                        out.append(cached);print("REUSED_ROOT",name,flush=True);continue
                idx,p=self.selected[name];kind,t,v,group,es=self.decls[idx]
                role=roles.get(name,"DISCOVERED_PRODUCER_LEAD" if name in discovery["selected"] else "ENDPOINT_EXCLUDED")
                row={"name":name,"role":role,"kind":kind,
                     "exact_declaration_record":p,"type_dependencies":self.direct(mp,t),
                     "value_dependencies":self.direct(mp,v),"structural_names":[self.name(z) for z in group],
                     "closure":self.closure(mp,idx,limit,seconds)}
                row["status"]="INDEXED"
                try:
                    row["type_expression"]=self.type_dag(mp,t)
                    row["type_status"]="ORIGINAL_EXPORT_EXPR_CONVERTED"
                    if kind=="def" and v and name in roles:
                        row["definition_expression"]=self.type_dag(mp,v)
                except RuntimeError as ex:
                    row["type_status"]="TYPE_CONVERSION_INCOMPLETE";row["type_error"]=str(ex)
                row["excluded_dependencies"]=sorted(set(x for x in row["closure"]["selected_roots_reached"] if x in excluded)|set(row["closure"]["endpoint_like_dependencies"]))
                out.append(row);print("ROOT",name,row["closure"]["status"],row["closure"]["declarations"],flush=True)
                if getattr(self,"checkpoint",False):
                    from index_checkpoint import save_root
                    save_root(self,name,row,limit,seconds)
        candidates=[x for x in out if x.get("status")=="INDEXED" and x["role"].startswith(("CONDITIONAL_","PRODUCER_","DISCOVERED_")) and x["closure"]["status"]=="COMPLETE" and not x["excluded_dependencies"] and set(x["closure"]["axioms"])<=set(PIN["allowed_axioms"])]
        candidates.sort(key=lambda x:(x["closure"]["declarations"],x["name"]))
        return {"schema":"OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1","mode":mode,"meta":self.meta,
                "raw_sha256":self.verified_digest or self.hash.hexdigest(),"raw_bytes":self.bytes,"names":len(self.parts),"expressions":self.nexpr,"declarations":len(self.decls),
                "roots":out,"discovery":discovery,"ranked_complete_closure_leads":[{"name":x["name"],"role":x["role"],"declarations":x["closure"]["declarations"]} for x in candidates],
                "scope":"ELABORATED_DEPENDENCY_EDGES_WITH_CONSERVATIVE_STRUCTURAL_GROUPS_NOT_A_KERNEL_CHECK",
                "proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"}
def remote(index,spec):
    expected=spec["raw_bytes"]
    diagnostics={"url":spec["url"],"expected_raw_bytes":expected,"expected_raw_sha256":spec["raw_sha256"]}
    index.transport=diagnostics
    stderr=index.folder/"zstd.stderr"
    def check_raw(proc,err,feed_error=None):
        error=None
        try:index.consume(proc.stdout,expected,spec["raw_sha256"])
        except BaseException as ex:error=ex
        finally:
            proc.stdout.close()
        rc=proc.wait(timeout=120)
        diagnostics.update(zstd_exit=rc,zstd_stderr=stderr.read_text(errors="replace")[-3000:],observed_raw_bytes=index.bytes,observed_raw_sha256=index.hash.hexdigest())
        if feed_error:raise RuntimeError(feed_error)
        if rc!=0:raise RuntimeError("zstd failed: "+diagnostics["zstd_stderr"])
        if error:raise error
    if spec["url"].endswith("/challenge.ndjson.zst"):
        # Small challenge: eliminate pipe/download races and retain the actual HTTP
        # response. Retry only the whole file, never concatenate partial attempts.
        archive=index.folder/"challenge.zst"
        headers=index.folder/"challenge.headers"
        rc=subprocess.run(["curl","--fail","--location","--silent","--show-error","--retry","3","--retry-all-errors","--max-time","600","-H","Accept-Encoding: identity","-H","Cache-Control: no-cache","--dump-header",str(headers),"--output",str(archive),spec["url"]],capture_output=True,text=True)
        diagnostics["curl_exit"]=rc.returncode
        diagnostics["http_headers"]=headers.read_text(errors="replace")[-4000:] if headers.exists() else ""
        need(rc.returncode==0,"challenge download failed: "+rc.stderr[-1000:])
        h=hashlib.sha256()
        with archive.open("rb") as f:
            for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
        diagnostics.update(compressed_bytes=archive.stat().st_size,compressed_sha256=h.hexdigest())
        need(archive.stat().st_size==spec["compressed_bytes"] and h.hexdigest()==spec["compressed_sha256"],"challenge compressed identity mismatch")
        # Separate from Index.consume: independent command-line byte and digest measurements.
        p=subprocess.Popen(["zstd","-d","-c",str(archive)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        count=subprocess.check_output(["wc","-c"],stdin=p.stdout);p.stdout.close()
        need(p.wait()==0 and int(count)==expected,"independent challenge length mismatch")
        p=subprocess.Popen(["zstd","-d","-c",str(archive)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        digest=subprocess.check_output(["sha256sum"],stdin=p.stdout).decode().split()[0];p.stdout.close()
        need(p.wait()==0 and digest==spec["raw_sha256"],"independent challenge digest mismatch")
        diagnostics.update(independent_wc=int(count),independent_sha256=digest)
        with stderr.open("wb") as err:
            proc=subprocess.Popen(["zstd","-d","-c","--long=27",str(archive)],stdout=subprocess.PIPE,stderr=err)
            try:check_raw(proc,err)
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        return diagnostics
    # Solution is too large to retain both archive and index on a hosted disk.
    # Independent exact byte authentication, HTTP length, and decompressor exit
    # all mandatory. Observe feed errors before accepting a raw mismatch.
    errors=[];stats={}
    with stderr.open("wb") as err:
        proc=subprocess.Popen(["zstd","-d","-c","--long=30"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,start_new_session=True)
        def feed():
            h=hashlib.sha256();n=0
            try:
                request=urllib.request.Request(spec["url"],headers={"Accept-Encoding":"identity","Cache-Control":"no-cache","User-Agent":"OPICA-proof-mining/1"})
                with urllib.request.urlopen(request,timeout=120) as src,proc.stdin as dst:
                    diagnostics.update(http_status=src.status,http_content_length=src.headers.get("Content-Length"),http_content_range=src.headers.get("Content-Range"),final_url=src.geturl())
                    need(src.status==200,"partial HTTP response refused")
                    if src.headers.get("Content-Length"):
                        need(abs(int(src.headers["Content-Length"])-spec["compressed_bytes"])<=spec.get("compressed_size_slack",0),"HTTP length outside reviewed cap")
                    while True:
                        b=src.read(1024*1024)
                        if not b:break
                        n+=len(b);h.update(b)
                        need(n<=spec["compressed_bytes"]+spec.get("compressed_size_slack",0),"compressed size exceeds reviewed cap")
                        dst.write(b)
                need(abs(n-spec["compressed_bytes"])<=spec.get("compressed_size_slack",0) and h.hexdigest()==spec["compressed_sha256"],"compressed artifact mismatch")
            except BaseException as ex:
                errors.append(repr(ex))
                try:proc.stdin.close()
                except Exception:pass
            finally:stats.update(compressed_bytes=n,compressed_sha256=h.hexdigest())
        t=threading.Thread(target=feed,daemon=True);t.start()
        failure=None
        try:
            try:index.consume(proc.stdout,expected,spec["raw_sha256"],spec.get("raw_size_slack",0))
            except BaseException as ex:failure=ex
            proc.stdout.close()
            t.join(timeout=180)
            rc=proc.wait(timeout=120)
            diagnostics.update(stats);diagnostics.update(feed_errors=errors,zstd_exit=rc,zstd_stderr=stderr.read_text(errors="replace")[-3000:],observed_raw_bytes=index.bytes,observed_raw_sha256=index.hash.hexdigest())
            need(not t.is_alive() and not errors,"compressed transport failed: "+str(errors))
            need(rc==0,"zstd failure: "+diagnostics["zstd_stderr"])
            if failure:raise failure
            diagnostics["published_size_deltas"]={"raw":index.bytes-expected,"compressed":stats["compressed_bytes"]-spec["compressed_bytes"]}
            return diagnostics
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
def main():
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=("challenge","solution"),required=True);p.add_argument("--output",type=pathlib.Path,required=True);p.add_argument("--scratch",type=pathlib.Path,required=True);p.add_argument("--closure-budget",type=int,default=100000000);p.add_argument("--root-seconds",type=int,default=300)
    p.add_argument("--keep-index",action="store_true")
    p.add_argument("--resume-index",action="store_true")
    a=p.parse_args();need(a.closure_budget>0 and a.root_seconds>0,"invalid budget")
    need(not a.output.exists(),"fresh output required")
    need(not a.resume_index or a.keep_index,"resume requires keep-index")
    if not a.resume_index:a.scratch.mkdir(parents=True,exist_ok=False)
    ix=None
    try:
        from index_checkpoint import save_index,load_index
        if a.resume_index:
            ix,st=load_index(a.scratch,a.mode,Index)
        else:
            ix=Index(a.scratch,10*1024**3)
            ix.want.update(["UpperTheory.FinalTheorems.riemannHypothesis","riemannZeta_eq_zero_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive"])
            ix.leaves={x.split(".")[-1] for x in ix.want}
            st=remote(ix,PIN["original"][a.mode])
            ix.verified_digest=ix.hash.hexdigest()
            if a.keep_index:save_index(ix,a.mode,st)
        ix.checkpoint=a.keep_index
        report=ix.report(a.mode,a.closure_budget,a.root_seconds);report["download"]=st
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
        if not a.output.exists():write(a.output,{"schema":"OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1","status":"INCOMPLETE_OR_REJECTED","mode":a.mode,"reason":str(ex)[:2000],"transport":getattr(ix,"transport",{}),"observed_raw_bytes":getattr(ix,"bytes",None),"observed_raw_sha256":ix.hash.hexdigest() if ix is not None else None,"proof_acceptance":False,"C1":"OPEN"})
        print("INDEX_FAILURE",repr(ex),json.dumps(getattr(ix,"transport",{})),flush=True);raise
    finally:
        if not a.keep_index:shutil.rmtree(a.scratch)
if __name__=="__main__":main()
