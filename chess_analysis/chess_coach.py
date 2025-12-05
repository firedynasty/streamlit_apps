"""
Chess Analyzer with Socratic Coaching
=====================================
A Streamlit app that analyzes chess games and provides AI-powered coaching
using Claude to help players understand their mistakes through Socratic questioning.
"""

import streamlit as st
import chess
import chess.pgn
import requests
import io
import re
import anthropic
from openai import OpenAI
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Chess Coach - AI Analysis",
    page_icon="♟️",
    layout="wide"
)

# ============================================================================
# CONSTANTS
# ============================================================================

# Evaluation thresholds (in centipawns)
BLUNDER_THRESHOLD = -200
MISTAKE_THRESHOLD = -100
INACCURACY_THRESHOLD = -50

# Available Claude models
ANTHROPIC_MODELS = {
    "Claude 3.5 Haiku": "claude-3-5-haiku-20241022",
    "Claude 3.5 Sonnet": "claude-3-5-sonnet-20241022",
    "Claude Sonnet 4": "claude-sonnet-4-20250514",
}

# Available OpenAI models
OPENAI_MODELS = {
    "GPT-4o Mini": "gpt-4o-mini",
    "GPT-4o": "gpt-4o",
    "GPT-4 Turbo": "gpt-4-turbo",
    "GPT-3.5 Turbo": "gpt-3.5-turbo",
}

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OpeningDeviation:
    """Represents a deviation from opening theory"""
    move_number: int
    notation: str  # e.g., "5..." or "6."
    move_played: str
    main_line_move: str
    main_line_percentage: float
    alternatives: str  # e.g., "Nf6 (58.3%), Bb6 (16.1%)"
    total_games: int
    fen: str
    opening_name: str = ""
    is_white: bool = True


@dataclass
class MoveError:
    """Represents a blunder, mistake, or inaccuracy"""
    move_number: int
    notation: str
    move: str
    severity: str  # BLUNDER, MISTAKE, INACCURACY
    eval_before: float
    eval_after: float
    swing: float
    fen: str
    is_white: bool = True


# ============================================================================
# LICHESS API FUNCTIONS
# ============================================================================

def get_opening_info(fen: str) -> Optional[Dict]:
    """Get opening name from Lichess Explorer API"""
    try:
        response = requests.get(
            f"https://explorer.lichess.ovh/masters?fen={requests.utils.quote(fen)}",
            timeout=5
        )
        if response.ok:
            data = response.json()
            if data.get('opening'):
                return {
                    'eco': data['opening'].get('eco', ''),
                    'name': data['opening'].get('name', '')
                }
    except Exception:
        pass
    return None


def get_opening_moves(fen: str) -> Optional[Dict]:
    """Get book moves and statistics from Lichess Explorer"""
    try:
        response = requests.get(
            f"https://explorer.lichess.ovh/masters?fen={requests.utils.quote(fen)}&topGames=0",
            timeout=5
        )
        if response.ok:
            data = response.json()
            if data.get('moves') and len(data['moves']) > 0:
                total_games = data.get('white', 0) + data.get('draws', 0) + data.get('black', 0)
                moves = []
                for m in data['moves'][:5]:
                    m_total = m.get('white', 0) + m.get('draws', 0) + m.get('black', 0)
                    pct = (m_total / total_games * 100) if total_games > 0 else 0
                    moves.append({
                        'san': m['san'],
                        'games': m_total,
                        'percentage': round(pct, 1)
                    })
                return {
                    'moves': moves,
                    'total_games': total_games,
                    'opening': data.get('opening')
                }
    except Exception:
        pass
    return None


def get_lichess_cloud_eval(fen: str) -> Optional[Dict]:
    """Get cloud evaluation from Lichess"""
    try:
        response = requests.get(
            f"https://lichess.org/api/cloud-eval?fen={requests.utils.quote(fen)}&multiPv=1",
            timeout=5
        )
        if response.status_code == 404:
            return None
        if response.ok:
            data = response.json()
            if data.get('pvs') and len(data['pvs']) > 0:
                pv = data['pvs'][0]
                if 'mate' in pv:
                    mate = pv['mate']
                    score = (10000 - abs(mate)) if mate > 0 else (-10000 + abs(mate))
                else:
                    score = pv.get('cp', 0)
                return {
                    'score': score,
                    'depth': data.get('depth', 0),
                    'best_move': pv.get('moves', '').split()[0] if pv.get('moves') else None
                }
    except Exception:
        pass
    return None


# ============================================================================
# CHESS.COM API FUNCTIONS
# ============================================================================

def fetch_chesscom_recent_games(username: str, num_games: int = 5) -> Dict[str, Dict]:
    """
    Fetch recent games from Chess.com for a given username.

    Returns a dictionary suitable for use as a dropdown:
    {
        "Game 1: Username vs Opponent (Win) - Dec 5": {"pgn": "...", "metadata": {...}},
        "Game 2: Opponent vs Username (Loss) - Dec 5": {"pgn": "...", "metadata": {...}},
        ...
    }
    """
    username = username.lower().strip()
    if not username:
        return {}

    headers = {
        'User-Agent': 'Chess Coach Streamlit App (Python/requests)'
    }

    games_dict = {}

    try:
        # Get current month's archive
        now = datetime.now()
        year = now.year
        month = str(now.month).zfill(2)

        archive_url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month}"
        response = requests.get(archive_url, headers=headers, timeout=10)

        games_list = []

        if response.ok:
            data = response.json()
            if 'games' in data:
                games_list.extend(data['games'])

        # If not enough games, try previous month
        if len(games_list) < num_games:
            prev_month = now.month - 1
            prev_year = now.year
            if prev_month == 0:
                prev_month = 12
                prev_year -= 1

            prev_archive_url = f"https://api.chess.com/pub/player/{username}/games/{prev_year}/{str(prev_month).zfill(2)}"
            time.sleep(0.5)  # Rate limiting
            prev_response = requests.get(prev_archive_url, headers=headers, timeout=10)

            if prev_response.ok:
                prev_data = prev_response.json()
                if 'games' in prev_data:
                    games_list.extend(prev_data['games'])

        # Sort by end_time (most recent first) and take last N games
        games_list.sort(key=lambda g: g.get('end_time', 0), reverse=True)
        recent_games = games_list[:num_games]

        # Build the dictionary
        for idx, game in enumerate(recent_games, 1):
            if 'pgn' not in game:
                continue

            # Extract metadata
            white = game.get('white', {})
            black = game.get('black', {})
            white_username = white.get('username', 'Unknown')
            black_username = black.get('username', 'Unknown')
            white_result = white.get('result', '')
            black_result = black.get('result', '')

            # Determine result for display
            if username.lower() == white_username.lower():
                opponent = black_username
                if white_result == 'win':
                    result_display = 'Win'
                elif black_result == 'win':
                    result_display = 'Loss'
                else:
                    result_display = 'Draw'
                player_color = 'White'
            else:
                opponent = white_username
                if black_result == 'win':
                    result_display = 'Win'
                elif white_result == 'win':
                    result_display = 'Loss'
                else:
                    result_display = 'Draw'
                player_color = 'Black'

            # Format date
            end_time = game.get('end_time', 0)
            if end_time:
                game_date = datetime.fromtimestamp(end_time).strftime('%b %d')
            else:
                game_date = 'Unknown'

            # Time control
            time_class = game.get('time_class', 'unknown')

            # Create display label
            label = f"Game {idx}: vs {opponent} ({result_display} as {player_color}) - {time_class} - {game_date}"

            # Store game data
            games_dict[label] = {
                'pgn': game['pgn'],
                'metadata': {
                    'white': white_username,
                    'black': black_username,
                    'white_rating': white.get('rating', '?'),
                    'black_rating': black.get('rating', '?'),
                    'result': game.get('result', 'Unknown'),
                    'time_class': time_class,
                    'time_control': game.get('time_control', ''),
                    'url': game.get('url', ''),
                    'end_time': end_time
                }
            }

        return games_dict

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching games: {str(e)}")
        return {}
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return {}


def extract_pgn_moves(pgn_text: str) -> str:
    """Extract just the moves from PGN (remove headers and annotations)"""
    lines = pgn_text.split('\n')
    move_lines = []

    for line in lines:
        line = line.strip()
        # Skip empty lines and header lines (starting with [)
        if not line or line.startswith('['):
            continue
        move_lines.append(line)

    # Join all move lines
    moves_text = ' '.join(move_lines)

    # Remove clock annotations
    moves_text = re.sub(r'\{[^}]*\}', '', moves_text)
    # Remove eval annotations
    moves_text = re.sub(r'\([^)]*\)', '', moves_text)
    # Remove Chess.com specific annotations like [%clk 0:05:00]
    moves_text = re.sub(r'\[%[^\]]*\]', '', moves_text)
    # Clean up whitespace
    moves_text = re.sub(r'\s+', ' ', moves_text).strip()

    return moves_text


# ============================================================================
# CHESS ANALYSIS
# ============================================================================

def clean_pgn(pgn: str) -> str:
    """Remove annotations from PGN"""
    import re
    # Remove NAG annotations ($1, $2, etc.)
    cleaned = re.sub(r'\$\d+', '', pgn)
    # Remove comments in curly braces
    cleaned = re.sub(r'\{[^}]*\}', '', cleaned)
    # Remove variations in parentheses
    cleaned = re.sub(r'\([^)]*\)', '', cleaned)
    # Remove clock annotations
    cleaned = re.sub(r'\[%[^\]]*\]', '', cleaned)
    # Clean up whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def analyze_game(pgn_text: str, progress_callback=None) -> Tuple[List[OpeningDeviation], List[MoveError], Optional[Dict]]:
    """
    Analyze a chess game and return deviations and errors.

    Returns:
        Tuple of (opening_deviations, move_errors, opening_info)
    """
    pgn_text = clean_pgn(pgn_text)

    # Parse PGN
    board = chess.Board()
    moves = []

    # Try to parse as PGN first
    try:
        pgn_io = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)
        if game:
            moves = list(game.mainline_moves())
    except Exception:
        pass

    # If PGN parsing failed, try as move list
    if not moves:
        board.reset()
        # Remove move numbers and parse
        import re
        move_text = re.sub(r'\d+\.+', '', pgn_text)
        move_tokens = move_text.strip().split()
        for token in move_tokens:
            token = token.strip()
            if not token or token in ['1-0', '0-1', '1/2-1/2', '*']:
                continue
            try:
                move = board.parse_san(token)
                moves.append(move)
                board.push(move)
            except Exception:
                continue

    if not moves:
        return [], [], None

    total_moves = len(moves)
    board.reset()

    # Phase 1: Detect opening deviations
    opening_deviations = []
    opening_info = None
    left_book = False

    temp_board = chess.Board()
    for i, move in enumerate(moves[:30]):  # Check first 30 moves for opening
        if left_book:
            break

        fen_before = temp_board.fen()
        move_san = temp_board.san(move)
        move_num = i // 2 + 1
        is_white = i % 2 == 0
        notation = f"{move_num}." if is_white else f"{move_num}..."

        # Get book moves for this position
        book_data = get_opening_moves(fen_before)

        # Make the move
        temp_board.push(move)

        # Update opening name
        opening = get_opening_info(temp_board.fen())
        if opening:
            opening_info = opening

        # Check if move is in book
        if book_data and book_data['moves']:
            book_moves = [m['san'] for m in book_data['moves']]
            is_book_move = move_san in book_moves

            if not is_book_move:
                # Player deviated from book
                left_book = True
                top_move = book_data['moves'][0]
                alternatives = ', '.join([f"{m['san']} ({m['percentage']}%)" for m in book_data['moves'][:3]])

                opening_deviations.append(OpeningDeviation(
                    move_number=move_num,
                    notation=notation,
                    move_played=move_san,
                    main_line_move=top_move['san'],
                    main_line_percentage=top_move['percentage'],
                    alternatives=alternatives,
                    total_games=book_data['total_games'],
                    fen=fen_before,
                    opening_name=opening_info['name'] if opening_info else "",
                    is_white=is_white
                ))
        elif not book_data or not book_data['moves']:
            left_book = True

    # Phase 2: Evaluate positions (cap at 20 moves - Lichess cloud eval works best for common positions)
    MAX_EVAL_MOVES = 20
    moves_to_eval = min(len(moves), MAX_EVAL_MOVES)

    if progress_callback:
        progress_callback(0, "Evaluating positions...")

    board.reset()
    evaluations = []

    # Get starting position eval
    eval_result = get_lichess_cloud_eval(board.fen())
    evaluations.append(eval_result['score'] if eval_result else 0)

    for i, move in enumerate(moves[:moves_to_eval]):
        board.push(move)
        eval_result = get_lichess_cloud_eval(board.fen())
        evaluations.append(eval_result['score'] if eval_result else evaluations[-1])

        if progress_callback:
            progress_callback((i + 1) / moves_to_eval, f"Evaluating move {i + 1}/{moves_to_eval}")

        # Small delay to be nice to Lichess API
        time.sleep(0.1)

    # Phase 3: Find mistakes (only for evaluated moves)
    board.reset()
    move_errors = []

    for i, move in enumerate(moves[:moves_to_eval]):
        move_san = board.san(move)
        move_num = i // 2 + 1
        is_white = i % 2 == 0
        notation = f"{move_num}." if is_white else f"{move_num}..."
        fen_before = board.fen()

        eval_before = evaluations[i]
        eval_after = evaluations[i + 1]

        # Calculate swing from the perspective of the player who moved
        # Lichess cloud returns eval from white's perspective
        if is_white:
            swing = eval_after - eval_before
            eval_before_display = eval_before
            eval_after_display = eval_after
        else:
            swing = eval_before - eval_after
            # Show from black's perspective (negate)
            eval_before_display = -eval_before
            eval_after_display = -eval_after

        board.push(move)

        # Classify
        severity = None
        if swing <= BLUNDER_THRESHOLD:
            severity = 'BLUNDER'
        elif swing <= MISTAKE_THRESHOLD:
            severity = 'MISTAKE'
        elif swing <= INACCURACY_THRESHOLD:
            severity = 'INACCURACY'

        if severity:
            move_errors.append(MoveError(
                move_number=move_num,
                notation=notation,
                move=move_san,
                severity=severity,
                eval_before=eval_before_display,
                eval_after=eval_after_display,
                swing=swing,
                fen=fen_before,
                is_white=is_white
            ))

    return opening_deviations, move_errors, opening_info


# ============================================================================
# SOCRATIC COACHING PROMPTS
# ============================================================================

def get_deviation_prompts(deviation: OpeningDeviation) -> List[Dict[str, str]]:
    """Get pre-defined prompts for opening deviations - sentence starters for user to complete"""
    move = deviation.move_played
    main = deviation.main_line_move
    opening = deviation.opening_name if deviation.opening_name else "this opening"

    return [
        {
            "label": "I played this because...",
            "starter": f"In the {opening}, I played {move} instead of {main} because "
        },
        {
            "label": "I thought the main line...",
            "starter": f"I considered {main} but I thought "
        },
        {
            "label": "My plan was...",
            "starter": f"After {move}, my plan was to "
        },
        {
            "label": "I was worried about...",
            "starter": f"I avoided {main} because I was worried about "
        }
    ]


def get_error_prompts(error: MoveError) -> List[Dict[str, str]]:
    """Get pre-defined prompts for move errors - sentence starters for user to complete"""
    move = error.move
    severity = error.severity.lower()

    return [
        {
            "label": "I played this because...",
            "starter": f"I played {error.notation} {move} because "
        },
        {
            "label": "I was trying to...",
            "starter": f"With {move}, I was trying to "
        },
        {
            "label": "I didn't see...",
            "starter": f"After playing {move}, I realize I didn't see "
        },
        {
            "label": "I thought my opponent...",
            "starter": f"I expected my opponent to respond with "
        }
    ]


def build_coaching_system_prompt(context_type: str, context_data: dict) -> str:
    """Build the system prompt for Claude coaching"""

    base_prompt = """You are a thoughtful chess coach using the Socratic method. Your role is to guide players to discover insights rather than lecturing them.

COACHING PRINCIPLES:
1. Start with validation - find what's reasonable in their thinking
2. Ask probing questions - help them discover what they missed
3. Teach principles - connect to broader chess understanding
4. Give concrete actions - one specific thing to study or practice

TONE: Encouraging, curious, thought-provoking. Like a wise mentor, not a critic.

IMPORTANT:
- Don't just cite engine evaluations
- Help build intuition and pattern recognition
- Keep responses focused and under 200 words
- End with a thought-provoking question or concrete study suggestion
"""

    if context_type == "deviation":
        dev = context_data
        return base_prompt + f"""

CURRENT CONTEXT - OPENING DEVIATION:
- Move played: {dev['move_played']}
- Main theory: {dev['main_line']} ({dev['percentage']}% of master games)
- Alternatives: {dev['alternatives']}
- Opening: {dev['opening_name']}
- Position (FEN): {dev['fen']}

Focus on helping them understand opening principles and why theory developed this way."""

    elif context_type == "error":
        err = context_data
        return base_prompt + f"""

CURRENT CONTEXT - {err['severity']}:
- Move played: {err['notation']} {err['move']}
- Evaluation change: {err['eval_before']:.2f} → {err['eval_after']:.2f}
- Position (FEN): {err['fen']}

Focus on helping them understand what they missed and how to spot similar patterns."""

    return base_prompt


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize all session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
    if "selected_item" not in st.session_state:
        st.session_state.selected_item = None
    if "selected_item_type" not in st.session_state:
        st.session_state.selected_item_type = None
    # AI Provider settings (ChatGPT is default)
    if "ai_provider" not in st.session_state:
        st.session_state.ai_provider = "ChatGPT"  # Default to ChatGPT
    if "anthropic_model" not in st.session_state:
        st.session_state.anthropic_model = "claude-3-5-haiku-20241022"
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4o-mini"
    if "coaching_context" not in st.session_state:
        st.session_state.coaching_context = None
    if "draft_message" not in st.session_state:
        st.session_state.draft_message = ""
    # Chess.com game fetching
    if "chesscom_username" not in st.session_state:
        st.session_state.chesscom_username = ""
    if "fetched_games" not in st.session_state:
        st.session_state.fetched_games = {}  # Dictionary of games for dropdown
    if "selected_game_key" not in st.session_state:
        st.session_state.selected_game_key = None


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    init_session_state()

    st.title("♟️ Chess Coach - AI Analysis")
    st.markdown("*Analyze your games and learn from your mistakes with Socratic coaching*")
    st.caption("⚠️ Analysis works up to 10 moves only due to Lichess API limitations")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # AI Provider Toggle with border styling and clickable labels
        chatgpt_active = st.session_state.ai_provider == "ChatGPT"
        claude_active = st.session_state.ai_provider == "Anthropic"


        # Clickable provider buttons
        btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 2])
        with btn_col1:
            chatgpt_label = "**ChatGPT**" if chatgpt_active else "ChatGPT"
            if st.button(chatgpt_label, key="btn_chatgpt", use_container_width=True):
                st.session_state.ai_provider = "ChatGPT"
                st.rerun()
        with btn_col2:
            use_anthropic = st.toggle(
                "Switch AI Provider",
                value=claude_active,
                key="provider_toggle",
                label_visibility="collapsed"
            )
            if use_anthropic and not claude_active:
                st.session_state.ai_provider = "Anthropic"
                st.rerun()
            elif not use_anthropic and not chatgpt_active:
                st.session_state.ai_provider = "ChatGPT"
                st.rerun()
        with btn_col3:
            claude_label = "**Claude**" if claude_active else "Claude"
            if st.button(claude_label, key="btn_claude", use_container_width=True):
                st.session_state.ai_provider = "Anthropic"
                st.rerun()

        # Conditional API key and model selection based on provider
        if st.session_state.ai_provider == "ChatGPT":
            api_key = st.text_input("OpenAI API Key:", type="password", key="openai_api_key")

            model_name = st.selectbox(
                "OpenAI Model:",
                options=list(OPENAI_MODELS.keys()),
                index=0
            )
            st.session_state.openai_model = OPENAI_MODELS[model_name]
        else:
            api_key = st.text_input("Anthropic API Key:", type="password", key="anthropic_api_key")

            model_name = st.selectbox(
                "Claude Model:",
                options=list(ANTHROPIC_MODELS.keys()),
                index=0
            )
            st.session_state.anthropic_model = ANTHROPIC_MODELS[model_name]

        st.divider()

        st.header("📊 Analysis Stats")
        if st.session_state.analysis_results:
            deviations, errors, opening = st.session_state.analysis_results

            if opening:
                st.info(f"**Opening:** {opening.get('eco', '')} {opening.get('name', '')}")

            blunders = sum(1 for e in errors if e.severity == 'BLUNDER')
            mistakes = sum(1 for e in errors if e.severity == 'MISTAKE')
            inaccuracies = sum(1 for e in errors if e.severity == 'INACCURACY')

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Blunders", blunders)
            with col2:
                st.metric("Mistakes", mistakes)
            with col3:
                st.metric("Inaccuracies", inaccuracies)

            if deviations:
                st.metric("Opening Deviations", len(deviations))

        st.divider()

        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.selected_item = None
            st.session_state.coaching_context = None
            st.session_state.draft_message = ""
            st.rerun()

    # Main content - Two columns
    col_analysis, col_chat = st.columns([1, 1])

    # Left column - Analysis
    with col_analysis:
        st.subheader("📝 Game Analysis")

        # Chess.com Game Fetching Section
        st.markdown("#### Import from Chess.com")

        col_user, col_fetch = st.columns([3, 1])
        with col_user:
            chesscom_username = st.text_input(
                "Chess.com Username:",
                value=st.session_state.chesscom_username,
                placeholder="Enter your Chess.com username",
                key="chesscom_user_input"
            )
        with col_fetch:
            st.markdown("")  # Spacing
            fetch_clicked = st.button("📥 Fetch Games", use_container_width=True)

        # Handle fetch button
        if fetch_clicked and chesscom_username.strip():
            st.session_state.chesscom_username = chesscom_username.strip()
            with st.spinner(f"Fetching games for {chesscom_username}..."):
                games = fetch_chesscom_recent_games(chesscom_username, num_games=5)
                if games:
                    st.session_state.fetched_games = games
                    st.success(f"Found {len(games)} recent games!")
                else:
                    st.warning("No games found. Check the username and try again.")
                    st.session_state.fetched_games = {}

        # Game selection dropdown (only show if games are fetched)
        if st.session_state.fetched_games:
            game_options = ["-- Select a game --"] + list(st.session_state.fetched_games.keys())

            # Callback to auto-load game when selection changes
            def on_game_select():
                selected = st.session_state.game_dropdown
                if selected and selected != "-- Select a game --":
                    game_data = st.session_state.fetched_games[selected]
                    clean_moves = extract_pgn_moves(game_data['pgn'])
                    st.session_state.pgn_input = clean_moves
                    st.session_state.selected_game_key = selected

            selected_game = st.selectbox(
                "Select a game to analyze:",
                options=game_options,
                key="game_dropdown",
                on_change=on_game_select
            )

            # Show game metadata when a game is selected
            if selected_game and selected_game != "-- Select a game --":
                if selected_game in st.session_state.fetched_games:
                    meta = st.session_state.fetched_games[selected_game]['metadata']
                    # Show link next to Game Details
                    detail_col1, detail_col2 = st.columns([1, 1])
                    with detail_col1:
                        if meta.get('url'):
                            st.markdown(f"[View on Chess.com]({meta['url']})")
                    with st.expander("Game Details"):
                        st.markdown(f"""
                        **White:** {meta['white']} ({meta['white_rating']})
                        **Black:** {meta['black']} ({meta['black_rating']})
                        **Time Control:** {meta['time_class']} ({meta['time_control']})
                        """)

        st.divider()
        st.markdown("#### Or paste PGN manually")

        pgn_input = st.text_area(
            "Paste PGN or moves:",
            height=150,
            placeholder="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6...",
            key="pgn_input"
        )

        if st.button("🔍 Analyze Game", type="primary"):
            if pgn_input.strip():
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(pct, text):
                    progress_bar.progress(pct)
                    status_text.text(text)

                with st.spinner("Analyzing..."):
                    deviations, errors, opening = analyze_game(pgn_input, update_progress)
                    st.session_state.analysis_results = (deviations, errors, opening)
                    st.session_state.messages = []
                    st.session_state.selected_item = None

                progress_bar.empty()
                status_text.empty()
                st.rerun()
            else:
                st.warning("Please enter a PGN or move list")

        # Display results
        if st.session_state.analysis_results:
            deviations, errors, opening = st.session_state.analysis_results

            # Opening deviations
            if deviations:
                st.markdown("### 📚 Opening Deviations")
                for i, dev in enumerate(deviations):
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"""
                            **{dev.notation} {dev.move_played}** ← OUT OF BOOK
                            Main line: **{dev.main_line_move}** ({dev.main_line_percentage}%)
                            *{dev.alternatives}*
                            """)
                        with col2:
                            if st.button("💬 Discuss", key=f"dev_{i}"):
                                st.session_state.selected_item = dev
                                st.session_state.selected_item_type = "deviation"
                                st.session_state.messages = []
                                st.session_state.coaching_context = {
                                    "type": "deviation",
                                    "move_played": dev.move_played,
                                    "main_line": dev.main_line_move,
                                    "percentage": dev.main_line_percentage,
                                    "alternatives": dev.alternatives,
                                    "opening_name": dev.opening_name,
                                    "fen": dev.fen
                                }

                        fen_encoded = dev.fen.replace(' ', '_')
                        st.markdown(f"[Analyze on Lichess](https://lichess.org/analysis/{fen_encoded})")
                        st.divider()

            # Move errors
            if errors:
                st.markdown("### ⚠️ Mistakes & Blunders")
                for i, err in enumerate(errors):
                    severity_color = {
                        'BLUNDER': '🔴',
                        'MISTAKE': '🟠',
                        'INACCURACY': '🟡'
                    }
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"""
                            {severity_color.get(err.severity, '')} **{err.notation} {err.move}** - {err.severity}
                            Eval: {err.eval_before/100:.2f} → {err.eval_after/100:.2f} ({err.swing/100:+.2f})
                            """)
                        with col2:
                            if st.button("💬 Discuss", key=f"err_{i}"):
                                st.session_state.selected_item = err
                                st.session_state.selected_item_type = "error"
                                st.session_state.messages = []
                                st.session_state.coaching_context = {
                                    "type": "error",
                                    "severity": err.severity,
                                    "notation": err.notation,
                                    "move": err.move,
                                    "eval_before": err.eval_before / 100,
                                    "eval_after": err.eval_after / 100,
                                    "fen": err.fen
                                }

                        fen_encoded = err.fen.replace(' ', '_')
                        st.markdown(f"[Analyze on Lichess](https://lichess.org/analysis/{fen_encoded})")
                        st.divider()

            if not deviations and not errors:
                st.success("Great game! No significant mistakes found.")

    # Right column - Chat
    with col_chat:
        st.subheader("🎓 Coaching Chat")

        # Show selected item context
        if st.session_state.selected_item:
            item = st.session_state.selected_item
            item_type = st.session_state.selected_item_type

            if item_type == "deviation":
                opening_label = f" in {item.opening_name}" if item.opening_name else ""
                st.info(f"**Discussing:** {item.notation} {item.move_played}{opening_label} (deviation from {item.main_line_move})")
                prompts = get_deviation_prompts(item)
            else:
                st.info(f"**Discussing:** {item.notation} {item.move} ({item.severity})")
                prompts = get_error_prompts(item)

            # Quick prompt starters - populate the input field
            st.markdown("**Complete your thought:** *(click to start)*")
            cols = st.columns(2)
            for i, prompt_option in enumerate(prompts):
                with cols[i % 2]:
                    if st.button(prompt_option["label"], key=f"prompt_{i}"):
                        # Populate the draft message instead of sending directly
                        st.session_state.draft_message = prompt_option["starter"]
                        st.rerun()
        else:
            st.markdown("*Select a move from the analysis to start discussing it*")

        st.divider()

        # Chat messages
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Message input area with text_area + send button
        st.markdown("**Your message:**")
        user_input = st.text_area(
            "Complete your thought and send:",
            value=st.session_state.draft_message,
            height=100,
            placeholder="Click a prompt starter above, or type your own question...",
            key="message_input",
            label_visibility="collapsed"
        )

        col_send, col_copy, col_clear = st.columns([1, 1, 1])
        with col_send:
            send_clicked = st.button("📤 Send", type="primary", use_container_width=True)
        with col_copy:
            copy_clicked = st.button("📋 Copy Chat", use_container_width=True)
        with col_clear:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.draft_message = ""
                st.rerun()

        # Show copy chat text area when copy is clicked
        if copy_clicked and st.session_state.messages:
            conversation_text = ""
            for msg in st.session_state.messages:
                prefix = "User: " if msg["role"] == "user" else "Assistant: "
                conversation_text += f"{prefix}{msg['content']}\n\n"
            st.text_area(
                "Select all and copy (Ctrl+A, Ctrl+C):",
                conversation_text,
                height=200,
                key="copy_chat_area"
            )
        elif copy_clicked and not st.session_state.messages:
            st.info("No conversation to copy yet.")

        # Handle send
        if send_clicked and user_input.strip():
            st.session_state.messages.append({"role": "user", "content": user_input.strip()})
            st.session_state.draft_message = ""  # Clear draft after sending
            st.rerun()

        # Generate response if needed
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            provider = st.session_state.ai_provider
            api_key_label = "OpenAI" if provider == "ChatGPT" else "Anthropic"

            if not api_key:
                st.warning(f"Please enter your {api_key_label} API key in the sidebar")
            elif st.session_state.coaching_context:
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            # Build system prompt
                            context = st.session_state.coaching_context
                            system_prompt = build_coaching_system_prompt(
                                context["type"],
                                context
                            )

                            # Prepare messages for API
                            api_messages = [
                                {"role": m["role"], "content": m["content"]}
                                for m in st.session_state.messages
                            ]

                            if provider == "ChatGPT":
                                # OpenAI API call
                                client = OpenAI(api_key=api_key)

                                # OpenAI uses system message in messages array
                                openai_messages = [{"role": "system", "content": system_prompt}] + api_messages

                                response = client.chat.completions.create(
                                    model=st.session_state.openai_model,
                                    max_tokens=1024,
                                    messages=openai_messages
                                )

                                assistant_msg = response.choices[0].message.content
                            else:
                                # Anthropic API call
                                client = anthropic.Anthropic(api_key=api_key)

                                response = client.messages.create(
                                    model=st.session_state.anthropic_model,
                                    max_tokens=1024,
                                    system=system_prompt,
                                    messages=api_messages
                                )

                                assistant_msg = response.content[0].text

                            st.markdown(assistant_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": assistant_msg
                            })

                        except Exception as e:
                            st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
