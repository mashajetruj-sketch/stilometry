from pathlib import Path
import json
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
required = [
    ".cursor/agents", ".cursor/skills", ".cursor/commands", ".cursor/rules",
    "metrics/metric-manifest.json", "src/stilometry/core.py", "src/stilometry/parser_stack.py",
    "src/stilometry/schemas.py", "stilometry.py",
    "scripts/install_nlp_models.py", "shared/pipeline-incident-fix-contract.md",
    "schemas/run.schema.json", "schemas/metrics.schema.json", "schemas/profile.schema.json",
    "schemas/approval.schema.json", "schemas/prompt.schema.json",
    "schemas/llm-estimates.schema.json", "metrics/human-labels.ru.json", "docs/VALIDATION.md"
]
missing = [p for p in required if not (ROOT / p).exists()]
manifest = json.loads((ROOT / "metrics/metric-manifest.json").read_text(encoding="utf-8"))
ids = [m["id"] for m in manifest["metrics"]]
if len(ids) != 28 or len(set(ids)) != 28:
    missing.append("metrics/metric-manifest.json:exactly-28-unique-ids")
errors = list(missing)

allowed_agent_fields = {"name", "description", "model", "readonly", "is_background"}
agent_names = set()
for path in sorted((ROOT / ".cursor/agents").glob("*.md")):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{path.relative_to(ROOT)}:missing-frontmatter")
        continue
    end = text.find("\n---", 4)
    if end < 0:
        errors.append(f"{path.relative_to(ROOT)}:unterminated-frontmatter")
        continue
    fields = {
        line.split(":", 1)[0].strip()
        for line in text[4:end].splitlines()
        if ":" in line and not line.lstrip().startswith("#")
    }
    unsupported = fields - allowed_agent_fields
    if unsupported:
        errors.append(f"{path.relative_to(ROOT)}:unsupported-frontmatter:{sorted(unsupported)}")
    name_match = re.search(r"^name:\s*(\S+)\s*$", text[4:end], re.MULTILINE)
    if not name_match:
        errors.append(f"{path.relative_to(ROOT)}:missing-name")
    else:
        name = name_match.group(1)
        if name in agent_names:
            errors.append(f"duplicate-agent-name:{name}")
        agent_names.add(name)
        if name != path.stem:
            errors.append(f"{path.relative_to(ROOT)}:name-path-mismatch")

registry_path = ROOT / ".cursor/agents-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8"))
registered = {item["name"] for item in registry.get("agents", [])}
if registered != agent_names:
    errors.append("registry-agent-set-does-not-match-files")
boundaries = set(registry.get("human_boundaries", []))
for item in registry.get("agents", []):
    name = item["name"]
    for field in ("calls", "calledBy"):
        for ref in item.get(field, []):
            if ref not in registered and ref not in boundaries:
                errors.append(f"registry-dangling-ref:{name}:{field}:{ref}")
            if field == "calls" and ref in registered:
                target = next(a for a in registry["agents"] if a["name"] == ref)
                if name not in target.get("calledBy", []):
                    errors.append(f"registry-asymmetry:{name}->{ref}")
            if field == "calledBy" and ref in registered:
                source = next(a for a in registry["agents"] if a["name"] == ref)
                if name not in source.get("calls", []):
                    errors.append(f"registry-asymmetry:{ref}->{name}")

command_text = "\n".join(
    path.read_text(encoding="utf-8") for path in (ROOT / ".cursor/commands").glob("*.md")
)
for script in re.findall(r"(?:python|py)\s+([A-Za-z0-9_./\\-]+\.py)", command_text):
    if not (ROOT / script.replace("\\", "/")).exists():
        errors.append(f"command-missing-script:{script}")

try:
    tree = ast.parse((ROOT / "src/stilometry/core.py").read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = imports & {"http", "httpx", "requests", "urllib", "socket", "webbrowser"}
    if forbidden:
        errors.append(f"core-network-imports:{sorted(forbidden)}")
except SyntaxError as exc:
    errors.append(f"core-syntax-error:{exc.msg}")

workflow = (ROOT / "src/stilometry/workflow.py").read_text(encoding="utf-8")
core = (ROOT / "src/stilometry/core.py").read_text(encoding="utf-8")
for marker, source in (
    ("approval-gate", workflow),
    ("approval-hash", workflow),
    ("path-containment", workflow),
    ("redaction-gate", workflow),
    ("network-provenance", core),
):
    token = {
        "approval-gate": "approved",
        "approval-hash": "approved_input_hash",
        "path-containment": "safe_path",
        "redaction-gate": "redaction_check",
        "network-provenance": "network_check",
    }[marker]
    if token not in source:
        errors.append(f"missing-{marker}")

if errors:
    print(json.dumps({"status": "blocked", "errors": errors}))
    raise SystemExit(2)

start_cmd = ROOT / ".cursor/commands/stilometry-start.md"
if not start_cmd.is_file():
    errors.append("missing-stilometry-start-command")
if (ROOT / ".cursor/commands/stilometry-analyze.md").exists():
    errors.append("deprecated-stilometry-analyze-still-present")
interp = ROOT / ".cursor/agents/linguistic-interpreter.md"
if not interp.is_file():
    errors.append("missing-linguistic-interpreter")
gap = ROOT / ".cursor/agents/parser-gap-estimator.md"
if not gap.is_file():
    errors.append("missing-parser-gap-estimator")
fixer = ROOT / ".cursor/agents/stilometry-fixer.md"
if not fixer.is_file():
    errors.append("missing-stilometry-fixer")
labels = ROOT / "metrics/human-labels.ru.json"
if not labels.is_file():
    errors.append("missing-human-labels")
if errors:
    print(json.dumps({"status": "blocked", "errors": errors}))
    raise SystemExit(2)

print(json.dumps({
    "status": "ok",
    "artifacts": len(required),
    "agents": len(agent_names),
    "metric_ids": 28,
    "registry": "symmetric",
    "core": "offline",
    "gates": "approval+privacy",
}))
