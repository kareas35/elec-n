
"""V3.8 bagimsiz, salt okunur confirmation denetimi."""

from pathlib import Path
from transaction_confirmation_signature import verify_transaction_confirmation


def inspect_signed_step(
    bundle, number, payload, signature,
    trusted_key, expected_fingerprint
):
    """Imza ve transaction kanitlarini kontrol eder; yazma yapmaz."""
    result = verify_transaction_confirmation(
        Path(bundle),
        number,
        payload,
        signature,
        trusted_key,
        expected_fingerprint=expected_fingerprint,
    )

    if result["status"] != "SIGNATURE_VALID_REVIEW_REQUIRED":
        return {
            "status": "BLOCKED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }

    return {
        "status": "INDEPENDENT_REVIEW_REQUIRED",
        "transaction_confirmed": False,
        "automatic_retry": False,
    }


def collect_step_evidence(bundle, number):
    """Transaction kanitlarini salt okunur olarak toplar."""
    from transaction_persistent_outcome import INTENT, read_record
    from transaction_step_journal import (
        step_path, inspect_step_write_result
    )
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
        write_result = read_record(
            step_path(bundle, number, "write-result")
        )
        state = load_state(bundle / "transaction-state.json")

        if inspect_step_write_result(bundle, number)["status"] != "REVIEW_REQUIRED":
            return blocked

        return {
            "status": "EVIDENCE_COLLECTED_REVIEW_REQUIRED",
            "intent": intent,
            "attempt": attempt,
            "write_result": write_result,
            "state": state,
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return blocked


def inspect_transferred_evidence(data, expected_fingerprint):
    """Yalnizca aktarilan kanitlari inceler; diskten okuma yapmaz."""
    from transaction_persistent_outcome import digest
    from transaction_confirmation_signature import (
        confirmation_payload, trusted_public_key, verify_signature
    )

    blocked = {
        "status": "BLOCKED",
        "transaction_confirmed": False,
        "automatic_retry": False,
    }

    try:
        i = data["intent"]
        a = data["attempt"]
        w = data["write_result"]
        state = data["state"]
        number = data["payload"]["step"]

        if type(number) is not int or number != 1:
            return blocked

        if i.get("version") != 1 or i.get("status") != "IN_FLIGHT":
            return blocked
        if a.get("operation_id") != i.get("operation_id"):
            return blocked
        if a.get("intent_sha256") != digest(i):
            return blocked
        if a.get("target_state") != state:
            return blocked

        if w != {
            "version": 1,
            "status": "WRITE_RETURNED",
            "step": number,
            "attempt_sha256": digest(a),
            "observed_state": state,
            "transaction_confirmed": False,
            "automatic_retry": False,
        }:
            return blocked

        expected = confirmation_payload(
            i["operation_id"], digest(i),
            number, digest(a), state
        )
        if data["payload"] != expected:
            return blocked

        public = trusted_public_key(
            bytes.fromhex(data["public"]),
            expected_fingerprint
        )
        if not verify_signature(
            expected, bytes.fromhex(data["signature"]), public
        ):
            return blocked

        return {
            "status": "TRANSFERRED_EVIDENCE_REVIEW_REQUIRED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
    except (KeyError, ValueError, TypeError, AttributeError):
        return blocked
