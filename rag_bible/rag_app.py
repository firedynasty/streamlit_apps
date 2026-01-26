"""
RAG Retriever - Streamlit App
Retrieve context from Bible knowledge bases for use with Claude.
"""

import streamlit as st
import os
import sys

# Available knowledge bases
RAG_FOLDERS = {
    "Psalms": "rag_psalms",
    "Proverbs": "rag_proverbs",
}

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


def retrieve_from_rag(rag_folder: str, query: str) -> str:
    """Retrieve context from specified RAG folder."""
    # Update sys.path for the selected RAG folder
    rag_path = os.path.join(APP_DIR, rag_folder)

    # Remove other RAG paths and add current one
    sys.path = [p for p in sys.path if not p.endswith(tuple(RAG_FOLDERS.values()))]
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
        options=list(RAG_FOLDERS.keys()),
        index=0
    )

# Main area
query = st.text_area(
    "Your Question",
    placeholder="e.g., What does the Bible say about wisdom?",
    height=100
)

col1, col2 = st.columns([1, 5])
with col1:
    retrieve_btn = st.button("🔍 Retrieve", type="primary", use_container_width=True)

# Retrieve and display
if retrieve_btn and query:
    rag_folder = RAG_FOLDERS[selected_kb]

    with st.spinner(f"Retrieving from {selected_kb}..."):
        try:
            context = retrieve_from_rag(rag_folder, query)

            st.success(f"Retrieved from {selected_kb}")

            # Display context in copyable text area
            st.subheader("Retrieved Context")
            st.text_area(
                "Context (select all and copy)",
                value=context,
                height=400,
                label_visibility="collapsed"
            )

            # Also show formatted version
            with st.expander("Formatted View"):
                st.markdown(context.replace("\n", "  \n"))

        except Exception as e:
            st.error(f"Error retrieving context: {e}")

elif retrieve_btn and not query:
    st.warning("Please enter a question.")

# Footer
st.markdown("---")
st.caption("Copy the context above and paste into Claude with your question.")
