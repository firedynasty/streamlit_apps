#!/bin/bash
# Summa Theologica shell functions
# Source this file: source /path/to/summa_functions.sh

# Set the directory where Summa files are located
SUMMA_DIR="/Users/stanleytan/Documents/25-technical/01-github/streamlit_apps/aquinas/questions"

# Read Summa Theologica: summa 1 3 (Question 1, Article 3)
# Omit article number to see the whole question: summa 1
summa() {
  local question="${1:-}"
  local article="${2:-}"

  if [[ -z "$question" ]]; then
    echo "Usage: summa <question> [article]"
    echo "Examples:"
    echo "  summa 1          # Question 1 (all articles)"
    echo "  summa 1 3        # Question 1, Article 3"
    echo "  summa 45 2       # Question 45, Article 2"
    echo ""
    echo "Part I (Prima Pars) has Questions 1-119"
    echo ""
    echo "Use 'summa_index' to open the index"
    return 1
  fi

  # Pad question to 3 digits
  local question_padded=$(printf "%03d" "$question")

  # Build filename
  local filename="ST1_Q${question_padded}.html"
  local filepath="$SUMMA_DIR/$filename"

  # Check if file exists
  if [[ ! -f "$filepath" ]]; then
    echo "Question not found: $filepath"
    echo "Available questions:"
    ls "$SUMMA_DIR/" 2>/dev/null | grep "^ST1_Q" | head -10
    return 1
  fi

  # Build URL with optional article anchor
  local url="file://$filepath"
  if [[ -n "$article" ]]; then
    url="${url}#art${article}"
  fi

  # Open in browser
  echo "Opening Summa Theologica Part I, Question $question${article:+, Article $article}"
  echo "File: $filename"
  open "$url"
}

# Open the Summa index
summa_index() {
  local filepath="$SUMMA_DIR/index.html"

  if [[ ! -f "$filepath" ]]; then
    echo "Index not found: $filepath"
    echo "Run the split_summa.py script first"
    return 1
  fi

  echo "Opening Summa Theologica Index"
  open "$filepath"
}

# Search Summa for a term
summa_search() {
  local term="$1"

  if [[ -z "$term" ]]; then
    echo "Usage: summa_search <term>"
    echo "Example: summa_search 'divine providence'"
    return 1
  fi

  echo "Searching Summa for: $term"
  grep -l -i "$term" "$SUMMA_DIR"/ST1_Q*.html 2>/dev/null | while read file; do
    basename "$file" .html | sed 's/ST1_Q0*/Question /'
  done
}
