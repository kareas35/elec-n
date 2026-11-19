#!/usr/bin/env python3
"""Elektronik Akademi V3.8 - kontrollu LDR rollback."""
import argparse
import csv
import hashlib
import io
import os
import sys
from pathlib import Path

V38 = Path(__file__).resolve().parent
ROOT = V38.parents[1]
PLAN = V38 / "restorasyon-entegrasyon-plani.csv"

sys.path.insert(0, str(V38))
from restorasyon_entegre import transform

TARGETS = ("100.html", "171.html")
IMAGE = "e14.gif"
SVG = "restored-e14-ldr.svg"

def digest(data):
    return hashlib.sha256(data).hexdigest()[:16]

def atomic_write(path, data):
    temp = path.with_name(path.name + ".rollback-tmp")
    if temp.exists():
        raise RuntimeError(f"Gecici dosya mevcut: {temp}")
    try:
        with temp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rollback", action="store_true",
        help="Dogrulanan iki LDR entegrasyonunu geri al"
    )
    args = parser.parse_args()

    with PLAN.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    prepared = []

    for filename in TARGETS:
        page = ROOT / "Arsiv/yayinlar" / filename
        backup = V38 / "integration-backups" / (
            filename + ".before-e14.gif"
        )

        original = backup.read_bytes()
        current = page.read_bytes()

        expected = transform(
            original.decode("utf-8"),
            IMAGE, SVG
        ).encode("utf-8")

        if current != expected:
            raise SystemExit(
                f"DURDURULDU: {filename} beklenen "
                "entegrasyon surumunden farkli."
            )

        matches = [
            row for row in rows
            if row["Original"] == IMAGE
            and row["Publication"] == filename
        ]

        if len(matches) != 1 or matches[0]["Integrated"] != "true":
            raise SystemExit(
                f"DURDURULDU: CSV durumu uyusmuyor: {filename}"
            )

        prepared.append((filename, page, original, matches[0]))

        print(
            f"OK: {filename} | "
            f"Mevcut: {digest(current)} | "
            f"Yedek: {digest(original)}"
        )

    if not args.rollback:
        print("\nGERI ALMA KONTROLU BASARILI")
        print("Dosya degisikligi: 0")
        print("Gercek rollback: YAPILMADI")
        return

    for filename, page, original, row in prepared:
        atomic_write(page, original)
        row["Integrated"] = "false"
        row["Status"] = "technical_review"
        print("GERI ALINDI:", filename)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "Original", "Publication", "Restored",
            "Status", "Integrated"
        ],
        lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)

    atomic_write(PLAN, buffer.getvalue().encode("utf-8-sig"))

    print("\nRollback tamamlandi.")
    print("Orijinal yedekler korundu.")
    print("Degisiklikler GitHub'a otomatik gonderilmedi.")

if __name__ == "__main__":
    main()
