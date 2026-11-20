#!/usr/bin/env python3
"""V3.8 - Outcome + HTML/CSV butunluk kontrolu.

Salt okunur degerlendirme.
Nihai CONFIRMED, retry, rollback veya silme YOK.
"""
from pathlib import Path

from transaction_outcome_verifier import assess
from transaction_recovery_validator import verify_recovered


def evaluate(bundle, live_dir, csv_path):
    bundle = Path(bundle)
    live_dir = Path(live_dir)
    csv_path = Path(csv_path)

    blocked = {
        "status": "BLOCKED",
        "transaction_confirmed": False,
        "automatic_retry": False,
        "integrity_verified": False,
    }

    # Once outcome degerlendirilir.
    try:
        outcome = assess(bundle)
        if outcome["status"] != "REVIEW_REQUIRED":
            return {
                **blocked,
                "reason": "OUTCOME_NOT_READY",
            }

        # Mevcut gercek dogrulayici kullanilir.
        if verify_recovered(bundle, live_dir, csv_path) is not True:
            return {
                **blocked,
                "reason": "INTEGRITY_NOT_VERIFIED",
            }

    except Exception:
        # Bu prototip beklenmeyen hatada da fail-closed.
        # Uretimde kontrollu hata gunlugu gereklidir.
        return {
            **blocked,
            "reason": "VERIFICATION_FAILED",
        }

    return {
        "status": "REVIEW_REQUIRED",
        "transaction_confirmed": False,
        "automatic_retry": False,
        "integrity_verified": True,
        "reason": "INTEGRITY_OK_DURABILITY_UNPROVEN",
    }
