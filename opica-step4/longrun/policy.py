"""Fixed source/host policy for a nonaccepting long-run OPICA execution adapter.

This module controls execution resources only. It cannot authorize theorem claims.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROFILE_PATH = HERE / "PROFILE.json"
EXPECTED_REPO = "HMarcusWH/riemann-hypothesis"
EXPECTED_PROFILE = "OPICA_LONGRUN_20H_DIO64K_V1"
EXPECTED_BASE = "51a2aab2566ed9736f6c4fcddbcfeea74d90e09d"
EXPECTED_MATHLIB = "0df444a360eaa60ab8c11dca51a86af692955474"
EXPECTED_NATIVE = "7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9"
EXPECTED_SUPPLIER = "24df20b62d9976ccd20da819bc20b16f808f0fdd"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
HASH64 = re.compile(r"[a-f0-9]{64}\Z")
TIMES = {
    "canonical_compile": 1800,
    "guarded_kernel_import": 14400,
    "fresh_closed_kernel_construction": 14400,
    "fresh_replay": 7200,
    "export": 7200,
    "replay": 3600,
    "comparison": 7200,
    "independent": 9000,
    "checker_bootstrap": 2400,
}

class PolicyError(RuntimeError):
    pass


def require(condition: bool, description: str) -> None:
    if not condition:
        raise PolicyError(description)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _no_duplicates(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise PolicyError("Duplicate JSON key: " + key)
        output[key] = value
    return output


def read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "Missing or linked JSON: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
    require(type(data) is dict, "Required JSON object: " + str(path))
    return data


def git(*args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(REPO), *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
    )
    return process.stdout.strip()


def profile() -> dict:
    p = read_json(PROFILE_PATH)
    require(p.get("schema") == "OPICA_LONGRUN_EXECUTION_PROFILE_V1", "Profile schema changed")
    require(p.get("id") == EXPECTED_PROFILE, "Profile identity changed")
    require(p.get("source_base_head") == EXPECTED_BASE, "Frozen source base changed")
    require(p.get("native_head") == EXPECTED_NATIVE, "Original native source pin changed")
    require(p.get("supplier_src_tree") == EXPECTED_SUPPLIER, "Supplier mathematical source tree changed")
    require(p.get("mathlib") == EXPECTED_MATHLIB and p.get("lean") == "4.33.1", "Compiler/Mathlib pin changed")
    require(p.get("limits_seconds") == TIMES, "Execution limits changed without versioned review")
    require(p.get("max_sampled_rss_plus_swap_mib") == 50000, "Memory cap changed")
    require(p.get("job_timeout_minutes") == 1200, "Job cap changed")
    contract = p.get("proof_contract", {})
    require([contract.get(k) for k in ("modular_stages", "independent_stages",
                                      "selected_roots", "supplier_roots", "native_roots", "closed_roots")]
            == [30, 7, 50, 38, 9, 3], "Proof contract cardinality changed")
    require(set(contract.get("allowed_axioms", []))
            == {"propext", "Classical.choice", "Quot.sound"}, "Axiom allowance changed")
    require(p.get("proof_acceptance_from_profile") is False, "Profile claims proof authority")
    return p


def source_identity(expected_head: str, *, check_worktree: bool = False) -> dict:
    require(SHA40.fullmatch(expected_head) is not None, "A full exact 40-hex commit is mandatory")
    actual = git("rev-parse", "HEAD")
    require(actual == expected_head, "Actual checked-out commit is not the explicitly selected commit")
    require(not check_worktree or git("status", "--porcelain", "--untracked-files=no") == "",
            "Tracked original source changed")
    git("merge-base", "--is-ancestor", EXPECTED_BASE, expected_head)
    tree = git("rev-parse", "HEAD^{tree}")
    require(SHA40.fullmatch(tree) is not None, "Invalid Git tree")
    # The profile and all original file bytes must correspond to the exact Git tree.
    for path in [PROFILE_PATH, REPO / "opica-step4/SOURCE_MANIFEST.json",
                 REPO / "opica-step4/modular/verify_modular.py",
                 REPO / "opica-step4/independent/verify_independent.py"]:
        require(not path.is_symlink() and path.is_file(), "Missing source subject: " + str(path))
        rel = path.relative_to(REPO).as_posix()
        expected = git("rev-parse", "HEAD:" + rel)
        current = git("hash-object", str(path))
        require(expected == current, "Source byte drift: " + rel)
    scope_path = HERE / "SOURCE_MANIFEST.json"
    scope = read_json(scope_path)
    require(scope.get("schema") == "OPICA_LONGRUN_ADDITIVE_SOURCE_SCOPE_V1"
            and scope.get("original_parent") == EXPECTED_BASE,
            "Wrong additive source scope identity")
    listed = scope.get("files")
    require(type(listed) is list and listed == sorted(set(listed)), "Unsorted/duplicated source inventory")
    changed = [row.split("\t") for row in
               git("diff", "--name-status", EXPECTED_BASE, "HEAD").splitlines()]
    require(all(len(row) == 2 and row[0] == "A" for row in changed),
            "Original tracked source was edited or removed")
    require(sorted(row[1] for row in changed) == listed,
            "Unexpected or missing additive source file")
    for relative in listed:
        path = REPO / relative
        require(path.is_file() and not path.is_symlink(),
                "Additive source file is absent/linked: " + relative)
        require(git("rev-parse", "HEAD:" + relative) == git("hash-object", str(path)),
                "Additive checked source bytes differ: " + relative)
    parent_manifest = read_json(REPO / "opica-step4/SOURCE_MANIFEST.json")
    require(parent_manifest.get("supplier_source_tree") == EXPECTED_SUPPLIER,
            "Original supplier mathematical source claim changed")
    require(parent_manifest.get("native_head") == EXPECTED_NATIVE, "Original native checkpoint changed")
    return {
        "head": actual, "tree": tree,
        "profile_sha256": sha256(PROFILE_PATH),
        "original_source_manifest_sha256": sha256(REPO / "opica-step4/SOURCE_MANIFEST.json"),
        "original_modular_runner_sha256": sha256(REPO / "opica-step4/modular/verify_modular.py"),
        "original_independent_runner_sha256": sha256(REPO / "opica-step4/independent/verify_independent.py"),
    }


def _memtotal_mib() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) // 1024
    raise PolicyError("Host memory total missing")


def host_identity(p: dict, work_parent: Path, environ=None, *, require_runner=True) -> dict:
    env = os.environ if environ is None else environ
    h = p["host"]
    if require_runner:
        require(env.get("GITHUB_ACTIONS") == "true", "Host run must originate from GitHub Actions")
        require(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "Long proof requires manual dispatch")
        require(env.get("GITHUB_REPOSITORY") == EXPECTED_REPO, "Wrong GitHub repository")
        require(env.get("RUNNER_ENVIRONMENT") == h["runner_environment"], "Unreviewed runner class")
        require(env.get("RUNNER_OS") == h["runner_os"], "Wrong operating system")
        require(env.get("RUNNER_NAME", "").startswith(h["runner_name_prefix"]), "Wrong runner name")
        require(env.get("OPICA_LONGRUN_SELECTION") == EXPECTED_PROFILE, "Long-run execution not explicitly selected")
        marker = Path(h["marker"])
        require(marker.exists() and marker.is_file() and not marker.is_symlink(), "Missing root-owned ephemeral runner marker")
        metadata = marker.stat()
        require(metadata.st_uid == 0 and metadata.st_mode & 0o022 == 0, "Runner marker must be root-owned and not writable by others")
        marker_json = read_json(marker)
        require(marker_json.get("schema") == "OPICA_EPHEMERAL_RUNNER_V1"
                and marker_json.get("ephemeral") is True
                and marker_json.get("runner_name") == env.get("RUNNER_NAME")
                and marker_json.get("profile_id") == EXPECTED_PROFILE,
                "Runner marker identity differs")
    else:
        marker_json = {"status": "TEST_ONLY_NO_RUNNER_ASSERTION"}
    require(len(os.sched_getaffinity(0)) >= h["min_cpus"], "Insufficient bound CPUs")
    physical_mib = _memtotal_mib()
    require(physical_mib >= h["min_memtotal_mib"], "Insufficient physical RAM")
    root = work_parent.resolve(strict=True)
    require(root.is_dir() and not work_parent.is_symlink(), "Work parent is not a regular directory")
    disk = shutil.disk_usage(root)
    free_gib = disk.free // (1024 ** 3)
    require(free_gib >= h["min_free_disk_gib"], "Insufficient free local disk")
    st = os.statvfs(root)
    require(st.f_favail >= h["min_free_inodes"], "Insufficient free inode capacity")
    fs = subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(root)],
                        check=True, capture_output=True, text=True, timeout=20).stdout.strip()
    require(fs in h["allowed_work_filesystems"], "Unreviewed work filesystem: " + fs)
    return {
        "marker": marker_json, "physical_memtotal_mib": physical_mib,
        "cpus_available": len(os.sched_getaffinity(0)),
        "free_disk_gib": free_gib, "free_inodes": st.f_favail,
        "filesystem": fs, "work_parent": str(root),
        "scope": "Operational resource eligibility only; no proof acceptance",
    }
