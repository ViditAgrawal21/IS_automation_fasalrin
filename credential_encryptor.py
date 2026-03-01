"""
Encryption utility for storing passwords securely using Fernet symmetric encryption.
Key is generated once and stored locally. Passwords are never stored in plaintext.
"""

from cryptography.fernet import Fernet
import os
from path_helper import get_app_dir

KEY_FILE = os.path.join(get_app_dir(), "secret.key")


def _ensure_key():
    """Generate encryption key if it doesn't exist."""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)


def _load_key() -> bytes:
    """Load the encryption key from file."""
    _ensure_key()
    with open(KEY_FILE, "rb") as f:
        return f.read()


def encrypt_password(password: str) -> str:
    """Encrypt a plaintext password and return the encrypted string."""
    f = Fernet(_load_key())
    return f.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt an encrypted password and return the plaintext string."""
    f = Fernet(_load_key())
    return f.decrypt(encrypted_password.encode()).decode()
