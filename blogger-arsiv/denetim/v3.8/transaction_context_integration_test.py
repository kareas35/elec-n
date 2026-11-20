#!/usr/bin/env python3
"""V3.8 - TransactionContext ile state entegrasyon prototipi.

Yalnizca gecici klasorde calisir.
Mevcut transaction modullerini degistirmez.
"""
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import (
    create_bundle, verify_bundle, V38, ROOT
)
from transaction_context_test import transaction_context
from transaction_csv_baseline import capture_baseline
from transaction_state import _save_state, load_state

NAMES = ("100.html", "171.html")


def guarded_transition(ctx, bundle, expected, target,
                       live_dir=None, csv_path=None):
    """Tek kilit sahibinin korudugu prototip state gecisi."""
    ctx.require_active()

    bundle = Path(bundle)

    required_lock = (
        bundle.parent / "transaction.lock"
    ).resolve()

    if ctx.lock_path.resolve() != required_lock:
        raise ValueError("Context farkli transaction'a ait")

    verify_bundle(bundle)

    return _save_state(
        bundle / "transaction-state.json",
        target,
        expected=expected,
        live_dir=live_dir,
        csv_path=csv_path
    )


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-context-integration-"
    ) as tmp:
        root = Path(tmp)
        bundle = root / "bundle"
        live = root / "live"
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

        plan = root / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        lock = root / "transaction.lock"

        with transaction_context(lock) as ctx:
            create_bundle(bundle, entries)
            capture_baseline(bundle, plan)

            guarded_transition(ctx, bundle, None, "PREPARED")
            state = bundle / "transaction-state.json"

            assert load_state(state) == "PREPARED"
            print("TEST 1 PASS: Kilit altinda PREPARED")

            guarded_transition(
                ctx, bundle, "PREPARED", "IN_PROGRESS"
            )
            assert load_state(state) == "IN_PROGRESS"
            print("TEST 2 PASS: Kilit altinda IN_PROGRESS")

            # HTML bozulursa RECOVERED yasak.
            page = live / "100.html"
            original_html = page.read_bytes()
            page.write_bytes(original_html + b"\nTAMPER")

            try:
                guarded_transition(
                    ctx, bundle, "IN_PROGRESS", "RECOVERED",
                    live_dir=live, csv_path=plan
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Bozuk HTML kabul edildi")

            assert load_state(state) == "IN_PROGRESS"
            page.write_bytes(original_html)
            print("TEST 3 PASS: Bozuk HTML reddedildi")

            # CSV bozulursa RECOVERED yasak.
            original_csv = plan.read_bytes()
            plan.write_bytes(original_csv + b"\nTAMPER")

            try:
                guarded_transition(
                    ctx, bundle, "IN_PROGRESS", "RECOVERED",
                    live_dir=live, csv_path=plan
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Bozuk CSV kabul edildi")

            assert load_state(state) == "IN_PROGRESS"
            plan.write_bytes(original_csv)
            print("TEST 4 PASS: Bozuk CSV reddedildi")

            # Yanlis bundle ile context kullanilamaz.
            try:
                guarded_transition(
                    ctx, root / "other_parent" / "bundle", "IN_PROGRESS",
                    "RECOVERED", live_dir=live, csv_path=plan
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Yanlis bundle kabul edildi")

            print("TEST 5 PASS: Context kapsam kontrolu")

            # Kilit zaten alindi; ikinci kez alinmaz.
            guarded_transition(
                ctx, bundle, "IN_PROGRESS", "RECOVERED",
                live_dir=live, csv_path=plan
            )

            assert load_state(state) == "RECOVERED"
            print("TEST 6 PASS: Tek kilitle RECOVERED")

            # Son durum degistirilemez.
            try:
                guarded_transition(
                    ctx, bundle, "RECOVERED", "IN_PROGRESS"
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Son durum degistirildi")

            print("TEST 7 PASS: Son durum korundu")

        # Kilit birakilinca eski context calismamali.
        try:
            guarded_transition(
                ctx, bundle, "RECOVERED", "IN_PROGRESS"
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Eski context kabul edildi")

        assert load_state(state) == "RECOVERED"
        print("TEST 8 PASS: Eski context reddedildi")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
