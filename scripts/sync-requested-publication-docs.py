#!/usr/bin/env python3
"""Refresh explicit reviewed documentation/script exports and their manifest."""
import importlib.util
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
D = P / 'publication/Hakios-Galaxy-A515F-source'


def main():
    spec = importlib.util.spec_from_file_location('exporter', P / 'scripts/prepare-requested-publication.py')
    e = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(e)
    manifest = json.loads((D / 'PUBLICATION-MANIFEST.json').read_text())
    e.D, e.files, e.excluded = D, manifest['files'], manifest['excluded_files']
    for name in ['scripts/publish-requested-source.py', 'scripts/record-requested-publication.py',
                 'scripts/sync-requested-publication-docs.py',
                 'docs/IMPLEMENTATION-LOG.md']:
        path = P / name
        e.emit(name, path.read_bytes(), str(path), force=True)
    state = json.loads((P / 'state.json').read_text())
    publication = state.get('source_publication_20261124')
    if publication:
        public_state = json.loads((D / 'state.json').read_text())
        public_state['source_publication_20261124'] = publication
        e.emit('state.json', (json.dumps(public_state, indent=2) + '\n').encode(),
               'selected state with first publication receipt', force=True)
        note = ('\n\nSource was published to the requested repository on main at initial commit `'
                + publication['commit'] + '`, independently verified against remote main. '
                'A subsequent documentation commit records this receipt; it does not change '
                'the v3 image or any hardware acceptance gate. Speaker audio and Iris acceptance '
                'remain pending.\n')
        for name in ['README.md', 'docs/PUBLIC-STATUS.md', 'docs/PUBLICATION.md']:
            raw = (D / name).read_bytes()
            if note.encode() not in raw:
                e.emit(name, raw + note.encode(), 'initial publication receipt', force=True)
    scan = e.b.scan_tree(D)
    assert scan['passed'], scan['failures']
    manifest.update(files=e.files, scan=scan)
    (D / 'PUBLICATION-MANIFEST.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    print(json.dumps({'files': len(e.files), 'scan': scan,
                      'first_publication_receipt_included': bool(publication)}, indent=2))


if __name__ == '__main__':
    main()
