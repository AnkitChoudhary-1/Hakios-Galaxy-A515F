#!/usr/bin/env python3
"""Complete source-only UEFI overlays and verification records before publication."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parents[1]
D = P / 'publication/Hakios-Galaxy-A515F-source'
UP = Path('/opt/a51-hakios/upstream-a51/hakios')


def main():
    spec = importlib.util.spec_from_file_location('exporter', P / 'scripts/prepare-requested-publication.py')
    e = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(e)
    manifest = json.loads((D / 'PUBLICATION-MANIFEST.json').read_text())
    e.D, e.files, e.excluded = D, manifest['files'], manifest['excluded_files']
    sources = json.loads((D / 'manifests/current-sources.json').read_text())
    overlay = []
    for relative in ['Mu-Silicium', 'Mu-Silicium/Mu_Basecore']:
        repo = UP / relative
        for name in sorted(e.b.candidates(repo)):
            path = repo / name
            if not path.is_file():
                continue
            if not (e.allowed(path) or path.suffix in {'.inf', '.inc', '.dec', '.dsc', '.fdf'}):
                e.excluded.append({'path': str(path), 'reason': 'UEFI_non_source_input', **e.b.pin(path.read_bytes())})
                continue
            target = 'port/current-uefi/' + relative + '/' + name
            e.emit(target, path.read_bytes(), str(path))
            overlay.append(target)
        for name in ['License.txt', 'LICENSE', 'LICENSE.txt', 'NOTICE', 'NOTICE.txt']:
            path = repo / name
            if path.is_file():
                e.emit('port/current-uefi/' + relative + '/' + name, path.read_bytes(), str(path))
    # Nested Git worktrees use .git files, which the first directory scan missed.
    rows = e.git(UP / 'Mu-Silicium', 'submodule', 'status', '--recursive').decode().splitlines()
    known = {x['path'] for x in sources['dependencies']}
    for row in rows:
        commit, name, *_ = row.strip().split()
        relative = 'Mu-Silicium/' + name
        if relative in known:
            continue
        repo = UP / relative
        sources['dependencies'].append({'path': relative, 'commit': commit.lstrip('+-'),
            'remote': e.git(repo, 'remote', 'get-url', 'origin').decode().strip(),
            'dirty': bool(e.git(repo, 'status', '--porcelain', '--untracked-files=no'))})
    sources['uefi_overlay_files'] = overlay
    e.emit('manifests/current-sources.json', (json.dumps(sources, indent=2) + '\n').encode(),
           'active Git identities and current UEFI source overlays', force=True)
    note = ('\n\n### Publication scope and patch verification supplement\n\n'
        'scripts/verify-requested-xnu-patch.py materialized pristine files at XNU commit '
        'c54f35ca767986246321eb901baf8f5ff7923f6a in an isolated WSL temporary directory. '
        'git apply --check and actual apply passed; all 269 resulting source hashes matched '
        'the current native tree. Upstream trailing whitespace warnings were preserved; '
        'no active source was changed. Receipt: evidence/publication/requested-20261124/'
        'xnu-patch-verification.json.\n\n'
        'Scope inspection found local Mu-Silicium/board and Mu_Basecore changes omitted by '
        'the initial dependency-only export. scripts/refine-requested-publication.py adds '
        'all changed/new text source as port/current-uefi overlays, retains applicable '
        'license files, and pins nested submodule revisions/remotes. Changed BMPs and DTB '
        'remain excluded binary inputs. Files normalize CRLF to LF and retain original '
        'and exported hashes. Overlay copies must target a separately checked-out pinned '
        'baseline. These older experiments are not validated by the v3 UEFI, which was '
        'retained unchanged. The final staged-byte/credential scan is required before push. '
        'Rollback: discard the separate export; active sources and device remain unchanged.\n')
    with (P / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write(note)
    e.emit('docs/IMPLEMENTATION-LOG.md', (D / 'docs/IMPLEMENTATION-LOG.md').read_bytes() + note.encode(),
           'implementation log with patch/UEFI supplement', force=True)
    for path in [P / 'scripts/verify-requested-xnu-patch.py', P / 'scripts/refine-requested-publication.py']:
        e.emit('scripts/' + path.name, path.read_bytes(), str(path))
    receipt = P / 'evidence/publication/requested-20261124/xnu-patch-verification.json'
    e.emit('validation/publication/xnu-patch-verification.json', receipt.read_bytes(), str(receipt))
    additions = {
        'docs/PUBLIC-BUILD.md': '\nLocal UEFI experiments are exported as source overlays under `port/current-uefi/`. Copy each overlay to its matching pristine Mu-Silicium/Mu_Basecore revision in `manifests/current-sources.json`, preserving file paths; supply excluded resources separately. These overlays are independent older experiments and were not rebuilt or used for v3. The current XNU patch passed an isolated apply check and exact verification of all 269 output hashes; receipt: `validation/publication/xnu-patch-verification.json`.\n',
        'docs/PUBLICATION.md': '\nThe final scope check additionally exports locally changed/new Mu-Silicium, A51 board and Mu_Basecore source as `port/current-uefi/` overlays, with nested submodule pins and original/exported hashes. Binary logo/DTB changes are excluded. XNU patch applicability and resulting hashes were independently checked on isolated pristine source.\n',
        'THIRD_PARTY_LICENSES.md': '\nCurrent `platform/` derives from speedyg2200/hakios-xnu-kernel at the commit pinned in manifests/current-sources.json. `patches/current-xnu.patch` uses pristine Apple XNU at its pinned commit, rather than the earlier prepared phase baseline. `port/current-uefi/` contains Project Silicium/Microsoft Mu/EDK II source overlays; preserve BSD-2-Clause-Patent and all embedded file notices, with upstream license texts alongside the overlays. Refer to their pinned upstream source for excluded resources and dependency terms.\n'}
    for name, addition in additions.items():
        e.emit(name, (D / name).read_bytes() + addition.encode(), 'publication scope supplement', force=True)
    syntax = 0
    for path in D.rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
        syntax += 1
    scan = e.b.scan_tree(D)
    assert scan['passed'], scan['failures']
    manifest.update(files=e.files, excluded_files=e.excluded, scan=scan, python_files_parsed=syntax)
    (D / 'PUBLICATION-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    result = {'uefi_overlay_files': len(overlay), 'dependencies': len(sources['dependencies']),
              'files': len(e.files), 'scan': scan, 'python_parsed': syntax,
              'phone_operations': False, 'active_source_changed': False}
    (P / 'evidence/publication/requested-20261124/refinement.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
