#!/usr/bin/env python3
"""Create the requested source snapshot in a NEW empty publication clone (WSL).

No device operations or Git push. Preserve active sources and old publication.
"""
import ast
import datetime as dt
import difflib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

P = Path(__file__).resolve().parents[1]
UP = Path('/opt/a51-hakios/upstream-a51/hakios')
D = P / 'publication/Hakios-Galaxy-A515F'
spec = importlib.util.spec_from_file_location('publication_helpers', P / 'scripts/prepare-publication.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
# Allow only a CI token VARIABLE URL, never a literal token/password.
b.SECRET_PATTERNS['credential_url'] = re.compile(r'https?://[^\s/@]+:(?!\$(?:\{[A-Z_]+\}|[A-Z_]+)@)[^\s/@]+@')
SKIP = {'.git', '__pycache__', 'build', 'BUILD', 'EXPORT_HDRS', 'OBJ', 'SYM', 'prebuilt', 'firmware', 'fw-a51'}
EXTRA = {'.m', '.mm', '.hpp', '.metal', '.html', '.css', '.js', '.plist', '.xml', '.txt', '.toml', '.y', '.l', '.mk', '.cmake', '.iig', '.list', '.ps1', '.bat'}
files, excluded = {}, []


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def allowed(path):
    return b.allowed(path) or path.suffix in EXTRA or path.name.startswith('rc.') or path.name in {'LICENSE', 'NOTICE', 'VERSION', '.gitignore', '.gitattributes', 'meson.build'}


def emit(name, raw, origin, executable=False, force=False):
    target = D / name
    if target.exists() and not force:
        raise ValueError('Duplicate export: ' + name)
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError:
        excluded.append({'path': origin, 'reason': 'binary', **b.pin(raw)})
        return
    if '\0' in content or len(raw) > 8 * 1024 * 1024:
        excluded.append({'path': origin, 'reason': 'binary_or_oversize', **b.pin(raw)})
        return
    clean = b.sanitize(content, Path(name) if name.endswith('.md') else None).replace('\r\n', '\n').encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(clean)
    files[name] = {'origin': origin, 'original': b.pin(raw), **b.pin(clean), 'mode': '100755' if executable else '100644', 'transformed': clean != raw}


def copy_family(root, family, prefix='', force=False):
    for source in sorted((root / family).rglob('*')):
        rel = source.relative_to(root)
        if source.is_file() and not any(x in SKIP for x in rel.parts) and allowed(rel):
            emit(prefix + rel.as_posix(), source.read_bytes(), str(source), source.suffix == '.sh', force)


def main():
    import argparse
    global D
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', default=str(D))
    D = Path(parser.parse_args().destination).resolve()
    assert D.parent == (P / 'publication').resolve(), 'Destination outside publication directory'
    assert (D / '.git').is_dir() and not [x for x in D.iterdir() if x.name != '.git'], 'Require empty NEW clone'
    assert git(D, 'remote', 'get-url', 'origin').decode().strip() == 'https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F.git'
    # Retain earlier authored port patches and license material as historical inputs.
    old = P / 'publication/hakios-SM-A515F'
    for family in ['port', 'patches', 'LICENSES']:
        copy_family(old, family)
    for family in ['scripts', 'prototype', 'diagnostics', 'drivers', 'userland', 'docs', 'apps', 'manifests']:
        copy_family(P, family)
    for name in ['README.md', 'AGENTS.md', 'LICENSE', 'LICENSE.APSL', 'NOTICE', 'CONTRIBUTING.md', 'THIRD_PARTY_LICENSES.md', '.gitattributes']:
        source = old / name
        if source.exists():
            emit(name, source.read_bytes(), str(source))
    emit('docs/ROADMAP.md', (P.parent / 'hakios-assessment/ROADMAP.md').read_bytes(), 'hakios-assessment/ROADMAP.md')
    # Common checkout: tracked source/build recipes plus the explicitly reviewed new adaptations.
    stages = git(UP, 'ls-files', '--stage', '-z').decode().split('\0')
    selected = {}
    for row in stages:
        if row:
            meta, name = row.split('\t', 1)
            selected[name] = meta.split()[0]
    new = ['docs/a51_audio_bringup.md', 'userland/rc.jobs.audio-iris', 'userland/rc.jobs.instagram', 'userland/rc.jobs.iris',
           'userland/src/app_reg.m', 'userland/src/iris_register.c']
    new += [x.relative_to(UP).as_posix() for x in (UP / 'xnu/files/bsd/vfs').glob('*') if x.is_file()]
    selected.update({name: '100644' for name in new})
    selected['.config'] = '100644'
    for name, mode in sorted(selected.items()):
        source = UP / name
        if not source.is_file():
            continue
        if name.startswith('prebuilt/') or name.endswith('focaltech_fw.h'):
            excluded.append({'path': str(source), 'reason': 'generated_binary_or_vendor_firmware', **b.pin(source.read_bytes())})
            continue
        raw = source.read_bytes()
        if name.endswith('.md'):
            raw = b'> Source snapshot note: hardware assertions below are upstream/historical. Current observed status is in ../../docs/PUBLIC-STATUS.md.\n\n' + raw
        emit('platform/' + name, raw, str(source), mode == '100755')
    device = UP / 'devices/a51'
    device_names = set(git(device, 'ls-files', '-z').decode().split('\0'))
    device_names.update(x.relative_to(device).as_posix() for family in ['drivers/audio', 'drivers/power'] for x in (device / family).rglob('*') if x.is_file())
    for name in sorted(device_names - {''}):
        source = device / name
        if source.is_file():
            emit('platform/devices/a51/' + name, source.read_bytes(), str(source), source.suffix == '.sh')
    # Full current native adaptations against pinned pristine Apple XNU, not a vendor binary tree.
    native = UP / 'xnu-src/xnu-8796.121.2'
    names = b.candidates(native)
    patch = []
    patch_files = []
    for name in sorted(names):
        source = native / name
        if any(x in SKIP for x in Path(name).parts) or name.endswith('focaltech_fw.h'):
            continue
        tracked = subprocess.run(['git', '-C', str(native), 'cat-file', '-e', 'HEAD:' + name], capture_output=True).returncode == 0
        before = git(native, 'show', 'HEAD:' + name) if tracked else b''
        after = source.read_bytes() if source.is_file() else b''
        try:
            a, z = before.decode(), after.decode()
        except UnicodeDecodeError:
            continue
        if '\0' in a + z or before == after:
            continue
        patch.extend(difflib.unified_diff(a.splitlines(True), z.splitlines(True), fromfile='a/' + name if tracked else '/dev/null', tofile='b/' + name if source.is_file() else '/dev/null'))
        patch_files.append({'path': name, 'before': b.pin(before), 'after': b.pin(after)})
    emit('patches/current-xnu.patch', ''.join(patch).encode(), 'active native cumulative adaptations')
    dependencies = []
    for root, dirs, _ in os.walk(UP):
        if '.git' in dirs:
            repo = Path(root)
            dependencies.append({'path': repo.relative_to(UP).as_posix(), 'commit': git(repo, 'rev-parse', 'HEAD').decode().strip(),
                'remote': git(repo, 'remote', 'get-url', 'origin').decode().strip(), 'dirty': bool(git(repo, 'status', '--porcelain', '--untracked-files=no'))})
        dirs[:] = [x for x in dirs if x not in {'.git', 'BUILD', 'OBJ', 'SYM', 'root', 'runtime', 'sdks', 'host', '__pycache__', 'prebuilt'}]
    emit('manifests/current-sources.json', (json.dumps({'dependencies': dependencies, 'native_patch_files': patch_files, 'common_source_commit': git(UP, 'rev-parse', 'HEAD').decode().strip()}, indent=2) + '\n').encode(), 'active Git identities')
    for name in ['manifest.json', 'audio-iris-tests.json', 'adaptation.json']:
        source = P / 'evidence/build-repair/audio-iris-20261124-v3' / name
        emit('validation/audio-iris-v3/' + name, source.read_bytes(), str(source))
    qemu = sorted((P / 'evidence/build-repair/audio-iris-20261124-v3').glob('qemu-*/result.json'))[-1]
    emit('validation/audio-iris-v3/qemu.json', qemu.read_bytes(), str(qemu))
    reference = P / 'evidence/build-repair/audio-iris-20261124-v3/reference-provenance.json'
    emit('validation/audio-iris-v3/reference-provenance.json', reference.read_bytes(), str(reference))
    # Maintainer documents describe this current export, overriding old-repo front matter.
    for source in sorted((P / 'publication/requested-templates').rglob('*')):
        if source.is_file():
            emit(source.relative_to(P / 'publication/requested-templates').as_posix(), source.read_bytes(), str(source), force=True)
    state = json.loads((P / 'state.json').read_text())
    public = {k: state[k] for k in ['schema_version', 'updated_date_local', 'target', 'active_phase', 'phase_1_status', 'phase_2_status', 'phase_3_status', 'phase_4_status', 'planned_phases', 'phase_4_device_gate_passed', 'audio_iris_repair_20261124']}
    emit('state.json', (json.dumps(public, indent=2) + '\n').encode(), 'selected current state')
    # Explain all absent local evidence links without publishing personal captures.
    for name in list(files):
        if not name.endswith('.md'):
            continue
        path = D / name
        def repair(m):
            target = m[2].strip('<>').split('#')[0]
            if not target or '://' in target or (path.parent / target).exists():
                return m[0]
            return '[' + m[1] + '](' + os.path.relpath(D / 'docs/PUBLICATION.md', path.parent).replace('\\', '/') + ')'
        raw = re.sub(r'\[([^\]\n]+)\]\(([^\)\n]+)\)', repair, path.read_text()).encode()
        path.write_bytes(raw)
        files[name].update(b.pin(raw))
    syntax = 0
    for path in D.rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
        syntax += 1
    scan = b.scan_tree(D)
    assert scan['passed'], scan['failures']
    report = {'repository': 'https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F', 'captured_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'files': files, 'excluded_files': excluded, 'scan': scan, 'python_files_parsed': syntax, 'phone_operations': False,
              'source_snapshot_not_complete_runtime': True, 'self_excluded_from_hashes': True}
    (D / 'PUBLICATION-MANIFEST.json').write_text(json.dumps(report, indent=2) + '\n')
    packet = P / 'evidence/publication/requested-20261124'
    packet.mkdir(exist_ok=False)
    (packet / 'export.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'bytes': sum(x['bytes'] for x in files.values()), 'dependencies': len(dependencies), 'native_patch_files': len(patch_files), 'python_parsed': syntax, 'scan': scan}, indent=2))


if __name__ == '__main__':
    main()
