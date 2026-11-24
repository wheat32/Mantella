import re
from typing import Callable, OrderedDict
from src.character_manager import Character
from src.characters_manager import Characters
from src.conversation.action import Action
from src.llm.output.output_parser import MarkedTextStateEnum, output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent
import src.utils as utils

logger = utils.get_logger()


class change_character_parser(output_parser):
    """Class to check if character change is in the current output of the LLM."""
    def __init__(self, characters_in_conversation: Characters, actions: list[Action] | None = None) -> None:
        super().__init__()
        self.__dict_name_permutations: OrderedDict[str, Character] = OrderedDict() #Dictionary to hold permutations of the name for easy checks. e.g. "Svana Far-Shield" -> ["Svana Far-Shield", "Svana", "Far-Shield"]
        self.__action_keywords: set[str] = set(a.keyword.lower() for a in (actions or []))
        self.__numbered_name_patterns: list[re.Pattern] = []
        for actor in characters_in_conversation.get_all_characters():
            name_without_number = utils.get_name_without_number(actor.name)
            if name_without_number != actor.name:
                number = actor.name[len(name_without_number):].strip()
                self.__numbered_name_patterns.append(re.compile(rf'\b({re.escape(name_without_number)})\s+{re.escape(number)}\b', re.IGNORECASE))
        for actor in characters_in_conversation.get_all_characters():
            if actor.is_player_character:
                self.__dict_name_permutations["player"] = actor
            self.__dict_name_permutations[actor.name] = actor
        
        # Parts of a name also identify a character ("Svana" for "Svana Far-Shield"), unless they are the name of another character:
        # with "bandit" and "bandit 2" in a conversation, "bandit" must keep meaning the first of the two
        full_names_lower: set[str] = set(name.lower() for name in self.__dict_name_permutations)
        split_names_to_add: OrderedDict[str, Character] = OrderedDict()
        for character in list(self.__dict_name_permutations.values()):
            split_name = character.name.split()
            if len(split_name) > 1:
                for name_part in split_name:
                    if name_part.isdigit(): # the number the game adds to characters that share a name
                        continue
                    if name_part.lower() in full_names_lower:
                        continue
                    if not split_names_to_add.__contains__(name_part):
                        split_names_to_add[name_part] = character

        for name, character in split_names_to_add.items():
            self.__dict_name_permutations[name] = character

        # Longer names are checked first, so that "bandit 2" is not taken for a character called "2" or "bandit"
        self.__dict_name_permutations = OrderedDict(sorted(self.__dict_name_permutations.items(), key=lambda item: len(item[0]), reverse=True))


    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent | None, str]:
        if not ':' in output:
            return None, output
        
        parts = output.split(':', 1)
        for name, character in self.__dict_name_permutations.items():
            if parts[0].lower().endswith(name.lower()):
                character_switch_removed = parts[0][:-len(name)]
                cleaned_prefix_rest = character_switch_removed.strip()
                if not len(cleaned_prefix_rest) == 0: #Special case where there is still text in front of a character change that needs to be processed first somehow
                    rest = str.join("", [name, ":", parts[1]])
                    return SentenceContent(current_settings.current_speaker, cleaned_prefix_rest, current_settings.sentence_type, False), rest
                else: #New sentence starts with character change
                    if character.is_player_character:
                        logger.log(28, f"Stopped LLM from speaking on behalf of the player")
                        current_settings.stop_generation = True
                        return None, ""
                    current_settings.current_speaker = character
                    current_settings.sentence_type = current_settings.unmarked_text #Reset to the last unmarked text type
                    current_settings.current_text_state = MarkedTextStateEnum.UNMARKED
                    return None, parts[1]

        # Discard character changes for characters not in the conversation
        prefix = parts[0].strip()
        if prefix and prefix.lower() not in self.__action_keywords:
            logger.warning(f"Discarding text for character not in conversation: {prefix}")
            current_settings.discarded_character_name = prefix
            current_settings.stop_generation = True
            return None, ""

        return None, output #There is a ':' in the text, but it doesn't seem to be part of a character change

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        # The number of a numbered name ("bandit 2") only tells characters of the same name apart. It is never said out loud
        for pattern in self.__numbered_name_patterns:
            cut_content.text = pattern.sub(lambda match: match.group(1), cut_content.text)
        return cut_content, last_content
    
    def get_cut_indicators(self) -> list[str]:
        return [":"]
