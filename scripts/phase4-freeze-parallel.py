#!/usr/bin/env python3
"""Freeze existing Phase 4 handoffs and the current source input set.
Run via scripts/run.py. No device operations or writes to existing worker/WSL trees.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase4_support import PROJECT, command, index_packet, new_packet, pin, require, write_json

PORT = Path('/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z')
XNU = PORT / 'xnu-src/xnu-8796.121.2'
FIRST = 'parallel/snapshots/20261117T013929281709Z-antigravity-first-handoff'
FIRST_SHA = '024b3c2add18375efca9067684054d789844439b7b005090df359aa5e8a1322a'
SUPPLEMENT = PROJECT / 'evidence/phase-4/antigravity-first-review-supplement/20261117T022721584880Z'
WORKERS = ('antigravity-phase4', 'antigravity-input', 'antigravity-review')

def copy(source, dest, expected=None):
    require(source.is_file() and not source.is_symlink(), 'Not a regular source: ' + str(source))
    actual = pin(source)
    if expected is not None:
        require(actual == expected, 'Source mismatch: ' + str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    require(pin(dest) == actual and pin(source) == actual, 'Concurrent change: ' + str(source))
    return actual

def freeze_tree(source, dest):
    files = {}
    for file in sorted(source.rglob('*')):
        require(not file.is_symlink(), 'Worker symlink requires review: ' + str(file))
        if file.is_file():
            rel = file.relative_to(source).as_posix()
            files[rel] = copy(file, dest / rel)
    return files

def inspect_processes():
    result = []
    relevant = ('make', 'ninja', 'clang', 'clang++', 'clang-18', 'clang++-18',
                'cc1', 'ld', 'ld64', 'ld.lld', 'qemu-system-aar', 'python', 'python3', 'python3.12',
                'adb', 'heimdall', 'wsl', 'wsl.exe', 'powershell.exe')
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit() or int(directory.name) == os.getpid():
            continue
        try:
            comm = (directory / 'comm').read_text().strip()
            if comm not in relevant:
                continue
            cmd = (directory / 'cmdline').read_bytes()
            argv = [part.decode('utf-8', 'replace') for part in cmd.split(b'\0') if part]
            cwd = str((directory / 'cwd').resolve(strict=True))
            result.append({'pid': int(directory.name), 'comm': comm, 'cwd': cwd,
                           'argv0': argv[0] if argv else '', 'argc': len(argv),
                           'cmdline_sha256': hashlib.sha256(cmd).hexdigest()})
        except (OSError, PermissionError):
            pass
    return result

def main():
    if os.name == 'nt':
        script = '/mnt/c' + str(Path(__file__).resolve()).replace('\\', '/')[2:]
        return subprocess.call(['wsl.exe', '-d', 'A51-KernelBuilder', '--exec', 'python3', '-B', script])
    packet = new_packet('parallel-source-freeze', __file__)
    snapshot = PROJECT / 'parallel/snapshots' / (packet.name + '-four-worker-inputs')
    snapshot.mkdir(parents=True, exist_ok=False)
    result = {'schema_version': 1, 'packet': packet.relative_to(PROJECT).as_posix(),
              'snapshot': snapshot.relative_to(PROJECT).as_posix(), 'frozen': False,
              'device_operations': False, 'existing_worker_writes': False,
              'main_source_changes': False, 'phase_4_gate_passed': False}
    records = []
    try:
        first = PROJECT / FIRST
        require(pin(first / 'MANIFEST.json')['sha256'] == FIRST_SHA, 'First snapshot drift')
        first_manifest = json.loads((first / 'MANIFEST.json').read_text())
        for rel, expected in first_manifest['antigravity_files'].items():
            require(pin(first / 'antigravity' / rel) == expected, 'First retained worker drift: ' + rel)
        manifest = {'schema_version': 1, 'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'snapshot': result['snapshot'], 'scope': 'fixed source slices, full handoffs and selected references; not a full dependency checkout',
                    'original_first_snapshot': FIRST, 'original_first_manifest': pin(first / 'MANIFEST.json'),
                    'workers': {}, 'main_files': {}, 'wsl_files': {}, 'references': {}, 'instructions': {}}
        for worker in WORKERS:
            source = PROJECT / 'parallel' / worker
            require(source.is_dir(), 'Missing existing worker: ' + worker)
            manifest['workers'][worker] = {'origin': source.relative_to(PROJECT).as_posix(),
                'files': freeze_tree(source, snapshot / 'handoffs' / worker)}
        manifest['first_worker_drift_from_retained_snapshot'] = [
            rel for rel, expected in first_manifest['antigravity_files'].items()
            if manifest['workers']['antigravity-phase4']['files'].get(rel) != expected]
        require(not manifest['first_worker_drift_from_retained_snapshot'], 'First worker changed after reviewed snapshot')
        selected = set()
        for directory in ('prototype/phase4-platform', 'drivers', 'scripts'):
            for file in (PROJECT / directory).rglob('*'):
                if file.is_file() and '__pycache__' not in file.parts:
                    selected.add(file.relative_to(PROJECT).as_posix())
        for file in (PROJECT / 'manifests').glob('phase4*.json'):
            selected.add(file.relative_to(PROJECT).as_posix())
        selected.update(('README.md', 'state.json', 'docs/STATE.md', 'docs/INDEX.md',
                         'docs/IMPLEMENTATION-LOG.md', 'docs/PHASE-4-HOST-CHECKPOINT.md',
                         'docs/PHASE-4-ANTIGRAVITY-FIRST-REVIEW.md', 'docs/PHASE-4-UFS-REPAIR.md',
                         'docs/PHASE-4-DEVICE-PATH.md', 'docs/BASELINE-RESTORATION-20261116.md'))
        for rel in sorted(selected):
            manifest['main_files'][rel] = copy(PROJECT / rel, snapshot / 'main-base' / rel)
        for label, file in [('AGENTS.md', PROJECT.parent / 'AGENTS.md'),
                            ('ROADMAP.md', PROJECT.parent / 'hakios-assessment/ROADMAP.md')]:
            manifest['instructions'][label] = copy(file, snapshot / 'instructions' / label)
        adaptation = json.loads((PROJECT / 'manifests/phase4-platform-adaptation.json').read_text())
        for change in adaptation['changes']:
            tree = XNU if change['tree'] == 'native' else PORT
            rel = change['path']
            expected = change['after']
            key = change['tree'] + '/' + rel
            manifest['wsl_files'][key] = copy(tree / rel, snapshot / 'wsl-adapted' / key, expected)
        for label, tree in (('common', PORT), ('native', XNU)):
            for name, argv in [('head', ['rev-parse', 'HEAD']),
                               ('status', ['status', '--short']),
                               ('working-diff', ['diff', '--binary', 'HEAD']),
                               ('untracked', ['ls-files', '--others', '--exclude-standard'])]:
                proc = command(packet, records, label + '-' + name,
                               ['git', '-C', str(tree), *argv], timeout=60)
                if name == 'head':
                    manifest[label + '_head'] = proc.stdout.decode().strip()
                copy(packet / (label + '-' + name + '.stdout'), snapshot / 'wsl-metadata' / (label + '-' + name + '.txt'))
            agent_files = sorted(tree.rglob('AGENTS.md'))
            manifest[label + '_agent_files'] = []
            for file in agent_files:
                if 'BUILD' in file.parts or '.git' in file.parts:
                    continue
                rel = file.relative_to(tree).as_posix()
                copy(file, snapshot / 'wsl-instructions' / label / rel)
                manifest[label + '_agent_files'].append(rel)
        require(SUPPLEMENT.is_dir(), 'Missing selected matching references')
        for item in json.loads((SUPPLEMENT / 'index.json').read_text()):
            if item['path'].startswith('references/'):
                rel = item['path'][len('references/'):]
                manifest['references'][rel] = copy(SUPPLEMENT / item['path'], snapshot / 'references' / rel,
                                                  {'bytes': item['bytes'], 'sha256': item['sha256']})
        for rel in ['tools/make-kernel.sh', 'Makefile', 'xnu-env.sh', 'drivers/map', 'drivers/core/conf']:
            if (PORT / rel).is_file() and not (PORT / rel).is_symlink():
                manifest['wsl_files']['common/' + rel] = copy(PORT / rel, snapshot / 'wsl-adapted/common' / rel)
        build_manifest = json.loads((PROJECT / 'manifests/phase4-platform-build.json').read_text())
        manifest['selected_build_manifest'] = pin(PROJECT / 'manifests/phase4-platform-build.json')
        manifest['current_artifacts'] = {}
        for rel in ('hakios-kernel', 'userland/hello'):
            manifest['current_artifacts'][rel] = pin(PORT / rel)
        processes = inspect_processes()
        write_json(packet / 'wsl-processes.json', processes)
        win = command(packet, records, 'windows-build-processes',
            ['powershell.exe', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|wsl|wslhost|make|ninja|clang|adb|heimdall|odin).*' } | Select-Object Name,ProcessId,ParentProcessId,CreationDate | ConvertTo-Json -Depth 3"],
            timeout=30, check=False)
        alias = {'windows_project': 'C:/Users/Ankit/Desktop/A51/hakios-a51',
                 'wsl_project': str(PROJECT.resolve()), 'windows_wsl_alias': '/mnt/c/Users/Ankit/Desktop/A51/hakios-a51',
                 'same_physical_project': str(PROJECT.resolve()) == '/mnt/c/Users/Ankit/Desktop/A51/hakios-a51',
                 'main_common': str(PORT.resolve()), 'main_native': str(XNU.resolve()),
                 'native_inside_common': XNU.resolve().is_relative_to(PORT.resolve()),
                 'shared_dependency_roots': ['/opt/a51-hakios/theos', '/opt/a51-hakios/toolchains'],
                 'worker_full_builds_allowed': False,
                 'reason': 'Legacy build helpers use one shared source/BUILD tree and central manifests; source snapshots are slices, not isolated complete dependency checkouts.',
                 'wsl_processes': processes, 'windows_process_query_exit_code': win.returncode}
        symlinks = []
        for root in (PORT / 'xnu-deps/host/bin', PORT / 'xnu-src/xnu-8796.121.2/BUILD/obj'):
            if root.is_dir():
                for file in sorted(root.iterdir()):
                    if file.is_symlink():
                        symlinks.append({'path': str(file), 'target': os.readlink(file),
                                         'resolved': str(file.resolve()), 'resolved_exists': file.resolve().exists()})
        alias['selected_build_symlinks'] = symlinks
        write_json(packet / 'path-audit.json', alias)
        copy(packet / 'path-audit.json', snapshot / 'PATH-AUDIT.json')
        write_json(snapshot / 'MANIFEST.json', manifest)
        for worker in WORKERS:
            for rel, expected in manifest['workers'][worker]['files'].items():
                require(pin(PROJECT / 'parallel' / worker / rel) == expected, 'Worker changed during freeze: ' + worker + '/' + rel)
        for rel, expected in manifest['main_files'].items():
            require(pin(PROJECT / rel) == expected, 'Main changed during freeze: ' + rel)
        for key, expected in manifest['wsl_files'].items():
            label, rel = key.split('/', 1)
            require(pin((XNU if label == 'native' else PORT) / rel) == expected, 'WSL changed during freeze: ' + key)
        require(alias['same_physical_project'], 'Unexpected Windows/WSL path identity')
        result.update(frozen=True, manifest=pin(snapshot / 'MANIFEST.json'),
                      workers={k: {'files': len(v['files']), 'handoff': v['files']['HANDOFF.md']} for k,v in manifest['workers'].items()},
                      main_files=len(manifest['main_files']), wsl_files=len(manifest['wsl_files']),
                      references=len(manifest['references']), path_audit=pin(packet/'path-audit.json'),
                      common_head=manifest['common_head'], native_head=manifest['native_head'],
                      selected_artifacts=manifest['current_artifacts'], worker_full_builds_allowed=False)
        write_json(packet / 'result.json', result)
        index_packet(packet)
        write_json(PROJECT / 'manifests/phase4-parallel-freeze.json', result)
        log = "\n\n## P4-045 - Freeze existing Phase 4 worker inputs (" + packet.name + ")\n\n"
        log += "Purpose/files: scripts/phase4-freeze-parallel.py, fixed main/adapted source slices and all three existing worker outputs in " + result['snapshot'] + "; manifests/phase4-parallel-freeze.json. Both first handoff and all prior verified progress are preserved. Existing worker folders and WSL/main implementation sources were read only.\n\n"
        log += "Verification: frozen=True; per-file hashes rechecked before/after copy; Windows/WSL project alias and selected shared build symlinks/processes recorded in " + result['packet'] + "/path-audit.json. Full worker XNU builds remain disabled because legacy helpers share source/BUILD outputs and central state. No phone operation or physical gate passed.\n\n"
        log += "Limitations/next: snapshots are explicit source slices, not standalone source/dependency checkouts. Review retained input and independent evidence; record corrected dispositions and issue four-worker BRIEF with private model/object output roots. Main retains full-build/device coordination.\n\n"
        log += "Rollback: withdraw only this new selection and new snapshot/script after preserving their indexed bytes; do not restore whole source trees, remove peer output or modify prior evidence. Retain this append-only log.\n"
        log_path = PROJECT / 'docs/IMPLEMENTATION-LOG.md'
        with log_path.open('a', encoding='utf-8') as out:
            out.write(log)
        print(json.dumps(result, indent=2), flush=True)
        return 0
    except Exception as exc:
        result['error'] = str(exc)
        write_json(packet / 'result.json', result)
        index_packet(packet)
        print(json.dumps(result, indent=2), flush=True)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
