"""
Configuration and data loading/saving for SplitLedger
"""
from __future__ import annotations
import json
import os
from typing import List
from dataclasses import asdict

from models import Card, Expense, Ledger
from utils import app_dir


def load_people(path: str) -> List[str]:
    """Load people list from JSON file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get("people", []))
    except FileNotFoundError:
        return []


def load_cards(path: str) -> List[Card]:
    """Load cards list from JSON file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Card(**c) for c in data.get("cards", [])]
    except FileNotFoundError:
        return []


def get_default_ledger() -> Ledger:
    """Create default ledger with loaded people and cards"""
    base = app_dir()
    people = load_people(os.path.join(base, "people.json"))
    cards = load_cards(os.path.join(base, "cards.json"))
    
    if not people:
        people = ["DJZ"]  # fallback
    if not cards:
        cards = [Card("Default 0%", 0.0)]
    
    return Ledger(
        people=people,
        cards=cards,
        expenses=[],
        apply_cashback_as_discount=True
    )


def ledger_to_dict(ledger: Ledger) -> dict:
    """Convert Ledger object to dictionary for JSON serialization"""
    return {
        "version": ledger.version,
        "people": ledger.people,
        "apply_cashback_as_discount": ledger.apply_cashback_as_discount,
        "cards": [asdict(c) for c in ledger.cards],
        "expenses": [asdict(e) for e in ledger.expenses],
    }


def dict_to_ledger(d: dict) -> Ledger:
    """Convert dictionary from JSON to Ledger object"""
    cards = [Card(**c) for c in d.get("cards", [])]
    exps = [Expense(**e) for e in d.get("expenses", [])]
    
    return Ledger(
        version=d.get("version", 1),
        people=list(d.get("people", [])),
        cards=cards,
        expenses=exps,
        apply_cashback_as_discount=bool(d.get("apply_cashback_as_discount", True)),
    )
