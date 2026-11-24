#!/usr/bin/env python3
"""Build a bounded log reader in WSL using the preserved matching Android ABI."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct

from phase4_support import PROJECT, new_packet, pin, require, command, write_json, index_packet, documents


def main():
    require(os.name == "posix", "Run this host builder in A51-KernelBuilder")
    packet = new_packet("storage-reader-build", __file__)
    records = []
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": False,
              "device_operations": False, "module_load_verified": False}
    base_result = PROJECT / "evidence/phase-2/page-probe-build/20261111T124258280383Z/result.json"
    base = json.loads(base_result.read_text(encoding="utf-8"))
    root = Path(base["build_directory"])
    require(root.is_relative_to(Path("/opt/a51-hakios/diagnostics/page-probe")), "Wrong preserved ABI root")
    spec = importlib.util.spec_from_file_location("storage_elf", PROJECT / "scripts/build-page-probe.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    abi = (".config", "Module.symvers", "include/generated/utsrelease.h", "include/generated/autoconf.h",
           "include/config/auto.conf", "include/config/kernel.release")
    require(base["status"] == "passed" and all(pin(root / "out" / name) == base["original_input_pins"][name]
            for name in abi), "Preserved Android ABI changed")
    before = helper.inventory(root / "src")
    work = Path("/opt/a51-hakios/diagnostics/storage-reader") / packet.name
    work.mkdir(parents=True, exist_ok=False)
    out = work / "out"
    out.mkdir()
    env = dict(os.environ, PATH="/usr/lib/llvm-18/bin:" + os.environ["PATH"])
    try:
        for name in ("include", "scripts", "arch/arm64/include/generated"):
            dest = out / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            command(packet, records, "copy-" + name.replace("/", "-"),
                    ["cp", "-a", "--reflink=auto", str(root / "out" / name), str(dest)], timeout=120)
        for name in (".config", "Module.symvers"):
            shutil.copy2(root / "out" / name, out / name)
        module = work / "module"
        shutil.copytree(PROJECT / "diagnostics/storage-reader", module)
        shutil.copytree(module, packet / "source")
        command(packet, records, "compiler", ["clang", "--version"], env=env)
        argv = ["make", "-C", str(root / "src"), "O=" + str(out), "M=" + str(module),
                "ARCH=arm64", "LLVM=1", "LLVM_IAS=1", "CC=clang", "LD=ld.lld", "AR=llvm-ar",
                "NM=llvm-nm", "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump", "READELF=llvm-readelf",
                "CROSS_COMPILE=aarch64-linux-gnu-", "CROSS_COMPILE_ARM32=arm-linux-gnueabi-",
                "CLANG_TRIPLE=aarch64-linux-gnu-", "V=1", "-j2", "modules"]
        command(packet, records, "build", argv, env=env, timeout=240)
        ko = module / "hakios_storage_reader.ko"
        sections = helper.elf_sections(ko.read_bytes())
        info = sections[".modinfo"][1].decode().split("\0")
        vermagic = next(row.split("=", 1)[1] for row in info if row.startswith("vermagic="))
        require(vermagic == base["vermagic"], "Reader vermagic differs from installed kernel")
        symvers = {line.split()[1]: int(line.split()[0], 16)
                   for line in (out / "Module.symvers").read_text().splitlines()}
        versions, imports = sections["__versions"][1], {}
        require(versions and len(versions) % 64 == 0, "Missing symbol versions")
        for offset in range(0, len(versions), 64):
            crc = struct.unpack_from("<Q", versions, offset)[0]
            name = versions[offset + 8:offset + 64].split(b"\0", 1)[0].decode()
            require(name not in imports and symvers.get(name) == crc, "Reader import CRC differs: " + name)
            imports[name] = hex(crc)
        undefined = command(packet, records, "undefined", ["llvm-nm", "--undefined-only", str(ko)], env=env).stdout.decode()
        require({line.split()[-1] for line in undefined.splitlines()} <= set(imports), "Unversioned reader import")
        require(before == helper.inventory(root / "src") and all(
                pin(root / "out" / name) == pin(out / name) == base["original_input_pins"][name] for name in abi),
                "Reader build changed preserved source or ABI")
        target = packet / ko.name
        shutil.copy2(ko, target)
        # Retain the actual legacy source, which differs from the old host template.
        legacy = Path("/opt/a51-hakios/diagnostics/early-probe/early_probe.c")
        shutil.copy2(legacy, packet / "legacy-early-probe.c")
        for name in (".config", "Module.symvers", "include/generated/utsrelease.h"):
            shutil.copy2(out / name, packet / Path(name).name)
        result.update(passed=True, build_directory=str(work), module={"path": target.relative_to(PROJECT).as_posix(), **pin(target)},
                      source_pins={name: pin(PROJECT / "diagnostics/storage-reader" / name)
                                   for name in ("Makefile", "hakios_storage_reader.c")},
                      abi_parent={"path": base_result.relative_to(PROJECT).as_posix(), **pin(base_result)},
                      vermagic=vermagic, imported_crcs=imports, preserved_source_and_abi_unchanged=True,
                      mapping_contract="fixed reserved GNSS 0xfb000000..0xfb0201ff; header 0xfb0001e0; data 0xfb000200; source pointer metadata only; <=128KiB with explicit printable prefix/binary tail")
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    note = f"\n\n## P4-032 — Bounded GNSS assembly-log reader ({packet.name})\n\nPurpose/files: diagnostics/storage-reader and scripts/phase4-build-storage-reader.py. Read the existing assembly copy only at fixed GNSS offsets: record 0xfb000000, header 0xfb0001e0, data 0xfb000200, maximum 128 KiB. Treat the pinned original log address as metadata; never map reusable Android RAM. Emit complete printable lines with explicit full/prefix/tail lengths, including binary stackshot tails, and fail overlong lines. The harness must verify the live gnss_if reservation and compare the independently retained raw recovery console. Verification: host_build_passed={result['passed']}; error={result.get('error')}; exact source, matching vermagic/import CRCs and build output are retained in `{result['packet']}`. No device action in this builder; preservation and lifecycle require later silicon execution. Rollback: restore the storage-repair checkpoint reader and selection; preserve Android sources/ABI and historical evidence. Temporary loading requires module unload, file cleanup and restored SELinux/Android boot ID.\n"
    documents(packet, {"docs/IMPLEMENTATION-LOG.md": (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    write_json(PROJECT / "manifests/phase4-storage-reader.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
