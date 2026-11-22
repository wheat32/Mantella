# Mantella (Skyrim fork)

<img src="./img/mantella_logo_github.png" align="right" alt="Mantella logo" width="150" height="auto">

> Bring Skyrim NPCs to life with AI

This is a fork of [Mantella](https://github.com/art-from-the-machine/Mantella), the Skyrim and Fallout 4 mod which allows you to naturally speak to NPCs using speech-to-text ([Moonshine](https://github.com/usefulsensors/moonshine) / [Whisper](https://github.com/openai/whisper)), LLMs, and text-to-speech ([Piper](https://github.com/rhasspy/piper) / [xVASynth](https://github.com/DanRuta/xVA-Synth) / [XTTS](https://www.nexusmods.com/skyrimspecialedition/mods/113445)).

The fork focuses on **Skyrim Special Edition**, and on making Mantella work well on **Linux (Steam Proton / Wine)**. It still runs on Windows, and the Fallout 4 code is still there, but only Skyrim is tested.

For general documentation on Mantella (requirements, settings, troubleshooting), see the [Mantella docs](https://art-from-the-machine.github.io/Mantella/index.html).

# What is different

## Linux (Proton / Wine)
- **Whisper no longer crashes Mantella.** Intel's OpenMP library aborts under Wine when it inspects the CPU layout. The `KMP_TOPOLOGY_METHOD=flat KMP_AFFINITY=disabled` workaround is now applied by Mantella itself, so it does not have to be added to the game's Steam launch options.
- **Speech-to-text models download correctly.** Hugging Face's downloader creates symlinks, which end up as empty files under Wine. Models are now downloaded as regular files, empty files left behind by earlier downloads are removed and downloaded again, and an empty local model produces a clear error instead of a crash.
- **Lip sync works.** FaceFXWrapper is called directly with absolute paths (previously through a `.bat` file written into the mod folder), and its output and exit code are logged when it fails.
- **Voicelines with typographic characters no longer silence the NPC.** Voiceline files are saved under plain ASCII names.
- **Black screen captures are skipped** (Vision), so that NPCs do not comment on a "black screen".
- **Linux paths.** Paths in the log and the web UI are shown as they are on your system (eg `/home/you/...` and not `C:\users\steamuser\...`), and path settings accept Linux paths.

## Conversations
- NPCs stay in character when your input is unclear, and no longer talk about microphones or speech recognition.
- Conversations that went wrong because of mishearings are not recorded as such in the NPC's memory.
- **Name correction** for Moonshine: words that sound like the name of an NPC in the conversation are replaced with that name (eg "roll off" becomes "Ralof"). Can be turned off under `Speech-to-Text` -> `Name Correction`.
- Changing a setting during a conversation no longer ends the conversation. The change is applied once the conversation is over.
- A failing LLM no longer leaves Mantella retrying a conversation summary forever, and a failed attempt to condense an NPC's memories no longer hides the memories they already have.

## Web UI
- **NPC Memories** tab to view, edit and delete what NPCs remember.
- **Console** below the settings, with errors in red and warnings in yellow.
- **Restart Mantella** and **Stop Mantella** buttons.
- The UI stays responsive while Mantella waits for you to speak.
- Folders of TTS services that are not in use (or that run on another machine) are no longer flagged as errors.

> The default prompts have changed. Prompts are stored in your `config.ini`, so to get the new versions on an existing installation, click `Default` next to the prompts in the `Prompts` tab of the Mantella UI (Skyrim Prompt, Skyrim Multi-NPC Prompt, Memory Prompt, Resummarize Prompt).

# Installation

The releases of this fork contain the Mantella software only (`Mantella.exe` and its files). The game plugin, scripts and SKSE plugins come from the original mod.

1. Install [Mantella](https://www.nexusmods.com/skyrimspecialedition/mods/98631) from Nexus Mods and its requirements with your mod manager.
2. Download `Mantella-Skyrim-<version>.zip` from the [latest release](../../releases/latest) and install it as a separate mod ("Install a new mod from an archive" in Mod Organizer 2).
3. Let it overwrite Mantella: in Mod Organizer 2, place it below Mantella in the mod list. In Vortex, set it to load after Mantella.

To go back to the original software, disable or remove the mod.

# Development

Mantella requires Python 3.11.

```bash
git clone https://github.com/wheat32/Mantella.git
cd Mantella
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r tests/requirements-ci.txt -r tests/requirements-test.txt
```

On Windows, use `py -3.11 -m venv .venv`, `.\.venv\Scripts\Activate` and `pip install -r requirements.txt`.

## Tests

```bash
pytest -q -m "not requires_audio and not requires_external_exe and not requires_llm"
```

## Building a mod archive to test with

`Mantella.exe` is a Windows program (on Linux it is run by Proton, alongside the game), so it has to be built on Windows. The easiest way is to let GitHub Actions build it:

```bash
packaging/get_test_build.sh
```

This builds the branch you are on (it has to be pushed) and downloads `Mantella-Skyrim-<version>.zip` to `dist/`. Install the zip with Mod Organizer 2 as described under [Installation](#installation). The same build can be started by hand from the Actions tab of the repo (`CI` -> `Run workflow`); the zip is then attached to the run as the `mod-archive-ci` artifact.

On a Windows machine, the archive can be built locally:

```bash
pip install -r requirements.txt -r packaging/requirements-build.txt
python packaging/build_mod_archive.py
```

## Releases

Every push to `main` runs the tests, builds the mod archive and publishes it as a GitHub release tagged with the version in `version.json`. Pull requests to `main` and `dev` run the tests and build the archive without releasing it.

## Related repos
- Mantella (upstream): [https://github.com/art-from-the-machine/Mantella](https://github.com/art-from-the-machine/Mantella)
- Mantella Spell (the Skyrim mod that talks to this software): [https://github.com/art-from-the-machine/Mantella-Spell](https://github.com/art-from-the-machine/Mantella-Spell)

# Attributions
Mantella is created by [art-from-the-machine](https://github.com/art-from-the-machine) and its contributors.

Mantella uses material from the "[Skyrim: Characters](https://elderscrolls.fandom.com/wiki/Category:Skyrim:_Characters)" articles on the [Elder Scrolls wiki](https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki) at [Fandom](https://www.fandom.com/) and is licensed under the [Creative Commons Attribution-Share Alike License](https://creativecommons.org/licenses/by-sa/3.0/).
