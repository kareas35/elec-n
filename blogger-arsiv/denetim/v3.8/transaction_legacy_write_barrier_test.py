#!/usr/bin/env python3
"""V3.8 - Eski public state yazma girisi engelleme testi."""
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_api import open_transaction
from transaction_state import (
    initialize, transition, save_state, load_state
)


def rejected(action):
    try:
        action()
    except RuntimeError as exc:
        assert "Legacy save_state kapali" in str(exc), str(exc)
        return
    raise AssertionError("Legacy state yazimi kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-legacy-write-barrier-"
    ) as tmp:
        root = Path(tmp)

        before = root / "before.html"
        after = root / "after.html"
        before.write_text("OLD", encoding="utf-8")
        after.write_text("NEW", encoding="utf-8")

        bundle = root / "bundle"
        create_bundle(bundle, [{
            "name": "100.html",
            "before": before,
            "after": after,
        }])

        state = bundle / "transaction-state.json"

        rejected(lambda: initialize(bundle))
        assert not state.exists()
        print("TEST 1 PASS: Legacy initialize engellendi")

        rejected(lambda: save_state(state, "PREPARED"))
        assert not state.exists()
        print("TEST 2 PASS: Dogrudan save_state engellendi")

        with open_transaction(bundle) as api:
            api.initialize()

        assert load_state(state) == "PREPARED"
        print("TEST 3 PASS: TransactionAPI initialize calisiyor")

        rejected(
            lambda: transition(bundle, "PREPARED", "IN_PROGRESS")
        )

        assert load_state(state) == "PREPARED"
        print("TEST 4 PASS: Legacy transition engellendi")

        rejected(
            lambda: save_state(
                state, "IN_PROGRESS", expected="PREPARED"
            )
        )

        assert load_state(state) == "PREPARED"
        print("TEST 5 PASS: Legacy state degisimi engellendi")

        with open_transaction(bundle) as api:
            api.transition("PREPARED", "IN_PROGRESS")

        assert load_state(state) == "IN_PROGRESS"
        print("TEST 6 PASS: TransactionAPI transition calisiyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Legacy public save_state: KAPATILDI")
    print("Dogrudan _save_state: HENUZ ACIK")
    print("Eski testler icin uyumluluk: INCELEME GEREKLI")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
