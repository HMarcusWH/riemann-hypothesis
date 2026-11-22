#!/usr/bin/env python3
"""Nonaccepting, exact-file I/O comparison; never a Lean proof or acceptance gate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import time

LINE=re.compile(r"([0-9a-f]{64})  (.+)\Z")
MAX_PATHS=350374

class StorageError(ValueError):
    pass


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda:stream.read(4<<20),b""):h.update(data)
    return h.hexdigest()


def parse_manifest(raw:str)->list[tuple[str,str]]:
    records=[]
    seen=set()
    for line in raw.splitlines():
        match=LINE.fullmatch(line)
        if match is None:
            raise StorageError("Invalid original sha256sum manifest row")
        digest,path=match.groups()
        p=Path(path)
        if p.is_absolute() or path in seen or p.as_posix()!=path or "." in p.parts or ".." in p.parts:
            raise StorageError("Unsafe or duplicate relative proof-store member")
        seen.add(path);records.append((digest,path))
    if not (0<len(records)<=MAX_PATHS):
        raise StorageError("Invalid manifest population")
    return records


def select(records:list[tuple[str,str]],count:int)->list[tuple[str,str]]:
    if not (0<count<=4096):
        raise StorageError("Benchmark sample count out of bounds")
    return sorted(records,key=lambda row:hashlib.sha256(row[1].encode()).hexdigest())[:min(count,len(records))]


def sample(root:Path,items:list[tuple[str,str]])->dict:
    if root.is_symlink() or not root.is_dir():
        raise StorageError("Proof store must be a directory, not a symlink")
    files=0;total=0
    t=time.monotonic()
    for expected,relative in items:
        target=root
        for part in Path(relative).parts:
            target=target/part
            if target.is_symlink():
                raise StorageError("Linked supplier proof object: "+relative)
        st=target.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise StorageError("Nonregular supplier proof object: "+relative)
        actual=sha256(target)
        if actual!=expected:
            raise StorageError("Supplier proof object checksum mismatch: "+relative)
        files+=1;total+=st.st_size
    return {"sampled_files":files,"verified_bytes":total,
            "elapsed_seconds":round(time.monotonic()-t,6),
            "status":"SAMPLED_IO_CHECKSUM_MATCH",
            "proof_acceptance":False}


def compare(manifest:Path,first:Path,second:Path,count:int)->dict:
    if manifest.is_symlink() or not manifest.is_file():
        raise StorageError("Unsafe original manifest")
    records=parse_manifest(manifest.read_text())
    items=select(records,count)
    return {
        "schema":"OPICA_NONACCEPTING_STORAGE_OBSERVATION_V1",
        "manifest_sha256":sha256(manifest),"manifest_file_count":len(records),
        "selection":"LEXICAL_SHA256_PATH_RANKED",
        "sampled_file_paths":[row[1] for row in items],
        "first":sample(first,items),"second":sample(second,items),
        "same_files_and_expected_digests":True,
        "causal_performance_claim":False,
        "complete_supplier_store_verified":False,
        "proof_acceptance":False,
        "scope":"Read-only, bounded sample; full 350374-object verification remains mandatory elsewhere",
    }


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--first",type=Path,required=True)
    p.add_argument("--second",type=Path,required=True)
    p.add_argument("--sample-count",type=int,default=512)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        p.error("Output must be fresh")
    data=compare(a.manifest,a.first,a.second,a.sample_count)
    a.output.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({"status":"NONACCEPTING_SAMPLE_COMPLETE",
                      "n":len(data["sampled_file_paths"]),"proof_acceptance":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
