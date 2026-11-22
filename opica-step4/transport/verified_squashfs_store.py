#!/usr/bin/env python3
"""Repack the pinned RH proof archive into a byte-preserving SquashFS store.

This is an input-transport gate, never a theorem-validity gate.  It streams the
compressed original archive through bounded buffers and sends validated-path
regular files to stock mksquashfs.  No complete expanded archive or input archive
is stored.  A partial filesystem is quarantined until all original compressed
bytes, all manifest entries, and every file digest have been checked.

The CLI has no override for production source identities.  Small tests call the
same implementation with a distinct explicit Pin object; their receipts are
marked fixture and cannot stand for the published supplier.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request

import zstandard as zstd

REVISION = "9036e64326acf4acfae159b96664e9708445c1d1"
BASE_URL = f"https://huggingface.co/datasets/JackMcCarthy/riemann-hypothesis-build/resolve/{REVISION}"
PREFIX = ".lake/build/lib/lean/"
CHUNK = 1024 * 1024
MAX_ZSTD_WINDOW_BYTES = 64 * 1024**2


@dataclass(frozen=True)
class Pin:
    label: str
    archive_size: int
    archive_sha256: str
    manifest_size: int
    manifest_sha256: str
    file_count: int
    expanded_bytes: int
    production: bool = False


PUBLISHED = Pin(
    "JackMcCarthy/riemann-hypothesis-build@" + REVISION,
    28638044751, "953bab5386a7849527a11960f80a2fab427c49c637d6e94cc75788dd8f40196b",
    64388496, "fb3609ad73a17102e6e3e2346c5358a9c0957bcf5945442a7e5ffaa00c441ff5",
    350374, 99269509951, True,
)


def digest_path(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def clean_path(name: str) -> str:
    # Accept tar's conventional leading ./, but no ambiguous interior syntax.
    while name.startswith("./"):
        name = name[2:]
    name = name.rstrip("/")
    if not name or name.startswith("/") or "\\" in name or any(ord(c) < 32 for c in name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    if any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError(f"Unsafe archive path components: {name!r}")
    return name


def read_manifest(data: bytes, pin: Pin) -> dict[str, str]:
    if len(data) != pin.manifest_size or hashlib.sha256(data).hexdigest() != pin.manifest_sha256:
        raise ValueError("Pinned manifest size/SHA256 mismatch")
    expected: dict[str, str] = {}
    for number, line in enumerate(data.decode("utf-8", "strict").splitlines(), 1):
        m = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if m is None:
            raise ValueError(f"Malformed manifest line {number}")
        h, name = m.groups()
        name = clean_path(name)
        if not name.startswith(PREFIX) or not name.endswith((".olean", ".ilean")):
            raise ValueError(f"Unexpected manifest entry: {name!r}")
        if name in expected:
            raise ValueError(f"Duplicate manifest entry: {name!r}")
        expected[name] = h
    if len(expected) != pin.file_count:
        raise ValueError("Pinned manifest file count mismatch")
    if pin.production:
        oleans = {n[:-6] for n in expected if n.endswith(".olean")}
        ileans = {n[:-6] for n in expected if n.endswith(".ilean")}
        if len(oleans) != 175187 or oleans != ileans:
            raise ValueError("Published olean/ilean module pairs mismatch")
    return expected


class BoundedHashReader:
    """Keep an exact digest and byte count without retaining the read bytes."""
    def __init__(self, source, limit: int):
        self.source, self.limit = source, limit
        self.count = 0
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        # All callers must stream; a negative-size request is bounded as well.
        size = CHUNK if size < 0 else min(size, CHUNK)
        data = self.source.read(size)
        self.count += len(data)
        if self.count > self.limit:
            raise ValueError("Input exceeds its pinned byte bound")
        self.digest.update(data)
        return data

    def verify(self, size: int, digest: str):
        if self.count != size or self.digest.hexdigest() != digest:
            raise ValueError("Stream size/SHA256 mismatch")


class PrefixReader:
    """Replay an already-hashed header before continuing its underlying input."""
    def __init__(self, prefix: bytes, source):
        self.prefix, self.source = prefix, source

    def read(self, size=-1):
        size = CHUNK if size < 0 else min(size, CHUNK)
        if self.prefix:
            result, self.prefix = self.prefix[:size], self.prefix[size:]
            return result
        return self.source.read(size)


class StrictTarFile(tarfile.TarFile):
    """Fail on malformed/truncated headers and nonzero data after tar EOF.

    The normal streaming tar reader can silently stop at an invalid later
    header.  Here a proper two-block zero terminator and zero padding are
    required.  GNU/PAX long-name processing remains stock tarfile behavior.
    """
    def next(self):
        if self.firstmember is not None:
            member, self.firstmember = self.firstmember, None
            return member
        if self.offset != self.fileobj.tell():
            if self.offset == 0:
                return None
            self.fileobj.seek(self.offset - 1)
            if not self.fileobj.read(1):
                raise tarfile.ReadError("Truncated member padding")
        try:
            member = self.tarinfo.fromtarfile(self)
        except tarfile.EOFHeaderError:
            if self.fileobj.read(512) != b"\0" * 512:
                raise tarfile.ReadError("Missing second zero tar terminator")
            tail_size = 0
            while tail := self.fileobj.read(CHUNK):
                tail_size += len(tail)
                if tail_size > CHUNK or any(tail):
                    raise tarfile.ReadError("Unexpected data after tar terminator")
            self._loaded = True
            return None
        except tarfile.HeaderError as exc:
            raise tarfile.ReadError(f"Invalid/truncated tar header: {exc}") from exc
        self.members.append(member)
        return member


def _limit_output(size: int):
    # Applies only to the packer child.  A too-large image fails the attempt.
    resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))


def build_store(source, manifest: bytes, pin: Pin, output: Path, *,
                mksquashfs="mksquashfs", image_max_bytes=40 * 1024**3,
                member_max_bytes=4 * 1024**3, min_free_bytes=1024**3,
                processors=2, memory_mb=512, compression_level=9,
                max_window_bytes=MAX_ZSTD_WINDOW_BYTES) -> dict:
    expected = read_manifest(manifest, pin)
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = output.with_suffix(output.suffix + ".receipt.json")
    manifest_out = output.with_suffix(output.suffix + ".files.sha256")
    if any(p.exists() or p.is_symlink() for p in (output, receipt_path, manifest_out)):
        raise ValueError("Output/receipt/manifest already exists; refusing overwrite")
    if shutil.disk_usage(output.parent).free < min_free_bytes:
        raise ValueError("Insufficient free disk for configured preflight minimum")
    started = time.monotonic()
    raw = BoundedHashReader(source, pin.archive_size)
    # Inspect the first frame's byte-size directly.  This avoids depending on
    # ambiguous documentation about max_window_size units.  The pinned 0.25.0
    # backend also enforces this byte limit on every later frame.
    if zstd.__version__ != "0.25.0":
        raise ValueError("This transport requires the tested zstandard==0.25.0 backend")
    header = raw.read(18)
    frame = zstd.get_frame_parameters(header)
    if frame.window_size > max_window_bytes:
        raise ValueError("Zstd frame window exceeds explicit byte bound")
    compressed = PrefixReader(header, raw)
    packer_path = Path(shutil.which(str(mksquashfs)) or mksquashfs).resolve(strict=True)
    seen: set[str] = set()
    total = 0
    largest = 0
    created: list[Path] = []
    with tempfile.TemporaryDirectory(prefix=".proof-store-", dir=output.parent) as staging_name:
        staging = Path(staging_name)
        partial = staging / "proof-store.partial"
        packlog = staging / "mksquashfs.log"
        command = [str(packer_path), "-", str(partial), "-tar", "-noappend", "-comp", "zstd",
                   "-Xcompression-level", str(compression_level), "-b", "64K", "-mem", f"{memory_mb}M",
                   "-processors", str(processors), "-no-progress", "-no-xattrs", "-all-root",
                   "-all-time", "0", "-mkfs-time", "0", "-exit-on-error"]
        proc = None
        try:
            with packlog.open("wb") as log:
                proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                        preexec_fn=lambda: _limit_output(image_max_bytes))
                assert proc.stdin is not None
                # zstd's largest window is explicitly bounded; the tar parser's
                # live member list is cleared after every item.
                with zstd.ZstdDecompressor(max_window_size=max_window_bytes).stream_reader(
                        compressed, read_across_frames=True, closefd=False) as decoded:
                    with StrictTarFile.open(fileobj=decoded, mode="r|") as incoming:
                        with tarfile.open(fileobj=proc.stdin, mode="w|", format=tarfile.GNU_FORMAT) as outgoing:
                            for member in incoming:
                                if member.isdir() and member.name in (".", "./"):
                                    incoming.members.clear()
                                    continue
                                name = clean_path(member.name)
                                if member.isdir():
                                    if not (name in (".lake", ".lake/build", ".lake/build/lib", ".lake/build/lib/lean")
                                            or name.startswith(PREFIX)):
                                        raise ValueError(f"Unexpected directory: {name!r}")
                                    incoming.members.clear()
                                    continue
                                if not member.isfile() or member.issparse() or name not in expected or name in seen:
                                    raise ValueError(f"Unexpected, nonregular or duplicate member: {name!r}")
                                if member.size < 0 or member.size > member_max_bytes or total + member.size > pin.expanded_bytes:
                                    raise ValueError("Member/expanded byte bound exceeded")
                                payload = incoming.extractfile(member)
                                if payload is None:
                                    raise ValueError("Missing regular file payload")
                                content = BoundedHashReader(payload, member.size)
                                target = tarfile.TarInfo(name[len(PREFIX):])
                                target.size = member.size
                                target.mode = 0o444
                                outgoing.addfile(target, content)
                                content.verify(member.size, expected[name])
                                seen.add(name)
                                total += member.size
                                largest = max(largest, member.size)
                                incoming.members.clear()
                                if len(seen) % 5000 == 0:
                                    print(json.dumps({"files":len(seen),"expected":pin.file_count,
                                        "bytes":total,"elapsed_s":round(time.monotonic()-started)}), flush=True)
                    # StrictTarFile consumes through decompressed EOF.  This
                    # second drain makes that requirement explicit as well.
                    if decoded.read(1):
                        raise ValueError("Unread data remains after tar verification")
                if raw.read(1):
                    raise ValueError("Unread compressed trailing data")
                raw.verify(pin.archive_size, pin.archive_sha256)
                if seen != expected.keys() or total != pin.expanded_bytes:
                    raise ValueError("Archive completeness/expanded-size mismatch")
                proc.stdin.close()
                if proc.wait() != 0:
                    raise RuntimeError("mksquashfs rejected input: " + packlog.read_text(errors="replace")[-4000:])
            size = partial.stat().st_size
            if not 0 < size <= image_max_bytes:
                raise ValueError("SquashFS image size outside configured bound")
            receipt = {"schema":1,"status":"VERIFIED_ARCHIVE_REPACKED",
                "proof_validity_established":False,"production_supplier":pin.production,
                "pin":pin.__dict__,"archive_bytes_checked":raw.count,
                "archive_sha256":raw.digest.hexdigest(),"files":len(seen),
                "expanded_bytes":total,"largest_member_bytes":largest,
                "image_bytes":size,"image_sha256":digest_path(partial),
                "mksquashfs_sha256":digest_path(packer_path),"zstandard_version":zstd.__version__,
                "helper_sha256":digest_path(Path(__file__).resolve()),
                "max_zstd_window_bytes":max_window_bytes,"first_frame_window_bytes":frame.window_size,
                "mksquashfs_command":command,"elapsed_s":round(time.monotonic()-started,3),
                "required_next_gate":"Read-only mount, verify every mounted file against files.sha256, then original closed theorem/proof/claim gates"}
            index = "".join(expected[n] + "  " + n[len(PREFIX):] + "\n" for n in sorted(expected))
            receipt["mounted_manifest_sha256"] = hashlib.sha256(index.encode()).hexdigest()
            # Hard-link publication is atomic and refuses a concurrent overwrite.
            partial.chmod(0o444)
            os.link(partial, output)
            created.append(output)
            with manifest_out.open("x") as f:
                f.write(index)
            created.append(manifest_out)
            with receipt_path.open("x") as f:
                json.dump(receipt, f, indent=2)
                f.write("\n")
            created.append(receipt_path)
            return receipt
        except BaseException as failure:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
            if proc is not None and proc.stdin is not None:
                try: proc.stdin.close()
                except BrokenPipeError: pass
            for p in reversed(created):
                p.unlink(missing_ok=True)
            if isinstance(failure, BrokenPipeError):
                raise RuntimeError("mksquashfs closed its input: " + packlog.read_text(errors="replace")[-4000:]) from failure
            raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, help="Existing original oleans.tar.zst; otherwise stream the pinned official URL")
    ap.add_argument("--manifest", type=Path, help="Existing original manifest; otherwise fetch the pinned official URL")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--mksquashfs", default="mksquashfs")
    ap.add_argument("--max-image-gib", type=int, default=40)
    ap.add_argument("--min-free-gib", type=int, default=45)
    ap.add_argument("--processors", type=int, default=2)
    ap.add_argument("--memory-mb", type=int, default=512)
    args = ap.parse_args()
    with ExitStack() as stack:
        if args.manifest:
            if args.manifest.stat().st_size != PUBLISHED.manifest_size:
                raise ValueError("Local published manifest has the wrong byte size")
            manifest = args.manifest.read_bytes()
        else:
            f = stack.enter_context(urllib.request.urlopen(BASE_URL + "/olean-manifest.sha256", timeout=120))
            manifest = f.read(PUBLISHED.manifest_size + 1)
        # Refuse malformed manifest before starting the large request.
        read_manifest(manifest, PUBLISHED)
        if args.archive:
            source = stack.enter_context(args.archive.open("rb"))
        else:
            source = stack.enter_context(urllib.request.urlopen(BASE_URL + "/oleans.tar.zst", timeout=120))
        receipt = build_store(source, manifest, PUBLISHED, args.output, mksquashfs=args.mksquashfs,
                    image_max_bytes=args.max_image_gib*1024**3, min_free_bytes=args.min_free_gib*1024**3,
                    processors=args.processors, memory_mb=args.memory_mb)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
