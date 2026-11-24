#!/usr/bin/env python3
"""Verify current Phase 4 host lineage and retained executions; never access a device.

This creates an indexed evidence packet only. It does not update central status,
run retained binaries, rebuild a kernel, or qualify physical peripheral gates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from phase4_support import PROJECT, command, index_packet, new_packet, pin, require, write_json


def indexed(packet):
    packet = packet.resolve()
    require(packet.is_relative_to((PROJECT / "evidence/phase-4").resolve()), "Evidence outside Phase 4")
    rows = json.loads((packet / "index.json").read_text(encoding="utf-8"))
    require(type(rows) is list and rows, "Missing packet index: " + str(packet))
    names = set()
    for row in rows:
        rel = row["path"]
        path = (packet / rel).resolve()
        require(type(rel) is str and path.is_relative_to(packet) and path != packet / "index.json"
                and rel not in names and not (packet / rel).is_symlink(), "Invalid indexed path")
        require(pin(path) == {key: row[key] for key in ("bytes", "sha256")}, "Indexed byte drift: " + str(path))
        names.add(rel)
    actual = {p.relative_to(packet).as_posix() for p in packet.rglob("*")
              if p.is_file() and p != packet / "index.json"}
    require(actual == names, "Indexed file set differs: " + str(packet))
    return len(names)


def commands_verified(packet):
    records = json.loads((packet / "commands.json").read_text(encoding="utf-8"))
    require(records and len({r["name"] for r in records}) == len(records), "Missing/duplicate commands")
    for row in records:
        require(row["exit_code"] == 0 and dt.datetime.fromisoformat(row["finished"]) >=
                dt.datetime.fromisoformat(row["started"]), "Failed/invalid command: " + row["name"])
        for stream in ("stdout", "stderr"):
            require(pin(packet / (row["name"] + "." + stream)) == row[stream], "Command output drift")
    return records


def retained_run(packet, script):
    matches = []
    for meta in (PROJECT / "runs").glob("*/metadata.json"):
        record = json.loads(meta.read_text(encoding="utf-8"))
        argv = record.get("command", [])
        if not any(str(arg).replace("\\", "/").rsplit("/", 1)[-1] == script for arg in argv):
            continue
        output = meta.parent / "output.log"
        if output.exists() and packet.name in output.read_text(encoding="utf-8", errors="replace"):
            require(record["status"] == "passed" and record["exit_code"] == 0 and "finished" in record,
                    "Unsuccessful retained wrapper run")
            require(pin(meta.parent / "project-scripts" / script) == pin(packet / "source.py"),
                    "Wrapper script does not match executed packet")
            matches.append({"run": meta.parent.relative_to(PROJECT).as_posix(),
                            "metadata": pin(meta), "output": pin(output)})
    require(len(matches) == 1, "Expected one completed matching run for " + script)
    return matches[0]


def main():
    if os.name == "nt":
        source = "/mnt/c" + str(Path(__file__).resolve()).replace("\\", "/")[2:]
        return subprocess.call(["wsl", "-d", "A51-KernelBuilder", "--", "python3", "-B", source, *sys.argv[1:]])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    packet = new_packet("host-readiness", __file__)
    result = {"schema_version": 1, "packet": packet.relative_to(PROJECT).as_posix(),
              "scope": "current source/build/reporting and simulated protocol evidence only",
              "passed": False, "device_operations": False, "phase_4_gate_passed": False,
              "selections": {}, "indexed_packets": {}, "runs": {}, "checks": {}}
    records = []
    try:
        values = {}
        for name in ("workspace", "platform-adaptation", "platform-build", "platform-qemu",
                     "peripheral-native-tests", "storage-trial-tests"):
            source = PROJECT / "manifests" / ("phase4-" + name + ".json")
            saved = packet / source.name
            shutil.copy2(source, saved)
            values[name] = json.loads(saved.read_text(encoding="utf-8"))
            result["selections"][name] = {"manifest": source.relative_to(PROJECT).as_posix(), **pin(saved)}
        workspace, adaptation, build, qemu, native, storage = [values[name] for name in
            ("workspace", "platform-adaptation", "platform-build", "platform-qemu",
             "peripheral-native-tests", "storage-trial-tests")]
        root = Path(workspace["root"]).resolve()
        require(root.is_relative_to(Path("/opt/a51-hakios/experimental/phase4-port")), "Wrong experimental root")
        require(root == Path(build["root"]) == Path(adaptation["root"]), "Source roots differ")
        revision_path = PROJECT / build["revision_result"]["path"]
        revision = json.loads(revision_path.read_text(encoding="utf-8"))
        source_capture = PROJECT / revision["captured_packet"]
        for selected in (revision_path.parent, source_capture, PROJECT / native["packet"],
                         PROJECT / build["packet"], PROJECT / qemu["packet"], PROJECT / storage["packet"]):
            result["indexed_packets"][selected.relative_to(PROJECT).as_posix()] = indexed(selected)
        for name, value in (("platform-build", build), ("platform-qemu", qemu),
                            ("peripheral-native-tests", native), ("storage-trial-tests", storage)):
            require(json.loads((PROJECT / value["packet"] / "result.json").read_text(encoding="utf-8")) == value,
                    "Manifest/result differs: " + name)
            require(value.get("device_operations", value.get("actual_device_operations")) is False,
                    "Selection is not host-only")
            require(value.get("phase_4_gate_passed", value.get("phase_4_device_gate_passed", False)) is False,
                    "Host selection claims a physical gate")
        require(build["build_verified"] is True and qemu["passed"] is True and native["passed"] is True
                and storage["passed"] is True and all(qemu["checks"].values()), "Selected check failed")
        require(pin(revision_path) == {k: build["revision_result"][k] for k in ("bytes", "sha256")}
                and adaptation["revision_packets"][-1] == revision["packet"] == build["adaptation_packet"]
                == qemu["adaptation_packet"], "Revision lineage mismatch")
        require(pin(PROJECT / "manifests/phase4-platform-adaptation.json") == build["adaptation_manifest"]
                == qemu["adaptation_manifest"] and pin(PROJECT / "manifests/phase4-workspace.json")
                == build["workspace_manifest"] and pin(PROJECT / "manifests/phase4-platform-build.json")
                == qemu["build_manifest"], "Build/QEMU input mismatch")
        require(build["source_pins"] == adaptation["source_pins"] == revision["source_pins"]
                == qemu["source_pins"] and build["adapted_sources"] == adaptation["changes"], "Source pins differ")
        for rel, expected in build["source_pins"].items():
            require(pin(PROJECT / "prototype/phase4-platform" / rel) == expected, "Template drift: " + rel)
        for row in adaptation["changes"]:
            require(row["tree"] in ("common", "native"), "Unknown source tree")
            tree = root if row["tree"] == "common" else root / "xnu-src/xnu-8796.121.2"
            path = (tree / row["path"]).resolve()
            require(path.is_relative_to(tree) and pin(path) == row["after"], "Adapted source drift")
        for rel, expected in build["artifacts"].items():
            require(pin(root / rel) == expected == pin(PROJECT / build["packet"] / "artifacts" / rel), "Artifact drift")
        for rel, expected in native["sources"].items():
            require(pin(PROJECT / "prototype/phase4-platform" / rel) == expected
                    == pin(PROJECT / native["packet"] / "sources" / rel), "Native model source drift")
        for rel, expected in storage["sources"].items():
            require(pin(PROJECT / "scripts" / rel) == expected == pin(PROJECT / storage["packet"] / rel),
                    "Storage harness source drift")
        for name, script in (("platform-build", "phase4-build-platform.py"),
                             ("platform-qemu", "phase4-qemu-platform.py"),
                             ("peripheral-native-tests", "phase4-test-peripherals.py"),
                             ("storage-trial-tests", "phase4-test-storage-trial.py")):
            selected = PROJECT / values[name]["packet"]
            require(pin(PROJECT / "scripts" / script) == pin(selected / "source.py"), "Runner drift: " + script)
            result["runs"][name] = retained_run(selected, script)
        native_packet = PROJECT / native["packet"]
        native_commands = commands_verified(native_packet)
        require(set(native["suites"]) == {"ufs", "input", "reporting"}, "Missing native suite")
        require({r["name"] for r in native_commands} == {"compiler", "ufs-compile", "ufs-execute",
                "input-compile", "input-execute", "reporting-compile", "reporting-execute"}, "Incomplete native execution")
        for suite, observed in native["suites"].items():
            require(json.loads((native_packet / (suite + "-execute.stdout")).read_text()) == observed,
                    "Native stdout differs from reported count")
            argv = next(r["argv"] for r in native_commands if r["name"] == suite + "-compile")
            require("-fsanitize=address,undefined" in argv and "-Werror" in argv, "Missing sanitizer/strict compiler")
        commands_verified(PROJECT / build["packet"])
        symbols = (PROJECT / build["packet"] / "driver-symbols.stdout").read_bytes()
        require(all(symbol in symbols for symbol in (b"_sysctl_a51_snapshot", b"_sysctl_a51_ufs_test",
                    b"_hakios_gicv2_qemu_test")), "Required driver symbol missing")
        qemu_packet = PROJECT / qemu["packet"]
        commands_verified(qemu_packet)
        require(pin(PROJECT / "scripts/phase4_reporting.py") == qemu["reporting_helper"], "Reporting helper drift")
        spec = importlib.util.spec_from_file_location("phase4_host_qemu_validator", PROJECT / "scripts/phase4-qemu-platform.py")
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        captured_record = struct.unpack_from("<9Q", (qemu_packet / "return-record.bin").read_bytes())
        log = (qemu_packet / "kernel-user.log").read_text(errors="replace").replace("\r", "")
        checks, samples = validator.validate(log, qemu["nonce"], captured_record)
        require(all(checks.values()) and all(qemu["checks"].get(k) == v for k, v in checks.items())
                and [list(row) for row in samples] == qemu["timer_samples"]
                and [hex(n) for n in captured_record] == qemu["record"]
                and qemu["qemu_exit_code"] == 0, "QEMU original-byte replay differs")
        require(storage["case_count"] == len(storage["cases"]) and all(c["passed"] and c["modeled"]
                for c in storage["cases"]), "Storage cases incomplete or not modeled")
        for label, tree in (("common", root), ("native", root / "xnu-src/xnu-8796.121.2")):
            head = command(packet, records, label + "-head", ["git", "-C", str(tree), "rev-parse", "HEAD"]).stdout.decode().strip()
            require(head == build["heads"][label], "Upstream HEAD drift")
        parent = Path(workspace["parent"]).resolve()
        require(parent.is_relative_to(Path("/opt/a51-hakios/experimental/phase3-port")), "Wrong preserved parent")
        require(all(pin(parent / rel) == expected for rel, expected in workspace["preserved"].items()), "Phase 3 parent drift")
        for name, selection in result["selections"].items():
            require(pin(PROJECT / selection["manifest"]) == {k: selection[k] for k in ("bytes", "sha256")},
                    "Manifest changed during host verification")
        result.update(passed=True, revision=revision["packet"], source_capture=revision["captured_packet"],
                      native_cases=sum(s["cases"] for s in native["suites"].values()),
                      native_checks=sum(s["checks"] for s in native["suites"].values()),
                      storage_cases=storage["case_count"], qemu_checks=len(qemu["checks"]),
                      adapted_source_files=len(adaptation["changes"]), preserved_parent_files=len(workspace["preserved"]))
        result["checks"] = {name: True for name in ("exact_packet_indexes", "current_source_lineage",
            "build_and_qemu_artifact_correspondence", "completed_wrapper_runs", "native_sanitized_stdout",
            "modeled_storage_sources_and_cases", "qemu_original_byte_replay", "required_symbols_linked",
            "upstream_heads_unchanged", "phase3_parent_preserved", "manifest_selection_stable")}
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    index_packet(packet)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
