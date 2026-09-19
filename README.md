# chess-ai-engine-
# Chess Game

A complete, two-player chess application for your desktop, written in
Python with the [`python-chess`](https://python-chess.readthedocs.io/)
library. All standard chess rules — castling, en passant, pawn promotion,
check, checkmate, stalemate and every draw — are handled by `python-chess`,
so you never have to worry about the rules being wrong.

## Features

- **Full chess rules** via `python-chess`: legal-move validation, check,
  checkmate, stalemate, castling (kingside & queenside), en passant, pawn
  promotion, insufficient material, threefold repetition and the
  fifty-move rule.
- **Player vs Player** — two players on the same computer (White vs Black),
  with automatic turn switching.
- **Player vs Computer** — optional Stockfish opponent with **Easy /
  Medium / Hard** difficulty levels, plus a built-in *Simple AI* fallback
  so computer mode works even without Stockfish.
- **Click-to-move interface** with legal-move highlighting, selected-piece
  highlighting, last-move highlighting, a red "check" marker and
  invalid-move feedback.
- **Move history panel** in standard algebraic notation (SAN), e.g.
  `1. e4 e5` / `2. Nf3 Nc6`, with a scrollbar.
- **Undo / Redo** buttons (plus `Ctrl+Z` / `Ctrl+Y` shortcuts). In
  computer mode Undo takes back the computer's reply too.
- **New Game** button with confirmation when a game is in progress.
- **Pawn promotion dialog** (Queen / Rook / Bishop / Knight).
- **Status line** that updates automatically: `White's Turn`, `Check!`,
  `Checkmate! White wins`, `Draw - Stalemate`, ...
- Clean, responsive board drawn with Tkinter; pieces are rendered as
  antialiased Unicode glyphs via Pillow, with an automatic text fallback
  when Pillow is missing. You can also drop your own PNG piece images into
  `assets/chess_pieces/`.

## Technologies

| Component    | Technology                              |
|--------------|-----------------------------------------|
| Language     | Python 3                                 |
| Chess logic  | `python-chess` (rules, SAN, engine I/O)  |
| GUI          | Tkinter (standard library)               |
| Piece images | Pillow (optional — Unicode glyphs + text fallback) |
| AI           | Stockfish (optional — via `python-chess` UCI engine wrapper) |

## Installation

You need **Python 3.8+** (with Tkinter — it ships with the standard Python
installer on Windows and macOS; on Debian/Ubuntu install
`sudo apt install python3-tk`).

It is recommended to use a virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

which installs `python-chess` and `Pillow`.

> `Pillow` is optional: without it the game still runs, pieces are just
> drawn as plain text glyphs instead of rendered images.

## Running the game

```bash
python main.py
```

The chess board opens with White to move. Click a piece to select it
(green square + legal-move dots/rings), then click a destination square.

## How to play

### Player vs Player (default)

Two players take turns on the same computer. White moves first; after each
move the turn switches automatically. You can only move pieces of the side
whose turn it is.

### Player vs Computer

1. In the **Mode** panel on the right, select **Player vs Computer**.
2. Choose a difficulty: **Easy**, **Medium** or **Hard**.
3. You (the human) play **White**; the computer plays **Black** and moves
   automatically after your move.

To switch back, select **Player vs Player**.

### Controls

| Control       | Action                                             |
|---------------|----------------------------------------------------|
| Click piece   | Select it and show its legal moves                 |
| Click square  | Move the selected piece there (or re-select)       |
| Promotion     | A dialog asks Queen / Rook / Bishop / Knight       |
| New Game      | Reset the board (asks for confirmation)            |
| Undo / Redo   | Take back / replay moves (`Ctrl+Z`, `Ctrl+Y`)      |
| `Esc`         | Deselect the current piece                         |

## Configuring Stockfish

Stockfish is **optional**. Without it, Player vs Computer mode uses the
built-in Simple AI (random with a preference for captures/checks), and the
app tells you how to install Stockfish the first time.

### Install Stockfish

- **Windows** — download the latest build from
  <https://stockfishchess.org/download/>, unzip it, and either
  - add the folder containing `stockfish.exe` to your `PATH`, or
  - set the environment variable `STOCKFISH_PATH` to the full path of the
    executable, e.g.
    ```powershell
    setx STOCKFISH_PATH "C:\path\to\stockfish\stockfish.exe"
    ```
    (restart the terminal after `setx`).
- **macOS** — `brew install stockfish`
- **Linux (Debian/Ubuntu)** — `sudo apt install stockfish`
  (many distros already ship it as `stockfish`).

The game finds Stockfish by checking, in order: the `STOCKFISH_PATH`
environment variable, the `PATH`, and a few common install locations.

### Difficulty levels

Difficulty is mapped to Stockfish's UCI settings:

| Level  | Skill level | Max search depth | Time budget |
|--------|-------------|------------------|-------------|
| Easy   | 2           | 3                | 0.5 s       |
| Medium | 10          | 12               | 1 s         |
| Hard   | 20          | 20               | 3 s         |

(When Stockfish is not available, difficulty has no effect on the built-in
Simple AI.)

### Custom piece images

Drop PNGs named `wK.png`, `wQ.png`, `wR.png`, `wB.png`, `wN.png`, `wP.png`
and their black counterparts (`bK.png`, ...) into
`assets/chess_pieces/`. See `assets/chess_pieces/README.md` for details.

## Project structure

```
chess_game/
│
├── main.py              # Entry point (starts the Tk window)
├── game.py              # Game state: board, turn, history, undo/redo, status
├── board.py             # Tkinter board widget: squares, pieces, highlights
├── gui.py               # Main window: layout, controls, user interaction
├── ai.py                # Computer opponent: Stockfish + Simple AI fallback
│
├── pieces/
│   ├── __init__.py
│   └── renderer.py      # Piece sprite rendering (PNG / Pillow / text)
│
├── assets/
│   └── chess_pieces/    # Optional custom PNG piece images (see README inside)
│
├── tests/
│   └── test_game.py     # Unit tests for game logic and the fallback AI
│
├── requirements.txt
└── README.md
```

## Architecture

```
┌──────────────┐    clicks    ┌──────────────┐   state    ┌─────────────┐
│   gui.py     │ ───────────▶ │   board.py   │ ◀───────── │   game.py   │
│ (window,     │              │ (canvas      │            │ (rules via  │
│  buttons,    │              │  widget)     │            │  python-    │
│  interaction)│              └──────────────┘            │  chess)     │
└──────┬───────┘                                           └──────┬──────┘
       │  AI moves (background thread)                           │
       ▼                                                          │
┌──────────────┐    best move    ┌───────────────────────────────┘
│    ai.py     │ ──────────────▶ │  Stockfish (UCI) or Simple AI
└──────────────┘                 └───────────────────────────────
```

The layers are deliberately separated:

- **`game.py`** owns a `chess.Board` and knows nothing about the GUI. It
  exposes `make_move`, `undo`, `redo`, `status_text`, SAN history, etc.
- **`board.py`** only *draws* the state it is given and reports clicks —
  it contains no chess rules.
- **`gui.py`** wires them together: it decides what a click means, shows
  the promotion dialog, and hands moves back to the `Game`.
- **`ai.py`** is completely independent; the GUI talks to it through the
  `BaseAI.find_best_move(board)` interface, so swapping the engine is easy.

## Error handling

- Illegal moves, empty squares and opponent pieces are ignored with
  friendly status feedback — the app never crashes on user input.
- Missing/corrupt piece images fall back to glyph rendering.
- Missing Stockfish falls back to the Simple AI with a one-time explanation
  dialog.
- Engine errors while the computer is "thinking" are caught and reported in
  the status line.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

(The Stockfish test is skipped automatically when no executable is found.)

## Future improvements

- Drag-and-drop piece movement
- "Play as Black" in computer mode
- Game timers (classical / blitz / bullet)
- Export/import games as PGN, paste FEN positions
- Opening book for the computer player
- Sound effects and animations
- Multi-language support
- Online play over a network

## License

Free to use and modify. Built with [`python-chess`](https://python-chess.readthedocs.io/)
(BSD/GPL) and [Stockfish](https://stockfishchess.org/) (GPLv3) when enabled.
