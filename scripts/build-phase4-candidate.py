#!/usr/bin/env python3
"""Build and reconstruct the Phase 4 candidate boot image with UFS multi-block fix."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parent
SCRIPTS = PROJECT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from samsung_boot_dry_run import reconstruct_in_memory

ROLLBACK_PATH = WORKSPACE / "everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img"
OUTPUT_CANDIDATE = PROJECT / "artifacts/hakios-candidate-p4-fixed-boot.img"
NONCE = "9f7a1e2b4d6c8e0a1b3c5e7f9a2b4d6e"

def main():
    print("=== Building Phase 4 Candidate Payload in WSL (APFS Root) ===")
    cmdline = f"rd=md0 root_apfs=ufs_darwin -v cpus=1 serial=0 debug=0x104008 loader_return_after=600 hakios_run_nonce={NONCE} hakios_kver=p4-exynos9611-apfs fb_threads=1 fb_decon=0x148B0000"
    pack_cmd = [
        "wsl", "-d", "A51-KernelBuilder",
        "python3", "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51/prototype/xnu-loader/pack_a51_payload.py",
        "--kernel", "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/hakios-kernel",
        "--hello", "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/root.apfs",
        "--output", "/tmp/a51_xnu_loader_p4_fixed.bin",
        "--checkpoint", "0",
        "--cmdline", cmdline,
        "--pad-to", "36334080",
        "--recovery-envelope"
    ]
    res = subprocess.run(pack_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error packing payload:\n{res.stderr}", file=sys.stderr)
        return 1
    print(res.stdout)

    print("=== Reconstructing Candidate Boot Image ===")
    template_bytes = ROLLBACK_PATH.read_bytes()
    raw_loader = Path("//wsl.localhost/A51-KernelBuilder/tmp/a51_xnu_loader_p4_fixed.bin").read_bytes()
    cand_bytes, recon_dict = reconstruct_in_memory(template_bytes, raw_loader)

    OUTPUT_CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_CANDIDATE.write_bytes(cand_bytes)

    cand_sha = hashlib.sha256(cand_bytes).hexdigest()
    single_sha = hashlib.sha256(cand_bytes[:4096]).hexdigest()
    multi_sha = hashlib.sha256(cand_bytes[:65536]).hexdigest()

    print(f"Candidate written to: {OUTPUT_CANDIDATE}")
    print(f"  Size: {len(cand_bytes)} bytes")
    print(f"  SHA-256: {cand_sha}")
    print(f"  Single 4k SHA-256: {single_sha}")
    print(f"  Multi 64k SHA-256: {multi_sha}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
