#!/usr/bin/env python3
"""V3.8 - Guarded transition ret nedeni ayrimi.

Yalnizca TemporaryDirectory kullanilir.
Gercek restorasyon, retry veya rollback YOK.
"""
import errno
import tempfile
from pathlib import Path
from unittest.mock import patch

from transaction_api import open_transaction
from transaction_bundle import create_bundle
from transaction_persistent_outcome import begin
from transaction_state import load_state

ATTEMPT = "transaction-guarded-attempt.json"


def prepare(root, name):
    source = root / ("sources-" + name)
    source.mkdir()

    before = source / "before.html"
    after = source / "after.html"
    before.write_text("OLD", encoding="utf-8")
    after.write_text("NEW", encoding="utf-8")

    bundle = root / name
    create_bundle(bundle, [{
        "name": "100.html",
        "before": before,
        "after": after,
    }])

    with open_transaction(bundle) as api:
        api.initialize()

    begin(bundle, "operation-187")
    return bundle


def transition(bundle):
    with open_transaction(bundle) as api:
        return api.guarded_transition(
            "operation-187",
            "PREPARED",
            "IN_PROGRESS",
        )


def expect_error(bundle, error_type, message):
    try:
        transition(bundle)
    except error_type as exc:
        assert message in str(exc), str(exc)
        return
    except Exception as exc:
        raise AssertionError(
            f"Yanlis ret nedeni: {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError("Beklenen ret gerceklesmedi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-guarded-rejection-"
    ) as tmp:
        root = Path(tmp)

        a = prepare(root, "io-error")

        # TEST 1: State yazimi oncesinde attempt yok.
        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        assert not (a / ATTEMPT).exists()
        print("TEST 1 PASS: Baslangic dogrulandi")

        # TEST 2: Attempt yayimlandiktan sonra state
        # yaziminda hata olusturuluyor.
        with patch(
            "transaction_api._save_state",
            side_effect=OSError(errno.EIO, "Injected error"),
        ):
            try:
                transition(a)
            except OSError as exc:
                assert exc.errno == errno.EIO
            else:
                raise AssertionError("EIO bekleniyordu")

        assert (a / ATTEMPT).is_file()
        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 2 PASS: Attempt var, state degismedi")

        # TEST 3: Ret dogrudan attempt kaynakli.
        expect_error(
            a,
            RuntimeError,
            "Onceki state girisimi mevcut",
        )
        print("TEST 3 PASS: RuntimeError attempt kaynakli")

        # TEST 4: Tekrar reddi state'i degistirmedi.
        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 4 PASS: Reddedilen girisim state'i korudu")

        # TEST 5: Basarili gecis farkli state olusturur.
        b = prepare(root, "successful")
        result = transition(b)

        assert result["transaction_confirmed"] is False
        assert (b / ATTEMPT).is_file()
        assert load_state(
            b / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 5 PASS: Basarili state gecisi")

        # TEST 6: State farki nedeniyle ValueError.
        expect_error(
            b,
            ValueError,
            "Beklenmeyen onceki state",
        )
        print("TEST 6 PASS: ValueError state kaynakli")

        # TEST 7: Her iki durumda da onay yok.
        for bundle in (a, b):
            assert not (
                bundle / "transaction-outcome-result.json"
            ).exists()

        print("TEST 7 PASS: Otomatik result/onay uretilmedi")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Attempt kaynakli ret: AYRI DOGRULANDI")
    print("State kaynakli ret: AYRI DOGRULANDI")
    print("Eski API bypass yollari: HENUZ ACIK")
    print("Guc kaybi durability: KANITLANMADI")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
