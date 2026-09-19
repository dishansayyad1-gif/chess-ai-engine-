"""The chess board widget.

``ChessBoard`` is a ``tk.Canvas`` that draws the 8x8 board (squares,
coordinates, pieces) plus move highlights, and reports clicks as chess
squares. It knows nothing about the rules of chess -- it simply displays
whatever board and highlight state the GUI hands it.
"""

import tkinter as tk

import chess

from pieces.renderer import PieceRenderer

# Colors
LIGHT_SQUARE = "#F0D9B5"
DARK_SQUARE = "#B58863"
BORDER_COLOR = "#5A4632"
COORDINATE_COLOR = "#E6D3B8"
LAST_MOVE_COLOR = "#C8D26B"    # soft yellow-green
SELECTED_COLOR = "#8EB84D"     # green
CHECK_COLOR = "#E05A47"        # red
LEGAL_DOT_COLOR = "#2F2F2F"
LEGAL_RING_COLOR = "#2F2F2F"


class ChessBoard(tk.Canvas):
    """An 8x8 chess board rendered on a Tkinter canvas."""

    def __init__(self, master, square_size=72, on_square_click=None):
        self.square_size = square_size
        self.margin = int(square_size * 0.39)  # strip for coordinate labels
        size = square_size * 8 + 2 * self.margin

        super().__init__(
            master,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg=BORDER_COLOR,
        )

        self.renderer = PieceRenderer(master, square_size)
        self._on_square_click = on_square_click

        self._board = None
        self._selected = None
        self._legal_targets = ()
        self._last_move = None
        self._check_square = None

        self.bind("<Button-1>", self._handle_click)

    # ------------------------------------------------------------------ #
    # Geometry                                                            #
    # ------------------------------------------------------------------ #
    def square_at(self, x, y):
        """Map canvas coordinates to a chess square, or ``None`` when the
        click landed in the coordinate margin."""
        x -= self.margin
        y -= self.margin
        if not (0 <= x < 8 * self.square_size and 0 <= y < 8 * self.square_size):
            return None
        file_ = int(x // self.square_size)
        rank = 7 - int(y // self.square_size)
        return rank * 8 + file_

    def square_center(self, square):
        """Center pixel of a square (for drawing pieces)."""
        file_ = chess.square_file(square)
        rank = chess.square_rank(square)
        x = self.margin + (file_ + 0.5) * self.square_size
        y = self.margin + (7 - rank + 0.5) * self.square_size
        return x, y

    def square_rect(self, square):
        """Pixel rectangle of a square."""
        file_ = chess.square_file(square)
        rank = chess.square_rank(square)
        x0 = self.margin + file_ * self.square_size
        y0 = self.margin + (7 - rank) * self.square_size
        return x0, y0, x0 + self.square_size, y0 + self.square_size

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    def display(self, board, selected=None, legal_targets=(), last_move=None,
                check_square=None):
        """Store the state to draw and redraw the whole board."""
        self._board = board
        self._selected = selected
        self._legal_targets = tuple(legal_targets)
        self._last_move = last_move
        self._check_square = check_square
        self._redraw()

    def _handle_click(self, event):
        square = self.square_at(event.x, event.y)
        if square is not None and self._on_square_click is not None:
            self._on_square_click(square)

    # ------------------------------------------------------------------ #
    # Drawing                                                             #
    # ------------------------------------------------------------------ #
    def _redraw(self):
        self.delete("all")
        if self._board is None:
            return

        for square in chess.SQUARES:
            self._draw_square(square)

        if self._last_move is not None:
            self._fill_square(self._last_move.to_square, LAST_MOVE_COLOR)
        if self._selected is not None:
            self._fill_square(self._selected, SELECTED_COLOR)
        if self._check_square is not None:
            self._fill_square(self._check_square, CHECK_COLOR, stipple="gray50")

        for target in self._legal_targets:
            self._draw_move_marker(target)

        self._draw_coordinates()

        for square in chess.SQUARES:
            piece = self._board.piece_at(square)
            if piece is not None:
                self._draw_piece(square, piece)

    def _draw_square(self, square):
        file_ = chess.square_file(square)
        rank = chess.square_rank(square)
        color = LIGHT_SQUARE if (file_ + rank) % 2 == 1 else DARK_SQUARE
        x0, y0, x1, y1 = self.square_rect(square)
        self.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    def _fill_square(self, square, color, stipple=None):
        x0, y0, x1, y1 = self.square_rect(square)
        kwargs = {"fill": color, "outline": ""}
        if stipple:
            kwargs["stipple"] = stipple
        self.create_rectangle(x0, y0, x1, y1, **kwargs)

    def _draw_move_marker(self, square):
        """A dot on empty squares, a ring on squares that contain a piece."""
        cx, cy = self.square_center(square)
        if self._board.piece_at(square) is None:
            radius = self.square_size * 0.14
            self.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                             fill=LEGAL_DOT_COLOR, outline="")
        else:
            radius = self.square_size * 0.40
            width = max(3, int(self.square_size * 0.05))
            self.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                             outline=LEGAL_RING_COLOR, width=width)

    def _draw_coordinates(self):
        font = ("Helvetica", max(8, self.square_size // 8))
        for file_ in range(8):
            x = self.margin + (file_ + 0.5) * self.square_size
            y = self.margin + 8 * self.square_size + self.margin * 0.55
            self.create_text(x, y, text=chess.FILE_NAMES[file_],
                             font=font, fill=COORDINATE_COLOR)
        for rank in range(8):
            x = self.margin * 0.45
            y = self.margin + (7 - rank + 0.5) * self.square_size
            self.create_text(x, y, text=chess.RANK_NAMES[rank],
                             font=font, fill=COORDINATE_COLOR)

    def _draw_piece(self, square, piece):
        cx, cy = self.square_center(square)
        image = self.renderer.image_for(piece.symbol())
        if image is not None:
            self.create_image(cx, cy, image=image)
        else:
            self._draw_text_piece(cx, cy, piece.symbol())

    def _draw_text_piece(self, cx, cy, symbol):
        """Fallback renderer: Unicode glyph drawn twice (outline + fill)."""
        glyph = self.renderer.glyph(symbol)
        font = (self.renderer.text_font_name, int(self.square_size * 0.78))
        if symbol.isupper():
            fill, outline = "#FFFFFF", "#3B3B3B"
        else:
            fill, outline = "#2B2B2B", "#E8E8E8"
        offset = max(1, int(self.square_size * 0.025))
        for dx in (-offset, 0, offset):
            for dy in (-offset, 0, offset):
                if dx == 0 and dy == 0:
                    continue
                self.create_text(cx + dx, cy + dy, text=glyph,
                                 font=font, fill=outline)
        self.create_text(cx, cy, text=glyph, font=font, fill=fill)