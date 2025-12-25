# AWS Bedrock Setup

This guide explains how to configure and use AWS Bedrock models with zen-mcp-server.

## Prerequisites

- AWS account with Bedrock access
- AWS credentials configured (IAM role, ~/.aws/credentials, or environment variables)
- Model access enabled in Bedrock console (https://console.aws.amazon.com/bedrock/)

## Configuration

### Option 1: IAM Role (Recommended for EC2/ECS/Lambda)

No configuration needed - boto3 uses instance profile automatically.

```bash
# No environment variables required
# zen-mcp-server will detect IAM role credentials automatically
```

### Option 2: AWS Credentials File (Recommended for Local Development)

```bash
# ~/.aws/credentials
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

# ~/.aws/config
[default]
region = us-east-1
```

### Option 3: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
export AWS_REGION=us-east-1
```

### Option 4: Disable Bedrock (If Not Using)

```bash
export BEDROCK_ENABLED=false
```

## Enabling Model Access

Before using Bedrock models, you must enable access in the AWS Console:

1. Go to https://console.aws.amazon.com/bedrock/
2. Navigate to "Model access" in the left sidebar
3. Click "Manage model access"
4. Select the models you want to use (e.g., Claude, Titan, Llama)
5. Click "Request model access" or "Enable"
6. Wait for access to be granted (usually instant for most models)

## Usage

### List Available Models

```bash
zen listmodels --provider bedrock
```

This will show all Bedrock models you have access to, including:
- Full model IDs (e.g., `us.anthropic.claude-haiku-4-5-20251001-v1:0`)
- User-friendly aliases (e.g., `bc-haiku-4.5-us`)

### Use Claude Haiku

```bash
zen codereview --model bc-haiku-4.5-us src/file.py
```

### Use Claude Sonnet

```bash
zen codereview --model bc-sonnet-4.5-us src/file.py
```

### Use Claude Opus

```bash
zen codereview --model bc-opus-4.1 src/file.py
```

### Use Full Model ID

```bash
zen codereview --model us.anthropic.claude-haiku-4-5-20251001-v1:0 src/file.py
```

## Supported Models

zen-mcp-server supports **all** AWS Bedrock foundation models through auto-discovery:

### Claude (Anthropic)
- Claude Haiku 4.5 (fast, cost-effective)
- Claude Sonnet 4.5 (balanced performance)
- Claude Opus 4.1 (highest capability)

### Titan (Amazon)
- Titan Text Premier
- Titan Text Express
- Titan Embeddings

### Llama (Meta)
- Llama 2 (7B, 13B, 70B)
- Llama 3 (8B, 70B)
- Llama 3.1 (8B, 70B, 405B)

### Mistral AI
- Mistral 7B
- Mixtral 8x7B
- Mistral Large

### Cohere
- Command
- Command Light
- Embed

### AI21 Labs
- Jurassic-2 Mid
- Jurassic-2 Ultra

## Model Aliases

zen-mcp-server creates user-friendly aliases for Bedrock models:

| Alias | Full Model ID |
|-------|---------------|
| `bc-haiku-4.5-us` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `bc-sonnet-4.5-us` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `bc-opus-4.1` | `us.anthropic.claude-opus-4-1-20250805-v1:0` |
| `bc-titan-premier` | `amazon.titan-text-premier-v1:0` |
| `bc-llama3-70b` | `meta.llama3-70b-instruct-v1:0` |

Aliases follow the pattern: `bc-{model-name}-{version}-{region}`

## Auto-Discovery

zen-mcp-server automatically discovers available Bedrock models using the `list_foundation_models` API. This means:

- **No manual configuration** - New models appear automatically
- **Always up-to-date** - No need to update zen when AWS adds models
- **Access-aware** - Only shows models you have access to

If auto-discovery fails (e.g., network issues), zen falls back to hardcoded Claude models.

## Troubleshooting

### Error: "AWS credentials not found"

**Solution**: Configure AWS credentials using one of the methods above.

```bash
# Test credentials
aws sts get-caller-identity

# If this works, zen-mcp-server will work too
```

### Error: "Model not found"

**Solution**: Enable model access in Bedrock console.

1. Go to https://console.aws.amazon.com/bedrock/
2. Navigate to "Model access"
3. Enable the model you want to use

### Error: "Access denied"

**Solution**: Ensure your IAM user/role has Bedrock permissions.

Required IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels",
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    }
  ]
}
```

### Error: "Rate limit exceeded"

**Solution**: Bedrock has rate limits per model. Wait and retry, or use a different model.

### List Available Models

```bash
# List all Bedrock models
aws bedrock list-foundation-models --region us-east-1

# List only Claude models
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`)]'
```

### Test Bedrock API

```bash
# Test Claude Haiku
aws bedrock-runtime invoke-model \
  --model-id us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' \
  --region us-east-1 \
  /tmp/response.json

# View response
cat /tmp/response.json | jq .
```

## Cost Optimization

Bedrock pricing varies by model. Use the right model for your task:

- **Claude Haiku**: Fast, cost-effective for simple tasks
- **Claude Sonnet**: Balanced for most tasks
- **Claude Opus**: Highest capability for complex tasks

See AWS Bedrock pricing: https://aws.amazon.com/bedrock/pricing/

## Regional Availability

Bedrock models are available in specific AWS regions. Use inference profiles for cross-region access:

- `us.anthropic.claude-*` - US inference profile (routes to available US region)
- `eu.anthropic.claude-*` - EU inference profile (routes to available EU region)

Check regional availability: https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html

## Security Best Practices

1. **Use IAM roles** instead of access keys when possible
2. **Rotate credentials** regularly
3. **Use least-privilege permissions** (only bedrock:InvokeModel for specific models)
4. **Enable CloudTrail** for audit logging
5. **Use VPC endpoints** for private network access

## Additional Resources

- AWS Bedrock Documentation: https://docs.aws.amazon.com/bedrock/
- Claude API Reference: https://docs.anthropic.com/claude/reference/
- Bedrock Pricing: https://aws.amazon.com/bedrock/pricing/
- Model Access: https://console.aws.amazon.com/bedrock/
