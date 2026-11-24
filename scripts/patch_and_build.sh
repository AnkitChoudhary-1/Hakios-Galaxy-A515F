#!/bin/bash
set -e

SRC_DIR="/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland"
cd "$SRC_DIR"

if [ -f src/init.c.bak ]; then
    cp src/init.c.bak src/init.c
fi

python3 - << 'PYEOF'
with open('src/init.c', 'r') as f:
    content = f.read()

# 1. Update mount_cryptex: check if cryptex/cache already exists in /System/Cryptexes/
old_cryptex = """static void
mount_cryptex(const char *name, const char *container, const char *flashdev)
{
	char at[64], spec[128], what[200];
	int err;

	strcpy(at, join("/private/preboot/Cryptexes/", name, ""));"""

new_cryptex = """static void
mount_cryptex(const char *name, const char *container, const char *flashdev)
{
	char at[64], spec[128], what[200];
	int err;
	struct stat c_st;

	if (stat(join("/System/Cryptexes/", name, "/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64"), &c_st) == 0 ||
	    stat(join("/System/Cryptexes/", name, ""), &c_st) == 0) {
		strcpy(what, join("the ", name, " cryptex (already in system image)"));
		check(1, what);
		return;
	}

	strcpy(at, join("/private/preboot/Cryptexes/", name, ""));"""

assert old_cryptex in content, "old_cryptex not found"
content = content.replace(old_cryptex, new_cryptex)

# 2. Update flash_root: check if /flash/redwood and LaunchDaemons link already exist
old_flash = """	check(synthetic_dir("/flash/redwood"), "a synthetic /redwood on it, for this image");
	check(bind_dir(in_image("/LaunchDaemons"), "/flash/System/Library/LaunchDaemons") &&
	    bind_dir(in_image("/empty"), "/flash/System/Library/NanoLaunchDaemons") &&
	    bind_dir(in_image("/empty"), "/flash/System/Library/LaunchAngels") &&
	    bind_dir(in_image("/xpc"), "/flash/System/Library/xpc"), "our launchd jobs, not Darwin's");"""

new_flash = """	if (stat("/flash/redwood", &fw_st) != 0) {
		check(synthetic_dir("/flash/redwood"), "a synthetic /redwood on it, for this image");
	} else {
		check(1, "a synthetic /redwood on it, for this image");
	}
	struct stat l_st;
	if (lstat("/flash/System/Library/LaunchDaemons", &l_st) == 0 && (l_st.st_mode & 0170000) == 0120000) {
		check(1, "our launchd jobs, not Darwin's");
	} else {
		check(bind_dir(in_image("/LaunchDaemons"), "/flash/System/Library/LaunchDaemons") &&
		    bind_dir(in_image("/empty"), "/flash/System/Library/NanoLaunchDaemons") &&
		    bind_dir(in_image("/empty"), "/flash/System/Library/LaunchAngels") &&
		    bind_dir(in_image("/xpc"), "/flash/System/Library/xpc"), "our launchd jobs, not Darwin's");
	}"""

assert old_flash in content, "old_flash not found"
content = content.replace(old_flash, new_flash)

# 3. Update apps check: accept 0 applications or all bound
apps_idx = content.find("applications waiting to be installed")
assert apps_idx != -1, "apps marker not found"
line_end = content.find("\n", apps_idx)
check_line_start = content.find("check(", line_end)
check_line_end = content.find("\n", check_line_start)
new_check_line = 'check(apps == 0 || bound == apps, "the first boot\'s applications in /Applications");'
content = content[:check_line_start] + new_check_line + content[check_line_end:]

# 4. Update redwood bind & base: bind /private/preboot to /redwood and set base = "/redwood"
old_bind = """	mount_cryptex("OS", ",c=1", devpath);
	mount_cryptex("App", ",c=2", devpath);
	check(bind_dir("/private/preboot/redwood", "/redwood"), "this image back on /redwood");
	flash_root_mode = 1;"""

new_bind = """	mount_cryptex("OS", ",c=1", devpath);
	mount_cryptex("App", ",c=2", devpath);
	const char *preboot_dir = "/private/preboot";
	if (stat("/private/preboot/redwood", &fw_st) == 0) {
		preboot_dir = "/private/preboot/redwood";
	}
	check(bind_dir(preboot_dir, "/redwood"), "this image back on /redwood");
	base = "/redwood";
	flash_root_mode = 1;"""

assert old_bind in content, "old_bind not found"
content = content.replace(old_bind, new_bind)

# 5. Update execve launchd: if /sbin/launchd.darwin exists, DO NOT replace it with /sbin/launchd (which is stage0)
old_exec = """		if (flash_root_mode && strcmp(argv[1], "/sbin/launchd.darwin") == 0) {
			argv[1] = "/sbin/launchd";      /* the root is Darwin's own volume: its launchd is that */
		}"""

new_exec = """		if (flash_root_mode && strcmp(argv[1], "/sbin/launchd.darwin") == 0) {
			struct stat st_ld;
			if (stat("/sbin/launchd.darwin", &st_ld) != 0) {
				argv[1] = "/sbin/launchd";      /* untouched flash volume: its launchd is Apple's */
			}
		}"""

assert old_exec in content, "old_exec not found"
content = content.replace(old_exec, new_exec)

with open('src/init.c', 'w') as f:
    f.write(content)
print("Successfully patched src/init.c")
PYEOF

source ../xnu-env.sh
CC="xnu-clang -arch arm64 -Os -static -nostdlib -ffreestanding -fno-stack-protector -fno-builtin -Wall -Wextra"
LD="-Wl,-e,_start -Wl,-pagezero_size,0x100000000"

echo "Compiling init..."
$CC -Ilibmini $LD -o obj/init src/init.c obj/mini.o obj/start.o

echo "Updating root directory..."
cp obj/init root/sbin/init
cp obj/init root/sbin/launchd
mkdir -p root/flash

echo "Repacking root.apfs..."
python3 ../tools/apfs/mkapfs.py -z --plain fw -o root.apfs redwood=root | tail -3

echo "=== BUILD COMPLETE ==="
