#!/bin/bash
# Dictionary shell functions
# Source this file: source /path/to/dictionary_functions.sh

# Set the directory and files
DICT_DIR="/Users/stanleytan/Documents/25-technical/01-github/streamlit_apps/aquinas/dictionary"
DICT_FILE="$DICT_DIR/dictionary.txt"
DICT_HISTORY="$DICT_DIR/dictionary_history.txt"

# Read dictionary lines sequentially: dict_read [count]
# Default is 50 lines, continues from last position
dict_read() {
  local count="${1:-50}"
  local total_lines
  local start_line

  # Check if dictionary exists
  if [[ ! -f "$DICT_FILE" ]]; then
    echo "Dictionary not found: $DICT_FILE"
    return 1
  fi

  # Get total line count
  total_lines=$(wc -l < "$DICT_FILE" | tr -d ' ')

  # Get current position from history (stores single number)
  if [[ -f "$DICT_HISTORY" ]]; then
    start_line=$(cat "$DICT_HISTORY" | tr -d ' ')
  else
    start_line=1
  fi

  # Check if we've reached the end
  if [[ $start_line -gt $total_lines ]]; then
    echo "Reached end of dictionary! Use 'dict_reset' to start over."
    return 1
  fi

  local end_line=$((start_line + count - 1))

  # Cap at total lines
  if [[ $end_line -gt $total_lines ]]; then
    end_line=$total_lines
  fi

  local actual_count=$((end_line - start_line + 1))

  echo "Reading lines $start_line-$end_line ($actual_count lines)"
  echo "----------------------------------------"

  # Display the lines
  sed -n "${start_line},${end_line}p" "$DICT_FILE"

  echo "----------------------------------------"
  echo "Displayed $actual_count lines (next: $((end_line + 1)))"

  # Save new position
  echo "$((end_line + 1))" > "$DICT_HISTORY"
}

# Reset the history (start fresh)
dict_reset() {
  if [[ -f "$DICT_HISTORY" ]]; then
    rm "$DICT_HISTORY"
    echo "Dictionary history cleared. Starting fresh!"
  else
    echo "No history to clear."
  fi
}

# Show history stats
dict_stats() {
  if [[ ! -f "$DICT_FILE" ]]; then
    echo "Dictionary not found: $DICT_FILE"
    return 1
  fi

  local total_lines=$(wc -l < "$DICT_FILE" | tr -d ' ')
  local current_pos=1

  if [[ -f "$DICT_HISTORY" ]]; then
    current_pos=$(cat "$DICT_HISTORY" | tr -d ' ')
  fi

  local seen_count=$((current_pos - 1))
  local remaining=$((total_lines - seen_count))
  local percent=$((seen_count * 100 / total_lines))

  echo "Dictionary Statistics:"
  echo "  Total lines:     $total_lines"
  echo "  Current position: $current_pos"
  echo "  Lines read:      $seen_count ($percent%)"
  echo "  Lines remaining: $remaining"
}

# Search dictionary for a term
dict_search() {
  local term="$1"

  if [[ -z "$term" ]]; then
    echo "Usage: dict_search <term>"
    echo "Example: dict_search 'philosophy'"
    return 1
  fi

  echo "Searching dictionary for: $term"
  echo "----------------------------------------"
  grep -i -A 1 "^${term}$" "$DICT_FILE" 2>/dev/null | head -50
}
