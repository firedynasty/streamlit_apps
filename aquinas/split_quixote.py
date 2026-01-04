#!/usr/bin/env python3
"""
Split Don Quijote HTML into individual chapter files.
Each chapter file contains the full chapter content with navigation links.
"""

import re
import os
from pathlib import Path

def get_all_css(html_content):
    """Extract all CSS blocks from the original HTML."""
    css_blocks = re.findall(r'<style>(.*?)</style>', html_content, re.DOTALL)
    return '\n'.join(css_blocks)

def parse_chapters(html_content):
    """Parse the HTML and extract chapters with their content."""
    # Pattern: <h3><a id="id_X_xxx"></a>Capítulo XXX. Title</h3>
    # Also capture prefatory material in Part 2
    chapter_pattern = r'<h3><a id="(id_(\d)_([^"]+))"></a>(Capítulo [^<]+|[A-ZÁÉÍÓÚÑ][^<]+)</h3>'

    chapters = []
    for match in re.finditer(chapter_pattern, html_content):
        full_id = match.group(1)
        part_num = int(match.group(2))
        chapter_id = match.group(3)
        title = match.group(4)

        # Extract chapter number from title if present
        num_match = re.search(r'Capítulo\s+(\w+)', title, re.IGNORECASE)
        if num_match:
            chapter_num_text = num_match.group(1)
        else:
            chapter_num_text = chapter_id

        chapters.append({
            'full_id': full_id,
            'part': part_num,
            'chapter_id': chapter_id,
            'chapter_num_text': chapter_num_text,
            'title': title,
            'start': match.start()
        })

    return chapters

def extract_chapter_content(html_content, chapters, index):
    """Extract content for a single chapter."""
    start = chapters[index]['start']

    # End is either the next chapter or end of main content
    if index + 1 < len(chapters):
        end = chapters[index + 1]['start']
    else:
        # Find the footer
        footer_match = re.search(r'<section class="pg-boilerplate pgfooter"', html_content)
        if footer_match:
            end = footer_match.start()
        else:
            # Fallback: find closing body tag
            body_match = re.search(r'</body>', html_content)
            end = body_match.start() if body_match else len(html_content)

    return html_content[start:end]

def create_chapter_html(content, chapter, prev_file, next_file, css):
    """Create a complete HTML file for a chapter."""
    part_name = "Primera Parte" if chapter['part'] == 1 else "Segunda Parte"

    prev_link = f'<a href="{prev_file}">&larr; Anterior</a>' if prev_file else '<span style="color:#ccc">&larr; Anterior</span>'
    next_link = f'<a href="{next_file}">Siguiente &rarr;</a>' if next_file else '<span style="color:#ccc">Siguiente &rarr;</span>'

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Don Quijote - {part_name} - {chapter['title']}</title>
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
            display: flex;
            justify-content: space-between;
        }}
        .nav a {{
            text-decoration: none;
            color: #333;
        }}
        .nav a:hover {{
            text-decoration: underline;
        }}
        h3 {{
            font-size: 1.3em;
            margin-top: 1em;
        }}
    </style>
</head>
<body>
<div class="nav">
    {prev_link}
    <a href="index.html">Índice</a>
    {next_link}
</div>

{content}

<div class="nav" style="margin-top: 40px;">
    {prev_link}
    <a href="index.html">Índice</a>
    {next_link}
</div>
</body>
</html>'''
    return html

def get_chapter_filename(chapter, index):
    """Generate a filename for a chapter."""
    # Format: DQ_P1_C01.html or DQ_P2_C01.html
    part = chapter['part']

    # Convert roman numerals or text to numbers
    roman_to_num = {
        'primero': 1, 'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
        'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
        'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15,
        'xvi': 16, 'xvii': 17, 'xviii': 18, 'xix': 19, 'xx': 20,
        'xxi': 21, 'xxii': 22, 'xxiii': 23, 'xxiv': 24, 'xxv': 25,
        'xxvi': 26, 'xxvii': 27, 'xxviii': 28, 'xxix': 29, 'xxx': 30,
        'xxxi': 31, 'xxxii': 32, 'xxxiii': 33, 'xxxiv': 34, 'xxxv': 35,
        'xxxvi': 36, 'xxxvii': 37, 'xxxviii': 38, 'xxxix': 39, 'xl': 40,
        'xli': 41, 'xlii': 42, 'xliii': 43, 'xliv': 44, 'xlv': 45,
        'xlvi': 46, 'xlvii': 47, 'xlviii': 48, 'xlix': 49, 'l': 50,
        'li': 51, 'lii': 52, 'liii': 53, 'liv': 54, 'lv': 55,
        'lvi': 56, 'lvii': 57, 'lviii': 58, 'lix': 59, 'lx': 60,
        'lxi': 61, 'lxii': 62, 'lxiii': 63, 'lxiv': 64, 'lxv': 65,
        'lxvi': 66, 'lxvii': 67, 'lxviii': 68, 'lxix': 69, 'lxx': 70,
        'lxxi': 71, 'lxxii': 72, 'lxxiii': 73, 'lxxiv': 74
    }

    chapter_id = chapter['chapter_id'].lower()

    # Check if it's a chapter or prefatory material
    if chapter_id in roman_to_num:
        num = roman_to_num[chapter_id]
        return f"DQ_P{part}_C{num:02d}.html"
    else:
        # Prefatory material (tasa, erratas, prologo, etc.)
        return f"DQ_P{part}_{chapter_id}.html"

def create_index_html(chapters_info, css):
    """Create an index page for all chapters."""

    # Group by part
    part1 = [c for c in chapters_info if c['part'] == 1]
    part2 = [c for c in chapters_info if c['part'] == 2]

    def make_toc(chapters):
        items = []
        for c in chapters:
            items.append(f'<li><a href="{c["filename"]}">{c["title"]}</a></li>')
        return '\n'.join(items)

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Don Quijote de la Mancha - Índice</title>
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
        h2 {{
            margin-top: 2em;
            border-bottom: 1px solid #ccc;
            padding-bottom: 0.5em;
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
    <script>
        // Navigation function - can be called from console or other scripts
        function goToChapter(part, chapter) {{
            const filename = `DQ_P${{part}}_C${{String(chapter).padStart(2, '0')}}.html`;
            window.location.href = filename;
        }}
    </script>
</head>
<body>
<h1>Don Quijote de la Mancha</h1>
<h3 style="text-align: center;">Miguel de Cervantes Saavedra</h3>
<hr>

<h2>Primera Parte</h2>
<ul>
{make_toc(part1)}
</ul>

<h2>Segunda Parte</h2>
<ul>
{make_toc(part2)}
</ul>

</body>
</html>'''
    return html

def main():
    input_file = Path(__file__).parent / 'pg2000-images.html'
    output_dir = Path(__file__).parent / 'quixote_chapters'

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("Extracting CSS...")
    css = get_all_css(html_content)

    print("Parsing chapters...")
    chapters = parse_chapters(html_content)
    print(f"Found {len(chapters)} chapters/sections")

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Generate filenames for all chapters
    for i, ch in enumerate(chapters):
        ch['filename'] = get_chapter_filename(ch, i)

    chapters_info = []

    for i, ch in enumerate(chapters):
        print(f"Processing Part {ch['part']}: {ch['title'][:50]}...")

        # Extract content
        content = extract_chapter_content(html_content, chapters, i)

        # Determine prev/next files
        prev_file = chapters[i-1]['filename'] if i > 0 else None
        next_file = chapters[i+1]['filename'] if i < len(chapters) - 1 else None

        # Create HTML
        chapter_html = create_chapter_html(content, ch, prev_file, next_file, css)

        # Write file
        output_file = output_dir / ch['filename']
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(chapter_html)

        chapters_info.append({
            'part': ch['part'],
            'title': ch['title'],
            'filename': ch['filename']
        })

    # Create index
    print("Creating index...")
    index_html = create_index_html(chapters_info, css)
    with open(output_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f"\nDone! Created {len(chapters)} chapter files in {output_dir}")
    print(f"Index file: {output_dir / 'index.html'}")

if __name__ == '__main__':
    main()
