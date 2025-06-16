# Adding a New Tool

This guide explains how to add a new tool to the Zen MCP Server. Tools are the primary way Claude interacts with the AI models, providing specialized capabilities like code review, debugging, test generation, and more.

## Overview

The tool system in Zen MCP Server is designed to be extensible. Each tool:
- Inherits from the `BaseTool` class
- Implements required abstract methods
- Defines a request model for parameter validation
- Is registered in the server's tool registry
- Can leverage different AI models based on task requirements

## Architecture Overview

### Key Components

1. **BaseTool** (`tools/base.py`): Abstract base class providing common functionality
2. **Request Models**: Pydantic models for input validation
3. **System Prompts**: Specialized prompts that configure AI behavior
4. **Tool Registry**: Registration system in `server.py`

### Tool Lifecycle

1. Claude calls the tool with parameters
2. Parameters are validated using Pydantic
3. File paths are security-checked
4. Prompt is prepared with system instructions
5. AI model generates response
6. Response is formatted and returned

## Step-by-Step Implementation Guide

### 1. Create the Tool File

Create a new file in the `tools/` directory (e.g., `tools/example.py`):

```python
"""
Example tool - Brief description of what your tool does

This tool provides [specific functionality] to help developers [achieve goal].
Key features:
- Feature 1
- Feature 2
- Feature 3
"""

import logging
from typing import Any, Optional

from mcp.types import TextContent
from pydantic import Field

from config import TEMPERATURE_BALANCED
from systemprompts import EXAMPLE_PROMPT  # You'll create this

from .base import BaseTool, ToolRequest
from .models import ToolOutput

logger = logging.getLogger(__name__)
```

### 2. Define the Request Model

Create a Pydantic model that inherits from `ToolRequest`:

```python
class ExampleRequest(ToolRequest):
    """Request model for the example tool."""
    
    # Required parameters
    prompt: str = Field(
        ...,
        description="The main input/question for the tool"
    )
    
    # Optional parameters with defaults
    files: Optional[list[str]] = Field(
        default=None,
        description="Files to analyze (must be absolute paths)"
    )
    
    focus_area: Optional[str] = Field(
        default=None,
        description="Specific aspect to focus on"
    )
    
    # You can add tool-specific parameters
    output_format: Optional[str] = Field(
        default="detailed",
        description="Output format: 'summary', 'detailed', or 'actionable'"
    )
    
    # New features - images and web search support
    images: Optional[list[str]] = Field(
        default=None,
        description="Optional images for visual context (file paths or base64 data URLs)"
    )
    
    use_websearch: Optional[bool] = Field(
        default=True,
        description="Enable web search for documentation and current information"
    )
```

### 3. Implement the Tool Class

```python
class ExampleTool(BaseTool):
    """Implementation of the example tool."""
    
    def get_name(self) -> str:
        """Return the tool's unique identifier."""
        return "example"
    
    def get_description(self) -> str:
        """Return detailed description for Claude."""
        return (
            "EXAMPLE TOOL - Brief tagline describing the tool's purpose. "
            "Use this tool when you need to [specific use cases]. "
            "Perfect for: [scenario 1], [scenario 2], [scenario 3]. "
            "Supports [key features]. Choose thinking_mode based on "
            "[guidance for mode selection]. "
            "Note: If you're not currently using a top-tier model such as "
            "Opus 4 or above, these tools can provide enhanced capabilities."
        )
    
    def get_input_schema(self) -> dict[str, Any]:
        """Define the JSON schema for tool parameters."""
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The main input/question for the tool",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to analyze (must be absolute paths)",
                },
                "focus_area": {
                    "type": "string",
                    "description": "Specific aspect to focus on",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["summary", "detailed", "actionable"],
                    "description": "Output format type",
                    "default": "detailed",
                },
                "model": self.get_model_field_schema(),
                "temperature": {
                    "type": "number",
                    "description": "Temperature (0-1, default varies by tool)",
                    "minimum": 0,
                    "maximum": 1,
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": "Thinking depth: minimal (0.5% of model max), "
                                   "low (8%), medium (33%), high (67%), max (100%)",
                },
                "use_websearch": {
                    "type": "boolean",
                    "description": "Enable web search for documentation and current information",
                    "default": True,
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional images for visual context",
                },
                "continuation_id": {
                    "type": "string",
                    "description": "Thread continuation ID for multi-turn conversations",
                },
            },
            "required": ["prompt"] + (
                ["model"] if self.is_effective_auto_mode() else []
            ),
        }
        return schema
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for this tool."""
        return EXAMPLE_PROMPT  # Defined in systemprompts/
    
    def get_default_temperature(self) -> float:
        """Return default temperature for this tool."""
        # Use predefined constants from config.py:
        # TEMPERATURE_CREATIVE (0.7) - For creative tasks
        # TEMPERATURE_BALANCED (0.5) - For balanced tasks
        # TEMPERATURE_ANALYTICAL (0.2) - For analytical tasks
        return TEMPERATURE_BALANCED
    
    def get_model_category(self):
        """Specify which type of model this tool needs."""
        from tools.models import ToolModelCategory
        
        # Choose based on your tool's needs:
        # FAST_RESPONSE - Quick responses, cost-efficient (chat, simple queries)
        # BALANCED - Standard analysis and generation
        # EXTENDED_REASONING - Complex analysis, deep thinking (debug, review)
        return ToolModelCategory.BALANCED
    
    def get_request_model(self):
        """Return the request model class."""
        return ExampleRequest
    
    def wants_line_numbers_by_default(self) -> bool:
        """Whether to add line numbers to code files."""
        # Return True if your tool benefits from precise line references
        # (e.g., code review, debugging, refactoring)
        # Return False for general analysis or token-sensitive operations
        return False
    
    async def prepare_prompt(self, request: ExampleRequest) -> str:
        """
        Prepare the complete prompt for the AI model.
        
        This method combines:
        - System prompt (behavior configuration)
        - User request
        - File contents (if provided)
        - Additional context
        """
        # Check for prompt.txt in files (handles large prompts)
        prompt_content, updated_files = self.handle_prompt_file(request.files)
        if prompt_content:
            request.prompt = prompt_content
        if updated_files is not None:
            request.files = updated_files
        
        # Build the prompt parts
        prompt_parts = []
        
        # Add main request
        prompt_parts.append(f"=== USER REQUEST ===")
        prompt_parts.append(f"Focus Area: {request.focus_area}" if request.focus_area else "")
        prompt_parts.append(f"Output Format: {request.output_format}")
        prompt_parts.append(request.prompt)
        prompt_parts.append("=== END REQUEST ===")
        
        # Add file contents if provided
        if request.files:
            # Use the centralized file handling (respects continuation)
            file_content = self._prepare_file_content_for_prompt(
                request.files,
                request.continuation_id,
                "Files to analyze"
            )
            if file_content:
                prompt_parts.append("\n=== FILES ===")
                prompt_parts.append(file_content)
                prompt_parts.append("=== END FILES ===")
        
        # Validate token limits
        full_prompt = "\n".join(filter(None, prompt_parts))
        self._validate_token_limit(full_prompt, "Prompt")
        
        return full_prompt
    
    def format_response(self, response: str, request: ExampleRequest, 
                       model_info: Optional[dict] = None) -> str:
        """
        Format the AI's response for display.
        
        Override this to add custom formatting, headers, or structure.
        The base class handles special status parsing automatically.
        """
        # Example: Add a footer with next steps
        return f"{response}\n\n---\n\n**Next Steps:** Review the analysis above and proceed with implementation."
```

### 4. Handle Large Prompts (Optional)

If your tool might receive large text inputs, override the `execute` method:

```python
async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
    """Override to check prompt size before processing."""
    # Validate request first
    request_model = self.get_request_model()
    request = request_model(**arguments)
    
    # Check if prompt is too large for MCP limits
    size_check = self.check_prompt_size(request.prompt)
    if size_check:
        return [TextContent(type="text", text=ToolOutput(**size_check).model_dump_json())]
    
    # Continue with normal execution
    return await super().execute(arguments)
```

### 5. Create the System Prompt

Create a new file in `systemprompts/` (e.g., `systemprompts/example_prompt.py`):

```python
"""System prompt for the example tool."""

EXAMPLE_PROMPT = """You are an AI assistant specialized in [tool purpose].

Your role is to [primary responsibility] by [approach/methodology].

Key principles:
1. [Principle 1]
2. [Principle 2]
3. [Principle 3]

When analyzing content:
- [Guideline 1]
- [Guideline 2]
- [Guideline 3]

Output format:
- Start with a brief summary
- Provide detailed analysis organized by [structure]
- Include specific examples and recommendations
- End with actionable next steps

Remember to:
- Be specific and reference exact locations (file:line) when discussing code
- Provide practical, implementable suggestions
- Consider the broader context and implications
- Maintain a helpful, constructive tone
"""
```

Add the import to `systemprompts/__init__.py`:

```python
from .example_prompt import EXAMPLE_PROMPT
```

### 6. Register the Tool

#### 6.1. Import in server.py

Add the import at the top of `server.py`:

```python
from tools.example import ExampleTool
```

#### 6.2. Add to TOOLS Dictionary

Find the `TOOLS` dictionary in `server.py` and add your tool:

```python
TOOLS = {
    "thinkdeep": ThinkDeepTool(),
    "codereview": CodeReviewTool(),
    "debug": DebugIssueTool(),
    "analyze": AnalyzeTool(),
    "chat": ChatTool(),
    "listmodels": ListModelsTool(),
    "precommit": Precommit(),
    "testgen": TestGenerationTool(),
    "refactor": RefactorTool(),
    "tracer": TracerTool(),
    "example": ExampleTool(),  # Add your tool here
}
```

### 7. Write Tests

Create unit tests in `tests/test_example.py`:

```python
"""Tests for the example tool."""

import pytest
from unittest.mock import Mock, patch

from tools.example import ExampleTool, ExampleRequest
from tools.models import ToolModelCategory


class TestExampleTool:
    """Test suite for ExampleTool."""
    
    def test_tool_metadata(self):
        """Test tool metadata methods."""
        tool = ExampleTool()
        
        assert tool.get_name() == "example"
        assert "EXAMPLE TOOL" in tool.get_description()
        assert tool.get_default_temperature() == 0.5
        assert tool.get_model_category() == ToolModelCategory.BALANCED
    
    def test_request_validation(self):
        """Test request model validation."""
        # Valid request
        request = ExampleRequest(prompt="Test prompt")
        assert request.prompt == "Test prompt"
        assert request.output_format == "detailed"  # default
        
        # Invalid request (missing required field)
        with pytest.raises(ValueError):
            ExampleRequest()
    
    def test_input_schema(self):
        """Test input schema generation."""
        tool = ExampleTool()
        schema = tool.get_input_schema()
        
        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert "prompt" in schema["required"]
        assert "model" in schema["properties"]
    
    @pytest.mark.asyncio
    async def test_prepare_prompt(self):
        """Test prompt preparation."""
        tool = ExampleTool()
        request = ExampleRequest(
            prompt="Analyze this code",
            focus_area="performance",
            output_format="summary"
        )
        
        with patch.object(tool, '_validate_token_limit'):
            prompt = await tool.prepare_prompt(request)
        
        assert "USER REQUEST" in prompt
        assert "Analyze this code" in prompt
        assert "Focus Area: performance" in prompt
        assert "Output Format: summary" in prompt
    
    @pytest.mark.asyncio
    async def test_file_handling(self):
        """Test file content handling."""
        tool = ExampleTool()
        request = ExampleRequest(
            prompt="Analyze",
            files=["/path/to/file.py"]
        )
        
        # Mock file reading
        with patch.object(tool, '_prepare_file_content_for_prompt') as mock_prep:
            mock_prep.return_value = "file contents"
            with patch.object(tool, '_validate_token_limit'):
                prompt = await tool.prepare_prompt(request)
        
        assert "FILES" in prompt
        assert "file contents" in prompt
```

### 8. Add Simulator Tests (Optional)

For tools that interact with external systems, create simulator tests in `simulator_tests/test_example_basic.py`:

```python
"""Basic simulator test for example tool."""

from simulator_tests.base_test import SimulatorTest


class TestExampleBasic(SimulatorTest):
    """Test basic example tool functionality."""
    
    def test_example_analysis(self):
        """Test basic analysis with example tool."""
        result = self.call_tool(
            "example",
            {
                "prompt": "Analyze the architecture of this codebase",
                "model": "flash",
                "output_format": "summary"
            }
        )
        
        self.assert_tool_success(result)
        self.assert_content_contains(result, ["architecture", "summary"])
```

### 9. Update Documentation

Add your tool to the README.md in the tools section:

```markdown
### Available Tools

- **thinkdeep** - Extended thinking and reasoning for complex problems
- **codereview** - Professional code review with bug and security analysis
- **debug** - Debug and root cause analysis for complex issues
- **analyze** - General-purpose file and code analysis
- **chat** - General chat and collaborative thinking
- **listmodels** - List all available AI models and their capabilities
- **precommit** - Pre-commit validation for git changes
- **testgen** - Comprehensive test generation with edge cases
- **refactor** - Intelligent code refactoring suggestions
- **tracer** - Static analysis for tracing code execution paths
- **example** - Brief description of what the tool does
  - Use cases: [scenario 1], [scenario 2]
  - Supports: [key features]
  - Best model: `balanced` category for standard analysis
```

## Advanced Features

### Token Budget Management

The server provides a `_remaining_tokens` parameter that tools can use for dynamic content allocation:

```python
# In execute method, you receive remaining tokens:
async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
    # Access remaining tokens if provided
    remaining_tokens = arguments.get('_remaining_tokens')
    
    # Use for file content preparation
    file_content = self._prepare_file_content_for_prompt(
        files,
        continuation_id,
        "Analysis files",
        max_tokens=remaining_tokens - 5000  # Reserve for response
    )
```

### Understanding Conversation Memory

The `continuation_id` feature enables multi-turn conversations using the conversation memory system (`utils/conversation_memory.py`). Here's how it works:

1. **Thread Creation**: When a tool wants to enable follow-up conversations, it creates a thread
2. **Turn Storage**: Each exchange (user/assistant) is stored as a turn with metadata
3. **Cross-Tool Continuation**: Any tool can continue a conversation started by another tool
4. **Automatic History**: When `continuation_id` is provided, the full conversation history is reconstructed

Key concepts:
- **ThreadContext**: Contains all conversation turns, files, and metadata
- **ConversationTurn**: Single exchange with role, content, timestamp, files, tool attribution
- **Thread Chains**: Conversations can have parent threads for extended discussions
- **Turn Limits**: Default 20 turns (configurable via MAX_CONVERSATION_TURNS)

Example flow:
```python
# Tool A creates thread
thread_id = create_thread("analyze", request_data)

# Tool A adds its response
add_turn(thread_id, "assistant", response, files=[...], tool_name="analyze")

# Tool B continues the same conversation
context = get_thread(thread_id)  # Gets full history
# Tool B sees all previous turns and files
```

### Supporting Special Response Types

Tools can return special status responses for complex interactions. These are defined in `tools/models.py`:

```python
# Currently supported special statuses:
SPECIAL_STATUS_MODELS = {
    "clarification_required": ClarificationRequest,
    "full_codereview_required": FullCodereviewRequired,
    "focused_review_required": FocusedReviewRequired,
    "test_sample_needed": TestSampleNeeded,
    "more_tests_required": MoreTestsRequired,
    "refactor_analysis_complete": RefactorAnalysisComplete,
    "trace_complete": TraceComplete,
    "resend_prompt": ResendPromptRequest,
    "code_too_large": CodeTooLargeRequest,
}
```

Example implementation:
```python
# In your tool's format_response or within the AI response:
if need_clarification:
    return json.dumps({
        "status": "need_clarification",
        "questions": ["What specific aspect should I focus on?"],
        "context": "I need more information to proceed"
    })

# For custom review status:
if more_analysis_needed:
    return json.dumps({
        "status": "focused_review_required", 
        "files": ["/path/to/file1.py", "/path/to/file2.py"],
        "focus": "security",
        "reason": "Found potential SQL injection vulnerabilities"
    })
```

To add a new custom response type:

1. Define the model in `tools/models.py`:
```python
class CustomStatusModel(BaseModel):
    """Model for custom status responses"""
    status: Literal["custom_status"]
    custom_field: str
    details: dict[str, Any]
```

2. Register it in `SPECIAL_STATUS_MODELS`:
```python
SPECIAL_STATUS_MODELS = {
    # ... existing statuses ...
    "custom_status": CustomStatusModel,
}
```

3. The base tool will automatically handle parsing and validation

### Token Management

For tools processing large amounts of data:

```python
# Calculate available tokens dynamically
def prepare_large_content(self, files: list[str], remaining_budget: int):
    # Reserve tokens for response
    reserve_tokens = 5000
    
    # Use model-specific limits
    effective_max = remaining_budget - reserve_tokens
    
    # Process files with budget
    content = self._prepare_file_content_for_prompt(
        files,
        continuation_id,
        "Analysis files",
        max_tokens=effective_max,
        reserve_tokens=reserve_tokens
    )
```

### Web Search Integration

Enable web search for tools that benefit from current information:

```python
# In prepare_prompt:
websearch_instruction = self.get_websearch_instruction(
    request.use_websearch,
    """Consider searching for:
    - Current best practices for [topic]
    - Recent updates to [technology]
    - Community solutions for [problem]"""
)

full_prompt = f"{system_prompt}{websearch_instruction}\n\n{user_content}"
```

### Image Support

Tools can now accept images for visual context:

```python
# In your request model:
images: Optional[list[str]] = Field(
    None,
    description="Optional images for visual context"
)

# In prepare_prompt:
if request.images:
    # Images are automatically validated and processed by base class
    # They will be included in the prompt sent to the model
    pass
```

Image validation includes:
- Size limits based on model capabilities
- Format validation (PNG, JPEG, GIF, WebP)
- Automatic base64 encoding for file paths
- Model-specific image count limits

## Best Practices

1. **Clear Tool Descriptions**: Write descriptive text that helps Claude understand when to use your tool
2. **Proper Validation**: Use Pydantic models for robust input validation
3. **Security First**: Always validate file paths are absolute
4. **Token Awareness**: Handle large inputs gracefully with prompt.txt mechanism
5. **Model Selection**: Choose appropriate model category for your tool's complexity
6. **Line Numbers**: Enable for tools needing precise code references
7. **Error Handling**: Provide helpful error messages for common issues
8. **Testing**: Write comprehensive unit tests and simulator tests
9. **Documentation**: Include examples and use cases in your description

## Common Pitfalls to Avoid

1. **Don't Skip Validation**: Always validate inputs, especially file paths
2. **Don't Ignore Token Limits**: Use `_validate_token_limit` and handle large prompts
3. **Don't Hardcode Models**: Use model categories for flexibility
4. **Don't Forget Tests**: Every tool needs tests for reliability
5. **Don't Break Conventions**: Follow existing patterns from other tools
6. **Don't Overlook Images**: Validate image limits based on model capabilities
7. **Don't Waste Tokens**: Use remaining_tokens budget for efficient allocation

## Testing Your Tool

### Manual Testing

1. Start the server with your tool registered
2. Use Claude Desktop to call your tool
3. Test various parameter combinations
4. Verify error handling

### Automated Testing

```bash
# Run unit tests
pytest tests/test_example.py -xvs

# Run all tests to ensure no regressions
pytest -xvs

# Run simulator tests if applicable
python communication_simulator_test.py
```

## Checklist

Before submitting your PR:

- [ ] Tool class created inheriting from `BaseTool`
- [ ] All abstract methods implemented
- [ ] Request model defined with proper validation
- [ ] System prompt created in `systemprompts/`
- [ ] Tool registered in `server.py`
- [ ] Unit tests written and passing
- [ ] Simulator tests added (if applicable)
- [ ] Documentation updated
- [ ] Code follows project style (ruff, black, isort)
- [ ] Large prompt handling implemented (if needed)
- [ ] Security validation for file paths
- [ ] Appropriate model category selected
- [ ] Tool description is clear and helpful

## Model Providers and Configuration

The Zen MCP Server supports multiple AI providers:

### Built-in Providers
- **Anthropic** (Claude models)
- **Google** (Gemini models) 
- **OpenAI** (GPT and O-series models)
- **X.AI** (Grok models)
- **Mistral** (Mistral models)
- **Meta** (Llama models via various providers)
- **Groq** (Fast inference)
- **Fireworks** (Open models)
- **OpenRouter** (Multi-provider gateway)
- **Deepseek** (Deepseek models)
- **Together** (Open models)

### Custom Endpoints
- **Ollama** - Local models via `http://host.docker.internal:11434/v1`
- **vLLM** - Custom inference endpoints

### Prompt Templates

The server supports prompt templates for quick tool invocation:

```python
PROMPT_TEMPLATES = {
    "thinkdeep": {
        "name": "thinkdeeper",
        "description": "Think deeply about the current context",
        "template": "Think deeper about this with {model} using {thinking_mode} thinking mode",
    },
    # Add your own templates in server.py
}
```

## Example: Complete Simple Tool

Here's a minimal but complete example tool:

```python
"""
Simple calculator tool for mathematical operations.
"""

from typing import Any, Optional
from mcp.types import TextContent
from pydantic import Field

from config import TEMPERATURE_ANALYTICAL
from .base import BaseTool, ToolRequest
from .models import ToolOutput


class CalculateRequest(ToolRequest):
    """Request model for calculator tool."""
    
    expression: str = Field(
        ...,
        description="Mathematical expression to evaluate"
    )


class CalculatorTool(BaseTool):
    """Simple calculator tool."""
    
    def get_name(self) -> str:
        return "calculate"
    
    def get_description(self) -> str:
        return (
            "CALCULATOR - Evaluates mathematical expressions. "
            "Use this for calculations, conversions, and math problems."
        )
    
    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                },
                "model": self.get_model_field_schema(),
            },
            "required": ["expression"] + (
                ["model"] if self.is_effective_auto_mode() else []
            ),
        }
        return schema
    
    def get_system_prompt(self) -> str:
        return """You are a mathematical assistant. Evaluate the expression 
        and explain the calculation steps clearly."""
    
    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL
    
    def get_request_model(self):
        return CalculateRequest
    
    async def prepare_prompt(self, request: CalculateRequest) -> str:
        return f"Calculate: {request.expression}\n\nShow your work step by step."
```

## Need Help?

- Look at existing tools (`chat.py`, `refactor.py`) for examples
- Check `base.py` for available helper methods
- Review test files for testing patterns
- Ask questions in GitHub issues if stuck