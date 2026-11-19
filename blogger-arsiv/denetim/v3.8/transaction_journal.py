#!/usr/bin/env python3
"""V3.8 - Transaction journal temel altyapisi."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(
            f"Mevcut journal korunuyor: {path}"
        )

    fd, temporary = tempfile.mkstemp(
        prefix=".journal-",
        dir=path.parent
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                payload, f,
                ensure_ascii=False,
                indent=2
            )
            f.flush()
            os.fsync(f.fileno())

        # Mevcut journal asla ezilmez.
        os.link(temporary, path)
        directory_fd = os.open(
            path.parent, os.O_RDONLY
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def create_journal(path, entries):
    if not entries:
        raise ValueError("Bos islem gunlugu olusturulamaz")

    journal = {
        "version": 1,
        "state": "prepared",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "entries": []
    }

    for entry in entries:
        before = Path(entry["before"])
        after = Path(entry["after"])

        if not before.is_file() or not after.is_file():
            raise FileNotFoundError("Islem dosyasi eksik")

        journal["entries"].append({
            "name": entry["name"],
            "before_sha256": sha256(before.read_bytes()),
            "after_sha256": sha256(after.read_bytes())
        })

    atomic_json_write(path, journal)
    return journal


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)

        before = folder / "before.html"
        after = folder / "after.html"
        journal_path = folder / "transaction.json"

        before.write_text(
            "<html>Orijinal</html>", encoding="utf-8"
        )
        after.write_text(
            "<html>Restorasyon</html>", encoding="utf-8"
        )

        result = create_journal(
            journal_path,
            [{
                "name": "test.html",
                "before": before,
                "after": after
            }]
        )

        assert result["state"] == "prepared"
        assert len(result["entries"]) == 1
        assert journal_path.exists()

        try:
            create_journal(
                journal_path,
                [{
                    "name": "test.html",
                    "before": before,
                    "after": after
                }]
            )
            raise AssertionError(
                "Mevcut journal ezilebildi"
            )
        except FileExistsError:
            pass

        print("TEST 1 PASS: Journal olusturuldu")
        print("TEST 2 PASS: SHA-256 kaydedildi")
        print("TEST 3 PASS: Mevcut journal korunuyor")
        print("TEST 4 PASS: Gecici klasorde calisti")
        print("\nGercek yayinlarda degisiklik: 0")
