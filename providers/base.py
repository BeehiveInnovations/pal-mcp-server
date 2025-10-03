"""Base interfaces and common behaviour for model providers."""

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    """Abstract base class for all model backends in the MCP server.

    Role
        Defines the interface every provider must implement so the registry,
        restriction service, and tools have a uniform surface for listing
        models, resolving aliases, and executing requests.

    Responsibilities
        * expose static capability metadata for each supported model via
          :class:`ModelCapabilities`
        * accept user prompts, forward them to the underlying SDK, and wrap
          responses in :class:`ModelResponse`
        * report tokenizer counts for budgeting and validation logic
        * advertise provider identity (``ProviderType``) so restriction
          policies can map environment configuration onto providers
        * validate whether a model name or alias is recognised by the provider

    Shared helpers like temperature validation, alias resolution, and
    restriction-aware ``list_models`` live here so concrete subclasses only
    need to supply their catalogue and wire up SDK-specific behaviour.
    """

    # All concrete providers must define their supported models
    MODEL_CAPABILITIES: dict[str, Any] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize the provider with API key and optional configuration."""
        self.api_key = api_key
        self.config = kwargs
        self._sorted_capabilities_cache: Optional[list[tuple[str, ModelCapabilities]]] = None

    # ------------------------------------------------------------------
    # Provider identity & capability surface
    # ------------------------------------------------------------------
    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Return the concrete provider identity."""

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Resolve capability metadata for a model name.

        This centralises the alias resolution → lookup → restriction check
        pipeline so providers only override the pieces they genuinely need to
        customise. Subclasses usually only override ``_lookup_capabilities`` to
        integrate a registry or dynamic source, or ``_finalise_capabilities`` to
        tweak the returned object.
        """

        resolved_name = self._resolve_model_name(model_name)
        capabilities = self._lookup_capabilities(resolved_name, model_name)

        if capabilities is None:
            self._raise_unsupported_model(model_name)

        self._ensure_model_allowed(capabilities, resolved_name, model_name)
        return self._finalise_capabilities(capabilities, resolved_name, model_name)

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Return statically declared capabilities when available."""

        model_map = getattr(self, "MODEL_CAPABILITIES", None)
        if isinstance(model_map, dict) and model_map:
            return {k: v for k, v in model_map.items() if isinstance(v, ModelCapabilities)}
        return {}

    def get_capabilities_by_rank(self) -> list[tuple[str, ModelCapabilities]]:
        """Return model capabilities sorted by effective capability rank."""

        if self._sorted_capabilities_cache is not None:
            return list(self._sorted_capabilities_cache)

        model_configs = self.get_all_model_capabilities()
        if not model_configs:
            self._sorted_capabilities_cache = []
            return []

        items = list(model_configs.items())
        items.sort(key=lambda item: (-item[1].get_effective_capability_rank(), item[0]))
        self._sorted_capabilities_cache = items
        return list(items)

    def _invalidate_capability_cache(self) -> None:
        """Clear cached sorted capability data (call after dynamic updates)."""

        self._sorted_capabilities_cache = None

    def list_models(
        self,
        *,
        respect_restrictions: bool = True,
        include_aliases: bool = True,
        lowercase: bool = False,
        unique: bool = False,
    ) -> list[str]:
        """Return formatted model names supported by this provider."""

        model_configs = self.get_all_model_capabilities()
        if not model_configs:
            return []

        restriction_service = None
        if respect_restrictions:
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service()

        if restriction_service:
            allowed_configs = {}
            for model_name, config in model_configs.items():
                if restriction_service.is_allowed(self.get_provider_type(), model_name):
                    allowed_configs[model_name] = config
            model_configs = allowed_configs

        if not model_configs:
            return []

        return ModelCapabilities.collect_model_names(
            model_configs,
            include_aliases=include_aliases,
            lowercase=lowercase,
            unique=unique,
        )

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------
    @abstractmethod
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the model."""

    def count_tokens(self, text: str, model_name: str) -> int:
        """Estimate token usage for a piece of text."""

        resolved_model = self._resolve_model_name(model_name)

        if not text:
            return 0

        estimated = max(1, len(text) // 4)
        logger.debug("Estimating %s tokens for model %s via character heuristic", estimated, resolved_model)
        return estimated

    def close(self) -> None:
        """Clean up any resources held by the provider."""

        return

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------
    def _is_error_retryable(self, error: Exception) -> bool:
        """Return True when an error warrants another attempt.

        Subclasses with structured provider errors should override this hook.
        The default implementation only retries obvious transient failures such
        as timeouts or 5xx responses detected via string inspection.
        """

        error_str = str(error).lower()

        if "429" in error_str or "rate limit" in error_str:
            return False

        retryable_indicators = [
            "timeout",
            "connection",
            "temporary",
            "unavailable",
            "retry",
            "reset",
            "refused",
            "broken pipe",
            "tls",
            "handshake",
            "network",
            "500",
            "502",
            "503",
            "504",
        ]

        return any(indicator in error_str for indicator in retryable_indicators)

    def _run_with_retries(
        self,
        operation: Callable[[], Any],
        *,
        max_attempts: int,
        delays: Optional[list[float]] = None,
        log_prefix: str = "",
    ):
        """Execute ``operation`` with retry semantics.

        Args:
            operation: Callable returning the provider result.
            max_attempts: Maximum number of attempts (>=1).
            delays: Optional list of sleep durations between attempts.
            log_prefix: Optional identifier for log clarity.

        Returns:
            Whatever ``operation`` returns.

        Raises:
            The last exception when all retries fail or the error is not retryable.
        """

        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        attempts = max_attempts
        delays = delays or []
        last_exc: Optional[Exception] = None

        for attempt_index in range(attempts):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001 - bubble exact provider errors
                last_exc = exc
                attempt_number = attempt_index + 1

                # Decide whether to retry based on subclass hook
                retryable = self._is_error_retryable(exc)
                if not retryable or attempt_number >= attempts:
                    raise

                delay_idx = min(attempt_index, len(delays) - 1) if delays else -1
                delay = delays[delay_idx] if delay_idx >= 0 else 0.0

                if delay > 0:
                    logger.warning(
                        "%s retryable error (attempt %s/%s): %s. Retrying in %ss...",
                        log_prefix or self.__class__.__name__,
                        attempt_number,
                        attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        "%s retryable error (attempt %s/%s): %s. Retrying...",
                        log_prefix or self.__class__.__name__,
                        attempt_number,
                        attempts,
                        exc,
                    )

        # Should never reach here because loop either returns or raises
        raise last_exc if last_exc else RuntimeError("Retry loop exited without result")

    # ------------------------------------------------------------------
    # Validation hooks
    # ------------------------------------------------------------------
    def validate_model_name(self, model_name: str) -> bool:
        """Return ``True`` when the model resolves to an allowed capability."""

        try:
            self.get_capabilities(model_name)
        except ValueError:
            return False
        return True

    def validate_parameters(self, model_name: str, temperature: float, **kwargs) -> None:
        """Validate model parameters against capabilities."""

        capabilities = self.get_capabilities(model_name)

        if not capabilities.temperature_constraint.validate(temperature):
            constraint_desc = capabilities.temperature_constraint.get_description()
            raise ValueError(f"Temperature {temperature} is invalid for model {model_name}. {constraint_desc}")

    # ------------------------------------------------------------------
    # Preference / registry hooks
    # ------------------------------------------------------------------
    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get the preferred model from this provider for a given category."""

        return None

    def get_model_registry(self) -> Optional[dict[str, Any]]:
        """Return the model registry backing this provider, if any."""

        return None

    # ------------------------------------------------------------------
    # Capability lookup pipeline
    # ------------------------------------------------------------------
    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: Optional[str] = None,
    ) -> Optional[ModelCapabilities]:
        """Return ``ModelCapabilities`` for the canonical model name."""

        return self.get_all_model_capabilities().get(canonical_name)

    def _ensure_model_allowed(
        self,
        capabilities: ModelCapabilities,
        canonical_name: str,
        requested_name: str,
    ) -> None:
        """Raise ``ValueError`` if the model violates restriction policy."""

        try:
            from utils.model_restrictions import get_restriction_service
        except Exception:  # pragma: no cover - only triggered if service import breaks
            return

        restriction_service = get_restriction_service()
        if not restriction_service:
            return

        if restriction_service.is_allowed(self.get_provider_type(), canonical_name, requested_name):
            return

        raise ValueError(
            f"{self.get_provider_type().value} model '{canonical_name}' is not allowed by restriction policy."
        )

    def _finalise_capabilities(
        self,
        capabilities: ModelCapabilities,
        canonical_name: str,
        requested_name: str,
    ) -> ModelCapabilities:
        """Allow subclasses to adjust capability metadata before returning."""

        return capabilities

    def _raise_unsupported_model(self, model_name: str) -> None:
        """Raise the canonical unsupported-model error."""

        raise ValueError(f"Unsupported model '{model_name}' for provider {self.get_provider_type().value}.")

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model shorthand to full name.

        This implementation uses the hook methods to support different
        model configuration sources.

        Args:
            model_name: Model name that may be an alias

        Returns:
            Resolved model name
        """
        # Get model configurations from the hook method
        model_configs = self.get_all_model_capabilities()

        # First check if it's already a base model name (case-sensitive exact match)
        if model_name in model_configs:
            return model_name

        # Check case-insensitively for both base models and aliases
        model_name_lower = model_name.lower()

        # Check base model names case-insensitively
        for base_model in model_configs:
            if base_model.lower() == model_name_lower:
                return base_model

        # Check aliases from the model configurations
        alias_map = ModelCapabilities.collect_aliases(model_configs)
        for base_model, aliases in alias_map.items():
            if any(alias.lower() == model_name_lower for alias in aliases):
                return base_model

        # If not found, return as-is
        return model_name
