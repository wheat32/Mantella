# SKSE plugins

The four SKSE plugins (`.dll` files) the Mantella mod needs, built from source against [CommonLibSSE-NG](https://github.com/alandtse/CommonLibVR) 12.1.0, which supports the Address Library format of Skyrim 1.7.99 and newer.

| Plugin | What it does | Source | Version |
|---|---|---|---|
| `MantellaLauncher` | Starts `Mantella.exe` with the game | [art-from-the-machine/Mantella-SKSE-Launcher](https://github.com/art-from-the-machine/Mantella-SKSE-Launcher) | `a7fdb92` |
| `MantellaDialogue` | Passes vanilla dialogue to Mantella | [mikastamm/mantella-vanilla-dialogue](https://github.com/mikastamm/mantella-vanilla-dialogue) | `4c5d9c5` (1.0.2) |
| `MantellaSubtitles` | Shows subtitles for generated voicelines | [swwu/Mantella-Subtitles-Plugin-NG](https://github.com/swwu/Mantella-Subtitles-Plugin-NG) | `053a814` |
| `SKSE_HTTP` | Lets the mod's scripts talk to `Mantella.exe` | [art-from-the-machine/SKSE_HTTP](https://github.com/art-from-the-machine/SKSE_HTTP), a fork of [Leidtier/SKSE_HTTP](https://github.com/Leidtier/SKSE_HTTP) | `7fba93e` |

The sources are copies of the versions above, each under the MIT License of its author (see the `LICENSE` file in each folder), with these changes to build against CommonLibSSE-NG 12:

- `MantellaSubtitles/Papyrus.cpp`: two log messages pass the subtitle as `subtitle.c_str()` (the game's string type can no longer be logged directly).
- `SKSE_HTTP/plugin.cpp`: `GetUInt()` is now called `GetUnsignedInteger()`, and three `#include` lines use the exact file name and forward slashes so that they also resolve when building on Linux.
- `SKSE_HTTP` takes its HTTP library (cpr) from vcpkg instead of building it as part of the plugin.
- `SKSE_HTTP/plugin.cpp`: new function `GetNearbyActors`, which returns the actors around the player without the limit of 5 that the mod's alias based scan has.
- `MantellaLauncher/plugin.cpp`: waiting for a previous `Mantella.exe` to close is limited to 5 seconds instead of freezing the game if it does not, and what the launcher does is written to `MantellaLauncher.log`. Building with `MANTELLA_CAPTURE_OUTPUT` defined gives a diagnostic launcher that also writes the output of `Mantella.exe` to `MantellaExe.log`.

CommonLibSSE-NG is licensed under GPL-3.0-or-later, so the compiled plugins, which link it statically, are distributed under the GPL-3.0-or-later as well. The builds do not support Skyrim VR.

## Building

On Linux:

```bash
packaging/build_skse_plugins.sh
```

The first run sets up a Windows cross-compile toolchain under `build/skse-toolchain` (clang-cl, the Windows SDK via [xwin](https://github.com/Jake-Shadle/xwin), vcpkg), which takes a while and a few GB; see the top of the script for what it needs and downloads. The `.dll` files are written to `dist/skse`. As CommonLibSSE-NG's own guide puts it, a clean build proves the toolchain, not that the plugins behave in-game, so test them in the game.

On Windows (this is what the `Build SKSE Plugins` job of the GitHub workflows does):

```
cmake -S skse -B build/skse -A x64 -DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows-static-md -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL
cmake --build build/skse --config Release
```

The `.dll` files end up in `build/skse/plugins`. `packaging/build_mod_archive.py` adds the plugins to the mod archive when they are in `dist/skse`.

To try locally built plugins in the game, copy the four files from `dist/skse` into the `SKSE/Plugins` folder of a mod that is placed below Mantella in Mod Organizer 2.

## After a game update

The plugins use the Address Library to find what they need in the game, so most game updates only need the Address Library mod to be updated. If the game reports that a plugin "must be recompiled for new address library", raise `COMMONLIBSSE_NG_TAG` in `CMakeLists.txt` to a release of CommonLibSSE-NG that supports the new version and rebuild.
