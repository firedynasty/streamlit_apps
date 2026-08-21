"""
cefr_json_engine.py

Runtime engine that serves the CEFR tuner from the precomputed
cefr_data.json (built by build_cefr_data.py) instead of consulting
WordNet/lemminflect live. Only spaCy is needed (tagging, lemmatization,
sentence splitting) — which is what makes the app deployable without the
nltk/lemminflect packages.

JsonTuner subclasses WordlistTuner and inherits everything except the
synonym lookup: is_hard, simplify_sentence (offset splicing, a/an fix),
sentence splitting, and tune() are unchanged. Replacements come from three
tables baked at build time:

  levels     lemma -> {cefr_pos: level}          (same semantics as CEFRWordlist)
  repl       "lemma|SPACYPOS|level" -> easier synonym lemma
  repl_part  "participle-surface|level" -> adjective-sense replacement,
             used as-is ("exhausted" -> "tired", never "tireded")
  forms      replacement lemma -> {tag: inflected form} for noun/verb swaps
             ("buy" -> VBD "bought")

Usage:
    import json
    from cefr_json_engine import JsonTuner
    tuner = JsonTuner(json.load(open("cefr_data.json")))
    segments, stats = tuner.tune(text, "A2")
"""

from cefr_loader import LEVEL_ORDER, LEVEL_RANK, SPACY_POS_TO_CEFR_POS
from cefr_engine import WordlistTuner


class JsonWordlist:
    """Duck-typed drop-in for CEFRWordlist, backed by the JSON levels table."""

    def __init__(self, levels):
        self._levels = levels

    def level(self, lemma, spacy_pos=None):
        lemma = lemma.lower()
        pos_entries = self._levels.get(lemma)
        if not pos_entries:
            return None
        cefr_pos = SPACY_POS_TO_CEFR_POS.get(spacy_pos) if spacy_pos else None
        if cefr_pos and cefr_pos in pos_entries:
            return pos_entries[cefr_pos]
        # POS unknown/unmatched -> lowest level for this lemma
        return min(pos_entries.values(), key=lambda l: LEVEL_RANK[l])


class JsonTuner(WordlistTuner):
    def __init__(self, data, nlp=None):
        super().__init__(wordlist=JsonWordlist(data["levels"]), nlp=nlp)
        self._repl = data["repl"]
        self._repl_part = data["repl_part"]
        self._forms = data["forms"]

    def find_replacement(self, token, target_rank):
        """
        Returns (final_form, None) — the form is already inflected here
        (via the forms table), so the caller's inflect_like becomes a
        capitalization-only no-op. None means no easier replacement exists.
        """
        lvl = LEVEL_ORDER[target_rank]

        # participle with an adjectival sense: used as-is
        if token.tag_ in ("VBN", "VBG"):
            part = self._repl_part.get(f"{token.text.lower()}|{lvl}")
            if part:
                return part, None

        cand = self._repl.get(f"{token.lemma_.lower()}|{token.pos_}|{lvl}")
        if cand is None:
            return None
        form = self._forms.get(cand, {}).get(token.tag_, cand)
        return form, None
