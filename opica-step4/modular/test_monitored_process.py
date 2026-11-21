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

import monitored_process as monitor

ROOT = Path(tempfile.mkdtemp(prefix='controls_', dir=Path(__file__).resolve().parent))


class ProcessControls(unittest.TestCase):
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


if __name__ == '__main__':
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProcessControls))
    receipt = {
        'schema': 'MONITORED_PROCESS_CONTROLS_V1', 'status': 'PASS' if result.wasSuccessful() else 'FAIL',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'elapsed_seconds': round(time.monotonic() - started, 3), 'controls_root': str(ROOT),
        'helper_sha256': monitor.sha256(Path(monitor.__file__)),
        'test_source_sha256': monitor.sha256(Path(__file__)),
        'no_lean_or_supplier_imports': True,
        'process_receipts': [str(path) for path in sorted(ROOT.glob('*/control.process.json'))],
    }
    (ROOT / 'CONTROLS_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
