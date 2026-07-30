"""Argon2id password hashing boundary."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Return an Argon2id hash suitable for persistent storage."""
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password without exposing verification failures to callers."""
    try:
        return password_hasher.verify(password_hash, password)
    except InvalidHashError, VerificationError:
        return False


def password_hash_needs_rehash(password_hash: str) -> bool:
    """Identify hashes that should be upgraded after successful authentication."""
    return password_hasher.check_needs_rehash(password_hash)
