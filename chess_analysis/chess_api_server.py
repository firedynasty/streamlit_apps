#!/usr/bin/env python3
"""
Chess Analyzer API Server

A simple Flask API that serves the web analyzer and provides additional features:
- Puzzle recommendations based on analysis
- Report generation
- Game history storage (optional)

The heavy lifting (Stockfish analysis) is done client-side via Stockfish.js
This server just provides supplementary features.
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# Import Lichess cloud eval for fallback/supplementary analysis
from lichess_cloud_eval import LichessCloudEval

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for local development

# Initialize Lichess cloud eval
cloud_eval = LichessCloudEval()

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.route('/')
def index():
    """Serve the main analyzer page"""
    return send_file('stockfish_web_analyzer.html')


@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('.', filename)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'engine': 'stockfish.js (client-side)',
        'fallback': 'lichess_cloud'
    })


@app.route('/api/cloud-eval', methods=['GET'])
def cloud_eval_endpoint():
    """
    Proxy to Lichess cloud eval (avoids CORS issues from browser)

    Query params:
        fen: FEN string of position to evaluate
    """
    fen = request.args.get('fen')
    if not fen:
        return jsonify({'error': 'FEN required'}), 400

    result = cloud_eval.get_eval(fen)

    if result:
        return jsonify({
            'fen': fen,
            'depth': result.get('depth'),
            'knodes': result.get('knodes'),
            'pvs': result.get('pvs', []),
            'source': 'lichess_cloud'
        })
    else:
        return jsonify({
            'error': 'Position not in Lichess cloud database',
            'fen': fen,
            'suggestion': 'Use client-side Stockfish.js for this position'
        }), 404


@app.route('/api/puzzles', methods=['POST'])
def get_puzzle_recommendations():
    """
    Get puzzle recommendations based on mistake patterns

    Request body (JSON):
        {
            "patterns": ["fork", "hanging", "backrank"],
            "count": 5
        }
    """
    data = request.get_json() or {}
    patterns = data.get('patterns', [])
    count = min(data.get('count', 5), 10)

    # Map patterns to Lichess puzzle themes
    theme_mapping = {
        'hanging': 'hangingPiece',
        'fork': 'fork',
        'pin': 'pin',
        'skewer': 'skewer',
        'backrank': 'backRankMate',
        'exposed_king': 'exposedKing',
        'tactical': 'middlegame',
        'positional': 'endgame',
        'mate': 'mate'
    }

    recommendations = []
    seen_themes = set()

    for pattern in patterns:
        lichess_theme = theme_mapping.get(pattern.lower())
        if lichess_theme and lichess_theme not in seen_themes:
            seen_themes.add(lichess_theme)
            recommendations.append({
                'theme': lichess_theme,
                'display_name': lichess_theme.replace('_', ' ').title(),
                'url': f'https://lichess.org/training/{lichess_theme}',
                'description': get_theme_description(lichess_theme)
            })

        if len(recommendations) >= count:
            break

    # Add daily puzzle as bonus
    try:
        import requests
        daily_response = requests.get('https://lichess.org/api/puzzle/daily', timeout=5)
        if daily_response.ok:
            daily = daily_response.json()
            puzzle_info = daily.get('puzzle', {})
            recommendations.append({
                'theme': 'daily',
                'display_name': 'Daily Puzzle',
                'url': 'https://lichess.org/training/daily',
                'rating': puzzle_info.get('rating'),
                'themes': puzzle_info.get('themes', [])[:3],
                'is_daily': True
            })
    except:
        pass

    return jsonify({
        'recommendations': recommendations,
        'based_on': patterns
    })


def get_theme_description(theme):
    """Get human-readable description for puzzle themes"""
    descriptions = {
        'hangingPiece': 'Win material by capturing undefended pieces',
        'fork': 'Attack two or more pieces simultaneously',
        'backRankMate': 'Deliver checkmate on the back rank',
        'pin': 'Attack a piece that cannot move without exposing a more valuable piece',
        'skewer': 'Attack a valuable piece, forcing it to move and exposing another',
        'exposedKing': 'Exploit a king with weak defenses',
        'middlegame': 'Tactical puzzles from the middlegame',
        'endgame': 'Tactical puzzles from the endgame',
        'mate': 'Deliver checkmate'
    }
    return descriptions.get(theme, 'Practice this tactical pattern')


@app.route('/api/report', methods=['POST'])
def generate_report():
    """
    Generate a text report from analysis results

    Request body (JSON):
        {
            "pgn": "1. e4 e5 ...",
            "mistakes": [...],
            "stats": {
                "blunders": 2,
                "mistakes": 3,
                "inaccuracies": 5
            }
        }
    """
    data = request.get_json() or {}

    pgn = data.get('pgn', '')
    mistakes = data.get('mistakes', [])
    stats = data.get('stats', {})
    game_info = data.get('game_info', {})

    # Build report
    report_lines = [
        "=" * 70,
        "CHESS GAME ANALYSIS REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Engine: Stockfish.js (Client-side)",
        "=" * 70,
        "",
    ]

    # Game info
    if game_info:
        report_lines.extend([
            "GAME INFORMATION",
            "-" * 70,
        ])
        for key, value in game_info.items():
            report_lines.append(f"{key}: {value}")
        report_lines.append("")

    # PGN
    if pgn:
        report_lines.extend([
            "PGN",
            "-" * 70,
            pgn,
            ""
        ])

    # Summary
    report_lines.extend([
        "SUMMARY",
        "-" * 70,
        f"Blunders: {stats.get('blunders', 0)}",
        f"Mistakes: {stats.get('mistakes', 0)}",
        f"Inaccuracies: {stats.get('inaccuracies', 0)}",
        ""
    ])

    # Mistakes
    if mistakes:
        report_lines.extend([
            "DETAILED MISTAKES",
            "-" * 70,
            ""
        ])

        for m in mistakes:
            severity = m.get('severity', 'UNKNOWN')
            notation = m.get('notation', '?')
            move = m.get('move', '?')
            eval_before = m.get('evalBefore', 0) / 100
            eval_after = m.get('evalAfter', 0) / 100
            fen = m.get('fen', '')

            report_lines.extend([
                f"{severity}: {notation} {move}",
                f"  Eval: {eval_before:.2f} -> {eval_after:.2f}",
                f"  FEN: {fen}",
                f"  Analyze: https://lichess.org/analysis/{fen.replace(' ', '_')}",
                ""
            ])

    # Puzzle recommendations
    patterns = []
    for m in mistakes:
        if m.get('severity') == 'BLUNDER':
            patterns.append('tactical')

    if patterns:
        report_lines.extend([
            "=" * 70,
            "RECOMMENDED PRACTICE",
            "=" * 70,
            "",
            "Based on your mistakes, practice these themes on Lichess:",
            ""
        ])

        for pattern in set(patterns)[:5]:
            theme = {'tactical': 'middlegame', 'positional': 'endgame'}.get(pattern, pattern)
            report_lines.append(f"  - https://lichess.org/training/{theme}")

    report_lines.append("")
    report_lines.append("=" * 70)

    report_text = "\n".join(report_lines)

    return jsonify({
        'report': report_text,
        'filename': f"chess_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    })


@app.route('/api/analyze-position', methods=['POST'])
def analyze_position_server():
    """
    Server-side position analysis using Lichess cloud
    (Fallback when client-side Stockfish.js fails)

    Request body (JSON):
        {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        }
    """
    data = request.get_json() or {}
    fen = data.get('fen')

    if not fen:
        return jsonify({'error': 'FEN required'}), 400

    result = cloud_eval.get_eval(fen)

    if result and result.get('pvs'):
        pv = result['pvs'][0]
        score = pv.get('cp', 0)
        if 'mate' in pv:
            mate = pv['mate']
            score = 10000 - abs(mate) if mate > 0 else -10000 + abs(mate)

        return jsonify({
            'fen': fen,
            'score': score,
            'bestMove': pv.get('moves', '').split()[0] if pv.get('moves') else None,
            'depth': result.get('depth'),
            'source': 'lichess_cloud'
        })
    else:
        return jsonify({
            'error': 'Position not cached',
            'fen': fen,
            'suggestion': 'Use client-side Stockfish.js'
        }), 404


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import sys

    # Get port from command line argument or default to 8080
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            print("Usage: python chess_api_server.py [port]")
            sys.exit(1)

    print("=" * 60)
    print("CHESS ANALYZER API SERVER")
    print("=" * 60)
    print()
    print("Architecture:")
    print("  Primary:  Stockfish.js (runs in browser)")
    print("  Fallback: Lichess Cloud Eval API")
    print()
    print("Endpoints:")
    print("  GET  /                     - Web analyzer UI")
    print("  GET  /api/health           - Health check")
    print("  GET  /api/cloud-eval?fen=  - Lichess cloud eval proxy")
    print("  POST /api/puzzles          - Get puzzle recommendations")
    print("  POST /api/report           - Generate text report")
    print("  POST /api/analyze-position - Server-side analysis fallback")
    print()
    print(f"Starting server on http://localhost:{port}")
    print()

    app.run(host='0.0.0.0', port=port, debug=True)
