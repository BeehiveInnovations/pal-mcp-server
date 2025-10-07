"""Mixin for providers backed by capability registries.

This mixin centralises the boilerplate for providers that expose their model
capabilities via JSON configuration files. Subclasses only need to set
``REGISTRY_CLASS`` to an appropriate :class:`CapabilityModelRegistry` and the
mix-in will take care of:

* Populating ``MODEL_CAPABILITIES`` exactly once per process (with optional
  reload support for tests).
* Lazily exposing the registry contents through the standard provider hooks
  (:meth:`get_all_model_capabilities` and :meth:`get_model_registry`).
* Providing defensive logging when a registry cannot be constructed so the
  provider can degrade gracefully instead of raising during import.

Using this helper keeps individual provider implementations focused on their
SDK-specific behaviour while ensuring capability loading is consistent across
OpenAI, Gemini, X.AI, and other native backends.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from .model_registry_base import CapabilityModelRegistry
from .shared import ModelCapabilities


class RegistryBackedProviderMixin:
    """Shared helper for providers that load capabilities from JSON registries."""

    REGISTRY_CLASS: ClassVar[type[CapabilityModelRegistry] | None] = None
    _registry: ClassVar[CapabilityModelRegistry | None] = None
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    @classmethod
    def _registry_logger(cls) -> logging.Logger:
        """Return the logger used for registry lifecycle messages."""
        return logging.getLogger(cls.__module__)

    @classmethod
    def _ensure_registry(cls, *, force_reload: bool = False) -> None:
        """Populate ``MODEL_CAPABILITIES`` from the configured registry.

        Args:
            force_reload: When ``True`` the registry is re-created even if it
                was previously loaded. This is primarily used by tests.
        """

        if cls.REGISTRY_CLASS is None:  # pragma: no cover - defensive programming
            raise RuntimeError(f"{cls.__name__} must define REGISTRY_CLASS.")

        if cls._registry is not None and not force_reload:
            return

        try:
            registry = cls.REGISTRY_CLASS()
        except Exception as exc:  # pragma: no cover - registry failures shouldn't break the provider
            cls._registry_logger().warning("Unable to load %s registry: %s", cls.__name__, exc)
            cls._registry = None
            cls.MODEL_CAPABILITIES = {}
            return

        cls._registry = registry
        cls.MODEL_CAPABILITIES = dict(registry.model_map)

    @classmethod
    def reload_registry(cls) -> None:
        """Force a registry reload (used in tests)."""

        cls._ensure_registry(force_reload=True)

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Return the registry-backed ``MODEL_CAPABILITIES`` map."""

        self._ensure_registry()
        return super().get_all_model_capabilities()

    def get_model_registry(self) -> dict[str, ModelCapabilities] | None:
        """Return a copy of the underlying registry map when available."""

        if self._registry is None:
            return None
        return dict(self._registry.model_map)
