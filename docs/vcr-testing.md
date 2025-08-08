# HTTP Transport Recorder for Testing

A custom HTTP recorder for testing expensive API calls (like o3-pro) with real responses.

## Overview

The HTTP Transport Recorder captures and replays HTTP interactions at the transport layer, enabling:
- Cost-efficient testing of expensive APIs (record once, replay forever)
- Deterministic tests with real API responses
- Seamless integration with httpx and OpenAI SDK
- Automatic PII sanitization for secure recordings

## Quick Start

```python
from tests.transport_helpers import inject_transport

# Simple one-line setup with automatic transport injection
def test_expensive_api_call(monkeypatch):
    inject_transport(monkeypatch, "tests/openai_cassettes/my_test.json")
    
    # Make API calls - automatically recorded/replayed with PII sanitization
    result = await chat_tool.execute({"prompt": "2+2?", "model": "o3-pro"})
```

## How It Works

1. **First run** (cassette doesn't exist): Records real API calls
2. **Subsequent runs** (cassette exists): Replays saved responses
3. **Re-record**: Delete cassette file and run again

## Usage in Tests

The `transport_helpers.inject_transport()` function simplifies test setup:

```python
from tests.transport_helpers import inject_transport

async def test_with_recording(monkeypatch):
    # One-line setup - handles all transport injection complexity
    inject_transport(monkeypatch, "tests/openai_cassettes/my_test.json")
    
    # Use API normally - recording/replay happens transparently
    result = await chat_tool.execute({"prompt": "2+2?", "model": "o3-pro"})
```

For manual setup, see `test_o3_pro_output_text_fix.py`.

## Automatic PII Sanitization

All recordings are automatically sanitized to remove sensitive data:

- **API Keys & Tokens**: Bearer tokens, API keys, and auth headers
- **Personal Data**: Email addresses, IP addresses, phone numbers
- **URLs**: Sensitive query parameters and paths
- **Custom Patterns**: Add your own sanitization rules

Sanitization is enabled by default in `RecordingTransport`. To disable:

```python
transport = TransportFactory.create_transport(cassette_path, sanitize=False)
```

## File Structure

```
tests/
├── openai_cassettes/           # Recorded API interactions
│   └── *.json                  # Cassette files
├── http_transport_recorder.py  # Transport implementation
├── pii_sanitizer.py           # Automatic PII sanitization
├── transport_helpers.py       # Simplified transport injection
├── sanitize_cassettes.py      # Batch sanitization script
└── test_o3_pro_output_text_fix.py  # Example usage
```

## Sanitizing Existing Cassettes

Use the `sanitize_cassettes.py` script to clean existing recordings:

```bash
# Sanitize all cassettes (creates backups)
python tests/sanitize_cassettes.py

# Sanitize specific cassette
python tests/sanitize_cassettes.py tests/openai_cassettes/my_test.json

# Skip backup creation
python tests/sanitize_cassettes.py --no-backup
```

The script will:
- Create timestamped backups of original files
- Apply comprehensive PII sanitization
- Preserve JSON structure and functionality

## Cost Management

- **One-time cost**: Initial recording only
- **Zero ongoing cost**: Replays are free
- **CI-friendly**: No API keys needed for replay

## Re-recording

When API changes require new recordings:

```bash
# Delete specific cassette
rm tests/openai_cassettes/my_test.json

# Run test with real API key
python -m pytest tests/test_o3_pro_output_text_fix.py
```

## Implementation Details

- **RecordingTransport**: Captures real HTTP calls with automatic PII sanitization
- **ReplayTransport**: Serves saved responses from cassettes
- **TransportFactory**: Auto-selects mode based on cassette existence
- **PIISanitizer**: Comprehensive sanitization of sensitive data (integrated by default)

**Security Note**: While recordings are automatically sanitized, always review new cassette files before committing. The sanitizer removes known patterns of sensitive data, but domain-specific secrets may need custom rules.

For implementation details, see:
- `tests/http_transport_recorder.py` - Core transport implementation
- `tests/pii_sanitizer.py` - Sanitization patterns and logic
- `tests/transport_helpers.py` - Simplified test integration

