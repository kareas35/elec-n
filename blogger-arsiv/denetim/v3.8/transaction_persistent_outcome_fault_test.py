#!/usr/bin/env python3
"""V3.8 - Persistent outcome hata ve crash testleri.

Amac: Mevcut guvenlik davranisini olcmek.
Guvenlik acigini gizlemeden raporlamak.
Tum dosyalar TemporaryDirectory icindedir.
"""
import errno
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from transaction_persistent_outcome import (
    begin, finish, inspect, INTENT, RESULT
)


def new_bundle(root, name):
    bundle = root / name
    bundle.mkdir()
    return bundle


def expect_oserror(action, code):
    try:
        action()
    except OSError as error:
        assert error.errno == code, error
        return
    raise AssertionError("Beklenen I/O hatasi olusmadi")


def fail_directory_fsync():
    real_fsync = os.fsync
    calls = [0]

    def injected(fd):
        calls[0] += 1
        if calls[0] == 2:
            raise OSError(errno.EIO, "Directory fsync error")
        return real_fsync(fd)

    return injected, calls


def probe_from_new_process(bundle):
    code = (
        "import sys; "
        "from transaction_persistent_outcome import inspect; "
        "print(inspect(sys.argv[1]))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(bundle)],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-outcome-fault-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: Intent yayinlama oncesi I/O hatasi.
        a = new_bundle(root, "intent-link-error")

        with patch(
            "transaction_journal.os.link",
            side_effect=OSError(errno.ENOSPC, "No space")
        ):
            expect_oserror(
                lambda: begin(a, "op-a"), errno.ENOSPC
            )

        assert inspect(a) == "BLOCKED"
        assert not (a / INTENT).exists()
        print("TEST 1 PASS: Intent yayinlanamadi, BLOCKED")

        # TEST 2: Intent yayinlandiktan sonra fsync hatasi.
        b = new_bundle(root, "intent-sync-error")
        injected, calls = fail_directory_fsync()

        with patch(
            "transaction_journal.os.fsync",
            side_effect=injected
        ):
            expect_oserror(
                lambda: begin(b, "op-b"), errno.EIO
            )

        assert calls[0] == 2
        assert (b / INTENT).is_file()
        assert inspect(b) == "BLOCKED"
        print("TEST 2 PASS: Intent fsync hatasi BLOCKED")

        # TEST 3: Var olan intent uzerine yazilamaz.
        try:
            begin(b, "op-b-retry")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Intent uzerine yazildi")

        assert inspect(b) == "BLOCKED"
        print("TEST 3 PASS: Tekrar begin reddedildi")

        # TEST 4: Result yayinlanamadi.
        c = new_bundle(root, "result-link-error")
        begin(c, "op-c")

        with patch(
            "transaction_journal.os.link",
            side_effect=OSError(errno.EACCES, "Permission")
        ):
            expect_oserror(
                lambda: finish(c, "op-c"), errno.EACCES
            )

        assert inspect(c) == "BLOCKED"
        assert not (c / RESULT).exists()
        print("TEST 4 PASS: Result yayinlanamadi, BLOCKED")

        # TEST 5: Result yayinlandiktan sonra fsync hatasi.
        d = new_bundle(root, "result-sync-error")
        begin(d, "op-d")
        injected, calls = fail_directory_fsync()

        with patch(
            "transaction_journal.os.fsync",
            side_effect=injected
        ):
            expect_oserror(
                lambda: finish(d, "op-d"), errno.EIO
            )

        assert calls[0] == 2
        assert (d / RESULT).is_file()

        # Bu mevcut prototipin guvenlik eksigidir.
        assert inspect(d) == "REVIEW_REQUIRED"
        print("TEST 5 PASS: Result fsync hatasi yeniden uretildi")
        print("  GUVENLI: inspect REVIEW_REQUIRED goruyor")
        print("  KRITIK: Disk kaliciligi kanitlanmadi")

        # TEST 6: Yeni surec de ayni riski goruyor.
        assert probe_from_new_process(d) == "REVIEW_REQUIRED"
        print("TEST 6 PASS: Yeniden baslatmada risk gorunur")

        # TEST 7: Intent sonrasi ani surec cikisi.
        e = new_bundle(root, "intent-crash")

        code = """
import os, sys
from transaction_persistent_outcome import begin
begin(sys.argv[1], "op-e")
os._exit(47)
"""
        proc = subprocess.run(
            [sys.executable, "-c", code, str(e)],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert proc.returncode == 47, proc.stderr
        assert probe_from_new_process(e) == "BLOCKED"
        print("TEST 7 PASS: Intent sonrasi crash BLOCKED")

        # TEST 8: Result oncesi crash.
        f = new_bundle(root, "result-crash")
        begin(f, "op-f")

        code = """
import os, sys
from transaction_persistent_outcome import finish
from unittest.mock import patch

def crash(*args, **kwargs):
    os._exit(48)

with patch(
    "transaction_persistent_outcome.atomic_json_write",
    side_effect=crash
):
    finish(sys.argv[1], "op-f")
"""
        proc = subprocess.run(
            [sys.executable, "-c", code, str(f)],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert proc.returncode == 48, proc.stderr
        assert probe_from_new_process(f) == "BLOCKED"
        print("TEST 8 PASS: Result oncesi crash BLOCKED")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("BULGU: RESULT_FSYNC_DURABILITY_UNPROVEN")
    print("Yaniltici API onayi engellendi; disk kaliciligi kanitlanmadi.")
    print("Gercek TransactionAPI: DEGISTIRILMEDI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
