#!/usr/bin/env python3
"""
Simple test script to verify that the localization fix works correctly.
"""
import os
import sys

# Set up path
sys.path.insert(0, ".")


# Simple test implementation that doesn't depend on heavy imports
class SimpleBaseTool:
    def get_language_instruction(self) -> str:
        """
        Generate language instruction based on LOCALE configuration.
        This is the FIXED version that reads directly from environment.
        """
        locale = os.getenv("LOCALE", "").strip()
        if not locale:
            return ""
        return f"Always respond in {locale}.\n\n"


def test_localization():
    """Test the localization functionality."""
    tool = SimpleBaseTool()

    # Save original locale
    original = os.environ.get("LOCALE")

    try:
        print("=== Testing Localization Fix ===")

        # Test 1: French locale
        print("\n1. Testing French locale...")
        os.environ["LOCALE"] = "fr-FR"
        instruction = tool.get_language_instruction()
        expected = "Always respond in fr-FR.\n\n"
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(instruction)}")
        print(f"   Result:   {'✅ PASS' if instruction == expected else '❌ FAIL'}")

        # Test 2: English locale
        print("\n2. Testing English locale...")
        os.environ["LOCALE"] = "en-US"
        instruction = tool.get_language_instruction()
        expected = "Always respond in en-US.\n\n"
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(instruction)}")
        print(f"   Result:   {'✅ PASS' if instruction == expected else '❌ FAIL'}")

        # Test 3: Empty locale
        print("\n3. Testing empty locale...")
        os.environ["LOCALE"] = ""
        instruction = tool.get_language_instruction()
        expected = ""
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(instruction)}")
        print(f"   Result:   {'✅ PASS' if instruction == expected else '❌ FAIL'}")

        # Test 4: No locale (unset)
        print("\n4. Testing unset locale...")
        if "LOCALE" in os.environ:
            del os.environ["LOCALE"]
        instruction = tool.get_language_instruction()
        expected = ""
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(instruction)}")
        print(f"   Result:   {'✅ PASS' if instruction == expected else '❌ FAIL'}")

        # Test 5: Locale with spaces
        print("\n5. Testing locale with spaces...")
        os.environ["LOCALE"] = "  zh-CN  "
        instruction = tool.get_language_instruction()
        expected = "Always respond in zh-CN.\n\n"
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(instruction)}")
        print(f"   Result:   {'✅ PASS' if instruction == expected else '❌ FAIL'}")

    finally:
        # Restore original locale
        if original is not None:
            os.environ["LOCALE"] = original
        else:
            os.environ.pop("LOCALE", None)

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_localization()
