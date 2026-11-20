#!/usr/bin/env python3
"""V3.8 - Salt okunur outcome guvenlik degerlendirmesi.

Kayit eslesmesi disk kaliciligi veya gercek transaction
butunlugu kaniti sayilmaz. Otomatik retry YOK.
"""
from transaction_persistent_outcome import inspect

BLOCKED = "BLOCKED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


def assess(bundle):
    try:
        legacy_result = inspect(bundle)
    except Exception:
        return {
            "status": BLOCKED,
            "automatic_retry": False,
            "transaction_confirmed": False,
            "reason": "INSPECTION_FAILED",
        }

    if legacy_result != "REVIEW_REQUIRED":
        return {
            "status": BLOCKED,
            "automatic_retry": False,
            "transaction_confirmed": False,
            "reason": "MISSING_OR_INVALID_EVIDENCE",
        }

    return {
        "status": REVIEW_REQUIRED,
        "automatic_retry": False,
        "transaction_confirmed": False,
        "reason": "RECORD_MATCH_NOT_DURABILITY_PROOF",
    }
