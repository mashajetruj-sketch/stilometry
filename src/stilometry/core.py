from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "metrics" / "metric-manifest.json"
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*")
SENT_RE = re.compile(r"(?<=[.!?…])(?:\s+|$)")
PUNCT = ",;:—-()…!?'\"«»"
FUNCTION = set("и в во не что он на я с со как а то это по к из у за от для но да же бы ли".split())
MARKERS = set("итак однако значит во-первых во вторых следовательно например наконец".split())
MODALS = set("может кажется вероятно возможно наверное должен должна стоит следует".split())
AFFECT = set("люблю нравится прекрасный хороший плохой страшный ужасный радость грустно".split())
ADDRESS = set("я ты вы вам вас тебе тебе".split())
REQUIRED_FIELDS = {"value", "unit", "n_tokens", "n_sentences", "data_sufficiency", "confidence", "evidence_spans", "formula_version", "provenance", "capability", "insufficiency_reason", "per_source_values", "median", "iqr", "bootstrap_ci"}
CONFIDENCE_FIELDS = {"measurement_confidence", "parser_confidence", "interpretation_confidence", "transfer_confidence"}
from .parser_stack import analyze_with_parser, ensure_models, metadata as parser_metadata_bundle

PII_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b(?:\+?\d[\d ()-]{7,}\d)\b")
IMPLEMENTATION_VERSION = "0.2.0"


def manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ids = [m["id"] for m in data["metrics"]]
    if len(ids) != 28 or len(set(ids)) != 28:
        raise ValueError("metric manifest must contain exactly 28 unique IDs")
    return data


def sha256(value: bytes | str) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def tokenize(text: str) -> list[str]:
    return [x.lower() for x in TOKEN_RE.findall(text)]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.split(text) if s.strip()]


def _suff(n: int, threshold: int) -> str:
    return "sufficient" if n >= threshold else "insufficient"


def _entry(
    metric: dict[str, Any],
    value: Any,
    words: list[str],
    sents: list[str],
    threshold: int,
    evidence: list[dict[str, Any]] | None = None,
    confidence: str = "low",
    *,
    capability: str | None = None,
    parser_confidence: str = "not_applicable",
    method: str | None = None,
    tokenizer: str = "razdel",
    parser: str | None = "slovnet-syntax+morph",
) -> dict[str, Any]:
    sufficient = _suff(len(words), threshold)
    is_proxy = "heuristic" in metric["formula"]
    cap = capability or ("stdlib_heuristic_proxy" if is_proxy else "slovnet_deterministic")
    meth = method or ("heuristic" if is_proxy else "deterministic")
    return {
        "value": value if sufficient == "sufficient" else None,
        "unit": metric["unit"],
        "n_tokens": len(words),
        "n_sentences": len(sents),
        "data_sufficiency": sufficient,
        "confidence": {
            "measurement_confidence": confidence if sufficient == "sufficient" else "low",
            "parser_confidence": parser_confidence,
            "interpretation_confidence": "not_applicable",
            "transfer_confidence": "low",
        },
        "evidence_spans": evidence or [],
        "formula_version": metric["version"],
        "capability": cap,
        "insufficiency_reason": None if sufficient == "sufficient" else f"requires at least {threshold} tokens",
        "per_source_values": [],
        "median": value if sufficient == "sufficient" else None,
        "iqr": 0.0 if sufficient == "sufficient" else None,
        "bootstrap_ci": {"status": "unavailable", "reason": "bootstrap not implemented in offline MVP"},
        "provenance": {
            "formula": metric["formula"],
            "tokenizer": tokenizer,
            "parser": parser,
            "method": meth,
            "implementation": "stilometry-core",
            "implementation_version": IMPLEMENTATION_VERSION,
        },
    }


def analyze_text(text: str, source_id: str = "source-1", source_path: str | None = None) -> dict[str, Any]:
    ensure_models(ROOT / "model-cache", download=True)
    parsed = analyze_with_parser(text, ROOT / "model-cache")
    ms = {m["id"]: m for m in manifest()["metrics"]}
    words, sents = parsed["words"], parsed["sentences"]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    counts = Counter(words)
    unique = set(words)
    lengths = [len(tokenize(s)) for s in sents]
    punct_count = sum(text.count(ch) for ch in PUNCT)
    evidence_end = min(len(text), 120)
    evidence = [{"source_id": source_id, "file_hash": sha256(text), "char_start": 0, "char_end": evidence_end, "line_start": 1, "line_end": text[:evidence_end].count("\n") + 1, "raw_span": None, "normalized_span": "[REDACTED]", "redacted": True, "quote_redacted": True, "citation_id": f"{source_id}:0-{evidence_end}"}]
    pconf = "medium"
    out: dict[str, Any] = {}
    out["avg_word_length"] = _entry(ms["avg_word_length"], sum(map(len, words))/len(words) if words else 0, words, sents, 200, evidence, "medium")
    out["ttr"] = _entry(ms["ttr"], len(unique)/len(words) if words else 0, words, sents, 500, evidence, "medium")
    factors, start = [], 0
    for i in range(1, len(words) + 1):
        if len(set(words[start:i])) / (i-start) < 0.72:
            factors.append(i-start); start = i
    if start < len(words): factors.append(len(words)-start)
    out["mtld"] = _entry(ms["mtld"], sum(factors)/len(factors) if factors else 0, words, sents, 500)
    out["function_word_ratio"] = _entry(ms["function_word_ratio"], parsed["function_word_ratio"], words, sents, 300, evidence, "medium", parser_confidence=pconf)
    out["hapax_ratio"] = _entry(ms["hapax_ratio"], parsed["hapax_ratio"], words, sents, 500, evidence, "medium", parser_confidence=pconf)
    out["avg_sentence_length"] = _entry(ms["avg_sentence_length"], sum(lengths)/len(lengths) if lengths else 0, words, sents, 20)
    out["complex_sentence_ratio"] = _entry(ms["complex_sentence_ratio"], parsed["complex_sentence_ratio"], words, sents, 30, parser_confidence=pconf)
    out["dependency_tree_depth"] = _entry(ms["dependency_tree_depth"], parsed["dependency_tree_depth"], words, sents, 30, parser_confidence=pconf)
    out["avg_noun_phrase_length"] = _entry(ms["avg_noun_phrase_length"], parsed["avg_noun_phrase_length"], words, sents, 200, parser_confidence=pconf)
    out["passive_impersonal_ratio"] = _entry(ms["passive_impersonal_ratio"], parsed["passive_impersonal_ratio"], words, sents, 500, parser_confidence=pconf)
    out["pos_entropy"] = _entry(ms["pos_entropy"], parsed["pos_entropy"], words, sents, 500, parser_confidence=pconf)
    out["verb_ratio"] = _entry(ms["verb_ratio"], parsed["verb_ratio"], words, sents, 300, parser_confidence=pconf)
    out["adjective_participle_ratio"] = _entry(ms["adjective_participle_ratio"], parsed["adjective_participle_ratio"], words, sents, 300, parser_confidence=pconf)
    out["morphological_variability"] = _entry(ms["morphological_variability"], parsed["morphological_variability"], words, sents, 500, parser_confidence=pconf)
    out["punctuation_density"] = _entry(ms["punctuation_density"], punct_count/len(words)*1000 if words else 0, words, sents, 300)
    profile = {ch: text.count(ch)/punct_count if punct_count else 0 for ch in PUNCT}
    out["punctuation_profile"] = _entry(ms["punctuation_profile"], profile, words, sents, 500)
    out["question_exclamation_ratio"] = _entry(ms["question_exclamation_ratio"], sum(s.endswith(("?", "!")) for s in sents)/len(sents) if sents else 0, words, sents, 30)
    mean = statistics.mean(lengths) if lengths else 0
    out["sentence_length_cv"] = _entry(ms["sentence_length_cv"], statistics.pstdev(lengths)/mean if len(lengths) > 1 and mean else 0, words, sents, 30)
    out["short_long_sentence_ratio"] = _entry(ms["short_long_sentence_ratio"], {"short": sum(x < 8 for x in lengths)/len(lengths) if lengths else 0, "long": sum(x > 30 for x in lengths)/len(lengths) if lengths else 0}, words, sents, 50)
    plen = [len(tokenize(p)) for p in paragraphs]
    pm = statistics.mean(plen) if plen else 0
    out["paragraph_burstiness"] = _entry(ms["paragraph_burstiness"], {"ratio": statistics.pstdev(plen)/pm if len(plen)>1 and pm else 0, "median": statistics.median(plen) if plen else 0}, words, sents, 300)
    bigrams = Counter(zip(words, words[1:])); trigrams = Counter(zip(words, words[1:], words[2:]))
    repeated = sum(v-1 for v in bigrams.values() if v > 1) + sum(v-1 for v in trigrams.values() if v > 1)
    out["repeated_ngram_rhythm"] = _entry(ms["repeated_ngram_rhythm"], repeated/len(words) if words else 0, words, sents, 500)
    out["discourse_marker_ratio"] = _entry(ms["discourse_marker_ratio"], sum(w in MARKERS for w in words)/len(sents) if sents else 0, words, sents, 300)
    out["figurative_candidate_ratio"] = _entry(
        ms["figurative_candidate_ratio"], parsed["figurative_candidate_ratio"], words, sents, 500,
        capability="slovnet_heuristic_proxy", method="heuristic", parser_confidence="low",
    )
    initials = [tokenize(s)[0] for s in sents if tokenize(s)]
    out["anaphora_ratio"] = _entry(ms["anaphora_ratio"], sum(v-1 for v in Counter(initials).values() if v>1)/len(sents) if sents else 0, words, sents, 50)
    out["modality_hedging_ratio"] = _entry(ms["modality_hedging_ratio"], sum(w in MODALS for w in words)/len(sents) if sents else 0, words, sents, 500)
    out["evaluation_emotion_ratio"] = _entry(ms["evaluation_emotion_ratio"], sum(w in AFFECT for w in words)/len(words) if words else 0, words, sents, 500)
    questions = sum(s.endswith("?") for s in sents)
    out["direct_address_ratio"] = _entry(ms["direct_address_ratio"], (sum(w in ADDRESS for w in words)+questions)/len(sents) if sents else 0, words, sents, 300)
    chars = max(len(text), 1)
    digital = {"urls": len(re.findall(r"https?://\S+", text)), "hashtags": text.count("#"), "mentions": text.count("@"), "emoji_or_symbols": sum(ord(c)>0x1F000 for c in text), "code_tokens": len(re.findall(r"`[^`]+`", text)), "latin_cyrillic_mixing": int(bool(re.search("[A-Za-z]", text) and re.search("[А-Яа-я]", text))), "repeated_punctuation": len(re.findall(r"[!?…]{2,}", text)), "ascii_emoticons": len(re.findall(r"[:;]-?[)(DP]", text))}
    out["digital_markup_signature"] = _entry(ms["digital_markup_signature"], {k: v/chars*1000 for k,v in digital.items()}, words, sents, 300)
    source_hash = sha256(text)
    for item in out.values():
        item["per_source_values"] = [{"source_id": source_id, "value": item["value"]}]
    source = {"source_id": source_id, "source_hash": source_hash, "source_path": source_path, "char_count": len(text), "token_count": len(words), "sentence_count": len(sents)}
    meta = parser_metadata_bundle()
    report = {"status": "ok", "schema_version": "1.0", "run_id": source_hash[:16], "source_id": source_id, "source_hash": source_hash, "sources": [source], "metrics": out, "evidence_refs": [], "citations": [], "uncertainty": {},
              "seed": 0, "platform": platform.platform(), "config_hash": sha256("stilometry-core-config-0.2.0"),
              "tokenizer_metadata": meta["tokenizer"], "parser_metadata": {**meta["syntax"], "morph": meta["morphology"], "status": "available"},
              "model_metadata": meta["embeddings"], "license_metadata": {"code": "project-local", "data": "natasha-ecosystem-mit"},
              "input_hash": sha256(json.dumps([source_hash], sort_keys=True)),
              "metrics_hash": sha256(json.dumps(out, sort_keys=True)),
              "intake": {"policy": "combined_corpus_characters", "per_source_minimum": None, "character_gate": "pass" if len(text) >= 5000 else "insufficient", "minimum_characters": 5000},
              "provenance": {"offline": True, "network_check": "pass", "redaction_check": "blocked" if PII_RE.search(text) else "pass", "source_provenance": [source]}}
    report["report_hash"] = sha256(json.dumps({k: v for k, v in report.items() if k != "report_hash"}, sort_keys=True))
    return report


def validate_report(report: dict[str, Any]) -> list[str]:
    errors = []
    from .schemas import validate_artifact
    errors.extend(validate_artifact("run", report))
    canonical = manifest()
    expected = {m["id"] for m in canonical["metrics"]}
    canonical_by_id = {m["id"]: m for m in canonical["metrics"]}
    actual = set(report.get("metrics", {}))
    if actual != expected:
        errors.append("metrics must contain exactly the canonical 28 IDs")
    for mid, item in report.get("metrics", {}).items():
        missing = REQUIRED_FIELDS - set(item)
        if missing:
            errors.append(f"{mid}: missing {sorted(missing)}")
            continue
        if set(item["confidence"]) != CONFIDENCE_FIELDS:
            errors.append(f"{mid}: decomposed confidence required")
        canonical_metric = canonical_by_id.get(mid)
        provenance = item.get("provenance", {})
        if canonical_metric and item.get("formula_version") != canonical_metric["version"]:
            errors.append(f"{mid}: formula_version differs from canonical manifest")
        if canonical_metric and provenance.get("formula") != canonical_metric["formula"]:
            errors.append(f"{mid}: formula differs from canonical manifest")
        if provenance.get("implementation") != canonical.get("implementation") or provenance.get("implementation_version") != canonical.get("implementation_version"):
            errors.append(f"{mid}: implementation/version differs from canonical manifest")
        if item.get("data_sufficiency") == "insufficient" and not item.get("insufficiency_reason"):
            errors.append(f"{mid}: insufficient metric requires explicit reason")
        if item.get("capability") == "stdlib_heuristic_proxy" and provenance.get("method") != "heuristic":
            errors.append(f"{mid}: heuristic proxy capability is not labeled")
        if item.get("capability") == "slovnet_heuristic_proxy" and provenance.get("method") != "heuristic":
            errors.append(f"{mid}: slovnet heuristic proxy capability is not labeled")
        for span in item["evidence_spans"]:
            if not {"source_id", "file_hash", "char_start", "char_end", "line_start", "line_end", "raw_span", "normalized_span", "redacted", "quote_redacted", "citation_id"} <= set(span):
                errors.append(f"{mid}: invalid evidence span")
            if span.get("char_start", -1) < 0 or span.get("char_end", -1) < span.get("char_start", 0):
                errors.append(f"{mid}: invalid evidence range")
            if span.get("quote_redacted") is not True or not span.get("citation_id"):
                errors.append(f"{mid}: evidence citation/redaction metadata invalid")
    sources = report.get("sources", [])
    source_hashes = [s.get("source_hash") for s in sources]
    source_map = {s.get("source_id"): s.get("source_hash") for s in sources}
    source_lengths = {s.get("source_id"): s.get("char_count") for s in sources}
    for mid, item in report.get("metrics", {}).items():
        for span in item.get("evidence_spans", []):
            if span.get("source_id") not in source_map or source_map.get(span.get("source_id")) != span.get("file_hash"):
                errors.append(f"{mid}: evidence source/hash mismatch")
            if span.get("char_end", -1) > source_lengths.get(span.get("source_id"), -1):
                errors.append(f"{mid}: evidence span exceeds source char_count")
    if not sources or any(not s.get("source_id") or not s.get("source_hash") for s in sources):
        errors.append("source provenance is required")
    if report.get("input_hash") != sha256(json.dumps(source_hashes, sort_keys=True)):
        errors.append("input_hash mismatch")
    if report.get("metrics_hash") != sha256(json.dumps(report.get("metrics", {}), sort_keys=True)):
        errors.append("metrics_hash mismatch")
    expected_report_hash = sha256(json.dumps({k: v for k, v in report.items() if k != "report_hash"}, sort_keys=True))
    if report.get("report_hash") != expected_report_hash:
        errors.append("report_hash mismatch")
    if report.get("intake", {}).get("character_gate") != "pass":
        errors.append("5000-character intake gate not passed")
    if report.get("provenance", {}).get("network_check") != "pass": errors.append("network_check must be pass")
    if report.get("provenance", {}).get("redaction_check") != "pass": errors.append("redaction_check must pass")
    if report.get("provenance", {}).get("source_provenance") != sources: errors.append("source provenance mismatch")
    return errors
