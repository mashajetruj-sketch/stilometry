---
name: privacy-local-first
description: Enforce local-only privacy and path safety.
---
Use pathlib containment checks, UTF-8, hashes and redacted spans. Default network denied. Keep corpus, private data, runs and model caches ignored. Stop on PII leakage, path traversal, symlink dependency or remote payload without explicit approval.
Use when reading local sources or writing approved project artifacts.
Do NOT use when exporting corpus, enabling unrestricted writes, or bypassing the privacy gate.
## Do NOT apply
Do NOT apply to remote processing, source export, unrestricted filesystem writes, or any workflow that bypasses the local privacy gate.
