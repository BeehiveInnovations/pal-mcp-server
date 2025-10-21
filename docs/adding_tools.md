# Adding Tools to Zen MCP Server

Zen MCP tools are Python classes that inherit from the shared infrastructure in `tools/shared/base_tool.py`.
Every tool must provide a request model (Pydantic), a system prompt, and the methods the base class marks as
abstract. The quickest path to a working tool is to copy an existing implementation that matches your use case
(`tools/chat.py` for simple request/response tools, `tools/consensus.py` or `tools/codereview.py` for workflows).
This document captures the minimal steps required to add a new tool without drifting from the current codebase.

## 1. Pick the Tool Architecture

Zen supports two architectures, implemented in `tools/simple/base.py` and `tools/workflow/base.py`.

- **SimpleTool** (`SimpleTool`): single MCP call – request comes in, you build one prompt, call the model, return.
  The base class handles schema generation, conversation threading, file loading, temperature bounds, retries,
  and response formatting hooks.
- **WorkflowTool** (`WorkflowTool`): multi-step workflows driven by `BaseWorkflowMixin`. The tool accumulates
  findings across steps, forces Claude to pause between investigations, and optionally calls an expert model at
  the end. Use this whenever you need structured multi-step work (debug, code review, consensus, etc.).

If you are unsure, compare `tools/chat.py` (SimpleTool) and `tools/consensus.py` (WorkflowTool) to see the patterns.

## 2. Common Responsibilities

Regardless of architecture, subclasses of `BaseTool` must provide:

- `get_name()`: unique string identifier used in the MCP registry.
- `get_description()`: concise, action-oriented summary for clients.
- `get_system_prompt()`: import your prompt from `systemprompts/` and return it.
- `get_input_schema()`: leverage the schema builders (`SchemaBuilder` or `WorkflowSchemaBuilder`) or override to
  match an existing contract exactly.
- `get_request_model()`: return the Pydantic model used to validate the incoming arguments.
- `async prepare_prompt(...)`: assemble the content sent to the model. You can reuse helpers like
  `prepare_chat_style_prompt` or `build_standard_prompt`.

The base class already handles model selection (`ToolModelCategory`), conversation memory, token budgeting, safety
failures, retries, and serialization. Override hooks like `get_default_temperature`, `get_model_category`, or
`format_response` only when you need behaviour different from the defaults.

## 3. Implementing a Simple Tool

1. **Define a request model** that inherits from `tools.shared.base_models.ToolRequest` to describe the fields and
   validation rules for your tool.
2. **Implement the tool class** by inheriting from `SimpleTool` and overriding the required methods. Most tools can
   rely on `SchemaBuilder` and the shared field constants already exposed on `SimpleTool`.

```python
from pydantic import Field
from systemprompts import CHAT_PROMPT
from tools.shared.base_models import ToolRequest
from tools.simple.base import SimpleTool

class ChatRequest(ToolRequest):
    prompt: str = Field(..., description="Your question or idea.")
    absolute_file_paths: list[str] | None = Field(default_factory=list)
    working_directory_absolute_path: str = Field(
        ...,
        description="Absolute path to an existing directory where generated code can be saved.",
    )

class ChatTool(SimpleTool):
    def get_name(self) -> str:  # required by BaseTool
        return "chat"

    def get_description(self) -> str:
        return "General chat and collaborative thinking partner."

    def get_system_prompt(self) -> str:
        return CHAT_PROMPT

    def get_request_model(self):
        return ChatRequest

    def get_tool_fields(self) -> dict[str, dict[str, object]]:
        return {
            "prompt": {"type": "string", "description": "Your question."},
            "absolute_file_paths": SimpleTool.FILES_FIELD,
            "working_directory_absolute_path": {
                "type": "string",
                "description": "Absolute path to an existing directory for generated code artifacts.",
            },
        }

    def get_required_fields(self) -> list[str]:
        return ["prompt", "working_directory_absolute_path"]

    async def prepare_prompt(self, request: ChatRequest) -> str:
        return self.prepare_chat_style_prompt(request)
```

Only implement `get_input_schema()` manually if you must preserve an existing schema contract (see
`tools/chat.py` for an example). Otherwise `SimpleTool.get_input_schema()` merges your field definitions with the
common parameters (temperature, model, continuation_id, etc.).

## 4. Implementing a Workflow Tool

Workflow tools extend `WorkflowTool`, which mixes in `BaseWorkflowMixin` for step tracking and expert analysis.

1. **Create a request model** that inherits from `tools.shared.base_models.WorkflowRequest` (or a subclass) and add
   any tool-specific fields or validators. Examples: `CodeReviewRequest`, `ConsensusRequest`.
2. **Override the workflow hooks** to steer the investigation. At minimum you must implement
   `get_required_actions(...)`; override `should_call_expert_analysis(...)` and
   `prepare_expert_analysis_context(...)` when the expert model call should happen conditionally.
3. **Expose the schema** either by returning `WorkflowSchemaBuilder.build_schema(...)` (the default implementation on
   `WorkflowTool` already does this) or by overriding `get_input_schema()` if you need custom descriptions/enums.

```python
from pydantic import Field
from systemprompts import CONSENSUS_PROMPT
from tools.shared.base_models import WorkflowRequest
from tools.workflow.base import WorkflowTool

class ConsensusRequest(WorkflowRequest):
    models: list[dict] = Field(..., description="Models to consult (with optional stance).")

class ConsensusTool(WorkflowTool):
    def get_name(self) -> str:
        return "consensus"

    def get_description(self) -> str:
        return "Multi-model consensus workflow with expert synthesis."

    def get_system_prompt(self) -> str:
        return CONSENSUS_PROMPT

    def get_workflow_request_model(self):
        return ConsensusRequest

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int, request=None) -> list[str]:
        if step_number == 1:
            return ["Write the shared proposal all models will evaluate."]
        return ["Summarize the latest model response before moving on."]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        return not (request and request.next_step_required)

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        return "\n".join(consolidated_findings.findings)
```

`WorkflowTool` already records work history, merges findings, and handles continuation IDs. Use helpers such as
`get_standard_required_actions` when you want default guidance, and override `requires_expert_analysis()` if the tool
never calls out to the assistant model.

## 5. Register the Tool

1. **Create or reuse a system prompt** in `systemprompts/your_tool_prompt.py` and export it from
   `systemprompts/__init__.py`.
2. **Expose the tool class** from `tools/__init__.py` so that `server.py` can import it.
3. **Add an instance to the `TOOLS` dictionary** in `server.py`. This makes the tool callable via MCP.
4. **(Optional) Add a prompt template** to `PROMPT_TEMPLATES` in `server.py` if you want clients to show a canned
   launch command.
5. Confirm that `DISABLED_TOOLS` environment variable handling covers the new tool if you need to toggle it.

## 6. Validate the Tool

- Run unit tests that cover any new request/response logic: `python -m pytest tests/ -v -m "not integration"`.
- Add a simulator scenario in `simulator_tests/communication_simulator_test.py` to exercise the tool end-to-end and
  run it with `python communication_simulator_test.py --individual <case>` or `--quick` for the fast smoke suite.
- If the tool interacts with external providers or multiple models, consider integration coverage via
  `./run_integration_tests.sh --with-simulator`.

Following the steps above keeps new tools aligned with the existing infrastructure and avoids drift between the
documentation and the actual base classes.
