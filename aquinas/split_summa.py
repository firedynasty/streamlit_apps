#!/usr/bin/env python3
"""
Split Summa Theologica HTML into individual question files.
Each question file contains all articles for that question with anchor links.
"""

import re
import os
from pathlib import Path

def extract_css(html_content):
    """Extract CSS from the original HTML."""
    css_match = re.search(r'<style>(.*?)</style>', html_content, re.DOTALL)
    return css_match.group(1) if css_match else ""

def get_all_css(html_content):
    """Extract all CSS blocks from the original HTML."""
    css_blocks = re.findall(r'<style>(.*?)</style>', html_content, re.DOTALL)
    return '\n'.join(css_blocks)

def parse_questions(html_content):
    """Parse the HTML and extract questions with their content."""
    # Find all questions - pattern: <h5 id="...">QUESTION N</h5>
    question_pattern = r'<h5 id="([^"]+)">(QUESTION (\d+))</h5>'

    questions = []
    for match in re.finditer(question_pattern, html_content):
        questions.append({
            'id': match.group(1),
            'title': match.group(2),
            'number': int(match.group(3)),
            'start': match.start()
        })

    return questions

def extract_question_content(html_content, questions, index):
    """Extract content for a single question."""
    start = questions[index]['start']

    # End is either the next question or end of main content
    if index + 1 < len(questions):
        end = questions[index + 1]['start']
    else:
        # Find the footer
        footer_match = re.search(r'<section class="pg-boilerplate pgfooter"', html_content)
        end = footer_match.start() if footer_match else len(html_content)

    return html_content[start:end]

def add_article_anchors(content, question_num):
    """Add anchor IDs to articles within a question for direct linking."""
    # Pattern for articles: FIRST ARTICLE [I, Q. X, Art. Y] or SECOND ARTICLE, etc.
    # Also handle numeric patterns like "Article 1"

    article_words = ['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH',
                     'SIXTH', 'SEVENTH', 'EIGHTH', 'NINTH', 'TENTH',
                     'ELEVENTH', 'TWELFTH', 'THIRTEENTH', 'FOURTEENTH',
                     'FIFTEENTH', 'SIXTEENTH']

    word_to_num = {word: i+1 for i, word in enumerate(article_words)}

    def replace_article(match):
        full_match = match.group(0)
        article_word = match.group(1)
        article_num = word_to_num.get(article_word, 1)
        anchor_id = f'art{article_num}'
        # Wrap in anchor
        return f'<a id="{anchor_id}"></a>{full_match}'

    pattern = r'<p id="[^"]+">(' + '|'.join(article_words) + r') ARTICLE'
    content = re.sub(pattern, replace_article, content)

    return content

def get_question_title(content):
    """Extract the question title (e.g., 'THE NATURE AND EXTENT OF SACRED DOCTRINE')."""
    # Look for the paragraph right after the h5 question header
    match = re.search(r'<p id="[^"]+">([A-Z][^<]+?)(?:\s*\(in [^)]+\))?</p>', content)
    if match:
        return match.group(1).strip()
    return ""

def create_question_html(content, question_num, question_title, css):
    """Create a complete HTML file for a question."""
    full_title = get_question_title(content) or question_title

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Summa Theologica I, Question {question_num}: {full_title}</title>
    <style>
{css}
    </style>
    <style>
        body {{
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            font-family: Georgia, serif;
            line-height: 1.6;
        }}
        .nav {{
            background: #f5f5f5;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .nav a {{
            margin-right: 15px;
            text-decoration: none;
            color: #333;
        }}
        .nav a:hover {{
            text-decoration: underline;
        }}
        h5 {{
            font-size: 1.5em;
            margin-top: 1em;
        }}
    </style>
</head>
<body>
<div class="nav">
    <a href="ST1_Q{question_num-1:03d}.html">&larr; Prev</a>
    <a href="index.html">Index</a>
    <a href="ST1_Q{question_num+1:03d}.html">Next &rarr;</a>
</div>

{content}

<div class="nav" style="margin-top: 40px;">
    <a href="ST1_Q{question_num-1:03d}.html">&larr; Prev</a>
    <a href="index.html">Index</a>
    <a href="ST1_Q{question_num+1:03d}.html">Next &rarr;</a>
</div>
</body>
</html>'''
    return html

def create_index_html(questions_info, css):
    """Create an index page for all questions."""
    toc = []
    for q in questions_info:
        toc.append(f'<li><a href="ST1_Q{q["number"]:03d}.html">Question {q["number"]}: {q["full_title"]}</a></li>')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Summa Theologica Part I (Prima Pars) - Index</title>
    <style>
        body {{
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            font-family: Georgia, serif;
            line-height: 1.6;
        }}
        h1 {{
            text-align: center;
        }}
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        li {{
            margin: 8px 0;
        }}
        a {{
            text-decoration: none;
            color: #333;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
<h1>Summa Theologica</h1>
<h2>Part I (Prima Pars)</h2>
<h3>St. Thomas Aquinas</h3>
<hr>
<ul>
{''.join(toc)}
</ul>
</body>
</html>'''
    return html

def main():
    input_file = Path(__file__).parent / 'pg17611-images.html'
    output_dir = Path(__file__).parent / 'questions'

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("Extracting CSS...")
    css = get_all_css(html_content)

    print("Parsing questions...")
    questions = parse_questions(html_content)
    print(f"Found {len(questions)} questions")

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    questions_info = []

    for i, q in enumerate(questions):
        print(f"Processing Question {q['number']}...")

        # Extract content
        content = extract_question_content(html_content, questions, i)

        # Add article anchors
        content = add_article_anchors(content, q['number'])

        # Get full title
        full_title = get_question_title(content)
        questions_info.append({
            'number': q['number'],
            'full_title': full_title
        })

        # Create HTML
        question_html = create_question_html(content, q['number'], q['title'], css)

        # Write file
        output_file = output_dir / f"ST1_Q{q['number']:03d}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(question_html)

    # Create index
    print("Creating index...")
    index_html = create_index_html(questions_info, css)
    with open(output_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f"\nDone! Created {len(questions)} question files in {output_dir}")
    print(f"Files named: ST1_Q001.html through ST1_Q{questions[-1]['number']:03d}.html")
    print(f"Index file: {output_dir / 'index.html'}")

if __name__ == '__main__':
    main()
