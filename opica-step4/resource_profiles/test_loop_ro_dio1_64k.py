"""Tiny simulated-host controls. No real loop allocation, mount, privilege or Lean use."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import loop_ro_dio1_64k as m


class FakeHost:
    def __init__(self, work):
        self.work = work
        self.calls = []
        self.allocated = self.mounted = False
        self.unsupported = self.mount_failure = self.wrong_inode = False
        self.missing_dio = False
        self.sha = m.IMAGE['sha256']
        self.values = {'loop/dio': '1', 'ro': '1', 'loop/offset': '0', 'loop/sizelimit': '0',
                       'queue/logical_block_size': '512', 'size': str(m.IMAGE['bytes'] // 512), 'dev': '7:17'}
        self.image_id = {'device': 30, 'inode': 1234, 'bytes': m.IMAGE['bytes'], 'mtime_ns': 100, 'ctime_ns': 100}
        self.config = dict(m.SINGLE)
        self.threads = None
        self.extra_mount = False

    def row(self):
        return {'name': '/dev/loop17', 'dio': int(self.values['loop/dio']), 'ro': int(self.values['ro']),
                'offset': int(self.values['loop/offset']), 'sizelimit': int(self.values['loop/sizelimit']),
                'log-sec': int(self.values['queue/logical_block_size']), 'back-file': str(self.work / 'proof-store.sqfs'),
                'back-ino': 999 if self.wrong_inode else 1234, 'back-maj:min': '0:30'}

    def command(self, argv, timeout=30):
        argv = list(map(str, argv)); self.calls.append(argv)
        out, code = '', 0
        if argv[0] == 'losetup' and '--list' in argv:
            out = json.dumps({'loopdevices': [self.row()] if self.allocated else []})
        elif argv[0] == 'losetup' and '--find' in argv:
            if self.unsupported: code = 1
            else: self.allocated = True; out = '/dev/loop17\n'
        elif argv[:2] == ['losetup', '--detach']:
            self.allocated = False
        elif argv[0] == 'mount':
            if self.mount_failure: code = 1
            else: self.mounted = True
        elif argv[0] == 'umount': self.mounted = False
        else: raise AssertionError('Unexpected simulated operation: ' + str(argv))
        return {'argv': argv, 'exit_code': code, 'disposition': 'COMPLETED', 'stdout': out,
                'stderr': 'unsupported fixture' if code else ''}

    def text(self, path):
        if path == '/proc/self/mountinfo':
            option = ',threads=' + self.threads if self.threads is not None else ''
            main = f'70 1 7:17 / {self.work}/proof-store ro,relatime - squashfs /dev/loop17 ro{option}' if self.mounted else ''
            extra = f'71 1 7:17 / {self.work}/another-target ro - squashfs /dev/loop17 ro' if self.extra_mount else ''
            return '\n'.join(x for x in (main, extra) if x)
        suffix = path.removeprefix('/sys/class/block/loop17/')
        if suffix == 'loop/dio' and self.missing_dio: raise FileNotFoundError(path)
        return self.values[suffix]

    def block_identity(self, _path): return '7:17'
    def image_identity(self, _path): return dict(self.image_id)
    def image_digest(self, _path, _expected):
        return {'identity': dict(self.image_id), 'sha256': self.sha, 'bytes_read': m.IMAGE['bytes'],
                'scope': 'Simulated host only; actual fixture file is tiny'}
    def context(self, _image):
        ok = {'exit_code': 0, 'disposition': 'COMPLETED', 'stdout': 'util-linux FIXTURE', 'stderr': ''}
        return {'kernel_release': 'FIXTURE_SINGLE_ONLY',
                'kernel_configurations': ([{'coverage': 'AVAILABLE', 'values': dict(self.config)}]
                                          if self.config is not None else [{'coverage': 'UNAVAILABLE', 'error': 'fixture missing config'}]),
                'versions': {x: dict(ok) for x in ('losetup', 'mount', 'findmnt')},
                'backing_filesystem': {**ok, 'stdout': json.dumps({'filesystems': [{'fstype': 'fixture-fs'}]})},
                'exact_kernel_build_source': 'NOT_ESTABLISHED'}


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name) / 'work'; self.work.mkdir()
        (self.work / 'proof-store').mkdir()
        (self.work / 'proof-store.sqfs').write_bytes(b'tiny simulated image')
        receipt = {'status': 'VERIFIED_ARCHIVE_REPACKED', 'production_supplier': True,
                   'image_sha256': m.IMAGE['sha256'], 'image_bytes': m.IMAGE['bytes'], 'files': m.IMAGE['files'],
                   'mounted_manifest_sha256': m.IMAGE['mounted_manifest_sha256'],
                   'helper_sha256': m.IMAGE['transport_helper_sha256'], 'mksquashfs_command': ['fixture', '-b', '64K']}
        (self.work / 'proof-store.sqfs.receipt.json').write_text(json.dumps(receipt))
        (self.work / 'mounted-store-verified.json').write_text(json.dumps({'status': 'PASS', 'files': m.IMAGE['files'],
                                                 'manifest_sha256': m.IMAGE['mounted_manifest_sha256']}))
        self.args = argparse.Namespace(work=self.work, supplier=Path(self.temp.name) / 'supplier', head='a' * 40,
                                       selection=m.PROFILE, modular_outcome='failure', independent_outcome='skipped')
        self.host = FakeHost(self.work)
        self.adapter = m.Adapter(self.args, self.host)
        self.auth = patch.object(m, 'authenticate_source', return_value=({}, {'fixture_source': 'b' * 64}))
        self.auth.start()

    def tearDown(self):
        self.auth.stop(); self.temp.cleanup()

    def assert_no_allocate(self):
        self.assertFalse(any('--find' in x for x in self.host.calls))

    def test_none_refuses_before_setup(self):
        self.args.selection = 'none'
        with self.assertRaises(m.Refusal): self.adapter.setup()
        self.assert_no_allocate(); self.assertFalse(self.adapter.output.exists())

    def test_wrong_image_hash_refuses_before_allocate(self):
        self.host.sha = '0' * 64
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertIn('SHA256', row['error']); self.assert_no_allocate()

    def test_wrong_transport_identity_refuses_before_allocate(self):
        path = self.work / 'proof-store.sqfs.receipt.json'; data = json.loads(path.read_text())
        data['image_sha256'] = '0' * 64; path.write_text(json.dumps(data))
        self.assertEqual(self.adapter.setup()[0], 2); self.assert_no_allocate()

    def test_unsupported_dio_has_no_automatic_fallback(self):
        self.host.unsupported = True
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertEqual(row['status'], 'INVALID_TREATMENT')
        self.assertEqual(len([x for x in self.host.calls if '--find' in x]), 1)
        self.assertFalse(any('--detach' in x or '--direct-io=off' in x for x in self.host.calls))

    def test_dio_zero_rejects_and_releases_only_owned_loop(self):
        self.host.values['loop/dio'] = '0'
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertEqual(row['cleanup']['status'], 'DETACH_REQUEST_SUCCEEDED')
        self.assertIn(['losetup', '--detach', '/dev/loop17'], self.host.calls)

    def test_unreadable_dio_rejects(self):
        self.host.missing_dio = True
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertEqual(row['error_type'], 'FileNotFoundError')

    def test_wrong_inode_never_detaches_unproven_device(self):
        self.host.wrong_inode = True
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertEqual(row['cleanup']['status'], 'CLEANUP_REFUSED_OR_FAILED')
        self.assertFalse(any('--detach' in x for x in self.host.calls))

    def test_preexisting_loop_is_not_reused(self):
        self.host.allocated = True
        self.assertEqual(self.adapter.setup()[0], 2); self.assert_no_allocate()
        self.assertFalse(any('--detach' in x for x in self.host.calls))

    def test_mount_failure_records_owned_cleanup(self):
        self.host.mount_failure = True
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertEqual(row['mount_request']['exit_code'], 1)
        self.assertEqual(row['cleanup']['status'], 'DETACH_REQUEST_SUCCEEDED')

    def test_ambiguous_absent_mode_refuses_and_cleans_owned_setup(self):
        self.host.config.pop('CONFIG_SQUASHFS_DECOMP_SINGLE')
        code, row = self.adapter.setup()
        self.assertEqual(code, 2); self.assertIn('NOT_READY_FOR_COMPARISON', row['error'])
        self.assertEqual(row['cleanup']['status'], 'DETACH_REQUEST_SUCCEEDED')

    def test_choice_kernel_with_actual_single_is_supported(self):
        self.host.config['CONFIG_SQUASHFS_CHOICE_DECOMP_BY_MOUNT'] = 'y'
        self.host.threads = 'single'
        code, row = self.adapter.setup()
        self.assertEqual(code, 0)
        self.assertEqual(row['mounted']['decompressor_mode']['basis'], 'ACTUAL_MOUNT_OPTION_THREADS_SINGLE')
        self.assertEqual(self.adapter.binding()[0], 0)

    def test_unavailable_config_with_actual_single_is_supported(self):
        self.host.config = None; self.host.threads = 'single'
        self.assertEqual(self.adapter.setup()[0], 0)
        self.assertEqual(self.adapter.binding()[0], 0)

    def test_non_single_effective_thread_modes_are_rejected(self):
        for value in ('multi', 'percpu', '2', '8'):
            with self.subTest(value=value), self.assertRaises(m.Refusal):
                m.single_mode({'options': 'ro', 'super_options': 'ro,threads=' + value}, self.host.context(self.adapter.image))

    def test_geometry_and_ro_refusals(self):
        self.host.allocated = True
        for field, bad in [('ro', '0'), ('loop/offset', '4096'), ('loop/sizelimit', '4096'),
                           ('size', '1'), ('queue/logical_block_size', '3')]:
            with self.subTest(field=field):
                original = self.host.values[field]; self.host.values[field] = bad
                with self.assertRaises(m.Refusal):
                    m.observe(self.host, '/dev/loop17', self.adapter.image, self.host.image_id)
                self.host.values[field] = original

    def test_existing_or_symlink_receipts_are_never_overwritten(self):
        self.adapter.output.mkdir(); sentinel = self.adapter.output / 'SETUP_RESULT.json'
        sentinel.write_bytes(b'previous receipt')
        with self.assertRaises(FileExistsError): self.adapter.setup()
        self.assertEqual(sentinel.read_bytes(), b'previous receipt'); self.assert_no_allocate()
        target = self.work / 'untouched'; target.write_bytes(b'sentinel')
        (self.adapter.output / 'FINAL.json').symlink_to(target)
        self.args.selection = 'none'
        with self.assertRaises(FileExistsError): self.adapter.final()
        self.assertEqual(target.read_bytes(), b'sentinel')

    def test_success_then_drift_preserves_raw_proof_and_does_not_cleanup(self):
        self.assertEqual(self.adapter.setup()[0], 0)
        self.assertEqual(self.adapter.binding()[0], 0)
        proof = self.work / 'verification'; proof.mkdir()
        path = proof / 'MODULAR_GATE_RECEIPT.json'; before = b'{"status":"INCOMPLETE"}\n'; path.write_bytes(before)
        self.host.values['loop/dio'] = '0'
        code, row = self.adapter.final()
        self.assertEqual(code, 2); self.assertEqual(row['raw_proof_receipts']['modular']['status'], 'INCOMPLETE')
        self.assertEqual(row['raw_proof_step_outcomes'], {'modular': 'failure', 'independent': 'skipped'})
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(any('--detach' in x or x[0] == 'umount' for x in self.host.calls))

    def test_bound_identity_unchanged_is_resource_only(self):
        self.assertEqual(self.adapter.setup()[0], 0); self.assertEqual(self.adapter.binding()[0], 0)
        code, row = self.adapter.final()
        self.assertEqual(code, 0); self.assertEqual(row['status'], 'FINAL_RESOURCE_IDENTITIES_UNCHANGED')
        self.assertFalse(row['proof_acceptance']); self.assertEqual(row['raw_proof_receipts']['modular']['status'], 'NOT_PRESENT')

    def test_partial_setup_without_binding_cannot_qualify(self):
        self.assertEqual(self.adapter.setup()[0], 0)
        code, row = self.adapter.final()
        self.assertEqual(code, 2); self.assertEqual(row['error_type'], 'FileNotFoundError')
        self.assertFalse(any('--detach' in x or x[0] == 'umount' for x in self.host.calls))

    def test_changed_image_before_binding_refuses_without_cleanup(self):
        self.assertEqual(self.adapter.setup()[0], 0)
        self.host.image_id['inode'] += 1
        code, row = self.adapter.binding()
        self.assertEqual(code, 2); self.assertEqual(row['status'], 'RESOURCE_BINDING_REFUSED')
        self.assertTrue((self.adapter.output / 'BIND_FAILURE.json').is_file())
        self.assertFalse((self.adapter.output / 'INITIAL.json').exists())
        self.assertFalse(any('--detach' in x or x[0] == 'umount' for x in self.host.calls))

    def test_other_mount_target_prevents_owned_device_cleanup(self):
        self.assertEqual(self.adapter.setup()[0], 0)
        self.host.extra_mount = True
        row = self.adapter.cleanup_owned_unbound('/dev/loop17', self.host.image_id)
        self.assertEqual(row['status'], 'CLEANUP_REFUSED_OR_FAILED')
        self.assertFalse(any('--detach' in x or x[0] == 'umount' for x in self.host.calls))

    def test_direct_file_hash_and_symlink_refusal_use_real_tiny_bytes(self):
        path = self.work / 'tiny'; path.write_bytes(b'real small hash input')
        actual = m.Host().image_digest(path, path.stat().st_size)
        self.assertEqual(actual['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        link = self.work / 'link'; link.symlink_to(path)
        with self.assertRaises(OSError): m.Host().image_digest(link, path.stat().st_size)

    def test_wrong_exact_head_fails_before_source_or_host_setup(self):
        self.auth.stop()
        class WrongHead:
            def command(self, argv):
                return {'exit_code': 0, 'disposition': 'COMPLETED', 'stdout': 'b' * 40, 'stderr': ''}
        with self.assertRaisesRegex(m.Refusal, 'head mismatch'):
            m.authenticate_source(self.args.supplier, self.args.head, WrongHead())
        self.auth.start(); self.assert_no_allocate()


if __name__ == '__main__':
    unittest.main()
