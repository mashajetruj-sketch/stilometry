---
name: plain-language-report
description: Human-readable Russian stylometry reports without jargon in main text.
---
## Правило plain language

**Основной текст** (`profile-draft.md`, `linguistic-interpretation.md`) — для **человека**, не для лингвиста.

### Запрещено в основном тексте

- Латинские ярлыки: TTR, MTLD, hapax, CV, burstiness, hedging, discourse_marker_ratio, anaphora_ratio и т.п.
- Snake_case id метрик: `evaluation_emotion_ratio`, `paragraph_burstiness`
- Английские technical terms без перевода

### Разрешено

- **Русские названия** из `metrics/human-labels.ru.json` → поле `title`
- Числа с **понятной единицей**: «13 слов в предложении», «доля 0,49»
- Краткое пояснение в скобках при первом упоминании показателя
- Цитаты из корпуса автора

### Структура отчёта

1. Блоки 1–10 — **только живой русский язык** + цитаты.
2. Блок 11 «Сводка цифр» — таблица с колонками: **Показатель** | **Значение** | **Что это значит** | **Уверенность**.
3. **Приложение** «Технические идентификаторы» (опционально, в конце) — соответствие русских названий и id для машинной обработки.

### Оценки ИИ вместо парсера

Если есть `runs/llm-metric-estimates.json` — в сводке показывать значения с пометкой **«оценка по тексту»**, не «insufficient».
