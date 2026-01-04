#!/usr/bin/env python3
"""
Anthropic Chat CLI - Chat with Claude from the Terminal
=========================================================
A command-line tool for interactive conversations with Claude.

Prompt: "with anthropic_chat_cli.py, and socratic_coaching.md walk me through"
Usage:
    python anthropic_chat_cli.py                    # Interactive mode
    python anthropic_chat_cli.py -f file1.txt       # Load context files
    python anthropic_chat_cli.py --model sonnet     # Select model
    python anthropic_chat_cli.py --socratic         # Enable Socratic coaching
    python anthropic_chat_cli.py -s -t "Python"     # Socratic mode with topic
    python anthropic_chat_cli.py --native -c "summarize"  # Clipboard + prompt for Claude Code

Requirements:
    - ANTHROPIC_API_KEY environment variable (or enter interactively)

Features:
    - Multiple Claude models (Haiku, Sonnet, Opus)
    - Load text files as context
    - Save/load conversation history
    - Streaming responses
    - Socratic coaching mode (ask, don't tell)
"""

import argparse
import os
import sys
import re
import glob
from typing import List, Dict, Optional

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not found. Install with: pip install anthropic")
    sys.exit(1)

# ============================================================================
# CONSTANTS
# ============================================================================

AVAILABLE_MODELS = {
    "1": ("Claude 3.5 Haiku", "claude-3-5-haiku-20241022"),
    "2": ("Claude 3.5 Sonnet", "claude-3-5-sonnet-20241022"),
    "3": ("Claude Sonnet 4", "claude-sonnet-4-20250514"),
    "4": ("Claude Opus 4.5", "claude-opus-4-5-20251101"),
}

MODEL_ALIASES = {
    "haiku": "1",
    "sonnet": "2",
    "sonnet4": "3",
    "opus": "4",
}

# Terminal colors
class Colors:
    RED = '\033[91m'
    ORANGE = '\033[93m'
    YELLOW = '\033[33m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


# Socratic coaching system prompt
SOCRATIC_SYSTEM_PROMPT = """You are a thoughtful coach using the Socratic method. Your role is to guide learners to discover insights rather than lecturing them.

CORE COACHING PRINCIPLES:

1. ASK, DON'T TELL
   Instead of giving direct answers, ask questions that lead to discovery.
   The learner remembers insights they discover far better than facts they're told.

2. VALIDATE FIRST, THEN PROBE
   Always find something reasonable in the learner's thinking before challenging it.
   This keeps them open and engaged rather than defensive.
   Example: "I see you were trying to [X] - that's good thinking! But let me ask..."

3. GUIDE TO PRINCIPLES, NOT JUST ANSWERS
   Connect specific situations to broader understanding.
   This builds transferable knowledge they can apply to new situations.

4. ONE QUESTION AT A TIME
   Don't overwhelm with multiple questions. Ask one, wait for reflection,
   then build on their response.

5. END WITH ACTION
   Give one concrete thing to study or practice. Not a list of five things.

COACHING CONVERSATION FLOW:

Step 1: UNDERSTAND THEIR THINKING
- "What were you trying to accomplish?"
- "What was your reasoning?"
- "What options did you consider?"

Step 2: REVEAL THE GAP
Help them see what they missed through questions, not statements.
- "What happens if...?"
- "How does this compare to...?"
- "What principle might apply here?"

Step 3: TEACH THE PRINCIPLE
Connect to a broader concept they can remember and reuse.

Step 4: GIVE CONCRETE PRACTICE
One specific exercise or study task.

TONE: Encouraging, curious, thought-provoking. Like a wise mentor, not a critic.

IMPORTANT:
- Keep responses focused and under 200 words when possible
- End with a thought-provoking question OR a concrete study suggestion
- Never be condescending - treat learners as capable people who just need guidance
- If they're stuck, give a small hint, then ask a follow-up question
"""


SOCRATIC_TOPIC_TEMPLATE = """
CURRENT COACHING TOPIC: {topic}

Focus your Socratic questioning on helping the learner understand {topic} deeply.
When they ask questions or make statements, guide them to discover insights about
{topic} through thoughtful questions rather than direct explanations.
"""


# ============================================================================
# FILE UTILITIES
# ============================================================================

def natural_sort_key(s: str) -> List:
    """Sort strings with embedded numbers naturally."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def get_clipboard_content() -> str:
    """Get content from system clipboard."""
    import subprocess
    import platform

    system = platform.system()
    try:
        if system == 'Darwin':  # macOS
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            return result.stdout
        elif system == 'Linux':
            # Try xclip first, then xsel
            try:
                result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                       capture_output=True, text=True)
                return result.stdout
            except FileNotFoundError:
                result = subprocess.run(['xsel', '--clipboard', '--output'],
                                       capture_output=True, text=True)
                return result.stdout
        elif system == 'Windows':
            result = subprocess.run(['powershell', '-command', 'Get-Clipboard'],
                                   capture_output=True, text=True)
            return result.stdout
    except Exception as e:
        print(f"Error reading clipboard: {e}")
        return ""

    return ""


def scan_folder(folder_path: str) -> List[str]:
    """Scan folder for .txt and .md files and return sorted list."""
    if not os.path.exists(folder_path):
        return []
    # Find both .txt and .md files
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    md_files = glob.glob(os.path.join(folder_path, "*.md"))
    found_files = txt_files + md_files
    found_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    return found_files


def extract_text(file_path: str) -> str:
    """Extract text from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        print(f"{Colors.RED}Error reading file: {e}{Colors.RESET}")
        return ""


def parse_conversation(text: str) -> List[Dict]:
    """Parse a text file into user and assistant messages."""
    messages = []
    lines = text.split('\n')
    current_role = None
    current_content = []

    for line in lines:
        # Check for user messages (case-insensitive)
        if line.lower().startswith("user:"):
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip()
                })
                current_content = []
            current_role = "user"
            colon_pos = line.index(':')
            content_after_prefix = line[colon_pos + 1:].strip()
            if content_after_prefix:
                current_content.append(content_after_prefix)
        # Check for assistant messages (case-insensitive)
        elif line.lower().startswith("assistant:"):
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip()
                })
                current_content = []
            current_role = "assistant"
            colon_pos = line.index(':')
            content_after_prefix = line[colon_pos + 1:].strip()
            if content_after_prefix:
                current_content.append(content_after_prefix)
        else:
            if current_role:
                current_content.append(line)

    # Add the last message
    if current_role and current_content:
        messages.append({
            "role": current_role,
            "content": "\n".join(current_content).strip()
        })

    return messages


def save_conversation(file_path: str, messages: List[Dict]):
    """Save conversation to a file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for msg in messages:
            prefix = "User: " if msg["role"] == "user" else "Assistant: "
            f.write(f"{prefix}{msg['content']}\n\n")
    print(f"{Colors.GREEN}Conversation saved to {file_path}{Colors.RESET}")


# ============================================================================
# SYSTEM PROMPT BUILDER
# ============================================================================

def build_system_prompt(loaded_files: Dict[str, str],
                       socratic_mode: bool = False,
                       socratic_topic: Optional[str] = None,
                       role_prompt: Optional[str] = None) -> Optional[str]:
    """Build system prompt with file context and optional Socratic coaching."""
    parts = []

    # Add custom role prompt if provided
    if role_prompt:
        parts.append(role_prompt)
    # Add Socratic coaching prompt if enabled (and no custom role)
    elif socratic_mode:
        parts.append(SOCRATIC_SYSTEM_PROMPT)
        if socratic_topic:
            parts.append(SOCRATIC_TOPIC_TEMPLATE.format(topic=socratic_topic))

    # Add file context if files are loaded
    if loaded_files:
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

4. If questions ask for "latest data", provide the most current information you have

Here are the files:

"""
        for filename, content in loaded_files.items():
            file_context += f"--- FILE: {filename} ---\n{content}\n\n"

        parts.append(file_context)

    if not parts:
        return None

    return "\n\n".join(parts)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def print_header():
    """Print the app header."""
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║           🤖  ANTHROPIC CHAT CLI - Claude Terminal           ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def print_divider():
    """Print a divider line."""
    print(f"{Colors.DIM}{'─' * 64}{Colors.RESET}")


def print_help():
    """Print help commands."""
    print(f"""
{Colors.BOLD}Commands:{Colors.RESET}
  {Colors.CYAN}/help{Colors.RESET}          - Show this help message
  {Colors.CYAN}/files{Colors.RESET}         - List loaded context files
  {Colors.CYAN}/load <path>{Colors.RESET}   - Load a text file as context
  {Colors.CYAN}/clear{Colors.RESET}         - Clear conversation history
  {Colors.CYAN}/save <path>{Colors.RESET}   - Save conversation to file
  {Colors.CYAN}/model{Colors.RESET}         - Change Claude model
  {Colors.CYAN}/history{Colors.RESET}       - Show conversation history
  {Colors.CYAN}/quit{Colors.RESET}          - Exit the program

{Colors.BOLD}Socratic Coaching:{Colors.RESET}
  {Colors.MAGENTA}/socratic{Colors.RESET}      - Toggle Socratic coaching mode
  {Colors.MAGENTA}/topic <name>{Colors.RESET}  - Set coaching topic (e.g., /topic Python)
  {Colors.MAGENTA}/status{Colors.RESET}        - Show current mode and settings
""")


def display_loaded_files(loaded_files: Dict[str, str]):
    """Display currently loaded files."""
    if not loaded_files:
        print(f"{Colors.YELLOW}No files loaded.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}Loaded Files:{Colors.RESET}")
    total_chars = 0
    for filename, content in loaded_files.items():
        char_count = len(content)
        total_chars += char_count
        print(f"  {Colors.GREEN}•{Colors.RESET} {filename} ({char_count:,} chars)")
    print(f"\n{Colors.DIM}Total: {len(loaded_files)} files, {total_chars:,} characters{Colors.RESET}")


def display_history(messages: List[Dict]):
    """Display conversation history."""
    if not messages:
        print(f"{Colors.YELLOW}No conversation history.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}Conversation History:{Colors.RESET}\n")
    for i, msg in enumerate(messages, 1):
        role = msg["role"]
        content = msg["content"]
        # Truncate long messages for display
        if len(content) > 200:
            content = content[:200] + "..."

        if role == "user":
            print(f"{Colors.BLUE}[{i}] User:{Colors.RESET} {content}")
        else:
            print(f"{Colors.GREEN}[{i}] Assistant:{Colors.RESET} {content}")
        print()


def select_model() -> tuple:
    """Interactive model selection."""
    print(f"\n{Colors.BOLD}Select Claude model:{Colors.RESET}")
    for key, (name, _) in AVAILABLE_MODELS.items():
        cost_note = ""
        if key == "4":
            cost_note = f" {Colors.ORANGE}(highest cost){Colors.RESET}"
        elif key == "1":
            cost_note = f" {Colors.GREEN}(fastest, lowest cost){Colors.RESET}"
        print(f"  [{key}] {name}{cost_note}")

    choice = input(f"\nChoice (default=1): ").strip() or "1"
    if choice not in AVAILABLE_MODELS:
        choice = "1"

    return AVAILABLE_MODELS[choice]


def stream_response(client: anthropic.Anthropic, model: str,
                   system_prompt: Optional[str], messages: List[Dict]) -> str:
    """Stream a response from Claude."""
    api_params = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
    }

    if system_prompt:
        api_params["system"] = system_prompt

    response_text = ""
    print(f"\n{Colors.GREEN}{Colors.BOLD}Assistant:{Colors.RESET} ", end="", flush=True)

    try:
        with client.messages.stream(**api_params) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                response_text += text
        print("\n")
    except Exception as e:
        error_msg = f"\n{Colors.RED}Error: {str(e)}{Colors.RESET}\n"
        print(error_msg)
        return ""

    return response_text


def display_status(socratic_mode: bool, socratic_topic: Optional[str],
                   model_name: str, loaded_files: Dict[str, str],
                   role_name: Optional[str] = None):
    """Display current settings and mode."""
    print(f"\n{Colors.BOLD}Current Settings:{Colors.RESET}")
    print(f"  Model: {Colors.CYAN}{model_name}{Colors.RESET}")

    if role_name:
        print(f"  Role: {Colors.MAGENTA}{role_name}{Colors.RESET}")
    elif socratic_mode:
        print(f"  Socratic Mode: {Colors.MAGENTA}ON{Colors.RESET}")
        if socratic_topic:
            print(f"  Topic: {Colors.MAGENTA}{socratic_topic}{Colors.RESET}")
        else:
            print(f"  Topic: {Colors.DIM}(none set){Colors.RESET}")
    else:
        print(f"  Role: {Colors.DIM}(none){Colors.RESET}")

    if loaded_files:
        print(f"  Files Loaded: {Colors.GREEN}{len(loaded_files)}{Colors.RESET}")
    else:
        print(f"  Files Loaded: {Colors.DIM}0{Colors.RESET}")
    print()


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Anthropic Chat CLI - Interactive Claude conversations"
    )
    parser.add_argument(
        "-f", "--files",
        nargs="+",
        help="Text files to load as context"
    )
    parser.add_argument(
        "-d", "--directory",
        help="Directory to scan for text files"
    )
    parser.add_argument(
        "--model",
        choices=["1", "2", "3", "4", "haiku", "sonnet", "sonnet4", "opus"],
        default="1",
        help="Claude model: 1/haiku, 2/sonnet, 3/sonnet4, 4/opus (default: 1)"
    )
    parser.add_argument(
        "-s", "--socratic",
        action="store_true",
        help="Enable Socratic coaching mode (built-in prompt)"
    )
    parser.add_argument(
        "-t", "--topic",
        help="Set Socratic coaching topic (e.g., 'Python', 'Chess', 'Math')"
    )
    parser.add_argument(
        "-r", "--role",
        help="Role prompt: 'socratic' (built-in), or path to .md/.txt file with custom role"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export loaded files as context and exit (for use with Claude Code)"
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Export files and role for Claude Code to process natively (no API key needed)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path for --native or --export mode (default: prints to stdout)"
    )
    parser.add_argument(
        "-c", "--clipboard",
        action="store_true",
        help="Read content from clipboard (use with --native)"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Instruction/prompt for Claude (e.g., 'summarize')"
    )
    args = parser.parse_args()

    # Export mode: load files and print context for Claude Code, then exit
    if args.export:
        loaded_files: Dict[str, str] = {}

        # Load context files if provided
        if args.files:
            for file_path in args.files:
                if os.path.exists(file_path):
                    content = extract_text(file_path)
                    filename = os.path.basename(file_path)
                    loaded_files[filename] = content

        # Scan directory if provided
        if args.directory:
            files = scan_folder(args.directory)
            for file_path in files:
                content = extract_text(file_path)
                filename = os.path.basename(file_path)
                loaded_files[filename] = content

        if not loaded_files:
            print("No files found to export.")
            sys.exit(1)

        # Filter out files over 100,000 characters (same limit as web app)
        MAX_CHARS_FOR_CHAT = 100000
        included_files = {k: v for k, v in loaded_files.items() if len(v) <= MAX_CHARS_FOR_CHAT}
        excluded_files = {k: v for k, v in loaded_files.items() if len(v) > MAX_CHARS_FOR_CHAT}

        # Warn about excluded files
        if excluded_files:
            print(f"=== WARNING: {len(excluded_files)} FILE(S) EXCLUDED (over {MAX_CHARS_FOR_CHAT:,} chars) ===")
            for filename, content in excluded_files.items():
                print(f"  - {filename} ({len(content):,} chars)")
            print()

        if not included_files:
            print("No files under the character limit to export.")
            sys.exit(1)

        # Print file context in a format Claude Code can use
        print(f"=== CONTEXT FROM {len(included_files)} FILE(S) ===\n")
        for filename, content in included_files.items():
            print(f"--- FILE: {filename} ({len(content):,} chars) ---")
            print(content)
            print()
        print(f"=== END OF CONTEXT ===")
        print(f"\nTotal: {len(included_files)} files, {sum(len(c) for c in included_files.values()):,} characters")
        if excluded_files:
            print(f"Excluded: {len(excluded_files)} files over {MAX_CHARS_FOR_CHAT:,} char limit")
        sys.exit(0)

    # Native mode: export files AND role for Claude Code to process
    if args.native:
        loaded_files: Dict[str, str] = {}
        role_content: Optional[str] = None
        role_name: Optional[str] = None
        user_prompt: Optional[str] = args.prompt

        # Handle clipboard
        if args.clipboard:
            clipboard_content = get_clipboard_content()
            if clipboard_content.strip():
                loaded_files["clipboard.txt"] = clipboard_content
                print(f"Loaded clipboard content ({len(clipboard_content):,} chars)")
            else:
                print("Warning: Clipboard is empty")

        # Handle role
        if args.role:
            if args.role.lower() == 'socratic':
                role_content = SOCRATIC_SYSTEM_PROMPT
                role_name = "Socratic Coach (built-in)"
                if args.topic:
                    role_content += "\n\n" + SOCRATIC_TOPIC_TEMPLATE.format(topic=args.topic)
            elif os.path.exists(args.role):
                role_content = extract_text(args.role)
                role_name = os.path.basename(args.role)
        elif args.socratic:
            role_content = SOCRATIC_SYSTEM_PROMPT
            role_name = "Socratic Coach (built-in)"
            if args.topic:
                role_content += "\n\n" + SOCRATIC_TOPIC_TEMPLATE.format(topic=args.topic)

        # Load context files if provided
        if args.files:
            for file_path in args.files:
                if os.path.exists(file_path):
                    content = extract_text(file_path)
                    filename = os.path.basename(file_path)
                    loaded_files[filename] = content

        # Scan directory if provided
        if args.directory:
            files = scan_folder(args.directory)
            for file_path in files:
                content = extract_text(file_path)
                filename = os.path.basename(file_path)
                loaded_files[filename] = content

        # Filter out files over 100,000 characters
        MAX_CHARS_FOR_CHAT = 100000
        included_files = {k: v for k, v in loaded_files.items() if len(v) <= MAX_CHARS_FOR_CHAT}
        excluded_files = {k: v for k, v in loaded_files.items() if len(v) > MAX_CHARS_FOR_CHAT}

        # If no files and no role, use topic or prompt for one
        if not included_files and not role_content:
            topic = args.topic
            if not topic:
                print("No files or role provided.")
                try:
                    topic = input("What would you like to discuss? ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    sys.exit(1)
            if not topic:
                print("No topic provided. Exiting.")
                sys.exit(1)
            # Create a simple context with the topic
            role_content = f"The user wants to discuss: {topic}\n\nPlease help them explore this topic."
            role_name = f"Topic: {topic}"

        # If we have a role but no files, add topic if provided or prompt
        elif role_content and not included_files:
            topic = args.topic
            if not topic:
                try:
                    topic = input("What would you like to discuss? ").strip()
                except (EOFError, KeyboardInterrupt):
                    pass  # Continue with just the role
            if topic:
                role_content += f"\n\nThe user's question/topic: {topic}"

        # Build the full output
        output_lines = []
        if role_content:
            output_lines.append(f"=== ROLE: {role_name} ===")
            output_lines.append(role_content)
            output_lines.append("=== END ROLE ===\n")

        if excluded_files:
            output_lines.append(f"=== WARNING: {len(excluded_files)} FILE(S) EXCLUDED (over {MAX_CHARS_FOR_CHAT:,} chars) ===")
            for fn, cont in excluded_files.items():
                output_lines.append(f"  - {fn} ({len(cont):,} chars)")
            output_lines.append("")

        if included_files:
            output_lines.append(f"=== CONTEXT FROM {len(included_files)} FILE(S) ===\n")
            for fn, cont in included_files.items():
                output_lines.append(f"--- FILE: {fn} ({len(cont):,} chars) ---")
                output_lines.append(cont)
                output_lines.append("")
            output_lines.append("=== END OF CONTEXT ===")
            output_lines.append(f"\nTotal: {len(included_files)} files, {sum(len(c) for c in included_files.values()):,} characters")

        if user_prompt:
            output_lines.append(f"\n=== USER REQUEST ===")
            output_lines.append(user_prompt)
            output_lines.append("=== END REQUEST ===")
        else:
            output_lines.append("\n=== CLAUDE CODE: Please use the above context and role to assist the user ===")

        full_output = "\n".join(output_lines)

        # Write to file (default: claude_context.txt in current directory)
        output_file = args.output if args.output else "claude_context.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_output)

        # Print the context directly so Claude Code sees it and can respond
        print(full_output)
        print(f"\n[Context also saved to: {output_file}]")
        sys.exit(0)

    print_header()

    # Get API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print(f"{Colors.DIM}Tip: Set ANTHROPIC_API_KEY env var to skip this prompt{Colors.RESET}")
        api_key = input(f"{Colors.BOLD}Enter your Anthropic API key:{Colors.RESET} ").strip()
        if not api_key:
            print(f"{Colors.RED}API key required. Exiting.{Colors.RESET}")
            sys.exit(1)

    # Initialize client
    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"{Colors.RED}Error initializing client: {e}{Colors.RESET}")
        sys.exit(1)

    # Select model
    model_choice = MODEL_ALIASES.get(args.model, args.model)
    model_name, model_id = AVAILABLE_MODELS[model_choice]
    print(f"{Colors.DIM}Using {model_name}{Colors.RESET}")

    print_divider()

    # Initialize state
    messages: List[Dict] = []
    loaded_files: Dict[str, str] = {}
    socratic_mode: bool = args.socratic
    socratic_topic: Optional[str] = args.topic
    role_prompt: Optional[str] = None
    role_name: Optional[str] = None

    # Handle --role argument
    if args.role:
        if args.role.lower() == 'socratic':
            # Use built-in Socratic prompt
            socratic_mode = True
            role_name = "Socratic Coach (built-in)"
        elif os.path.exists(args.role):
            # Load role from file
            role_prompt = extract_text(args.role)
            role_name = os.path.basename(args.role)
            print(f"{Colors.MAGENTA}Role loaded: {role_name} ({len(role_prompt):,} chars){Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Role file not found: {args.role}{Colors.RESET}")
            print(f"{Colors.YELLOW}Use 'socratic' for built-in, or provide a valid file path{Colors.RESET}")

    # Show Socratic mode status if enabled
    if socratic_mode:
        print(f"{Colors.MAGENTA}Socratic coaching mode: ON{Colors.RESET}")
        if socratic_topic:
            print(f"{Colors.MAGENTA}Topic: {socratic_topic}{Colors.RESET}")

    # Load context files if provided
    if args.files:
        for file_path in args.files:
            if os.path.exists(file_path):
                content = extract_text(file_path)
                filename = os.path.basename(file_path)
                loaded_files[filename] = content
                print(f"{Colors.GREEN}Loaded: {filename}{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}File not found: {file_path}{Colors.RESET}")

    # Scan directory if provided
    if args.directory:
        files = scan_folder(args.directory)
        for file_path in files:
            content = extract_text(file_path)
            filename = os.path.basename(file_path)
            loaded_files[filename] = content
        print(f"{Colors.GREEN}Loaded {len(files)} files from {args.directory}{Colors.RESET}")

    # Show loaded context
    if loaded_files:
        display_loaded_files(loaded_files)
        print()

    print(f"{Colors.DIM}Type /help for commands, or start chatting!{Colors.RESET}\n")

    # Main chat loop
    while True:
        try:
            # Show different prompt based on role/Socratic mode
            if role_prompt:
                prompt_prefix = f"{Colors.MAGENTA}[{role_name}]{Colors.RESET} {Colors.BLUE}{Colors.BOLD}You:{Colors.RESET} "
            elif socratic_mode:
                prompt_prefix = f"{Colors.MAGENTA}[Socratic]{Colors.RESET} {Colors.BLUE}{Colors.BOLD}You:{Colors.RESET} "
            else:
                prompt_prefix = f"{Colors.BLUE}{Colors.BOLD}You:{Colors.RESET} "
            user_input = input(prompt_prefix).strip()
        except EOFError:
            break
        except KeyboardInterrupt:
            print(f"\n\n{Colors.CYAN}Goodbye!{Colors.RESET}")
            sys.exit(0)

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith('/'):
            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            cmd_arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

            if cmd in ['/quit', '/exit', '/q']:
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                break

            elif cmd == '/help':
                print_help()

            elif cmd == '/files':
                display_loaded_files(loaded_files)

            elif cmd == '/load':
                if cmd_arg:
                    if os.path.exists(cmd_arg):
                        content = extract_text(cmd_arg)
                        filename = os.path.basename(cmd_arg)
                        loaded_files[filename] = content
                        print(f"{Colors.GREEN}Loaded: {filename} ({len(content):,} chars){Colors.RESET}")
                    else:
                        print(f"{Colors.RED}File not found: {cmd_arg}{Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}Usage: /load <filepath>{Colors.RESET}")

            elif cmd == '/clear':
                messages = []
                print(f"{Colors.GREEN}Conversation cleared.{Colors.RESET}")

            elif cmd == '/save':
                if cmd_arg:
                    save_conversation(cmd_arg, messages)
                else:
                    print(f"{Colors.YELLOW}Usage: /save <filepath>{Colors.RESET}")

            elif cmd == '/model':
                model_name, model_id = select_model()
                print(f"{Colors.GREEN}Switched to {model_name}{Colors.RESET}")

            elif cmd == '/history':
                display_history(messages)

            elif cmd == '/socratic':
                socratic_mode = not socratic_mode
                if socratic_mode:
                    print(f"{Colors.MAGENTA}Socratic coaching mode: ON{Colors.RESET}")
                    print(f"{Colors.DIM}Claude will now guide you through questions rather than giving direct answers.{Colors.RESET}")
                    if not socratic_topic:
                        print(f"{Colors.DIM}Tip: Use /topic <name> to set a coaching topic{Colors.RESET}")
                else:
                    print(f"{Colors.DIM}Socratic coaching mode: OFF{Colors.RESET}")

            elif cmd == '/topic':
                if cmd_arg:
                    socratic_topic = cmd_arg
                    print(f"{Colors.MAGENTA}Topic set to: {socratic_topic}{Colors.RESET}")
                    if not socratic_mode:
                        socratic_mode = True
                        print(f"{Colors.MAGENTA}Socratic coaching mode: ON{Colors.RESET}")
                else:
                    if socratic_topic:
                        socratic_topic = None
                        print(f"{Colors.DIM}Topic cleared{Colors.RESET}")
                    else:
                        print(f"{Colors.YELLOW}Usage: /topic <name> (e.g., /topic Python){Colors.RESET}")

            elif cmd == '/status':
                display_status(socratic_mode, socratic_topic, model_name, loaded_files, role_name)

            else:
                print(f"{Colors.YELLOW}Unknown command: {cmd}. Type /help for commands.{Colors.RESET}")

            continue

        # Add user message
        messages.append({"role": "user", "content": user_input})

        # Build system prompt with file context, Socratic mode, and custom role
        system_prompt = build_system_prompt(loaded_files, socratic_mode, socratic_topic, role_prompt)

        # Stream response
        if model_id == "claude-opus-4-5-20251101":
            print(f"{Colors.ORANGE}Note: Using Opus 4.5 (higher cost){Colors.RESET}")

        response = stream_response(client, model_id, system_prompt, messages)

        if response:
            messages.append({"role": "assistant", "content": response})
        else:
            # Remove failed user message
            messages.pop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.CYAN}Goodbye!{Colors.RESET}")
        sys.exit(0)
