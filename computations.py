"""
Business logic and computations for SplitLedger
"""
from __future__ import annotations
from datetime import date
from typing import Dict, List, Optional, Tuple

from models import Card, Expense, Ledger
from utils import parse_date


def normalize_allocations(alloc: Dict[str, float], people: List[str]) -> Dict[str, float]:
    """Normalize allocations so they sum to 1.0"""
    out = {p: float(alloc.get(p, 0.0)) for p in people}
    s = sum(max(0.0, v) for v in out.values())
    if s <= 0:
        # default equal split
        n = max(1, len(people))
        return {p: 1.0 / n for p in people}
    return {p: max(0.0, out[p]) / s for p in people}


def build_card_map(cards: List[Card]) -> Dict[str, float]:
    """Build mapping of card name to cashback rate"""
    return {c.name: float(c.cashback_rate) for c in cards}


def expense_split_base(e: Expense, card_rate: float, apply_discount: bool) -> float:
    """Calculate split base amount for expense"""
    return float(e.amount) * (1.0 - card_rate) if apply_discount else float(e.amount)


def expense_cashback(e: Expense, card_rate: float) -> float:
    """Calculate cashback amount for expense"""
    return float(e.amount) * card_rate


def filter_expenses_by_date(
    expenses: List[Expense], 
    start: Optional[date], 
    end: Optional[date]
) -> List[Expense]:
    """Filter expenses by date range"""
    out = []
    for e in expenses:
        ed = parse_date(e.date)
        if start and ed < start:
            continue
        if end and ed > end:
            continue
        out.append(e)
    return out


def compute_summary(
    ledger: Ledger, 
    start: Optional[date] = None, 
    end: Optional[date] = None
) -> Dict[str, dict]:
    """
    Compute summary statistics for each person.
    Returns dict mapping person -> {paid, consumed, net, cashback, net_after_cashback}
    """
    people = ledger.people
    card_rate = build_card_map(ledger.cards)
    exps = filter_expenses_by_date(ledger.expenses, start, end)

    paid = {p: 0.0 for p in people}
    consumed = {p: 0.0 for p in people}
    cashback = {p: 0.0 for p in people}

    for e in exps:
        if e.payer in paid:
            paid[e.payer] += float(e.amount)
        rate = card_rate.get(e.card, 0.0)
        base = expense_split_base(e, rate, ledger.apply_cashback_as_discount)
        # allocations may miss new people names; normalize
        alloc = normalize_allocations(e.allocations, people)
        for p in people:
            consumed[p] += base * alloc.get(p, 0.0)
        if e.payer in cashback:
            cashback[e.payer] += expense_cashback(e, rate)

    net = {p: paid[p] - consumed[p] for p in people}  # positive -> should receive; negative -> should pay
    net_after_cashback = {p: net[p] + cashback[p] for p in people}
    
    return {
        p: {
            "paid": paid[p],
            "consumed": consumed[p],
            "net": net[p],
            "cashback": cashback[p],
            "net_after_cashback": net_after_cashback[p],
        } for p in people
    }


def compute_transfers(net: Dict[str, float], eps: float = 1e-6) -> List[Tuple[str, str, float]]:
    """
    Compute transfers to settle debts.
    Greedy settlement: debtors pay creditors. net>0 creditor; net<0 debtor.
    Returns list of (debtor, creditor, amount) tuples.
    """
    creditors = [(p, v) for p, v in net.items() if v > eps]
    debtors = [(p, -v) for p, v in net.items() if v < -eps]
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)
    
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        dname, damt = debtors[i]
        cname, camt = creditors[j]
        x = min(damt, camt)
        if x > eps:
            transfers.append((dname, cname, x))
        damt -= x
        camt -= x
        if damt <= eps:
            i += 1
        else:
            debtors[i] = (dname, damt)
        if camt <= eps:
            j += 1
        else:
            creditors[j] = (cname, camt)
    
    return transfers
