"""Game state management built on top of python-chess.

``Game`` owns the ``chess.Board`` and everything the interface needs around
it: the move history with SAN notation, undo/redo, the computer-mode flag
and the human readable status text. It deliberately contains **no GUI
code**, so it can be tested and reused independently.
"""

import chess


class Game:
    """High-level wrapper around ``chess.Board``."""

    def __init__(self):
        self._board = chess.Board()
        self._history = []   # every chess.Move played this game
        self._sans = []      # SAN of every move, kept in sync with _history
        self._cursor = 0     # how many of those moves are currently applied
        self._ai_mode = False

    # ------------------------------------------------------------------ #
    # Basic accessors                                                     #
    # ------------------------------------------------------------------ #
    @property
    def board(self):
        """The underlying ``chess.Board`` (read directly if needed)."""
        return self._board

    @property
    def turn(self):
        return self._board.turn

    @property
    def last_move(self):
        """The move that was most recently applied, or ``None``."""
        return self._history[self._cursor - 1] if self._cursor > 0 else None

    @property
    def can_undo(self):
        return self._cursor > 0

    @property
    def can_redo(self):
        return self._cursor < len(self._history)

    def is_game_over(self):
        return self._board.is_game_over()

    # ------------------------------------------------------------------ #
    # Computer mode                                                       #
    # ------------------------------------------------------------------ #
    def is_ai_mode(self):
        return self._ai_mode

    def set_ai_mode(self, enabled):
        self._ai_mode = bool(enabled)

    def is_ai_turn(self):
        """True when the computer (which plays Black) must move."""
        return (
            self._ai_mode
            and self._board.turn == chess.BLACK
            and not self._board.is_game_over()
        )

    # ------------------------------------------------------------------ #
    # Move lookup                                                         #
    # ------------------------------------------------------------------ #
    def piece_at(self, square):
        return self._board.piece_at(square)

    def legal_moves_from(self, square):
        """Every legal move that starts on ``square``."""
        return [m for m in self._board.legal_moves if m.from_square == square]

    def requires_promotion(self, from_square, to_square):
        """True when a move between these squares must be a promotion."""
        return any(
            m.from_square == from_square
            and m.to_square == to_square
            and m.promotion
            for m in self._board.legal_moves
        )

    def find_move(self, from_square, to_square, promotion=None):
        """Return the legal ``chess.Move`` matching these squares, or
        ``None`` if there is no such legal move.

        ``promotion`` must be one of ``chess.QUEEN``/``ROOK``/``BISHOP``/
        ``KNIGHT`` when the move is a promotion.
        """
        for move in self._board.legal_moves:
            if move.from_square == from_square and move.to_square == to_square:
                if move.promotion:
                    if promotion == move.promotion:
                        return move
                elif promotion is None:
                    return move
        return None

    # ------------------------------------------------------------------ #
    # Actions                                                             #
    # ------------------------------------------------------------------ #
    def make_move(self, move):
        """Apply a move. Returns ``(ok, san)`` where ``ok`` is False when
        the move is illegal (the board is left untouched)."""
        if move not in self._board.legal_moves:
            return False, ""
        # Discard any undone moves (the redo branch) before appending.
        if self._cursor < len(self._history):
            del self._history[self._cursor:]
            del self._sans[self._cursor:]
        san = self._board.san(move)
        self._board.push(move)
        self._history.append(move)
        self._sans.append(san)
        self._cursor += 1
        return True, san

    def undo(self):
        """Take back the last move.

        In computer mode the computer's reply is taken back too, so the
        human is always returned to *their* position. Returns True when
        anything was undone.
        """
        if self._cursor == 0:
            return False
        steps = 2 if self._ai_mode else 1
        undone = 0
        while steps > 0 and self._cursor > 0:
            self._board.pop()
            self._cursor -= 1
            steps -= 1
            undone += 1
        return undone > 0

    def redo(self):
        """Re-apply moves that were undone (one ply, or a human+computer
        pair in computer mode). Returns True when a move was replayed."""
        if self._cursor >= len(self._history):
            return False
        limit = 2 if self._ai_mode else 1
        replayed = 0
        while limit > 0 and self._cursor < len(self._history):
            self._board.push(self._history[self._cursor])
            self._cursor += 1
            limit -= 1
            replayed += 1
        return replayed > 0

    def reset(self):
        """Start a fresh game: starting position, no history."""
        self._board.reset()
        self._history.clear()
        self._sans.clear()
        self._cursor = 0

    # ------------------------------------------------------------------ #
    # Status and history text                                             #
    # ------------------------------------------------------------------ #
    def status_text(self):
        """Human readable status, e.g. ``"White's Turn"``, ``"Check!"``,
        ``"Checkmate! Black wins"`` or ``"Draw - Stalemate"``."""
        board = self._board
        if board.is_checkmate():
            winner = "Black" if board.turn == chess.WHITE else "White"
            return f"Checkmate! {winner} wins"
        if board.is_stalemate():
            return "Draw - Stalemate"
        if board.is_insufficient_material():
            return "Draw - Insufficient material"
        if board.is_seventyfive_moves() or board.is_repetition(3):
            return "Draw - Repetition"
        if board.is_fifty_moves():
            return "Draw - Fifty-move rule"
        turn = "White" if board.turn == chess.WHITE else "Black"
        if board.is_check():
            return f"Check! {turn}'s Turn"
        return f"{turn}'s Turn"

    def move_history_text(self):
        """Format the history like ``1. e4 e5\\n2. Nf3 Nc6``."""
        lines = []
        for index in range(0, len(self._sans), 2):
            number = index // 2 + 1
            white = self._sans[index]
            black = self._sans[index + 1] if index + 1 < len(self._sans) else ""
            lines.append(f"{number}. {white} {black}".rstrip())
        return "\n".join(lines)

    def check_square(self):
        """Square of the king currently in check, or ``None``."""
        if not self._board.is_check():
            return None
        return self._board.king(self._board.turn)