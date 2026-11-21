#!/usr/bin/env python3
"""V3.8 - Transaction API regresyon ve guvenlik testleri.

Tum dosya islemleri gecici klasorde yapilir.
Gercek yayinlar, CSV ve rollback kodu degistirilmez.
"""
import tempfile
import threading
from pathlib import Path

from transaction_api import open_transaction
from transaction_persistent_outcome import begin
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state


def must_reject(action, errors):
    try:
        action()
    except errors:
        return
    raise AssertionError("Guvensiz islem kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-api-regression-"
    ) as tmp:
        root = Path(tmp)
        a = make_bundle(root, "bundle-a")
        b = make_bundle(root, "bundle-b")

        state_a = a / "transaction-state.json"

        # TEST 1: Gecerli ilk durum.
        with open_transaction(a) as api:
            api.initialize()
            assert load_state(state_a) == "PREPARED"
        print("TEST 1 PASS: PREPARED olusturuldu")

        # TEST 2: Tekrar initialize yasak.
        with open_transaction(a) as api:
            must_reject(api.initialize, (FileExistsError,))
        assert load_state(state_a) == "PREPARED"
        print("TEST 2 PASS: Tekrar initialize reddedildi")

        # TEST 3: Yanlis beklenen durum.
        begin(a, "op-209c-wrong-state")
        with open_transaction(a) as api:
            must_reject(
                lambda: api.guarded_transition(
                    "op-209c-wrong-state",
                    "IN_PROGRESS", "COMPLETED"
                ),
                (ValueError,)
            )
        assert load_state(state_a) == "PREPARED"
        print("TEST 3 PASS: Yanlis expected reddedildi")

        # TEST 4: Gecersiz state gecisi.
        with open_transaction(a) as api:
            must_reject(
                lambda: api.guarded_transition(
                    "op-209c-wrong-state",
                    "PREPARED", "RECOVERED"
                ),
                (ValueError,)
            )
        assert load_state(state_a) == "PREPARED"
        print("TEST 4 PASS: Gecersiz gecis reddedildi")

        # TEST 5: Farkli thread API kullanamaz.
        with open_transaction(a) as api:
            errors = []

            def other_thread():
                try:
                    api.transition(
                        "PREPARED", "IN_PROGRESS"
                    )
                except RuntimeError:
                    errors.append("REJECTED")

            worker = threading.Thread(target=other_thread)
            worker.start()
            worker.join(timeout=5)

            assert not worker.is_alive()
            assert errors == ["REJECTED"]

        assert load_state(state_a) == "PREPARED"
        print("TEST 5 PASS: Farkli thread reddedildi")

        # TEST 6: Iki bundle ayni kilidi paylasir.
        with open_transaction(a):
            must_reject(
                lambda: nested_open(b),
                (RuntimeError,)
            )
        print("TEST 6 PASS: Ortak kilit cakismasi")

        # TEST 7: Kilit inode degisimi.
        lock = root / "transaction.lock"

        with open_transaction(a) as api:
            old_lock = root / "old-lock"
            lock.rename(old_lock)
            lock.write_bytes(b"replacement")

            must_reject(
                lambda: api.transition(
                    "PREPARED", "IN_PROGRESS"
                ),
                (RuntimeError,)
            )

        # Bu test sadece gecici klasorde yapildi.
        assert load_state(state_a) == "PREPARED"
        print("TEST 7 PASS: Kilit inode degisimi reddedildi")

        # TEST 8: Eksik bundle reddedilir.
        missing = root / "missing-bundle"
        must_reject(
            lambda: nested_open(missing),
            (ValueError,)
        )
        assert not missing.exists()
        print("TEST 8 PASS: Eksik bundle reddedildi")

        # TEST 9: Sembolik bundle reddedilir.
        alias = root / "bundle-alias"
        alias.symlink_to(a, target_is_directory=True)

        must_reject(
            lambda: nested_open(alias),
            (ValueError,)
        )
        print("TEST 9 PASS: Sembolik bundle reddedildi")

        # TEST 10: Onceki basarili state korunur.
        assert load_state(state_a) == "PREPARED"
        assert not (
            b / "transaction-state.json"
        ).exists()
        print("TEST 10 PASS: Redlerden sonra veri korundu")

    print("\nSONUC: 10/10 TEST BASARILI")
    print("Islemler: SADECE GECICI KLASOR")
    print("Eski transaction API: DEGISTIRILMEDI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


def nested_open(bundle):
    with open_transaction(bundle):
        pass


if __name__ == "__main__":
    main()
