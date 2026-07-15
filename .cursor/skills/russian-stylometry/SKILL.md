---
name: russian-stylometry
description: Russian-first stylometry — session intake, deterministic metrics, mandatory LLM interpretation.
---
## Workflow

Use when running `/stilometry-start` or session-based analysis.

1. **start** — welcome + `python stilometry.py start`.
2. **ingest** — corpus into `stilometry-memory/sessions/<id>/corpus/`.
3. **metrics** — `python stilometry.py analyze ... --session <id>`.
4. **interpret** — Task(`linguistic-interpreter`) full 10-block LLM report with quotes.
5. **draft** — Task(`profile-writer`) → `profile-draft.md`.

## Gates

5000 chars recommended; 28 metric IDs; corpus quotes must resolve to session files.

## Failure handling

Stop on missing corpus, path escape, fabricated quotes, or skipping LLM interpretation.

## Do not apply

Diagnosis, attribution without baseline, or approval inferred from chat.
