#!/usr/bin/env python3
"""
Streamlit UI for chinese_csv.py: paste Chinese text (or upload a .txt file)
and get a Chinese/Pinyin/English meaning table -- one row per sentence plus
a word-by-word breakdown, with each dictionary meaning on its own row (the
word and pinyin repeated down). Choose how many meanings per word to keep.

Two engines, same table layout:
  - Local dictionary (chinese_csv.py: jieba + pypinyin + CC-CEDICT) -- free,
    no network, dictionary meanings.
  - OpenAI (openai_gloss.py) -- used by default whenever an API key is
    available (OPENAI_API_KEY env var, Streamlit secrets, or pasted in the
    sidebar); one meaning per word that fits the sentence.

Usage:
    streamlit run chinese_streamlit_csv.py
"""

import csv
import io
import os

import pandas as pd
import streamlit as st

from chinese_csv import chinese_text_to_rows, load_cedict
from openai_gloss import DEFAULT_MODEL, openai_text_to_rows

LOCAL = "Local dictionary (free)"
OPENAI = "OpenAI (fits the sentence)"


def rows_to_csv(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue().strip()


st.set_page_config(page_title="Chinese -> CSV", page_icon="🀄", layout="wide")


@st.cache_resource
def get_cedict() -> dict:
    return load_cedict()


def configured_api_key() -> str:
    """OPENAI_API_KEY from the environment, else from Streamlit secrets
    (.streamlit/secrets.toml locally, the app's Secrets on Streamlit Cloud)."""
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    try:
        return st.secrets.get("OPENAI_API_KEY", "")
    except Exception:  # no secrets file at all
        return ""


def main() -> None:
    st.title("🀄 Chinese -> CSV")
    st.caption(
        "Paste Chinese text and get a Chinese, Pinyin, English meaning table -- "
        "word-by-word, one row per meaning, ready to paste into Google Sheets. "
        "Works on Simplified or Traditional text. Free local dictionary, or OpenAI "
        "when an API key is set."
    )

    with st.sidebar:
        configured_key = configured_api_key()
        engine = st.radio("Engine", [OPENAI, LOCAL], index=0 if configured_key else 1)

        if engine == OPENAI:
            if configured_key:
                api_key = configured_key
                st.caption("Using the OpenAI API key from the environment / secrets.")
            else:
                api_key = st.text_input(
                    "OpenAI API key",
                    type="password",
                    placeholder="sk-...",
                    help="Only used for this session, not stored anywhere.",
                )
            model = st.text_input("Model", value=DEFAULT_MODEL)
            st.caption("One meaning per word, chosen to fit the sentence.")
        else:
            all_meanings = st.checkbox("Show all meanings", value=False)
            max_meanings = st.number_input(
                "Meanings per word",
                min_value=1,
                max_value=20,
                value=3,
                disabled=all_meanings,
                help="Each meaning gets its own row, with the word and pinyin repeated.",
            )

        st.divider()
        st.markdown("**Original source code**")
        st.markdown(
            "OpenAI version (`mandarin-gloss-plain` capability):  \n"
            "`/Users/stanleytan/Documents/technical/python/language_capabilities`\n\n"
            "Local NLP version (jieba + pypinyin + CC-CEDICT):  \n"
            "`/Users/stanleytan/Documents/technical/ollama/natural_nlp`"
        )

    uploaded = st.file_uploader("Upload a .txt file (or paste below)", type=["txt"])
    chinese_text = st.text_area(
        "Chinese text",
        value=uploaded.getvalue().decode("utf-8") if uploaded else "",
        height=250,
        placeholder="起初，神創造天地。",
        label_visibility="collapsed",
    )

    needs_key = engine == OPENAI and not api_key
    if needs_key:
        st.info("Enter your OpenAI API key in the sidebar, or switch the engine to the free local dictionary.")

    if st.button("Convert", type="primary", disabled=not chinese_text.strip() or needs_key):
        if engine == OPENAI:
            from openai import OpenAI

            progress = st.progress(0.0, text="Sending sentences to OpenAI...")
            try:
                rows, fallbacks = openai_text_to_rows(
                    chinese_text.strip(),
                    OpenAI(api_key=api_key),
                    get_cedict(),
                    model=model or DEFAULT_MODEL,
                    on_progress=lambda done, total: progress.progress(
                        done / total, text=f"{done}/{total} sentences"
                    ),
                )
            except Exception as e:  # bad key, network, unknown model, ...
                progress.empty()
                st.error(f"OpenAI request failed: {e}")
                st.stop()
            progress.empty()
            if fallbacks:
                st.warning(
                    f"{fallbacks} sentence(s) got an unreadable reply from OpenAI and "
                    "used the local dictionary instead."
                )
        else:
            with st.spinner("Converting..."):
                rows = chinese_text_to_rows(
                    chinese_text.strip(), get_cedict(), None if all_meanings else int(max_meanings)
                )
        if not rows:
            st.error("No Chinese sentences found in that input.")
        else:
            st.session_state.rows = rows

    rows = st.session_state.get("rows")
    if rows:
        df = pd.DataFrame(rows[1:], columns=rows[0])
        # A static HTML table, not st.dataframe: it can't be re-sorted, so rows
        # always stay in sentence order. (Not df.style + st.table -- Styler
        # imports matplotlib, and has no index-free st.table otherwise.)
        st.markdown(df.to_html(index=False, escape=True), unsafe_allow_html=True)
        st.caption(
            "Select the table text and ⌘C/Ctrl+C to paste into Google Sheets, "
            "or use the download button."
        )
        st.download_button("Download .csv", data=rows_to_csv(rows), file_name="chinese_vocab.csv", mime="text/csv")


if __name__ == "__main__":
    main()
