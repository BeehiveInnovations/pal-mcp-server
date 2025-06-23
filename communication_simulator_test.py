"""
Communication Simulator Test for Zen MCP Server

This script provides comprehensive end-to-end testing of the Zen MCP server
by simulating real Claude CLI communications and validating conversation
continuity, file handling, deduplication features, and clarification scenarios.

Test Flow:
1. Setup standalone server environment
2. Load and run individual test modules
3. Validate system behavior through logs and memory
4. Cleanup and report results

Usage:
    python communication_simulator_test.py [--verbose] [--keep-logs] [--tests TEST_NAME...] [--individual TEST_NAME] [--setup]

    --tests: Run specific tests only (space-separated)
    --list-tests: List all available tests
    --individual: Run a single test individually
    --setup: Force setup standalone server environment using run-server.sh

Available tests:
    basic_conversation          - Basic conversation flow with chat tool
    content_validation          - Content validation and duplicate detection
    per_tool_deduplication      - File deduplication for individual tools
    cross_tool_continuation     - Cross-tool conversation continuation scenarios
    cross_tool_comprehensive    - Comprehensive cross-tool integration testing
    line_number_validation      - Line number handling validation across tools
    memory_validation           - Conversation memory validation
    model_thinking_config       - Model thinking configuration testing
    o3_model_selection          - O3 model selection and routing testing
    ollama_custom_url           - Ollama custom URL configuration testing
    openrouter_fallback         - OpenRouter fallback mechanism testing
    openrouter_models           - OpenRouter models availability testing
    token_allocation_validation - Token allocation and limits validation
    testgen_validation          - TestGen tool validation with specific test function
    refactor_validation         - Refactor tool validation with codesmells
    debug_validation            - Debug tool validation with actual bugs
    conversation_chain_validation - Conversation chain continuity validation

Quick Test Mode (for time-limited testing):
    Use --quick to run the essential 6 tests that provide maximum coverage:
    - cross_tool_continuation (cross-tool conversation memory)
    - basic_conversation (basic chat functionality)
    - content_validation (content validation and deduplication)
    - model_thinking_config (flash/flashlite model testing)
    - o3_model_selection (o3 model selection testing)
    - per_tool_deduplication (file deduplication for individual tools)

Examples:
    # Run all tests
    python communication_simulator_test.py

    # Run only basic conversation and content validation tests
    python communication_simulator_test.py --tests basic_conversation content_validation

    # Run a single test individually (with full standalone setup)
    python communication_simulator_test.py --individual content_validation

    # Run quick test mode (essential 6 tests for time-limited testing)
    python communication_simulator_test.py --quick

    # Force setup standalone server environment before running tests
    python communication_simulator_test.py --setup

    # List available tests
    python communication_simulator_test.py --list-tests
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile


class CommunicationSimulator:
    """Simulates real-world Claude CLI communication with MCP Gemini server"""

    def __init__(
        self,
        verbose: bool = False,
        keep_logs: bool = False,
        selected_tests: list[str] = None,
        setup: bool = False,
        quick_mode: bool = False,
    ):
        self.verbose = verbose
        self.keep_logs = keep_logs
        self.selected_tests = selected_tests or []
        self.setup = setup
        self.quick_mode = quick_mode
        self.temp_dir = None
        self.server_process = None
        self.python_path = self._get_python_path()

        # Configure logging first
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)

        # Import test registry
        from simulator_tests import TEST_REGISTRY

        self.test_registry = TEST_REGISTRY

        # Define quick mode tests (essential tests for time-limited testing)
        # Focus on tests that work with current tool configurations
        self.quick_mode_tests = [
            "cross_tool_continuation",  # Cross-tool conversation memory
            "basic_conversation",  # Basic chat functionality
            "content_validation",  # Content validation and deduplication
            "model_thinking_config",  # Flash/flashlite model testing
            "o3_model_selection",  # O3 model selection testing
            "per_tool_deduplication",  # File deduplication for individual tools
        ]

        # If quick mode is enabled, override selected_tests
        if self.quick_mode:
            self.selected_tests = self.quick_mode_tests
            self.logger.info(f"Quick mode enabled - running {len(self.quick_mode_tests)} essential tests")

        # Available test methods mapping
        self.available_tests = {
            name: self._create_test_runner(test_class) for name, test_class in self.test_registry.items()
        }

        # Test result tracking
        self.test_results = dict.fromkeys(self.test_registry.keys(), False)

    def _get_python_path(self) -> str:
        """Get the Python path for the virtual environment"""
        current_dir = os.getcwd()
        venv_python = os.path.join(current_dir, "venv", "bin", "python")

        if os.path.exists(venv_python):
            return venv_python

        # Try .zen_venv as fallback
        zen_venv_python = os.path.join(current_dir, ".zen_venv", "bin", "python")
        if os.path.exists(zen_venv_python):
            return zen_venv_python

        # Fallback to system python if venv doesn't exist
        self.logger.warning("Virtual environment not found, using system python")
        return "python"

    def _create_test_runner(self, test_class):
        """Create a test runner function for a test class"""

        def run_test():
            test_instance = test_class(verbose=self.verbose)
            result = test_instance.run_test()
            # Update results
            test_name = test_instance.test_name
            self.test_results[test_name] = result
            return result

        return run_test

    def setup_test_environment(self) -> bool:
        """Setup test environment"""
        try:
            self.logger.info("Setting up test environment...")

            # Create temporary directory for test files
            self.temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
            self.logger.debug(f"Created temp directory: {self.temp_dir}")

            # Only run run-server.sh if setup is requested
            if self.setup:
                if not self._run_server_script():
                    return False

            # Always verify server environment is available
            return self._verify_server_environment()

        except Exception as e:
            self.logger.error(f"Failed to setup test environment: {e}")
            return False

    def _run_server_script(self) -> bool:
        """Run the run-server.sh script"""
        try:
            self.logger.info("Running run-server.sh...")

            # Check if run-server.sh exists
            setup_script = "./run-server.sh"
            if not os.path.exists(setup_script):
                self.logger.error(f"run-server.sh not found at {setup_script}")
                return False

            # Make sure it's executable
            result = self._run_command(["chmod", "+x", setup_script], capture_output=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to make run-server.sh executable: {result.stderr}")
                return False

            # Run the setup script
            result = self._run_command([setup_script], capture_output=True)
            if result.returncode != 0:
                self.logger.error(f"run-server.sh failed: {result.stderr}")
                return False

            self.logger.info("run-server.sh completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to run run-server.sh: {e}")
            return False

    def _verify_server_environment(self) -> bool:
        """Verify that server environment is ready"""
        try:
            self.logger.info("Verifying standalone server environment...")

            # Check if server.py exists
            server_file = "server.py"
            if not os.path.exists(server_file):
                self.logger.error(f"Server file not found: {server_file}")
                self.logger.error("Please ensure you're in the correct directory and server.py exists")
                return False

            # Check if virtual environment is available
            if not os.path.exists(self.python_path):
                self.logger.error(f"Python executable not found: {self.python_path}")
                self.logger.error("Please run ./run-server.sh first to set up the environment")
                return False

            # Check if required dependencies are available
            try:
                result = self._run_command([self.python_path, "-c", "import json; print('OK')"], capture_output=True)
                if result.returncode != 0:
                    self.logger.error("Python environment validation failed")
                    return False
            except Exception as e:
                self.logger.error(f"Python environment check failed: {e}")
                return False

            self.logger.info("Standalone server environment is ready")
            return True

        except Exception as e:
            self.logger.error(f"Server environment verification failed: {e}")
            self.logger.error("Please ensure the server environment is set up correctly, or use --setup")
            return False

    def simulate_claude_cli_session(self) -> bool:
        """Simulate a complete Claude CLI session with conversation continuity"""
        try:
            self.logger.info("Starting Claude CLI simulation...")

            # If specific tests are selected, run only those
            if self.selected_tests:
                return self._run_selected_tests()

            # Otherwise run all tests in order
            test_sequence = list(self.test_registry.keys())

            for test_name in test_sequence:
                if not self._run_single_test(test_name):
                    return False

            self.logger.info("All tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Claude CLI simulation failed: {e}")
            return False

    def _run_selected_tests(self) -> bool:
        """Run only the selected tests"""
        try:
            self.logger.info(f"Running selected tests: {', '.join(self.selected_tests)}")

            for test_name in self.selected_tests:
                if not self._run_single_test(test_name):
                    return False

            self.logger.info("All selected tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Selected tests failed: {e}")
            return False

    def _run_single_test(self, test_name: str) -> bool:
        """Run a single test by name"""
        try:
            if test_name not in self.available_tests:
                self.logger.error(f"Unknown test: {test_name}")
                self.logger.info(f"Available tests: {', '.join(self.available_tests.keys())}")
                return False

            self.logger.info(f"Running test: {test_name}")
            test_function = self.available_tests[test_name]
            result = test_function()

            if result:
                self.logger.info(f"Test {test_name} passed")
            else:
                self.logger.error(f"Test {test_name} failed")

            return result

        except Exception as e:
            self.logger.error(f"Test {test_name} failed with exception: {e}")
            return False

    def run_individual_test(self, test_name: str) -> bool:
        """Run a single test individually"""
        try:
            if test_name not in self.available_tests:
                self.logger.error(f"Unknown test: {test_name}")
                self.logger.info(f"Available tests: {', '.join(self.available_tests.keys())}")
                return False

            self.logger.info(f"Running individual test: {test_name}")

            # Setup environment
            if not self.setup_test_environment():
                self.logger.error("Environment setup failed")
                return False

            # Run the single test
            test_function = self.available_tests[test_name]
            result = test_function()

            if result:
                self.logger.info(f"Individual test {test_name} passed")
            else:
                self.logger.error(f"Individual test {test_name} failed")

            return result

        except Exception as e:
            self.logger.error(f"Individual test {test_name} failed with exception: {e}")
            return False
        finally:
            if not self.keep_logs:
                self.cleanup()

    def get_available_tests(self) -> dict[str, str]:
        """Get available tests with descriptions"""
        descriptions = {}
        for name, test_class in self.test_registry.items():
            # Create temporary instance to get description
            temp_instance = test_class(verbose=False)
            descriptions[name] = temp_instance.test_description
        return descriptions

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("ZEN MCP COMMUNICATION SIMULATOR - TEST RESULTS SUMMARY")
        self.logger.info("=" * 70)

        passed_count = sum(1 for result in self.test_results.values() if result)
        total_count = len(self.test_results)

        for test_name, result in self.test_results.items():
            status = "PASS" if result else "FAIL"
            # Get test description
            temp_instance = self.test_registry[test_name](verbose=False)
            description = temp_instance.test_description
            if result:
                self.logger.info(f"{description}: {status}")
            else:
                self.logger.error(f"{description}: {status}")

        if passed_count == total_count:
            self.logger.info("\nOVERALL RESULT: SUCCESS")
        else:
            self.logger.error("\nOVERALL RESULT: FAILURE")
        self.logger.info(f"{passed_count}/{total_count} tests passed")
        self.logger.info("=" * 70)
        return passed_count == total_count

    def run_full_test_suite(self) -> bool:
        """Run the complete test suite"""
        try:
            self.logger.info("Starting Zen MCP Communication Simulator Test Suite")

            # Setup
            if not self.setup_test_environment():
                self.logger.error("Environment setup failed")
                return False

            # Main simulation
            if not self.simulate_claude_cli_session():
                self.logger.error("Claude CLI simulation failed")
                return False

            # Print comprehensive summary
            overall_success = self.print_test_summary()

            return overall_success

        except Exception as e:
            self.logger.error(f"Test suite failed: {e}")
            return False
        finally:
            if not self.keep_logs:
                self.cleanup()

    def cleanup(self):
        """Cleanup test environment"""
        try:
            self.logger.info("Cleaning up test environment...")

            # Stop any running server processes
            if self.server_process and self.server_process.poll() is None:
                self.logger.info("Stopping server process...")
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
                    self.server_process.wait()

            if not self.keep_logs:
                self.logger.info("Test completed. Standalone server process stopped.")
            else:
                self.logger.info("Keeping logs for inspection")

            # Remove temp directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.logger.debug(f"Removed temp directory: {self.temp_dir}")

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

    def _run_command(self, cmd: list[str], check: bool = True, capture_output: bool = False, **kwargs):
        """Run a shell command with logging"""
        if self.verbose:
            self.logger.debug(f"Running: {' '.join(cmd)}")

        return subprocess.run(cmd, check=check, capture_output=capture_output, **kwargs)


def parse_arguments():
    """Parse and validate command line arguments"""
    parser = argparse.ArgumentParser(description="Zen MCP Communication Simulator Test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--keep-logs", action="store_true", help="Keep logs for inspection after test completion")
    parser.add_argument("--tests", "-t", nargs="+", help="Specific tests to run (space-separated)")
    parser.add_argument("--list-tests", action="store_true", help="List available tests and exit")
    parser.add_argument("--individual", "-i", help="Run a single test individually")
    parser.add_argument(
        "--quick", "-q", action="store_true", help="Run quick test mode (6 essential tests for time-limited testing)"
    )
    parser.add_argument(
        "--setup", action="store_true", help="Force setup standalone server environment using run-server.sh"
    )

    return parser.parse_args()


def list_available_tests():
    """List all available tests and exit"""
    simulator = CommunicationSimulator()
    # Create a simple logger for this function
    logger = logging.getLogger("list_tests")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    logger.info("Available tests:")
    for test_name, description in simulator.get_available_tests().items():
        logger.info(f"  {test_name:<25} - {description}")


def run_individual_test(simulator, test_name):
    """Run a single test individually"""
    logger = simulator.logger
    try:
        success = simulator.run_individual_test(test_name)

        if success:
            logger.info(f"\nINDIVIDUAL TEST {test_name.upper()}: PASSED")
            return 0
        else:
            logger.error(f"\nINDIVIDUAL TEST {test_name.upper()}: FAILED")
            return 1

    except KeyboardInterrupt:
        logger.warning(f"\nIndividual test {test_name} interrupted by user")
        simulator.cleanup()
        return 130
    except Exception as e:
        logger.error(f"\nIndividual test {test_name} failed with error: {e}")
        simulator.cleanup()
        return 1


def run_test_suite(simulator):
    """Run the full test suite or selected tests"""
    logger = simulator.logger
    try:
        success = simulator.run_full_test_suite()

        if success:
            logger.info("\nCOMPREHENSIVE MCP COMMUNICATION TEST: PASSED")
            return 0
        else:
            logger.error("\nCOMPREHENSIVE MCP COMMUNICATION TEST: FAILED")
            logger.error("Check detailed results above")
            return 1

    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user")
        simulator.cleanup()
        return 130
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}")
        simulator.cleanup()
        return 1


def main():
    """Main entry point"""
    args = parse_arguments()

    # Handle list tests request
    if args.list_tests:
        list_available_tests()
        return

    # Initialize simulator consistently for all use cases
    simulator = CommunicationSimulator(
        verbose=args.verbose,
        keep_logs=args.keep_logs,
        selected_tests=args.tests,
        setup=args.setup,
        quick_mode=args.quick,
    )

    # Determine execution mode and run
    if args.individual:
        exit_code = run_individual_test(simulator, args.individual)
    else:
        exit_code = run_test_suite(simulator)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
