

def main():
    try:
        import tkinter as tk
    except ImportError:
        print(
            "Tkinter is not available on this Python installation.\n"
            "Install it first, e.g. on Debian/Ubuntu: sudo apt install python3-tk"
        )
        return 1

    from gui import ChessApp

    root = tk.Tk()
    ChessApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())