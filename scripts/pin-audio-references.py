#!/usr/bin/env python3
"""Replay exact-commit reference downloads and qualify old source-audit claims."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

P = Path(__file__).resolve().parents[1]
WORK = Path('/opt/a51-hakios/build-repair/audio-iris-20261124')
COMMIT = '4bcfb0263b21b553760a3bdce542452db3184820'
EXPECTED = {'abox.h': '6173915f547134a66aff5827afa91930ea6ef6c09a344c7bad9d39a3a3a01d15',
            'abox_rdma.c': '3f758deb56f22622a8e577a0e7b8b5fb8e0c6d77ac1248f6db7ab2343e4811c5'}


def main():
    rows = []
    ref = WORK / 'reference'
    ref.mkdir(exist_ok=True)
    for name, expected in EXPECTED.items():
        url = 'https://raw.githubusercontent.com/LineageOS/android_kernel_samsung_exynos9820/' + COMMIT + '/sound/soc/samsung/abox/' + name
        raw = urllib.request.urlopen(url, timeout=30).read()
        sha = hashlib.sha256(raw).hexdigest()
        assert sha == expected and raw == (ref / name).read_bytes()
        (ref / ('pinned-' + name)).write_bytes(raw)
        rows.append({'url': url, 'commit': COMMIT, 'bytes': len(raw), 'sha256': sha, 'prior_matches': True})
    receipt = ref / 'provenance.json'
    receipt.write_text(json.dumps(rows, indent=2) + '\n')
    dest = P / 'evidence/build-repair/audio-iris-20261124-v3/reference-provenance.json'
    shutil.copy2(receipt, dest)
    doc = Path('/opt/a51-hakios/upstream-a51/hakios/docs/a51_audio_bringup.md')
    backup = WORK / 'before/docs/a51_audio_bringup.md'
    backup.parent.mkdir(parents=True, exist_ok=True)
    assert not backup.exists(), 'Preserve original audit document'
    shutil.copy2(doc, backup)
    text = doc.read_text()
    text = text.replace('**Status:** Driver Updated, Hardware Register Sequence Verified, Kernel Compiled & Linked',
                        '**Status:** Historical source/register audit; audible speaker output unverified')
    doc.write_text('> 24 November 2026 update: v2 reached the home screen per user but audio was silent. V3 host checks and flash/readback passed; live audio acceptance is pending. Historical pipeline/register assertions below are source hypotheses, not v3 hardware validation. See the workspace AUDIO-IRIS-REPAIR-20261124.md.\n\n' + text)
    after = P / 'evidence/build-repair/audio-iris-20261124-v3/after/docs/a51_audio_bringup.md'
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(doc, after)
    print(json.dumps({'references': rows, 'source_document_qualified': True, 'device_operations': False}, indent=2))


if __name__ == '__main__':
    main()
