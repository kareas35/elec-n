#!/usr/bin/env python3
"""V3.8 - RECOVERED state gecisi guvenlik testleri."""

import shutil
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, V38, ROOT
from transaction_csv_baseline import capture_baseline
from transaction_lock import transaction_lock
from transaction_state import initialize, transition, load_state

NAMES = ("100.html", "171.html")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-recovered-state-"
    ) as tmp:

        base = Path(tmp)
        bundle = base / "bundle"
        live = base / "live"
        live.mkdir()

        entries = []

        for name in NAMES:
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

        csv_path = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            csv_path
        )

        lock = base / "transaction.lock"

        with transaction_lock(lock):
            capture_baseline(bundle, csv_path)

        initialize(bundle)

        state_path = bundle / "transaction-state.json"

        def recover():
            transition(
                bundle,
                "IN_PROGRESS",
                "RECOVERED",
                live_dir=live,
                csv_path=csv_path
            )

        def expect_rejected(label, exception=ValueError):
            original_state = state_path.read_bytes()
            try:
                recover()
            except exception:
                assert state_path.read_bytes() == original_state
                print(label)
            else:
                raise AssertionError(
                    "Guvenlik kontrolu atlandi: " + label
                )

        # TEST 1: PREPARED -> RECOVERED yasak.
        expect_rejected(
            "TEST 1 PASS: PREPARED -> RECOVERED reddedildi"
        )

        transition(bundle, "PREPARED", "IN_PROGRESS")

        # TEST 2: Bozuk HTML reddedilmeli.
        page = live / "100.html"
        original_html = page.read_bytes()
        page.write_bytes(original_html + b"\nTAMPER")

        expect_rejected(
            "TEST 2 PASS: Bozuk HTML reddedildi"
        )
        page.write_bytes(original_html)

        # TEST 3: Bozuk CSV reddedilmeli.
        original_csv = csv_path.read_bytes()
        csv_path.write_bytes(original_csv + b"\nTAMPER")

        expect_rejected(
            "TEST 3 PASS: Bozuk CSV reddedildi"
        )
        csv_path.write_bytes(original_csv)

        # TEST 4: Baska islem kilidi tutarken gecis yasak.
        with transaction_lock(lock):
            expect_rejected(
                "TEST 4 PASS: Kilit cakismasi engellendi",
                RuntimeError
            )

        # TEST 5: Parametre eksikse gecis yasak.
        before = state_path.read_bytes()

        try:
            transition(
                bundle,
                "IN_PROGRESS",
                "RECOVERED"
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Parametresiz RECOVERED kabul edildi"
            )

        assert state_path.read_bytes() == before
        print("TEST 5 PASS: Eksik dogrulama reddedildi")

        # TEST 6: Gecerli gecis.
        recover()
        assert load_state(state_path) == "RECOVERED"

        print("TEST 6 PASS: RECOVERED kaydedildi")

        # TEST 7: Son durum degistirilemez.
        before = state_path.read_bytes()

        try:
            transition(
                bundle,
                "RECOVERED",
                "IN_PROGRESS"
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "RECOVERED son durumu degistirildi"
            )

        assert state_path.read_bytes() == before

        print("TEST 7 PASS: RECOVERED son durumu korundu")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
