"""
Main application window for SplitLedger GUI
"""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Optional, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ModuleNotFoundError:
    tk = None
    ttk = None
    messagebox = None
    filedialog = None

from models import Card, Ledger
from config import get_default_ledger, ledger_to_dict, dict_to_ledger
from utils import parse_date, safe_float
from computations import (
    build_card_map,
    expense_cashback,
    expense_split_base,
    normalize_allocations,
    compute_summary,
    compute_transfers
)
from excel_export import export_excel
from gui_dialogs import ExpenseDialog
from csv_handler import export_expenses_to_csv, import_expenses_from_csv


class SplitLedgerApp(ttk.Frame):
    """Main application window"""
    
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=8)
        self.master = master
        self.master.title("SplitLedger")
        self.master.geometry("1100x650")
        self.grid(row=0, column=0, sticky="nsew")
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

        self.ledger_path: Optional[str] = None
        self.ledger: Ledger = get_default_ledger()

        self._build_menu()
        self._build_ui()
        self.refresh_all()

    # ---------- Menu ----------
    def _build_menu(self):
        """Build application menu bar"""
        menubar = tk.Menu(self.master)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="New", command=self.new_ledger)
        filem.add_command(label="Open…", command=self.open_ledger)
        filem.add_command(label="Save", command=self.save_ledger)
        filem.add_command(label="Save As…", command=self.save_as_ledger)
        filem.add_separator()
        filem.add_command(label="Export CSV…", command=self.export_csv_dialog)
        filem.add_command(label="Import CSV…", command=self.import_csv_dialog)
        filem.add_separator()
        filem.add_command(label="Export Excel…", command=self.export_excel_dialog)
        filem.add_separator()
        filem.add_command(label="Exit", command=self.master.destroy)
        menubar.add_cascade(label="File", menu=filem)

        settingsm = tk.Menu(menubar, tearoff=0)
        self.apply_discount_var = tk.BooleanVar(value=True)
        settingsm.add_checkbutton(
            label="Apply cashback as discount when splitting",
            variable=self.apply_discount_var,
            command=self._toggle_discount,
        )
        menubar.add_cascade(label="Settings", menu=settingsm)

        self.master.config(menu=menubar)

    def _toggle_discount(self):
        """Toggle cashback discount setting"""
        self.ledger.apply_cashback_as_discount = bool(self.apply_discount_var.get())
        self.refresh_all()

    # ---------- UI ----------
    def _build_ui(self):
        """Build main UI with tabs"""
        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tab_expenses = ttk.Frame(nb, padding=8)
        self.tab_people = ttk.Frame(nb, padding=8)
        self.tab_cards = ttk.Frame(nb, padding=8)
        self.tab_reports = ttk.Frame(nb, padding=8)

        nb.add(self.tab_expenses, text="Expenses")
        nb.add(self.tab_people, text="People")
        nb.add(self.tab_cards, text="Cards")
        nb.add(self.tab_reports, text="Reports")

        self._build_expenses_tab()
        self._build_people_tab()
        self._build_cards_tab()
        self._build_reports_tab()

    def _build_expenses_tab(self):
        """Build expenses tab"""
        top = ttk.Frame(self.tab_expenses)
        top.grid(row=0, column=0, sticky="ew")
        self.tab_expenses.columnconfigure(0, weight=1)

        ttk.Button(top, text="Add", command=self.add_expense).pack(side="left", padx=3)
        ttk.Button(top, text="Edit", command=self.edit_selected_expense).pack(side="left", padx=3)
        ttk.Button(top, text="Delete", command=self.delete_selected_expense).pack(side="left", padx=3)

        ttk.Separator(self.tab_expenses, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=6)

        cols = ("date", "payer", "card", "merchant", "item", "amount", "split_base", "cashback", "alloc", "notes")
        self.exp_tree = ttk.Treeview(self.tab_expenses, columns=cols, show="headings", height=18)
        for c, w in zip(cols, [95, 80, 110, 160, 220, 90, 90, 90, 220, 500]):
            self.exp_tree.heading(c, text=c)
            self.exp_tree.column(c, width=w, anchor="w")
        self.exp_tree.grid(row=2, column=0, sticky="nsew")
        self.tab_expenses.rowconfigure(2, weight=1)

        yscroll = ttk.Scrollbar(self.tab_expenses, orient="vertical", command=self.exp_tree.yview)
        self.exp_tree.configure(yscroll=yscroll.set)
        yscroll.grid(row=2, column=1, sticky="ns")

    def _build_people_tab(self):
        """Build people management tab"""
        self.tab_people.columnconfigure(0, weight=1)
        frm = ttk.Frame(self.tab_people)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="People:").grid(row=0, column=0, sticky="w")
        self.people_list = tk.Listbox(frm, height=18)
        self.people_list.grid(row=1, column=0, sticky="nsew", pady=6)
        frm.rowconfigure(1, weight=1)
        frm.columnconfigure(0, weight=1)

        controls = ttk.Frame(frm)
        controls.grid(row=2, column=0, sticky="ew")
        self.new_person_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.new_person_var, width=18).pack(side="left")
        ttk.Button(controls, text="Add", command=self.add_person).pack(side="left", padx=4)
        ttk.Button(controls, text="Remove Selected", command=self.remove_selected_person).pack(side="left", padx=4)

        ttk.Label(frm,
                  text="Note: removing a person will also remove them from future allocations; existing expenses are preserved but will be normalized.").grid(
            row=3, column=0, sticky="w", pady=(8, 0))

    def _build_cards_tab(self):
        """Build cards management tab"""
        self.tab_cards.columnconfigure(0, weight=1)
        top = ttk.Frame(self.tab_cards)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Add Card", command=self.add_card).pack(side="left", padx=3)
        ttk.Button(top, text="Edit Selected", command=self.edit_selected_card).pack(side="left", padx=3)
        ttk.Button(top, text="Remove Selected", command=self.remove_selected_card).pack(side="left", padx=3)

        cols = ("name", "cashback_rate")
        self.card_tree = ttk.Treeview(self.tab_cards, columns=cols, show="headings", height=18)
        self.card_tree.heading("name", text="name")
        self.card_tree.heading("cashback_rate", text="cashback_rate")
        self.card_tree.column("name", width=240, anchor="w")
        self.card_tree.column("cashback_rate", width=120, anchor="w")
        self.card_tree.grid(row=1, column=0, sticky="nsew", pady=6)
        self.tab_cards.rowconfigure(1, weight=1)

        yscroll = ttk.Scrollbar(self.tab_cards, orient="vertical", command=self.card_tree.yview)
        self.card_tree.configure(yscroll=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns")

        ttk.Label(self.tab_cards, text="cashback_rate is a fraction: 0.06 means 6%.").grid(row=2, column=0,
                                                                                           sticky="w")

    def _build_reports_tab(self):
        """Build reports tab"""
        self.tab_reports.columnconfigure(0, weight=1)

        filt = ttk.Frame(self.tab_reports)
        filt.grid(row=0, column=0, sticky="ew")
        ttk.Label(filt, text="Start (YYYY-MM-DD)").pack(side="left")
        self.rep_start = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self.rep_start, width=12).pack(side="left", padx=4)
        ttk.Label(filt, text="End (YYYY-MM-DD)").pack(side="left")
        self.rep_end = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self.rep_end, width=12).pack(side="left", padx=4)

        ttk.Button(filt, text="Refresh", command=self.refresh_reports).pack(side="left", padx=8)
        ttk.Button(filt, text="Export Excel…", command=self.export_excel_dialog).pack(side="left", padx=3)

        self.report_note = tk.StringVar(value="")
        ttk.Label(self.tab_reports, textvariable=self.report_note).grid(row=1, column=0, sticky="w", pady=(6, 0))

        cols = ("person", "paid", "consumed", "net", "cashback", "net_plus_cashback")
        self.sum_tree = ttk.Treeview(self.tab_reports, columns=cols, show="headings", height=10)
        for c, w in zip(cols, [90, 120, 120, 120, 120, 140]):
            self.sum_tree.heading(c, text=c)
            self.sum_tree.column(c, width=w, anchor="w")
        self.sum_tree.grid(row=2, column=0, sticky="nsew", pady=6)
        self.tab_reports.rowconfigure(2, weight=1)

        ttk.Label(self.tab_reports, text="Transfers (settlement) based on Net (Paid-Consumed):").grid(row=3,
                                                                                                      column=0,
                                                                                                      sticky="w",
                                                                                                      pady=(10, 0))
        tcols = ("from", "to", "amount")
        self.tr_tree = ttk.Treeview(self.tab_reports, columns=tcols, show="headings", height=10)
        for c, w in zip(tcols, [140, 140, 120]):
            self.tr_tree.heading(c, text=c)
            self.tr_tree.column(c, width=w, anchor="w")
        self.tr_tree.grid(row=4, column=0, sticky="nsew")
        self.tab_reports.rowconfigure(4, weight=1)

    # ---------- CRUD: Expenses ----------
    def add_expense(self):
        """Add new expense"""
        if not self.ledger.people:
            messagebox.showerror("No people", "Please add at least one person first.")
            return
        dlg = ExpenseDialog(self.master, self.ledger, None)
        self.master.wait_window(dlg)
        if dlg.result:
            self.ledger.expenses.append(dlg.result)
            self.refresh_all()

    def edit_selected_expense(self):
        """Edit selected expense"""
        sel = self.exp_tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select an expense row first.")
            return
        iid = sel[0]
        e = next((x for x in self.ledger.expenses if x.id == iid), None)
        if not e:
            return
        dlg = ExpenseDialog(self.master, self.ledger, e)
        self.master.wait_window(dlg)
        if dlg.result:
            for i, x in enumerate(self.ledger.expenses):
                if x.id == dlg.result.id:
                    self.ledger.expenses[i] = dlg.result
                    break
            self.refresh_all()

    def delete_selected_expense(self):
        """Delete selected expense"""
        sel = self.exp_tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select an expense row first.")
            return
        iid = sel[0]
        if messagebox.askyesno("Delete", "Delete selected expense?"):
            self.ledger.expenses = [e for e in self.ledger.expenses if e.id != iid]
            self.refresh_all()

    # ---------- CRUD: People ----------
    def add_person(self):
        """Add new person"""
        name = self.new_person_var.get().strip()
        if not name:
            return
        if name in self.ledger.people:
            messagebox.showinfo("People", "Name already exists.")
            return
        self.ledger.people.append(name)
        self.new_person_var.set("")
        # normalize existing allocations
        for e in self.ledger.expenses:
            e.allocations = normalize_allocations(e.allocations, self.ledger.people)
        self.refresh_all()

    def remove_selected_person(self):
        """Remove selected person"""
        sel = self.people_list.curselection()
        if not sel:
            return
        name = self.people_list.get(sel[0])
        if messagebox.askyesno("Remove person", f"Remove '{name}'? Existing expenses will be re-normalized."):
            self.ledger.people = [p for p in self.ledger.people if p != name]
            for e in self.ledger.expenses:
                if name in e.allocations:
                    del e.allocations[name]
                e.allocations = normalize_allocations(e.allocations, self.ledger.people)
            self.refresh_all()

    # ---------- CRUD: Cards ----------
    def add_card(self):
        """Add new card"""
        dlg = tk.Toplevel(self.master)
        dlg.title("Add Card")
        dlg.resizable(False, False)
        v_name = tk.StringVar()
        v_rate = tk.StringVar(value="0.0")
        frm = ttk.Frame(dlg, padding=10)
        frm.grid(row=0, column=0)
        ttk.Label(frm, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_name, width=28).grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text="Cashback rate (e.g., 0.06)").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_rate, width=12).grid(row=1, column=1, sticky="w")

        def ok():
            name = v_name.get().strip()
            if not name:
                messagebox.showerror("Invalid", "Name required.")
                return
            if any(c.name == name for c in self.ledger.cards):
                messagebox.showerror("Invalid", "Card name already exists.")
                return
            rate = safe_float(v_rate.get(), None)
            if rate is None or rate < 0 or rate > 1:
                messagebox.showerror("Invalid", "Rate must be between 0 and 1.")
                return
            self.ledger.cards.append(Card(name, float(rate)))
            dlg.destroy()
            self.refresh_all()

        ttk.Button(frm, text="OK", command=ok).grid(row=2, column=0, pady=(10, 0))
        ttk.Button(frm, text="Cancel", command=dlg.destroy).grid(row=2, column=1, pady=(10, 0), sticky="e")
        dlg.grab_set()
        dlg.transient(self.master)

    def edit_selected_card(self):
        """Edit selected card"""
        sel = self.card_tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select a card row first.")
            return
        iid = sel[0]
        idx = int(iid)
        c = self.ledger.cards[idx]

        dlg = tk.Toplevel(self.master)
        dlg.title("Edit Card")
        dlg.resizable(False, False)
        v_name = tk.StringVar(value=c.name)
        v_rate = tk.StringVar(value=str(c.cashback_rate))
        frm = ttk.Frame(dlg, padding=10)
        frm.grid(row=0, column=0)
        ttk.Label(frm, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_name, width=28).grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text="Cashback rate (0~1)").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_rate, width=12).grid(row=1, column=1, sticky="w")

        def ok():
            name = v_name.get().strip()
            if not name:
                messagebox.showerror("Invalid", "Name required.")
                return
            rate = safe_float(v_rate.get(), None)
            if rate is None or rate < 0 or rate > 1:
                messagebox.showerror("Invalid", "Rate must be between 0 and 1.")
                return
            old_name = c.name
            c.name = name
            c.cashback_rate = float(rate)
            for e in self.ledger.expenses:
                if e.card == old_name:
                    e.card = name
            dlg.destroy()
            self.refresh_all()

        ttk.Button(frm, text="OK", command=ok).grid(row=2, column=0, pady=(10, 0))
        ttk.Button(frm, text="Cancel", command=dlg.destroy).grid(row=2, column=1, pady=(10, 0), sticky="e")
        dlg.grab_set()
        dlg.transient(self.master)

    def remove_selected_card(self):
        """Remove selected card"""
        sel = self.card_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        name = self.ledger.cards[idx].name
        if messagebox.askyesno("Remove card",
                               f"Remove '{name}'? Expenses using it will keep the name (historical)."):
            self.ledger.cards.pop(idx)
            self.refresh_all()

    # ---------- File ops ----------
    def new_ledger(self):
        """Create new ledger"""
        if messagebox.askyesno("New", "Start a new ledger (unsaved changes will be lost)?"):
            self.ledger = get_default_ledger()
            self.ledger_path = None
            self.refresh_all()

    def open_ledger(self):
        """Open ledger from file"""
        fp = filedialog.askopenfilename(
            title="Open ledger JSON",
            filetypes=[("Ledger JSON", "*.json"), ("All files", "*.*")]
        )
        if not fp:
            return
        try:
            with open(fp, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.ledger = dict_to_ledger(d)
            self.ledger_path = fp
            self.apply_discount_var.set(self.ledger.apply_cashback_as_discount)
            self.refresh_all()
        except Exception as ex:
            messagebox.showerror("Open failed", str(ex))

    def save_ledger(self):
        """Save ledger to file"""
        if not self.ledger_path:
            return self.save_as_ledger()
        try:
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(ledger_to_dict(self.ledger), f, ensure_ascii=False, indent=2)
            self.master.title(f"SplitLedger - {os.path.basename(self.ledger_path)}")
        except Exception as ex:
            messagebox.showerror("Save failed", str(ex))

    def save_as_ledger(self):
        """Save ledger to new file"""
        fp = filedialog.asksaveasfilename(
            title="Save ledger JSON",
            defaultextension=".json",
            filetypes=[("Ledger JSON", "*.json")]
        )
        if not fp:
            return
        self.ledger_path = fp
        self.save_ledger()

    def export_excel_dialog(self):
        """Export to Excel file"""
        start, end = self._get_report_dates()
        fp = filedialog.asksaveasfilename(
            title="Export Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not fp:
            return
        try:
            export_excel(self.ledger, fp, start, end)
            messagebox.showinfo("Export", f"Exported: {fp}")
        except Exception as ex:
            messagebox.showerror("Export failed", str(ex))

    # ---------- Refresh ----------
    def refresh_all(self):
        """Refresh all UI elements"""
        self.apply_discount_var.set(self.ledger.apply_cashback_as_discount)
        self.refresh_expenses()
        self.refresh_people()
        self.refresh_cards()
        self.refresh_reports()

    def refresh_expenses(self):
        """Refresh expenses tree view"""
        for iid in self.exp_tree.get_children():
            self.exp_tree.delete(iid)

        people = self.ledger.people
        card_map = build_card_map(self.ledger.cards)

        exps = list(self.ledger.expenses)
        exps.sort(key=lambda e: (e.date, e.payer, e.merchant, e.item))
        for e in exps:
            rate = card_map.get(e.card, 0.0)
            cb = expense_cashback(e, rate)
            base = expense_split_base(e, rate, self.ledger.apply_cashback_as_discount)
            alloc = normalize_allocations(e.allocations, people)
            alloc_txt = ", ".join([f"{p}:{alloc.get(p, 0.0):.2f}" for p in people])
            values = (
                e.date, e.payer, e.card, e.merchant, e.item, 
                f"{e.amount:.2f}", f"{base:.2f}", f"{cb:.2f}", alloc_txt, e.notes
            )
            self.exp_tree.insert("", "end", iid=e.id, values=values)

    def refresh_people(self):
        """Refresh people list"""
        self.people_list.delete(0, tk.END)
        for p in self.ledger.people:
            self.people_list.insert(tk.END, p)

    def refresh_cards(self):
        """Refresh cards tree view"""
        for iid in self.card_tree.get_children():
            self.card_tree.delete(iid)
        for i, c in enumerate(self.ledger.cards):
            self.card_tree.insert("", "end", iid=str(i), values=(c.name, f"{c.cashback_rate:.4f}"))

    def _get_report_dates(self) -> Tuple[Optional[date], Optional[date]]:
        """Parse report date range from inputs"""
        s = self.rep_start.get().strip()
        e = self.rep_end.get().strip()
        start = None
        end = None
        if s:
            try:
                start = parse_date(s)
            except Exception:
                messagebox.showerror("Invalid date", "Start date must be YYYY-MM-DD.")
                return None, None
        if e:
            try:
                end = parse_date(e)
            except Exception:
                messagebox.showerror("Invalid date", "End date must be YYYY-MM-DD.")
                return None, None
        return start, end

    def refresh_reports(self):
        """Refresh reports tab"""
        start, end = self._get_report_dates()
        if start is None and self.rep_start.get().strip():
            return
        if end is None and self.rep_end.get().strip():
            return

        # note
        mode = "Split base = amount*(1-cashback)" if self.ledger.apply_cashback_as_discount else "Split base = amount (cashback tracked separately)"
        filt = f"Date filter: {start.isoformat() if start else '—'} to {end.isoformat() if end else '—'}; {mode}"
        self.report_note.set(filt)

        # summary table
        for iid in self.sum_tree.get_children():
            self.sum_tree.delete(iid)
        summary = compute_summary(self.ledger, start, end)
        for p in self.ledger.people:
            s = summary[p]
            self.sum_tree.insert("", "end", values=(
                p,
                f"{s['paid']:.2f}",
                f"{s['consumed']:.2f}",
                f"{s['net']:.2f}",
                f"{s['cashback']:.2f}",
                f"{s['net_after_cashback']:.2f}",
            ))

        # transfers
        for iid in self.tr_tree.get_children():
            self.tr_tree.delete(iid)
        net = {p: summary[p]["net"] for p in self.ledger.people}
        transfers = compute_transfers(net)
        for a, b, amt in transfers:
            self.tr_tree.insert("", "end", values=(a, b, f"{amt:.2f}"))

    # ---------- CSV Import/Export ----------
    def export_csv_dialog(self):
        """Export current expenses to CSV file"""
        if not self.ledger.expenses:
            messagebox.showinfo("Export CSV", "No expenses to export.")
            return
        
        fp = filedialog.asksaveasfilename(
            title="Export Expenses to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not fp:
            return
        
        try:
            export_expenses_to_csv(self.ledger.expenses, fp)
            messagebox.showinfo("Export CSV", f"Exported {len(self.ledger.expenses)} expenses to:\n{fp}")
        except Exception as ex:
            messagebox.showerror("Export failed", str(ex))

    def import_csv_dialog(self):
        """Import expenses from CSV file"""
        fp = filedialog.askopenfilename(
            title="Import Expenses from CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not fp:
            return
        
        try:
            imported_expenses = import_expenses_from_csv(fp)
            if not imported_expenses:
                messagebox.showinfo("Import CSV", "No expenses found in CSV file.")
                return
            
            # Ask user if they want to append or replace
            choice = messagebox.askyesnocancel(
                "Import CSV",
                f"Found {len(imported_expenses)} expenses in CSV.\n\n"
                "Yes: Append to current expenses\n"
                "No: Replace current expenses\n"
                "Cancel: Cancel import"
            )
            
            if choice is None:  # Cancel
                return
            elif choice:  # Yes - Append
                self.ledger.expenses.extend(imported_expenses)
                messagebox.showinfo("Import CSV", f"Appended {len(imported_expenses)} expenses.")
            else:  # No - Replace
                self.ledger.expenses = imported_expenses
                messagebox.showinfo("Import CSV", f"Replaced with {len(imported_expenses)} expenses.")
            
            # Normalize allocations for all imported expenses
            for e in self.ledger.expenses:
                e.allocations = normalize_allocations(e.allocations, self.ledger.people)
            
            self.refresh_all()
        except Exception as ex:
            messagebox.showerror("Import failed", str(ex))
