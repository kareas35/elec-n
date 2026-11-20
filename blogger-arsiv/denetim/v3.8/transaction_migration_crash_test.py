#!/usr/bin/env python3
"""V3.8 - Migrasyon sirasinda ani kapanma testleri.

Yalnizca gecici test klasorlerinde calisir.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_bundle import V38
from transaction_lock import transaction_lock
from transaction_migration_test import (
    fixture, make_recovered, migrate_legacy
)
from transaction_unified_record_test import load_unified

CHILD = r'''
import os
import sys
from pathlib import Path
import transaction_migration_test as migration

bundle = Path(sys.argv[1])
live = Path(sys.argv[2])
csv_path = Path(sys.argv[3])
mode = sys.argv[4]

original_write = migration.atomic_json_write

def crash_write(path, payload):
    if mode == "before":
        os._exit(73)

    if mode == "after":
        original_write(path, payload)
        os._exit(74)

    raise RuntimeError("Bilinmeyen test modu")

migration.atomic_json_write = crash_write
migration.migrate_legacy(bundle, live, csv_path)
raise RuntimeError("Beklenen kesinti gerceklesmedi")
'''


def snapshot(bundle):
    names = (
        "transaction-state.json",
        "recovery-result.json",
        "transaction.json",
        "csv-baseline.csv",
        "csv-baseline.json"
    )
    return {
        name: (bundle / name).read_bytes()
        for name in names
        if (bundle / name).exists()
    }


def assert_unchanged(bundle, before):
    for name, content in before.items():
        assert (bundle / name).read_bytes() == content, name


def crash(bundle, live, csv_path, mode, expected):
    process = subprocess.run(
        [
            sys.executable, "-c", CHILD,
            str(bundle), str(live),
            str(csv_path), mode
        ],
        cwd=V38,
        capture_output=True,
        text=True,
        timeout=15
    )

    if process.returncode != expected:
        raise AssertionError(
            f"Beklenen cikis {expected}, "
            f"gercek {process.returncode}: "
            f"{process.stderr[:500]}"
        )


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-migration-crash-"
    ) as tmp:
        root = Path(tmp)

        # SENARYO A: Dosya yayinlanmadan once kesinti.
        bundle, live, csv_path = fixture(root / "before")
        make_recovered(bundle, live, csv_path)

        before = snapshot(bundle)
        output = bundle / "transaction-record.json"

        crash(bundle, live, csv_path, "before", 73)

        assert not output.exists()
        assert_unchanged(bundle, before)
        print("TEST 1 PASS: Erken kesintide kaynaklar korundu")

        with transaction_lock(
            bundle.parent / "transaction.lock"
        ):
            pass
        print("TEST 2 PASS: Kesinti sonrasi kilit alinabildi")

        record = migrate_legacy(bundle, live, csv_path)
        assert record["state"] == "RECOVERED"
        assert load_unified(output) == record
        assert_unchanged(bundle, before)

        print("TEST 3 PASS: Migrasyon guvenle tekrarlandi")

        # SENARYO B: Dosya yayinlandiktan sonra kesinti.
        bundle2, live2, csv2 = fixture(root / "after")
        make_recovered(bundle2, live2, csv2)

        before2 = snapshot(bundle2)
        output2 = bundle2 / "transaction-record.json"

        crash(bundle2, live2, csv2, "after", 74)

        assert output2.is_file()
        record2 = load_unified(output2)
        assert record2["state"] == "RECOVERED"
        assert_unchanged(bundle2, before2)

        print("TEST 4 PASS: Gec kesintide kayit saglam")

        with transaction_lock(
            bundle2.parent / "transaction.lock"
        ):
            pass
        print("TEST 5 PASS: Ikinci kesintide kilit serbest")

        saved = output2.read_bytes()

        try:
            migrate_legacy(bundle2, live2, csv2)
            raise AssertionError("Mevcut kayit ezildi")
        except FileExistsError:
            pass

        assert output2.read_bytes() == saved
        assert_unchanged(bundle2, before2)

        print("TEST 6 PASS: Tekrar migrasyon kaydi ezemedi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")
    print("Test klasoru: OTOMATIK TEMIZLENDI")


if __name__ == "__main__":
    main()
