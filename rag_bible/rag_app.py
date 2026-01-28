"""
RAG Retriever - Streamlit App
Retrieve context from Bible knowledge bases for use with Claude.
"""

import streamlit as st
import os
import sys

# Knowledge bases configuration
# Format: "Display Name": {"type": "rag"|"txt", "path": "folder_or_file", "source": "source_name"}

KNOWLEDGE_BASES = {
    # Old Testament - in biblical order
    "Genesis": {"type": "txt", "path": "genesis.txt", "source": "Matthew Henry's Commentary"},
    "Exodus": {"type": "txt", "path": "exodus.txt", "source": "Matthew Henry's Commentary"},
    "Leviticus": {"type": "txt", "path": "leviticus.txt", "source": "Matthew Henry's Commentary"},
    "Numbers": {"type": "txt", "path": "numbers.txt", "source": "Matthew Henry's Commentary"},
    "Deuteronomy": {"type": "txt", "path": "deuteronomy.txt", "source": "Matthew Henry's Commentary"},
    "Joshua": {"type": "txt", "path": "joshua.txt", "source": "Matthew Henry's Commentary"},
    "Judges": {"type": "txt", "path": "judges.txt", "source": "Matthew Henry's Commentary"},
    "1 Samuel": {"type": "txt", "path": "1_samuel.txt", "source": "Matthew Henry's Commentary"},
    "2 Samuel": {"type": "txt", "path": "2_samuel.txt", "source": "Matthew Henry's Commentary"},
    "1 Kings": {"type": "txt", "path": "1_kings.txt", "source": "Matthew Henry's Commentary"},
    "2 Kings": {"type": "txt", "path": "2_kings.txt", "source": "Matthew Henry's Commentary"},
    "Psalms": {"type": "rag", "path": "rag_psalms", "source": "Matthew Henry's Commentary"},
    "Proverbs": {"type": "txt", "path": "proverbs.txt", "source": "Matthew Henry's Commentary"},
    "Ecclesiastes": {"type": "txt", "path": "ecclesiastes.txt", "source": "Matthew Henry's Commentary"},
    "Song of Solomon": {"type": "txt", "path": "solomon.txt", "source": "Matthew Henry's Commentary"},
    "Isaiah": {"type": "rag", "path": "rag_isaiah", "source": "Matthew Henry's Commentary"},
    "Jeremiah": {"type": "txt", "path": "jeremiah.txt", "source": "Matthew Henry's Commentary"},
    # New Testament - in biblical order
    "Romans": {"type": "rag", "path": "rag_romans", "source": "studyandobey"},
    "2 Corinthians": {"type": "rag", "path": "rag_2corinthians", "source": "studyandobey"},
    "Galatians": {"type": "rag", "path": "rag_galatians", "source": "studyandobey"},
}

# For backwards compatibility
RAG_FOLDERS = {name: cfg["path"] for name, cfg in KNOWLEDGE_BASES.items() if cfg["type"] == "rag"}

# Get the directory where this script is located
APP_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def load_rag_module(rag_folder: str):
    """Load RAG module from specified folder."""
    rag_path = os.path.join(APP_DIR, rag_folder)

    if rag_path not in sys.path:
        sys.path.insert(0, rag_path)

    # Import fresh each time by reloading
    import importlib

    # Clear any cached imports from other RAG folders
    modules_to_remove = [m for m in sys.modules if m.startswith('src.')]
    for m in modules_to_remove:
        del sys.modules[m]

    from src.retrieval import get_knowledge_base, get_context
    from src.constants import get_rag_config

    return get_knowledge_base, get_context, get_rag_config


def retrieve_from_txt(file_path: str) -> str:
    """Read entire text file."""
    full_path = os.path.join(APP_DIR, file_path)
    with open(full_path, 'r', encoding='utf-8') as f:
        return f.read()


def retrieve_from_rag(rag_folder: str, query: str) -> str:
    """Retrieve context from specified RAG folder using semantic search."""
    # Update sys.path for the selected RAG folder
    rag_path = os.path.join(APP_DIR, rag_folder)

    # Remove other RAG paths and add current one
    rag_paths = [cfg["path"] for cfg in KNOWLEDGE_BASES.values() if cfg["type"] == "rag"]
    sys.path = [p for p in sys.path if not p.endswith(tuple(rag_paths))]
    if rag_path not in sys.path:
        sys.path.insert(0, rag_path)

    # Clear cached src modules
    modules_to_remove = [m for m in sys.modules if m.startswith('src.')]
    for m in modules_to_remove:
        del sys.modules[m]

    # Import fresh
    from src.retrieval import get_knowledge_base, get_context
    from src.constants import get_rag_config

    config = get_rag_config()
    k_base = get_knowledge_base()

    context = get_context(
        k_base=k_base,
        query_text=query,
        n_retrieve=config["retriever"]["n_retrieve"],
        n_titles=config["retriever"]["n_titles"],
        enrich_first=config["retriever"]["enrich_first"],
        reranker=config["retriever"]["reranker"]
    )

    return context


def retrieve_context(kb_name: str, query: str) -> str:
    """Retrieve context based on knowledge base type."""
    config = KNOWLEDGE_BASES[kb_name]
    if config["type"] == "txt":
        return retrieve_from_txt(config["path"])
    else:
        return retrieve_from_rag(config["path"], query)


# Page config
st.set_page_config(
    page_title="Bible RAG Retriever",
    page_icon="📖",
    layout="wide"
)

st.title("📖 Bible RAG Retriever")
st.markdown("Retrieve context from Bible commentaries for your questions.")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    selected_kb = st.selectbox(
        "Knowledge Base",
        options=list(KNOWLEDGE_BASES.keys()),
        index=0
    )
    # Show source info
    source = KNOWLEDGE_BASES[selected_kb]["source"]
    kb_type = KNOWLEDGE_BASES[selected_kb]["type"]
    st.caption(f"Source: {source}")
    st.caption(f"Type: {'Full text' if kb_type == 'txt' else 'Semantic search'}")
    st.markdown("[Matthew Henry Commentary](https://www.christianity.com/bible/commentary/matthew-henry-complete/)")
    st.markdown("[Matthew Henry Search](https://matthew-henry.netlify.app/)")

# Main area
query = st.text_area(
    "Paste verse or question",
    placeholder="e.g., Paste a verse for analysis, or ask a thematic question like 'What does the commentary say about trusting God in difficult times?'",
    height=100
)

col1, col2 = st.columns([1, 5])
with col1:
    retrieve_btn = st.button("🔍 Retrieve", type="primary", use_container_width=True)

# Retrieve and display
if retrieve_btn and query:
    kb_config = KNOWLEDGE_BASES[selected_kb]
    source_name = kb_config["source"]

    with st.spinner(f"Retrieving from {selected_kb}..."):
        try:
            context = retrieve_context(selected_kb, query)

            st.success(f"Retrieved from {selected_kb}")

            # Build full output with instructions and question appended
            full_output = f"""[CONTEXT FROM {source_name.upper()}]
Below are excerpts from {source_name} on thematically similar passages.

Please:
1. Analyze the verse/passage I provide
2. Enrich your analysis using insights from the commentary excerpts below (they cover similar themes even if not the exact same chapter)

{context}

---
{query}"""

            # Display with copy button using st.code
            st.subheader("Copy this to Claude")
            st.code(full_output, language=None)

            # Also show formatted version
            with st.expander("Formatted View"):
                st.markdown(context.replace("\n", "  \n"))
                st.markdown("---")
                st.markdown(f"**My question:** {query}")

        except Exception as e:
            st.error(f"Error retrieving context: {e}")

elif retrieve_btn and not query:
    st.warning("Please enter a question.")

# Footer
st.markdown("---")
st.caption("Click the copy icon in the code block above, then paste into Claude.")
