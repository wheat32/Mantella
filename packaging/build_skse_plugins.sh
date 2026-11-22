#!/usr/bin/env bash
# Builds the four SKSE plugins (skse/) on Linux, producing the same kind of Windows .dll files as a build on Windows:
# clang-cl and lld-link compile against the Windows SDK / MSVC runtime files that xwin downloads from Microsoft.
#
# The first run sets up everything it needs under build/skse-toolchain (several GB; takes a while):
#   - xwin (built with cargo) and the Windows SDK + MSVC CRT. Running this script accepts Microsoft's licence
#     for these files on your behalf: https://go.microsoft.com/fwlink/?LinkId=2086102
#   - vcpkg, which builds the libraries the plugins use
#   - llvm-mingw, to build a small tool that DirectXTK (a dependency of CommonLibSSE-NG) needs under Wine
#   - CommonLibSSE-NG, at the version set in skse/CMakeLists.txt
#
# Needed on this machine: clang (with clang-cl), llvm, cmake, ninja, cargo (Rust), git, wine, curl
# and lld (lld-link). Without lld, the linker that comes with Rust (rust-lld) is used.
#
# Usage: packaging/build_skse_plugins.sh        -> dist/skse/*.dll (picked up by packaging/build_mod_archive.py)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tc="$repo/build/skse-toolchain"
build_dir="$repo/build/skse"
xwin_version="0.10.0"
llvm_mingw_release="20260826"
llvm_mingw_name="llvm-mingw-${llvm_mingw_release}-ucrt-ubuntu-22.04-x86_64"

fail() { echo "Error: $*" >&2; exit 1; }
for tool in clang-cl cmake ninja cargo git wine curl llvm-rc llvm-mt; do
    command -v "$tool" >/dev/null || fail "'$tool' is not installed."
done
mkdir -p "$tc/bin"
export PATH="$tc/bin:$tc/cargo/bin:$PATH"

# Linker: lld-link, or the copy of lld that ships with Rust
if ! command -v lld-link >/dev/null; then
    rust_lld="$(find "$(rustc --print sysroot)" -name rust-lld -type f | head -n 1)"
    [[ -n "$rust_lld" ]] || fail "Neither lld-link (package 'lld') nor rust-lld was found."
    printf '#!/bin/sh\nexec "%s" -flavor link "$@"\n' "$rust_lld" > "$tc/bin/lld-link"
    chmod +x "$tc/bin/lld-link"
fi

# xwin and the Windows SDK / MSVC CRT
if [[ ! -x "$tc/cargo/bin/xwin" ]]; then
    echo "== Building xwin $xwin_version..."
    cargo install xwin --version "$xwin_version" --locked --root "$tc/cargo" --quiet
fi
if [[ ! -d "$tc/xwin-out/VC" ]]; then
    echo "== Downloading the Windows SDK and MSVC CRT with xwin..."
    xwin --accept-license --http-retry 10 --cache-dir "$tc/xwin-cache" splat --output "$tc/xwin-out" \
        --include-debug-libs --use-winsysroot-style --preserve-ms-arch-notation
fi

# vcpkg
if [[ ! -x "$tc/vcpkg/vcpkg" ]]; then
    echo "== Setting up vcpkg..."
    [[ -d "$tc/vcpkg/.git" ]] || git clone --quiet https://github.com/microsoft/vcpkg "$tc/vcpkg"
    "$tc/vcpkg/bootstrap-vcpkg.sh" -disableMetrics > "$tc/vcpkg-bootstrap.log" 2>&1 || fail "vcpkg bootstrap failed, see $tc/vcpkg-bootstrap.log"
fi

# llvm-mingw
if [[ ! -x "$tc/llvm-mingw/bin/x86_64-w64-mingw32-clang++" ]]; then
    echo "== Downloading llvm-mingw..."
    curl --fail --location --silent --show-error --output "$tc/llvm-mingw.tar.xz" \
        "https://github.com/mstorsjo/llvm-mingw/releases/download/${llvm_mingw_release}/${llvm_mingw_name}.tar.xz"
    rm -rf "$tc/llvm-mingw" && mkdir -p "$tc/llvm-mingw"
    tar -xf "$tc/llvm-mingw.tar.xz" -C "$tc/llvm-mingw" --strip-components 1
    rm "$tc/llvm-mingw.tar.xz"
fi

# CommonLibSSE-NG, at the version skse/CMakeLists.txt asks for
commonlib_tag="$(sed -n 's/^set(COMMONLIBSSE_NG_TAG "\([^"]*\)".*/\1/p' "$repo/skse/CMakeLists.txt")"
[[ -n "$commonlib_tag" ]] || fail "Could not read COMMONLIBSSE_NG_TAG from skse/CMakeLists.txt"
commonlib="$tc/commonlib"
if [[ "$(git -C "$commonlib" rev-parse HEAD 2>/dev/null || true)" != "$commonlib_tag" ]]; then
    echo "== Fetching CommonLibSSE-NG $commonlib_tag..."
    [[ -d "$commonlib/.git" ]] || git clone --quiet https://github.com/alandtse/CommonLibVR.git "$commonlib"
    git -C "$commonlib" fetch --quiet --tags origin
    git -C "$commonlib" -c advice.detachedHead=false checkout --quiet "$commonlib_tag"
fi

export VCPKG_ROOT="$tc/vcpkg" XWIN_SYSROOT="$tc/xwin-out" LLVM_MINGW_BIN="$tc/llvm-mingw/bin"
export VCPKG_DEFAULT_BINARY_CACHE="$tc/vcpkg-binary-cache" VCPKG_DISABLE_METRICS=1
export WINEPREFIX="${WINEPREFIX:-$tc/wineprefix}" WINEDEBUG="${WINEDEBUG:--all}"
mkdir -p "$VCPKG_DEFAULT_BINARY_CACHE"
cross="$commonlib/examples/linux-cross-compile"

# (-ffile-prefix-map keeps the paths of this machine out of the .dll files: source file names are used in log messages)
echo "== Configuring (the first run builds the libraries the plugins use, which takes a while)..."
cmake -S "$repo/skse" -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" \
    -DVCPKG_CHAINLOAD_TOOLCHAIN_FILE="$commonlib/cmake/toolchain-linux-clangcl.cmake" \
    -DVCPKG_TARGET_TRIPLET=x64-windows-clangcl \
    -DVCPKG_OVERLAY_TRIPLETS="$cross/custom-triplets" \
    -DVCPKG_OVERLAY_PORTS="$cross/custom-ports" \
    -DXWIN_SYSROOT="$XWIN_SYSROOT" \
    -DFETCHCONTENT_SOURCE_DIR_COMMONLIBSSE_NG="$commonlib" \
    -DCMAKE_CXX_FLAGS="/permissive- /bigobj /clang:-ffile-prefix-map=$repo=. -Wno-overloaded-virtual -Wno-delete-non-abstract-non-virtual-dtor -Wno-inconsistent-missing-override -Wno-reinterpret-base-class -Wno-nonportable-include-path -Wno-deprecated-copy-with-user-provided-copy -Wno-invalid-offsetof -Wno-switch -Wno-unused-command-line-argument -Wno-deprecated-volatile -Wno-unused-private-field"

echo "== Building..."
cmake --build "$build_dir"

mkdir -p "$repo/dist/skse"
cp "$build_dir"/plugins/*.dll "$repo/dist/skse/"
echo "Done:"
ls -l "$repo/dist/skse"/*.dll
