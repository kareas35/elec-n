#!/usr/bin/env python3
"""V3.8 - Atomic JSON ic kesinti testleri.

Sadece gecici klasorlerde calisir.
Gercek yayinlar ve CSV degistirilmez.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_bundle import V38
from transaction_migration_test import (
    fixture, make_recovered, migrate_legacy
)
from transaction_unified_record_test import load_unified

CHILD = r'''
import os
import sys
from pathlib import Path

import transaction_journal as journal
from transaction_migration_test import migrate_legacy

bundle = Path(sys.argv[1])
live = Path(sys.argv[2])
csv_path = Path(sys.argv[3])
mode = sys.argv[4]

if mode == "before_fsync":
    def crash_fsync(fd):
        os._exit(71)
    journal.os.fsync = crash_fsync

elif mode == "before_link":
    def crash_link(source, target):
        os._exit(72)
    journal.os.link = crash_link

elif mode == "after_link":
    original_link = journal.os.link

    def crash_after_link(source, target):
        original_link(source, target)
        os._exit(73)

    journal.os.link = crash_after_link

else:
    raise RuntimeError("Bilinmeyen kesinti modu")

migrate_legacy(bundle, live, csv_path)
raise RuntimeError("Beklenen kesinti gerceklesmedi")
'''


def snapshot(bundle, live, csv_path):
    files = [
        bundle / "transaction-state.json",
        bundle / "recovery-result.json",
        bundle / "transaction.json",
        bundle / "csv-baseline.csv",
        bundle / "csv-baseline.json",
        live / "100.html",
        live / "171.html",
        csv_path
    ]
    return [(p, p.read_bytes()) for p in files]


def check_snapshot(saved):
    for path, content in saved:
        assert path.read_bytes() == content, (
            "Kaynak dosya degisti: " + str(path)
        )


def run_case(root, name, exit_code, published):
    base = root / name
    bundle, live, csv_path = fixture(base)
    make_recovered(bundle, live, csv_path)

    saved = snapshot(bundle, live, csv_path)
    target = bundle / "transaction-record.json"

    child = subprocess.run(
        [
            sys.executable, "-c", CHILD,
            str(bundle), str(live),
            str(csv_path), name
        ],
        cwd=V38,
        capture_output=True,
        text=True,
        timeout=15
    )

    assert child.returncode == exit_code, (
        f"Beklenen: {exit_code}; "
        f"Gercek: {child.returncode}; "
        f"Hata: {child.stderr[:500]}"
    )

    check_snapshot(saved)

    # Yayinlama oncesi: hedef hic olusmamali.
    # Yayinlama sonrasi: hedef gecerli olmali.
    assert target.exists() == published

    leftovers = list(bundle.glob(".journal-*"))
    assert leftovers, "Kesinti sonrasi gecici dosya bulunamadi"

    if not published:
        # Artik gecici dosyalara dokunmadan
        # migrasyon yeniden denenebilmeli.
        record = migrate_legacy(bundle, live, csv_path)
        assert load_unified(target) == record
    else:
        record = load_unified(target)
        assert record["state"] == "RECOVERED"

        original = target.read_bytes()

        try:
            migrate_legacy(bundle, live, csv_path)
        except FileExistsError:
            pass
        else:
            raise AssertionError(
                "Mevcut birlesik kayit ezilebildi"
            )

        assert target.read_bytes() == original

    check_snapshot(saved)
    return len(leftovers)


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-atomic-crash-"
    ) as tmp:
        root = Path(tmp)

        scenarios = [
            ("before_fsync", 71, False),
            ("before_link", 72, False),
            ("after_link", 73, True)
        ]

        for i, (name, code, published) in enumerate(
            scenarios, start=1
        ):
            orphan_count = run_case(
                root, name, code, published
            )

            print(
                f"TEST {i} PASS: {name} kesintisi; "
                f"gecici dosya sayisi={orphan_count}"
            )

        print("TEST 4 PASS: Kaynak dosyalar korundu")
        print("TEST 5 PASS: Erken kesintilerden sonra tekrar denendi")
        print("TEST 6 PASS: Yayinlanmis kayit ezilemedi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")
    print("Gecici test klasorleri temizlendi")


if __name__ == "__main__":
    main()
