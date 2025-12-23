#!/usr/bin/env bash
set -euo pipefail

# build_native_pi.sh
# Build the Python extension _NIRScanner in one script (SWIG + compile + link)
# Usage: ./build_native_pi.sh [python-executable]
# Example: ./build_native_pi.sh /home/pi/tflite-env/bin/python

PYTHON_BIN=${1:-python3}

echo "Using Python executable: ${PYTHON_BIN}"
PY_VERSION=$(${PYTHON_BIN} -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
PY_SHORT=$(${PYTHON_BIN} -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
echo "Python version: ${PY_VERSION} (short: ${PY_SHORT})"

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
SRC_DIR="$ROOT_DIR/src"
BUILD_DIR="$SRC_DIR/build_native"

mkdir -p "$BUILD_DIR"
cd "$SRC_DIR"

# If SWIG + interface exist, generate wrapper (produces NIRScanner_wrap.cxx)
if command -v swig >/dev/null 2>&1 && [ -f "${SRC_DIR}/NIRScanner.i" ]; then
    echo "Running swig to generate wrapper..."
    swig -c++ -python NIRScanner.i || true
else
    echo "swig not found or NIRScanner.i missing; skipping swig (will use existing wrapper if present)."
fi

# Python include dir (for compile) and extension suffix
PY_INCDIR=$(${PYTHON_BIN} -c "import sysconfig; print(sysconfig.get_paths()['include'])")
PY_EXT_SUFFIX=$(${PYTHON_BIN} -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX') or '')")
echo "Python include dir: ${PY_INCDIR}"

# Use nullglob so empty globs expand to nothing
shopt -s nullglob

echo "Collecting sources in ${SRC_DIR} (excluding main.cpp)"
C_SOURCES=(./*.c)
CPP_SOURCES=(./*.cpp)
CXX_SOURCES=(./*.cxx)

# Filter out main.cpp (application) - don't include it in the shared object
CPP_FILTERED=()
for f in "${CPP_SOURCES[@]}"; do
    base=$(basename -- "$f")
    if [ "$base" = "main.cpp" ]; then
        echo "  skipping $base"
        continue
    fi
    CPP_FILTERED+=("$f")
done

# Include wrapper if present
WRAPPER="./NIRScanner_wrap.cxx"
if [ -f "$WRAPPER" ]; then
    echo "  will include SWIG wrapper: $WRAPPER"
    CXX_SOURCES+=("$WRAPPER")
fi

if [ ${#C_SOURCES[@]} -eq 0 ] && [ ${#CPP_FILTERED[@]} -eq 0 ] && [ ${#CXX_SOURCES[@]} -eq 0 ]; then
    echo "No C/C++ sources found in ${SRC_DIR}; aborting." >&2
    exit 1
fi

echo "Compiling sources into ${BUILD_DIR}"
for src in "${C_SOURCES[@]}"; do
    [ -f "$src" ] || continue
    obj="$BUILD_DIR/$(basename "$src").o"
    echo "  gcc -fPIC -I${PY_INCDIR} -c $src -o $obj"
    gcc -fPIC -I"${PY_INCDIR}" -c "$src" -o "$obj"
done

for src in "${CPP_FILTERED[@]}"; do
    [ -f "$src" ] || continue
    obj="$BUILD_DIR/$(basename "$src").o"
    echo "  g++ -fPIC -I${PY_INCDIR} -c $src -o $obj"
    g++ -fPIC -I"${PY_INCDIR}" -c "$src" -o "$obj"
done

for src in "${CXX_SOURCES[@]}"; do
    [ -f "$src" ] || continue
    obj="$BUILD_DIR/$(basename "$src").o"
    echo "  g++ -fPIC -I${PY_INCDIR} -c $src -o $obj"
    g++ -fPIC -I"${PY_INCDIR}" -c "$src" -o "$obj"
done

echo "Objects in ${BUILD_DIR}:"
ls -1 "$BUILD_DIR"/*.o || true

# Try to detect libpython to link against (optional). If not found, link without -lpython.
LINK_PYLIB="python${PY_SHORT}m"
if ! ldconfig -p 2>/dev/null | grep -q "lib${LINK_PYLIB}"; then
    LINK_PYLIB="python${PY_SHORT}"
    if ! ldconfig -p 2>/dev/null | grep -q "lib${LINK_PYLIB}"; then
        echo "Could not detect libpython for ${PY_SHORT}, will link without -lpython..."
        LINK_PYLIB=""
    else
        echo "Using python lib: ${LINK_PYLIB}"
    fi
else
    echo "Using python lib: ${LINK_PYLIB}"
fi

cd "$BUILD_DIR"
echo "Linking shared object _NIRScanner${PY_EXT_SUFFIX}"
# create output name considering Python EXT_SUFFIX if available
OUTNAME="_NIRScanner${PY_EXT_SUFFIX:-.so}"
if [ -n "${LINK_PYLIB}" ]; then
    g++ -shared -o "$OUTNAME" ./*.o -ludev -l${LINK_PYLIB}
else
    g++ -shared -o "$OUTNAME" ./*.o -ludev
fi

echo "Copying ${OUTNAME} to lib/ and project root..."
mkdir -p "$ROOT_DIR/lib"
cp -v "$OUTNAME" "$ROOT_DIR/lib/_NIRScanner${PY_EXT_SUFFIX}.${PY_SHORT}" || true
cp -v "$OUTNAME" "$ROOT_DIR/_NIRScanner${PY_EXT_SUFFIX}" || true

echo "Build finished. Result:"
ls -lh "$OUTNAME" || true
echo "If import issues occur, ensure you ran this script with the same Python executable used to run your scripts (provide full path to python when invoking)."
