from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "metrics" / "human-labels.ru.json"

PARSER_GAP_IDS = (
    "dependency_tree_depth",
    "avg_noun_phrase_length",
    "passive_impersonal_ratio",
    "figurative_candidate_ratio",
)


@lru_cache(maxsize=1)
def human_labels() -> dict[str, Any]:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def label_for(metric_id: str) -> dict[str, Any]:
    return human_labels()["metrics"].get(metric_id, {"title": metric_id, "plain_hint": "", "unit_human": ""})


def parser_gap_ids() -> tuple[str, ...]:
    return PARSER_GAP_IDS
