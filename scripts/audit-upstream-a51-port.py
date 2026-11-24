#!/usr/bin/env python3
"""Capture a reproducible, host-only audit of the upstream Galaxy A51 port.

Run this script inside the A51-KernelBuilder WSL distribution through run.py.
It reads the active upstream checkout, retained build runs, toolchain and SDK. It
never contacts, reboots, writes, stages or flashes a phone.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKOUT = Path("/opt/a51-hakios/upstream-a51/hakios")
DEFAULT_SDK = Path("/opt/a51-hakios/theos/sdks/iPhoneOS16.5.sdk")
DEFAULT_UEFI = Path("Mu-Silicium/Build/a51Pkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd")
DEFAULT_KERNEL = Path("hakios-kernel")

EXPECTED_REPOSITORIES = {
    ".": {
        "role": "hakios",
        "expected_state": "clean",
        "expected_commit": "14b7cdbe502f9ca5e1481cf1e6c7890fe8d3343a",
    },
    "devices/a51": {
        "role": "a51_device_overlay_source",
        "expected_state": "clean",
        "expected_commit": "0773636aea5de1c246e2cb3a72b2cb824c5b7316",
    },
    "uefi": {
        "role": "hakios_uefi_overlay_source",
        "expected_state": "clean",
        "expected_commit": "26fe9a2844e0c2c852dca79cb173091744ba8aae",
    },
    "Mu-Silicium": {
        "role": "generated_uefi_overlay",
        "expected_state": "overlay",
        "expected_commit": "e51cd877e31c8fbb322032dc4cb6715e83d25ad3",
    },
    "Mu-Silicium/Mu_Basecore": {
        "role": "generated_uefi_basecore_overlay",
        "expected_state": "overlay",
        "expected_commit": "cfb93724a06ff86ff5ba971413368a7809ee42a5",
    },
    "xnu-src/xnu-8796.121.2": {
        "role": "generated_hakios_a51_xnu_overlay",
        "expected_state": "overlay",
        "expected_commit": "c54f35ca767986246321eb901baf8f5ff7923f6a",
    },
}

RUN_PINS = [
    ("uefi_clean_integrity", "20261119T102442938364Z-upstream-a51-uefi-clean-integrity-gate"),
    ("uefi_overlay_application", "20261119T102554914585Z-upstream-a51-uefi-apply-hakios-and-a51-overlay"),
    ("nasm_adaptation", "20261119T103030258440Z-upstream-a51-uefi-system-nasm-workaround"),
    ("uefi_build", "20261119T103049730380Z-upstream-a51-uefi-build-a51-release-attempt-1"),
    ("xnu_build", "20261119T103700042168Z-upstream-a51-xnu-build-a51-attempt-1"),
    ("repository_status", "20261119T104659150209Z-upstream-a51-repository-status-audit"),
]

EXPECTED_CONFIG_SHA256 = "72b228f50e0c78e6a19bc42932d057901a2d4e92792fb7649a8df490ad61f30d"
EXPECTED_KERNEL_SHA256 = "38ea0ee0c6bf38bbc0c3a5ac2f60b28dd2bdbf1a058a3130a2bdd79750093f33"
EXPECTED_KERNEL_SIZE = 15048864
EXPECTED_UEFI_SHA256 = "038283aa0f0afcda6058e44b7331febd31cbc990bce0456c408bc9be17250ec1"
EXPECTED_UEFI_SIZE = 2097152
EXPECTED_NASM_STATE_SHA256 = "e191bc0a4c46e0317f42fd9080021b885617a69dc854f1955388defcee71b587"
EXPECTED_SDK_COMMIT = "0222fd5413cf4b9af096f37b4621afa2688572f7"

PACKAGE_NAMES = [
    "7zip",
    "acpica-tools",
    "binutils-aarch64-linux-gnu",
    "build-essential",
    "clang",
    "device-tree-compiler",
    "gcc-aarch64-linux-gnu",
    "git",
    "lld",
    "lz4",
    "make",
    "meson",
    "nasm",
    "python3",
    "python3-pip",
    "python3-venv",
    "qemu-system-arm",
]

TOOL_COMMANDS = [
    ("git", ["git", "--version"]),
    ("python3", ["python3", "--version"]),
    ("venv_python", [str(DEFAULT_CHECKOUT / "venv/bin/python"), "--version"]),
    ("clang", ["clang", "--version"]),
    ("clang++", ["clang++", "--version"]),
    ("ld.lld", ["ld.lld", "--version"]),
    ("lld-link", ["lld-link", "--version"]),
    ("aarch64-linux-gnu-gcc", ["aarch64-linux-gnu-gcc", "--version"]),
    ("aarch64-linux-gnu-ld", ["aarch64-linux-gnu-ld", "--version"]),
    ("make", ["make", "--version"]),
    ("nasm", ["nasm", "-v"]),
    ("ndisasm", ["ndisasm", "-v"]),
    ("dtc", ["dtc", "--version"]),
    ("qemu-system-aarch64", ["qemu-system-aarch64", "--version"]),
    ("theos_ld", ["/opt/a51-hakios/theos/toolchain/linux/iphone/bin/ld", "-v"]),
]

MACHO_COMMANDS = {
    0x1: "LC_SEGMENT",
    0x2: "LC_SYMTAB",
    0x5: "LC_UNIXTHREAD",
    0x19: "LC_SEGMENT_64",
    0x1B: "LC_UUID",
    0x1D: "LC_CODE_SIGNATURE",
    0x22: "LC_DYLD_INFO",
    0x80000022: "LC_DYLD_INFO_ONLY",
    0x26: "LC_FUNCTION_STARTS",
    0x29: "LC_DATA_IN_CODE",
    0x2A: "LC_SOURCE_VERSION",
    0x2B: "LC_DYLIB_CODE_SIGN_DRS",
    0x80000028: "LC_MAIN",
    0x32: "LC_BUILD_VERSION",
    0x35: "LC_FILESET_ENTRY",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> bytes:
    payload = json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path) -> dict:
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def payload_identity(relative: str, payload: bytes) -> dict:
    return {"path": relative, "size": len(payload), "sha256": sha256_bytes(payload)}


def run_command(argv: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"command failed ({result.returncode}): {argv!r}: {stderr}")
    return result


def decode(payload: bytes) -> str:
    return payload.decode("utf-8", errors="surrogateescape")


def git_bytes(repo: Path, *args: str, check: bool = True) -> bytes:
    return run_command(["git", "-C", str(repo), *args], check=check).stdout


def git_text(repo: Path, *args: str, check: bool = True) -> str:
    return decode(git_bytes(repo, *args, check=check)).strip()


def relative_to(root: Path, path: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    require(resolved.is_relative_to(root_resolved), f"path outside checkout: {path}")
    rel = resolved.relative_to(root_resolved).as_posix()
    return rel or "."


def redact_remote(value: str) -> str:
    if "://" not in value:
        return value
    parsed = urlsplit(value)
    netloc = parsed.netloc
    if "@" in netloc:
        netloc = "<redacted>@" + netloc.rsplit("@", 1)[1]
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def discover_git_worktrees(root: Path) -> list[Path]:
    require(root.is_dir(), f"missing checkout: {root}")
    result = run_command(["find", str(root), "-name", ".git", "-print0"])
    roots: dict[str, Path] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        marker = Path(os.fsdecode(raw))
        candidate = marker.parent
        probe = run_command(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"], check=False)
        if probe.returncode != 0:
            continue
        top = Path(decode(probe.stdout).strip()).resolve()
        require(top.is_relative_to(root.resolve()), f"Git worktree escaped checkout: {top}")
        roots[str(top)] = top
    return sorted(roots.values(), key=lambda path: (relative_to(root, path) != ".", relative_to(root, path)))


def parse_status_paths(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    parts = payload.split(b"\0")
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        require(len(item) >= 4 and item[2:3] == b" ", "invalid Git porcelain record")
        code = item[:2].decode("ascii", errors="replace")
        path = decode(item[3:])
        records[path] = code
        if "R" in code or "C" in code:
            if index < len(parts) and parts[index]:
                index += 1
    return records


def nul_paths(payload: bytes) -> list[str]:
    return [decode(item) for item in payload.split(b"\0") if item]


def base_git_entry(repo: Path, relative: str) -> dict | None:
    payload = git_bytes(repo, "ls-tree", "-z", "HEAD", "--", relative)
    if not payload:
        return None
    first = payload.split(b"\0", 1)[0]
    metadata, _, recorded_path = first.partition(b"\t")
    mode, kind, object_id = metadata.decode("ascii").split(" ")
    return {
        "mode": mode,
        "type": kind,
        "object": object_id,
        "path": decode(recorded_path),
    }


def working_entry(repo: Path, relative: str, category: str, status_code: str | None) -> dict:
    path = repo / relative
    entry = {
        "path": relative,
        "category": category,
        "status": status_code,
        "base": base_git_entry(repo, relative),
    }
    try:
        info = path.lstat()
    except FileNotFoundError:
        entry["working"] = {"type": "deleted"}
        return entry
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        payload = os.fsencode(target)
        entry["working"] = {
            "type": "symlink",
            "mode": oct(mode),
            "target": target,
            "size": len(payload),
            "sha256": sha256_bytes(payload),
        }
    elif stat.S_ISREG(info.st_mode):
        entry["working"] = {
            "type": "file",
            "mode": oct(mode),
            "size": info.st_size,
            "sha256": sha256_file(path),
        }
    elif stat.S_ISDIR(info.st_mode):
        nested = run_command(["git", "-C", str(path), "rev-parse", "HEAD"], check=False)
        nested_status = run_command(
            ["git", "-C", str(path), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            check=False,
        )
        entry["working"] = {
            "type": "git_worktree" if nested.returncode == 0 else "directory",
            "mode": oct(mode),
            "head": decode(nested.stdout).strip() if nested.returncode == 0 else None,
            "dirty": bool(nested_status.stdout) if nested_status.returncode == 0 else None,
        }
    else:
        entry["working"] = {"type": "special", "mode": oct(mode), "size": info.st_size}
    return entry


def repo_expectation(relative: str) -> dict:
    return EXPECTED_REPOSITORIES.get(
        relative,
        {"role": "nested_dependency", "expected_state": "clean", "expected_commit": None},
    )


def repository_snapshot(root: Path, repo: Path, issues: list[str]) -> tuple[dict, dict[str, bytes]]:
    relative = relative_to(root, repo)
    expectation = repo_expectation(relative)
    head = git_text(repo, "rev-parse", "HEAD")
    branch_probe = run_command(["git", "-C", str(repo), "symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    branch = decode(branch_probe.stdout).strip() if branch_probe.returncode == 0 else None
    status_short = git_bytes(repo, "status", "--short", "--branch", "--untracked-files=all")
    porcelain = git_bytes(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    status_map = parse_status_paths(porcelain)
    dirty = bool(porcelain)

    remotes = []
    for name in git_text(repo, "remote").splitlines():
        fetch = run_command(["git", "-C", str(repo), "remote", "get-url", "--all", name], check=False)
        push = run_command(["git", "-C", str(repo), "remote", "get-url", "--push", "--all", name], check=False)
        remotes.append(
            {
                "name": name,
                "fetch": [redact_remote(line) for line in decode(fetch.stdout).splitlines()],
                "push": [redact_remote(line) for line in decode(push.stdout).splitlines()],
            }
        )

    tracked = sorted(set(nul_paths(git_bytes(repo, "diff", "--name-only", "-z", "HEAD", "--"))))
    untracked = sorted(set(nul_paths(git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z"))))
    entries = [working_entry(repo, path, "tracked", status_map.get(path)) for path in tracked]
    entries.extend(working_entry(repo, path, "untracked", status_map.get(path)) for path in untracked)
    inventory_value = {"schema_version": 1, "repository": relative, "entries": entries}
    inventory_payload = json_bytes(inventory_value)
    patch_payload = git_bytes(repo, "diff", "--binary", "--full-index", "HEAD", "--")

    commit_matches = expectation["expected_commit"] in (None, head)
    state_matches = (not dirty) if expectation["expected_state"] == "clean" else dirty
    if not commit_matches:
        issues.append(f"repository commit mismatch: {relative}: {head}")
    if not state_matches:
        issues.append(
            f"repository state mismatch: {relative}: expected {expectation['expected_state']}, dirty={dirty}"
        )

    record = {
        "path": relative,
        "absolute_path": str(repo),
        "role": expectation["role"],
        "expected_state": expectation["expected_state"],
        "expected_commit": expectation["expected_commit"],
        "head": head,
        "branch": branch,
        "detached": branch is None,
        "remotes": remotes,
        "dirty": dirty,
        "commit_matches": commit_matches,
        "state_matches": state_matches,
        "status_porcelain": {"size": len(porcelain), "sha256": sha256_bytes(porcelain)},
        "tracked_changed_paths": len(tracked),
        "untracked_paths": len(untracked),
    }
    return record, {
        "status.txt": status_short,
        "tracked.patch": patch_payload,
        "inventory.json": inventory_payload,
    }


def collect_repositories(root: Path, packet: Path | None, issues: list[str]) -> dict:
    worktrees = discover_git_worktrees(root)
    records = []
    for repo in worktrees:
        record, payloads = repository_snapshot(root, repo, issues)
        relative = record["path"]
        evidence_dir = Path("repositories/root" if relative == "." else "repositories") / (
            Path() if relative == "." else Path(relative)
        )
        evidence = {}
        for name, payload in payloads.items():
            if name != "status.txt" and not record["dirty"]:
                continue
            relpath = (evidence_dir / name).as_posix()
            evidence[name] = payload_identity(relpath, payload)
            if packet is not None:
                target = packet / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
        record["evidence"] = evidence
        records.append(record)
    return {
        "schema_version": 1,
        "checkout": str(root),
        "repository_count": len(records),
        "dirty_repository_count": sum(1 for item in records if item["dirty"]),
        "all_expected_commits_match": all(item["commit_matches"] for item in records),
        "all_expected_states_match": all(item["state_matches"] for item in records),
        "repositories": records,
    }


def macho_version(value: int) -> str:
    return f"{(value >> 16) & 0xffff}.{(value >> 8) & 0xff}.{value & 0xff}"


def parse_macho(path: Path) -> dict:
    data = path.read_bytes()
    magic = data[:4]
    magics = {
        b"\xcf\xfa\xed\xfe": ("<", "MH_MAGIC_64"),
        b"\xfe\xed\xfa\xcf": (">", "MH_CIGAM_64"),
    }
    require(magic in magics, f"not a 64-bit Mach-O image: {path}")
    endian, magic_name = magics[magic]
    require(len(data) >= 32, "truncated Mach-O header")
    _, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from(
        endian + "IiiIIIII", data, 0
    )
    command_limit = 32 + sizeofcmds
    require(command_limit <= len(data), "Mach-O load commands exceed file")
    commands = []
    offset = 32
    for index in range(ncmds):
        require(offset + 8 <= command_limit, "truncated Mach-O load command header")
        command, command_size = struct.unpack_from(endian + "II", data, offset)
        require(command_size >= 8 and offset + command_size <= command_limit, "invalid Mach-O load command size")
        item = {
            "index": index,
            "offset": offset,
            "command": f"0x{command:08x}",
            "name": MACHO_COMMANDS.get(command, "UNKNOWN"),
            "size": command_size,
        }
        if command == 0x19 and command_size >= 72:
            segname = data[offset + 8 : offset + 24].rstrip(b"\0").decode("ascii", errors="replace")
            vmaddr, vmsize, fileoff, filesize, maxprot, initprot, nsects, segflags = struct.unpack_from(
                endian + "QQQQiiII", data, offset + 24
            )
            item["segment"] = {
                "name": segname,
                "vmaddr": f"0x{vmaddr:x}",
                "vmsize": vmsize,
                "fileoff": fileoff,
                "filesize": filesize,
                "maxprot": maxprot,
                "initprot": initprot,
                "sections": nsects,
                "flags": f"0x{segflags:x}",
                "file_range_valid": fileoff + filesize <= len(data),
            }
        elif command == 0x1B and command_size >= 24:
            item["uuid"] = str(uuid.UUID(bytes=bytes(data[offset + 8 : offset + 24])))
        elif command == 0x80000028 and command_size >= 24:
            entryoff, stacksize = struct.unpack_from(endian + "QQ", data, offset + 8)
            item["entryoff"] = entryoff
            item["stacksize"] = stacksize
        elif command == 0x5 and command_size >= 16:
            flavor, count = struct.unpack_from(endian + "II", data, offset + 8)
            item["thread_flavor"] = flavor
            item["thread_count"] = count
            if flavor == 6 and count >= 68 and offset + 280 <= offset + command_size:
                item["arm64_pc"] = f"0x{struct.unpack_from(endian + 'Q', data, offset + 272)[0]:x}"
        elif command == 0x32 and command_size >= 24:
            platform_id, minimum, sdk, tool_count = struct.unpack_from(endian + "IIII", data, offset + 8)
            item["build_version"] = {
                "platform": platform_id,
                "minimum": macho_version(minimum),
                "sdk": macho_version(sdk),
                "tools": tool_count,
            }
        elif command == 0x2A and command_size >= 16:
            item["source_version"] = struct.unpack_from(endian + "Q", data, offset + 8)[0]
        commands.append(item)
        offset += command_size
    segment_ranges_valid = all(
        item.get("segment", {}).get("file_range_valid", True) for item in commands
    )
    return {
        "magic": magic_name,
        "endianness": "little" if endian == "<" else "big",
        "cputype": f"0x{cputype & 0xffffffff:08x}",
        "cpu_name": "ARM64" if (cputype & 0xffffffff) == 0x0100000C else "unknown",
        "cpusubtype": f"0x{cpusubtype & 0xffffffff:08x}",
        "filetype": filetype,
        "filetype_name": {2: "MH_EXECUTE", 5: "MH_PRELOAD", 11: "MH_KEXT_BUNDLE"}.get(filetype, "unknown"),
        "ncmds": ncmds,
        "sizeofcmds": sizeofcmds,
        "flags": f"0x{flags:08x}",
        "reserved": reserved,
        "commands_end": offset,
        "declared_commands_end": command_limit,
        "command_size_sum_matches": offset == command_limit,
        "segment_file_ranges_valid": segment_ranges_valid,
        "load_commands": commands,
    }


def parse_firmware_volumes(path: Path) -> dict:
    data = path.read_bytes()
    signatures = []
    cursor = 0
    while True:
        found = data.find(b"_FVH", cursor)
        if found < 0:
            break
        cursor = found + 1
        base = found - 0x28
        if base < 0 or base + 56 > len(data):
            continue
        fv_length = struct.unpack_from("<Q", data, base + 32)[0]
        attributes = struct.unpack_from("<I", data, base + 44)[0]
        header_length, checksum, ext_header_offset = struct.unpack_from("<HHH", data, base + 48)
        revision = data[base + 55]
        if header_length < 56 or fv_length < header_length or base + fv_length > len(data):
            continue
        header = data[base : base + header_length]
        if len(header) % 2:
            header += b"\0"
        checksum_sum = sum(struct.unpack("<" + "H" * (len(header) // 2), header)) & 0xFFFF
        block_map = []
        map_offset = base + 56
        while map_offset + 8 <= base + header_length:
            blocks, length = struct.unpack_from("<II", data, map_offset)
            block_map.append({"blocks": blocks, "block_length": length, "bytes": blocks * length})
            map_offset += 8
            if blocks == 0 and length == 0:
                break
        block_total = sum(item["bytes"] for item in block_map if item["blocks"] and item["block_length"])
        signatures.append(
            {
                "offset": base,
                "signature_offset": found,
                "filesystem_guid": str(uuid.UUID(bytes_le=bytes(data[base + 16 : base + 32]))),
                "fv_length": fv_length,
                "attributes": f"0x{attributes:08x}",
                "header_length": header_length,
                "header_checksum": f"0x{checksum:04x}",
                "header_checksum_valid": checksum_sum == 0,
                "ext_header_offset": ext_header_offset,
                "revision": revision,
                "block_map": block_map,
                "block_map_bytes": block_total,
                "block_map_matches_length": block_total == fv_length,
                "range_valid": base + fv_length <= len(data),
            }
        )
    return {
        "file_size": len(data),
        "firmware_volume_count": len(signatures),
        "firmware_volumes": signatures,
        "all_headers_valid": bool(signatures)
        and all(
            item["header_checksum_valid"]
            and item["block_map_matches_length"]
            and item["range_valid"]
            for item in signatures
        ),
    }


def file_description(path: Path) -> str:
    result = run_command(["file", "--brief", "--dereference", str(path)])
    return decode(result.stdout).strip()


def collect_artifacts(root: Path, issues: list[str]) -> dict:
    kernel_path = root / DEFAULT_KERNEL
    uefi_path = root / DEFAULT_UEFI
    require(kernel_path.is_file(), f"missing kernel artifact: {kernel_path}")
    require(uefi_path.is_file(), f"missing UEFI artifact: {uefi_path}")
    kernel = file_identity(kernel_path)
    kernel.update(file_output=file_description(kernel_path), macho=parse_macho(kernel_path))
    kernel["expected_size"] = EXPECTED_KERNEL_SIZE
    kernel["expected_sha256"] = EXPECTED_KERNEL_SHA256
    kernel["matches_expected"] = (
        kernel["size"] == EXPECTED_KERNEL_SIZE and kernel["sha256"] == EXPECTED_KERNEL_SHA256
    )
    uefi = file_identity(uefi_path)
    uefi.update(file_output=file_description(uefi_path), firmware=parse_firmware_volumes(uefi_path))
    uefi["expected_size"] = EXPECTED_UEFI_SIZE
    uefi["expected_sha256"] = EXPECTED_UEFI_SHA256
    uefi["matches_expected"] = uefi["size"] == EXPECTED_UEFI_SIZE and uefi["sha256"] == EXPECTED_UEFI_SHA256
    prebuilt_path = root / "prebuilt/hakios-kernel"
    prebuilt = file_identity(prebuilt_path) if prebuilt_path.is_file() else None
    if not kernel["matches_expected"]:
        issues.append("kernel artifact does not match selected size/SHA-256")
    if not kernel["macho"]["command_size_sum_matches"] or not kernel["macho"]["segment_file_ranges_valid"]:
        issues.append("kernel Mach-O structure is invalid")
    if not uefi["matches_expected"]:
        issues.append("UEFI artifact does not match selected size/SHA-256")
    if not uefi["firmware"]["all_headers_valid"]:
        issues.append("UEFI firmware-volume structure is invalid")
    return {"schema_version": 1, "kernel": kernel, "uefi": uefi, "prebuilt_kernel": prebuilt}


def parse_config(path: Path) -> dict:
    symbols = {}
    disabled = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            symbols[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            key = line[2 : -len(" is not set")]
            symbols[key] = "n"
            disabled += 1
    selected = {
        key: value
        for key, value in symbols.items()
        if key.startswith("CONFIG_HAKIOS") or key in {"CONFIG_UFS", "CONFIG_MACH_HAKIOS", "CONFIG_ARM64"}
    }
    identity = file_identity(path)
    identity.update(symbol_count=len(symbols), disabled_count=disabled, selected_symbols=selected)
    identity["expected_sha256"] = EXPECTED_CONFIG_SHA256
    identity["matches_expected"] = identity["sha256"] == EXPECTED_CONFIG_SHA256
    return identity


def executable_identity(value: str, cache: dict[str, dict]) -> dict | None:
    located = value if os.path.isabs(value) else shutil.which(value)
    if not located:
        return None
    path = Path(located)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return None
    key = str(resolved)
    if key not in cache:
        cache[key] = file_identity(resolved)
    result = dict(cache[key])
    result["invoked_as"] = value
    result["located_path"] = str(path)
    return result


def command_pin(label: str, argv: list[str], cache: dict[str, dict]) -> dict:
    result = run_command(argv, check=False)
    return {
        "label": label,
        "argv": argv,
        "exit_code": result.returncode,
        "stdout": decode(result.stdout),
        "stderr": decode(result.stderr),
        "executable": executable_identity(argv[0], cache),
    }


def package_pin(name: str) -> dict:
    result = run_command(
        ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${Status}\n", name], check=False
    )
    return {
        "name": name,
        "installed": result.returncode == 0 and "install ok installed" in decode(result.stdout),
        "exit_code": result.returncode,
        "record": decode(result.stdout).strip(),
        "error": decode(result.stderr).strip(),
    }


def collect_toolchain(issues: list[str]) -> dict:
    cache: dict[str, dict] = {}
    commands = [command_pin(label, argv, cache) for label, argv in TOOL_COMMANDS]
    for command in commands:
        if command["exit_code"] != 0 or command["executable"] is None:
            issues.append(f"required tool unavailable or failed: {command['label']}")
    venv = DEFAULT_CHECKOUT / "venv/bin/python"
    pip_freeze = command_pin("venv_pip_freeze", [str(venv), "-m", "pip", "freeze", "--all"], cache)
    if pip_freeze["exit_code"] != 0:
        issues.append("UEFI virtual-environment package inventory failed")
    return {
        "schema_version": 1,
        "python_runtime": {"version": sys.version, "executable": sys.executable},
        "commands": commands,
        "packages": [package_pin(name) for name in PACKAGE_NAMES],
        "uefi_venv_packages": pip_freeze,
    }


def tree_digest(root: Path) -> dict:
    digest = hashlib.sha256()
    counts = {"directories": 0, "files": 0, "symlinks": 0, "bytes": 0}

    def feed(kind: str, relative: str, mode: int, size: int, content_hash: str) -> None:
        fields = [kind.encode(), os.fsencode(relative), oct(mode).encode(), str(size).encode(), content_hash.encode()]
        for field in fields:
            digest.update(len(field).to_bytes(8, "little"))
            digest.update(field)

    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs.sort()
        files.sort()
        retained_dirs = []
        for name in dirs:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if path.is_symlink():
                target = os.readlink(path)
                payload = os.fsencode(target)
                counts["symlinks"] += 1
                feed("symlink", relative, stat.S_IMODE(info.st_mode), len(payload), sha256_bytes(payload))
            else:
                counts["directories"] += 1
                feed("directory", relative, stat.S_IMODE(info.st_mode), 0, "")
                retained_dirs.append(name)
        dirs[:] = retained_dirs
        for name in files:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if path.is_symlink():
                target = os.readlink(path)
                payload = os.fsencode(target)
                counts["symlinks"] += 1
                feed("symlink", relative, stat.S_IMODE(info.st_mode), len(payload), sha256_bytes(payload))
            elif path.is_file():
                content_hash = sha256_file(path)
                counts["files"] += 1
                counts["bytes"] += info.st_size
                feed("file", relative, stat.S_IMODE(info.st_mode), info.st_size, content_hash)
            else:
                feed("special", relative, stat.S_IMODE(info.st_mode), info.st_size, "")
    return {**counts, "sha256": digest.hexdigest(), "algorithm": "path-mode-size-content-sha256-v1"}


def collect_sdk(issues: list[str]) -> dict:
    sdk = DEFAULT_SDK
    require(sdk.exists(), f"missing SDK: {sdk}")
    link_target = os.readlink(sdk) if sdk.is_symlink() else None
    resolved = sdk.resolve(strict=True)
    sdk_repo = resolved.parent
    while sdk_repo != sdk_repo.parent and not (sdk_repo / ".git").exists():
        sdk_repo = sdk_repo.parent
    require((sdk_repo / ".git").exists(), f"SDK is not inside a Git checkout: {resolved}")
    head = git_text(sdk_repo, "rev-parse", "HEAD")
    status = git_bytes(sdk_repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    remotes = git_text(sdk_repo, "remote", "-v").splitlines()
    key_files = []
    for relative in ("SDKSettings.json", "SDKSettings.plist", "System/Library/CoreServices/SystemVersion.plist"):
        path = resolved / relative
        if path.is_file():
            item = file_identity(path)
            item["relative_path"] = relative
            key_files.append(item)
    if head != EXPECTED_SDK_COMMIT:
        issues.append(f"Theos SDK repository commit mismatch: {head}")
    if status:
        issues.append("Theos SDK repository is modified")
    return {
        "schema_version": 1,
        "path": str(sdk),
        "symlink_target": link_target,
        "resolved_path": str(resolved),
        "repository": {
            "path": str(sdk_repo),
            "head": head,
            "expected_commit": EXPECTED_SDK_COMMIT,
            "clean": not status,
            "status_size": len(status),
            "status_sha256": sha256_bytes(status),
            "remotes": [redact_remote(line) for line in remotes],
        },
        "tree": tree_digest(resolved),
        "key_files": key_files,
    }


def symlink_pin(path: Path) -> dict:
    info = path.lstat()
    require(stat.S_ISLNK(info.st_mode), f"expected symlink: {path}")
    target = os.readlink(path)
    return {"path": str(path), "target": target, "resolved": str(path.resolve(strict=True))}


def collect_nasm_adaptation(issues: list[str]) -> dict:
    base = DEFAULT_CHECKOUT / "Mu-Silicium/Mu_Basecore/BaseTools/Bin/mu_nasm_extdep"
    state = base / "extdep_state.yaml"
    source = PROJECT / "patches/mu-nasm-extdep-state.yaml"
    require(state.is_file() and source.is_file(), "missing NASM external-dependency adaptation")
    state_record = file_identity(state)
    source_record = file_identity(source)
    nasm = symlink_pin(base / "Linux-x86-64/nasm")
    ndisasm = symlink_pin(base / "Linux-x86-64/ndisasm")
    if state_record["sha256"] != EXPECTED_NASM_STATE_SHA256 or source_record["sha256"] != EXPECTED_NASM_STATE_SHA256:
        issues.append("NASM external-dependency state does not match the retained adaptation")
    return {
        "schema_version": 1,
        "expected_state_sha256": EXPECTED_NASM_STATE_SHA256,
        "installed_state": state_record,
        "retained_source": source_record,
        "nasm_link": nasm,
        "ndisasm_link": ndisasm,
    }


def collect_run_pins(project: Path, packet: Path | None, issues: list[str]) -> dict:
    records = []
    for role, run_id in RUN_PINS:
        source_dir = project / "runs" / run_id
        metadata_path = source_dir / "metadata.json"
        output_path = source_dir / "output.log"
        require(metadata_path.is_file() and output_path.is_file(), f"missing retained run: {run_id}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if metadata.get("status") != "passed" or metadata.get("exit_code") != 0:
            issues.append(f"selected retained run did not pass: {run_id}")
        copied = {}
        for source in (metadata_path, output_path):
            relative = Path("run-pins") / run_id / source.name
            payload = source.read_bytes()
            copied[source.name] = payload_identity(relative.as_posix(), payload)
            if packet is not None:
                target = packet / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
        records.append(
            {
                "role": role,
                "run_id": run_id,
                "status": metadata.get("status"),
                "exit_code": metadata.get("exit_code"),
                "command": metadata.get("command"),
                "started": metadata.get("started"),
                "finished": metadata.get("finished"),
                "source": source_dir.relative_to(project).as_posix(),
                "evidence": copied,
            }
        )
    return {"schema_version": 1, "runs": records}


def collect_claims(root: Path, packet: Path | None) -> dict:
    source = root / "devices/a51/PORTING.md"
    require(source.is_file(), f"missing upstream claims source: {source}")
    content = source.read_bytes()
    text = content.decode("utf-8", errors="replace")
    matcher = re.compile(r"ios 16\.5|home screen|display|touch|buttons|wi-?fi|gpu|metal|fps|springboard", re.I)
    excerpts = [
        {"line": index, "text": line}
        for index, line in enumerate(text.splitlines(), 1)
        if matcher.search(line)
    ]
    source_relative = "source/PORTING.md"
    excerpts_relative = "source/claims-excerpts.json"
    excerpts_value = {
        "schema_version": 1,
        "classification": "upstream_assertions_not_local_hardware_validation",
        "source": source_relative,
        "excerpts": excerpts,
    }
    excerpts_payload = json_bytes(excerpts_value)
    if packet is not None:
        target = packet / source_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        (packet / excerpts_relative).write_bytes(excerpts_payload)
    return {
        "schema_version": 1,
        "classification": "upstream_assertions_not_local_hardware_validation",
        "checkout_path": source.relative_to(root).as_posix(),
        "source_snapshot": payload_identity(source_relative, content),
        "excerpts": payload_identity(excerpts_relative, excerpts_payload),
        "excerpt_count": len(excerpts),
        "local_device_validation_performed": False,
    }


def build_manifest(packet: Path) -> dict:
    files = []
    for path in sorted(packet.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(packet).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": 1,
        "files": files,
        "limits": (
            "This ledger detects later byte changes. It does not authenticate upstream claims, prove an A51 boot, "
            "or replace physical-device acceptance evidence. Large build artifacts remain under /opt/a51-hakios."
        ),
    }


def resolve_packet(value: str) -> Path:
    base = (PROJECT / "evidence/phase-1/upstream-a51-port").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (PROJECT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    require(candidate.is_relative_to(base), f"packet must stay under {base}")
    require(not candidate.exists(), f"packet already exists: {candidate}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", default=str(DEFAULT_CHECKOUT))
    parser.add_argument("--output", required=True, help="new packet directory, relative to the project or absolute")
    args = parser.parse_args()
    root = Path(args.checkout).resolve()
    packet = resolve_packet(args.output)
    packet.mkdir(parents=True)
    issues: list[str] = []
    try:
        repositories = collect_repositories(root, packet, issues)
        write_json(packet / "repositories.json", repositories)

        artifacts = collect_artifacts(root, issues)
        write_json(packet / "artifacts.json", artifacts)

        config = parse_config(root / ".config")
        if not config["matches_expected"]:
            issues.append("A51 kernel configuration hash mismatch")
        config_payload = (root / ".config").read_bytes()
        (packet / "configuration").mkdir()
        (packet / "configuration/a51.config").write_bytes(config_payload)
        write_json(packet / "configuration.json", config)

        toolchain = collect_toolchain(issues)
        write_json(packet / "toolchain.json", toolchain)

        sdk = collect_sdk(issues)
        write_json(packet / "sdk.json", sdk)

        nasm = collect_nasm_adaptation(issues)
        write_json(packet / "nasm-adaptation.json", nasm)

        run_pins = collect_run_pins(PROJECT, packet, issues)
        write_json(packet / "run-pins.json", run_pins)

        claims = collect_claims(root, packet)
        write_json(packet / "claims.json", claims)

        agents_files = [relative_to(root, path) for path in root.rglob("AGENTS.md")]
        result = {
            "schema_version": 1,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "passed" if not issues else "failed",
            "passed": not issues,
            "scope": "host-only supplemental Phase 1 audit of the active upstream Galaxy A51 checkout",
            "checkout": str(root),
            "packet": str(packet),
            "device_operations": False,
            "phone_queries": False,
            "phone_writes": False,
            "phone_reboots": False,
            "flashing": False,
            "ipsw_downloaded": False,
            "a51_boot_verified_by_this_audit": False,
            "ios_home_screen_verified_by_this_audit": False,
            "display_verified_by_this_audit": False,
            "wifi_verified_by_this_audit": False,
            "gpu_or_metal_verified_by_this_audit": False,
            "repository_count": repositories["repository_count"],
            "dirty_repository_count": repositories["dirty_repository_count"],
            "kernel": {
                "path": artifacts["kernel"]["path"],
                "size": artifacts["kernel"]["size"],
                "sha256": artifacts["kernel"]["sha256"],
            },
            "uefi": {
                "path": artifacts["uefi"]["path"],
                "size": artifacts["uefi"]["size"],
                "sha256": artifacts["uefi"]["sha256"],
            },
            "config_sha256": config["sha256"],
            "sdk_commit": sdk["repository"]["head"],
            "agents_files_in_checkout": agents_files,
            "upstream_claims_classification": claims["classification"],
            "issues": issues,
        }
        write_json(packet / "result.json", result)
        manifest = build_manifest(packet)
        write_json(packet / "manifest.json", manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        print(f"Manifest files: {len(manifest['files'])}")
        return 0 if result["passed"] else 1
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "failed",
            "passed": False,
            "scope": "host-only supplemental Phase 1 audit of the active upstream Galaxy A51 checkout",
            "checkout": str(root),
            "packet": str(packet),
            "device_operations": False,
            "error": f"{type(exc).__name__}: {exc}",
            "issues": issues,
        }
        write_json(packet / "result.json", failure)
        write_json(packet / "manifest.json", build_manifest(packet))
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
