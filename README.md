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
- **Vision works in Skyrim under Proton**: with `Vision` -> `Use Game Screenshots` enabled, the game takes the screenshot itself (Mantella presses the Print Screen key and reads the file the game saves), instead of Mantella trying to capture the game window from the outside.
- **Linux paths.** Paths in the log and the web UI are shown as they are on your system (eg `/home/you/...` and not `C:\users\steamuser\...`), and path settings accept Linux paths.
- **The settings page opens in your own browser** when Mantella starts (it is handed to the desktop's default browser instead of looking for one inside the Wine prefix).

## Conversations
- NPCs stay in character when your input is unclear, and no longer talk about microphones or speech recognition.
- Conversations that went wrong because of mishearings are not recorded as such in the NPC's memory.
- **Name correction** for Moonshine: words that sound like the name of an NPC in the conversation are replaced with that name (eg "roll off" becomes "Ralof"). Can be turned off under `Speech-to-Text` -> `Name Correction`.
- **Interrupting NPCs works with push-to-talk**: press the push-to-talk key while an NPC is speaking to cut in. The NPC is told that they were interrupted, and reacts to it in character (a self-important NPC may take offence, a follower will not mind). Requires `Speech-to-Text` -> `Allow Interruption` and `Push-to-Talk` in the Mantella UI. With the Mantella v0.14 mod the interrupted voiceline stops once the NPC starts to respond to you; cutting it off instantly needs newer mod scripts (`Instant Interruption`).
- A line that ends in an ellipsis ("I wonder...") is treated as a finished sentence, so that in conversations with several NPCs the next speaker's line is no longer read out by the previous speaker. An ellipsis in the middle of a line is still a pause.
- When an NPC's memories no longer fit into the prompt, the oldest memories are left out first, instead of all of them.
- Changing a setting during a conversation no longer ends the conversation. The change is applied once the conversation is over, and the UI says so.
- A failing LLM no longer leaves Mantella retrying a conversation summary forever, and a failed attempt to condense an NPC's memories no longer hides the memories they already have.

## Language models
- **Anthropic service**: connect to Claude directly (`Large Language Model` -> `LLM Service` -> `Anthropic`), with prompt caching applied the way the Claude API expects it. Put your Anthropic API key in `GPT_SECRET_KEY.txt` (or under `"Anthropic"` in `secret_keys.json`).
- Prompt caching for Claude via OpenRouter now also caches the system prompt separately and covers requests that follow a tool call.
- Claude models have a known context size, also when the model list has not been loaded.
- Requests to the LLM time out (`Large Language Model` -> `Response Timeout`, 60 seconds by default) instead of leaving a conversation hanging, and are retried quietly on rate limits and server errors.

## Web UI
- **NPC Memories** tab to view, edit and delete what NPCs remember.
- **Console** below the settings, with errors in red and warnings in yellow.
- **Restart Mantella** and **Stop Mantella** buttons.
- The UI stays responsive while Mantella waits for you to speak.
- Folders of TTS services that are not in use (or that run on another machine) are no longer flagged as errors, and the options of a local XTTS server are hidden while the XTTS URL points to another machine.
- `Other` -> `Save Console Logs` saves the console output of each run to its own file (`My Games/Mantella/logs`), for debugging.

> The default prompts have changed. Prompts are stored in your `config.ini`, so to get the new versions on an existing installation, click `Default` next to the prompts in the `Prompts` tab of the Mantella UI (Skyrim Prompt, Skyrim Multi-NPC Prompt, Memory Prompt, Resummarize Prompt).

# Installation

The releases of this fork replace the Mantella mod from Nexus Mods: the archive contains the game plugin, scripts, the Mantella software, the Piper text-to-speech program and the Moonshine speech-to-text model. Two things are not included (yet):

- **Piper voice models** (4 GB). These are part of the [Mantella](https://www.nexusmods.com/skyrimspecialedition/mods/98631) download on Nexus Mods.
- **The SKSE plugins** (`MantellaDialogue.dll`, `MantellaLauncher.dll`, `MantellaSubtitles.dll`, `SKSE_HTTP.dll`). On Skyrim 1.7.99 and newer, use the plugins from the [Mantella 1.7.104 SKSE Plugin Fix](https://www.nexusmods.com/skyrimspecialedition/mods/195872). On older versions of the game, use the ones in the Mantella download.

Steps (Mod Organizer 2):

1. Install the requirements of Mantella: [SKSE64](https://www.nexusmods.com/skyrimspecialedition/mods/30379), [Address Library for SKSE Plugins](https://www.nexusmods.com/skyrimspecialedition/mods/32444), [SkyUI](https://www.nexusmods.com/skyrimspecialedition/mods/12604), [UIExtensions](https://www.nexusmods.com/skyrimspecialedition/mods/17561) and the FonixData file.
2. Download `Mantella-Skyrim-<version>.zip` from the [latest release](../../releases/latest) and install it ("Install a new mod from an archive").
3. Voices: create an empty mod (eg "Mantella Voices") and copy the folder `SKSE/Plugins/MantellaSoftware/piper/models` from the Mantella download on Nexus Mods into it, keeping that folder structure.
4. SKSE plugins: keep the SKSE Plugin Fix installed (or, on older game versions, copy the four `.dll` files from `SKSE/Plugins` of the Mantella download into a mod of their own).
5. Paste your LLM secret key into `GPT_SECRET_KEY.txt` in the installed mod's folder.
6. Disable the Mantella mod from Nexus Mods. Its files are no longer needed.

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

## Repository layout

| Folder | Contents |
|---|---|
| `src/`, `data/`, `main.py` | The Mantella software (Python), built into `Mantella.exe` |
| `mod/` | The Skyrim mod: `Mantella.esp`, Papyrus scripts (`Scripts/Source/*.psc` and their compiled `Scripts/*.pex`), voice files and FaceFXWrapper. Laid out like the game's `Data` folder. Based on [Mantella Spell](https://github.com/art-from-the-machine/Mantella-Spell) v0.14 |
| `third_party/` | Programs and models that ship with the mod as they are: the Piper runtime (without voices) and the Moonshine model |
| `packaging/` | Scripts that build `Mantella.exe` and assemble the mod archive |

The compiled scripts in `mod/Scripts` have to be kept in step with their sources by hand: when a `.psc` file is changed, its `.pex` has to be recompiled (with the Papyrus compiler of the Creation Kit, or [Pyro](https://github.com/fireundubh/pyro) using `skyrimse.ppj` of Mantella Spell) and committed along with it.

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

# Licenses and attributions
Mantella is created by [art-from-the-machine](https://github.com/art-from-the-machine) and its contributors. The Mantella software (this repo, excluding the folders below) is licensed under the [GNU Affero General Public License v3](LICENSE), as it is upstream.

- `mod/`: [Mantella Spell](https://github.com/art-from-the-machine/Mantella-Spell) by art-from-the-machine, MIT License (`mod/LICENSE.md`). `mod/Sound/Voice/Processing/FaceFXWrapper.exe` is [FaceFXWrapper](https://github.com/Nukem9/FaceFXWrapper) by Nukem, MIT License.
- `third_party/piper`: [Piper](https://github.com/rhasspy/piper) by Michael Hansen, MIT License. It includes [eSpeak NG](https://github.com/espeak-ng/espeak-ng), GPL v3.
- `third_party/moonshine`: [Moonshine](https://github.com/usefulsensors/moonshine) by Useful Sensors, MIT License.

Mantella uses material from the "[Skyrim: Characters](https://elderscrolls.fandom.com/wiki/Category:Skyrim:_Characters)" articles on the [Elder Scrolls wiki](https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki) at [Fandom](https://www.fandom.com/) and is licensed under the [Creative Commons Attribution-Share Alike License](https://creativecommons.org/licenses/by-sa/3.0/).
