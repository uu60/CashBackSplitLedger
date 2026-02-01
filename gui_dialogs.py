"""
Dialog windows for SplitLedger GUI
"""
from __future__ import annotations
import uuid
from typing import Dict, List, Optional

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ModuleNotFoundError:
    tk = None
    ttk = None
    messagebox = None

from models import Expense, Ledger
from utils import today_str, safe_float, parse_date
from computations import normalize_allocations, build_card_map


class AllocationEditor(tk.Toplevel):
    """Dialog for editing consumption share allocations"""
    
    def __init__(self, master, people: List[str], alloc: Dict[str, float]):
        super().__init__(master)
        self.title("Allocation (Consumption Shares)")
        self.resizable(False, False)
        self.people = people
        self.vars: Dict[str, tk.StringVar] = {}
        self.result: Optional[Dict[str, float]] = None

        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Enter each person's share (will be normalized).").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        for i, p in enumerate(people):
            ttk.Label(frm, text=p).grid(row=i + 1, column=0, sticky="w")
            v = tk.StringVar(value=str(alloc.get(p, 0.0)))
            self.vars[p] = v
            ttk.Entry(frm, textvariable=v, width=10).grid(row=i + 1, column=1, sticky="w")
        
        self.sum_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.sum_var).grid(row=1, column=2, rowspan=len(people), sticky="n")

        btns = ttk.Frame(frm)
        btns.grid(row=len(people) + 2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Equal", command=self._equal).grid(row=0, column=0, padx=3)
        ttk.Button(btns, text="Normalize", command=self._normalize_only).grid(row=0, column=1, padx=3)
        ttk.Button(btns, text="Clear", command=self._clear).grid(row=0, column=2, padx=3)
        ttk.Button(btns, text="OK", command=self._ok).grid(row=0, column=3, padx=12)
        ttk.Button(btns, text="Cancel", command=self._cancel).grid(row=0, column=4, padx=3)

        for p in people:
            self.vars[p].trace_add("write", lambda *_: self._update_sum())
        self._update_sum()

        self.grab_set()
        self.transient(master)

    def _read(self) -> Dict[str, float]:
        """Read current allocation values from inputs"""
        d = {}
        for p, v in self.vars.items():
            d[p] = safe_float(v.get(), 0.0)
        return d

    def _update_sum(self):
        """Update sum label"""
        d = self._read()
        s = sum(max(0.0, v) for v in d.values())
        self.sum_var.set(f"Sum: {s:.4f}")

    def _equal(self):
        """Set equal shares for all people"""
        n = max(1, len(self.people))
        for p in self.people:
            self.vars[p].set(str(1.0 / n))

    def _normalize_only(self):
        """Normalize current values to sum to 1"""
        d = normalize_allocations(self._read(), self.people)
        for p in self.people:
            self.vars[p].set(f"{d[p]:.6f}")

    def _clear(self):
        """Clear all allocations"""
        for p in self.people:
            self.vars[p].set("0")

    def _ok(self):
        """Save and close"""
        d = normalize_allocations(self._read(), self.people)
        self.result = d
        self.destroy()

    def _cancel(self):
        """Cancel and close"""
        self.result = None
        self.destroy()


class ExpenseDialog(tk.Toplevel):
    """Dialog for adding/editing an expense"""
    
    def __init__(self, master, ledger: Ledger, expense: Optional[Expense] = None):
        super().__init__(master)
        self.title("Add Expense" if expense is None else "Edit Expense")
        self.resizable(False, False)
        self.ledger = ledger
        self.expense = expense
        self.result: Optional[Expense] = None

        self._bind_enter_to_ok()

        people = ledger.people
        cards = [c.name for c in ledger.cards] or ["Default 0%"]

        # Read last defaults safely
        last = getattr(ledger, "last_defaults", {}) or {}

        def default_or(fallback, key):
            v = last.get(key)
            return v if v else fallback

        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        # Default logic (EDIT > LAST DEFAULT > FALLBACK)
        self.v_date = tk.StringVar(
            value=expense.date if expense else default_or(today_str(), "date")
        )
        self.v_payer = tk.StringVar(
            value=expense.payer if expense else default_or((people[0] if people else ""), "payer")
        )
        self.v_card = tk.StringVar(
            value=expense.card if expense else default_or((cards[0] if cards else ""), "card")
        )
        self.v_merchant = tk.StringVar(
            value=expense.merchant if expense else default_or("", "merchant")
        )

        self.v_item = tk.StringVar(value=expense.item if expense else "")
        self.v_amount = tk.StringVar(value=str(expense.amount) if expense else "0")
        self.v_notes = tk.StringVar(value=expense.notes if expense else "")

        r = 0
        ttk.Label(frm, text="Date (YYYY-MM-DD)").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_date, width=18).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Payer").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Combobox(frm, textvariable=self.v_payer, values=people,
                     width=16, state="readonly").grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Card").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Combobox(frm, textvariable=self.v_card, values=cards,
                     width=16, state="readonly").grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Merchant").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_merchant, width=28).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Item").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_item, width=28).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Amount").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_amount, width=18).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(frm, text="Notes").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_notes, width=28).grid(row=r, column=1, sticky="w")
        r += 1

        # Allocation
        self.alloc = normalize_allocations(
            (expense.allocations if expense else {}), people
        ) if people else {}

        alloc_frame = ttk.Frame(frm)
        alloc_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            alloc_frame, text="Edit Consumption Shares…", command=self._edit_alloc
        ).grid(row=0, column=0, sticky="w")

        self.alloc_label = ttk.Label(alloc_frame, text=self._alloc_text())
        self.alloc_label.grid(row=0, column=1, padx=8, sticky="w")
        r += 1

        # Cashback info
        self.cashback_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.cashback_var).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        self._update_cashback_label()
        self.v_amount.trace_add("write", lambda *_: self._update_cashback_label())
        self.v_card.trace_add("write", lambda *_: self._update_cashback_label())
        r += 1

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="OK", command=self._ok).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Cancel", command=self._cancel).grid(row=0, column=1, padx=4)

        self.grab_set()
        self.transient(master)

    def _bind_enter_to_ok(self):
        """Bind Enter/Return to OK (avoid triggering when focus is on buttons if you want)."""

        def on_enter(event=None):
            self._ok()
            return "break"  # prevent default beeps / double handling

        # Main Enter and keypad Enter
        self.bind("<Return>", on_enter)
        self.bind("<KP_Enter>", on_enter)

    def _alloc_text(self) -> str:
        """Format allocation for display"""
        parts = [f"{p}:{self.alloc.get(p, 0.0):.2f}" for p in self.ledger.people]
        return "  ".join(parts)

    def _edit_alloc(self):
        """Open allocation editor dialog"""
        dlg = AllocationEditor(self, self.ledger.people, self.alloc)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.alloc = dlg.result
            self.alloc_label.config(text=self._alloc_text())

    def _update_cashback_label(self):
        """Update cashback information label"""
        amt = safe_float(self.v_amount.get(), 0.0)
        rate = build_card_map(self.ledger.cards).get(self.v_card.get(), 0.0)
        cb = amt * rate
        mult = 1.0 - rate if self.ledger.apply_cashback_as_discount else 1.0
        base = amt * mult
        self.cashback_var.set(
            f"Cashback: {cb:.2f}   Split base: {base:.2f}   (rate={rate:.2%})"
        )

    def _ok(self):
        """Validate and save expense"""
        try:
            parse_date(self.v_date.get())
        except Exception:
            messagebox.showerror("Invalid date", "Date must be YYYY-MM-DD.")
            return

        amt = safe_float(self.v_amount.get(), None)
        if amt is None or amt < 0:
            messagebox.showerror("Invalid amount", "Amount must be a non-negative number.")
            return

        if not self.v_payer.get():
            messagebox.showerror("Missing payer", "Please select a payer.")
            return

        if not self.v_item.get() and not self.v_merchant.get():
            messagebox.showerror("Missing description", "Please fill merchant or item.")
            return

        alloc = normalize_allocations(self.alloc, self.ledger.people)
        eid = self.expense.id if self.expense else str(uuid.uuid4())

        self.result = Expense(
            id=eid,
            date=self.v_date.get().strip(),
            payer=self.v_payer.get().strip(),
            card=self.v_card.get().strip(),
            merchant=self.v_merchant.get().strip(),
            item=self.v_item.get().strip() or self.v_merchant.get().strip(),
            amount=float(amt),
            allocations=alloc,
            notes=self.v_notes.get().strip(),
        )

        # Update last defaults for next Add
        if not hasattr(self.ledger, "last_defaults"):
            self.ledger.last_defaults = {}
        self.ledger.last_defaults.update({
            "date": self.result.date,
            "merchant": self.result.merchant,
            "payer": self.result.payer,
            "card": self.result.card,
        })

        self.destroy()

    def _cancel(self):
        """Cancel and close"""
        self.result = None
        self.destroy()
