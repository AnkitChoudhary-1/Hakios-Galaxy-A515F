#!/usr/bin/env python3
"""Build and retain only the isolated Phase 4 kernel and static Darwin probe."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase4_support import PROJECT, require, pin, new_packet, command, documents, write_json, index_packet


def verify_sources(root, adaptation):
    for change in adaptation["changes"]:
        require(change["tree"] in ("native", "common"), "Unknown source tree")
        tree = (root / "xnu-src/xnu-8796.121.2" if change["tree"] == "native" else root).resolve()
        path = (tree / change["path"]).resolve()
        require(path.is_relative_to(tree) and pin(path) == change["after"],
                "Adapted source drift: " + change["path"])
    for name, expected in adaptation["source_pins"].items():
        require(pin(PROJECT / "prototype/phase4-platform" / name) == expected, "Template drift: " + name)


def main():
    if os.name == "nt":
        source = "/mnt/c" + str(Path(__file__).resolve()).replace("\\", "/")[2:]
        return subprocess.call(["wsl", "-d", "A51-KernelBuilder", "--", "python3", "-B", source])
    workspace = json.loads((PROJECT / "manifests/phase4-workspace.json").read_text())
    adaptation_path = PROJECT / "manifests/phase4-platform-adaptation.json"
    adaptation_raw = adaptation_path.read_bytes()
    adaptation = json.loads(adaptation_raw)
    root = Path(workspace["root"]).resolve()
    require(adaptation["applied"] and adaptation["root"] == str(root), "No matching adaptation")
    require(root.is_relative_to(Path("/opt/a51-hakios/experimental/phase4-port")), "Wrong root")
    verify_sources(root, adaptation)
    latest_revision = adaptation.get("revision_packets", [adaptation["packet"]])[-1]
    revision_path = PROJECT / latest_revision / "result.json"
    revision_raw = revision_path.read_bytes()
    revision = json.loads(revision_raw)
    require(revision["applied"] and revision["root"] == str(root) and
            revision["source_pins"] == adaptation["source_pins"], "Latest source revision differs from adaptation")
    packet = new_packet("platform-build", __file__)
    inputs = packet / "inputs"
    inputs.mkdir()
    (inputs / "adaptation-manifest.json").write_bytes(adaptation_raw)
    (inputs / "revision-result.json").write_bytes(revision_raw)
    shutil.copy2(PROJECT / "manifests/phase4-workspace.json", inputs / "workspace-manifest.json")
    result = {"root": str(root), "packet": packet.relative_to(PROJECT).as_posix(), "build_verified": False,
        "adaptation_packet": latest_revision, "initial_adaptation_packet": adaptation["packet"],
        "adaptation_manifest": pin(inputs / "adaptation-manifest.json"),
        "revision_result": {"path": latest_revision + "/result.json", **pin(inputs / "revision-result.json")},
        "workspace_manifest": pin(inputs / "workspace-manifest.json"),
        "source_pins": adaptation["source_pins"], "adapted_sources": adaptation["changes"],
        "device_operations": False, "phase_4_gate_passed": False}
    records = []
    for rel in ("hakios-kernel", "userland/hello", ".config", "xnu-build.log"):
        path = root / rel
        if path.is_file():
            dest = packet / "before" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    env = dict(os.environ, THEOS="/opt/a51-hakios/theos",
               MAKEFLAGS="MAKEJOBS=--jobs=2 SHELL=/bin/bash",
               PATH="/usr/lib/llvm-18/bin:" + os.environ["PATH"])
    try:
        require(pin(adaptation_path) == result["adaptation_manifest"] and
                pin(revision_path) == pin(inputs / "revision-result.json") and
                pin(PROJECT / "manifests/phase4-workspace.json") == result["workspace_manifest"],
                "Build input manifest changed during retention")
        for change in adaptation["changes"]:
            tree = root / "xnu-src/xnu-8796.121.2" if change["tree"] == "native" else root
            saved = packet / "sources" / change["tree"] / change["path"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tree / change["path"], saved)
            require(pin(saved) == change["after"], "Source changed during build capture")
        result["heads"] = {}
        for label, tree in (("common", root), ("native", root / "xnu-src/xnu-8796.121.2")):
            result["heads"][label] = command(packet, records, label + "-head-before",
                ["git", "-C", str(tree), "rev-parse", "HEAD"]).stdout.decode().strip()
        print("Building isolated Phase 4 kernel; complete stdout/stderr will be retained in " + str(packet), flush=True)
        command(packet, records, "kernel", ["bash", "tools/make-kernel.sh", "-j2", "MAKEJOBS=--jobs=2", "SHELL=/bin/bash"],
                timeout=1800, cwd=root, env=env)
        command(packet, records, "hello", ["make", "hello", "SHELL=/bin/bash"], timeout=120, cwd=root, env=env)
        identification = command(packet, records, "artifact-identification", ["file", "hakios-kernel", "userland/hello"], cwd=root)
        print(identification.stdout.decode(), flush=True)
        symbols = command(packet, records, "driver-symbols", ["llvm-nm", "hakios-kernel"], cwd=root, env=env).stdout
        require(b"_sysctl_a51_snapshot" in symbols and b"_hakios_gicv2_qemu_test" in symbols, "New driver/test not linked")
        result["artifacts"] = {}
        for rel in ("hakios-kernel", "userland/hello", ".config", "xnu-build.log"):
            dest = packet / "artifacts" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, dest)
            result["artifacts"][rel] = pin(dest)
        result["parent_unchanged"] = all(pin(Path(workspace["parent"]) / rel) == expected
            for rel, expected in workspace["preserved"].items())
        require(result["parent_unchanged"], "Phase 3 parent changed")
        verify_sources(root, adaptation)
        require(pin(adaptation_path) == result["adaptation_manifest"] and
                pin(revision_path) == pin(inputs / "revision-result.json") and
                pin(PROJECT / "manifests/phase4-workspace.json") == result["workspace_manifest"],
                "Build input manifest changed during compilation")
        for label, tree in (("common", root), ("native", root / "xnu-src/xnu-8796.121.2")):
            actual = command(packet, records, label + "-head-after",
                ["git", "-C", str(tree), "rev-parse", "HEAD"]).stdout.decode().strip()
            require(actual == result["heads"][label], "Upstream HEAD changed during compilation")
        result["source_and_manifest_stable"] = True
        result["build_verified"] = True
    except Exception as exc:
        result["error"] = str(exc)
        for name in ("kernel.stdout", "kernel.stderr", "hello.stdout", "hello.stderr"):
            path = packet / name
            if path.is_file():
                for line in path.read_text(errors="replace").splitlines():
                    if "error:" in line or "make-kernel:" in line or "fatal error" in line:
                        print(line[:300], flush=True)
    finally:
        write_json(packet / "result.json", result)
        write_json(PROJECT / "manifests/phase4-platform-build.json", result)
        state = json.loads((PROJECT / "state.json").read_text())
        state["phase_4_build"] = {"result": result["packet"] + "/result.json", "verified": result["build_verified"], "error": result.get("error")}
        state["next_action"] = "verify_phase4_qemu_reporting_and_guards" if result["build_verified"] else "resolve_phase4_build_failure"
        log = f"\n\n## P4-007 — Build isolated Phase 4 diagnostics\n\nPurpose/files: scripts/phase4-build-platform.py, isolated build outputs, build manifest, state and this log. Retain the current adaptation manifest, latest applied revision, every adapted source, template pins and upstream HEADs; reject drift before/after compilation. Verification: build_verified={result['build_verified']}; error={result.get('error')}; exact commands/output/exit/times, previous outputs and new artifacts are retained in `{result['packet']}`. The build is attributed to `{latest_revision}`, with the initial adaptation retained as history. A51 snapshot and SPI test symbols must be linked; the writable foreign UFS driver remains disabled. No phone operation occurred. QEMU and A51 execution remain pending and Phase 4 remains incomplete. Rollback/rebuild: select this packet's before outputs or the untouched Phase 3 tree; reproduce the retained source adaptation and execute this builder through scripts/run.py. Preserve failure output and all baseline/evidence pins.\n"
        documents(packet, {"state.json": json.dumps(state, indent=2) + "\n",
            "docs/IMPLEMENTATION-LOG.md": (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text() + log})
        index_packet(packet)
    print(json.dumps({k: v for k, v in result.items() if k not in ("artifacts", "adapted_sources", "source_pins")}, indent=2), flush=True)
    return 0 if result["build_verified"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
