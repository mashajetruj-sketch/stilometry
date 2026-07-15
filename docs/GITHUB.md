# Публикация на GitHub

Репозиторий: **https://github.com/mashajetruj-sketch/stilometry**

## Перед push

1. Убедитесь, что в индексе **нет** `stilometry-memory/sessions/`, `model-cache/`, `corpus/`, персональных текстов.

## Первый push

```powershell
cd projects/stilometry
git init
git add .
git status   # проверьте список файлов
git commit -m "Initial public release: Stilometry Cursor plugin v0.2.0"
git branch -M main
git remote add origin https://github.com/mashajetruj-sketch/stilometry.git
git push -u origin main
```

Если remote уже есть с другим URL:

```powershell
git remote set-url origin https://github.com/mashajetruj-sketch/stilometry.git
git push -u origin main
```

## Поля репозитория (Settings → General)

| Поле | Значение |
|------|----------|
| **Description** | Cursor plugin: Russian author stylometry — 28 metrics, Slovnet NLP, LLM profile & style prompt |
| **Website** | _(опционально)_ |
| **Topics** | `cursor`, `stylometry`, `russian-nlp`, `nlp`, `writing-style`, `slovnet`, `cursor-plugin`, `llm` |
| **Social preview** | Upload `docs/assets/github-cover.png` |

## Topics (copy-paste)

```
cursor stylometry russian-nlp nlp writing-style slovnet pymorphy3 razdel cursor-plugin linguistics author-profile
```
