"""Pure checks separating Phase 4 diagnostics from physical completion.

No device access or state mutation occurs on import or during validation.
Diagnostic and timer PASS markers retain their narrower meanings.
"""
from __future__ import annotations

import re

REPORTING_LINE = "HAKIOS_A51_REPORTING version=1"
PENDING_LINE = ("HAKIOS_PHASE4_PENDING display=unverified brightness=unverified "
                "touch=unverified keys=unverified known_image=host_check_required")
LEGACY_COMPLETION = re.compile(
    r"\bHAKIOS_(?:PHASE4|DISPLAY|DSIM|BRIGHTNESS|TOUCH|KEYS|STORAGE|IMAGE_LOAD)_"
    r"(?:VERIFIED|PASS|COMPLETE|COMPLETED)\b|\bHAKIOS_STORAGE_MATCH\b")


def reporting_checks(frame: str, full_log: str | None = None) -> dict[str, bool]:
    """Require one exact reporting contract and reject unsupported success.

    The caller provides the single attributable user frame. A full log can
    additionally expose misleading labels outside that frame. These checks
    certify reporting grammar only; they cannot pass a physical device gate.
    """
    lines = frame.splitlines()
    versions = [line for line in lines if line.startswith("HAKIOS_A51_REPORTING")]
    pending = [line for line in lines if line.startswith("HAKIOS_PHASE4_PENDING")]
    return {
        "reporting_version_1_exactly_once": versions == [REPORTING_LINE],
        "phase4_physical_gate_explicitly_pending": pending == [PENDING_LINE],
        "no_legacy_hardware_completion_markers": LEGACY_COMPLETION.search(
            frame if full_log is None else full_log) is None,
    }
