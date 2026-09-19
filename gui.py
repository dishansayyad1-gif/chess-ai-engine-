"""The main application window.

``ChessApp`` puts everything together: the board widget, the status line,
the move-history panel and the control buttons, and it wires up all user
interaction (clicks, promotion dialog, undo/redo, computer mode).

The computer opponent runs in a background thread so the interface stays
responsive while it thinks; results are applied back on the Tk main thread
via ``root.after``.
"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import chess

from board import ChessBoard
from game import Game
import ai as ai_module

_PROMOTION_PIECES = (
    ("Queen", chess.QUEEN),
    ("Rook", chess.ROOK),
    ("Bishop", chess.BISHOP),
    ("Knight", chess.KNIGHT),
)


class ChessApp:
    """The whole application: window, widgets and event handling."""

    def __init__(self, root):
        self.root = root
        self.root.title("Chess Game")

        self.game = Game()
        self.ai_manager = ai_module.AIManager()

        self._mode = tk.StringVar(value="pvp")
        self._difficulty = tk.StringVar(value="Medium")

        self._ai = None            # resolved lazily when computer mode is on
        self._ai_thinking = False
        self._generation = 0       # bumped to discard stale AI results
        self._ai_queue = None      # worker -> GUI communication channel
        self._ai_generation = 0
        self._poll_job = None
        self._selected = None
        self._status_job = None
        self._stockfish_warning_shown = False

        self._build_ui()
        self._refresh()

        # Keyboard shortcuts
        self.root.bind_all("<Control-z>", lambda _e: self._on_undo())
        self.root.bind_all("<Control-y>", lambda _e: self._on_redo())
        self.root.bind_all("<Control-Shift-z>", lambda _e: self._on_redo())
        self.root.bind_all("<Escape>", lambda _e: self._deselect())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # UI construction                                                     #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # Header + status
        tk.Label(self.root, text="CHESS GAME",
                 font=("Helvetica", 20, "bold")).pack(pady=(14, 2))
        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Helvetica", 14, "bold")).pack(pady=(0, 10))

        # Main row: board on the left, side panel on the right
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=14)

        self.board = ChessBoard(main, square_size=72,
                                on_square_click=self._on_square_click)
        self.board.pack(side="left", padx=(0, 16))

        side = tk.Frame(main)
        side.pack(side="left", fill="both", expand=True)

        # -- Move history panel
        tk.Label(side, text="Move History",
                 font=("Helvetica", 12, "bold")).pack(anchor="w")
        history_row = tk.Frame(side)
        history_row.pack(fill="both", expand=True, pady=(4, 10))
        self.history_text = tk.Text(
            history_row, width=26, height=16, wrap="none",
            state="disabled", font=("Consolas", 11),
        )
        scrollbar = ttk.Scrollbar(history_row, command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scrollbar.set)
        self.history_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        # -- Mode selection
        mode_frame = ttk.LabelFrame(side, text="Mode", padding=8)
        mode_frame.pack(fill="x", pady=(0, 8))

        self.pvp_radio = ttk.Radiobutton(
            mode_frame, text="Player vs Player", variable=self._mode,
            value="pvp", command=self._on_mode_change)
        self.pvp_radio.pack(anchor="w")

        self.pvc_radio = ttk.Radiobutton(
            mode_frame, text="Player vs Computer", variable=self._mode,
            value="pvc", command=self._on_mode_change)
        self.pvc_radio.pack(anchor="w", pady=(2, 0))

        difficulty_row = tk.Frame(mode_frame)
        difficulty_row.pack(anchor="w", pady=(6, 0))
        tk.Label(difficulty_row, text="Difficulty:",
                 font=("Helvetica", 10)).pack(side="left")
        self.difficulty_menu = ttk.Combobox(
            difficulty_row, textvariable=self._difficulty, state="readonly",
            values=list(ai_module.DIFFICULTIES), width=8,
        )
        self.difficulty_menu.pack(side="left", padx=(6, 0))
        self.difficulty_menu.bind("<<ComboboxSelected>>",
                                  self._on_difficulty_change)

        tk.Label(mode_frame, text="You play White; the computer plays Black.",
                 font=("Helvetica", 9), fg="#666666").pack(anchor="w",
                                                           pady=(6, 0))

        # -- Bottom buttons
        bottom = tk.Frame(self.root)
        bottom.pack(fill="x", padx=14, pady=(4, 14))

        self.new_game_btn = ttk.Button(bottom, text="New Game",
                                       command=self._on_new_game)
        self.new_game_btn.pack(side="left")
        self.undo_btn = ttk.Button(bottom, text="Undo",
                                   command=self._on_undo)
        self.undo_btn.pack(side="left", padx=(8, 0))
        self.redo_btn = ttk.Button(bottom, text="Redo",
                                   command=self._on_redo)
        self.redo_btn.pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------ #
    # Refresh                                                             #
    # ------------------------------------------------------------------ #
    def _refresh(self):
        """Redraw board, status, history and button states."""
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
            self._status_job = None
        self.status_var.set(self._current_status())

        targets = ()
        if self._selected is not None:
            targets = [m.to_square
                       for m in self.game.legal_moves_from(self._selected)]
        self.board.display(
            board=self.game.board,
            selected=self._selected,
            legal_targets=targets,
            last_move=self.game.last_move,
            check_square=self.game.check_square(),
        )

        self._update_history()
        self._update_controls()

    def _current_status(self):
        if self._ai_thinking:
            return "Computer is thinking..."
        return self.game.status_text()

    def _update_history(self):
        text = self.game.move_history_text()
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        self.history_text.insert("1.0", text)
        self.history_text.configure(state="disabled")
        self.history_text.see("end")

    def _update_controls(self):
        thinking = self._ai_thinking
        self.undo_btn.state(["disabled"] if (thinking or not self.game.can_undo)
                            else ["!disabled"])
        self.redo_btn.state(["disabled"] if (thinking or not self.game.can_redo)
                            else ["!disabled"])
        for widget in (self.pvp_radio, self.pvc_radio, self.difficulty_menu):
            widget.state(["disabled"] if thinking else ["!disabled"])
        if self._mode.get() == "pvp" and not thinking:
            self.difficulty_menu.state(["disabled"])
        self.root.config(cursor="" if not thinking else "watch")

    # ------------------------------------------------------------------ #
    # Click handling                                                      #
    # ------------------------------------------------------------------ #
    def _on_square_click(self, square):
        if self._ai_thinking or self.game.is_game_over():
            return
        if self.game.is_ai_turn():
            return

        if self._selected is not None:
            if square == self._selected:
                self._deselect()
                return
            if self._try_move(self._selected, square):
                return
        self._select_square(square)

    def _select_square(self, square):
        """Select a piece of the side to move (with feedback otherwise)."""
        piece = self.game.piece_at(square)
        if piece is None:
            if self._selected is not None:
                self._deselect()
                self._flash("Illegal move - no piece can move there")
            return
        if piece.color != self.game.turn:
            self._deselect()
            self._flash("You cannot move the opponent's pieces")
            return
        self._selected = square
        self._refresh()

    def _try_move(self, from_square, to_square):
        """Try to move the selected piece. Returns True when the click was
        consumed (move made or promotion cancelled)."""
        if self.game.requires_promotion(from_square, to_square):
            promotion = self._ask_promotion()
            if promotion is None:
                return True  # dialog cancelled - keep the piece selected
            move = self.game.find_move(from_square, to_square, promotion)
        else:
            move = self.game.find_move(from_square, to_square)

        if move is None:
            return False

        ok, _san = self.game.make_move(move)
        if not ok:
            return False

        self._selected = None
        self._refresh()
        self._maybe_run_ai()
        return True

    def _deselect(self):
        self._selected = None
        self._refresh()

    def _flash(self, message):
        """Temporarily replace the status line with feedback."""
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
        self.status_var.set(message)
        self._status_job = self.root.after(1600, self._restore_status)

    def _restore_status(self):
        self._status_job = None
        self.status_var.set(self._current_status())

    # ------------------------------------------------------------------ #
    # Promotion dialog                                                    #
    # ------------------------------------------------------------------ #
    def _ask_promotion(self):
        """Modal dialog asking which piece to promote to. Returns one of
        ``chess.QUEEN/ROOK/BISHOP/KNIGHT`` or ``None`` when cancelled."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Pawn Promotion")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        choice = {"value": None}
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        tk.Label(dialog, text="Choose a promotion piece:",
                 font=("Helvetica", 12, "bold")).pack(padx=20, pady=(14, 10))

        buttons = tk.Frame(dialog)
        buttons.pack(padx=20, pady=(0, 14))

        white = self.game.turn == chess.WHITE
        for index, (name, promo) in enumerate(_PROMOTION_PIECES):
            symbol = ("QRNB"[index]).lower() if not white else "QRNB"[index]
            image = self.board.renderer.image_for(symbol, size=56)
            if image is not None:
                button = tk.Button(buttons, text=name, image=image,
                                   compound="top", padx=6, pady=4,
                                   command=lambda p=promo: self._promotion_pick(
                                       dialog, choice, p))
            else:
                button = tk.Button(buttons, text=name, width=8,
                                   command=lambda p=promo: self._promotion_pick(
                                       dialog, choice, p))
            button.grid(row=0, column=index, padx=6)

        # Center the dialog over the main window.
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        dialog.grab_set()
        self.root.wait_window(dialog)
        return choice["value"]

    @staticmethod
    def _promotion_pick(dialog, choice, promo):
        choice["value"] = promo
        dialog.destroy()

    # ------------------------------------------------------------------ #
    # Controls                                                            #
    # ------------------------------------------------------------------ #
    def _on_new_game(self):
        if self.game.can_undo or self.game.can_redo:
            answer = messagebox.askyesno(
                "New Game",
                "Start a new game?\n\nThe current game will be lost.",
                parent=self.root)
            if not answer:
                return
        self._generation += 1  # discard any pending computer move
        self.game.reset()
        self._deselect()

    def _on_undo(self):
        if not self.game.can_undo or self._ai_thinking:
            return
        self._generation += 1
        self.game.undo()
        self._deselect()

    def _on_redo(self):
        if not self.game.can_redo or self._ai_thinking:
            return
        self._generation += 1
        self.game.redo()
        self._deselect()
        self._maybe_run_ai()

    def _on_mode_change(self):
        computer_mode = self._mode.get() == "pvc"
        self.game.set_ai_mode(computer_mode)
        self._selected = None

        if computer_mode:
            self._ensure_ai()
        self._refresh()
        self._maybe_run_ai()

    def _on_difficulty_change(self, _event=None):
        if self._mode.get() == "pvc" and not self._ai_thinking:
            self._ensure_ai()  # reapplies the new difficulty to the engine

    def _ensure_ai(self):
        """Start (or reconfigure) the computer opponent, warning the user
        once when Stockfish is unavailable."""
        self._ai = self.ai_manager.get_ai(self._difficulty.get())
        if (not self.ai_manager.uses_stockfish()
                and not self._stockfish_warning_shown):
            self._stockfish_warning_shown = True
            messagebox.showinfo(
                "Computer mode",
                "Stockfish was not found, so the built-in Simple AI will be "
                "used instead.\n\n"
                "To play against Stockfish:\n"
                "  - Windows: download it from stockfishchess.org and set "
                "the STOCKFISH_PATH environment variable, or\n"
                "  - macOS: brew install stockfish\n"
                "  - Linux: apt install stockfish\n\n"
                "See the README for details.",
                parent=self.root)

    # ------------------------------------------------------------------ #
    # Computer turn                                                       #
    # ------------------------------------------------------------------ #
    def _maybe_run_ai(self):
        if self.game.is_ai_turn():
            self._start_ai_move()

    def _start_ai_move(self):
        if self._ai_thinking or not self.game.is_ai_turn():
            return
        self._ai_thinking = True
        self._ensure_ai()
        self.status_var.set("Computer is thinking...")
        self._update_controls()

        # The worker hands the result back through a queue; the main
        # thread polls it with ``after``. (Tk widgets must only be touched
        # from the main thread, so the worker never calls Tk directly.)
        generation = self._generation
        board_snapshot = self.game.board.copy()
        self._ai_queue = queue.Queue()
        self._ai_generation = generation
        self._poll_job = self.root.after(80, self._poll_ai_result)

        def worker():
            try:
                move = self._ai.find_best_move(board_snapshot)
            except Exception:
                move = None
            self._ai_queue.put(move)

        threading.Thread(target=worker, daemon=True).start()

    def _poll_ai_result(self):
        """Check for a finished computer move (runs on the main thread)."""
        self._poll_job = None
        try:
            move = self._ai_queue.get_nowait()
        except queue.Empty:
            if self._ai_thinking:
                self._poll_job = self.root.after(80, self._poll_ai_result)
            return
        self._on_ai_done(self._ai_generation, move)

    def _on_ai_done(self, generation, move):
        self._ai_thinking = False
        self._update_controls()
        if generation != self._generation:
            return  # the game changed while the computer was thinking
        if move is None:
            self._flash("Computer could not find a move")
            self._refresh()
            return
        ok, _san = self.game.make_move(move)
        self._refresh()
        if ok and self.game.is_ai_turn():
            self._start_ai_move()

    # ------------------------------------------------------------------ #
    # Shutdown                                                            #
    # ------------------------------------------------------------------ #
    def _on_close(self):
        self.ai_manager.close()
        self.root.destroy()