import streamlit as st
import os
import glob
import re
import anthropic

st.set_page_config(page_title="Claude Chat with File Loading")

# Initialize session states
# Define available models

if "available_models" not in st.session_state:
    st.session_state["available_models"] = {
        "Claude 3.5 Haiku": "claude-3-5-haiku-20241022",
        "Claude 3.5 Sonnet": "claude-3-5-sonnet-20241022",
        "Claude Sonnet 4": "claude-sonnet-4-20250514",
        "Claude Opus 4.5": "claude-opus-4-5-20251101",
        "Claude 3 Haiku": "claude-3-haiku-20240307",
        "Claude 3 Sonnet": "claude-3-sonnet-20240229",
        "Claude 3 Opus": "claude-3-opus-20240229",
    }

if "anthropic_model" not in st.session_state:
    st.session_state["anthropic_model"] = "claude-3-5-haiku-20241022"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "folder_files" not in st.session_state:
    st.session_state.folder_files = []
if "selected_file" not in st.session_state:
    st.session_state.selected_file = None
if "uploaded_files_content" not in st.session_state:
    st.session_state.uploaded_files_content = {}  # {filename: content}
if "file_modifications" not in st.session_state:
    st.session_state.file_modifications = {}  # Track which files have been modified

# Function to sort filenames naturally
def natural_sort_key(s):
    """Sort strings with embedded numbers naturally."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

# Function to scan for text files in a directory
def scan_folder(folder_path):
    """Scan folder for .txt files and return sorted list."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    found_files = glob.glob(os.path.join(folder_path, "*.txt"))
    found_files.sort(key=natural_sort_key)
    return found_files

# Function to extract text from file
def extract_text(file_path):
    """Extract text from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return ""

# Function to parse a conversation file into messages
def parse_conversation(text):
    """Parse a text file into user and assistant messages."""
    messages = []
    lines = text.split('\n')
    current_role = None
    current_content = []

    for line in lines:
        # Check for user messages (case-insensitive)
        if line.lower().startswith("user:"):
            # Save previous message if exists
            if current_role and current_content:
                messages.append({"role": current_role, "content": "\n".join(current_content).strip()})
                current_content = []
            # Start new user message
            current_role = "user"
            # Find the position of the colon and extract content after it
            colon_pos = line.index(':')
            content_after_prefix = line[colon_pos + 1:].strip()
            if content_after_prefix:
                current_content.append(content_after_prefix)
        # Check for assistant messages (case-insensitive)
        elif line.lower().startswith("assistant:"):
            # Save previous message if exists
            if current_role and current_content:
                messages.append({"role": current_role, "content": "\n".join(current_content).strip()})
                current_content = []
            # Start new assistant message
            current_role = "assistant"
            # Find the position of the colon and extract content after it
            colon_pos = line.index(':')
            content_after_prefix = line[colon_pos + 1:].strip()
            if content_after_prefix:
                current_content.append(content_after_prefix)
        else:
            # Continue current message
            if current_role:
                current_content.append(line)

    # Add the last message
    if current_role and current_content:
        messages.append({"role": current_role, "content": "\n".join(current_content).strip()})

    return messages

# Function to load conversation from file
def load_conversation():
    if st.session_state.selected_file:
        text = extract_text(st.session_state.selected_file)
        st.session_state.messages = parse_conversation(text)

# Function to save conversation to file
def save_conversation(file_path):
    """Save current conversation to a file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for msg in st.session_state.messages:
            prefix = "User: " if msg["role"] == "user" else "Assistant: "
            f.write(f"{prefix}{msg['content']}\n\n")

# Function to build messages with file context (returns system prompt and messages separately for Anthropic)
def build_messages_with_files(user_prompt):
    """Build message list including file contents as context."""
    system_prompt = None
    messages = []

    # Add file context as system message if files are loaded
    if st.session_state.uploaded_files_content:
        file_context = """You have access to the following text files.

IMPORTANT INSTRUCTIONS:
1. Each file may contain questions at the END marked with "***" (three asterisks)
2. When the user asks to "answer the questions" or mentions "***":
   - Look at the END of each file
   - Find ALL lines that start with "***"
   - Answer each question thoroughly

3. TWO WAYS TO RESPOND:

   A) If user says "write", "update", "add to file", or "save answers":
      Format with full file content:

      --- FILE: filename.txt ---
      [Full original content]

      *** Question here?
      ANSWER: [Your answer]

   B) If user just asks to "answer" or "list":
      Just provide the answers directly without file markers:

      **filename.txt:**
      *** Question here?
      ANSWER: [Your answer]

      **another.txt:**
      *** Another question?
      ANSWER: [Your answer]

4. If questions ask for "latest data", provide the most current information you have

Here are the files:

"""
        for filename, content in st.session_state.uploaded_files_content.items():
            file_context += f"--- FILE: {filename} ---\n{content}\n\n"

        system_prompt = file_context

    # Add conversation history
    for msg in st.session_state.messages:
        messages.append({"role": msg["role"], "content": msg["content"]})

    return system_prompt, messages

# Function to parse response and update files if needed
def parse_response_for_file_updates(response_text):
    """Parse AI response to extract file updates."""
    import re

    # Pattern to match file updates: --- FILE: filename.txt ---
    file_pattern = r'---\s*FILE:\s*([^\n]+?)\s*---\s*\n(.*?)(?=---\s*FILE:|$)'
    matches = re.findall(file_pattern, response_text, re.DOTALL)

    updated_files = []
    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()

        if filename in st.session_state.uploaded_files_content:
            st.session_state.uploaded_files_content[filename] = content
            st.session_state.file_modifications[filename] = True
            updated_files.append(filename)

    return updated_files

# Main application
st.title("Claude Chat with File Processing")

# Show helpful prompt hint if files are loaded
if st.session_state.uploaded_files_content:
    st.info("**Quick prompt:** Please answer each question in each file that is formatted with *** before the question, it's at the end of each file")

# Show instructions if files are loaded
if st.session_state.uploaded_files_content:
    with st.expander("How to work with loaded files", expanded=False):
        st.markdown("""
        ### Working with Your Files

        Your uploaded files are automatically included in the AI's context. You can:

        **Ask questions about the files:**
        - "Summarize each file"
        - "What are the main topics in file1.txt?"
        - "Compare the content across all files"

        **Answer *** questions (view only):**
        - "Please answer the questions that start with ***"
        - "Answer all *** questions"
        - AI will show just the answers without updating files

        **Answer *** questions and UPDATE files:**
        - "Write answers to the *** questions in each file"
        - "Update files with answers to *** questions"
        - "Save answers to the *** questions in the files"
        - AI will include full file content with `--- FILE: ---` markers to trigger file updates

        **Other file modifications:**
        - "Write a summary at the top of each file"
        - "Add a conclusion section to each file"

        **Tip:** If you just want to see answers, use "answer". If you want to update the files, use "write" or "update".
        """)

# Sidebar for API key and folder input
with st.sidebar:
    st.header("Configuration")

    # API key input
    api_key = st.text_input("Anthropic API Key:", type="password")

    # Model selection
    model_display_name = st.selectbox(
        "Select Model:",
        options=list(st.session_state["available_models"].keys()),
        index=0
    )

    # Update the model in session state when selection changes
    st.session_state["anthropic_model"] = st.session_state["available_models"][model_display_name]

    # Display model info
    if model_display_name == "Claude Opus 4.5":
        st.info("Claude Opus 4.5 is Anthropic's most capable model with enhanced reasoning. Higher cost.")
    elif model_display_name == "Claude Sonnet 4":
        st.info("Claude Sonnet 4 offers excellent performance with balanced speed and capability.")
    elif model_display_name == "Claude 3.5 Sonnet":
        st.info("Claude 3.5 Sonnet provides strong performance at a moderate cost.")
    elif model_display_name == "Claude 3.5 Haiku":
        st.info("Claude 3.5 Haiku is the fastest and most affordable option.")

    st.header("Text Files")

    # File uploader
    uploaded_files = st.file_uploader(
        "Upload text files to work with:",
        type=['txt'],
        accept_multiple_files=True,
        help="Upload multiple text files to include in your chat context"
    )

    # Process uploaded files
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.uploaded_files_content:
                content = uploaded_file.read().decode('utf-8')
                st.session_state.uploaded_files_content[uploaded_file.name] = content
                st.session_state.file_modifications[uploaded_file.name] = False

    # Display loaded files
    if st.session_state.uploaded_files_content:
        st.subheader("Loaded Files:")
        for filename in list(st.session_state.uploaded_files_content.keys()):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                modified_indicator = " (modified)" if st.session_state.file_modifications.get(filename, False) else ""
                st.text(f"{filename}{modified_indicator}")
            with col2:
                # Download button
                if st.download_button(
                    label="Download",
                    data=st.session_state.uploaded_files_content[filename],
                    file_name=filename,
                    mime="text/plain",
                    key=f"download_{filename}"
                ):
                    pass
            with col3:
                # Remove button
                if st.button("Remove", key=f"remove_{filename}"):
                    del st.session_state.uploaded_files_content[filename]
                    if filename in st.session_state.file_modifications:
                        del st.session_state.file_modifications[filename]
                    st.rerun()

        # Clear all files button
        if st.button("Clear All Files"):
            st.session_state.uploaded_files_content = {}
            st.session_state.file_modifications = {}
            st.rerun()

        # Show file context info
        total_chars = sum(len(content) for content in st.session_state.uploaded_files_content.values())
        st.caption(f"{len(st.session_state.uploaded_files_content)} files loaded ({total_chars:,} characters)")

    st.divider()

    # Initialize Anthropic client when API key is provided
    client = None
    if api_key:
        client = anthropic.Anthropic(api_key=api_key)

    st.header("Conversation Files")

    # Input for conversation folder path
    folder_input = st.text_input(
        "Conversation Folder Path:",
        value="conversations",
        help="Path to folder containing conversation .txt files"
    )

    # Process folder button to refresh file list
    if st.button("Process Folder"):
        if folder_input:
            st.session_state.folder_files = scan_folder(folder_input)
            if not st.session_state.folder_files:
                st.info(f"No .txt files found in {folder_input}. Create some conversation files.")
        else:
            st.warning("Please enter a folder path first")

    # Scan folder for files
    if folder_input:
        st.session_state.folder_files = scan_folder(folder_input)

        if st.session_state.folder_files:
            file_options = ["Select a file..."] + [os.path.basename(f) for f in st.session_state.folder_files]
            selected_file_name = st.selectbox("Select a conversation file:", file_options)

            if selected_file_name != "Select a file...":
                file_idx = file_options.index(selected_file_name) - 1  # Adjust for the "Select a file..." option
                st.session_state.selected_file = st.session_state.folder_files[file_idx]

                # Button to load conversation
                if st.button("Load Conversation"):
                    load_conversation()
                    st.success(f"Loaded conversation from {selected_file_name}")
        else:
            st.info(f"No .txt files found in {folder_input}. Create some conversation files.")

    # File name input for saving current conversation
    save_filename = st.text_input("Save conversation as:",
                                 help="Filename to save current conversation (will be saved to the folder specified above)")

    if save_filename and folder_input:
        # Add .txt extension if not present
        if not save_filename.endswith('.txt'):
            save_filename += '.txt'

        save_path = os.path.join(folder_input, save_filename)

        if st.button("Save Current Conversation"):
            save_conversation(save_path)
            st.success(f"Conversation saved to {save_filename}")
            # Update file list
            st.session_state.folder_files = scan_folder(folder_input)

    # Copy conversation section
    st.header("Copy Conversation")

    # Initialize show_copy state
    if "show_copy_text" not in st.session_state:
        st.session_state.show_copy_text = False

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Show Conversation Text"):
            st.session_state.show_copy_text = True
    with col2:
        if st.button("Hide"):
            st.session_state.show_copy_text = False

    if st.session_state.show_copy_text:
        if st.session_state.messages:
            # Format the conversation for copying
            conversation_text = ""
            for msg in st.session_state.messages:
                prefix = "User: " if msg["role"] == "user" else "Assistant: "
                conversation_text += f"{prefix}{msg['content']}\n\n"

            # Display in a text area for easy copying
            st.text_area(
                "Select all text and copy (Ctrl+A, Ctrl+C / Cmd+A, Cmd+C):",
                conversation_text,
                height=300,
                key="copy_chat_text"
            )
        else:
            st.warning("No conversation to copy yet.")

# Add information about model pricing
st.sidebar.markdown("""
### Model Pricing Information
- **Claude 3.5 Haiku**: Lowest cost, fastest
- **Claude 3.5 Sonnet**: Moderate cost
- **Claude Sonnet 4**: Higher capability
- **Claude Opus 4.5**: Highest cost, most capable
""")

# Display conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Check if client is initialized (API key is provided)
    if client:
        with st.chat_message("assistant"):
            try:
                # Display a message when using the expensive Opus model
                if st.session_state["anthropic_model"] == "claude-opus-4-5-20251101":
                    st.warning("Note: You are using Claude Opus 4.5 which has significantly higher costs than other models.")

                # Build messages with file context
                system_prompt, messages_with_context = build_messages_with_files(prompt)

                # Debug: Show context being sent (optional)
                if st.session_state.uploaded_files_content:
                    with st.expander("Debug: Files included in context", expanded=False):
                        st.write(f"Total messages sent: {len(messages_with_context)}")
                        st.write(f"Files loaded: {len(st.session_state.uploaded_files_content)}")
                        if system_prompt:
                            st.text_area("System message preview:", system_prompt[:500] + "...", height=150)

                # Build API call parameters
                api_params = {
                    "model": st.session_state["anthropic_model"],
                    "max_tokens": 4096,
                    "messages": messages_with_context,
                }

                # Add system prompt if available
                if system_prompt:
                    api_params["system"] = system_prompt

                # Use streaming for response
                response_text = ""
                message_placeholder = st.empty()

                with client.messages.stream(**api_params) as stream:
                    for text in stream.text_stream:
                        response_text += text
                        message_placeholder.markdown(response_text + "...")

                # Final display without trailing dots
                message_placeholder.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

                # Check if response contains file updates
                updated_files = parse_response_for_file_updates(response_text)
                if updated_files:
                    st.success(f"Updated {len(updated_files)} file(s): {', '.join(updated_files)}")
                    st.rerun()

                # Show model used for this response
                st.caption(f"Response generated using: {model_display_name}")

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                # Add a placeholder response in case of error
                st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I encountered an error: {error_msg}"})
    else:
        with st.chat_message("assistant"):
            error_msg = "Please enter your Anthropic API key in the sidebar to enable chat functionality."
            st.warning(error_msg)
            # Don't add this message to the conversation history
