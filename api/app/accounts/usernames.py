"""Canonical local username handling."""

import unicodedata


def normalise_username(value: str) -> str:
    """Return the single representation used for lookup and uniqueness."""
    normalised = unicodedata.normalize("NFKC", value).strip().casefold()
    if not normalised:
        raise ValueError("Username cannot be empty")
    return normalised
