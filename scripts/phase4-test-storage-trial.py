#!/usr/bin/env python3
"""Exercise actual storage parsers and cycle cleanup using modeled ADB only."""
from __future__ import annotations

import contextlib
import copy
import fnmatch
import io
import json
import re
import shutil
import struct
import subprocess
import zlib
from unittest import mock

from phase4_storage import (RAMOOPS_COMMAND, RAMOOPS_PARAMETERS, RECOVERY_ROUTE, SUPPORT, StorageCycle,
                            decode_console, decode_reader, decode_recovery, load,
                            validate_gnss_reservation, validate_ramoops_parameters, validate_storage)
from phase4_support import PROJECT, documents, index_packet, new_packet, pin, require, write_json
from phase4_reporting import PENDING_LINE, REPORTING_LINE
import phase4_device

models = load("phase4_storage_cycle_models", PROJECT / "scripts/phase4-test-device-cycle.py")
boot_fixtures = load("phase4_storage_fdt_fixtures", PROJECT / "scripts/test-boot-formats.py")
NONCE = "0123456789abcdef0123456789abcdef"


def fixture_selected(candidate, baseline, reader):
    return {"kind": "storage", "nonce": NONCE, "candidate": pin(candidate),
        "cmdline": "MODELED_STORAGE_ARGS hakios_run_nonce=" + NONCE + " hakios_a51_probe=16",
        "rollback_pins": {role: pin(baseline) for role in ("template", "recovery", "dtbo")},
        "read_hashes": {"single": "a" * 64, "multi": "b" * 64},
        "reader_module": pin(reader), "reader_vermagic": "MODELED_ABI SMP", "log_pa": 0x83b449c0,
        "snapshot_contract": {"groups": 16, "version": 1, "bytes": 3096,
            "registers": [{"pa": 0x13520010, "group": 16}],
            "banks": [{"pa": 0x13520000, "group": 16, "count": 1}]}}


def fixture_gnss(*, start=0xfb000000, size=0x800000, status=None,
                 reusable=False, missing=False, translated=False, extra_reg=False, binding=0x103):
    cell = boot_fixtures.cell
    node = {"compatible": b"exynos,gnss_if\0", "reg": cell(0, start, size),
            "phandle": cell(0x103), "linux,phandle": cell(0x103)}
    if status:
        node["status"] = status.encode("ascii") + b"\0"
    if reusable:
        node["reusable"] = b""
    if extra_reg:
        node["reg"] += cell(0, 0xfa000000, 0x800000)
    parent = {"#address-cells": cell(2), "#size-cells": cell(1),
              "ranges": cell(0, 0, 0) if translated else b""}
    if not missing:
        parent["gnss_if"] = node
    return boot_fixtures.fdt({"#address-cells": cell(2), "#size-cells": cell(1),
        "reserved-memory": parent, "gnss_pdata": {"memory-region": cell(binding)}})


def fixture_log(selected):
    text = ("HAKIOS_USER_BEGIN pid=1 uid=0 console=0\n"
        "kern.bootargs=" + selected["cmdline"] + "\nHAKIOS_RUN_NONCE=" + selected["nonce"] + "\n"
        "HAKIOS_A51_SNAPSHOT_SIZE rc=0 bytes=3096\nHAKIOS_A51_ABI small_rc=-12 write_rc=-1\n"
        "HAKIOS_A51_SNAPSHOT rc=0 version=1 count=1 groups=0x10 sequence=1 counter=1 pass=1\n"
        "HAKIOS_A51_REG index=0 pa=0x13520010 group=0x10 value=0x101\n" + REPORTING_LINE + "\n" +
        "HAKIOS_STORAGE_DIAG ufs_rc=0 abi=2 bytes=336 init_rc=0 s_rc=0 s_ocs=0 m_rc=0 m_ocs=0 r_rc=0 r_ocs=0 run=0x0 dbr=0x0\n")
    for name, blocks in (("single", 1), ("multi", 16), ("reread", 1)):
        text += (f"HAKIOS_UFS_TRANSFER name={name} rc=0 ocs=0 lba=27792 blocks={blocks} lifecycle=23 stages=0xfe "
            f"transaction=33 response=0 status=0 residual=0 sense_len=0 prdt_count=1 prdt_bytes=128 "
            "elapsed_us=300 sha256=" + selected["read_hashes"]["multi" if blocks == 16 else "single"] + "\n")
    text += ("HAKIOS_STORAGE_WRITE_GUARD rc=-30 rejected=1 doorbell=0x0 pass=1\n"
        "HAKIOS_STORAGE_TRANSFER_STATUS single=1 multi=1 reread=1 write_guard=1\n"
        "HAKIOS_IMAGE_LOAD_OBSERVATION bytes=65536 commands=1 sha256=" + selected["read_hashes"]["multi"] +
        " known_contents=host_check_required\n" + PENDING_LINE + "\n" +
        "HAKIOS_A51_SPI rc=-6 flags=0x0\nHAKIOS_A51_DIAG_PASS\n"
        "HAKIOS_PLATFORM gic=2 cores=1 midr=0x410fd034\n")
    for i in range(1, 4):
        text += (f"HAKIOS_TIMER_SAMPLE index={i} select_rc=0 elapsed_us=1000000 "
                 f"irq_before={i - 1} irq_after={i} read_rc=0 pass=1\n")
    text += ("HAKIOS_TIMER_PASS samples=3\nHAKIOS_USER_EXIT outcome=0 timer_verified=1\n"
        "[   1.000000]: HAKIOS_A51_PROBE_BEGIN pa=0x13520000 group=0x10\n"
        "[   1.000001]: HAKIOS_A51_PROBE_DONE pa=0x13520000 count=1\n")
    for name, blocks in (("device-start", 0), ("lun0-start", 0), ("unit-ready", 0),
                         ("single", 1), ("multi", 16), ("reread", 1)):
        text += (f"[   2.000000]: HAKIOS_UFS_REPORT name={name} rc=0 cleanup_rc=0 lba={27792 if blocks else 0} blocks={blocks} "
            f"bytes={blocks * 4096} ocs=0 trans=0x21 resp=0 status=0 residual=0 sense_len=0 stages=0xfe "
            f"submitted=1 completed=1 restored=1 quarantined=0 prdt_count={1 if blocks else 0} prdt_bytes={128 if blocks else 0} elapsed_us=300\n")
        text += (f"[   2.000000]: HAKIOS_UFS_TERMINAL name={name} is=0x1 dbr=0x0 task=0x0 run=0x1 "
            "hcs=0x10f hce=0x1 uic=0x0:0x0:0x0:0x0:0x0 rx_error=0x0 dma=0x0:0x0:0x0:0x0 final_dbr=0x0 final_run=0x0\n")
    return text


def mutate_command(text, marker, name, replacements):
    """Change one actual command row while preserving both capture fixtures."""
    lines, matches = text.splitlines(keepends=True), 0
    for i, line in enumerate(lines):
        if marker + " name=" + name + " " not in line:
            continue
        matches += 1
        for key, value in replacements.items():
            line, count = re.subn(r"(?<= )" + re.escape(key) + r"=[^\s]+", key + "=" + str(value), line)
            require(count == 1, "Missing/duplicate modeled command field: " + key)
        lines[i] = line
    require(matches == 1, "Missing/duplicate modeled command row")
    return "".join(lines)


def fixture_console(selected, *, change=None, tail=b""):
    text = fixture_log(selected)
    if change:
        text = change(text)
    return text.encode("ascii") + tail


def fixture_reader(selected, token, *, change=None, tail=b""):
    console = fixture_console(selected, change=change, tail=tail)
    _, capture = decode_console(console)
    text = console[:capture["text_bytes"]].decode("ascii")
    raw = (f"[   20.0] HAKIOS_STORAGE_RECORD token={token} magic=32454c5241494b48 version=1 bytes=256 "
        f"status=6 reason=0 code=0 log_pa={selected['log_pa']:016x} log_len={len(console)} el=1 cntfrq=26000000 midr=00000000410fd034\n")
    raw += (f"[   20.0] HAKIOS_STORAGE_CAPTURE_BEGIN token={token} bank=gnss bytes={len(console)} "
            f"text_bytes={capture['text_bytes']} tail_bytes={capture['tail_bytes']}\n")
    raw += "".join(f"[   20.0] HAKIOS_STORAGE_OUT: {line}\n" for line in text.splitlines())
    raw += (f"[   20.0] HAKIOS_STORAGE_CAPTURE_END token={token} bank=gnss prefix_complete=1 "
            f"text_bytes={capture['text_bytes']} tail_bytes={capture['tail_bytes']}\n")
    return raw.encode("ascii")


def fixture_ramoops():
    return "".join(f"{key}={value}\n" for key, value in RAMOOPS_PARAMETERS.items()).encode("ascii")


def fixture_recovery(selected, *, change=None, tail=b"", record_change=None):
    log = fixture_console(selected, change=change, tail=tail)
    contract = selected["record_contract"]
    values = [0x32454c5241494b48, 1, 256, 6, 0, 0, selected["log_pa"], len(log),
              1, 0xc0, 0x30d00800, 26000000, 0x410fd034,
              contract["entry_pa"], contract["ba_pa"], contract["checkpoint"], 0x83012340] + [0] * 15
    if record_change:
        record_change(values)
    payload = struct.pack("<32Q", *values) + log
    header = struct.pack("<8s4I", b"HKUFSR01", 1, 256, len(log), 32 + len(payload))
    return header + struct.pack("<2I", zlib.crc32(header + payload), 0x31434b48) + payload


class StorageModel(models.ModelDevice):
    def __init__(self, *args, log_change=None, **kwargs):
        super().__init__(*args, banks={}, **kwargs)
        self.selinux, self.module_live, self.token = "Enforcing", False, None
        self.log_change = log_change

    def run_command(self, argv, **kwargs):
        name = self.current_name
        extras = (name.endswith("-ramoops-parameters") or name.endswith("-ufs-block-size") or name.endswith("-boot-start") or name.endswith("-gnss-reservation") or name.startswith("reader-") or
                  name in ("capture-pstore-console", "capture-pstore-pmsg") or "-fallback-" in name)
        if not extras or name == "reader-stage":
            return super().run_command(argv, **kwargs)
        require(argv[:3] == ["adb", "-s", phase4_device.SERIAL], "Wrong modeled storage serial")
        self.events.append({"name": name, "state_before": self.state, "modeled": True})
        rule = {}
        for pattern, row in self.rules.items():
            if fnmatch.fnmatchcase(name, pattern):
                self.rule_hits[pattern] = self.rule_hits.get(pattern, 0) + 1
                if self.rule_hits[pattern] in row.get("on", [self.rule_hits[pattern]]):
                    rule = row
                break
        command, child = argv[-1], "HAKIOS_PRIV_EXIT" in argv[-1]
        raw, remote_rc = b"", rule.get("remote_rc", 0)
        if name.endswith("-ramoops-parameters"):
            require(RAMOOPS_COMMAND in command, "Ramoops geometry was not read from live parameters")
            raw = fixture_ramoops()
        elif name.endswith("-ufs-block-size"):
            raw = b"4096\n"
        elif name.endswith("-boot-start"):
            raw = b"222336\n"
        elif name.endswith("-gnss-reservation"):
            require("cat /sys/firmware/fdt" in command, "GNSS reservation did not use the live FDT")
            raw = fixture_gnss()
        elif name == "capture-pstore-console":
            raw = fixture_console(self.selected, change=self.log_change)
        elif name == "capture-pstore-pmsg":
            if self.selected.get("capture_route") == RECOVERY_ROUTE:
                raw = fixture_recovery(self.selected, change=self.log_change)
            else:
                remote_rc = remote_rc or 1
        elif "-fallback-" in name:
            if name.endswith("-fallback-source"):
                remote = command.split("test -f ", 1)[1].split(" &&", 1)[0]
                remote_rc = remote_rc or int(remote not in self.files)
            elif name.endswith("-size"):
                remote = command.split("stat -c %s ", 1)[1].split(";", 1)[0]
                raw = (str(self.files[remote]["bytes"]) + "\n").encode()
            elif name.endswith("-hash"):
                remote = command.split("sha256sum ", 1)[1].split(";", 1)[0]
                raw = (self.files[remote]["sha256"] + "  MODELED_BASELINE\n").encode()
            elif name.endswith("-copy"):
                self.assert_intent("file_writes")
                source, target = command.split("cp ", 1)[1].split(" &&", 1)[0].split()
                if not rule.get("no_effect"):
                    self.files[target] = copy.deepcopy(self.files[source])
            else:
                raise AssertionError("Unhandled fallback request: " + name)
        elif name in ("reader-selinux-before", "reader-selinux-after"):
            raw = (self.selinux + "\n").encode()
        elif name == "reader-kernel-release":
            raw = b"MODELED_ABI\n"
        elif name in ("reader-module-absent", "reader-final-module-absent"):
            remote_rc = remote_rc or int(self.module_live)
        elif name in ("reader-file-absent", "reader-final-file-absent"):
            remote = command.split("test ! -e ", 1)[1].split(" &&", 1)[0]
            remote_rc = remote_rc or int(remote in self.files)
        elif name == "reader-stage-size":
            remote = command.split("stat -c %s ", 1)[1].split(";", 1)[0]
            raw = (str(self.files[remote]["bytes"]) + "\n").encode()
        elif name == "reader-stage-hash":
            remote = command.split("sha256sum ", 1)[1].split(";", 1)[0]
            raw = (self.files[remote]["sha256"] + "  MODELED_READER\n").encode()
        elif name in ("reader-selinux-permissive", "reader-selinux-restore"):
            self.assert_intent("security_changes")
            if not rule.get("no_effect"):
                self.selinux = "Permissive" if name.endswith("permissive") else "Enforcing"
            if self.selinux != ("Permissive" if name.endswith("permissive") else "Enforcing"):
                remote_rc = remote_rc or 1
        elif name == "reader-load":
            self.assert_intent("module_loads")
            require(self.baseline_readback_ok and self.state == "device" and self.boot_id == models.BOOT_IDS[2],
                    "Reader loaded before verified baseline Android")
            self.token = re.search(r"capture_token=([0-9a-f]{32})", command)[1]
            self.module_live = not rule.get("no_effect")
        elif name == "reader-unload":
            self.assert_intent("module_unloads")
            if not rule.get("no_effect"):
                self.module_live = False
        elif name == "reader-dmesg-before":
            raw = b"MODELED_ANDROID_DMESG\n"
        elif name == "reader-dmesg-after":
            raw = fixture_reader(self.selected, self.token, change=self.log_change)
        elif name == "reader-final-boot-id":
            raw = (self.boot_id + "\n").encode()
        else:
            raise AssertionError("Unhandled storage model request: " + name)
        raw = rule.get("stdout", raw)
        if isinstance(raw, str):
            raw = raw.encode()
        if child and not rule.get("child_unframed"):
            raw += f"\nHAKIOS_PRIV_EXIT:{remote_rc}\n".encode()
        if rule.get("framing") != "missing":
            raw += f"\nHAKIOS_REMOTE_EXIT:{remote_rc}\n".encode()
        if rule.get("timeout"):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=raw, stderr=b"MODELED timeout")
        return subprocess.CompletedProcess(argv, rule.get("transport_rc", 0), raw, b"MODELED_STORAGE_ONLY\n")


def main():
    packet = new_packet("storage-trial-tests", __file__)
    for name in SUPPORT:
        shutil.copy2(PROJECT / "scripts" / name, packet / name)
    inputs = packet / "fixtures"
    inputs.mkdir()
    for name, raw in (("candidate", b"MODELED_CANDIDATE"), ("baseline", b"MODELED_BASELINE"), ("reader", b"MODELED_READER")):
        (inputs / name).write_bytes(raw)
    selected = fixture_selected(inputs / "candidate", inputs / "baseline", inputs / "reader")
    cases = []
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": False,
              "actual_device_operations": False, "sources": {name: pin(PROJECT / "scripts" / name) for name in SUPPORT}}
    try:
        token = "c" * 32
        # Change both independent captures for protocol-failure cases. Otherwise
        # rejection would exercise only the bank comparison and miss the fault.
        variants = {
            "valid": {"accepted": True},
            "valid_ansi_sgr": {"accepted": True, "reader_change": lambda raw:
                b"\x1b[1;31m" + raw + b"\x1b[0m"},
            "valid_empty_sgr": {"accepted": True, "reader_change": lambda raw:
                b"\x1b[m" + raw + b"\x1b[0m"},
            "malformed_ansi_escape": {"reader_change": lambda raw: b"\x1b[2K" + raw},
            "malformed_ansi_sgr": {"reader_change": lambda raw: b"\x1b[9999m" + raw},
            "unexpected_control": {"reader_change": lambda raw: b"\x00" + raw},
            "nonascii_dmesg": {"reader_change": lambda raw: b"\xff" + raw},
            "stale_boot_nonce": {"log_change": lambda text: text.replace(NONCE, "d" * 32)},
            "truncated_bank": {"reader_change": lambda raw: raw.rsplit(b"HAKIOS_STORAGE_CAPTURE_END", 1)[0]},
            "reader_incomplete": {"reader_change": lambda raw: raw.replace(b"prefix_complete=1", b"prefix_complete=0")},
            "saved_pointer_mismatch": {"reader_change": lambda raw: raw.replace(b"0000000083b449c0", b"0000000083b449c8")},
            "duplicate_record": {"reader_change": lambda raw: raw.splitlines(keepends=True)[0] + raw},
            "legacy_mirror_bank": {"reader_change": lambda raw: raw.replace(b"bank=gnss", b"bank=mirror")},
            "legacy_full_bank": {"reader_change": lambda raw: raw.replace(b"bank=gnss", b"bank=full")},
            "conflicting_footer_counts": {"reader_change": lambda raw:
                raw.rsplit(b"tail_bytes=0", 1)[0] + b"tail_bytes=1\n"},
            "conflicting_capture_bytes": {"reader_change": lambda raw: raw.replace(b"bank=gnss bytes=", b"bank=gnss bytes=1")},
            "gnss_recovery_disagree": {"reader_change": lambda raw:
                raw.replace(b"HAKIOS_USER_EXIT outcome=0", b"HAKIOS_USER_EXIT outcome=1")},
            "recovery_tail_extent_disagrees": {"recovery_change": lambda raw: raw + b"\x00"},
            "nonzero_ocs_despite_hash": {"log_change": lambda text: text.replace("ocs=0 lba=27792", "ocs=7 lba=27792")},
            "multi_timeout": {"log_change": lambda text: text.replace("name=multi rc=0", "name=multi rc=-110")},
            "multi_digest_mismatch": {"log_change": lambda text: text.replace("b" * 64, "e" * 64)},
            "restoration_missing": {"log_change": lambda text: text.replace("lifecycle=23", "lifecycle=7")},
            "wrong_prdt_length": {"log_change": lambda text: text.replace("prdt_bytes=128", "prdt_bytes=64")},
            "wrong_prdt_count": {"log_change": lambda text: text.replace("prdt_count=1", "prdt_count=99")},
            "residual_nonzero": {"log_change": lambda text: text.replace("residual=0", "residual=1")},
            "write_doorbell_active": {"log_change": lambda text: text.replace("doorbell=0x0 pass=1", "doorbell=0x1 pass=1")},
            "user_exit_failure": {"log_change": lambda text: text.replace("outcome=0", "outcome=1")},
            "timer_no_progress": {"log_change": lambda text: text.replace("irq_before=0 irq_after=1", "irq_before=0 irq_after=0")},
            "duplicate_transfer_field": {"log_change": lambda text: text.replace("name=multi rc=0", "name=multi rc=0 rc=0")},
            "terminal_active": {"log_change": lambda text: text.replace("final_dbr=0x0", "final_dbr=0x1")},
            "fatal_status_with_cleared_doorbell": {"log_change": lambda text:
                text.replace("name=multi is=0x1", "name=multi is=0x20001")},
            "failed_cleanup": {"log_change": lambda text: text.replace("cleanup_rc=0", "cleanup_rc=-110")},
            "quarantined_dma": {"log_change": lambda text: text.replace("quarantined=0", "quarantined=1")},
            "missing_driver_completion": {"log_change": lambda text: text.replace("completed=1", "completed=0")},
            "missing_driver_restore": {"log_change": lambda text: text.replace("restored=1", "restored=0")},
            "binary_tail_after_complete_diagnostics": {"accepted": True, "tail": b"\x00\xffSTACKSHOT\x00\ntext after binary\n"},
            "partial_printable_tail_after_diagnostics": {"accepted": True, "tail": b"INCOMPLETE_STACKSHOT_HEADER"},
            "binary_before_user_exit": {"log_change": lambda text: text.replace("HAKIOS_USER_EXIT", "\x00HAKIOS_USER_EXIT")},
            "log_exceeds_old_eight_kib_capacity": {"accepted": True, "log_change": lambda text:
                ("MODELED_PADDING_" + "x" * 240 + "\n") * 100 + text},
        }
        for name, change in {
            "missing_reporting_version": lambda text: text.replace(REPORTING_LINE + "\n", ""),
            "duplicate_reporting_version": lambda text: text.replace(REPORTING_LINE, (REPORTING_LINE + "\n") * 2),
            "wrong_reporting_version": lambda text: text.replace(REPORTING_LINE, "HAKIOS_A51_REPORTING version=2"),
            "noncanonical_reporting_version": lambda text: text.replace(REPORTING_LINE, "HAKIOS_A51_REPORTING version=01"),
        }.items():
            variants[name] = {"log_change": change, "failed_check": "reporting_version_1_exactly_once"}
        for name, change in {
            "missing_physical_pending": lambda text: text.replace(PENDING_LINE + "\n", ""),
            "duplicate_physical_pending": lambda text: text.replace(PENDING_LINE, (PENDING_LINE + "\n") * 2),
            "unearned_physical_completion": lambda text: text.replace("display=unverified", "display=verified"),
            "unearned_image_completion": lambda text: text.replace("known_image=host_check_required", "known_image=verified"),
        }.items():
            variants[name] = {"log_change": change, "failed_check": "phase4_physical_gate_explicitly_pending"}
        for legacy in ("HAKIOS_PHASE4_PASS", "HAKIOS_DISPLAY_VERIFIED", "HAKIOS_DSIM_VERIFIED",
                       "HAKIOS_BRIGHTNESS_VERIFIED", "HAKIOS_TOUCH_VERIFIED", "HAKIOS_KEYS_VERIFIED",
                       "HAKIOS_STORAGE_VERIFIED", "HAKIOS_STORAGE_PASS", "HAKIOS_STORAGE_MATCH",
                       "HAKIOS_IMAGE_LOAD_VERIFIED", "HAKIOS_PHASE4_COMPLETE"):
            variants["legacy_" + legacy] = {"log_change": lambda text, marker=legacy:
                text.replace("HAKIOS_A51_DIAG_PASS\n", marker + "\nHAKIOS_A51_DIAG_PASS\n"),
                "failed_check": "no_legacy_hardware_completion_markers"}
        variants["legacy_completion_outside_user_frame"] = {
            "log_change": lambda text: text + "HAKIOS_PHASE4_PASS\n",
            "failed_check": "no_legacy_hardware_completion_markers"}
        for name, change in {
            "aggregate_image_commands": lambda text: text.replace("bytes=65536 commands=1", "bytes=65536 commands=16"),
            "wrong_image_extent": lambda text: text.replace("bytes=65536 commands=1", "bytes=4096 commands=1"),
            "missing_content_comparison_notice": lambda text: text.replace(" known_contents=host_check_required", ""),
            "missing_transfer_status": lambda text: re.sub(r"HAKIOS_STORAGE_TRANSFER_STATUS[^\n]*\n", "", text),
            "duplicate_transfer_status": lambda text: re.sub(r"(HAKIOS_STORAGE_TRANSFER_STATUS[^\n]*\n)", r"\1\1", text),
            "missing_image_observation": lambda text: re.sub(r"HAKIOS_IMAGE_LOAD_OBSERVATION[^\n]*\n", "", text),
            "duplicate_image_observation": lambda text: re.sub(r"(HAKIOS_IMAGE_LOAD_OBSERVATION[^\n]*\n)", r"\1\1", text),
        }.items():
            variants[name] = {"log_change": change, "failed_check": "strict_storage_observation_markers"}
        # Keep the user-visible aggregate label/hash unchanged and mutate only
        # the independently logged driver command. Each fault must reach the
        # command-correspondence check rather than just the bank comparison.
        for key, value in {"lba": 27793, "blocks": 1, "bytes": 4096, "trans": "0x20", "resp": 1,
                           "status": 2, "residual": 4096, "sense_len": 18, "prdt_count": 16,
                           "prdt_bytes": 64, "elapsed_us": 301, "rc": -5, "ocs": 7}.items():
            variants["driver_user_disagreement_" + key] = {
                "log_change": lambda text, field=key, observed=value:
                    mutate_command(text, "HAKIOS_UFS_REPORT", "multi", {field: observed}),
                "failed_check": "multi_driver_user_command_correspondence"}
        variants["single_command_label_over_chunked_driver"] = {
            "log_change": lambda text: mutate_command(text, "HAKIOS_UFS_REPORT", "multi", {"blocks": 1, "bytes": 4096}),
            "failed_check": "multi_driver_user_command_correspondence"}
        for name, changes in {"missing_stage": {"stages": "0xfd"}, "extra_stage": {"stages": "0x1fe"},
                              "extra_lifecycle_flag": {"lifecycle": 31}, "wrong_multi_blocks": {"blocks": 1}}.items():
            variants[name] = {"log_change": lambda text, fields=changes:
                mutate_command(text, "HAKIOS_UFS_TRANSFER", "multi", fields),
                "failed_check": "multi_protocol_prdt_lifecycle_and_independent_sha256"}
        for elapsed in (1, 5000000):
            variants["valid_elapsed_boundary_" + str(elapsed)] = {"accepted": True,
                "log_change": lambda text, value=elapsed:
                    mutate_command(mutate_command(text, "HAKIOS_UFS_TRANSFER", "multi", {"elapsed_us": value}),
                                   "HAKIOS_UFS_REPORT", "multi", {"elapsed_us": value})}
        variants["extra_driver_command"] = {"log_change": lambda text:
            text + next(line for line in text.splitlines(keepends=True) if "HAKIOS_UFS_REPORT name=single " in line),
            "failed_check": "six_ordered_driver_commands"}
        for activation in ("device-start", "lun0-start", "unit-ready"):
            variants["missing_activation_report_" + activation] = {
                "log_change": lambda text, command=activation:
                    re.sub(r"[^\n]*HAKIOS_UFS_REPORT name=" + command + r" [^\n]*\n", "", text),
                "failed_check": "six_ordered_driver_commands"}
            variants["missing_activation_terminal_" + activation] = {
                "log_change": lambda text, command=activation:
                    re.sub(r"[^\n]*HAKIOS_UFS_TERMINAL name=" + command + r" [^\n]*\n", "", text),
                "failed_check": "six_ordered_terminal_captures"}
            for key, value in {"lba": 27792, "blocks": 1, "bytes": 4096, "prdt_count": 1,
                               "prdt_bytes": 128, "trans": "0x20", "resp": 1, "status": 2,
                               "residual": 4096, "sense_len": 18, "elapsed_us": 0}.items():
                variants["activation_protocol_" + activation + "_" + key] = {
                    "log_change": lambda text, command=activation, field=key, observed=value:
                        mutate_command(text, "HAKIOS_UFS_REPORT", command, {field: observed}),
                    "failed_check": activation + "_nondata_protocol_geometry"}
            for key, value in {"rc": -5, "cleanup_rc": -5, "ocs": 7, "stages": "0xfd",
                               "submitted": 0, "completed": 0, "restored": 0, "quarantined": 1}.items():
                variants["activation_lifecycle_" + activation + "_" + key] = {
                    "log_change": lambda text, command=activation, field=key, observed=value:
                        mutate_command(text, "HAKIOS_UFS_REPORT", command, {field: observed}),
                    "failed_check": activation + "_driver_completion_and_cleanup"}
            for key, value in {"is": "0x70885", "dbr": "0x1", "task": "0x1",
                               "final_dbr": "0x1", "rx_error": "0x1"}.items():
                variants["activation_terminal_" + activation + "_" + key] = {
                    "log_change": lambda text, command=activation, field=key, observed=value:
                        mutate_command(text, "HAKIOS_UFS_TERMINAL", command, {field: observed}),
                    "failed_check": activation + "_terminal_capture"}
        for name, variant in variants.items():
            observed, error, parsed = True, None, {"checks": {}}
            try:
                change, tail = variant.get("log_change"), variant.get("tail", b"")
                if change:
                    require(change(fixture_log(selected)) != fixture_log(selected), "Log mutation was not exercised: " + name)
                reader_raw = fixture_reader(selected, token, change=change, tail=tail)
                recovery_raw = fixture_console(selected, change=change, tail=tail)
                if variant.get("reader_change"):
                    changed = variant["reader_change"](reader_raw)
                    require(changed != reader_raw, "Reader mutation was not exercised: " + name)
                    reader_raw = changed
                if variant.get("recovery_change"):
                    recovery_raw = variant["recovery_change"](recovery_raw)
                record, banks = decode_reader(reader_raw, selected, token)
                banks["recovery"], capture = decode_console(recovery_raw)
                require(record["capture"] == capture, "GNSS/recovery extents disagree")
                validate_storage(record, banks, selected, parsed)
                if name == "log_exceeds_old_eight_kib_capacity":
                    require(capture["text_bytes"] > 8192, "Large-log fixture remained below the old bound")
                if tail:
                    require(capture["tail_bytes"] == len(tail), "Binary/partial tail extent was misreported")
            except (ValueError, UnicodeError) as exc:
                observed, error = False, str(exc)
            require(observed == variant.get("accepted", False), "Parser model disagrees: " + name + ": " + str(error))
            if variant.get("failed_check"):
                require(parsed["checks"].get(variant["failed_check"]) is False,
                        "Mutation missed its intended check: " + name + ": " + str(error))
            cases.append({"name": name, "accepted": observed, "passed": True, "modeled": True,
                          "rejection": error, "checks": parsed["checks"]})

        for name, raw, accepted in (
            ("gnss_reserved_span", fixture_gnss(), True),
            ("gnss_wrong_start", fixture_gnss(start=0xfa000000), False),
            ("gnss_wrong_size", fixture_gnss(size=0x20200), False),
            ("gnss_missing", fixture_gnss(missing=True), False),
            ("gnss_disabled", fixture_gnss(status="disabled"), False),
            ("gnss_reusable", fixture_gnss(reusable=True), False),
            ("gnss_translation", fixture_gnss(translated=True), False),
            ("gnss_multiple_ranges", fixture_gnss(extra_reg=True), False),
            ("gnss_wrong_binding", fixture_gnss(binding=0x104), False),
            ("gnss_trailing_bytes", fixture_gnss() + b"\0", False),
            ("gnss_truncated_fdt", fixture_gnss()[:-4], False),
            ("gnss_iomem_is_not_fdt", b"fb000000-fb7fffff : gnss_if\n", False),
        ):
            observed = True
            try:
                validate_gnss_reservation(raw)
            except ValueError:
                observed = False
            require(observed == accepted, "Reservation model disagrees: " + name)
            cases.append({"name": name, "accepted": observed, "passed": True, "modeled": True})
        failure_cases = {
            "cycle_success": ({}, None, True),
            "baseline_prestage_partial": ({"stage-preflight-baseline": {"partial": True, "timeout": True}}, None, False),
            "candidate_partial_write": ({"write-candidate": {"partial": True, "timeout": True}}, None, False),
            "candidate_no_recovery": ({"boot-candidate": {"no_effect": True}}, None, False),
            "recovery_capture_failed": ({"capture-root": {"remote_rc": 1, "on": [1]}}, None, False),
            "rollback_host_push_failed": ({"stage-baseline-0": {"partial": True, "timeout": True}}, None, True),
            "rollback_copy_failed_retry": ({"stage-baseline-0": {"partial": True, "timeout": True},
                "stage-baseline-0-fallback-copy": {"remote_rc": 1, "no_effect": True}}, None, True),
            "reader_partial_stage": ({"reader-stage": {"partial": True, "timeout": True}}, None, False),
            "reader_load_partial_failure": ({"reader-load": {"remote_rc": 1}}, None, False),
            "reader_child_unframed": ({"reader-load": {"child_unframed": True}}, None, False),
            "reader_capture_failure": ({"reader-dmesg-after": {"remote_rc": 1}}, None, False),
            "missing_recovery_console": ({"capture-pstore-console": {"remote_rc": 1, "stdout": b""}}, None, False),
            "wrong_reader_gnss_reservation": ({"reader-gnss-reservation": {"stdout": fixture_gnss(size=0x20200)}}, None, False),
            "wrong_initial_gnss_reservation": ({"initial-gnss-reservation": {"stdout": fixture_gnss(size=0x20200)}}, None, False),
            "selinux_partial_failure": ({"reader-selinux-permissive": {"remote_rc": 1}}, None, False),
            "silicon_multi_timeout": ({}, lambda text: text.replace("name=multi rc=0", "name=multi rc=-110"), False)}
        for name, (rules, log_change, accepted) in failure_cases.items():
            folder = packet / name
            folder.mkdir()
            model = StorageModel(folder, selected, rules=rules, log_change=log_change)
            clock = models.VirtualClock()
            trial = StorageCycle(folder, copy.deepcopy(selected), inputs / "candidate", inputs / "baseline", model,
                                 reader_path=inputs / "reader", seconds=60, clock=clock.now, sleep=clock.sleep)
            with mock.patch.object(phase4_device.subprocess, "run", side_effect=model.run_command), contextlib.redirect_stdout(io.StringIO()):
                outcome = trial.run()
            write_json(folder / "result.json", outcome)
            require(outcome["passed"] == accepted, "Cycle model disagrees: " + name + ": " + str(outcome.get("error")))
            require(model.boot_hash == selected["rollback_pins"]["template"]["sha256"], "Modeled baseline changed: " + name)
            if name == "wrong_initial_gnss_reservation":
                require(outcome.get("baseline_untouched") and not outcome["candidate_write_attempted"] and
                        outcome["operations"]["reboots"] == 0, "Wrong GNSS FDT reached a candidate write/reboot")
            else:
                require(outcome["baseline_verified"], "Modeled baseline was not verified after failure: " + name)
            require(not model.files and not model.module_live and model.selinux == "Enforcing", "Modeled cleanup failed: " + name)
            if name == "baseline_prestage_partial":
                require(not outcome["candidate_write_attempted"] and outcome["operations"]["reboots"] == 0,
                        "Candidate mutated after baseline prestaging failure")
            require(not outcome["phase_4_gate_passed"], "Storage cycle claimed full Phase 4")
            require(outcome["storage_gate_passed"] == outcome["passed"], "Failed lifecycle claimed a storage gate: " + name)
            require(set(model.rule_hits) == set(rules), "A modeled failure was not exercised: " + name)
            if name == "rollback_host_push_failed":
                require(outcome.get("rollback_prestaged_fallbacks") == ["stage-baseline-0"],
                        "Rollback did not use the independently verified prestaged baseline")
            cases.append({"name": name, "passed": True, "accepted": outcome["passed"], "modeled": True,
                          "journal_checks": model.journal_checks})

        recovered = copy.deepcopy(selected)
        recovered.update(capture_route=RECOVERY_ROUTE,
                         record_contract={"entry_pa": 0x83000000, "ba_pa": 0x84500000, "checkpoint": 0})
        recovery_variants = {
            "committed_binary": {"accepted": True},
            "binary_tail": {"accepted": True, "tail": b"\0\xffSTACKSHOT\0\n"},
            "partial_tail": {"accepted": True, "tail": b"INCOMPLETE"},
            "large_log": {"accepted": True, "log_change": lambda text: "PADDING\n" * 2000 + text},
            "max_log": {"accepted": True, "tail": b"\0" * (131072 - len(fixture_console(recovered)))},
            "over_max_log": {"tail": b"\0" * (131073 - len(fixture_console(recovered)))},
            "missing_pmsg": {"raw_change": lambda raw: b""},
            "truncated_header": {"raw_change": lambda raw: raw[:31]},
            "truncated_record": {"raw_change": lambda raw: raw[:287]},
            "truncated_log": {"raw_change": lambda raw: raw[:-1]},
            "trailing_bytes": {"raw_change": lambda raw: raw + b"\0"},
            "bad_magic": {"raw_change": lambda raw: b"BADMAGIC" + raw[8:]},
            "bad_version": {"raw_change": lambda raw: raw[:8] + struct.pack("<I", 2) + raw[12:]},
            "bad_record_size": {"raw_change": lambda raw: raw[:12] + struct.pack("<I", 255) + raw[16:]},
            "uncommitted": {"raw_change": lambda raw: raw[:28] + b"\0" * 4 + raw[32:]},
            "bad_crc": {"raw_change": lambda raw: raw[:24] + b"\0" * 4 + raw[28:]},
            "corrupt_record": {"raw_change": lambda raw: raw[:100] + bytes([raw[100] ^ 1]) + raw[101:]},
            "corrupt_binary_tail": {"tail": b"\0\xff", "raw_change": lambda raw: raw[:-1] + b"\0"},
            "wrong_loader_magic": {"record_change": lambda values: values.__setitem__(0, 0)},
            "wrong_return_status": {"record_change": lambda values: values.__setitem__(3, 5)},
            "wrong_log_address": {"record_change": lambda values: values.__setitem__(6, values[6] + 8)},
            "wrong_log_length": {"record_change": lambda values: values.__setitem__(7, values[7] - 1)},
            "wrong_entry_el": {"record_change": lambda values: values.__setitem__(8, 2)},
            "wrong_counter_frequency": {"record_change": lambda values: values.__setitem__(11, 24000000)},
            "wrong_cpu": {"record_change": lambda values: values.__setitem__(12, 0x410fd090)},
            "wrong_entry_configuration": {"record_change": lambda values: values.__setitem__(13, values[13] + 4)},
            "wrong_bootargs_configuration": {"record_change": lambda values: values.__setitem__(14, values[14] + 8)},
            "wrong_checkpoint": {"record_change": lambda values: values.__setitem__(15, 1)},
            "stale_nonce": {"log_change": lambda text: text.replace(NONCE, "d" * 32)},
            "duplicate_nonce": {"log_change": lambda text: text.replace("HAKIOS_RUN_NONCE=" + NONCE,
                ("HAKIOS_RUN_NONCE=" + NONCE + "\n") * 2)},
            "console_mismatch": {"console_change": lambda raw: raw + b"\0"},
            "same_length_tail_mismatch": {"tail": b"\0\xff", "console_change": lambda raw: raw[:-1] + b"\0"},
            "multi_fatal_protocol": {"log_change": lambda text: text.replace("name=multi rc=0", "name=multi rc=-5")},
        }
        for name, variant in recovery_variants.items():
            observed, error, parsed = True, None, {"checks": {}}
            try:
                change, tail = variant.get("log_change"), variant.get("tail", b"")
                raw = fixture_recovery(recovered, change=change, tail=tail,
                                       record_change=variant.get("record_change"))
                console = fixture_console(recovered, change=change, tail=tail)
                if variant.get("raw_change"):
                    changed = variant["raw_change"](raw)
                    require(changed != raw, "Recovery mutation was not exercised: " + name)
                    raw = changed
                if variant.get("console_change"):
                    console = variant["console_change"](console)
                record, banks = decode_recovery(raw, console, recovered)
                validate_storage(record, banks, recovered, parsed)
                require(record["capture"]["bytes"] == len(console), "Recovery raw log extent mismatch")
            except (ValueError, UnicodeError) as exc:
                observed, error = False, str(exc)
            require(observed == variant.get("accepted", False), "Recovery parser disagrees: " + name + ": " + str(error))
            cases.append({"name": "recovery_" + name, "accepted": observed, "passed": True,
                          "modeled": True, "rejection": error, "checks": parsed["checks"]})

        for key in RAMOOPS_PARAMETERS:
            raw = fixture_ramoops().replace(f"{key}={RAMOOPS_PARAMETERS[key]}\n".encode(),
                                            f"{key}={RAMOOPS_PARAMETERS[key] + 1}\n".encode())
            try:
                validate_ramoops_parameters(raw)
            except ValueError:
                cases.append({"name": "ramoops_changed_" + key, "accepted": False, "passed": True, "modeled": True})
            else:
                raise ValueError("Changed ramoops geometry was accepted: " + key)

        recovery_cycles = {
            "success_before_rollback": ({}, None, True),
            "missing_pmsg": ({"capture-pstore-pmsg": {"remote_rc": 1, "stdout": b""}}, None, False),
            "unframed_pmsg": ({"capture-pstore-pmsg": {"framing": "missing"}}, None, False),
            "failed_console_command": ({"capture-pstore-console": {"remote_rc": 1}}, None, False),
            "corrupt_pmsg": ({"capture-pstore-pmsg": {"stdout": b"CORRUPTED"}}, None, False),
            "wrong_initial_geometry": ({"initial-ramoops-parameters": {"stdout": b"mem_size=0\n"}}, None, False),
            "wrong_recovery_geometry": ({"capture-ramoops-parameters": {"stdout": b"mem_size=0\n"}}, None, False),
            "partial_candidate_write": ({"write-candidate": {"partial": True, "timeout": True}}, None, False),
            "rollback_prestaged_fallback": ({"stage-baseline-0": {"partial": True, "timeout": True}}, None, True),
            "fatal_multi": ({}, lambda text: text.replace("name=multi rc=0", "name=multi rc=-5"), False),
        }
        for name, (rules, log_change, accepted) in recovery_cycles.items():
            folder = packet / ("recovery_cycle_" + name)
            folder.mkdir()
            model = StorageModel(folder, recovered, rules=rules, log_change=log_change)
            clock = models.VirtualClock()
            trial = StorageCycle(folder, copy.deepcopy(recovered), inputs / "candidate", inputs / "baseline", model,
                                 seconds=60, clock=clock.now, sleep=clock.sleep)
            with mock.patch.object(phase4_device.subprocess, "run", side_effect=model.run_command), contextlib.redirect_stdout(io.StringIO()):
                outcome = trial.run()
            write_json(folder / "result.json", outcome)
            require(outcome["passed"] == accepted, "Recovery lifecycle disagrees: " + name + ": " + str(outcome.get("error")))
            require(model.boot_hash == recovered["rollback_pins"]["template"]["sha256"] and
                    not model.files and not model.module_live and model.selinux == "Enforcing",
                    "Recovery lifecycle failed baseline/file/security cleanup: " + name)
            require(set(model.rule_hits) == set(rules), "Recovery failure was not exercised: " + name)
            require(not any(event["name"].startswith("reader-") for event in model.events) and
                    outcome["operations"]["module_loads"] == outcome["operations"]["security_changes"] == 0,
                    "Recovery capture reached the legacy Android reader")
            require(outcome["storage_gate_passed"] == outcome["passed"] and not outcome["phase_4_gate_passed"],
                    "Failed recovery lifecycle claimed a storage/Phase 4 gate")
            if name == "wrong_initial_geometry":
                require(outcome.get("baseline_untouched") and not outcome["candidate_write_attempted"] and
                        outcome["operations"]["reboots"] == 0, "Invalid geometry reached a candidate mutation")
            else:
                require(outcome["baseline_verified"], "Recovery baseline restoration unverified: " + name)
            if accepted:
                events = [event["name"] for event in model.events]
                require(events.index("capture-pstore-pmsg") < events.index("restore-baseline-0"),
                        "Recovery log was read after baseline restoration")
            cases.append({"name": "recovery_cycle_" + name, "passed": True, "accepted": accepted,
                          "modeled": True, "journal_checks": model.journal_checks})
        result.update(passed=True, cases=cases, case_count=len(cases))
    except Exception as exc:
        result.update(error=str(exc), cases=cases, case_count=len(cases))
    write_json(packet / "result.json", result)
    note = (f"\n\n## P4-033 — Storage harness failure models ({packet.name})\n\n"
        "Purpose/files: scripts/phase4-test-storage-trial.py, phase4_storage.py and phase4-storage-trial.py. "
        "Exercise actual parser and explicit-serial/framed ADB lifecycle against deliberately modeled logs/transports. "
        "Cover independent GNSS/recovery prefixes and raw/tail extents, valid ANSI SGR and malformed controls, "
        "binary/partial tails, logs beyond the old 8KiB capacity, exact live GNSS FDT reservation/binding, "
        "rejection before candidate mutation, stale/truncated/conflicting "
        "evidence, exact reporting/pending grammar and legacy completion rejection, per-command driver/user "
        "correspondence preventing aggregate labels from concealing one-block commands, one-entry UFS "
        "PRDT/protocol/hashes, fatal status despite a cleared doorbell, failed cleanup, "
        "partial writes, no recovery, reader staging/load/capture failures and SELinux restoration. "
        "Every modeled device mutation checks durable intent. "
        "Recovery tests cover CRC/commit/configuration/nonce, complete binary equality, capacity, live ramoops "
        "geometry and capture-before-rollback without an Android module or SELinux change. "
        f"Verification: passed={result['passed']}; cases={result['case_count']}; error={result.get('error')}; packet "
        f"`{result['packet']}`. No physical device operation or silicon evidence. Rollback: remove these new "
        "host scripts/selection; preserve the tested driver, Phase 3 and all Android images.\n")
    documents(packet, {"docs/IMPLEMENTATION-LOG.md": (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    write_json(PROJECT / "manifests/phase4-storage-trial-tests.json", result)
    print(json.dumps({key: value for key, value in result.items() if key not in ("cases", "sources")}, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
