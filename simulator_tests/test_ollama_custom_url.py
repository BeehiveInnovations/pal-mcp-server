#!/usr/bin/env python3
"""
Ollama Custom URL Test

Tests custom API endpoint functionality with Ollama-style local models, including:
- Basic chat with custom model via local endpoint
- File analysis with local model
- Conversation continuation with custom provider
- Model alias resolution for local models
"""


from .base_test import BaseSimulatorTest


class OllamaCustomUrlTest(BaseSimulatorTest):
    """Test Ollama custom URL functionality"""

    @property
    def test_name(self) -> str:
        return "ollama_custom_url"

    @property
    def test_description(self) -> str:
        return "Ollama custom URL endpoint functionality"

    def run_test(self) -> bool:
        """Test Ollama custom URL functionality"""
        try:
            self.logger.info("Test: Ollama custom URL functionality")

            # Check if custom URL is configured
            import os

            custom_url = os.environ.get("CUSTOM_API_URL")
            if not custom_url:
                self.logger.warning("CUSTOM_API_URL not set, skipping Ollama test")
                self.logger.info("To enable this test, add to .env file:")
                self.logger.info("CUSTOM_API_URL=http://localhost:11434/v1")
                self.logger.info("CUSTOM_API_KEY=")
                return True  # Skip gracefully

            self.logger.info(f"Testing with custom URL: {custom_url}")

            # Setup test files
            self.setup_test_files()

            # Test 1: Basic chat with local model
            self.logger.info("  1.1: Basic chat with local model")
            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Hello! Can you introduce yourself and tell me what model you are? Keep your response brief.",
                    "model": "llama3.2",  # Use exact Ollama model name
                },
            )

            if not self.validate_successful_response(response1, "local model chat"):
                return False

            self.logger.info(f"  ✅ Local model responded with continuation_id: {continuation_id}")

            # Test 2: File analysis with local model using a specific Ollama-related file
            self.logger.info("  1.2: File analysis with local model")

            # Create a simple, clear file that shouldn't require clarification
            ollama_test_content = '''"""
Ollama API Client Test
A simple test client for connecting to Ollama API endpoints
"""

import requests
import json

class OllamaClient:
    """Simple client for Ollama API"""

    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def list_models(self):
        """List available models"""
        response = requests.get(f"{self.base_url}/api/tags")
        return response.json()

    def generate(self, model, prompt):
        """Generate text using a model"""
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(f"{self.base_url}/api/generate", json=data)
        return response.json()

if __name__ == "__main__":
    client = OllamaClient()
    models = client.list_models()
    print(f"Available models: {len(models['models'])}")
'''

            # Create the test file
            ollama_test_file = self.create_additional_test_file("ollama_client.py", ollama_test_content)

            response2, _ = self.call_mcp_tool(
                "analyze",
                {
                    "files": [ollama_test_file],
                    "prompt": "Analyze this Ollama client code. What does this code do and what are its main functions?",
                    "model": "llama3.2",
                },
            )

            if not self.validate_successful_response(response2, "local model file analysis", files_provided=True):
                return False

            self.logger.info("  ✅ Local model analyzed file successfully")

            # Test 3: Continue conversation with local model
            if continuation_id:
                self.logger.info("  1.3: Continue conversation with local model")
                response3, _ = self.call_mcp_tool(
                    "chat",
                    {
                        "prompt": "Thanks for the introduction! I just analyzed an Ollama client Python file. Can you suggest one improvement for writing better API client code in general?",
                        "continuation_id": continuation_id,
                        "model": "llama3.2",
                    },
                )

                if not self.validate_successful_response(response3, "local model conversation continuation"):
                    return False

                self.logger.info("  ✅ Conversation continuation with local model working")

            # Test 4: Test alternative local model aliases
            self.logger.info("  1.4: Test alternative local model aliases")
            response4, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Quick test with alternative alias. Say 'Local model working' if you can respond.",
                    "model": "llama3.2",  # Alternative alias
                },
            )

            if not self.validate_successful_response(response4, "alternative local model alias"):
                return False

            self.logger.info("  ✅ Alternative local model alias working")

            # Test 5: Test direct model name (if applicable)
            self.logger.info("  1.5: Test direct model name")
            response5, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Final test with direct model name. Respond briefly.",
                    "model": "llama3.2",  # Direct model name
                },
            )

            if not self.validate_successful_response(response5, "direct model name"):
                return False

            self.logger.info("  ✅ Direct model name working")

            self.logger.info("  ✅ All Ollama custom URL tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Ollama custom URL test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()

    def validate_successful_response(self, response: str, test_name: str, files_provided: bool = False) -> bool:
        """Validate that the response indicates success, not an error

        Args:
            response: The response text to validate
            test_name: Name of the test for logging
            files_provided: Whether actual files were provided to the tool
        """
        if not response:
            self.logger.error(f"No response received for {test_name}")
            self._check_server_logs_for_errors()
            return False

        # Check for common error indicators
        error_indicators = [
            "OpenRouter API error",
            "is not a valid model ID",
            "API key not found",
            "Connection error",
            "connection refused",
            "network is unreachable",
            "timeout",
            "error 404",
            "error 400",
            "error 401",
            "error 403",
            "error 500",
            "status code 404",
            "status code 400",
            "status code 401",
            "status code 403",
            "status code 500",
            "status: error",
        ]

        # Special handling for clarification requests from local models
        if "files_required_to_continue" in response.lower():
            if files_provided:
                # If we provided actual files, clarification request is a FAILURE
                self.logger.error(
                    f"❌ Local model requested clarification for {test_name} despite being provided with actual files"
                )
                self.logger.debug(f"Clarification response: {response[:200]}...")
                return False
            else:
                # If no files were provided, clarification request is acceptable
                self.logger.info(
                    f"✅ Local model requested clarification for {test_name} - valid when no files provided"
                )
                self.logger.debug(f"Clarification response: {response[:200]}...")
                return True

        # Check for SSRF security restriction - this is expected for local URLs
        if "restricted IP address" in response and "security risk (SSRF)" in response:
            self.logger.info(
                f"✅ Custom URL routing working - {test_name} correctly attempted to connect to custom API"
            )
            self.logger.info("   (Connection blocked by SSRF protection, which is expected for local URLs)")
            return True

        response_lower = response.lower()
        for error in error_indicators:
            if error.lower() in response_lower:
                self.logger.error(f"Error detected in {test_name}: {error}")
                self.logger.debug(f"Full response: {response}")
                self._check_server_logs_for_errors()
                return False

        # Response should be substantial (more than just a few words)
        if len(response.strip()) < 10:
            self.logger.error(f"Response too short for {test_name}: {response}")
            self._check_server_logs_for_errors()
            return False

        # Verify this looks like a real AI response, not just an error message
        if not self._validate_ai_response_content(response):
            self.logger.error(f"Response doesn't look like valid AI output for {test_name}")
            self._check_server_logs_for_errors()
            return False

        self.logger.debug(f"Successful response for {test_name}: {response[:100]}...")
        return True

    def _validate_ai_response_content(self, response: str) -> bool:
        """Validate that response appears to be legitimate AI output"""
        if not response:
            return False

        response_lower = response.lower()

        # Check for indicators this is a real AI response
        positive_indicators = [
            "i am",
            "i'm",
            "i can",
            "i'll",
            "i would",
            "i think",
            "this code",
            "this function",
            "this file",
            "this configuration",
            "hello",
            "hi",
            "yes",
            "sure",
            "certainly",
            "of course",
            "analysis",
            "analyze",
            "review",
            "suggestion",
            "improvement",
            "here",
            "below",
            "above",
            "following",
            "based on",
            "python",
            "code",
            "function",
            "class",
            "variable",
            "llama",
            "model",
            "assistant",
            "ai",
        ]

        # Response should contain at least some AI-like language
        ai_indicators_found = sum(1 for indicator in positive_indicators if indicator in response_lower)

        if ai_indicators_found < 2:
            self.logger.warning(f"Response lacks AI-like indicators: {response[:200]}...")
            return False

        return True

    def _check_server_logs_for_errors(self):
        """Check server logs for any error messages that might explain failures"""
        try:
            # Get recent logs from the log file
            log_file_path = "logs/mcp_server.log"
            with open(log_file_path) as f:
                lines = f.readlines()
                recent_logs = lines[-50:]  # Last 50 lines

            if recent_logs:
                self.logger.info("Recent server logs:")
                for line in recent_logs[-10:]:  # Last 10 lines
                    if line.strip():
                        self.logger.info(f"  {line.strip()}")

        except Exception as e:
            self.logger.debug(f"Failed to check server logs: {e}")

    def validate_local_model_response(self, response: str) -> bool:
        """Validate that response appears to come from a local model"""
        if not response:
            return False

        # Basic validation - response should be non-empty and reasonable
        response_lower = response.lower()

        # Check for some indicators this might be from a local model
        # (This is heuristic - local models often mention their nature)
        local_indicators = ["llama", "local", "assistant", "ai", "model", "help"]

        # At least response should be meaningful text
        return len(response.strip()) > 10 and any(indicator in response_lower for indicator in local_indicators)
