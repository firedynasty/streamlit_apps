
```bash

⏺ Update(chess_coach.py)
  ⎿  Updated chess_coach.py with 161 additions                           
       158    
       159    
       160    # =========================================================
             ===================
       161 +  # CHESS.COM API FUNCTIONS
       162 +  # =========================================================
           + ===================
       163 +  
       164 +  def fetch_chesscom_recent_games(username: str, num_games: 
           + int = 5) -> Dict[str, Dict]:
       165 +      """
       166 +      Fetch recent games from Chess.com for a given username.
       167 +  
       168 +      Returns a dictionary suitable for use as a dropdown:
       169 +      {
       170 +          "Game 1: Username vs Opponent (Win) - Dec 5": 
           + {"pgn": "...", "metadata": {...}},
       171 +          "Game 2: Opponent vs Username (Loss) - Dec 5": 
           + {"pgn": "...", "metadata": {...}},
       172 +          ...
       173 +      }
       174 +      """
       175 +      username = username.lower().strip()
       176 +      if not username:
       177 +          return {}
       178 +  
       179 +      headers = {
       180 +          'User-Agent': 'Chess Coach Streamlit App 
           + (Python/requests)'
       181 +      }
       182 +  
       183 +      games_dict = {}
       184 +  
       185 +      try:
       186 +          # Get current month's archive
       187 +          now = datetime.now()
       188 +          year = now.year
       189 +          month = str(now.month).zfill(2)
       190 +  
       191 +          archive_url = f"https://api.chess.com/pub/player/{u
           + sername}/games/{year}/{month}"
       192 +          response = requests.get(archive_url, 
           + headers=headers, timeout=10)
       193 +  
       194 +          games_list = []
       195 +  
       196 +          if response.ok:
       197 +              data = response.json()
       198 +              if 'games' in data:
       199 +                  games_list.extend(data['games'])
       200 +  
       201 +          # If not enough games, try previous month
       202 +          if len(games_list) < num_games:
       203 +              prev_month = now.month - 1
       204 +              prev_year = now.year
       205 +              if prev_month == 0:
       206 +                  prev_month = 12
       207 +                  prev_year -= 1
       208 +  
       209 +              prev_archive_url = 
           + f"https://api.chess.com/pub/player/{username}/games/{prev_ye
           + ar}/{str(prev_month).zfill(2)}"
       210 +              time.sleep(0.5)  # Rate limiting
       211 +              prev_response = requests.get(prev_archive_url, 
           + headers=headers, timeout=10)
       212 +  
       213 +              if prev_response.ok:
       214 +                  prev_data = prev_response.json()
       215 +                  if 'games' in prev_data:
       216 +                      games_list.extend(prev_data['games'])
       217 +  
       218 +          # Sort by end_time (most recent first) and take 
           + last N games
       219 +          games_list.sort(key=lambda g: g.get('end_time', 0),
           +  reverse=True)
       220 +          recent_games = games_list[:num_games]
       221 +  
       222 +          # Build the dictionary
       223 +          for idx, game in enumerate(recent_games, 1):
       224 +              if 'pgn' not in game:
       225 +                  continue
       226 +  
       227 +              # Extract metadata
       228 +              white = game.get('white', {})
       229 +              black = game.get('black', {})
       230 +              white_username = white.get('username', 
           + 'Unknown')
       231 +              black_username = black.get('username', 
           + 'Unknown')
       232 +              white_result = white.get('result', '')
       233 +              black_result = black.get('result', '')
       234 +  
       235 +              # Determine result for display
       236 +              if username.lower() == white_username.lower():
       237 +                  opponent = black_username
       238 +                  if white_result == 'win':
       239 +                      result_display = 'Win'
       240 +                  elif black_result == 'win':
       241 +                      result_display = 'Loss'
       242 +                  else:
       243 +                      result_display = 'Draw'
       244 +                  player_color = 'White'
       245 +              else:
       246 +                  opponent = white_username
       247 +                  if black_result == 'win':
       248 +                      result_display = 'Win'
       249 +                  elif white_result == 'win':
       250 +                      result_display = 'Loss'
       251 +                  else:
       252 +                      result_display = 'Draw'
       253 +                  player_color = 'Black'
       254 +  
       255 +              # Format date
       256 +              end_time = game.get('end_time', 0)
       257 +              if end_time:
       258 +                  game_date = 
           + datetime.fromtimestamp(end_time).strftime('%b %d')
       259 +              else:
       260 +                  game_date = 'Unknown'
       261 +  
       262 +              # Time control
       263 +              time_class = game.get('time_class', 'unknown')
       264 +  
       265 +              # Create display label
       266 +              label = f"Game {idx}: vs {opponent} 
           + ({result_display}, {player_color}) - {time_class} - 
           + {game_date}"
       267 +  
       268 +              # Store game data
       269 +              games_dict[label] = {
       270 +                  'pgn': game['pgn'],
       271 +                  'metadata': {
       272 +                      'white': white_username,
       273 +                      'black': black_username,
       274 +                      'white_rating': white.get('rating', 
           + '?'),
       275 +                      'black_rating': black.get('rating', 
           + '?'),
       276 +                      'result': game.get('result', 
           + 'Unknown'),
       277 +                      'time_class': time_class,
       278 +                      'time_control': 
           + game.get('time_control', ''),
       279 +                      'url': game.get('url', ''),
       280 +                      'end_time': end_time
       281 +                  }
       282 +              }
       283 +  
       284 +          return games_dict
       285 +  
       286 +      except requests.exceptions.RequestException as e:
       287 +          st.error(f"Error fetching games: {str(e)}")
       288 +          return {}
       289 +      except Exception as e:
       290 +          st.error(f"Unexpected error: {str(e)}")
       291 +          return {}
       292 +  
       293 +  
       294 +  def extract_pgn_moves(pgn_text: str) -> str:
       295 +      """Extract just the moves from PGN (remove headers and 
           + annotations)"""
       296 +      lines = pgn_text.split('\n')
       297 +      move_lines = []
       298 +  
       299 +      for line in lines:
       300 +          line = line.strip()
       301 +          # Skip empty lines and header lines (starting with 
           + [)
       302 +          if not line or line.startswith('['):
       303 +              continue
       304 +          move_lines.append(line)
       305 +  
       306 +      # Join all move lines
       307 +      moves_text = ' '.join(move_lines)
       308 +  
       309 +      # Remove clock annotations
       310 +      moves_text = re.sub(r'\{[^}]*\}', '', moves_text)
       311 +      # Remove eval annotations
       312 +      moves_text = re.sub(r'\([^)]*\)', '', moves_text)
       313 +      # Remove Chess.com specific annotations like [%clk 
           + 0:05:00]
       314 +      moves_text = re.sub(r'\[%[^\]]*\]', '', moves_text)
       315 +      # Clean up whitespace
       316 +      moves_text = re.sub(r'\s+', ' ', moves_text).strip()
       317 +  
       318 +      return moves_text
       319 +  
       320 +  
       321 +  # =========================================================
           + ===================
       322    # CHESS ANALYSIS
       323    # =========================================================
             ===================
       324    

⏺ Now let me update the session state initialization to include the new
  variables:

⏺ Update(chess_coach.py)
  ⎿  Updated chess_coach.py with 7 additions                             
       634            st.session_state.coaching_context = None
       635        if "draft_message" not in st.session_state:
       636            st.session_state.draft_message = ""
       637 +      # Chess.com game fetching
       638 +      if "chesscom_username" not in st.session_state:
       639 +          st.session_state.chesscom_username = ""
       640 +      if "fetched_games" not in st.session_state:
       641 +          st.session_state.fetched_games = {}  # Dictionary 
           + of games for dropdown
       642 +      if "selected_game_key" not in st.session_state:
       643 +          st.session_state.selected_game_key = None
       644    
       645    
       646    # =========================================================
             ===================

⏺ Now let me update the main app to add the username input, fetch button,
  and dropdown. I need to find and modify the game analysis section:

⏺ Read(chess_coach.py)
  ⎿  Read 120 lines

⏺ Now I'll update the game analysis section to add the Chess.com username
  input and dropdown:

⏺ Update(chess_coach.py)
  ⎿  Updated chess_coach.py with 69 additions                            
       706        with col_analysis:
       707            st.subheader("📝 Game Analysis")
       708    
       709 +          # Chess.com Game Fetching Section
       710 +          st.markdown("#### Import from Chess.com")
       711 +  
       712 +          col_user, col_fetch = st.columns([3, 1])
       713 +          with col_user:
       714 +              chesscom_username = st.text_input(
       715 +                  "Chess.com Username:",
       716 +                  value=st.session_state.chesscom_username,
       717 +                  placeholder="Enter your Chess.com 
           + username",
       718 +                  key="chesscom_user_input"
       719 +              )
       720 +          with col_fetch:
       721 +              st.markdown("")  # Spacing
       722 +              fetch_clicked = st.button("📥 Fetch Games", 
           + use_container_width=True)
       723 +  
       724 +          # Handle fetch button
       725 +          if fetch_clicked and chesscom_username.strip():
       726 +              st.session_state.chesscom_username = 
           + chesscom_username.strip()
       727 +              with st.spinner(f"Fetching games for 
           + {chesscom_username}..."):
       728 +                  games = 
           + fetch_chesscom_recent_games(chesscom_username, num_games=5)
       729 +                  if games:
       730 +                      st.session_state.fetched_games = games
       731 +                      st.success(f"Found {len(games)} recent 
           + games!")
       732 +                  else:
       733 +                      st.warning("No games found. Check the 
           + username and try again.")
       734 +                      st.session_state.fetched_games = {}
       735 +  
       736 +          # Game selection dropdown (only show if games are 
           + fetched)
       737 +          if st.session_state.fetched_games:
       738 +              game_options = ["-- Select a game --"] + 
           + list(st.session_state.fetched_games.keys())
       739 +              selected_game = st.selectbox(
       740 +                  "Select a game to analyze:",
       741 +                  options=game_options,
       742 +                  key="game_dropdown"
       743 +              )
       744 +  
       745 +              # Load selected game into textarea
       746 +              if selected_game and selected_game != "-- 
           + Select a game --":
       747 +                  if st.button("📋 Load Selected Game"):
       748 +                      game_data = 
           + st.session_state.fetched_games[selected_game]
       749 +                      # Extract clean moves from PGN
       750 +                      clean_moves = 
           + extract_pgn_moves(game_data['pgn'])
       751 +                      st.session_state.loaded_pgn = 
           + clean_moves
       752 +                      st.session_state.selected_game_key = 
           + selected_game
       753 +                      st.rerun()
       754 +  
       755 +                  # Show game metadata
       756 +                  if selected_game in 
           + st.session_state.fetched_games:
       757 +                      meta = 
           + st.session_state.fetched_games[selected_game]['metadata']
       758 +                      with st.expander("Game Details"):
       759 +                          st.markdown(f"""
       760 +                          **White:** {meta['white']} 
           + ({meta['white_rating']})
       761 +                          **Black:** {meta['black']} 
           + ({meta['black_rating']})
       762 +                          **Time Control:** 
           + {meta['time_class']} ({meta['time_control']})
       763 +                          """)
       764 +                          if meta.get('url'):
       765 +                              st.markdown(f"[View on 
           + Chess.com]({meta['url']})")
       766 +  
       767 +          st.divider()
       768 +          st.markdown("#### Or paste PGN manually")
       769 +  
       770 +          # Get initial value for textarea
       771 +          initial_pgn = ""
       772 +          if hasattr(st.session_state, 'loaded_pgn') and 
           + st.session_state.loaded_pgn:
       773 +              initial_pgn = st.session_state.loaded_pgn
       774 +              # Clear after loading
       775 +              st.session_state.loaded_pgn = ""
       776 +  
       777            pgn_input = st.text_area(
       778                "Paste PGN or moves:",
       779 +              value=initial_pgn,
       780                height=150,
       781                placeholder="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6...",
       782                key="pgn_input"

⏺ Now let me also initialize the loaded_pgn session state variable:

⏺ Update(chess_coach.py)
  ⎿  Updated chess_coach.py with 2 additions                             
       641            st.session_state.fetched_games = {}  # Dictionary 
             of games for dropdown
       642        if "selected_game_key" not in st.session_state:
       643            st.session_state.selected_game_key = None
       644 +      if "loaded_pgn" not in st.session_state:
       645 +          st.session_state.loaded_pgn = ""
       646    
       647    
       648    # =========================================================
             ===================

⏺ The implementation is complete. Let me verify by checking the overall
  structure of the updated file:

⏺ Bash(python -m py_compile chess_coach.py && echo "Syntax OK")
  ⎿  Syntax OK

⏺ The syntax is valid. Let me provide a summary of the changes made:

  Summary of Changes to chess_coach.py

  New Features Added:

  1. Chess.com Username Input (lines 712-722)
    - Added a text input field above the PGN textarea for entering a
  Chess.com username
    - Added a "Fetch Games" button next to the input
  2. Chess.com API Integration (lines 164-291)
    - Added fetch_chesscom_recent_games() function that:
        - Fetches the last 5 games from Chess.com's public API
      - Returns a dictionary with descriptive labels as keys (e.g., "Game 1:
   vs Magnus (Win, White) - bullet - Dec 5")
      - Each entry contains the full PGN and metadata (ratings, time
  control, URL, etc.)
    - Added extract_pgn_moves() helper to clean PGN for analysis
  3. Game Selection Dropdown (lines 736-765)
    - Shows a dropdown populated with fetched games
    - "Load Selected Game" button loads the PGN into the textarea
    - Expandable "Game Details" section shows metadata (players, ratings,
  time control, link to Chess.com)
  4. Session State Management (lines 637-645)
    - Added new session state variables:
        - chesscom_username - Stores the entered username
      - fetched_games - Dictionary storing fetched games (the
  "JavaScript-style dictionary" you requested)
      - selected_game_key - Tracks which game is selected
      - loaded_pgn - Temporarily holds PGN to load into textarea

```
