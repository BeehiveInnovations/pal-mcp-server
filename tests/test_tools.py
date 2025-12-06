"""
Tests for individual tool implementations
"""

import json
import shutil
import tempfile

import pytest

from tools import AnalyzeTool, ChatTool, CodeReviewTool, ThinkDeepTool
from tools.shared.exceptions import ToolExecutionError


class TestThinkDeepTool:
    """Test the thinkdeep tool"""

    @pytest.fixture
    def tool(self):
        return ThinkDeepTool()

    def test_tool_metadata(self, tool):
        """Test tool metadata"""
        assert tool.get_name() == "thinkdeep"
        assert "investigation and reasoning" in tool.get_description()
        assert tool.get_default_temperature() == 1.0

        schema = tool.get_input_schema()
        # ThinkDeep is now a workflow tool with step-based fields
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]

        # Required fields for workflow
        expected_required = {"step", "step_number", "total_steps", "next_step_required", "findings"}
        assert expected_required.issubset(set(schema["required"]))

    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        """Test successful execution using real integration testing"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for real provider resolution
            os.environ["OPENAI_API_KEY"] = "sk-test-key-thinkdeep-success-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution
            try:
                result = await tool.execute(
                    {
                        "step": "Initial analysis",
                        "step_number": 1,
                        "total_steps": 1,
                        "next_step_required": False,
                        "findings": "Initial thinking about building a cache",
                        "problem_context": "Building a cache",
                        "focus_areas": ["performance", "scalability"],
                        "model": "o3-mini",
                    }
                )

                # If we get here, check the response format
                assert len(result) == 1
                # Should be a valid JSON response
                output = json.loads(result[0].text)
                assert "status" in output

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None


class TestCodeReviewTool:
    """Test the codereview tool"""

    @pytest.fixture
    def tool(self):
        return CodeReviewTool()

    def test_tool_metadata(self, tool):
        """Test tool metadata"""
        assert tool.get_name() == "codereview"
        assert "code review" in tool.get_description()
        assert tool.get_default_temperature() == 1.0

        schema = tool.get_input_schema()
        assert "relevant_files" in schema["properties"]
        assert "step" in schema["properties"]
        assert "step_number" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_with_review_type(self, tool, tmp_path):
        """Test execution with specific review type using real provider resolution"""
        import importlib
        import os

        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def insecure(): pass", encoding="utf-8")

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for testing
            os.environ["OPENAI_API_KEY"] = "sk-test-key-codereview-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution - expect it to fail at API level
            try:
                result = await tool.execute(
                    {
                        "step": "Review for security issues",
                        "step_number": 1,
                        "total_steps": 1,
                        "next_step_required": False,
                        "findings": "Initial security review",
                        "relevant_files": [str(test_file)],
                        "model": "o3-mini",
                    }
                )
                # If we somehow get here, that's fine too
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None


class TestAnalyzeTool:
    """Test the analyze tool"""

    @pytest.fixture
    def tool(self):
        return AnalyzeTool()

    def test_tool_metadata(self, tool):
        """Test tool metadata"""
        assert tool.get_name() == "analyze"
        assert "code analysis" in tool.get_description()
        assert tool.get_default_temperature() == 1.0

        schema = tool.get_input_schema()
        # New workflow tool requires step-based fields
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]
        # Workflow tools use relevant_files instead of files
        assert "relevant_files" in schema["properties"]

        # Required fields for workflow
        expected_required = {"step", "step_number", "total_steps", "next_step_required", "findings"}
        assert expected_required.issubset(set(schema["required"]))

    @pytest.mark.asyncio
    async def test_execute_with_analysis_type(self, tool, tmp_path):
        """Test execution with specific analysis type using real provider resolution"""
        import importlib
        import os

        # Create test file
        test_file = tmp_path / "module.py"
        test_file.write_text("class Service: pass", encoding="utf-8")

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for testing
            os.environ["OPENAI_API_KEY"] = "sk-test-key-analyze-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution - expect it to fail at API level
            try:
                result = await tool.execute(
                    {
                        "step": "Analyze the structure of this code",
                        "step_number": 1,
                        "total_steps": 1,
                        "next_step_required": False,
                        "findings": "Initial analysis of code structure",
                        "relevant_files": [str(test_file)],
                        "analysis_type": "architecture",
                        "output_format": "summary",
                        "model": "o3-mini",
                    }
                )
                # If we somehow get here, that's fine too
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None


class TestAbsolutePathValidation:
    """Test absolute path validation across all tools"""

    # Removed: test_analyze_tool_relative_path_rejected - workflow tool handles validation differently

    # NOTE: CodeReview tool test has been commented out because the codereview tool has been
    # refactored to use a workflow-based pattern. The workflow tools handle path validation
    # differently and may accept relative paths in step 1 since validation happens at the
    # file reading stage. See simulator_tests/test_codereview_validation.py for comprehensive
    # workflow testing of the new codereview tool.

    @pytest.mark.asyncio
    async def test_thinkdeep_tool_relative_path_rejected(self):
        """Test that thinkdeep tool rejects relative paths"""
        tool = ThinkDeepTool()
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(
                {
                    "step": "My analysis",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Initial analysis",
                    "files_checked": ["./local/file.py"],
                }
            )

        response = json.loads(exc_info.value.payload)
        assert response["status"] == "error"
        assert "must be FULL absolute paths" in response["content"]
        assert "./local/file.py" in response["content"]

    @pytest.mark.asyncio
    async def test_chat_tool_relative_path_rejected(self):
        """Test that chat tool rejects relative paths"""
        tool = ChatTool()
        temp_dir = tempfile.mkdtemp()
        try:
            with pytest.raises(ToolExecutionError) as exc_info:
                await tool.execute(
                    {
                        "prompt": "Explain this code",
                        "absolute_file_paths": ["code.py"],  # relative path without ./
                        "working_directory_absolute_path": temp_dir,
                    }
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        response = json.loads(exc_info.value.payload)
        assert response["status"] == "error"
        assert "must be FULL absolute paths" in response["content"]
        assert "code.py" in response["content"]

    @pytest.mark.asyncio
    async def test_analyze_tool_accepts_absolute_paths(self):
        """Test that analyze tool accepts absolute paths using real provider resolution"""
        import importlib
        import os

        tool = AnalyzeTool()

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for testing
            os.environ["OPENAI_API_KEY"] = "sk-test-key-absolute-path-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution - expect it to fail at API level
            try:
                result = await tool.execute(
                    {
                        "step": "Analyze this code file",
                        "step_number": 1,
                        "total_steps": 1,
                        "next_step_required": False,
                        "findings": "Initial code analysis",
                        "relevant_files": ["/absolute/path/file.py"],
                        "model": "o3-mini",
                    }
                )
                # If we somehow get here, that's fine too
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None


class TestSpecialStatusModels:
    """Test SPECIAL_STATUS_MODELS registry and structured response handling"""

    def test_trace_complete_status_in_registry(self):
        """Test that trace_complete status is properly registered"""
        from tools.models import SPECIAL_STATUS_MODELS, TraceComplete

        assert "trace_complete" in SPECIAL_STATUS_MODELS
        assert SPECIAL_STATUS_MODELS["trace_complete"] == TraceComplete

    def test_trace_complete_model_validation(self):
        """Test TraceComplete model validation"""
        from tools.models import TraceComplete

        # Test precision mode
        precision_data = {
            "status": "trace_complete",
            "trace_type": "precision",
            "entry_point": {
                "file": "/path/to/file.py",
                "class_or_struct": "MyClass",
                "method": "myMethod",
                "signature": "def myMethod(self, param1: str) -> bool",
                "parameters": {"param1": "test"},
            },
            "call_path": [
                {
                    "from": {"file": "/path/to/file.py", "class": "MyClass", "method": "myMethod", "line": 10},
                    "to": {"file": "/path/to/other.py", "class": "OtherClass", "method": "otherMethod", "line": 20},
                    "reason": "direct call",
                    "condition": None,
                    "ambiguous": False,
                }
            ],
        }

        model = TraceComplete(**precision_data)
        assert model.status == "trace_complete"
        assert model.trace_type == "precision"
        assert model.entry_point.file == "/path/to/file.py"
        assert len(model.call_path) == 1

        # Test dependencies mode
        dependencies_data = {
            "status": "trace_complete",
            "trace_type": "dependencies",
            "target": {
                "file": "/path/to/file.py",
                "class_or_struct": "MyClass",
                "method": "myMethod",
                "signature": "def myMethod(self, param1: str) -> bool",
            },
            "incoming_dependencies": [
                {
                    "from_file": "/path/to/caller.py",
                    "from_class": "CallerClass",
                    "from_method": "callerMethod",
                    "line": 15,
                    "type": "direct_call",
                }
            ],
            "outgoing_dependencies": [
                {
                    "to_file": "/path/to/dependency.py",
                    "to_class": "DepClass",
                    "to_method": "depMethod",
                    "line": 25,
                    "type": "method_call",
                }
            ],
        }

        model = TraceComplete(**dependencies_data)
        assert model.status == "trace_complete"
        assert model.trace_type == "dependencies"
        assert model.target.file == "/path/to/file.py"
        assert len(model.incoming_dependencies) == 1
        assert len(model.outgoing_dependencies) == 1
