# Stilometry — agent pipeline pitfalls

- Run `python stilometry.py install-models` once per machine before first analysis.
- `model-cache/` is gitignored; missing models block `analyze_text`.
- Reports for humans: skill `plain-language-report` — no TTR/MTLD in main text.
- `parser-gap-estimator` only when slovnet metrics fail — not default path.
- Session corpus lives in `stilometry-memory/sessions/<id>/corpus/` — never commit.
