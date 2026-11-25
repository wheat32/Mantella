"""What Mantella keeps about NPCs beyond their memories, per player character / world: the names that NPCs without a name of their
own gave themselves, and the NPCs that are traveling with the player (and why)."""
import json
import os
import re
from typing import Any
import src.utils as utils

logger = utils.get_logger()

RECORDS_FILE_NAME = 'npc_records.json'
MAX_NAME_LENGTH = 40


class NpcRecords:
    def __init__(self, conversations_folder: str, world_id: str) -> None:
        self.__conversations_folder: str = conversations_folder
        self.__world_id: str = world_id
        self.__path: str = os.path.join(conversations_folder, world_id, RECORDS_FILE_NAME) if conversations_folder and world_id else ''
        self.__records: dict[str, Any] = self.__load()

    def __load(self) -> dict[str, Any]:
        if not self.__path or not os.path.exists(self.__path):
            return {}
        try:
            with open(self.__path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            return records if isinstance(records, dict) else {}
        except (OSError, ValueError) as e:
            logger.warning(f'Could not read {self.__path}: {e}')
            return {}

    def __save(self) -> None:
        if not self.__path:
            return
        try:
            os.makedirs(os.path.dirname(self.__path), exist_ok=True)
            with open(self.__path, 'w', encoding='utf-8') as f:
                json.dump(self.__records, f, indent=4, ensure_ascii=False)
        except OSError as e:
            logger.warning(f'Could not save {self.__path}: {e}')

    def __section(self, name: str) -> dict[str, Any]:
        section = self.__records.get(name)
        if not isinstance(section, dict):
            section = {}
            self.__records[name] = section
        return section

    # --- names NPCs gave themselves

    @staticmethod
    def clean_name(name: Any) -> str:
        """The name as the LLM gave it, without quotes or anything around it. Empty if it is no usable name"""
        text = re.sub(r"[^\w' -]", '', str(name or '')).strip()
        text = re.sub(r'\s+', ' ', text)
        if not text or len(text) > MAX_NAME_LENGTH or not re.search(r'[^\W\d_]', text):
            return ''
        return text

    def get_given_name(self, ref_id: Any) -> str | None:
        name = self.__section('given_names').get(str(ref_id))
        return name if isinstance(name, str) and name else None

    def set_given_name(self, ref_id: Any, name: str) -> None:
        self.__section('given_names')[str(ref_id)] = name
        self.__save()

    # --- NPCs traveling with the player

    def get_companion(self, ref_id: Any) -> dict[str, str] | None:
        companion = self.__section('companions').get(str(ref_id))
        return companion if isinstance(companion, dict) else None

    def set_companion(self, ref_id: Any, purpose: str, destination: str) -> None:
        self.__section('companions')[str(ref_id)] = {'purpose': purpose, 'destination': destination}
        self.__save()

    def remove_companion(self, ref_id: Any) -> None:
        if self.__section('companions').pop(str(ref_id), None) is not None:
            self.__save()

    # --- memories under a new name

    def move_memories(self, ref_id: Any, old_name: str, new_name: str) -> None:
        """An NPC's memories and conversation history are kept in a folder named after them ('<name> - <ref id>/<name>...').
        When they get a new name, the folder and its files are renamed, so that they keep their memories"""
        if not self.__conversations_folder or not self.__world_id:
            return
        world_folder = os.path.join(self.__conversations_folder, self.__world_id)
        old_base = utils.remove_trailing_number(old_name)
        old_folder = os.path.join(world_folder, f'{old_base} - {ref_id}')
        new_folder = os.path.join(world_folder, f'{new_name} - {ref_id}')
        if not os.path.isdir(old_folder) or os.path.exists(new_folder):
            return
        try:
            for file_name in os.listdir(old_folder):
                if file_name.startswith(old_base):
                    os.rename(os.path.join(old_folder, file_name), os.path.join(old_folder, new_name + file_name[len(old_base):]))
            os.rename(old_folder, new_folder)
        except OSError as e:
            logger.warning(f'Could not move the memories of {old_name} to their new name {new_name}: {e}')
