"""Generic loader for extra OpenAI-compatible providers from ~/.pal/keys.json.

Any entry whose ``status`` starts with "WORKING", that has a ``base`` URL and an
explicit ``models`` list, and whose name is not already natively wired, is
registered as an OpenAI-compatible provider that claims ONLY its listed models
(a strict allowlist, so it never shadows other providers). Each is inserted into
the registry priority order before Cohere/HuggingFace/OpenRouter so it wins for
its own models. Robust: one bad entry never breaks startup.
"""

from __future__ import annotations

import json
import logging
import os

from providers.openai_compatible import OpenAICompatibleProvider
from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

log = logging.getLogger(__name__)

_NATIVE = {"openrouter", "gemini", "groq", "openai", "custom", "huggingface", "cohere", "glm"}


def _ensure_provider_type(name: str) -> ProviderType:
    """Return a ProviderType member for ``name``, extending the enum if needed."""
    key = name.upper()
    if key in ProviderType.__members__:
        return ProviderType[key]
    try:
        from aenum import extend_enum

        extend_enum(ProviderType, key, name.lower())
        return ProviderType[key]
    except Exception:
        # Fallback: inject directly into the enum maps.
        member = object.__new__(ProviderType)
        member._name_ = key
        member._value_ = name.lower()
        ProviderType._member_map_[key] = member
        ProviderType._value2member_map_[name.lower()] = member
        return member


def _make_provider(base_url, friendly, ptype, allow, api_key):
    """Factory so each provider binds ITS OWN values (avoids loop-closure bugs)."""

    class _Extra(OpenAICompatibleProvider):
        FRIENDLY_NAME = friendly

        def __init__(self, api_key=None, **kw):
            super().__init__(api_key or api_key_default, base_url=base_url, **kw)

        def get_provider_type(self):
            return ptype

        def validate_model_name(self, model_name: str) -> bool:
            return model_name in allow

        def _lookup_capabilities(self, canonical_name, requested_name=None):
            if canonical_name in allow:
                cap = ModelCapabilities(
                    provider=ptype, model_name=canonical_name, friendly_name=friendly,
                    intelligence_score=9, context_window=128_000, max_output_tokens=4_096,
                    supports_extended_thinking=False, supports_system_prompts=True,
                    supports_streaming=True, supports_function_calling=True,
                    temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
                )
                cap._is_generic = True
                return cap
            return None

    api_key_default = api_key
    return _Extra


def _make_anthropic_provider(base_url, friendly, ptype, allow, api_key, extra_headers):
    """Factory for Anthropic Messages wire-format endpoints (non-Claude gateways).

    Mirrors ``_make_provider`` but builds on AnthropicCompatibleProvider, which
    refuses api.anthropic.com base URLs and claude-* model names.
    """
    from providers.anthropic_compatible import AnthropicCompatibleProvider

    class _ExtraAnthropic(AnthropicCompatibleProvider):
        FRIENDLY_NAME = friendly

        def __init__(self, api_key=None, **kw):
            super().__init__(
                api_key or api_key_default,
                base_url=base_url,
                extra_headers=dict(extra_headers or {}),
                **kw,
            )

        def get_provider_type(self):
            return ptype

        def validate_model_name(self, model_name: str) -> bool:
            if not super().validate_model_name(model_name):
                return False
            return model_name in allow

    api_key_default = api_key
    return _ExtraAnthropic


def register_extras(registry) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return  # inert during tests to avoid catalog pollution
    kf = os.path.expanduser("~/.pal/keys.json")
    try:
        data = json.load(open(kf, encoding="utf-8"))
    except Exception as exc:
        log.debug("extra_providers: cannot read %s: %s", kf, exc)
        return

    # Insert extras BEFORE these native providers so an extra's own (allowlisted)
    # models win over a native provider that also claims them. CUSTOM (the groq
    # flat-rate endpoint) aliases gpt-oss:120b/20b to its low-cap openai/gpt-oss-*;
    # without CUSTOM here, Ollama Cloud's gpt-oss:120b wrongly resolves to groq
    # (8000 TPM) and rate-limits. Extras have strict allowlists, so this is safe.
    insert_before = [ProviderType.OPENROUTER]
    for nm in ("CUSTOM", "COHERE", "HUGGINGFACE"):
        if nm in ProviderType.__members__:
            insert_before.append(ProviderType[nm])

    for name, info in data.items():
        try:
            if name.lower() in _NATIVE:
                continue
            base = (info or {}).get("base")
            status = (info or {}).get("status", "")
            models = [m for m in ((info or {}).get("models") or []) if m]
            keys = [k for k in ((info or {}).get("keys") or []) if k]
            if not base or not status.startswith("WORKING") or not models or not keys:
                continue

            p_type = _ensure_provider_type(name)
            api = str((info or {}).get("api", "")).lower()
            if api == "anthropic":
                if "anthropic.com" in base.lower():
                    log.debug("extra_providers: refusing anthropic.com base for %s", name)
                    continue
                headers = (info or {}).get("extra_headers") or {}
                klass = _make_anthropic_provider(
                    base, name.title(), p_type, set(models), keys[0], headers
                )
            else:
                klass = _make_provider(base, name.title(), p_type, set(models), keys[0])
            registry.register_provider(p_type, klass)
            # Pre-build the instance (key baked in) so get_provider returns it
            # directly without needing a *_API_KEY env mapping.
            try:
                registry()._initialized_providers[p_type] = klass(keys[0])
            except Exception as _e:
                log.debug("extra_providers: could not pre-init %s: %s", name, _e)
            order = getattr(registry, "PROVIDER_PRIORITY_ORDER", None)
            if isinstance(order, list):
                if p_type in order:
                    order.remove(p_type)
                idxs = [order.index(t) for t in insert_before if t in order]
                order.insert(min(idxs) if idxs else 0, p_type)
            log.debug("extra_providers: registered %s for %s", name, sorted(models))
        except Exception as exc:
            log.debug("extra_providers: skipped %s: %s", name, exc)
