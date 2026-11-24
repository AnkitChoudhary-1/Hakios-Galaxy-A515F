> Source snapshot note: hardware assertions below are upstream/historical. Current observed status is in ../../docs/PUBLIC-STATUS.md.

# Device repositories

`devices/manifest.conf` names every device; `tools/hakios-device.py sync` clones each into `devices/<name>/`. `devices/qemu/` is
kept here: QEMU's machine, with none of a phone's drivers, the device every checkout of the common repository can build and run.
A device of your own: `tools/hakios-device.py new` ([Port a device](../docs/porting/index.md)).
