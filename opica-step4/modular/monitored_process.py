#!/usr/bin/env python3
"""Bounded Linux process-group execution with explicit, sampled resource evidence.

An execution PASS is not a proof-validation claim. RSS+swap enforcement is a
user-space watchdog: it kills on the first observed excess and does not claim a
kernel/cgroup hard limit between samples. In particular, RLIMIT_AS is not used.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

MAX_MEMORY_MIB = 50_000
POLL_SECONDS = 0.25
RECONCILE_SECONDS = 0.25
RECONCILE_RETRY_SECONDS = 0.01
RETIRED_STATES = frozenset(('Z', 'X', 'x'))
PROGRESS_SECONDS = 30.0
CLEANUP_GRACE_SECONDS = 1.0
TELEMETRY_LIMIT = 64 << 20
STDOUT_ARTIFACT_LIMIT = 128 << 30
IO_COUNTERS = ('rchar', 'wchar', 'syscr', 'syscw', 'read_bytes', 'write_bytes',
               'cancelled_write_bytes')
MEM_KEYS = ('MemTotal', 'MemFree', 'MemAvailable', 'SwapTotal', 'SwapFree',
            'SwapCached', 'Dirty', 'Writeback', 'AnonPages', 'Mapped', 'Shmem',
            'PageTables', 'Slab', 'KReclaimable')
VM_KEYS = ('pgfault', 'pgmajfault', 'pswpin', 'pswpout', 'oom_kill')
DIAGNOSTIC = re.compile(
    r'(?im)(?:^|[\r\n])(?:[^\r\n]*?:\d+:\d+:\s*)?(?:error|warning|panic)\b'
    r'|uncaught exception|excessive memory consumption|stack overflow'
    r'|invalid[- ]proof|kernel exception'
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json_write(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def _stat(pid: int) -> dict:
    raw = Path(f'/proc/{pid}/stat').read_text()
    end = raw.rfind(')')
    if end < 0:
        raise RuntimeError(f'malformed /proc stat for PID {pid}')
    fields = raw[end + 2:].split()
    return {
        'pid': pid, 'comm': raw[raw.find('(') + 1:end], 'state': fields[0],
        'ppid': int(fields[1]), 'pgrp': int(fields[2]),
        'minor_faults': int(fields[7]), 'major_faults': int(fields[9]),
        'user_ticks': int(fields[11]), 'system_ticks': int(fields[12]),
        'threads': int(fields[17]), 'start_ticks': int(fields[19]),
    }


def _proc_members(pgid: int) -> list[dict]:
    members = []
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            row = _stat(int(path.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            # Other users' processes may be hidden; group members are our children.
            continue
        if row['pgrp'] == pgid:
            members.append(row)
    return sorted(members, key=lambda row: row['pid'])


def _identity(row: dict) -> dict:
    return {key: row[key] for key in ('pid', 'start_ticks', 'pgrp')}


def _memory_status(pid: int) -> dict:
    status = {}
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in ('VmRSS', 'VmSwap'):
            parts = value.split()
            if (key in status or len(parts) != 2 or parts[1] != 'kB'
                    or not parts[0].isdecimal()):
                raise ValueError(f'malformed mandatory resource counter {key} for PID {pid}')
            status[key] = int(parts[0]) * 1024
    return status


class ResourceObservationError(RuntimeError):
    def __init__(self, message: str, observation: dict):
        self.resource_observation = observation
        super().__init__(message)


def _member_memory(original: dict, reconcile_deadline: float,
                   execution_deadline: float | None) -> tuple[dict, dict | None, dict | None]:
    """Reconcile incomplete counters only; never invent a live memory value."""
    started = time.monotonic()
    identity = _identity(original)
    current = original
    attempts = 0
    missing = []
    initial_error = None
    last_error = None
    try:
        status = _memory_status(original['pid'])
    except (FileNotFoundError, ProcessLookupError) as exc:
        status = {}
        initial_error = type(exc).__name__
    if set(status) == {'VmRSS', 'VmSwap'}:
        return original, status, None
    observed = dict(status)
    missing = sorted({'VmRSS', 'VmSwap'} - set(status))
    initial_missing = list(missing)

    def evidence(outcome):
        return {'identity': identity, 'initial_state': original['state'],
                'initial_missing_counters': initial_missing, 'initial_error_type': initial_error,
                'last_identity': _identity(current), 'last_state': current['state'],
                'last_missing_counters': list(missing), 'last_error_type': last_error,
                'observed_counter_maxima_bytes': dict(observed),
                'counter_maxima_need_not_be_simultaneous': True,
                'retries': attempts, 'elapsed_seconds': round(time.monotonic() - started, 6),
                'reconciliation_limit_seconds': RECONCILE_SECONDS, 'outcome': outcome,
                'shared_budget_remaining_at_entry_seconds': round(max(0, reconcile_deadline - started), 6),
                'missing_values_are_not_measured_zero': True}

    def budget_check():
        now = time.monotonic()
        if execution_deadline is not None and now >= execution_deadline:
            error = _Stop('INCOMPLETE', 'TIMEOUT', 'execution deadline reached during resource reconciliation')
            error.resource_observation = evidence('EXECUTION_DEADLINE')
            raise error
        if now >= reconcile_deadline:
            raise ResourceObservationError(
                f'incomplete resource counters remain unresolved for PID {original["pid"]}',
                evidence('RECONCILIATION_BUDGET_EXHAUSTED'))

    def finish(outcome, values=None):
        budget_check()
        return current, values, evidence(outcome)

    def checked_stat():
        nonlocal current
        current = _stat(original['pid'])
        if _identity(current) != identity:
            raise ResourceObservationError(
                f'process identity or group changed during resource reconciliation for PID {original["pid"]}',
                evidence('IDENTITY_OR_GROUP_CHANGED'))
        return current

    while True:
        budget_check()
        attempts += 1
        try:
            checked_stat()
        except (FileNotFoundError, ProcessLookupError):
            return finish('CONFIRMED_DISAPPEARED')
        except ResourceObservationError:
            raise
        except (OSError, ValueError, RuntimeError, IndexError) as exc:
            last_error = type(exc).__name__
            raise ResourceObservationError(str(exc), evidence('IDENTITY_UNREADABLE')) from exc
        if current['state'] in RETIRED_STATES:
            return finish('CONFIRMED_RETIRED_STATE')
        try:
            status = _memory_status(original['pid'])
            last_error = None
        except (FileNotFoundError, ProcessLookupError) as exc:
            status = {}
            last_error = type(exc).__name__
        except (OSError, ValueError) as exc:
            last_error = type(exc).__name__
            raise ResourceObservationError(str(exc), evidence('LIVE_COUNTERS_UNREADABLE_OR_MALFORMED')) from exc
        for key, value in status.items():
            observed[key] = max(observed.get(key, value), value)
        missing = sorted({'VmRSS', 'VmSwap'} - set(status))
        if not missing:
            # A recovered row must not silently belong to a reused/escaped PID.
            # Retain valid bytes for the cap even if this final read finds exit.
            try:
                checked_stat()
            except (FileNotFoundError, ProcessLookupError):
                return finish('RECOVERED_COUNTERS_THEN_DISAPPEARED', status)
            except ResourceObservationError:
                raise
            except (OSError, ValueError, RuntimeError, IndexError) as exc:
                last_error = type(exc).__name__
                raise ResourceObservationError(str(exc), evidence('RECOVERED_IDENTITY_UNREADABLE')) from exc
            outcome = ('RECOVERED_COUNTERS_THEN_RETIRED' if current['state'] in RETIRED_STATES
                       else 'RECOVERED_LIVE_COUNTERS')
            return finish(outcome, status)
        budget_check()
        wait = min(RECONCILE_RETRY_SECONDS, reconcile_deadline - time.monotonic())
        if execution_deadline is not None:
            wait = min(wait, execution_deadline - time.monotonic())
        if wait > 0:
            time.sleep(wait)


def sample_process_group(pgid: int, *, deadline: float | None = None) -> dict:
    """Observe the group with one shared, deadline-bounded reconciliation budget."""
    reconcile_deadline = time.monotonic() + RECONCILE_SECONDS
    members, reconciliations = [], []
    for row in _proc_members(pgid):
        observation = None
        if row['state'] in RETIRED_STATES:
            status = None
            retired = True
        else:
            row, status, observation = _member_memory(row, reconcile_deadline, deadline)
            retired = status is None or row['state'] in RETIRED_STATES or (
                observation is not None and observation['outcome'] == 'RECOVERED_COUNTERS_THEN_DISAPPEARED')
        if observation is not None:
            reconciliations.append(observation)
        # Valid partial/high observations remain in the cap even after exit or
        # recovery. Absent components stay null; none are fabricated as zero.
        measured = dict(status or {})
        for key, value in (observation or {}).get('observed_counter_maxima_bytes', {}).items():
            measured[key] = max(measured.get(key, value), value)
        coverage = ('MEASURED' if status is not None else
                    'NOT_LIVE_PARTIAL_MEASUREMENT' if measured else 'NOT_LIVE_NO_MEASUREMENT')
        row.update(memory_coverage=coverage,
                   confirmed_not_live=retired,
                   rss_bytes=measured.get('VmRSS'), swap_bytes=measured.get('VmSwap'))
        if retired:
            row.update(io={}, io_coverage='NOT_LIVE')
            members.append(row)
            continue
        # RSS and swap above remain mandatory. I/O is optional diagnostic data:
        # an unavailable I/O counter must not erase a measured member or weaken
        # the memory watchdog. Missing values are not reported as measured zero.
        io = {}
        try:
            for line in Path(f"/proc/{row['pid']}/io").read_text().splitlines():
                key, _, value = line.partition(':')
                if key in IO_COUNTERS:
                    io[key] = int(value.strip())
            if set(io) != set(IO_COUNTERS) or any(value < 0 for value in io.values()):
                raise ValueError('incomplete or invalid optional process I/O counters')
            row['io_coverage'] = 'AVAILABLE'
        except (OSError, ValueError) as exc:
            io = {}
            row.update(io_coverage='UNAVAILABLE', io_error_type=type(exc).__name__)
        row.update(io=io)
        members.append(row)
    totals = {
        'rss_bytes': sum(row['rss_bytes'] for row in members if row['rss_bytes'] is not None),
        'swap_bytes': sum(row['swap_bytes'] for row in members if row['swap_bytes'] is not None),
        'user_ticks': sum(row['user_ticks'] for row in members),
        'system_ticks': sum(row['system_ticks'] for row in members),
        'minor_faults': sum(row['minor_faults'] for row in members),
        'major_faults': sum(row['major_faults'] for row in members),
        'io': {key: sum(row['io'].get(key, 0) for row in members) for key in IO_COUNTERS},
    }
    totals['rss_plus_swap_bytes'] = totals['rss_bytes'] + totals['swap_bytes']
    return {'pgid': pgid, 'members': members,
            'live_pids': [row['pid'] for row in members if not row['confirmed_not_live']],
            'totals': totals,
            'memory_coverage': {
                'status': 'COMPLETE_FOR_OBSERVED_LIVE_IDENTITIES',
                'measured_member_samples': sum(row['memory_coverage'] == 'MEASURED' for row in members),
                'not_live_without_measurement': sum(row['memory_coverage'] == 'NOT_LIVE_NO_MEASUREMENT' for row in members),
                'not_live_partial_measurement': sum(row['memory_coverage'] == 'NOT_LIVE_PARTIAL_MEASUREMENT' for row in members),
                'reconciliations': reconciliations,
                'totals_include_all_valid_observed_counters': True,
            },
            'io_coverage': {
                'status': 'INCOMPLETE' if any(row['io_coverage'] == 'UNAVAILABLE' for row in members)
                          else 'AVAILABLE_FOR_OBSERVED_LIVE_MEMBERS',
                'available_member_samples': sum(row['io_coverage'] == 'AVAILABLE' for row in members),
                'unavailable_member_samples': sum(row['io_coverage'] == 'UNAVAILABLE' for row in members),
                'unavailable_members': [{'pid': row['pid'], 'error_type': row['io_error_type']}
                                        for row in members if row['io_coverage'] == 'UNAVAILABLE'],
                'aggregate_includes_only_available_counters': True,
            }}


def sample_host() -> dict:
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in MEM_KEYS:
            memory[key] = int(value.split()[0]) * 1024
    if not {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'} <= set(memory):
        raise RuntimeError('required host memory counters are unavailable')
    vm = {}
    for line in Path('/proc/vmstat').read_text().splitlines():
        key, value = line.split()
        if key in VM_KEYS:
            vm[key] = int(value)
    pressure = {}
    for kind in ('cpu', 'memory', 'io'):
        path = Path('/proc/pressure') / kind
        try:
            pressure[kind] = {'available': True, 'raw': path.read_text().strip()}
        except OSError as exc:
            pressure[kind] = {'available': False, 'error_type': type(exc).__name__}
    return {'memory_bytes': memory, 'vm_counters': vm, 'pressure': pressure}


class CounterHistory:
    """Accumulate observed per-PID deltas, including the last seen exited members.

    CPU/fault totals are lower bounds when a child lives entirely between samples
    or does work after its final observation. Own CPU/fault counters avoid adding
    cutime/cstime or cminflt/cmajflt. Linux process I/O can include waited-for
    children, so the aggregate I/O indicator may double-count that transfer.
    PID plus start time distinguishes PID reuse.
    """
    def __init__(self):
        self.previous = {}
        self.total = {key: 0 for key in ('user_ticks', 'system_ticks', 'minor_faults',
                                       'major_faults', *IO_COUNTERS)}
        self.io_available_samples = 0
        self.io_unavailable_samples = 0
        self.io_errors_first = []
        self.memory_measured_samples = 0
        self.memory_retired_samples = 0
        self.memory_retired_partial_samples = 0
        self.memory_reconciliation_count = 0
        self.memory_reconciliations_first = []

    def observe(self, snapshot: dict) -> None:
        memory = snapshot.get('memory_coverage', {})
        self.memory_measured_samples += memory.get('measured_member_samples', 0)
        self.memory_retired_samples += memory.get('not_live_without_measurement', 0)
        self.memory_retired_partial_samples += memory.get('not_live_partial_measurement', 0)
        reconciliations = memory.get('reconciliations', [])
        self.memory_reconciliation_count += len(reconciliations)
        self.memory_reconciliations_first.extend(reconciliations[:max(0, 16 - len(self.memory_reconciliations_first))])
        coverage = snapshot['io_coverage']
        self.io_available_samples += coverage['available_member_samples']
        self.io_unavailable_samples += coverage['unavailable_member_samples']
        for item in coverage['unavailable_members']:
            if item not in self.io_errors_first and len(self.io_errors_first) < 16:
                self.io_errors_first.append(item)
        for member in snapshot['members']:
            identity = (member['pid'], member['start_ticks'])
            current = {key: member[key] for key in
                       ('user_ticks', 'system_ticks', 'minor_faults', 'major_faults')}
            current.update(member['io'])
            previous = self.previous.get(identity, {})
            for key, value in current.items():
                self.total[key] += max(0, value - previous.get(key, 0))
            # Preserve each last available I/O value across an unavailable
            # sample, preventing its later return from being double-counted.
            self.previous[identity] = previous | {
                key: max(value, previous.get(key, 0)) for key, value in current.items()
            }

    def summary(self) -> dict:
        tick_rate = os.sysconf('SC_CLK_TCK')
        return {
            'observed_process_identities': len(self.previous),
            'user_seconds_observed': self.total['user_ticks'] / tick_rate,
            'system_seconds_observed': self.total['system_ticks'] / tick_rate,
            'minor_faults_observed': self.total['minor_faults'],
            'major_faults_observed': self.total['major_faults'],
            'io_observed': {key: self.total[key] for key in IO_COUNTERS},
            'cpu_and_fault_observations_are_lower_bounds': True,
            'io_observed_is_sampled_aggregate_not_exact_total': True,
            'io_aggregation_caveat': 'Linux process I/O can include waited-for children; parent+child aggregation may double-count transferred counters',
            'mandatory_memory_observations': {
                'measured_member_samples': self.memory_measured_samples,
                'confirmed_not_live_without_measurement': self.memory_retired_samples,
                'confirmed_not_live_with_partial_measurement': self.memory_retired_partial_samples,
                'reconciliation_count': self.memory_reconciliation_count,
                'reconciliations_first_at_most_16': self.memory_reconciliations_first,
                'missing_live_counters_never_count_as_measured_zero': True,
            },
            'optional_io_telemetry': {
                'coverage_status': 'INCOMPLETE' if self.io_unavailable_samples
                                   else 'AVAILABLE_FOR_OBSERVED_LIVE_MEMBERS',
                'available_member_samples': self.io_available_samples,
                'unavailable_member_samples': self.io_unavailable_samples,
                'errors_first_at_most_16': self.io_errors_first,
                'io_unavailability_does_not_relax_memory_or_exit_gates': True,
            },
        }


def cleanup_group(process: subprocess.Popen, grace: float = CLEANUP_GRACE_SECONDS) -> dict:
    """Kill the group even after its original leader has exited."""
    result = {'pgid': process.pid, 'signals_sent': [], 'live_pids_after': []}
    for sig, wait_seconds in ((signal.SIGTERM, grace), (signal.SIGKILL, 3.0)):
        live = [row['pid'] for row in _proc_members(process.pid) if row['state'] not in RETIRED_STATES]
        if not live:
            break
        try:
            os.killpg(process.pid, sig)
            result['signals_sent'].append(sig.name)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            process.poll()  # Reap our own leader promptly; orphan zombies cannot write.
            live = [row['pid'] for row in _proc_members(process.pid) if row['state'] not in RETIRED_STATES]
            if not live:
                break
            time.sleep(0.05)
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    result['live_pids_after'] = [row['pid'] for row in _proc_members(process.pid)
                                if row['state'] not in RETIRED_STATES]
    result['status'] = 'PASS' if not result['live_pids_after'] else 'FAIL'
    return result


class _Stop(Exception):
    def __init__(self, status: str, kind: str, message: str):
        self.status, self.kind, self.message = status, kind, message
        super().__init__(message)


class _SignalStop(Exception):
    def __init__(self, signum: int):
        self.signum = signum


def _signal_stop(signum, _frame):
    raise _SignalStop(signum)


def run(name, argv, *, cwd, env, output, timeout, memory_mib=MAX_MEMORY_MIB,
        expected=0, log_limit=64 << 20, stdout_path=None):
    """Return ``(row, log_text)`` for every execution outcome; preserve evidence.

    PASS requires exit 0, no diagnostic, bounded observed resources/output, EOF,
    and no surviving same-group descendants. INCOMPLETE covers time/resource
    limits and interruption. FAIL covers invalid execution/diagnostics/cleanup.
    Argument errors or reused evidence paths raise ValueError before execution.
    stdout_path, when given, receives exact stdout; stderr alone is diagnostic.
    """
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', str(name)):
        raise ValueError('name must be one safe filename component')
    if not argv or not all(isinstance(arg, (str, os.PathLike)) for arg in argv):
        raise ValueError('argv must be a nonempty sequence of path/string arguments')
    if expected != 0:
        raise ValueError('this gate helper requires expected=0')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    if not isinstance(memory_mib, int) or not 0 < memory_mib <= MAX_MEMORY_MIB:
        raise ValueError('memory_mib must be in 1..50000')
    if not isinstance(log_limit, int) or not 0 < log_limit <= 256 << 20:
        raise ValueError('log_limit must be in 1..256MiB')
    cwd, output = Path(cwd).resolve(), Path(output).resolve()
    if not cwd.is_dir() or not Path('/proc/self/stat').is_file():
        raise ValueError('an existing cwd and Linux /proc are required')
    output.mkdir(parents=True, exist_ok=True)
    log = output / (name + '.log')
    receipt = output / (name + '.process.json')
    telemetry = output / (name + '.telemetry.jsonl')
    artifact_input = Path(stdout_path).absolute() if stdout_path is not None else None
    if artifact_input and (artifact_input.exists() or artifact_input.is_symlink()):
        raise ValueError('stdout artifact path must be fresh')
    artifact = artifact_input.resolve() if artifact_input else None
    paths = [log, receipt, telemetry, receipt.with_name(receipt.name + '.tmp')] + ([artifact] if artifact else [])
    if len(set(paths)) != len(paths) or any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError('all log, receipt, telemetry and output-artifact paths must be distinct and fresh')
    if artifact:
        artifact.parent.mkdir(parents=True, exist_ok=True)
    argv = [os.fspath(arg) for arg in argv]
    env = dict(os.environ) if env is None else dict(env)
    row = {
        'schema': 'MONITORED_PROCESS_GROUP_RESOURCE_LIFECYCLE_V3', 'name': str(name), 'status': 'RUNNING',
        'command': argv, 'cwd': str(cwd), 'started_utc': utc_now(),
        'log': str(log), 'telemetry': str(telemetry), 'exit_code': None,
        'timeout_seconds': timeout, 'rss_plus_swap_limit_bytes': memory_mib * 1024**2,
        'log_limit_bytes': log_limit, 'resource_poll_seconds': POLL_SECONDS,
        'progress_seconds': PROGRESS_SECONDS,
        'memory_enforcement': 'Sampled process-group RSS+swap; terminate on first observed excess; no kernel/cgroup hard cap claimed',
        'measurement_limits': 'VmRSS is asynchronously maintained; shared RSS may be counted per process; VmSwap excludes swapped shared memory; short-lived children and peaks between polls may be missed; trusted commands must not escape the process group',
        'optional_io_policy': 'Unavailable process I/O counters are explicitly recorded as incomplete diagnostic coverage; mandatory RSS/swap, exit, EOF, log, cleanup and evidence checks are unchanged',
        'memory_reconciliation_policy': 'Incomplete RSS/swap requires identity-stable complete counters or confirmed original-identity retirement; persistent live missing/unreadable/malformed counters and identity/group changes fail; no measured zero is invented',
        'memory_reconciliation_shared_seconds': RECONCILE_SECONDS,
        'memory_reconciliation_retry_seconds': RECONCILE_RETRY_SECONDS,
        'environment_resources': {key: env[key] for key in
                                  ('LEAN_NUM_THREADS', 'LEAN_ABORT_ON_PANIC') if key in env},
        'helper_sha256': sha256(Path(__file__).resolve()),
        'python_version': sys.version.split()[0], 'diagnostics': [],
        'proof_validity_established': False,
        'max_sampled_rss_bytes': 0, 'max_sampled_swap_bytes': 0,
        'max_sampled_rss_plus_swap_bytes': 0,
    }
    if artifact:
        row.update(stdout_artifact=str(artifact), stdout_artifact_limit_bytes=STDOUT_ARTIFACT_LIMIT)
    with receipt.open('x') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')

    started = time.monotonic()
    process = None
    history = CounterHistory()
    log_bytes = stdout_bytes = telemetry_bytes = 0
    artifact_hash = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    diagnostic_tail = ''
    selectors_open = selectors.DefaultSelector()
    log_stream = telemetry_stream = artifact_stream = None
    old_handlers = {}
    last_progress = -PROGRESS_SECONDS
    last_snapshot = None

    def telemetry_record(event: str, snapshot=None, observation=None) -> None:
        nonlocal telemetry_bytes, last_progress
        sample = {'event': event, 'utc': utc_now(),
                  'elapsed_seconds': round(time.monotonic() - started, 6),
                  'process_group': snapshot, 'observed_totals': history.summary(),
                  'host': sample_host(), 'log_bytes': log_bytes,
                  'stdout_artifact_bytes': stdout_bytes if artifact else None}
        if observation is not None:
            sample['resource_observation'] = observation
        encoded = json.dumps(sample, separators=(',', ':')).encode() + b'\n'
        if telemetry_bytes + len(encoded) > TELEMETRY_LIMIT:
            raise _Stop('INCOMPLETE', 'TELEMETRY_LIMIT', 'telemetry exceeded its fixed size limit')
        telemetry_stream.write(encoded)
        telemetry_stream.flush()
        telemetry_bytes += len(encoded)
        last_progress = time.monotonic() - started

    def retain_resource_observation(observation):
        row['resource_observation_failure'] = observation
        try:
            telemetry_record('resource_observation_failure', observation=observation)
        except Exception as exc:
            # A secondary evidence error must not skip cleanup/final receipts.
            row.setdefault('secondary_failures', []).append(
                'RESOURCE_OBSERVATION_TELEMETRY_' + type(exc).__name__)

    def accept_log(block: bytes) -> None:
        nonlocal log_bytes, diagnostic_tail
        available = max(0, log_limit - log_bytes)
        stored = block[:available]
        log_stream.write(stored)
        log_stream.flush()
        log_bytes += len(stored)
        if len(block) > available:
            raise _Stop('INCOMPLETE', 'LOG_LIMIT', 'diagnostic output exceeded its byte limit')
        text = diagnostic_tail + decoder.decode(block)
        match = DIAGNOSTIC.search(text)
        if match:
            row['diagnostics'].append(text[max(0, match.start() - 100):match.end() + 300])
            raise _Stop('FAIL', 'DIAGNOSTIC', 'error/warning/invalid-proof diagnostic in process output')
        diagnostic_tail = text[-2048:]

    try:
        log_stream = log.open('xb')
        telemetry_stream = telemetry.open('xb')
        if artifact:
            artifact_stream = artifact.open('xb')
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_handlers[sig] = signal.signal(sig, _signal_stop)
        telemetry_record('before_launch')
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE if artifact else subprocess.STDOUT,
                                   start_new_session=True)
        row['pid'] = row['pgid'] = process.pid
        for stream, kind in ((process.stdout, 'artifact' if artifact else 'log'),
                             (process.stderr, 'log')):
            if stream is not None:
                os.set_blocking(stream.fileno(), False)
                selectors_open.register(stream, selectors.EVENT_READ, kind)
        _json_write(receipt, row)
        while True:
            elapsed = time.monotonic() - started
            if elapsed > timeout:
                raise _Stop('INCOMPLETE', 'TIMEOUT', 'process exceeded its wall-time budget')
            first_snapshot = last_snapshot is None
            last_snapshot = sample_process_group(process.pid, deadline=started + timeout)
            history.observe(last_snapshot)
            for key in ('rss_bytes', 'swap_bytes', 'rss_plus_swap_bytes'):
                row['max_sampled_' + key] = max(row['max_sampled_' + key], last_snapshot['totals'][key])
            if last_snapshot['totals']['rss_plus_swap_bytes'] > row['rss_plus_swap_limit_bytes']:
                telemetry_record('memory_limit', last_snapshot)
                raise _Stop('INCOMPLETE', 'MEMORY_LIMIT', 'observed process-group RSS+swap exceeded its limit')
            if time.monotonic() - started > timeout:
                raise _Stop('INCOMPLETE', 'TIMEOUT', 'execution deadline reached during resource observation')
            if last_snapshot['memory_coverage']['reconciliations']:
                telemetry_record('memory_reconciliation', last_snapshot)
            if first_snapshot or elapsed - last_progress >= PROGRESS_SECONDS:
                telemetry_record('after_launch' if first_snapshot else 'progress', last_snapshot)
                print(f"{name}: {elapsed:.1f}s RSS={last_snapshot['totals']['rss_bytes'] / 1024**3:.2f} GiB "
                      f"swap={last_snapshot['totals']['swap_bytes'] / 1024**3:.2f} GiB", flush=True)
            code = process.poll()
            if code is not None and code != 0:
                raise _Stop('FAIL', 'NONZERO_EXIT', f'process exited with {code}')
            live_descendants = [pid for pid in last_snapshot['live_pids'] if pid != process.pid]
            if code is not None and live_descendants:
                raise _Stop('FAIL', 'ORPHANED_DESCENDANTS', 'leader exited while same-group descendants remained alive')
            if code is not None and not selectors_open.get_map():
                break
            for key, _ in selectors_open.select(timeout=min(POLL_SECONDS, max(0, timeout - elapsed))):
                for _ in range(16):  # Bound each drain to1MiB so resource polling cannot starve.
                    try:
                        block = os.read(key.fd, 64 << 10)
                    except BlockingIOError:
                        break
                    if not block:
                        selectors_open.unregister(key.fileobj)
                        break
                    if key.data == 'log':
                        accept_log(block)
                    else:
                        if stdout_bytes + len(block) > STDOUT_ARTIFACT_LIMIT:
                            raise _Stop('INCOMPLETE', 'STDOUT_LIMIT', 'stdout artifact exceeded its fixed size limit')
                        artifact_stream.write(block)
                        artifact_hash.update(block)
                        stdout_bytes += len(block)
        if process.returncode != 0:
            raise _Stop('FAIL', 'NONZERO_EXIT', 'exit zero was not established')
        row['status'] = 'PASS'
    except _Stop as exc:
        row.update(status=exc.status, failure_kind=exc.kind, failure=exc.message)
        if hasattr(exc, 'resource_observation'):
            retain_resource_observation(exc.resource_observation)
    except _SignalStop as exc:
        row.update(status='INCOMPLETE', failure_kind='INTERRUPTED',
                   failure=f'received signal {exc.signum}', interrupted_signal=exc.signum)
    except KeyboardInterrupt:
        row.update(status='INCOMPLETE', failure_kind='INTERRUPTED', failure='operator interrupt')
    except Exception as exc:
        row.update(status='FAIL', failure_kind='MONITOR_OR_LAUNCH_ERROR',
                   failure=str(exc), exception_type=type(exc).__name__)
        if isinstance(exc, ResourceObservationError):
            row.update(failure_kind='RESOURCE_OBSERVATION')
            retain_resource_observation(exc.resource_observation)
    finally:
        # Ignore a second graceful interrupt only during bounded group cleanup.
        for sig in old_handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None:
                row['cleanup'] = cleanup_group(process)
                row['exit_code'] = process.returncode
                if row['cleanup']['status'] != 'PASS':
                    row.update(status='FAIL', failure_kind='CLEANUP_FAILURE',
                               failure='live process-group members survived cleanup')
                # Preserve the final bounded pipe output even on failure. Never block on a writer.
                for key in list(selectors_open.get_map().values()):
                    for _ in range(32):
                        try:
                            block = os.read(key.fd, 64 << 10)
                        except (BlockingIOError, OSError):
                            break
                        if not block:
                            break
                        if key.data == 'log':
                            available = max(0, log_limit - log_bytes)
                            log_stream.write(block[:available])
                            log_bytes += min(len(block), available)
                            if len(block) > available:
                                row.setdefault('secondary_failures', []).append('LOG_LIMIT_DURING_CLEANUP')
                                if row['status'] == 'PASS':
                                    row.update(status='INCOMPLETE', failure_kind='LOG_LIMIT',
                                               failure='final diagnostic burst exceeded its byte limit')
                        elif artifact_stream and stdout_bytes + len(block) <= STDOUT_ARTIFACT_LIMIT:
                            artifact_stream.write(block)
                            artifact_hash.update(block)
                            stdout_bytes += len(block)
                last_snapshot = sample_process_group(process.pid)
                history.observe(last_snapshot)
            if telemetry_stream is not None:
                telemetry_record('after_cleanup', last_snapshot)
        except Exception as exc:
            row.update(status='FAIL', failure_kind='FINALIZATION_ERROR', failure=str(exc),
                       exception_type=type(exc).__name__)
        finally:
            selectors_open.close()
            if process:
                for stream in (process.stdout, process.stderr):
                    if stream:
                        stream.close()
            for stream in (log_stream, telemetry_stream, artifact_stream):
                if stream:
                    stream.close()
            for sig, previous in old_handlers.items():
                signal.signal(sig, previous)

    text = log.read_text(errors='replace') if log.exists() else ''
    final_diagnostics = [match.group(0) for match in DIAGNOSTIC.finditer(text)]
    if final_diagnostics:
        row['diagnostics'] = list(dict.fromkeys([*row['diagnostics'], *final_diagnostics]))
        if row['status'] == 'PASS':
            row.update(status='FAIL', failure_kind='DIAGNOSTIC', failure='diagnostic found in final output')
    if row['status'] == 'PASS' and row['exit_code'] != 0:
        row.update(status='FAIL', failure_kind='NONZERO_EXIT', failure='exit zero was not established')
    # Hash evidence after cleanup. Bound a potentially large stdout-artifact reread
    # by the same overall deadline; never turn an uncompleted reread into PASS.
    finalization_deadline = time.monotonic() + 5.0

    def final_hash(path: Path) -> str | None:
        if not path.exists():
            return None
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while True:
                if time.monotonic() > finalization_deadline:
                    row.setdefault('secondary_failures', []).append('EVIDENCE_HASHING_DEADLINE')
                    if row['status'] == 'PASS':
                        row.update(status='INCOMPLETE', failure_kind='TIMEOUT',
                                   failure='final evidence hashing exceeded its bounded cleanup allowance')
                    return None
                if row['status'] == 'PASS' and time.monotonic() - started > timeout:
                    row.update(status='INCOMPLETE', failure_kind='TIMEOUT',
                               failure='wall-time budget expired during final evidence hashing')
                    return None
                block = stream.read(1 << 20)
                if not block:
                    return digest.hexdigest()
                digest.update(block)
    row.update(log_bytes=log.stat().st_size if log.exists() else 0,
               log_sha256=final_hash(log), telemetry_sha256=final_hash(telemetry),
               telemetry_bytes=telemetry.stat().st_size if telemetry.exists() else 0,
               observed_totals=history.summary())
    if row['status'] == 'PASS' and (row['log_sha256'] is None or row['telemetry_sha256'] is None):
        row.update(status='FAIL', failure_kind='EVIDENCE_MISSING',
                   failure='final log and telemetry identities were not both established')
    if artifact:
        row.update(stdout_artifact_bytes=stdout_bytes, stdout_stream_sha256=artifact_hash.hexdigest(),
                   stdout_artifact_sha256=final_hash(artifact))
        if row['status'] == 'PASS' and row['stdout_artifact_sha256'] != row['stdout_stream_sha256']:
            row.update(status='FAIL', failure_kind='OUTPUT_IDENTITY', failure='stdout artifact bytes changed')
        row['stdout_artifact_identity_completed'] = row['stdout_artifact_sha256'] is not None
    row.update(ended_utc=utc_now(), elapsed_seconds=round(time.monotonic() - started, 6))
    _json_write(receipt, row)
    return row, text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--cwd', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', required=True, type=float)
    parser.add_argument('--memory-mib', type=int, default=MAX_MEMORY_MIB)
    parser.add_argument('--log-limit', type=int, default=64 << 20)
    parser.add_argument('--stdout-path', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    row, _ = run(args.name, command, cwd=args.cwd, env=os.environ, output=args.output,
                 timeout=args.timeout, memory_mib=args.memory_mib,
                 log_limit=args.log_limit, stdout_path=args.stdout_path)
    print(f"{row['status']}: {row['name']} ({row.get('failure_kind', 'EXIT_ZERO')})", flush=True)
    return 0 if row['status'] == 'PASS' else 2 if row['status'] == 'INCOMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
