"""
Configuration and constants for Zen MCP Server

This module centralizes all configuration settings for the Zen MCP Server.
It defines model configurations, token limits, temperature defaults, and other
constants used throughout the application.

Configuration values can be overridden by environment variables where appropriate.
"""

import os

# Version and metadata
# These values are used in server responses and for tracking releases
# IMPORTANT: This is the single source of truth for version and author info
# Semantic versioning: MAJOR.MINOR.PATCH
__version__ = "5.1.0"
# Last update date in ISO format
__updated__ = "2025-06-18"
# Primary maintainer
__author__ = "Fahad Gilani"

# Model configuration
# DEFAULT_MODEL: The default model used for all AI operations
# This should be a stable, high-performance model suitable for code analysis
# Can be overridden by setting DEFAULT_MODEL environment variable
# Special value "auto" means Claude should pick the best model for each task
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "auto")

# Auto mode detection - when DEFAULT_MODEL is "auto", Claude picks the model
IS_AUTO_MODE = DEFAULT_MODEL.lower() == "auto"

# Model capabilities descriptions for auto mode
# These help Claude choose the best model for each task
#
# IMPORTANT: These are the built-in natively supported models:
# - When GEMINI_API_KEY is set: Enables "flash", "pro" (and their full names)
# - When OPENAI_API_KEY is set: Enables "o3", "o3mini", "o4-mini", "o4-mini-high"
# - When both are set: All models below are available
# - When neither is set but OpenRouter/Custom API is configured: These model
#   aliases will automatically map to equivalent models via the proxy provider
#
# In auto mode (DEFAULT_MODEL=auto), Claude will see these descriptions and
# intelligently select the best model for each task. The descriptions appear
# in the tool schema to guide Claude's selection based on task requirements.
MODEL_CAPABILITIES_DESC = {
    # Gemini models - Available when GEMINI_API_KEY is configured
    "flash": "Ultra-fast (1M context) - Quick analysis, simple queries, rapid iterations",
    "pro": "Deep reasoning + thinking mode (1M context) - Complex problems, architecture, deep analysis",
    # OpenAI models - Available when OPENAI_API_KEY is configured
    "o3": "Strong reasoning (200K context) - Logical problems, code generation, systematic analysis",
    "o3-mini": "Fast O3 variant (200K context) - Balanced performance/speed, moderate complexity",
    "o3-pro": "Professional-grade reasoning (200K context) - EXTREMELY EXPENSIVE: Only for the most complex problems requiring universe-scale complexity analysis OR when the user explicitly asks for this model. Use sparingly for critical architectural decisions or exceptionally complex debugging that other models cannot handle.",
    "o4-mini": "Latest reasoning model (200K context) - Optimized for shorter contexts, rapid reasoning",
    "o4-mini-high": "Enhanced O4 mini (200K context) - Higher reasoning effort for complex tasks",
    # X.AI GROK models - Available when XAI_API_KEY is configured
    "grok": "GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
    "grok-3": "GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
    "grok-3-fast": "GROK-3 Fast (131K context) - Higher performance variant, faster processing but more expensive",
    "grok3": "GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
    "grokfast": "GROK-3 Fast (131K context) - Higher performance variant, faster processing but more expensive",
    # Full model names also supported (for explicit specification)
    "gemini-2.5-flash-preview-05-20": "Ultra-fast (1M context) - Quick analysis, simple queries, rapid iterations",
    "gemini-2.5-pro-preview-06-05": (
        "Deep reasoning + thinking mode (1M context) - Complex problems, architecture, deep analysis"
    ),
}

# OpenRouter/Custom API Fallback Behavior:
# When only OpenRouter or Custom API is configured (no native API keys), these
# model aliases automatically map to equivalent models through the proxy:
# - "flash" → "google/gemini-2.5-flash-preview-05-20" (via OpenRouter)
# - "pro" → "google/gemini-2.5-pro-preview-06-05" (via OpenRouter)
# - "o3" → "openai/o3" (via OpenRouter)
# - "o3mini" → "openai/o3-mini" (via OpenRouter)
# - "o4-mini" → "openai/o4-mini" (via OpenRouter)
# - "o4-mini-high" → "openai/o4-mini-high" (via OpenRouter)
#
# This ensures the same model names work regardless of which provider is configured.


# Temperature defaults for different tool types
# Temperature controls the randomness/creativity of model responses
# Lower values (0.0-0.3) produce more deterministic, focused responses
# Higher values (0.7-1.0) produce more creative, varied responses

# TEMPERATURE_ANALYTICAL: Used for tasks requiring precision and consistency
# Ideal for code review, debugging, and error analysis where accuracy is critical
TEMPERATURE_ANALYTICAL = 0.2  # For code review, debugging

# TEMPERATURE_BALANCED: Middle ground for general conversations
# Provides a good balance between consistency and helpful variety
TEMPERATURE_BALANCED = 0.5  # For general chat

# TEMPERATURE_CREATIVE: Higher temperature for exploratory tasks
# Used when brainstorming, exploring alternatives, or architectural discussions
TEMPERATURE_CREATIVE = 0.7  # For architecture, deep thinking

# Thinking Mode Defaults
# DEFAULT_THINKING_MODE_THINKDEEP: Default thinking depth for extended reasoning tool
# Higher modes use more computational budget but provide deeper analysis
DEFAULT_THINKING_MODE_THINKDEEP = os.getenv("DEFAULT_THINKING_MODE_THINKDEEP", "high")

# Consensus Tool Defaults
# Consensus timeout and rate limiting settings
DEFAULT_CONSENSUS_TIMEOUT = 120.0  # 2 minutes per model
DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION = 2

# NOTE: Consensus tool now uses sequential processing for MCP compatibility
# Concurrent processing was removed to avoid async pattern violations

# MCP Protocol Transport Limits
#
# IMPORTANT: This limit ONLY applies to the Claude CLI ↔ MCP Server transport boundary.
# It does NOT limit internal MCP Server operations like system prompts, file embeddings,
# conversation history, or content sent to external models (Gemini/O3/OpenRouter).
#
# MCP Protocol Architecture:
# Claude CLI ←→ MCP Server ←→ External Model (Gemini/O3/etc.)
#     ↑                              ↑
#     │                              │
# MCP transport                Internal processing
# (25K token limit)            (No MCP limit - can be 1M+ tokens)
#
# MCP_PROMPT_SIZE_LIMIT: Maximum character size for USER INPUT crossing MCP transport
# The MCP protocol has a combined request+response limit of ~25K tokens total.
# To ensure adequate space for MCP Server → Claude CLI responses, we limit user input
# to 50K characters (roughly ~10-12K tokens). Larger user prompts must be sent
# as prompt.txt files to bypass MCP's transport constraints.
#
# What IS limited by this constant:
# - request.prompt field content (user input from Claude CLI)
# - prompt.txt file content (alternative user input method)
# - Any other direct user input fields
#
# What is NOT limited by this constant:
# - System prompts added internally by tools
# - File content embedded by tools
# - Conversation history loaded from storage
# - Web search instructions or other internal additions
# - Complete prompts sent to external models (managed by model-specific token limits)
#
# This ensures MCP transport stays within protocol limits while allowing internal
# processing to use full model context windows (200K-1M+ tokens).
MCP_PROMPT_SIZE_LIMIT = 50_000  # 50K characters (user input only)

# Threading configuration
# Simple in-memory conversation threading for stateless MCP environment
# Conversations persist only during the Claude session
