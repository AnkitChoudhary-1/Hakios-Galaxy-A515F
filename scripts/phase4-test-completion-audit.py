#!/usr/bin/env python3
"""Offline regression checks against retained logs; never execute a device path."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from phase4_support import PROJECT, index_packet, new_packet, write_json


def import_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = import_script("completion_audit", PROJECT / "scripts/phase4-audit-completion.py")
OPTIONS = None


class CompletionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cycle = sorted((PROJECT / audit.EXECUTION).glob("cycle-1_*"))[0]
        raw = (cycle / "dmesg.txt").read_bytes() + b"\n" + (cycle / "console-ramoops.log").read_bytes()
        cls.raw = raw
        cls.rows = audit.normalized_records(raw)
        cls.nonce = json.loads((cycle / "cycle_result.json").read_bytes())["nonce"]
        cls.single = audit.unique_fields(cls.rows, "HAKIOS_UFS_TRANSFER", name="single")["sha256"]
        cls.large = audit.unique_fields(cls.rows, "HAKIOS_UFS_TRANSFER", name="multi")["sha256"]

    def analyze(self, rows=None):
        return audit.analyze_records(self.rows if rows is None else rows, self.nonce, self.single, self.large)

    def changed(self, prefix, old, new):
        matching = [row for row in self.rows if row.startswith(prefix)]
        self.assertEqual(len(matching), 1)
        self.assertIn(old, matching[0])
        return [row.replace(old, new, 1) if row == matching[0] else row for row in self.rows]

    def test_retained_records_preserve_useful_observations_without_qualifying_phase4(self):
        result = self.analyze()
        for key in ("nonce_record_attributable", "single_4k_hash_record_matches_candidate",
                    "reread_4k_hash_record_matches_candidate", "aggregate_64k_hash_record_matches_candidate",
                    "write_rejection_record_observed", "timer_samples_replayed", "user_exit_record_observed"):
            self.assertTrue(result[key], key)
        for key in ("display_verified", "brightness_verified", "touch_verified", "keys_verified",
                    "single_64k_read10_verified", "committed_recovery_envelope_verified", "qualifying_phase_4_cycle"):
            self.assertFalse(result[key], key)

    def test_recovered_copies_are_deduplicated(self):
        self.assertEqual(audit.normalized_records(self.raw + b"\n" + self.raw), self.rows)
        self.assertEqual(self.analyze(self.rows * 4), self.analyze())

    def test_labels_alone_never_qualify_peripherals_or_storage(self):
        rows = [row for row in self.rows if any(row.startswith("HAKIOS_" + label) for label in
                ("DISPLAY_VERIFIED", "DSIM_VERIFIED", "TOUCH_VERIFIED", "KEYS_VERIFIED", "PHASE4_PASS"))]
        rows.append("HAKIOS_RUN_NONCE=" + self.nonce)
        result = self.analyze(rows)
        self.assertFalse(result["qualifying_phase_4_cycle"])
        self.assertFalse(result["aggregate_64k_hash_record_matches_candidate"])
        self.assertFalse(result["timer_samples_replayed"])
        for key in ("display_verified", "brightness_verified", "touch_verified", "keys_verified"):
            self.assertFalse(result[key])

    def test_removing_constant_labels_keeps_storage_and_timer_evidence(self):
        rows = [row for row in self.rows if not any(row.startswith("HAKIOS_" + label) for label in
                ("DISPLAY_VERIFIED", "DSIM_VERIFIED", "TOUCH_VERIFIED", "KEYS_VERIFIED", "PHASE4_PASS"))]
        self.assertEqual(self.analyze(rows), self.analyze())

    def test_missing_stale_conflicting_or_malformed_nonce_rejects_attribution(self):
        base = [row for row in self.rows if not row.startswith("HAKIOS_RUN_NONCE")]
        cases = [base, base + ["HAKIOS_RUN_NONCE=" + "0" * 32],
                 self.rows + ["HAKIOS_RUN_NONCE=" + "0" * 32],
                 self.rows + ["HAKIOS_RUN_NONCE=malformed"]]
        for rows in cases:
            with self.subTest(nonce_rows=[r for r in rows if r.startswith("HAKIOS_RUN_NONCE")]):
                result = self.analyze(rows)
                for key in ("nonce_record_attributable", "single_4k_hash_record_matches_candidate",
                            "aggregate_64k_hash_record_matches_candidate", "timer_samples_replayed"):
                    self.assertFalse(result[key], key)

    def test_incomplete_wrong_or_conflicting_transfer_records_reject_hash_match(self):
        cases = [("rc=0", "rc=-5"), ("ocs=0", "ocs=15"), ("blocks=16", "blocks=1"),
                 ("residual=0", "residual=1"), ("prdt_count=1", "prdt_count=16"),
                 ("prdt_bytes=128", "prdt_bytes=16"), ("elapsed_us=1637", "elapsed_us=NaN"),
                 ("sha256=" + self.large, "sha256=" + "0" * 64),
                 ("sha256=" + self.large, "sha256=" + self.large[:-1]),
                 ("lba=27792", "lba=27792 lba=0")]
        for old, new in cases:
            with self.subTest(field=old):
                rows = self.changed("HAKIOS_UFS_TRANSFER name=multi ", old, new)
                self.assertFalse(self.analyze(rows)["aggregate_64k_hash_record_matches_candidate"])
        conflicting = [r for r in self.rows if r.startswith("HAKIOS_UFS_TRANSFER name=multi ")][0]
        self.assertFalse(self.analyze(self.rows + [conflicting.replace("rc=0", "rc=-5")])[
            "aggregate_64k_hash_record_matches_candidate"])

    def test_conflicting_image_load_or_exit_record_is_rejected(self):
        for extra, key in (("HAKIOS_IMAGE_LOAD_VERIFIED bytes=65536 sha256=" + "0" * 64,
                            "aggregate_64k_hash_record_matches_candidate"),
                           ("HAKIOS_USER_EXIT outcome=1 timer_verified=1", "user_exit_record_observed")):
            with self.subTest(record=extra):
                self.assertFalse(self.analyze(self.rows + [extra])[key])

    def test_malformed_guard_counters_do_not_crash_or_pass(self):
        for bad in ("NaN", "-1", "0", "1.0", "1x", "9" * 100):
            with self.subTest(rejected=bad):
                self.assertFalse(self.analyze(self.changed("HAKIOS_STORAGE_WRITE_GUARD ",
                                 "rejected=1", "rejected=" + bad))["write_rejection_record_observed"])
        self.assertFalse(self.analyze(self.changed("HAKIOS_STORAGE_WRITE_GUARD ",
                         "doorbell=0x0", "doorbell=0x1"))["write_rejection_record_observed"])

    def test_timer_failures_and_malformed_values_reject_cleanly(self):
        cases = [("elapsed_us=1005040", "elapsed_us=0"),
                 ("elapsed_us=1005040", "elapsed_us=1500001"),
                 ("elapsed_us=1005040", "elapsed_us=NaN"),
                 ("irq_after=77", "irq_after=14"), ("irq_before=14", "irq_before=-1"),
                 ("irq_after=77", "irq_after=" + "9" * 100),
                 ("select_rc=0", "select_rc=-1"), ("read_rc=0", "read_rc=-1"),
                 ("index=1", "index=2")]
        for old, new in cases:
            with self.subTest(field=old):
                self.assertFalse(self.analyze(self.changed("HAKIOS_TIMER_SAMPLE index=1 ", old, new))[
                    "timer_samples_replayed"])
        self.assertFalse(self.analyze(self.changed("HAKIOS_TIMER_SAMPLE index=2 ",
                         "irq_before=77", "irq_before=76"))["timer_samples_replayed"])

    def test_extra_missing_and_conflicting_timer_samples_reject(self):
        first = [row for row in self.rows if row.startswith("HAKIOS_TIMER_SAMPLE index=1 ")][0]
        cases = [self.rows + [first.replace("index=1", "index=4")],
                 [row for row in self.rows if row != first],
                 self.rows + [first.replace("irq_after=77", "irq_after=76")]]
        for rows in cases:
            with self.subTest(sample_count=sum(r.startswith("HAKIOS_TIMER_SAMPLE ") for r in rows)):
                self.assertFalse(self.analyze(rows)["timer_samples_replayed"])

    def test_reconciliation_prerequisite_stops_before_document_mutation(self):
        # A minimal review without a gate guard must fail before it opens any document.
        with tempfile.TemporaryDirectory(prefix="prerequisite-", dir=OPTIONS.packet) as folder:
            root = Path(folder)
            with mock.patch.object(audit, "PROJECT", root), mock.patch.object(audit, "verify", return_value={}):
                with self.assertRaisesRegex(ValueError, "Legacy gate must be disabled"):
                    audit.reconcile(root)
            self.assertEqual(list(root.rglob("*")), [])

    def test_guarded_execution_entry_points_have_no_device_or_filesystem_actions(self):
        if not OPTIONS.require_guard:
            self.skipTest("Runs after the original gate source is preserved and guarded")
        gate = import_script("guarded_phase4_gate", PROJECT / audit.GATE)
        self.assertTrue(audit.gate_guard_valid((PROJECT / audit.GATE).read_bytes()))
        with mock.patch.object(gate.subprocess, "run", side_effect=AssertionError("Subprocess reached")), \
             mock.patch.object(gate, "wait_for_device", side_effect=AssertionError("Device reached")), \
             mock.patch.object(Path, "mkdir", side_effect=AssertionError("Filesystem mutation reached")), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(gate.main(), 2)
            with self.assertRaisesRegex(RuntimeError, "Legacy Phase 4 gate is disabled"):
                gate.run_phase4_cycle(1, 3, OPTIONS.packet)
        self.assertIn(audit.GATE_DISABLED, stderr.getvalue())

    def test_historical_replay_does_not_scan_new_run_metadata(self):
        if OPTIONS.review is None:
            self.skipTest("Requires the captured audit packet")
        result = json.loads((OPTIONS.review / "result.json").read_bytes())
        original_glob = Path.glob
        def guarded_glob(path, pattern):
            if path == PROJECT / "runs":
                raise AssertionError("Historical replay searched mutable run metadata")
            return original_glob(path, pattern)
        with mock.patch.object(Path, "glob", guarded_glob):
            replay = audit.review_result(OPTIONS.review, result["execution_packet"])
        for key, value in replay.items():
            self.assertEqual(result[key], value, key)


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-guard", action="store_true")
    parser.add_argument("--review", type=Path)
    OPTIONS = parser.parse_args()
    if OPTIONS.review:
        OPTIONS.review = OPTIONS.review.resolve()
    OPTIONS.packet = new_packet("completion-audit-tests", __file__)
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CompletionAuditTests)
    runner = unittest.TextTestRunner(stream=output, verbosity=2)
    result = runner.run(suite)
    (OPTIONS.packet / "test-output.txt").write_text(output.getvalue(), encoding="utf-8")
    write_json(OPTIONS.packet / "result.json", {"passed": result.wasSuccessful(),
        "test_methods": result.testsRun, "skipped": len(result.skipped), "device_operations": False,
        "guard_required": OPTIONS.require_guard, "review": str(OPTIONS.review) if OPTIONS.review else None})
    index_packet(OPTIONS.packet)
    print(output.getvalue())
    print(json.dumps({"packet": OPTIONS.packet.relative_to(PROJECT).as_posix(),
        "passed": result.wasSuccessful(), "test_methods": result.testsRun, "skipped": len(result.skipped),
        "device_operations": False}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
