#!/usr/bin/env python3
"""Test actual audio helpers and exhaustive touch range under ASan/UBSan."""
from pathlib import Path
import json
import re
import subprocess
import hashlib

P = Path(__file__).resolve().parents[1]
UP = Path('/opt/a51-hakios/upstream-a51/hakios')
W = Path('/opt/a51-hakios/build-repair/touch-audio-20261124-r1')
old = (P / 'scripts/test-audio-iris.py').read_text()
old = old.replace("work = Path('/opt/a51-hakios/build-repair/audio-iris-20261124')", "work = Path('" + str(W) + "')")
old = old.replace('static uint32_t ring[A51_DMA_FRAMES], status;', 'static uint32_t ring[A51_DMA_FRAMES], status, sink_calls, sink_frames, sink_status;')
exec(compile(old, 'retained-native-audio-iris-tests', 'exec'))
audio = (UP / 'devices/a51/drivers/audio/hakios.a51audio.c').read_text()
touch = (UP / 'devices/a51/drivers/input/hakios.a51input.c').read_text()
gate = re.search(r'static uint32_t a51_gate_value\(.*?\n\}', audio, re.S).group()
qch = re.search(r'static uint32_t a51_qch_value\(.*?\n\}', audio, re.S).group()
scale = re.search(r'static uint32_t\nscale\(.*?\n\}', touch, re.S).group()
harness = '''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
''' + gate + qch + scale + r'''
int main(void) {
    uint32_t prev=0;
    assert(scale(4095,4096)==65535 && scale(0,4096)==0);
    assert(scale(4096,4096)==65535 && scale(UINT32_MAX,4096)==65535);
    assert(scale(999,0)==0 && scale(999,1)==0);
    assert(scale(1000,4096)>15000 && scale(1000,4096)<17000);
    /* Reproduce metadata=1080 clipping three quarters of the raw range. */
    assert(scale(2048,1080)==65535 && scale(2048,4096)>=32767 && scale(2048,4096)<=32776);
    for (uint32_t v=0;v<4096;v++) {
        uint32_t next=scale(v,4096);
        assert(next==((uint64_t)v*65535/4095));
        assert(next>=prev && next<=65535); prev=next;
    }
    for (uint32_t bit=0;bit<32;bit++) {
        uint32_t samples[]={1u<<bit, ~(1u<<bit)};
        for (unsigned i=0;i<2;i++) {
            uint32_t before=samples[i], g=a51_gate_value(before), q=a51_qch_value(before);
            assert((g&((1u<<28)|(3u<<20)))==(3u<<20));
            assert(((g^before)&~((1u<<28)|(3u<<20)))==0);
            assert((q&7u)==6u && ((q^before)&~7u)==0);
        }
    }
    puts("Touch: all 4096 coordinates, endpoints, clamp and metadata regression passed; 64 gate/QCH patterns passed");
}
'''
(W / 'touch-clock-test.c').write_text(harness)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-o',str(W/'touch-clock-test'),str(W/'touch-clock-test.c')],check=True)
subprocess.run([str(W/'touch-clock-test')],check=True)
record = {'passed':True, 'touch_coordinates':4096, 'clock_patterns':64, 'hardware_verified':False,
    'touch_sha256':hashlib.sha256(touch.encode()).hexdigest(), 'audio_sha256':hashlib.sha256(audio.encode()).hexdigest()}
(W/'touch-clock-tests.json').write_text(json.dumps(record,indent=2)+'\n')
