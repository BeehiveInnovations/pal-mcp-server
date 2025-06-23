import os
import sys

sys.path.append(".")

from tests.test_utf8_localization import TestTool

# Test the language instruction generation
tool = TestTool()

# Test French locale
print("Testing French locale...")
os.environ["LOCALE"] = "fr-FR"
instruction_fr = tool.get_language_instruction()
print(f'French instruction: "{instruction_fr}"')

# Test English locale
print("Testing English locale...")
os.environ["LOCALE"] = "en-US"
instruction_en = tool.get_language_instruction()
print(f'English instruction: "{instruction_en}"')

# Test empty locale
print("Testing empty locale...")
os.environ["LOCALE"] = ""
instruction_empty = tool.get_language_instruction()
print(f'Empty instruction: "{instruction_empty}"')

# Test no locale
print("Testing no locale...")
os.environ.pop("LOCALE", None)
instruction_none = tool.get_language_instruction()
print(f'None instruction: "{instruction_none}"')

print("Test completed.")
