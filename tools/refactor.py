"""
Refactor tool - Intelligent code refactoring suggestions with precise line-number references

This tool analyzes code for refactoring opportunities across four main categories:
- codesmells: Detect and suggest fixes for common code smells
- decompose: Break down large functions, classes, and modules into smaller, focused components
- modernize: Update code to use modern language features and patterns
- organization: Suggest better organization and logical grouping of related functionality

Key Features:
- Cross-language support with language-specific guidance
- Precise line-number references for Claude
- Large context handling with token budgeting
- Structured JSON responses for easy parsing
- Style guide integration for project-specific patterns
"""

import logging
import os
from typing import Any, Literal, Optional

from pydantic import Field

from config import TEMPERATURE_ANALYTICAL
from systemprompts import REFACTOR_PROMPT

from .base import BaseTool, ToolRequest

logger = logging.getLogger(__name__)


# Field descriptions to avoid duplication between Pydantic and JSON schema
REFACTOR_FIELD_DESCRIPTIONS = {
    "files": "Code files or directories to analyze for refactoring opportunities. MUST be FULL absolute paths to real files / folders - DO NOT SHORTEN."
    "The files also MUST directly involve the classes, functions etc that need to be refactored. Closely related or dependent files"
    "will also help.",
    "prompt": "Description of refactoring goals, context, and specific areas of focus.",
    "refactor_type": "Type of refactoring analysis to perform",
    "focus_areas": "Specific areas to focus on (e.g., 'performance', 'readability', 'maintainability', 'security')",
    "style_guide_examples": (
        "Optional existing code files to use as style/pattern reference (must be FULL absolute paths to real files / folders - DO NOT SHORTEN). "
        "These files represent the target coding style and patterns for the project."
    ),
}


class RefactorRequest(ToolRequest):
    """
    Request model for the refactor tool.

    This model defines all parameters that can be used to customize
    the refactoring analysis process.
    """

    files: list[str] = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["files"])
    prompt: str = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["prompt"])
    refactor_type: Literal["codesmells", "decompose", "modernize", "organization"] = Field(
        ..., description=REFACTOR_FIELD_DESCRIPTIONS["refactor_type"]
    )
    focus_areas: Optional[list[str]] = Field(None, description=REFACTOR_FIELD_DESCRIPTIONS["focus_areas"])
    style_guide_examples: Optional[list[str]] = Field(
        None, description=REFACTOR_FIELD_DESCRIPTIONS["style_guide_examples"]
    )


class RefactorTool(BaseTool):
    """
    Refactor tool implementation.

    This tool analyzes code to provide intelligent refactoring suggestions
    with precise line-number references for Claude to implement.
    """

    def get_name(self) -> str:
        return "refactor"

    def get_description(self) -> str:
        return (
            "INTELLIGENT CODE REFACTORING - Analyzes code for refactoring opportunities with precise line-number guidance. "
            "Supports four refactor types: 'codesmells' (detect anti-patterns), 'decompose' (break down large functions/classes/modules into smaller components), "
            "'modernize' (update to modern language features), and 'organization' (improve organization and grouping of related functionality). "
            "Provides specific, actionable refactoring steps that Claude can implement directly. "
            "Choose thinking_mode based on codebase complexity: 'medium' for standard modules (default), "
            "'high' for complex systems, 'max' for legacy codebases requiring deep analysis. "
            "Note: If you're not currently using a top-tier model such as Opus 4 or above, these tools can provide enhanced capabilities."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": REFACTOR_FIELD_DESCRIPTIONS["files"],
                },
                "model": self.get_model_field_schema(),
                "prompt": {
                    "type": "string",
                    "description": REFACTOR_FIELD_DESCRIPTIONS["prompt"],
                },
                "refactor_type": {
                    "type": "string",
                    "enum": ["codesmells", "decompose", "modernize", "organization"],
                    "description": REFACTOR_FIELD_DESCRIPTIONS["refactor_type"],
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": REFACTOR_FIELD_DESCRIPTIONS["focus_areas"],
                },
                "style_guide_examples": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": REFACTOR_FIELD_DESCRIPTIONS["style_guide_examples"],
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), max (100% of model max)",
                },
                "continuation_id": {
                    "type": "string",
                    "description": (
                        "Thread continuation ID for multi-turn conversations. Can be used to continue conversations "
                        "across different tools. Only provide this if continuing a previous conversation thread."
                    ),
                },
            },
            "required": ["files", "prompt", "refactor_type"] + (["model"] if self.is_effective_auto_mode() else []),
        }

        return schema

    def get_system_prompt(self) -> str:
        return REFACTOR_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    # Line numbers are enabled by default from base class for precise targeting

    def get_model_category(self):
        """Refactor tool requires extended reasoning for comprehensive analysis"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_request_model(self):
        return RefactorRequest

    def detect_primary_language(self, file_paths: list[str]) -> str:
        """
        Detect the primary programming language from file extensions.

        Args:
            file_paths: List of file paths to analyze

        Returns:
            str: Detected language or "mixed" if multiple languages found
        """
        # Language detection based on file extensions
        language_extensions = {
            "python": {".py"},
            "javascript": {".js", ".jsx", ".mjs"},
            "typescript": {".ts", ".tsx"},
            "java": {".java"},
            "csharp": {".cs"},
            "cpp": {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"},
            "go": {".go"},
            "rust": {".rs"},
            "swift": {".swift"},
            "kotlin": {".kt"},
            "ruby": {".rb"},
            "php": {".php"},
            "scala": {".scala"},
        }

        # Count files by language
        language_counts = {}
        for file_path in file_paths:
            extension = os.path.splitext(file_path.lower())[1]
            for lang, exts in language_extensions.items():
                if extension in exts:
                    language_counts[lang] = language_counts.get(lang, 0) + 1
                    break

        if not language_counts:
            return "unknown"

        # Return most common language, or "mixed" if multiple languages
        max_count = max(language_counts.values())
        dominant_languages = [lang for lang, count in language_counts.items() if count == max_count]

        if len(dominant_languages) == 1:
            return dominant_languages[0]
        else:
            return "mixed"

    def get_language_specific_guidance(self, language: str, refactor_type: str) -> str:
        """
        Generate language-specific guidance for the refactoring prompt.

        Args:
            language: Detected programming language
            refactor_type: Type of refactoring being performed

        Returns:
            str: Language-specific guidance to inject into the prompt
        """
        if language == "unknown" or language == "mixed":
            return ""

        # Language-specific modernization features
        modernization_features = {
            "python": "f-strings, dataclasses, type hints, pathlib, async/await, context managers, list/dict comprehensions, walrus operator",
            "javascript": "async/await, destructuring, arrow functions, template literals, optional chaining, nullish coalescing, modules (import/export)",
            "typescript": "strict type checking, utility types, const assertions, template literal types, mapped types",
            "java": "streams API, lambda expressions, optional, records, pattern matching, var declarations, text blocks",
            "csharp": "LINQ, nullable reference types, pattern matching, records, async streams, using declarations",
            "swift": "value types, protocol-oriented programming, property wrappers, result builders, async/await",
            "go": "modules, error wrapping, context package, generics (Go 1.18+)",
            "rust": "ownership patterns, iterator adapters, error handling with Result, async/await",
        }

        # Language-specific code splitting patterns
        splitting_patterns = {
            "python": "modules, classes, functions, decorators for cross-cutting concerns",
            "javascript": "modules (ES6), classes, functions, higher-order functions",
            "java": "packages, classes, interfaces, abstract classes, composition over inheritance",
            "csharp": "namespaces, classes, interfaces, extension methods, dependency injection",
            "swift": "extensions, protocols, structs, enums with associated values",
            "go": "packages, interfaces, struct composition, function types",
        }

        guidance_parts = []

        if refactor_type == "modernize" and language in modernization_features:
            guidance_parts.append(
                f"LANGUAGE-SPECIFIC MODERNIZATION ({language.upper()}): Focus on {modernization_features[language]}"
            )

        if refactor_type == "decompose" and language in splitting_patterns:
            guidance_parts.append(
                f"LANGUAGE-SPECIFIC DECOMPOSITION ({language.upper()}): Use {splitting_patterns[language]} to break down large components"
            )

        # General language guidance
        general_guidance = {
            "python": "Follow PEP 8, use descriptive names, prefer composition over inheritance",
            "javascript": "Use consistent naming conventions, avoid global variables, prefer functional patterns",
            "java": "Follow Java naming conventions, use interfaces for abstraction, consider immutability",
            "csharp": "Follow C# naming conventions, use nullable reference types, prefer async methods",
        }

        if language in general_guidance:
            guidance_parts.append(f"GENERAL GUIDANCE ({language.upper()}): {general_guidance[language]}")

        return "\n".join(guidance_parts) if guidance_parts else ""

    def _process_style_guide_examples(
        self, style_examples: list[str], continuation_id: Optional[str], available_tokens: int = None
    ) -> tuple[str, str]:
        """
        Process style guide example files using available token budget.

        Args:
            style_examples: List of style guide file paths
            continuation_id: Continuation ID for filtering already embedded files
            available_tokens: Available token budget for examples

        Returns:
            tuple: (formatted_content, summary_note)
        """
        logger.debug(f"[REFACTOR] Processing {len(style_examples)} style guide examples")

        if not style_examples:
            logger.debug("[REFACTOR] No style guide examples provided")
            return "", ""

        # Use existing file filtering to avoid duplicates in continuation
        examples_to_process = self.filter_new_files(style_examples, continuation_id)
        logger.debug(f"[REFACTOR] After filtering: {len(examples_to_process)} new style examples to process")

        if not examples_to_process:
            logger.info(f"[REFACTOR] All {len(style_examples)} style examples already in conversation history")
            return "", ""

        logger.debug(f"[REFACTOR] Processing {len(examples_to_process)} file paths")

        # Calculate token budget for style examples (20% of available tokens, or fallback)
        if available_tokens:
            style_examples_budget = int(available_tokens * 0.20)  # 20% for style examples
            logger.debug(
                f"[REFACTOR] Allocating {style_examples_budget:,} tokens (20% of {available_tokens:,}) for style examples"
            )
        else:
            style_examples_budget = 25000  # Fallback if no budget provided
            logger.debug(f"[REFACTOR] Using fallback budget of {style_examples_budget:,} tokens for style examples")

        original_count = len(examples_to_process)
        logger.debug(
            f"[REFACTOR] Processing {original_count} style example files with {style_examples_budget:,} token budget"
        )

        # Sort by file size (smallest first) for pattern-focused selection
        file_sizes = []
        for file_path in examples_to_process:
            try:
                size = os.path.getsize(file_path)
                file_sizes.append((file_path, size))
                logger.debug(f"[REFACTOR] Style example {os.path.basename(file_path)}: {size:,} bytes")
            except (OSError, FileNotFoundError) as e:
                logger.warning(f"[REFACTOR] Could not get size for {file_path}: {e}")
                file_sizes.append((file_path, float("inf")))

        # Sort by size and take smallest files for pattern reference
        file_sizes.sort(key=lambda x: x[1])
        examples_to_process = [f[0] for f in file_sizes]
        logger.debug(
            f"[REFACTOR] Sorted style examples by size (smallest first): {[os.path.basename(f) for f in examples_to_process]}"
        )

        # Use standard file content preparation with dynamic token budget and line numbers
        try:
            logger.debug(f"[REFACTOR] Preparing file content for {len(examples_to_process)} style examples")
            content, processed_files = self._prepare_file_content_for_prompt(
                examples_to_process,
                continuation_id,
                "Style guide examples",
                max_tokens=style_examples_budget,
                reserve_tokens=1000,
            )
            # Store processed files for tracking - style examples are tracked separately from main code files

            # Determine how many files were actually included
            if content:
                from utils.token_utils import estimate_tokens

                used_tokens = estimate_tokens(content)
                logger.info(
                    f"[REFACTOR] Successfully embedded style examples: {used_tokens:,} tokens used ({style_examples_budget:,} available)"
                )
                if original_count > 1:
                    truncation_note = f"Note: Used {used_tokens:,} tokens ({style_examples_budget:,} available) for style guide examples from {original_count} files to determine coding patterns."
                else:
                    truncation_note = ""
            else:
                logger.warning("[REFACTOR] No content generated for style examples")
                truncation_note = ""

            return content, truncation_note

        except Exception as e:
            # If style example processing fails, continue without examples rather than failing
            logger.error(f"[REFACTOR] Failed to process style examples: {type(e).__name__}: {e}")
            return "", f"Warning: Could not process style guide examples: {str(e)}"

    async def prepare_prompt(self, request: RefactorRequest) -> str:
        """
        Prepare the refactoring prompt with code analysis and optional style examples.

        This method reads the requested files, processes any style guide examples,
        and constructs a detailed prompt for comprehensive refactoring analysis.

        Args:
            request: The validated refactor request

        Returns:
            str: Complete prompt for the model

        Raises:
            ValueError: If the code exceeds token limits
        """
        logger.info(f"[REFACTOR] prepare_prompt called with {len(request.files)} files, type={request.refactor_type}")
        logger.debug(f"[REFACTOR] Preparing prompt for {len(request.files)} code files")
        logger.debug(f"[REFACTOR] Refactor type: {request.refactor_type}")
        if request.style_guide_examples:
            logger.debug(f"[REFACTOR] Including {len(request.style_guide_examples)} style guide examples")

        # Check for prompt.txt in files
        prompt_content, updated_files = self.handle_prompt_file(request.files)

        # If prompt.txt was found, incorporate it into the prompt
        if prompt_content:
            logger.debug("[REFACTOR] Found prompt.txt file, incorporating content")
            request.prompt = prompt_content + "\n\n" + request.prompt

        # Update request files list
        if updated_files is not None:
            logger.debug(f"[REFACTOR] Updated files list after prompt.txt processing: {len(updated_files)} files")
            request.files = updated_files

        # Check user input size at MCP transport boundary (before adding internal content)
        user_content = request.prompt
        size_check = self.check_prompt_size(user_content)
        if size_check:
            from tools.models import ToolOutput

            raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        # Calculate available token budget for dynamic allocation
        continuation_id = getattr(request, "continuation_id", None)

        # Get model context for token budget calculation
        available_tokens = None

        if hasattr(self, "_model_context") and self._model_context:
            try:
                capabilities = self._model_context.capabilities
                # Use 75% of context for content (code + style examples), 25% for response
                available_tokens = int(capabilities.context_window * 0.75)
                logger.debug(
                    f"[REFACTOR] Token budget calculation: {available_tokens:,} tokens (75% of {capabilities.context_window:,}) for model {self._model_context.model_name}"
                )
            except Exception as e:
                # Fallback to conservative estimate
                logger.warning(f"[REFACTOR] Could not get model capabilities: {e}")
                available_tokens = 120000  # Conservative fallback
                logger.debug(f"[REFACTOR] Using fallback token budget: {available_tokens:,} tokens")
        else:
            # No model context available (shouldn't happen in normal flow)
            available_tokens = 120000  # Conservative fallback
            logger.debug(f"[REFACTOR] No model context, using fallback token budget: {available_tokens:,} tokens")

        # Process style guide examples first to determine token allocation
        style_examples_content = ""
        style_examples_note = ""

        if request.style_guide_examples:
            logger.debug(f"[REFACTOR] Processing {len(request.style_guide_examples)} style guide examples")
            style_examples_content, style_examples_note = self._process_style_guide_examples(
                request.style_guide_examples, continuation_id, available_tokens
            )
            if style_examples_content:
                logger.info("[REFACTOR] Style guide examples processed successfully for pattern reference")
            else:
                logger.info("[REFACTOR] No style guide examples content after processing")

        # Remove files that appear in both 'files' and 'style_guide_examples' to avoid duplicate embedding
        code_files_to_process = request.files.copy()
        if request.style_guide_examples:
            # Normalize paths for comparison
            style_example_set = {os.path.normpath(os.path.abspath(f)) for f in request.style_guide_examples}
            original_count = len(code_files_to_process)

            code_files_to_process = [
                f for f in code_files_to_process if os.path.normpath(os.path.abspath(f)) not in style_example_set
            ]

            duplicates_removed = original_count - len(code_files_to_process)
            if duplicates_removed > 0:
                logger.info(
                    f"[REFACTOR] Removed {duplicates_removed} duplicate files from code files list "
                    f"(already included in style guide examples for pattern reference)"
                )

        # Calculate remaining tokens for main code after style examples
        if style_examples_content and available_tokens:
            from utils.token_utils import estimate_tokens

            style_tokens = estimate_tokens(style_examples_content)
            remaining_tokens = available_tokens - style_tokens - 5000  # Reserve for prompt structure
            logger.debug(
                f"[REFACTOR] Token allocation: {style_tokens:,} for examples, {remaining_tokens:,} remaining for code files"
            )
        else:
            if available_tokens:
                remaining_tokens = available_tokens - 10000
            else:
                remaining_tokens = 110000  # Conservative fallback (120000 - 10000)
            logger.debug(
                f"[REFACTOR] Token allocation: {remaining_tokens:,} tokens available for code files (no style examples)"
            )

        # Use centralized file processing logic for main code files (with line numbers enabled)
        logger.debug(f"[REFACTOR] Preparing {len(code_files_to_process)} code files for analysis")
        code_content, processed_files = self._prepare_file_content_for_prompt(
            code_files_to_process, continuation_id, "Code to analyze", max_tokens=remaining_tokens, reserve_tokens=2000
        )
        self._actually_processed_files = processed_files

        if code_content:
            from utils.token_utils import estimate_tokens

            code_tokens = estimate_tokens(code_content)
            logger.info(f"[REFACTOR] Code files embedded successfully: {code_tokens:,} tokens")
        else:
            logger.warning("[REFACTOR] No code content after file processing")

        # Detect primary language for language-specific guidance
        primary_language = self.detect_primary_language(request.files)
        logger.debug(f"[REFACTOR] Detected primary language: {primary_language}")

        # Get language-specific guidance
        language_guidance = self.get_language_specific_guidance(primary_language, request.refactor_type)

        # Build the complete prompt
        prompt_parts = []

        # Add system prompt with dynamic language guidance
        base_system_prompt = self.get_system_prompt()
        if language_guidance:
            enhanced_system_prompt = f"{base_system_prompt}\n\n{language_guidance}"
        else:
            enhanced_system_prompt = base_system_prompt
        prompt_parts.append(enhanced_system_prompt)

        # Add user context
        prompt_parts.append("=== USER CONTEXT ===")
        prompt_parts.append(f"Refactor Type: {request.refactor_type}")
        if request.focus_areas:
            prompt_parts.append(f"Focus Areas: {', '.join(request.focus_areas)}")
        prompt_parts.append(f"User Goals: {request.prompt}")
        prompt_parts.append("=== END CONTEXT ===")

        # Add style guide examples if provided
        if style_examples_content:
            prompt_parts.append("\n=== STYLE GUIDE EXAMPLES ===")
            if style_examples_note:
                prompt_parts.append(f"// {style_examples_note}")
            prompt_parts.append(style_examples_content)
            prompt_parts.append("=== END STYLE GUIDE EXAMPLES ===")

        # Add main code to analyze
        prompt_parts.append("\n=== CODE TO ANALYZE ===")
        prompt_parts.append(code_content)
        prompt_parts.append("=== END CODE ===")

        # Add generation instructions
        prompt_parts.append(
            f"\nPlease analyze the code for {request.refactor_type} refactoring opportunities following the multi-expert workflow specified in the system prompt."
        )
        if style_examples_content:
            prompt_parts.append(
                "Use the provided style guide examples as a reference for target coding patterns and style."
            )

        full_prompt = "\n".join(prompt_parts)

        # Log final prompt statistics
        from utils.token_utils import estimate_tokens

        total_tokens = estimate_tokens(full_prompt)
        logger.info(f"[REFACTOR] Complete prompt prepared: {total_tokens:,} tokens, {len(full_prompt):,} characters")

        return full_prompt

    def format_response(self, response: str, request: RefactorRequest, model_info: Optional[dict] = None) -> str:
        """
        Format the refactoring response with immediate implementation directives.

        The base tool handles structured response validation via SPECIAL_STATUS_MODELS,
        so this method focuses on ensuring Claude immediately implements the refactorings.

        Args:
            response: The raw refactoring analysis from the model
            request: The original request for context
            model_info: Optional dict with model metadata

        Returns:
            str: The response with clear implementation directives
        """
        logger.debug(f"[REFACTOR] Formatting response for {request.refactor_type} refactoring")

        # Check if this response indicates more refactoring is required
        is_more_required = False
        try:
            import json

            parsed = json.loads(response)
            if isinstance(parsed, dict) and parsed.get("more_refactor_required") is True:
                is_more_required = True
        except (json.JSONDecodeError, ValueError):
            # Not JSON or parsing error
            pass

        continuation_instruction = ""
        if is_more_required:
            continuation_instruction = """

AFTER IMPLEMENTING ALL ABOVE: Use the refactor tool again with the SAME parameters but include the continuation_id from this response to get additional refactoring opportunities."""
        # endif

        # Return response + steps
        return f"""{response}

---

MANDATORY NEXT STEPS:

Start executing the refactoring plan immediately:
1. INFORM USER by displaying a brief summary of required refactorings
2. CREATE A CHECKLIST of each refactoring to keep a record of what is to change, how and why
3. IMPLEMENT each refactoring opportunity immediately - think carefully about each change as you implement
4. CREATE new files as needed where decomposition is suggested
5. MODIFY existing files to apply improvements as needed
6. UPDATE all imports, references, and dependencies as needed
7. VERIFY each change works before moving to the next

After each refactoring is implemented:
Show: `IMPLEMENTED: [brief description] - Files: [list]` to the user

IMPORTANT:
- DO NOT SKIP any refactorings - implement them all one after another
- VALIDATE each change doesn't break functionality
- UPDATE any imports and references properly and think and search for any other reference that may need updating
- TEST if possible to ensure changes work where tests are available

MANDATORY: MUST start executing the refactor plan and follow each step listed above{continuation_instruction}"""
