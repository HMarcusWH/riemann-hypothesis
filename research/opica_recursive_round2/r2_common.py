"""Immutable research epoch helpers. No source/claim promotion."""
from __future__ import annotations
import hashlib,json,os,re,subprocess,signal,time,sys,gzip
from functools import lru_cache
from pathlib import Path

HERE=Path(__file__).resolve().parent
R1=HERE.parent/"opica_extract_round1"
LOCK=json.loads((HERE/"LOCK.json").read_text())
R1_PIN=json.loads((R1/"CONTRACT.json").read_text())
CLAIMS={"RH":"OPEN","C1":"OPEN","Step4":"OPEN","proof_acceptance":False}
ALLOWED={"propext","Classical.choice","Quot.sound"}
BUDGET=LOCK["budget"]
def need(ok,reason):
    if not ok: raise RuntimeError(reason)
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def filehash(path):
    with Path(path).open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()
def read(path,limit=256<<20):
    path=Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=limit,"Missing, linked or oversized input: "+str(path))
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d,"Duplicate JSON key: "+k);d[k]=v
        return d
    return json.loads(path.read_bytes(),object_pairs_hook=pairs)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f: json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def dependency_key(row):
    return digest([row["world"],row["declaration"],row["type_sha256"]])

def compact_dependency_row(row,folder):
    """Store the full checked dependency set separately, not 978 MB of
    repeated names in the search inventory. Search retains counts and hashes."""
    row=dict(row);deps=row.pop("dependencies")
    need(type(deps) is list and all(isinstance(x,str) for x in deps),"Invalid dependency list")
    key=dependency_key(row)
    rel="dependency-closures/"+key+".json.gz";p=Path(folder)/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(deps,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
    with p.open("xb") as f:
        with gzip.GzipFile(filename="",mode="wb",fileobj=f,mtime=0,compresslevel=6) as z:z.write(raw)
    row.update(closure_count=row.get("closure_count",len(deps)),dependency_count=len(deps),dependency_sha256=hashlib.sha256(raw).hexdigest(),dependency_file=rel,dependency_archive_sha256=filehash(p),dependency_archive_bytes=p.stat().st_size)
    return row
def verify_dependency_row(row,folder):
    rel=row["dependency_file"];need(re.fullmatch(r"dependency-closures/[0-9a-f]{64}\.json\.gz",rel) is not None,"Bad closure path")
    need(rel=="dependency-closures/"+dependency_key(row)+".json.gz","Closure is not bound to declaration/type/world")
    p=Path(folder)/rel;need(p.resolve().is_relative_to(Path(folder).resolve()) and not p.parent.is_symlink() and p.is_file() and not p.is_symlink() and p.stat().st_size==row["dependency_archive_bytes"] and filehash(p)==row["dependency_archive_sha256"],"Closure archive drift")
    with gzip.open(p,"rb") as z:raw=z.read(64<<20)
    need(len(raw)<64<<20 and hashlib.sha256(raw).hexdigest()==row["dependency_sha256"],"Closure digest/size")
    deps=json.loads(raw);need(type(deps) is list and len(deps)==row.get("dependency_count",row["closure_count"]) and all(isinstance(x,str) and not forbidden(x) for x in deps),"Closure inventory or endpoint")
    return True

def verify_inventory(inventory,folder):
    """Fail closed before using the on-disk inventory in any feedback pass."""
    need(inventory.get("schema")=="OPICA_R2_QUALIFIED_RESEARCH_INVENTORY_V2","Unexpected inventory schema")
    rows=inventory["native_rows"]+inventory["external_research_rows"]
    seen=set()
    for row in rows:
        key=dependency_key(row)
        need(key not in seen,"Duplicate inventory identity")
        seen.add(key)
        verify_dependency_row(row,folder)
    return len(seen)

def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True,timeout=180).strip()
def check_pin(repo,pin,clean=True):
    need(git(repo,"rev-parse","HEAD")==pin["head"] and git(repo,"rev-parse","HEAD^{tree}")==pin["tree"],"Exact source pin differs")
    if clean: need(not git(repo,"status","--porcelain","--untracked-files=all"),"Source checkout dirty")
    if "toolchain" in pin:
        need((repo/"lean-toolchain").read_text().strip()==pin["toolchain"],"Compiler pin differs")
        p=[x for x in read(repo/"lake-manifest.json")["packages"] if x["name"]=="mathlib"]
        need(len(p)==1 and p[0]["rev"]==pin["mathlib"],"Mathlib pin differs")
def controller_scope(repo):
    parent=LOCK["controller"]["parent"]
    need(git(repo,"rev-parse",parent+"^{tree}")==LOCK["controller"]["tree"],"R1 parent tree differs")
    need(subprocess.run(["git","-C",str(repo),"merge-base","--is-ancestor",parent,"HEAD"],capture_output=True).returncode==0,"R2 ancestry differs")
    rows=git(repo,"diff","--name-status","--no-renames",parent,"HEAD").splitlines()
    need(rows and all(x.startswith("A\t") and (x[2:].startswith("research/opica_recursive_round2/") or x[2:]==".github/workflows/opica-recursive-r2.yml") for x in rows),"R2 must not alter inherited source")
    need(not git(repo,"status","--porcelain","--untracked-files=all"),"Controller checkout dirty")
    return {"head":git(repo,"rev-parse","HEAD"),"tree":git(repo,"rev-parse","HEAD^{tree}"),"parent":parent,"files":[x[2:] for x in rows]}
def compiler_env():
    d=dict(os.environ)
    for k in ("GH_TOKEN","GITHUB_TOKEN","OPICA_READ_TOKEN","ACTIONS_RUNTIME_TOKEN","LD_PRELOAD","LD_AUDIT","DYLD_INSERT_LIBRARIES","LEAN_PATH","LEAN_SRC_PATH","LEAN_SYSROOT"):
        d.pop(k,None)
    d["LEAN_NUM_THREADS"]="2";d["LAKE_ARTIFACT_CACHE"]="false";d["PYTHONDONTWRITEBYTECODE"]="1"
    return d
def command(argv,cwd,env,log,seconds=600,max_bytes=128<<20):
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    begin=time.monotonic();p=None;reason=None
    with log.open("xb") as f:
        try:
            p=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            while p.poll() is None:
                if time.monotonic()-begin>seconds or log.stat().st_size>max_bytes:
                    reason="RESOURCE_EXHAUSTED";break
                time.sleep(.1)
        finally:
            if p is not None:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait()
    status=reason or ("PASS" if p and p.returncode==0 else "REJECTED")
    if log.stat().st_size>max_bytes: status="RESOURCE_EXHAUSTED"
    return {"status":status,"exit":p.returncode if p else None,"sha256":filehash(log),"seconds":round(time.monotonic()-begin,2)}
def marker_rows(log,marker):
    prefix=marker+"\t"
    return [json.loads(x[len(prefix):]) for x in Path(log).read_text(encoding="utf-8",errors="replace").splitlines() if x.startswith(prefix)]
def source_name(s):
    need(isinstance(s,str) and re.fullmatch(r"[\w'.]+",s) is not None and not s.startswith(".") and not s.endswith("."),"Invalid declaration/module name")
    return s
@lru_cache(maxsize=200000)
def forbidden(n):
    # Reuse R1's stronger final-endpoint list and additionally exclude terminal
    # consumers, calibration answers and explicit RH-conditioned proof inputs.
    if str(R1) not in sys.path:sys.path.insert(0,str(R1))
    from candidate_validate import FORBIDDEN,SUFFIXES
    leaf=n.split(".")[-1]
    return (n in FORBIDDEN or leaf in SUFFIXES or "riemannHypothesis" in leaf or "RiemannHypothesis" in leaf
            or any(s in n for s in (".Validation.",".identityGold",".transportGold",".packetGold"))
            or leaf in {"no_off_line_zero_of_cofinal_moment_slice_bounds","not_cofinal_moment_slice_bounds_of_off_line_zero"})
