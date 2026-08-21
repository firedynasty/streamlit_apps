"""
build_cefr_data.py

Build-time script: bakes everything the CEFR tuner needs at runtime into a
single cefr_data.json, so the deployed app doesn't need NLTK/WordNet or
lemminflect installed — only spaCy (for tagging/sentences) plus this file.

Output structure:
  {
    "levels":    {"purchase": {"verb": "B1", "noun": "B1"}, ...},
    "repl":      {"purchase|VERB|A1": "buy", ...},       # base-tag lookups
    "repl_part": {"exhausted|A2": "tired", ...},         # participle surface
                                                         # forms w/ adjective
                                                         # sense (used as-is)
    "forms":     {"buy": {"VBD": "bought", "VBG": "buying", ...}, ...}
  }

Replacements are computed by running the real WordNet engine
(cefr_engine.WordlistTuner.find_replacement) over every (lemma, POS, target
level) where the word would be "hard", so HAND_OVERRIDES and all ranking
logic are baked in exactly. Inflected forms come from lemminflect.

Build-only requirements (not needed at runtime): nltk + wordnet corpus,
lemminflect. Run from this directory:

    python build_cefr_data.py
"""

import json
import os
from types import SimpleNamespace

import spacy
from lemminflect import getInflection

from cefr_loader import CEFRWordlist, LEVEL_ORDER, LEVEL_RANK
from cefr_engine import WordlistTuner

CEFR_POS_TO_SPACY = {"noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADV"}
BASE_TAG = {"NOUN": "NN", "VERB": "VB", "ADJ": "JJ", "ADV": "RB"}
VERB_TAGS = ("VB", "VBP", "VBZ", "VBD", "VBG", "VBN")

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cefr_data.json")


def fake_token(lemma, spacy_pos, tag, text=None):
    """Just the attributes find_replacement touches: lemma_/pos_/tag_/text."""
    return SimpleNamespace(
        lemma_=lemma, pos_=spacy_pos, tag_=tag, text=text or lemma
    )


def main():
    from nltk.corpus import wordnet as wn

    wl = CEFRWordlist()
    nlp = spacy.load("en_core_web_sm")
    tuner = WordlistTuner(wordlist=wl, nlp=nlp)

    levels = wl.entries()
    repl = {}
    repl_part = {}
    forms_needed = set()  # (replacement lemma, source wnpos) for inflection

    # The universe of possibly-replaceable words is every WordNet content
    # lemma, not just wordlist entries: words MISSING from the wordlist
    # ("wickedness", "precept") are treated as above-level at runtime, and
    # the engine still swaps them when WordNet offers an in-list synonym.
    content_lemmas = set()
    for wnpos in ("n", "v", "a", "r"):
        for name in wn.all_lemma_names(pos=wnpos):
            if name.isalpha():
                content_lemmas.add(name.lower())

    for lemma in sorted(content_lemmas):
        for spacy_pos, wnpos in (
            ("NOUN", "n"), ("VERB", "v"), ("ADJ", "a"), ("ADV", "r"),
        ):
            if not wn.synsets(lemma, pos=wnpos):
                continue
            word_level = wl.level(lemma, spacy_pos)
            # known words are only "hard" below their own level; unknown
            # words (None) are treated as hard at every level
            targets = (
                range(len(LEVEL_ORDER))
                if word_level is None
                else range(LEVEL_RANK[word_level])
            )
            for target_rank in targets:
                lvl = LEVEL_ORDER[target_rank]

                res = tuner.find_replacement(
                    fake_token(lemma, spacy_pos, BASE_TAG[spacy_pos]), target_rank
                )
                if res:
                    cand, source = res
                    repl[f"{lemma}|{spacy_pos}|{lvl}"] = cand
                    if source in ("n", "v"):
                        forms_needed.add((cand, source))

                # participles take the adjective-sense path in the engine
                # ("exhausted" -> "tired"); keyed by surface form, used as-is
                if spacy_pos == "VERB":
                    for tag in ("VBN", "VBG"):
                        surf = getInflection(lemma, tag)
                        if not surf:
                            continue
                        surface = surf[0].lower()
                        res = tuner.find_replacement(
                            fake_token(lemma, spacy_pos, tag, text=surface),
                            target_rank,
                        )
                        if res and res[1] == "a":
                            repl_part[f"{surface}|{lvl}"] = res[0]

    forms = {}
    for cand, source in sorted(forms_needed):
        tags = VERB_TAGS if source == "v" else ("NNS",)
        for tag in tags:
            f = getInflection(cand, tag)
            if f and f[0] != cand:
                forms.setdefault(cand, {})[tag] = f[0]

    data = {
        "levels": levels,
        "repl": dict(sorted(repl.items())),
        "repl_part": dict(sorted(repl_part.items())),
        "forms": dict(sorted(forms.items())),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"wrote {OUT_PATH}")
    print(
        f"lemmas={len(levels)}  repl={len(repl)}  "
        f"repl_part={len(repl_part)}  forms={len(forms)}  size={size_kb:.0f} KB"
    )


if __name__ == "__main__":
    main()
