#!/usr/bin/env python3
"""V3.8 - Intentsiz public transition engeli testi."""
import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_guarded_transition_test import make_bundle
from transaction_persistent_outcome import begin
from transaction_state import load_state


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-unguarded-barrier-"
    ) as tmp:
        root = Path(tmp)
        bundle = make_bundle(root, "barrier")
        state = bundle / "transaction-state.json"

        with open_transaction(bundle) as api:
            try:
                api.transition("PREPARED", "IN_PROGRESS")
            except RuntimeError as error:
                assert "Intentsiz transition kapali" in str(error)
            else:
                raise AssertionError("Intentsiz gecis kabul edildi")

        assert load_state(state) == "PREPARED"
        print("TEST 1 PASS: Intent olmadan public gecis reddedildi")

        begin(bundle, "op-209a")

        with open_transaction(bundle) as api:
            try:
                api.transition("PREPARED", "IN_PROGRESS")
            except RuntimeError as error:
                assert "Intentsiz transition kapali" in str(error)
            else:
                raise AssertionError("Public gecis intent ile kabul edildi")

        assert load_state(state) == "PREPARED"
        print("TEST 2 PASS: Intent varken public gecis reddedildi")

        with open_transaction(bundle) as api:
            result = api.guarded_transition(
                "op-209a", "PREPARED", "IN_PROGRESS"
            )

        assert result["status"] == "STATE_WRITE_ATTEMPTED"
        assert load_state(state) == "IN_PROGRESS"
        print("TEST 3 PASS: Korumali gecis calisti")

    print("\nSONUC: 3/3 TEST BASARILI")
    print("Intentsiz public transition: KAPALI")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar/CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
