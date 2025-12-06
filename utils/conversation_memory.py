"""
Conversation Memory for AI-to-AI Multi-turn Discussions

This module provides conversation persistence and context reconstruction for
stateless MCP (Model Context Protocol) environments. It enables multi-turn
conversations between the agent and downstream models by storing conversation
state in memory across independent request cycles.

CRITICAL ARCHITECTURAL REQUIREMENT:
This conversation memory system is designed for PERSISTENT MCP SERVER PROCESSES.
It uses in-memory storage that persists only within a single Python process.

⚠️  IMPORTANT: This system will NOT work correctly if MCP tool calls are made
    as separate subprocess invocations (each subprocess starts with empty memory).

    WORKING SCENARIO: Claude Desktop with persistent MCP server process
    FAILING SCENARIO: Simulator tests calling server.py as individual subprocesses

    Root cause of test failures: Each subprocess call loses the conversation
    state from previous calls because memory is process-specific, not shared
    across subprocess boundaries.

ARCHITECTURE OVERVIEW:
The MCP protocol is inherently stateless - each tool request is independent
with no memory of previous interactions. This module bridges that gap by:

1. Creating persistent conversation threads with unique UUIDs
2. Storing complete conversation context (turns, files, metadata) in memory
3. Reconstructing conversation history when tools are called with continuation_id
4. Supporting cross-tool continuation - seamlessly switch between different tools
   while maintaining full conversation context and file references

CROSS-TOOL CONTINUATION:
A conversation started with one tool (e.g., 'analyze') can be continued with
any other tool (e.g., 'codereview', 'debug', 'chat') using the same continuation_id.
The second tool will have access to:
- All previous conversation turns and responses
- File context from previous tools (preserved in conversation history)
- Original thread metadata and timing information
- Accumulated knowledge from the entire conversation

Key Features:
- UUID-based conversation thread identification with security validation
- Turn-by-turn conversation history storage with tool attribution
- Cross-tool continuation support - switch tools while preserving context
- File context preservation - files shared in earlier turns remain accessible
- NEWEST-FIRST FILE PRIORITIZATION - when the same file appears in multiple turns,
  references from newer turns take precedence over older ones. This ensures the
  most recent file context is preserved when token limits require exclusions.
- Automatic turn limiting (20 turns max) to prevent runaway conversations
- Context reconstruction for stateless request continuity
- In-memory persistence with automatic expiration (3 hour TTL)
- Thread-safe operations for concurrent access
- Graceful degradation when storage is unavailable

DUAL PRIORITIZATION STRATEGY (Files & Conversations):
The conversation memory system implements sophisticated prioritization for both files and
conversation turns, using a consistent "newest-first" approach during collection but
presenting information in the optimal format for LLM consumption:

FILE PRIORITIZATION (Newest-First Throughout):
1. When collecting files across conversation turns, the system walks BACKWARDS through
   turns (newest to oldest) and builds a unique file list
2. If the same file path appears in multiple turns, only the reference from the
   NEWEST turn is kept in the final list
3. This "newest-first" ordering is preserved throughout the entire pipeline:
   - get_conversation_file_list() establishes the order
   - build_conversation_history() maintains it during token budgeting
   - When token limits are hit, OLDER files are excluded first
4. This strategy works across conversation chains - files from newer turns in ANY
   thread take precedence over files from older turns in ANY thread

CONVERSATION TURN PRIORITIZATION (Newest-First Collection, Chronological Presentation):
1. COLLECTION PHASE: Processes turns newest-to-oldest to prioritize recent context
   - When token budget is tight, OLDER turns are excluded first
   - Ensures most contextually relevant recent exchanges are preserved
2. PRESENTATION PHASE: Reverses collected turns to chronological order (oldest-first)
   - LLM sees natural conversation flow: "Turn 1 → Turn 2 → Turn 3..."
   - Maintains proper sequential understanding while preserving recency prioritization

This dual approach ensures optimal context preservation (newest-first) with natural
conversation flow (chronological) for maximum LLM comprehension and relevance.

USAGE EXAMPLE:
1. Tool A creates thread: create_thread("analyze", request_data) → returns UUID
2. Tool A adds response: add_turn(UUID, "assistant", response, files=[...], tool_name="analyze")
3. Tool B continues thread: get_thread(UUID) → retrieves full context
4. Tool B sees conversation history via build_conversation_history()
5. Tool B adds its response: add_turn(UUID, "assistant", response, tool_name="codereview")

DUAL STRATEGY EXAMPLE:
Conversation has 5 turns, token budget allows only 3 turns:

Collection Phase (Newest-First Priority):
- Evaluates: Turn 5 → Turn 4 → Turn 3 → Turn 2 → Turn 1
- Includes: Turn 5, Turn 4, Turn 3 (newest 3 fit in budget)
- Excludes: Turn 2, Turn 1 (oldest, dropped due to token limits)

Presentation Phase (Chronological Order):
- LLM sees: "--- Turn 3 (Agent) ---", "--- Turn 4 (Model) ---", "--- Turn 5 (Agent) ---"
- Natural conversation flow maintained despite prioritizing recent context

This enables true AI-to-AI collaboration across the entire tool ecosystem with optimal
context preservation and natural conversation understanding.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from utils.env import get_env

logger = logging.getLogger(__name__)

# Configuration constants
# Get max conversation turns from environment, default to 20 turns (10 exchanges)
try:
    max_turns_raw = (get_env("MAX_CONVERSATION_TURNS", "50") or "50").strip()
    MAX_CONVERSATION_TURNS = int(max_turns_raw)
    if MAX_CONVERSATION_TURNS <= 0:
        logger.warning(f"Invalid MAX_CONVERSATION_TURNS value ({MAX_CONVERSATION_TURNS}), using default of 50 turns")
        MAX_CONVERSATION_TURNS = 50
except ValueError:
    logger.warning(
        f"Invalid MAX_CONVERSATION_TURNS value ('{get_env('MAX_CONVERSATION_TURNS')}'), using default of 50 turns"
    )
    MAX_CONVERSATION_TURNS = 50

# Get conversation timeout from environment (in hours), default to 3 hours
try:
    timeout_raw = (get_env("CONVERSATION_TIMEOUT_HOURS", "3") or "3").strip()
    CONVERSATION_TIMEOUT_HOURS = int(timeout_raw)
    if CONVERSATION_TIMEOUT_HOURS <= 0:
        logger.warning(
            f"Invalid CONVERSATION_TIMEOUT_HOURS value ({CONVERSATION_TIMEOUT_HOURS}), using default of 3 hours"
        )
        CONVERSATION_TIMEOUT_HOURS = 3
except ValueError:
    logger.warning(
        f"Invalid CONVERSATION_TIMEOUT_HOURS value ('{get_env('CONVERSATION_TIMEOUT_HOURS')}'), using default of 3 hours"
    )
    CONVERSATION_TIMEOUT_HOURS = 3

CONVERSATION_TIMEOUT_SECONDS = CONVERSATION_TIMEOUT_HOURS * 3600


class ConversationTurn(BaseModel):
    """
    Single turn in a conversation

    Represents one exchange in the AI-to-AI conversation, tracking both
    the content and metadata needed for cross-tool continuation.

    Attributes:
        role: "user" (Agent request) or "assistant" (model response)
        content: The actual message content/response
        timestamp: ISO timestamp when this turn was created
        files: List of file paths referenced in this specific turn
        images: List of image paths referenced in this specific turn
        tool_name: Which tool generated this turn (for cross-tool tracking)
        model_provider: Provider used (e.g., "google", "openai")
        model_name: Specific model used (e.g., "gemini-2.5-flash", "o3-mini")
        model_metadata: Additional model-specific metadata (e.g., thinking mode, token usage)
    """

    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    files: Optional[list[str]] = None  # Files referenced in this turn
    images: Optional[list[str]] = None  # Images referenced in this turn
    tool_name: Optional[str] = None  # Tool used for this turn
    model_provider: Optional[str] = None  # Model provider (google, openai, etc)
    model_name: Optional[str] = None  # Specific model used
    model_metadata: Optional[dict[str, Any]] = None  # Additional model info


class ThreadContext(BaseModel):
    """
    Complete conversation context for a thread

    Contains all information needed to reconstruct a conversation state
    across different tools and request cycles. This is the core data
    structure that enables cross-tool continuation.

    Attributes:
        thread_id: UUID identifying this conversation thread
        parent_thread_id: UUID of parent thread (for conversation chains)
        created_at: ISO timestamp when thread was created
        last_updated_at: ISO timestamp of last modification
        tool_name: Name of the tool that initiated this thread
        turns: List of all conversation turns in chronological order
        initial_context: Original request data that started the conversation
    """

    thread_id: str
    parent_thread_id: Optional[str] = None  # Parent thread for conversation chains
    created_at: str
    last_updated_at: str
    tool_name: str  # Tool that created this thread (preserved for attribution)
    turns: list[ConversationTurn]
    initial_context: dict[str, Any]  # Original request parameters


def get_storage():
    """
    Get in-memory storage backend for conversation persistence.

    Returns:
        InMemoryStorage: Thread-safe in-memory storage backend
    """
    from .storage_backend import get_storage_backend

    return get_storage_backend()


def create_thread(tool_name: str, initial_request: dict[str, Any], parent_thread_id: Optional[str] = None) -> str:
    """
    Create new conversation thread and return thread ID

    Initializes a new conversation thread for AI-to-AI discussions.
    This is called when a tool wants to enable follow-up conversations
    or when Claude explicitly starts a multi-turn interaction.

    Args:
        tool_name: Name of the tool creating this thread (e.g., "analyze", "chat")
        initial_request: Original request parameters (will be filtered for serialization)
        parent_thread_id: Optional parent thread ID for conversation chains

    Returns:
        str: UUID thread identifier that can be used for continuation

    Note:
        - Thread expires after the configured timeout (default: 3 hours)
        - Non-serializable parameters are filtered out automatically
        - Thread can be continued by any tool using the returned UUID
        - Parent thread creates a chain for conversation history traversal
    """
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Filter out non-serializable parameters to avoid JSON encoding issues
    filtered_context = {
        k: v
        for k, v in initial_request.items()
        if k not in ["temperature", "thinking_mode", "model", "continuation_id"]
    }

    context = ThreadContext(
        thread_id=thread_id,
        parent_thread_id=parent_thread_id,  # Link to parent for conversation chains
        created_at=now,
        last_updated_at=now,
        tool_name=tool_name,  # Track which tool initiated this conversation
        turns=[],  # Empty initially, turns added via add_turn()
        initial_context=filtered_context,
    )

    # Store in memory with configurable TTL to prevent indefinite accumulation
    storage = get_storage()
    key = f"thread:{thread_id}"
    storage.setex(key, CONVERSATION_TIMEOUT_SECONDS, context.model_dump_json())

    logger.debug(f"[THREAD] Created new thread {thread_id} with parent {parent_thread_id}")

    return thread_id


def get_thread(thread_id: str) -> Optional[ThreadContext]:
    """
    Retrieve thread context from in-memory storage

    Fetches complete conversation context for cross-tool continuation.
    This is the core function that enables tools to access conversation
    history from previous interactions.

    Args:
        thread_id: UUID of the conversation thread

    Returns:
        ThreadContext: Complete conversation context if found
        None: If thread doesn't exist, expired, or invalid UUID

    Security:
        - Validates UUID format to prevent injection attacks
        - Handles storage connection failures gracefully
        - No error information leakage on failure
    """
    if not thread_id or not _is_valid_uuid(thread_id):
        return None

    try:
        storage = get_storage()
        key = f"thread:{thread_id}"
        data = storage.get(key)

        if data:
            return ThreadContext.model_validate_json(data)
        return None
    except Exception:
        # Silently handle errors to avoid exposing storage details
        return None


def add_turn(
    thread_id: str,
    role: str,
    content: str,
    files: Optional[list[str]] = None,
    images: Optional[list[str]] = None,
    tool_name: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    model_metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Add turn to existing thread with atomic file ordering.

    Appends a new conversation turn to an existing thread. This is the core
    function for building conversation history and enabling cross-tool
    continuation. Each turn preserves the tool and model that generated it.

    Args:
        thread_id: UUID of the conversation thread
        role: "user" (Agent request) or "assistant" (model response)
        content: The actual message/response content
        files: Optional list of files referenced in this turn
        images: Optional list of images referenced in this turn
        tool_name: Name of the tool adding this turn (for attribution)
        model_provider: Provider used (e.g., "google", "openai")
        model_name: Specific model used (e.g., "gemini-2.5-flash", "o3-mini")
        model_metadata: Additional model info (e.g., thinking mode, token usage)

    Returns:
        bool: True if turn was successfully added, False otherwise

    Failure cases:
        - Thread doesn't exist or expired
        - Maximum turn limit reached
        - Storage connection failure

    Note:
        - Refreshes thread TTL to configured timeout on successful update
        - Turn limits prevent runaway conversations
        - File references are preserved for cross-tool access with atomic ordering
        - Image references are preserved for cross-tool visual context
        - Model information enables cross-provider conversations
    """
    logger.debug(f"[FLOW] Adding {role} turn to {thread_id} ({tool_name})")

    context = get_thread(thread_id)
    if not context:
        logger.debug(f"[FLOW] Thread {thread_id} not found for turn addition")
        return False

    # Check turn limit to prevent runaway conversations
    if len(context.turns) >= MAX_CONVERSATION_TURNS:
        logger.debug(f"[FLOW] Thread {thread_id} at max turns ({MAX_CONVERSATION_TURNS})")
        return False

    # Create new turn with complete metadata
    turn = ConversationTurn(
        role=role,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        files=files,  # Preserved for cross-tool file context
        images=images,  # Preserved for cross-tool visual context
        tool_name=tool_name,  # Track which tool generated this turn
        model_provider=model_provider,  # Track model provider
        model_name=model_name,  # Track specific model
        model_metadata=model_metadata,  # Additional model info
    )

    context.turns.append(turn)
    context.last_updated_at = datetime.now(timezone.utc).isoformat()

    # Save back to storage and refresh TTL
    try:
        storage = get_storage()
        key = f"thread:{thread_id}"
        storage.setex(key, CONVERSATION_TIMEOUT_SECONDS, context.model_dump_json())  # Refresh TTL to configured timeout
        return True
    except Exception as e:
        logger.debug(f"[FLOW] Failed to save turn to storage: {type(e).__name__}")
        return False


def get_thread_chain(thread_id: str, max_depth: int = 20) -> list[ThreadContext]:
    """
    Traverse the parent chain to get all threads in conversation sequence.

    Retrieves the complete conversation chain by following parent_thread_id
    links. Returns threads in chronological order (oldest first).

    Args:
        thread_id: Starting thread ID
        max_depth: Maximum chain depth to prevent infinite loops

    Returns:
        list[ThreadContext]: All threads in chain, oldest first
    """
    chain = []
    current_id = thread_id
    seen_ids = set()

    # Build chain from current to oldest
    while current_id and len(chain) < max_depth:
        # Prevent circular references
        if current_id in seen_ids:
            logger.warning(f"[THREAD] Circular reference detected in thread chain at {current_id}")
            break

        seen_ids.add(current_id)

        context = get_thread(current_id)
        if not context:
            logger.debug(f"[THREAD] Thread {current_id} not found in chain traversal")
            break

        chain.append(context)
        current_id = context.parent_thread_id

    # Reverse to get chronological order (oldest first)
    chain.reverse()

    logger.debug(f"[THREAD] Retrieved chain of {len(chain)} threads for {thread_id}")
    return chain


def get_conversation_file_list(context: ThreadContext) -> list[str]:
    """
    Extract all unique files from conversation turns with newest-first prioritization.

    This function implements the core file prioritization logic used throughout the
    conversation memory system. It walks backwards through conversation turns
    (from newest to oldest) and collects unique file references, ensuring that
    when the same file appears in multiple turns, the reference from the NEWEST
    turn takes precedence.

    PRIORITIZATION ALGORITHM:
    1. Iterate through turns in REVERSE order (index len-1 down to 0)
    2. For each turn, process files in the order they appear in turn.files
    3. Add file to result list only if not already seen (newest reference wins)
    4. Skip duplicate files that were already added from newer turns

    This ensures that:
    - Files from newer conversation turns appear first in the result
    - When the same file is referenced multiple times, only the newest reference is kept
    - The order reflects the most recent conversation context

    Example:
        Turn 1: files = ["main.py", "utils.py"]
        Turn 2: files = ["test.py"]
        Turn 3: files = ["main.py", "config.py"]  # main.py appears again

        Result: ["main.py", "config.py", "test.py", "utils.py"]
        (main.py from Turn 3 takes precedence over Turn 1)

    Args:
        context: ThreadContext containing all conversation turns to process

    Returns:
        list[str]: Unique file paths ordered by newest reference first.
                   Empty list if no turns exist or no files are referenced.

    Performance:
        - Time Complexity: O(n*m) where n=turns, m=avg files per turn
        - Space Complexity: O(f) where f=total unique files
        - Uses set for O(1) duplicate detection
    """
    if not context.turns:
        logger.debug("[FILES] No turns found, returning empty file list")
        return []

    # Collect files by walking backwards (newest to oldest turns)
    seen_files = set()
    file_list = []

    logger.debug(f"[FILES] Collecting files from {len(context.turns)} turns (newest first)")

    # Process turns in reverse order (newest first) - this is the CORE of newest-first prioritization
    # By iterating from len-1 down to 0, we encounter newer turns before older turns
    # When we find a duplicate file, we skip it because the newer version is already in our list
    for i in range(len(context.turns) - 1, -1, -1):  # REVERSE: newest turn first
        turn = context.turns[i]
        if turn.files:
            logger.debug(f"[FILES] Turn {i + 1} has {len(turn.files)} files: {turn.files}")
            for file_path in turn.files:
                if file_path not in seen_files:
                    # First time seeing this file - add it (this is the NEWEST reference)
                    seen_files.add(file_path)
                    file_list.append(file_path)
                    logger.debug(f"[FILES] Added new file: {file_path} (from turn {i + 1})")
                else:
                    # File already seen from a NEWER turn - skip this older reference
                    logger.debug(f"[FILES] Skipping duplicate file: {file_path} (newer version already included)")

    logger.debug(f"[FILES] Final file list ({len(file_list)}): {file_list}")
    return file_list


def get_conversation_image_list(context: ThreadContext) -> list[str]:
    """
    Extract all unique images from conversation turns with newest-first prioritization.

    This function implements the identical prioritization logic as get_conversation_file_list()
    to ensure consistency in how images are handled across conversation turns. It walks
    backwards through conversation turns (from newest to oldest) and collects unique image
    references, ensuring that when the same image appears in multiple turns, the reference
    from the NEWEST turn takes precedence.

    PRIORITIZATION ALGORITHM:
    1. Iterate through turns in REVERSE order (index len-1 down to 0)
    2. For each turn, process images in the order they appear in turn.images
    3. Add image to result list only if not already seen (newest reference wins)
    4. Skip duplicate images that were already added from newer turns

    This ensures that:
    - Images from newer conversation turns appear first in the result
    - When the same image is referenced multiple times, only the newest reference is kept
    - The order reflects the most recent conversation context

    Example:
        Turn 1: images = ["diagram.png", "flow.jpg"]
        Turn 2: images = ["error.png"]
        Turn 3: images = ["diagram.png", "updated.png"]  # diagram.png appears again

        Result: ["diagram.png", "updated.png", "error.png", "flow.jpg"]
        (diagram.png from Turn 3 takes precedence over Turn 1)

    Args:
        context: ThreadContext containing all conversation turns to process

    Returns:
        list[str]: Unique image paths ordered by newest reference first.
                   Empty list if no turns exist or no images are referenced.

    Performance:
        - Time Complexity: O(n*m) where n=turns, m=avg images per turn
        - Space Complexity: O(i) where i=total unique images
        - Uses set for O(1) duplicate detection
    """
    if not context.turns:
        logger.debug("[IMAGES] No turns found, returning empty image list")
        return []

    # Collect images by walking backwards (newest to oldest turns)
    seen_images = set()
    image_list = []

    logger.debug(f"[IMAGES] Collecting images from {len(context.turns)} turns (newest first)")

    # Process turns in reverse order (newest first) - this is the CORE of newest-first prioritization
    # By iterating from len-1 down to 0, we encounter newer turns before older turns
    # When we find a duplicate image, we skip it because the newer version is already in our list
    for i in range(len(context.turns) - 1, -1, -1):  # REVERSE: newest turn first
        turn = context.turns[i]
        if turn.images:
            logger.debug(f"[IMAGES] Turn {i + 1} has {len(turn.images)} images: {turn.images}")
            for image_path in turn.images:
                if image_path not in seen_images:
                    # First time seeing this image - add it (this is the NEWEST reference)
                    seen_images.add(image_path)
                    image_list.append(image_path)
                    logger.debug(f"[IMAGES] Added new image: {image_path} (from turn {i + 1})")
                else:
                    # Image already seen from a NEWER turn - skip this older reference
                    logger.debug(f"[IMAGES] Skipping duplicate image: {image_path} (newer version already included)")

    logger.debug(f"[IMAGES] Final image list ({len(image_list)}): {image_list}")
    return image_list


def _plan_file_inclusion_by_size(
    all_files: list[str], max_file_tokens: int, model_context=None
) -> tuple[list[str], list[str], int]:
    """
    Plan which files to include based on size constraints.

    This is ONLY used for conversation history building, not MCP boundary checks.

    Args:
        all_files: List of files to consider for inclusion
        max_file_tokens: Maximum tokens available for file content
        model_context: Optional ModelContext for provider-specific token estimation

    Returns:
        Tuple of (files_to_include, files_to_skip, estimated_total_tokens)
    """
    if not all_files:
        return [], [], 0

    files_to_include = []
    files_to_skip = []
    total_tokens = 0

    logger.debug(f"[FILES] Planning inclusion for {len(all_files)} files with budget {max_file_tokens:,} tokens")

    for file_path in all_files:
        try:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                # Use model-specific token estimation when available (e.g., Gemini)
                # Falls back to file_utils estimation for other providers
                if model_context:
                    estimated_tokens = model_context.estimate_file_tokens(file_path)
                else:
                    from utils.file_utils import estimate_file_tokens

                    estimated_tokens = estimate_file_tokens(file_path)

                if total_tokens + estimated_tokens <= max_file_tokens:
                    files_to_include.append(file_path)
                    total_tokens += estimated_tokens
                    logger.debug(
                        f"[FILES] Including {file_path} - {estimated_tokens:,} tokens (total: {total_tokens:,})"
                    )
                else:
                    files_to_skip.append(file_path)
                    logger.debug(
                        f"[FILES] Skipping {file_path} - would exceed budget (needs {estimated_tokens:,} tokens)"
                    )
            else:
                files_to_skip.append(file_path)
                # More descriptive message for missing files
                if not os.path.exists(file_path):
                    logger.debug(
                        f"[FILES] Skipping {file_path} - file no longer exists (may have been moved/deleted since conversation)"
                    )
                else:
                    logger.debug(f"[FILES] Skipping {file_path} - file not accessible (not a regular file)")

        except Exception as e:
            files_to_skip.append(file_path)
            logger.debug(f"[FILES] Skipping {file_path} - error during processing: {type(e).__name__}: {e}")

    logger.debug(
        f"[FILES] Inclusion plan: {len(files_to_include)} include, {len(files_to_skip)} skip, {total_tokens:,} tokens"
    )
    return files_to_include, files_to_skip, total_tokens


def build_conversation_history(context: ThreadContext, model_context=None, read_files_func=None) -> tuple[str, int]:
    """
    Build formatted conversation history for tool prompts with embedded file contents.

    Creates a comprehensive conversation history that includes both conversation turns and
    file contents, with intelligent prioritization to maximize relevant context within
    token limits. This function enables stateless tools to access complete conversation
    context from previous interactions, including cross-tool continuations.

    FILE PRIORITIZATION BEHAVIOR:
    Files from newer conversation turns are prioritized over files from older turns.
    When the same file appears in multiple turns, the reference from the NEWEST turn
    takes precedence. This ensures the most recent file context is preserved when
    token limits require file exclusions.

    CONVERSATION CHAIN HANDLING:
    If the thread has a parent_thread_id, this function traverses the entire chain
    to include complete conversation history across multiple linked threads. File
    prioritization works across the entire chain, not just the current thread.

    CONVERSATION TURN ORDERING STRATEGY:
    The function employs a sophisticated two-phase approach for optimal token utilization:

    PHASE 1 - COLLECTION (Newest-First for Token Budget):
    - Processes conversation turns in REVERSE chronological order (newest to oldest)
    - Prioritizes recent turns within token constraints
    - If token budget is exceeded, OLDER turns are excluded first
    - Ensures the most contextually relevant recent exchanges are preserved

    PHASE 2 - PRESENTATION (Chronological for LLM Understanding):
    - Reverses the collected turns back to chronological order (oldest to newest)
    - Presents conversation flow naturally for LLM comprehension
    - Maintains "--- Turn 1, Turn 2, Turn 3..." sequential numbering
    - Enables LLM to follow conversation progression logically

    This approach balances recency prioritization with natural conversation flow.

    TOKEN MANAGEMENT:
    - Uses model-specific token allocation (file_tokens + history_tokens)
    - Files are embedded ONCE at the start to prevent duplication
    - Turn collection prioritizes newest-first, presentation shows chronologically
    - Stops adding turns when token budget would be exceeded
    - Gracefully handles token limits with informative notes

    Args:
        context: ThreadContext containing the conversation to format
        model_context: ModelContext for token allocation (optional, uses DEFAULT_MODEL fallback)
        read_files_func: Optional function to read files (primarily for testing)

    Returns:
        tuple[str, int]: (formatted_conversation_history, total_tokens_used)
        Returns ("", 0) if no conversation turns exist in the context

    Output Format:
        === CONVERSATION HISTORY (CONTINUATION) ===
        Thread: <thread_id>
        Tool: <original_tool_name>
        Turn <current>/<max_allowed>
        You are continuing this conversation thread from where it left off.

        === FILES REFERENCED IN THIS CONVERSATION ===
        The following files have been shared and analyzed during our conversation.
        [NOTE: X files omitted due to size constraints]
        Refer to these when analyzing the context and requests below:

        <embedded_file_contents_with_line_numbers>

        === END REFERENCED FILES ===

        Previous conversation turns:

        --- Turn 1 (Claude) ---
        Files used in this turn: file1.py, file2.py

        <turn_content>

        --- Turn 2 (gemini-2.5-flash using analyze via google) ---
        Files used in this turn: file3.py

        <turn_content>

        === END CONVERSATION HISTORY ===

        IMPORTANT: You are continuing an existing conversation thread...
        This is turn X of the conversation - use the conversation history above...

    Cross-Tool Collaboration:
        This formatted history allows any tool to "see" both conversation context AND
        file contents from previous tools, enabling seamless handoffs between analyze,
        codereview, debug, chat, and other tools while maintaining complete context.

    Performance Characteristics:
        - O(n) file collection with newest-first prioritization
        - Intelligent token budgeting prevents context window overflow
        - In-memory persistence with automatic TTL management
        - Graceful degradation when files are inaccessible or too large
    """
    # Get the complete thread chain
    if context.parent_thread_id:
        # This thread has a parent, get the full chain
        chain = get_thread_chain(context.thread_id)

        # Collect all turns from all threads in chain
        all_turns = []
        total_turns = 0

        for thread in chain:
            all_turns.extend(thread.turns)
            total_turns += len(thread.turns)

        # Use centralized file collection logic for consistency across the entire chain
        # This ensures files from newer turns across ALL threads take precedence
        # over files from older turns, maintaining the newest-first prioritization
        # even when threads are chained together
        temp_context = ThreadContext(
            thread_id="merged_chain",
            created_at=context.created_at,
            last_updated_at=context.last_updated_at,
            tool_name=context.tool_name,
            turns=all_turns,  # All turns from entire chain in chronological order
            initial_context=context.initial_context,
        )
        all_files = get_conversation_file_list(temp_context)  # Applies newest-first logic to entire chain
        logger.debug(f"[THREAD] Built history from {len(chain)} threads with {total_turns} total turns")
    else:
        # Single thread, no parent chain
        all_turns = context.turns
        total_turns = len(context.turns)
        all_files = get_conversation_file_list(context)

    if not all_turns:
        return "", 0

    logger.debug(f"[FILES] Found {len(all_files)} unique files in conversation history")

    # Get model-specific token allocation early (needed for both files and turns)
    if model_context is None:
        from config import DEFAULT_MODEL, IS_AUTO_MODE
        from utils.model_context import ModelContext

        # In auto mode, use an intelligent fallback model for token calculations
        # since "auto" is not a real model with a provider
        model_name = DEFAULT_MODEL
        if IS_AUTO_MODE and model_name.lower() == "auto":
            # Use intelligent fallback based on available API keys
            from providers.registry import ModelProviderRegistry

            model_name = ModelProviderRegistry.get_preferred_fallback_model()

        model_context = ModelContext(model_name)

    token_allocation = model_context.calculate_token_allocation()
    max_file_tokens = token_allocation.file_tokens
    max_history_tokens = token_allocation.history_tokens

    logger.debug(f"[HISTORY] Using model-specific limits for {model_context.model_name}:")
    logger.debug(f"[HISTORY]   Max file tokens: {max_file_tokens:,}")
    logger.debug(f"[HISTORY]   Max history tokens: {max_history_tokens:,}")

    history_parts = [
        "=== CONVERSATION HISTORY (CONTINUATION) ===",
        f"Thread: {context.thread_id}",
        f"Tool: {context.tool_name}",  # Original tool that started the conversation
        f"Turn {total_turns}/{MAX_CONVERSATION_TURNS}",
        "You are continuing this conversation thread from where it left off.",
        "",
    ]

    # Embed files referenced in this conversation with size-aware selection
    if all_files:
        logger.debug(f"[FILES] Starting embedding for {len(all_files)} files")

        # Plan file inclusion based on size constraints
        # CRITICAL: all_files is already ordered by newest-first prioritization from get_conversation_file_list()
        # So when _plan_file_inclusion_by_size() hits token limits, it naturally excludes OLDER files first
        # while preserving the most recent file references - exactly what we want!
        files_to_include, files_to_skip, estimated_tokens = _plan_file_inclusion_by_size(
            all_files, max_file_tokens, model_context
        )

        if files_to_skip:
            logger.info(f"[FILES] Excluding {len(files_to_skip)} files from conversation history: {files_to_skip}")
            logger.debug("[FILES] Files excluded for various reasons (size constraints, missing files, access issues)")

        if files_to_include:
            history_parts.extend(
                [
                    "=== FILES REFERENCED IN THIS CONVERSATION ===",
                    "The following files have been shared and analyzed during our conversation.",
                    (
                        ""
                        if not files_to_skip
                        else f"[NOTE: {len(files_to_skip)} files omitted (size constraints, missing files, or access issues)]"
                    ),
                    "Refer to these when analyzing the context and requests below:",
                    "",
                ]
            )

            if read_files_func is None:
                from utils.file_utils import read_file_content

                # Process files for embedding
                file_contents = []
                total_tokens = 0
                files_included = 0

                for file_path in files_to_include:
                    try:
                        logger.debug(f"[FILES] Processing file {file_path}")
                        formatted_content, content_tokens = read_file_content(file_path)
                        if formatted_content:
                            file_contents.append(formatted_content)
                            total_tokens += content_tokens
                            files_included += 1
                            logger.debug(
                                f"File embedded in conversation history: {file_path} ({content_tokens:,} tokens)"
                            )
                        else:
                            logger.debug(f"File skipped (empty content): {file_path}")
                    except Exception as e:
                        # More descriptive error handling for missing files
                        try:
                            if not os.path.exists(file_path):
                                logger.info(
                                    f"File no longer accessible for conversation history: {file_path} - file was moved/deleted since conversation (marking as excluded)"
                                )
                            else:
                                logger.warning(
                                    f"Failed to embed file in conversation history: {file_path} - {type(e).__name__}: {e}"
                                )
                        except Exception:
                            # Fallback if path translation also fails
                            logger.warning(
                                f"Failed to embed file in conversation history: {file_path} - {type(e).__name__}: {e}"
                            )
                        continue

                if file_contents:
                    files_content = "".join(file_contents)
                    if files_to_skip:
                        files_content += (
                            f"\n[NOTE: {len(files_to_skip)} additional file(s) were omitted due to size constraints, missing files, or access issues. "
                            f"These were older files from earlier conversation turns.]\n"
                        )
                    history_parts.append(files_content)
                    logger.debug(
                        f"Conversation history file embedding complete: {files_included} files embedded, {len(files_to_skip)} omitted, {total_tokens:,} total tokens"
                    )
                else:
                    history_parts.append("(No accessible files found)")
                    logger.debug(f"[FILES] No accessible files found from {len(files_to_include)} planned files")
            else:
                # Fallback to original read_files function
                files_content = read_files_func(all_files)
                if files_content:
                    # Add token validation for the combined file content
                    from utils.token_utils import check_token_limit

                    within_limit, estimated_tokens = check_token_limit(files_content)
                    if within_limit:
                        history_parts.append(files_content)
                    else:
                        # Handle token limit exceeded for conversation files
                        error_message = f"ERROR: The total size of files referenced in this conversation has exceeded the context limit and cannot be displayed.\nEstimated tokens: {estimated_tokens}, but limit is {max_file_tokens}."
                        history_parts.append(error_message)
                else:
                    history_parts.append("(No accessible files found)")

        history_parts.extend(
            [
                "",
                "=== END REFERENCED FILES ===",
                "",
            ]
        )

    history_parts.append("Previous conversation turns:")

    # === PHASE 1: COLLECTION (Newest-First for Token Budget) ===
    # Build conversation turns bottom-up (most recent first) to prioritize recent context within token limits
    # This ensures we include as many recent turns as possible within the token budget by excluding
    # OLDER turns first when space runs out, preserving the most contextually relevant exchanges
    turn_entries = []  # Will store (index, formatted_turn_content) for chronological ordering later
    total_turn_tokens = 0
    file_embedding_tokens = sum(model_context.estimate_tokens(part) for part in history_parts)

    # CRITICAL: Process turns in REVERSE chronological order (newest to oldest)
    # This prioritization strategy ensures recent context is preserved when token budget is tight
    for idx in range(len(all_turns) - 1, -1, -1):
        turn = all_turns[idx]
        turn_num = idx + 1

        if turn.role == "user":
            role_label = "Agent"
        else:
            role_label = turn.model_name or "Assistant"

        # Build the complete turn content
        turn_parts = []

        # Add turn header with tool attribution for cross-tool tracking
        turn_header = f"\n--- Turn {turn_num} ({role_label}"
        if turn.tool_name:
            turn_header += f" using {turn.tool_name}"

        # Add model info if available
        if turn.model_provider:
            provider_descriptor = turn.model_provider
            if turn.model_name and turn.model_name != role_label:
                provider_descriptor += f"/{turn.model_name}"
            turn_header += f" via {provider_descriptor}"
        elif turn.model_name and turn.model_name != role_label:
            turn_header += f" via {turn.model_name}"

        turn_header += ") ---"
        turn_parts.append(turn_header)

        # Get tool-specific formatting if available
        # This includes file references and the actual content
        tool_formatted_content = _get_tool_formatted_content(turn)
        turn_parts.extend(tool_formatted_content)

        # Calculate tokens for this turn
        turn_content = "\n".join(turn_parts)
        turn_tokens = model_context.estimate_tokens(turn_content)

        # Check if adding this turn would exceed history budget
        if file_embedding_tokens + total_turn_tokens + turn_tokens > max_history_tokens:
            # Stop adding turns - we've reached the limit
            logger.debug(f"[HISTORY] Stopping at turn {turn_num} - would exceed history budget")
            logger.debug(f"[HISTORY]   File tokens: {file_embedding_tokens:,}")
            logger.debug(f"[HISTORY]   Turn tokens so far: {total_turn_tokens:,}")
            logger.debug(f"[HISTORY]   This turn: {turn_tokens:,}")
            logger.debug(f"[HISTORY]   Would total: {file_embedding_tokens + total_turn_tokens + turn_tokens:,}")
            logger.debug(f"[HISTORY]   Budget: {max_history_tokens:,}")
            break

        # Add this turn to our collection (we'll reverse it later for chronological presentation)
        # Store the original index to maintain proper turn numbering in final output
        turn_entries.append((idx, turn_content))
        total_turn_tokens += turn_tokens

    # === PHASE 2: PRESENTATION (Chronological for LLM Understanding) ===
    # Reverse the collected turns to restore chronological order (oldest first)
    # This gives the LLM a natural conversation flow: Turn 1 → Turn 2 → Turn 3...
    # while still having prioritized recent turns during the token-constrained collection phase
    turn_entries.reverse()

    # Add the turns in chronological order for natural LLM comprehension
    # The LLM will see: "--- Turn 1 (Agent) ---" followed by "--- Turn 2 (Model) ---" etc.
    for _, turn_content in turn_entries:
        history_parts.append(turn_content)

    # Log what we included
    included_turns = len(turn_entries)
    total_turns = len(all_turns)
    if included_turns < total_turns:
        logger.info(f"[HISTORY] Included {included_turns}/{total_turns} turns due to token limit")
        history_parts.append(f"\n[Note: Showing {included_turns} most recent turns out of {total_turns} total]")

    history_parts.extend(
        [
            "",
            "=== END CONVERSATION HISTORY ===",
            "",
            "IMPORTANT: You are continuing an existing conversation thread. Build upon the previous exchanges shown above,",
            "reference earlier points, and maintain consistency with what has been discussed.",
            "",
            "DO NOT repeat or summarize previous analysis, findings, or instructions that are already covered in the",
            "conversation history. Instead, provide only new insights, additional analysis, or direct answers to",
            "the follow-up question / concerns / insights. Assume the user has read the prior conversation.",
            "",
            f"This is turn {len(all_turns) + 1} of the conversation - use the conversation history above to provide a coherent continuation.",
        ]
    )

    # Calculate total tokens for the complete conversation history
    complete_history = "\n".join(history_parts)
    from utils.token_utils import estimate_tokens

    total_conversation_tokens = estimate_tokens(complete_history)

    # Summary log of what was built
    user_turns = len([t for t in all_turns if t.role == "user"])
    assistant_turns = len([t for t in all_turns if t.role == "assistant"])
    logger.debug(
        f"[FLOW] Built conversation history: {user_turns} user + {assistant_turns} assistant turns, {len(all_files)} files, {total_conversation_tokens:,} tokens"
    )

    return complete_history, total_conversation_tokens


def _get_tool_formatted_content(turn: ConversationTurn) -> list[str]:
    """
    Get tool-specific formatting for a conversation turn.

    This function attempts to use the tool's custom formatting method if available,
    falling back to default formatting if the tool cannot be found or doesn't
    provide custom formatting.

    Args:
        turn: The conversation turn to format

    Returns:
        list[str]: Formatted content lines for this turn
    """
    if turn.tool_name:
        try:
            # Dynamically import to avoid circular dependencies
            from server import TOOLS

            tool = TOOLS.get(turn.tool_name)
            if tool:
                # Use inheritance pattern - try to call the method directly
                # If it doesn't exist or raises AttributeError, fall back to default
                try:
                    return tool.format_conversation_turn(turn)
                except AttributeError:
                    # Tool doesn't implement format_conversation_turn - use default
                    pass
        except Exception as e:
            # Log but don't fail - fall back to default formatting
            logger.debug(f"[HISTORY] Could not get tool-specific formatting for {turn.tool_name}: {e}")

    # Default formatting
    return _default_turn_formatting(turn)


def _default_turn_formatting(turn: ConversationTurn) -> list[str]:
    """
    Default formatting for conversation turns.

    This provides the standard formatting when no tool-specific
    formatting is available.

    Args:
        turn: The conversation turn to format

    Returns:
        list[str]: Default formatted content lines
    """
    parts = []

    # Add files context if present
    if turn.files:
        parts.append(f"Files used in this turn: {', '.join(turn.files)}")
        parts.append("")  # Empty line for readability

    # Add the actual content
    parts.append(turn.content)

    return parts


def _is_valid_uuid(val: str) -> bool:
    """
    Validate UUID format for security

    Ensures thread IDs are valid UUIDs to prevent injection attacks
    and malformed requests.

    Args:
        val: String to validate as UUID

    Returns:
        bool: True if valid UUID format, False otherwise
    """
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False
