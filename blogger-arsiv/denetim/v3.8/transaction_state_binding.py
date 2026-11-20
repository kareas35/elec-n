#!/usr/bin/env python3
"""V3.8 - Salt okunur transaction baglanti prototipi.

Baglanti tutarliligi, islem gecmisi veya durability kaniti degildir.
"""
import hashlib
from pathlib import Path

from transaction_integrity_gate import evaluate
from transaction_persistent_outcome import (
    INTENT, read_record, digest
)
from transaction_state import ALLOWED, load_state

BINDING = "transaction-state-binding.json"


def sha256_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Eksik veya guvensiz dosya")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_binding(
    bundle, live_dir, csv_path,
    operation_id, expected, target, manifest_sha256
):
    blocked = {
        "status": "BLOCKED",
        "binding_verified": False,
        "transaction_confirmed": False,
        "automatic_retry": False,
    }

    try:
        bundle = Path(bundle)

        # Bagimsiz beklenen degerler cagiran tarafindan saglanmali.
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("Gecersiz operation_id")

        if (
            expected not in ALLOWED
            or target not in ALLOWED[expected]
        ):
            raise ValueError("Gecersiz state gecisi")

        if (
            not isinstance(manifest_sha256, str)
            or len(manifest_sha256) != 64
            or any(c not in "0123456789abcdef"
                   for c in manifest_sha256)
        ):
            raise ValueError("Gecersiz manifest hash")

        integrity = evaluate(bundle, live_dir, csv_path)

        if (
            integrity["status"] != "REVIEW_REQUIRED"
            or integrity["integrity_verified"] is not True
        ):
            raise ValueError("Dosya butunlugu dogrulanamadi")

        state_path = bundle / "transaction-state.json"
        manifest_path = bundle / "transaction.json"

        state_hash = sha256_file(state_path)
        actual_manifest = sha256_file(manifest_path)

        if actual_manifest != manifest_sha256:
            raise ValueError("Manifest uyusmazligi")

        if load_state(state_path) != target:
            raise ValueError("State hedefi uyusmuyor")

        intent = read_record(bundle / INTENT)

        if (
            not isinstance(intent, dict)
            or intent.get("operation_id") != operation_id
        ):
            raise ValueError("Intent kimligi uyusmuyor")

        record = read_record(bundle / BINDING)

        expected_record = {
            "version": 1,
            "operation_id": operation_id,
            "expected_state": expected,
            "target_state": target,
            "manifest_sha256": actual_manifest,
            "state_sha256": state_hash,
            "intent_sha256": digest(intent),
        }

        if record != expected_record:
            raise ValueError("Baglanti kaydi uyusmuyor")

    except (OSError, ValueError, TypeError, KeyError):
        return {**blocked, "reason": "BINDING_NOT_VERIFIED"}

    return {
        "status": "REVIEW_REQUIRED",
        "binding_verified": True,
        "transaction_confirmed": False,
        "automatic_retry": False,
        "reason": "BINDING_MATCH_NOT_EXECUTION_PROOF",
    }
