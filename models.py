"""
Data models for SplitLedger application
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Card:
    """Credit card with cashback rate"""
    name: str
    cashback_rate: float  # e.g., 0.05 for 5%


@dataclass
class Expense:
    """Single expense transaction"""
    id: str
    date: str  # YYYY-MM-DD
    payer: str
    card: str  # card name
    merchant: str
    item: str
    amount: float  # original amount charged
    allocations: Dict[str, float]  # person -> share (sum to 1)
    notes: str = ""


@dataclass
class Ledger:
    """Complete ledger containing all data"""
    people: List[str]
    cards: List[Card]
    expenses: List[Expense]
    apply_cashback_as_discount: bool = True  # if True, split base = amount*(1-rate)
    version: int = 1
