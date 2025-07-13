# HTTP Transport Recorder for Testing

A custom HTTP recorder for testing expensive API calls (like o3-pro) with real responses.

## Overview

The HTTP Transport Recorder captures and replays HTTP interactions at the transport layer, enabling:
- Cost-efficient testing of expensive APIs (record once, replay forever)
- Deterministic tests with real API responses
- Seamless integration with httpx and OpenAI SDK

## Quick Start

```python
from tests.http_transport_recorder import TransportFactory
from providers import ModelProviderRegistry

# Setup transport recorder
cassette_path = "tests/openai_cassettes/my_test.json"
transport = TransportFactory.create_transport(cassette_path)

# Inject into provider
provider = ModelProviderRegistry.get_provider_for_model("o3-pro")
provider._test_transport = transport

# Make API calls - automatically recorded/replayed
```

## How It Works

1. **First run** (cassette doesn't exist): Records real API calls
2. **Subsequent runs** (cassette exists): Replays saved responses
3. **Re-record**: Delete cassette file and run again

## Usage in Tests

See `test_o3_pro_output_text_fix.py` for a complete example:

```python
async def test_with_recording():
    # Transport factory auto-detects record vs replay mode
    transport = TransportFactory.create_transport("tests/openai_cassettes/my_test.json")
    provider._test_transport = transport

    # Use normally - recording happens transparently
    result = await chat_tool.execute({"prompt": "2+2?", "model": "o3-pro"})
```

## File Structure

```
tests/
├── openai_cassettes/           # Recorded API interactions
│   └── *.json                  # Cassette files
├── http_transport_recorder.py  # Transport implementation
└── test_o3_pro_output_text_fix.py  # Example usage
```

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

- **RecordingTransport**: Captures real HTTP calls
- **ReplayTransport**: Serves saved responses
- **TransportFactory**: Auto-selects mode based on cassette existence
- **PII Sanitization**: Automatically removes API keys from recordings

**Security Note**: Always review new cassette files before committing to ensure no sensitive data is included.

For implementation details, see `tests/http_transport_recorder.py`.

