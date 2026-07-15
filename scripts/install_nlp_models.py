#!/usr/bin/env python3
"""Download Slovnet/Navec model packs into project model-cache/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stilometry.parser_stack import ensure_models, metadata, model_cache  # noqa: E402


def main() -> int:
    cache = model_cache(ROOT)
    paths = ensure_models(cache, download=True)
    report = {
        "status": "ok",
        "cache": cache.as_posix(),
        "models": {name: path.stat().st_size for name, path in paths.items()},
        "metadata": metadata(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
