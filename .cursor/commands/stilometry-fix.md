# /stilometry-fix

Post-run fixer loop. Язык — **русский**.

## Когда

После пайплайна или blocker, если `stilometry-memory/pipeline-fix-queue.md` содержит `status: open`.

## Действие

`Task(stilometry-fixer)` — прочитать contract + queue, внести durable правки, прогнать pytest/validate_install.

Не запускать новый `/stilometry-start` при open blocker-инцидентах без явного согласия пользователя.
