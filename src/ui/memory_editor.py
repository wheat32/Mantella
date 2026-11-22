import os
import re
import src.utils as utils
from src.wine import to_host_path

logger = utils.get_logger()


class MemoryEditor:
    """Lists, reads, edits and deletes the conversation summaries ("memories") that NPCs have of past conversations.

    Memories are stored as text files in <save folder>/data/<game>/conversations/<player / world>/<NPC>/<NPC>_summary_<n>.txt.
    The file with the highest number is the one that is added to the NPC's prompt
    """
    SUMMARY_FILE_PATTERN = re.compile(r'^(?P<name>.+)_summary_(?P<number>\d+)\.txt$')

    def __init__(self, conversations_folder: str) -> None:
        self.__conversations_folder = conversations_folder

    @property
    def conversations_folder(self) -> str:
        return self.__conversations_folder

    def list_npcs(self) -> list[str]:
        """Returns all NPCs with saved memories as '<player / world>/<NPC folder>' entries"""
        npcs: list[str] = []
        if not os.path.isdir(self.__conversations_folder):
            return npcs
        for world in sorted(os.listdir(self.__conversations_folder)):
            world_path = os.path.join(self.__conversations_folder, world)
            if not os.path.isdir(world_path):
                continue
            for npc in sorted(os.listdir(world_path)):
                if self.__get_summary_files(os.path.join(world_path, npc)):
                    npcs.append(f'{world}/{npc}')
        return npcs

    def read_memory(self, npc: str | None) -> str:
        """Returns the memories currently used for the given NPC"""
        latest_file = self.get_latest_summary_file(npc)
        if not latest_file:
            return ''
        with open(latest_file, 'r', encoding='utf-8') as f:
            return f.read()

    def save_memory(self, npc: str | None, text: str) -> str:
        """Overwrites the memories currently used for the given NPC

        Returns:
            str: a message describing the result
        """
        latest_file = self.get_latest_summary_file(npc)
        if not latest_file:
            return 'No memory file found for the selected NPC.'
        text = (text or '').strip()
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n\n' if text else '') # summaries are separated by empty lines
        logger.info(f'Memories of {npc} edited via the web UI: {latest_file}')
        return f'Saved to {to_host_path(latest_file)}'

    def delete_memory(self, npc: str | None) -> str:
        """Deletes all memory (summary) files of the given NPC. Conversation logs are left untouched

        Returns:
            str: a message describing the result
        """
        folder = self.__get_npc_folder(npc)
        if not folder:
            return 'No NPC selected.'
        summary_files = self.__get_summary_files(folder)
        for _, file_name in summary_files:
            os.remove(os.path.join(folder, file_name))
        logger.info(f'Memories of {npc} deleted via the web UI ({len(summary_files)} file(s) in {folder})')
        return f'Deleted {len(summary_files)} memory file(s) of {npc}.'

    def get_latest_summary_file(self, npc: str | None) -> str | None:
        folder = self.__get_npc_folder(npc)
        if not folder:
            return None
        summary_files = self.__get_summary_files(folder)
        if not summary_files:
            return None
        return os.path.join(folder, max(summary_files)[1])

    def __get_npc_folder(self, npc: str | None) -> str | None:
        """Resolves a '<player / world>/<NPC folder>' entry to its folder, refusing anything outside the conversations folder"""
        if not npc:
            return None
        root = os.path.realpath(self.__conversations_folder)
        folder = os.path.realpath(os.path.join(root, *npc.split('/')))
        if os.path.commonpath([root, folder]) != root or folder == root or not os.path.isdir(folder):
            return None
        return folder

    def __get_summary_files(self, folder: str) -> list[tuple[int, str]]:
        if not os.path.isdir(folder):
            return []
        summary_files: list[tuple[int, str]] = []
        for file_name in os.listdir(folder):
            match = self.SUMMARY_FILE_PATTERN.match(file_name)
            if match:
                summary_files.append((int(match.group('number')), file_name))
        return summary_files
