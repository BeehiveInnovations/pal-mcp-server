# SAIA AI Provider

## Overview

[SAIA](https://chat-ai.academiccloud.de/) (Scalable Artificial Intelligence Accelerator) is a GWDG-hosted AI service that provides OpenAI-compatible API access to multiple LLM models with automatic API key rotation for load balancing.

## Getting Started

### 1. Get API Keys

Request API keys through the [KISSKI LLM Service page](https://kisski.gwdg.de/en/leistungen/2-02-llm-service):
1. Visit [https://kisski.gwdg.de/en/leistungen/2-02-llm-service](https://kisski.gwdg.de/en/leistungen/2-02-llm-service)
2. Click "Book"
3. Fill out the form with your credentials and intentions
4. Use the same email address as your AcademicCloud account

**Important:**
- DO NOT share your API keys
- Each API key is bound to a specific rate limit (typically 1000 requests/minute)
- Keys require Academic Cloud account registration

### 2. Configure PAL MCP Server

Add the following environment variables to your `.env` file:

```bash
# Required - Comma-separated list of API keys (supports multiple keys for rotation)
SAIA_API_KEY=key1,key2,key3

# Optional - Rotation strategy (default: round_robin)
# Options: round_robin, least_used, random
SAIA_ROTATION_STRATEGY=round_robin

# Optional - Backoff duration when key hits rate limits (default: 60 seconds)
SAIA_BACKOFF_SECONDS=60
```

### 3. Available Models

#### Open-Weight Models (Hosted by GWDG)

| Model | Capabilities | Context Window | Specialization |
|--------|--------------|----------------|----------------|
| **meta-llama-3.1-8b-instruct** | text | 128k | Fast, lightweight |
| **llama-3.1-sauerkrautlm-70b-instruct** | text, arcana | 128k | German language |
| **llama-3.3-70b-instruct** | text | 128k | General purpose |
| **gemma-3.27b-it** | text, image | 128k | Fast, multilingual |
| **medgemma-27b-it** | text, image | 128k | Medical domain |
| **teuken-7b-instruct-research** | text | 128k | European languages |
| **mistral-large-instruct** | text | 128k | Coding, multilingual |
| **qwen3-32b** | text | 128k | Global affairs |
| **qwen3-235b-a22b** | reasoning | 222k | Advanced reasoning |
| **qwen2.5-coder-32b-instruct** | text, code | 128k | Code completion |
| **codestral-22b** | text, code | 128k | Coding tasks |
| **internvl2.5-8b** | text, image | 128k | Vision, lightweight |
| **qwen2.5-vl-72b-instruct** | text, image | 128k | Vision, multilingual |
| **qwq-32b** | reasoning | 131k | Problem-solving |
| **deepseek-r1** | reasoning | 131k | Great reasoning |
| **e5-mistral-7b-instruct** | embeddings | 4k | Embeddings only |
| **multilingual-e5-large-instruct** | embeddings | - | Multilingual embeddings |
| **qwen3-embedding-4b** | embeddings | - | Embeddings |

#### Usage Examples

**Using SAIA models in PAL MCP Server:**

```bash
# Set SAIA API keys (comma-separated for rotation)
export SAIA_API_KEY="your_key1,your_key2,your_key3"

# Run PAL MCP server
./run-server.sh
```

**Example prompts:**

```text
"Use saia to generate code with qwen3-32b model"
"Analyze this file using saia with deepseek-r1 reasoning"
"Generate embeddings with saia e5-mistral-7b-instruct model"
```

### 4. API Key Rotation

The SAIA provider implements **intelligent API key rotation** to balance load across multiple keys and respect rate limits:

#### Features

- **Multiple API Keys**: Provide comma-separated list of keys in `SAIA_API_KEY`
- **Automatic Rotation**: Keys are rotated based on configured strategy
- **Rate Limit Tracking**: Monitors `x-ratelimit-*` headers from SAIA responses
- **Smart Backoff**: When a key hits rate limits, it's marked as exhausted and next key is used
- **Thread-Safe**: Concurrent requests use different keys safely
- **Three Strategies**:
  - `round_robin` (default): Sequential rotation
  - `least_used`: Use key with highest remaining quota
  - `random`: Random key selection

#### Rotation Strategy Comparison

| Strategy | Best For | Description |
|-----------|----------|-------------|
| **round_robin** | General use | Even distribution, predictable |
| **least_used** | High volume | Maximizes available quota |
| **random** | Avoidance | Prevents patterns, randomizes |

#### Rate Limit Behavior

SAIA enforces rate limits via response headers:
- `x-ratelimit-limit-minute`: Max requests per minute
- `x-ratelimit-remaining-minute`: Requests remaining this minute
- `x-ratelimit-limit-hour`: Max requests per hour
- `x-ratelimit-limit-day`: Max requests per day
- `x-ratelimit-remaining-*`: Remaining quota for each window
- `ratelimit-reset`: Seconds until counter resets

When a key's remaining quota drops below threshold, it's marked as **exhausted** and the provider automatically rotates to the next available key.

#### Configuration

```bash
# .env configuration
SAIA_API_KEY=key1,key2,key3
SAIA_ROTATION_STRATEGY=least_used  # Best for high-volume usage
SAIA_BACKOFF_SECONDS=120  # Wait 2 minutes before retrying exhausted keys

# Restrict to specific models (optional)
SAIA_ALLOWED_MODELS=meta-llama-3.1-8b-instruct,qwen3-235b-a22b
```

### 5. Technical Details

**API Compatibility**: Fully OpenAI-compatible
- Base URL: `https://chat-ai.academiccloud.de/v1`
- Endpoints: `/chat/completions`, `/completions`, `/embeddings`, `/models`
- Authentication: Bearer token in Authorization header
- Streaming: Supported via `stream=true` parameter

**Model Aliases**: Short forms supported for convenience:
- `llama` → `meta-llama-3.1-8b-instruct`
- `teuken` → `teuken-7b-instruct-research`
- `gemma` → `gemma-3.27b-it`
- `qwen` → `qwen3-32b`
- `qwq` → `qwq-32b` (reasoning)
- `codex` → `codestral-22b` (code)
- `embed` → `e5-mistral-7b-instruct` (embeddings)

**Rate Limit Headers**: Automatically parsed from every response:
```python
{
  "limit_minute": 1000,
  "remaining_minute": 999,
  "limit_hour": 60000,
  "remaining_hour": 59999,
  "limit_day": 240000,
  "remaining_day": 239999
}
```

### 6. Implementation

The SAIA provider (`providers/saia.py`) extends `OpenAICompatibleProvider` and adds:

1. **APIKeyRotator**: Thread-safe rotation manager with rate limit tracking
2. **Automatic Key Selection**: Chooses next key based on rotation strategy
3. **Error Handling**: Automatically retries with rotated keys on 429/500 errors
4. **Usage Statistics**: Get rotation stats via `provider.get_rotation_stats()`

### 7. Testing

Comprehensive tests in `tests/test_saia_provider.py`:
- Multiple key initialization
- Rotation strategies (round-robin, least-used, random)
- Rate limit parsing from headers
- Automatic rotation on 429 errors
- Thread-safe concurrent requests
- Usage statistics gathering

### 8. Troubleshooting

**Rate limits hit frequently?**
- Add more API keys to increase capacity
- Use `least_used` strategy to maximize quota utilization
- Check logs for rotation events

**Requests failing with 429 errors?**
- Ensure valid API keys
- Check rotation strategy configuration
- Verify backoff duration allows keys to reset

**Keys not being rotated?**
- Verify `SAIA_API_KEY` contains multiple keys (comma-separated)
- Check logs for rotation activity
- Confirm strategy is set (default is `round_robin`)

### 9. Data Privacy

**SAIA API Data Handling**:
- **Open-weight models**: No data storage or training
- **External models**: Microsoft Azure retains data for 30 days (GDPR compliant)
- **No model training**: SAIA only hosts inference - your data never used for training
- **Privacy**: Prompts and responses not logged for marketing purposes

---

**See Also:**
- [Adding Providers Guide](adding_providers.md)
- [Provider Architecture](../providers/README.md)
