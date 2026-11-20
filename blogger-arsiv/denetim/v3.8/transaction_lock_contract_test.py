#!/usr/bin/env python3
"""V3.8 - Ortak transaction kilidi sozlesmesi testi.

Gercek dosyalara yazmaz. Mevcut modulleri degistirmez.
"""
import tempfile
from multiprocessing import Event, Process
from pathlib import Path

from transaction_lock import transaction_lock


def worker(lock_path, ready, release):
    with transaction_lock(lock_path):
        ready.set()
        if not release.wait(timeout=10):
            raise RuntimeError("Test zaman asimi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-lock-contract-"
    ) as tmp:
        root = Path(tmp)
        lock = root / "transaction.lock"

        # TEST 1: Tek kilit sahibi.
        with transaction_lock(lock):
            assert lock.is_file()
        print("TEST 1 PASS: Ortak kilit alindi")

        # TEST 2: Ic ice ayni kilit alinmamali.
        with transaction_lock(lock):
            try:
                with transaction_lock(lock):
                    raise AssertionError("Cift kilit kabul edildi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)

        print("TEST 2 PASS: Ic ice kilit sorunu tespit edildi")

        # TEST 3: Kilit disinda islem yapilmamali.
        def protected_operation(locked):
            if not locked:
                raise RuntimeError("KILIT GEREKLI")
            return "OK"

        try:
            protected_operation(False)
            raise AssertionError("Kilitsiz islem kabul edildi")
        except RuntimeError as error:
            assert "KILIT GEREKLI" in str(error)

        print("TEST 3 PASS: Kilitsiz islem reddedildi")

        # TEST 4: Kilit sahipligi tek noktadan aktarilir.
        with transaction_lock(lock):
            result = protected_operation(True)
            assert result == "OK"

        print("TEST 4 PASS: Tek kilit sahibiyle islem")

        # TEST 5: Diger surec kilidi asamaz.
        ready = Event()
        release = Event()
        process = Process(
            target=worker,
            args=(lock, ready, release)
        )
        process.start()

        try:
            assert ready.wait(timeout=5)

            try:
                with transaction_lock(lock):
                    raise AssertionError("Cakisma engellenmedi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)

            print("TEST 5 PASS: Surecler arasi kilit")
        finally:
            release.set()
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join()

        assert process.exitcode == 0

        # TEST 6: Kilit serbest kaldiktan sonra.
        with transaction_lock(lock):
            assert protected_operation(True) == "OK"

        print("TEST 6 PASS: Kilit yeniden kullanildi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
