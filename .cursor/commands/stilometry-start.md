# /stilometry-start

Точка входа в стилометрию. Язык с пользователем — **русский**.

## Приветствие (обязательно в чат)

При запуске **сначала** выведи короткое приветствие пользователю (можно взять из `reports/00-welcome.md` сессии или текст ниже):

> **Stilometry** построит лингвистический отпечаток ваших текстов: 28 метрик + глубокий разбор по 10 блокам с цитатами. После вашего approve — языковые гипотезы и промпт для имитации стиля без нейрослопа. Нужны **ваши** тексты (≥5000 символов): посты, переписки, заметки, соцсети.

## Шаг 1 — сессия и NLP

1. Если модели не скачаны: `python stilometry.py install-models`
2. Выполни: `python stilometry.py start --json`
2. Запомни `session_id` и папку `stilometry-memory/sessions/<session_id>/`.
3. Каждый новый запуск `/stilometry-start` без продолжения сессии создаёт **новую** папку сессии.

## Шаг 2 — корпус

Если пользователь **не приложил** файлы и **не указал** пути:

- Остановись и **спроси**: «Прикрепите тексты в чат или укажите пути внутри проекта (например `corpus/notes.txt`).»
- Не запускай метрики и LLM без корпуса.

Если файлы есть:

- **В чате:** сохрани содержимое/вложения в `stilometry-memory/sessions/<session_id>/corpus/` (UTF-8), затем обнови `session.json` через `python stilometry.py ingest <paths> --session <id>`.
- **Путь в проекте:** `python stilometry.py ingest path/to/file.txt --session <id>`.

Проверь `intake_gate`: при `<5000` символов предупреди, но можно продолжить с пометкой низкой уверенности.

## Шаг 3 — пайплайн (только через Task)

Не делай весь анализ в основном чате. Делегируй:

| Порядок | Task | Роль |
|--------|------|------|
| 1 | `corpus-guardian` | Валидация корпуса, PII, границы |
| 2 | `metrics-analyst` | `python stilometry.py analyze <corpus paths> --session <id>` |
| 3 | `report-auditor` | Аудит metrics.json |
| 4 | `parser-gap-estimator` | **LLM-оценка** 4 показателей без парсера → `llm-metric-estimates.json` |
| 5 | `linguistic-interpreter` | Полный разбор 10 блоков, **plain Russian**, цитаты |
| 6 | `profile-writer` | `reports/profile-draft.md` |
| 7 | `profile-reviewer` | QA: plain language, цитаты, anti-slop |

Память сессии: `stilometry-memory/sessions/<session_id>/` (`corpus/`, `runs/`, `reports/`, `fragments/`).

## Шаг 4 — пользователю

Покажи краткое резюме и путь к `reports/profile-draft.md`. Предложи `/stilometry-approve` или `/stilometry-revise`.

## Шаг 5 — fixer (если были инциденты)

Если в `stilometry-memory/pipeline-fix-queue.md` есть `status: open` → `/stilometry-fix` → `Task(stilometry-fixer)`.

## Запреты

- Не пропускать приветствие и запрос файлов.
- Не смешивать сессии.
- Не выдумывать цитаты — только из корпуса сессии.
- Не переходить к personality/compile без approve.
