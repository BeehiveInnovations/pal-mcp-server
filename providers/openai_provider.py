"""OpenAI model provider implementation."""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType, TemperatureConstraint

logger = logging.getLogger(__name__)


class OpenAIModelProvider(OpenAICompatibleProvider):
    """Implementation that talks to api.openai.com using rich model metadata.

    In addition to the built-in catalogue, the provider can surface models
    defined in ``conf/custom_models.json`` (for organisations running their own
    OpenAI-compatible gateways) while still respecting restriction policies.
    """

    # Model configurations using ModelCapabilities objects
    MODEL_CAPABILITIES = {
        "gpt-5": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-5",
            friendly_name="OpenAI (GPT-5)",
            intelligence_score=16,
            context_window=400_000,  # 400K tokens
            max_output_tokens=128_000,  # 128K max output tokens
            supports_extended_thinking=True,  # Supports reasoning tokens
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # GPT-5 supports vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=True,  # Regular models accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="GPT-5 (400K context, 128K output) - Advanced model with reasoning support",
            aliases=["gpt5"],
        ),
        "gpt-5-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-5-mini",
            friendly_name="OpenAI (GPT-5-mini)",
            intelligence_score=15,
            context_window=400_000,  # 400K tokens
            max_output_tokens=128_000,  # 128K max output tokens
            supports_extended_thinking=True,  # Supports reasoning tokens
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # GPT-5-mini supports vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="GPT-5-mini (400K context, 128K output) - Efficient variant with reasoning support",
            aliases=["gpt5-mini", "gpt5mini", "mini"],
        ),
        "gpt-5-nano": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-5-nano",
            friendly_name="OpenAI (GPT-5 nano)",
            intelligence_score=13,
            context_window=400_000,
            max_output_tokens=128_000,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="GPT-5 nano (400K context) - Fastest, cheapest version of GPT-5 for summarization and classification tasks",
            aliases=["gpt5nano", "gpt5-nano", "nano"],
        ),
        "o3": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3",
            friendly_name="OpenAI (O3)",
            intelligence_score=14,
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="Strong reasoning (200K context) - Logical problems, code generation, systematic analysis",
            aliases=[],
        ),
        "o3-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-mini",
            friendly_name="OpenAI (O3-mini)",
            intelligence_score=12,
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="Fast O3 variant (200K context) - Balanced performance/speed, moderate complexity",
            aliases=["o3mini"],
        ),
        "o3-pro": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-pro",
            friendly_name="OpenAI (O3-Pro)",
            intelligence_score=15,
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="Professional-grade reasoning (200K context) - EXTREMELY EXPENSIVE: Only for the most complex problems requiring universe-scale complexity analysis OR when the user explicitly asks for this model. Use sparingly for critical architectural decisions or exceptionally complex debugging that other models cannot handle.",
            aliases=["o3pro"],
        ),
        "o4-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o4-mini",
            friendly_name="OpenAI (O4-mini)",
            intelligence_score=11,
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O4 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O4 models don't accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("fixed"),
            description="Latest reasoning model (200K context) - Optimized for shorter contexts, rapid reasoning",
            aliases=["o4mini"],
        ),
        "gpt-4.1": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-4.1",
            friendly_name="OpenAI (GPT 4.1)",
            intelligence_score=13,
            context_window=1_000_000,  # 1M tokens
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # GPT-4.1 supports vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=True,  # Regular models accept temperature parameter
            temperature_constraint=TemperatureConstraint.create("range"),
            description="GPT-4.1 (1M context) - Advanced reasoning model with large context window",
            aliases=["gpt4.1"],
        ),
        "gpt-5-codex": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-5-codex",
            friendly_name="OpenAI (GPT-5 Codex)",
            intelligence_score=17,  # Higher than GPT-5 for coding tasks
            context_window=400_000,  # 400K tokens (same as GPT-5)
            max_output_tokens=128_000,  # 128K output tokens
            supports_extended_thinking=True,  # Responses API supports reasoning tokens
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,  # Enhanced for agentic software engineering
            supports_json_mode=True,
            supports_images=True,  # Screenshots, wireframes, diagrams
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("range"),
            description="GPT-5 Codex (400K context) - Uses Responses API for 40-80% cost savings. Specialized for coding, refactoring, and software architecture. 3% better performance on SWE-bench.",
            aliases=["gpt5-codex", "codex", "gpt-5-code", "gpt5-code"],
        ),
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize OpenAI provider with API key."""
        # Set default OpenAI base URL, allow override for regions/custom endpoints
        kwargs.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(api_key, **kwargs)

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: Optional[str] = None,
    ) -> Optional[ModelCapabilities]:
        """Look up OpenAI capabilities from built-ins or the custom registry."""

        builtin = super()._lookup_capabilities(canonical_name, requested_name)
        if builtin is not None:
            return builtin

        try:
            from .openrouter_registry import OpenRouterModelRegistry

            registry = OpenRouterModelRegistry()
            config = registry.get_model_config(canonical_name)

            if config and config.provider == ProviderType.OPENAI:
                return config

        except Exception as exc:  # pragma: no cover - registry failures are non-critical
            logger.debug(f"Could not resolve custom OpenAI model '{canonical_name}': {exc}")

        return None

    def _finalise_capabilities(
        self,
        capabilities: ModelCapabilities,
        canonical_name: str,
        requested_name: str,
    ) -> ModelCapabilities:
        """Ensure registry-sourced models report the correct provider type."""

        if capabilities.provider != ProviderType.OPENAI:
            capabilities.provider = ProviderType.OPENAI
        return capabilities

    def _raise_unsupported_model(self, model_name: str) -> None:
        raise ValueError(f"Unsupported OpenAI model: {model_name}")

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using OpenAI API with proper model name resolution."""
        # Resolve model alias before making API call
        resolved_model_name = self._resolve_model_name(model_name)

        # Call parent implementation with resolved model name
        return super().generate_content(
            prompt=prompt,
            model_name=resolved_model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Provider preferences
    # ------------------------------------------------------------------

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get OpenAI's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # Helper to find first available from preference list
        def find_first(preferences: list[str]) -> Optional[str]:
            """Return first available model from preference list."""
            for model in preferences:
                if model in allowed_models:
                    return model
            return None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer models with extended thinking support
            # GPT-5-Codex first for coding tasks (uses Responses API with 40-80% cost savings)
            preferred = find_first(["gpt-5-codex", "o3", "o3-pro", "gpt-5"])
            return preferred if preferred else allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer fast, cost-efficient models
            # GPT-5 models for speed, GPT-5-Codex after (premium pricing but cached)
            preferred = find_first(["gpt-5", "gpt-5-mini", "gpt-5-codex", "o4-mini", "o3-mini"])
            return preferred if preferred else allowed_models[0]

        else:  # BALANCED or default
            # Prefer balanced performance/cost models
            # Include GPT-5-Codex for coding workflows
            preferred = find_first(["gpt-5", "gpt-5-codex", "gpt-5-mini", "o4-mini", "o3-mini"])
            return preferred if preferred else allowed_models[0]
