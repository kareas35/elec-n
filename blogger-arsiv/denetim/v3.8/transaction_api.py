#!/usr/bin/env python3
"""V3.8 - Kilitli ve bundle kapsamli state API.

Ilk surum: yalnizca transaction state yonetimi.
Gercek restorasyon veya rollback islemi icermez.
"""
import os
import stat
import threading
from contextlib import contextmanager
from pathlib import Path

from transaction_bundle import verify_bundle
from transaction_lock import transaction_lock
from transaction_state import _save_state


_TOKEN = object()


class TransactionAPI:
    def __init__(self, bundle, lock, token):
        if token is not _TOKEN:
            raise RuntimeError("API dogrudan olusturulamaz")

        self._bundle = Path(bundle).absolute()
        self._lock = Path(lock).absolute()
        self._pid = os.getpid()
        self._thread = threading.get_ident()
        self._active = True

        if self._bundle.is_symlink():
            raise ValueError("Sembolik bundle yasak")

        bundle_stat = self._bundle.stat()
        lock_stat = self._lock.stat()

        if not stat.S_ISDIR(bundle_stat.st_mode):
            raise ValueError("Bundle klasor olmali")
        if not stat.S_ISREG(lock_stat.st_mode):
            raise ValueError("Kilit normal dosya olmali")

        self._bundle_identity = (
            bundle_stat.st_dev, bundle_stat.st_ino
        )
        self._lock_identity = (
            lock_stat.st_dev, lock_stat.st_ino
        )

    def _require_active(self):
        if not self._active:
            raise RuntimeError("Transaction API suresi dolmus")

        if os.getpid() != self._pid:
            raise RuntimeError("Farkli surec API kullanamaz")

        if threading.get_ident() != self._thread:
            raise RuntimeError("Farkli thread API kullanamaz")

        for path, identity, expected_type in (
            (self._bundle, self._bundle_identity, stat.S_ISDIR),
            (self._lock, self._lock_identity, stat.S_ISREG),
        ):
            if path.is_symlink():
                raise RuntimeError("Sembolik yol degisikligi")

            try:
                info = path.stat()
            except OSError as error:
                raise RuntimeError("Islem yolu kayboldu") from error

            if (
                not expected_type(info.st_mode)
                or (info.st_dev, info.st_ino) != identity
            ):
                raise RuntimeError("Islem yolu degistirildi")

        verify_bundle(self._bundle)

    def initialize(self):
        self._require_active()
        return _save_state(
            self._bundle / "transaction-state.json",
            "PREPARED",
        )

    def transition(self, expected, target,
                   live_dir=None, csv_path=None):
        self._require_active()
        return _save_state(
            self._bundle / "transaction-state.json",
            target,
            expected=expected,
            live_dir=live_dir,
            csv_path=csv_path,
        )

    def guarded_transition(
        self, operation_id, expected, target,
        live_dir=None, csv_path=None
    ):
        """Intent zorunlu, kilitli state gecisi prototipi.

        open_transaction() kilidi altinda kullanilir.
        Result/binding uretmez; nihai onay vermez.
        """
        from transaction_persistent_outcome import (
            INTENT, RESULT, read_record
        )
        from transaction_state_binding import BINDING
        from transaction_state import load_state

        self._require_active()

        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("Gecersiz operation_id")

        intent_path = self._bundle / INTENT

        intent = read_record(intent_path)

        if intent != {
            "version": 1,
            "status": "IN_FLIGHT",
            "operation_id": operation_id,
        }:
            raise ValueError("Intent kaydi uyusmuyor")

        for name in (RESULT, BINDING):
            path = self._bundle / name
            if path.exists() or path.is_symlink():
                raise RuntimeError("Onceki sonuc/binding mevcut")

        current = load_state(
            self._bundle / "transaction-state.json"
        )

        if current != expected:
            raise ValueError("Beklenmeyen onceki state")

        # State yazimina baslamadan once tek kullanimlik
        # attempt kaydini kalici olarak yayimla.
        # Bu kod zaten open_transaction kilidi altindadir.
        import hashlib
        from transaction_journal import atomic_json_write
        from transaction_persistent_outcome import digest

        attempt_path = (
            self._bundle / "transaction-guarded-attempt.json"
        )

        if attempt_path.exists() or attempt_path.is_symlink():
            raise RuntimeError(
                "Onceki state girisimi mevcut; manuel inceleme gerekli"
            )

        manifest_path = self._bundle / "transaction.json"
        state_path = self._bundle / "transaction-state.json"

        attempt = {
            "version": 1,
            "operation_id": operation_id,
            "expected_state": expected,
            "target_state": target,
            "intent_sha256": digest(intent),
            "manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "before_state_sha256": hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
        }

        # Yazim basarisiz veya belirsiz olursa state'e
        # gecilmez. Yayimlanan attempt otomatik silinmez.
        atomic_json_write(attempt_path, attempt)

        # Ayni API sahibi ve ayni kilit icinde ilerler.
        # fsync hatasinda istisna yayilir; otomatik retry YOK.
        self.transition(
            expected, target,
            live_dir=live_dir,
            csv_path=csv_path,
        )

        return {
            "status": "STATE_WRITE_ATTEMPTED",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }

    def _invalidate(self):
        self._active = False


@contextmanager
def open_transaction(bundle):
    bundle = Path(bundle).absolute()

    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("Gecersiz bundle")

    lock = bundle.parent / "transaction.lock"

    with transaction_lock(lock):
        verify_bundle(bundle)
        api = TransactionAPI(bundle, lock, _TOKEN)
        try:
            yield api
        finally:
            api._invalidate()
