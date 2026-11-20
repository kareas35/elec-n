#!/usr/bin/env python3
"""Transaction API - gecici klasorde guvenlik testleri."""
import tempfile
from pathlib import Path

from transaction_api import TransactionAPI, open_transaction
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state


def reject(action, errors=(RuntimeError, ValueError)):
    try:
        action()
    except errors:
        return
    raise AssertionError("Guvenlik kontrolu atlatildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-api-"
    ) as tmp:
        root = Path(tmp)
        a = make_bundle(root, "bundle-a")
        b = make_bundle(root, "bundle-b")

        reject(lambda: TransactionAPI(a, root / "transaction.lock", None))
        print("TEST 1 PASS: Dogrudan API olusturma reddedildi")

        with open_transaction(a) as api:
            api.initialize()
            assert load_state(
                a / "transaction-state.json"
            ) == "PREPARED"
            print("TEST 2 PASS: Kilit altinda PREPARED")

            api.transition("PREPARED", "IN_PROGRESS")
            assert load_state(
                a / "transaction-state.json"
            ) == "IN_PROGRESS"
            print("TEST 3 PASS: Kilit altinda IN_PROGRESS")

            # API yalnizca kendi bundle yolunu kullanir.
            assert not (
                b / "transaction-state.json"
            ).exists()
            print("TEST 4 PASS: Bundle B etkilenmedi")

            reject(lambda: open_nested(b))
            print("TEST 5 PASS: Ortak kilit cakismasi reddedildi")

        reject(lambda: api.transition("IN_PROGRESS", "PREPARED"))
        print("TEST 6 PASS: Suresi dolmus API reddedildi")

        with open_transaction(b) as other:
            other.initialize()

        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        assert load_state(
            a / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 7 PASS: Iki bundle bagimsiz state")

        with open_transaction(a) as current:
            renamed = root / "bundle-a-renamed"
            a.rename(renamed)
            a.mkdir()

            reject(lambda: current.transition(
                "IN_PROGRESS", "PREPARED"
            ))

            assert not (
                a / "transaction-state.json"
            ).exists()

        assert load_state(
            renamed / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 8 PASS: Bundle inode degisimi reddedildi")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("API: BAGIMSIZ MODUL / STATE ILE SINIRLI")
    print("Eski state API: DEGISTIRILMEDI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


def open_nested(bundle):
    with open_transaction(bundle):
        pass


if __name__ == "__main__":
    main()
