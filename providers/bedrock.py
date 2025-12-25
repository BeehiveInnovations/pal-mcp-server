"""AWS Bedrock provider with auto-discovery and multi-model support."""

import json
import logging
import re
from typing import Any, ClassVar, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import ModelProvider
from .shared import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)

logger = logging.getLogger(__name__)


class BedrockModelProvider(ModelProvider):
    """AWS Bedrock provider supporting all foundation models."""

    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}
    
    CLAUDE_PATTERN = re.compile(r'anthropic\.claude')
    TITAN_PATTERN = re.compile(r'amazon\.titan')
    LLAMA_PATTERN = re.compile(r'meta\.llama')
    MISTRAL_PATTERN = re.compile(r'mistral\.')

    def __init__(self, api_key: str = None, **kwargs):
        self._client = None
        self._runtime_client = None
        self._model_cache: dict[str, ModelCapabilities] = {}
        self._alias_map: dict[str, str] = {}
        self._region = kwargs.get('region', 'us-east-1')
        
        super().__init__(api_key or "not-used", **kwargs)
        
        try:
            self._discover_models()
            logger.info(f"Discovered {len(self._model_cache)} Bedrock models")
        except Exception as e:
            logger.warning(f"Auto-discovery failed: {e}. Using fallback models.")
            self._load_fallback_models()

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = boto3.client('bedrock', region_name=self._region)
            except NoCredentialsError:
                logger.error("AWS credentials not found")
                raise
        return self._client

    @property
    def runtime_client(self):
        if self._runtime_client is None:
            try:
                self._runtime_client = boto3.client('bedrock-runtime', region_name=self._region)
            except NoCredentialsError:
                logger.error("AWS credentials not found")
                raise
        return self._runtime_client

    def _discover_models(self) -> None:
        try:
            response = self.client.list_foundation_models()
            
            for model_info in response.get('modelSummaries', []):
                model_id = model_info['modelId']
                capabilities = self._parse_model_capabilities(model_info)
                self._model_cache[model_id] = capabilities
                
                alias = self._create_alias(model_info)
                if alias:
                    self._alias_map[alias] = model_id
                    logger.debug(f"Mapped alias {alias} → {model_id}")
                
        except ClientError as e:
            logger.error(f"Failed to list Bedrock models: {e}")
            raise

    def _parse_model_capabilities(self, model_info: dict) -> ModelCapabilities:
        model_id = model_info['modelId']
        model_name = model_info.get('modelName', model_id)
        provider_name = model_info.get('providerName', 'Unknown')
        
        intelligence_score = self._estimate_intelligence_score(model_id, model_name)
        context_window = self._estimate_context_window(model_id)
        max_output_tokens = context_window // 4
        
        input_modalities = model_info.get('inputModalities', [])
        supports_images = 'IMAGE' in input_modalities
        
        return ModelCapabilities(
            provider=ProviderType.BEDROCK,
            model_name=model_id,
            friendly_name=f"{provider_name} {model_name}",
            intelligence_score=intelligence_score,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            supports_extended_thinking=False,
            supports_json_mode=True,
            supports_function_calling=False,
            supports_images=supports_images,
            temperature_constraint=RangeTemperatureConstraint(0.0, 1.0, 0.7),
            description=f"{provider_name} {model_name} via AWS Bedrock",
            aliases=[],
        )

    def _estimate_intelligence_score(self, model_id: str, model_name: str) -> int:
        model_lower = f"{model_id} {model_name}".lower()
        
        if 'opus' in model_lower:
            return 19
        elif 'sonnet' in model_lower:
            return 16
        elif 'haiku' in model_lower:
            return 14
        elif 'llama' in model_lower:
            if '70b' in model_lower or '405b' in model_lower:
                return 17
            elif '8b' in model_lower or '13b' in model_lower:
                return 13
        elif 'mistral' in model_lower:
            if 'large' in model_lower or '8x' in model_lower:
                return 16
            else:
                return 12
        elif 'titan' in model_lower:
            if 'premier' in model_lower:
                return 15
            else:
                return 10
        
        return 10

    def _estimate_context_window(self, model_id: str) -> int:
        model_lower = model_id.lower()
        
        if 'claude' in model_lower:
            return 200_000
        elif 'llama' in model_lower:
            if 'llama3' in model_lower or 'llama-3' in model_lower:
                return 128_000
            else:
                return 32_000
        elif 'mistral' in model_lower:
            return 32_000
        elif 'titan' in model_lower:
            return 32_000
        
        return 16_000

    def _create_alias(self, model_info: dict) -> Optional[str]:
        model_id = model_info['modelId']
        
        region_prefix = None
        if model_id.startswith('us.') or model_id.startswith('eu.'):
            region_prefix = model_id.split('.')[0]
            model_id_base = '.'.join(model_id.split('.')[1:])
        else:
            model_id_base = model_id
        
        parts = model_id_base.split('.')
        if len(parts) < 2:
            return None
        
        model_part = parts[1]
        
        if 'claude' in model_part:
            match = re.search(r'claude-(\w+)-(\d+)-(\d+)', model_part)
            if match:
                name, major, minor = match.groups()
                alias = f"bc-{name}-{major}.{minor}"
            else:
                return None
        elif 'titan' in model_part:
            match = re.search(r'titan-\w+-(\w+)', model_part)
            if match:
                variant = match.group(1)
                alias = f"bc-titan-{variant}"
            else:
                alias = "bc-titan"
        elif 'llama' in model_part:
            match = re.search(r'llama(\d+)-(\d+b)', model_part)
            if match:
                version, size = match.groups()
                alias = f"bc-llama{version}-{size}"
            else:
                alias = "bc-llama"
        else:
            name = model_part.split('-')[0]
            alias = f"bc-{name}"
        
        if region_prefix:
            alias = f"{alias}-{region_prefix}"
        
        return alias

    def _load_fallback_models(self) -> None:
        fallback_models = {
            "us.anthropic.claude-haiku-4-5-20251001-v1:0": ModelCapabilities(
                provider=ProviderType.BEDROCK,
                model_name="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                friendly_name="Claude Haiku 4.5 (US)",
                intelligence_score=14,
                context_window=200_000,
                max_output_tokens=50_000,
                supports_extended_thinking=False,
                supports_json_mode=True,
                supports_function_calling=False,
                supports_images=True,
                temperature_constraint=RangeTemperatureConstraint(0.0, 1.0, 0.7),
                description="Claude Haiku 4.5 via AWS Bedrock (US inference profile)",
                aliases=["bc-haiku-4.5-us", "bc-haiku-us"],
            ),
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0": ModelCapabilities(
                provider=ProviderType.BEDROCK,
                model_name="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                friendly_name="Claude Sonnet 4.5 (US)",
                intelligence_score=16,
                context_window=200_000,
                max_output_tokens=50_000,
                supports_extended_thinking=False,
                supports_json_mode=True,
                supports_function_calling=False,
                supports_images=True,
                temperature_constraint=RangeTemperatureConstraint(0.0, 1.0, 0.7),
                description="Claude Sonnet 4.5 via AWS Bedrock (US inference profile)",
                aliases=["bc-sonnet-4.5-us", "bc-sonnet-us"],
            ),
            "us.anthropic.claude-opus-4-1-20250805-v1:0": ModelCapabilities(
                provider=ProviderType.BEDROCK,
                model_name="us.anthropic.claude-opus-4-1-20250805-v1:0",
                friendly_name="Claude Opus 4.1 (US)",
                intelligence_score=19,
                context_window=200_000,
                max_output_tokens=50_000,
                supports_extended_thinking=False,
                supports_json_mode=True,
                supports_function_calling=False,
                supports_images=True,
                temperature_constraint=RangeTemperatureConstraint(0.0, 1.0, 0.7),
                description="Claude Opus 4.1 via AWS Bedrock (US inference profile)",
                aliases=["bc-opus-4.1", "bc-opus"],
            ),
        }
        
        for model_id, capabilities in fallback_models.items():
            self._model_cache[model_id] = capabilities
            for alias in capabilities.aliases:
                self._alias_map[alias] = model_id

    def generate_content(self, model: str, messages: list[dict], **kwargs) -> ModelResponse:
        model_id = self._alias_map.get(model, model)
        
        if model_id not in self._model_cache:
            raise ValueError(f"Model '{model}' not found")
        
        request_body = self._format_request(model_id, messages, **kwargs)
        
        try:
            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            return self._parse_response(model_id, response_body)
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            logger.error(f"Bedrock API error: {error_msg}")
            raise RuntimeError(f"Bedrock API error: {error_msg}") from e

    def _format_request(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        if self.CLAUDE_PATTERN.search(model_id):
            return self._format_claude_request(messages, **kwargs)
        elif self.TITAN_PATTERN.search(model_id):
            return self._format_titan_request(messages, **kwargs)
        elif self.LLAMA_PATTERN.search(model_id):
            return self._format_llama_request(messages, **kwargs)
        elif self.MISTRAL_PATTERN.search(model_id):
            return self._format_mistral_request(messages, **kwargs)
        else:
            raise ValueError(f"Unsupported model family: {model_id}")

    def _format_claude_request(self, messages: list[dict], **kwargs) -> dict:
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": kwargs.get('max_tokens', 4096),
            "temperature": kwargs.get('temperature', 0.7),
        }

    def _format_titan_request(self, messages: list[dict], **kwargs) -> dict:
        prompt = "\n\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)
        
        return {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": kwargs.get('max_tokens', 512),
                "temperature": kwargs.get('temperature', 0.7),
                "topP": kwargs.get('top_p', 0.9),
            }
        }

    def _format_llama_request(self, messages: list[dict], **kwargs) -> dict:
        prompt_parts = []
        for msg in messages:
            if msg['role'] == 'user':
                prompt_parts.append(f"[INST] {msg['content']} [/INST]")
            elif msg['role'] == 'assistant':
                prompt_parts.append(msg['content'])
        
        prompt = "<s>" + " ".join(prompt_parts)
        
        return {
            "prompt": prompt,
            "max_gen_len": kwargs.get('max_tokens', 512),
            "temperature": kwargs.get('temperature', 0.7),
            "top_p": kwargs.get('top_p', 0.9),
        }

    def _format_mistral_request(self, messages: list[dict], **kwargs) -> dict:
        prompt_parts = []
        for msg in messages:
            if msg['role'] == 'user':
                prompt_parts.append(f"[INST] {msg['content']} [/INST]")
            elif msg['role'] == 'assistant':
                prompt_parts.append(msg['content'])
        
        prompt = "<s>" + " ".join(prompt_parts)
        
        return {
            "prompt": prompt,
            "max_tokens": kwargs.get('max_tokens', 512),
            "temperature": kwargs.get('temperature', 0.7),
            "top_p": kwargs.get('top_p', 0.9),
        }

    def _parse_response(self, model_id: str, response_body: dict) -> ModelResponse:
        if self.CLAUDE_PATTERN.search(model_id):
            return self._parse_claude_response(response_body)
        elif self.TITAN_PATTERN.search(model_id):
            return self._parse_titan_response(response_body)
        elif self.LLAMA_PATTERN.search(model_id):
            return self._parse_llama_response(response_body)
        elif self.MISTRAL_PATTERN.search(model_id):
            return self._parse_mistral_response(response_body)
        else:
            raise ValueError(f"Unsupported model family: {model_id}")

    def _parse_claude_response(self, response_body: dict) -> ModelResponse:
        content = response_body['content'][0]['text']
        usage = response_body.get('usage', {})
        
        return ModelResponse(
            content=content,
            model=response_body.get('model', 'unknown'),
            provider=ProviderType.BEDROCK,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
        )

    def _parse_titan_response(self, response_body: dict) -> ModelResponse:
        result = response_body['results'][0]
        content = result['outputText']
        
        return ModelResponse(
            content=content,
            model='titan',
            provider=ProviderType.BEDROCK,
            input_tokens=0,
            output_tokens=result.get('tokenCount', 0),
        )

    def _parse_llama_response(self, response_body: dict) -> ModelResponse:
        return ModelResponse(
            content=response_body['generation'],
            model='llama',
            provider=ProviderType.BEDROCK,
            input_tokens=response_body.get('prompt_token_count', 0),
            output_tokens=response_body.get('generation_token_count', 0),
        )

    def _parse_mistral_response(self, response_body: dict) -> ModelResponse:
        output = response_body['outputs'][0]
        
        return ModelResponse(
            content=output['text'],
            model='mistral',
            provider=ProviderType.BEDROCK,
            input_tokens=0,
            output_tokens=0,
        )

    def get_provider_type(self) -> ProviderType:
        return ProviderType.BEDROCK

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        return self._model_cache

    def _lookup_capabilities(self, model_name: str) -> Optional[ModelCapabilities]:
        if model_name in self._model_cache:
            return self._model_cache[model_name]
        
        if model_name in self._alias_map:
            full_model_id = self._alias_map[model_name]
            return self._model_cache.get(full_model_id)
        
        return None
