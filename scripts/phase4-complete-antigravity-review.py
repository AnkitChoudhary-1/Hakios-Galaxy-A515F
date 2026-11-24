#!/usr/bin/env python3
"""Complete the first frozen handoff review without changing any worker/main source.

Run through scripts/run.py. Captures correct references, fixes the reviewer
include-path omission, and records adversarial model observations. No device IO.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase4_support import PROJECT, command, index_packet, new_packet, pin, require, write_json

SNAPSHOT = 'parallel/snapshots/20261117T013929281709Z-antigravity-first-handoff'
MANIFEST_SHA = '024b3c2add18375efca9067684054d789844439b7b005090df359aa5e8a1322a'
FIRST = 'evidence/phase-4/antigravity-first-review/20261117T015701009941Z'
ANDROID = Path('/opt/a51-everline/src')
XNU = Path('/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/xnu-src/xnu-8796.121.2')
REFERENCES = {
    'android': (ANDROID, [
        'arch/arm64/boot/dts/samsung/exynos9611-a51_common.dtsi',
        'arch/arm64/boot/dts/samsung/exynos9611-a51_eur_open_gpio_00.dtsi',
        'arch/arm64/boot/dts/samsung/exynos9611-a51_eur_open_gpio_07.dtsi',
        'arch/arm64/boot/dts/samsung/display-lcd_a51_common.dtsi',
        'arch/arm64/boot/dts/samsung/display-lcd_gta4xl_common.dtsi',
        'arch/arm64/boot/dts/exynos/exynos9610.dts',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100.c',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100_mod.c',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100_reg.h',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-decon.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dsim.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dpp.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/dpp_reg.c',
        'drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_lcd_ctrl.c',
        'drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_param.h',
        'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_lcd_ctrl.c',
        'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_param.h',
    ]),
    'xnu': (XNU, [
        'osfmk/arm/memory_types.h', 'osfmk/arm/machine_routines.h',
        'osfmk/arm64/machine_routines.c', 'osfmk/arm/io_map.c',
    ]),
}
C_PROBE = r'''
#include <stdio.h>
#include "a51_display.h"
struct model { unsigned int writes, completion_reads; unsigned long long time; };
static unsigned int rd(void *c, unsigned int r) {
    struct model *m = c;
    if (r == A51_DECON_SCALED_SIZE_0) return A51_DECON_SCALED_SIZE_EXPECTED;
    if (r == A51_DSIM_INTSRC) m->completion_reads++;
    return 0;
}
static void wr(void *c, unsigned int r, unsigned int v) {
    (void)r; (void)v; ((struct model *)c)->writes++;
}
static void barrier(void *c) { (void)c; }
static unsigned long long now(void *c) { return ((struct model *)c)->time; }
static void delay(void *c, unsigned int n) { ((struct model *)c)->time += n; }
int main(void) {
    struct model decon = {0}, dsim = {0};
    struct a51_decon_io d = {&decon, rd, wr, barrier};
    unsigned int size = 0, glb = 1;
    int drc = a51_decon_verify_and_update(&d, &size, &glb);
    struct a51_dsim_io s = {&dsim, rd, wr, now, delay, barrier};
    const uint8_t steps[5] = {50, 120, 200, 255, 180};
    uint8_t history[8] = {0};
    unsigned int done = 0;
    int src = a51_dsim_step_sequence(&s, steps, 5, history, &done);
    printf("{\"scope\":\"simulated_only\",\"decon_disabled_rc\":%d,"
           "\"decon_global_control\":%u,\"decon_shadow_writes\":%u,"
           "\"dsim_no_completion_rc\":%d,\"completion_reads\":%u,"
           "\"brightness_steps\":%u,\"brightness_sequence_delay_us\":%llu}\n",
           drc, glb, decon.writes, src, dsim.completion_reads, done, dsim.time);
    return !(drc == 0 && glb == 0 && decon.writes == 1 &&
             src == 0 && dsim.completion_reads == 0 && done == 5 && dsim.time == 500);
}
'''
CPP_PROBE = r'''
#include <cstdio>
#include "ExynosDSIM.h"
int main() {
    alignas(8) uint32_t regs[0x10000 / 4] = {};
    ExynosDSIMDevice dev = {};
    dev.mmio_base = reinterpret_cast<uintptr_t>(regs);
    regs[DSIM_FIFOCTRL / 4] = DSIM_FIFO_FULL_PH | DSIM_FIFO_FULL_PL;
    regs[DSIM_PKTHDR / 4] = 0xa5a5a5a5u;
    int rc = ExynosDSIM_SendDCSCommand(&dev, DCS_CMD_SET_DISPLAY_ON, nullptr, 0);
    uint32_t header = regs[DSIM_PKTHDR / 4];
    int absent = ExynosDSIM_SendDCSCommand(nullptr, DCS_CMD_SET_DISPLAY_ON, nullptr, 0);
    std::printf("{\"scope\":\"simulated_only\",\"permanent_fifo_full_rc\":%d,"
                "\"header_written_after_timeout\":%s,\"absent_mmio_rc\":%d}\n",
                rc, header != 0xa5a5a5a5u ? "true" : "false", absent);
    return !(rc == 0 && header == (0x05u | (DCS_CMD_SET_DISPLAY_ON << 8)) && absent == 0);
}
'''

def capture(source, dest, expected=None):
    actual = pin(source)
    if expected is not None:
        require(actual == expected, 'Pin mismatch: ' + str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    require(pin(source) == actual and pin(dest) == actual, 'Concurrent source change: ' + str(source))
    return actual

def verify_index(packet):
    for item in json.loads((packet / 'index.json').read_text()):
        require(pin(packet / item['path']) == {'bytes':item['bytes'],'sha256':item['sha256']},
                'Previous review index mismatch: ' + item['path'])

def main():
    if os.name == 'nt':
        script = '/mnt/c' + str(Path(__file__).resolve()).replace('\\', '/')[2:]
        return subprocess.call(['wsl.exe','-d','A51-KernelBuilder','--exec','python3','-B',script])
    snapshot = PROJECT / SNAPSHOT
    require(pin(snapshot / 'MANIFEST.json')['sha256'] == MANIFEST_SHA, 'Frozen manifest drift')
    manifest = json.loads((snapshot / 'MANIFEST.json').read_text())
    first = PROJECT / FIRST
    verify_index(first)
    first_result = json.loads((first / 'result.json').read_text())
    require(first_result['native_claims_reproduced'] and
            first_result['total_cases'] == 230 and first_result['total_checks'] == 337647,
            'First review model evidence unavailable')
    packet = new_packet('antigravity-first-review-supplement', __file__)
    build = Path('/opt/a51-hakios/parallel/main/first-handoff-supplement') / packet.name
    build.mkdir(parents=True, exist_ok=False)
    result = {'schema_version':1, 'packet':packet.relative_to(PROJECT).as_posix(),
              'build':str(build), 'snapshot':SNAPSHOT, 'manifest':pin(snapshot/'MANIFEST.json'),
              'reused_native_review':{'path':FIRST,'result':pin(first/'result.json'),
                                      'cases':230,'checks':337647},
              'review_commands_complete':False, 'accepted_for_main':False,
              'phase_4_gate_passed':False, 'device_operations':False,
              'references':{}, 'cpp':{}, 'observations':{}}
    records = []
    try:
        for rel, expected in manifest['antigravity_files'].items():
            require(pin(snapshot/'antigravity'/rel) == expected, 'Frozen source drift: '+rel)
            if rel.startswith('work/') and '__pycache__' not in rel:
                capture(snapshot/'antigravity'/rel, build/'candidate'/rel[5:], expected)
        for rel, expected in manifest['base_files'].items():
            require(pin(PROJECT/rel) == expected, 'Main source drift: '+rel)
        capture(snapshot/'MANIFEST.json', packet/'snapshot-manifest.json')
        capture(first/'result.json', packet/'reused-first-result.json')
        for name in ['ExynosDECON','ExynosKeyDriver','MelfasTouchDriver']:
            capture(first/(name+'-cpp-compile.stderr'), packet/'prior-diagnostics'/(name+'.stderr'))
        for group,(root,paths) in REFERENCES.items():
            result['references'][group]={'root':str(root),'git_head_verified':False,'files':{}}
            for rel in paths:
                require((root/rel).is_file(), 'Reference path unavailable: '+str(root/rel))
                result['references'][group]['files'][rel]=capture(root/rel,packet/'references'/group/rel)
        candidate=build/'candidate'
        includes=candidate/'drivers'
        outputs=build/'outputs'
        outputs.mkdir()
        command(packet,records,'clang-cpp-version',['clang++-18','--version'])
        for strict in [False,True]:
            label='stated' if not strict else 'freestanding'
            result['cpp'][label]={}
            for rel in ['drivers/display/ExynosDECON.cpp','drivers/display/ExynosDSIM.cpp',
                        'drivers/input/ExynosKeyDriver.cpp','drivers/input/MelfasTouchDriver.cpp']:
                name=Path(rel).stem
                output=outputs/(name+'-'+label+'.o')
                argv=['clang++-18','-std=c++17','-Wall','-Wextra','-Werror','-I',str(includes)]
                if strict:
                    argv += ['-ffreestanding','-fno-exceptions','-fno-rtti']
                argv += ['-c',str(candidate/rel),'-o',str(output)]
                proc=command(packet,records,name+'-'+label,argv,timeout=60,check=False)
                entry={'exit_code':proc.returncode,'compiled':proc.returncode == 0}
                if proc.returncode == 0:
                    entry['object']=capture(output,packet/'objects'/output.name)
                result['cpp'][label][rel]=entry
        for name,content in [('display-review-probe.c',C_PROBE),('cpp-display-review-probe.cpp',CPP_PROBE)]:
            (packet/name).write_text(content,encoding='utf-8')
            capture(packet/name,build/name)
        inc=candidate/'prototype/phase4-platform'
        cbin=outputs/'display-review-probe'
        cpbin=outputs/'cpp-display-review-probe'
        common=['-O1','-g','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
        command(packet,records,'c-probe-compile',['clang-18','-std=c11',*common,'-I',str(inc),
                str(build/'display-review-probe.c'),'-o',str(cbin)],timeout=60)
        command(packet,records,'cpp-probe-compile',['clang++-18','-std=c++17',*common,
                '-I',str(candidate/'drivers/display'),str(build/'cpp-display-review-probe.cpp'),
                str(candidate/'drivers/display/ExynosDSIM.cpp'),'-o',str(cpbin)],timeout=60)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        for label,binary in [('c',cbin),('cpp',cpbin)]:
            proc=command(packet,records,label+'-probe-execute',[str(binary)],timeout=30,env=env)
            result['observations'][label]=json.loads(proc.stdout)
            capture(binary,packet/'binaries'/binary.name)
        for name,patterns,paths in [
            ('touch-protocol',['MIP_R0_EVENT','MIP_R1_EVENT','packet_size','event_format == 10','event_format','event_size'],
             ['drivers/input/touchscreen/melfas/mss100/melfas_mss100_reg.h',
              'drivers/input/touchscreen/melfas/mss100/melfas_mss100.c',
              'drivers/input/touchscreen/melfas/mss100/melfas_mss100_mod.c']),
            ('a51-dts',['melfas','event_info','max_x','max_y','gpa1','touch','decon','dsim','dpp'],
             ['arch/arm64/boot/dts/samsung/exynos9611-a51_common.dtsi',
              'arch/arm64/boot/dts/samsung/exynos9611-a51_eur_open_gpio_00.dtsi',
              'arch/arm64/boot/dts/exynos/exynos9610.dts']),
            ('panel-brightness',['0x51','SEQ_BRIGHTNESS','brightness_table','0x03','msleep'],
             ['drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_lcd_ctrl.c',
              'drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_param.h',
              'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_lcd_ctrl.c',
              'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_param.h']),
            ('dpp-map',['IDMA_IN_BASE_ADDR_Y','IDMA_IN_CON','IDMA_IN_CTRL','SYSMMU'],
             ['drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dpp.h',
              'drivers/video/fbdev/exynos/dpu20/cal_9610/dpp_reg.c']),
        ]:
            argv=['rg','-n','-C','4']
            for pattern in patterns:
                argv += ['-e',pattern]
            argv += [str(packet/'references/android'/p) for p in paths]
            command(packet,records,name,argv)
        command(packet,records,'xnu-map-interface',['rg','-n','-C','4','-e','VM_WIMG_WCOMB',
                '-e','ml_io_map_unmappable','-e','ml_io_unmap',
                str(packet/'references/xnu/osfmk/arm/memory_types.h'),
                str(packet/'references/xnu/osfmk/arm/machine_routines.h'),
                str(packet/'references/xnu/osfmk/arm64/machine_routines.c'),
                str(packet/'references/xnu/osfmk/arm/io_map.c')])
        for rel,expected in manifest['base_files'].items():
            require(pin(PROJECT/rel) == expected,'Main changed during review: '+rel)
        for rel,expected in manifest['antigravity_files'].items():
            require(pin(snapshot/'antigravity'/rel) == expected,'Snapshot changed during review: '+rel)
        for group,(root,paths) in REFERENCES.items():
            for rel in paths:
                require(pin(root/rel) == result['references'][group]['files'][rel],
                        'Reference changed during review: '+rel)
        result['all_cpp_compiled']=all(e['compiled'] for suite in result['cpp'].values() for e in suite.values())
        result['review_commands_complete']=True
    except Exception as exc:
        result['error']=str(exc)
    write_json(packet/'result.json',result)
    index_packet(packet)
    print(json.dumps(result,indent=2),flush=True)
    return 0 if result['review_commands_complete'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
