"""Builds Mantella.exe and packages it, together with the Skyrim mod files in this repo, as a mod archive (.zip)
that can be installed with a mod manager (Mod Organizer 2 / Vortex) in place of the Mantella mod from Nexus Mods.

The archive contains:
    - the game plugin, scripts and voice files (mod/)
    - the Mantella software (SKSE/Plugins/MantellaSoftware), with the Piper runtime and the Moonshine speech-to-text model (third_party/)

Not included: the Piper voice models (see the README), and the SKSE plugins (.dll files).

Usage (on Windows, or under Wine, with the packages from requirements.txt and PyInstaller installed):
    python packaging/build_mod_archive.py
    python packaging/build_mod_archive.py --skip-build   # only re-package an existing dist/Mantella build
"""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_FOLDER = PROJECT_ROOT / 'dist'
BUILD_FOLDER = PROJECT_ROOT / 'build'
SOFTWARE_FOLDER_IN_MOD = Path('SKSE') / 'Plugins' / 'MantellaSoftware'

MOD_FOLDER = PROJECT_ROOT / 'mod'
SKSE_PLUGINS_FOLDER = DIST_FOLDER / 'skse'
SKSE_PLUGINS = ['MantellaDialogue.dll', 'MantellaLauncher.dll', 'MantellaSubtitles.dll', 'SKSE_HTTP.dll']
THIRD_PARTY_FOLDER = PROJECT_ROOT / 'third_party'

# Files and folders that Mantella expects next to Mantella.exe, relative to the project root
RUNTIME_FILES = ['data', 'src/ui/style.css', 'Mantella.ico', 'version.json', 'LICENSE', 'custom_user_folder.ini']
# Third-party folders that are copied next to Mantella.exe as they are
THIRD_PARTY_RUNTIME = ['piper', 'moonshine']
# Parts of mod/ that are only needed for development
MOD_FILES_NOT_PACKAGED = ('Spriggit_data',)
# Files that must never end up in an archive, wherever they are found
NEVER_PACKAGED = ('GPT_SECRET_KEY.txt', 'secret_keys.json', 'meta.ini', 'config.ini', 'logging.log')


def get_version() -> str:
    with open(PROJECT_ROOT / 'version.json', 'r', encoding='utf-8') as f:
        return json.load(f)['app_version']


def build_executable():
    for folder in (DIST_FOLDER / 'Mantella', BUILD_FOLDER):
        shutil.rmtree(folder, ignore_errors=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(DIST_FOLDER), '--workpath', str(BUILD_FOLDER),
                    str(PROJECT_ROOT / 'packaging' / 'Mantella.spec')], cwd=PROJECT_ROOT, check=True)


def copy_runtime_files(software_folder: Path):
    for relative_path in RUNTIME_FILES:
        source = PROJECT_ROOT / relative_path
        destination = software_folder / relative_path
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', 'tmp'))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def add_folder(archive: zipfile.ZipFile, folder: Path, folder_in_archive: Path, exclude: tuple[str, ...] = ()) -> int:
    file_count = 0
    for file in sorted(folder.rglob('*')):
        relative_path = file.relative_to(folder)
        if not file.is_file() or any(part in exclude for part in relative_path.parts) or file.name in NEVER_PACKAGED:
            continue
        archive.write(file, (folder_in_archive / relative_path).as_posix())
        file_count += 1
    return file_count


def create_archive(software_folder: Path, archive_path: Path) -> int:
    archive_path.unlink(missing_ok=True)
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        # The game plugin, scripts and voice files, laid out like the game's Data folder
        file_count = add_folder(archive, MOD_FOLDER, Path('.'), exclude=MOD_FILES_NOT_PACKAGED)
        # The SKSE plugins, if they have been built (see skse/README.md)
        plugins = sorted(SKSE_PLUGINS_FOLDER.glob('*.dll')) if SKSE_PLUGINS_FOLDER.is_dir() else []
        for plugin in plugins:
            archive.write(plugin, (Path('SKSE') / 'Plugins' / plugin.name).as_posix())
        file_count += len(plugins)
        missing = sorted(set(SKSE_PLUGINS) - {plugin.name for plugin in plugins})
        if missing:
            print(f'Note: the archive does not contain these SKSE plugins, as they were not found in {SKSE_PLUGINS_FOLDER}: {", ".join(missing)}')
        # An empty placeholder for the user's secret key. A key file is never taken from disk
        archive.writestr('GPT_SECRET_KEY.txt', '')
        file_count += 1
        # The Mantella software, and the third-party programs / models it runs
        file_count += add_folder(archive, software_folder, SOFTWARE_FOLDER_IN_MOD)
        for name in THIRD_PARTY_RUNTIME:
            file_count += add_folder(archive, THIRD_PARTY_FOLDER / name, SOFTWARE_FOLDER_IN_MOD / name)
    return file_count


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--skip-build', action='store_true', help='Package the existing build in dist/Mantella instead of running PyInstaller')
    parser.add_argument('--output', type=Path, default=None, help='Path of the archive to create (default: dist/Mantella-Skyrim-<version>.zip)')
    args = parser.parse_args()

    software_folder = DIST_FOLDER / 'Mantella'
    if not args.skip_build:
        build_executable()
    if not (software_folder / 'Mantella.exe').exists():
        sys.exit(f'Could not find {software_folder / "Mantella.exe"}. Run this script without --skip-build on Windows first.')

    copy_runtime_files(software_folder)
    archive_path = args.output or DIST_FOLDER / f'Mantella-Skyrim-{get_version()}.zip'
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = create_archive(software_folder, archive_path)
    print(f'Created {archive_path} ({file_count} files, {archive_path.stat().st_size / 1_000_000:.1f} MB)')


if __name__ == '__main__':
    main()
