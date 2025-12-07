what in javascript can I use to convert a pgn string to // Your game moves
 in UCI format
const moves = [
    "e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d5a5", "f1c4", "g8f6",
    "a2a4", "b8c6", "g1f3", "e7e5", "d2d3", "f8c5", "e1g1", "c6d4",
    "f1e1", "e8g8", "e1e5", "c8g4", "c3e4", "f6e4", "d3e4", "d4f3",
    "g2f3", "g4h3", "e5d5", "c7c6", "d5d3", "a5c7", "c1g5", "h7h6",
    "g5h4", "g8h8", "h4g3", "c7e7", "d3d7", "e7g5", "d7f7", "f8f7",
    "c4f7", "h6h5", "f3f4", "g5e7", "f7g6", "e7e6", "d1h5", "h8g8",
    "g6f7", "e6f7", "h5h3", "a8d8", "h3f1", "d8d2", "a1d1", "d2c2",
    "d1d8", "g8h7", "f1h3", "h7g6", "h3g4", "g6h7", "g4h4", "h7g6",
    "d8h8", "f7d7", "f4f5", "g6f7", "h4h5", "f7e7", "g3h4", "e7d6",
    "h5g6", "d6c7", "h8g8", "c2c1", "g1g2", "c1c2", "g8g7", "c2b2"
]; 

⏺ The most common solution is chess.js - it can parse PGN and give you move
  details that you can convert to UCI format.

  import { Chess } from 'chess.js';

  const pgn = `1. e4 d5 2. exd5 Qxd5 3. Nc3 Qa5 4. Bc4 Nf6...`;

  const chess = new Chess();
  chess.loadPgn(pgn);

  // Get moves in UCI format
  const moves = chess.history({ verbose: true }).map(move => {
      let uci = move.from + move.to;
      if (move.promotion) {
          uci += move.promotion;  // e.g., "e7e8q"
      }
      return uci;
  });

  console.log(moves);
  // ["e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d5a5", "f1c4", "g8f6", ...]

  Install:
  npm install chess.js

  For browser (CDN):
  <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.13.4/chess.
  min.js"></script>

  Key points:
  - chess.loadPgn(pgn) - parses the PGN string
  - chess.history({ verbose: true }) - returns move objects with from, to,
  promotion properties
  - UCI format is simply from + to (+ promotion piece if applicable)

  Handling castling: chess.js automatically converts O-O to e1g1/e8g8 and
  O-O-O to e1c1/e8c8 in the verbose history.
