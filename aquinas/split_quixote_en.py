#!/usr/bin/env python3
"""
Split Don Quixote (English) HTML into individual chapter files.
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
    # English format: <h3>\n<a id="ch1"></a>CHAPTER I.<br>\nTITLE</h3>
    # or <a id="ch1b"></a> for Part 2
    # Also prefatory: <h3><a id="pref02"></a>PREFARATORY</h3>

    chapters = []

    # Find all chapter/section markers
    # Pattern for chapters: <a id="chXX"></a> or <a id="chXXb"></a>
    chapter_pattern = r'<h3>\s*<a id="(ch(\d+)(b)?|pref\d+)"></a>(CHAPTER [IVXLC]+\.<br>\s*[^<]+|[A-Z][^<]+)</h3>'

    for match in re.finditer(chapter_pattern, html_content, re.DOTALL):
        anchor_id = match.group(1)
        chapter_num = match.group(2)
        is_part2 = match.group(3) == 'b'
        title_raw = match.group(4)

        # Clean up title - replace <br> and newlines with space
        title = re.sub(r'<br>\s*', ' ', title_raw)
        title = re.sub(r'\s+', ' ', title).strip()

        # Determine part number
        if anchor_id.startswith('pref'):
            part_num = 0  # Prefatory material
        elif is_part2:
            part_num = 2
        else:
            part_num = 1

        chapters.append({
            'anchor_id': anchor_id,
            'part': part_num,
            'chapter_num': int(chapter_num) if chapter_num else 0,
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

def get_dark_mode_styles():
    """Return dark mode CSS and JavaScript."""
    return '''
    /* Dark mode styles */
    body.dark-mode {
        background: #1a1a1a !important;
        color: #e0e0e0 !important;
    }
    body.dark-mode h1, body.dark-mode h2, body.dark-mode h3,
    body.dark-mode h4, body.dark-mode h5, body.dark-mode b,
    body.dark-mode i, body.dark-mode font {
        color: #e0e0e0 !important;
    }
    body.dark-mode a {
        color: #6db3f2 !important;
    }
    body.dark-mode a:visited {
        color: #b39ddb !important;
    }
    body.dark-mode hr {
        border-color: #444 !important;
    }
    body.dark-mode .nav {
        background: #2a2a2a !important;
    }
    body.dark-mode .nav a, body.dark-mode .nav span {
        color: #e0e0e0 !important;
    }
    body.dark-mode .nav a {
        color: #6db3f2 !important;
    }
    /* Toggle button */
    .dark-mode-toggle {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 9999;
        padding: 8px 16px;
        border: 1px solid rgba(0,0,0,0.2);
        border-radius: 20px;
        cursor: pointer;
        font-size: 14px;
        background: rgba(50,50,50,0.15);
        color: #333;
        box-shadow: none;
        backdrop-filter: blur(2px);
    }
    .dark-mode-toggle:hover {
        background: rgba(50,50,50,0.3);
    }
    body.dark-mode .dark-mode-toggle {
        background: rgba(255,255,255,0.15);
        color: #e0e0e0;
        border-color: rgba(255,255,255,0.2);
    }
    body.dark-mode .dark-mode-toggle:hover {
        background: rgba(255,255,255,0.3);
    }
'''

def get_dark_mode_script():
    """Return dark mode JavaScript."""
    return '''
<script>
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    var btn = document.querySelector('.dark-mode-toggle');
    if (document.body.classList.contains('dark-mode')) {
        btn.textContent = 'Light Mode';
        localStorage.setItem('dq-dark-mode', 'true');
    } else {
        btn.textContent = 'Dark Mode';
        localStorage.setItem('dq-dark-mode', 'false');
    }
}
// Check saved preference on load
if (localStorage.getItem('dq-dark-mode') === 'true') {
    document.body.classList.add('dark-mode');
    document.querySelector('.dark-mode-toggle').textContent = 'Light Mode';
}
</script>
'''

def create_chapter_html(content, chapter, prev_file, next_file, css):
    """Create a complete HTML file for a chapter."""
    if chapter['part'] == 0:
        part_name = "Prefatory Material"
    elif chapter['part'] == 1:
        part_name = "Part One"
    else:
        part_name = "Part Two"

    prev_link = f'<a href="{prev_file}">&larr; Previous</a>' if prev_file else '<span style="color:#ccc">&larr; Previous</span>'
    next_link = f'<a href="{next_file}">Next &rarr;</a>' if next_file else '<span style="color:#ccc">Next &rarr;</span>'

    dark_mode_css = get_dark_mode_styles()
    dark_mode_script = get_dark_mode_script()

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Don Quixote - {part_name} - {chapter['title']}</title>
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
        {dark_mode_css}
    </style>
</head>
<body>
<button class="dark-mode-toggle" onclick="toggleDarkMode()">Dark Mode</button>

<div class="nav">
    {prev_link}
    <a href="index.html">Contents</a>
    {next_link}
</div>

{content}

<div class="nav" style="margin-top: 40px;">
    {prev_link}
    <a href="index.html">Contents</a>
    {next_link}
</div>
{dark_mode_script}
</body>
</html>'''
    return html

def get_chapter_filename(chapter, index):
    """Generate a filename for a chapter."""
    part = chapter['part']

    if part == 0:
        # Prefatory material
        return f"DQ_pref_{chapter['anchor_id']}.html"
    else:
        # Regular chapter: DQ_P1_C01.html or DQ_P2_C01.html
        num = chapter['chapter_num']
        return f"DQ_P{part}_C{num:02d}.html"

def create_index_html(chapters_info, css):
    """Create an index page for all chapters."""

    # Group by part
    pref = [c for c in chapters_info if c['part'] == 0]
    part1 = [c for c in chapters_info if c['part'] == 1]
    part2 = [c for c in chapters_info if c['part'] == 2]

    def make_toc(chapters):
        items = []
        for c in chapters:
            items.append(f'<li><a href="{c["filename"]}">{c["title"]}</a></li>')
        return '\n'.join(items)

    pref_section = ""
    if pref:
        pref_section = f'''
<h2>Prefatory Material</h2>
<ul>
{make_toc(pref)}
</ul>
'''

    dark_mode_css = get_dark_mode_styles()
    dark_mode_script = get_dark_mode_script()

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Don Quixote - Contents</title>
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
        body.dark-mode h2 {{
            border-bottom-color: #444;
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
        {dark_mode_css}
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
<button class="dark-mode-toggle" onclick="toggleDarkMode()">Dark Mode</button>

<h1>Don Quixote</h1>
<h3 style="text-align: center;">Miguel de Cervantes Saavedra</h3>
<h4 style="text-align: center;">Translated by John Ormsby</h4>
<hr>
{pref_section}
<h2>Part One</h2>
<ul>
{make_toc(part1)}
</ul>

<h2>Part Two</h2>
<ul>
{make_toc(part2)}
</ul>

{dark_mode_script}
</body>
</html>'''
    return html

def main():
    input_file = Path(__file__).parent / 'pg996-images.html'
    output_dir = Path(__file__).parent / 'quixote_chapters_en'

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("Extracting CSS...")
    css = get_all_css(html_content)

    print("Parsing chapters...")
    chapters = parse_chapters(html_content)
    print(f"Found {len(chapters)} chapters/sections")

    if len(chapters) == 0:
        print("ERROR: No chapters found! Check the regex patterns.")
        return

    # Debug: show first few chapters found
    print("\nFirst 5 chapters found:")
    for ch in chapters[:5]:
        print(f"  Part {ch['part']}: {ch['title'][:60]}...")

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
