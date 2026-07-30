"""One-way storage for high-entropy session and reset tokens."""

import hashlib
import secrets


def hash_token(token: str) -> str:
    """Return a fixed-length SHA-256 digest; raw tokens must not be persisted."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    """Return a URL-safe high-entropy token suitable for browser sessions."""
    return secrets.token_urlsafe(32)
