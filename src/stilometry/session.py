from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import sha256
from .workflow import safe_path

SESSION_ROOT = "stilometry-memory/sessions"
WELCOME_RU = """# Stilometry — стилометрический профиль автора

Сейчас будет построен **лингвистический отпечаток** ваших текстов — как ДНК, только для слов.

**Что сделаем:**
1. Соберём корпус из ваших авторских текстов (рекомендуется ≥ 5000 символов).
2. Посчитаем 28 стилометрических метрик (лексика, синтаксис, морфология, пунктуация, ритм, риторика, прагматика, цифровой стиль).
3. Проведём **глубокий LLM-разбор** с цитатами из ваших текстов по 10 блокам отчёта.
4. Сформируем черновик профиля для вашей проверки → после approve: гипотезы о языковых осях → промпт для имитации стиля без нейрослопа.

**Что нужно от вас:** прикрепите файлы в чат **или** укажите пути внутри проекта (например `corpus/notes.txt`).

Подойдут: посты, переписки, рабочие сообщения, заметки, соцсети — короткие и длинные форматы. Только **ваши** тексты, без ИИ.
"""

SLUG_RE = re.compile(r"[^a-z0-9-]+")


def session_dir(root: Path, session_id: str) -> Path:
    return safe_path(root, f"{SESSION_ROOT}/{session_id}")


def _slug(label: str | None) -> str:
    if not label:
        return "session"
    slug = SLUG_RE.sub("-", label.strip().lower())
    return slug.strip("-") or "session"


def create_session(root: Path, label: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    session_id = f"{ts}-{_slug(label)}"
    base = session_dir(root, session_id)
    for name in ("corpus", "runs", "reports", "fragments"):
        (base / name).mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "awaiting_corpus",
        "welcome_shown": True,
        "corpus_files": [],
        "character_count": 0,
        "token_count": 0,
        "paths": {
            "root": base.as_posix(),
            "corpus": (base / "corpus").as_posix(),
            "runs": (base / "runs").as_posix(),
            "reports": (base / "reports").as_posix(),
            "fragments": (base / "fragments").as_posix(),
        },
        "next_action": "ingest_corpus",
    }
    (base / "session.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "reports" / "00-welcome.md").write_text(WELCOME_RU, encoding="utf-8")
    return meta


def load_session(root: Path, session_id: str) -> dict[str, Any]:
    path = session_dir(root, session_id) / "session.json"
    if not path.is_file():
        raise FileNotFoundError(session_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(root: Path, meta: dict[str, Any]) -> None:
    base = session_dir(root, meta["session_id"])
    (base / "session.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_files(root: Path, session_id: str, sources: list[str], *, from_chat: bool = False) -> dict[str, Any]:
    meta = load_session(root, session_id)
    base = session_dir(root, session_id)
    corpus = base / "corpus"
    ingested: list[dict[str, Any]] = []
    total_chars = 0

    for idx, source in enumerate(sources, start=1):
        src = safe_path(root, source)
        if not src.is_file():
            raise FileNotFoundError(source)
        text = src.read_text(encoding="utf-8")
        dest_name = f"{idx:02d}-{src.name}"
        dest = corpus / dest_name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        file_hash = sha256(text)
        record = {
            "source_id": dest_name,
            "original_path": source,
            "session_path": dest.relative_to(root).as_posix(),
            "source_hash": file_hash,
            "char_count": len(text),
            "from_chat": from_chat,
        }
        ingested.append(record)
        total_chars += len(text)

    existing = {f["source_id"]: f for f in meta.get("corpus_files", [])}
    for record in ingested:
        existing[record["source_id"]] = record
    meta["corpus_files"] = list(existing.values())
    meta["character_count"] = sum(f["char_count"] for f in meta["corpus_files"])
    meta["intake_gate"] = "pass" if meta["character_count"] >= 5000 else "insufficient"
    meta["state"] = "corpus_ready" if meta["corpus_files"] else "awaiting_corpus"
    meta["next_action"] = "run_metrics" if meta["corpus_files"] else "ingest_corpus"
    save_session(root, meta)
    return meta


def corpus_paths(root: Path, session_id: str) -> list[str]:
    meta = load_session(root, session_id)
    return [f["session_path"] for f in meta.get("corpus_files", [])]


def latest_session(root: Path) -> str | None:
    sessions_root = safe_path(root, SESSION_ROOT)
    if not sessions_root.is_dir():
        return None
    candidates = sorted(p.name for p in sessions_root.iterdir() if p.is_dir() and (p / "session.json").is_file())
    return candidates[-1] if candidates else None
