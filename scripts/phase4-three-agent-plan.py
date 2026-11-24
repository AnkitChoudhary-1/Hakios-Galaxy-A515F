#!/usr/bin/env python3
"""Prepare and verify an isolated, documented Phase 4 three-agent round.

Run consequential invocations through scripts/run.py. Preparation copies source
slices and saved handoffs, and creates empty private WSL output directories. It
does not build a kernel, start an agent, or access the phone. Publishing changes
only central planning/documentation files. Captured evidence is never deleted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_ROUND = "phase4-three-agents-20261117"
OLD_BASE = "parallel/snapshots/20261117T032633356619Z-four-worker-baseline"
OLD_BASE_SHA = "830e8ccb031b63ed24687b380c446cd93bc866789333cb566b74b8600d9ac881"
OLD_ROUND = "parallel/phase4-20261117T032633356619Z"
PORT = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z"
ROLES = {
    "agent-1-storage-recovery": {
        "task": "Read-only UFS initialization, genuine larger reads and recovery persistence",
        "seed": "base",
        "owned": ["drivers/storage/*", "prototype/phase4-platform/a51_ufs_readonly.h",
                  "prototype/phase4-platform/tests/ufs_model.c",
                  "prototype/phase4-platform/tests/storage_recovery/*",
                  "prototype/xnu-loader/a51_recovery_export.S",
                  "scripts/phase4_envelope.py", "scripts/phase4_pstore.py",
                  "scripts/phase4_storage.py", "scripts/phase4_capture.py"],
    },
    "agent-2-display-brightness": {
        "task": "Framebuffer ownership, DECON/DSIM/panel control and brightness",
        "seed": "display-brightness",
        "owned": ["drivers/display/*", "prototype/phase4-platform/a51_display.h",
                  "prototype/phase4-platform/tests/display_model.c",
                  "prototype/phase4-platform/tests/display/*"],
    },
    "agent-3-touch-keys": {
        "task": "Melfas touch, power/volume keys and event delivery",
        "seed": "touch-keys",
        "owned": ["drivers/input/*", "prototype/phase4-platform/a51_input.h",
                  "prototype/phase4-platform/tests/input_model.c",
                  "prototype/phase4-platform/tests/input/*"],
    },
}
SHARED = ["prototype/phase4-platform/hakios.a51.c",
          "prototype/phase4-platform/hakios.a51.h",
          "prototype/phase4-platform/hello.c",
          "prototype/phase4-platform/gic_v2_irq.c",
          "prototype/phase4-platform/qemu_entry.S",
          "prototype/phase4-platform/tests/reporting_model.c",
          "prototype/phase4-platform/tests/cpp_driver_model.cpp",
          "prototype/xnu-loader/xnu_trampoline.S",
          "prototype/xnu-loader/xnu_trampoline.h",
          "scripts/phase4_reporting.py", "scripts/phase4_support.py"]
SEEDS = {
    "display-brightness": {
        "version": "Sixth Delivery", "status": "unreviewed_saved_candidate",
        "patch": "patches/unified_antigravity_phase4.patch",
        "sha256": "aef3f6d2acd6df4b29f88d8df1a106c92e9822f0a5fe861b67865ad604cd2c06",
        "claimed_host_cases": 233, "claimed_host_checks": 337857,
        "review": "main/verification/display-fifth/REVIEW-FIFTH.md",
        "review_manifest": "main/verification/display-fifth/20261117T075600790338Z/REVIEW-MANIFEST.json",
        "review_manifest_sha256": "878ddacb2c1ddacb428940903262156ba23c8dac2e05d203fa4ac9a17cb7734a",
    },
    "touch-keys": {
        "version": "Revision 7", "status": "unreviewed_saved_candidate",
        "patch": "patches/phase4_input_root.patch",
        "sha256": "f0a4677ad49f622afc743ef79ee60b4389ff52088074c34d98fe7c1764d413ed",
        "claimed_host_checks": 349443,
        "review": "main/verification/input-rev6/REVIEW-REVISION-6.md",
        "review_manifest": "main/verification/input-rev6/20261117T082608558933Z/REVIEW-MANIFEST.json",
        "review_manifest_sha256": "c9a600e705fa8f32ea9492de724233709ff2a62e2872f5f94b8e5d7510dcf3e8",
    },
}
CENTRAL = ["README.md", "docs/INDEX.md", "docs/STATE.md", "state.json",
           "docs/IMPLEMENTATION-LOG.md", "manifests/phase4-three-agent-workflow.json"]
PLAN_DOCS = ["README.md", "WORKFLOW.md", "HANDOFF-TEMPLATE.md",
             "CODEX-MERGE-AND-PHYSICAL-TEST.md",
             "prompts/agent-1-storage-recovery.md",
             "prompts/agent-2-display-brightness.md",
             "prompts/agent-3-touch-keys.md"]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def pin(path):
    require(path.is_file() and not path.is_symlink(), "Not a regular file: " + str(path))
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel(path):
    return path.relative_to(PROJECT).as_posix()


def files_under(root, skip_scratch=False):
    found = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink() and not path.is_junction(), "Link requires separate audit: " + str(path))
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if skip_scratch and (name.startswith("test_results/tmp/") or "__pycache__" in path.parts):
            continue
        found[name] = pin(path)
    return found


def copy_checked(source, dest, expected):
    require(pin(source) == expected, "Source changed before copy: " + str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    require(pin(dest) == expected and pin(source) == expected, "Source changed during copy: " + str(source))


def freeze_tree(source, dest, skip_scratch=False):
    before = files_under(source, skip_scratch)
    for name, expected in before.items():
        copy_checked(source / name, dest / name, expected)
    require(files_under(source, skip_scratch) == before, "Tree changed during capture: " + str(source))
    require(files_under(dest) == before, "Captured tree mismatch: " + str(dest))
    return before


def check_legacy_guards():
    text = (PROJECT / "scripts/phase4-device-gate.py").read_text(encoding="utf-8")
    require("raise RuntimeError(LEGACY_GATE_DISABLED)" in text, "Legacy cycle guard missing")
    require(re.search(r"def main\(\):\s+print\(LEGACY_GATE_DISABLED, file=sys.stderr\)\s+return 2", text),
            "Legacy main guard missing")


def verify_old_snapshot():
    root = PROJECT / OLD_BASE
    require(pin(root / "MANIFEST.json")["sha256"] == OLD_BASE_SHA, "Historical baseline manifest drift")
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    sections = {"main_files": "main-base", "wsl_files": "wsl-adapted",
                "references": "references", "instructions": "instructions", "metadata_files": ""}
    count = 0
    for section, directory in sections.items():
        for name, expected in manifest[section].items():
            require(pin(root / directory / name) == expected, "Historical source drift: " + section + "/" + name)
            count += 1
    for label, worker in manifest["workers"].items():
        for name, expected in worker["files"].items():
            require(pin(root / "handoffs" / label / name) == expected, "Historical worker drift: " + label + "/" + name)
            count += 1
    return manifest, count


def select_main_sources():
    selected = set()
    suffixes = {".c", ".cpp", ".h", ".S", ".ld", ".py", ".md"}
    for folder in ["drivers", "prototype/phase4-platform", "prototype/xnu-loader"]:
        for path in (PROJECT / folder).rglob("*"):
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts:
                selected.add(rel(path))
    for name in ["run.py", "phase4_reporting.py", "phase4_envelope.py", "phase4_pstore.py",
                 "phase4_storage.py", "phase4_capture.py", "phase4_support.py"]:
        selected.add("scripts/" + name)
    return {name: pin(PROJECT / name) for name in sorted(selected)}


def prepare_wsl(round_id, packet):
    # All subprocess arguments are passed directly, without a shell. Only the
    # new round's directories may be created; shared sources are read-only.
    code = '''import hashlib,json,pathlib,subprocess
project=pathlib.Path('/mnt/c/Users/Ankit/Desktop/A51/hakios-a51')
old=json.loads((project / OLD / 'MANIFEST.json').read_text())
port=pathlib.Path(PORT)
native=port/'xnu-src/xnu-8796.121.2'
result={'source_changes':False,'device_operations':0,'files':{},'heads':{}}
for key,expected in old['wsl_files'].items():
    kind,name=key.split('/',1)
    source=(native if kind=='native' else port)/name
    data=source.read_bytes()
    actual={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    result['files'][key]={'path':str(source),'pin':actual,'matches_old':actual==expected}
for label,root in [('common',port),('native',native)]:
    head=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    result['heads'][label]=head
task_root=pathlib.Path('/opt/a51-hakios/parallel')/ROUND
assert not task_root.exists(), 'WSL round already exists; choose a new ID'
assert task_root.resolve().is_relative_to(pathlib.Path('/opt/a51-hakios').resolve()), 'WSL path escaped HakiOS root'
task_root.mkdir(parents=True,exist_ok=False)
result['private_roots']={}
for role in ROLES+['codex-integration']:
    root=task_root/role
    root.mkdir(exist_ok=False)
    for folder in ['obj','tmp','cache','tests']:
        (root/folder).mkdir(exist_ok=False)
    result['private_roots'][role]=str(root)
print(json.dumps(result,indent=2))
'''
    code = "OLD=" + repr(OLD_BASE) + "\nPORT=" + repr(PORT) + "\nROUND=" + repr(round_id) + "\nROLES=" + repr(list(ROLES)) + "\n" + code
    argv = ["wsl.exe", "-d", "A51-KernelBuilder", "--exec", "python3", "-B", "-c", code]
    started = now()
    result = subprocess.run(argv, capture_output=True, timeout=60, check=False)
    (packet / "wsl.stdout").write_bytes(result.stdout)
    (packet / "wsl.stderr").write_bytes(result.stderr)
    write_json(packet / "wsl-command.json", {"argv": argv, "started_utc": started,
                                             "finished_utc": now(), "exit_code": result.returncode})
    require(result.returncode == 0, "WSL setup failed; retain original stdout/stderr in " + rel(packet))
    return json.loads(result.stdout.decode("utf-8"))


def prepare(round_id):
    root = PROJECT / "parallel" / round_id
    require(not root.exists(), "Round already exists; do not overwrite it: " + str(root))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    packet = PROJECT / "evidence/phase-4/three-agent-preparation" / stamp
    packet.mkdir(parents=True, exist_ok=False)
    snapshot = PROJECT / "parallel/snapshots" / (stamp + "-three-agent-seeds")
    snapshot.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "round": round_id, "packet": rel(packet), "snapshot": rel(snapshot),
              "started_utc": now(), "status": "capturing", "agents_started": False,
              "kernel_builds": 0, "device_operations": 0, "phase_4_gate_passed": False}
    write_json(packet / "REPORT.json", report)
    try:
        check_legacy_guards()
        old, count = verify_old_snapshot()
        main = select_main_sources()
        protected = dict(main)
        protected["scripts/phase4-device-gate.py"] = pin(PROJECT / "scripts/phase4-device-gate.py")
        for name, expected in main.items():
            copy_checked(PROJECT / name, snapshot / "base" / name, expected)
        for section, dest in [("references", "references"), ("wsl_files", "wsl-adapted"), ("instructions", "instructions")]:
            for name, expected in old[section].items():
                copy_checked(PROJECT / OLD_BASE / dest / name, snapshot / dest / name, expected)
        captured = {}
        for name, details in SEEDS.items():
            source = PROJECT / OLD_ROUND / name
            require(details["version"] in (source / "HANDOFF.md").read_text(encoding="utf-8"), "Unexpected handoff version: " + name)
            require(pin(source / details["patch"])["sha256"] == details["sha256"], "Unexpected seed patch: " + name)
            captured[name] = freeze_tree(source, snapshot / "candidates" / name, skip_scratch=True)
            for key in ["review", "review_manifest"]:
                current = PROJECT / OLD_ROUND / details[key]
                expected = pin(current)
                if key == "review_manifest":
                    require(expected["sha256"] == details["review_manifest_sha256"], "Historical review manifest drift: " + name)
                copy_checked(current, snapshot / "historical-reviews" / name / current.name, expected)
        wsl = prepare_wsl(round_id, packet)
        root.mkdir(parents=True, exist_ok=False)
        roles = {}
        for role, details in ROLES.items():
            worker = root / role
            worker.mkdir(exist_ok=False)
            shutil.copytree(snapshot / "base", worker / "original")
            shutil.copytree(snapshot / "base", worker / "seed")
            if details["seed"] != "base":
                shutil.copytree(snapshot / "candidates" / details["seed"] / "work", worker / "seed", dirs_exist_ok=True)
            shutil.copytree(worker / "seed", worker / "work")
            for folder in ["scripts", "docs", "patches", "proposals", "test-results"]:
                (worker / folder).mkdir(exist_ok=False)
            copy_checked(PROJECT / "scripts/run.py", worker / "scripts/run.py", main["scripts/run.py"])
            (worker / "docs/STATE.md").write_text("# Private worker state\n\nPrepared; agent has not started. Host and physical acceptance are pending.\n\nUpdate this file with evidence links; central STATE/state.json belong to Codex.\n", encoding="utf-8")
            (worker / "docs/IMPLEMENTATION-LOG.md").write_text("# Private implementation log\n\nAppend every implementation/configuration change, purpose, files, logged verification, failures, limitations and rollback. No agent implementation has started.\n", encoding="utf-8")
            seed_manifest = {"schema_version": 1, "round": round_id, "role": role,
                             "seed_name": details["seed"], "status": "prepared_not_started",
                             "original": files_under(worker / "original"), "seed": files_under(worker / "seed"),
                             "logger": pin(worker / "scripts/run.py")}
            write_json(worker / "SEED-MANIFEST.json", seed_manifest)
            roles[role] = {**details, "windows_root": str(worker).replace("\\", "/"),
                           "wsl_alias": "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51/parallel/" + round_id + "/" + role,
                           "wsl_root": wsl["private_roots"][role], "status": "prepared_not_started",
                           "seed_manifest": {"path": rel(worker / "SEED-MANIFEST.json"), **pin(worker / "SEED-MANIFEST.json")}}
        integration = root / "codex-integration"
        (integration / "scripts").mkdir(parents=True, exist_ok=False)
        copy_checked(PROJECT / "scripts/run.py", integration / "scripts/run.py", main["scripts/run.py"])
        manifest = {"schema_version": 1, "created_utc": now(), "round": round_id,
                    "scope": "Current source slices and saved unreviewed candidates; not full dependency checkouts or hardware evidence",
                    "previous_baseline": {"path": OLD_BASE, "sha256": OLD_BASE_SHA, "verified_files": count},
                    "main_matches_previous": {name: expected == old["main_files"].get(name) for name, expected in main.items() if name in old["main_files"]},
                    "common_head_historical": old["common_head"], "native_head_historical": old["native_head"],
                    "wsl_probe": wsl, "candidates": SEEDS, "captured_candidate_files": captured,
                    "protected_main_files": protected, "files": files_under(snapshot),
                    "pre_post_capture_checks": True, "independent_latest_seed_acceptance": False}
        for name, expected in protected.items():
            require(pin(PROJECT / name) == expected, "Main source changed during preparation: " + name)
        for name, expected in captured.items():
            require(files_under(PROJECT / OLD_ROUND / name, True) == expected, "Worker changed before final freeze check: " + name)
        write_json(snapshot / "MANIFEST.json", manifest)
        baseline = {"schema_version": 1, "round": round_id, "packet": rel(packet),
                    "snapshot": rel(snapshot), "snapshot_manifest": pin(snapshot / "MANIFEST.json"),
                    "previous_baseline": manifest["previous_baseline"], "roles": roles,
                    "coordinator": {"windows_root": str(integration).replace("\\", "/"),
                                    "wsl_root": wsl["private_roots"]["codex-integration"]},
                    "candidates": SEEDS, "helper": {"path": rel(Path(__file__)), **pin(Path(__file__))},
                    "device_operations": 0, "agents_started": False, "physical_gate_passed": False}
        write_json(root / "BASELINE.json", baseline)
        write_json(root / "OWNERSHIP.json", {"round": round_id, "roles": roles,
                                              "coordinator_proposals_only": SHARED,
                                              "central_state_owner": "Codex", "device_owner": "Codex",
                                              "shared_full_builds": "serialized_by_Codex",
                                              "new_agents": "Require a new task ID, isolated roots, disjoint owned paths and declared dependencies"})
        copy_checked(Path(__file__), packet / "preparer.py", pin(Path(__file__)))
        report.update(status="inputs_prepared", finished_utc=now(), baseline=pin(root / "BASELINE.json"),
                      snapshot_manifest=baseline["snapshot_manifest"], protected_main_files_unchanged=True)
        write_json(packet / "REPORT.json", report)
        print(json.dumps({"status": report["status"], "round_root": str(root), "snapshot": rel(snapshot),
                          "snapshot_sha256": baseline["snapshot_manifest"]["sha256"],
                          "captured_candidate_files": {name: len(value) for name, value in captured.items()},
                          "wsl_previous_sources_match": all(item["matches_old"] for item in wsl["files"].values()),
                          "packet": rel(packet)}, indent=2))
    except Exception as exc:
        report.update(status="failed", finished_utc=now(), error=str(exc))
        write_json(packet / "REPORT.json", report)
        raise


def verify_inputs(round_id, role=None):
    root = PROJECT / "parallel" / round_id
    baseline = json.loads((root / "BASELINE.json").read_text(encoding="utf-8"))
    require(pin(PROJECT / baseline["helper"]["path"])["sha256"] == baseline["helper"]["sha256"], "Planning helper drift")
    snapshot = PROJECT / baseline["snapshot"]
    require(pin(snapshot / "MANIFEST.json") == baseline["snapshot_manifest"], "Selected snapshot manifest drift")
    manifest = json.loads((snapshot / "MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        require(pin(snapshot / name) == expected, "Frozen input drift: " + name)
    chosen = [role] if role else list(ROLES)
    for name in chosen:
        require(name in baseline["roles"], "Unknown role: " + name)
        worker = root / name
        require(pin(worker / "SEED-MANIFEST.json") == {k: v for k, v in baseline["roles"][name]["seed_manifest"].items() if k != "path"}, "Worker seed manifest drift: " + name)
        saved = json.loads((worker / "SEED-MANIFEST.json").read_text(encoding="utf-8"))
        require(files_under(worker / "original") == saved["original"], "Worker original drift: " + name)
        require(files_under(worker / "seed") == saved["seed"], "Worker seed drift: " + name)
        require(pin(worker / "scripts/run.py") == saved["logger"], "Private logger drift: " + name)
    print(json.dumps({"status": "verified_inputs", "round": round_id, "roles": chosen,
                      "snapshot_files": len(manifest["files"]), "snapshot_sha256": baseline["snapshot_manifest"]["sha256"],
                      "kernel_builds": 0, "device_operations": 0}, indent=2))
    return baseline, manifest


def replace_navigation(path, round_id):
    current = path.read_text(encoding="utf-8")
    heading_end = current.find("\n")
    historical = current.find("\n## Retained Phase 4 host checkpoint")
    require(heading_end >= 0 and historical > heading_end, "Unexpected navigation structure: " + str(path))
    block = ("\n\n## Phase 4 three-agent plan - 17 November 2026\n\n"
             "Phase 4 remains IN PROGRESS; its physical peripheral gate is UNPASSED. "
             "Three separate prompts cover UFS/recovery, display/brightness and touch/keys. "
             "Codex owns independent review, shared integration, central documentation and later serialized physical testing. "
             "Read [the workflow](PHASE-4-THREE-AGENT-WORKFLOW.md) for the current dispatch.\n\n"
             "Display Sixth Delivery and input Revision 7 are pinned saved candidates awaiting independent review. "
             "Their host claims are not acceptance evidence. Previous worker rounds and reviewed snapshots are retained. "
             "No agent or phone test was started while preparing this plan. Older scopes below are historical.\n")
    if path.name == "README.md":
        block = block.replace("(PHASE-4-THREE-AGENT-WORKFLOW.md)", "(docs/PHASE-4-THREE-AGENT-WORKFLOW.md)")
    path.write_text(current[:heading_end] + block + current[historical:], encoding="utf-8")


def publish(round_id):
    baseline, manifest = verify_inputs(round_id)
    root = PROJECT / "parallel" / round_id
    packet = PROJECT / baseline["packet"]
    report = json.loads((packet / "REPORT.json").read_text(encoding="utf-8"))
    require(report["status"] == "inputs_prepared", "Publish once only; preserve prior packet")
    documents = [rel(root / name) for name in PLAN_DOCS] + ["docs/PHASE-4-THREE-AGENT-WORKFLOW.md", rel(Path(__file__))]
    for name in documents:
        require((PROJECT / name).is_file(), "Missing plan document: " + name)
    for name, expected in manifest["protected_main_files"].items():
        require(pin(PROJECT / name) == expected, "Main source changed before publication: " + name)
    check_legacy_guards()
    before = {}
    for name in CENTRAL:
        source = PROJECT / name
        before[name] = pin(source) if source.exists() else None
        if source.exists():
            copy_checked(source, packet / "before" / name, before[name])
    report["before"] = before
    write_json(packet / "REPORT.json", report)
    for name in ["README.md", "docs/INDEX.md"]:
        replace_navigation(PROJECT / name, round_id)
    state_path = PROJECT / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    workflow = {"schema_version": 1, "status": "prepared_not_started", "round": round_id,
                "guide": "docs/PHASE-4-THREE-AGENT-WORKFLOW.md", "packet": baseline["packet"],
                "baseline": rel(root / "BASELINE.json"), "snapshot": baseline["snapshot"],
                "snapshot_manifest": baseline["snapshot_manifest"], "roles": baseline["roles"],
                "latest_candidates": SEEDS, "coordinator": baseline["coordinator"],
                "agents_started": False, "device_operations_this_preparation": 0,
                "main_driver_changes": False, "wsl_source_changes": False, "physical_gate_passed": False,
                "previous_workflow_retained": "phase_4_parallel_workflow",
                "prior_criteria": {k: state["phase_4_criteria"][k] for k in ["display_scanout_and_dimensions", "dsim_repeatable_brightness",
                    "physical_touch_events_and_coordinates", "physical_power_volume_key_events", "input_event_interface"]}}
    state["updated_date_local"] = "2026-11-17"
    state["active_task"] = "Three Phase 4 prompts prepared; UFS/recovery, display Sixth Delivery and input Revision 7 await worker execution/review; Codex owns integration and later physical acceptance"
    state["phase_4_three_agent_workflow"] = workflow
    state["phase_4_criteria"].update({
        "display_scanout_and_dimensions": "physical_unverified;private_display_sixth_candidate_unreviewed;authoritative_framebuffer_provenance_pending",
        "dsim_repeatable_brightness": "physical_unverified;private_display_sixth_host_claims_await_independent_reproduction",
        "physical_touch_events_and_coordinates": "physical_unverified;private_input_rev7_candidate_unreviewed",
        "physical_power_volume_key_events": "physical_unverified;private_input_rev7_candidate_unreviewed",
        "input_event_interface": "private_rev7_production_bus_irq_sysctl_candidate_unreviewed;combined_interface_acceptance_pending"})
    state["blockers"] = [
        "Display Sixth Delivery needs independent review/reproduction and authoritative framebuffer allocation or inherited reservation; physical visibility/dimensions/brightness remain unverified",
        "Input Revision 7 needs independent recovery, fault-state and end-to-end callback deadline verification; combined event delivery and physical touch/keys remain unverified",
        "UFS controller/PHY initialization is pending; current read-only core adopts an already initialized idle link",
        "Current genuine 64 KiB READ(10) has no qualifying silicon result; earlier system bus fatal cause remains unresolved",
        "Committed binary recovery export persistence is unverified; historical baseline restoration is verified, current phone state is unknown",
        "Combined patch review, attributed full build/QEMU and serialized physical peripheral acceptance remain pending"]
    require(state["phase_4_status"] == "in_progress" and state["phase_4_device_gate_passed"] is False, "Phase 4 status unexpectedly changed")
    write_json(state_path, state)
    write_json(PROJECT / "manifests/phase4-three-agent-workflow.json", workflow)
    (PROJECT / "docs/STATE.md").write_text(
        "# HakiOS A51 - current state\n\nUpdated 17 November 2026 (Asia/Calcutta). Phase 4 is IN PROGRESS; its physical peripheral gate is UNPASSED. Phases 1-3 retain selected completion gates; Phases 5-10 remain planned.\n\n"
        "The [three-agent workflow](PHASE-4-THREE-AGENT-WORKFLOW.md) is prepared, with separate prompts/workspaces for UFS and recovery, display and brightness, and touch and keys. Codex owns independent review, shared ABI/platform integration, central state/documentation, serialized full builds and later phone operations. No agents were started or phone operations performed during preparation.\n\n"
        "Display **Sixth Delivery** and input **Revision 7** are frozen saved candidates, **unreviewed**. They claim to repair the fifth-display and revision-6 input findings; those claims still require independent reproduction against the exact selected sources. Do not restart from the older candidates or treat earlier findings as automatically still present. The [round baseline](../parallel/" + round_id + "/BASELINE.json) pins all selected inputs and private seeds. Prior rounds, failed freeze evidence and reviewed packets are preserved.\n\n"
        "Retained main host proof: **216 native cases / 337,511 checks, 244 storage models and 25 QEMU checks**, reusable only for matching source/dependency/build pins. Display-sixth's 233/337,857 and input-rev7's 349,443 checks are worker claims, not newly accepted results; their overlapping totals must not be added together.\n\n"
        "Remaining work: genuine UFS controller/PHY initialization; current one-command 64 KiB known-image execution; committed recovery-envelope persistence; authoritative framebuffer ownership/coherency and reliable visible output; independent validation of latest display/input fixes; combined event delivery/build execution; and physical brightness, touch, key and read-only storage acceptance. Hardware bring-up effort cannot be estimated reliably from compilation or case counts.\n\n"
        "Historical 4 KiB UFS prefixes, 16 x 4 KiB aggregates and independently verified baseline restoration retain their original scopes. None verifies the current genuine 64 KiB revision. The current phone state is unknown. Historical device-query/write fields in state.json are preserved; the new planning record explicitly has zero device operations. Both legacy device-gate entry guards remain disabled; phase4-resume-audit.py was not run.\n\n"
        "Next: launch the three provided prompts in separate chats or agent contexts, validate/document their fixed outputs, then have Codex reconstruct and review their patches, resolve shared changes and execute the combined host/build/QEMU checks. A later bounded physical session must retain fresh-nonce original results, user observations and verified return evidence before any physical gate changes.\n", encoding="utf-8")
    log_path = PROJECT / "docs/IMPLEMENTATION-LOG.md"
    log = log_path.read_text(encoding="utf-8")
    next_id = max([int(x) for x in re.findall(r"^## P4-(\d+) -", log, re.M)] or [0]) + 1
    entry = ("\n\n## P4-" + str(next_id).zfill(3) + " - Prepare the three-agent Phase 4 dispatch (" + packet.name + ")\n\n"
             "Purpose/files: new scripts/phase4-three-agent-plan.py; parallel/" + round_id + "/ prompts, workflow, ownership, handoff and Codex integration/physical-test guides; fixed source/candidate snapshot " + baseline["snapshot"] + "; three private Windows source/logger roots and empty WSL output roots plus coordinator roots; docs/PHASE-4-THREE-AGENT-WORKFLOW.md; README/INDEX, STATE/state.json, manifests/phase4-three-agent-workflow.json and this append-only log. No existing worker, main driver or WSL source was edited.\n\n"
             "Verification: exact prepare/publish/verify argv, output, times and exit statuses are retained under runs/ via scripts/run.py. The old 464-file snapshot was checked. New saved display Sixth Delivery and input Revision 7 were captured with pre/post source/tree hashes and explicitly remain unreviewed; MANIFEST SHA-256 " + baseline["snapshot_manifest"]["sha256"] + ". Per-file sizes/hashes, original/seed correspondence, logger copies, WSL adapted source/HEAD observations, disjoint ownership, planning links and disabled legacy entry guards are verified by the planning helper. No kernel build or peripheral test was needed for this documentation/setup change.\n\n"
             "Limitations/next: all Phase 4 physical peripheral gates remain unpassed. Worker totals are claims and overlap; do not sum them or attribute them to a merged binary. Source slices are not full checkouts. Launch the three prompts, reproduce the latest fixes and retain failed attempts, submit owned patches separately from shared proposals, then let Codex review/build/test the combined sources and coordinate a later physical session. No agents or phone operations were started here; current device state remains unknown. Historical phone-query/write fields are preserved.\n\n"
             "Rollback: retain this evidence packet, new round and snapshots; restore only central files still matching the recorded after hashes from exact before copies. For newly created planning files, record withdrawal separately and preserve their bytes; do not delete historical evidence or reset source trees. Private output directories are additive. Never re-enable the two legacy device-gate guards or run the obsolete resume audit as a rollback. No device restoration is required for this planning change.\n")
    log_path.write_text(log + entry, encoding="utf-8")
    after = {}
    for name in CENTRAL + documents + [rel(root / "BASELINE.json"), rel(root / "OWNERSHIP.json")]:
        after[name] = pin(PROJECT / name)
        copy_checked(PROJECT / name, packet / "after" / name, after[name])
    report.update(status="plan_published", published_utc=now(), after=after,
                  implementation_log_entry="P4-" + str(next_id).zfill(3),
                  documentation_changes_only=True, independent_latest_seed_acceptance=False)
    write_json(packet / "REPORT.json", report)
    print(json.dumps({"status": report["status"], "packet": rel(packet),
                      "implementation_log_entry": report["implementation_log_entry"], "documents": len(documents),
                      "agents_started": False, "device_operations": 0}, indent=2))


def verify_plan(round_id):
    baseline, manifest = verify_inputs(round_id)
    root = PROJECT / "parallel" / round_id
    report = json.loads((PROJECT / baseline["packet"] / "REPORT.json").read_text(encoding="utf-8"))
    require(report["status"] == "plan_published", "Plan has not been published")
    for name, expected in report["after"].items():
        require(pin(PROJECT / name) == expected, "Published document drift: " + name)
    for name, expected in manifest["protected_main_files"].items():
        require(pin(PROJECT / name) == expected, "Protected main source drift: " + name)
    check_legacy_guards()
    state = json.loads((PROJECT / "state.json").read_text(encoding="utf-8"))
    require(state["phase_4_device_gate_passed"] is False, "Physical gate changed during planning")
    require(state["phone_queries_this_continuation"] == json.loads((PROJECT / baseline["packet"] / "before/state.json").read_text(encoding="utf-8"))["phone_queries_this_continuation"], "Historical query field overwritten")
    require(state["device_writes_this_phase"] == json.loads((PROJECT / baseline["packet"] / "before/state.json").read_text(encoding="utf-8"))["device_writes_this_phase"], "Historical write field overwritten")
    for name in PLAN_DOCS:
        text = (root / name).read_text(encoding="utf-8")
        require("TODO" not in text and "@SNAPSHOT" not in text, "Unfilled plan template: " + name)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            require((root / name).parent.joinpath(target.split("#", 1)[0]).resolve().exists(), "Broken plan link: " + name + " -> " + target)
    ownership = json.loads((root / "OWNERSHIP.json").read_text(encoding="utf-8"))
    flat = [(role, pattern) for role, item in ownership["roles"].items() for pattern in item["owned"]]
    require(len({pattern for _, pattern in flat}) == len(flat), "Duplicate owned patterns")
    verification = {"status": "verified_plan", "verified_utc": now(), "round": round_id,
                    "published_files": len(report["after"]), "source_files_unchanged": len(manifest["protected_main_files"]),
                    "private_roles": len(ROLES), "legacy_entry_guards_disabled": 2,
                    "kernel_builds": 0, "agents_started": False, "device_operations": 0,
                    "phase_4_device_gate_passed": False}
    write_json(PROJECT / baseline["packet"] / "VERIFICATION.json", verification)
    print(json.dumps(verification, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "publish", "verify-inputs", "verify"])
    parser.add_argument("--round", default=DEFAULT_ROUND)
    parser.add_argument("--role", choices=list(ROLES))
    args = parser.parse_args()
    require(re.fullmatch(r"[a-z0-9-]+", args.round), "Round ID must be a simple lowercase name")
    {"prepare": prepare, "publish": publish, "verify-inputs": lambda name: verify_inputs(name, args.role),
     "verify": verify_plan}[args.action](args.round)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
