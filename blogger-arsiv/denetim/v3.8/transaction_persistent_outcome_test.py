#!/usr/bin/env python3
"""V3.8 - Yeniden baslatma ve kalici engel testleri."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_persistent_outcome import (
    begin, finish, inspect, INTENT, RESULT
)


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-persistent-outcome-"
    ) as tmp:
        root = Path(tmp)
        bundle = root / "bundle"
        bundle.mkdir()

        # TEST 1: Kayit yoksa varsayilan engel.
        assert inspect(bundle) == "BLOCKED"
        print("TEST 1 PASS: Eksik kayit BLOCKED")

        # TEST 2: Intent yazildiktan sonra ani cikis.
        code = """
import os, sys
from transaction_persistent_outcome import begin
begin(sys.argv[1], "operation-001")
os._exit(41)
"""
        child = subprocess.run(
            [sys.executable, "-c", code, str(bundle)],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=15
        )
        assert child.returncode == 41, child.stderr
        assert (bundle / INTENT).is_file()
        assert inspect(bundle) == "BLOCKED"
        print("TEST 2 PASS: Crash sonrasi intent korundu")

        # TEST 3: Yeni Python sureci de engeli goruyor.
        probe = subprocess.run(
            [
                sys.executable, "-c",
                "import sys; "
                "from transaction_persistent_outcome import inspect; "
                "print(inspect(sys.argv[1]))",
                str(bundle),
            ],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=15
        )
        assert probe.returncode == 0, probe.stderr
        assert probe.stdout.strip() == "BLOCKED"
        print("TEST 3 PASS: Yeniden baslatmada BLOCKED")

        # TEST 4: Ayni intent yeniden baslatilamaz.
        try:
            begin(bundle, "operation-002")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Eski intent uzerine yazildi")
        print("TEST 4 PASS: Tekrar baslatma reddedildi")

        # TEST 5: Prototip sonucu eslesirse gorunur onay.
        assert finish(bundle, "operation-001") == "CONFIRMED"
        assert inspect(bundle) == "CONFIRMED"
        print("TEST 5 PASS: Eslesen sonuc kaydi okundu")

        # TEST 6: Sonuc bozulursa engel geri gelir.
        result = bundle / RESULT
        original = result.read_bytes()
        result.write_text('{"status":"CONFIRMED"}', encoding="utf-8")
        assert inspect(bundle) == "BLOCKED"
        result.write_bytes(original)
        print("TEST 6 PASS: Bozuk sonuc BLOCKED")

        # TEST 7: Eslesmeyen operation_id reddedilir.
        other = root / "other"
        other.mkdir()
        begin(other, "operation-003")
        try:
            finish(other, "wrong-operation")
        except ValueError:
            pass
        else:
            raise AssertionError("Yanlis islem onaylandi")

        assert inspect(other) == "BLOCKED"
        print("TEST 7 PASS: Yanlis operation_id reddedildi")

        # TEST 8: Sembolik kayit reddedilir.
        alias = root / "alias"
        alias.mkdir()
        (alias / INTENT).symlink_to(bundle / INTENT)
        assert inspect(alias) == "BLOCKED"
        print("TEST 8 PASS: Sembolik kayit BLOCKED")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Kalici intent prototipi: TEST EDILDI")
    print("Gercek TransactionAPI entegrasyonu: YOK")
    print("Otomatik retry: YOK")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
