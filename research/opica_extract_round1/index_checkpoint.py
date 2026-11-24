"""Reusable research-only completed index and root traversal checkpoints.
No pickle, no deserialization of executable state. Resume requires a fully
authenticated export ingest, not an unverified partial download. Rehash
the disk index and serialized tables before reuse. A retained local index
is not independent mathematical evidence; new runs never inherit proof authority.
"""
import array,gzip,hashlib,json,pathlib,os
from scan import PIN,need
from export_graph import BASE_REC,REC,INDEX_FORMAT
def producer_identity():
    return {n:filehash(pathlib.Path(__file__).with_name(n)) for n in ("export_graph.py","index_checkpoint.py")}
def filehash(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def atomic(path,data):
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def sha(data):return hashlib.sha256(data).hexdigest()
def save_index(ix,mode,transport):
    spec=PIN["original"][mode]
    need(ix.verified_digest==spec["raw_sha256"],"cannot checkpoint unauthenticated export")
    state={"parents":list(ix.parents),"parts":ix.parts,"decls":[[k,*v] for k,v in ix.decls.items()],"levels":ix.levels,"us":ix.us,"literals":ix.literals,"selected":ix.selected,"want":sorted(ix.want),"nexpr":ix.nexpr,"extra_count":ix.extra_count,"nlevels":ix.nlevels,"bytes":ix.bytes,"lines":ix.lines,"meta":ix.meta}
    p=ix.folder/"tables.json.gz";tmp=p.with_suffix(".tmp")
    with gzip.open(tmp,"wt",encoding="utf8",compresslevel=3) as f:json.dump(state,f,ensure_ascii=False,separators=(",",":"))
    tmp.replace(p)
    edges=ix.folder/"expr.edges"
    overflow=ix.folder/"expr.overflow"
    need(edges.stat().st_size==BASE_REC.size*ix.nexpr and overflow.stat().st_size==REC.size*ix.extra_count,"index size changed")
    meta={"schema":"OPICA_COMPLETE_INDEX_V2","format":INDEX_FORMAT,"producer":producer_identity(),"mode":mode,"raw_sha256":ix.verified_digest,"raw_bytes":ix.bytes,"tables_sha256":filehash(p),"edges_sha256":filehash(edges),"edges_bytes":edges.stat().st_size,"overflow_sha256":filehash(overflow),"overflow_bytes":overflow.stat().st_size,"transport":transport,"proof_acceptance":False}
    atomic(ix.folder/"INDEX_READY.json",json.dumps(meta,sort_keys=True).encode())
    ix.index_identity=sha((ix.folder/"INDEX_READY.json").read_bytes())
def load_index(folder,mode,cls):
    p=folder/"INDEX_READY.json";raw=p.read_bytes();m=json.loads(raw)
    need(m["schema"]=="OPICA_COMPLETE_INDEX_V2" and m["format"]==INDEX_FORMAT and m["producer"]==producer_identity() and m["mode"]==mode and m["raw_sha256"]==PIN["original"][mode]["raw_sha256"] and m["proof_acceptance"] is False,"index epoch mismatch")
    need(filehash(folder/"tables.json.gz")==m["tables_sha256"] and filehash(folder/"expr.edges")==m["edges_sha256"] and filehash(folder/"expr.overflow")==m["overflow_sha256"],"checkpoint integrity")
    with gzip.open(folder/"tables.json.gz","rt",encoding="utf8") as f:s=json.load(f)
    need(s["bytes"]==m["raw_bytes"] and (folder/"expr.edges").stat().st_size==BASE_REC.size*s["nexpr"]==m["edges_bytes"] and (folder/"expr.overflow").stat().st_size==REC.size*s["extra_count"]==m["overflow_bytes"],"checkpoint size")
    ix=cls.__new__(cls);ix.folder=folder;ix.cap=m["edges_bytes"]+m["overflow_bytes"];ix.extra_count=s["extra_count"];ix.extra_map=None;ix.parents=array.array("I",s["parents"]);ix.parts=s["parts"]
    ix.decls={r[0]:(r[1],r[2],r[3],tuple(r[4]),tuple(r[5])) for r in s["decls"]}
    ix.levels=s["levels"];ix.us=[tuple(x) for x in s["us"]];ix.literals=[tuple(x) for x in s["literals"]]
    ix.selected={k:tuple(v) for k,v in s["selected"].items()};ix.want=set(s["want"]);ix.leaves={k.split(".")[-1] for k in ix.want}
    ix.nexpr=s["nexpr"];ix.nlevels=s["nlevels"];ix.bytes=s["bytes"];ix.lines=s["lines"];ix.meta=s["meta"]
    ix.verified_digest=m["raw_sha256"];ix.hash=hashlib.sha256();ix.root_cache={};ix.index_identity=sha(raw)
    return ix,m["transport"]
def rootpath(ix,name,limit,seconds):
    key=sha(json.dumps([ix.index_identity,name,limit,seconds,sorted(ix.want)],ensure_ascii=False,separators=(",",":")).encode())
    p=ix.folder/"root-checkpoints";p.mkdir(exist_ok=True)
    return p/(key+".json")
def save_root(ix,name,row,limit,seconds):
    if row["closure"]["status"]!="COMPLETE":return
    p=rootpath(ix,name,limit,seconds);raw=json.dumps(row,ensure_ascii=False,separators=(",",":")).encode()
    atomic(p,json.dumps({"sha256":sha(raw),"row":row},ensure_ascii=False,separators=(",",":")).encode())
def load_root(ix,name,limit,seconds):
    p=rootpath(ix,name,limit,seconds)
    if not p.is_file():return None
    x=json.loads(p.read_bytes());raw=json.dumps(x["row"],ensure_ascii=False,separators=(",",":")).encode()
    need(sha(raw)==x["sha256"] and x["row"]["name"]==name and x["row"]["closure"]["status"]=="COMPLETE","bad root checkpoint")
    return x["row"]
