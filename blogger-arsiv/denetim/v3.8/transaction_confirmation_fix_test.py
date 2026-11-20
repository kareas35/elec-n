#!/usr/bin/env python3
"""V3.8 - Legacy CONFIRMED engelleme regresyon testi."""
import ast
import errno
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from transaction_persistent_outcome import (
    begin, finish, inspect, RESULT
)
from transaction_outcome_verifier import assess


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-confirmation-fix-"
    ) as tmp:
        root = Path(tmp)
        bundle = root / "bundle"
        bundle.mkdir()

        assert inspect(bundle) == "BLOCKED"
        print("TEST 1 PASS: Eksik kayit BLOCKED")

        begin(bundle, "op-001")
        assert inspect(bundle) == "BLOCKED"
        print("TEST 2 PASS: Intent-only BLOCKED")

        result = finish(bundle, "op-001")
        assert result == "REVIEW_REQUIRED"
        assert inspect(bundle) == "REVIEW_REQUIRED"
        print("TEST 3 PASS: finish ve inspect guvenli")

        assert assess(bundle)["status"] == "REVIEW_REQUIRED"
        assert assess(bundle)["transaction_confirmed"] is False
        print("TEST 4 PASS: Verifier nihai onay vermedi")

        # Result JSON kaydi ile API onay karari farklidir.
        import json
        record = json.loads(
            (bundle / RESULT).read_text(encoding="utf-8")
        )
        assert record["status"] == "CONFIRMED"
        assert inspect(bundle) != "CONFIRMED"
        print("TEST 5 PASS: Kayit durumu ve onay ayrildi")

        # Dizin fsync hatasindan sonra yeni API sonucu.
        other = root / "fsync-error"
        other.mkdir()
        begin(other, "op-002")

        real_fsync = os.fsync
        count = [0]

        def fail_second(fd):
            count[0] += 1
            if count[0] == 2:
                raise OSError(errno.EIO, "Directory fsync")
            return real_fsync(fd)

        with patch(
            "transaction_journal.os.fsync",
            side_effect=fail_second,
        ):
            try:
                finish(other, "op-002")
            except OSError as error:
                assert error.errno == errno.EIO
            else:
                raise AssertionError("fsync hatasi bekleniyordu")

        assert count[0] == 2
        assert inspect(other) == "REVIEW_REQUIRED"
        assert assess(other)["transaction_confirmed"] is False
        print("TEST 6 PASS: fsync hatasi CONFIRMED olmadi")

        # Yeniden baslatilan Python sureci ayni karari verir.
        code = (
            "import sys; "
            "from transaction_persistent_outcome import inspect; "
            "print(inspect(sys.argv[1]))"
        )

        proc = subprocess.run(
            [sys.executable, "-c", code, str(other)],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "REVIEW_REQUIRED"
        print("TEST 7 PASS: Yeniden baslatmada guvenli")

        # inspect() icinde dogrudan CONFIRMED donusu olamaz.
        source = Path(__file__).with_name(
            "transaction_persistent_outcome.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))

        function = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "inspect"
        )

        assert not any(
            isinstance(n, ast.Return)
            and isinstance(n.value, ast.Constant)
            and n.value.value == "CONFIRMED"
            for n in ast.walk(function)
        )
        print("TEST 8 PASS: inspect CONFIRMED dondurmuyor")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Legacy CONFIRMED onay yolu: DEVRE DISI")
    print("Nihai transaction onayi: HENUZ YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
