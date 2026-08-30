"""
reading_coach.py

Pronunciation assessment tool powered by Azure Speech SDK.
Paste a passage, read it aloud, and get word-by-word feedback on accuracy,
fluency, completeness, and prosody.

Secrets (in .streamlit/secrets.toml):
    AZURE_SPEECH_KEY = "..."
    AZURE_REGION     = "eastus"
"""

import hashlib
import os
import tempfile
import streamlit as st
import azure.cognitiveservices.speech as speechsdk

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Reading Coach", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    "<style>[data-testid='collapsedControl'] { display: none; }</style>",
    unsafe_allow_html=True,
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
body { background: #0e1117; }
textarea { font-size: 18px !important; line-height: 1.6 !important; }

.score-grid {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin: 18px 0 24px;
}
.score-card {
    flex: 1;
    min-width: 110px;
    background: #1c1f26;
    border-radius: 10px;
    padding: 16px 12px 12px;
    text-align: center;
    border: 1px solid #2e3340;
}
.score-card .label {
    font-size: 11px;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #8a8f9e;
    margin-bottom: 6px;
}
.score-card .value {
    font-size: 34px;
    font-weight: 700;
    line-height: 1;
}
.score-card .value.good  { color: #4ade80; }
.score-card .value.ok    { color: #facc15; }
.score-card .value.poor  { color: #f87171; }

.word-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}
.chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 500;
    cursor: default;
}
.chip.good      { background: #14532d; color: #4ade80; border: 1px solid #166534; }
.chip.ok        { background: #422006; color: #fdba74; border: 1px solid #7c2d12; }
.chip.poor      { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
.chip.omission  { background: #1e1b4b; color: #a5b4fc; border: 1px solid #312e81; }
.chip.insertion { background: #2d1d4b; color: #c4b5fd; border: 1px solid #4c1d95; }
.chip .badge    { font-size: 10px; opacity: .75; }

.section-title {
    font-size: 13px;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #6b7280;
    margin: 24px 0 8px;
    border-bottom: 1px solid #2e3340;
    padding-bottom: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_class(score: float) -> str:
    if score >= 80:
        return "good"
    if score >= 50:
        return "ok"
    return "poor"


def _error_label(error_type: str) -> str:
    return {
        "Mispronunciation": "mis",
        "Omission": "skip",
        "Insertion": "extra",
        "UnexpectedBreak": "break",
        "MissingBreak": "no-break",
        "Monotone": "mono",
    }.get(error_type, error_type.lower())


def assess(audio_bytes: bytes, reference_text: str) -> speechsdk.PronunciationAssessmentResult:
    speech_key = st.secrets.get("AZURE_SPEECH_KEY", "")
    region = st.secrets.get("AZURE_REGION", "eastus")

    if not speech_key:
        st.error("AZURE_SPEECH_KEY is empty — fill it in `.streamlit/secrets.toml`.")
        st.stop()

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.speech_recognition_language = "en-US"

    pron_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Word,
    )
    pron_config.enable_prosody_assessment()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        audio_config = speechsdk.audio.AudioConfig(filename=tmp_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config, audio_config)
        pron_config.apply_to(recognizer)
        result = recognizer.recognize_once()
    finally:
        os.unlink(tmp_path)

    if result.reason == speechsdk.ResultReason.Canceled:
        details = speechsdk.CancellationDetails.from_result(result)
        st.error(f"Azure error: {details.reason} — {details.error_details}")
        st.stop()

    return speechsdk.PronunciationAssessmentResult(result)


def render_scores(pron_result: speechsdk.PronunciationAssessmentResult):
    scores = {
        "Accuracy":     pron_result.accuracy_score,
        "Fluency":      pron_result.fluency_score,
        "Completeness": pron_result.completeness_score,
        "Prosody":      pron_result.prosody_score,
        "Overall":      pron_result.pronunciation_score,
    }
    cards = "".join(
        f"""<div class="score-card">
                <div class="label">{label}</div>
                <div class="value {_score_class(v)}">{v:.0f}</div>
            </div>"""
        for label, v in scores.items()
    )
    st.markdown(f'<div class="score-grid">{cards}</div>', unsafe_allow_html=True)


def render_words(pron_result: speechsdk.PronunciationAssessmentResult):
    st.markdown('<div class="section-title">Word-by-word breakdown</div>', unsafe_allow_html=True)
    chips = []
    for word in pron_result.words:
        err = word.error_type
        score = word.accuracy_score

        if err == "Omission":
            css, badge = "omission", "skip"
        elif err == "Insertion":
            css, badge = "insertion", "extra"
        elif err not in ("None", ""):
            css, badge = _score_class(score), _error_label(err)
        else:
            css, badge = _score_class(score), f"{score:.0f}"

        chips.append(
            f'<span class="chip {css}">{word.word}'
            f'<span class="badge">{badge}</span></span>'
        )
    st.markdown(f'<div class="word-row">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_problem_summary(pron_result: speechsdk.PronunciationAssessmentResult):
    problems = [
        w for w in pron_result.words
        if w.error_type not in ("None", "", "Insertion") and w.accuracy_score < 80
    ]
    if not problems:
        st.success("No major problem words — well done!")
        return

    st.markdown('<div class="section-title">Focus words</div>', unsafe_allow_html=True)
    for w in problems:
        label = f"**{w.word}**"
        if w.error_type and w.error_type != "None":
            label += f" — _{_error_label(w.error_type)}_"
        if w.error_type not in ("Omission",):
            label += f" (score: {w.accuracy_score:.0f})"
        st.markdown(f"- {label}")


def speak_word(word: str) -> bytes:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=word,
    )
    return response.content


def render_word_practice(pron_result: speechsdk.PronunciationAssessmentResult):
    problem_words = [
        w.word for w in pron_result.words
        if w.error_type not in ("None", "", "Insertion") and w.accuracy_score < 80
    ]
    all_words = [w.word for w in pron_result.words if w.error_type != "Insertion"]
    seen = set()
    ordered = []
    for w in problem_words + all_words:
        if w.lower() not in seen:
            seen.add(w.lower())
            ordered.append(w)

    st.markdown('<div class="section-title">Practice a word</div>', unsafe_allow_html=True)

    selected = st.selectbox(
        "Choose a word:",
        options=ordered,
        key="practice_word_select",
        label_visibility="collapsed",
    )

    col_hear, col_rec = st.columns([1, 2])

    with col_hear:
        if st.button("▶ Hear it", use_container_width=True):
            with st.spinner("Synthesizing…"):
                tts_bytes = speak_word(selected)
            if tts_bytes:
                st.audio(tts_bytes, format="audio/mp3", autoplay=True)

    with col_rec:
        practice_audio = st.audio_input(
            "Record yourself",
            key=f"practice_rec_{selected}",
            label_visibility="collapsed",
        )

    if practice_audio:
        audio_bytes = practice_audio.getvalue()
        cache_key = f"practice_score_{selected}_{hashlib.md5(audio_bytes).hexdigest()[:8]}"
        if cache_key not in st.session_state:
            with st.spinner("Checking…"):
                word_result = assess(audio_bytes, selected)
            st.session_state[cache_key] = word_result.accuracy_score

        score = st.session_state[cache_key]
        css = _score_class(score)
        color = {"good": "#4ade80", "ok": "#facc15", "poor": "#f87171"}[css]
        st.markdown(
            f'<p style="font-size:22px; font-weight:700; color:{color}; margin-top:8px;">'
            f'"{selected}" — {score:.0f} / 100</p>',
            unsafe_allow_html=True,
        )

# ── Main UI ───────────────────────────────────────────────────────────────────

st.title("Reading Coach")
st.caption("Paste a passage, record yourself reading it, and get instant pronunciation feedback.")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("#### Passage")
    passage = st.text_area(
        "Paste or type the text you want to practise:",
        height=260,
        placeholder="e.g. The quick brown fox jumps over the lazy dog.",
        label_visibility="collapsed",
    )

    st.markdown("#### Record")
    st.caption("Record yourself reading the passage aloud, then click **Assess**.")
    audio = st.audio_input("Record passage", key="recorder", label_visibility="collapsed")

    if audio and passage.strip():
        if st.button("Assess pronunciation", type="primary", use_container_width=True):
            with st.spinner("Sending to Azure Speech…"):
                result = assess(audio.getvalue(), passage.strip())
            st.session_state["pron_result"] = result

with col_right:
    if "pron_result" in st.session_state:
        result = st.session_state["pron_result"]
        st.markdown("#### Results")
        render_scores(result)
        render_words(result)
        render_problem_summary(result)
        render_word_practice(result)
    else:
        st.markdown("#### Results")
        st.info("Record yourself reading the passage, then click **Assess pronunciation**.")
