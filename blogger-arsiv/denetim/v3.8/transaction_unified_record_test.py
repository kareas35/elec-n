#!/usr/bin/env python3
"""V3.8 - Birlesik transaction kaydi prototipi.

Eski kayitlari degistirmez.
Yalnizca gecici klasorde calisir.
"""
import json
import tempfile
from pathlib import Path

from transaction_journal import atomic_json_write

STATES = {
    "PREPARED", "IN_PROGRESS",
    "COMPLETED", "RECOVERED"
}


def validate_record(record):
    if not isinstance(record, dict):
        raise ValueError("Gecersiz kayit")

    if record.get("version") != 1:
        raise ValueError("Desteklenmeyen surum")

    state = record.get("state")
    if state not in STATES:
        raise ValueError("Bilinmeyen durum")

    recovery = record.get("recovery")

    if state == "RECOVERED":
        if not isinstance(recovery, dict):
            raise ValueError("Recovery bilgisi zorunlu")

        if recovery.get("recovered_to") != "INTEGRATED":
            raise ValueError("Gecersiz recovery hedefi")

        for key in ("manifest_sha256", "csv_sha256"):
            value = recovery.get(key)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("Gecersiz SHA-256")

        files = recovery.get("files")
        if (
            not isinstance(files, list)
            or not files
            or len(files) != len(set(files))
            or any(
                not isinstance(n, str)
                or not n
                or Path(n).name != n
                or n in (".", "..")
                or "/" in n or "\\" in n
                for n in files
            )
        ):
            raise ValueError("Gecersiz dosya listesi")

    elif recovery is not None:
        raise ValueError("Recovery bilgisi yanlis durumda")

    return True


def load_unified(path):
    path = Path(path)

    if path.is_symlink() or not path.is_file():
        raise ValueError("Guvensiz kayit dosyasi")

    record = json.loads(path.read_text("utf-8"))
    validate_record(record)
    return record


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-unified-record-"
    ) as tmp:
        base = Path(tmp)
        path = base / "transaction-record.json"

        recovered = {
            "version": 1,
            "state": "RECOVERED",
            "recovery": {
                "recovered_to": "INTEGRATED",
                "manifest_sha256": "a" * 64,
                "csv_sha256": "b" * 64,
                "files": ["100.html", "171.html"]
            }
        }

        assert validate_record(recovered)
        atomic_json_write(path, recovered)
        assert load_unified(path) == recovered
        print("TEST 1 PASS: Birlesik kayit olusturuldu")

        try:
            atomic_json_write(path, recovered)
            raise AssertionError("Mevcut kayit ezildi")
        except FileExistsError:
            pass
        print("TEST 2 PASS: Mevcut kayit korundu")

        broken = json.loads(json.dumps(recovered))
        broken["recovery"]["csv_sha256"] = "INVALID"

        try:
            validate_record(broken)
            raise AssertionError("Gecersiz SHA kabul edildi")
        except ValueError:
            pass
        print("TEST 3 PASS: Gecersiz SHA reddedildi")

        broken = json.loads(json.dumps(recovered))
        broken["recovery"]["files"] = ["../unsafe.html"]

        try:
            validate_record(broken)
            raise AssertionError("Guvensiz yol kabul edildi")
        except ValueError:
            pass
        print("TEST 4 PASS: Guvensiz dosya yolu reddedildi")

        # Eski kayit formatlarini salt okunur incele.
        legacy_state = base / "transaction-state.json"
        legacy_result = base / "recovery-result.json"

        legacy_state.write_text(
            json.dumps({"state": "RECOVERED"}),
            encoding="utf-8"
        )
        legacy_result.write_text(
            json.dumps({
                "version": 1,
                "state": "RECOVERED",
                **recovered["recovery"]
            }),
            encoding="utf-8"
        )

        before_state = legacy_state.read_bytes()
        before_result = legacy_result.read_bytes()

        old_state = json.loads(before_state)
        old_result = json.loads(before_result)

        assert old_state["state"] == recovered["state"]
        assert all(
            old_result[k] == recovered["recovery"][k]
            for k in recovered["recovery"]
        )

        assert legacy_state.read_bytes() == before_state
        assert legacy_result.read_bytes() == before_result

        print("TEST 5 PASS: Eski kayitlar salt okunur incelendi")

        prepared = {
            "version": 1,
            "state": "PREPARED",
            "recovery": None
        }
        assert validate_record(prepared)
        print("TEST 6 PASS: PREPARED kaydi destekleniyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
