import json
from typing import Any, Hashable

from threading import Lock
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from src.config.config_loader import ConfigLoader
from src.games.fallout4 import Fallout4
from src.games.gameable import Gameable
from src.games.skyrim import Skyrim
from src.output_manager import ChatManager
from src.llm.llm_client import LLMClient
from src.setup import MantellaSetup
from src.llm.client_base import ClientBase
from src.llm.summary_client import SummaryLLMClient
from src.game_manager import GameStateManager
from src.http.routes.routeable import routeable
from src.http.communication_constants import communication_constants as comm_consts
from src.tts.ttsable import TTSable
from src.tts.tts_factory import create_tts
from src import utils
from src.config.definitions.game_definitions import GameEnum
from src.config.definitions.tts_definitions import TTSEnum
from src.actions.function_manager import FunctionManager

logger = utils.get_logger()


class mantella_route(routeable):
    """Main route for Mantella conversations

    Args:
        routeable (_type_): _description_
    """
    def __init__(self, config: ConfigLoader, language_info: dict[Hashable, str]) -> None:
        super().__init__(config)
        self.__language_info: dict[Hashable, str] = language_info
        self.__game: GameStateManager | None = None
        self.__tts: TTSable | None = None
        self.__has_deferred_config_change_been_logged: bool = False
        self.__request_lock: Lock = Lock()

        # if not self._can_route_be_used():
        #     error_message = "MantellaSoftware settings faulty. Please check MantellaSoftware's window or log."
        #     logger.error(error_message)

    @utils.time_it
    def _setup_route(self):
        if self.__game:
            self.__game.end_conversation({})

        game: Gameable
        game_enum = self._config.game
        if game_enum.base_game == GameEnum.FALLOUT4:
            game = Fallout4(self._config)
        else:
            game = Skyrim(self._config)

        if self.__tts:
            try:
                self.__tts.shutdown() # eg stop the Piper process of the previous settings
            except Exception as e:
                logger.debug(f'Could not shut down the previous TTS service: {e}')
        tts: TTSable = create_tts(self._config.tts_service, self._config, game)
        self.__tts = tts

        ClientBase.request_timeout = float(self._config.llm_timeout)
        MantellaSetup.apply_console_log_setting(self._config)
        llm_client = LLMClient(self._config)

        summary_client: SummaryLLMClient | None = None
        if self._config.summary_llm_enabled:
            summary_client = SummaryLLMClient(self._config)

        chat_manager = ChatManager(self._config, tts, llm_client, game)
        self.__game = GameStateManager(game, chat_manager, self._config, self.__language_info, llm_client, summary_client)

    def __should_defer_config_changes(self, received_json: dict[str, Any] | None) -> bool:
        """Settings changed in the UI while a conversation is running are only applied once that conversation has ended.
        Applying them straight away would rebuild the LLM / TTS / STT services and cut the conversation off mid-sentence
        """
        if not self.__game or not self.__game.is_conversation_active or not received_json:
            self.__has_deferred_config_change_been_logged = False
            return False
        request_type = received_json.get(comm_consts.KEY_REQUESTTYPE)
        is_conversation_request = request_type in (comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION, comm_consts.KEY_REQUESTTYPE_PLAYERINPUT, comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION)
        if not is_conversation_request:
            return False
        if self._config.has_any_config_value_changed and not self.__has_deferred_config_change_been_logged:
            self.__has_deferred_config_change_been_logged = True
            logger.log(24, 'Settings have been changed during a conversation. The new settings will be applied once the current conversation has ended')
        return True

    @utils.time_it
    def add_route_to_server(self, app: FastAPI):
        @app.post("/mantella")
        async def mantella(request: Request):
            received_json: dict[str, Any] | None = await request.json()
            # Requests can block for a long time (eg while waiting for the player to speak).
            # Handling them in a worker thread keeps the rest of the server (eg the settings UI) responsive in the meantime
            return await run_in_threadpool(self._handle_request, received_json)

    def _handle_request(self, received_json: dict[str, Any] | None) -> dict[str, Any]:
        # The game's requests are processed strictly one after the other. A request that is waiting for the player to speak
        # can hold things up indefinitely (with push-to-talk: until the key is pressed), so requests that end or (re)start
        # a conversation call that wait off instead of queueing behind it
        cancels_listening = False
        if received_json and self.__game and self.__request_lock.locked():
            request_type = received_json.get(comm_consts.KEY_REQUESTTYPE)
            if request_type in (comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION, comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION, comm_consts.KEY_REQUESTTYPE_INIT):
                cancels_listening = True
                self.__game.cancel_listening()
        with self.__request_lock:
            if cancels_listening and self.__game:
                self.__game.clear_listening_cancel()
            if not self._can_route_be_used(self.__should_defer_config_changes(received_json)):
                error_message = "MantellaSoftware settings faulty. Please check MantellaSoftware's window or log."
                logger.error(error_message)
                return self.error_message(error_message)
            if not self.__game:
                error_message = "Game manager setup failed. There is most likely an issue with the config.ini."
                logger.error(error_message)
                return self.error_message(error_message)
            reply = {}
            if received_json:
                logger.debug('Processing request...')
                if self._config.show_http_debug_messages:
                    logger.log(self._log_level_http_in, json.dumps(received_json, indent=4))
                request_type: str = received_json[comm_consts.KEY_REQUESTTYPE]
                match request_type:
                    case comm_consts.KEY_REQUESTTYPE_INIT:
                        # nothing needs to be done for this request aside from self._can_route_be_used() being triggered
                        logger.debug('Mantella settings initialized')
                        reply = {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_INITCOMPLETED}
                    case comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION:
                        reply = self.__game.start_conversation(received_json)
                    case comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION:
                        reply = self.__game.continue_conversation(received_json)
                    case comm_consts.KEY_REQUESTTYPE_PLAYERINPUT:
                        reply = self.__game.player_input(received_json)
                    case comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION:
                        reply = self.__game.end_conversation(received_json)
                    case _:
                        reply = self.error_message(f"Request type '{request_type}' was not recognized")
            else:
                reply = self.error_message(f"Request did not contain properly formatted json!")

            if self._config.show_http_debug_messages:
                logger.log(self._log_level_http_out, json.dumps(reply, indent=4))
            return reply
