#!/usr/bin/env python3
"""Repair/package the retained A51 port in WSL; never contacts the phone.

Run each action through scripts/run.py. See docs/GPU-AUDIO-BUILD-REPAIR.md.
Existing dirty sources are preserved. Outputs use a separate repair directory.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import re

UP = Path('/opt/a51-hakios/upstream-a51/hakios')
WORK = Path('/opt/a51-hakios/build-repair/gpu-audio-20261124')
GPU = 'devices/a51/drivers/gpu/hakios.a51gpu.c'
AUDIO = 'devices/a51/drivers/audio/hakios.a51audio.c'
XNU = 'xnu-src/xnu-8796.121.2'
FD = 'Mu-Silicium/Build/a51Pkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd'
IMAGE = 'A51-HakiOS-full-quality-gpu-audio-fixed-v2-boot.img'
EXPECTED_AUDIO = 'bab89d13130474c6d8155a33aefdf772969920e50976d383fed7ec172dd48e4f'


def pin(path):
    data = Path(path).read_bytes()
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def run(args, **kw):
    print('COMMAND ' + json.dumps([str(a) for a in args]), flush=True)
    return subprocess.run([str(a) for a in args], cwd=UP, check=True, **kw)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def prepare():
    WORK.mkdir(parents=True, exist_ok=False)
    names = [GPU, AUDIO, XNU + '/bsd/dev/hakios.a51gpu.c',
             XNU + '/bsd/dev/hakios.a51audio.c', '.config', 'hakios-kernel',
             'userland/root.apfs', 'userland/flashboot.apfs', 'userland/obj/stage0',
             'userland/src/stage0.c', 'userland/root/sbin/init', 'userland/root/sbin/launchd',
             'xnuloader/loader.c', 'xnuloader/loader.efi', 'xnuloader/loader.obj',
             'xnuloader/build.sh', 'xnuloader/mkpayload.py', 'mkxnuimg.py', FD,
             'Mu-Silicium/BootShim/BootShim.S', 'Mu-Silicium/BootShim/Makefile',
             'Mu-Silicium/BootShim/BootShim.bin', 'Mu-Silicium/BootShim/BootShim.elf',
             'Mu-Silicium/Resources/DTBs/a51.dtb', 'Mu-Silicium/Resources/ramdisk',
             'Mu-Silicium/Resources/Scripts/mkbootimg.py',
             'tools/apfs/mkapfs.py', 'tools/apfs/check-image.py', 'apfs-work/apfs-tool',
             'xnu-deps/build/apfsprogs/apfsck/apfsck', 'userland/a51-full-quality-build.log']
    inputs = {}
    for name in names:
        source = UP / name
        if source.is_file():
            dest = WORK / 'before' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            inputs[name] = pin(source)
    for repo in ['', 'devices/a51', XNU, 'Mu-Silicium']:
        label = repo.replace('/', '-') or 'root'
        for args, suffix in [(['rev-parse', 'HEAD'], '.head'), (['status', '--short'], '.status'),
                             (['diff', '--binary', 'HEAD'], '.patch')]:
            data = run(['git', '-C', UP / repo, *args], capture_output=True).stdout
            (WORK / (label + suffix)).write_bytes(data)
    write_json(WORK / 'inputs.json', inputs)
    assert inputs[AUDIO]['sha256'] == EXPECTED_AUDIO, 'Audio source drift: inspect before continuing'
    source = UP / GPU
    before = source.read_text()
    old = 'kmem_alloc(kernel_map, &va, round_page(size), KMA_KOBJECT | KMA_ZERO | KMA_DATA, VM_KERN_MEMORY_IOKIT)'
    new = 'kmem_alloc_contig(kernel_map, &va, round_page(size), PAGE_MASK, 0, 0,\n\t    KMA_KOBJECT | KMA_ZERO | KMA_DATA, VM_KERN_MEMORY_IOKIT)'
    assert before.count(old) == 1
    after = before.replace(old, new)
    old_guard = 'printf("a51gpu: the memory at %lx is not in one piece\\n", va);\n\t\t\treturn 0;'
    new_guard = 'printf("a51gpu: the memory at %lx is not in one piece\\n", va);\n\t\t\tkmem_free(kernel_map, va, round_page(size));\n\t\t\t*phys = 0;\n\t\t\treturn 0;'
    assert after.count(old_guard) == 1
    after = after.replace(old_guard, new_guard)
    source.write_text(after)
    shutil.copy2(source, UP / XNU / 'bsd/dev/hakios.a51gpu.c')
    (WORK / 'gpu-contiguous.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/' + GPU, tofile='b/' + GPU)))
    assert pin(UP / AUDIO)['sha256'] == EXPECTED_AUDIO
    print('Prepared snapshots and GPU contiguous allocation/cleanup repair: ' + str(WORK))


def build_kernel():
    # Force both requested drivers to compile even when an old object happens
    # to have newer timestamps. Bytes of the user's audio source stay unchanged.
    for name in ['gpu', 'audio']:
        src = UP / f'devices/a51/drivers/{name}/hakios.a51{name}.c'
        dst = UP / XNU / f'bsd/dev/hakios.a51{name}.c'
        shutil.copy2(src, dst)
        dst.touch()
    log = WORK / ('kernel-build-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.log')
    env = dict(os.environ, KERNEL_LOG=str(log))
    started = dt.datetime.now(dt.timezone.utc).timestamp()
    run(['bash', 'tools/make-kernel.sh', '-j8'], env=env)
    kernel = UP / 'hakios-kernel'
    assert kernel.stat().st_mtime >= started, 'Linked kernel is stale'
    for name in ['gpu', 'audio']:
        src = UP / f'devices/a51/drivers/{name}/hakios.a51{name}.c'
        dst = UP / XNU / f'bsd/dev/hakios.a51{name}.c'
        assert pin(src) == pin(dst), name + ' sync mismatch'
        objects = list((UP / XNU / 'BUILD/obj').rglob(f'hakios.a51{name}.c.o'))
        if not objects:
            objects = list((UP / XNU / 'BUILD/obj').rglob(f'*a51{name}*.o'))
        assert objects, 'No driver object: ' + name
        assert max(p.stat().st_mtime for p in objects) >= started, 'Stale driver object: ' + name
    assert pin(UP / AUDIO)['sha256'] == EXPECTED_AUDIO
    shutil.copy2(kernel, WORK / 'hakios-kernel')
    write_json(WORK / 'kernel.json', {'kernel': pin(kernel), 'gpu': pin(UP / GPU),
               'audio': pin(UP / AUDIO), 'linked_after': started, 'build_log': str(log)})


def build_loader():
    run(['bash', 'xnuloader/build.sh'])
    shutil.copy2(UP / 'xnuloader/loader.efi', WORK / 'loader.efi')


def package():
    assert pin(UP / AUDIO)['sha256'] == EXPECTED_AUDIO
    tree = WORK / 'flashboot-full-quality'
    tree.mkdir(exist_ok=False)
    for name in ['sbin', 'redwood', 'dev', 'flash', 'Cryptexes/OS', 'Cryptexes/App', 'apps']:
        (tree / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(UP / 'userland/obj/stage0', tree / 'sbin/launchd')
    (tree / 'sbin/launchd').chmod(0o755)
    # Preserve the latest optional app, as the existing flashboot recipe does.
    app = Path('/opt/a51-hakios/apps/Payload/Iris.app')
    assert app.is_dir(), 'Existing Iris app must be preserved in this repair'
    shutil.copytree(app, tree / 'apps/Iris.app', copy_function=shutil.copy2)
    for path in [app / 'Iris', app / 'Info.plist']:
        restored = run([UP / 'apfs-work/apfs-tool', 'cat', WORK / 'before/userland/flashboot.apfs',
                        '/apps/Iris.app/' + path.name], capture_output=True).stdout
        assert restored == path.read_bytes(), 'Existing app drift'
    for name in ['manifest.json', 'recipe.json', 'payload.bin', 'flashboot.apfs']:
        if (WORK / name).exists():
            shutil.copy2(WORK / name, WORK / ('first-minimal-' + name))
    root = WORK / 'root.apfs'
    shutil.copy2(UP / 'userland/root.apfs', root)
    run(['python3', 'tools/apfs/check-image.py', root, 'redwood=userland/root'])
    run(['python3', 'tools/apfs/mkapfs.py', '-z', '--plain', 'fw', '-o', WORK / 'flashboot.apfs', 'Boot=' + str(tree)])
    run(['python3', 'tools/apfs/check-image.py', WORK / 'flashboot.apfs', 'Boot=' + str(tree)])
    # The old boot filesystem was valid; restoring its contents is byte exact
    # at the file/mode/owner level. The actual boot defect was absent md1.
    run(['python3', 'tools/apfs/check-image.py', WORK / 'before/userland/flashboot.apfs', 'Boot=' + str(tree)])
    args = ('loader_return_after=0 touch_lat=0 root_apfs=ufs_darwin ufs=2 ufs_write=1 var_store=1 '
            'bootcpu=4 cpus=7 small_cores_after=0 touchscreen=1 a51gpu=8 a51gpu_keep=1 a51gpu_clock=3 '
            'a51cpu0_khz=1742000 a51cpu1_khz=2314000 a51gpu_mhz=1053 a51mif_khz=2093000 '
            'a51int_khz=667000 a51wifi=8 a51audio=4 fb_threads=1 fb_decon_trig=1 fb_decon_double=1 '
            'fb_decon_second=0xcaa00000 fb_decon_third=0xcb400000 fb_ca_hz=120 sb_delay=8 '
            'enable_skstb=1 a51battery=2 fbscale=2 epoch=' + str(int(dt.datetime.now(dt.timezone.utc).timestamp())))
    version = run(['python3', 'tools/kernel-version.py'], capture_output=True, text=True).stdout.strip()
    # Loader prepends debug/root/shared-page/version. Reserve the longest A51 prefix, plus WDT if armed.
    budget = len('debug=0x8 serial=3 rd=md0 hv_wdt_pet=1 ufs_shared_pa=0x' + '0' * 16 + ' hakios_kver=' + version + ' ') + len(args)
    assert budget <= 607, ('Command line may truncate', budget)
    (WORK / 'cmdline.txt').write_text(args + '\n')
    run(['python3', 'xnuloader/mkpayload.py', '-o', WORK / 'payload.bin',
         'loader.efi=' + str(WORK / 'loader.efi'), 'kernel=' + str(WORK / 'hakios-kernel'),
         'ramdisk=' + str(root), 'resident=' + str(WORK / 'flashboot.apfs'),
         '--cmdline', args, '--kernel-version', version])
    run(['python3', 'mkxnuimg.py', '--device', 'a51', '-p', WORK / 'payload.bin', '-o', WORK / IMAGE])
    write_json(WORK / 'recipe.json', {'cmdline': args, 'kernel_version': version,
               'command_line_conservative_bytes': budget, 'md0': 'resident=flashboot.apfs',
               'md1': 'ramdisk=root.apfs', 'device_operations': False})
    verify()


def verify():
    inputs = json.loads((WORK / 'inputs.json').read_text())
    data = (WORK / IMAGE).read_bytes()
    assert data[:8] == b'ANDROID!'
    ksize, kaddr, rsize, raddr, ssize, saddr, tags, page, ver = struct.unpack_from('<9I', data, 8)
    assert (kaddr, raddr, tags, page, ver, ssize) == (0x10008000, 0x11000000, 0x10000100, 2048, 2, 0)
    roundup = lambda x: (x + page - 1) // page * page
    kend = page + ksize
    ramoff = page + roundup(ksize)
    dtbo_size, dtbo_off, header_size = struct.unpack_from('<IQI', data, 1632)
    dtb_size, dtb_addr = struct.unpack_from('<IQ', data, 1648)
    assert dtbo_size == 0 and header_size == 1660 and dtb_addr == 0x10000000
    dtboff = ramoff + roundup(rsize)
    assert len(data) == dtboff + roundup(dtb_size)
    assert len(data) <= 61865984, 'Boot partition overflow'
    shim = (UP / 'Mu-Silicium/BootShim/BootShim.bin').read_bytes()
    fd = (UP / FD).read_bytes()
    payload = (WORK / 'payload.bin').read_bytes()
    assert pin(UP / FD) == inputs[FD], 'Firmware changed'
    assert data[page:page + len(shim)] == shim and shim[56:60] == b'ARM\x64'
    assert data[page + len(shim):page + len(shim) + len(fd)] == fd
    assert fd[40:44] == b'_FVH', 'Invalid UEFI firmware volume'
    poff = page + len(shim) + len(fd)
    assert data[poff:poff + len(payload)] == payload and kend >= poff + len(payload)
    assert data[ramoff:ramoff + rsize] == (UP / 'Mu-Silicium/Resources/ramdisk').read_bytes()
    assert data[dtboff:dtboff + dtb_size] == (UP / 'Mu-Silicium/Resources/DTBs/a51.dtb').read_bytes()
    assert payload[:4] == b'XNUP' and len(payload) == 8 + struct.unpack_from('<I', payload, 4)[0]
    assert len(payload) <= 0x04000000 - 0x1000
    entries, off = {}, 8
    while off + 24 <= len(payload):
        raw, size, reserved = struct.unpack_from('<16sII', payload, off)
        off += 24
        if not raw.strip(b'\0'):
            assert size == 0 and off == len(payload)
            break
        name = raw.split(b'\0')[0].decode()
        assert name not in entries and reserved == 0 and off + size <= len(payload)
        entry = payload[off:off + size]
        entries[name] = {'size': size, 'sha256': hashlib.sha256(entry).hexdigest()}
        if name in ['loader.efi', 'kernel', 'ramdisk', 'resident']:
            file = {'loader.efi': 'loader.efi', 'kernel': 'hakios-kernel',
                    'ramdisk': 'root.apfs', 'resident': 'flashboot.apfs'}[name]
            assert entry == (WORK / file).read_bytes()
        if name == 'cmdline':
            assert b'ufs_shared_pa=' not in entry and b'a51audio=4' in entry and b'a51gpu=8' in entry
        off += (size + 15) // 16 * 16
    assert set(entries) == {'loader.efi', 'kernel', 'ramdisk', 'resident', 'cmdline', 'kernel.ver'}
    # mkbootimg v2 ID = SHA1(kernel+len, ramdisk+len, second+len, recovery_dtbo+len, dtb+len).
    digest = hashlib.sha1()
    for section in [data[page:kend], data[ramoff:ramoff + rsize], b'', b'', data[dtboff:dtboff + dtb_size]]:
        digest.update(section)
        digest.update(struct.pack('<I', len(section)))
    assert data[576:596] == digest.digest(), 'Android image ID mismatch'
    manifest = {'schema_version': 1, 'verified_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'image': pin(WORK / IMAGE), 'kernel_section_bytes': ksize, 'partition_bytes': 61865984,
                'header_version': ver, 'page_size': page, 'shim': pin(UP / 'Mu-Silicium/BootShim/BootShim.bin'),
                'firmware': pin(UP / FD), 'entries': entries, 'gpu': pin(UP / GPU), 'audio': pin(UP / AUDIO),
                'host_package_verified': True, 'device_boot_verified': False, 'audible_audio_verified': False,
                'gpu_hardware_execution_verified': False, 'device_writes': False}
    write_json(WORK / 'manifest.json', manifest)
    print(json.dumps(manifest, indent=2))


def test():
    # Exercise the actual helper with a modeled page map, including allocation
    # failure and the defensive cleanup path. This does not emulate Mali MMIO.
    source = (UP / GPU).read_text()
    helper = re.search(r'static vm_offset_t\ngpu_page\(.*?\n\}', source, re.S).group()
    stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef unsigned long vm_offset_t;
typedef unsigned long vm_size_t;
#define PAGE_MASK 16383UL
#define KMA_KOBJECT 1
#define KMA_ZERO 2
#define KMA_DATA 4
#define VM_KERN_MEMORY_IOKIT 11
#define KERN_SUCCESS 0
#define kernel_map 9
#define round_page(n) (((n) + PAGE_MASK) & ~PAGE_MASK)
static int fail_alloc, fragment, freed, allocated;
static vm_size_t want_size;
static int kmem_alloc_contig(int map, vm_offset_t *va, vm_size_t size,
    vm_offset_t mask, int maxp, int pnum, int flags, int tag) {
    assert(map == kernel_map && size == want_size && mask == PAGE_MASK);
    assert(maxp == 0 && pnum == 0 && flags == 7 && tag == VM_KERN_MEMORY_IOKIT);
    allocated++;
    if (fail_alloc) return 1;
    *va = 0x100000;
    return KERN_SUCCESS;
}
static uint64_t kvtophys(vm_offset_t va) {
    return va + 0x200000 + ((fragment && va >= 0x101000) ? 4096 : 0);
}
static void kmem_free(int map, vm_offset_t va, vm_size_t size) {
    assert(map == kernel_map && va == 0x100000 && size == want_size);
    freed++;
}
'''
    cases = r'''
int main(void) {
    uint64_t pa = 0;
    want_size = 16384;
    assert(gpu_page(16384, &pa) == 0x100000 && pa == 0x300000 && freed == 0);
    pa = 0;
    assert(gpu_page(5000, &pa) == 0x100000 && pa == 0x300000 && freed == 0);
    fail_alloc = 1;
    assert(gpu_page(16384, &pa) == 0 && freed == 0);
    fail_alloc = 0; fragment = 1;
    assert(gpu_page(16384, &pa) == 0 && pa == 0 && freed == 1 && allocated == 4);
    puts("GPU allocator: 4 functional cases passed (modeled memory, no hardware)");
}
'''
    path = WORK / 'gpu-allocator-test.c'
    path.write_text(stub + helper + cases)
    run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
         '-o', WORK / 'gpu-allocator-test', path])
    run([WORK / 'gpu-allocator-test'])
    write_json(WORK / 'allocator-test.json', {'cases': 4, 'passed': True, 'hardware': False,
               'source': pin(UP / GPU), 'harness': pin(path)})


def qemu():
    folder = WORK / ('qemu-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(exist_ok=False)
    (WORK / 'xnuloader').mkdir(exist_ok=True)
    shutil.copy2(WORK / 'loader.efi', WORK / 'xnuloader/loader.efi')
    shutil.copy2(UP / 'qemu/run.sh', folder / 'run.sh')
    shutil.copy2(UP / 'userland/src/hello.c', folder / 'hello.c')
    run(['bash', '-c', 'source ./xnu-env.sh && xnu-clang -arch arm64 -Os -static '
         '-nostdlib -ffreestanding -fno-stack-protector -fno-builtin -Wl,-e,_start '
         '-Wl,-pagezero_size,0x100000000 -o "$1" "$2"', 'compile-hello', folder / 'hello', folder / 'hello.c'])
    run(['python3', 'xnuloader/mkpayload.py', '-o', folder / 'payload.bin',
         'kernel=' + str(WORK / 'hakios-kernel'), 'ramdisk=' + str(folder / 'hello'),
         '--cmdline', 'a51audio=0 cpus=1 hello_wait=120'])
    result = subprocess.run(['bash', str(folder / 'run.sh'), '35'], cwd=folder,
                            capture_output=True, timeout=45)
    (folder / 'serial.log').write_bytes(result.stdout + result.stderr)
    serial = result.stdout.decode(errors='replace')
    print('\n'.join(line for line in serial.splitlines() if any(marker in line for marker in
          ['cmdline:', 'Darwin Kernel Version', 'Hello from user', 'I am process', 'kernel.ver=', 'panic(cpu'])))
    assert result.returncode == 124, ('Unexpected QEMU termination', result.returncode)
    assert 'Hello from user space on Darwin!' in serial and 'I am process 1, uid 0' in serial
    assert 'panic(cpu' not in serial
    write_json(folder / 'result.json', {'passed': True, 'kernel': pin(WORK / 'hakios-kernel'),
               'loader': pin(WORK / 'loader.efi'), 'serial': pin(folder / 'serial.log'),
               'hello': pin(folder / 'hello'), 'hello_source': pin(folder / 'hello.c'),
               'timeout_seconds': 35, 'exit_code': result.returncode,
               'process_1_uid_0_verified': True, 'a51_hardware_verified': False,
               'scope': 'same repaired kernel and UEFI loader; QEMU virt; raw hello ramdisk; A51 audio disabled'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'kernel', 'loader', 'package', 'verify', 'test', 'qemu'])
    action = parser.parse_args().action
    {'prepare': prepare, 'kernel': build_kernel, 'loader': build_loader,
     'package': package, 'verify': verify, 'test': test, 'qemu': qemu}[action]()
