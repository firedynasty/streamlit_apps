#!/bin/bash
# Don Quixote shell functions
# Source this file: source /path/to/quixote_functions.sh

# Set the directory where Quixote chapter files are located
QUIXOTE_DIR="/Users/stanleytan/Documents/25-technical/01-github/streamlit_apps/aquinas/quixote_chapters_en"

# Read Don Quixote: quixote 1 10 (Part 1, Chapter 10)
quixote() {
  local part="${1:-}"
  local chapter="${2:-}"

  if [[ -z "$part" || -z "$chapter" ]]; then
    echo "Usage: quixote <part> <chapter>"
    echo "Examples:"
    echo "  quixote 1 8       # Part 1, Chapter 8 (windmills)"
    echo "  quixote 1 52      # Part 1, Chapter 52 (last of Part 1)"
    echo "  quixote 2 1       # Part 2, Chapter 1"
    echo "  quixote 2 74      # Part 2, Chapter 74 (final chapter)"
    echo ""
    echo "Part 1: Chapters 1-52"
    echo "Part 2: Chapters 1-74"
    echo "(John Ormsby translation)"
    echo ""
    echo "Use 'quixote_index' to open the index"
    return 1
  fi

  # Validate part number
  if [[ "$part" != "1" && "$part" != "2" ]]; then
    echo "Invalid part: $part (must be 1 or 2)"
    return 1
  fi

  # Pad chapter to 2 digits
  local chapter_padded=$(printf "%02d" "$chapter")

  # Build filename
  local filename="DQ_P${part}_C${chapter_padded}.html"
  local filepath="$QUIXOTE_DIR/$filename"

  # Check if file exists
  if [[ ! -f "$filepath" ]]; then
    echo "Chapter not found: $filepath"
    echo "Available chapters for Part $part:"
    ls "$QUIXOTE_DIR/" 2>/dev/null | grep "^DQ_P${part}_C" | head -10
    return 1
  fi

  # Open in browser
  echo "Opening Don Quixote Part $part, Chapter $chapter"
  echo "File: $filename"
  open "file://$filepath"
}

# Open the Quixote index
quixote_index() {
  local filepath="$QUIXOTE_DIR/index.html"

  if [[ ! -f "$filepath" ]]; then
    echo "Index not found: $filepath"
    echo "Run the split_quixote.py script first"
    return 1
  fi

  echo "Opening Don Quixote Index"
  open "$filepath"
}

# Search Don Quixote for a term
quixote_search() {
  local term="$1"

  if [[ -z "$term" ]]; then
    echo "Usage: quixote_search <term>"
    echo "Example: quixote_search 'Dulcinea'"
    return 1
  fi

  echo "Searching Don Quixote for: $term"
  grep -l -i "$term" "$QUIXOTE_DIR"/DQ_P*.html 2>/dev/null | while read file; do
    basename "$file" .html | sed 's/DQ_P\([12]\)_C0*/Part \1, Chapter /'
  done
}
