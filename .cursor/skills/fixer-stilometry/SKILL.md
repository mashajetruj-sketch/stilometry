---
name: fixer-stilometry
description: Post-run fixer runbook for Stilometry pipeline incidents.
---
## Когда запускаться

После завершения `/stilometry-start` пайплайна или терминального blocker, если `stilometry-memory/pipeline-fix-queue.md` содержит `status: open`.

## Вход

- `stilometry-memory/pipeline-fix-queue.md`
- `shared/pipeline-incident-fix-contract.md`
- файлы из `Suggested files to inspect/change`
- git diff/status (если доступен)

## Алгоритм

1. Прочитай всю очередь инцидентов.
2. Выбери open для текущего run (или все open, сгруппировав по причине).
3. Для каждого: prompt/skill/script/NLP/handoff?
4. Исправь durable source (agents, skills, shared, scripts, `src/stilometry/`).
5. Синхронизируй `.cursor/*` при правке контрактов.
6. Проверки: pytest, validate_install, install_nlp_models при NLP.
7. Обнови incident → `fixed` / `needs-human`.

## Хороший fix

- Следующий run ловит ошибку раньше (gate/script).
- Idempotent retry/fallback описан в skill.
- Без secrets в memory.

## Запреты

- Не чинить симптом только в `reports/` сессии.
- Не закрывать open молча.
