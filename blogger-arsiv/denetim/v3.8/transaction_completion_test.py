#!/usr/bin/env python3
"""V3.8 - Rollback tamamlanma dogrulama prototipi.

Sadece gecici klasorde calisir.
Gercek yayinlari veya CSV'yi degistirmez.
"""
import csv
import json
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import (
    create_bundle,
    verify_bundle,
    V38,
    ROOT,
)
from transaction_journal import sha256

NAMES = ("100.html", "171.html")


def verify_completion(bundle, live_dir, csv_path):
    """Butun HTML ve CSV kayitlari tamamlandi mi?"""
    verify_bundle(bundle)

    journal = json.loads(
        (bundle / "transaction.json").read_text("utf-8")
    )

    entries = journal["entries"]

    if {e["name"] for e in entries} != set(NAMES):
        raise ValueError("Beklenmeyen yayin kapsami")

    # Rollback sonrasi her HTML, BEFORE kopyasina esit olmali.
    for entry in entries:
        name = entry["name"]
        page = live_dir / name

        if page.is_symlink() or not page.is_file():
            raise ValueError(f"Eksik veya guvensiz yayin: {name}")

        actual = sha256(page.read_bytes())

        if actual != entry["before_sha256"]:
            raise ValueError(f"Yayin henuz tamamlanmadi: {name}")

    if csv_path.is_symlink() or not csv_path.is_file():
        raise ValueError("Gecersiz CSV dosyasi")

    with csv_path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)
        if not {"Original", "Publication", "Status",
                "Integrated"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV sutunlari gecersiz")
        rows = list(reader)

    for name in NAMES:
        matches = [
            r for r in rows
            if r["Original"] == "e14.gif"
            and r["Publication"] == name
        ]

        if len(matches) != 1:
            raise ValueError(f"CSV kaydi gecersiz: {name}")

        row = matches[0]
        if (row["Integrated"] != "false"
                or row["Status"] != "technical_review"):
            raise ValueError(f"CSV henuz tamamlanmadi: {name}")

    return True


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-completion-"
    ) as tmp:
        root = Path(tmp)
        live = root / "live"
        live.mkdir()
        entries = []

        for name in NAMES:
            before = (
                V38 / "integration-backups" /
                (name + ".before-e14.gif")
            )
            after = ROOT / "Arsiv/yayinlar" / name

            entries.append({
                "name": name,
                "before": before,
                "after": after,
            })

            # Baslangicta entegre kopyalar.
            shutil.copy2(after, live / name)

        bundle = root / "bundle"
        create_bundle(bundle, entries)

        plan = root / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        def expect_rejected(label):
            try:
                verify_completion(bundle, live, plan)
            except ValueError:
                print("PASS:", label)
            else:
                raise AssertionError(
                    "Eksik islem kabul edildi: " + label
                )

        # 1. Islem baslamadan tamamlandi denemez.
        expect_rejected(
            "TEST 1 - Entegre HTML tamamlanmis sayilmadi"
        )

        # 2. Sadece ilk HTML geri alindi.
        shutil.copy2(entries[0]["before"], live / NAMES[0])
        expect_rejected(
            "TEST 2 - Yari kalmis rollback reddedildi"
        )

        # 3. HTML'ler tamam; CSV eski durumda.
        shutil.copy2(entries[1]["before"], live / NAMES[1])
        expect_rejected(
            "TEST 3 - Guncellenmemis CSV reddedildi"
        )

        # CSV'yi sadece gecici klasorde guncelle.
        with plan.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)

        for row in rows:
            if (row["Original"] == "e14.gif"
                    and row["Publication"] in NAMES):
                row["Integrated"] = "false"
                row["Status"] = "technical_review"

        with plan.open(
            "w", encoding="utf-8-sig", newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        assert verify_completion(bundle, live, plan)
        print("TEST 4 PASS: HTML ve CSV tamamlanmasi dogrulandi")

        # 5. Bilinmeyen dosya degisikligi.
        page = live / NAMES[1]
        original = page.read_bytes()
        page.write_bytes(original + b"\nUNEXPECTED")

        expect_rejected(
            "TEST 5 - Beklenmeyen degisiklik reddedildi"
        )

    print("\nSONUC: 5/5 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
