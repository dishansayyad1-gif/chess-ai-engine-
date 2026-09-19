"""Computer opponent.

``AIManager`` returns the best available engine:

* **Stockfish** when an executable can be found (searched in
  ``STOCKFISH_PATH``, the ``PATH`` and a few common install locations);
* a tiny built-in **Simple AI** otherwise, so Player vs Computer mode
  always works out of the box.

Difficulty is mapped to Stockfish UCI settings (skill level + depth + time
budget). This module has no GUI dependencies.
"""

import os
import random
import shutil
import threading

import chess
import chess.engine

# Difficulty -> Stockfish settings. Easy plays fast and weak, Hard plays
# deep and slow. "time" is a soft budget; play() stops at whichever limit
# is reached first.
DIFFICULTIES = {
    "Easy":   {"skill_level": 2,  "depth": 3,  "time": 0.5},
    "Medium": {"skill_level": 10, "depth": 12, "time": 1.0},
    "Hard":   {"skill_level": 20, "depth": 20, "time": 3.0},
}

_PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}


def find_stockfish():
    """Locate a Stockfish executable, or return ``None``."""
    env = os.environ.get("STOCKFISH_PATH")
    if env and os.path.isfile(env):
        return env
    exe = shutil.which("stockfish")
    if exe:
        return exe
    common_locations = [
        "/usr/games/stockfish",
        "/usr/local/bin/stockfish",
        "/opt/homebrew/bin/stockfish",
        "/usr/bin/stockfish",
        r"C:\Program Files\Stockfish\stockfish.exe",
        r"C:\stockfish\stockfish.exe",
    ]
    for path in common_locations:
        if os.path.isfile(path):
            return path
    return None


class BaseAI:
    """Common interface every computer opponent implements."""

    name = "Base AI"

    def find_best_move(self, board):
        """Return a ``chess.Move`` for the side to move (or ``None`` if the
        game is over / no move can be found)."""
        raise NotImplementedError


class RandomAI(BaseAI):
    """Built-in fallback: prefers captures, checks and promotions but is
    otherwise random. Good enough for casual play without Stockfish."""

    name = "Simple AI"

    def find_best_move(self, board):
        moves = list(board.legal_moves)
        if not moves:
            return None

        def score(move):
            value = 0
            if board.is_capture(move):
                target = board.piece_at(move.to_square)
                value += 10 + (_PIECE_VALUES.get(target.piece_type, 0) if target else 0)
            if board.gives_check(move):
                value += 5
            if move.promotion:
                value += 15
            return value

        best = max(score(move) for move in moves)
        candidates = [move for move in moves if score(move) == best]
        return random.choice(candidates)


class StockfishAI(BaseAI):
    """Stockfish through python-chess's UCI engine wrapper."""

    name = "Stockfish"

    def __init__(self, executable, difficulty="Medium"):
        self._engine = chess.engine.SimpleEngine.popen_uci(executable)
        self._limit = None
        self._difficulty = None
        self.set_difficulty(difficulty)

    def set_difficulty(self, difficulty):
        if difficulty == self._difficulty:
            return
        settings = DIFFICULTIES[difficulty]
        self._engine.configure({"Skill Level": settings["skill_level"], "Threads": 1})
        self._limit = chess.engine.Limit(depth=settings["depth"], time=settings["time"])
        self._difficulty = difficulty

    def find_best_move(self, board):
        result = self._engine.play(board, self._limit)
        return result.move

    def close(self):
        self._engine.quit()


class AIManager:
    """Creates and caches the computer opponent.

    ``get_ai`` is cheap to call repeatedly: Stockfish is only started once
    (the first time computer mode is enabled) and subsequent calls just
    apply the chosen difficulty.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stockfish = None
        self._attempted = False
        self._fallback_reason = None
        self._simple = RandomAI()

    def uses_stockfish(self):
        return self._stockfish is not None

    @property
    def fallback_reason(self):
        return self._fallback_reason

    def get_ai(self, difficulty):
        """Return the opponent to use for ``difficulty``."""
        with self._lock:
            if self._stockfish is None and not self._attempted:
                self._attempted = True
                executable = find_stockfish()
                if executable:
                    try:
                        self._stockfish = StockfishAI(executable, difficulty)
                    except Exception as exc:  # engine refused to start
                        self._fallback_reason = f"Failed to start Stockfish: {exc}"
                else:
                    self._fallback_reason = (
                        "Stockfish executable not found. Install Stockfish or "
                        "set the STOCKFISH_PATH environment variable."
                    )
            elif self._stockfish is not None:
                try:
                    self._stockfish.set_difficulty(difficulty)
                except Exception:
                    pass  # keep the previous difficulty on engine errors
            return self._stockfish if self._stockfish is not None else self._simple

    def close(self):
        """Shut the engine down (call when the application exits)."""
        with self._lock:
            if self._stockfish is not None:
                try:
                    self._stockfish.close()
                except Exception:
                    pass
                self._stockfish = None