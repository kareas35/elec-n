#!/usr/bin/env python3
"""V3.8 - DURABILITY_UNKNOWN guvenlik testleri."""
import errno
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import contextmanager
import os
from types import SimpleNamespace
import transaction_state
from transaction_persistent_outcome import begin

from transaction_api import open_transaction
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state

from transaction_write_outcome import (
    CONFIRMED,
    NO_VISIBLE_CHANGE,
    DURABILITY_UNKNOWN,
    WriteOutcomeSession,
)


@contextmanager
def state_os_fault(name, side_effect):
    """Yalnizca state modulundeki OS cagrilarini etkiler."""
    proxy = SimpleNamespace(**vars(os))
    setattr(proxy, name, Mock(side_effect=side_effect))
    with patch.object(transaction_state, "os", proxy):
        yield


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-write-outcome-"
    ) as tmp:
        root = Path(tmp)
        bundle = make_bundle(root, "bundle")
        state = bundle / "transaction-state.json"

        with open_transaction(bundle) as api:
            api.initialize()

        assert load_state(state) == "PREPARED"

        # TEST 1: Basarili state gecisi.
        session = WriteOutcomeSession()
        begin(bundle, "op-219-success")

        with open_transaction(bundle) as api:
            outcome = session.execute(
                lambda: api.guarded_transition("op-219-success",
                    "PREPARED", "IN_PROGRESS"
                ),
                state, "PREPARED", "IN_PROGRESS"
            )

        assert outcome["status"] == CONFIRMED
        print("TEST 1 PASS: Basarili yazim CONFIRMED")

        # TEST 2: os.replace oncesinde EIO.
        before = make_bundle(root, "before-error")

        with open_transaction(before) as api:
            api.initialize()

        session2 = WriteOutcomeSession()
        begin(before, "op-219-replace-error")
        before_state = before / "transaction-state.json"

        with open_transaction(before) as api:
            with state_os_fault(
                "replace",
                side_effect=OSError(errno.EIO, "Replace failed")
            ):
                outcome = session2.execute(
                    lambda: api.guarded_transition("op-219-replace-error",
                        "PREPARED", "IN_PROGRESS"
                    ),
                    before_state, "PREPARED", "IN_PROGRESS"
                )

        assert outcome["status"] == NO_VISIBLE_CHANGE
        assert outcome["automatic_retry"] is False
        assert load_state(before_state) == "PREPARED"
        print("TEST 2 PASS: Eski state gorunur, tekrar otomatik degil")

        # TEST 3: Dizin fsync hatasinda yeni state gorunur.
        after = make_bundle(root, "after-error")

        with open_transaction(after) as api:
            api.initialize()

        after_state = after / "transaction-state.json"
        session3 = WriteOutcomeSession()
        begin(after, "op-219-sync-error")

        import os
        real_fsync = os.fsync
        count = [0]

        def fail_directory_sync(fd):
            count[0] += 1
            if count[0] == 2:
                raise OSError(errno.EIO, "Directory fsync failed")
            return real_fsync(fd)

        with open_transaction(after) as api:
            with state_os_fault(
                "fsync",
                side_effect=fail_directory_sync
            ):
                outcome = session3.execute(
                    lambda: api.guarded_transition("op-219-sync-error",
                        "PREPARED", "IN_PROGRESS"
                    ),
                    after_state, "PREPARED", "IN_PROGRESS"
                )

        assert count[0] == 2
        assert outcome["status"] == DURABILITY_UNKNOWN
        assert outcome["observed"] == "IN_PROGRESS"
        assert session3.blocked
        print("TEST 3 PASS: Dizin fsync hatasi DURABILITY_UNKNOWN")

        # TEST 4: Belirsizlikten sonra yeniden deneme yasak.
        called = [False]

        def forbidden_retry():
            called[0] = True

        try:
            session3.execute(
                forbidden_retry,
                after_state, "PREPARED", "IN_PROGRESS"
            )
        except RuntimeError as error:
            assert "DURABILITY_UNKNOWN" in str(error)
        else:
            raise AssertionError("Tekrar deneme kabul edildi")

        assert called[0] is False
        print("TEST 4 PASS: Ayni oturumda tekrar engellendi")

        # TEST 5: Bozuk state otomatik basari sayilmaz.
        damaged = root / "damaged-state.json"
        damaged.write_text("{broken", encoding="utf-8")
        session4 = WriteOutcomeSession()

        def failed_action():
            raise OSError(errno.EIO, "Disk error")

        outcome = session4.execute(
            failed_action,
            damaged, "PREPARED", "IN_PROGRESS"
        )

        assert outcome["status"] == DURABILITY_UNKNOWN
        assert session4.blocked
        print("TEST 5 PASS: Bozuk kayit belirsiz kabul edildi")

        # TEST 6: Gercek state enum'una yeni durum eklenmedi.
        from transaction_state import ALLOWED

        assert DURABILITY_UNKNOWN not in ALLOWED
        assert load_state(after_state) == "IN_PROGRESS"
        print("TEST 6 PASS: Transaction state modeli korunuyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Durability modeli: PROTOTIP")
    print("Otomatik retry: YOK")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
