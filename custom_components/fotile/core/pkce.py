"""PKCE (RFC 7636) helpers, stdlib only."""
from __future__ import annotations

import base64
import hashlib
import secrets

__all__ = [
    "CODE_VERIFIER_MAX_LENGTH",
    "CODE_VERIFIER_MIN_LENGTH",
    "compute_code_challenge",
    "generate_code_verifier",
]

CODE_VERIFIER_MIN_LENGTH = 43
CODE_VERIFIER_MAX_LENGTH = 128
DEFAULT_CODE_VERIFIER_LENGTH = 128


def generate_code_verifier(length: int = DEFAULT_CODE_VERIFIER_LENGTH) -> str:
    """Generate a RFC 7636 §4.1 code_verifier (43..128 chars)."""
    if not CODE_VERIFIER_MIN_LENGTH <= length <= CODE_VERIFIER_MAX_LENGTH:
        raise ValueError(
            "code_verifier length must be "
            f"{CODE_VERIFIER_MIN_LENGTH}-{CODE_VERIFIER_MAX_LENGTH}, got {length}"
        )
    try:
        from homeassistant.helpers.oauth2 import (  # noqa: PLC0415
            generate_code_verifier as _ha_generate,
        )
    except ImportError:
        return secrets.token_urlsafe(96)[:length]
    return _ha_generate(length)


def compute_code_challenge(code_verifier: str) -> str:
    """S256 challenge: BASE64URL(SHA256(ASCII(verifier))), no padding."""
    if not CODE_VERIFIER_MIN_LENGTH <= len(code_verifier) <= CODE_VERIFIER_MAX_LENGTH:
        raise ValueError(
            "code_verifier must be "
            f"{CODE_VERIFIER_MIN_LENGTH}-{CODE_VERIFIER_MAX_LENGTH} chars, "
            f"got {len(code_verifier)}"
        )
    try:
        from homeassistant.helpers.oauth2 import (  # noqa: PLC0415
            compute_code_challenge as _ha_compute,
        )
    except ImportError:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return _ha_compute(code_verifier)


def compute_code_challenge_s256_raw(code_verifier: str) -> str:
    """Pure-stdlib S256 with no length check. For RFC test-vector comparison."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
