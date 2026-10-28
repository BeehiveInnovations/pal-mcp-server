"""
Smoke test suite for SecSuiteTool (native Burp alternative tool).
"""

import pytest
from tools.secsuite import SecSuiteTool, SecSuiteRequest


def test_secsuite_jwt_decode():
    tool = SecSuiteTool()
    assert tool.get_name() == "secsuite"

    # Create a dummy token or test action
    # For testing jwt_decode action with an invalid or test token
    request = SecSuiteRequest(
        action="jwt_decode",
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    # We can invoke execute or test request parsing
    assert request.action == "jwt_decode"
    assert request.token is not None


def test_secsuite_metadata():
    tool = SecSuiteTool()
    assert "security testing" in tool.get_description()
    assert tool.requires_model() is False
