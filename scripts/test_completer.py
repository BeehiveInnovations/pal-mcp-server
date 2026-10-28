import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle

class TestCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            yield Completion("model", start_position=-len(text)+1)
            yield Completion("plan", start_position=-len(text)+1)

session = PromptSession(
    completer=TestCompleter(),
    complete_while_typing=True,
    complete_style=CompleteStyle.MULTI_COLUMN
)

print("MULTI_COLUMN completer initialized successfully")
