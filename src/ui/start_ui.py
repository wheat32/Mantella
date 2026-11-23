import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
import webbrowser
import gradio as gr
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src.ui.settings_ui_constructor import SettingsUIConstructor
from src.ui.log_buffer import get_log_buffer
from src.ui.memory_editor import MemoryEditor
from src.ui import process_control
from src.wine import to_host_path
from src.config.definitions.tts_definitions import TTSDefinitions
from src.setup import MantellaSetup
from src.config.definitions.game_definitions import GameEnum
import src.utils as utils

logger = utils.get_logger()


class StartUI(routeable):
    BANNER = "docs/_static/img/mantella_banner.png"
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config)
        self.__constructor = SettingsUIConstructor(self.__on_setting_changed)

    def create_main_block(self) -> gr.Blocks:
        with gr.Blocks(title="Mantella", fill_height=True, analytics_enabled=False, theme= self.__get_theme(), css=self.__load_css(), js=self.CONSOLE_JS) as main_block:
            # with gr.Tab("Settings") as tabs:
            settings_page = self.__generate_settings_page()
            # Options that configure the XTTS server Mantella starts itself are meaningless if XTTS runs on another machine
            self.__constructor.setup_conditional_visibility(
                "xtts_url", ["xtts_server_folder", "xtts_device", "xtts_deepspeed", "xtts_lowvram"],
                lambda xtts_url: TTSDefinitions.is_xtts_url_local(xtts_url))
            with gr.Tab("NPC Memories"):
                self.__generate_memory_page()
            # with gr.Tab("Chat with NPCs", interactive=False):
            #     self.__generate_chat_page()
            # with gr.Tab("NPC editor", interactive=False):
            #     self.__generate_character_editor_page()

            self.__generate_console_section()

            with gr.Row(elem_classes="custom-footer"):
                gr.HTML("""
                    <div class="custom-footer">
                        <a href="https://art-from-the-machine.github.io/Mantella/" target="_blank">Mantella Installation Guide</a>
                    </div>
                """)
        return main_block

    def __on_setting_changed(self, config_value):
        """Applies settings that can take effect straight away, without waiting for Mantella's services to be set up again"""
        if config_value.identifier == "save_console_logs":
            self._config.save_console_logs = config_value.value
            MantellaSetup.apply_console_log_setting(self._config)

    def _get_memory_editor(self) -> MemoryEditor:
        game_folder = "Fallout4" if self._config.game.base_game == GameEnum.FALLOUT4 else "Skyrim"
        return MemoryEditor(os.path.join(self._config.save_folder, "data", game_folder, "conversations"))

    def __generate_memory_page(self):
        """A page to view, edit and delete what NPCs remember of past conversations"""
        def refresh_npcs():
            return gr.Dropdown(choices=self._get_memory_editor().list_npcs(), value=None), "", ""

        def load_memory(npc: str | None):
            editor = self._get_memory_editor()
            latest_file = editor.get_latest_summary_file(npc)
            return editor.read_memory(npc), (f"Editing `{to_host_path(latest_file)}`" if latest_file else "")

        def save_memory(npc: str | None, text: str):
            return self._get_memory_editor().save_memory(npc, text)

        def delete_memory(npc: str | None):
            editor = self._get_memory_editor()
            message = editor.delete_memory(npc)
            return gr.Dropdown(choices=editor.list_npcs(), value=None), "", message

        gr.Markdown("After each conversation, NPCs store a summary of it as a memory. Here you can correct or remove memories (eg of a conversation that went wrong). Each paragraph is one remembered conversation. Changes apply from the next conversation with the NPC.")
        with gr.Row():
            npc_dropdown = gr.Dropdown(choices=self._get_memory_editor().list_npcs(), value=None, label="NPC (player / NPC)", scale=4)
            refresh_button = gr.Button("Refresh list", size='sm', scale=1)
        memory_text = gr.Text(label="Memories", lines=14, max_lines=30, interactive=True)
        with gr.Row():
            save_button = gr.Button("Save changes", variant="primary", size='sm')
            delete_button = gr.Button("Delete all memories of this NPC", variant="stop", size='sm')
        status = gr.Markdown("")

        npc_dropdown.change(load_memory, npc_dropdown, [memory_text, status])
        refresh_button.click(refresh_npcs, None, [npc_dropdown, memory_text, status])
        save_button.click(save_memory, [npc_dropdown, memory_text], status)
        delete_button.click(delete_memory, npc_dropdown, [npc_dropdown, memory_text, status])

    def __generate_console_section(self):
        """Shows Mantella's console output below the settings, along with buttons to stop / restart Mantella"""
        with gr.Column(elem_classes="console-section"):
            with gr.Row(elem_classes="console-header"):
                gr.HTML('<h3 style="margin: 0;">Console</h3>')
                restart_button = gr.Button("Restart Mantella", size='sm', scale=0, min_width=160)
                stop_button = gr.Button("Stop Mantella", variant="stop", size='sm', scale=0, min_width=160)
            control_status = gr.Markdown("")
            gr.HTML('<div id="mantella-console" class="mantella-console" role="log" aria-label="Mantella console output"></div>')
            restart_button.click(process_control.restart_mantella, None, control_status)
            stop_button.click(process_control.stop_mantella, None, control_status)

    # Polls the server for new log messages and appends them to the console panel
    CONSOLE_JS = """
    () => {
        let lastId = 0;
        let wasOffline = false;
        const poll = async () => {
            const panel = document.getElementById('mantella-console');
            if (panel) {
                try {
                    const response = await fetch('/mantella/logs?after=' + lastId, {cache: 'no-store'});
                    const data = await response.json();
                    wasOffline = false;
                    if (panel.dataset.marker && data.restarted_marker !== panel.dataset.marker) {
                        // Mantella has been restarted, so its log has started over: fetch it from the beginning
                        panel.dataset.marker = data.restarted_marker;
                        lastId = 0;
                        data.entries = [];
                    }
                    panel.dataset.marker = data.restarted_marker;
                    const stickToBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 40;
                    for (const entry of data.entries) {
                        const line = document.createElement('div');
                        line.className = 'console-line console-' + entry.level;
                        line.textContent = '[' + entry.time + '] ' + entry.label + ': ' + entry.message;
                        panel.appendChild(line);
                        lastId = Math.max(lastId, entry.id);
                    }
                    while (panel.childElementCount > 2000) { panel.removeChild(panel.firstChild); }
                    if (stickToBottom && data.entries.length) { panel.scrollTop = panel.scrollHeight; }
                } catch (error) {
                    if (!wasOffline) {
                        wasOffline = true;
                        const line = document.createElement('div');
                        line.className = 'console-line console-warning';
                        line.textContent = 'Lost connection to Mantella. Waiting for it to come back...';
                        panel.appendChild(line);
                        panel.scrollTop = panel.scrollHeight;
                    }
                }
            }
            setTimeout(poll, 1500);
        };
        poll();
    }
    """

    def __generate_settings_page(self) -> gr.Column:
        # with gr.Column() as settings:
        for cf in self._config.definitions.base_groups:
            if not cf.is_hidden:
                with gr.Tab(cf.name):
                    cf.accept_visitor(self.__constructor)
        return None #settings
    
    def __generate_chat_page(self):
        return gr.Column()
    
    def __generate_character_editor_page(self):
        return gr.Column() 

    def __get_theme(self):
        return gr.themes.Soft(primary_hue="green",
                            secondary_hue="green",
                            neutral_hue="zinc",
                            font=['Montserrat', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                            font_mono=['IBM Plex Mono', 'ui-monospace', 'Consolas', 'monospace']).set(
                                input_text_size='*text_md',
                                input_padding='*spacing_md',
                            )

    
    def add_route_to_server(self, app: FastAPI):
        @app.get("/favicon.ico")
        async def favicon():
            return FileResponse(os.path.join(utils.resolve_path(), "Mantella.ico"))

        @app.get("/mantella/logs")
        def logs(after: int = 0):
            # the marker changes when Mantella is restarted, telling the page that entry ids have started over
            return {"entries": get_log_buffer().get_entries(after), "restarted_marker": str(os.getpid())}

        gr.mount_gradio_app(app,
                            self.create_main_block(),
                            path="/ui")
        
        link = f'http://localhost:{str(self._config.port)}/ui?__theme=dark'
        logger.log(24, f'\nMantella settings can be changed via this link:')
        logger.log(25, link)
        if self._config.auto_launch_ui == True and not process_control.was_restarted_from_ui():
            if not webbrowser.open(link, new=2):
                logger.warning('\nFailed to open Mantella settings UI automatically. To edit settings, see here:')
                logger.log(25, link)
    
    def __load_css(self):
        with open(os.path.join(utils.resolve_path(), 'src', 'ui', 'style.css'), 'r', encoding='utf-8') as file:
            css_content = file.read()
        return css_content
    
    def _setup_route(self):
        pass

    