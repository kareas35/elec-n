"""V3.8 - Cok asamali transaction kayit altyapisi.

State degistirmez, retry veya rollback yapmaz.
"""
from pathlib import Path
from contextvars import ContextVar
from contextlib import contextmanager

_step_write_scope = ContextVar("v38_step_write_scope", default=False)


@contextmanager
def _authorized_step_write():
    token = _step_write_scope.set(True)
    try:
        yield
    finally:
        _step_write_scope.reset(token)



from transaction_journal import atomic_json_write
from transaction_persistent_outcome import read_record


def step_path(bundle, number, kind):
    if type(number) is not int or number < 1:
        raise ValueError("Gecersiz adim")
    if kind not in ("attempt", "confirmation", "write-result"):
        raise ValueError("Gecersiz kayit tipi")
    return Path(bundle) / f"transaction-step-{number:04d}-{kind}.json"


def write_attempt(bundle, number, record):
    if not _step_write_scope.get():
        raise RuntimeError("Yetkisiz step kaydi yazimi")
    if number != 1:
        raise RuntimeError(
            "Cok asamali islem kilitli: guvenilir confirmation gerekli"
        )
    from transaction_persistent_outcome import INTENT, digest
    intent = read_record(Path(bundle) / INTENT)
    if not isinstance(intent, dict) or not isinstance(record, dict):
        raise ValueError("Gecersiz islem kaydi")
    if intent.get("version") != 1 or intent.get("status") != "IN_FLIGHT":
        raise ValueError("Gecersiz INTENT")
    if record.get("operation_id") != intent.get("operation_id") or (
        record.get("intent_sha256") != digest(intent)
    ):
        raise ValueError("INTENT eslesmiyor")
    if number > 1:
        prior_record = read_record(step_path(bundle, number - 1, "attempt"))
        if prior_record.get("operation_id") != intent["operation_id"] or (
            prior_record.get("intent_sha256") != digest(intent)
        ):
            raise ValueError("Onceki ATTEMPT farkli isleme ait")
    if number > 1:
        previous = step_path(bundle, number - 1, "confirmation")
        confirmed = read_record(previous)
        prior = read_record(step_path(bundle, number - 1, "attempt"))

        from transaction_persistent_outcome import digest
        from transaction_state import load_state

        state = load_state(
            Path(bundle) / "transaction-state.json"
        )

        if not isinstance(confirmed, dict) or not isinstance(prior, dict):
            raise RuntimeError("Gecersiz adim kaniti")

        if confirmed != {
            "version": 1,
            "status": "VERIFIED",
            "step": number - 1,
            "attempt_sha256": digest(prior),
            "verified_state": prior.get("target_state"),
        }:
            raise RuntimeError("Onceki adim kaniti uyusmuyor")

        if state != prior.get("target_state"):
            raise RuntimeError("Onceki adimin state sonucu uyusmuyor")

        result_check = inspect_step_write_result(bundle, number - 1)
        if result_check["status"] != "REVIEW_REQUIRED":
            raise RuntimeError("Onceki adimin write-result kaniti gecersiz")

        if not isinstance(record, dict) or (
            record.get("expected_state") != state
        ):
            raise RuntimeError("Yeni adim baslangici uyusmuyor")

    path = step_path(bundle, number, "attempt")
    atomic_json_write(path, record)
    return path


def inspect_step_confirmation(bundle, number):
    """Kalici kanitlari inceler; tek basina onay vermez."""
    from transaction_persistent_outcome import INTENT, digest
    from transaction_state import load_state

    bundle = Path(bundle)
    try:
        intent = read_record(bundle / INTENT)
        attempt = read_record(step_path(bundle, number, "attempt"))
        state = load_state(bundle / "transaction-state.json")

        valid = (
            isinstance(intent, dict)
            and intent.get("version") == 1
            and intent.get("status") == "IN_FLIGHT"
            and isinstance(attempt, dict)
            and attempt.get("operation_id") == intent.get("operation_id")
            and attempt.get("intent_sha256") == digest(intent)
            and attempt.get("target_state") == state
        )
        return {
            "status": "REVIEW_REQUIRED" if valid else "BLOCKED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {
            "status": "BLOCKED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }


def write_step_result(bundle, number, record):
    """Yetkili kapsamda, onay vermeyen yazma sonucu kaydi."""
    if not _step_write_scope.get():
        raise RuntimeError("Yetkisiz step sonucu yazimi")

    if not isinstance(record, dict):
        raise ValueError("Gecersiz sonuc kaydi")

    from transaction_persistent_outcome import INTENT, digest
    from transaction_state import load_state

    bundle = Path(bundle)
    intent = read_record(bundle / INTENT)
    attempt = read_record(step_path(bundle, number, "attempt"))
    state = load_state(bundle / "transaction-state.json")

    if not isinstance(intent, dict) or not isinstance(attempt, dict):
        raise ValueError("Eksik islem kaniti")

    if attempt.get("operation_id") != intent.get("operation_id"):
        raise ValueError("Islem kimligi uyusmuyor")

    if attempt.get("intent_sha256") != digest(intent):
        raise ValueError("INTENT ozeti uyusmuyor")

    expected = {
        "version": 1,
        "status": "WRITE_RETURNED",
        "step": number,
        "attempt_sha256": digest(attempt),
        "observed_state": state,
        "transaction_confirmed": False,
        "automatic_retry": False,
    }
    if record != expected or state != attempt.get("target_state"):
        raise ValueError("Yazma sonucu kaniti uyusmuyor")

    path = step_path(bundle, number, "write-result")
    atomic_json_write(path, expected)
    return path


def inspect_step_write_result(bundle, number):
    """Kalici yazma kanitini kontrol eder; confirmation vermez."""
    from transaction_persistent_outcome import INTENT, digest
    from transaction_state import load_state

    bundle = Path(bundle)
    blocked = {
        "status": "BLOCKED",
        "transaction_confirmed": False,
        "automatic_retry": False,
    }

    try:
        intent = read_record(bundle / INTENT)
        attempt = read_record(step_path(bundle, number, "attempt"))
        result = read_record(step_path(bundle, number, "write-result"))
        state = load_state(bundle / "transaction-state.json")

        if not isinstance(intent, dict) or not isinstance(attempt, dict):
            return blocked

        if intent.get("version") != 1 or intent.get("status") != "IN_FLIGHT":
            return blocked

        if attempt.get("operation_id") != intent.get("operation_id"):
            return blocked

        if attempt.get("intent_sha256") != digest(intent):
            return blocked

        expected = {
            "version": 1,
            "status": "WRITE_RETURNED",
            "step": number,
            "attempt_sha256": digest(attempt),
            "observed_state": state,
            "transaction_confirmed": False,
            "automatic_retry": False,
        }

        if result != expected or state != attempt.get("target_state"):
            return blocked

        return {
            "status": "REVIEW_REQUIRED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return blocked
