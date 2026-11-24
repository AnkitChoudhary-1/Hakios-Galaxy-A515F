#!/usr/bin/env python3
"""Retain host input snapshots and inspect the failed Samsung/XNU package."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
WSL_ROOT = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios')
UP = WSL_ROOT / 'upstream-a51/hakios'
sys.path.insert(0, str(PROJECT / 'prototype/xnu-loader'))
from hakios_macho import BootArgs, MachOFile

def pin(path):
    data = path.read_bytes()
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def main():
    packet = PROJECT / 'evidence/build-repair' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    packet.mkdir(parents=True)
    report = {'scope': 'host audit and source snapshot; no phone writes', 'packet': str(packet), 'inputs': {}}
    sources = ['.config', 'devices/a51/configs/a51.config',
               'devices/a51/drivers/gpu/hakios.a51gpu.c', 'devices/a51/drivers/audio/hakios.a51audio.c',
               'xnuloader/loader.c', 'xnuloader/loader.efi', 'tools/make-kernel.sh',
               'xnu-src/xnu-8796.121.2/bsd/dev/hakios.a51gpu.c',
               'xnu-src/xnu-8796.121.2/bsd/dev/hakios.a51audio.c', 'hakios-kernel', 'userland/root.apfs']
    for name in sources:
        src = UP / name
        dst = packet / 'before/upstream' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        report['inputs'][name] = pin(src)
    for name in ['state.json', 'docs/STATE.md', 'docs/IMPLEMENTATION-LOG.md', 'docs/INDEX.md',
                 'artifacts/A51-HakiOS-audio-boot.img', 'artifacts/a51_xnu_loader_audio.bin']:
        src = PROJECT / name
        dst = packet / 'before/workspace' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        report['inputs'][name] = pin(src)
    for repo in ['', 'devices/a51', 'xnu-src/xnu-8796.121.2']:
        name = repo.replace('/', '-') or 'root'
        linux = '/opt/a51-hakios/upstream-a51/hakios' + ('/' + repo if repo else '')
        for cmd, suffix in [(['rev-parse', 'HEAD'], 'head.txt'), (['status', '--short'], 'status.txt'),
                            (['diff', '--binary', 'HEAD'], 'patch')]:
            p = subprocess.run(['wsl', '-d', 'A51-KernelBuilder', 'git', '-C', linux, *cmd], capture_output=True, check=True)
            (packet / (name + '.' + suffix)).write_bytes(p.stdout)
    loader = (PROJECT / 'artifacts/a51_xnu_loader_audio.bin').read_bytes()
    boot = (PROJECT / 'artifacts/A51-HakiOS-audio-boot.img').read_bytes()
    report['raw_loader_in_boot'] = loader in boot
    report['raw_loader_header_size'] = struct.unpack_from('<Q', loader, 16)[0]
    blob = (WSL_ROOT / 'experimental/a51-xnu-loader/payload_blob.bin').read_bytes()
    report['generated_blob_in_failed_loader'] = blob in loader
    ba = BootArgs.unpack(blob)
    report['failed_boot_args'] = ba.__dict__ | {'video': ba.video.__dict__}
    toc_s = (WSL_ROOT / 'experimental/a51-xnu-loader/a51_toc.S').read_text()
    (packet / 'failed-a51_toc.S').write_text(toc_s)
    report['kernel_comparisons'] = {}
    for name, path in [('latest', UP / 'hakios-kernel'), ('phase4', WSL_ROOT / 'experimental/phase4-port/20261114T150320411427Z/hakios-kernel')]:
        mf = MachOFile(path.read_bytes())
        rows = []
        for seg in mf.segments:
            if seg.filesize:
                rows.append({'segment': seg.name, 'bytes': seg.filesize, 'present_in_failed_loader': seg.data in loader})
        report['kernel_comparisons'][name] = rows
    (packet / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    (PROJECT / 'evidence/build-repair/latest-audit.txt').write_text(str(packet) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
