#!/usr/bin/env python3
"""V3.8 - Korumali TransactionAPI gecis testleri."""
import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_bundle import create_bundle
from transaction_persistent_outcome import begin, INTENT, RESULT
from transaction_state import load_state


def make_bundle(root, label):
    sources = root / ("sources-" + label)
    sources.mkdir()

    before = sources / "before.html"
    after = sources / "after.html"

    before.write_text("OLD", encoding="utf-8")
    after.write_text("NEW", encoding="utf-8")

    bundle = root / label
    create_bundle(bundle, [{
        "name": "100.html",
        "before": before,
        "after": after,
    }])

    with open_transaction(bundle) as api:
        api.initialize()

    return bundle


def run_guarded(bundle, operation_id):
    with open_transaction(bundle) as api:
        return api.guarded_transition(
            operation_id, "PREPARED", "IN_PROGRESS"
        )


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-guarded-transition-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: Intent olmadan gecis yasak.
        a = make_bundle(root, "missing")
        try:
            run_guarded(a, "op-182-a")
        except ValueError:
            pass
        else:
            raise AssertionError("Intent olmadan gecis kabul edildi")

        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 1 PASS: Intent eksik, state korunuyor")

        # TEST 2: Yanlis operation_id engellenir.
        b = make_bundle(root, "wrong")
        begin(b, "op-182-b")

        try:
            run_guarded(b, "wrong-id")
        except ValueError:
            pass
        else:
            raise AssertionError("Yanlis operation_id kabul edildi")

        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 2 PASS: Yanlis operation_id reddedildi")

        # TEST 3: Gecerli intent ile kilitli gecis.
        result = run_guarded(b, "op-182-b")

        assert result["status"] == "STATE_WRITE_ATTEMPTED"
        assert result["transaction_confirmed"] is False
        assert result["automatic_retry"] is False
        assert load_state(
            b / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 3 PASS: Korumali API state gecisi")

        # TEST 4: Tekrar ayni gecis reddedilir.
        try:
            run_guarded(b, "op-182-b")
        except ValueError:
            pass
        else:
            raise AssertionError("Tekrarlanan gecis kabul edildi")

        assert load_state(
            b / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 4 PASS: Tekrar gecis reddedildi")

        # TEST 5: Mevcut result kaydi engeller.
        c = make_bundle(root, "result-existing")
        begin(c, "op-182-c")
        (c / RESULT).write_text(
            "{}", encoding="utf-8"
        )

        try:
            run_guarded(c, "op-182-c")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Mevcut result kabul edildi")

        assert load_state(
            c / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 5 PASS: Onceki result gecisi engelledi")

        # TEST 6: Intent mevcut; otomatik sonuc yok.
        assert (b / INTENT).is_file()
        assert not (b / RESULT).exists()
        print("TEST 6 PASS: Otomatik result ve onay yok")

    print("\\nSONUC: 6/6 TEST BASARILI")
    print("guarded_transition: PROTOTIP")
    print("Eski transition giris noktasi: HENUZ ACIK")
    print("Dogrudan _save_state: HENUZ ACIK")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
