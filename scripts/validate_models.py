#!/usr/bin/env python3
"""Validate conf/*.json model config files.

Checks performed:
- each JSON file parses
- contains a top-level `models` array
- each model has a `model_name` string
- collects aliases and ensures no duplicates across files
"""
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    conf_dir = repo_root / "conf"
    if not conf_dir.exists():
        print(f"conf directory not found at {conf_dir}")
        return 2

    json_files = sorted(conf_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found under conf/")
        return 1

    model_names = {}
    alias_map = {}
    ok = True

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: Failed to parse {jf}: {e}")
            ok = False
            continue

        models = data.get("models")
        if models is None:
            print(f"WARNING: {jf} has no top-level 'models' array")
            continue
        if not isinstance(models, list):
            print(f"ERROR: {jf} 'models' is not a list")
            ok = False
            continue

        for idx, m in enumerate(models):
            if not isinstance(m, dict):
                print(f"ERROR: {jf} models[{idx}] is not an object")
                ok = False
                continue
            name = m.get("model_name")
            if not name or not isinstance(name, str):
                print(f"ERROR: {jf} models[{idx}] missing or invalid 'model_name'")
                ok = False
                continue
            prev = model_names.get(name)
            if prev:
                print(f"ERROR: duplicate model_name '{name}' in {jf} and {prev}")
                ok = False
            else:
                model_names[name] = str(jf)

            aliases = m.get("aliases") or []
            if not isinstance(aliases, list):
                print(f"ERROR: {jf} models[{idx}] 'aliases' must be a list if present")
                ok = False
                continue
            for a in aliases:
                if not isinstance(a, str):
                    print(f"ERROR: {jf} models[{idx}] alias {a!r} is not a string")
                    ok = False
                    continue
                low = a.lower()
                if low in alias_map:
                    print(f"ERROR: duplicate alias '{a}' in {jf} and {alias_map[low]}")
                    ok = False
                else:
                    alias_map[low] = str(jf)

    print("\nSummary:")
    print(f"  JSON files checked: {len(json_files)}")
    print(f"  Unique model names: {len(model_names)}")
    print(f"  Unique aliases: {len(alias_map)}")

    if ok:
        print("All conf JSON files parsed and validated successfully.")
        return 0
    else:
        print("One or more problems detected. See errors above.")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
