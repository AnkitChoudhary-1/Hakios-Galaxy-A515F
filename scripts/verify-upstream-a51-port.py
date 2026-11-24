#!/usr/bin/env python3
"""Verify an upstream A51 audit packet against its ledger and live host inputs.

Run inside A51-KernelBuilder WSL through run.py. This is host-only and never
contacts or changes the phone.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = PROJECT / "scripts/audit-upstream-a51-port.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("upstream_a51_audit", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load audit implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_audit_module()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_packet(value: str) -> Path:
    base = (PROJECT / "evidence/phase-1/upstream-a51-port").resolve()
    candidate = Path(value)
    candidate = (PROJECT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    require(candidate.is_relative_to(base), f"packet must stay under {base}")
    require(candidate.is_dir(), f"missing packet: {candidate}")
    return candidate


def verify_manifest(packet: Path) -> dict:
    manifest = load_json(packet / "manifest.json")
    require(manifest.get("schema_version") == 1, "unsupported manifest schema")
    expected = {}
    for record in manifest.get("files", []):
        relative = record["path"]
        require(relative not in expected and relative != "manifest.json", f"duplicate/invalid manifest path: {relative}")
        path = (packet / relative).resolve()
        require(path.is_relative_to(packet.resolve()), f"manifest path escapes packet: {relative}")
        require(path.is_file(), f"missing packet file: {relative}")
        require(path.stat().st_size == record["size"], f"packet size mismatch: {relative}")
        require(AUDIT.sha256_file(path) == record["sha256"], f"packet hash mismatch: {relative}")
        expected[relative] = record
    actual = {
        path.relative_to(packet).as_posix()
        for path in packet.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    require(actual == set(expected), "packet contains unlisted or missing files")
    return manifest


def compare_payload(packet: Path, identity: dict, payload: bytes) -> None:
    path = packet / identity["path"]
    require(path.read_bytes() == payload, f"live payload differs: {identity['path']}")
    require(len(payload) == identity["size"], f"live payload size differs: {identity['path']}")
    require(AUDIT.sha256_bytes(payload) == identity["sha256"], f"live payload hash differs: {identity['path']}")


def verify_repositories(packet: Path, root: Path) -> dict:
    stored = load_json(packet / "repositories.json")
    issues: list[str] = []
    current_paths = AUDIT.discover_git_worktrees(root)
    current_relatives = [AUDIT.relative_to(root, path) for path in current_paths]
    stored_relatives = [record["path"] for record in stored["repositories"]]
    require(current_relatives == stored_relatives, "Git worktree set changed")
    for repo, saved in zip(current_paths, stored["repositories"]):
        current, payloads = AUDIT.repository_snapshot(root, repo, issues)
        saved_without_evidence = dict(saved)
        evidence = saved_without_evidence.pop("evidence")
        require(current == saved_without_evidence, f"repository state changed: {saved['path']}")
        for name, identity in evidence.items():
            compare_payload(packet, identity, payloads[name])
    require(not issues, "repository expectation checks failed: " + "; ".join(issues))
    return {"repositories": len(current_paths), "dirty": stored["dirty_repository_count"]}


def strip_run_evidence(value: dict) -> dict:
    result = json.loads(json.dumps(value))
    for record in result["runs"]:
        record.pop("evidence", None)
    return result


def verify_components(packet: Path, root: Path) -> dict:
    counts = {}
    issues: list[str] = []

    artifacts = AUDIT.collect_artifacts(root, issues)
    require(artifacts == load_json(packet / "artifacts.json"), "artifact identity or structure changed")
    counts["artifacts"] = 2

    config = AUDIT.parse_config(root / ".config")
    require(config == load_json(packet / "configuration.json"), "kernel configuration changed")
    compare_payload(
        packet,
        {"path": "configuration/a51.config", "size": (root / ".config").stat().st_size,
         "sha256": AUDIT.sha256_file(root / ".config")},
        (root / ".config").read_bytes(),
    )
    counts["config_symbols"] = config["symbol_count"]

    toolchain = AUDIT.collect_toolchain(issues)
    require(toolchain == load_json(packet / "toolchain.json"), "toolchain/package inventory changed")
    counts["tool_commands"] = len(toolchain["commands"])

    sdk = AUDIT.collect_sdk(issues)
    require(sdk == load_json(packet / "sdk.json"), "Theos SDK identity changed")
    counts["sdk_files"] = sdk["tree"]["files"]

    nasm = AUDIT.collect_nasm_adaptation(issues)
    require(nasm == load_json(packet / "nasm-adaptation.json"), "NASM adaptation changed")

    saved_runs = load_json(packet / "run-pins.json")
    current_runs = AUDIT.collect_run_pins(PROJECT, None, issues)
    require(strip_run_evidence(saved_runs) == strip_run_evidence(current_runs), "retained run pins changed")
    for record in current_runs["runs"]:
        saved = next(item for item in saved_runs["runs"] if item["run_id"] == record["run_id"])
        for name, identity in saved["evidence"].items():
            source = PROJECT / record["source"] / name
            compare_payload(packet, identity, source.read_bytes())
    counts["run_pins"] = len(current_runs["runs"])

    claims = AUDIT.collect_claims(root, None)
    require(claims == load_json(packet / "claims.json"), "upstream claims source changed")
    source = root / claims["checkout_path"]
    compare_payload(packet, claims["source_snapshot"], source.read_bytes())
    text = source.read_text(encoding="utf-8", errors="replace")
    matcher = AUDIT.re.compile(r"ios 16\.5|home screen|display|touch|buttons|wi-?fi|gpu|metal|fps|springboard", AUDIT.re.I)
    excerpts = [
        {"line": index, "text": line}
        for index, line in enumerate(text.splitlines(), 1)
        if matcher.search(line)
    ]
    excerpt_payload = AUDIT.json_bytes(
        {
            "schema_version": 1,
            "classification": "upstream_assertions_not_local_hardware_validation",
            "source": "source/PORTING.md",
            "excerpts": excerpts,
        }
    )
    compare_payload(packet, claims["excerpts"], excerpt_payload)
    counts["claim_excerpts"] = claims["excerpt_count"]

    require(not issues, "component expectation checks failed: " + "; ".join(issues))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--checkout", default=str(AUDIT.DEFAULT_CHECKOUT))
    args = parser.parse_args()
    packet = resolve_packet(args.packet)
    root = Path(args.checkout).resolve()
    manifest = verify_manifest(packet)
    result = load_json(packet / "result.json")
    require(result.get("passed") is True and result.get("status") == "passed", "audit packet did not pass")
    require(
        all(result.get(key) is False for key in (
            "device_operations", "phone_queries", "phone_writes", "phone_reboots", "flashing", "ipsw_downloaded"
        )),
        "packet incorrectly records a device or IPSW operation",
    )
    repository_counts = verify_repositories(packet, root)
    component_counts = verify_components(packet, root)
    verification = {
        "schema_version": 1,
        "passed": True,
        "scope": "packet ledger plus live host checkout/toolchain/SDK; no phone access",
        "packet": str(packet),
        "manifest_files": len(manifest["files"]),
        **repository_counts,
        **component_counts,
        "device_operations": False,
    }
    print(json.dumps(verification, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
