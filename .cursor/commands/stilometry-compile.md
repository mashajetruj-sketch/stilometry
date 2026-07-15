# /stilometry-compile
Use when compiling constraints from a verified approved artifact.
Do NOT use when approval is absent or the output would contain persona imitation, raw quotes, or PII.
Compile an approved profile into abstract `must`, `must_not`, and `tests`. Strip raw quotes and PII; run anti-slop QA; fail on approval mismatch.
CLI: `python stilometry.py compile runs/approved.json`.
