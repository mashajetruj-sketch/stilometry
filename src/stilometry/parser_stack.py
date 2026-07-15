from __future__ import annotations

import math
import re
import urllib.request
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "model-cache"

MODEL_URLS = {
    "navec_news_v1_1B_250K_300d_100q.tar": "https://storage.yandexcloud.net/natasha-navec/packs/navec_news_v1_1B_250K_300d_100q.tar",
    "slovnet_syntax_news_v1.tar": "https://storage.yandexcloud.net/natasha-slovnet/packs/slovnet_syntax_news_v1.tar",
    "slovnet_morph_news_v1.tar": "https://storage.yandexcloud.net/natasha-slovnet/packs/slovnet_morph_news_v1.tar",
}

FUNCTION_LEMMAS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
    "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по",
    "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему",
    "теперь", "когда", "даже", "ну", "ли", "если", "уже", "или", "ни", "быть", "был",
    "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя",
    "ничего", "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы",
    "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже",
    "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому", "этого",
    "какой", "совсем", "ним", "здесь", "этом", "один", "почти", "мой", "тем", "чтобы",
    "нее", "сейчас", "были", "куда", "зачем", "всех", "никогда", "можно", "при", "наконец",
    "два", "об", "другой", "хоть", "после", "над", "больше", "тот", "через", "эти", "нас",
    "про", "всего", "них", "какая", "много", "разве", "три", "эту", "моя", "впрочем",
    "хорошо", "свою", "этой", "перед", "иногда", "лучше", "чуть", "том", "нельзя", "такой",
    "им", "более", "всегда", "конечно", "всю", "между",
}

FIGURATIVE_PATTERNS = (
    r"\bкак\b",
    r"\bсловно\b",
    r"\bбудто\b",
    r"\bточно\b",
    r"\bподобн",
    r"\bнапомина",
    r"можно сказать",
    r"образно",
)


def model_cache(root: Path | None = None) -> Path:
    return (root or ROOT) / "model-cache"


def ensure_models(cache_dir: Path | None = None, *, download: bool = True) -> dict[str, Path]:
    cache = cache_dir or DEFAULT_CACHE
    cache.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    missing: list[str] = []
    for name, url in MODEL_URLS.items():
        path = cache / name
        paths[name] = path
        if path.is_file() and path.stat().st_size > 1000:
            continue
        if not download:
            missing.append(name)
            continue
        urllib.request.urlretrieve(url, path)
    if missing:
        raise FileNotFoundError(
            f"NLP models missing in {cache}: {missing}. Run: python scripts/install_nlp_models.py"
        )
    return paths


def metadata() -> dict[str, Any]:
    return {
        "tokenizer": {"name": "razdel", "version": "0.5+", "license": "MIT"},
        "morphology": {"name": "pymorphy3+slovnet-morph", "version": "1.0", "license": "MIT"},
        "syntax": {"name": "slovnet-syntax-news-v1", "version": "1.0", "license": "MIT"},
        "embeddings": {"name": "navec-news-v1", "version": "1.0", "license": "MIT"},
    }


@lru_cache(maxsize=1)
def _morph_analyzer():
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=1)
def _navec(cache: str):
    from navec import Navec

    return Navec.load(cache)


@lru_cache(maxsize=1)
def _syntax(cache_syntax: str, cache_navec: str):
    from slovnet import Syntax

    syntax = Syntax.load(cache_syntax)
    syntax.navec(_navec(cache_navec))
    return syntax


@lru_cache(maxsize=1)
def _morph_tagger(cache_morph: str, cache_navec: str):
    from slovnet import Morph

    morph = Morph.load(cache_morph)
    morph.navec(_navec(cache_navec))
    return morph


def razdel_sentences(text: str) -> list[str]:
    from razdel import sentenize

    return [s.text.strip() for s in sentenize(text) if s.text.strip()]


def razdel_tokens(text: str) -> list[str]:
    from razdel import sentenize, tokenize

    words: list[str] = []
    for sent in sentenize(text):
        words.extend(t.text.lower() for t in tokenize(sent.text) if t.text.strip())
    return words


def sentence_token_chunks(text: str) -> list[list[str]]:
    from razdel import sentenize, tokenize

    return [[t.text for t in tokenize(sent.text) if t.text.strip()] for sent in sentenize(text) if sent.text.strip()]


def lemma(word: str) -> str:
    parsed = _morph_analyzer().parse(word)
    return parsed[0].normal_form if parsed else word.lower()


def lemmatize_words(words: list[str]) -> list[str]:
    return [lemma(w) for w in words]


def _tree_depth(tokens: list[Any]) -> int:
    by_id = {t.id: t for t in tokens}
    depths: list[int] = []
    for token in tokens:
        depth = 0
        head_id = token.head_id
        seen: set[str] = set()
        while head_id != "0" and head_id in by_id and head_id not in seen:
            seen.add(head_id)
            depth += 1
            head_id = by_id[head_id].head_id
        depths.append(depth)
    return max(depths) if depths else 0


def _noun_phrase_lengths(syntax_tokens: list[Any], morph_tokens: list[Any]) -> list[int]:
    pos_by_text = {t.text: t.pos for t in morph_tokens}
    lengths: list[int] = []
    for token in syntax_tokens:
        if pos_by_text.get(token.text) != "NOUN":
            continue
        mods = {token.id}
        for other in syntax_tokens:
            if other.head_id == token.id and other.rel in {"amod", "det", "nummod", "compound", "nmod", "appos"}:
                mods.add(other.id)
            if other.id == token.head_id and other.rel in {"amod", "det", "nummod", "compound"}:
                mods.add(other.id)
        lengths.append(len(mods))
    return lengths


def _is_passive_sentence(syntax_tokens: list[Any], morph_tokens: list[Any]) -> bool:
    if any("pass" in (token.rel or "") for token in syntax_tokens):
        return True
    return any(token.pos == "VERB" and token.feats.get("Voice") == "Pass" for token in morph_tokens)


def _finite_verbs(morph_tokens: list[Any]) -> int:
    return sum(1 for t in morph_tokens if t.pos in {"VERB", "AUX"} and t.feats.get("VerbForm") == "Fin")


def analyze_with_parser(text: str, cache_dir: Path | None = None) -> dict[str, Any]:
    paths = ensure_models(cache_dir)
    navec_path = str(paths["navec_news_v1_1B_250K_300d_100q.tar"])
    syntax_path = str(paths["slovnet_syntax_news_v1.tar"])
    morph_path = str(paths["slovnet_morph_news_v1.tar"])

    words = razdel_tokens(text)
    sents = razdel_sentences(text)
    chunks = sentence_token_chunks(text)
    lemmas = lemmatize_words(words)

    syntax = _syntax(syntax_path, navec_path)
    morph = _morph_tagger(morph_path, navec_path)

    tree_depths: list[int] = []
    np_lengths: list[int] = []
    passive_sentences = 0
    complex_sentences = 0
    pos_counts: Counter[str] = Counter()
    morph_variants: set[tuple[str, str]] = set()
    adj_count = 0
    parsed_sentence_count = 0

    syntax_markups = list(syntax.map(chunks))
    morph_markups = list(morph.map(chunks))

    for syntax_markup, morph_markup in zip(syntax_markups, morph_markups):
        if not syntax_markup.tokens:
            continue
        parsed_sentence_count += 1
        tree_depths.append(_tree_depth(syntax_markup.tokens))
        np_lengths.extend(_noun_phrase_lengths(syntax_markup.tokens, morph_markup.tokens))
        if _is_passive_sentence(syntax_markup.tokens, morph_markup.tokens):
            passive_sentences += 1
        if _finite_verbs(morph_markup.tokens) >= 2:
            complex_sentences += 1
        for token in morph_markup.tokens:
            pos_counts[token.pos] += 1
            morph_variants.add((token.pos, str(sorted(token.feats.items()))))
            if token.pos == "ADJ":
                adj_count += 1
            if token.pos == "VERB" and token.feats.get("VerbForm") in {"Part", "Conv"}:
                adj_count += 1

    pos_total = sum(pos_counts.values()) or 1
    pos_entropy = -sum((c / pos_total) * math.log2(c / pos_total) for c in pos_counts.values()) if pos_counts else 0.0
    lemma_counts = Counter(lemmas)
    unique_lemmas = set(lemmas)

    return {
        "words": words,
        "lemmas": lemmas,
        "sentences": sents,
        "parsed_sentence_count": parsed_sentence_count,
        "dependency_tree_depth": float(statistics_median(tree_depths)),
        "avg_noun_phrase_length": statistics_mean(np_lengths),
        "passive_impersonal_ratio": passive_sentences / parsed_sentence_count if parsed_sentence_count else 0.0,
        "complex_sentence_ratio": complex_sentences / parsed_sentence_count if parsed_sentence_count else 0.0,
        "figurative_candidate_ratio": sum(len(re.findall(pat, text, flags=re.I)) for pat in FIGURATIVE_PATTERNS) / len(words) * 1000 if words else 0.0,
        "pos_entropy": pos_entropy,
        "verb_ratio": pos_counts.get("VERB", 0) / pos_total,
        "adjective_participle_ratio": adj_count / pos_total,
        "morphological_variability": len(morph_variants) / pos_total,
        "function_word_ratio": sum(1 for item in lemmas if item in FUNCTION_LEMMAS) / len(lemmas) if lemmas else 0.0,
        "hapax_ratio": sum(1 for c in lemma_counts.values() if c == 1) / len(unique_lemmas) if unique_lemmas else 0.0,
        "parser_metadata": metadata(),
    }


def statistics_median(values: list[float]) -> float:
    if not values:
        return 0.0
    import statistics

    return float(statistics.median(values))


def statistics_mean(values: list[int]) -> float:
    if not values:
        return 0.0
    import statistics

    return float(statistics.mean(values))
