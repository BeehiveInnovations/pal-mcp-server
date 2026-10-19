"""Tests for *_DISALLOWED_MODELS block-list functionality."""

import os
from unittest.mock import patch

from providers.openai import OpenAIModelProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from utils.model_restrictions import ModelRestrictionService


class TestDisallowedModels:
    """Block-list behaviour and its interaction with allow-lists."""

    def test_blocklist_rejects_listed_model_allows_others(self):
        """With only a block-list set, the listed model is rejected; others pass."""
        with patch.dict(os.environ, {"OPENAI_DISALLOWED_MODELS": "gpt-5.5-pro,gpt-5.4-pro"}, clear=True):
            service = ModelRestrictionService()

            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro")
            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.4-pro")
            # Everything else stays allowed (no allow-list configured)
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5")
            assert service.is_allowed(ProviderType.OPENAI, "o3")
            # has_restrictions must be True so filter_models actually filters
            assert service.has_restrictions(ProviderType.OPENAI)
            assert service.filter_models(ProviderType.OPENAI, ["gpt-5.4", "gpt-5.5-pro"]) == ["gpt-5.4"]

    def test_blocklist_takes_precedence_over_allowlist(self):
        """A model on both lists is blocked (block-list wins)."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_ALLOWED_MODELS": "gpt-5.4,gpt-5.5,gpt-5.5-pro",
                "OPENAI_DISALLOWED_MODELS": "gpt-5.5-pro",
            },
            clear=True,
        ):
            service = ModelRestrictionService()

            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.4")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5")
            # On the allow-list, but also blocked -> rejected
            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro")
            # Not on the allow-list -> rejected
            assert not service.is_allowed(ProviderType.OPENAI, "o3")

    def test_blocklist_is_per_provider(self):
        """A block-list on one provider does not affect another."""
        with patch.dict(os.environ, {"OPENROUTER_DISALLOWED_MODELS": "openai/gpt-5.5-pro"}, clear=True):
            service = ModelRestrictionService()

            assert not service.is_allowed(ProviderType.OPENROUTER, "openai/gpt-5.5-pro")
            assert service.is_allowed(ProviderType.OPENROUTER, "openai/gpt-5.5")
            # Other providers unaffected
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro")
            assert not service.has_restrictions(ProviderType.OPENAI)
            assert service.has_restrictions(ProviderType.OPENROUTER)

    def test_no_lists_allows_everything(self):
        """Sanity: with neither list set, nothing is restricted."""
        with patch.dict(os.environ, {}, clear=True):
            service = ModelRestrictionService()
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro")
            assert not service.has_restrictions(ProviderType.OPENAI)

    def test_get_disallowed_models(self):
        """get_disallowed_models returns the normalised block-list set."""
        with patch.dict(os.environ, {"OPENAI_DISALLOWED_MODELS": "GPT-5.5-Pro, gpt-5.4-pro"}, clear=True):
            service = ModelRestrictionService()
            assert service.get_disallowed_models(ProviderType.OPENAI) == {"gpt-5.5-pro", "gpt-5.4-pro"}
            assert service.get_disallowed_models(ProviderType.GOOGLE) is None

    def test_blocklist_alias_blocks_canonical(self):
        """A block-list entry written as an alias resolves and blocks the canonical model.

        Exercises the alias-aware matching in `_set_matches`: the block-list holds the alias
        `gpt55pro`, and a request for the resolved canonical `gpt-5.5-pro` must be rejected
        while its sibling `gpt-5.5` stays allowed. Requires a live provider for alias resolution.
        """
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "OPENAI_DISALLOWED_MODELS": "gpt55pro"},
            clear=True,
        ):
            service = ModelRestrictionService()

            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5")
            assert service.filter_models(ProviderType.OPENAI, ["gpt-5.5", "gpt-5.5-pro"]) == ["gpt-5.5"]

    def test_blocklist_canonical_blocks_request_via_alias(self):
        """A canonical model on the block-list rejects a request made via one of its aliases.

        `is_allowed` is called with the resolved canonical plus the `original_name` the caller
        used (`gpt55pro`); the canonical match must reject it.
        """
        with patch.dict(os.environ, {"OPENAI_DISALLOWED_MODELS": "gpt-5.5-pro"}, clear=True):
            service = ModelRestrictionService()

            assert not service.is_allowed(ProviderType.OPENAI, "gpt-5.5-pro", original_name="gpt55pro")
            assert service.is_allowed(ProviderType.OPENAI, "gpt-5.5", original_name="gpt55")
