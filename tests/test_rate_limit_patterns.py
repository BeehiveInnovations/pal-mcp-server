"""
Test to verify structured error code-based retry logic.
"""

from providers.gemini import GeminiModelProvider
from providers.openai_provider import OpenAIModelProvider


def test_openai_structured_error_retry_logic():
    """Test OpenAI provider's structured error code retry logic."""
    provider = OpenAIModelProvider(api_key="test-key")

    # Test structured token-related 429 error (should NOT be retried)
    class MockTokenError(Exception):
        def __init__(self):
            # Simulate the actual error format from OpenAI API
            self.args = (
                "Error code: 429 - {'error': {'message': 'Request too large for o3', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}",
            )

    token_error = MockTokenError()
    assert not provider._is_error_retryable(token_error), "Token-related 429 should not be retryable"

    # Test standard rate limiting 429 error (should be retried)
    class MockRateLimitError(Exception):
        def __init__(self):
            self.args = (
                "Error code: 429 - {'error': {'message': 'Too many requests', 'type': 'requests', 'code': 'rate_limit_exceeded'}}",
            )

    rate_limit_error = MockRateLimitError()
    assert provider._is_error_retryable(rate_limit_error), "Request rate limiting should be retryable"

    # Test context length error (should NOT be retried)
    class MockContextError(Exception):
        def __init__(self):
            self.args = (
                "Error code: 429 - {'error': {'message': 'Context length exceeded', 'code': 'context_length_exceeded'}}",
            )

    context_error = MockContextError()
    assert not provider._is_error_retryable(context_error), "Context length errors should not be retryable"


def test_gemini_structured_error_retry_logic():
    """Test Gemini provider's structured error code retry logic."""
    provider = GeminiModelProvider(api_key="test-key")

    # Test quota exceeded error (should NOT be retried)
    class MockQuotaError(Exception):
        def __init__(self):
            self.args = ("429 Resource exhausted: Quota exceeded for model",)
            self.details = "quota_exceeded"

    quota_error = MockQuotaError()
    assert not provider._is_error_retryable(quota_error), "Quota exceeded should not be retryable"

    # Test resource exhausted error (should NOT be retried)
    class MockResourceError(Exception):
        def __init__(self):
            self.args = ("429 Resource exhausted: Token limit exceeded",)

    resource_error = MockResourceError()
    assert not provider._is_error_retryable(resource_error), "Resource exhausted should not be retryable"

    # Test temporary rate limiting (should be retried)
    class MockTempError(Exception):
        def __init__(self):
            self.args = ("429 Too many requests, please try again later",)

    temp_error = MockTempError()
    assert provider._is_error_retryable(temp_error), "Temporary rate limiting should be retryable"


def test_actual_log_error_from_issue_with_structured_parsing():
    """Test the specific error from the user's log using structured parsing."""
    provider = OpenAIModelProvider(api_key="test-key")

    # Create the exact error from the user's log
    class MockUserLogError(Exception):
        def __init__(self):
            # This is the exact error message from the user's issue
            self.args = (
                "Error code: 429 - {'error': {'message': 'Request too large for o3 in organization org-MWp466of2XGyS90J8huQk4R6 on tokens per min (TPM): Limit 30000, Requested 31756. The input or output tokens must be reduced in order to run successfully. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'tokens', 'param': None, 'code': 'rate_limit_exceeded'}}",
            )

    user_error = MockUserLogError()

    # This specific error should NOT be retryable because it has type='tokens'
    assert not provider._is_error_retryable(user_error), "The user's specific error should be non-retryable"


def test_non_429_errors_still_work():
    """Test that non-429 errors are still handled correctly."""
    provider = OpenAIModelProvider(api_key="test-key")

    # Test retryable non-429 errors
    class MockTimeoutError(Exception):
        def __init__(self):
            self.args = ("Connection timeout",)

    timeout_error = MockTimeoutError()
    assert provider._is_error_retryable(timeout_error), "Timeout errors should be retryable"

    class Mock500Error(Exception):
        def __init__(self):
            self.args = ("500 Internal Server Error",)

    server_error = Mock500Error()
    assert provider._is_error_retryable(server_error), "500 errors should be retryable"

    # Test non-retryable non-429 errors
    class MockAuthError(Exception):
        def __init__(self):
            self.args = ("401 Unauthorized",)

    auth_error = MockAuthError()
    assert not provider._is_error_retryable(auth_error), "Auth errors should not be retryable"


def test_edge_cases_and_fallbacks():
    """Test edge cases and fallback behavior."""
    provider = OpenAIModelProvider(api_key="test-key")

    # Test malformed JSON in error (should fall back gracefully)
    class MockMalformedError(Exception):
        def __init__(self):
            self.args = ("Error code: 429 - {invalid json}",)

    malformed_error = MockMalformedError()
    # Should still be retryable since it's a 429 without clear non-retryable indicators
    assert provider._is_error_retryable(malformed_error), "Malformed 429 errors should default to retryable"

    # Test 429 without structured data (should be retryable by default)
    class MockSimple429Error(Exception):
        def __init__(self):
            self.args = ("429 Too Many Requests",)

    simple_429_error = MockSimple429Error()
    assert provider._is_error_retryable(simple_429_error), "Simple 429 without type info should be retryable"
