#!/usr/bin/env python3
"""Native checks extracted from the actual driver and registration helper."""
from pathlib import Path
import re
import subprocess
import json
import hashlib

up = Path('/opt/a51-hakios/upstream-a51/hakios')
work = Path('/opt/a51-hakios/build-repair/audio-iris-20261124')
source = (up / 'devices/a51/drivers/audio/hakios.a51audio.c').read_text()
sink = re.search(r'static uint32_t a51_audio_sink\(.*?\n\}', source, re.S).group()
clock = re.search(r'static uint32_t a51_bclk_div\(.*?\n\}', source, re.S).group()
sink = sink.replace('__asm__ volatile("dsb sy" ::: "memory");', '(void)0;')
stub = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#define HAKIOS_AUDIO_FRAME 4
#define A51_DMA_FRAMES 16384u
#define A51_DMA_PERIOD 4096u
static uint32_t ring[A51_DMA_FRAMES], status;
static int16_t *dma_virt_buffer = (int16_t *)ring;
static unsigned long abox_base=0x1000;
static bool audio_sink_active=true, dma_writer_started;
static uint32_t dma_write_frame_offset, dma_last_read;
static uint32_t audio_rd(unsigned long addr) { assert(addr==0x2030); return status; }
'''
cases = r'''
int main(void) {
 uint32_t hz=0, con=0xa0000000u|(45u<<16)|(1u<<8);
 assert(a51_bclk_div(con,24319,15,&hz)==48 && hz>=1535990 && hz<=1536010);
 assert(a51_bclk_div(con,24319,31,&hz)==24);
 assert(a51_bclk_div(con&~(63u<<8),24319,15,&hz)==0);
 assert(a51_bclk_div(con&~(1u<<29),24319,15,&hz)==0);
 assert(a51_bclk_div(con,24319,0,&hz)==0); /* divider exceeds 512 */
 int16_t samples[8]={1,2,3,4,5,6,7,8};
 status=0; assert(a51_audio_sink(samples,4)==0);
 status=0x80000000; audio_sink_active=false; assert(a51_audio_sink(samples,4)==0);
 audio_sink_active=true; assert(a51_audio_sink(samples,4)==4);
 assert(ring[2048]==0x00020001 && ring[2051]==0x00080007 && ring[0]==0);
 dma_write_frame_offset=16000; assert(a51_audio_sink(samples,4)==0); /* no unsigned underflow */
 dma_writer_started=false; status=0x80000000u|((16380u*4/16)<<16);
 assert(a51_audio_sink(samples,4)==4 && ring[2044]==0x00020001);
 dma_last_read=10; status=0x80000000u|((20u*4/16)<<16); ring[10]=123;
 assert(a51_audio_sink(samples,4)==4 && ring[10]==0);
 puts("Audio: 11 clock/ring cases passed; hardware not emulated");
}
'''
path=work/'audio-test.c'
path.write_text(stub+sink+clock+cases)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-o',str(work/'audio-test'),str(path)],check=True)
subprocess.run([str(work/'audio-test')],check=True)
iris=(up/'userland/src/iris_register.c').read_text().replace('#include "mini.h"', r'''
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
static int calls, succeed, missing, reap_fail;
static int test_stat(const char *p, struct stat *st) { (void)p;(void)st;return missing?-1:0; }
static pid_t test_fork(void) { calls++;return 123; }
static pid_t test_wait(pid_t p,int *s,int flags,void *r) { (void)flags;(void)r;*s=calls==succeed?0:256;return reap_fail?-1:p; }
static int test_sleep(useconds_t n) { assert(n==3000000);return 0; }
#define stat test_stat
#define fork test_fork
#define wait4 test_wait
#define usleep test_sleep
#define main iris_main
''').replace('struct stat st;', 'struct stat st;')
# use function-like stat macro so the struct tag remains intact
iris=iris.replace('#define stat test_stat', '#define stat(p,s) test_stat(p,s)')
iris += r'''
#undef main
int main(void) {
 calls=0;succeed=3;assert(iris_main(0,0,0)==0 && calls==3);
 calls=0;succeed=0;assert(iris_main(0,0,0)==1 && calls==20);
 calls=0;missing=1;assert(iris_main(0,0,0)==1 && calls==0);
 calls=0;missing=0;succeed=1;reap_fail=1;assert(iris_main(0,0,0)==1 && calls==20);
 puts("Iris: 4 retry/failure cases passed; LaunchServices not emulated");
}
'''
# Keep native tests away from real filesystem permissions and log paths.
iris=iris.replace('mkdir("/private/var/mobile/Library/Logs", 0755);', '(void)0;')
iris=iris.replace('chown("/private/var/mobile/Library/Logs", 501, 501);', '(void)0;')
iris=iris.replace('int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0644);', 'int fd = -1; (void)log;')
path=work/'iris-test.c';path.write_text(iris)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-o',str(work/'iris-test'),str(path)],check=True)
subprocess.run([str(work/'iris-test')],check=True)
result={'audio_cases':11,'iris_cases':4,'passed':True,'hardware_verified':False,
 'audio_sha256':hashlib.sha256(source.encode()).hexdigest(),
 'iris_sha256':hashlib.sha256((up/'userland/src/iris_register.c').read_bytes()).hexdigest()}
(work/'audio-iris-tests.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
