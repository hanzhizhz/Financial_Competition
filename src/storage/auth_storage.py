"""Simple JSON-based account storage for authentication."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

ACCOUNT_FILE = Path("/data/disk2/zhz/票据管理比赛/data/account.json")


def _ensure_data_dir() -> None:
    """Ensure the parent directory for the account file exists."""
    ACCOUNT_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_accounts() -> List[Dict[str, str]]:
    """Load all accounts from the JSON file.
    
    Returns:
        List of account dicts with keys: username, password, user_id
    """
    _ensure_data_dir()
    if not ACCOUNT_FILE.exists():
        return []

    with ACCOUNT_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []

    if isinstance(data, list):
        # Ensure each entry has username/password/user_id keys
        return [
            {
                "username": acc.get("username", ""),
                "password": acc.get("password", ""),
                "user_id": acc.get("user_id", ""),
            }
            for acc in data
            if isinstance(acc, dict)
        ]

    return []


def save_accounts(accounts: List[Dict[str, str]]) -> None:
    """Persist accounts to the JSON file."""
    _ensure_data_dir()
    with ACCOUNT_FILE.open("w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def find_account(username: str) -> Optional[Dict[str, str]]:
    """Find an existing account by username."""
    username = username.strip()
    if not username:
        return None

    for acc in load_accounts():
        if acc.get("username") == username:
            return acc
    return None


def create_account(username: str, password: str) -> Dict[str, str]:
    """Create a new account if the username is not taken.
    
    Args:
        username: Account username
        password: Account password (plaintext)
        
    Returns:
        New account dict with username, password, user_id
        
    Raises:
        ValueError: If username is empty or already exists
    """
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")

    accounts = load_accounts()
    if any(acc.get("username") == username for acc in accounts):
        raise ValueError("Username already exists")

    # Generate user_id from username
    user_id = f"user_{username}"
    
    new_account = {
        "username": username,
        "password": password,
        "user_id": user_id,
    }
    accounts.append(new_account)
    save_accounts(accounts)
    return new_account


def ensure_demo_account() -> None:
    """Ensure the demo account (123/123) exists."""
    accounts = load_accounts()

    if not any(acc.get("username") == "123" for acc in accounts):
        accounts.append({
            "username": "123",
            "password": "123",
            "user_id": "user_123"
        })
        save_accounts(accounts)


# Ensure the data directory and demo account exist when module is imported.
ensure_demo_account()


