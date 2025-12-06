# HTTP Cassette Testing - Maintenance Guide

## Overview

This project uses HTTP cassettes (recorded HTTP interactions) to test API integrations without making real API calls during CI. This document explains how the cassette system works and how to maintain it.

## How Cassette Matching Works

### Standard Matching (Non-o3 Models)

For most models, cassettes match requests using:
- HTTP method (GET, POST, etc.)
- Request path (/v1/chat/completions, etc.)
- **Exact hash of the request body**

If ANY part of the request changes, the hash changes and the cassette won't match.

### Semantic Matching (o3 Models)

**Problem**: o3 models use system prompts and conversation memory instructions that change frequently with code updates. Using exact hash matching would require re-recording cassettes after every prompt change.

**Solution**: o3 models use **semantic matching** that only compares:
- Model name (e.g., "o3-pro", "o3-mini")
- User's actual question (extracted from request)
- Core parameters (reasoning effort, temperature)

**Ignored fields** (can change without breaking cassettes):
- System prompts
- Conversation memory instructions
- Follow-up guidance text
- Token limits and other metadata

### Example

These two requests will match with semantic matching:

```json
// Request 1 - Old system prompt
{
  "model": "o3-pro",
  "reasoning": {"effort": "medium"},
  "input": [{
    "role": "user",
    "content": [{
      "text": "Old system prompt v1...\n\n=== USER REQUEST ===\nWhat is 2 + 2?\n=== END REQUEST ===\n\nOld instructions..."
    }]
  }]
}

// Request 2 - New system prompt (DIFFERENT)
{
  "model": "o3-pro",
  "reasoning": {"effort": "medium"},
  "input": [{
    "role": "user",
    "content": [{
      "text": "New system prompt v2...\n\n=== USER REQUEST ===\nWhat is 2 + 2?\n=== END REQUEST ===\n\nNew instructions..."
    }]
  }]
}
```

Both extract the same semantic content:
```json
{
  "model": "o3-pro",
  "reasoning": {"effort": "medium"},
  "user_question": "What is 2 + 2?"
}
```

## When to Re-Record Cassettes

### You MUST re-record when:

1. **The user's test question changes**
   - Example: Changing "What is 2 + 2?" to "What is 3 + 3?"

2. **Core parameters change**
   - Model name changes (o3-pro → o3-mini)
   - Reasoning effort changes (medium → high)
   - Temperature changes

3. **For non-o3 models: ANY request body change**

### You DON'T need to re-record when (o3 models only):

1. **System prompts change**
   - Semantic matching ignores these

2. **Conversation memory instructions change**
   - Follow-up guidance text changes
   - Token limit instructions change

3. **Response format instructions change**
   - As long as the user's actual question stays the same

## How to Re-Record a Cassette

### Step 1: Delete the Old Cassette

```bash
rm tests/openai_cassettes/<cassette_name>.json
```

### Step 2: Run the Test with Real API Key

```bash
# Make sure you have a valid API key in .env
export OPENAI_API_KEY="your-real-key"

# Run the specific test
python -m pytest tests/test_o3_pro_output_text_fix.py -v
```

The test will:
1. Detect the missing cassette
2. Make a real API call
3. Record the interaction
4. Save it as a new cassette

### Step 3: Verify the Cassette Works in Replay Mode

```bash
# Test with dummy key (forces replay mode)
OPENAI_API_KEY="dummy-key" python -m pytest tests/test_o3_pro_output_text_fix.py -v
```

### Step 4: Commit the New Cassette

```bash
git add tests/openai_cassettes/<cassette_name>.json
git commit -m "chore: re-record cassette for <test_name>"
```

## Troubleshooting

### Error: "No matching interaction found"

**Cause**: The request body has changed in a way that affects the hash.

**For o3 models**: This should NOT happen due to semantic matching. If it does:
1. Check if the user question changed
2. Check if model name or reasoning effort changed
3. Verify semantic matching is working (run `test_cassette_semantic_matching.py`)

**For non-o3 models**: This is expected when request changes. Re-record the cassette.

**Solution**: Re-record the cassette following the steps above.

### Error: "Cassette file not found"

**Cause**: Cassette hasn't been recorded yet or was deleted.

**Solution**: Re-record the cassette with a real API key.

### CI Fails but Local Tests Pass

**Cause**:
1. You recorded with uncommitted code changes
2. CI is running different code than your local environment

**Solution**:
1. Commit all your changes first
2. Then re-record cassettes
3. Commit the cassettes

## Best Practices

### 1. Keep Test Questions Simple
- Use simple, stable questions like "What is 2 + 2?"
- Avoid questions that might elicit different responses over time

### 2. Document Cassette Recording Conditions
- Add comments in tests explaining when recorded
- Note any special setup required

### 3. Use Semantic Matching for Prompt-Heavy Tests
- If your test involves lots of system prompts, use o3 models
- Or extend semantic matching to other models if needed

### 4. Test Both Record and Replay Modes
- Always verify cassettes work in replay mode
- Ensure tests can record new cassettes when needed

### 5. Don't Commit Cassettes with Secrets
- The recording system sanitizes API keys automatically
- But double-check for any other sensitive data

## Implementation Details

### Semantic Matching Code

The semantic matching is implemented in `tests/http_transport_recorder.py`:

- `_is_o3_model_request()`: Detects o3 model requests
- `_extract_semantic_fields()`: Extracts only essential fields
- `_get_request_signature()`: Generates hash from semantic fields

### Adding Semantic Matching to Other Models

To add semantic matching for other models:

1. Update `_is_o3_model_request()` to include your model
2. Update `_extract_semantic_fields()` if needed
3. Add tests in `test_cassette_semantic_matching.py`

Example:
```python
def _is_o3_model_request(self, content_dict: dict) -> bool:
    """Check if this is an o3 or other semantic-matching model request."""
    model = content_dict.get("model", "")
    return model.startswith("o3") or model.startswith("gpt-5")  # Add more models
```

## Questions?

If you encounter issues with cassette testing:

1. Check this guide first
2. Review existing cassette tests for examples
3. Run semantic matching tests to verify the system
4. Open an issue if you find a bug in the matching logic

## Dual-Model Cassette Coverage

Some integration tests maintain cassettes for multiple model variants to ensure regression coverage across model families. For example:

### Consensus Tool Cassettes

The `test_consensus_integration.py` test uses parameterized fixtures to test both `gpt-5` and `gpt-5.1` models:

- `tests/openai_cassettes/consensus_step1_gpt5_for.json` - Cassette for gpt-5 model
- `tests/openai_cassettes/consensus_step1_gpt51_for.json` - Cassette for gpt-5.1 model

**When updating consensus cassettes:**

1. Both cassettes should be updated if the test logic changes
2. If only one model's behavior changes, update only that cassette
3. The test uses `@pytest.mark.parametrize` to run against both models
4. Each cassette path is mapped in the `CONSENSUS_CASSETTES` dictionary

**To re-record a specific model's cassette:**

```bash
# Delete the specific cassette
rm tests/openai_cassettes/consensus_step1_gpt5_for.json

# Run the test with real API key (it will record for gpt-5)
OPENAI_API_KEY="your-real-key" python -m pytest tests/test_consensus_integration.py::test_consensus_multi_model_consultations[gpt-5] -v

# Or for gpt-5.1
rm tests/openai_cassettes/consensus_step1_gpt51_for.json
OPENAI_API_KEY="your-real-key" python -m pytest tests/test_consensus_integration.py::test_consensus_multi_model_consultations[gpt-5.1] -v
```

This dual-coverage approach ensures that both model families continue to work correctly as the codebase evolves.

## Related Files

- `tests/http_transport_recorder.py` - Cassette recording/replay implementation
- `tests/transport_helpers.py` - Helper functions for injecting transports
- `tests/test_cassette_semantic_matching.py` - Tests for semantic matching
- `tests/test_o3_pro_output_text_fix.py` - Example of cassette usage
- `tests/test_consensus_integration.py` - Example of dual-model cassette coverage
- `tests/openai_cassettes/` - Directory containing recorded cassettes
