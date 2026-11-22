#!/usr/bin/env python3
"""One opt-in read-only loop profile; resource evidence never grants proof acceptance."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import stat
import subprocess
import tempfile
import time

PROFILE = 'LOOP_RO_DIO1_ORIGINAL64K_V1'
BASE = '2d54e707ab9ac8a50c2ed3cb2fd72b4171cb21bf'
REL = 'opica-step4/resource_profiles/'
IMAGE = {'sha256': '49f7e6d407ee8bb17d55cbd5d479c0a01a0f29f40768d9f6214e8a7b3f6ea475',
         'bytes': 30748491776, 'block_bytes': 65536, 'files': 350374,
         'mounted_manifest_sha256': '4b2a2b978e16e54c663fd5c19f4cab3cd8d5a6d5a0141468efefdc6f07d1e411',
         'transport_helper_sha256': '36e330ddc0a9baae25de15d489dfbcf0c5ce8049cc472db031be58eaa1174d49'}
SINGLE = {'CONFIG_SQUASHFS_DECOMP_SINGLE': 'y', 'CONFIG_SQUASHFS_DECOMP_MULTI': 'n',
          'CONFIG_SQUASHFS_DECOMP_MULTI_PERCPU': 'n', 'CONFIG_SQUASHFS_CHOICE_DECOMP_BY_MOUNT': 'n'}
COLUMNS = 'NAME,DIO,RO,OFFSET,SIZELIMIT,LOG-SEC,BACK-FILE,BACK-INO,BACK-MAJ:MIN'
FIXED_PATH = '/usr/sbin:/usr/bin:/sbin:/bin'


class Refusal(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise Refusal(reason)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs)


def absolute(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts, 'Absolute normalized path required')
    return p


def directory_fd(path):
    p = absolute(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def regular_fd(path):
    path = absolute(path)
    parent = directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise Refusal('Expected regular file: ' + str(path))
    return fd


def identity(st):
    return {'device': st.st_dev, 'inode': st.st_ino, 'bytes': st.st_size,
            'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns}


def read_regular(path, limit=2 << 20):
    fd = regular_fd(path)
    with os.fdopen(fd, 'rb') as stream:
        before = identity(os.fstat(stream.fileno()))
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'Read exceeds bound: ' + str(path))
        require(identity(os.fstat(stream.fileno())) == before, 'File changed during read')
    return raw


def write_once(folder, name, record):
    parent = directory_fd(folder)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(record, indent=2) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(parent)


def mkdir_fresh(path):
    parent = directory_fd(path.parent)
    try:
        os.mkdir(path.name, mode=0o755, dir_fd=parent)
    finally:
        os.close(parent)


class Host:
    """Only the fixed observations and owned loop operations used by this profile."""
    def command(self, argv, timeout=30):
        require(argv[0] in {'git', 'losetup', 'mount', 'umount', 'findmnt'}, 'Unexpected tool')
        executable = shutil.which(argv[0], path=FIXED_PATH)
        require(executable is not None, 'Required tool missing: ' + argv[0])
        command = [str(Path(executable).resolve()), *map(str, argv[1:])]
        env = {'PATH': FIXED_PATH, 'LC_ALL': 'C', 'LANG': 'C', 'GIT_NO_LAZY_FETCH': '1',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
        def limits():
            resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       env=env, preexec_fn=limits, start_new_session=True)
            try:
                code, disposition = process.wait(timeout=timeout), 'COMPLETED'
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
                code, disposition = None, 'TIMED_OUT'
            out.seek(0); err.seek(0)
            stdout, stderr = out.read((1 << 20) + 1), err.read((1 << 20) + 1)
        require(len(stdout) <= 1 << 20 and len(stderr) <= 1 << 20, 'Command output exceeded bound')
        return {'argv': command, 'exit_code': code, 'disposition': disposition,
                'stdout': stdout.decode(errors='replace'), 'stderr': stderr.decode(errors='replace')}

    def text(self, path):
        with Path(path).open('rb') as stream:
            raw = stream.read(65537)
        require(len(raw) <= 65536, 'Kernel observation exceeded bound')
        return raw.decode().strip()

    def image_identity(self, path):
        fd = regular_fd(path)
        try:
            return identity(os.fstat(fd))
        finally:
            os.close(fd)

    def image_digest(self, path, expected_bytes):
        fd = regular_fd(path)
        started = time.monotonic()
        def timeout(_signum, _frame):
            raise TimeoutError('Image authentication exceeded 600 seconds')
        previous = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, 600)
        try:
            with os.fdopen(fd, 'rb') as stream:
                before = identity(os.fstat(stream.fileno()))
                require(before['bytes'] == expected_bytes, 'Wrong image size')
                count, h = 0, hashlib.sha256()
                while chunk := stream.read(4 << 20):
                    count += len(chunk)
                    require(count <= expected_bytes, 'Image exceeds size bound')
                    h.update(chunk)
                require(count == expected_bytes and identity(os.fstat(stream.fileno())) == before,
                        'Image changed during authentication')
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        require(self.image_identity(path) == before, 'Image path changed during authentication')
        return {'identity': before, 'sha256': h.hexdigest(), 'bytes_read': count,
                'elapsed_seconds': time.monotonic() - started,
                'cache_effect': 'One additional buffered image authentication read; no eviction or cold-cache claim'}

    def block_identity(self, path):
        st = os.stat(path, follow_symlinks=False)
        require(stat.S_ISBLK(st.st_mode), 'Expected a block device')
        return f'{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}'

    def context(self, image):
        release = os.uname().release
        configurations = []
        for path in ('/boot/config-' + release, '/proc/config.gz'):
            try:
                raw = read_regular(Path(path))
                if path.endswith('.gz'):
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                        raw = stream.read((2 << 20) + 1)
                require(len(raw) <= 2 << 20, 'Kernel config exceeds bound')
                values = {}
                for line in raw.decode().splitlines():
                    m = re.fullmatch(r'(CONFIG_SQUASHFS_[A-Z_]+)=([ynm])', line)
                    n = re.fullmatch(r'# (CONFIG_SQUASHFS_[A-Z_]+) is not set', line)
                    if m: values[m[1]] = m[2]
                    if n: values[n[1]] = 'n'
                configurations.append({'path': path, 'coverage': 'AVAILABLE', 'sha256': digest(raw),
                                       'values': values})
            except (OSError, ValueError, EOFError, Refusal) as exc:
                configurations.append({'path': path, 'coverage': 'UNAVAILABLE', 'error': str(exc)})
        versions = {tool: self.command([tool, '--version']) for tool in ('losetup', 'mount', 'findmnt')}
        backing = self.command(['findmnt', '--json', '--target', image, '--output',
                                'TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN'])
        return {'kernel_release': release, 'kernel_configurations': configurations,
                'versions': versions, 'backing_filesystem': backing,
                'exact_kernel_build_source': 'NOT_ESTABLISHED'}


def good_command(host, argv):
    row = host.command(argv)
    require(row['exit_code'] == 0 and row['disposition'] == 'COMPLETED',
            'Command failed: ' + json.dumps(row))
    return row


def authenticate_source(supplier, head, host):
    require(bool(re.fullmatch(r'[0-9a-f]{40}', head)), 'Full exact head required')
    git = ['git', '-c', 'safe.directory=' + str(supplier), '-C', supplier]
    require(good_command(host, [*git, 'rev-parse', 'HEAD'])['stdout'].strip() == head, 'Checkout head mismatch')
    good_command(host, [*git, 'merge-base', '--is-ancestor', BASE, head])
    names = ['opica-step4/SOURCE_MANIFEST.json', '.github/workflows/opica-combined-modular.yml',
             REL + 'loop_ro_dio1_64k.py', REL + 'loop_ro_dio1_64k.json',
             REL + 'test_loop_ro_dio1_64k.py', 'opica-step4/transport/verified_squashfs_store.py']
    raw = {}
    for name in names:
        current = read_regular(supplier / name)
        committed = good_command(host, [*git, 'show', head + ':' + name])['stdout'].encode()
        require(current == committed, 'Source differs from exact commit: ' + name)
        raw[name] = current
    require(Path(__file__).absolute() == supplier / (REL + 'loop_ro_dio1_64k.py'), 'Adapter must run from exact checkout')
    manifest = decode(raw['opica-step4/SOURCE_MANIFEST.json'])
    require(manifest['workflow_sha256'] == digest(raw['.github/workflows/opica-combined-modular.yml']),
            'Workflow source manifest mismatch')
    rows = {}
    for row in manifest['files']:
        require(row['path'] not in rows, 'Duplicate source manifest path')
        rows[row['path']] = row
    for name in names[2:]:
        row = rows[name.removeprefix('opica-step4/')]
        require(row['sha256'] == digest(raw[name]) and row['bytes'] == len(raw[name]), 'Source inventory mismatch')
    profile = decode(raw[REL + 'loop_ro_dio1_64k.json'])
    require(profile['id'] == PROFILE and profile['image'] == IMAGE and profile['single_only_kernel_config_fallback'] == SINGLE,
            'Exact resource profile changed')
    require(profile['mount_options'] == ['ro'] and profile['decompressor_threads_option'] is None,
            'Decompressor mount policy changed')
    require(digest(raw[names[-1]]) == IMAGE['transport_helper_sha256'], 'Frozen transport changed')
    return profile, {name: digest(content) for name, content in raw.items()}


def number(value, name, boolean=False):
    if isinstance(value, bool):
        require(boolean, 'Boolean is not a geometry integer: ' + name)
        return int(value)
    require((isinstance(value, int) and value >= 0) or
            (isinstance(value, str) and re.fullmatch(r'[0-9]+', value)), 'Invalid integer: ' + name)
    return int(value)


def loop_rows(host, image=None, device=None):
    argv = ['losetup', '--list', '--json', '--output', COLUMNS]
    if image is not None: argv += ['--associated', image]
    if device is not None: argv += [device]
    data = decode(good_command(host, argv)['stdout'])
    require(isinstance(data, dict) and isinstance(data.get('loopdevices'), list), 'Invalid losetup JSON')
    return data['loopdevices']


def ownership(host, device, image, image_id):
    require(bool(re.fullmatch(r'/dev/loop[0-9]+', device)), 'Unexpected loop device name')
    rows = loop_rows(host, device=device)
    require(len(rows) == 1, 'Loop identity is not unique')
    row = rows[0]
    require(row.get('name') == device and row.get('back-file') == str(image), 'Loop backing path mismatch')
    require(number(row.get('back-ino'), 'backing inode') == image_id['inode'], 'Loop backing inode mismatch')
    backing_dev = f"{os.major(image_id['device'])}:{os.minor(image_id['device'])}"
    require(row.get('back-maj:min') == backing_dev, 'Loop backing device mismatch')
    require(host.image_identity(image) == image_id, 'Backing image identity changed')
    return row, host.block_identity(device)


def mount_rows(host):
    rows = []
    unescape = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    for line in host.text('/proc/self/mountinfo').splitlines():
        left, right = line.split(' - ', 1)
        a, b = left.split(), right.split()
        rows.append({'id': a[0], 'device': a[2], 'root': unescape(a[3]), 'target': unescape(a[4]),
                     'options': a[5], 'filesystem': b[0], 'source': unescape(b[1]), 'super_options': b[2]})
    return rows


def mount_row(host, mountpoint):
    rows = [x for x in mount_rows(host) if x['target'] == str(mountpoint)]
    require(len(rows) == 1, 'Missing or ambiguous exact mountpoint')
    return rows[0]


def single_mode(mounted, context):
    settings = [x.removeprefix('threads=') for field in ('options', 'super_options')
                for x in mounted[field].split(',') if x.startswith('threads=')]
    if settings:
        require(set(settings) == {'single'}, 'Observed decompressor mode is not explicit single')
        return {'basis': 'ACTUAL_MOUNT_OPTION_THREADS_SINGLE', 'value': 'single'}
    available = [x for x in context['kernel_configurations'] if x['coverage'] == 'AVAILABLE']
    require(available and all(all(x['values'].get(k) == v for k, v in SINGLE.items()) for x in available),
            'NOT_READY_FOR_COMPARISON: absent mount option and no unambiguous single-only kernel config')
    return {'basis': 'UNAMBIGUOUS_SINGLE_ONLY_KERNEL_CONFIG', 'value': 'single'}


def observe(host, device, image, image_id, mountpoint=None, context=None):
    row, block_id = ownership(host, device, image, image_id)
    root = '/sys/class/block/' + Path(device).name
    fields = {'dio': 'loop/dio', 'ro': 'ro', 'offset': 'loop/offset', 'sizelimit': 'loop/sizelimit',
              'logical_sector': 'queue/logical_block_size', 'capacity_sectors_512': 'size'}
    values = {key: number(host.text(root + '/' + suffix), key) for key, suffix in fields.items()}
    require(host.text(root + '/dev') == block_id, 'Sysfs device identity mismatch')
    for key, column in [('dio', 'dio'), ('ro', 'ro'), ('offset', 'offset'), ('sizelimit', 'sizelimit'),
                        ('logical_sector', 'log-sec')]:
        require(values[key] == number(row.get(column), column, boolean=key in ('dio', 'ro')),
                'Sysfs/losetup disagreement: ' + key)
    require(values['dio'] == 1 and values['ro'] == 1, 'Effective DIO and device read-only must both be one')
    require(values['offset'] == 0 and values['sizelimit'] == 0, 'Loop geometry changed')
    require(values['logical_sector'] > 0 and image_id['bytes'] % values['logical_sector'] == 0,
            'Unsupported logical sector alignment')
    require(values['capacity_sectors_512'] * 512 == image_id['bytes'], 'Loop does not cover exact image size')
    result = {'device': device, 'block_device': block_id, 'loop': values, 'losetup': row,
              'image_identity': image_id}
    if mountpoint is not None:
        mounted = mount_row(host, mountpoint)
        require(mounted['source'] == device and mounted['device'] == block_id and
                mounted['filesystem'] == 'squashfs' and 'ro' in mounted['options'].split(','),
                'Mounted supplier identity/read-only mode differs')
        result['mount'] = mounted
        require(context is not None, 'Missing mode-observation context')
        result['decompressor_mode'] = single_mode(mounted, context)
    ownership(host, device, image, image_id)
    return result


def check_context(context):
    require(bool(context['kernel_release']), 'Kernel release unavailable')
    for row in context['versions'].values():
        require(row['exit_code'] == 0 and row['stdout'].strip(), 'util-linux version unavailable')
    backing = context['backing_filesystem']
    require(backing['exit_code'] == 0, 'Backing filesystem unavailable')
    rows = decode(backing['stdout']).get('filesystems', [])
    require(len(rows) == 1 and rows[0].get('fstype'), 'Backing filesystem identity invalid')


def raw_proof(work):
    rows = {}
    for label, relative in [('modular', 'verification/MODULAR_GATE_RECEIPT.json'),
                            ('independent', 'independent-verification/INDEPENDENT_RECEIPT.json')]:
        try:
            raw = read_regular(work / relative, 8 << 20)
            data = decode(raw)
            require(isinstance(data, dict), 'Proof receipt must be an object')
            rows[label] = {'sha256': digest(raw), 'status': data.get('status', 'UNKNOWN')}
        except FileNotFoundError:
            rows[label] = {'status': 'NOT_PRESENT'}
        except (OSError, ValueError, Refusal) as exc:
            rows[label] = {'status': 'UNREADABLE_OR_INVALID', 'error': str(exc)}
    return rows


class Adapter:
    def __init__(self, args, host):
        self.args, self.host = args, host
        self.work, self.supplier = absolute(args.work), absolute(args.supplier)
        self.output = self.work / 'loop-dio-resource'
        self.image, self.mount = self.work / 'proof-store.sqfs', self.work / 'proof-store'

    def base_record(self, operation):
        return {'schema': 'OPICA_LOOP_DIO_RESOURCE_OPERATION_V1', 'operation': operation, 'utc': utc(),
                'selected_profile': self.args.selection, 'requested_head': self.args.head,
                'proof_acceptance': False, 'step4_status': 'OPEN', 'rh_status': 'OPEN'}

    def authenticated(self):
        require(self.args.selection == PROFILE, 'RESOURCE_PROFILE_NOT_SELECTED')
        return authenticate_source(self.supplier, self.args.head, self.host)

    def cleanup_owned_unbound(self, device, image_id):
        row = {'attempted': False, 'scope': 'New owned device only; before proof binding'}
        try:
            require(not (self.output / 'INITIAL.json').exists(), 'Cleanup forbidden after binding')
            _, block_id = ownership(self.host, device, self.image, image_id)
            mounts = mount_rows(self.host)
            relevant = [x for x in mounts if x['target'] == str(self.mount)]
            require(len(relevant) <= 1, 'Refuse ambiguous stacked mount cleanup')
            require(not any(x['device'] == block_id and x['target'] != str(self.mount) for x in mounts),
                    'Owned loop is mounted at another target; refuse cleanup')
            if relevant:
                require(relevant[0]['source'] == device and relevant[0]['device'] == block_id,
                        'Refuse to unmount unrelated mount')
                good_command(self.host, ['umount', self.mount])
            require(not any(x['device'] == block_id for x in mount_rows(self.host)), 'Loop remains mounted')
            ownership(self.host, device, self.image, image_id)
            row['attempted'] = True
            row['detach'] = self.host.command(['losetup', '--detach', device])
            row['status'] = 'DETACH_REQUEST_SUCCEEDED' if row['detach']['exit_code'] == 0 else 'DETACH_FAILED'
        except (OSError, ValueError, Refusal) as exc:
            row.update(status='CLEANUP_REFUSED_OR_FAILED', error=str(exc))
        return row

    def setup(self):
        profile, source_hashes = self.authenticated()
        mkdir_fresh(self.output)
        row = self.base_record('setup')
        row.update(status='STARTED_NOT_BOUND', source_hashes=source_hashes)
        write_once(self.output, 'SETUP_STARTED.json', row)
        device, image_id = None, None
        try:
            context = self.host.context(self.image)
            row['context'] = context
            check_context(context)
            receipt_raw = read_regular(self.work / 'proof-store.sqfs.receipt.json')
            receipt = decode(receipt_raw)
            require(receipt['status'] == 'VERIFIED_ARCHIVE_REPACKED' and receipt['production_supplier'] is True,
                    'Fresh production transport receipt required')
            for key in ('image_sha256', 'image_bytes', 'files', 'mounted_manifest_sha256', 'helper_sha256'):
                expected = {'image_sha256': IMAGE['sha256'], 'image_bytes': IMAGE['bytes'], 'files': IMAGE['files'],
                            'mounted_manifest_sha256': IMAGE['mounted_manifest_sha256'],
                            'helper_sha256': IMAGE['transport_helper_sha256']}[key]
                require(receipt.get(key) == expected, 'Transport identity mismatch: ' + key)
            cmd = receipt['mksquashfs_command']
            require(cmd[cmd.index('-b') + 1] == '64K', 'Wrong image block profile')
            row['transport_receipt_sha256'] = digest(receipt_raw)
            row['image_authentication'] = self.host.image_digest(self.image, IMAGE['bytes'])
            require(row['image_authentication']['sha256'] == IMAGE['sha256'], 'Actual image SHA256 mismatch')
            image_id = row['image_authentication']['identity']
            require(not loop_rows(self.host, image=self.image), 'Image already associated with a loop')
            mount_fd = directory_fd(self.mount)
            try: require(not os.listdir(mount_fd), 'Mountpoint is not empty')
            finally: os.close(mount_fd)
            require(not any(x['target'] == str(self.mount) for x in mount_rows(self.host)), 'Mountpoint is already mounted')
            allocation = self.host.command(['losetup', '--find', '--show', '--read-only', '--direct-io=on',
                                            '--offset', '0', '--sizelimit', '0', self.image])
            row['allocation'] = allocation
            require(allocation['exit_code'] == 0, 'Direct-I/O loop allocation failed')
            device = allocation['stdout'].strip()
            require(bool(re.fullmatch(r'/dev/loop[0-9]+', device)), 'Allocation did not return one loop')
            ownership(self.host, device, self.image, image_id)
            write_once(self.output, 'OWNED_LOOP.json', {'device': device, 'image_identity': image_id,
                       'head': self.args.head, 'profile': PROFILE, 'proof_bound': False})
            require(len(loop_rows(self.host, image=self.image)) == 1, 'Concurrent image loop association')
            row['pre_mount'] = observe(self.host, device, self.image, image_id)
            row['mount_request'] = self.host.command(['mount', '-t', 'squashfs', '-o', 'ro', device, self.mount])
            require(row['mount_request']['exit_code'] == 0, 'Read-only mount failed')
            row['mounted'] = observe(self.host, device, self.image, image_id, self.mount, context)
            row['status'] = 'READY_FOR_ORIGINAL_FILE_VERIFICATION_NOT_BOUND'
            code = 0
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, Refusal) as exc:
            row.update(status='INVALID_TREATMENT', error_type=type(exc).__name__, error=str(exc))
            if device is not None and image_id is not None:
                row['cleanup'] = self.cleanup_owned_unbound(device, image_id)
            code = 2
        row['completed_utc'] = utc()
        write_once(self.output, 'SETUP_RESULT.json', row)
        return code, row

    def binding(self):
        try:
            return self._binding()
        except (OSError, ValueError, KeyError, TypeError, AttributeError, Refusal) as exc:
            row = self.base_record('bind')
            row.update(status='RESOURCE_BINDING_REFUSED', error_type=type(exc).__name__, error=str(exc))
            write_once(self.output, 'BIND_FAILURE.json', row)
            return 2, row

    def _binding(self):
        _, sources = self.authenticated()
        setup = decode(read_regular(self.output / 'SETUP_RESULT.json'))
        require(setup['status'] == 'READY_FOR_ORIGINAL_FILE_VERIFICATION_NOT_BOUND' and
                setup['requested_head'] == self.args.head and setup['source_hashes'] == sources, 'Setup is not qualified')
        verified = decode(read_regular(self.work / 'mounted-store-verified.json'))
        require(verified.get('status') == 'PASS' and verified.get('files') == IMAGE['files'] and
                verified.get('manifest_sha256') == IMAGE['mounted_manifest_sha256'], 'Original file sweep missing')
        context = self.host.context(self.image)
        check_context(context)
        require(context == setup['context'], 'Host support context changed before binding')
        initial = observe(self.host, setup['mounted']['device'], self.image,
                          setup['image_authentication']['identity'], self.mount, context)
        require(initial == setup['mounted'], 'Loop or mount changed before binding')
        row = self.base_record('bind')
        row.update(status='INITIAL_RESOURCE_IDENTITY_BOUND', identity=initial, context=context,
                   source_hashes=sources, setup_sha256=digest(read_regular(self.output / 'SETUP_RESULT.json')))
        write_once(self.output, 'INITIAL.json', row)
        return 0, row

    def final(self):
        row = self.base_record('final')
        row['raw_proof_step_outcomes'] = {'modular': self.args.modular_outcome, 'independent': self.args.independent_outcome}
        row['raw_proof_receipts'] = raw_proof(self.work)
        if not self.work.exists(): mkdir_fresh(self.work)
        if not self.output.exists(): mkdir_fresh(self.output)
        try:
            if self.args.selection == 'none':
                row['status'] = 'RESOURCE_PROFILE_NOT_SELECTED'
                code = 0
            else:
                _, sources = self.authenticated()
                initial_raw = read_regular(self.output / 'INITIAL.json')
                initial = decode(initial_raw)
                require(initial['requested_head'] == self.args.head and initial['source_hashes'] == sources,
                        'Initial source binding differs')
                before = initial['identity']
                context = self.host.context(self.image)
                check_context(context)
                after = observe(self.host, before['device'], self.image, before['image_identity'], self.mount, context)
                row.update(initial_sha256=digest(initial_raw), observed_identity=after, observed_context=context)
                require(after == before and context == initial['context'], 'Resource identity/context drifted')
                row['status'] = 'FINAL_RESOURCE_IDENTITIES_UNCHANGED'
                code = 0
        except (OSError, ValueError, KeyError, TypeError, AttributeError, Refusal) as exc:
            row.update(status='INVALID_OR_UNOBSERVED_RESOURCE_TREATMENT', error_type=type(exc).__name__, error=str(exc))
            code = 2
        row['scope'] = 'Snapshot resource equality only; no continuous monitoring, proof acceptance or physical-I/O guarantee'
        write_once(self.output, 'FINAL.json', row)
        return code, row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['selection', 'setup', 'bind', 'final'])
    p.add_argument('--selection', required=True)
    p.add_argument('--supplier', type=Path)
    p.add_argument('--head')
    p.add_argument('--work', type=Path)
    p.add_argument('--modular-outcome', default='NOT_AVAILABLE')
    p.add_argument('--independent-outcome', default='NOT_AVAILABLE')
    args = p.parse_args()
    try:
        require(args.selection in ('none', PROFILE), 'Unknown resource selector')
        if args.operation == 'selection':
            require(args.selection == PROFILE, 'RESOURCE_PROFILE_NOT_SELECTED: refuse before bootstrap')
            code, result = 0, {'status': 'EXPLICIT_RESOURCE_PROFILE_SELECTED', 'profile': PROFILE, 'proof_acceptance': False}
        else:
            require(args.supplier is not None and args.head is not None and args.work is not None, 'Missing exact source/work inputs')
            adapter = Adapter(args, Host())
            operation = adapter.binding if args.operation == 'bind' else getattr(adapter, args.operation)
            code, result = operation()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, Refusal) as exc:
        code, result = 2, {'status': 'REFUSED_OR_UNAVAILABLE', 'operation': args.operation,
                           'error_type': type(exc).__name__, 'error': str(exc), 'proof_acceptance': False}
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
