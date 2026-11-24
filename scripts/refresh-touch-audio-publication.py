#!/usr/bin/env python3
"""Refresh the existing requested source export; no device changes or push."""
import argparse
import ast
import datetime as dt
import difflib
import importlib.util
import json
from pathlib import Path
import os
import re
import subprocess

P = Path(__file__).resolve().parents[1]
D = P / 'publication/Hakios-Galaxy-A515F-source'
UP = Path('/opt/a51-hakios/upstream-a51/hakios')
E = P / 'evidence/publication/touch-audio-20261124-r1'
spec = importlib.util.spec_from_file_location('exporter', P / 'scripts/prepare-requested-publication.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def finish(manifest):
    for name in list(e.files):
        if not name.endswith('.md'):
            continue
        path = D / name
        def repair(match):
            target = match[2].strip('<>').split('#')[0]
            if not target or '://' in target or (path.parent / target).exists():
                return match[0]
            return '[' + match[1] + '](' + os.path.relpath(D / 'docs/PUBLICATION.md', path.parent).replace('\\', '/') + ')'
        raw = re.sub(r'\[([^\]\n]+)\]\(([^\)\n]+)\)', repair, path.read_text()).encode()
        path.write_bytes(raw)
        e.files[name].update(e.b.pin(raw))
    syntax = 0
    for path in D.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        syntax += 1
    scan = e.b.scan_tree(D)
    assert scan['passed'], scan['failures']
    manifest.update(files=e.files, excluded_files=e.excluded, scan=scan,
        python_files_parsed=syntax, captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        repair_revision='touch-audio-20261124-r1', phone_operations=False)
    (D / 'PUBLICATION-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {'files': len(e.files), 'python_parsed': syntax, 'scan': scan, 'phone_operations': False}


def emit(name, raw, origin):
    e.emit(name, raw, origin, force=True)


def sources():
    E.mkdir(exist_ok=True)
    manifest = json.loads((D / 'PUBLICATION-MANIFEST.json').read_text())
    if not (E / 'manifest-before.json').exists():
        (E / 'manifest-before.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (E / 'parent.txt').write_bytes(e.git(D, 'rev-parse', 'HEAD'))
    assert (E / 'parent.txt').read_bytes() == e.git(D, 'rev-parse', 'HEAD'), 'Publication parent changed'
    e.D, e.files, e.excluded = D, manifest['files'], manifest['excluded_files']
    for family in ['scripts', 'prototype', 'diagnostics', 'drivers', 'userland', 'docs', 'apps', 'manifests']:
        e.copy_family(P, family, force=True)
    selected = {}
    for row in e.git(UP, 'ls-files', '--stage', '-z').decode().split('\0'):
        if row:
            meta, name = row.split('\t', 1)
            selected[name] = meta.split()[0]
    selected.update({name: '100644' for name in ['.config', 'docs/a51_audio_bringup.md',
        'userland/rc.jobs.audio-iris', 'userland/rc.jobs.instagram', 'userland/rc.jobs.iris',
        'userland/src/app_reg.m', 'userland/src/iris_register.c']})
    for path in (UP / 'xnu/files/bsd/vfs').glob('*'):
        if path.is_file():
            selected[path.relative_to(UP).as_posix()] = '100644'
    for name, mode in sorted(selected.items()):
        path = UP / name
        if not path.is_file() or name.startswith('prebuilt/') or name.endswith('focaltech_fw.h'):
            continue
        raw = path.read_bytes()
        if name.endswith('.md'):
            raw = b'> Source snapshot note: hardware assertions below are upstream/historical. Current observed status is in ../../docs/PUBLIC-STATUS.md.\n\n' + raw
        e.emit('platform/' + name, raw, str(path), executable=mode == '100755', force=True)
    device = UP / 'devices/a51'
    names = set(e.git(device, 'ls-files', '-z').decode().split('\0')) - {''}
    for family in ['drivers/audio', 'drivers/power']:
        names.update(path.relative_to(device).as_posix() for path in (device / family).rglob('*') if path.is_file())
    for name in sorted(names):
        path = device / name
        if path.is_file():
            e.emit('platform/devices/a51/' + name, path.read_bytes(), str(path), executable=path.suffix == '.sh', force=True)
    native = UP / 'xnu-src/xnu-8796.121.2'
    patch, records = [], []
    for name in sorted(e.b.candidates(native)):
        if any(x in e.SKIP for x in Path(name).parts) or name.endswith('focaltech_fw.h'):
            continue
        source = native / name
        proc = subprocess.run(['git', '-C', str(native), 'show', 'HEAD:' + name], capture_output=True)
        before = proc.stdout if proc.returncode == 0 else b''
        after = source.read_bytes() if source.is_file() else b''
        try:
            a, z = before.decode(), after.decode()
        except UnicodeDecodeError:
            continue
        if '\0' in a + z or before == after:
            continue
        patch.extend(difflib.unified_diff(a.splitlines(True), z.splitlines(True),
            fromfile='a/' + name if proc.returncode == 0 else '/dev/null',
            tofile='b/' + name if source.is_file() else '/dev/null'))
        records.append({'path': name, 'before': e.b.pin(before), 'after': e.b.pin(after)})
    emit('patches/current-xnu.patch', ''.join(patch).encode(), 'current native cumulative adaptations')
    sources = json.loads((D / 'manifests/current-sources.json').read_text())
    for dep in sources['dependencies']:
        repo = UP / dep['path']
        dep.update(commit=e.git(repo, 'rev-parse', 'HEAD').decode().strip(),
            remote=e.git(repo, 'remote', 'get-url', 'origin').decode().strip(),
            dirty=bool(e.git(repo, 'status', '--porcelain', '--untracked-files=no')))
    sources.update(native_patch_files=records,
        common_source_commit=e.git(UP, 'rev-parse', 'HEAD').decode().strip())
    emit('manifests/current-sources.json', (json.dumps(sources, indent=2) + '\n').encode(), 'current source identities')
    # Refresh previously exported source overlays; preserve unrelated UEFI work.
    for name, record in list(e.files.items()):
        if name.startswith('port/current-uefi/') and str(record['origin']).startswith('/opt/'):
            path = Path(record['origin'])
            if path.is_file():
                e.emit(name, path.read_bytes(), str(path), executable=record['mode'] == '100755', force=True)
    packet = P / 'evidence/build-repair/touch-audio-20261124-r1'
    for name in ['manifest.json', 'adaptation.json', 'references.json', 'root-recipe.json',
                 'audio-iris-tests.json', 'touch-clock-tests.json']:
        emit('validation/touch-audio-r1/' + name, (packet / name).read_bytes(), str(packet / name))
    qemu = sorted(packet.glob('qemu-*/result.json'))[-1]
    emit('validation/touch-audio-r1/qemu.json', qemu.read_bytes(), str(qemu))
    state = json.loads((P / 'state.json').read_text())
    public = json.loads((D / 'state.json').read_text())
    public['touch_audio_repair_20261124_r1'] = state['touch_audio_repair_20261124_r1']
    emit('state.json', (json.dumps(public, indent=2) + '\n').encode(), 'selected current host/device state')
    status = '''# Current observed status — 24 November 2026

Latest user report: silent speaker audio and taps landing in the wrong place. The latest installed image pin and Iris observation are unknown while ADB is disconnected. Earlier v3/v4 installation evidence is historical; external v9 source changes are not proof of a tested image.

Implemented in r1: DT-based 0–4095 touch mapping, checked manual gates/Q-channel and PLL transitions, amplifier transfer failure gating, ordinary-memory read-only diagnostics and restored full userland/Iris registration. Sources: platform/devices/a51, patches/current-xnu.patch, scripts/repair-touch-audio.py and scripts/device-diagnostics.c.

Host verified: fresh kernel/loader; 11 audio and 4 Iris native ASan/UBSan cases; all4096 touch coordinates and64 clock patterns; all507 root and12 flashboot entries read back with clean APFS checks; image layout/pins; same kernel/loader reaches Darwin PID1/uid0 in QEMU with raw hello and audio disabled. Validation receipts: validation/touch-audio-r1/. The existing post-link XNU kext symbol-set-only exit2 remains an accepted wrapper limitation.

Candidate r1 has not been installed by this repair. Physical touch accuracy, speaker media playback, Iris icon/launch, diagnostic persistence and GPU acceleration remain unverified. Headphones, capture and route switching remain unavailable. Source audits and compilation are not hardware validation. Phase4 is in progress with its peripheral gate unpassed; storage/recovery-export blockers persist.

The new candidate restores a separate root-tree from the retained verified v3 userland image; it preserves the externally stripped active root. The public export includes authored source, recipes, docs and hashed evidence summaries. Runtime/SDK/firmware/generated phone images and private diagnostics/backups remain local. Read [r1 repair record](TOUCH-AUDIO-REPAIR-20261124.md) for exact pins, prerequisites, limits and rollback.
'''
    emit('docs/PUBLIC-STATUS.md', status.encode(), 'current r1 implementation and evidence limits')
    readme = '''# HakiOS for Galaxy A51 (SM-A515F)

Experimental A51 HakiOS source, Iris app source, build tools and documentation. The latest r1 candidate corrects touch coordinate mapping, checks speaker clock/amplifier setup, and restores full userland/Iris startup with diagnostics.

Host builds, native checks, image/APFS verification and minimal Darwin QEMU boot pass. The latest installed build is user-reported to have inaccurate touch and silent audio. The new candidate awaits TWRP installation and physical testing; audible speaker output and Iris launch are unverified.

Start with [current status](docs/PUBLIC-STATUS.md), [build scope](docs/PUBLIC-BUILD.md), [r1 repair record](docs/TOUCH-AUDIO-REPAIR-20261124.md) and [publication scope](docs/PUBLICATION.md). Exact source/dependency identities are in manifests/current-sources.json; PUBLICATION-MANIFEST.json pins exported files. The cumulative XNU patch must be applied to its pristine pinned baseline. Earlier repairs/experiments and phase records are preserved with their original scope.

This source export requires separately supplied SDK/runtime/firmware inputs to build a phone image. Generated images, vendor firmware, private logs and device backups remain local. Physical peripheral acceptance and Phase4 remain incomplete.
'''
    emit('README.md', readme.encode(), 'current r1 source export overview')
    addition = ('\n\n## Current r1 repair\n\nThe current candidate is described in '
        '[TOUCH-AUDIO-REPAIR-20261124.md](TOUCH-AUDIO-REPAIR-20261124.md). '
        'It uses a separately restored retained v3 root image and new diagnostics helper, '
        'rather than the stripped active root. Some current platform/userland sources '
        'and job recipes contain later experiments; they were not compiled into the '
        'restored v3 root. Use the r1 separate-root recipe for this candidate, rather '
        'than the older RC_JOBS recommendation above. The scripts intentionally require local '
        'retained inputs and preserve their hashes. Current physical touch/audio/Iris '
        'acceptance and diagnostic persistence are unverified. The current cumulative '
        'XNU patch supersedes the older v3 patch snapshot; an isolated pristine apply '
        'and all resulting hashes are checked before this publication.\n')
    for name in ['docs/PUBLIC-BUILD.md', 'docs/PUBLICATION.md']:
        raw = (D / name).read_bytes()
        if b'\n\n## Current r1 repair\n\n' in raw:
            raw = raw.split(b'\n\n## Current r1 repair\n\n', 1)[0]
        emit(name, raw + addition.encode(), 'current r1 publication supplement')
    result = finish(manifest)
    result.update(native_patch_files=len(records), dependencies=len(sources['dependencies']))
    (E / 'export.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


def receipts():
    manifest = json.loads((D / 'PUBLICATION-MANIFEST.json').read_text())
    e.D, e.files, e.excluded = D, manifest['files'], manifest['excluded_files']
    path = E / 'xnu-patch-verification.json'
    receipt = json.loads(path.read_text())
    assert receipt['passed']
    e.copy_family(P, 'scripts', force=True)
    for name in ['docs/IMPLEMENTATION-LOG.md', 'docs/TOUCH-AUDIO-REPAIR-20261124.md',
                 'docs/STATE.md', 'docs/INDEX.md']:
        emit(name, (P / name).read_bytes(), str(P / name))
    state = json.loads((P / 'state.json').read_text())
    repair = state['touch_audio_repair_20261124_r1']
    public = json.loads((D / 'state.json').read_text())
    public['touch_audio_repair_20261124_r1'] = repair
    emit('state.json', (json.dumps(public, indent=2) + '\n').encode(), 'selected current repair state')
    installation = repair.get('device_installation', {})
    if installation.get('boot_write_verified'):
        brief = ('R1 was flashed on 25 November 2026 from TWRP with full boot backup and '
            'matching full-partition readback. The user explicitly requested proceeding '
            'at 1% battery; USB charging was checked before staging and before writing. '
            'Recovery/DTBO remained unchanged. Physical boot completion, accurate touch, '
            'speaker playback, Iris icon/launch and diagnostic persistence await confirmation. '
            'Phase gates remain unchanged. Earlier checkpoints below retain their historical scope.')
        for name in ['README.md', 'docs/PUBLIC-STATUS.md', 'docs/TOUCH-AUDIO-REPAIR-20261124.md']:
            raw = (D / name).read_text()
            marker = '\n\n## Current installation — 25 November 2026\n\n'
            if marker not in raw:
                first, rest = raw.split('\n', 1)
                emit(name, (first + marker + brief + '\n\n' + rest.lstrip('\n')).encode(),
                    'current checked r1 installation and evidence limits')
        summary = {key: installation[key] for key in [
            'image_sha256', 'full_partition_sha256', 'boot_write_verified',
            'reboot_command_succeeded', 'recovery_dtbo_unchanged',
            'low_battery_override', 'observation_status', 'device_boot_verified', 'phase_gates_changed']}
        emit('validation/touch-audio-r1/installation.json',
            (json.dumps(summary, indent=2) + '\n').encode(), 'sanitized installation verification summary')
    emit('validation/touch-audio-r1/xnu-patch-verification.json', path.read_bytes(), str(path))
    # Preserve the v3 verification as historical evidence, select the refreshed check.
    emit('validation/publication/xnu-patch-verification.json', path.read_bytes(), str(path))
    result = finish(manifest)
    (E / 'receipt-export.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['sources', 'receipts'])
    args = parser.parse_args()
    {'sources': sources, 'receipts': receipts}[args.action]()
