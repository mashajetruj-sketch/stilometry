---
name: stilometry-director
description: Director workflow for /stilometry-start — welcome, session folder, corpus intake, Task pipeline.
---
## /stilometry-start

1. Приветствие (что и зачем).
2. `python stilometry.py start --json` → новая сессия.
3. Нет файлов → спросить; есть → ingest в `corpus/`.
4. Task chain: corpus-guardian → metrics-analyst → report-auditor → **linguistic-interpreter** → profile-writer → profile-reviewer.
5. Показать `reports/profile-draft.md`; ждать approve/revise.

Session root: `stilometry-memory/sessions/<session_id>/`.
