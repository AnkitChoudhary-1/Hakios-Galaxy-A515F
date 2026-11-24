#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Iris for HakiOS (Darwin/ARM64) ==="

export THEOS="${THEOS:-/opt/a51-hakios/theos}"

# Load XNU / Theos environment
XNU_ENV="/opt/a51-hakios/upstream-a51/hakios/xnu-env.sh"
if [ -f "$XNU_ENV" ]; then
    source "$XNU_ENV"
fi
SDK="${THEOS}/sdks/iPhoneOS16.5.sdk"
TOOLCHAIN="${THEOS}/toolchain/linux/iphone/bin"
LDID="${TOOLCHAIN}/ldid"

if [ ! -d "$SDK" ]; then
    echo "Error: iPhoneOS 16.5 SDK not found at $SDK"
    exit 1
fi

BUILD_DIR="$SCRIPT_DIR/build"
APP_DIR="$BUILD_DIR/Iris.app"
rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR"

SOURCES=$(find "$SCRIPT_DIR/src" -name "*.m")
echo "Compiling sources:"
for s in $SOURCES; do
    echo "  - $(basename "$s")"
done

# Compile and link using xnu-clang
CLANG="xnu-clang"
if ! command -v $CLANG >/dev/null 2>&1; then
    CLANG="/opt/a51-hakios/upstream-a51/hakios/xnu-deps/host/bin/xnu-clang"
fi

$CLANG -arch arm64 \
    -isysroot "$SDK" \
    -target arm64-apple-ios16.5 \
    -fobjc-arc \
    -O2 \
    -I"$SCRIPT_DIR/src" \
    -framework UIKit \
    -framework Foundation \
    -framework CoreGraphics \
    -framework QuartzCore \
    -o "$APP_DIR/Iris" \
    $SOURCES

# Copy Info.plist
cp "$SCRIPT_DIR/resources/Info.plist" "$APP_DIR/Info.plist"

# Fake sign with ldid
if [ -x "$LDID" ]; then
    echo "Signing Iris binary with ldid..."
    "$LDID" -S "$APP_DIR/Iris"
else
    echo "Warning: ldid not found at $LDID"
fi

echo "Verifying Mach-O executable:"
file "$APP_DIR/Iris"

echo "Iris.app successfully built at: $APP_DIR"

# Stage in /opt/a51-hakios/apps/Payload/
STAGE_DIR="/opt/a51-hakios/apps/Payload"
mkdir -p "$STAGE_DIR"
rm -rf "$STAGE_DIR/Iris.app"
cp -a "$APP_DIR" "$STAGE_DIR/"
echo "Staged to $STAGE_DIR/Iris.app"

# Generate APFS package for HakiOS
MKAPFS="/opt/a51-hakios/upstream-a51/hakios/tools/apfs/mkapfs.py"
if [ -f "$MKAPFS" ]; then
    echo "Creating APFS package iris.apfs..."
    STAGE_APFS_ROOT="$BUILD_DIR/staging"
    mkdir -p "$STAGE_APFS_ROOT/apps"
    cp -a "$APP_DIR" "$STAGE_APFS_ROOT/apps/"
    python3 "$MKAPFS" -z -o "$BUILD_DIR/iris.apfs" Apps="$STAGE_APFS_ROOT/apps"
    cp -f "$BUILD_DIR/iris.apfs" "/opt/a51-hakios/apps/iris.apfs"
    echo "APFS container built: $BUILD_DIR/iris.apfs (and copied to /opt/a51-hakios/apps/iris.apfs)"
fi

echo "=== Iris build completed successfully! ==="
