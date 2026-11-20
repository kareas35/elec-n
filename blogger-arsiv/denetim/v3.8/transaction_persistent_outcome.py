#!/usr/bin/env python3
"""V3.8 - Kalici islem sonucu prototipi.

Gercek transaction API'ye bagli degildir.
Otomatik retry, rollback veya dosya silme yapmaz.
"""
import hashlib
import json
from pathlib import Path

from transaction_journal import atomic_json_write
from transaction_lock import transaction_lock

INTENT = "transaction-outcome-intent.json"
RESULT = "transaction-outcome-result.json"


def digest(data):
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def read_record(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Eksik veya guvensiz kayit")
    return json.loads(path.read_text(encoding="utf-8"))


def inspect(bundle):
    """Eksik veya bozuk kanitta varsayilan BLOCKED."""
    bundle = Path(bundle)
    intent_path = bundle / INTENT
    result_path = bundle / RESULT

    if not intent_path.exists() and not intent_path.is_symlink():
        return "BLOCKED"

    try:
        intent = read_record(intent_path)
        if (
            not isinstance(intent, dict)
            or intent.get("version") != 1
            or intent.get("status") != "IN_FLIGHT"
            or not isinstance(intent.get("operation_id"), str)
            or not intent["operation_id"]
        ):
            return "BLOCKED"

        if not result_path.exists() and not result_path.is_symlink():
            return "BLOCKED"

        result = read_record(result_path)
        expected = {
            "version": 1,
            "status": "CONFIRMED",
            "operation_id": intent["operation_id"],
            "intent_sha256": digest(intent),
        }

        if result != expected:
            return "BLOCKED"

        return "REVIEW_REQUIRED"
    except (OSError, ValueError, TypeError, KeyError):
        return "BLOCKED"


def begin(bundle, operation_id):
    """Intent'i yazmadan islem baslatildigini kabul etme."""
    bundle = Path(bundle)
    if (
        not bundle.is_dir()
        or bundle.is_symlink()
        or not isinstance(operation_id, str)
        or not operation_id
    ):
        raise ValueError("Gecersiz islem")

    lock = bundle.parent / "transaction.lock"

    with transaction_lock(lock):
        if (
            (bundle / INTENT).exists()
            or (bundle / INTENT).is_symlink()
            or (bundle / RESULT).exists()
            or (bundle / RESULT).is_symlink()
        ):
            raise RuntimeError("Islem kaydi zaten mevcut")

        intent = {
            "version": 1,
            "status": "IN_FLIGHT",
            "operation_id": operation_id,
        }
        atomic_json_write(bundle / INTENT, intent)
        return intent


def finish(bundle, operation_id):
    """Yalnizca prototip sonuc kaydi.

    Gercek state'in basarili oldugunu kendi basina kanitlamaz.
    """
    bundle = Path(bundle)
    lock = bundle.parent / "transaction.lock"

    with transaction_lock(lock):
        intent = read_record(bundle / INTENT)

        if (
            intent.get("version") != 1
            or intent.get("status") != "IN_FLIGHT"
            or intent.get("operation_id") != operation_id
        ):
            raise ValueError("Intent uyusmazligi")

        result = {
            "version": 1,
            "status": "CONFIRMED",
            "operation_id": operation_id,
            "intent_sha256": digest(intent),
        }

        atomic_json_write(bundle / RESULT, result)
        return inspect(bundle)
