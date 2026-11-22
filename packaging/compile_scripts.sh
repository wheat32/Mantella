#!/usr/bin/env bash
# Compiles the Papyrus scripts of the mod (mod/Scripts/Source/*.psc -> mod/Scripts/*.pex) on Linux,
# using the Papyrus compiler of the Creation Kit under Wine.
#
# Needed on this machine:
#   - wine with wine-mono (the compiler is a .NET program), git, bsdtar or unrar, python3 or uv
#   - the Creation Kit (free on Steam): provides the compiler and the game's own script sources
#   - Skyrim Special Edition with SKSE64 installed, including its script sources (Data/Scripts/Source)
#   - the UIExtensions mod (its archive contains the script sources Mantella calls)
#
# Paths can be set through environment variables (defaults in brackets):
#   CREATION_KIT_DIR  folder that contains "Papyrus Compiler" and Data/Scripts.rar or Data/Scripts.zip
#   SKYRIM_DIR        Skyrim Special Edition folder (for the SKSE64 script sources)
#   UIEXTENSIONS_BSA  path to UIExtensions.bsa
#
# Usage: packaging/compile_scripts.sh [script names without extension ...]   (default: all scripts)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
steam_common="${STEAM_COMMON_DIR:-$HOME/.local/share/Steam/steamapps/common}"
ck_dir="${CREATION_KIT_DIR:-$steam_common/skyrim}"
skyrim_dir="${SKYRIM_DIR:-$steam_common/Skyrim Special Edition}"
uiextensions_bsa="${UIEXTENSIONS_BSA:-}"

deps="$repo/build/papyrus"        # downloaded / extracted dependencies (not committed)
source_dir="$repo/mod/Scripts/Source"
output_dir="$repo/mod/Scripts"
compiler="$ck_dir/Papyrus Compiler/PapyrusCompiler.exe"

fail() { echo "Error: $*" >&2; exit 1; }
[[ -f "$compiler" ]] || fail "Papyrus compiler not found at '$compiler'. Install the Creation Kit and set CREATION_KIT_DIR."
[[ -d "$skyrim_dir/Data/Scripts/Source" ]] || fail "SKSE64 script sources not found in '$skyrim_dir/Data/Scripts/Source'. Set SKYRIM_DIR."
command -v wine >/dev/null || fail "wine is not installed."

mkdir -p "$deps"

# 1. The game's own script sources, from the Creation Kit
if [[ ! -d "$deps/vanilla/Scripts/Source" ]]; then
    echo "Extracting the game's script sources from the Creation Kit..."
    mkdir -p "$deps/vanilla"
    if [[ -f "$ck_dir/Data/Scripts.zip" ]]; then
        (cd "$deps/vanilla" && bsdtar -xf "$ck_dir/Data/Scripts.zip")
    elif [[ -f "$ck_dir/Data/Scripts.rar" ]]; then
        (cd "$deps/vanilla" && { bsdtar -xf "$ck_dir/Data/Scripts.rar" 2>/dev/null || unrar x -inul "$ck_dir/Data/Scripts.rar"; })
    else
        fail "Neither Data/Scripts.zip nor Data/Scripts.rar found in '$ck_dir'."
    fi
fi
vanilla_sources="$(find "$deps/vanilla" -type d -ipath '*scripts/source' -o -type d -ipath '*source/scripts' | head -n 1)"
[[ -n "$vanilla_sources" ]] || fail "Could not find the extracted script sources in '$deps/vanilla'."

# 2. SkyUI script sources (for the mod configuration menu), plus declarations of the functions SkyUI SE added since
if [[ ! -d "$deps/skyui" ]]; then
    echo "Fetching the SkyUI script sources..."
    git clone --quiet --depth 1 https://github.com/schlangster/skyui.git "$deps/skyui"
fi
mkdir -p "$deps/skyui_se"
cat "$deps/skyui/dist/Data/Scripts/Source/SKI_ConfigBase.psc" "$repo/packaging/papyrus/SKI_ConfigBase_SE_additions.psc" > "$deps/skyui_se/SKI_ConfigBase.psc"

# 3. UIExtensions script sources, from the archive of the installed mod
if [[ ! -f "$deps/uiextensions/uiextensions.psc" ]]; then
    [[ -f "$uiextensions_bsa" ]] || fail "Set UIEXTENSIONS_BSA to the path of UIExtensions.bsa (in the folder of the UIExtensions mod)."
    echo "Extracting the UIExtensions script sources..."
    if command -v uv >/dev/null; then
        uv run --quiet --no-project --with lz4 python "$repo/packaging/papyrus/bsa_extract.py" "$uiextensions_bsa" ".psc" "$deps/uiextensions"
    else
        python3 "$repo/packaging/papyrus/bsa_extract.py" "$uiextensions_bsa" ".psc" "$deps/uiextensions"   # needs the lz4 package
    fi
fi

# 4. Compile
to_wine_path() { printf 'Z:%s' "${1//\//\\}"; }
export WINEPREFIX="${WINEPREFIX:-$deps/wineprefix}" WINEDEBUG="${WINEDEBUG:--all}"
imports="$(to_wine_path "$source_dir");$(to_wine_path "$skyrim_dir/Data/Scripts/Source");$(to_wine_path "$deps/skyui_se");$(to_wine_path "$deps/skyui/dist/Data/Scripts/Source");$(to_wine_path "$deps/uiextensions");$(to_wine_path "$vanilla_sources")"
compiled="$deps/out"
rm -rf "$compiled" && mkdir -p "$compiled"
log="$deps/compile.log"

if [[ $# -eq 0 ]]; then
    echo "Compiling all scripts in mod/Scripts/Source..."
    wine "$compiler" "$(to_wine_path "$source_dir")" -all -f="TESV_Papyrus_Flags.flg" -i="$imports" -o="$(to_wine_path "$compiled")" > "$log" 2>&1 || true
    expected="$(find "$source_dir" -maxdepth 1 -iname '*.psc' | wc -l)"
else
    : > "$log"
    for script in "$@"; do
        echo "Compiling ${script%.psc}..."
        wine "$compiler" "${script%.psc}.psc" -f="TESV_Papyrus_Flags.flg" -i="$imports" -o="$(to_wine_path "$compiled")" >> "$log" 2>&1 || true
    done
    expected=$#
fi

count="$(find "$compiled" -maxdepth 1 -iname '*.pex' | wc -l)"
if [[ "$count" -ne "$expected" ]]; then
    grep -E '\.psc\([0-9]+,[0-9]+\)|^Failed on|error' "$log" | sed 's/^.*\\Source\\//' | sort -u | head -n 40 >&2
    fail "$count of $expected scripts compiled. Full output: $log"
fi

# 5. Remove the user and computer name the compiler writes into each script, then put the scripts in place
python3 "$repo/packaging/anonymize_pex.py" "$compiled"
cp "$compiled"/*.pex "$output_dir/"
echo "Done: $count compiled scripts written to mod/Scripts"
