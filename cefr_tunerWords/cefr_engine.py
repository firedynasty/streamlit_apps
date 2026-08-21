"""
cefr_engine.py

Deterministic (no-AI) CEFR text tuner. Instead of an LLM, it uses:
  - the CEFR-J + Octanove graded wordlists (via cefr_loader.CEFRWordlist)
    to decide which words are above the target level,
  - WordNet (via NLTK) to find easier synonyms for out-of-level words,
  - lemminflect to match the replacement's grammatical form to the
    original token (e.g. "purchased" -> "bought", not "buy"),
  - spaCy for sentence segmentation, POS tagging and lemmatization.

Long sentences are additionally split at coordinating conjunctions
("and/but/so/or") and subordinators ("because/when/if/...") when both
halves are long enough to stand alone.

The tuner only simplifies DOWNWARD. Targeting C1/C2 on easy text will
return everything unchanged.

Usage:
    from cefr_engine import WordlistTuner
    tuner = WordlistTuner()                    # loads wordlist + spaCy once
    segments, stats = tuner.tune(text, "A2")
    # segments -> same dict shape the AI engine returns
    #   {"original": ..., "simplified": ..., "type": "simplified"|"unchanged"}
    # stats   -> {"unreplaced": [words still above level, ...]}
"""

import spacy
from functools import lru_cache

from cefr_loader import CEFRWordlist, LEVEL_RANK

# NLTK (wordnet) and lemminflect are imported lazily inside the methods that
# use them, so cefr_json_engine.JsonTuner can subclass WordlistTuner in
# environments where those packages aren't installed (e.g. Streamlit Cloud
# running off the precomputed cefr_data.json).

# Only content words are candidates for replacement. PROPN is deliberately
# excluded so names (God, Jerusalem, Paul) are never swapped out.
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
# WordNet POS constants as plain strings (wn.NOUN == "n", etc.) so this
# module doesn't need nltk imported at load time.
WN_POS = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r"}

# Max words per sentence before we try to split it, per target level.
MAX_SENT_WORDS = {
    "A1": 10, "A2": 13, "B1": 17, "B2": 22, "C1": 28, "C2": 10_000,
}

SPLIT_COORD = {"and", "but", "so", "or"}
SPLIT_SUBORD = {
    "because", "when", "if", "although", "though", "while",
    "after", "before", "since", "unless", "as",
}

MIN_CLAUSE_WORDS = 4   # never split off a fragment shorter than this
MAX_SPLITS = 3         # cap splits per sentence


@lru_cache(maxsize=None)
def _sense_count(cand, wnpos):
    """Total WordNet count for a candidate across all its synsets of one POS
    (a frequency proxy). Cached — the build script hammers this."""
    from nltk.corpus import wordnet as wn
    return sum(
        l.count()
        for s in wn.synsets(cand, pos=wnpos)
        for l in s.lemmas()
        if l.name().lower() == cand
    )


@lru_cache(maxsize=None)
def _lemma_index(wnpos):
    """All real WordNet lemmas for a POS. Used to reject garbage lookups:
    spaCy occasionally mis-lemmatizes ("cross" NNS -> "cros"), and
    wn.synsets() silently morphy-falls back ("cros" -> "CRO" ->
    oscilloscope!), producing absurd replacements ("cross" -> "scopes")."""
    from nltk.corpus import wordnet as wn
    return {name.lower() for name in wn.all_lemma_names(pos=wnpos)}

# Curated swaps for common words where WordNet ranking picks a wrong-sense
# synonym ("evil" -> "dark"/"black" via the sinister satellite, when "bad"
# is obviously right). WordNet can't separate these by frequency — dark
# outranks bad — so the few worst offenders are pinned by hand.
HAND_OVERRIDES = {
    "evil": "bad",
    "wicked": "bad",
    "wickedness": "evil",
}


class WordlistTuner:
    def __init__(self, wordlist=None, nlp=None, max_synsets=2):
        self.wl = wordlist or CEFRWordlist()
        self.nlp = nlp or spacy.load("en_core_web_sm")
        # Only the first N synsets (most frequent senses) are used for
        # synonym candidates — deeper synsets drift off-meaning.
        self.max_synsets = max_synsets

    # ── level checks ─────────────────────────────────────────────────────

    def is_hard(self, token, target_rank):
        """True if the token is a content word above the target level."""
        if token.pos_ not in CONTENT_POS or not token.is_alpha:
            return False
        if len(token.text) < 3:
            return False
        lvl = self.wl.level(token.lemma_, token.pos_)
        if lvl is None:
            # Not in any list -> rare/unknown word, treat as above level.
            return True
        return LEVEL_RANK[lvl] > target_rank

    # ── replacement ──────────────────────────────────────────────────────

    def find_replacement(self, token, target_rank):
        """
        Best easier synonym for a hard token, or None.
        Participles (VBN/VBG) often carry an adjectival sense ("exhausted"
        = tired), so adjective synsets are searched first for those,
        under both the lemma and the raw token text (WordNet lists the
        adjective under "exhausted", not "exhaust") — otherwise verb
        sense drift produces "exhausted" -> "eaten".
        """
        lemma = token.lemma_.lower()

        override = HAND_OVERRIDES.get(lemma)
        if override:
            lvl = self.wl.level(override, token.pos_)
            if lvl is not None and LEVEL_RANK[lvl] <= target_rank:
                return override, None

        search = []  # (wnpos, lookup_word)
        if token.pos_ in WN_POS:
            search.append((WN_POS[token.pos_], lemma))
        if token.tag_ in ("VBN", "VBG", "JJ", "JJR", "JJS"):
            adj_lookups = [token.text.lower()] if token.text.lower() != lemma else []
            adj_lookups.append(lemma)
            search = [("a", w) for w in adj_lookups] + [
                (p, w) for p, w in search if p != "a"
            ]
        for wnpos, word in search:
            hit = self._candidates(word, token.pos_, wnpos, target_rank)
            if hit:
                return hit, wnpos
        return None

    def _candidates(self, lookup, spacy_pos, wnpos, target_rank):
        """
        Level-acceptable synonyms for one lookup word. Direct synset
        synonyms win first; for adjectives, the linked head synsets
        (similar_tos) are tried next — satellites carry no direct
        synonyms, so the natural easy swap (evil -> bad) lives there.
        Within each pool, most sense-attested overall wins (by total
        WordNet lemma count across the candidate's synsets).
        """
        from nltk.corpus import wordnet as wn
        if lookup not in _lemma_index(wnpos):
            return None
        for syn in wn.synsets(lookup, pos=wnpos)[: self.max_synsets]:
            pools = [self._pool([syn], lookup, spacy_pos, target_rank)]
            if wnpos == wn.ADJ:
                pools.append(
                    self._pool(syn.similar_tos(), lookup, spacy_pos, target_rank)
                )
            for pool in pools:
                if pool:
                    return max(pool, key=lambda c: c[0])[1]
        return None

    def _pool(self, synsets, lookup, spacy_pos, target_rank):
        pool = []
        for syn in synsets:
            for lem in syn.lemmas():
                cand = lem.name().lower()
                if cand == lookup or "_" in cand or not cand.isalpha():
                    continue
                lvl = self.wl.level(cand, spacy_pos)
                if lvl is None or LEVEL_RANK[lvl] > target_rank:
                    continue
                pool.append((_sense_count(cand, WN_POS[spacy_pos]), cand))
        return pool

    @staticmethod
    def inflect_like(token, candidate_lemma, should_inflect):
        """
        Match the replacement to the original token's morphology.
        "purchased" (VBD) + "buy" -> "bought"; "apples" (NNS) + "fruit" -> "fruits".
        Only same-POS noun/verb candidates inflect — an adjective found for a
        participle slot ("exhausted" -> "tired") stays as-is, otherwise
        lemminflect over-generates "tireded".
        """
        forms = ()
        if should_inflect:
            from lemminflect import getInflection
            forms = getInflection(candidate_lemma, token.tag_)
        form = forms[0] if forms else candidate_lemma
        if token.text[:1].isupper():
            form = form.capitalize()
        return form

    def simplify_sentence(self, sent, target_rank):
        """
        Replace out-of-level words in one sentence via offset splicing
        (preserves original spacing/punctuation). Returns
        (new_text, unreplaced_words).
        """
        text = sent.text
        edits = []   # (start, end, replacement) offsets relative to sent
        unreplaced = []

        for token in sent:
            if not self.is_hard(token, target_rank):
                continue
            found = self.find_replacement(token, target_rank)
            if found is None:
                unreplaced.append(token.text)
                continue
            cand, source_pos = found
            same_pos = source_pos is not None and source_pos == WN_POS.get(token.pos_)
            should_inflect = same_pos and source_pos in ("n", "v")
            form = self.inflect_like(token, cand, should_inflect)
            if form.lower() == token.text.lower():
                continue
            start = token.idx - sent.start_char
            edits.append((start, start + len(token.text), form))

        for start, end, form in sorted(edits, reverse=True):
            text = text[:start] + form + text[end:]

        # fix a/an agreement introduced by vowel-initial replacements
        text = _fix_articles(text)
        return text, unreplaced

    # ── sentence splitting ───────────────────────────────────────────────

    def split_long_sentence(self, text, target_level):
        """
        Split an over-long simplified sentence at a conjunction, provided
        both halves can stand alone (each has a finite verb and enough
        words). Returns a list of 1+ sentences.
        """
        max_words = MAX_SENT_WORDS[target_level]
        parts = [text]
        splits_done = 0
        i = 0
        while i < len(parts) and splits_done < MAX_SPLITS:
            part = parts[i]
            doc = self.nlp(part)
            words = [t for t in doc if t.is_alpha]
            if len(words) <= max_words:
                i += 1
                continue
            cut = self._find_split_point(doc)
            if cut is None:
                i += 1
                continue
            left, right = part[:cut].rstrip(" ,;:"), part[cut:].lstrip(" ,")
            if not left.endswith((".", "!", "?", '"')):
                left += "."
            right = right[:1].upper() + right[1:]
            parts[i : i + 1] = [left, right]
            splits_done += 1
            # re-examine the same index (now the left half) before moving on
        return parts

    @staticmethod
    def _find_split_point(doc):
        """Char offset of the first good split token, or None."""
        for token in doc:
            if token.i == 0:
                continue  # never split before the first token
            lower = token.lower_
            # POS guards keep noun-sense "while" ("for a while"), adverbial
            # "when", intensifier "so", etc. from triggering splits
            is_coord = lower in SPLIT_COORD and token.pos_ == "CCONJ"
            is_subord = lower in SPLIT_SUBORD and token.pos_ == "SCONJ"
            if not (is_coord or is_subord):
                continue
            left = doc[: token.i]
            right = doc[token.i + 1 :]
            left_words = [t for t in left if t.is_alpha]
            right_words = [t for t in right if t.is_alpha]
            if len(left_words) < MIN_CLAUSE_WORDS or len(right_words) < MIN_CLAUSE_WORDS:
                continue
            if is_coord:
                # only split between real clauses: each side needs a verb,
                # and the right side needs its own subject before that verb
                # (blocks "they thought | or imagined", where the right
                # side is just a conjoined verb phrase)
                if not any(t.pos_ in ("VERB", "AUX") for t in left):
                    continue
                right_verb_pos = next(
                    (j for j, t in enumerate(right) if t.pos_ in ("VERB", "AUX")),
                    None,
                )
                if right_verb_pos is None:
                    continue
                has_subject = any(
                    t.pos_ in ("NOUN", "PROPN", "PRON")
                    for t in right[:right_verb_pos]
                )
                if not has_subject:
                    continue
            return token.idx - doc[0].idx
        return None

    # ── public API ───────────────────────────────────────────────────────

    def tune(self, text, target_level):
        """
        Returns (segments, stats). Segment dicts match the AI engine's
        shape so render_tree() works unchanged. "dropped" is never
        produced — deterministic dropping is too risky.
        """
        target_rank = LEVEL_RANK[target_level]
        doc = self.nlp(text.strip())
        segments = []
        unreplaced_all = []

        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            hard = [t for t in sent if self.is_hard(t, target_rank)]
            too_long = len(words) > MAX_SENT_WORDS[target_level]

            if not hard and not too_long:
                segments.append({
                    "original": sent.text,
                    "simplified": sent.text,
                    "type": "unchanged",
                })
                continue

            new_text, unreplaced = self.simplify_sentence(sent, target_rank)
            parts = self.split_long_sentence(new_text, target_level)
            simplified = " ".join(parts)
            unreplaced_all.extend(unreplaced)

            seg_type = "simplified" if simplified != sent.text else "unchanged"
            segments.append({
                "original": sent.text,
                "simplified": simplified,
                "type": seg_type,
            })

        return segments, {"unreplaced": unreplaced_all}


def _fix_articles(text):
    """'a' -> 'an' before vowel-initial words (cheap post-replacement fix)."""
    out = []
    tokens = text.split(" ")
    for i, tok in enumerate(tokens):
        if tok.lower() == "a" and i + 1 < len(tokens):
            nxt = tokens[i + 1].lstrip('"\'(')
            if nxt[:1].lower() in "aeiou":
                tok = "An" if tok[:1].isupper() else "an"
        out.append(tok)
    return " ".join(out)


if __name__ == "__main__":
    tuner = WordlistTuner()
    sample = (
        "The Lord observed the extent of human wickedness on the earth, "
        "and he saw that everything they thought or imagined was consistently "
        "and totally evil. It grieved him deeply, so he decided to eliminate "
        "the people he had created, but Noah found favor in the eyes of the Lord."
    )
    for level in ("A1", "A2", "B1"):
        print(f"\n=== target {level} ===")
        segs, stats = tuner.tune(sample, level)
        for s in segs:
            print(f"[{s['type']}] {s['simplified']}")
            if s["type"] == "simplified":
                print(f"    ↳ {s['original']}")
        if stats["unreplaced"]:
            print("unreplaced:", ", ".join(stats["unreplaced"]))
