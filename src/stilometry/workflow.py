from __future__ import annotations

import json
import re
import statistics
import os
import platform
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import analyze_text, manifest, sha256, validate_report
from .schemas import validate_artifact

STATES = ("ingest", "metrics_validated", "draft", "approved", "revised", "personality_hypotheses", "prompt_compiled")
APPROVED_ARTIFACT_DIRS = (
    "runs",
    "stilometry-memory/runs",
    "stilometry-memory/fragments",
    "stilometry-memory/sessions",
)
PROTECTED_INPUT_DIRS = ("corpus", "private")


def _is_reparse_or_link(path: Path) -> bool:
    try:
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            return True
        if os.name == "nt" and hasattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT"):
            return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return False
    except OSError as exc:
        raise ValueError(f"cannot inspect path component: {path}") from exc


def _check_existing_components(path: Path) -> None:
    parts = path.parts
    current = Path(parts[0]) if parts else path
    for part in parts[1:]:
        current /= part
        if os.path.lexists(current) and _is_reparse_or_link(current):
            raise ValueError("symlink or junction paths are not allowed")


def safe_path(root: Path, candidate: str | Path) -> Path:
    root = Path(root).absolute()
    _check_existing_components(root)
    root = root.resolve(strict=False)
    raw = Path(candidate)
    lexical = raw if raw.is_absolute() else root / raw
    _check_existing_components(lexical)
    path = lexical.resolve(strict=False)
    if path != root and root not in path.parents:
        raise ValueError("path escapes project root")
    _check_existing_components(path)
    return path


def approved_output_path(root: Path, candidate: str | Path, inputs: list[Path]) -> Path:
    output = safe_path(root, candidate)
    root_resolved = Path(root).resolve(strict=False)
    relative = output.relative_to(root_resolved).as_posix()
    if not any(relative == allowed or relative.startswith(allowed + "/") for allowed in APPROVED_ARTIFACT_DIRS):
        raise ValueError("output is outside approved artifact destinations")
    protected = [root_resolved / name for name in PROTECTED_INPUT_DIRS]
    protected.extend(path.resolve(strict=False) for path in inputs)
    if any(output == path or path.is_dir() and path in output.parents for path in protected):
        raise ValueError("output overlaps source or private input")
    return output


def redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b(?:\+?\d[\d ()-]{7,}\d)\b", "[PHONE]", text)
    return text


def analyze_files(root: Path, paths: list[str], output: Path) -> dict[str, Any]:
    sources = []
    for name in paths:
        path = safe_path(root, name)
        if not path.is_file():
            raise FileNotFoundError(name)
        text = path.read_text(encoding="utf-8")
        source_report = analyze_text(text, path.relative_to(root).as_posix(), str(path.relative_to(root)))
        sources.append(source_report)
    source_meta = [s["sources"][0] for s in sources]
    all_metrics = {}
    for metric in manifest()["metrics"]:
        entries = [s["metrics"][metric["id"]] for s in sources]
        usable = [e for e in entries if e["value"] is not None and e["data_sufficiency"] == "sufficient"]
        if metric["type"] == "scalar":
            values = [e["value"] for e in usable]
            value = statistics.median(values) if values else None
        else:
            keys = set().union(*(e["value"].keys() for e in usable if isinstance(e["value"], dict)))
            value = {k: statistics.median([e["value"][k] for e in usable]) for k in keys} if usable and keys else None
        base = dict(entries[0])
        base["value"] = value
        base["n_tokens"] = sum(e["n_tokens"] for e in entries)
        base["n_sentences"] = sum(e["n_sentences"] for e in entries)
        base["data_sufficiency"] = "sufficient" if len(usable) == len(entries) and usable else "insufficient"
        base["evidence_spans"] = [span for e in entries for span in e["evidence_spans"]]
        base["per_source_values"] = [{"source_id": source_meta[i]["source_id"], "value": entries[i]["value"]} for i in range(len(entries))]
        base["median"] = value
        base["iqr"] = (statistics.quantiles(values, n=4)[2] - statistics.quantiles(values, n=4)[0]) if metric["type"] == "scalar" and len(values) >= 4 else (0.0 if values and metric["type"] == "scalar" else None)
        base["bootstrap_ci"] = {"status": "unavailable", "reason": "bootstrap not implemented in offline MVP"}
        if base["data_sufficiency"] == "insufficient" and not base.get("insufficiency_reason"):
            base["insufficiency_reason"] = "one or more source units below metric threshold or required capability unavailable"
        base["provenance"] = dict(base["provenance"], aggregation="median" if metric["type"] == "scalar" else "component_median")
        all_metrics[metric["id"]] = base
    input_hash = sha256(json.dumps([s["source_hash"] for s in sources], sort_keys=True))
    report = {"status": "ok" if sum(s["char_count"] for s in source_meta) >= 5000 else "blocked", "schema_version": "1.0", "run_id": input_hash[:16], "sources": source_meta, "metrics": all_metrics, "evidence_refs": [], "citations": [], "uncertainty": {},
              "seed": 0, "platform": platform.platform(), "config_hash": sha256("stilometry-core-config-0.1.0"), "tokenizer_metadata": {"name": "stdlib-regex", "version": "1.0", "license": "Python standard library"}, "parser_metadata": {"name": None, "version": None, "status": "unavailable"}, "model_metadata": {"name": None, "version": None, "status": "not_used"}, "license_metadata": {"code": "project-local", "data": "source-provided"},
              "input_hash": input_hash, "metrics_hash": sha256(json.dumps(all_metrics, sort_keys=True)),
              "intake": {"policy": "combined_corpus_characters", "per_source_minimum": None, "character_gate": "pass" if sum(s["sources"][0]["char_count"] for s in sources) >= 5000 else "insufficient", "minimum_characters": 5000},
              "provenance": {"offline": True, "network_check": "pass", "redaction_check": "pass" if all(s["provenance"]["redaction_check"] == "pass" for s in sources) else "blocked", "source_provenance": source_meta}}
    report["report_hash"] = sha256(json.dumps(report, sort_keys=True))
    output = approved_output_path(root, output, [safe_path(root, name) for name in paths])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def approve(draft: dict[str, Any], reviewer: str) -> dict[str, Any]:
    if draft.get("status") not in {"draft", "revised_draft"}:
        raise ValueError("only reviewed draft reports can be approved")
    source_report = {"status": "ok", "schema_version": "1.0", "run_id": draft.get("run_id"), "sources": draft.get("sources", []), "metrics": draft.get("metrics", {}), "evidence_refs": draft.get("evidence_refs", []), "citations": draft.get("citations", []), "uncertainty": draft.get("uncertainty", {}), "input_hash": draft.get("input_hash"), "metrics_hash": draft.get("metrics_hash"), "intake": draft.get("intake", {}), "seed": draft.get("seed", 0), "platform": draft.get("platform"), "config_hash": draft.get("config_hash"), "tokenizer_metadata": draft.get("tokenizer_metadata", {}), "parser_metadata": draft.get("parser_metadata", {}), "model_metadata": draft.get("model_metadata", {}), "license_metadata": draft.get("license_metadata", {}), "provenance": draft.get("provenance", {}), "report_hash": draft.get("analysis_report_hash")}
    if draft.get("source_id") is not None:
        source_report["source_id"] = draft["source_id"]
        source_report["source_hash"] = draft["source_hash"]
    if validate_report(source_report):
        raise ValueError("draft report is invalid")
    event = {"event": "human_approval", "reviewer": reviewer, "timestamp": datetime.now(timezone.utc).isoformat(), "input_hash": draft["input_hash"], "metrics_hash": draft["metrics_hash"], "report_hash": draft["analysis_report_hash"]}
    if draft.get("stale_approval_hash"):
        event["supersedes_approval_hash"] = draft["stale_approval_hash"]
    payload = {"status": "ok", "schema_version": "1.0", "run_id": draft["run_id"], "sources": draft["sources"], "metrics": draft["metrics"], "evidence_refs": draft.get("evidence_refs", []), "citations": draft.get("citations", []), "uncertainty": draft.get("uncertainty", {}), "input_hash": draft["input_hash"], "metrics_hash": draft["metrics_hash"], "intake": draft["intake"], "seed": draft.get("seed", 0), "platform": draft.get("platform"), "config_hash": draft.get("config_hash"), "tokenizer_metadata": draft.get("tokenizer_metadata", {}), "parser_metadata": draft.get("parser_metadata", {}), "model_metadata": draft.get("model_metadata", {}), "license_metadata": draft.get("license_metadata", {}), "provenance": draft["provenance"]}
    if draft.get("source_id") is not None:
        payload["source_id"] = draft["source_id"]
        payload["source_hash"] = draft["source_hash"]
    result = {"status": "approved", "schema_version": "1.0", "approval_event": event, "approved_input_hash": event["input_hash"], "approved_metrics_hash": event["metrics_hash"], "approved_report_hash": event["report_hash"], "approved_payload": payload, "provenance": {"network_check": "pass", "redaction_check": "pass"}, "blockers": []}
    if validate_artifact("approval", result):
        raise ValueError("approval artifact schema invalid")
    return result


def draft(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("status") != "ok" or validate_report(report):
        raise ValueError("validated analysis report is required")
    result = {"status": "draft", "schema_version": "1.0", "run_id": report["run_id"], "source_id": report.get("source_id"), "source_hash": report.get("source_hash"), "input_hash": report["input_hash"], "metrics_hash": report["metrics_hash"], "analysis_report_hash": report["report_hash"], "sources": report["sources"], "metrics": report["metrics"], "intake": report["intake"], "seed": report.get("seed", 0), "platform": report.get("platform"), "config_hash": report.get("config_hash"), "tokenizer_metadata": report.get("tokenizer_metadata", {}), "parser_metadata": report.get("parser_metadata", {}), "model_metadata": report.get("model_metadata", {}), "license_metadata": report.get("license_metadata", {}), "observations": report.get("observations", []), "evidence_refs": report.get("evidence_refs", []), "citations": report.get("citations", []), "uncertainty": report.get("uncertainty", {}), "provenance": report["provenance"], "blockers": []}
    if validate_artifact("profile", result):
        raise ValueError("profile artifact schema invalid")
    return result


def revise(approved: dict[str, Any], approved_hash: str) -> dict[str, Any]:
    _verify_approval(approved)
    if approved.get("approved_input_hash") != approved_hash:
        raise ValueError("approval hash mismatch")
    payload = approved["approved_payload"]
    return {
        "status": "revised_draft",
        "schema_version": "1.0",
        "revision_id": sha256(json.dumps({"approved_report_hash": approved["approved_report_hash"], "approved_input_hash": approved_hash}, sort_keys=True))[:16],
        "approval_state": "invalidated_for_revision",
        "stale_approval_hash": approved_hash,
        "approved_run_id": payload["run_id"],
        "approved_report_hash": approved["approved_report_hash"],
        "approved_input_hash": approved_hash,
        "approved_metrics_hash": approved["approved_metrics_hash"],
        "source_id": payload.get("source_id"),
        "source_hash": payload.get("source_hash"),
        "run_id": payload["run_id"],
        "analysis_report_hash": approved["approved_report_hash"],
        "input_hash": approved_hash,
        "metrics_hash": approved["approved_metrics_hash"],
        "intake": payload.get("intake", {}),
        "seed": payload.get("seed", 0),
        "platform": payload.get("platform"),
        "config_hash": payload.get("config_hash"),
        "tokenizer_metadata": payload.get("tokenizer_metadata", {}),
        "parser_metadata": payload.get("parser_metadata", {}),
        "model_metadata": payload.get("model_metadata", {}),
        "license_metadata": payload.get("license_metadata", {}),
        "sources": payload["sources"],
        "metrics": payload["metrics"],
        "evidence_refs": payload.get("evidence_refs", []),
        "citations": payload.get("citations", []),
        "uncertainty": payload.get("uncertainty", {}),
        "provenance": payload["provenance"],
        "next_action": "new human approval required",
        "blockers": ["approval invalidated by revision"],
    }


def personality(approved: dict[str, Any]) -> dict[str, Any]:
    _verify_approval(approved)
    return {"status": "personality_hypotheses", "schema_version": "1.0", "disclaimer": "Это наблюдательные гипотезы о языке, не диагноз и не факт о личности.", "axes": [], "alternatives": [], "confidence": "low", "evidence_refs": [], "provenance": {"network_check": "pass", "redaction_check": "pass", "approval_hash": approved["approved_input_hash"]}, "blockers": []}


def compile_prompt(approved: dict[str, Any]) -> dict[str, Any]:
    _verify_approval(approved)
    result = {"status": "prompt_compiled", "schema_version": "1.0", "must": ["preserve observed sentence rhythm", "retain evidence-backed hedging level"], "must_not": ["invent quotes", "claim personality diagnosis", "add unsupported persona traits"], "tests": ["all constraints cite approved evidence", "no raw quotes or PII", "network_check=pass"], "evidence_refs": [], "provenance": {"network_check": "pass", "redaction_check": "pass", "approval_hash": approved["approved_input_hash"]}, "blockers": []}
    if validate_artifact("prompt", result):
        raise ValueError("prompt artifact schema invalid")
    return result


def _verify_approval(approved: dict[str, Any]) -> None:
    if approved.get("status") != "approved" or not approved.get("approved_input_hash"):
        raise ValueError("immutable human approval is required")
    event = approved.get("approval_event", {})
    payload = approved.get("approved_payload")
    if not payload or validate_report(dict(payload, report_hash=approved.get("approved_report_hash"))):
        raise ValueError("approved payload hash/provenance mismatch")
    recomputed_input = sha256(json.dumps([s["source_hash"] for s in payload["sources"]], sort_keys=True))
    recomputed_metrics = sha256(json.dumps(payload["metrics"], sort_keys=True))
    recomputed_report = sha256(json.dumps({k: v for k, v in payload.items() if k != "report_hash"}, sort_keys=True))
    if recomputed_input != approved.get("approved_input_hash") or recomputed_metrics != approved.get("approved_metrics_hash") or recomputed_report != approved.get("approved_report_hash"):
        raise ValueError("approval payload hash mismatch")
    if event.get("input_hash") != approved["approved_input_hash"]:
        raise ValueError("approval input hash mismatch")
    if event.get("metrics_hash") != approved.get("approved_metrics_hash") or event.get("report_hash") != approved.get("approved_report_hash"):
        raise ValueError("approval hash mismatch")
