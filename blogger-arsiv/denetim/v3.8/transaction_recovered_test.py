#!/usr/bin/env python3
"""V3.8 - RECOVERED durum kaydi prototipi.

Gercek yayinlara ve CSV'ye yazmaz.
"""
import json
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, verify_bundle, V38, ROOT
from transaction_journal import sha256, atomic_json_write
from transaction_lock import transaction_lock
from transaction_state import load_state
from transaction_api import open_transaction

NAMES = ("100.html", "171.html")


def record_recovered(bundle, live, plan, baseline, lock_path):
    """Kurtarma sonucunu yalnizca dogrulamadan sonra kaydet."""
    with transaction_lock(lock_path):
        verify_bundle(bundle)

        if load_state(bundle / "transaction-state.json") != "IN_PROGRESS":
            raise ValueError("Islem IN_PROGRESS durumunda degil")

        manifest_path = bundle / "transaction.json"
        manifest = json.loads(manifest_path.read_text("utf-8"))

        names = {entry["name"] for entry in manifest["entries"]}
        if names != set(NAMES):
            raise ValueError("Beklenmeyen yayin kapsami")

        for entry in manifest["entries"]:
            page = live / entry["name"]

            if page.is_symlink() or not page.is_file():
                raise ValueError("Gecersiz yayin dosyasi")

            if sha256(page.read_bytes()) != entry["after_sha256"]:
                raise ValueError("HTML entegre duruma donmemis")

        if (
            plan.is_symlink() or baseline.is_symlink()
            or not plan.is_file() or not baseline.is_file()
        ):
            raise ValueError("CSV dosyasi eksik veya guvensiz")

        csv_hash = sha256(baseline.read_bytes())

        if sha256(plan.read_bytes()) != csv_hash:
            raise ValueError("CSV onceki saglam durumla uyusmuyor")

        result = {
            "version": 1,
            "state": "RECOVERED",
            "recovered_to": "INTEGRATED",
            "manifest_sha256": sha256(manifest_path.read_bytes()),
            "csv_sha256": csv_hash,
            "files": sorted(names)
        }

        # Mevcut sonuc kaydi asla ezilmez.
        atomic_json_write(bundle / "recovery-result.json", result)
        return result



def _api_compat_initialize(bundle):
    """Gecici test bundle'ini kilitli API ile baslat."""
    with open_transaction(bundle) as api:
        return api.initialize()


def _api_compat_transition(
    bundle, expected, target, live_dir=None, csv_path=None
):
    """Eski recovery testini kilitli API ile calistir."""
    with open_transaction(bundle) as api:
        return api.transition(
            expected,
            target,
            live_dir=live_dir,
            csv_path=csv_path,
        )


initialize = _api_compat_initialize
transition = _api_compat_transition


def main():
    with tempfile.TemporaryDirectory(prefix="v38-recovered-") as tmp:
        base = Path(tmp)
        bundle = base / "bundle"
        live = base / "live"
        live.mkdir()

        entries = []

        for name in NAMES:
            before = V38 / "integration-backups" / (
                name + ".before-e14.gif"
            )
            after = ROOT / "Arsiv/yayinlar" / name

            entries.append({
                "name": name,
                "before": before,
                "after": after
            })

            shutil.copy2(after, live / name)

        plan = base / "plan.csv"
        baseline = base / "baseline.csv"

        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            baseline
        )
        shutil.copy2(baseline, plan)

        create_bundle(bundle, entries)
        initialize(bundle)

        lock_path = base / "restoration.lock"
        result_path = bundle / "recovery-result.json"

        def attempt():
            return record_recovered(
                bundle, live, plan, baseline, lock_path
            )

        def reject(message, expected_exception=ValueError):
            try:
                attempt()
            except expected_exception:
                assert not result_path.exists()
                print("PASS:", message)
            else:
                raise AssertionError("Guvenlik kontrolu atlandi")

        # TEST 1
        reject("TEST 1 - PREPARED durumunda kurtarma kapatilamadi")

        transition(bundle, "PREPARED", "IN_PROGRESS")

        # TEST 2
        page = live / "100.html"
        good_html = page.read_bytes()
        page.write_bytes(good_html + b"\nUNEXPECTED")

        reject("TEST 2 - Bozuk HTML reddedildi")
        page.write_bytes(good_html)

        # TEST 3
        original_csv = plan.read_bytes()
        plan.write_bytes(original_csv + b"\nUNEXPECTED")

        reject("TEST 3 - Degismis CSV reddedildi")
        plan.write_bytes(original_csv)

        # TEST 4
        with transaction_lock(lock_path):
            try:
                attempt()
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)
                assert not result_path.exists()
                print("PASS: TEST 4 - Cakisan islem engellendi")
            else:
                raise AssertionError("Islem kilidi asilabildi")

        # TEST 5
        result = attempt()
        assert result["state"] == "RECOVERED"
        assert result["recovered_to"] == "INTEGRATED"
        assert json.loads(
            result_path.read_text("utf-8")
        ) == result

        print("TEST 5 PASS: Dogrulanmis RECOVERED kaydi olusturuldu")

        # TEST 6
        try:
            attempt()
            raise AssertionError("Mevcut sonuc kaydi ezildi")
        except FileExistsError:
            pass

        assert json.loads(
            result_path.read_text("utf-8")
        ) == result

        print("TEST 6 PASS: RECOVERED kaydi korunuyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
