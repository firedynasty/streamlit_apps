"""
cefr_loader.py

Loads the CEFR-J (A1-B2) + Octanove C1/C2 extension wordlists into a
single lemma -> level lookup table, and exposes a level() function that
takes a raw token + spaCy POS tag and returns the CEFR level (or None
if the word isn't in either list).

Data sources (both from openlanguageprofiles/olp-en-cefrj on GitHub):
  - cefrj-vocabulary-profile-1.5.csv        (A1-B2, ~7.8k rows)
  - octanove-vocabulary-profile-c1c2-1.0.csv (C1-C2, ~2.1k rows)

Usage:
    from cefr_loader import CEFRWordlist
    wl = CEFRWordlist()
    wl.level("purchase", "VERB")   -> "B1"
    wl.level("purchased", "VERB")  -> "B1"   (via spaCy lemmatization upstream)
"""

import csv
import os
from collections import defaultdict

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}

# Maps spaCy's universal POS tags -> the POS strings used in the CEFR-J /
# Octanove CSVs. Several spaCy tags collapse onto the same wordlist POS
# (e.g. AUX and VERB both -> "verb").
SPACY_POS_TO_CEFR_POS = {
    "NOUN": "noun",
    "PROPN": "noun",
    "VERB": "verb",
    "AUX": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
    "ADP": "preposition",
    "CCONJ": "conjunction",
    "SCONJ": "conjunction",
    "DET": "determiner",
    "PRON": "pronoun",
    "NUM": "number",
    "INTJ": "interjection",
    "PART": None,  # particles ("to", "'s", "not") aren't leveled words
}

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE_CSV = os.path.join(_THIS_DIR, "cefrj-vocabulary-profile-1.5.csv")
DEFAULT_C1C2_CSV = os.path.join(_THIS_DIR, "octanove-vocabulary-profile-c1c2-1.0.csv")


class CEFRWordlist:
    def __init__(self, base_csv=DEFAULT_BASE_CSV, c1c2_csv=DEFAULT_C1C2_CSV):
        # lemma -> {pos: level}   (a lemma can have different levels per POS,
        # e.g. "access" noun=B1, verb=B2)
        self._by_lemma_pos = defaultdict(dict)
        # lemma -> lowest level seen across all POS, for POS-agnostic fallback
        self._by_lemma_any = {}

        self._load_csv(base_csv, notes_col=False)
        self._load_csv(c1c2_csv, notes_col=True)

    def _load_csv(self, path, notes_col):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"CEFR wordlist not found at {path}. "
                "Download it from https://github.com/openlanguageprofiles/olp-en-cefrj"
            )
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = (row.get("headword") or "").strip().lower()
                pos = (row.get("pos") or "").strip().lower()
                level = (row.get("CEFR") or "").strip().upper()
                if not headword or level not in LEVEL_RANK:
                    continue
                # normalize the "vern" typo present in the C1/C2 source file
                if pos == "vern":
                    pos = "verb"
                # a headword like "a.m./A.M./am/AM" packs multiple surface
                # forms into one row - split and register each
                for form in headword.split("/"):
                    form = form.strip()
                    if not form:
                        continue
                    self._register(form, pos, level)

    def _register(self, lemma, pos, level):
        existing = self._by_lemma_pos[lemma].get(pos)
        if existing is None or LEVEL_RANK[level] < LEVEL_RANK[existing]:
            self._by_lemma_pos[lemma][pos] = level

        current_any = self._by_lemma_any.get(lemma)
        if current_any is None or LEVEL_RANK[level] < LEVEL_RANK[current_any]:
            self._by_lemma_any[lemma] = level

    def level(self, lemma, spacy_pos=None):
        """
        Look up the CEFR level for a lemma (lowercased word stem).
        spacy_pos: a spaCy universal POS tag string (e.g. "VERB", "NOUN").
        Falls back to the lowest known level across all POS if the
        specific POS isn't found, then to None if the lemma is unknown.
        """
        lemma = lemma.lower()
        pos_entries = self._by_lemma_pos.get(lemma)
        if pos_entries:
            cefr_pos = SPACY_POS_TO_CEFR_POS.get(spacy_pos) if spacy_pos else None
            if cefr_pos and cefr_pos in pos_entries:
                return pos_entries[cefr_pos]
            # POS unknown/unmatched -> lowest level for this lemma
            return min(pos_entries.values(), key=lambda l: LEVEL_RANK[l])
        return self._by_lemma_any.get(lemma)  # None if truly unknown

    def rank(self, level):
        """A1=0 ... C2=5, for numeric comparison against a target level."""
        return LEVEL_RANK.get(level)

    def entries(self):
        """{lemma: {pos: level}} for every registered headword (a copy)."""
        return {lemma: dict(pos) for lemma, pos in self._by_lemma_pos.items()}

    def stats(self):
        from collections import Counter
        c = Counter(self._by_lemma_any.values())
        return {"total_lemmas": len(self._by_lemma_any), "by_level": dict(c)}


if __name__ == "__main__":
    wl = CEFRWordlist()
    print("Loaded wordlist stats:", wl.stats())
    tests = [
        ("purchase", "VERB"),
        ("access", "NOUN"),
        ("access", "VERB"),
        ("rebellious", "ADJ"),
        ("resistant", "ADJ"),
        ("stubborn", "ADJ"),
        ("mercy", "NOUN"),
        ("grace", "NOUN"),
        ("gibberishword", "NOUN"),
    ]
    print()
    for lemma, pos in tests:
        print(f"{lemma:15s} ({pos:6s}) -> {wl.level(lemma, pos)}")
