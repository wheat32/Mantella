"""Finds the Piper voice models on this machine, and downloads the ones that are missing.

The voices (about 63 MB each, 4 GB in total for Skyrim) are not part of the mod archive. They are downloaded from the
releases of a GitHub repo: a voice is fetched the moment an NPC needs it, and the rest follow in the background.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path
import requests
import src.utils as utils
from src.wine import to_host_path

logger = utils.get_logger()


class PiperVoiceStore:
    MANIFEST_NAME = 'manifest.json'
    LOG_LEVEL = 29 # TTS

    def __init__(self, bundled_folder: Path, download_folder: Path, base_url: str | None) -> None:
        """
        Args:
            bundled_folder: Where voices that come with the installation are (eg installed by hand or by another mod). These are never changed
            download_folder: Where downloaded voices are saved. Kept outside of the mod folder, so that updating the mod does not remove them
            base_url: The URL the voices (and their manifest.json) are downloaded from, or None / '' to not download anything
        """
        self.__bundled_folder = Path(bundled_folder)
        self.__download_folder = Path(download_folder)
        self.__base_url = (base_url or '').strip().rstrip('/')
        self.__manifest: dict[str, dict] = {}
        self.__file_locks: dict[str, threading.Lock] = {}
        self.__locks_lock = threading.Lock()
        self.__background_thread: threading.Thread | None = None
        self.__stop_background = threading.Event()
        if self.__base_url:
            self.__manifest = self.__load_manifest()

    @property
    def can_download(self) -> bool:
        return bool(self.__base_url) and bool(self.__manifest)

    @property
    def download_folder(self) -> Path:
        return self.__download_folder

    # ------------------------------------------------------------------ lookup

    def get_available_voices(self) -> list[str]:
        """The names of all voices that are on this machine or can be downloaded"""
        voices = set()
        for folder in (self.__bundled_folder, self.__download_folder):
            if folder.is_dir():
                voices.update(f[:-len('.onnx')] for f in os.listdir(folder) if f.endswith('.onnx'))
        voices.update(name[:-len('.onnx')] for name in self.__manifest if name.endswith('.onnx'))
        return sorted(voices)

    def get_missing_voices(self) -> list[str]:
        return [voice for voice in self.get_available_voices() if self.__find_local(voice) is None]

    def __find_local(self, voice: str) -> Path | None:
        for folder in (self.__bundled_folder, self.__download_folder):
            model, settings = folder / f'{voice}.onnx', folder / f'{voice}.onnx.json'
            if model.is_file() and settings.is_file() and model.stat().st_size > 0:
                return model
        return None

    def get_model_path(self, voice: str) -> Path | None:
        """Returns the path of a voice's model, downloading the voice first if it is not on this machine yet

        Returns:
            Path | None: the path of the .onnx file, or None if the voice does not exist or could not be downloaded
        """
        local = self.__find_local(voice)
        if local:
            return local
        if not self.can_download or f'{voice}.onnx' not in self.__manifest:
            return None
        size_mb = self.__manifest[f'{voice}.onnx'].get('size', 0) / 1_000_000
        logger.log(self.LOG_LEVEL, f"Downloading the voice '{voice}' ({size_mb:.0f} MB). This only happens the first time a voice is used...")
        if self.__download_voice(voice):
            return self.__find_local(voice)
        return None

    # ------------------------------------------------------------------ downloads

    def download_missing_in_background(self) -> None:
        """Downloads all voices that are not on this machine yet, one after the other, without holding anything up"""
        if not self.can_download or (self.__background_thread and self.__background_thread.is_alive()):
            return
        missing = self.get_missing_voices()
        if not missing:
            return
        total_gb = sum(self.__manifest.get(f'{voice}.onnx', {}).get('size', 0) for voice in missing) / 1_000_000_000
        logger.log(self.LOG_LEVEL, f'Downloading {len(missing)} Piper voice(s) ({total_gb:.1f} GB) in the background to {to_host_path(str(self.__download_folder))}. Conversations can be started in the meantime: the voice of an NPC is downloaded first when it is needed.')
        self.__stop_background.clear()
        self.__background_thread = threading.Thread(target=self.__download_all, args=(missing,), daemon=True)
        self.__background_thread.start()

    def stop_background_download(self) -> None:
        self.__stop_background.set()

    def __download_all(self, voices: list[str]) -> None:
        downloaded = 0
        for voice in voices:
            if self.__stop_background.is_set():
                return
            if self.__find_local(voice) is None:
                if not self.__download_voice(voice):
                    time.sleep(5) # eg no connection: do not hammer the server
                    continue
            downloaded += 1
        if downloaded == len(voices):
            logger.log(self.LOG_LEVEL, 'All Piper voices have been downloaded')
        else:
            logger.warning(f'{len(voices) - downloaded} Piper voice(s) could not be downloaded. They will be tried again the next time Mantella starts, or when they are needed')

    def __get_lock(self, name: str) -> threading.Lock:
        with self.__locks_lock:
            return self.__file_locks.setdefault(name, threading.Lock())

    def __download_voice(self, voice: str) -> bool:
        # the small settings file first, so that a model is never present without it
        return self.__download_file(f'{voice}.onnx.json') and self.__download_file(f'{voice}.onnx')

    def __download_file(self, name: str) -> bool:
        """Downloads a file listed in the manifest, checking its size and checksum. Safe to call from several threads"""
        expected = self.__manifest.get(name)
        if not expected:
            return False
        target = self.__download_folder / name
        with self.__get_lock(name):
            if target.is_file() and target.stat().st_size == expected.get('size'):
                return True
            partial = self.__download_folder / f'{name}.part'
            try:
                self.__download_folder.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with requests.get(f'{self.__base_url}/{name}', stream=True, timeout=(10, 60)) as response:
                    response.raise_for_status()
                    with open(partial, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            f.write(chunk)
                            digest.update(chunk)
                if partial.stat().st_size != expected.get('size') or (expected.get('sha256') and digest.hexdigest() != expected['sha256']):
                    raise IOError('the downloaded file is incomplete or damaged')
                os.replace(partial, target)
                return True
            except Exception as e:
                logger.warning(f'Could not download {name} from {self.__base_url}: {e}')
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
                return False

    def __load_manifest(self) -> dict[str, dict]:
        """Fetches the list of downloadable files. A copy is kept on disk for when there is no connection"""
        cached = self.__download_folder / self.MANIFEST_NAME
        try:
            response = requests.get(f'{self.__base_url}/{self.MANIFEST_NAME}', timeout=(5, 15))
            response.raise_for_status()
            files = response.json().get('files', {})
            if not isinstance(files, dict) or not files:
                raise ValueError('the manifest lists no files')
            try:
                self.__download_folder.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps({'format': 1, 'files': files}), encoding='utf-8')
            except OSError:
                pass
            return files
        except Exception as e:
            try:
                files = json.loads(cached.read_text(encoding='utf-8')).get('files', {})
                if files:
                    return files
            except (OSError, ValueError):
                pass
            logger.debug(f'Could not get the list of downloadable Piper voices from {self.__base_url}: {e}')
            return {}
