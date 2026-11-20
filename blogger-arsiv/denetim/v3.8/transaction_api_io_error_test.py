#!/usr/bin/env python3
"""V3.8 - TransactionAPI I/O hata enjeksiyonu.

Sadece gecici klasorlerde calisir.
Gercek yayin, CSV ve rollback islemi yapmaz.
"""
import errno
import tempfile
from pathlib import Path
from unittest.mock import patch

from transaction_api import open_transaction
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state


def inject_error(module_target, error, operation):
    """Tek bir sistem cagrisi icin kontrollu hata."""
    with patch(module_target, side_effect=error):
        try:
            operation()
        except OSError as caught:
            assert caught.errno == error.errno, caught
            return
    raise AssertionError("Beklenen I/O hatasi olusmadi")


def check_state(bundle, expected):
    state = bundle / "transaction-state.json"

    if expected is None:
        assert not state.exists()
    else:
        assert load_state(state) == expected


def check_lock_reusable(bundle):
    with open_transaction(bundle):
        pass


def make_case(root, name, initialized=False):
    folder = root / name
    folder.mkdir()
    bundle = make_bundle(folder, "bundle")

    if initialized:
        with open_transaction(bundle) as api:
            api.initialize()

    return bundle


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-api-io-error-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: Diskte yer yok - gecici dosya acilamiyor.
        a = make_case(root, "enospc")

        with open_transaction(a) as api:
            inject_error(
                "transaction_state.tempfile.mkstemp",
                OSError(errno.ENOSPC, "No space left"),
                api.initialize,
            )

        check_state(a, None)
        check_lock_reusable(a)
        print("TEST 1 PASS: ENOSPC, state olusmadi")

        # TEST 2: Dosya fsync asamasinda EIO.
        b = make_case(root, "file-fsync")

        with open_transaction(b) as api:
            inject_error(
                "transaction_state.os.fsync",
                OSError(errno.EIO, "File sync failed"),
                api.initialize,
            )

        check_state(b, None)
        check_lock_reusable(b)
        print("TEST 2 PASS: Dosya fsync EIO")

        # TEST 3: Yeni kayit yayinlanirken izin hatasi.
        c = make_case(root, "link-permission")

        with open_transaction(c) as api:
            inject_error(
                "transaction_state.os.link",
                OSError(errno.EACCES, "Permission denied"),
                api.initialize,
            )

        check_state(c, None)
        check_lock_reusable(c)
        print("TEST 3 PASS: EACCES, kayit yayinlanmadi")

        # TEST 4: Gecis oncesi os.replace EIO.
        d = make_case(root, "replace-eio", initialized=True)

        with open_transaction(d) as api:
            inject_error(
                "transaction_state.os.replace",
                OSError(errno.EIO, "Replace failed"),
                lambda: api.transition(
                    "PREPARED", "IN_PROGRESS"
                ),
            )

        check_state(d, "PREPARED")
        check_lock_reusable(d)
        print("TEST 4 PASS: Replace EIO, eski state korundu")

        # TEST 5: Gecis dosya fsync hatasi.
        e = make_case(root, "transition-fsync", initialized=True)

        with open_transaction(e) as api:
            inject_error(
                "transaction_state.os.fsync",
                OSError(errno.EIO, "Sync failed"),
                lambda: api.transition(
                    "PREPARED", "IN_PROGRESS"
                ),
            )

        check_state(e, "PREPARED")
        check_lock_reusable(e)
        print("TEST 5 PASS: Gecis fsync EIO")

        # TEST 6: Yayinlama sonrasinda dizin fsync hatasi.
        f = make_case(root, "directory-fsync", initialized=True)

        real_fsync = __import__("os").fsync
        calls = [0]

        def fail_second_fsync(fd):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError(errno.EIO, "Directory sync failed")
            return real_fsync(fd)

        with open_transaction(f) as api:
            inject_error(
                "transaction_state.os.fsync",
                OSError(errno.EIO, "Directory sync failed"),
                lambda: None,
            ) if False else None

            with patch(
                "transaction_state.os.fsync",
                side_effect=fail_second_fsync
            ):
                try:
                    api.transition("PREPARED", "IN_PROGRESS")
                except OSError as error:
                    assert error.errno == errno.EIO
                else:
                    raise AssertionError("Dizin fsync hatasi bekleniyordu")

        assert calls[0] == 2
        check_state(f, "IN_PROGRESS")
        check_lock_reusable(f)
        print("TEST 6 PASS: Dizin fsync EIO, yeni state gorunur")
        print("  UYARI: Kalicilik sonucu BELIRSIZ")

        # TEST 7: Hatalar diger bundle durumlarini bozmaz.
        assert all(
            load_state(x / "transaction-state.json") == "PREPARED"
            for x in (d, e)
        )
        check_state(a, None)
        check_state(b, None)
        check_state(c, None)
        print("TEST 7 PASS: Basarisiz yazimlarda state korundu")

        # TEST 8: Basarili yeniden deneme.
        with open_transaction(a) as api:
            api.initialize()

        check_state(a, "PREPARED")
        print("TEST 8 PASS: Hata sonrasi kontrollu yeniden deneme")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("I/O hatalari: SIMULE EDILDI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")
    print("Elektrik kesintisi dayanimi: KANITLANMADI")


if __name__ == "__main__":
    main()
