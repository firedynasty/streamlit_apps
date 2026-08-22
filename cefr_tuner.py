"""
CEFR Text Tuner
Uses structured LLM alignment. Output renders as a bullet tree:
  • simplified sentence
      ↳ original sentence (indented, grayed)
Dropped content shows as struck-through in the original.
"""

import streamlit as st
import json
import os
import sys
import re
import html

# cefr_tunerWords/ holds the offline engine + graded wordlists
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cefr_tunerWords")
)

st.set_page_config(page_title="CEFR Text Tuner", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    "<style>[data-testid='collapsedControl'] { display: none; }</style>",
    unsafe_allow_html=True,
)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert ESL (English as a Second Language) editor.
Rewrite the user's text to exactly match the requested CEFR level.

Break the original text into logical clauses or phrases. For each, produce an alignment object.

Segment types:
- "simplified" — clause was rewritten (vocabulary, length, or grammar changed)
- "unchanged"  — clause kept exactly as-is
- "dropped"    — clause removed entirely (simplified is null)

You may merge multiple original clauses into one simplified clause.
If you do, put all merged original text in the "original" field (joined with " / ").

CEFR level rules:
- A1/A2 — simple present/past tenses, most common 1,000 words only, very short sentences.
- B1/B2 — moderate sentence lengths, clear transitions, common 4,000 words.
- C1/C2 — complex clause structures, academic/technical vocabulary, native idioms.

Return ONLY a valid JSON object with a "segments" array. No markdown, no explanation.

Required output format:
{
  "segments": [
    {"original": "<original clause>", "simplified": "<rewritten clause>", "type": "simplified"},
    {"original": "<original clause>", "simplified": "<same text>",         "type": "unchanged"},
    {"original": "<dropped clause>",  "simplified": null,                  "type": "dropped"}
  ]
}"""

# ── CEFR metadata ─────────────────────────────────────────────────────────────

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

CEFR_DESCRIPTIONS = {
    "A1": "Beginner — very simple words, very short sentences",
    "A2": "Elementary — basic everyday expressions and familiar topics",
    "B1": "Intermediate — clear standard language on familiar subjects",
    "B2": "Upper-Intermediate — complex texts, abstract topics",
    "C1": "Advanced — fluent, flexible, sophisticated use of language",
    "C2": "Mastery — native-like precision and full nuance",
}

# ── CSS for bullet tree ───────────────────────────────────────────────────────

TREE_CSS = """
<style>
ul.cefr-tree, ul.cefr-tree ul {
  list-style: none;
  margin: 0;
  padding-left: 0;
}
ul.cefr-tree ul {
  padding-left: 22px;
  margin: 2px 0 8px;
}
ul.cefr-tree > li {
  position: relative;
  padding-left: 18px;
  margin: 10px 0;
  line-height: 1.65;
  font-size: 1em;   /* scales with the container's font-size */
}
ul.cefr-tree > li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.68em;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #5580cc;
}
ul.cefr-tree > li.unchanged::before {
  background: #b9b2a2;
}
ul.cefr-tree > li.dropped-li {
  color: #c0392b;
  text-decoration: line-through;
}
ul.cefr-tree > li.dropped-li::before {
  background: #e8a0a0;
}
ul.cefr-tree ul li {
  position: relative;
  padding-left: 16px;
  margin: 2px 0;
  color: #888;
  font-style: italic;
  font-size: 0.92em;
  line-height: 1.55;
}
ul.cefr-tree ul li::before {
  content: "↳";
  position: absolute;
  left: 0;
  color: #bbb;
  font-style: normal;
}
ul.cefr-tree span.original {
  color: #5580cc;
}
/* Clickable hard words — the handler in _TOOLTIP_JS looks up data-w on
   Datamuse. .unrep = no replacement found (underline + *), .replaced =
   engine swapped it (underline only, gloss follows in parentheses). */
ul.cefr-tree .unrep,
ul.cefr-tree .replaced {
  text-decoration: underline;
  text-decoration-color: #5580cc;
  text-underline-offset: 3px;
  cursor: pointer;
}
ul.cefr-tree sup.unrep-mark {
  color: #5580cc;
  font-size: 0.62em;
  margin-left: 1px;
}
</style>
"""

BOX_STYLE = (
    "border:1px solid #e0e0e0;"
    "border-radius:8px;"
    "padding:16px 20px;"
    "min-height:220px;"
)

# ── Rendering ─────────────────────────────────────────────────────────────────

def _mark_unreplaced(text: str, unreplaced: frozenset) -> str:
    """Wrap whole-word occurrences of unreplaced words in ⟦ ⟧ markers.
    Sentinel chunks («...») are split out first so replaced words and their
    glosses are never marked. Markers are converted to HTML after escaping."""
    parts = re.split(r"(«[^|»]*\|[^»]*»)", text)
    marked = []
    for part in parts:
        if part.startswith("«"):
            marked.append(part)
            continue
        marked.append(re.sub(
            r"[A-Za-z]+",
            lambda m: f"⟦{m.group(0)}⟧" if m.group(0).lower() in unreplaced else m.group(0),
            part,
        ))
    return "".join(marked)


def _escape_simplified(text: str, unreplaced: frozenset = frozenset()) -> str:
    """Escape, mark unreplaced words, then convert «new|orig» sentinels into:
    new (orig) with (orig) in blue."""
    if unreplaced:
        text = _mark_unreplaced(text, unreplaced)
    escaped = html.escape(text)
    def _sub(m: re.Match) -> str:
        new_word = m.group(1)
        orig_word = m.group(2)
        # Underline the ORIGINAL hard word and make it the tooltip trigger —
        # lookups run on it, not on the gloss (alternatives to the easy word
        # drift away from the sentence's meaning).
        return (f'<span class="replaced" data-w="{orig_word.lower()}">{orig_word}</span> '
                f'<span class="original">({new_word})</span>')
    out = re.sub(r"«([^|»]+)\|([^»]+)»", _sub, escaped)
    return re.sub(
        r"⟦([^⟧]+)⟧",
        lambda m: (
            f'<span class="unrep" data-w="{m.group(1).lower()}">{m.group(1)}</span>'
            f'<sup class="unrep-mark">*</sup>'
        ),
        out,
    )


def render_tree(segments: list, font_px: int = 24, unreplaced: frozenset = frozenset()) -> str:
    """
    Bullet tree:
      • simplified text          (blue dot)
          ↳ original text        (indented, gray italic)
      • unchanged text           (gray dot, no sub-bullet)
      • ~~dropped original~~     (red strikethrough, no sub-bullet)
    font_px scales the whole tree (inner sizes are em-based).
    unreplaced (lowercased word set) marks still-hard words with a blue
    underline + superscript *.
    """
    items = []
    for seg in segments:
        seg_type = seg.get("type", "unchanged")
        simplified = (seg.get("simplified") or "").strip()
        original   = html.escape((seg.get("original") or "").strip())

        if seg_type == "dropped":
            items.append(f'<li class="dropped-li">{original}</li>')

        elif seg_type == "simplified":
            items.append(
                f'<li>{_escape_simplified(simplified, unreplaced)}</li>'
            )

        else:  # unchanged — no sub-bullet needed
            items.append(f'<li class="unchanged">{_escape_simplified(simplified, unreplaced)}</li>')

    inner = "\n".join(items)
    return (
        f'{TREE_CSS}<div style="{BOX_STYLE}font-size:{font_px}px;">'
        f'<ul class="cefr-tree">{inner}</ul></div>'
    )


def _bump_font(delta: int):
    st.session_state.font_px = min(24, max(11, st.session_state.font_px + delta))


# ── Sidebar ───────────────────────────────────────────────────────────────────

@st.cache_resource
def load_wordlist_tuner():
    """Load the precomputed cefr_data.json (local file first, then the
    CEFR_DATA_URL env var — e.g. a Dropbox ?raw=1 link) and build the
    engine. No NLTK/WordNet/lemminflect needed at runtime."""
    import requests
    from cefr_json_engine import JsonTuner

    local = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "cefr_tunerWords", "cefr_data.json",
    )
    if os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            data = json.load(f)
    else:
        url = os.getenv("CEFR_DATA_URL", "")
        if not url:
            raise FileNotFoundError(
                "cefr_data.json not found locally, and CEFR_DATA_URL is not set."
            )
        data = requests.get(url, timeout=30).json()
    return JsonTuner(data)

_env_key = os.getenv("OPENAI_API_KEY", "")

with st.sidebar:
    st.header("Settings")

    st.subheader("Engine")
    engine = st.radio(
        "engine",
        ["Wordlist (no AI)", "OpenAI"],
        index=0,
        label_visibility="collapsed",
    )
    if engine == "Wordlist (no AI)":
        st.caption(
            "Offline: swaps above-level words for easier synonyms and splits "
            "long sentences. Simplifies downward only — it can't make easy "
            "text more advanced."
        )
        api_key = None
    else:
        if _env_key:
            st.success("OpenAI API key loaded from environment.")
            api_key = _env_key
        else:
            api_key = st.text_input("OpenAI API Key:", type="password")

    st.divider()

    st.subheader("Target CEFR Level")
    cefr_level = st.selectbox(
        "level", CEFR_LEVELS, index=2, label_visibility="collapsed"
    )
    st.caption(CEFR_DESCRIPTIONS[cefr_level])

    st.divider()

    st.subheader("Level Reference")
    for lvl, desc in CEFR_DESCRIPTIONS.items():
        _, detail = desc.split(" — ", 1)
        st.markdown(f"**{lvl}** — {detail}")

# ── Main UI ───────────────────────────────────────────────────────────────────

import streamlit.components.v1 as components

st.title("CEFR Text Tuner")
st.caption(
    "Each bullet is the simplified text. "
    "The ↳ line below shows the original phrase it replaced. "
    "Red strikethrough = dropped content."
)

st.subheader("Original Text")
st.session_state.setdefault("font_px", 24)

original_input = st.text_area(
    label="original",
    label_visibility="collapsed",
    height=140,
    placeholder="Paste your text here…",
    key="original_text",
)

# Paste-from-clipboard button. Streamlit's component iframes don't allow
# clipboard-read, so the click handler calls the PARENT page's clipboard API
# (top-level documents aren't under the iframe policy), then writes into the
# streamlit textarea with the native setter + input/blur events so React
# commits the value. Fills the textarea only — never triggers a tune.
_PASTE_HTML = """
<div style="display:flex;align-items:center;height:2.6rem;">
<button id="pbtn" style="width:100%;padding:0.42rem 0;border-radius:8px;
  border:1px solid rgba(49,51,63,0.3);background:transparent;cursor:pointer;
  font-family:sans-serif;font-size:0.95rem;color:#31333F;">Paste</button>
<style>
@media (prefers-color-scheme: dark) {
  #pbtn { color:#FAFAFA; border-color:rgba(250,250,250,0.3); }
}
</style>
</div>
<script>
const btn = document.getElementById('pbtn');
btn.addEventListener('click', async () => {
  try {
    const pwin = window.parent;
    const text = await pwin.navigator.clipboard.readText();
    const ta = pwin.document.querySelector('textarea[aria-label="original"]');
    if (!ta) { btn.textContent = 'No text box found'; return; }
    const setter = Object.getOwnPropertyDescriptor(
      pwin.HTMLTextAreaElement.prototype, 'value').set;
    ta.focus();
    setter.call(ta, text);
    ta.dispatchEvent(new pwin.Event('input', {bubbles: true}));
    ta.blur();  // streamlit commits the textarea value on blur
    btn.textContent = 'Pasted \\u2713';
    setTimeout(() => { btn.textContent = 'Paste'; }, 1500);
  } catch (e) {
    // clipboard read blocked (permission/gesture) — focus the box for Cmd+V
    const ta = window.parent.document.querySelector('textarea[aria-label="original"]');
    if (ta) ta.focus();
    btn.textContent = 'Press \\u2318V / Ctrl+V';
    setTimeout(() => { btn.textContent = 'Paste'; }, 2500);
  }
});
</script>
"""

col_tune, col_clear, col_paste, _ = st.columns([2, 1, 1, 4])
with col_tune:
    tune_btn = st.button(f"Tune to {cefr_level}", type="primary", use_container_width=True)
with col_clear:
    st.button(
        "Clear",
        use_container_width=True,
        on_click=lambda: st.session_state.update(
            original_text="", segments=None, summary="", note="", unreplaced=[]
        ),
    )
with col_paste:
    components.html(_PASTE_HTML, height=44)

if engine == "OpenAI" and not api_key:
    st.info("Enter your OpenAI API key in the sidebar, or set OPENAI_API_KEY in your shell.")

col_result, col_minus, col_plus = st.columns([6, 1, 1])
with col_result:
    st.subheader(f"Tuned Result — {cefr_level}")
with col_minus:
    st.button("A−", use_container_width=True, help="Smaller text",
              on_click=_bump_font, args=(-1,))
with col_plus:
    st.button("A+", use_container_width=True, help="Larger text",
              on_click=_bump_font, args=(1,))

# Page-down button. The button markup goes into the parent page via
# st.markdown — but <script> inside st.markdown never executes (Streamlit
# inserts it via innerHTML, and scripts injected that way don't run).
# So the click handler is bound separately below, from a same-origin
# component iframe.
st.markdown("""
<div style="position:fixed;bottom:1.4rem;right:1.4rem;z-index:9999;">
<button id="pgdn" title="Page down"
  style="width:2.6rem;height:2.6rem;border-radius:50%;border:1px solid rgba(49,51,63,0.3);
         background:transparent;cursor:pointer;font-size:1.2rem;line-height:1;color:#31333F;">
  &#8595;
</button>
</div>
<style>
@media (prefers-color-scheme: dark) {
  #pgdn { color:#FAFAFA; border-color:rgba(250,250,250,0.3); }
}
</style>
""", unsafe_allow_html=True)

# Bind #pgdn's click handler on the PARENT document, using event delegation
# (delegation survives Streamlit re-rendering the button node on reruns, and
# the __pgdnBound flag prevents double-binding when this iframe re-executes).
_PGDN_JS = """
<script>
const pwin = window.parent;
if (!pwin.__pgdnBound) {
  pwin.__pgdnBound = true;
  pwin.document.addEventListener('click', (e) => {
    const btn = e.target.closest('#pgdn');
    if (!btn) return;
    // Walk up from the button to the container that actually scrolls, so
    // this works regardless of Streamlit's layout version.
    let el = btn.parentElement;
    while (el && el !== pwin.document.body) {
      const s = pwin.getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight) {
        el.scrollBy({top: el.clientHeight * 0.85, behavior: 'smooth'});
        return;
      }
      el = el.parentElement;
    }
    pwin.scrollBy({top: pwin.innerHeight * 0.85, behavior: 'smooth'});
  });
}
</script>
"""
components.html(_PGDN_JS, height=0)

# Synonym tooltip for unreplaced (blue-underlined) words. Fully CLIENT-SIDE:
# the browser fetches api.datamuse.com directly — no Python rerun, no server
# round trip. Bound from this component iframe (scripts in st.markdown don't
# execute) via delegation on the parent document, so it survives reruns.
# Results are cached in a Map on the parent window: repeat clicks are free.
_TOOLTIP_JS = """
<script>
const pwin = window.parent, pdoc = pwin.document;
if (!pwin.__unrepTipBound) {
  pwin.__unrepTipBound = true;
  pwin.__synCache = new Map();  // word -> Promise<string[]>

  const style = pdoc.createElement('style');
  style.textContent = [
    '.unrep-tip{position:fixed;z-index:99999;max-width:320px;background:#fff;',
    'color:#31333F;border:1px solid rgba(49,51,63,.25);border-radius:8px;',
    'padding:8px 12px;font:14px/1.5 sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.15);}',
    '.unrep-tip-body{margin-top:2px;}',
    '.unrep-tip-label{color:#888;font-size:.85em;}',
    '@media (prefers-color-scheme:dark){.unrep-tip{background:#262730;color:#FAFAFA;',
    'border-color:rgba(250,250,250,.25);}}'
  ].join('');
  pdoc.head.appendChild(style);

  let tip = null, reqSeq = 0;
  const hideTip = () => { if (tip) { tip.remove(); tip = null; } };
  const esc = (s) => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  const showTip = (anchor, bodyHtml) => {
    hideTip();
    tip = pdoc.createElement('div');
    tip.className = 'unrep-tip';
    tip.innerHTML = bodyHtml;
    pdoc.body.appendChild(tip);
    const r = anchor.getBoundingClientRect();
    let left = Math.max(8, Math.min(r.left, pwin.innerWidth - tip.offsetWidth - 8));
    let top = r.bottom + 6;
    if (top + tip.offsetHeight > pwin.innerHeight - 8) {
      top = Math.max(8, r.top - tip.offsetHeight - 6);  // flip above the word
    }
    // hard clamp: never render outside the viewport
    top = Math.max(8, Math.min(top, pwin.innerHeight - tip.offsetHeight - 8));
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  };

  const fetchSyns = (word) => {
    if (!pwin.__synCache.has(word)) {
      const w = encodeURIComponent(word);
      const get = (param) => fetch('https://api.datamuse.com/words?' + param + '=' + w + '&max=12')
        .then(r => { if (!r.ok) throw new Error('datamuse ' + r.status); return r.json(); })
        .then(arr => arr.map(o => o.word));
      pwin.__synCache.set(word, Promise.allSettled([get('rel_syn'), get('ml')]).then(results => {
        if (results.every(r => r.status === 'rejected')) throw new Error('datamuse unreachable');
        const syn = results[0].status === 'fulfilled' ? results[0].value : [];
        const ml  = results[1].status === 'fulfilled' ? results[1].value : [];
        return { syn, similar: ml.filter(x => !syn.includes(x)) };  // dedupe overlap
      }));
    }
    return pwin.__synCache.get(word);
  };

  const tipBody = (res) => {
    const parts = [];
    if (res.syn.length)     parts.push('<span class="unrep-tip-label">Synonyms:</span> ' + res.syn.map(esc).join(', '));
    if (res.similar.length) parts.push('<span class="unrep-tip-label">Similar:</span> ' + res.similar.map(esc).join(', '));
    return parts.length ? parts.join('<br>') : 'No synonyms found.';
  };

  pdoc.addEventListener('click', async (e) => {
    const mark = e.target.closest('.unrep-mark');
    const span = e.target.closest('.unrep,.replaced') || (mark && mark.previousElementSibling);
    if (!span || !span.dataset || !span.dataset.w) {
      if (tip && !tip.contains(e.target)) hideTip();  // clicked elsewhere
      return;
    }
    const word = span.dataset.w, seq = ++reqSeq;
    const head = '<b>' + esc(word) + '</b><div class="unrep-tip-body">';
    showTip(span, head + '&hellip;</div>');
    try {
      const res = await fetchSyns(word);
      if (seq !== reqSeq) return;  // user clicked another word meanwhile
      showTip(span, head + tipBody(res) + '</div>');
    } catch (err) {
      pwin.__synCache.delete(word);  // don't cache failures
      if (seq !== reqSeq) return;
      showTip(span, head + 'Could not load synonyms.</div>');
    }
  });
  pdoc.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); });
  pdoc.addEventListener('scroll', hideTip, true);  // capture: catches container scrolls
}
</script>
"""
components.html(_TOOLTIP_JS, height=0)

result_area = st.empty()
result_area.markdown(
    f'<div style="{BOX_STYLE}color:#aaa;font-size:{st.session_state.font_px}px;">'
    "Your rewritten text will appear here.</div>",
    unsafe_allow_html=True,
)

# ── Tuning logic ──────────────────────────────────────────────────────────────

if tune_btn and not original_input.strip():
    st.warning("Paste some text above first.")
elif tune_btn and engine == "OpenAI" and not api_key:
    st.warning("Add your OpenAI API key in the sidebar first.")
elif tune_btn and engine == "Wordlist (no AI)":
    with st.spinner(f"Rewriting to {cefr_level}…"):
        try:
            tuner = load_wordlist_tuner()
            segments, stats = tuner.tune(original_input.strip(), cefr_level)

            simplified_count = sum(1 for s in segments if s.get("type") == "simplified")
            st.session_state.update(
                segments=segments,
                summary=(
                    f"{simplified_count} sentence{'s' if simplified_count != 1 else ''} rewritten."
                    if simplified_count else ""
                ),
                note="" if simplified_count else "No changes were needed for this level.",
                unreplaced=stats["unreplaced"],
            )
        except Exception as e:
            st.error(f"Error: {e}")
elif tune_btn:
    try:
        from openai import OpenAI, AuthenticationError
    except ImportError:
        st.error(
            "The `openai` package isn't installed. Run `pip install openai`, "
            "or switch to the Wordlist engine in the sidebar."
        )
        st.stop()
    with st.spinner(f"Rewriting to {cefr_level}…"):
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=2048,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Rewrite to CEFR level {cefr_level}:\n\n"
                            f"{original_input.strip()}"
                        ),
                    },
                ],
            )

            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            segments = data.get("segments", [])

            simplified_count = sum(1 for s in segments if s.get("type") == "simplified")
            dropped_count    = sum(1 for s in segments if s.get("type") == "dropped")

            parts = []
            if simplified_count:
                parts.append(f"{simplified_count} phrase{'s' if simplified_count != 1 else ''} rewritten")
            if dropped_count:
                parts.append(f"{dropped_count} dropped")

            st.session_state.update(
                segments=segments,
                summary=", ".join(parts) + "." if parts else "",
                note="" if parts else "No changes were needed for this level.",
                unreplaced=[],
            )

        except json.JSONDecodeError:
            st.error("Could not parse the AI response. Please try again.")
            result_area.code(raw, language=None)
        except AuthenticationError:
            st.error("Invalid API key. Please check your OpenAI API key.")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Persistent result render (survives A+/A− and other reruns) ───────────────

_segments = st.session_state.get("segments")
if _segments is not None:
    _unreplaced = frozenset(
        w.lower() for w in (st.session_state.get("unreplaced") or [])
    )
    result_area.markdown(
        render_tree(_segments, st.session_state.font_px, _unreplaced),
        unsafe_allow_html=True,
    )
    if st.session_state.get("summary"):
        st.success(st.session_state["summary"])
    if st.session_state.get("note"):
        st.info(st.session_state["note"])
    if st.session_state.get("unreplaced"):
        st.warning(
            "No easy replacement found for: "
            + ", ".join(dict.fromkeys(st.session_state["unreplaced"]))
        )
