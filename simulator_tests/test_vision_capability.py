#!/usr/bin/env python3
"""
Vision Capability Test

Tests vision capability with the chat tool using O3 model:
- Test file path image (PNG triangle)
- Test base64 data URL image
- Use chat tool with O3 model to analyze the images
- Verify the model correctly identifies shapes
"""

import base64
import os

from .base_test import BaseSimulatorTest


class VisionCapabilityTest(BaseSimulatorTest):
    """Test vision capability with chat tool and O3 model"""

    @property
    def test_name(self) -> str:
        return "vision_capability"

    @property
    def test_description(self) -> str:
        return "Vision capability test with chat tool and O3 model"

    def get_triangle_png_path(self) -> str:
        """Get the path to the triangle.png file in tests directory"""
        # Get the project root and find the triangle.png in tests/
        current_dir = os.getcwd()
        triangle_path = os.path.join(current_dir, "tests", "triangle.png")

        if not os.path.exists(triangle_path):
            raise FileNotFoundError(f"triangle.png not found at {triangle_path}")

        abs_path = os.path.abspath(triangle_path)
        self.logger.debug(f"Using triangle PNG at host path: {abs_path}")
        return abs_path

    def create_base64_triangle_data_url(self) -> str:
        """Create a base64 data URL from the triangle.png file"""
        triangle_path = self.get_triangle_png_path()

        with open(triangle_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        data_url = f"data:image/png;base64,{image_data}"
        self.logger.debug(f"Created base64 data URL with {len(image_data)} characters")
        return data_url

    def run_test(self) -> bool:
        """Test vision capability with O3 model"""
        try:
            self.logger.info("Test: Vision capability with O3 model")

            # Test 1: File path image
            self.logger.info("  1.1: Testing file path image (PNG triangle)")
            triangle_path = self.get_triangle_png_path()
            self.logger.info(f"  ✅ Using triangle PNG at: {triangle_path}")

            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What shape do you see in this image? Please be specific and only mention the shape name.",
                    "images": [triangle_path],
                    "model": "o3",
                },
            )

            if not response1:
                self.logger.error("Failed to get response from O3 model for file path test")
                return False

            # Check for error indicators first
            response1_lower = response1.lower()
            if any(
                error_phrase in response1_lower
                for error_phrase in [
                    "don't have access",
                    "cannot see",
                    "no image",
                    "files_required_to_continue",
                    "image you're referring to",
                    "supply the image",
                    "error",
                ]
            ):
                self.logger.error(f"  ❌ O3 model cannot access file path image. Response: {response1[:300]}...")
                return False

            if "triangle" not in response1_lower:
                self.logger.error(
                    f"  ❌ O3 did not identify triangle in file path test. Response: {response1[:200]}..."
                )
                return False

            self.logger.info("  ✅ O3 correctly identified file path image as triangle")

            # Test 2: Base64 data URL image
            self.logger.info("  1.2: Testing base64 data URL image")
            data_url = self.create_base64_triangle_data_url()

            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What shape do you see in this image? Please be specific and only mention the shape name.",
                    "images": [data_url],
                    "model": "o3",
                },
            )

            if not response2:
                self.logger.error("Failed to get response from O3 model for base64 test")
                return False

            response2_lower = response2.lower()
            if any(
                error_phrase in response2_lower
                for error_phrase in [
                    "don't have access",
                    "cannot see",
                    "no image",
                    "files_required_to_continue",
                    "image you're referring to",
                    "supply the image",
                    "error",
                ]
            ):
                self.logger.error(f"  ❌ O3 model cannot access base64 image. Response: {response2[:300]}...")
                return False

            if "triangle" not in response2_lower:
                self.logger.error(f"  ❌ O3 did not identify triangle in base64 test. Response: {response2[:200]}...")
                return False

            self.logger.info("  ✅ O3 correctly identified base64 image as triangle")

            # Optional: Test continuation with same image
            if continuation_id:
                self.logger.info("  1.3: Testing continuation with same image")
                response3, _ = self.call_mcp_tool(
                    "chat",
                    {
                        "prompt": "What color is this triangle?",
                        "images": [triangle_path],  # Same image should be deduplicated
                        "continuation_id": continuation_id,
                        "model": "o3",
                    },
                )

                if response3:
                    self.logger.info("  ✅ Continuation also working correctly")
                else:
                    self.logger.warning("  ⚠️  Continuation response not received")

            self.logger.info("  ✅ Vision capability test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Vision capability test failed: {e}")
            return False
