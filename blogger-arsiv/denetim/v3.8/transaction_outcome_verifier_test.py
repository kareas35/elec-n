#!/usr/bin/env python3
"""V3.8 - Outcome degerlendirme / fsync hata testleri."""
import errno
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from transaction_persistent_outcome import (
    begin, finish, inspect, RESULT,
)
from transaction_outcome_verifier import (
    assess, BLOCKED, REVIEW_REQUIRED,
)


def check(bundle, status):
    result = assess(bundle)
    assert result["status"] == status, result
    assert result["automatic_retry"] is False
    assert result["transaction_confirmed"] is False


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-outcome-verifier-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: Eksik kayit.
        a = root / "missing"
        a.mkdir()
        check(a, BLOCKED)
        print("TEST 1 PASS: Eksik kanit BLOCKED")

        # TEST 2: Yalnizca intent.
        b = root / "intent-only"
        b.mkdir()
        begin(b, "op-b")
        check(b, BLOCKED)
        print("TEST 2 PASS: Intent-only BLOCKED")

        # TEST 3: Eslesen result bile gercek onay degil.
        c = root / "matched"
        c.mkdir()
        begin(c, "op-c")
        assert finish(c, "op-c") == "REVIEW_REQUIRED"
        check(c, REVIEW_REQUIRED)
        print("TEST 3 PASS: Kayit eslesmesi REVIEW_REQUIRED")

        # TEST 4: Result fsync basarisiz ancak gorunur.
        d = root / "failed-fsync"
        d.mkdir()
        begin(d, "op-d")

        real_fsync = os.fsync
        calls = [0]

        def fail_second(fd):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError(errno.EIO, "Directory fsync failed")
            return real_fsync(fd)

        with patch(
            "transaction_journal.os.fsync",
            side_effect=fail_second,
        ):
            try:
                finish(d, "op-d")
            except OSError as error:
                assert error.errno == errno.EIO
            else:
                raise AssertionError("fsync hatasi olusmadi")

        assert calls[0] == 2
        assert inspect(d) == "REVIEW_REQUIRED"
        check(d, REVIEW_REQUIRED)
        print("TEST 4 PASS: fsync hatasi yaniltici onay degil")

        # TEST 5: Yeni surec de otomatik onay vermez.
        code = (
            "import sys; "
            "from transaction_outcome_verifier import assess; "
            "print(assess(sys.argv[1])['status'])"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, str(d)],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == REVIEW_REQUIRED
        print("TEST 5 PASS: Yeniden baslatma REVIEW_REQUIRED")

        # TEST 6: Bozuk sonuc fail-closed.
        result_path = c / RESULT
        result_path.write_text('{"broken":true}', encoding="utf-8")
        check(c, BLOCKED)
        print("TEST 6 PASS: Bozuk sonuc BLOCKED")

        # TEST 7: Sembolik sonuc fail-closed.
        e = root / "symlink"
        e.mkdir()
        begin(e, "op-e")
        (e / RESULT).symlink_to(d / RESULT)
        check(e, BLOCKED)
        print("TEST 7 PASS: Sembolik sonuc BLOCKED")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Yeni verifier otomatik CONFIRMED: YOK")
    print("Gercek TransactionAPI entegrasyonu: YOK")
    print("Otomatik retry veya silme: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
