"""Cheap process controls only: no Lean imports, caches, network or proof jobs."""
from pathlib import Path
import hashlib
import json
import os
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

import monitored_process as monitor

ROOT = Path(tempfile.mkdtemp(prefix='controls_', dir=Path(os.environ.get(
    'OPICA_MONITOR_CONTROL_PARENT', str(Path(__file__).resolve().parent)))))


class ProcessControls(unittest.TestCase):
    @staticmethod
    def deny_proc_file(basename):
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.parent.parent == Path('/proc') and path.parent.name.isdecimal() and path.name == basename:
                raise PermissionError('fixture denied optional I/O' if basename == 'io'
                                      else 'fixture denied mandatory RSS/swap')
            return original(path, *args, **kwargs)

        return mock.patch.object(Path, 'read_text', read)

    def execute(self, code, *, timeout=5, memory_mib=50000, log_limit=65536, artifact=False):
        output = ROOT / self.id().rsplit('.', 1)[-1]
        output.mkdir()
        artifact_path = output / 'stdout.bin' if artifact else None
        env = dict(os.environ, MONITOR_TEST_SECRET='private-fixture-value-never-record')
        row, text = monitor.run('control', [sys.executable, '-c', code], cwd=output,
                                env=env, output=output, timeout=timeout,
                                memory_mib=memory_mib, log_limit=log_limit,
                                stdout_path=artifact_path)
        saved = json.loads((output / 'control.process.json').read_text())
        self.assertEqual(row, saved)
        self.assertEqual(row['cleanup']['status'], 'PASS')
        self.assertEqual(row['cleanup']['live_pids_after'], [])
        self.assertEqual(monitor.sample_process_group(row['pgid'])['live_pids'], [])
        self.assertEqual(hashlib.sha256(Path(row['log']).read_bytes()).hexdigest(), row['log_sha256'])
        self.assertEqual(hashlib.sha256(Path(row['telemetry']).read_bytes()).hexdigest(), row['telemetry_sha256'])
        return row, text, output

    def test_exit_zero_and_resource_evidence(self):
        row, text, output = self.execute("import time; print('marker', flush=True); time.sleep(.15)")
        self.assertEqual((row['status'], row['exit_code']), ('PASS', 0))
        self.assertEqual(text, 'marker\n')
        samples = [json.loads(line) for line in Path(row['telemetry']).read_text().splitlines()]
        self.assertEqual(samples[0]['event'], 'before_launch')
        self.assertEqual(samples[-1]['event'], 'after_cleanup')
        self.assertTrue(any(sample['process_group'] for sample in samples))
        self.assertIn('MemAvailable', samples[0]['host']['memory_bytes'])
        self.assertEqual(set(samples[0]['host']['pressure']), {'cpu', 'memory', 'io'})
        self.assertIn('major_faults_observed', row['observed_totals'])
        self.assertIn('read_bytes', row['observed_totals']['io_observed'])
        self.assertNotIn('private-fixture-value-never-record', json.dumps(row) + Path(row['telemetry']).read_text())
        before = (output / 'control.process.json').read_bytes()
        with self.assertRaises(ValueError):
            monitor.run('control', [sys.executable, '-c', 'pass'], cwd=output,
                        env=os.environ, output=output, timeout=1)
        self.assertEqual(before, (output / 'control.process.json').read_bytes())

    def test_nonzero_is_failure(self):
        row, text, _ = self.execute("import sys; print('before-exit', flush=True); sys.exit(7)")
        self.assertEqual((row['status'], row['failure_kind'], row['exit_code']), ('FAIL', 'NONZERO_EXIT', 7))
        self.assertIn('before-exit', text)

    def test_zero_exit_warning_is_failure(self):
        row, _, _ = self.execute("print('Probe.lean:2:3: warning: fixture')")
        self.assertEqual((row['status'], row['failure_kind']), ('FAIL', 'DIAGNOSTIC'))
        self.assertTrue(row['diagnostics'])

    def test_timeout_is_incomplete(self):
        row, _, _ = self.execute('import time; time.sleep(20)', timeout=.3)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'TIMEOUT'))
        self.assertNotEqual(row['exit_code'], 0)

    def test_timeout_after_stdout_eof(self):
        row, _, _ = self.execute('import os,time; os.close(1); os.close(2); time.sleep(20)', timeout=.3)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'TIMEOUT'))

    def test_memory_limit_is_incomplete(self):
        row, _, _ = self.execute("import time; data=bytearray(64*1024*1024); print('allocated',flush=True); time.sleep(20)", memory_mib=32)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'MEMORY_LIMIT'))
        self.assertGreater(row['max_sampled_rss_plus_swap_bytes'], 32 * 1024**2)

    def test_log_limit_is_incomplete_and_disk_bounded(self):
        row, _, _ = self.execute("import os; os.write(1,b'x'*8192)", log_limit=256)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'LOG_LIMIT'))
        self.assertEqual(Path(row['log']).stat().st_size, 256)

    def test_child_ignoring_sigterm_is_killed(self):
        child = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('child-ready',flush=True); time.sleep(20)"
        code = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(20)'
        row, text, _ = self.execute(code, timeout=.7)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'TIMEOUT'))
        self.assertIn('child-ready', text)
        self.assertIn('SIGKILL', row['cleanup']['signals_sent'])

    def test_exited_leader_descendant_is_not_pass(self):
        child = 'import time; time.sleep(20)'
        code = f'import subprocess,sys,os; subprocess.Popen([sys.executable,"-c",{child!r}]); os._exit(0)'
        row, _, _ = self.execute(code)
        self.assertEqual((row['status'], row['failure_kind']), ('FAIL', 'ORPHANED_DESCENDANTS'))
        self.assertEqual(row['exit_code'], 0)

    def test_sigterm_to_monitor_preserves_receipt_and_cleans_child(self):
        code = 'import os,signal,time; time.sleep(.1); os.kill(os.getppid(),signal.SIGTERM); time.sleep(20)'
        row, _, _ = self.execute(code)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'INTERRUPTED'))
        self.assertEqual(row['interrupted_signal'], signal.SIGTERM)

    def test_exact_binary_stdout_artifact(self):
        row, text, output = self.execute("import os; os.write(1,bytes([0,10,255,128,13])); os.write(2,b'marker\\n')", artifact=True)
        self.assertEqual((row['status'], row['exit_code']), ('PASS', 0))
        self.assertEqual((output / 'stdout.bin').read_bytes(), bytes([0,10,255,128,13]))
        self.assertEqual(row['stdout_artifact_sha256'], row['stdout_stream_sha256'])
        self.assertEqual(text, 'marker\n')

    def test_periodic_cpu_fault_and_io_telemetry(self):
        previous = monitor.PROGRESS_SECONDS
        monitor.PROGRESS_SECONDS = .05  # Accelerate the interval only for this process control.
        try:
            code = """import time
data=bytearray(4*1024*1024)
with open('io-control.bin','wb') as f: f.write(bytes(1024*1024))
print('working',flush=True)
deadline=time.monotonic()+.4
x=1
while time.monotonic()<deadline: x=(x*1664525+1013904223)&0xffffffff
"""
            row, _, _ = self.execute(code)
        finally:
            monitor.PROGRESS_SECONDS = previous
        self.assertEqual(row['status'], 'PASS')
        samples = [json.loads(line) for line in Path(row['telemetry']).read_text().splitlines()]
        self.assertTrue(any(sample['event'] == 'progress' for sample in samples))
        self.assertGreater(row['observed_totals']['user_seconds_observed'], 0)
        self.assertGreater(row['observed_totals']['minor_faults_observed'], 0)
        self.assertGreaterEqual(row['observed_totals']['io_observed']['wchar'], 1024*1024)

    def test_deleted_log_cannot_pass(self):
        output = ROOT / self.id().rsplit('.', 1)[-1]
        output.mkdir()
        row, _ = monitor.run('control', [sys.executable, '-c', "import os; os.unlink('control.log')"],
                             cwd=output, env=os.environ, output=output, timeout=5)
        self.assertEqual((row['status'], row['failure_kind']), ('FAIL', 'EVIDENCE_MISSING'))
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['cleanup']['live_pids_after'], [])
        self.assertEqual(json.loads((output / 'control.process.json').read_text()), row)

    def test_denied_optional_io_records_incomplete_coverage_and_passes(self):
        with self.deny_proc_file('io'):
            row, text, _ = self.execute("import time; a=bytearray(4*1024*1024); print('complete',flush=True); time.sleep(.35)")
        self.assertEqual((row['status'], row['exit_code']), ('PASS', 0))
        self.assertEqual(text, 'complete\n')
        self.assertGreater(row['max_sampled_rss_plus_swap_bytes'], 0)
        coverage = row['observed_totals']['optional_io_telemetry']
        self.assertEqual(coverage['coverage_status'], 'INCOMPLETE')
        self.assertGreater(coverage['unavailable_member_samples'], 0)
        self.assertTrue(any(item['error_type'] == 'PermissionError'
                            for item in coverage['errors_first_at_most_16']))
        samples = [json.loads(line) for line in Path(row['telemetry']).read_text().splitlines()]
        self.assertTrue(any(sample['observed_totals']['optional_io_telemetry']['coverage_status'] == 'INCOMPLETE'
                            for sample in samples))

    def test_denied_optional_io_does_not_disable_memory_limit(self):
        with self.deny_proc_file('io'):
            row, _, _ = self.execute('import time; a=bytearray(64*1024*1024); time.sleep(20)', memory_mib=32)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'MEMORY_LIMIT'))
        self.assertGreater(row['max_sampled_rss_plus_swap_bytes'], 32 * 1024**2)
        self.assertEqual(row['observed_totals']['optional_io_telemetry']['coverage_status'], 'INCOMPLETE')

    def test_denied_mandatory_rss_swap_still_fails(self):
        with self.deny_proc_file('status'):
            row, _, _ = self.execute('import time; time.sleep(20)')
        self.assertEqual((row['status'], row['failure_kind']), ('FAIL', 'MONITOR_OR_LAUNCH_ERROR'))
        self.assertEqual(row['exception_type'], 'PermissionError')
        self.assertIn('mandatory RSS/swap', row['failure'])

    def test_io_counter_history_does_not_reset_across_unavailable_sample(self):
        history = monitor.CounterHistory()
        for index, io_value in enumerate([10, None, 15], start=1):
            member = {'pid': 12345, 'start_ticks': 67890, 'user_ticks': index,
                      'system_ticks': index, 'minor_faults': index, 'major_faults': index,
                      'io': {} if io_value is None else {key: io_value for key in monitor.IO_COUNTERS}}
            unavailable = io_value is None
            history.observe({'members': [member], 'io_coverage': {
                'available_member_samples': int(not unavailable),
                'unavailable_member_samples': int(unavailable),
                'unavailable_members': [{'pid': 12345, 'error_type': 'PermissionError'}] if unavailable else []}})
        summary = history.summary()
        self.assertEqual(set(summary['io_observed'].values()), {15})
        self.assertEqual(summary['minor_faults_observed'], 3)
        self.assertEqual(summary['optional_io_telemetry']['unavailable_member_samples'], 1)

    def test_persistent_missing_live_counter_preserves_failure_evidence(self):
        original = Path.read_text

        def read(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            if path.parent.parent == Path('/proc') and path.name == 'status':
                return '\n'.join(line for line in text.splitlines() if not line.startswith('VmSwap:'))
            return text

        with mock.patch.object(Path, 'read_text', read):
            row, _, _ = self.execute('import time; time.sleep(20)')
        self.assertEqual((row['status'], row['failure_kind']), ('FAIL', 'RESOURCE_OBSERVATION'))
        failed = row['resource_observation_failure']
        self.assertEqual(failed['initial_missing_counters'], ['VmSwap'])
        self.assertEqual(failed['last_missing_counters'], ['VmSwap'])
        self.assertEqual(failed['identity'], failed['last_identity'])
        self.assertGreater(failed['retries'], 1)
        self.assertEqual(failed['outcome'], 'RECONCILIATION_BUDGET_EXHAUSTED')
        samples = [json.loads(line) for line in Path(row['telemetry']).read_text().splitlines()]
        self.assertTrue(any(s.get('resource_observation') == failed for s in samples))

    def test_missing_counter_cannot_extend_execution_deadline(self):
        original = monitor._memory_status

        def missing(pid):
            return {k: v for k, v in original(pid).items() if k != 'VmSwap'}

        with mock.patch.object(monitor, '_memory_status', missing):
            row, _, _ = self.execute('import time; time.sleep(20)', timeout=.08)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'TIMEOUT'))
        self.assertEqual(row['resource_observation_failure']['outcome'], 'EXECUTION_DEADLINE')

    def test_over_limit_recovered_counters_still_terminate_process(self):
        original = Path.read_text
        injected = set()

        def read(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            if path.parent.parent == Path('/proc') and path.name == 'status':
                rss = next((int(line.split()[1]) * 1024 for line in text.splitlines()
                            if line.startswith('VmRSS:')), 0)
                if rss > 32 * 1024**2 and path.parent.name not in injected:
                    injected.add(path.parent.name)
                    return '\n'.join(line for line in text.splitlines() if not line.startswith('VmSwap:'))
            return text

        with mock.patch.object(Path, 'read_text', read):
            row, _, _ = self.execute('import time; a=bytearray(64*1024*1024); time.sleep(20)', memory_mib=32)
        self.assertTrue(injected)
        self.assertEqual((row['status'], row['failure_kind']), ('INCOMPLETE', 'MEMORY_LIMIT'))
        self.assertGreater(row['max_sampled_rss_plus_swap_bytes'], 32 * 1024**2)
        history = row['observed_totals']['mandatory_memory_observations']
        self.assertGreater(history['reconciliation_count'], 0)
        self.assertIn('RECOVERED_LIVE_COUNTERS', [r['outcome'] for r in history['reconciliations_first_at_most_16']])


class ResourceLifecycleControls(unittest.TestCase):
    """Deterministic proc snapshots: no dependence on reproducing an exit race."""
    PID = 424242
    LIVE = {'pid': PID, 'comm': 'fixture', 'state': 'R', 'ppid': 123,
            'pgrp': PID, 'minor_faults': 7, 'major_faults': 0,
            'user_ticks': 2, 'system_ticks': 1, 'threads': 1, 'start_ticks': 123456}
    MISSING = 'Name:\tfixture\nState:\tR (running)\n'
    VALID = 'VmRSS:\t10 kB\nVmSwap:\t2 kB\n'

    def simulate(self, statuses, *, states=None, members=None, deadline=None):
        members = members or [dict(self.LIVE)]
        if not isinstance(statuses, dict):
            statuses = {self.PID: statuses}
        state_map = states if isinstance(states, dict) else {self.PID: states or [dict(self.LIVE)]}
        status_queues = {pid: list(values) for pid, values in statuses.items()}
        state_queues = {pid: list(values) for pid, values in state_map.items()}
        clock = [1000.0]

        def take(queue):
            result = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(result, BaseException):
                raise result
            return dict(result) if isinstance(result, dict) else result

        def read(path, *_args, **_kwargs):
            pid = int(path.parent.name)
            if path.name == 'status':
                return take(status_queues[pid])
            if path.name == 'io':
                return '\n'.join(f'{key}: 0' for key in monitor.IO_COUNTERS)
            raise AssertionError('Unplanned fixture read: ' + str(path))

        record = {'fixture': self.id(), 'original_members': members,
                  'execution_deadline_offset': deadline, 'result': None}
        try:
            with mock.patch.object(monitor, '_proc_members', return_value=[dict(r) for r in members]), \
                 mock.patch.object(monitor, '_stat', side_effect=lambda pid: take(state_queues[pid])), \
                 mock.patch.object(Path, 'read_text', read), \
                 mock.patch.object(monitor.time, 'monotonic', side_effect=lambda: clock[0]), \
                 mock.patch.object(monitor.time, 'sleep', side_effect=lambda delay: clock.__setitem__(0, clock[0] + delay)):
                result = monitor.sample_process_group(self.PID, deadline=None if deadline is None else 1000 + deadline)
                record['result'] = result
                return result
        except BaseException as exc:
            record.update(exception_type=type(exc).__name__, failure=str(exc),
                          observation=getattr(exc, 'resource_observation', None))
            raise
        finally:
            record['simulated_elapsed_seconds'] = round(clock[0] - 1000, 6)
            (ROOT / (self.id().rsplit('.', 1)[-1] + '.reconciliation.json')).write_text(json.dumps(record, indent=2) + '\n')

    def test_missing_live_counters_then_confirmed_zombie(self):
        result = self.simulate([self.MISSING], states=[dict(self.LIVE), dict(self.LIVE, state='Z')])
        member = result['members'][0]
        self.assertEqual(result['live_pids'], [])
        self.assertIsNone(member['rss_bytes'])
        self.assertIsNone(member['swap_bytes'])
        self.assertEqual(member['memory_coverage'], 'NOT_LIVE_NO_MEASUREMENT')
        self.assertEqual(result['memory_coverage']['reconciliations'][0]['outcome'], 'CONFIRMED_RETIRED_STATE')

    def test_missing_live_counters_then_confirmed_dead(self):
        result = self.simulate([self.MISSING], states=[dict(self.LIVE, state='X')])
        self.assertEqual(result['live_pids'], [])
        self.assertIsNone(result['members'][0]['rss_bytes'])

    def test_missing_live_counters_then_confirmed_disappearance(self):
        result = self.simulate([self.MISSING], states=[FileNotFoundError('original stat disappeared')])
        self.assertEqual(result['live_pids'], [])
        self.assertIsNone(result['members'][0]['swap_bytes'])
        self.assertEqual(result['memory_coverage']['reconciliations'][0]['outcome'], 'CONFIRMED_DISAPPEARED')

    def test_complete_counters_recover_for_same_live_identity(self):
        result = self.simulate([self.MISSING, self.VALID])
        self.assertEqual(result['live_pids'], [self.PID])
        self.assertEqual(result['totals']['rss_plus_swap_bytes'], 12 * 1024)
        event = result['memory_coverage']['reconciliations'][0]
        self.assertEqual(event['outcome'], 'RECOVERED_LIVE_COUNTERS')
        self.assertEqual(event['identity'], event['last_identity'])

    def test_persistent_missing_live_counters_fail_with_bounded_evidence(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate(['VmRSS:\t10 kB\n'])
        event = caught.exception.resource_observation
        self.assertEqual(event['last_missing_counters'], ['VmSwap'])
        self.assertEqual(event['last_state'], 'R')
        self.assertEqual(event['outcome'], 'RECONCILIATION_BUDGET_EXHAUSTED')
        self.assertLessEqual(event['elapsed_seconds'], monitor.RECONCILE_SECONDS + .000001)

    def test_missing_status_file_is_not_disappearance_of_live_identity(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate([FileNotFoundError('status unavailable while stat remains live')])
        self.assertEqual(caught.exception.resource_observation['outcome'], 'RECONCILIATION_BUDGET_EXHAUSTED')

    def test_pid_reuse_is_not_silently_retired(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate([self.MISSING], states=[dict(self.LIVE, start_ticks=654321)])
        self.assertEqual(caught.exception.resource_observation['outcome'], 'IDENTITY_OR_GROUP_CHANGED')

    def test_changed_group_is_not_silently_retired(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate([self.MISSING], states=[dict(self.LIVE, pgrp=self.PID + 1)])
        self.assertEqual(caught.exception.resource_observation['outcome'], 'IDENTITY_OR_GROUP_CHANGED')

    def test_recovered_values_require_identity_check_after_read(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate([self.MISSING, self.VALID], states=[dict(self.LIVE), dict(self.LIVE, start_ticks=654321)])
        self.assertEqual(caught.exception.resource_observation['outcome'], 'IDENTITY_OR_GROUP_CHANGED')

    def test_malformed_live_counters_are_fatal(self):
        with self.assertRaises(ValueError):
            self.simulate(['VmRSS:\t-1 kB\nVmSwap:\t2 kB\n'])

    def test_denied_identity_during_reconciliation_is_fatal(self):
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate([self.MISSING], states=[PermissionError('cannot confirm original identity')])
        self.assertEqual(caught.exception.resource_observation['outcome'], 'IDENTITY_UNREADABLE')

    def test_valid_partial_high_counter_is_retained_after_exit(self):
        result = self.simulate(['VmRSS:\t65536 kB\n'], states=[dict(self.LIVE, state='Z')])
        self.assertEqual(result['totals']['rss_bytes'], 64 * 1024**2)
        self.assertIsNone(result['members'][0]['swap_bytes'])
        self.assertEqual(result['members'][0]['memory_coverage'], 'NOT_LIVE_PARTIAL_MEASUREMENT')

    def test_recovered_high_observation_is_not_erased_by_lower_later_value(self):
        result = self.simulate(['VmRSS:\t65536 kB\n', self.VALID])
        self.assertEqual(result['totals']['rss_bytes'], 64 * 1024**2)

    def test_retired_leader_does_not_retire_live_descendant(self):
        child = dict(self.LIVE, pid=self.PID + 1, start_ticks=123457)
        result = self.simulate({self.PID: [self.MISSING], child['pid']: [self.VALID]},
            states={self.PID: [dict(self.LIVE, state='Z')], child['pid']: [child]},
            members=[dict(self.LIVE), child])
        self.assertEqual(result['live_pids'], [child['pid']])
        self.assertEqual(result['totals']['rss_plus_swap_bytes'], 12 * 1024)

    def test_reconciliation_budget_is_shared_by_group(self):
        child = dict(self.LIVE, pid=self.PID + 1, start_ticks=123457)
        with self.assertRaises(monitor.ResourceObservationError) as caught:
            self.simulate({self.PID: [self.MISSING] * 20 + [self.VALID], child['pid']: [self.MISSING]},
                states={self.PID: [dict(self.LIVE)], child['pid']: [child]}, members=[dict(self.LIVE), child])
        event = caught.exception.resource_observation
        self.assertEqual(event['identity']['pid'], child['pid'])
        self.assertLess(event['shared_budget_remaining_at_entry_seconds'], .1)
        self.assertLessEqual(event['elapsed_seconds'], .1)


if __name__ == '__main__':
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    receipt = {
        'schema': 'MONITORED_PROCESS_CONTROLS_RESOURCE_LIFECYCLE_V3', 'status': 'PASS' if result.wasSuccessful() else 'FAIL',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'elapsed_seconds': round(time.monotonic() - started, 3), 'controls_root': str(ROOT),
        'helper_sha256': monitor.sha256(Path(monitor.__file__)),
        'test_source_sha256': monitor.sha256(Path(__file__)),
        'no_lean_or_supplier_imports': True,
        'process_receipts': [str(path) for path in sorted(ROOT.glob('*/control.process.json'))],
        'lifecycle_records': [str(path) for path in sorted(ROOT.glob('*.reconciliation.json'))],
    }
    (ROOT / 'CONTROLS_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
