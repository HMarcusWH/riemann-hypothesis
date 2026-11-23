#!/usr/bin/env python3
"""Fresh, bounded native OPICA common-pin bootstrap. Python 3.11+, Linux x86_64.

Creates a new integration directory; never updates native pins or accepts old
native objects. Trusted dependency packages live outside both proof projects.
Only the 572-module receiver closure is compiled. The receipt is consumed
unchanged by Round19 portable_gate/verify_combined.py::native_build_receipt.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time

BUNDLE = Path(__file__).resolve().parent
NATIVE_HEAD = "7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9"
NATIVE_TREE = "9248b76d7aff60aab3bb775c4be9750dc6006003"
MATHLIB = "0df444a360eaa60ab8c11dca51a86af692955474"
TOOLCHAIN = "leanprover/lean4:v4.33.1"
VERSION = "Lean (version 4.33.1, x86_64-unknown-linux-gnu, commit 819816b2e0a3bf405af45ae5c7af2491d8f5bee6, Release)"
ENDPOINT = "Zeta23.OPICARound4.ArithmeticFrontier.ZeroFreeFloor"
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
AUDIT_MODULES = ("OPICAStep4.ReceiverAudit", "OPICAStep4.ClaimFingerprint",
                 "OPICAStep4.BoundaryFlatCharacterization")
AUDIT_NAMES = (
    "Zeta23.OPICARound19.ReceiverAudit.exactReceiver",
    "Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_reflexive",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_is_native",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive",
    "Zeta23.OPICARound20.even_zero_bound_of_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.riemannHypothesis_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.finite_negative_boundary_flat_witness_refutes_c1",
)


class Failure(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Failure(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def inspect(argv, cwd, env=None):
    p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, timeout=180)
    require(p.returncode == 0, f"Inspection failed: {argv!r}\n{p.stderr[-3000:]}")
    return p.stdout.strip()


def git(repo, *args):
    return inspect(["git", "-C", repo, *args], repo)


def clean(repo, paths):
    require(not git(repo, "status", "--porcelain", "--untracked-files=no", "--", *paths),
            f"Tracked source/pin modifications: {repo}")
    extras = git(repo, "ls-files", "--others", "--exclude-standard", "--", *paths)
    require(not any(p.endswith(".lean") for p in extras.splitlines()),
            f"Untracked Lean sources in protected root: {repo}")


def strip_comments(text):
    """Same nested-comment handling as the frozen gate; not a proof parser."""
    out, depth, i, quoted = [], 0, 0, False
    while i < len(text):
        pair, c = text[i:i + 2], text[i]
        if depth:
            if pair == "/-":
                depth += 1; i += 2
            elif pair == "-/":
                depth -= 1; i += 2
            else:
                out.append("\n" if c == "\n" else " "); i += 1
        elif quoted:
            out.append(c)
            if c == "\\" and i + 1 < len(text):
                out.append(text[i + 1]); i += 2
            else:
                if c == '"': quoted = False
                i += 1
        elif pair == "/-":
            depth = 1; out.append("  "); i += 2
        elif pair == "--":
            j = text.find("\n", i)
            if j < 0: break
            out.append("\n"); i = j + 1
        else:
            out.append(c)
            if c == '"': quoted = True
            i += 1
    require(depth == 0, "Unclosed Lean comment")
    return "".join(out)


def module_path(module, suffix=".lean"):
    require(bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*", module)),
            "Invalid module name")
    return Path(*module.split(".")).with_suffix(suffix)


def imports(path):
    out = set()
    for line in strip_comments(path.read_text()).splitlines():
        match = re.match(r"^\s*(?:public\s+)?import\s+(.+?)\s*$", line)
        if match: out.update(match.group(1).split())
    return out


def source_closure(native):
    pending, graph, external = [ENDPOINT], {}, set()
    while pending:
        name = pending.pop()
        if name in graph: continue
        source = native / module_path(name)
        require(source.is_file(), f"Missing native source: {name}")
        imps = imports(source)
        deps = {x for x in imps if x.startswith("Zeta23.")}
        graph[name] = deps
        external.update(imps - deps)
        pending.extend(deps)
    frozen = json.loads((BUNDLE / "native_sources.json").read_text())
    require(len(graph) == 572 and set(graph) == set(frozen["modules"]),
            "Native import closure differs from the frozen 572 modules")
    for name, expected in frozen["modules"].items():
        source=native / module_path(name)
        require(digest(source) == expected, f"Native source changed: {name}")
        require(not re.search(r'\b(?:sorry|sorryAx|admit|axiom)\b',strip_comments(source.read_text())),
                f"Placeholder or project axiom token in native closure: {name}")
    external.add("Mathlib.NumberTheory.LSeries.RiemannZeta")
    return graph, sorted(external), frozen


def verify_native(native):
    require(git(native, "rev-parse", "HEAD") == NATIVE_HEAD, "Wrong native HEAD")
    require(git(native, "rev-parse", "HEAD^{tree}") == NATIVE_TREE, "Wrong native tree")
    require((native / "lean-toolchain").read_text().strip() == "leanprover/lean4:v4.33.0-rc2",
            "Native toolchain pin changed")
    clean(native, ["Zeta23", "lean-toolchain", "lake-manifest.json"])
    return source_closure(native)


def verify_runtime(rt):
    require(rt.name == "bin", "--toolchain-bin must name the actual toolchain bin directory")
    frozen = json.loads((BUNDLE / "runtime_files.json").read_text())
    for row in frozen["files"]:
        f = rt.parent / row["path"]
        require(f.is_file() and digest(f) == row["sha256"], f"Runtime byte identity mismatch: {f}")
    require(inspect([rt / "lean", "--version"], rt) == VERSION, "Unexpected compiler version")
    return {"compiler_version": VERSION, "compiler_sha256": digest(rt / "lean"),
            "lake_sha256": digest(rt / "lake"), "kernel_checker_sha256": digest(rt / "leanchecker"),
            "runtime_manifest_sha256": digest(BUNDLE / "runtime_files.json")}


def verify_package_sources(packages, manifest):
    result = []
    for row in manifest["packages"]:
        root = packages / row["name"]
        require(root.is_dir(), f"Missing pinned package: {root}")
        require(git(root, "rev-parse", "HEAD") == row["rev"], f"Wrong package revision: {row['name']}")
        clean(root, ["."])
        result.append({"name": row["name"], "revision": row["rev"], "path": str(root.resolve())})
    return result


def verify_reference_objects(packages):
    reference_path=BUNDLE / "trusted_objects.json.gz"
    with gzip.open(reference_path,'rt',encoding='utf-8') as stream:
        frozen = json.load(stream)
    for row in frozen["objects"]:
        f = packages / row["package"] / ".lake/build/lib/lean" / row["path"]
        require(f.is_file() and digest(f) == row["sha256"], f"Reference dependency object mismatch/missing: {f}")
    for package in packages.iterdir():
        root = package / ".lake/build/lib/lean/Zeta23"
        require(not root.exists(), "Trusted dependency root would shadow native Zeta23 modules")
    return {"count": frozen["count"], "bytes": frozen["bytes"],
            "reference_manifest_sha256": digest(reference_path),
            "scope": frozen["scope"]}


class Runner:
    def __init__(self, args, work):
        self.args, self.work = args, work
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.abort = threading.Event()
        self.active, self.records = {}, []
        self.logs = work / "bootstrap-logs"
        self.logs.mkdir(parents=True)
        self.monitor_error = None
        self.max_total_rss = 0
        self.monitor = threading.Thread(target=self.watch, daemon=True)
        self.monitor.start()

    def kill_all(self):
        with self.lock: procs = list(self.active.values())
        for p in procs:
            try: os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError: pass

    def watch(self):
        while not self.abort.wait(1):
            with self.lock: groups = set(self.active)
            rss = 0
            if groups:
                for f in Path('/proc').glob('[0-9]*/stat'):
                    try:
                        fields = f.read_text().rsplit(')', 1)[1].split()
                        if int(fields[3]) in groups: rss += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
                    except (OSError, ValueError, IndexError): pass
            self.max_total_rss = max(self.max_total_rss, rss)
            error = None
            if time.monotonic() - self.started > self.args.timeout: error = "Global bootstrap timeout"
            elif rss > self.args.aggregate_rss_mb * 1024**2: error = "Aggregate sampled process RSS limit"
            elif shutil.disk_usage(self.work).free < self.args.min_free_gb * 1024**3: error = "Disk reserve limit"
            if error:
                self.monitor_error = error; self.abort.set(); self.kill_all(); break

    def run(self, name, argv, cwd, env=None, strict=False):
        require(not self.abort.is_set(), self.monitor_error or "Bootstrap already failed")
        log = self.logs / (name + ".log")
        record = {"name": name, "command": list(map(str, argv)), "cwd": str(cwd),
                  "started_utc": utc(), "status": "RUNNING", "log": str(log)}
        started = time.monotonic()
        def limits():
            # Hard per-process virtual address bound, inherited by grandchildren.
            cap = self.args.process_address_space_gb * 1024**3
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        with log.open('wb') as output:
            p = subprocess.Popen(record["command"], cwd=cwd, env=env, stdout=output,
                                 stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
            with self.lock: self.active[p.pid] = p
            try:
                while p.poll() is None:
                    if self.abort.wait(.5):
                        try: os.killpg(p.pid, signal.SIGTERM)
                        except ProcessLookupError: pass
                        try: p.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            try: os.killpg(p.pid, signal.SIGKILL)
                            except ProcessLookupError: pass
                            p.wait()
                        break
                rc = p.wait()
            finally:
                with self.lock: self.active.pop(p.pid, None)
        text = log.read_text(errors='replace')
        errors = [line for line in text.splitlines() if re.search(
            r"(?:^|\s)error(?:\[[^\]]*\])?\s*:|uncaught exception|PANIC|sorryAx|unsolved goals|declaration uses 'sorry'", line)]
        warnings = [line for line in text.splitlines() if re.search(r"\bwarning(?:\[[^\]]*\])?\s*:", line)]
        ok = rc == 0 and not errors and not (strict and warnings) and not self.abort.is_set()
        record.update(exit_code=rc, status="PASS" if ok else "FAIL", completed_utc=utc(),
                      elapsed_seconds=round(time.monotonic()-started, 3), log_sha256=digest(log),
                      error_diagnostics=errors, warning_count=len(warnings))
        with self.lock: self.records.append(record)
        write_json(log.with_suffix('.process.json'), record)
        if not ok:
            self.abort.set(); self.kill_all()
            raise Failure(f"{name} failed (exit {rc}); {self.monitor_error or ''}; see {log}")
        return record


def fetch_git(runner, target, url, revision, sparse_native=False):
    require(not target.exists(), f"Refusing existing clone target: {target}")
    target.mkdir(parents=True)
    label = target.name
    runner.run(label+'_git_init', ['git','init',str(target)], target)
    runner.run(label+'_git_remote', ['git','remote','add','origin',url], target)
    if sparse_native:
        runner.run(label+'_git_sparse_init', ['git','sparse-checkout','init','--no-cone'], target)
        patterns = ['/Zeta23/','/lean-toolchain','/lake-manifest.json','/AGENTS.md']
        runner.run(label+'_git_sparse_set', ['git','sparse-checkout','set','--no-cone',*patterns], target)
    command = ['git','fetch','--depth=1']
    if sparse_native: command += ['--filter=blob:none']
    command += ['origin',revision]
    runner.run(label+'_git_fetch', command, target)
    runner.run(label+'_git_checkout', ['git','checkout','--detach',revision], target)


def install_runtime(runner, work):
    frozen = json.loads((BUNDLE/'runtime_files.json').read_text())
    archive = work/'lean-4.33.1-linux.tar.zst'
    runner.run('toolchain_download', ['curl','--fail','--location','--retry','2','--output',archive,
                                     frozen['archive_url']], work)
    require(digest(archive) == frozen['archive_sha256'], 'Official runtime archive SHA mismatch')
    runner.run('toolchain_extract', ['tar','--zstd','-xf',archive,'-C',work], work)
    # The exact authenticated archive has now been extracted. Free its redundant bytes.
    archive.unlink()
    return work/'lean-4.33.1-linux/bin'


def lake_env(rt, integration, jobs):
    env = os.environ.copy()
    for name in ['LEAN_PATH','LEAN_SRC_PATH','LEAN_SYSROOT','LAKE_CONFIG']:
        env.pop(name, None)
    env.update(PATH=str(rt)+os.pathsep+env.get('PATH',''), LEAN_NUM_THREADS=str(jobs), LEAN_ABORT_ON_PANIC='1')
    expr = 'import os,json; print(json.dumps({k:os.environ[k] for k in ["LEAN_PATH","LEAN_SRC_PATH","PATH","LD_LIBRARY_PATH","LEAN_SYSROOT"] if k in os.environ}))'
    env.update(json.loads(inspect([rt/'lake','env',sys.executable,'-c',expr],integration,env)))
    return env


def compile_one(runner, rt, integration, env, native, name, expected, strict=False):
    source = native/module_path(name)
    output = integration/'.lake/build/lib/lean'/module_path(name,'.olean')
    require(not output.exists(), f"Refusing stale native object: {output}")
    require(digest(source) == expected, f"Source changed before compilation: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [rt/'lean','-j1',f'-M{runner.args.lean_memory_mb}','-DrelaxedAutoImplicit=false',
           '-DmaxHeartbeats=800000', '--root='+str(native)]
    if strict: cmd.append('-DwarningAsError=true')
    cmd += [source,'-o',output,'-i',output.with_suffix('.ilean')]
    run = runner.run(name.replace('.','_'),cmd,integration,env,strict)
    require(output.is_file() and output.stat().st_size > 0, f"Missing compiled object: {name}")
    require(digest(source) == expected, f"Source changed during compilation: {name}")
    sidecars = {suffix: {'path':str(output.with_suffix(suffix)),
                         'sha256':digest(output.with_suffix(suffix))}
                for suffix in ['.olean.private','.olean.server','.ir','.ilean']
                if output.with_suffix(suffix).exists()}
    return {'module':name,'source_path':str(source),'source_sha256':expected,
            'object_path':str(output),'object_sha256':digest(output),
            'preexisting_object':False,'source_unchanged':True,'sidecars':sidecars,'process':run}


def build_native(runner, rt, integration, env, native, graph, frozen):
    todo, done, running, rows = set(graph), set(), {}, []
    with ThreadPoolExecutor(max_workers=runner.args.jobs) as pool:
        try:
            while todo or running:
                for name in sorted(todo):
                    if len(running) >= runner.args.jobs: break
                    if graph[name] <= done:
                        todo.remove(name)
                        task = pool.submit(compile_one,runner,rt,integration,env,native,name,frozen['modules'][name])
                        running[task] = name
                require(running, 'Cyclic or incomplete native dependency graph')
                finished, _ = wait(running, return_when=FIRST_COMPLETED)
                for task in finished:
                    name = running.pop(task)
                    rows.append(task.result());done.add(name)
                if len(done) % 20 == 0 or not todo:
                    print(f'Native modules completed: {len(done)}/572',flush=True)
        except BaseException:
            runner.abort.set(); runner.kill_all()
            raise
    return sorted(rows,key=lambda x:x['module'])


def parse_audits(text):
    result = {}
    for name in AUDIT_NAMES:
        begin, end = 'NATIVE_TYPE_BEGIN '+name, 'NATIVE_TYPE_END '+name
        require(text.splitlines().count(begin)==1 and text.splitlines().count(end)==1,
                'Missing/duplicate theorem type audit: '+name)
        m = re.search(re.escape(begin)+r'\n(.*?)\n'+re.escape(end),text,re.S)
        require(m is not None and '...' not in m.group(1) and '⋯' not in m.group(1), 'Incomplete theorem type')
        matches=re.findall("'"+re.escape(name)+r"' depends on axioms:\s*\[([^\]]*)\]",text,re.S)
        require(len(matches)==1,'Missing/duplicate axiom audit: '+name)
        axioms={x.strip() for x in matches[0].split(',') if x.strip()}
        require(axioms <= ALLOWED_AXIOMS,'Unexpected axioms: '+repr(axioms))
        result[name]={'type':m.group(1).strip(),'axioms':sorted(axioms)}
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True,help='New bootstrap workspace; existing directory is refused')
    parser.add_argument('--native-source',type=Path,help='Read-only immutable local checkout; otherwise fetch sparse exact HEAD')
    parser.add_argument('--trusted-packages',type=Path,required=True,help='Pinned common dependency directory, outside both projects')
    parser.add_argument('--toolchain-bin',type=Path,help='Actual verified 4.33.1 bin; otherwise install SHA-pinned archive')
    parser.add_argument('--external-project',type=Path,help='Only used to reject canonical paths under external project; never mutated')
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--timeout',type=int,default=14400)
    parser.add_argument('--aggregate-rss-mb',type=int,default=10000)
    parser.add_argument('--process-address-space-gb',type=int,default=24)
    parser.add_argument('--lean-memory-mb',type=int,default=6144)
    parser.add_argument('--min-free-gb',type=float,default=3.0)
    parser.add_argument('--cache-parallel',type=int,default=8,
                        help='Maximum concurrent official Mathlib cache transfers')
    parser.add_argument('--plan-only',action='store_true',help='Read and validate existing inputs only; does not create a PASS receipt')
    args=parser.parse_args(argv)
    require(1<=args.jobs<=8 and args.timeout>0 and args.aggregate_rss_mb>0 and args.min_free_gb>=0,
            'Invalid resource bounds')
    require(1<=args.cache_parallel<=64,
            'Cache concurrency must be an integer in [1,64]')
    args.work_dir=args.work_dir.resolve();args.trusted_packages=args.trusted_packages.resolve()
    native=args.native_source.resolve() if args.native_source else args.work_dir/'native-source'
    integration=args.work_dir/'integration'
    for forbidden in [native,integration,*([args.external_project.resolve()] if args.external_project else [])]:
        require(not args.trusted_packages.is_relative_to(forbidden), 'Trusted packages must be outside native/external project roots')
    manifest=json.loads((BUNDLE/'lake-manifest.json').read_text())
    require(next(p['rev'] for p in manifest['packages'] if p['name']=='mathlib')==MATHLIB,'Bundle Mathlib pin mismatch')
    if args.plan_only:
        require(args.native_source and args.toolchain_bin,'Plan-only needs existing native source and toolchain')
        graph,roots,_=verify_native(native);runtime=verify_runtime(args.toolchain_bin.resolve())
        packages=verify_package_sources(args.trusted_packages,manifest)
        objects=verify_reference_objects(args.trusted_packages)
        print(json.dumps({'status':'PLAN_VALIDATED_NOT_BUILT','native_module_count':len(graph),
                          'mathlib_cache_roots':len(roots),'runtime':runtime,'packages':packages,
                          'reference_objects':objects,'closure_claim':'NOT_ESTABLISHED'},indent=2))
        return 0
    require(not args.work_dir.exists(),'Refusing existing work directory (fresh native object requirement)')
    args.work_dir.mkdir(parents=True)
    runner=Runner(args,args.work_dir)
    receipt={'schema':1,'scope':'Fresh common-pin native receiver closure; conditional/equivalence results only, no closed C1 supplier',
             'status':'RUNNING','started_utc':utc(),'native_head':NATIVE_HEAD,'native_tree':NATIVE_TREE,
             'common_mathlib_rev':MATHLIB,'command':[sys.executable,*sys.argv],
             'c1_closed':False,'rh_closed':False,'modules':[],
             'resource_policy':{'native_processes':args.jobs,'lean_threads_per_process':1,
               'lean_allocation_cap_mb_per_process':args.lean_memory_mb,
               'hard_address_space_gb_per_process':args.process_address_space_gb,
               'sampled_aggregate_rss_cap_mb':args.aggregate_rss_mb,'rss_poll_seconds':1,
               'timeout_seconds':args.timeout,'minimum_free_disk_gb':args.min_free_gb,
               'aggregate_limit_note':'RSS watchdog, not a cgroup hard-memory cap; process virtual-address cap is hard'}}
    receipt_path=integration/'NATIVE_COMMON_PIN_BUILD.json'
    try:
        rt=args.toolchain_bin.resolve() if args.toolchain_bin else install_runtime(runner,args.work_dir)
        receipt.update(verify_runtime(rt))
        if not args.native_source:
            fetch_git(runner,native,'https://github.com/HMarcusWH/zeta-23-lean.git',NATIVE_HEAD,True)
        graph,cache_roots,frozen=verify_native(native)
        native_pin_hashes={p:digest(native/p) for p in ['lean-toolchain','lake-manifest.json']}
        integration.mkdir()
        (integration/'lean-toolchain').write_text(TOOLCHAIN+'\n')
        shutil.copyfile(BUNDLE/'lake-manifest.json',integration/'lake-manifest.json')
        src_dir=json.dumps(str(native))
        (integration/'lakefile.toml').write_text('name = "opica_step4_integration"\nversion = "0.1.0"\nmoreLeanArgs = ["-j1"]\n[leanOptions]\npp.unicode.fun = true\nrelaxedAutoImplicit = false\nmaxHeartbeats = 800000\n[[require]]\nname = "mathlib"\ngit = "https://github.com/leanprover-community/mathlib4"\nrev = "'+MATHLIB+'"\n[[lean_lib]]\nname = "Zeta23"\nsrcDir = '+src_dir+'\n[[lean_lib]]\nname = "OPICAStep4"\n')
        (integration/'.lake').mkdir()
        (integration/'.lake/packages').symlink_to(args.trusted_packages,target_is_directory=True)
        args.trusted_packages.mkdir(parents=True,exist_ok=True)
        for package in manifest['packages']:
            target=args.trusted_packages/package['name']
            if not target.exists(): fetch_git(runner,target,package['url'],package['rev'])
        receipt['packages']=verify_package_sources(args.trusted_packages,manifest)
        env=lake_env(rt,integration,args.jobs)
        env['MATHLIB_CACHE_DIR']=str(args.work_dir/'mathlib-download-cache')
        root_paths=[Path(x).resolve() for x in env['LEAN_PATH'].split(os.pathsep) if x]
        allowed=[integration/'.lake/build/lib/lean',rt.parent/'lib/lean']
        allowed.extend(args.trusted_packages/p['name']/'.lake/build/lib/lean' for p in manifest['packages'])
        require(set(root_paths)<={p.resolve() for p in allowed},'Unexpected import root in native-only Lake environment')
        if args.external_project:
            require(all(not p.is_relative_to(args.external_project.resolve()) for p in root_paths),
                    'Canonical environment resolves into external proof project')
        try: reference=verify_reference_objects(args.trusted_packages)
        except Failure:
            print('Fetching official pinned Mathlib dependency cache',flush=True)
            # Bound ordinary official Mathlib-cache transport. HTTP 429 is not
            # retried, masked or changed into success. This wrapper changes
            # concurrency only, never repository source or cache verification.
            # curl --rate is ineffective with --parallel; no start-rate cap is claimed.
            real_curl=shutil.which('curl',path=env['PATH'])
            require(real_curl is not None,'curl is required for the official cache')
            wrappers=args.work_dir/'cache-transport-bin';wrappers.mkdir()
            curl_wrapper=wrappers/'curl'
            curl_wrapper.write_text('#!'+sys.executable+'\nimport os,sys\nargs=sys.argv[1:]\n'
                'if "--parallel" in args: args += '+repr(['--parallel-max',str(args.cache_parallel),
                    '--retry','0'])+'\n'
                'os.execv('+repr(real_curl)+',['+repr(real_curl)+',*args])\n')
            curl_wrapper.chmod(0o755)
            env['PATH']=str(wrappers)+os.pathsep+env['PATH']
            receipt['cache_transport']={'maximum_parallel':args.cache_parallel,
                                        'request_start_rate_limit':'NOT_ENFORCED_NOT_CLAIMED',
                                        'automatic_retries':0,'wrapper_sha256':digest(curl_wrapper)}
            # The external endpoint and frozen combined gate also require the
            # Mathlib root. Fetch the official dependency cache once, shared by
            # both projects; native source compilation is still only 572 modules.
            runner.run('official_mathlib_cache',[rt/'lake','exe','cache',
                        '--repo=leanprover-community/mathlib4','--cache-from=master','get','Mathlib'],integration,env)
            reference=verify_reference_objects(args.trusted_packages)
        receipt['trusted_reference_objects']=reference
        (integration/'OPICAStep4').mkdir()
        authored={}
        for module in AUDIT_MODULES:
            source=BUNDLE/module_path(module)
            text=strip_comments(source.read_text())
            require(not re.search(r'\b(?:sorry|sorryAx|admit|axiom)\b',text),
                    'Placeholder or project axiom in authored module')
            require(not re.search(r'(?m)^\s*example\b',text),'Anonymous audit examples are forbidden')
            destination=integration/module_path(module)
            shutil.copyfile(source,destination)
            authored[module]=digest(source)
        native_lib=integration/'.lake/build/lib/lean'
        require(all(not (native_lib/module_path(n,'.olean')).exists() for n in graph),
                'Preexisting native object before fresh build')
        receipt['modules']=build_native(runner,rt,integration,env,native,graph,frozen)
        receipt['audit_modules']=[compile_one(runner,rt,integration,env,integration,m,h,True)
                                  for m,h in authored.items()]
        audit_source=integration/'OPICAStep4/NativeBootstrapAudit.lean'
        lines=['import '+m for m in AUDIT_MODULES]
        lines+=['set_option pp.fullNames true','set_option pp.universes false','set_option pp.maxSteps 100000']
        for name in AUDIT_NAMES:
            lines+=['#eval IO.println "NATIVE_TYPE_BEGIN '+name+'"','#check @'+name,
                    '#eval IO.println "NATIVE_TYPE_END '+name+'"','#print axioms '+name]
        audit_source.write_text('\n'.join(lines)+'\n')
        audit=compile_one(runner,rt,integration,env,integration,'OPICAStep4.NativeBootstrapAudit',digest(audit_source),True)
        receipt['type_axiom_audit']=parse_audits(Path(audit['process']['log']).read_text())
        receipt['audit_consumer']=audit
        receipt['kernel_replays']=[runner.run('replay_'+m.replace('.','_'),[rt/'leanchecker','--verbose',m],integration,env,True)
                                   for m in AUDIT_MODULES]
        verify_native(native)
        require({p:digest(native/p) for p in native_pin_hashes}==native_pin_hashes,'Native pin changed during bootstrap')
        verify_package_sources(args.trusted_packages,manifest)
        verify_reference_objects(args.trusted_packages)
        for row in receipt['modules']:
            require(digest(Path(row['source_path']))==row['source_sha256'],'Native source changed after build')
            require(digest(Path(row['object_path']))==row['object_sha256'],'Native object changed after build')
            for artifact in row['sidecars'].values():
                require(digest(Path(artifact['path']))==artifact['sha256'],'Native sidecar changed after build')
        receipt.update(status='PASS',exit_code=0,source_unchanged=True,
                       source_placeholder_and_project_axiom_scan='PASS_572_NATIVE_AND_3_AUTHORED_MODULES',
                       full_fresh_import_replay='NOT_RUN_NOT_CLAIMED')
    except BaseException as exc:
        receipt.update(status='INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'FAIL',exit_code=1,error=str(exc))
        runner.abort.set();runner.kill_all()
        raise
    finally:
        runner.abort.set();runner.monitor.join(timeout=2)
        receipt.update(completed_utc=utc(),elapsed_seconds=time.monotonic()-runner.started,
                       max_sampled_process_group_rss_bytes=runner.max_total_rss,
                       processes=sorted(runner.records,key=lambda x:x['started_utc']))
        write_json(receipt_path,receipt)
        print(json.dumps({'status':receipt['status'],'receipt':str(receipt_path),
                          'native_modules':len(receipt['modules']),'c1_closed':False,'rh_closed':False}),flush=True)
    return 0


if __name__=='__main__':
    try: sys.exit(main())
    except (Failure,OSError,subprocess.SubprocessError) as exc:
        print('BOOTSTRAP FAILED: '+str(exc),file=sys.stderr);sys.exit(1)
