#!/usr/bin/env python3
"""V3.8 - CSV kurtarma kopyasi prototipi.

Gercek yayinlara ve gercek CSV'ye yazmaz.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, verify_bundle, V38, ROOT
from transaction_journal import sha256, atomic_json_write
from transaction_lock import transaction_lock


def capture_baseline(bundle, source):
    bundle, source = Path(bundle), Path(source)
    verify_bundle(bundle)

    if source.is_symlink() or not source.is_file():
        raise ValueError("Guvensiz CSV kaynagi")

    target = bundle / "csv-baseline.csv"
    metadata = bundle / "csv-baseline.json"

    if target.exists() or target.is_symlink():
        raise FileExistsError("CSV baseline zaten mevcut")
    if metadata.exists() or metadata.is_symlink():
        raise FileExistsError("CSV metadata zaten mevcut")

    data = source.read_bytes()
    manifest_hash = sha256(
        (bundle / "transaction.json").read_bytes()
    )

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    atomic_json_write(metadata, {
        "version": 1,
        "csv_sha256": sha256(data),
        "manifest_sha256": manifest_hash
    })

    return verify_baseline(bundle)


def verify_baseline(bundle):
    bundle = Path(bundle)
    verify_bundle(bundle)

    csv_file = bundle / "csv-baseline.csv"
    metadata = bundle / "csv-baseline.json"
    manifest = bundle / "transaction.json"

    for path in (csv_file, metadata, manifest):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Eksik veya guvensiz kurtarma dosyasi")

    info = json.loads(metadata.read_text("utf-8"))

    if info.get("version") != 1:
        raise ValueError("Gecersiz baseline surumu")

    if sha256(csv_file.read_bytes()) != info.get("csv_sha256"):
        raise ValueError("CSV SHA-256 uyusmazligi")

    if sha256(manifest.read_bytes()) != info.get("manifest_sha256"):
        raise ValueError("Transaction manifest SHA-256 uyusmazligi")

    return True


def main():
    with tempfile.TemporaryDirectory(prefix="v38-csv-baseline-") as tmp:
        root = Path(tmp)
        bundle = root / "bundle"
        source = root / "source.csv"

        entries = [
            {
                "name": name,
                "before": V38 / "integration-backups" /
                          (name + ".before-e14.gif"),
                "after": ROOT / "Arsiv/yayinlar" / name
            }
            for name in ("100.html", "171.html")
        ]

        create_bundle(bundle, entries)

        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            source
        )

        lock = root / "transaction.lock"

        with transaction_lock(lock):
            assert capture_baseline(bundle, source)
        print("TEST 1 PASS: CSV baseline ve SHA-256 kaydedildi")

        assert verify_baseline(bundle)
        print("TEST 2 PASS: Kalici kopya dogrulandi")

        try:
            with transaction_lock(lock):
                capture_baseline(bundle, source)
            raise AssertionError("Mevcut baseline ezildi")
        except FileExistsError:
            pass
        print("TEST 3 PASS: Mevcut baseline korunuyor")

        csv_file = bundle / "csv-baseline.csv"
        original = csv_file.read_bytes()
        csv_file.write_bytes(original + b"\nTAMPER")

        try:
            verify_baseline(bundle)
            raise AssertionError("Bozuk CSV kabul edildi")
        except ValueError:
            pass
        print("TEST 4 PASS: Bozulmus CSV reddedildi")

        csv_file.write_bytes(original)
        assert verify_baseline(bundle)

        meta = bundle / "csv-baseline.json"
        saved = meta.read_bytes()
        changed = json.loads(saved)
        changed["manifest_sha256"] = "0" * 64
        meta.write_text(json.dumps(changed), encoding="utf-8")

        try:
            verify_baseline(bundle)
            raise AssertionError("Manifest uyusmazligi kabul edildi")
        except ValueError:
            pass
        print("TEST 5 PASS: Manifest uyusmazligi reddedildi")

    print("\nSONUC: 5/5 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
