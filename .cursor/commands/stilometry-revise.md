# /stilometry-revise
Use when revising an approved artifact while retaining traceable evidence and run linkage.
Do NOT use when silently preserving approval; revision invalidates prior approval until explicit re-approval.
Revise only from an approved hash, preserving evidence links and blockers. Reject mismatched or expired approval; never overwrite source corpus.
CLI: `python stilometry.py revise runs/approved.json --approval-hash HASH --output runs/revised.json`.
