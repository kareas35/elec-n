#!/usr/bin/env python3
"""V3.8 - TransactionContext kilit sahipligi prototipi.

Gercek yayinlari veya CSV'yi degistirmez.
"""
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from transaction_lock import transaction_lock


class TransactionContext:
    """Yalnizca aktif kilit kapsami icinde kullanilan baglam."""

    def __init__(self, lock_path, secret):
        if secret is not _TOKEN:
            raise RuntimeError("Baglam dogrudan olusturulamaz")
        self.lock_path = Path(lock_path)
        self.owner_pid = os.getpid()
        self.owner_thread = threading.get_ident()
        self._active = True

    def require_active(self):
        if not self._active:
            raise RuntimeError("TransactionContext suresi dolmus")

        if os.getpid() != self.owner_pid:
            raise RuntimeError("Farkli surec baglami kullanamaz")

        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("Farkli thread baglami kullanamaz")

        return True

    def invalidate(self):
        self._active = False


_TOKEN = object()


@contextmanager
def transaction_context(lock_path):
    """Kilit kapsamindan cikilinca baglami gecersiz kil."""
    with transaction_lock(lock_path):
        ctx = TransactionContext(lock_path, _TOKEN)
        try:
            yield ctx
        finally:
            ctx.invalidate()


def protected_operation(ctx):
    if not isinstance(ctx, TransactionContext):
        raise RuntimeError("TransactionContext gerekli")

    ctx.require_active()
    return "OK"


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-context-"
    ) as tmp:
        lock = Path(tmp) / "transaction.lock"

        # TEST 1: Kilit altinda gecerli baglam.
        with transaction_context(lock) as ctx:
            assert protected_operation(ctx) == "OK"
        print("TEST 1 PASS: Gecerli context")

        # TEST 2: Kilit birakildiktan sonra eski baglam.
        try:
            protected_operation(ctx)
            raise AssertionError("Eski context kabul edildi")
        except RuntimeError:
            pass
        print("TEST 2 PASS: Suresi dolmus context reddedildi")

        # TEST 3: Sahte parametre.
        try:
            protected_operation(True)
            raise AssertionError("Sahte sahiplik kabul edildi")
        except RuntimeError:
            pass
        print("TEST 3 PASS: locked=True reddedildi")

        # TEST 4: Dogrudan context olusturma.
        try:
            TransactionContext(lock, None)
            raise AssertionError("Dogrudan context kabul edildi")
        except RuntimeError:
            pass
        print("TEST 4 PASS: Dogrudan olusturma reddedildi")

        # TEST 5: Farkli thread.
        with transaction_context(lock) as active_ctx:
            errors = []

            def another_thread():
                try:
                    protected_operation(active_ctx)
                except RuntimeError:
                    errors.append("REJECTED")

            worker = threading.Thread(target=another_thread)
            worker.start()
            worker.join(timeout=5)

            assert not worker.is_alive()
            assert errors == ["REJECTED"]

        print("TEST 5 PASS: Farkli thread reddedildi")

        # TEST 6: Hata sonrasi context gecersiz.
        error_ctx = None
        try:
            with transaction_context(lock) as error_ctx:
                raise ValueError("Test hatasi")
        except ValueError:
            pass

        try:
            protected_operation(error_ctx)
            raise AssertionError("Hata sonrasi context aktif")
        except RuntimeError:
            pass

        with transaction_context(lock) as fresh:
            assert protected_operation(fresh) == "OK"

        print("TEST 6 PASS: Hata sonrasi kilit ve context guvenli")

        # TEST 7: Ic ice kilit engelleniyor.
        with transaction_context(lock):
            try:
                with transaction_context(lock):
                    raise AssertionError("Ic ice kilit kabul edildi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)

        print("TEST 7 PASS: Ic ice kilit reddedildi")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
