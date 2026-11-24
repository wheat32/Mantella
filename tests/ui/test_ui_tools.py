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


def test_reset_all_button_of_a_settings_tab():
    """The Prompts tab can be reset to its defaults in one go, after a confirmation"""
    import gradio as gr
    from src.ui.settings_ui_constructor import SettingsUIConstructor
    from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew

    definitions = MantellaConfigValueDefinitionsNew.get_config_values(False)
    extras_added = []
    with gr.Blocks() as blocks:
        constructor = SettingsUIConstructor(None, group_extras={"Other": lambda: extras_added.append(True)}, groups_with_reset_all={"Prompts"})
        for group in definitions.base_groups:
            with gr.Tab(group.name):
                group.accept_visitor(constructor)

    assert extras_added == [True] # only the Other tab gets its extra elements
    button_labels = [block.value for block in blocks.blocks.values() if isinstance(block, gr.Button)]
    assert button_labels.count("Reset All Prompts to Default") == 1

    functions = blocks.fns.values() if isinstance(blocks.fns, dict) else blocks.fns
    reset_all = [f.fn for f in functions if f.fn is not None and f.fn.__name__ == 'reset_all'][0]
    prompts = [cv for cv in constructor.config_value_to_ui_element if cv.identifier in ('skyrim_prompt', 'memory_prompt')]
    assert len(prompts) == 2
    for prompt in prompts:
        prompt.value = 'my own prompt {name}'

    reset_all(False) # the question was answered with "Cancel"
    assert all(prompt.value == 'my own prompt {name}' for prompt in prompts)
    updates = reset_all(True)
    assert all(prompt.value == prompt.default_value for prompt in prompts)
    assert len(updates) > len(prompts) # every setting of the tab gets its default back in the UI


def test_prompts_are_grouped_by_game():
    """Settings of a tab can be divided over tabs of their own, and none of them gets lost"""
    import gradio as gr
    from src.ui.settings_ui_constructor import SettingsUIConstructor
    from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew

    definitions = MantellaConfigValueDefinitionsNew.get_config_values(False)
    with gr.Blocks() as blocks:
        constructor = SettingsUIConstructor(None, group_sub_tabs={"Prompts": [
            ("All Games", lambda setting: not setting.identifier.startswith(("skyrim_", "fallout4_"))),
            ("Skyrim", lambda setting: setting.identifier.startswith("skyrim_")),
            ("Fallout 4", lambda setting: setting.identifier.startswith("fallout4_")),
        ]})
        for group in definitions.base_groups:
            with gr.Tab(group.name):
                group.accept_visitor(constructor)

    tabs = {block.label: block for block in blocks.blocks.values() if isinstance(block, gr.Tab)}
    assert {"Skyrim", "Fallout 4", "All Games"} <= set(tabs)
    tab_order = [block.label for block in blocks.blocks.values() if isinstance(block, gr.Tab) and block.label in ("Skyrim", "Fallout 4", "All Games")]
    assert tab_order == ["All Games", "Skyrim", "Fallout 4"]

    def get_tab_of(identifier: str) -> str | None:
        setting = [cv for cv in constructor.config_value_to_ui_element if cv.identifier == identifier][0]
        parent = constructor.config_value_to_ui_element[setting].parent
        while parent is not None and not (isinstance(parent, gr.Tab) and parent.label in ("Skyrim", "Fallout 4", "All Games")):
            parent = parent.parent
        return parent.label if parent is not None else None

    assert get_tab_of("skyrim_prompt") == "Skyrim"
    assert get_tab_of("skyrim_radiant_prompt") == "Skyrim"
    assert get_tab_of("fallout4_multi_npc_prompt") == "Fallout 4"
    assert get_tab_of("memory_prompt") == "All Games"
    assert get_tab_of("radiant_max_turns") == "All Games"

    # every visible setting of every tab has been created
    created = {cv.identifier for cv in constructor.config_value_to_ui_element}
    for group in definitions.base_groups:
        if not group.is_hidden:
            for setting in group.value:
                if not setting.is_hidden:
                    assert setting.identifier in created, setting.identifier


def test_version_is_shown_in_the_web_ui():
    from src.ui.start_ui import StartUI
    footer = StartUI.get_footer_html('0.17.0-alpha.1')
    assert 'Mantella 0.17.0-alpha.1' in footer and 'Installation Guide' in footer
    assert 'mantella-version' not in StartUI.get_footer_html('')
    banner = StartUI.get_prerelease_banner_html('0.17.0-beta.2', 'beta.2')
    assert '<b>BETA</b>' in banner and '0.17.0-beta.2' in banner
