"""ULID generation (Crockford base32, 26 chars). No external dependency."""

from __future__ import annotations

import os
import re
import threading
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

_lock = threading.Lock()
_last_ms = -1
_last_rand = 0


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(out))


def new_id() -> str:
    """Return a new monotonic ULID string (sortable by creation time)."""
    global _last_ms, _last_rand
    with _lock:
        ms = int(time.time() * 1000)
        if ms == _last_ms:
            _last_rand = (_last_rand + 1) & ((1 << 80) - 1)
        else:
            _last_ms = ms
            _last_rand = int.from_bytes(os.urandom(10), "big")
        return _encode(ms, 10) + _encode(_last_rand, 16)


def is_id(value: str) -> bool:
    return bool(_ULID_RE.match(value))
