---
name: report-provenance
description: Validate reproducible local report provenance.
---
Require schema_version, input/file hashes, formulas, versions, source spans, sufficiency, confidence, redaction_check and network_check. Reject unknown metric IDs and approval hash mismatches. Never treat a self-reported pass as evidence.
Use when validating local run, metric, profile, approval, or prompt artifacts.
Do NOT use when provenance is missing or when a report should be repaired by guessing.
## Do NOT apply
Do NOT apply to reports without immutable source hashes, bounded evidence spans, explicit provenance, or to infer approval from chat context.
