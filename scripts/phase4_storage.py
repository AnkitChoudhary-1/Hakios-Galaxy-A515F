"""Bounded storage-only silicon cycle and strict assembly-log validation.

Importing this module never queries a phone. The C-loader gate remains separate.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import struct
import uuid
import zlib

from phase4_device import BOOT
from phase4_reporting import reporting_checks
from phase4_support import PROJECT, pin, require, write_json
from boot_formats import parse_fdt, reg_ranges, scalar, sha256, strings


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cycle = load("phase4_storage_base_cycle", PROJECT / "scripts/phase4-device-cycle.py")
SUPPORT = ("phase4_storage.py", "phase4-storage-trial.py", "phase4-test-storage-trial.py",
           "phase4-device-cycle.py", "phase4_device.py", "phase4_support.py",
           "boot_formats.py", "test-boot-formats.py", "phase4-test-device-cycle.py",
           "phase4-test-capture.py", "phase4_pstore.py", "phase4_envelope.py",
           "phase4_reporting.py")
RECORD_MAGIC = "32454c5241494b48"
GNSS_RESERVATION = (0xfb000000, 0xfb7fffff)
UFS_ERROR_MASK = 0x70884
RECOVERY_ROUTE = "recovery-envelope-v1"
RECOVERY_MAGIC = b"HKUFSR01"
RECOVERY_HEADER = struct.Struct("<8s6I")
RECOVERY_COMMIT = 0x31434b48
MAX_LOG_BYTES = 131072
RECOVERY_MAX_BYTES = RECOVERY_HEADER.size + 256 + MAX_LOG_BYTES
RAMOOPS_PARAMETERS = {"mem_address": 0xf9d10000, "mem_size": 0x200000,
    "record_size": 0x80000, "console_size": 0x80000, "ftrace_size": 0x80000,
    "pmsg_size": 0x80000, "ecc": 0, "mem_type": 0}
RAMOOPS_COMMAND = ("for hakios_parameter in " + " ".join(RAMOOPS_PARAMETERS) +
    "; do printf '%s=' \"$hakios_parameter\"; "
    "cat /sys/module/ramoops/parameters/\"$hakios_parameter\" || exit 1; done")


def validate_ramoops_parameters(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 4096, "Invalid ramoops parameter capture")
    rows = raw.decode("ascii", "strict").splitlines()
    values = {}
    for row in rows:
        require(row.count("=") == 1, "Malformed ramoops parameter")
        key, value = row.split("=")
        require(key in RAMOOPS_PARAMETERS and key not in values and
                re.fullmatch(r"(?:0x[0-9a-fA-F]+|[0-9]+)", value), "Invalid/duplicate ramoops parameter")
        values[key] = int(value, 16 if value.startswith("0x") else 10)
    require(values == RAMOOPS_PARAMETERS, "Recovery ramoops geometry differs from the assembly console contract")
    return values


def fields(line, marker):
    require(line.startswith(marker + " "), "Wrong diagnostic marker: " + marker)
    out = {}
    for word in line[len(marker) + 1:].split():
        require(word.count("=") == 1, "Malformed diagnostic field: " + word)
        key, value = word.split("=")
        require(key not in out and key and value, "Duplicate/empty diagnostic field: " + key)
        out[key] = value
    return out


def number(row, name, *, base=10):
    raw = row.get(name, "")
    pattern = r"-?[0-9]{1,20}" if base == 10 else r"0x[0-9a-f]{1,16}"
    require(re.fullmatch(pattern, raw), "Invalid/missing numeric field: " + name)
    return int(raw, base)


def one(log, marker):
    rows = [line for line in log.splitlines() if line.startswith(marker + " ")]
    require(len(rows) == 1, "Missing/duplicate marker: " + marker)
    return fields(rows[0], marker)


def validate_gnss_reservation(raw):
    # This Android kernel omits reserved-memory children from /proc/iomem.
    # Validate the original live FDT, not a source snapshot or an invented
    # iomem entry. The reservation is shared GNSS memory, not a DMA allocation.
    require(isinstance(raw, bytes) and 40 <= len(raw) <= 1048576, "Invalid live GNSS FDT bound")
    tree = parse_fdt(raw)
    require(tree.header["totalsize"] == len(raw), "Live FDT has trailing bytes")
    parent = tree.nodes.get("/reserved-memory", {})
    node = tree.nodes.get("/reserved-memory/gnss_if", {})
    owner = tree.nodes.get("/gnss_pdata", {})
    require(parent.get("ranges") == b"" and scalar(parent.get("#address-cells", b"")) == 2 and
            scalar(parent.get("#size-cells", b"")) == 1,
            "Live GNSS reserved-memory translation/cell contract changed")
    require(strings(node.get("compatible", b"")) == ["exynos,gnss_if"] and "reusable" not in node and
            all(strings(props.get("status", b"")) in ([], ["okay"], ["ok"])
                for props in (tree.nodes["/"], parent, node)), "Live GNSS reservation is missing, disabled or reusable")
    ranges = reg_ranges(node.get("reg", b""), 2, 1)
    require(len(ranges) == 1 and (ranges[0]["start"], ranges[0]["end_exclusive"] - 1) == GNSS_RESERVATION,
            "Live GNSS reservation differs from the bounded assembly-copy region")
    phandle = scalar(node.get("phandle", b""))
    require(phandle > 0 and scalar(node.get("linux,phandle", node.get("phandle", b""))) == phandle and
            scalar(owner.get("memory-region", b"")) == phandle,
            "Live GNSS memory-region binding changed")
    return {"start": GNSS_RESERVATION[0], "end": GNSS_RESERVATION[1], "name": "gnss_if",
            "path": "/reserved-memory/gnss_if", "source": "live_linux_exported_fdt", "fdt_sha256": sha256(raw)}


def normalize_dmesg(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 2097152, "Reader output exceeds its bound")
    text = raw.decode("ascii", "strict")
    # Android dmesg adds SGR colour around timestamps and message bodies.
    text = re.sub(r"\x1b\[(?:[0-9]{1,3}(?:;[0-9]{1,3})*)?m", "", text)
    require(all(32 <= ord(c) <= 126 or c in "\t\r\n" for c in text),
            "Malformed ANSI escape or control byte in Android dmesg")
    return text.replace("\r", "")


def normalize_log(text):
    # XNU printf lines include an internal timestamp; user console lines do not.
    return "\n".join(re.sub(r"^\[\s*[0-9.]+\]:\s*", "", line)
                     for line in text.replace("\r", "").splitlines()) + "\n"


def decode_console(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 131072, "Recovery console exceeds the log bound")
    end = 0
    for i, value in enumerate(raw):
        if value not in (9, 10, 13) and not 32 <= value <= 126:
            break
        if value == 10:
            end = i + 1
    require(end > 0, "Recovery console has no complete printable lines")
    return normalize_log(raw[:end].decode("ascii")), {
        "bytes": len(raw), "text_bytes": end, "tail_bytes": len(raw) - end}


def decode_recovery(raw, console, selected):
    """Validate the committed binary pmsg envelope against the raw console.

    CRC covers the first 24 header bytes and every record/log byte. Compare
    complete binary logs before reducing them to printable diagnostic lines.
    The embedded user frame supplies the fresh candidate nonce.
    """
    require(isinstance(raw, bytes) and RECOVERY_HEADER.size + 256 < len(raw) <= RECOVERY_MAX_BYTES,
            "Recovery envelope exceeds its exact bound or is truncated")
    magic, version, record_bytes, log_bytes, total_bytes, crc, commit = RECOVERY_HEADER.unpack_from(raw)
    require(magic == RECOVERY_MAGIC and version == 1 and record_bytes == 256 and
            0 < log_bytes <= MAX_LOG_BYTES and total_bytes == len(raw) ==
            RECOVERY_HEADER.size + record_bytes + log_bytes and commit == RECOVERY_COMMIT,
            "Recovery envelope header, extent or commit is invalid")
    require(zlib.crc32(raw[RECOVERY_HEADER.size:], zlib.crc32(raw[:24])) == crc,
            "Recovery envelope CRC32 mismatch")
    values = struct.unpack_from("<32Q", raw, RECOVERY_HEADER.size)
    require(values[0] == int(RECORD_MAGIC, 16) and values[1:6] == (1, 256, 6, 0, 0) and
            values[6] == selected["log_pa"] and values[7] == log_bytes and values[8] == 1 and
            values[11] == 26000000 and (values[12] >> 4) & 0xfff == 0xd03,
            "Recovery loader record differs from the pinned successful return contract")
    contract = selected["record_contract"]
    require(values[13:16] == (contract["entry_pa"], contract["ba_pa"], contract["checkpoint"]),
            "Recovery record belongs to another loader configuration")
    log_raw = raw[RECOVERY_HEADER.size + record_bytes:]
    require(isinstance(console, bytes) and console == log_raw,
            "Recovery pmsg and independently retained raw console disagree")
    log, capture = decode_console(log_raw)
    user_frame(log, selected)
    record = {"magic": RECORD_MAGIC, "version": "1", "bytes": "256", "status": "6",
        "reason": "0", "code": "0", "log_pa": f"{values[6]:016x}", "log_len": str(log_bytes),
        "el": "1", "cntfrq": str(values[11]), "midr": f"{values[12]:016x}",
        "entry_daif": values[9], "entry_sctlr": values[10], "xnu_entry_pc": values[13],
        "xnu_boot_args_pa": values[14], "checkpoint_requested": values[15],
        "return_pc": values[16], "capture": capture, "crc32": f"{crc:08x}",
        "route": RECOVERY_ROUTE}
    return record, {"pmsg": log, "recovery": log}


def decode_reader(raw, selected, token):
    require(re.fullmatch(r"[0-9a-f]{32}", token), "Invalid reader capture token")
    text = normalize_dmesg(raw)
    lines = [re.sub(r"^\[\s*[0-9.]+\]\s*", "", line) for line in text.splitlines()]
    record_lines = [line for line in lines if line.startswith("HAKIOS_STORAGE_RECORD token=" + token + " ")]
    require(len(record_lines) == 1, "Missing/duplicate reader record")
    record = fields(record_lines[0], "HAKIOS_STORAGE_RECORD")
    require(record["magic"] == RECORD_MAGIC and number(record, "version") == 1 and
            number(record, "bytes") == 256 and number(record, "status") == 6 and
            number(record, "reason") == number(record, "code") == 0 and
            record["log_pa"] == f"{selected['log_pa']:016x}" and
            0 < number(record, "log_len") <= 131072 and number(record, "el") == 1 and
            number(record, "cntfrq") == 26000000 and
            (int(record["midr"], 16) >> 4) & 0xfff == 0xd03,
            "Saved loader record differs from the pinned successful return contract")
    require(not any(line == "HAKIOS_STORAGE_CAPTURE_REFUSED token=" + token for line in lines),
            "Reader refused the pinned buffer/header")
    banks, active, contents, capture = {}, None, [], None
    for line in lines:
        if line.startswith("HAKIOS_STORAGE_CAPTURE_BEGIN token=" + token + " "):
            row = fields(line, "HAKIOS_STORAGE_CAPTURE_BEGIN")
            bank = row.get("bank")
            require(active is None and bank == "gnss" and bank not in banks,
                    "Nested/duplicate reader bank")
            capture = {key: number(row, key) for key in ("bytes", "text_bytes", "tail_bytes")}
            require(capture["bytes"] == number(record, "log_len") and capture["text_bytes"] > 0 and
                    capture["tail_bytes"] >= 0 and capture["text_bytes"] + capture["tail_bytes"] == capture["bytes"],
                    "Reader prefix/tail length disagreement")
            active, contents = bank, []
        elif line.startswith("HAKIOS_STORAGE_CAPTURE_END token=" + token + " "):
            row = fields(line, "HAKIOS_STORAGE_CAPTURE_END")
            require(active is not None and row.get("bank") == active and number(row, "prefix_complete") == 1 and
                    all(number(row, key) == capture[key] for key in ("text_bytes", "tail_bytes")),
                    "Incomplete/conflicting reader bank")
            banks[active] = normalize_log("\n".join(contents) + "\n")
            active, contents = None, []
        elif active is not None:
            prefix = "HAKIOS_STORAGE_OUT: "
            if line.startswith(prefix):
                contents.append(line[len(prefix):])
            elif line.startswith("HAKIOS_STORAGE_"):
                raise ValueError("Wrong reader prefix inside a bank")
    require(active is None and set(banks) == {"gnss"}, "Missing/unterminated reader bank")
    record["capture"] = capture
    return record, banks


def user_frame(log, selected):
    starts = [i for i, line in enumerate(log.splitlines()) if line.startswith("HAKIOS_USER_BEGIN ")]
    ends = [i for i, line in enumerate(log.splitlines()) if line.startswith("HAKIOS_USER_EXIT ")]
    require(len(starts) == len(ends) == 1 and starts[0] < ends[0], "Missing/duplicate user frame")
    lines = log.splitlines()[starts[0]:ends[0] + 1]
    frame = "\n".join(lines) + "\n"
    begin = one(frame, "HAKIOS_USER_BEGIN")
    require(number(begin, "pid") == 1 and number(begin, "uid") == 0 and number(begin, "console") >= 0,
            "PID 1/root console unverified")
    require([line for line in lines if line.startswith("kern.bootargs=")] == ["kern.bootargs=" + selected["cmdline"]] and
            [line for line in lines if line.startswith("HAKIOS_RUN_NONCE=")] == ["HAKIOS_RUN_NONCE=" + selected["nonce"]],
            "Actual boot nonce/arguments differ from the candidate")
    return frame


def validate_storage(record, banks, selected, result):
    checks = result["checks"]
    primary = "pmsg" if selected.get("capture_route") == RECOVERY_ROUTE else "gnss"
    require(set(banks) == {primary, "recovery"} and banks[primary] == banks["recovery"],
            "Saved log and independently retained recovery console prefixes disagree")
    frame = user_frame(banks[primary], selected)
    full_frame = user_frame(banks["recovery"], selected)
    require(frame == full_frame, "Independently captured user frames disagree")
    checks.update(reporting_checks(frame, banks[primary]))
    checks["attributable_complete_matching_user_frames"] = True
    checks["pinned_loader_return_record"] = True
    platform = one(frame, "HAKIOS_PLATFORM")
    checks["a53_gicv2_single_core"] = (number(platform, "gic") == 2 and number(platform, "cores") == 1 and
                                      number(platform, "midr", base=16) == int(record["midr"], 16))
    samples = [fields(line, "HAKIOS_TIMER_SAMPLE") for line in frame.splitlines()
               if line.startswith("HAKIOS_TIMER_SAMPLE ")]
    timer_ok, previous_after = len(samples) == 3, -1
    for i, row in enumerate(samples, 1):
        before, after = number(row, "irq_before"), number(row, "irq_after")
        timer_ok &= (number(row, "index") == i and number(row, "select_rc") == number(row, "read_rc") == 0 and
                     900000 <= number(row, "elapsed_us") <= 3000000 and before >= previous_after and
                     after > before and number(row, "pass") == 1)
        previous_after = after
    checks["three_measured_monotonic_timer_samples"] = timer_ok and frame.count("HAKIOS_TIMER_PASS samples=3\n") == 1
    result["timer_samples"] = samples
    diag = one(frame, "HAKIOS_STORAGE_DIAG")
    checks["storage_abi_and_ready"] = (number(diag, "ufs_rc") == 0 and number(diag, "abi") == 2 and
                                      number(diag, "bytes") == 336 and number(diag, "init_rc") == 0)
    transfers = [fields(line, "HAKIOS_UFS_TRANSFER") for line in frame.splitlines()
                 if line.startswith("HAKIOS_UFS_TRANSFER ")]
    require([row.get("name") for row in transfers] == ["single", "multi", "reread"], "Wrong transfer order/count")
    result["transfers"] = transfers
    for row, blocks in zip(transfers, (1, 16, 1)):
        name = row["name"]
        valid = (number(row, "rc") == number(row, "ocs") == 0 and number(row, "lba") == 27792 and
                 number(row, "blocks") == blocks and number(row, "lifecycle") == 23 and
                 number(row, "transaction") == 33 and
                 all(number(row, field) == 0 for field in ("response", "status", "residual", "sense_len")) and
                 number(row, "stages", base=16) == 0xfe and
                 number(row, "prdt_count") == 1 and number(row, "prdt_bytes") == 128 and
                 0 < number(row, "elapsed_us") <= 5000000 and
                 row.get("sha256") == selected["read_hashes"]["multi" if blocks == 16 else "single"])
        checks[name + "_protocol_prdt_lifecycle_and_independent_sha256"] = valid
        rc_key, ocs_key = {"single": ("s_rc", "s_ocs"), "multi": ("m_rc", "m_ocs"), "reread": ("r_rc", "r_ocs")}[name]
        checks[name + "_summary_agrees"] = (number(diag, rc_key) == number(row, "rc") and
                                            number(diag, ocs_key) == number(row, "ocs"))
    checks["reread_matches_single"] = transfers[0]["sha256"] == transfers[2]["sha256"] == selected["read_hashes"]["single"]
    guard = one(frame, "HAKIOS_STORAGE_WRITE_GUARD")
    checks["write_rejected_before_doorbell"] = (number(guard, "rc") == -30 and number(guard, "rejected") >= 1 and
                                              number(guard, "doorbell", base=16) == 0 and number(guard, "pass") == 1)
    checks["strict_storage_observation_markers"] = (
        [line for line in frame.splitlines() if line.startswith("HAKIOS_STORAGE_TRANSFER_STATUS")] ==
            ["HAKIOS_STORAGE_TRANSFER_STATUS single=1 multi=1 reread=1 write_guard=1"] and
        [line for line in frame.splitlines() if line.startswith("HAKIOS_IMAGE_LOAD_OBSERVATION")] ==
            ["HAKIOS_IMAGE_LOAD_OBSERVATION bytes=65536 commands=1 sha256=" +
             selected["read_hashes"]["multi"] + " known_contents=host_check_required"] and
        frame.count("HAKIOS_A51_DIAG_PASS\n") == 1 and "HAKIOS_A51_DIAG_FAIL" not in frame)
    exit_row = one(frame, "HAKIOS_USER_EXIT")
    checks["user_exit_zero"] = number(exit_row, "outcome") == 0 and number(exit_row, "timer_verified") == 1
    cycle.validate_snapshot(banks[primary], selected, result)
    reports = [fields(line, "HAKIOS_UFS_REPORT") for line in banks[primary].splitlines()
               if line.startswith("HAKIOS_UFS_REPORT ")]
    result["driver_reports"] = reports
    terminal = [fields(line, "HAKIOS_UFS_TERMINAL") for line in banks[primary].splitlines()
                if line.startswith("HAKIOS_UFS_TERMINAL ")]
    result["terminal_telemetry"] = terminal
    activation_names = ("device-start", "lun0-start", "unit-ready")
    command_names = (*activation_names, "single", "multi", "reread")
    checks["six_ordered_driver_commands"] = [row.get("name") for row in reports] == list(command_names)
    checks["six_ordered_terminal_captures"] = [row.get("name") for row in terminal] == list(command_names)
    for name in command_names:
        matches = [row for row in terminal if row.get("name") == name]
        checks[name + "_terminal_capture"] = (len(matches) == 1 and
            all(number(matches[0], key, base=16) == 0 for key in ("dbr", "task", "final_dbr", "rx_error")) and
            number(matches[0], "is", base=16) & UFS_ERROR_MASK == 0 and
            number(matches[0], "is", base=16) & 1 == 1)
        matching_reports = [row for row in reports if row.get("name") == name]
        checks[name + "_driver_completion_and_cleanup"] = (len(matching_reports) == 1 and
            all(number(matching_reports[0], key) == 0 for key in ("rc", "cleanup_rc", "ocs", "quarantined")) and
            all(number(matching_reports[0], key) == 1 for key in ("submitted", "completed", "restored")) and
            number(matching_reports[0], "stages", base=16) == 0xfe)
        if name in activation_names:
            checks[name + "_nondata_protocol_geometry"] = (len(matching_reports) == 1 and
                all(number(matching_reports[0], key) == 0 for key in
                    ("lba", "blocks", "bytes", "prdt_count", "prdt_bytes", "resp", "status", "residual", "sense_len")) and
                number(matching_reports[0], "trans", base=16) == 0x21 and
                0 < number(matching_reports[0], "elapsed_us") <= 5000000)
    for transfer, blocks in zip(transfers, (1, 16, 1), strict=True):
        name = transfer["name"]
        matching_reports = [row for row in reports if row.get("name") == name]
        # Bind each user report to the actual submitted command. An aggregate
        # digest or a rewritten 16-block label cannot stand in for one 64 KiB
        # READ(10). Kernel trans is hexadecimal; the user ABI uses decimal.
        checks[name + "_driver_user_command_correspondence"] = (len(matching_reports) == 1 and
            number(matching_reports[0], "lba") == number(transfer, "lba") == 27792 and
            number(matching_reports[0], "blocks") == number(transfer, "blocks") == blocks and
            number(matching_reports[0], "bytes") == blocks * 4096 and
            number(matching_reports[0], "trans", base=16) == number(transfer, "transaction") == 0x21 and
            number(matching_reports[0], "resp") == number(transfer, "response") == 0 and
            all(number(matching_reports[0], key) == number(transfer, key)
                for key in ("rc", "ocs", "status", "residual", "sense_len", "prdt_count", "prdt_bytes", "elapsed_us")))
    result["storage_gate_passed"] = (all(checks.values()) and "error" not in result and
                                     "restoration_error" not in result)
    require(result["storage_gate_passed"], "Hardware storage checks failed: " + ", ".join(k for k, v in checks.items() if not v))


def privileged(device, name, command, **kwargs):
    """Frame both the ksud child and outer su exit; a prompt is not success."""
    require("HAKIOS_STORAGE_EOF" not in command, "Invalid privileged command delimiter")
    inner = ("{ " + command + "; }; hakios_priv_rc=$?; "
             "printf '\\nHAKIOS_PRIV_EXIT:%d\\n' \"$hakios_priv_rc\"; exit \"$hakios_priv_rc\"")
    wrapper = ("/data/adb/ksu/bin/ksud debug su -g << 'HAKIOS_STORAGE_EOF'\n" + inner +
               "\nHAKIOS_STORAGE_EOF\nhakios_ksud_rc=$?; (exit \"$hakios_ksud_rc\")")
    raw = device.root(name, wrapper, **kwargs)
    statuses = re.findall(rb"\nHAKIOS_PRIV_EXIT:([0-9]{1,3})\r?\n", raw)
    require(len(statuses) == 1 and int(statuses[0]) == 0, name + ": privileged child failed or was unframed")
    return raw


class StorageCycle(cycle.Cycle):
    def __init__(self, *args, reader_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reader_path = reader_path
        self.result.update(scope="Storage-only: 4KiB -> 64KiB -> 4KiB, write guard, timers and rollback",
                           storage_gate_passed=False, phase_4_gate_passed=False)
        self.result["operations"].update(module_loads=0, module_unloads=0, security_changes=0)

    def target(self, label, recovery):
        super().target(label, recovery)
        require(self.device.text(label + "-ufs-block-size", "cat /sys/class/block/sda/queue/logical_block_size",
                                 recovery=recovery) == "4096", "Unexpected UFS logical block size")
        require(self.device.text(label + "-boot-start", "cat /sys/class/block/sda12/start", recovery=recovery) == "222336",
                "Boot partition no longer starts at LBA 27792")
        if self.selected.get("capture_route") == RECOVERY_ROUTE:
            self.result.setdefault("ramoops_parameters", {})[label] = validate_ramoops_parameters(
                self.device.root(label + "-ramoops-parameters", RAMOOPS_COMMAND,
                                 recovery=recovery, limit=4096))
        elif not recovery:
            self.result.setdefault("gnss_reservations", {})[label] = validate_gnss_reservation(
                self.device.root(label + "-gnss-reservation", "cat /sys/firmware/fdt", limit=1048576))

    def stage(self, name, local, remote, expected, recovery=False):
        if name == "stage-candidate":
            baseline_remote = "/data/local/tmp/hakios-p4-baseline-" + self.selected["nonce"] + ".img"
            super().stage("stage-preflight-baseline", self.baseline, baseline_remote,
                          self.selected["rollback_pins"]["template"])
            self.result["checks"]["baseline_prestaged_before_candidate"] = True
        try:
            super().stage(name, local, remote, expected, recovery)
        except Exception as exc:
            # A disconnected/failed host push must not be the only rollback source.
            # Only replace a destination this cycle already claimed before its push.
            if not name.startswith("stage-baseline-") or remote not in self.staging:
                raise
            self.result.setdefault("rollback_transfer_errors", []).append({"name": name, "error": str(exc)})
            source = "/data/local/tmp/hakios-p4-baseline-" + self.selected["nonce"] + ".img"
            require(self.result["checks"].get("baseline_prestaged_before_candidate") and source in self.staging,
                    "No verified prestaged baseline is available")
            source_q, remote_q = shlex.quote(source), shlex.quote(remote)
            self.device.root(name + "-fallback-source", "test -f " + source_q + " && test ! -L " + source_q,
                             recovery=recovery)
            require(self.device.text(name + "-fallback-source-size", "stat -c %s " + source_q,
                                     recovery=recovery) == str(expected["bytes"]), "Prestaged baseline size changed")
            require(self.device.text(name + "-fallback-source-hash", "sha256sum " + source_q,
                                     recovery=recovery).split()[0] == expected["sha256"], "Prestaged baseline hash changed")
            self.intent("file_writes", name + "-fallback-copy")
            self.device.root(name + "-fallback-copy", "cp " + source_q + " " + remote_q + " && sync",
                             recovery=recovery, timeout=90)
            require(self.device.text(name + "-fallback-size", "stat -c %s " + remote_q,
                                     recovery=recovery) == str(expected["bytes"]), "Rollback copy size mismatch")
            require(self.device.text(name + "-fallback-hash", "sha256sum " + remote_q,
                                     recovery=recovery).split()[0] == expected["sha256"], "Rollback copy hash mismatch")
            self.result.setdefault("rollback_prestaged_fallbacks", []).append(name)

    def capture(self):
        self.capture_attempted = True
        self.target("capture", True)
        boot_id = self.device.text("capture-boot-id", "cat /proc/sys/kernel/random/boot_id", recovery=True)
        require(cycle.UUID.fullmatch(boot_id) and boot_id != self.result["boot_id_before"], "Fresh recovery UUID unverified")
        self.result["recovery_boot_id"] = boot_id
        # Retain BOTH original exports before parsing, even if either fails.
        self.device.root("capture-pstore-files", "ls -ln /sys/fs/pstore", recovery=True, check=False)
        saved = {}
        for bank in ("console", "pmsg"):
            saved[bank] = self.device.root("capture-pstore-" + bank,
                "test -r /sys/fs/pstore/" + bank + "-ramoops-0 && cat /sys/fs/pstore/" + bank + "-ramoops-0",
                recovery=True, check=False, timeout=15, limit=2097152)
        if self.selected.get("capture_route") == RECOVERY_ROUTE:
            for bank in ("console", "pmsg"):
                matches = [row for row in self.device.records if row["name"] == "capture-pstore-" + bank]
                require(len(matches) == 1 and matches[0]["exit_code"] == 0,
                        "Recovery " + bank + " export failed or was unframed")
            record, banks = decode_recovery(saved["pmsg"], saved["console"], self.selected)
            self.result["log_capture"] = {"route": RECOVERY_ROUTE, "capture": record["capture"],
                "raw": {bank: {"path": "capture-pstore-" + bank + ".stdout.bin",
                    **pin(self.packet / ("capture-pstore-" + bank + ".stdout.bin"))} for bank in saved}}
            write_json(self.packet / "recovery-record.json", record)
            for bank, log in banks.items():
                (self.packet / (bank + ".log")).write_text(log, encoding="ascii")
            validate_storage(record, banks, self.selected, self.result)

    def reader_capture(self):
        device, result = self.device, self.result
        remote = "/data/local/tmp/hakios-p4-reader-" + self.selected["nonce"] + ".ko"
        quoted, staged, load_attempted, security_attempted = shlex.quote(remote), False, False, False
        token = uuid.uuid4().hex
        result["capture_token"] = token
        expected = self.selected["reader_module"]
        require(pin(self.reader_path) == {key: expected[key] for key in ("bytes", "sha256")}, "Reader module changed")
        original = device.text("reader-selinux-before", "getenforce")
        require(original in ("Enforcing", "Permissive", "Disabled"), "SELinux state unavailable")
        require(device.text("reader-kernel-release", "uname -r") == self.selected["reader_vermagic"].split()[0],
                "Restored Android kernel no longer matches the reader ABI")
        device.root("reader-module-absent", "test ! -d /sys/module/hakios_storage_reader")
        device.root("reader-file-absent", "test ! -e " + quoted + " && test ! -L " + quoted)
        result["gnss_reservation"] = validate_gnss_reservation(
            device.root("reader-gnss-reservation", "cat /sys/firmware/fdt", limit=1048576))
        device.root("reader-dmesg-before", "dmesg", limit=2097152)
        cleanup_errors, raw = [], None
        try:
            staged = True  # Even a failed push can leave a partial file.
            self.intent("file_writes", "reader-stage")
            device.adb("reader-stage", ["push", str(self.reader_path), remote], timeout=45)
            require(device.text("reader-stage-size", "stat -c %s " + quoted) == str(expected["bytes"]), "Reader staging size mismatch")
            require(device.text("reader-stage-hash", "sha256sum " + quoted).split()[0] == expected["sha256"], "Reader staging hash mismatch")
            if original == "Enforcing":
                security_attempted = True
                self.intent("security_changes", "reader-selinux-permissive")
                privileged(device, "reader-selinux-permissive", "setenforce 0 && test \"$(getenforce)\" = Permissive")
            load_attempted = True
            self.intent("module_loads", "reader-load")
            privileged(device, "reader-load", "insmod " + quoted + " expected_log_pa=" + str(self.selected["log_pa"]) +
                       " capture_token=" + token + " && test -d /sys/module/hakios_storage_reader", timeout=20)
            raw = device.root("reader-dmesg-after", "dmesg", limit=2097152)
            (self.packet / "dmesg.txt").write_bytes(raw)
        finally:
            if load_attempted:
                try:
                    self.intent("module_unloads", "reader-unload")
                    privileged(device, "reader-unload", "if test -d /sys/module/hakios_storage_reader; then "
                        "rmmod hakios_storage_reader; else :; fi && test ! -d /sys/module/hakios_storage_reader")
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            if security_attempted:
                try:
                    self.intent("security_changes", "reader-selinux-restore")
                    privileged(device, "reader-selinux-restore", "setenforce 1 && test \"$(getenforce)\" = Enforcing")
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            if staged:
                try:
                    self.cleanup(remote)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            result["reader_cleanup_errors"] = cleanup_errors
            result["checks"]["reader_unloaded_and_temporary_file_removed"] = not cleanup_errors
            try:
                result["checks"]["original_selinux_state_restored"] = device.text("reader-selinux-after", "getenforce") == original
                result["checks"]["reader_kept_verified_android_boot"] = (
                    device.text("reader-final-boot-id", "cat /proc/sys/kernel/random/boot_id") == result["boot_id_after"])
                device.root("reader-final-module-absent", "test ! -d /sys/module/hakios_storage_reader")
                device.root("reader-final-file-absent", "test ! -e " + quoted + " && test ! -L " + quoted)
            except Exception as exc:
                result["checks"]["reader_unloaded_and_temporary_file_removed"] = False
                result["reader_cleanup_errors"].append(str(exc))
        require(not result["reader_cleanup_errors"] and result["checks"]["original_selinux_state_restored"] and
                result["checks"]["reader_kept_verified_android_boot"], "Reader cleanup or Android state unverified")
        record, banks = decode_reader(raw, self.selected, token)
        # Recovery was captured before restoring Android; retain its binary tail
        # verbatim and compare only its explicitly measured printable prefix.
        recovery_path = self.packet / "capture-pstore-console.stdout.bin"
        console, console_capture = decode_console(recovery_path.read_bytes())
        require(console_capture == record["capture"], "GNSS/recovery raw, prefix or tail extents disagree")
        result["log_capture"] = {"gnss": record["capture"], "recovery": console_capture,
                                 "recovery_raw": {"path": recovery_path.name, **pin(recovery_path)}}
        banks["recovery"] = console
        for bank, log in banks.items():
            (self.packet / (bank + ".log")).write_text(log, encoding="ascii")
        write_json(self.packet / "reader-record.json", record)
        validate_storage(record, banks, self.selected, result)

    def restore(self):
        try:
            super().restore()
        except Exception:
            self.result["storage_gate_passed"] = False
            raise
        if self.selected.get("capture_route") == RECOVERY_ROUTE:
            if not self.result["baseline_verified"]:
                self.result["storage_gate_passed"] = False
            return
        if self.may_have_written and self.result["baseline_verified"]:
            try:
                self.reader_capture()
            except Exception as exc:
                # Failed evidence is not a failed baseline restoration.
                self.result.setdefault("error", str(exc))
                self.result["storage_gate_passed"] = False
                print("Storage evidence failed: " + str(exc), flush=True)
