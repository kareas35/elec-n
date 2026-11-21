
"""Ed25519 confirmation imza dogrulamasi (salt okunur)."""

import json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_bytes(record):
    if not isinstance(record, dict):
        raise ValueError("Gecersiz confirmation verisi")
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False
    ).encode("utf-8")


def verify_signature(record, signature, public_key):
    """Yalnizca imzayi dogrular; transaction onayi vermez."""
    if not isinstance(signature, bytes) or len(signature) != 64:
        return False
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        return False
    try:
        key = Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, canonical_bytes(record))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def confirmation_payload(operation_id, intent_sha256,
                         step, attempt_sha256, verified_state):
    """Belirli transaction ve adima bagli imzalanacak veri."""
    import re

    if not isinstance(operation_id, str) or not operation_id:
        raise ValueError("Gecersiz operation_id")

    for value in (intent_sha256, attempt_sha256):
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-f]{64}", value
        ):
            raise ValueError("Gecersiz SHA256")

    if type(step) is not int or step < 1:
        raise ValueError("Gecersiz step")

    if verified_state not in (
        "IN_PROGRESS", "COMPLETED", "RECOVERED"
    ):
        raise ValueError("Gecersiz verified_state")

    return {
        "version": 1,
        "purpose": "V38_STEP_CONFIRMATION",
        "operation_id": operation_id,
        "intent_sha256": intent_sha256,
        "step": step,
        "attempt_sha256": attempt_sha256,
        "verified_state": verified_state,
    }


def verify_transaction_confirmation(
    bundle, number, payload, signature, public_key,
    expected_fingerprint=None
):
    """Transaction kanitlariyla imzayi karsilastirir; islem onaylamaz."""
    from pathlib import Path
    from transaction_persistent_outcome import INTENT, digest, read_record
    from transaction_step_journal import step_path, inspect_step_write_result
    from transaction_state import load_state

    blocked = {
        "status": "BLOCKED",
        "transaction_confirmed": False,
        "automatic_retry": False,
    }

    try:
        bundle = Path(bundle)
        intent = read_record(bundle / INTENT)
        attempt = read_record(step_path(bundle, number, "attempt"))
        state = load_state(bundle / "transaction-state.json")

        if not isinstance(intent, dict) or not isinstance(attempt, dict):
            return blocked

        expected = confirmation_payload(
            intent["operation_id"],
            digest(intent),
            number,
            digest(attempt),
            state
        )

        if payload != expected:
            return blocked

        if attempt.get("target_state") != state:
            return blocked

        if inspect_step_write_result(bundle, number)["status"] != "REVIEW_REQUIRED":
            return blocked

        if expected_fingerprint is None:
            return blocked

        trusted_key = trusted_public_key(
            public_key, expected_fingerprint
        )
        if not verify_signature(payload, signature, trusted_key):
            return blocked

        return {
            "status": "SIGNATURE_VALID_REVIEW_REQUIRED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return blocked


def trusted_public_key(configured_key, expected_fingerprint):
    """Disaridan sabitlenmis acik anahtari dogrular."""
    import hashlib
    import hmac

    if not isinstance(configured_key, bytes) or len(configured_key) != 32:
        raise ValueError("Gecersiz Ed25519 acik anahtari")

    fingerprint = hashlib.sha256(configured_key).hexdigest()

    if not isinstance(expected_fingerprint, str) or not hmac.compare_digest(
        fingerprint, expected_fingerprint
    ):
        raise ValueError("Guvenilir anahtar kimligi uyusmuyor")

    return configured_key
