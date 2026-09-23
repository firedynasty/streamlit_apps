"""
openai_gloss.py

OpenAI alternative to chinese_csv.py's local dictionary pipeline: one LLM
call per sentence returns a word-by-word gloss whose meanings fit the
sentence (靈 -> "spirit", not the dictionary's first sense "quick"). Output
rows use the same Chinese/Pinyin/English meaning layout as chinese_csv.py.

Prompt ported from language_capabilities/capabilities/mandarin_gloss_plain.py.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from chinese_csv import chinese_text_to_rows, split_sentences

DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = (
    "You are a Mandarin Chinese linguistics assistant that creates word-by-word glosses for language learners.\n\n"
    "For each line you receive, break down EVERY word/phrase. Return a JSON array of objects:\n"
    '[  {"chinese": "我", "pinyin": "wǒ", "english": "I / me"},\n'
    '  {"chinese": "想", "pinyin": "xiǎng", "english": "want / think"},\n  ...\n]\n\n'
    "Rules:\n"
    "- Break down by meaningful units (words/phrases, not individual characters when they form a word)\n"
    "- Include pinyin with tone marks for every entry\n"
    "- Note grammar particles and their function (e.g. 了 le = completed action, 的 de = possessive/attributive)\n"
    "- Note measure words and their usage (e.g. 个 gè = general measure word)\n"
    "- Explain verb complements and directional verbs in parentheses\n"
    "- For chengyu (idioms) or set phrases, keep them together and explain the meaning\n"
    "- Keep words in the same order as the line\n"
    "- Keep compound words and fixed pairs together as ONE entry (e.g. 天地 tiāndì = heaven and earth, "
    "水面 shuǐmiàn = surface of the water) — do not split them into single characters\n"
    "- If the line starts with a speaker name and a colon (e.g. 小西:), skip the speaker name\n"
    "- Give the meaning that fits THIS sentence\n"
    "- Keep the characters exactly as written (do not convert Traditional to Simplified or vice versa)\n"
    "- Return ONLY the JSON array, no markdown, no explanation"
)


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return raw


def gloss_sentence(client, model: str, sentence: str) -> Optional[list[list[str]]]:
    """Word rows for one sentence, or None if the reply wasn't a valid JSON array."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sentence},
        ],
        temperature=0,
    )
    try:
        glosses = json.loads(_strip_code_fence(response.choices[0].message.content))
    except json.JSONDecodeError:
        return None
    if not isinstance(glosses, list):
        return None
    return [
        [str(g.get("chinese", "")), str(g.get("pinyin", "")), str(g.get("english", ""))]
        for g in glosses
        if isinstance(g, dict)
    ]


def openai_text_to_rows(
    text: str,
    client,
    cedict: dict,
    model: str = DEFAULT_MODEL,
    max_workers: int = 8,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[list[str]], int]:
    """Same table as chinese_csv.chinese_text_to_rows, glossed by OpenAI.

    Sentences are sent in parallel (max_workers at a time) so a long text
    doesn't take one round-trip per sentence. A sentence whose reply can't
    be parsed falls back to the local dictionary gloss; the second return
    value counts those fallbacks."""
    sentences = split_sentences(text)
    if not sentences:
        return [], 0

    # progress is reported from this (the caller's) thread as futures finish,
    # not from the workers -- Streamlit can only update the page from its
    # own script thread
    results: list = [None] * len(sentences)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(gloss_sentence, client, model, s): i for i, s in enumerate(sentences)}
        for done, future in enumerate(as_completed(futures), 1):
            results[futures[future]] = future.result()
            if on_progress:
                on_progress(done, len(sentences))

    rows = [["Chinese", "Pinyin", "English meaning"]]
    fallbacks = 0
    for i, (sentence, word_rows) in enumerate(zip(sentences, results), 1):
        rows.append([f"Dialogue {i}", "", ""])
        rows.append([sentence, "", ""])
        if word_rows is None:
            fallbacks += 1
            # local gloss of just this sentence; [3:] drops its own header,
            # "Dialogue 1" and sentence rows, already added above
            word_rows = chinese_text_to_rows(sentence, cedict, 1)[3:]
        rows.extend(word_rows)
    return rows, fallbacks
