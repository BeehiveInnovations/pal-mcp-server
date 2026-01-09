"""Tests for SAIA provider with API key rotation."""

import os
from unittest.mock import MagicMock, patch

from providers.saia import SAIAProvider, RotationStrategy
from providers.shared import ProviderType
from providers.api_key_rotator import APIKeyRotator, KeyUsageTracker


class TestSAIAProvider:
    """Test SAIA provider functionality with API key rotation."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear any cached providers
        import providers.saia
        import providers.registry

        providers.registry.ModelProviderRegistry._providers = {}

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear providers registry
        import providers.registry

        providers.registry.ModelProviderRegistry._providers = {}

    @patch.dict(os.environ, {"SAIA_API_KEY": "key1,key2,key3"})
    def test_initialization_with_multiple_keys(self):
        """Test SAIA provider initialization with multiple API keys."""
        provider = SAIAProvider(["key1", "key2", "key3"])

        assert provider.get_provider_type() == "saia"
        assert provider.SAIA_BASE_URL == "https://chat-ai.academiccloud.de/v1"
        assert provider.key_rotator.strategy == RotationStrategy.ROUND_ROBIN
        assert len(provider.key_rotator.api_keys) == 3

    @patch.dict(os.environ, {"SAIA_API_KEY": "single-key"})
    def test_initialization_with_single_key(self):
        """Test SAIA provider initialization with single API key."""
        provider = SAIAProvider(["single-key"])

        assert provider.get_provider_type() == "saia"
        assert provider.key_rotator.strategy == RotationStrategy.ROUND_ROBIN
        assert len(provider.key_rotator.api_keys) == 1

    @patch.dict(os.environ, {"SAIA_API_KEY": "  key1  ,  key2  ,  key3  "})
    def test_initialization_with_whitespace_keys(self):
        """Test SAIA provider initialization with keys containing whitespace."""
        provider = SAIAProvider(["key1", "key2", "key3"])

        assert provider.get_provider_type() == "saia"
        # Should trim and ignore empty keys
        assert len(provider.key_rotator.api_keys) == 3

    @patch.dict(os.environ, {"SAIA_API_KEY": ""})
    def test_initialization_with_empty_key(self):
        """Test that empty SAIA_API_KEY raises ValueError."""
        with self.assertRaises(ValueError) as context:
            SAIAProvider([])

    @patch.dict(os.environ, {"SAIA_API_KEY": "key1,key2"})
    def test_model_validation(self):
        """Test model name validation for SAIA models."""
        provider = SAIAProvider(["key1"])

        # Test valid models
        assert provider.validate_model_name("meta-llama-3.1-8b-instruct") is True
        assert provider.validate_model_name("llama-3.1") is True  # alias
        assert provider.validate_model_name("gemma-3.27b-it") is True
        assert provider.validate_model_name("qwq-32b") is True
        assert provider.validate_model_name("deepseek-r1") is True
        assert provider.validate_model_name("qwen3-embedding-4b") is True

        # Test invalid models
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4o") is False  # OpenAI model, not SAIA

    def test_get_all_model_capabilities(self):
        """Test that provider exposes all model capabilities."""
        provider = SAIAProvider(["key1"])

        capabilities = provider.get_all_model_capabilities()

        # Should have all models defined in MODEL_CAPABILITIES
        assert len(capabilities) == 21  # Count of models in saia.py

        # Test specific models
        assert "meta-llama-3.1-8b-instruct" in capabilities
        assert "deepseek-r1" in capabilities
        assert "qwen3-embedding-4b" in capabilities

    def test_rotation_strategies(self):
        """Test different rotation strategies."""
        import threading

        # Test round-robin strategy
        provider_round_robin = SAIAProvider(["key1", "key2"], strategy=RotationStrategy.ROUND_ROBIN)
        assert provider_round_robin.key_rotator.strategy == RotationStrategy.ROUND_ROBIN

        # Test least-used strategy
        provider_least_used = SAIAProvider(["key1", "key2"], strategy=RotationStrategy.LEAST_USED)
        assert provider_least_used.key_rotator.strategy == RotationStrategy.LEAST_USED

        # Test random strategy
        provider_random = SAIAProvider(["key1", "key2"], strategy=RotationStrategy.RANDOM)
        assert provider_random.key_rotator.strategy == RotationStrategy.RANDOM

    def test_key_rotation_on_rate_limit(self):
        """Test that provider rotates keys on 429 rate limit errors."""
        provider = SAIAProvider(["key1", "key2"])

        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {
            "x-ratelimit-limit-minute": "1000",
            "x-ratelimit-remaining-minute": "0",
            "ratelimit-reset": "3600",  # 1 hour
        }

        # Simulate first request getting rate limited
        provider.key_rotator._update_key_usage("key1", mock_response.headers)
        tracker = provider.key_rotator.usage_trackers["key1"]
        assert tracker.is_exhausted is True
        assert tracker.requests_remaining == 0

        # Next request should rotate to key2
        key2_tracker = provider.key_rotator.usage_trackers["key2"]
        key2, _ = provider.key_rotator.get_next_key()

        assert key2 == "key2"

    def test_rate_limit_parsing(self):
        """Test rate limit header parsing."""
        from providers.api_key_rotator import RateLimitHeaders

        # Test valid headers
        headers = {
            "x-ratelimit-limit-minute": "1000",
            "x-ratelimit-remaining-minute": "999",
            "ratelimit-reset": "1800",
        }

        parsed = RateLimitHeaders()

        assert parsed.limit_minute == 1000
        assert parsed.remaining_minute == 999
        assert parsed.reset_time is not None  # Should be set in parsing

    def test_usage_stats(self):
        """Test usage statistics gathering."""
        provider = SAIAProvider(["key1", "key2", "key3"])

        stats = provider.get_rotation_stats()

        assert stats["total_keys"] == 3
        assert stats["strategy"] == RotationStrategy.ROUND_ROBIN
        assert "total_remaining_requests" in stats
        assert stats["exhausted_keys"] == 0

    def test_custom_backoff_duration(self):
        """Test custom backoff duration configuration."""
        provider = SAIAProvider(["key1"], backoff_seconds=120)

        assert provider.key_rotator.backoff_seconds == 120

    def test_concurrent_key_selection(self):
        """Test thread-safe key selection for concurrent requests."""
        import threading

        provider = SAIAProvider(["key1", "key2", "key3"])

        # Simulate concurrent requests
        results = []
        threads = []

        def select_key(thread_id):
            key, _ = provider.key_rotator.get_next_key()
            results.append((thread_id, key))

        for i in range(10):
            t = threading.Thread(target=select_key, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check that all selections succeeded without errors
        assert len(results) == 10
        assert len(set(k for _, k in results)) >= 2  # At least 2 keys should be used

    def test_get_rotation_stats_format(self):
        """Test that rotation stats are in correct format."""
        provider = SAIAProvider(["key1", "key2"])

        stats = provider.get_rotation_stats()

        # Check structure
        assert "total_keys" in stats
        assert "exhausted_keys" in stats
        assert "strategy" in stats
        assert "total_remaining_requests" in stats

        # Check per-key stats exist
        per_key_keys = [k for k in stats.keys() if "..." in k]
        assert len(per_key_keys) == 3  # All 3 keys should have stats

    @patch.dict(os.environ, {"SAIA_API_KEY": "key1,key2"}, {"SAIA_ROTATION_STRATEGY": "least_used"})
    def test_generate_content_with_rotation(self):
        """Test that generate_content uses rotated keys."""
        provider = SAIAProvider(["key1", "key2"], strategy=RotationStrategy.LEAST_USED)

        # Mock responses to simulate rotation
        with patch.object(provider, "_client") as mock_client:
            # First call - rate limited with key1
            mock_client.return_value = MagicMock(
                status_code=429, headers={"x-ratelimit-remaining-minute": "0", "ratelimit-reset": "3600"}
            )

            response1 = provider.generate_content(
                prompt="Test 1",
                model_name="meta-llama-3.1-8b-instruct",
                temperature=0.5,
            )

            assert "rotation_performed" in response1.metadata

            # Second call - successful with key2
            mock_client.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "choices": [{"message": {"content": "Response 2"}}],
                    "usage": {"total_tokens": 10},
                },
                headers={
                    "x-ratelimit-limit-minute": "1000",
                    "x-ratelimit-remaining-minute": "999",
                },
            )

            response2 = provider.generate_content(
                prompt="Test 2",
                model_name="meta-llama-3.1-8b-instruct",
                temperature=0.5,
            )

            # Verify key2 was used
            assert response2.metadata["api_key_used"] == "key2..."

            # Third call - should use key2 again
            response3 = provider.generate_content(
                prompt="Test 3",
                model_name="meta-llama-3.1-8b-instruct",
                temperature=0.5,
            )

            assert response3.metadata["api_key_used"] == "key2..."
