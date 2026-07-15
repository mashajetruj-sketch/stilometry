import json
from pathlib import Path

import pytest

from stilometry.core import analyze_text, manifest, validate_report
from stilometry.schemas import validate_artifact, validation_backend
from stilometry.workflow import analyze_files, approve, compile_prompt, draft, personality, revise, safe_path


TEXT = ("Это короткий пример. Однако он повторяется, потому что проверяет метрики. "
        "Вы можете проверить вопрос? Это хороший и ясный текст! ") * 120


def test_manifest_has_exactly_28_unique_ids():
    items = manifest()["metrics"]
    assert len(items) == 28
    assert len({x["id"] for x in items}) == 28


def test_all_metrics_present_and_parser_metrics_available():
    report = analyze_text(TEXT)
    assert len(report["metrics"]) == 28
    assert report["metrics"]["dependency_tree_depth"]["data_sufficiency"] == "sufficient"
    assert report["metrics"]["dependency_tree_depth"]["value"] is not None
    assert validate_report(report) == []


def test_short_threshold_is_insufficient():
    report = analyze_text("Коротко.")
    assert report["metrics"]["ttr"]["value"] is None
    assert report["metrics"]["ttr"]["data_sufficiency"] == "insufficient"


def test_unknown_metric_rejected():
    report = analyze_text(TEXT)
    report["metrics"]["unknown"] = {}
    assert validate_report(report)


def test_canonical_formula_and_implementation_tampering_rejected():
    report = analyze_text(TEXT)
    report["metrics"]["ttr"]["formula_version"] = "tampered"
    report["metrics"]["ttr"]["provenance"]["formula"] = "tampered"
    report["metrics"]["ttr"]["provenance"]["implementation_version"] = "9.9.9"
    report["metrics_hash"] = __import__("stilometry.core", fromlist=["sha256"]).sha256(
        json.dumps(report["metrics"], sort_keys=True)
    )
    report["report_hash"] = __import__("stilometry.core", fromlist=["sha256"]).sha256(
        json.dumps({k: v for k, v in report.items() if k != "report_hash"}, sort_keys=True)
    )
    errors = validate_report(report)
    assert any("canonical manifest" in error for error in errors)
    assert any("implementation/version" in error for error in errors)


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, "../outside.txt")


def test_output_cannot_equal_source_or_leave_approved_destinations(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text(TEXT, encoding="utf-8")
    with pytest.raises(ValueError):
        analyze_files(tmp_path, ["source.txt"], "source.txt")
    with pytest.raises(ValueError):
        analyze_files(tmp_path, ["source.txt"], "not-approved/report.json")


def test_internal_symlink_component_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        safe_path(tmp_path, "link/file.txt")


def test_prompt_requires_approval():
    with pytest.raises(ValueError):
        compile_prompt({"status": "draft"})


def test_offline_provenance():
    report = analyze_text(TEXT)
    assert report["provenance"]["network_check"] == "pass"
    assert report["source_hash"]


def test_draft_preserves_hashes_and_approval_transitions():
    report = analyze_text(TEXT)
    prepared = dict(report, run_id="test-run")
    prepared["report_hash"] = __import__("stilometry.core", fromlist=["sha256"]).sha256(
        json.dumps({k: v for k, v in prepared.items() if k != "report_hash"}, sort_keys=True)
    )
    draft_report = draft(prepared)
    assert draft_report["metrics_hash"] == report["metrics_hash"]
    assert validate_artifact("profile", draft_report) == []
    approved = approve(draft_report, "reviewer")
    assert validate_artifact("approval", approved) == []
    assert personality(approved)["status"] == "personality_hypotheses"
    compiled = compile_prompt(approved)
    assert compiled["status"] == "prompt_compiled"
    assert validate_artifact("prompt", compiled) == []
    revised = revise(approved, approved["approved_input_hash"])
    assert revised["approval_state"] == "invalidated_for_revision"
    assert revised["sources"] == approved["approved_payload"]["sources"]
    assert revised["metrics"] == approved["approved_payload"]["metrics"]
    assert revised["evidence_refs"] == approved["approved_payload"]["evidence_refs"]
    assert revised["citations"] == approved["approved_payload"]["citations"]
    assert revised["uncertainty"] == approved["approved_payload"]["uncertainty"]
    assert revised["approved_run_id"] == approved["approved_payload"]["run_id"]
    reapproved = approve(revised, "reviewer-2")
    assert reapproved["approval_event"]["supersedes_approval_hash"] == approved["approved_input_hash"]


def test_approval_hash_mismatch_is_rejected():
    report = analyze_text(TEXT)
    report["run_id"] = "test-run"
    report["report_hash"] = __import__("stilometry.core", fromlist=["sha256"]).sha256(
        json.dumps({k: v for k, v in report.items() if k != "report_hash"}, sort_keys=True)
    )
    approved = approve(draft(report), "reviewer")
    approved["approved_metrics_hash"] = "tampered"
    with pytest.raises(ValueError):
        compile_prompt(approved)


def test_multi_source_aggregation_and_short_intake(tmp_path):
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text(TEXT, encoding="utf-8")
    two.write_text(TEXT, encoding="utf-8")
    report = analyze_files(tmp_path, ["one.txt", "two.txt"], "runs/report.json")
    assert len(report["sources"]) == 2
    assert report["metrics"]["avg_word_length"]["n_tokens"] == sum(s["token_count"] for s in report["sources"])
    short = tmp_path / "short.txt"
    short.write_text("короткий текст", encoding="utf-8")
    short_report = analyze_files(tmp_path, ["short.txt"], "runs/short.json")
    assert short_report["intake"]["character_gate"] == "insufficient"


def test_evidence_and_privacy_validation():
    report = analyze_text(TEXT)
    report["metrics"]["ttr"]["evidence_spans"][0]["char_end"] = -1
    assert validate_report(report)
    report = analyze_text(TEXT)
    report["metrics"]["ttr"]["evidence_spans"][0]["char_end"] = report["sources"][0]["char_count"] + 1
    assert "evidence span exceeds source char_count" in " ".join(validate_report(report))
    private = analyze_text(TEXT + " test@example.com")
    assert private["provenance"]["redaction_check"] == "blocked"


def test_combined_corpus_gate_is_not_per_source(tmp_path):
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("слово " * 420, encoding="utf-8")
    two.write_text("текст " * 420, encoding="utf-8")
    report = analyze_files(tmp_path, ["one.txt", "two.txt"], "runs/combined.json")
    assert report["intake"]["policy"] == "combined_corpus_characters"
    assert report["intake"]["per_source_minimum"] is None
    assert report["intake"]["character_gate"] == "pass"


def test_schema_validation_and_reproducibility_metadata():
    report = analyze_text(TEXT)
    assert validate_artifact("run", report) == []
    assert validation_backend() in {"jsonschema-draft2020-12", "stdlib-draft2020-12-fallback"}
    malformed = dict(report, sources=[1])
    assert validate_artifact("run", malformed)
    assert validate_artifact("metrics", {"schema_version": "1.0", "metrics": report["metrics"], "metrics_hash": report["metrics_hash"], "provenance": report["provenance"]}) == []
    assert report["seed"] == 0
    assert report["platform"]
    assert report["config_hash"]
    assert report["tokenizer_metadata"]["name"] == "razdel"
    assert report["parser_metadata"]["status"] == "available"
    assert report["model_metadata"]["name"] == "navec-news-v1"
    assert report["license_metadata"]
    assert all("per_source_values" in metric for metric in report["metrics"].values())
    invalid = dict(report, unexpected=True)
    assert any("unexpected" in error or "Additional properties" in error or "unknown field" in error for error in validate_artifact("run", invalid))


def test_evidence_schema_and_capability_labels():
    report = analyze_text(TEXT)
    evidence = report["metrics"]["ttr"]["evidence_spans"][0]
    assert evidence["raw_span"] is None
    assert evidence["normalized_span"] == "[REDACTED]"
    assert evidence["quote_redacted"] is True
    assert evidence["citation_id"]
    assert report["metrics"]["complex_sentence_ratio"]["capability"] == "slovnet_deterministic"
    figurative = report["metrics"]["figurative_candidate_ratio"]
    assert figurative["value"] is not None
    assert figurative["capability"] == "slovnet_heuristic_proxy"
    assert figurative["provenance"]["method"] == "heuristic"


def test_human_labels_cover_all_metrics():
    from stilometry.labels import human_labels, parser_gap_ids

    ids = {m["id"] for m in manifest()["metrics"]}
    labeled = set(human_labels()["metrics"])
    assert ids == labeled
    assert len(parser_gap_ids()) == 4


def test_session_create_and_ingest(tmp_path):
    from stilometry.session import create_session, ingest_files, latest_session, load_session

    meta = create_session(tmp_path, label="test")
    assert meta["state"] == "awaiting_corpus"
    session_id = meta["session_id"]
    assert (tmp_path / "stilometry-memory/sessions" / session_id / "corpus").is_dir()
    assert (tmp_path / "stilometry-memory/sessions" / session_id / "reports/00-welcome.md").is_file()

    source = tmp_path / "notes.txt"
    source.write_text(TEXT, encoding="utf-8")
    updated = ingest_files(tmp_path, session_id, ["notes.txt"])
    assert updated["character_count"] >= 5000
    assert updated["intake_gate"] == "pass"
    assert updated["state"] == "corpus_ready"
    assert latest_session(tmp_path) == session_id
    reloaded = load_session(tmp_path, session_id)
    assert len(reloaded["corpus_files"]) == 1


def test_session_analyze_output(tmp_path):
    from stilometry.session import create_session, ingest_files

    meta = create_session(tmp_path)
    source = tmp_path / "one.txt"
    source.write_text(TEXT, encoding="utf-8")
    ingested = ingest_files(tmp_path, meta["session_id"], ["one.txt"])
    rel = ingested["corpus_files"][0]["session_path"]
    report = analyze_files(
        tmp_path,
        [rel],
        f"stilometry-memory/sessions/{meta['session_id']}/runs/metrics.json",
    )
    assert report["status"] == "ok"
    assert (tmp_path / f"stilometry-memory/sessions/{meta['session_id']}/runs/metrics.json").is_file()
