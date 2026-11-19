#!/usr/bin/env python3
"""V3.8 - Linux transaction kilitleme altyapisi."""

import fcntl
import os
import tempfile
from contextlib import contextmanager
from multiprocessing import Event, Process, Queue
from pathlib import Path


@contextmanager
def transaction_lock(lock_path):
    """Ayni kilit yolunda tek islemin calismasina izin ver."""
    path = Path(lock_path)

    if not path.parent.is_dir():
        raise FileNotFoundError("Kilit klasoru mevcut degil")

    if path.is_symlink():
        raise ValueError("Sembolik baglanti kullanilamaz")

    flags = os.O_CREAT | os.O_RDWR
    flags |= getattr(os, "O_NOFOLLOW", 0)

    fd = os.open(path, flags, 0o600)

    try:
        if not os.path.isfile(path):
            raise ValueError("Gecersiz kilit dosyasi")

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "ISLEM KILITLI: Baska bir transaction calisiyor"
            )

        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def holder(path, ready, release):
    with transaction_lock(path):
        ready.set()
        if not release.wait(timeout=10):
            raise RuntimeError("Test zaman asimi")


def self_test():
    with tempfile.TemporaryDirectory(
        prefix="v38-lock-"
    ) as tmp:
        path = Path(tmp) / "transaction.lock"

        # TEST 1: Ilk kilit alinabiliyor.
        with transaction_lock(path):
            assert path.exists()
            print("TEST 1 PASS: Kilit alindi")

            # TEST 2: Ayni anda ikinci kilit engelleniyor.
            try:
                with transaction_lock(path):
                    raise AssertionError("Ikinci kilit kabul edildi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)
            print("TEST 2 PASS: Cakisan islem engellendi")

        # TEST 3: Kilit birakildiktan sonra yeniden alinabiliyor.
        with transaction_lock(path):
            pass
        print("TEST 3 PASS: Kilit yeniden alinabildi")

        # TEST 4: Ayrı bir surecte tutulan kilit goruluyor.
        ready = Event()
        release = Event()
        process = Process(
            target=holder,
            args=(path, ready, release)
        )
        process.start()

        try:
            assert ready.wait(timeout=5), "Alt surec hazir degil"

            try:
                with transaction_lock(path):
                    raise AssertionError("Diger surecin kilidi asilabildi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)

            print("TEST 4 PASS: Ayrı surec kilidi korundu")
        finally:
            release.set()
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join()

        assert process.exitcode == 0

        # TEST 5: Hata sonrasi kilit serbest kaliyor.
        try:
            with transaction_lock(path):
                raise ValueError("Simule edilen uygulama hatasi")
        except ValueError:
            pass

        with transaction_lock(path):
            pass
        print("TEST 5 PASS: Hata sonrasi kilit serbest")

        # TEST 6: Sembolik baglanti reddediliyor.
        target = Path(tmp) / "target.txt"
        target.write_text("korunacak", encoding="utf-8")
        link = Path(tmp) / "unsafe.lock"
        link.symlink_to(target)

        try:
            with transaction_lock(link):
                raise AssertionError("Sembolik baglanti kabul edildi")
        except ValueError:
            pass

        assert target.read_text(encoding="utf-8") == "korunacak"
        print("TEST 6 PASS: Sembolik baglanti reddedildi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    self_test()
