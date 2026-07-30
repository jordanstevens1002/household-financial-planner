"""One-way storage for high-entropy session and reset tokens."""

import hashlib


def hash_token(token: str) -> str:
    """Return a fixed-length SHA-256 digest; raw tokens must not be persisted."""
    return hashlib.sha256(token.encode()).hexdigest()
