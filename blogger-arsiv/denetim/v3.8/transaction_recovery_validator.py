#!/usr/bin/env python3
"""V3.8 - RECOVERED gecisi icin dosya dogrulayicisi.

Sadece gecici kopyalarla test edilir.
"""
import json
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import (
    create_bundle, verify_bundle, V38, ROOT
)
from transaction_csv_baseline import (
    capture_baseline, verify_baseline
)
from transaction_journal import sha256
from transaction_lock import transaction_lock

NAMES = {"100.html", "171.html"}


def verify_recovered(bundle, live_dir, csv_path):
    bundle = Path(bundle)
    live_dir = Path(live_dir)
    csv_path = Path(csv_path)

    verify_bundle(bundle)
    verify_baseline(bundle)

    manifest = json.loads(
        (bundle / "transaction.json").read_text("utf-8")
    )
    entries = manifest["entries"]

    if {entry["name"] for entry in entries} != NAMES:
        raise ValueError("Beklenmeyen yayin kapsami")

    for entry in entries:
        page = live_dir / entry["name"]

        if page.is_symlink() or not page.is_file():
            raise ValueError("Eksik veya guvensiz HTML")

        if sha256(page.read_bytes()) != entry["after_sha256"]:
            raise ValueError("HTML entegre duruma donmemis")

    if csv_path.is_symlink() or not csv_path.is_file():
        raise ValueError("Eksik veya guvensiz CSV")

    baseline = bundle / "csv-baseline.csv"

    if sha256(csv_path.read_bytes()) != sha256(
        baseline.read_bytes()
    ):
        raise ValueError("CSV baseline ile uyusmuyor")

    return True


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-recovery-validator-"
    ) as tmp:
        base = Path(tmp)
        bundle = base / "bundle"
        live = base / "live"
        live.mkdir()

        entries = []

        for name in sorted(NAMES):
            before = (
                V38 / "integration-backups"
                / (name + ".before-e14.gif")
            )
            after = ROOT / "Arsiv/yayinlar" / name

            entries.append({
                "name": name,
                "before": before,
                "after": after
            })
            shutil.copy2(after, live / name)

        create_bundle(bundle, entries)

        plan = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        with transaction_lock(base / "transaction.lock"):
            capture_baseline(bundle, plan)

        assert verify_recovered(bundle, live, plan)
        print("TEST 1 PASS: HTML ve CSV dogrulandi")

        page = live / "100.html"
        original = page.read_bytes()
        page.write_bytes(original + b"\nUNEXPECTED")

        try:
            verify_recovered(bundle, live, plan)
            raise AssertionError("Bozuk HTML kabul edildi")
        except ValueError:
            pass

        page.write_bytes(original)
        print("TEST 2 PASS: Bozuk HTML reddedildi")

        original_csv = plan.read_bytes()
        plan.write_bytes(original_csv + b"\nUNEXPECTED")

        try:
            verify_recovered(bundle, live, plan)
            raise AssertionError("Bozuk CSV kabul edildi")
        except ValueError:
            pass

        plan.write_bytes(original_csv)
        print("TEST 3 PASS: Bozuk CSV reddedildi")

        baseline = bundle / "csv-baseline.csv"
        original_baseline = baseline.read_bytes()
        baseline.write_bytes(original_baseline + b"\nTAMPER")

        try:
            verify_recovered(bundle, live, plan)
            raise AssertionError("Bozuk baseline kabul edildi")
        except ValueError:
            pass

        baseline.write_bytes(original_baseline)
        print("TEST 4 PASS: Bozuk baseline reddedildi")

        manifest_path = bundle / "transaction.json"
        original_manifest = manifest_path.read_bytes()
        manifest_path.write_bytes(
            original_manifest + b"\nTAMPER"
        )

        try:
            verify_recovered(bundle, live, plan)
            raise AssertionError("Bozuk manifest kabul edildi")
        except (ValueError, json.JSONDecodeError):
            pass

        manifest_path.write_bytes(original_manifest)
        assert verify_recovered(bundle, live, plan)

        print("TEST 5 PASS: Manifest bozulmasi reddedildi")

    print("\nSONUC: 5/5 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
