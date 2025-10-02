# Locale Configuration for Zen MCP Server

This guide explains how to configure and use the localization feature to customize the language of responses from MCP tools.

## Overview

The localization feature allows you to specify the language in which MCP tools should respond, while maintaining their analytical capabilities. This is especially useful for non-English speakers who want to receive answers in their native language.

## Configuration

### 1. Environment Variable

Set the language using the `LOCALE` environment variable in your `.env` file:

```bash
# In your .env file
LOCALE=fr-FR
```

### 2. Supported Languages

You can use any standard language code. Examples:

- `fr-FR` - French (France)
- `en-US` - English (United States)
- `zh-CN` - Chinese (Simplified)
- `zh-TW` - Chinese (Traditional)
- `ja-JP` - Japanese
- `ko-KR` - Korean
- `es-ES` - Spanish (Spain)
- `de-DE` - German (Germany)
- `it-IT` - Italian (Italy)
- `pt-PT` - Portuguese (Portugal)
- `ru-RU` - Russian (Russia)
- `ar-SA` - Arabic (Saudi Arabia)

### 3. Default Behavior

If no language is specified (`LOCALE` is empty or unset), tools will default to English.

## Technical Implementation

### Architecture

Localization is implemented in the `BaseTool` class in `tools/shared/base_tool.py`. All tools inherit this feature automatically.

### `get_language_instruction()` Method

```python
def get_language_instruction(self) -> str:
    """
    Generate language instruction based on LOCALE configuration.
    Returns:
        str: Language instruction to prepend to prompt, or empty string if no locale set
    """
    import os

    locale = os.getenv("LOCALE", "").strip()

    if not locale:
        return ""

    return f"Always respond in {locale}.\n\n"
```

### Integration in Tool Execution

The language instruction is automatically prepended to the system prompt of each tool:

```python
# In tools/simple/base.py
base_system_prompt = self.get_system_prompt()
language_instruction = self.get_language_instruction()
system_prompt = language_instruction + base_system_prompt
```

## Usage

### 1. Basic Setup

1. Edit your `.env` file:
   ```bash
   LOCALE=fr-FR
   ```
2. Restart the MCP server:
   ```bash
   ./run-server.sh
   ```
3. Use any tool – responses will be in the specified language.

### 2. Example

**Before (default English):**
```
Tool: chat
Input: "Explain how to use Python dictionaries"
Output: "Python dictionaries are key-value pairs that allow you to store and organize data..."
```

**After (with LOCALE=fr-FR):**
```
Tool: chat
Input: "Explain how to use Python dictionaries"
Output: "Les dictionnaires Python sont des paires clé-valeur qui permettent de stocker et d'organiser des données..."
```

### 3. Affected Tools

All MCP tools are affected by this configuration:

- `chat` – General conversation
- `codereview` – Code review
- `analyze` – Code analysis
- `debug` – Debugging
- `refactor` – Refactoring
- `thinkdeep` – Deep thinking
- `consensus` – Model consensus
- And all other tools...

## Best Practices

### 1. Language Choice
- Use standard language codes (ISO 639-1 with ISO 3166-1 country codes)
- Be specific with regional variants if needed (e.g., `zh-CN` vs `zh-TW`)

### 2. Consistency
- Use the same language setting across your team for consistency
- Document the chosen language in your team documentation

### 3. Testing
- Test the configuration with different tools to ensure consistency

## Troubleshooting

### Issue: Language does not change
**Solution:**
1. Check that the `LOCALE` variable is correctly set in `.env`
2. Fully restart the MCP server
3. Ensure there are no extra spaces in the value

### Issue: Partially translated responses
**Explanation:**
- AI models may sometimes mix languages
- This depends on the multilingual capabilities of the model used
- Technical terms may remain in English

### Issue: Configuration errors
**Solution:**
1. Check the syntax of your `.env` file
2. Make sure there are no quotes around the value

## Advanced Customization

### Customizing the Language Instruction

To customize the language instruction, modify the `get_language_instruction()` method in `tools/shared/base_tool.py`:

```python
def get_language_instruction(self) -> str:
    import os

    locale = os.getenv("LOCALE", "").strip()

    if not locale:
        return ""
    # Custom instruction
    return f"Always respond in {locale} and use a professional tone.\n\n"
```

### Per-Tool Customization

You can also override the method in specific tools for custom behavior:

```python
class MyCustomTool(SimpleTool):
    def get_language_instruction(self) -> str:
        import os

        locale = os.getenv("LOCALE", "").strip()

        if locale == "fr-FR":
            return "Respond in French with precise technical vocabulary.\n\n"
        elif locale == "zh-CN":
            return "请用中文回答，使用专业术语。\n\n"
        else:
            return super().get_language_instruction()
```

## Integration with Other Features

Localization works with all other MCP server features:

- **Conversation threading** – Multilingual conversations are supported
- **File processing** – File analysis is in the specified language
- **Web search** – Search instructions remain functional
- **Model selection** – Works with all supported models
