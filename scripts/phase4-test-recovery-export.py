#!/usr/bin/env python3
"""Execute the production stackless recovery exporter against independent bytes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zlib

from phase4_support import PROJECT, command, documents, index_packet, new_packet, pin, require, write_json

SOURCES = ("prototype/xnu-loader/a51_recovery_export.S", "prototype/xnu-loader/xnu_trampoline.h",
           "prototype/xnu-loader/tests/recovery_export_entry.S",
           "prototype/xnu-loader/tests/recovery_export_test.c",
           "prototype/xnu-loader/tests/recovery_export.ld", "scripts/phase4-test-recovery-export.py")


def fixture(log_pa, length):
    # Host zlib supplies the independent CRC; the guest never recomputes it.
    log = bytes((index * 73 + length) & 255 for index in range(length))
    record = struct.pack("<32Q", 0x32454c5241494b48, 1, 256, 6, 0, 0, log_pa, length,
                         1, 0xc0, 0x30d00800, 26000000, 0x410fd034,
                         0x83000000, 0x84500000, 0, 0x83012340, *([0] * 15))
    payload = record + log
    header = struct.pack("<8s4I", b"HKUFSR01", 1, 256, length, 32 + len(payload))
    return header + struct.pack("<II", zlib.crc32(header + payload), 0x31434b48) + payload


def generate(work, packet):
    cases = []
    def add(name, *, length=64, record=0x81000000, log=0x81001000,
            pmsg=0xf9e90000, console=0xf9d90000, rc=0, mutation=0,
            stage_record=None, stage_log=None, fixture_length=None):
        if stage_record is None: stage_record = record if rc == 0 else 0x81000000
        if stage_log is None: stage_log = log if rc == 0 else 0x81001000
        cases.append(dict(name=name, length=length, record=record, log=log, pmsg=pmsg, console=console,
                          rc=rc, mutation=mutation, stage_record=stage_record, stage_log=stage_log,
                          fixture_length=fixture_length if fixture_length is not None else length))
    for length in (1, 7, 256, 4096, 8193, 131072):
        add("exact_binary_" + str(length), length=length)
    add("source_upper_edges", length=131072, record=0xbfffff00, log=0xbffc0000)
    add("last_log_byte", length=1, record=0xbfff0000, log=0xbfffffff)
    add("last_32bit_destination", pmsg=0xfff80000)
    for name, args in (
        ("null_pmsg", {"pmsg": 0}), ("null_console", {"console": 0}),
        ("unaligned_pmsg", {"pmsg": 0xf9e90001}), ("unaligned_console", {"console": 0xf9d90008}),
        ("destination_equal", {"console": 0xf9e90000}),
        ("destination_overlap", {"console": 0xf9e90040}),
        ("destination_reverse_overlap", {"pmsg": 0xf9d90040}),
        ("destination_32bit_overflow", {"pmsg": 0xfff80040}),
        ("zero_log", {"length": 0, "fixture_length": 64}),
        ("oversize_log", {"length": 131073, "fixture_length": 64}),
        ("log_length_wrap", {"length": 0xffffffffffffffff, "fixture_length": 64}),
        ("unaligned_record", {"record": 0x81000001}),
        ("low_record", {"record": 0x7ffffff8}), ("null_record", {"record": 0}),
        ("high_record", {"record": 0xbfffff08}),
        ("low_log", {"log": 0x7fffffff}), ("null_log", {"log": 0}),
        ("high_log", {"log": 0xc0000000}),
        ("log_span_overflow", {"log": 0xbfffffff}),
        ("pmsg_overlaps_record", {"pmsg": 0x81000000}),
        ("console_overlaps_record", {"console": 0x81000000}),
        ("pmsg_overlaps_log", {"pmsg": 0x81001000}),
        ("console_overlaps_log", {"console": 0x81001000}),
        ("wrong_record_magic", {"mutation": 1}), ("wrong_record_version", {"mutation": 2}),
        ("wrong_record_size", {"mutation": 3}), ("record_log_pointer_mismatch", {"mutation": 4}),
        ("record_log_length_mismatch", {"mutation": 5}),
    ):
        add(name, rc=-22, **args)
    assembly = ['.section .rodata, "a", %progbits\n']
    header = []
    entries = []
    for index, case in enumerate(cases):
        raw = fixture(case["stage_log"], case["fixture_length"])
        name = "expected-" + str(index) + ".bin"
        (work / name).write_bytes(raw)
        shutil.copy2(work / name, packet / name)
        symbol = "recovery_fixture_" + str(index)
        assembly.append(f'.balign 8\n.global {symbol}\n{symbol}:\n.incbin "{work / name}"\n')
        header.append(f"extern const unsigned char {symbol}[];\n")
        values = [json.dumps(case["name"])] + [hex(case[key]) + "ULL" for key in
            ("record", "log", "pmsg", "console", "stage_record", "stage_log", "length")]
        values += [str(case["mutation"]), str(case["rc"]), symbol, str(len(raw))]
        entries.append("    {" + ", ".join(values) + "},\n")
    header.append("static const struct recovery_case recovery_cases[] = {\n" + "".join(entries) + "};\n")
    (work / "generated_cases.h").write_text("".join(header))
    (work / "generated_fixtures.S").write_text("".join(assembly))
    shutil.copy2(work / "generated_cases.h", packet / "generated_cases.h")
    shutil.copy2(work / "generated_fixtures.S", packet / "generated_fixtures.S")
    write_json(packet / "cases.json", cases)
    return len(cases)


def main():
    if os.name == "nt":
        script = "/mnt/c" + str(Path(__file__).resolve()).replace("\\", "/")[2:]
        return subprocess.call(["wsl", "-d", "A51-KernelBuilder", "--exec", "python3", "-B", script])
    packet = new_packet("recovery-export-qemu", __file__)
    work = Path("/opt/a51-hakios/experimental/recovery-export-tests") / packet.name
    work.mkdir(parents=True, exist_ok=False)
    records = []
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "work": str(work), "passed": False,
              "device_operations": False, "sources": {name: pin(PROJECT / name) for name in SOURCES}}
    try:
        for name in SOURCES:
            destination = packet / "sources" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT / name, destination)
        count = generate(work, packet)
        source = packet / "sources/prototype/xnu-loader"
        env = dict(os.environ, PATH="/usr/lib/llvm-18/bin:" + os.environ["PATH"])
        command(packet, records, "compiler", ["clang", "--version"], env=env)
        result["executions"] = {}
        for alignment in (0, 1):
            mode = "alignment-" + str(alignment)
            executable = work / ("test-" + mode + ".elf")
            command(packet, records, "compile-" + mode, ["clang", "--target=aarch64-none-elf", "-mcpu=cortex-a53",
            "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-mgeneral-regs-only", "-O2",
            "-mstrict-align", "-DRECOVERY_TEST_ALIGNMENT=" + str(alignment),
            "-Wall", "-Wextra", "-Werror", "-nostdlib", "-fuse-ld=lld", "-Wl,--build-id=none",
            "-Wl,-T," + str(source / "tests/recovery_export.ld"), "-I" + str(source), "-I" + str(work),
            str(source / "a51_recovery_export.S"), str(source / "tests/recovery_export_entry.S"),
            str(source / "tests/recovery_export_test.c"), str(work / "generated_fixtures.S"),
            "-o", str(executable)], env=env, timeout=60)
            shutil.copy2(executable, packet / executable.name)
            trace = work / (mode + "-exceptions.log")
            execution = command(packet, records, "execute-" + mode, ["qemu-system-aarch64", "-M",
            "virt,gic-version=2,secure=off,virtualization=off", "-cpu", "cortex-a53", "-smp", "1", "-m", "4G",
            "-accel", "tcg", "-display", "none", "-serial", "none", "-monitor", "none", "-no-reboot",
            "-d", "int", "-D", str(trace), "-semihosting-config", "enable=on,target=native",
            "-device", f"loader,file={executable},cpu-num=0"],
            env=env, timeout=45, check=False)
            shutil.copy2(trace, packet / trace.name)
            observed = execution.stdout + execution.stderr
            rows = re.findall(rb'^\{"suite":"recovery-export".+\}$', observed, re.M)
            run = {"exit_code": execution.returncode, "executable": pin(packet / executable.name),
                   "trace": pin(packet / trace.name)}
            result["executions"][mode] = run
            require(execution.returncode == 0 and len(rows) == 1,
                    "Recovery exporter execution failed with " + mode)
            report = json.loads(rows[0])
            run["report"] = report
            require(report["passed"] and report["cases"] == count and report["checks"] > count and
                    report["alignment_checks"] == alignment and
                    report["sctlr"] & (1 | 2 | 4 | 0x1000) == 0x1000 | (alignment << 1),
                "Recovery exporter did not execute every case")
        report = {"suite": "recovery-export", "cases": count * 2,
                  "checks": sum(run["report"]["checks"] for run in result["executions"].values()),
                  "alignment_modes": [0, 1], "mmu_off": True, "dcache_off": True,
                  "icache_on": True, "passed": True}
        require(all(pin(PROJECT / name) == expected for name, expected in result["sources"].items()),
                "Recovery exporter source changed during execution")
        result.update(passed=True, report=report)
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    note = (f"\n\n## P4-038 — Execute exact recovery-envelope exporter ({packet.name})\n\n"
        "Purpose/files: prototype/xnu-loader/{a51_recovery_export.S,xnu_trampoline.h,xnu_trampoline.S,"
        "pack_a51_payload.py,tests/recovery_export*}, scripts/phase4-test-recovery-export.py, "
        "phase4_storage.py, phase4-storage-trial.py and phase4-test-storage-trial.py. Publish a bounded, "
        "committed CRC32 envelope containing the loader record and complete binary log to audited pmsg, "
        "with a separate raw console copy. Decode/capture before Android restoration; pin exporter execution "
        "and package configuration. Exact leaf runs in QEMU with SP=0, x19–x29 preservation, independent "
        "host-zlib expected bytes, full-zone canaries, source preservation and invalid-input rejection. "
        "Both SCTLR alignment settings are exercised with MMU/data cache disabled and I-cache enabled; "
        "the guest verifies that state and exception traces are retained. "
        f"Verification: passed={result['passed']}; report={result.get('report')}; error={result.get('error')}; "
        f"packet `{result['packet']}`. This establishes emulated exporter behavior; recovery survival and UFS "
        "hardware remain separate gates. Rollback: use storage checkpoint 20261115T212201791095Z for "
        "existing sources and remove newly introduced test files/selection; preserve every silicon packet, "
        "the Phase 3 parent and Android baselines. Rebuild/test via scripts/run.py. No device operation.\n")
    documents(packet, {"docs/IMPLEMENTATION-LOG.md":
        (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    write_json(PROJECT / "manifests/phase4-recovery-export-qemu.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "sources"}, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
