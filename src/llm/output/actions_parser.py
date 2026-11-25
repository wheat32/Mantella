import re
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent
from src.conversation.action import Action
import src.utils as utils

logger = utils.get_logger()

    
class actions_parser(output_parser):
    # Actions that open a menu: running them while the NPC is still talking would hide what the NPC says behind the menu.
    # They run once the NPC has finished speaking, whichever sentence of the response they were given with
    AFTER_SPEECH_ACTIONS: set[str] = {'mantella_npc_inventory', 'mantella_npc_barter'}

    def __init__(self, actions: list[Action]) -> None:
        super().__init__()
        self.__actions = actions

    def find_actions_in_text(self, text: str) -> tuple[str, list[Action]]:
        """Finds the action keywords ("Inventory:") in a text

        Returns:
            tuple[str, list[Action]]: the text without the keywords, and the actions found
        """
        found: list[Action] = []
        for action in self.__actions:
            pattern = re.compile(rf'\b{re.escape(action.keyword)}\s*:', re.IGNORECASE)
            if pattern.search(text):
                text = pattern.sub('', text)
                found.append(action)
        return re.sub(r'\s+', ' ', text).strip(), found

    def add_action(self, action: Action, cut_content: SentenceContent | None, settings: sentence_generation_settings) -> None:
        """Attaches the action to the sentence, or keeps it for the end of the response if it opens a menu"""
        action_data = {'identifier': action.identifier}
        if action.identifier in self.AFTER_SPEECH_ACTIONS or cut_content is None:
            if action_data not in settings.deferred_actions:
                settings.deferred_actions.append(action_data)
            logger.log(28, f'Action triggered: {action.name} ({action.identifier}), once the NPC has finished speaking')
        else:
            cut_content.actions.append(action_data)
            logger.log(28, f'Action triggered: {action.name} ({action.identifier})')
        if action.is_interrupting:
            settings.stop_generation = True

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent|None, str|None]:
        return None, output

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        if ":" in cut_content.text:
            for action in self.__actions:
                keyword = action.keyword + ":"
                if keyword in cut_content.text:
                    cut_content.text = cut_content.text.replace(keyword,"").strip()
                    self.add_action(action, cut_content, settings)
        return cut_content, last_content
    
    def get_cut_indicators(self) -> list[str]:
        return [":"]
