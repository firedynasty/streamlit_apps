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
ul.cefr-tree span.replaced {
  text-decoration: underline;
  text-decoration-color: #5580cc;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
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

def _escape_simplified(text: str) -> str:
    """Escape, then convert the engine's « » sentinels into underline spans."""
    return (
        html.escape(text)
        .replace("«", '<span class="replaced">')
        .replace("»", "</span>")
    )


def render_tree(segments: list, font_px: int = 24) -> str:
    """
    Bullet tree:
      • simplified text          (blue dot)
          ↳ original text        (indented, gray italic)
      • unchanged text           (gray dot, no sub-bullet)
      • ~~dropped original~~     (red strikethrough, no sub-bullet)
    font_px scales the whole tree (inner sizes are em-based).
    """
    items = []
    for seg in segments:
        seg_type = seg.get("type", "unchanged")
        simplified = (seg.get("simplified") or "").strip()
        original   = html.escape((seg.get("original") or "").strip())

        if seg_type == "dropped":
            items.append(f'<li class="dropped-li">{original}</li>')

        elif seg_type == "simplified":
            sub = f'<ul><li>{original}</li></ul>' if original else ""
            items.append(
                f'<li>{_escape_simplified(simplified)}{sub}</li>'
            )

        else:  # unchanged — no sub-bullet needed
            items.append(f'<li class="unchanged">{_escape_simplified(simplified)}</li>')

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
    result_area.markdown(
        render_tree(_segments, st.session_state.font_px), unsafe_allow_html=True
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
