# Stilometry — incident memory and fixer loop

## Canonical files

| File | Purpose |
|------|---------|
| `stilometry-memory/pipeline-fix-queue.md` | durable incident memory |
| `.cursor/agents/stilometry-fixer.md` | fixer agent contract |
| `.cursor/skills/fixer-stilometry/SKILL.md` | fixer runbook |
| `shared/agent-pipeline-pitfalls.md` | stable lessons before every run |

## When any agent must write an incident

Append to `stilometry-memory/pipeline-fix-queue.md` when:

- blocker, missing NLP models, schema mismatch, parser failure;
- retry/workaround not documented;
- user correction revealed unclear contract;
- validation failed and fix was inferred ad-hoc.

Handoff line in `fragments/`:

```text
incident_report: none
```

or:

```text
incident_report: stilometry-memory/pipeline-fix-queue.md#INC-...
```

## Incident format

```markdown
## INC-YYYYMMDD-HHMM-<role>-<slug>
status: open
run_date: YYYY-MM-DD
role: <agent-name>
session_id: <id> | n/a
severity: low | medium | high | blocker
category: prompt | script | docs | env | nlp | handoff | qa | other

### What went wrong
- ...

### How the agent recovered this run
- ...

### Durable fix needed before next run
- ...

### Suggested files to inspect/change
- `path/to/file`

### Secrets
- none recorded

### Fixer resolution
- pending
```

## Director duty

After pipeline completion or terminal blocker:

1. Read `stilometry-memory/pipeline-fix-queue.md`.
2. If `status: open` incidents exist → `Task(stilometry-fixer)`.
3. Do not start a new `/stilometry-start` with open blocker incidents unless user says skip.

## Fixer duty

- Fix durable sources: `.cursor/agents/`, `.cursor/skills/`, `shared/`, `scripts/`, `src/stilometry/`.
- Run `pytest`, `validate_install.py`, `install_nlp_models.py` when NLP-related.
- Mark incidents `fixed` or `needs-human`.
- No secrets in memory.
