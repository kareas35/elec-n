#!/usr/bin/env python3
"""V3.8 - State yazim sonucu siniflandirma prototipi.

Dosya yazmaz. Kalicilik garantisi vermez.
"""
from pathlib import Path

from transaction_state import load_state


CONFIRMED = "CONFIRMED"
NO_VISIBLE_CHANGE = "NO_VISIBLE_CHANGE"
DURABILITY_UNKNOWN = "DURABILITY_UNKNOWN"


def inspect_failed_write(state_path, previous, target):
    """Hata sonrasi state'i yalnizca okuyarak siniflandir."""
    path = Path(state_path)

    try:
        if path.is_symlink():
            raise ValueError("Sembolik state yolu")

        if not path.exists():
            observed = None
        else:
            observed = load_state(path)
    except (OSError, ValueError, KeyError, TypeError):
        observed = None
        return {
            "status": DURABILITY_UNKNOWN,
            "observed": observed,
            "automatic_retry": False,
        }

    if observed == previous and previous != target:
        return {
            "status": NO_VISIBLE_CHANGE,
            "observed": observed,
            "automatic_retry": False,
        }

    return {
        "status": DURABILITY_UNKNOWN,
        "observed": observed,
        "automatic_retry": False,
    }


class WriteOutcomeSession:
    """Belirsiz yazim sonrasi ayni oturumda tekrar denemeyi engeller."""

    def __init__(self):
        self._blocked = False

    def execute(self, action, state_path, previous, target):
        if self._blocked:
            raise RuntimeError(
                "DURABILITY_UNKNOWN: Otomatik tekrar yasak"
            )

        try:
            result = action()
        except OSError:
            outcome = inspect_failed_write(
                state_path, previous, target
            )
            if outcome["status"] == DURABILITY_UNKNOWN:
                self._blocked = True
            return outcome

        return {
            "status": CONFIRMED,
            "observed": target,
            "automatic_retry": False,
            "result": result,
        }

    @property
    def blocked(self):
        return self._blocked
