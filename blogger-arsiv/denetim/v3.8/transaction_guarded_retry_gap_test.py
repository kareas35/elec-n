#!/usr/bin/env python3
"""V3.8 - Intent tekrar kullanimini engelleme testi.

Yalnizca gecici dosyalar. Gercek rollback/restorasyon YOK.
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


def setup(root, name):
    src = root / ("sources-" + name)
    src.mkdir()
    old = src / "old.html"
    new = src / "new.html"
    old.write_text("OLD", encoding="utf-8")
    new.write_text("NEW", encoding="utf-8")

    bundle = root / name
    create_bundle(bundle, [{
        "name": "100.html",
        "before": old,
        "after": new,
    }])

    with open_transaction(bundle) as api:
        api.initialize()

    begin(bundle, "operation-185")
    return bundle


def transition(bundle):
    with open_transaction(bundle) as api:
        return api.guarded_transition(
            "operation-185", "PREPARED", "IN_PROGRESS"
        )


def reject_retry(bundle):
    try:
        transition(bundle)
    except (RuntimeError, ValueError):
        return
    raise AssertionError("Tekrar girisim kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-intent-reuse-fix-"
    ) as tmp:
        root = Path(tmp)
        a = setup(root, "io-failure")

        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        assert not (a / ATTEMPT).exists()
        print("TEST 1 PASS: Baslangic durumu")

        with patch(
            "transaction_api._save_state",
            side_effect=OSError(errno.EIO, "Injected I/O error"),
        ):
            try:
                transition(a)
            except OSError as exc:
                assert exc.errno == errno.EIO
            else:
                raise AssertionError("I/O hatasi bekleniyordu")

        assert (a / ATTEMPT).is_file()
        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 2 PASS: Hata sonrasi attempt kalici kayitli")

        reject_retry(a)
        assert load_state(
            a / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 3 PASS: Ayni intent ikinci kez kullanilamadi")

        b = setup(root, "normal-transition")
        result = transition(b)

        assert result["transaction_confirmed"] is False
        assert result["automatic_retry"] is False
        assert load_state(
            b / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 4 PASS: Normal korumali gecis")

        reject_retry(b)
        assert (b / ATTEMPT).is_file()
        print("TEST 5 PASS: Basarili gecis sonrasi tekrar engelli")

        c = setup(root, "attempt-write-failure")

        with patch(
            "transaction_journal.atomic_json_write",
            side_effect=OSError(errno.ENOSPC, "Disk full"),
        ):
            try:
                transition(c)
            except OSError as exc:
                assert exc.errno == errno.ENOSPC
            else:
                raise AssertionError("ENOSPC bekleniyordu")

        assert load_state(
            c / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 6 PASS: Attempt yazilamazsa state korunuyor")

        from transaction_journal import atomic_json_write

        d = setup(root, "publish-then-error")

        def publish_then_fail(path, data):
            atomic_json_write(path, data)
            raise OSError(errno.EIO, "Uncertain write")

        with patch(
            "transaction_journal.atomic_json_write",
            side_effect=publish_then_fail,
        ):
            try:
                transition(d)
            except OSError:
                pass
            else:
                raise AssertionError("Hata bekleniyordu")

        assert (d / ATTEMPT).is_file()
        reject_retry(d)
        assert load_state(
            d / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 7 PASS: Belirsiz yazim sonrasi tekrar engelli")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Intent tekrar kullanimi: TEST EDILEN YOLLARDA ENGELLENDI")
    print("Eski API bypass yollari: HENUZ ACIK")
    print("Guc kaybi durability garantisi: KANITLANMADI")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar/CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
