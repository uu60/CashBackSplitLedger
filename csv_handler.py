"""
CSV export and import functionality for SplitLedger
"""
from __future__ import annotations
import csv
from typing import List
from datetime import datetime

from models import Expense


def export_expenses_to_csv(expenses: List[Expense], filepath: str) -> None:
    """
    Export expenses list to CSV file
    CSV columns: id, date, payer, card, merchant, item, amount, allocations_json, notes
    """
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['id', 'date', 'payer', 'card', 'merchant', 'item', 'amount', 'allocations', 'notes'])
        
        # Write data
        for e in expenses:
            # Convert allocations dict to string representation
            alloc_str = ';'.join([f"{k}:{v}" for k, v in e.allocations.items()])
            writer.writerow([
                e.id,
                e.date,
                e.payer,
                e.card,
                e.merchant,
                e.item,
                e.amount,
                alloc_str,
                e.notes
            ])


def import_expenses_from_csv(filepath: str) -> List[Expense]:
    """
    Import expenses list from CSV file
    Returns list of Expense objects
    """
    expenses = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Parse allocations from string
            allocations = {}
            if row['allocations']:
                for pair in row['allocations'].split(';'):
                    if ':' in pair:
                        k, v = pair.split(':', 1)
                        allocations[k.strip()] = float(v.strip())
            
            expense = Expense(
                id=row['id'],
                date=row['date'],
                payer=row['payer'],
                card=row['card'],
                merchant=row['merchant'],
                item=row['item'],
                amount=float(row['amount']),
                allocations=allocations,
                notes=row.get('notes', '')
            )
            expenses.append(expense)
    
    return expenses
