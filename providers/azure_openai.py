"""Azure OpenAI provider built on the OpenAI-compatible implementation."""

from __future__ import annotations

import logging
from dataclasses import asdict, replace

try:  # pragma: no cover - optional dependency
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover
    AzureOpenAI = None  # type: ignore[assignment]

from config import OPENAI_IMAGE_DETAIL
from utils import openai_token_estimator
from utils.env import get_env, suppress_env_vars

from .openai import OpenAIModelProvider
from .openai_compatible import OpenAICompatibleProvider
from .registries.azure import AzureModelRegistry
from .shared import ModelCapabilities, ModelResponse, ProviderType, TemperatureConstraint

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Thin Azure wrapper that reuses the OpenAI-compatible request pipeline."""

    FRIENDLY_NAME = "Azure OpenAI"
    DEFAULT_API_VERSION = "2024-02-15-preview"

    # The OpenAI-compatible base expects subclasses to expose capabilities via
    # ``get_all_model_capabilities``.  Azure deployments are user-defined, so we
    # build the catalogue dynamically from environment configuration instead of
    # relying on a static ``MODEL_CAPABILITIES`` map.
    MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {}

    def __init__(
        self,
        api_key: str,
        *,
        azure_endpoint: str | None = None,
        api_version: str | None = None,
        deployments: dict[str, object] | None = None,
        **kwargs,
    ) -> None:
        # Let the OpenAI-compatible base handle shared configuration such as
        # timeouts, restriction-aware allowlists, and logging. ``base_url`` maps
        # directly onto Azure's endpoint URL.
        super().__init__(api_key, base_url=azure_endpoint, **kwargs)

        if not azure_endpoint:
            azure_endpoint = get_env("AZURE_OPENAI_ENDPOINT")
        if not azure_endpoint:
            raise ValueError("Azure OpenAI endpoint is required via parameter or AZURE_OPENAI_ENDPOINT")

        self.azure_endpoint = azure_endpoint.rstrip("/")
        self.api_version = api_version or get_env("AZURE_OPENAI_API_VERSION", self.DEFAULT_API_VERSION)

        registry_specs = self._load_registry_entries()
        override_specs = self._normalise_deployments(deployments or {}) if deployments else {}

        self._model_specs = self._merge_specs(registry_specs, override_specs)
        if not self._model_specs:
            raise ValueError(
                "Azure OpenAI provider requires at least one configured deployment. "
                "Populate conf/azure_models.json or set AZURE_MODELS_CONFIG_PATH."
            )

        self._capabilities = self._build_capabilities_map()
        self._deployment_map = {name: spec["deployment"] for name, spec in self._model_specs.items()}
        self._deployment_alias_lookup = {
            deployment.lower(): canonical for canonical, deployment in self._deployment_map.items()
        }
        self._canonical_lookup = {name.lower(): name for name in self._model_specs.keys()}
        self._invalidate_capability_cache()

    # ------------------------------------------------------------------
    # Capability helpers
    # ------------------------------------------------------------------
    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        return dict(self._capabilities)

    def get_provider_type(self) -> ProviderType:
        return ProviderType.AZURE

    def get_capabilities(self, model_name: str) -> ModelCapabilities:  # type: ignore[override]
        lowered = model_name.lower()
        if lowered in self._deployment_alias_lookup:
            canonical = self._deployment_alias_lookup[lowered]
            return super().get_capabilities(canonical)
        canonical = self._canonical_lookup.get(lowered)
        if canonical:
            return super().get_capabilities(canonical)
        return super().get_capabilities(model_name)

    def validate_model_name(self, model_name: str) -> bool:  # type: ignore[override]
        lowered = model_name.lower()
        if lowered in self._deployment_alias_lookup or lowered in self._canonical_lookup:
            return True
        return super().validate_model_name(model_name)

    def _build_capabilities_map(self) -> dict[str, ModelCapabilities]:
        capabilities: dict[str, ModelCapabilities] = {}

        for canonical_name, spec in self._model_specs.items():
            template_capability: ModelCapabilities | None = spec.get("capability")
            overrides = spec.get("overrides", {})

            if template_capability:
                cloned = replace(template_capability)
            else:
                template = OpenAIModelProvider.MODEL_CAPABILITIES.get(canonical_name)

                if template:
                    friendly = template.friendly_name.replace("OpenAI", "Azure OpenAI", 1)
                    cloned = replace(
                        template,
                        provider=ProviderType.AZURE,
                        friendly_name=friendly,
                        aliases=list(template.aliases),
                    )
                else:
                    deployment_name = spec.get("deployment", "")
                    cloned = ModelCapabilities(
                        provider=ProviderType.AZURE,
                        model_name=canonical_name,
                        friendly_name=f"Azure OpenAI ({canonical_name})",
                        description=f"Azure deployment '{deployment_name}' for {canonical_name}",
                        aliases=[],
                    )

            if overrides:
                overrides = dict(overrides)
                temp_override = overrides.get("temperature_constraint")
                if isinstance(temp_override, str):
                    overrides["temperature_constraint"] = TemperatureConstraint.create(temp_override)

                aliases_override = overrides.get("aliases")
                if isinstance(aliases_override, str):
                    overrides["aliases"] = [alias.strip() for alias in aliases_override.split(",") if alias.strip()]
                provider_override = overrides.get("provider")
                if provider_override:
                    overrides.pop("provider", None)

                try:
                    cloned = replace(cloned, **overrides)
                except TypeError:
                    base_data = asdict(cloned)
                    base_data.update(overrides)
                    base_data["provider"] = ProviderType.AZURE
                    temp_value = base_data.get("temperature_constraint")
                    if isinstance(temp_value, str):
                        base_data["temperature_constraint"] = TemperatureConstraint.create(temp_value)
                    cloned = ModelCapabilities(**base_data)

            if cloned.provider != ProviderType.AZURE:
                cloned.provider = ProviderType.AZURE

            capabilities[canonical_name] = cloned

        return capabilities

    def _load_registry_entries(self) -> dict[str, dict]:
        try:
            registry = AzureModelRegistry()
        except Exception as exc:  # pragma: no cover - registry failure should not crash provider
            logger.warning("Unable to load Azure model registry: %s", exc)
            return {}

        entries: dict[str, dict] = {}
        for model_name, capability, extra in registry.iter_entries():
            deployment = extra.get("deployment")
            if not deployment:
                logger.warning("Azure model '%s' missing deployment in registry", model_name)
                continue
            entries[model_name] = {"deployment": deployment, "capability": capability}

        return entries

    @staticmethod
    def _merge_specs(
        registry_specs: dict[str, dict],
        override_specs: dict[str, dict],
    ) -> dict[str, dict]:
        specs: dict[str, dict] = {}

        for canonical, entry in registry_specs.items():
            specs[canonical] = {
                "deployment": entry.get("deployment"),
                "capability": entry.get("capability"),
                "overrides": {},
            }

        for canonical, entry in override_specs.items():
            spec = specs.get(canonical, {"deployment": None, "capability": None, "overrides": {}})
            deployment = entry.get("deployment")
            if deployment:
                spec["deployment"] = deployment
            overrides = {k: v for k, v in entry.items() if k not in {"deployment"}}
            overrides.pop("capability", None)
            if overrides:
                spec["overrides"].update(overrides)
            specs[canonical] = spec

        return {k: v for k, v in specs.items() if v.get("deployment")}

    @staticmethod
    def _normalise_deployments(mapping: dict[str, object]) -> dict[str, dict]:
        normalised: dict[str, dict] = {}
        for canonical, spec in mapping.items():
            canonical_name = (canonical or "").strip()
            if not canonical_name:
                continue

            deployment_name: str | None = None
            overrides: dict[str, object] = {}

            if isinstance(spec, str):
                deployment_name = spec.strip()
            elif isinstance(spec, dict):
                deployment_name = spec.get("deployment") or spec.get("deployment_name")
                overrides = {k: v for k, v in spec.items() if k not in {"deployment", "deployment_name"}}

            if not deployment_name:
                continue

            normalised[canonical_name] = {"deployment": deployment_name.strip(), **overrides}

        return normalised

    # ------------------------------------------------------------------
    # Azure-specific configuration
    # ------------------------------------------------------------------
    @property
    def client(self):  # type: ignore[override]
        """Instantiate the Azure OpenAI client on first use."""

        if self._client is None:
            if AzureOpenAI is None:
                raise ImportError(
                    "Azure OpenAI support requires the 'openai' package. Install it with `pip install openai`."
                )

            import httpx

            proxy_env_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]

            with suppress_env_vars(*proxy_env_vars):
                try:
                    timeout_config = self.timeout_config

                    http_client = httpx.Client(timeout=timeout_config, follow_redirects=True)

                    client_kwargs = {
                        "api_key": self.api_key,
                        "azure_endpoint": self.azure_endpoint,
                        "api_version": self.api_version,
                        "http_client": http_client,
                    }

                    if self.DEFAULT_HEADERS:
                        client_kwargs["default_headers"] = self.DEFAULT_HEADERS.copy()

                    logger.debug(
                        "Initializing Azure OpenAI client endpoint=%s api_version=%s timeouts=%s",
                        self.azure_endpoint,
                        self.api_version,
                        timeout_config,
                    )

                    self._client = AzureOpenAI(**client_kwargs)

                except Exception as exc:
                    logger.error("Failed to create Azure OpenAI client: %s", exc)
                    raise

        return self._client

    # ------------------------------------------------------------------
    # Request delegation
    # ------------------------------------------------------------------
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int | None = None,
        images: list[str] | None = None,
        **kwargs,
    ) -> ModelResponse:
        canonical_name, deployment_name = self._resolve_canonical_and_deployment(model_name)

        # Delegate to the shared OpenAI-compatible implementation using the
        # deployment name – Azure requires the deployment identifier in the
        # ``model`` field.  The returned ``ModelResponse`` is normalised so
        # downstream consumers continue to see the canonical model name.
        raw_response = super().generate_content(
            prompt=prompt,
            model_name=deployment_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            images=images,
            **kwargs,
        )

        capabilities = self._capabilities.get(canonical_name)
        friendly_name = capabilities.friendly_name if capabilities else self.FRIENDLY_NAME

        return ModelResponse(
            content=raw_response.content,
            usage=raw_response.usage,
            model_name=canonical_name,
            friendly_name=friendly_name,
            provider=ProviderType.AZURE,
            metadata={**raw_response.metadata, "deployment": deployment_name},
        )

    def _resolve_canonical_and_deployment(self, model_name: str) -> tuple[str, str]:
        resolved_canonical = self._resolve_model_name(model_name)

        if resolved_canonical not in self._deployment_map:
            # The base resolver may hand back the deployment alias. Try to map it
            # back to a canonical entry.
            for canonical, deployment in self._deployment_map.items():
                if deployment.lower() == resolved_canonical.lower():
                    return canonical, deployment
            raise ValueError(f"Model '{model_name}' is not configured for Azure OpenAI")

        return resolved_canonical, self._deployment_map[resolved_canonical]

    def _parse_allowed_models(self) -> set[str] | None:  # type: ignore[override]
        # Support both AZURE_ALLOWED_MODELS (inherited behaviour) and the
        # clearer AZURE_OPENAI_ALLOWED_MODELS alias.
        explicit = get_env("AZURE_OPENAI_ALLOWED_MODELS")
        if explicit:
            models = {m.strip().lower() for m in explicit.split(",") if m.strip()}
            if models:
                logger.info("Configured allowed models for Azure OpenAI: %s", sorted(models))
                self._allowed_alias_cache = {}
                return models

        return super()._parse_allowed_models()

    # ------------------------------------------------------------------
    # Token estimation (Azure uses OpenAI models)
    # ------------------------------------------------------------------
    def _calculate_text_tokens(self, model_name: str, content: str) -> int:
        """Calculate text token count using OpenAI's tiktoken.

        Azure OpenAI hosts OpenAI models, so we use OpenAI's token estimation.

        Args:
            model_name: The model to count tokens for
            content: Text content

        Returns:
            Token count
        """
        return openai_token_estimator.calculate_text_tokens(model_name, content)

    def estimate_tokens_for_files(self, model_name: str, files: list[dict], image_detail: str = None) -> int:
        """Estimate token count for files using OpenAI's offline calculation.

        Azure OpenAI hosts OpenAI models, so we use OpenAI's token estimation.

        Supports:
        - Text files: tiktoken with model-specific encodings
        - Images:
          * Tile-based (Main models: GPT-4o, GPT-4.1, GPT-5, o3, o4)
          * Patch-based (Small models: mini/nano variants)
        - PDF/Documents: Via Responses API (accurate with MediaBox and aspect ratio)

        Args:
            model_name: The model to estimate tokens for
            files: List of file dicts with 'path' and 'mime_type' keys
            image_detail: Detail level for images ("low", "high", or "auto").
                          If None, uses module-level OPENAI_IMAGE_DETAIL configuration

        Returns:
            Estimated token count

        Raises:
            ValueError: If a file cannot be accessed or has an unsupported mime type
        """
        # Check if model uses Responses API (enables PDF/document support)
        try:
            capabilities = self.get_capabilities(model_name)
            use_responses_api = getattr(capabilities, "use_openai_response_api", False)
        except Exception:
            use_responses_api = False

        # Use explicit parameter or fall back to module-level config (PR 302 pattern)
        detail = image_detail if image_detail is not None else OPENAI_IMAGE_DETAIL

        return openai_token_estimator.estimate_tokens_for_files(
            model_name, files, detail, use_responses_api=use_responses_api
        )
