#!/usr/bin/env python3
"""Targeted WSL v3 repair; snapshots v2 first and never contacts a device."""
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('retained', HERE / 'repair-gpu-audio-build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.WORK = Path('/opt/a51-hakios/build-repair/audio-iris-20261124')
b.IMAGE = 'A51-HakiOS-full-quality-audio-iris-v3-boot.img'
if (b.WORK / 'adaptation.json').is_file():
    b.EXPECTED_AUDIO = json.loads((b.WORK / 'adaptation.json').read_text())['audio']['sha256']


def replace_once(text, old, new):
    assert text.count(old) == 1, 'Expected one source anchor: ' + old[:100]
    return text.replace(old, new)


def prepare():
    before = b.WORK / 'before'
    before.mkdir(exist_ok=False)
    names = [b.GPU, b.AUDIO, b.FD, '.config', 'hakios-kernel',
             'userland/root.apfs', 'userland/flashboot.apfs', 'userland/root/etc/rc.jobs',
             'userland/rc.jobs', 'userland/src/init.c', 'userland/obj/init',
             'userland/root/sbin/init', 'userland/root/sbin/launchd', 'xnuloader/loader.efi']
    inputs = {}
    for name in names:
        p = b.UP / name
        target = before / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        inputs[name] = b.pin(p)
    assert inputs[b.GPU]['sha256'] == '2b6d56d74187fd68cf18620dbc90fbcb3fc2702f75c03209c7f8b8612e640a29'
    assert inputs[b.AUDIO]['sha256'] == 'bab89d13130474c6d8155a33aefdf772969920e50976d383fed7ec172dd48e4f'
    b.write_json(b.WORK / 'inputs.json', inputs)
    p = b.UP / b.AUDIO
    old = p.read_text()
    s = replace_once(old, ' * Complete implementation: un-reset, I2C register config, clock ungating,\n * I2S2 pinmux, ABOX routing, SysMMU bypass, DMA ring buffer, and CoreAudio sink.',
        ' * Experimental speaker output. Host checks do not establish audible playback.\n * Wired headphones, capture and route switching are not implemented here.')
    s = replace_once(s, '        ret = amp_write_reg(127, book); /* Book register is 127 */',
        '        /* Book select is only accessible on page zero. */\n        ret = amp_write_reg(0, 0);\n        if (ret != 0) { current_page = -1; return ret; }\n        current_page = 0;\n        ret = amp_write_reg(127, book); /* Book register is 127 */')
    start = s.index('/* CoreAudio playback sink:')
    end = s.index('/* =========================================================================', start)
    s = s[:start] + '''/* BUF_OFFSET is the DMA period size, not a software producer pointer.
 * Read STATUS to keep writes ahead of the hardware consumer. Generic audio
 * serializes this sink. RDMA0 alone feeds SPUS OUT0 -> SIFS1 -> UAIF2.
 */
#define A51_DMA_PERIOD 4096u
static bool dma_writer_started;
static uint32_t dma_last_read;
static uint32_t a51_audio_sink(const int16_t *frames, uint32_t count)
{
    if (!audio_sink_active || !dma_virt_buffer || !abox_base) return 0;
    if (!count) return 0;
    uint32_t status = audio_rd(abox_base + 0x1030);
    if (!(status & (1u << 31))) return 0;
    uint32_t read_frame = (((status >> 16) & 0x1fffu) << 4) / HAKIOS_AUDIO_FRAME;
    if (read_frame >= A51_DMA_FRAMES) return 0;
    volatile uint32_t *words = (volatile uint32_t *)dma_virt_buffer;
    /* Clear consumed samples so idle playback does not loop old sound. */
    if (dma_writer_started) {
        for (uint32_t f = dma_last_read; f != read_frame; f = (f + 1) % A51_DMA_FRAMES)
            words[f] = 0;
    }
    dma_last_read = read_frame;
    uint32_t cur = dma_write_frame_offset;
    uint32_t ahead = (cur + A51_DMA_FRAMES - read_frame) % A51_DMA_FRAMES;
    uint32_t period_frames = A51_DMA_PERIOD / HAKIOS_AUDIO_FRAME;
    if (!dma_writer_started || ahead < period_frames) {
        cur = (read_frame + 2 * period_frames) % A51_DMA_FRAMES;
        ahead = 2 * period_frames;
        dma_writer_started = true;
    }
    uint32_t free_frames = ahead >= A51_DMA_FRAMES - period_frames ? 0 : A51_DMA_FRAMES - ahead - period_frames;
    if (count > free_frames) count = free_frames;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t sample = ((uint32_t)(uint16_t)frames[2*i + 1] << 16) | (uint16_t)frames[2*i];
        words[(cur + i) % A51_DMA_FRAMES] = sample;
    }
    __asm__ volatile("dsb sy" ::: "memory");
    dma_write_frame_offset = (cur + count) % A51_DMA_FRAMES;
    return count;
}

/* Retained PLL_AUD: 26 MHz reference, signed fractional K, AUDIF parent.
 * Do not assume a 73.728 MHz parent or silently claim a measured BCLK.
 */
static uint32_t a51_bclk_div(uint32_t con0, uint32_t con3, uint32_t audif,
    uint32_t *actual)
{
    uint32_t p = (con0 >> 8) & 63, m = (con0 >> 16) & 1023, shift = con0 & 7;
    if (!p || !m || (con0 & 0xa0000000u) != 0xa0000000u) return 0;
    int64_t fixed = (int64_t)m * 65536 + (int16_t)(con3 & 65535);
    if (fixed <= 0) return 0;
    uint64_t parent = (26000000ULL * (uint64_t)fixed) /
        ((uint64_t)p * 65536 * (1u << shift) * ((audif & 511) + 1));
    uint32_t div = (uint32_t)((parent + 768000) / 1536000);
    if (!div || div > 512) return 0;
    *actual = (uint32_t)(parent / div);
    uint32_t error = *actual > 1536000 ? *actual - 1536000 : 1536000 - *actual;
    return error <= 15360 ? div : 0; /* within one percent of 48k/32fs */
}

''' + s[end:]
    s = replace_once(s, 'static void a51_audio_hardware_init(vm_offset_t cmu)', 'static int a51_audio_hardware_init(vm_offset_t cmu)')
    s = replace_once(s, '    /* 3. Clocks: CMU_DISPAUD ungate & dividers */',
        '    if (!pinctrl) return -1;\n\n    /* 3. Clocks: CMU_DISPAUD ungate & dividers */')
    a = s.index('    /* Set UAIF2 clock divider:')
    z = s.index('    /* 5. ABOX', a)
    s = s[:a] + '''    uint32_t bclk = 0;
    uint32_t div = a51_bclk_div(audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c),
        audio_rd(cmu + 0x1800), &bclk);
    char clock_log[160];
    snprintf(clock_log, sizeof(clock_log), "a51audio: retained PLL=%08x K=%08x AUDIF=%08x BCLK estimate=%u divider=%u\\n",
        audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c), audio_rd(cmu + 0x1800), bclk, div);
    loader_log_line(clock_log);
    if (!div) return -1;
    audio_wr(cmu + 0x182c, (audio_rd(cmu + 0x182c) & ~511u) | (div - 1));
    audio_wr(cmu + 0x1018, audio_rd(cmu + 0x1018) & ~1u); /* internal UAIF2 parent */
    /* This driver uses reserved physical DRAM, not DSP IOVA mappings. */
    vm_offset_t sysmmu = ml_io_map(0x14920000UL, 0x1000);
    if (!sysmmu) return -1;
    uint32_t mmu_before = audio_rd(sysmmu);
    audio_wr(sysmmu, 0u); /* Samsung CTRL_DISABLE: translation bypass */
    if (audio_rd(sysmmu) != 0) return -1;
    snprintf(clock_log, sizeof(clock_log), "a51audio: ABOX SysMMU CTRL %08x -> %08x\\n", mmu_before, audio_rd(sysmmu));
    loader_log_line(clock_log);

''' + s[z:]
    a = s.index('        /* 6. Map DMA Buffer')
    z = s.index('        /* Now that RDMA', a)
    s = s[:a] + '''        /* Stop before changing DMA geometry; no continuous boot tone. */
        audio_wr(abox_base + 0x1000, 0u);
        audio_wr(abox_base + 0x1700, 0u);
        dma_virt_buffer = (int16_t *)ml_io_map(A51_DMA_BASE_PA, A51_DMA_BUFFER_SIZE);
        if (!dma_virt_buffer) return -1;
        volatile uint32_t *words = (volatile uint32_t *)dma_virt_buffer;
        for (uint32_t f = 0; f < A51_DMA_FRAMES; f++) words[f] = 0;
        dma_write_frame_offset = 0;
        dma_writer_started = false;
        audio_wr(abox_base + 0x1008, (uint32_t)A51_DMA_BASE_PA);
        audio_wr(abox_base + 0x100c, (uint32_t)(A51_DMA_BASE_PA + A51_DMA_BUFFER_SIZE));
        audio_wr(abox_base + 0x1010, A51_DMA_PERIOD);
        audio_wr(abox_base + 0x1014, (uint32_t)A51_DMA_BASE_PA);
        audio_wr(abox_base + 0x1018, 0x007fffffu); /* half of the 24-bit maximum */
        audio_wr(abox_base + 0x101c, 1u);
        audio_wr(abox_base + 0x1000, 1u);
        loader_log_line("a51audio: RDMA0 physical ring enabled, 4096-byte period; RDMA7 stopped\\n");

''' + s[z:]
    a = s.index('        /* Clear any initial transient')
    z = s.index('        char log[160];', a)
    s = s[:a] + s[z:] # status is diagnostic, not assumed W1C
    s = replace_once(s, '    }\n}\n\n/* =========================================================================\n * TAS2562',
        '        return 0;\n    }\n    return -1;\n}\n\n/* =========================================================================\n * TAS2562')
    s = replace_once(s, 'amp_write(0, 0, 0x38, 0x0C); /* CLOCKCONFIGURATION: auto-detect rate, 64-fs ratio */',
        'amp_write(0, 0, 0x38, 0x08); /* CLOCKCONFIGURATION: 32fs, 16-bit stereo */')
    # Fail every configuration transfer rather than accepting stale readbacks.
    a = s.index('    /* 4. Software Reset:')
    z = s.index('/* =========================================================================\n * Driver Initialization', a)
    region = s[a:z]
    region = re.sub(r'(?m)^(\s*)(amp_(?:write|read)\([^;]+\));', r'\1if (\2 != 0) return -1;', region)
    s = s[:a] + region + s[z:]
    s = replace_once(s, '    return (pwr == 0x00) ? 0 : -1;', '    return (pwr == 0x00 && (irq & 0x04) == 0 && (liveirq & 0x04) == 0) ? 0 : -1;')
    s = replace_once(s, '    a51_audio_hardware_init(cmu);',
        '    if (a51_audio_hardware_init(cmu) != 0) {\n        loader_log_line("a51audio: hardware setup failed; sink unavailable\\n");\n        return;\n    }')
    s = replace_once(s, '    /* 5. Register with Darwin',
        '    if (amp_status != 0) {\n        (void)amp_write(0, 0, 0x02, 0x02); /* shutdown */\n        audio_wr(abox_base + 0x1000, 0u);\n        audio_wr(abox_base + 0x0520, audio_rd(abox_base + 0x0520) & ~1u);\n        loader_log_line("a51audio: amp configuration failed; sink unavailable\\n");\n        return;\n    }\n\n    /* 5. Register with Darwin')
    p.write_text(s)
    shutil.copy2(p, b.UP / b.XNU / 'bsd/dev/hakios.a51audio.c')
    (b.WORK / 'audio-v3.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True), s.splitlines(True), fromfile='a/'+b.AUDIO, tofile='b/'+b.AUDIO)))
    # Iris metadata is changed deliberately; preserve the executable.
    import plistlib
    app = Path('/opt/a51-hakios/apps/Payload/Iris.app')
    shutil.copytree(app, before / 'Iris.app')
    plist = plistlib.loads((app / 'Info.plist').read_bytes())
    plist.update(CFBundleSupportedPlatforms=['iPhoneOS'], MinimumOSVersion='16.5')
    (app / 'Info.plist').write_bytes(plistlib.dumps(plist))
    local = Path('/mnt/c/Users/Ankit/Desktop/A51/hakios-a51/apps/Iris/resources/Info.plist')
    shutil.copy2(local, before / 'Iris-source-Info.plist')
    local.write_bytes(plistlib.dumps(plist))
    src = b.UP / 'userland/src/iris_register.c'
    shutil.copy2(HERE / 'iris-register.c', src)
    jobs = b.UP / 'userland/root/etc/rc.jobs'
    jobs.write_text('# Register the included app after LaunchServices starts.\n/redwood/bin/iris-register &\n' + jobs.read_text())
    build = b.UP / 'userland/build.sh'
    shutil.copy2(build, before / 'userland/build.sh')
    text = build.read_text()
    text = replace_once(text, 'for prog in init child stage0 var_store; do', 'for prog in init child stage0 var_store iris_register; do')
    text = replace_once(text, 'cp obj/init root/sbin/init', 'cp obj/iris_register root/bin/iris-register\ncp obj/init root/sbin/init')
    build.write_text(text)
    # Make the safe job recipe selectable by future full builds as well.
    shutil.copy2(jobs, b.UP / 'userland/rc.jobs.audio-iris')
    b.write_json(b.WORK / 'adaptation.json', {'audio': b.pin(p), 'gpu': b.pin(b.UP / b.GPU),
        'iris_executable': b.pin(app / 'Iris'), 'iris_plist': b.pin(app / 'Info.plist'),
        'device_operations': False, 'audible_audio_verified': False})
    print('Prepared v3 snapshots and targeted audio/Iris changes')


def userland():
    shutil.copy2(HERE / 'iris-register.c', b.UP / 'userland/src/iris_register.c')
    target = b.UP / 'userland/obj/iris_register'
    b.run(['bash', '-c', 'source ./xnu-env.sh && xnu-clang -arch arm64 -Os -static -nostdlib -ffreestanding '
           '-fno-stack-protector -fno-builtin -Wall -Wextra -Iuserland/libmini '
           '-Wl,-e,_start -Wl,-pagezero_size,0x100000000 -o "$1" '
           'userland/src/iris_register.c userland/obj/mini.o userland/obj/start.o', 'compile', target])
    shutil.copy2(target, b.UP / 'userland/root/bin/iris-register')
    assert (b.UP / 'userland/root/bin/uicache').is_file()
    b.run(['python3', 'tools/apfs/mkapfs.py', '-z', '--plain', 'fw', '-o', b.WORK / 'root.apfs', 'redwood=userland/root'])
    b.run(['python3', 'tools/apfs/check-image.py', b.WORK / 'root.apfs', 'redwood=userland/root'])


def revise():
    p = b.UP / b.AUDIO
    before = p.read_text()
    after = replace_once(before, 'uint32_t free_frames = A51_DMA_FRAMES - ahead - period_frames;',
        'uint32_t free_frames = ahead >= A51_DMA_FRAMES - period_frames ? 0 : A51_DMA_FRAMES - ahead - period_frames;')
    after = replace_once(after, '0x00800000u); /* 0 dB reference in Samsung TLV */',
        '0x007fffffu); /* half of the 24-bit maximum */')
    p.write_text(after)
    shutil.copy2(p, b.UP / b.XNU / 'bsd/dev/hakios.a51audio.c')
    (b.WORK / 'audio-v3-capacity-correction.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/'+b.AUDIO, tofile='b/'+b.AUDIO)))
    data = json.loads((b.WORK / 'adaptation.json').read_text())
    data['audio'] = b.pin(p)
    b.write_json(b.WORK / 'adaptation.json', data)


def package():
    # Retained v2 architecture/verification with intentional md1 and plist changes.
    source = (HERE / 'repair-gpu-audio-build.py').read_text()
    body = source[source.index('def package():'):source.index('\ndef verify():')]
    body = body.replace("    shutil.copy2(UP / 'userland/root.apfs', root)\n", '')
    start = body.index("    for path in [app / 'Iris'")
    end = body.index("    for name in ['manifest.json'", start)
    body = body[:start] + body[end:]
    body = body.replace("    run(['python3', 'tools/apfs/check-image.py', WORK / 'before/userland/flashboot.apfs', 'Boot=' + str(tree)])\n", '')
    b.EXPECTED_AUDIO = json.loads((b.WORK / 'adaptation.json').read_text())['audio']['sha256']
    exec(compile(body, 'v3-retained-package', 'exec'), b.__dict__)
    b.package()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'revise', 'kernel', 'userland', 'loader', 'package', 'verify', 'test', 'qemu'])
    action = parser.parse_args().action
    {'prepare': prepare, 'revise': revise, 'kernel': b.build_kernel, 'userland': userland, 'loader': b.build_loader,
     'package': package, 'verify': b.verify, 'test': b.test, 'qemu': b.qemu}[action]()
