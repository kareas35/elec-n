
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
