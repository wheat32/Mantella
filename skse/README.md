# SKSE plugins

The four SKSE plugins (`.dll` files) the Mantella mod needs, built from source against [CommonLibSSE-NG](https://github.com/alandtse/CommonLibVR) 12.1.0, which supports the Address Library format of Skyrim 1.7.99 and newer.

| Plugin | What it does | Source | Version |
|---|---|---|---|
| `MantellaLauncher` | Starts `Mantella.exe` with the game | [art-from-the-machine/Mantella-SKSE-Launcher](https://github.com/art-from-the-machine/Mantella-SKSE-Launcher) | `a7fdb92` |
| `MantellaDialogue` | Passes vanilla dialogue to Mantella | [mikastamm/mantella-vanilla-dialogue](https://github.com/mikastamm/mantella-vanilla-dialogue) | `4c5d9c5` (1.0.2) |
| `MantellaSubtitles` | Shows subtitles for generated voicelines | [swwu/Mantella-Subtitles-Plugin-NG](https://github.com/swwu/Mantella-Subtitles-Plugin-NG) | `053a814` |
| `SKSE_HTTP` | Lets the mod's scripts talk to `Mantella.exe` | [art-from-the-machine/SKSE_HTTP](https://github.com/art-from-the-machine/SKSE_HTTP), a fork of [Leidtier/SKSE_HTTP](https://github.com/Leidtier/SKSE_HTTP) | `7fba93e` |

The sources are unchanged copies of the versions above, each under the MIT License of its author (see the `LICENSE` file in each folder). CommonLibSSE-NG is licensed under GPL-3.0-or-later, so the compiled plugins, which link it statically, are distributed under the GPL-3.0-or-later as well.

## Building

The plugins are built by GitHub Actions (job `Build SKSE Plugins`) on Windows:

```
cmake -S skse -B build/skse -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows-static-md -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL
cmake --build build/skse
```

The `.dll` files end up in `build/skse/plugins`. `packaging/build_mod_archive.py` adds them to the mod archive when they are placed in `dist/skse`.

## After a game update

The plugins use the Address Library to find what they need in the game, so most game updates only need the Address Library mod to be updated. If the game reports that a plugin "must be recompiled for new address library", raise `COMMONLIBSSE_NG_TAG` in `CMakeLists.txt` to a release of CommonLibSSE-NG that supports the new version and rebuild.
