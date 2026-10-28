#!/usr/bin/env python3
"""pal-diag — dump smart-router + learning state for troubleshooting.

Thin wrapper around providers.router.diag (shared with `pal diag`).

Usage:
    python scripts/pal-diag.py            # human-readable
    python scripts/pal-diag.py --json     # machine-readable
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    from providers.router import diag

    data = diag.collect()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        print(diag.render(data))


if __name__ == "__main__":
    main()
