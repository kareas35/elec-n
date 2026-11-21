#!/usr/bin/env python3
"""V3.8 - API disi state yazma reddi."""
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_api import open_transaction
from transaction_state import _save_state, load_state


def rejected(action):
    try:
        action()
    except RuntimeError as exc:
        assert "Dogrudan state yazimi yasak" in str(exc)
        return
    raise AssertionError("Yetkisiz state yazimi kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-private-write-scope-"
    ) as tmp:
        root = Path(tmp)

        old = root / "old.html"
        new = root / "new.html"
        old.write_text("OLD", encoding="utf-8")
        new.write_text("NEW", encoding="utf-8")

        bundle = root / "bundle"
        create_bundle(bundle, [{
            "name": "100.html",
            "before": old,
            "after": new,
        }])

        state = bundle / "transaction-state.json"

        rejected(lambda: _save_state(state, "PREPARED"))
        assert not state.exists()
        print("TEST 1 PASS: Dogrudan initialize reddedildi")

        with open_transaction(bundle) as api:
            api.initialize()

        assert load_state(state) == "PREPARED"
        print("TEST 2 PASS: API initialize calisiyor")

        rejected(lambda: _save_state(
            state, "IN_PROGRESS", expected="PREPARED"
        ))
        assert load_state(state) == "PREPARED"
        print("TEST 3 PASS: Dogrudan transition reddedildi")

        from transaction_persistent_outcome import begin
        begin(bundle, "op-212-guarded")
        with open_transaction(bundle) as api:
            api.guarded_transition(
                "op-212-guarded", "PREPARED", "IN_PROGRESS"
            )

        assert load_state(state) == "IN_PROGRESS"
        print("TEST 4 PASS: API transition calisiyor")

        rejected(lambda: _save_state(
            state, "COMPLETED", expected="IN_PROGRESS"
        ))
        assert load_state(state) == "IN_PROGRESS"
        print("TEST 5 PASS: API sonrasi yazma kapsamı kapandi")

    print("\nSONUC: 5/5 TEST BASARILI")
    print("Dogrudan _save_state: TEST EDILEN YOLDA ENGELLENDI")
    print("TransactionAPI.transition intent zorunlulugu: HENUZ YOK")
    print("Python icinde mutlak yetki izolasyonu: YOK")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
