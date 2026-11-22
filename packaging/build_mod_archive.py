"""Builds Mantella.exe and packages it as a mod archive (.zip) that can be installed with a mod manager (Mod Organizer 2 / Vortex).

The archive only contains the Mantella software (SKSE/Plugins/MantellaSoftware). It is installed on top of the Mantella mod
from Nexus Mods, which provides the game plugin, scripts and SKSE plugins: in Mod Organizer 2, place it below (after) Mantella
so that it overwrites the software that ships with the mod.

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

# Files and folders that Mantella expects next to Mantella.exe, relative to the project root
RUNTIME_FILES = ['data', 'src/ui/style.css', 'Mantella.ico', 'version.json', 'LICENSE']


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


def create_archive(software_folder: Path, archive_path: Path) -> int:
    archive_path.unlink(missing_ok=True)
    file_count = 0
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(software_folder.rglob('*')):
            if file.is_file():
                archive.write(file, (SOFTWARE_FOLDER_IN_MOD / file.relative_to(software_folder)).as_posix())
                file_count += 1
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
