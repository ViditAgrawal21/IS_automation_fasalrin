"""
Profile management for IS Claim Automation.

Each profile contains:
  - Login credentials (password encrypted via Fernet)
  - Claim settings (financial year, claim type, claim status, submission type)

Profiles are stored as JSON files in the /profiles directory.
"""

import json
import os
from credential_encryptor import encrypt_password, decrypt_password
from path_helper import get_app_dir

PROFILE_DIR = os.path.join(get_app_dir(), "profiles")

# Default profile template
PROFILE_TEMPLATE = {
    # Login Credentials
    "username": "",
    "password": "",

    # Claim Settings
    "financial_year": "",
    "claim_type": "",           # IS or PRI
    "claim_status": "",         # PENDING, DRAFT, etc.
    "submission_type": "",      # COMPLETE or PARTIAL
}


def save_profile(profile_name: str, data: dict):
    """Save a profile with encrypted password."""
    os.makedirs(PROFILE_DIR, exist_ok=True)

    save_data = data.copy()
    if save_data.get("password"):
        save_data["password"] = encrypt_password(save_data["password"])

    filepath = os.path.join(PROFILE_DIR, f"{profile_name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=4, ensure_ascii=False)


def load_profile(profile_name: str) -> dict:
    """Load a profile and decrypt its password."""
    filepath = os.path.join(PROFILE_DIR, f"{profile_name}.json")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("password"):
        try:
            data["password"] = decrypt_password(data["password"])
        except Exception:
            pass  # Password may already be decrypted during edit
    return data


def delete_profile(profile_name: str):
    """Delete a profile and its session file."""
    filepath = os.path.join(PROFILE_DIR, f"{profile_name}.json")
    session_path = os.path.join(PROFILE_DIR, f"{profile_name}_session.json")

    if os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(session_path):
        os.remove(session_path)


def list_profiles() -> list:
    """List all available profile names."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    return [
        f.replace(".json", "")
        for f in os.listdir(PROFILE_DIR)
        if f.endswith(".json") and not f.endswith("_session.json")
    ]


def profile_exists(profile_name: str) -> bool:
    """Check if a profile exists."""
    filepath = os.path.join(PROFILE_DIR, f"{profile_name}.json")
    return os.path.exists(filepath)
