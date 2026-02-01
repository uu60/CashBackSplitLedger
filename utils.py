"""
Utility functions for SplitLedger application
"""
from __future__ import annotations
import os
from datetime import date, datetime


def today_str() -> str:
    """Get today's date as ISO string"""
    return date.today().isoformat()


def parse_date(s: str) -> date:
    """Parse YYYY-MM-DD date string"""
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def safe_float(x: str, default: float = 0.0) -> float:
    """Convert string to float safely, returning default on error"""
    try:
        return float(x)
    except Exception:
        return default


def app_dir() -> str:
    """
    Get application data directory: ~/Library/Application Support/SplitLedger
    Creates directory if it doesn't exist.
    """
    base = os.path.expanduser("~/Library/Application Support")
    path = os.path.join(base, "SplitLedger")
    os.makedirs(path, exist_ok=True)
    return path
