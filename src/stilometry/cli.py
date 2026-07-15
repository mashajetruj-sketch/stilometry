from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import validate_report
from .parser_stack import ensure_models, model_cache
from .session import WELCOME_RU, create_session, ingest_files, latest_session
from .workflow import analyze_files, approve, approved_output_path, compile_prompt, draft, personality, revise, safe_path


def main() -> int:
    p = argparse.ArgumentParser(prog="stilometry")
    sub = p.add_subparsers(dest="command", required=True)

    st = sub.add_parser("start", help="Create a new analysis session and show welcome")
    st.add_argument("--root", default=".")
    st.add_argument("--label", default=None, help="Optional session label slug")
    st.add_argument("--json", action="store_true", help="Machine-readable output only")

    ins = sub.add_parser("install-models", help="Download Slovnet/Navec models into model-cache/")
    ins.add_argument("--root", default=".")

    ing = sub.add_parser("ingest", help="Ingest corpus files into a session")
    ing.add_argument("files", nargs="+")
    ing.add_argument("--root", default=".")
    ing.add_argument("--session", default=None, help="Session id; defaults to latest")

    a = sub.add_parser("analyze", help="Run deterministic metrics on corpus files")
    a.add_argument("files", nargs="+")
    a.add_argument("--root", default=".")
    a.add_argument("--output", default="runs/report.json")
    a.add_argument("--session", default=None, help="If set, write to session runs/")

    v = sub.add_parser("validate")
    v.add_argument("report")
    ap = sub.add_parser("approve")
    ap.add_argument("draft")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--output", default="runs/approved.json")
    d = sub.add_parser("draft")
    d.add_argument("report")
    d.add_argument("--output", default="runs/draft.json")
    r = sub.add_parser("revise")
    r.add_argument("approved")
    r.add_argument("--approval-hash", required=True)
    r.add_argument("--output", default="runs/revised.json")
    ph = sub.add_parser("personality")
    ph.add_argument("approved")
    ph.add_argument("--output", default="runs/personality.json")
    cp = sub.add_parser("compile")
    cp.add_argument("approved")
    cp.add_argument("--output", default="runs/prompt-compiler.json")
    for command in (v, ap, d, r, ph, cp):
        command.add_argument("--root", default=".")

    args = p.parse_args()
    root = Path(args.root).resolve()

    if args.command == "install-models":
        paths = ensure_models(model_cache(root), download=True)
        print(json.dumps({"status": "ok", "cache": model_cache(root).as_posix(), "models": [p.name for p in paths.values()]}, ensure_ascii=False))
        return 0

    if args.command == "start":
        meta = create_session(root, args.label)
        if args.json:
            print(json.dumps({"status": "ok", "session": meta}, ensure_ascii=False))
        else:
            print(WELCOME_RU)
            print(f"\n**Сессия:** `{meta['session_id']}`")
            print(f"**Папка:** `{meta['paths']['root']}`")
            print("\nПрикрепите файлы в чат или укажите пути — затем: `/stilometry-start` снова или `python stilometry.py ingest <paths> --session " + meta["session_id"] + "`")
        return 0

    if args.command == "ingest":
        session_id = args.session or latest_session(root)
        if not session_id:
            print(json.dumps({"status": "blocked", "error": "no session; run start first"}, ensure_ascii=False))
            return 2
        meta = ingest_files(root, session_id, args.files)
        print(json.dumps({
            "status": "ok",
            "session_id": session_id,
            "files": len(meta["corpus_files"]),
            "character_count": meta["character_count"],
            "intake_gate": meta.get("intake_gate"),
            "next_action": meta.get("next_action"),
        }, ensure_ascii=False))
        return 0 if meta.get("intake_gate") == "pass" else 1

    if args.command == "analyze":
        output = Path(args.output)
        if args.session:
            output = Path(f"stilometry-memory/sessions/{args.session}/runs/metrics.json")
        report = analyze_files(root, args.files, output)
        print(json.dumps({"status": report["status"], "output": output.as_posix(), "session": args.session}, ensure_ascii=False))
        return 0 if report["status"] == "ok" else 2

    input_name = args.report if hasattr(args, "report") else args.draft if hasattr(args, "draft") else args.approved
    data = json.loads(safe_path(root, input_name).read_text(encoding="utf-8"))
    if args.command == "validate":
        errors = validate_report(data)
        print(json.dumps({"status": "ok" if not errors else "blocked", "errors": errors}, ensure_ascii=False))
        return 0 if not errors else 2
    if args.command == "approve":
        result = approve(data, args.reviewer)
    elif args.command == "draft":
        result = draft(data)
    elif args.command == "revise":
        result = revise(data, args.approval_hash)
    elif args.command == "personality":
        result = personality(data)
    else:
        result = compile_prompt(data)
    output = approved_output_path(root, args.output, [safe_path(root, input_name)])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
