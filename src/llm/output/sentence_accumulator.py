import re

from src.llm.output.clean_sentence_parser import clean_sentence_parser


class sentence_accumulator:
    """Accumulates the token-wise output of an LLM into raw sentences.
    """
    # Marks a line break that directly follows an ellipsis. An ellipsis in the middle of a line is a pause ("Well... I suppose so."),
    # but a line that ends in one is a finished (trailing off) sentence, typically followed by the line of the next speaker
    LINE_END_MARKER = '\x1e'
    __ellipsis_before_line_break = re.compile(r'((?:\.{2,}|…)["\'”’*)]*)[ \t]*\r?\n')
    __trailing_ellipsis = re.compile(r'(?:\.{2,}|…)["\'”’*)]*[ \t]*$')
    __leading_line_break = re.compile(r'^[ \t]*\r?\n')

    def __init__(self, cut_indicators: list[str]) -> None:
        self.__cut_indicators = cut_indicators
        self.__cleaned_llm_output: str = ""
        # Match at least one word character, then the first sentence-ending punctuation.
        # A standalone period (not part of an ellipsis) or any other end-of-sentence char.
        other_chars = [c for c in cut_indicators if c != '.']
        other_chars_escaped = ''.join([re.escape(c) for c in other_chars])
        self.__sentence_end_reg = re.compile(rf"^.*?\w.*?(?:(?<!\.)\.(?!\.)|[{other_chars_escaped}]|{re.escape(self.LINE_END_MARKER)})+")
        self.__unparseable: str = ""
        self.__prepared_match: str = ""
        self.__cleaner = clean_sentence_parser()
    
    def has_next_sentence(self) -> bool:
        if len(self.__prepared_match) > 0:
            return True
        
        match = self.__sentence_end_reg.match(self.__cleaned_llm_output)
        if not match:
            return False
        else:
            self.__prepared_match = match.group()
            self.__cleaned_llm_output = self.__cleaned_llm_output.removeprefix(self.__prepared_match)
            return True
    
    def get_next_sentence(self) -> str:
        result = self.__unparseable + self.__prepared_match
        self.__unparseable = ""
        self.__prepared_match = ""
        return result
    
    def accumulate(self, llm_output: str):
        # The ellipsis and the line break after it can arrive in separate chunks
        if self.__trailing_ellipsis.search(self.__cleaned_llm_output) and self.__leading_line_break.match(llm_output):
            llm_output = self.LINE_END_MARKER + llm_output
        llm_output = self.__ellipsis_before_line_break.sub(lambda m: m.group(1) + self.LINE_END_MARKER + ' ', llm_output)
        llm_output = self.__cleaner.clean_sentence(llm_output)
        self.__cleaned_llm_output += llm_output
    
    def refuse(self, refused_text: str):
        self.__unparseable = refused_text
    


    
