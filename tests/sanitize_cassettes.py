#!/usr/bin/env python3
"""
Script to sanitize existing cassettes by applying PII sanitization.

This script will:
1. Load existing cassettes
2. Apply PII sanitization to all interactions
3. Create backups of originals
4. Save sanitized versions
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add tests directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from pii_sanitizer import PIISanitizer


def sanitize_cassette(cassette_path: Path, backup: bool = True) -> bool:
    """Sanitize a single cassette file."""
    print(f"\n🔍 Processing: {cassette_path}")

    if not cassette_path.exists():
        print(f"❌ File not found: {cassette_path}")
        return False

    try:
        # Load cassette
        with open(cassette_path) as f:
            cassette_data = json.load(f)

        # Create backup if requested
        if backup:
            backup_path = cassette_path.with_suffix(f'.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json')
            shutil.copy2(cassette_path, backup_path)
            print(f"📦 Backup created: {backup_path}")

        # Initialize sanitizer
        sanitizer = PIISanitizer()

        # Sanitize interactions
        if "interactions" in cassette_data:
            sanitized_interactions = []

            for interaction in cassette_data["interactions"]:
                sanitized_interaction = {}

                # Sanitize request
                if "request" in interaction:
                    sanitized_interaction["request"] = sanitizer.sanitize_request(interaction["request"])

                # Sanitize response
                if "response" in interaction:
                    sanitized_interaction["response"] = sanitizer.sanitize_response(interaction["response"])

                sanitized_interactions.append(sanitized_interaction)

            cassette_data["interactions"] = sanitized_interactions

        # Save sanitized cassette
        with open(cassette_path, "w") as f:
            json.dump(cassette_data, f, indent=2, sort_keys=True)

        print(f"✅ Sanitized: {cassette_path}")
        return True

    except Exception as e:
        print(f"❌ Error processing {cassette_path}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Sanitize all cassettes in the openai_cassettes directory."""
    cassettes_dir = Path(__file__).parent / "openai_cassettes"

    if not cassettes_dir.exists():
        print(f"❌ Directory not found: {cassettes_dir}")
        sys.exit(1)

    # Find all JSON cassettes
    cassette_files = list(cassettes_dir.glob("*.json"))

    if not cassette_files:
        print(f"❌ No cassette files found in {cassettes_dir}")
        sys.exit(1)

    print(f"🎬 Found {len(cassette_files)} cassette(s) to sanitize")

    # Process each cassette
    success_count = 0
    for cassette_path in cassette_files:
        if sanitize_cassette(cassette_path):
            success_count += 1

    print(f"\n✨ Sanitization complete: {success_count}/{len(cassette_files)} cassettes processed successfully")

    if success_count < len(cassette_files):
        sys.exit(1)


if __name__ == "__main__":
    main()
