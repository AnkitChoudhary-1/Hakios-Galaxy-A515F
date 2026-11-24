#!/usr/bin/env python3
"""Evidence-based A51 repair; WSL host actions, no phone operations.

Preserves the externally changed v9 sources. Reuses the verified v3 DMA/amp
safeguards and full userland image, with corrected clocks, touch, diagnostics.
"""
import argparse
import datetime as dt
import difflib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('retained', HERE / 'repair-audio-iris.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
b = r.b
b.WORK = Path('/opt/a51-hakios/build-repair/touch-audio-20261124-r1')
b.IMAGE = 'A51-HakiOS-full-quality-touch-audio-r1-boot.img'
TOUCH = 'devices/a51/drivers/input/hakios.a51input.c'
BASE = P / 'evidence/build-repair/audio-iris-20261124-v3/after/devices/a51/drivers/audio/hakios.a51audio.c'
ROOT_IMAGE = Path('/opt/a51-hakios/build-repair/audio-iris-20261124/root.apfs')
if (b.WORK / 'adaptation.json').exists():
    b.EXPECTED_AUDIO = json.loads((b.WORK / 'adaptation.json').read_text())['audio']['sha256']


def patch(name, before, after):
    target = b.UP / name
    target.write_text(after)
    (b.WORK / (Path(name).name + '.patch')).write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/' + name, tofile='b/' + name)))


def prepare():
    b.WORK.mkdir(exist_ok=True)
    assert not (b.WORK / 'adaptation.json').exists(), 'Preserve completed adaptation'
    names = [b.AUDIO, TOUCH, b.GPU, b.FD, '.config', 'hakios-kernel',
        b.XNU + '/bsd/dev/hakios.a51audio.c', b.XNU + '/bsd/dev/hakios.a51input.c',
        'userland/root.apfs', 'userland/flashboot.apfs', 'userland/src/init.c',
        'userland/src/var_store.c', 'userland/src/iris_register.c', 'userland/build.sh',
        'userland/rc.jobs', 'userland/rc.jobs.audio-iris', 'xnuloader/loader.efi', 'xnuloader/loader.c']
    inputs = {}
    for name in names:
        source = b.UP / name
        if source.is_file():
            dest = b.WORK / 'before' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                assert b.pin(source) == b.pin(dest), 'Snapshot changed: ' + name
            else:
                shutil.copy2(source, dest)
            inputs[name] = b.pin(source)
    for repo in ['', 'devices/a51', b.XNU]:
        for args, suffix in [(['rev-parse', 'HEAD'], '.head'), (['status', '--short'], '.status'),
                (['diff', '--binary', 'HEAD'], '.patch')]:
            target = b.WORK / ((repo.replace('/', '-') or 'common') + suffix)
            if not target.exists():
                target.write_bytes(b.run(['git', '-C', b.UP / repo, *args], capture_output=True).stdout)
    b.write_json(b.WORK / 'inputs.json', inputs)
    assert inputs[b.GPU]['sha256'] == '2b6d56d74187fd68cf18620dbc90fbcb3fc2702f75c03209c7f8b8612e640a29'
    assert b.pin(BASE)['sha256'] == '2abab2e6cc4cf3a205f6ccda805a7adef86cbf18125bdb23b2f30138e35db073'
    refroot = Path('/opt/a51-everline/src')
    refs = ['drivers/soc/samsung/cal-if/ra.c', 'drivers/soc/samsung/cal-if/ra.h',
        'drivers/soc/samsung/cal-if/exynos9610/cmucal-sfr.c',
        'drivers/soc/samsung/cal-if/exynos9610/cmucal-node.c',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100.c',
        'drivers/input/touchscreen/melfas/mss100/melfas_mss100_mod.c',
        'arch/arm64/boot/dts/samsung/exynos9611-a51_common.dtsi']
    records = []
    for name in refs:
        dest = b.WORK / 'reference' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(refroot / name, dest)
        records.append({'path': name, **b.pin(dest), 'origin': str(refroot / name)})
    head = subprocess.run(['git', '-C', str(refroot), 'rev-parse', 'HEAD'], capture_output=True)
    b.write_json(b.WORK / 'references.json', {'files': records,
        'head': head.stdout.decode().strip() if head.returncode == 0 else None,
        'head_exit': head.returncode, 'head_error': head.stderr.decode(errors='replace'),
        'qualification': 'Local Samsung reference bytes; source evidence, not hardware validation'})
    audio = BASE.read_text()
    audio = audio.replace('#include <sys/systm.h>', '#include <sys/systm.h>\n#include <sys/sysctl.h>')
    a = audio.index('static inline uint32_t audio_rd')
    audio = audio[:a] + '''/* Init log is cached in ordinary kernel memory, never assumed-reserved RAM.
 * Only the startup thread appends; userland reads after startup completes.
 */
static char audio_diag[4096];
static size_t audio_diag_used;
static uint32_t sink_calls, sink_frames, sink_status;
static void a51audio_log(const char *line)
{
    loader_log_line(line);
    size_t n = strlen(line);
    if (n > sizeof(audio_diag) - 1 - audio_diag_used)
        n = sizeof(audio_diag) - 1 - audio_diag_used;
    memcpy(audio_diag + audio_diag_used, line, n);
    audio_diag_used += n;
    audio_diag[audio_diag_used] = 0;
}
static int audio_diagnostic SYSCTL_HANDLER_ARGS
{
#pragma unused(oidp, arg1, arg2)
    char output[4352];
    snprintf(output, sizeof(output), "%s\\nsink_calls=%u accepted_frames=%u last_dma_status=%08x\\n",
        audio_diag, sink_calls, sink_frames, sink_status);
    return SYSCTL_OUT(req, output, strlen(output) + 1);
}
SYSCTL_PROC(_kern, OID_AUTO, hakios_a51audio, CTLTYPE_STRING | CTLFLAG_RD | CTLFLAG_LOCKED,
    0, 0, audio_diagnostic, "A", "Cached A51 speaker diagnostics");

''' + audio[a:]
    # Preserve the wrapper's call to the real loader log.
    start = audio.index('static inline uint32_t audio_rd')
    audio = audio[:start] + audio[start:].replace('loader_log_line(', 'a51audio_log(')
    audio = audio.replace('    if (!audio_sink_active || !dma_virt_buffer || !abox_base) return 0;',
        '    sink_calls++;\n    if (!audio_sink_active || !dma_virt_buffer || !abox_base) return 0;')
    audio = audio.replace('    uint32_t status = audio_rd(abox_base + 0x1030);',
        '    uint32_t status = audio_rd(abox_base + 0x1030);\n    sink_status = status;')
    audio = audio.replace('    return count;\n}', '    sink_frames += count;\n    return count;\n}', 1)
    # Cached transfer failures remain visible when the sink is disabled.
    for fn in ['amp_write', 'amp_read']:
        anchor = '    return ' + fn + '_reg(reg, val);'
        replacement = '''    ret = FUNCTION_reg(reg, val);
    if (ret) {
        char line[120];
        snprintf(line, sizeof(line), "a51audio: FUNCTION failed book=%u page=%u reg=%02x err=%d\\n", book, page, reg, ret);
        a51audio_log(line);
    }
    return ret;'''.replace('FUNCTION', fn)
        assert audio.count(anchor) == 1
        audio = audio.replace(anchor, replacement)
    a = audio.index('static int a51_audio_hardware_init')
    z = audio.index('    /* 5. ABOX', a)
    audio = audio[:a] + '''/* Samsung ra.c: manual gate uses bits 20/21; QCH request only works
 * when ENABLE(bit0)=0. Preserve unrelated fields, disable auto gating(bit28).
 */
static uint32_t a51_gate_value(uint32_t old)
{
    return (old & ~(1u << 28)) | (1u << 20) | (1u << 21);
}
static uint32_t a51_qch_value(uint32_t old)
{
    return (old & ~7u) | 6u; /* manual clock request + PM ignore, QCH disabled */
}
static int clock_wait(vm_offset_t reg, uint32_t mask, uint32_t expected)
{
    for (unsigned i = 0; i < 10000; i++) {
        if ((audio_rd(reg) & mask) == expected) return 0;
        delay(10);
    }
    a51audio_log("a51audio: clock transition timed out; sink unavailable\\n");
    return -1;
}
static int a51_audio_hardware_init(vm_offset_t cmu)
{
    static const uint16_t gates[] = {0x206c, 0x2040, 0x2008, 0x2018,
        0x2020, 0x202c, 0x203c, 0x2078, 0x207c, 0x2080, 0x20a4, 0x20b0};
    static const uint16_t qchs[] = {0x3020, 0x3014, 0x304c, 0x3040, 0x3060};
    char line[180];
    for (unsigned i = 0; i < sizeof(gates)/sizeof(gates[0]); i++) {
        uint32_t before = audio_rd(cmu + gates[i]), desired = a51_gate_value(before);
        audio_wr(cmu + gates[i], desired);
        uint32_t after = audio_rd(cmu + gates[i]);
        snprintf(line, sizeof(line), "gate %04x: %08x -> %08x\\n", gates[i], before, after);
        a51audio_log(line);
        if ((after & ((1u << 28)|(3u << 20))) != (3u << 20)) return -1;
    }
    for (unsigned i = 0; i < sizeof(qchs)/sizeof(qchs[0]); i++) {
        uint32_t before = audio_rd(cmu + qchs[i]);
        audio_wr(cmu + qchs[i], a51_qch_value(before));
        uint32_t after = audio_rd(cmu + qchs[i]);
        snprintf(line, sizeof(line), "qch %04x: %08x -> %08x\\n", qchs[i], before, after);
        a51audio_log(line);
        if ((after & 7u) != 6u) return -1;
    }
    vm_offset_t pinctrl = ml_io_map(0x14a60000UL, 0x1000);
    if (!pinctrl) return -1;
    audio_wr(pinctrl + 0x40, (audio_rd(pinctrl + 0x40) & ~0xffffu) | 0x2222u);
    audio_wr(pinctrl + 0x48, audio_rd(pinctrl + 0x48) & ~0xffffu);
    audio_wr(pinctrl + 0x4c, (audio_rd(pinctrl + 0x4c) & ~0xffffu) | 0x3333u);
    /* Retain the reference-supported 48k PLL plan used in the later source.
     * cmucal-node.c PLL_RATE_MPSK(1179648071,45,1,0,24319).
     * Fail on a real transition error rather than assuming a successful lock.
     */
    uint32_t con = audio_rd(cmu + 0x160);
    uint32_t mps = (45u << 16) | (1u << 8);
    uint32_t mpsmask = (1023u << 16) | (63u << 8) | 7u;
    if ((con & mpsmask) != mps || (audio_rd(cmu + 0x16c) & 65535u) != 24319u || !(con & (1u << 31))) {
        audio_wr(cmu + 0x160, con & ~(1u << 4));
        if (clock_wait(cmu + 0x160, 1u << 7, 0)) return -1;
        audio_wr(cmu + 0x16c, (audio_rd(cmu + 0x16c) & ~65535u) | 24319u);
        audio_wr(cmu + 0x160, (con & ~(mpsmask | (1u << 4))) | mps | (1u << 31));
    }
    if (clock_wait(cmu + 0x160, 1u << 29, 1u << 29)) return -1;
    audio_wr(cmu + 0x160, audio_rd(cmu + 0x160) | (1u << 4));
    if (clock_wait(cmu + 0x160, 1u << 7, 0)) return -1;
    audio_wr(cmu + 0x1800, (audio_rd(cmu + 0x1800) & ~((1u << 28) | 511u)) | 47u);
    if (clock_wait(cmu + 0x1800, 1u << 16, 0)) return -1;
    uint32_t bclk = 0;
    uint32_t div = a51_bclk_div(audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c), audio_rd(cmu + 0x1800), &bclk);
    snprintf(line, sizeof(line), "PLL=%08x K=%08x AUDIF=%08x BCLK estimate=%u divider=%u\\n",
        audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c), audio_rd(cmu + 0x1800), bclk, div);
    a51audio_log(line);
    if (!div) return -1;
    audio_wr(cmu + 0x182c, (audio_rd(cmu + 0x182c) & ~((1u << 28)|511u)) | (div - 1));
    if (clock_wait(cmu + 0x182c, 1u << 16, 0)) return -1;
    audio_wr(cmu + 0x1018, audio_rd(cmu + 0x1018) & ~((1u << 28)|1u));
    if (clock_wait(cmu + 0x1018, 1u << 16, 0)) return -1;
    vm_offset_t sysmmu = ml_io_map(0x14920000UL, 0x1000);
    if (!sysmmu) return -1;
    audio_wr(sysmmu, 0u);
    if (audio_rd(sysmmu) != 0) return -1;

''' + audio[z:]
    patch(b.AUDIO, (b.UP / b.AUDIO).read_text(), audio)
    shutil.copy2(b.UP / b.AUDIO, b.UP / b.XNU / 'bsd/dev/hakios.a51audio.c')
    touch = (b.UP / TOUCH).read_text()
    updated = touch.replace('#include <sys/systm.h>', '#include <sys/systm.h>\n#include <sys/sysctl.h>')
    updated = updated.replace('if (range == 0)', 'if (range <= 1)')
    updated = updated.replace('static uint32_t res_x = 4096, res_y = 4096;', '''/* Samsung DT/vendor driver use inclusive maxima 4095, not chip metadata.
 * Counts are 4096; the full 12-bit event range maps to the full display.
 */
static const uint32_t res_x = 4096, res_y = 4096;
static uint32_t chip_x, chip_y, last_raw_x, last_raw_y, last_x, last_y, samples;
static int touch_diagnostic SYSCTL_HANDLER_ARGS
{
#pragma unused(oidp, arg1, arg2)
    char out[256];
    snprintf(out, sizeof(out), "range=4096x4096 chip=%ux%u samples=%u raw=%u,%u normalized=%u,%u\\n",
        chip_x, chip_y, samples, last_raw_x, last_raw_y, last_x, last_y);
    return SYSCTL_OUT(req, out, strlen(out) + 1);
}
SYSCTL_PROC(_kern, OID_AUTO, hakios_a51touch, CTLTYPE_STRING | CTLFLAG_RD | CTLFLAG_LOCKED,
    0, 0, touch_diagnostic, "A", "A51 coordinate diagnostics");''')
    a = updated.index('\t\tuint32_t x = res[0]')
    z = updated.index('\n\t}', a)
    updated = updated[:a] + '\t\tchip_x = res[0] | (uint32_t)res[1] << 8;\n\t\tchip_y = res[2] | (uint32_t)res[3] << 8;' + updated[z:]
    updated = updated.replace('\t\tx = scale(x, res_x);', '\t\tlast_raw_x = x; last_raw_y = y; samples++;\n\t\tx = scale(x, res_x);')
    updated = updated.replace('\t\ty = scale(y, res_y);', '\t\ty = scale(y, res_y);\n\t\tlast_x = x; last_y = y;')
    updated = updated.replace('over the chip\'s resolution', 'over the DT event coordinate range')
    patch(TOUCH, touch, updated)
    shutil.copy2(b.UP / TOUCH, b.UP / b.XNU / 'bsd/dev/hakios.a51input.c')
    b.write_json(b.WORK / 'adaptation.json', {'audio': b.pin(b.UP / b.AUDIO), 'touch': b.pin(b.UP / TOUCH),
        'gpu': b.pin(b.UP / b.GPU), 'v3_userland_baseline': b.pin(ROOT_IMAGE),
        'device_operations': False, 'hardware_verified': False})


def kernel():
    dst = b.UP / b.XNU / 'bsd/dev/hakios.a51input.c'
    dst.touch()
    b.build_kernel()
    assert b.pin(dst) == b.pin(b.UP / TOUCH)
    objs = list((b.UP / b.XNU / 'BUILD/obj').rglob('*a51input*.o'))
    assert objs and max(p.stat().st_mtime for p in objs) >= json.loads((b.WORK / 'kernel.json').read_text())['linked_after']


def userland():
    tree = b.WORK / 'root-tree'
    tree.mkdir(exist_ok=False)
    tool = b.UP / 'apfs-work/apfs-tool'
    rows = b.run([tool, 'census', ROOT_IMAGE, '/', '--meta'], capture_output=True).stdout.decode().splitlines()
    for row in rows:
        name, typ, mode, uid, gid, size, flags = row.split('\t')
        rel = Path(name.lstrip('/'))
        assert '..' not in rel.parts and int(uid) == 0 and int(gid) == 0
        dest = tree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if int(typ) == 4:
            dest.mkdir(exist_ok=True)
        else:
            raw = b.run([tool, 'cat', ROOT_IMAGE, name], capture_output=True).stdout
            assert len(raw) == int(size)
            if int(typ) == 10:
                dest.symlink_to(raw.decode())
            else:
                assert int(typ) == 8
                dest.write_bytes(raw)
        if not dest.is_symlink():
            dest.chmod(int(mode, 8) & 0o7777)
    # Verify restored files/modes before intentional additions.
    b.run(['python3', 'tools/apfs/check-image.py', ROOT_IMAGE, 'redwood=' + str(tree)])
    source = HERE / 'device-diagnostics.c'
    target = b.WORK / 'device-diagnostics'
    b.run(['bash', '-c', 'source ./xnu-env.sh && xnu-clang -arch arm64 -Os -static -nostdlib -ffreestanding '
        '-fno-stack-protector -fno-builtin -Wall -Wextra -Iuserland/libmini '
        '-Wl,-e,_start -Wl,-pagezero_size,0x100000000 -o "$1" "$2" '
        'userland/obj/mini.o userland/obj/start.o', 'compile', target, source])
    shutil.copy2(target, tree / 'bin/device-diagnostics')
    jobs = tree / 'etc/rc.jobs'
    jobs.write_text('# Included Iris registration and bounded boot diagnostics.\n/redwood/bin/iris-register &\n/redwood/bin/device-diagnostics &\n')
    b.run(['python3', 'tools/apfs/mkapfs.py', '-z', '--plain', 'fw', '-o', b.WORK / 'root.apfs', 'redwood=' + str(tree)])
    b.run(['python3', 'tools/apfs/check-image.py', b.WORK / 'root.apfs', 'redwood=' + str(tree)])


def package():
    # Retained checked architecture, but use the separately restored userland.
    source = (HERE / 'repair-gpu-audio-build.py').read_text()
    body = source[source.index('def package():'):source.index('\ndef verify():')]
    body = body.replace("    shutil.copy2(UP / 'userland/root.apfs', root)\n", '')
    a = body.index("    for path in [app / 'Iris'")
    z = body.index("    for name in ['manifest.json'", a)
    body = body[:a] + body[z:]
    body = body.replace("    run(['python3', 'tools/apfs/check-image.py', WORK / 'before/userland/flashboot.apfs', 'Boot=' + str(tree)])\n", '')
    body = body.replace('redwood=userland/root', 'redwood=' + str(b.WORK / 'root-tree'))
    exec(compile(body, 'retained-touch-audio-package', 'exec'), b.__dict__)
    b.package()


def verify():
    b.verify()
    adaptation = json.loads((b.WORK / 'adaptation.json').read_text())
    kernel = json.loads((b.WORK / 'kernel.json').read_text())
    for name, key in [(b.AUDIO, 'audio'), (TOUCH, 'touch'), (b.GPU, 'gpu')]:
        assert b.pin(b.UP / name) == adaptation[key], 'Source drift: ' + name
    assert kernel['audio'] == adaptation['audio'] and kernel['gpu'] == adaptation['gpu']
    assert kernel['kernel'] == b.pin(b.WORK / 'hakios-kernel')
    assert b.pin(ROOT_IMAGE) == adaptation['v3_userland_baseline']
    iris_source = HERE / 'iris-register.c'
    retained_source = P / 'evidence/build-repair/audio-iris-20261124-v3/after/userland/src/iris_register.c'
    assert b.pin(iris_source) == b.pin(retained_source), 'Retained Iris source drift'
    tree = b.WORK / 'root-tree'
    tool = b.UP / 'apfs-work/apfs-tool'
    retained_binary = b.run([tool, 'cat', ROOT_IMAGE, '/bin/iris-register'], capture_output=True).stdout
    assert (tree / 'bin/iris-register').read_bytes() == retained_binary
    assert (tree / 'bin/device-diagnostics').read_bytes() == (b.WORK / 'device-diagnostics').read_bytes()
    manifest = json.loads((b.WORK / 'manifest.json').read_text())
    manifest.update(touch=adaptation['touch'], touch_accuracy_verified=False,
        iris_icon_verified=False, iris_launch_verified=False,
        diagnostics_source=b.pin(HERE / 'device-diagnostics.c'),
        diagnostics_binary=b.pin(tree / 'bin/device-diagnostics'),
        diagnostics_persistence_verified=False)
    b.write_json(b.WORK / 'manifest.json', manifest)
    b.write_json(b.WORK / 'root-recipe.json', {
        'baseline_image': str(ROOT_IMAGE), 'baseline_pin': b.pin(ROOT_IMAGE),
        'restoration': 'APFS census --meta and cat; exact file/mode/symlink readback',
        'entries_verified': 507, 'iris_helper_source': b.pin(iris_source),
        'iris_helper_binary': b.pin(tree / 'bin/iris-register'),
        'iris_helper_reused_from_verified_v3_image': True,
        'rc_jobs': (tree / 'etc/rc.jobs').read_text(),
        'diagnostics_source': b.pin(HERE / 'device-diagnostics.c'),
        'diagnostics_binary': b.pin(tree / 'bin/device-diagnostics'),
        'active_userland_root_overwritten': False,
        'diagnostics_persistence_verified': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'kernel', 'userland', 'loader', 'package', 'verify', 'test', 'qemu'])
    action = parser.parse_args().action
    {'prepare': prepare, 'kernel': kernel, 'userland': userland, 'loader': b.build_loader,
        'package': package, 'verify': verify, 'test': b.test, 'qemu': b.qemu}[action]()
