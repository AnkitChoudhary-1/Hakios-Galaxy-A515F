#!/usr/bin/env python3
"""Preserve and inventory main Phase 4 work. No device mutation.
Run through scripts/run.py. Antigravity's entire working tree is excluded.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
from phase4_device import BASELINE_SHA256, Device
from phase4_support import PROJECT, command, documents, index_packet, new_packet, pin, require, write_json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    packet = new_packet("main-resume", __file__)
    before = {}
    paths = [PROJECT / "README.md", PROJECT / "state.json"]
    for directory in ("docs", "scripts", "manifests", "drivers",
                      "prototype/phase4-platform", "prototype/phase4-loader", "prototype/xnu-loader"):
        paths += [p for p in (PROJECT / directory).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts]
    for path in sorted(set(paths)):
        rel = path.relative_to(PROJECT).as_posix()
        require(not rel.startswith("parallel/"), "Parallel workspace is excluded")
        saved = packet / "initial" / rel
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)
        before[rel] = pin(saved)
    for source, name in ((PROJECT.parent / "AGENTS.md", "AGENTS.md"),
                         (PROJECT.parent / "hakios-assessment/ROADMAP.md", "ROADMAP.md")):
        shutil.copy2(source, packet / name)
    write_json(packet / "initial-pins.json", before)
    report = {"schema_version": 1, "packet": packet.relative_to(PROJECT).as_posix(),
              "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "main_files_preserved": len(before), "antigravity_accessed": False,
              "device_queries": False, "device_writes": False, "device_reboots": False,
              "phase_4_device_gate_passed": False, "errors": []}
    recent = []
    for folder in sorted((PROJECT / "runs").iterdir(), key=lambda p: p.name)[-50:]:
        meta = folder / "metadata.json"
        if meta.is_file():
            value = json.loads(meta.read_text(encoding="utf-8"))
            recent.append({key: value.get(key) for key in
                           ("run_id", "label", "status", "exit_code", "started", "finished")})
    write_json(packet / "recent-runs.json", recent)
    report["unfinished_recent_wrappers"] = [r["run_id"] for r in recent if r["status"] == "running"]
    workspace = json.loads((PROJECT / "manifests/phase4-workspace.json").read_text(encoding="utf-8"))
    root = workspace["root"]
    adaptation = json.loads((PROJECT / "manifests/phase4-platform-adaptation.json").read_text(encoding="utf-8"))
    build = json.loads((PROJECT / "manifests/phase4-platform-build.json").read_text(encoding="utf-8"))
    wsl_packet = "/mnt/c" + str(packet).replace("\\", "/")[2:]
    wsl_code = """
import hashlib, json, pathlib, shutil, subprocess
root=pathlib.Path(ROOT)
native=root/'xnu-src/xnu-8796.121.2'
packet=pathlib.Path(PACKET)
assert root.is_relative_to(pathlib.Path('/opt/a51-hakios/experimental/phase4-port'))
def ppin(p):
 b=p.read_bytes(); return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def git(tree,*args):
 p=subprocess.run(['git','-C',str(tree),*args],capture_output=True,timeout=40)
 if p.returncode: raise RuntimeError(p.stderr.decode('utf-8','replace'))
 return p.stdout
instructions={}
for tree in (root,native):
 for ancestor in (tree,*tree.parents):
  p=ancestor/'AGENTS.md'
  if p.is_file(): instructions[str(p)]=p.read_text()
scan=subprocess.run(['rg','--files','--hidden','-g','AGENTS.md','-g','!**/.git/**',
                     '-g','!**/BUILD/**','-g','!xnu-deps/**',str(root)],
                     capture_output=True,timeout=40)
assert scan.returncode in (0,1), scan.stderr
for name in scan.stdout.decode().splitlines():
 p=pathlib.Path(name); instructions[name]=p.read_text()
result={'root':str(root),'instructions':instructions,'heads':{},'drift':[],
        'artifacts':{},'phase3_parent_unchanged':True,'active_processes':[]}
for label,tree in (('common',root),('native',native)):
 result['heads'][label]=git(tree,'rev-parse','HEAD').decode().strip()
 (packet/(label+'-git.diff')).write_bytes(git(tree,'diff','--binary','HEAD'))
 (packet/(label+'-git-status.txt')).write_bytes(git(tree,'status','--short'))
for row in ADAPTED:
 path=(native if row['tree']=='native' else root)/row['path']
 observed=ppin(path) if path.is_file() else None
 if observed!=row['after']: result['drift'].append({'tree':row['tree'],'path':row['path'],'observed':observed,'expected':row['after']})
 if path.is_file():
  saved=packet/'wsl-initial'/row['tree']/row['path']
  saved.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,saved)
for rel in ('hakios-kernel','userland/hello','.config'):
 path=root/rel
 result['artifacts'][rel]=ppin(path) if path.is_file() else None
for rel,expected in PARENT.items():
 path=pathlib.Path(PARENT_ROOT)/rel
 if not path.is_file() or ppin(path)!=expected: result['phase3_parent_unchanged']=False
for path in pathlib.Path('/proc').iterdir():
 if path.name.isdigit():
  try:
   raw=(path/'cmdline').read_bytes().replace(bytes([0]),b' ').decode('utf-8','replace')
   if str(root) in raw and any(t in raw for t in ('qemu-system','make-kernel','aarch64-linux','clang','make ')):
    result['active_processes'].append({'pid':int(path.name),'command':raw[:1500]})
  except (OSError,PermissionError): pass
print(json.dumps(result))
"""
    wsl_code = ("ROOT=" + repr(root) + "\nPACKET=" + repr(wsl_packet) +
                "\nADAPTED=" + repr(adaptation["changes"]) +
                "\nPARENT=" + repr(workspace["preserved"]) +
                "\nPARENT_ROOT=" + repr(workspace["parent"]) + "\n" + wsl_code)
    records = []
    try:
        proc = command(packet, records, "wsl-state",
                       ["wsl", "-d", "A51-KernelBuilder", "--exec", "python3", "-B", "-c", wsl_code],
                       timeout=60)
        report["wsl"] = json.loads(proc.stdout)
        require(not report["wsl"]["drift"], "Adapted WSL sources drifted; before bytes retained")
        require(report["wsl"]["phase3_parent_unchanged"], "Selected Phase 3 parent changed")
        require(report["wsl"]["heads"] == build["heads"], "Pinned upstream HEADs changed")
    except Exception as exc:
        report["errors"].append("Host inventory: " + str(exc))
    if not args.host_only:
        dev = Device(packet / "device")
        dev.packet.mkdir()
        report["device_queries"] = True
        mode = dev.mode("connection")
        report["device_mode"] = mode
        if mode == "device":
            try:
                text = dev.text("identity-baseline",
                    "id && getprop ro.product.model && getprop ro.product.device && "
                    "getprop sys.boot_completed && cat /proc/sys/kernel/random/boot_id && "
                    "readlink -f /dev/block/by-name/boot && "
                    "sha256sum /dev/block/sda12 /dev/block/by-name/recovery /dev/block/by-name/dtbo && "
                    "blockdev --getsize64 /dev/block/sda12 && cat /proc/sys/kernel/random/boot_id",
                    timeout=55, limit=16384)
                expected = {"boot": BASELINE_SHA256,
                    "recovery":"12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999",
                    "dtbo":"41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6"}
                lines = text.splitlines()
                ids = [s for s in lines if len(s)==36 and s.count("-")==4]
                require("uid=0(root)" in text and "SM-A515F" in text and "a51" in lines, "Unexpected device/root")
                require(len(ids)==2 and ids[0]==ids[1], "Android rebooted during inventory")
                require("1" in lines and "61865984" in lines and "/dev/block/sda12" in lines, "Boot identity mismatch")
                require(all(v in text for v in expected.values()), "Device image hash differs from baseline")
                rollback = PROJECT.parent/"everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img"
                require(pin(rollback)=={"bytes":61865984,"sha256":BASELINE_SHA256}, "Host rollback hash differs")
                report.update(current_android_baseline_verified=True, android_boot_id=ids[0], baseline_hashes=expected)
            except Exception as exc:
                report["errors"].append("Read-only device inventory: " + str(exc))
        else:
            report["errors"].append("Expected Android is unavailable; connection="+repr(mode))
    report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["inventory_passed"] = not report["errors"]
    require(all(pin(PROJECT / rel)==value for rel,value in before.items()),
            "Concurrent main-workspace change; snapshot retained, state not overwritten")
    write_json(packet/"result.json",report)
    state = json.loads((PROJECT/"state.json").read_text(encoding="utf-8"))
    state.update(updated_date_local="2026-11-17", active_phase="phase_4",
                 phase_4_status="in_progress", phase_4_device_gate_passed=False,
                 active_task="Main-owned UFS/storage, recovery evidence and build integration; Antigravity owns display/input preparation",
                 next_action="Resolve source-matched UFS initialization and recovery export; review Antigravity handoff before integration")
    state["phase_4_main_continuation"] = {
        "result":report["packet"]+"/result.json", "inventory_passed":report["inventory_passed"],
        "device_queries":report["device_queries"], "device_writes":False,"device_reboots":False,
        "antigravity_working_folder":"parallel/antigravity-phase4","antigravity_accessed":False,
        "current_android_baseline_verified":report.get("current_android_baseline_verified",False),
        "errors":report["errors"]}
    if report["device_queries"]:
        state["phone_queries_this_continuation"]=True
    status = ("A read-only query verified completed rooted Android and the pinned boot/recovery/DTBO hashes."
              if report.get("current_android_baseline_verified") else
              "The current phone state is not verified: " + "; ".join(report["errors"]))
    intro = f"""# HakiOS A51 — current state

Updated 17 November 2026 (Asia/Calcutta).

## Main Phase 4 continuation — 17 November

Phase 4 is **IN PROGRESS**; its physical peripheral gate is **UNPASSED**. The main agent owns read-only UFS/storage, recovery/log evidence, build integration and device testing. Antigravity prepares display, brightness, touch and keys in parallel/antigravity-phase4; its working folder has not been accessed. Integration awaits the user's handoff.

The previous host proof (216 native cases / 337,511 checks, 244 modeled storage cases and 25 QEMU checks) and selected Phases 1–3 completion evidence remain retained. {status} This inventory made no device write or reboot and establishes no new HakiOS peripheral success.

Initial main files, WSL adapted source bytes, Git diffs, source/build correspondence and recent stopped-wrapper records are retained in {report['packet']}. Inventory passed: {report['inventory_passed']}. Full controller/PHY initialization, attributable current UFS reads, binary recovery persistence and all physical display/input gates remain unfinished. Next: finish the independent storage/recovery work, then review source versions and integrate supported Antigravity changes for combined validation.

"""
    old_state=(PROJECT/"docs/STATE.md").read_text(encoding="utf-8")
    note=f"""

## P4-043 — Preserve and resume the main Phase 4 workspace ({packet.name})

Purpose/files: new scripts/phase4-main-resume.py; docs/STATE.md, state.json and this append-only log. Preserve {len(before)} main project files and every selected WSL adapted file before implementation; record current heads/diffs, artifact pins, selected Phase 3 parent and recent running/stopped wrappers. Exclude Antigravity's entire folder. The dated phase4-resume-audit.py was inspected but not executed because it would overwrite the newer verified checkpoint with obsolete source/failure state.

Verification: logged inventory passed={report['inventory_passed']}; device queries={report['device_queries']}; current pinned Android baseline verified={report.get('current_android_baseline_verified',False)}; errors={report['errors']}. Packet: {report['packet']}; initial-pins.json, wsl-state.stdout, original framed device commands, recent-runs.json and result.json retain exact evidence. Normal exec/node sandboxes failed before any command with registered runtime ownership missing; approved outside-sandbox reads and the project logger provide the usable runtime. All source/build/native/QEMU results remain historical proof unless current pins match.

Limits/next: no device write/reboot, no actual HakiOS storage/display/input execution, no new gate success; current UFS adopts an initialized link and recovery export is unverified. Continue source-matched read-only storage and recovery work while Antigravity prepares display/input. Only this chat coordinates device operations.

Rollback: verify the indexed before/after document copies and restore only this entry's STATE/state changes after checking for later edits; preserve the appended log entry as history. The new resume script may be withdrawn after preserving it. Initial main/WSL source copies are recovery evidence; never wholesale-restore over later supported work. Preserve all prior evidence, Android projects and Antigravity files.
"""
    documents(packet,{"docs/STATE.md":intro+"## Retained 16 November host checkpoint\n\n"+old_state,
                      "state.json":json.dumps(state,indent=2)+"\n",
                      "docs/IMPLEMENTATION-LOG.md":(PROJECT/"docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8")+note})
    index_packet(packet)
    print(json.dumps({k:report.get(k) for k in ("packet","inventory_passed","main_files_preserved","device_mode",
                                               "current_android_baseline_verified","errors")}),flush=True)
    return 0 if report["inventory_passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
