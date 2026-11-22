import logging
import sys
from src.ui.log_buffer import LogBuffer
from src.ui.memory_editor import MemoryEditor
from src.ui import process_control


def _create_memories(tmp_path):
    npc_folder = tmp_path / "Dragonborn" / "Ralof - 0002BF9F"
    npc_folder.mkdir(parents=True)
    (npc_folder / "Ralof_summary_1.txt").write_text("Old memories.\n\n", encoding="utf-8")
    (npc_folder / "Ralof_summary_2.txt").write_text("Condensed memories.\n\n", encoding="utf-8")
    (npc_folder / "Ralof.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Dragonborn" / "Empty NPC").mkdir()
    return npc_folder


def test_memory_editor_lists_npcs_with_memories(tmp_path):
    _create_memories(tmp_path)
    assert MemoryEditor(str(tmp_path)).list_npcs() == ["Dragonborn/Ralof - 0002BF9F"]
    assert MemoryEditor(str(tmp_path / "missing")).list_npcs() == []


def test_memory_editor_reads_and_saves_latest_summary(tmp_path):
    npc_folder = _create_memories(tmp_path)
    editor = MemoryEditor(str(tmp_path))
    npc = "Dragonborn/Ralof - 0002BF9F"

    assert editor.read_memory(npc) == "Condensed memories.\n\n"
    editor.save_memory(npc, "  Corrected memories.  ")
    assert (npc_folder / "Ralof_summary_2.txt").read_text(encoding="utf-8") == "Corrected memories.\n\n"
    assert (npc_folder / "Ralof_summary_1.txt").read_text(encoding="utf-8") == "Old memories.\n\n"


def test_memory_editor_deletes_only_summaries(tmp_path):
    npc_folder = _create_memories(tmp_path)
    editor = MemoryEditor(str(tmp_path))

    editor.delete_memory("Dragonborn/Ralof - 0002BF9F")
    assert sorted(p.name for p in npc_folder.iterdir()) == ["Ralof.json"]
    assert editor.list_npcs() == []


def test_memory_editor_refuses_paths_outside_conversations_folder(tmp_path):
    conversations = tmp_path / "conversations"
    conversations.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Secret_summary_1.txt").write_text("keep", encoding="utf-8")
    editor = MemoryEditor(str(conversations))

    assert editor.read_memory("../outside") == ""
    editor.delete_memory("../outside")
    assert (outside / "Secret_summary_1.txt").exists()
    assert editor.read_memory(None) == ""


def test_log_buffer_collects_entries_with_severity():
    buffer = LogBuffer(max_entries=3)
    logger = logging.getLogger("test_log_buffer")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(buffer)
    try:
        logger.info("one")
        logger.warning("two")
        logger.error("three")
        logger.log(42, "http debug output")
    finally:
        logger.removeHandler(buffer)

    entries = buffer.get_entries()
    assert [e["message"] for e in entries] == ["two", "three", "http debug output"] # oldest entry dropped
    assert [e["level"] for e in entries] == ["warning", "error", "debug"]
    assert buffer.get_entries(after_id=entries[1]["id"]) == entries[2:]


def test_restart_command(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--integrated"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert process_control.get_restart_command() == [sys.executable, "--integrated"]

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    command = process_control.get_restart_command()
    assert command[0] == sys.executable and command[-1] == "--integrated" and len(command) == 3
