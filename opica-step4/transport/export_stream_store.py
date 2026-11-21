#!/usr/bin/env python3
"""Store a command's exact stdout as a read-only compressed regular file.

Stock mksquashfs's dynamic pseudo-file reader handles unknown output length.
The producer runs without a shell, reports its actual exit status and stdout
digest, and a separate stock unsquashfs readback must match every byte.  This
tool proves transport integrity only; the stored export still needs checking.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from verified_squashfs_store import CHUNK, digest_path, _limit_output


def worker(spec_path: Path) -> int:
    spec=json.loads(spec_path.read_text())
    sha=hashlib.sha256(); count=0; proc=None; code=None; failure=None
    try:
        with open(spec['stderr'],'wb') as err:
            proc=subprocess.Popen(spec['command'],cwd=spec['cwd'],stdout=subprocess.PIPE,stderr=err)
            assert proc.stdout is not None
            with proc.stdout:
                while block:=proc.stdout.read(CHUNK):
                    count+=len(block)
                    if count>spec['max_bytes']:
                        raise ValueError('Producer exceeded uncompressed output bound')
                    sha.update(block)
                    sys.stdout.buffer.write(block)
            sys.stdout.buffer.flush()
            code=proc.wait()
    except BaseException as exc:
        failure=repr(exc)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
        code=proc.returncode if proc is not None else 127
    result={'command':spec['command'],'cwd':spec['cwd'],'exit_code':code,
            'stdout_bytes':count,'stdout_sha256':sha.hexdigest(),'transport_error':failure}
    Path(spec['result']).write_text(json.dumps(result,indent=2)+'\n')
    if failure or code!=0:
        return 1
    return 0


def build_export(command: list[str], cwd: Path, output: Path, *, mksquashfs='mksquashfs',
                 unsquashfs='unsquashfs', max_bytes=100*1024**3,
                 image_max_bytes=16*1024**3, min_free_bytes=18*1024**3,
                 expected_sha256=None, expected_bytes=None, memory_mb=512,
                 processors=2, timeout_seconds=18000) -> dict:
    if not command or any(not isinstance(x,str) or '\0' in x for x in command):
        raise ValueError('Producer argv must be a nonempty string array')
    cwd=cwd.resolve(strict=True)
    output=output.absolute(); output.parent.mkdir(parents=True,exist_ok=True)
    receipt_path=output.with_suffix(output.suffix+'.receipt.json')
    producer_log=output.with_suffix(output.suffix+'.producer.log')
    if any(p.exists() or p.is_symlink() for p in (output,receipt_path,producer_log)):
        raise ValueError('Output/receipt/log already exists')
    if shutil.disk_usage(output.parent).free<min_free_bytes:
        raise ValueError('Insufficient free disk for configured export preflight')
    mk=Path(shutil.which(str(mksquashfs)) or mksquashfs).resolve(strict=True)
    un=Path(shutil.which(str(unsquashfs)) or unsquashfs).resolve(strict=True)
    started=time.monotonic(); created=[]
    with tempfile.TemporaryDirectory(prefix='.export-store-',dir=output.parent) as stage_name:
        stage=Path(stage_name); empty=stage/'empty'; empty.mkdir()
        image=stage/'image.partial'; result=stage/'producer-result.json'; stderr=stage/'producer.log'
        spec=stage/'producer-spec.json'
        spec.write_text(json.dumps({'command':command,'cwd':str(cwd),'max_bytes':max_bytes,
                        'result':str(result),'stderr':str(stderr)}))
        worker_cmd=' '.join(shlex.quote(x) for x in [sys.executable,str(Path(__file__).resolve()),'--worker',str(spec)])
        pseudo='export.ndjson f 444 0 0 '+worker_cmd
        argv=[str(mk),str(empty),str(image),'-noappend','-comp','zstd','-Xcompression-level','9',
              '-b','1M','-processors',str(processors),'-mem',f'{memory_mb}M','-no-progress',
              '-no-xattrs','-all-root','-all-time','0','-mkfs-time','0','-exit-on-error','-p',pseudo]
        proc=None
        try:
            with (stage/'mksquashfs.log').open('wb') as log:
                proc=subprocess.Popen(argv,stdout=log,stderr=log,start_new_session=True,
                            preexec_fn=lambda:_limit_output(image_max_bytes))
                rc=proc.wait(timeout=timeout_seconds)
            if rc!=0:
                raise RuntimeError('mksquashfs/producer failure: '+(stage/'mksquashfs.log').read_text(errors='replace')[-3000:])
            if not result.is_file(): raise ValueError('Missing independent producer receipt')
            report=json.loads(result.read_text())
            if report['exit_code']!=0 or report['transport_error'] is not None:
                raise ValueError('Producer did not complete successfully')
            if expected_sha256 is not None and report['stdout_sha256']!=expected_sha256:
                raise ValueError('Export does not match required SHA256')
            if expected_bytes is not None and report['stdout_bytes']!=expected_bytes:
                raise ValueError('Export does not match required byte count')
            if not 0<report['stdout_bytes']<=max_bytes:
                raise ValueError('Empty or oversized export')
            sha=hashlib.sha256(); count=0
            with (stage/'readback.log').open('wb') as log:
                readback=subprocess.Popen([str(un),'-cat',str(image),'export.ndjson'],stdout=subprocess.PIPE,stderr=log)
                assert readback.stdout is not None
                with readback.stdout:
                    while block:=readback.stdout.read(CHUNK):
                        count+=len(block)
                        if count>max_bytes:
                            readback.kill(); readback.wait(); raise ValueError('Readback exceeded byte bound')
                        sha.update(block)
                if readback.wait()!=0: raise ValueError('Stock unsquashfs readback failed')
            if count!=report['stdout_bytes'] or sha.hexdigest()!=report['stdout_sha256']:
                raise ValueError('Byte-exact independent export readback mismatch')
            report.update({'schema':1,'status':'EXACT_EXPORT_TRANSPORT_VERIFIED','proof_validity_established':False,
                'image_sha256':digest_path(image),'image_bytes':image.stat().st_size,'path_in_image':'export.ndjson',
                'readback_sha256':sha.hexdigest(),'readback_bytes':count,
                'mksquashfs_sha256':digest_path(mk),'unsquashfs_sha256':digest_path(un),
                'helper_sha256':digest_path(Path(__file__).resolve()),
                'elapsed_s':round(time.monotonic()-started,3)})
            image.chmod(0o444); os.link(image,output); created.append(output)
            with producer_log.open('xb') as f, stderr.open('rb') as source_log:
                shutil.copyfileobj(source_log,f,CHUNK)
            created.append(producer_log)
            with receipt_path.open('x') as f: json.dump(report,f,indent=2); f.write('\n')
            created.append(receipt_path)
            return report
        except BaseException:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL); proc.wait()
            for p in reversed(created): p.unlink(missing_ok=True)
            raise


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        raise SystemExit(worker(Path(sys.argv[2])))
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--cwd',required=True,type=Path)
    ap.add_argument('--mksquashfs',default='mksquashfs')
    ap.add_argument('--unsquashfs',default='unsquashfs')
    ap.add_argument('--expected-sha256')
    ap.add_argument('--expected-bytes',type=int)
    ap.add_argument('--max-export-gib',type=int,default=100)
    ap.add_argument('--max-image-gib',type=int,default=16)
    ap.add_argument('--min-free-gib',type=int,default=18)
    ap.add_argument('command',nargs=argparse.REMAINDER)
    args=ap.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    report=build_export(command,args.cwd,args.output,mksquashfs=args.mksquashfs,
        unsquashfs=args.unsquashfs,expected_sha256=args.expected_sha256,expected_bytes=args.expected_bytes,
        max_bytes=args.max_export_gib*1024**3,image_max_bytes=args.max_image_gib*1024**3,
        min_free_bytes=args.min_free_gib*1024**3)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
