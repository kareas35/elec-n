#!/usr/bin/env python3
"""V3.8 - Kurtarma kopyalari. Gercek yayinlara yazmaz."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from transaction_journal import sha256, atomic_json_write

V38 = Path(__file__).resolve().parent
ROOT = V38.parents[1]


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def valid_name(name):
    return (
        isinstance(name, str)
        and bool(name)
        and name not in (".", "..")
        and Path(name).name == name
        and "/" not in name
        and "\\" not in name
    )


def write_copy(path, data):
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def create_bundle(folder, entries):
    folder = Path(folder)

    if not entries:
        raise ValueError("Bos islem listesi")

    names = [e["name"] for e in entries]

    if any(not valid_name(n) for n in names):
        raise ValueError("Guvensiz dosya adi")

    if len(names) != len(set(names)):
        raise ValueError("Tekrarlanan dosya adi")

    # Var olan bir klasor asla ezilmez.
    folder.mkdir(parents=False, exist_ok=False)

    before_dir = folder / "before"
    after_dir = folder / "after"
    before_dir.mkdir()
    after_dir.mkdir()

    records = []

    for entry in entries:
        name = entry["name"]
        before = Path(entry["before"])
        after = Path(entry["after"])

        if (
            before.is_symlink()
            or after.is_symlink()
            or not before.is_file()
            or not after.is_file()
        ):
            raise ValueError("Gecersiz kaynak dosya")

        before_data = before.read_bytes()
        after_data = after.read_bytes()

        write_copy(before_dir / name, before_data)
        write_copy(after_dir / name, after_data)

        records.append({
            "name": name,
            "before_sha256": sha256(before_data),
            "after_sha256": sha256(after_data)
        })

    sync_dir(before_dir)
    sync_dir(after_dir)

    manifest = {
        "version": 2,
        "state": "prepared",
        "entries": records
    }

    # Manifest en son yayinlanir.
    atomic_json_write(folder / "transaction.json", manifest)
    sync_dir(folder)

    return manifest


def verify_bundle(folder):
    folder = Path(folder)

    manifest_path = folder / "transaction.json"
    if manifest_path.is_symlink():
        raise ValueError("Guvensiz manifest")

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if (
        manifest.get("version") != 2
        or manifest.get("state") != "prepared"
    ):
        raise ValueError("Gecersiz journal")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Gecersiz kayit listesi")

    seen = set()

    for entry in entries:
        name = entry["name"]

        if not valid_name(name) or name in seen:
            raise ValueError("Gecersiz veya tekrarlanan ad")
        seen.add(name)

        for phase in ("before", "after"):
            path = folder / phase / name
            expected = entry[phase + "_sha256"]

            if (
                not isinstance(expected, str)
                or len(expected) != 64
                or any(c not in "0123456789abcdef" for c in expected)
                or path.is_symlink()
                or not path.is_file()
                or sha256(path.read_bytes()) != expected
            ):
                raise ValueError(
                    f"Kurtarma kopyasi dogrulanamadi: {phase}/{name}"
                )

    return True


def self_test():
    with tempfile.TemporaryDirectory(prefix="v38-bundle-") as tmp:
        root = Path(tmp)
        entries = []

        for name in ("100.html", "171.html"):
            entries.append({
                "name": name,
                "before": (
                    V38 / "integration-backups" /
                    (name + ".before-e14.gif")
                ),
                "after": ROOT / "Arsiv/yayinlar" / name
            })

        bundle = root / "transaction-001"

        create_bundle(bundle, entries)
        assert (bundle / "transaction.json").is_file()
        print("TEST 1 PASS: Kurtarma kopyalari olusturuldu")

        assert verify_bundle(bundle)
        print("TEST 2 PASS: SHA-256 dogrulamasi")

        try:
            create_bundle(bundle, entries)
            raise AssertionError("Var olan bundle ezildi")
        except FileExistsError:
            pass
        print("TEST 3 PASS: Mevcut bundle korunuyor")

        # Kopyayi bilerek boz.
        copy = bundle / "after/171.html"
        original = copy.read_bytes()
        copy.write_bytes(original + b"TEST")

        try:
            verify_bundle(bundle)
            raise AssertionError("Bozuk kopya kabul edildi")
        except ValueError:
            pass
        print("TEST 4 PASS: Bozuk kopya reddedildi")

        copy.write_bytes(original)
        assert verify_bundle(bundle)
        print("TEST 5 PASS: Saglam kopyalar yeniden dogrulandi")

        try:
            create_bundle(
                root / "invalid",
                [{
                    "name": "../outside.html",
                    "before": entries[0]["before"],
                    "after": entries[0]["after"]
                }]
            )
            raise AssertionError("Guvensiz yol kabul edildi")
        except ValueError:
            pass
        print("TEST 6 PASS: Guvensiz dosya yolu reddedildi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    self_test()
