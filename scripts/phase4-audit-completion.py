#!/usr/bin/env python3
"""Audit retained Phase 4 evidence offline; never query or modify a device.

The legacy labels are diagnostic strings, not physical acceptance evidence.
Capture before reconciling status. Verification replays original bytes and checks
the review index, input pins and recorded document/source changes.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

from phase4_support import PROJECT, index_packet, new_packet, pin, require, write_json

EXECUTION = "evidence/phase-4/silicon-execution/20261116T091954739903Z"
BASELINE = "eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67"
RESTORATION = "evidence/phase-4/baseline-restoration-review/20261116T015024935010Z"
GATE = "scripts/phase4-device-gate.py"
GATE_DISABLED = (
    "Legacy Phase 4 gate is disabled: constant peripheral labels and aggregate "
    "storage reports cannot qualify Phase 4. Use scripts/phase4-audit-completion.py "
    "for offline review."
)
DOCUMENTS = (
    "README.md", "docs/STATE.md", "docs/INDEX.md", "docs/HANDOFF.md",
    "docs/PHASE-4-COMPLETION-REVIEW.md", "docs/PHASE-4-UFS-REPAIR.md",
    "docs/PHASE-4-DEVICE-PATH.md", "docs/IMPLEMENTATION-LOG.md", "state.json",
)
SOURCES = (
    GATE, "scripts/phase4-record-baseline-restoration.py",
    "scripts/phase4_storage.py", "prototype/phase4-platform/hello.c",
    "prototype/phase4-platform/hakios.a51.c", "prototype/phase4-platform/hakios.a51.h",
    "prototype/phase4-platform/a51_ufs_readonly.h",
    "prototype/xnu-loader/pack_a51_payload.py", "prototype/xnu-loader/hakios_macho.py",
    "manifests/phase4-platform-build.json", "manifests/phase4-platform-adaptation.json",
    "manifests/phase4-readonly-revision.json",
)
REVIEW_SOURCES = ("scripts/phase4-audit-completion.py", "scripts/phase4-test-completion-audit.py")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized_records(raw):
    """Deduplicate recovered copies; retain whole records, not substrings."""
    rows = []
    for line in raw.decode("utf-8", "replace").splitlines():
        for match in re.finditer(r"HAKIOS_(?!OUT:|KERN:)[A-Z][A-Z0-9_]*(?:=|\s|$)", line):
            row = line[match.start():].strip()
            if row not in rows:
                rows.append(row)
            break
    return rows


def fields(record):
    parsed = {}
    for token in record.split()[1:]:
        match = re.fullmatch(r"([a-z][a-z0-9_]*)=([^\s]+)", token)
        if not match or match[1] in parsed:
            return {}
        parsed[match[1]] = match[2]
    return parsed


def unsigned(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value):
        return None
    return int(value)


def unique_fields(rows, prefix, **selector):
    found = [fields(row) for row in dict.fromkeys(rows) if row.startswith(prefix + " ")]
    found = [row for row in found if all(row.get(k) == str(v) for k, v in selector.items())]
    return found[0] if len(found) == 1 else {}


def analyze_records(rows, nonce, expected_single, expected_large):
    nonces = {row for row in rows if row.startswith("HAKIOS_RUN_NONCE")}
    attributed = bool(re.fullmatch(r"[0-9a-f]{32}", nonce)) and nonces == {"HAKIOS_RUN_NONCE=" + nonce}
    single = unique_fields(rows, "HAKIOS_UFS_TRANSFER", name="single")
    reread = unique_fields(rows, "HAKIOS_UFS_TRANSFER", name="reread")
    multi = unique_fields(rows, "HAKIOS_UFS_TRANSFER", name="multi")
    transfer_rows = [fields(row) for row in dict.fromkeys(rows) if row.startswith("HAKIOS_UFS_TRANSFER ")]
    transfer_set_valid = len(transfer_rows) == 3 and {row.get("name") for row in transfer_rows} == {"single", "multi", "reread"}
    common = {"rc": "0", "ocs": "0", "lba": "27792", "lifecycle": "23",
              "stages": "0xfe", "transaction": "33", "response": "0", "status": "0",
              "residual": "0", "sense_len": "0"}
    def valid_transfer(row, blocks, expected):
        elapsed = unsigned(row.get("elapsed_us"))
        return (all(row.get(k) == v for k, v in common.items()) and
                row.get("blocks") == str(blocks) and row.get("sha256") == expected and
                row.get("prdt_count") == str(blocks) and
                row.get("prdt_bytes") == str(blocks * 128) and
                elapsed is not None and 0 < elapsed <= 5000000)
    single_match = attributed and transfer_set_valid and valid_transfer(single, 1, expected_single)
    reread_match = attributed and transfer_set_valid and valid_transfer(reread, 1, expected_single)
    large_match = attributed and transfer_set_valid and valid_transfer(multi, 16, expected_large) and (
        unique_fields(rows, "HAKIOS_IMAGE_LOAD_VERIFIED") == {"bytes": "65536", "sha256": expected_large})
    guard = unique_fields(rows, "HAKIOS_STORAGE_WRITE_GUARD")
    rejected = unsigned(guard.get("rejected"))
    guard_observed = attributed and all(guard.get(k) == v for k, v in
        {"rc": "-30", "doorbell": "0x0", "pass": "1"}.items()) and rejected is not None and rejected >= 1
    timer_rows = [row for row in dict.fromkeys(rows) if row.startswith("HAKIOS_TIMER_SAMPLE ")]
    samples = []
    for i in range(1, 4):
        sample = unique_fields(rows, "HAKIOS_TIMER_SAMPLE", index=i)
        elapsed, before, after = (unsigned(sample.get(k)) for k in ("elapsed_us", "irq_before", "irq_after"))
        good = (sample.get("select_rc") == "0" and sample.get("read_rc") == "0" and
                sample.get("pass") == "1" and elapsed is not None and 900000 <= elapsed <= 1500000 and
                before is not None and after is not None and after > before)
        if samples:
            previous = unsigned(samples[-1].get("irq_after"))
            good = good and previous is not None and before >= previous
        samples.append({**sample, "replayed_valid": good})
    timers = (attributed and len(timer_rows) == 3 and all(s["replayed_valid"] for s in samples) and
              unique_fields(rows, "HAKIOS_TIMER_PASS") == {"samples": "3"})
    return {
        "nonce_record_attributable": attributed,
        "single_4k_hash_record_matches_candidate": single_match,
        "reread_4k_hash_record_matches_candidate": reread_match,
        "aggregate_64k_hash_record_matches_candidate": large_match,
        "write_rejection_record_observed": guard_observed,
        "timer_samples_replayed": timers, "timer_samples": samples,
        "user_exit_record_observed": attributed and unique_fields(rows, "HAKIOS_USER_EXIT") == {"outcome": "0", "timer_verified": "1"},
        "display_verified": False, "brightness_verified": False,
        "touch_verified": False, "keys_verified": False,
        "single_64k_read10_verified": False,
        "committed_recovery_envelope_verified": False,
        "qualifying_phase_4_cycle": False,
    }


def gate_guard_valid(raw):
    """Check that both execution entry points stop before their historical bodies."""
    try:
        tree = ast.parse(raw)
        assignments = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1 and
                       isinstance(node.targets[0], ast.Name) and node.targets[0].id == "LEGACY_GATE_DISABLED"}
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        cycle_guard = ast.parse("raise RuntimeError(LEGACY_GATE_DISABLED)").body[0]
        main_guard = ast.parse("print(LEGACY_GATE_DISABLED, file=sys.stderr)\nreturn 2").body
        return (assignments.get("LEGACY_GATE_DISABLED") == GATE_DISABLED and
                not functions["run_phase4_cycle"].decorator_list and not functions["main"].decorator_list and
                ast.dump(functions["run_phase4_cycle"].body[0]) == ast.dump(cycle_guard) and
                [ast.dump(node) for node in functions["main"].body[:2]] == [ast.dump(node) for node in main_guard])
    except (SyntaxError, ValueError, KeyError, IndexError, TypeError):
        return False


def capture_wrapper_provenance(review):
    """Retain discovery once; later guard runs must not change historical replay."""
    scanned, matching = [], []
    for path in sorted((PROJECT / "runs").glob("*/metadata.json")):
        raw = path.read_bytes()
        meta = json.loads(raw)
        rel = path.relative_to(PROJECT).as_posix()
        scanned.append({"path": rel, "bytes": len(raw), "sha256": sha(raw)})
        if any(str(arg).replace("\\", "/").split("/")[-1] == "phase4-device-gate.py"
               for arg in meta.get("command", [])):
            matching.append({"path": rel, "metadata": meta, "bytes": len(raw), "sha256": sha(raw)})
    provenance = {"captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "metadata present at completion-audit capture; not a reconstruction of unretained commands",
        "metadata_files_scanned": scanned, "matching_gate_metadata": matching}
    write_json(review / "wrapper-provenance.json", provenance)
    return matching


def capture_file(review, rel):
    raw = (PROJECT / rel).read_bytes()
    dest = review / "before" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    require((PROJECT / rel).read_bytes() == raw, "Input changed while capturing: " + rel)
    return pin(dest)


def review_result(review, execution):
    summary = json.loads((PROJECT / execution / "phase4_execution_summary.json").read_bytes())
    cycles = []
    for cycle_dir in sorted((PROJECT / execution).glob("cycle-*")):
        result = json.loads((cycle_dir / "cycle_result.json").read_bytes())
        candidate = (cycle_dir / "candidate-boot.img").read_bytes()
        require(re.fullmatch(r"[0-9a-f]{32}", result["nonce"]), "Invalid cycle nonce")
        require(result["rollback_sha256"] == BASELINE, "Unexpected reported rollback pin")
        require(len(candidate) == 61865984 and sha(candidate) == result["candidate_sha256"], "Candidate pin mismatch")
        require(result in summary["results"], "Cycle disagrees with original summary")
        dmesg = (cycle_dir / "dmesg.txt").read_bytes()
        console = (cycle_dir / "console-ramoops.log").read_bytes()
        rows = normalized_records(dmesg + b"\n" + console)
        cycle = {"cycle": result["cycle"], "nonce": result["nonce"],
                 "path": cycle_dir.relative_to(PROJECT).as_posix(),
                 "candidate": {"bytes": len(candidate), "sha256": sha(candidate)},
                 "expected_4k_sha256": sha(candidate[:4096]),
                 "expected_64k_sha256": sha(candidate[:65536]),
                 "original_qualifying_cycle_reported": result["qualifying_cycle_passed"],
                 "baseline_rollback_reported": result["baseline_verified_post_boot"],
                 "reconnect_mode_reported": result["reconnect_mode"],
                 "raw_hakios_line_count": sum("HAKIOS" in line for line in (dmesg + b"\n" + console).decode("utf-8", "replace").splitlines()),
                 "distinct_record_count": len(rows),
                 "derived_extracted_records_agree": rows == normalized_records((cycle_dir / "hakios_extracted_records.txt").read_bytes()),
                 **analyze_records(rows, result["nonce"], sha(candidate[:4096]), sha(candidate[:65536]))}
        cycles.append(cycle)
    require([c["cycle"] for c in cycles] == [1, 2, 3] and
            summary["cycles_requested"] == summary["cycles_completed"] == 3 and len(summary["results"]) == 3,
            "Expected exactly the three retained cycles")
    require(len({c["nonce"] for c in cycles}) == 3, "Cycle nonces are not distinct")
    hello = (review / "before/prototype/phase4-platform/hello.c").read_text(encoding="utf-8")
    driver = (review / "before/prototype/phase4-platform/hakios.a51.c").read_text(encoding="utf-8")
    labels = [name for name in ("DISPLAY", "DSIM", "TOUCH", "KEYS") if f'put(fd, "HAKIOS_{name}_VERIFIED ' in hello]
    chunked = ("b < A51_UFS_MAX_BLOCKS" in driver and
               "A51_UFS_BOOT_LBA + b, 1, &report" in driver and
               "report = first_report;" in driver and "report.blocks = A51_UFS_MAX_BLOCKS;" in driver and
               "report.bytes = A51_UFS_DMA_BYTES;" in driver)
    gate = (review / "before" / GATE).read_text(encoding="utf-8")
    hardcoded = 'put(fd, "HAKIOS_PHASE4_PASS display=1 touch=1 keys=1 storage="' in hello
    substring_gate = '("HAKIOS_DISPLAY_VERIFIED" in full_log_str)' in gate
    brightness_missing = "brightness_verified" not in gate
    wrappers = json.loads((review / "wrapper-provenance.json").read_bytes())["matching_gate_metadata"]
    return {"audit_completed": True, "device_operations": False,
            "execution_packet": execution, "original_all_cycles_passed_reported": summary["all_cycles_passed"],
            "cycles_reviewed": len(cycles), "qualifying_phase_4_cycles": 0, "phase_4_gate_passed": False,
            "constant_peripheral_verified_labels": labels, "storage_source_uses_16_separate_read10_commands": chunked,
            "hardcoded_phase4_peripheral_pass": hardcoded,
            "legacy_gate_uses_substring_labels": substring_gate, "legacy_gate_omits_brightness": brightness_missing,
            "aggregate_report_rewrites_single_command_block_and_byte_counts": chunked,
            "physical_display_brightness_touch_key_evidence": "not_established_by_constant_labels_or_mmio_snapshot",
            "baseline_restoration_scope": "three_cycle_booleans_reported; original_command_responses_not_retained_in_packet; independent_01h29_baseline_evidence_preserved",
            "recovery_log_scope": "Android_early_probe_and_console_text_retained; committed_binary_export_not_verified",
            "candidate_to_kernel_segments_and_source_correspondence_verified": False,
            "matching_gate_wrapper_metadata_found": [row["path"] for row in wrappers], "cycles": cycles}


def capture(execution):
    review = new_packet("completion-audit", __file__)
    before = {rel: capture_file(review, rel) for rel in (*DOCUMENTS, *SOURCES)}
    review_sources = {rel: capture_file(review, rel) for rel in REVIEW_SOURCES}
    matching_wrappers = capture_wrapper_provenance(review)
    inputs = {p.relative_to(PROJECT).as_posix(): pin(p) for p in sorted((PROJECT / execution).rglob("*")) if p.is_file()}
    restoration = json.loads((PROJECT / RESTORATION / "result.json").read_bytes())
    require(pin(PROJECT / RESTORATION / "result.json") == {
        "bytes": 22518, "sha256": "8dcd27639dd825f5fcd207e9ff41a24932894ab462bbe0d75a5f4e4b8d20d8f6"},
        "Selected completed restoration review changed")
    for row in json.loads((PROJECT / RESTORATION / "index.json").read_bytes()):
        require(pin(PROJECT / RESTORATION / row["path"]) == {k: row[k] for k in ("bytes", "sha256")},
                "Earlier restoration review index mismatch: " + row["path"])
    for rel, expected in restoration["inputs"].items():
        require(pin(PROJECT / rel) == expected, "Earlier restoration input changed: " + rel)
        inputs[rel] = expected
    for path in sorted((PROJECT / RESTORATION).rglob("*")):
        if path.is_file():
            inputs[path.relative_to(PROJECT).as_posix()] = pin(path)
    for row in matching_wrappers:
        rel = row["path"]
        inputs[rel] = pin(PROJECT / rel)
    result = review_result(review, execution)
    build = json.loads((review / "before/manifests/phase4-platform-build.json").read_bytes())
    wsl_root = Path("//wsl.localhost/A51-KernelBuilder" + build["root"])
    result["current_build_correspondence"] = {}
    for rel in ("hakios-kernel", "userland/hello"):
        path = wsl_root / rel
        if path.is_file():
            actual = pin(path)
            result["current_build_correspondence"][rel] = {"path": str(path), **actual,
                "matches_build_manifest": actual == build["artifacts"][rel]}
        else:
            result["current_build_correspondence"][rel] = {"path": str(path), "available": False}
    for rel in ("drivers/core/hakios.a51.c", "xnu-src/xnu-8796.121.2/bsd/dev/hakios.a51.c", "userland/src/hello.c"):
        path = wsl_root / rel
        if path.is_file():
            dest = review / "wsl-source" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
            result.setdefault("wsl_source_pins", {})[rel] = pin(dest)
    result["before_pins"] = before
    result["added_host_script_pins"] = review_sources
    result["immutable_input_pins"] = inputs
    result["packet"] = review.relative_to(PROJECT).as_posix()
    result["captured_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    for rel, expected in inputs.items():
        require(pin(PROJECT / rel) == expected, "Original evidence changed during capture: " + rel)
    write_json(review / "initial-result.json", result)
    write_json(review / "result.json", result)
    index_packet(review)
    verify(review)
    print(json.dumps({k: result[k] for k in ("packet", "audit_completed", "cycles_reviewed", "phase_4_gate_passed", "constant_peripheral_verified_labels")}, indent=2))
    return review


def verify(review, check_current=True):
    result = json.loads((review / "result.json").read_bytes())
    index = json.loads((review / "index.json").read_bytes())
    require({row["path"] for row in index} == {p.relative_to(review).as_posix() for p in review.rglob("*")
                if p.is_file() and p != review / "index.json"}, "Review index file set differs")
    for row in index:
        require(pin(review / row["path"]) == {k: row[k] for k in ("bytes", "sha256")}, "Review index mismatch: " + row["path"])
    for rel, expected in result["immutable_input_pins"].items():
        require(pin(PROJECT / rel) == expected, "Original evidence changed: " + rel)
    for rel, expected in result["before_pins"].items():
        require(pin(review / "before" / rel) == expected, "Before snapshot changed: " + rel)
    for rel, expected in result["added_host_script_pins"].items():
        require(pin(review / "before" / rel) == expected, "Audit source snapshot changed: " + rel)
        if check_current:
            require(pin(PROJECT / rel) == expected, "Audit implementation drift: " + rel)
    replay = review_result(review, result["execution_packet"])
    for key, value in replay.items():
        require(result[key] == value, "Audit replay differs: " + key)
    if check_current and (review / "changes.json").exists():
        for row in json.loads((review / "changes.json").read_bytes()):
            require(pin(PROJECT / row["path"]) == row["after"], "Reviewed change drift: " + row["path"])
    if (review / "gate-guard-change.json").exists():
        gate_change = json.loads((review / "gate-guard-change.json").read_bytes())
        require(pin(review / "after" / GATE) == gate_change["after"] and
                gate_guard_valid((review / "after" / GATE).read_bytes()), "Retained legacy gate guard differs")
        if check_current:
            require(pin(PROJECT / GATE) == gate_change["after"], "Current legacy gate guard differs")
    print(json.dumps({"review": result["packet"], "verified": True,
                      "original_input_pins_checked": len(result["immutable_input_pins"]), "phase_4_gate_passed": False}, indent=2))
    return result


def disable_legacy_gate(review):
    result = verify(review)
    require(not result.get("status_reconciled"), "Review is already reconciled")
    original = (review / "before" / GATE).read_bytes()
    require((PROJECT / GATE).read_bytes() == original, "Concurrent legacy gate change")
    source = original.decode("utf-8")
    require(source.count("def run_phase4_cycle(") == source.count("def main():") == 1,
            "Unexpected historical gate entry points")
    source = source.replace('"""Execute Phase 4 Silicon Driver Validation on Samsung Galaxy A51 (SM-A515F).',
        '"""Historical Phase 4 gate; both execution entry points are disabled.\n\n'
        'The retained body overstates peripheral verification and is kept for audit.\n'
        'Its original description follows:', 1)
    source = source.replace('EXPECTED_SERIAL = "A51_SERIAL_HERE"',
        "# Historical execution below is unreachable until truthful acceptance is implemented.\n"
        "LEGACY_GATE_DISABLED = " + repr(GATE_DISABLED) + '\n\nEXPECTED_SERIAL = "A51_SERIAL_HERE"', 1)
    source = source.replace("def run_phase4_cycle(cycle_num: int, total_cycles: int, output_base: Path) -> dict:\n",
        "def run_phase4_cycle(cycle_num: int, total_cycles: int, output_base: Path) -> dict:\n"
        "    raise RuntimeError(LEGACY_GATE_DISABLED)\n\n", 1)
    source = source.replace("def main():\n", "def main():\n"
        "    print(LEGACY_GATE_DISABLED, file=sys.stderr)\n    return 2\n\n", 1)
    after = source.encode("utf-8")
    require(gate_guard_valid(after), "Prepared legacy gate guard invalid")
    dest = review / "after" / GATE
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(after)
    change = {"path": GATE, "before": result["before_pins"][GATE], "after": pin(dest)}
    write_json(review / "gate-guard-change.json", change)
    (review / "gate-guard.patch").write_text("".join(difflib.unified_diff(
        original.decode("utf-8").splitlines(True), source.splitlines(True),
        fromfile="a/"+GATE, tofile="b/"+GATE)), encoding="utf-8")
    index_packet(review)
    require((PROJECT / GATE).read_bytes() == original, "Concurrent legacy gate change before guard")
    (PROJECT / GATE).write_bytes(after)
    verify(review)
    print(json.dumps({"legacy_gate_disabled_before_device_actions": True, "device_operations": False}))


def intro(result):
    return ("## Current Phase 4 completion audit — 2026-11-16\n\n"
        "Phase 4 is **IN PROGRESS**; its device gate is **UNPASSED**. The newer three-cycle packet "
        "reports success, but its display, DSIM/brightness, touch and key labels are constant strings emitted "
        "after a register snapshot. No visible-output, repeatable-brightness or physical-input gate is established.\n\n"
        "The retained candidate bytes independently match the recorded 4 KiB reads and aggregated 64 KiB hashes. "
        "The current driver uses **sixteen separate 4 KiB READ(10)s** and rewrites a single-command report as "
        "a 16-block result. This is evidence of chunked image loading; the repaired **single 64 KiB READ(10) remains "
        "unverified on hardware**. Nonce and three timer samples per run replay successfully.\n\n"
        "The newer runs report recovery reconnection and baseline rollback, but their original rollback command "
        "responses are absent from the packet. The independently verified earlier baseline restoration and failed "
        "genuine-read retry remain preserved. Recovered Android probe/console text does not establish the committed "
        "recovery export envelope. The legacy device gate is disabled before device actions because its tests "
        "overstate completion. See [completion review](docs/PHASE-4-COMPLETION-REVIEW.md) and the retained audit "
        f"`{result['packet']}/result.json`.\n\n"
        "Phases 1–3 retain their selected completion gates. Phases 5–10 remain planned. Next: remove the constant "
        "PASS producer, restore truthful per-command storage telemetry, and implement physical peripheral acceptance "
        "before any further hardware gate. Historical milestone sections below retain their original dates; "
        "use the current state and review for the completion decision.\n\n")


def reconcile(review):
    result = verify(review, check_current=False)
    require(not result.get("status_reconciled"), "Review is already reconciled")
    # Validate every prerequisite before preparing or writing any current document.
    require((review / "gate-guard-change.json").is_file() and gate_guard_valid((PROJECT / GATE).read_bytes()),
            "Legacy gate must be disabled before status reconciliation")
    require(pin(PROJECT / GATE) == pin(review / "after" / GATE), "Legacy gate guard drift")
    require(result["constant_peripheral_verified_labels"] == ["DISPLAY", "DSIM", "TOUCH", "KEYS"] and
            result["hardcoded_phase4_peripheral_pass"] and result["legacy_gate_uses_substring_labels"] and
            result["legacy_gate_omits_brightness"] and result["storage_source_uses_16_separate_read10_commands"],
            "Source findings differ from the proposed correction")
    observation_keys = ("nonce_record_attributable", "single_4k_hash_record_matches_candidate",
        "reread_4k_hash_record_matches_candidate", "aggregate_64k_hash_record_matches_candidate",
        "write_rejection_record_observed", "timer_samples_replayed", "user_exit_record_observed",
        "derived_extracted_records_agree")
    require(all(c[key] for c in result["cycles"] for key in observation_keys),
            "Useful record replay failed; revise the proposed correction before changing status")
    for rel in DOCUMENTS:
        require(pin(PROJECT / rel) == result["before_pins"][rel], "Concurrent document change: " + rel)
    raw_state = (review / "before/state.json").read_bytes()
    state = json.loads(raw_state)
    state.update(active_phase=4, active_task="Audit completed; physical display/brightness/input and genuine 64 KiB READ(10) remain unverified",
                 phase_4_status="in_progress", phase_4="in_progress", phase_4_device_gate_passed=False,
                 updated_date_local="2026-11-16", next_action="repair_truthful_diagnostics_then_physical_phase4_acceptance")
    criteria = state["phase_4_criteria"]
    criteria.update(display_scanout_and_dimensions="unverified_constant_labels_after_mmio_snapshot",
        dsim_repeatable_brightness="unverified_no_repeatable_visible_evidence",
        physical_touch_events_and_coordinates="unverified_constant_controller_and_bounds_labels_no_physical_events",
        physical_power_volume_key_events="unverified_constant_keycode_labels_no_press_release_transitions",
        ufs_read_known_image="retained_4k_candidate_prefix_hash_records_independently_matched_three_cycles",
        larger_image_loading="retained_64k_aggregate_hash_records_match_three_candidates_chunked_16x4k_read10",
        single_64k_read10="unverified_newer_source_substitutes_16_separate_read10_commands",
        working_xnu_timers="retained_three_timer_samples_per_nonce_replayed_three_cycles",
        per_run_nonce_attributable="retained_exact_nonce_records_replayed_three_cycles",
        storage_writes_disabled="retained_minus30_rejection_doorbell_zero_records_three_cycles; earlier_shared_boundary_model_verified",
        baseline_rollback_verified="newer_three_cycles_reported_no_original_command_stdout; earlier_independent_restoration_verified",
        recovery_export_persistence="retained_android_probe_console_text; committed_binary_envelope_unverified",
        status="in_progress_device_gate_unpassed")
    original_gate = state.get("phase_4_silicon_gate", {})
    state["phase_4_silicon_gate"] = {"result": result["execution_packet"] + "/phase4_execution_summary.json",
        "reported_result_preserved": original_gate, "audit": result["packet"] + "/result.json",
        "cycles_reviewed": result["cycles_reviewed"], "qualifying_cycles": 0, "all_cycles_passed": False,
        "display_verified": False, "brightness_verified": False, "touch_verified": False, "keys_verified": False,
        "single_64k_read10_verified": False, "baseline_rollback_verified": False,
        "baseline_rollback_scope": "newer_reported_only; earlier_independent_baseline_verified",
        "write_rejection_records_observed": all(c["write_rejection_record_observed"] for c in result["cycles"]),
        "timer_samples_replayed": all(c["timer_samples_replayed"] for c in result["cycles"]),
        "exact_nonce_records_replayed": all(c["nonce_record_attributable"] for c in result["cycles"]),
        "aggregate_64k_hash_records_match": all(c["aggregate_64k_hash_record_matches_candidate"] for c in result["cycles"])}
    state["phase_4_completion_audit"] = {"result": result["packet"] + "/result.json",
        "audit_completed": True, "phase_4_gate_passed": False, "device_operations": False}
    state["phase_4_device_status"]["observation_scope"] = "historical_independent_01h29_verification; newer_rollback_reported; no_live_query_in_completion_audit"
    state["phase_4_device_status"]["newer_reported_cycles"] = result["execution_packet"]
    replacements = {"state.json": json.dumps(state, indent=2) + "\n"}
    for rel in ("README.md", "docs/INDEX.md", "docs/HANDOFF.md"):
        old = (review / "before" / rel).read_text(encoding="utf-8")
        start = old.index("## Current Phase 4 storage repair")
        end = old.find("\n## ", start + 1)
        if rel == "README.md":
            end = old.index("Start with ", start)
        elif rel == "docs/INDEX.md":
            end = old.index("1. `README.md`", start)
        require(end > start, "Current section boundary missing: " + rel)
        section = intro(result)
        if rel != "README.md":
            section = section.replace("(docs/PHASE-4-COMPLETION-REVIEW.md)", "(PHASE-4-COMPLETION-REVIEW.md)")
        replacements[rel] = old[:start] + section + old[end:].lstrip("\n")
    rows = "\n".join(f"| {c['cycle']} | `{c['nonce']}` | matching | matching, chunked | replayed | unpassed |" for c in result["cycles"])
    replacements["docs/PHASE-4-COMPLETION-REVIEW.md"] = (
        "# Phase 4 completion review — audited 16 November 2026\n\n"
        "**IN PROGRESS — device gate UNPASSED.** The earlier COMPLETE decision exceeds its evidence and is superseded. "
        "The original completion documents, source and state bytes are retained in this audit's `before/` directory; "
        "all execution packets remain unchanged.\n\n"
        "The roadmap requires visible display at correct dimensions, physical touch coordinates, repeatable brightness "
        "and key behavior, known-image reads, larger-image loading and a read-only driver. Three automatic PASS reports "
        "do not supply the missing physical tests.\n\n"
        f"Original packet: `{result['execution_packet']}/`. Offline audit: `{result['packet']}/result.json`.\n\n"
        "| Cycle | Nonce | 4 KiB hash | 64 KiB aggregate hash | Three timer samples | Phase 4 |\n"
        "|---|---|---|---|---|---|\n" + rows + "\n\n"
        "Each candidate's full SHA-256 and length were checked against its per-cycle result and summary. Its first "
        "4 KiB and 64 KiB were hashed independently and compared with complete normalized transfer records. Recovered "
        "copies are deduplicated; 852 extracted lines per cycle are not 852 independent hardware observations. Exact "
        "nonce records and timer indices, durations and increasing IRQ counters were replayed.\n\n"
        "`prototype/phase4-platform/hello.c` prints constant DISPLAY/DSIM/TOUCH/KEYS_VERIFIED labels inside the "
        "snapshot-success branch, despite its own comment saying that snapshots do not prove visible output or input "
        "events. `HAKIOS_PHASE4_PASS` hard-codes display/touch/keys to 1. The legacy parser accepts these through "
        "substring matching and omits brightness. None qualifies a physical peripheral gate.\n\n"
        "`hakios.a51.c` submits READ(10) with one block sixteen times, copies each result to staging and then rewrites "
        "the first report's block count, byte count and elapsed time as an aggregate. It does not submit one 64 KiB "
        "READ(10). The matching aggregate hash is useful chunked-loading evidence, but the genuine transfer's earlier "
        "system bus fatal error and repaired candidate's failed attributable-log capture are unresolved. Chunking "
        "does not establish the DMA root cause or verify that repair. The original roadmap does not prescribe a single "
        "64 KiB command; that command is the outstanding repair test, while physical brightness/input alone already "
        "prevent roadmap completion.\n\n"
        "Each cycle reports recovery reconnection and matching baseline readback. The packet lacks original staging, "
        "write/readback, remote-exit, Android-completion and final partition-hash command outputs, so this review "
        "preserves those reports without upgrading them to an independent rollback replay. The older [independent "
        "restoration](BASELINE-RESTORATION-20261116.md) remains verified. Recovery console and Android early_probe "
        "logs were recovered; the committed binary pmsg envelope has not been verified by these text captures.\n\n"
        "The current kernel and hello hashes were compared with the selected build manifest where available; the "
        "audit result retains the comparison. No matching `run.py` metadata was found among the metadata present "
        "at audit capture. That discovery is retained separately, so a later disabled-gate guard test cannot change "
        "historical replay. Candidate-to-kernel-segment and historical source/build correspondence were not "
        "established by this review. Source findings describe the captured template and available WSL source, "
        "while hardware observations are limited to the retained nonce-bound logs.\n\n"
        "The legacy `phase4-device-gate.py` entry points are disabled before device actions. Its original code remains "
        "in the audit snapshot. No driver, kernel binary, phone partition or runtime was changed during this review. "
        "Next: replace constant PASS production and misleading aggregate protocol telemetry, establish physical "
        "display/brightness/input acceptance, and test the genuine read with matched source/build and reliable logs.\n\n"
        "Reproduce the offline audit through `scripts/run.py`:\n\n```powershell\n"
        f"python scripts/run.py --label p4-completion-audit-replay -- python -B scripts/phase4-audit-completion.py --verify-review {result['packet']}\n"
        "```\n\nRollback: verify `index.json` and `changes.json`, then restore only this review's indexed before "
        "documents and original gate/recorder source. Retain every original/new audit packet. Documentation/source rollback "
        "does not restore the phone. Phases 5–10 remain planned.\n")
    replacements["docs/STATE.md"] = (
        "# HakiOS A51 — current state\n\nUpdated 16 November 2026 (Asia/Calcutta).\n\n"
        "**Phase 4 is IN PROGRESS; its device gate is UNPASSED.** The newer three-cycle automatic PASS report "
        "overstates physical peripheral verification. The earlier ALL PHASES COMPLETE claim is superseded.\n\n"
        "| Phase | Current status |\n|---|---|\n| 1 | Complete for its retained host/QEMU gate |\n"
        "| 2 | Complete for its selected minimal-payload/log/return gate |\n"
        "| 3 | Complete for its selected three-run user-program/timer/return gate |\n"
        "| 4 | In progress; physical peripheral gate unpassed |\n| 5–10 | Planned |\n\n"
        "The newer retained candidates match the recorded 4 KiB reads and aggregate 64 KiB image hashes in all "
        "three cycles. Source implements sixteen separate one-block READ(10)s. The genuine single 64 KiB DMA read "
        "repair remains unverified. Nonce records and three timer samples per cycle replay successfully.\n\n"
        "Visible display, repeatable brightness, real touch coordinates and power/volume transitions remain "
        "unverified: their VERIFIED strings are constants after a register snapshot. The legacy gate omits "
        "brightness and accepts those strings. Its execution entry points are now disabled before device actions.\n\n"
        "The earlier independently verified baseline restoration remains verified. Newer recovery/rollback results are reported "
        "without original command responses for independent replay. This audit made no live phone query, write or "
        "reboot; current screen/connection cannot be inferred from historical captures. Android probe/console log "
        "recovery is observed, while the committed binary export envelope remains unverified.\n\n"
        f"Audit: `{result['packet']}/result.json`. Original newer packet: `{result['execution_packet']}/`. "
        "See [completion review](PHASE-4-COMPLETION-REVIEW.md), [restoration](BASELINE-RESTORATION-20261116.md) "
        "and [UFS repair](PHASE-4-UFS-REPAIR.md). Original completion documents/state and source are preserved "
        "in the audit's before snapshots. Machine-readable state retains the reported result alongside the correction.\n\n"
        "Next: remove false PASS production, retain truthful per-command storage evidence, implement physical "
        "peripheral acceptance, then validate matched source/build and log capture before another hardware test. "
        "The audit changes host documentation and gate availability only; Android projects, backups, recovery, "
        "DTBO, userdata and partition layout are preserved.\n")
    ufs = (review / "before/docs/PHASE-4-UFS-REPAIR.md").read_text(encoding="utf-8")
    ufs = ufs.replace("242-second trial deadline", "240-second configured deadline, with a 242-second recorded wait")
    insertion = ("\n## Newer chunked-read evidence — 16 November completion audit\n\n"
        "Three later candidates have matching recorded 64 KiB aggregate hashes through sixteen separate 4 KiB "
        "READ(10)s. Their aggregate report rewrites the first command's block/byte counts; it does not verify the "
        "single 64 KiB READ(10) repair. The current template therefore differs from the genuine-read implementation "
        "described historically below. No driver source was changed in this audit. Text logs were recovered via "
        "Android early_probe/console; the committed binary export remains unverified. Phase 4 stays unpassed "
        "because physical display, brightness and input tests are missing. See [current review](PHASE-4-COMPLETION-REVIEW.md).\n")
    first_heading = ufs.find("\n## ")
    require(first_heading >= 0, "UFS guide heading missing")
    replacements["docs/PHASE-4-UFS-REPAIR.md"] = ufs[:first_heading] + insertion + ufs[first_heading:]
    device = (review / "before/docs/PHASE-4-DEVICE-PATH.md").read_text(encoding="utf-8")
    first_heading = device.find("\n## ")
    require(first_heading >= 0, "Device guide heading missing")
    replacements["docs/PHASE-4-DEVICE-PATH.md"] = (device[:first_heading] +
        "\n## Completion-audit correction — 16 November\n\n"
        "The newer automatic PASS is superseded by [the completion audit](PHASE-4-COMPLETION-REVIEW.md). "
        "The legacy device-gate entry points are disabled before hardware actions; their constant display/input "
        "labels and chunked storage aggregate do not complete Phase 4. Preserve the existing independent baseline "
        "restoration evidence and use its pinned recovery instructions for any actual unverified return. This "
        "offline audit does not query the current phone or authorize a new device experiment.\n" + device[first_heading:])
    source_rel = "scripts/phase4-record-baseline-restoration.py"
    source = (review / "before" / source_rel).read_text(encoding="utf-8")
    require(pin(PROJECT / source_rel) == result["before_pins"][source_rel], "Concurrent recorder source change")
    replacements[source_rel] = source.replace("242-second trial deadline", "240-second configured deadline, with a 242-second recorded wait")
    replacements["docs/IMPLEMENTATION-LOG.md"] = (review / "before/docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + (
        "\n\n## P4-041 — Audit newer completion claim and preserve truthful status\n\n"
        "Purpose/files: scripts/phase4-{audit-completion,test-completion-audit,device-gate,record-baseline-restoration}.py; "
        "README.md, docs/{STATE,INDEX,HANDOFF,PHASE-4-COMPLETION-REVIEW,PHASE-4-UFS-REPAIR,PHASE-4-DEVICE-PATH,IMPLEMENTATION-LOG}.md "
        "and state.json. Preserve the newer COMPLETE documents/state before correcting their claim, retain all execution "
        "evidence, and disable the legacy hardware gate before any device action. Correct the historical timeout wording "
        "to 240 seconds configured / 242 seconds recorded without rerunning or rewriting the completed restoration packet.\n\n"
        f"Verification: offline packet `{result['packet']}` pins every original newer candidate/log/result and earlier "
        "restoration review. Three candidate lengths/full hashes agree with per-cycle results and summary; independent "
        "4 KiB/64 KiB prefix hashes agree with complete transfer records; exact nonces and three timer samples/IRQ "
        "sequences per cycle replay. Thirteen offline regression test methods (including parser rejection subcases, "
        "pre-mutation reconciliation guards, both disabled execution entry points and stable historical replay) "
        "are run through scripts/run.py; their packets are under evidence/phase-4/completion-audit-tests/. "
        "The initial run skipped the two post-capture/guard methods; the final run requires both. Source proves "
        "constant display/DSIM/touch/key VERIFIED strings, hard-coded "
        "Phase 4 PASS, substring-only parser with no brightness criterion, and sixteen one-block reads followed by "
        "rewritten aggregate counts. Native/kernel binaries and source were read only. Regression/guard/replay runs "
        "are retained through scripts/run.py; this entry records audit logic and corrected state, not hardware success.\n\n"
        "Limitations: chunked image hashes do not exercise the genuine 64 KiB READ(10); no physical display, repeatable "
        "brightness, touch coordinates or key transitions are established. Newer rollback is reported without original "
        "command outputs; Android probe/console text does not verify the committed pmsg binary envelope. No newer gate "
        "run.py wrapper metadata was found at capture; its retained discovery is separate from immutable record replay. "
        "Candidate-to-kernel-segment and historical source/build correspondence remain unverified. The existing "
        "independent baseline restoration and failed genuine-read "
        "retry remain verified in their original scopes. No phone query/write/reboot, upstream mutation or driver "
        "implementation change occurred. Next: fix the producer/protocol reporting and establish physical acceptance "
        "before further hardware trials. Phases 5–10 remain planned.\n\n"
        "Rollback: verify the audit index and changes.json, restore only indexed before documents and gate/recorder "
        "source, and retain both original and audit evidence. Newly added offline audit/test scripts may be removed. "
        "This does not restore a phone partition. Preserve Android projects/images, Phase 3, recovery, DTBO and userdata.\n")
    changes, patches = [], []
    for rel in replacements:
        require((PROJECT / rel).read_bytes() == (review / "before" / rel).read_bytes(),
                "Concurrent change before reconciliation: " + rel)
    for rel, text in replacements.items():
        path = PROJECT / rel
        old = (review / "before" / rel).read_bytes()
        require(path.read_bytes() == old, "Concurrent change before write: " + rel)
        after = text.encode("utf-8")
        dest = review / "after" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(after)
        path.write_bytes(after)
        changes.append({"path": rel, "before": pin(review / "before" / rel), "after": pin(dest)})
        patches.append("".join(difflib.unified_diff(old.decode("utf-8").splitlines(True), text.splitlines(True), fromfile="a/"+rel, tofile="b/"+rel)))
    gate_rel = "scripts/phase4-device-gate.py"
    gate = (PROJECT / gate_rel).read_bytes()
    require(gate_guard_valid(gate), "Legacy gate guard changed during reconciliation")
    dest = review / "after" / gate_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(gate)
    changes.append({"path": gate_rel, "before": result["before_pins"][gate_rel], "after": pin(dest)})
    patches.append("".join(difflib.unified_diff((review / "before" / gate_rel).read_text(encoding="utf-8").splitlines(True), gate.decode("utf-8").splitlines(True), fromfile="a/"+gate_rel, tofile="b/"+gate_rel)))
    write_json(review / "changes.json", changes)
    (review / "changes.patch").write_text("".join(patches), encoding="utf-8")
    result["status_reconciled"] = True
    result["legacy_gate_disabled_before_device_actions"] = True
    write_json(review / "result.json", result)
    index_packet(review)
    verify(review)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify-review", type=Path)
    group.add_argument("--reconcile-review", type=Path)
    group.add_argument("--disable-legacy-gate", type=Path)
    parser.add_argument("--execution-packet", default=EXECUTION)
    args = parser.parse_args()
    if args.verify_review:
        verify(args.verify_review.resolve())
    elif args.reconcile_review:
        reconcile(args.reconcile_review.resolve())
    elif args.disable_legacy_gate:
        disable_legacy_gate(args.disable_legacy_gate.resolve())
    else:
        execution = (PROJECT / args.execution_packet).resolve()
        require(execution.is_relative_to(PROJECT / "evidence/phase-4/silicon-execution"), "Execution packet outside evidence tree")
        capture(execution.relative_to(PROJECT).as_posix())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("Offline completion audit failed: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
