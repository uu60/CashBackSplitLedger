"""
SplitLedger GUI
- Record who paid what, who consumed what share, and per-transaction credit-card cashback.
- Export an Excel report similar to the user's sample: one sheet per payer + summary + transfers.

Run:
  python split_ledger_gui.py

Dependencies:
  pip install openpyxl
(Tkinter ships with most Python distributions; on some Linux you may need: sudo apt-get install python3-tk)
"""
from __future__ import annotations

try:
    import tkinter as tk
except ModuleNotFoundError:
    tk = None

from main_app import SplitLedgerApp
import openpyxl


def main():
    """Main entry point for the application"""
    if tk is None:
        raise RuntimeError(
            'tkinter is not available. Install it (e.g., on Ubuntu: sudo apt-get install python3-tk) '
            'and re-run to use the GUI.'
        )
    
    root = tk.Tk()
    app = SplitLedgerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
