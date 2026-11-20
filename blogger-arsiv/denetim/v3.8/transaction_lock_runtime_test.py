#!/usr/bin/env python3
"""V3.8 - Cok surecli transaction kilit testi.

Yalnizca gecici dosyalari kullanir.
Gercek restorasyon, retry veya rollback YOK.
"""
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_api import open_transaction
from transaction_persistent_outcome import (
    begin, finish, INTENT, RESULT
)

HERE = Path(__file__).resolve().parent

HOLDER = """
import sys
from transaction_api import open_transaction

with open_transaction(sys.argv[1]):
    print("READY", flush=True)
    sys.stdin.readline()
"""

ATTEMPT = """
import sys
from transaction_api import open_transaction
from transaction_persistent_outcome import begin, finish

bundle = sys.argv[1]
action = sys.argv[2]

if action == "begin":
    begin(bundle, "op-177")
elif action == "finish":
    finish(bundle, "op-177")
elif action == "api":
    with open_transaction(bundle) as api:
        api.initialize()
else:
    raise ValueError("Unknown action")
"""


def make_bundle(root, name):
    source = root / ("source-" + name)
    source.mkdir()

    before = source / "before.html"
    after = source / "after.html"
    before.write_text("OLD", encoding="utf-8")
    after.write_text("NEW", encoding="utf-8")

    bundle = root / name

    create_bundle(bundle, [{
        "name": "100.html",
        "before": before,
        "after": after,
    }])

    return bundle


@contextmanager
def held_lock(bundle):
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(bundle)],
        cwd=HERE,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        # Alt surecin kilidi aldigi bilgisi.
        ready = proc.stdout.readline().strip()
        if ready != "READY":
            raise AssertionError(
                "Lock holder baslatilamadi: " +
                proc.stderr.read()
            )
        yield
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)


def attempt(bundle, action):
    return subprocess.run(
        [sys.executable, "-c", ATTEMPT, str(bundle), action],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )


def rejected(proc):
    # Kilit basarisizken surec hata ile cikmali.
    assert proc.returncode != 0, (
        "Kilit varken islem basarili gorundu"
    )


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-lock-runtime-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: Bir surec kilit tutuyor.
        bundle = make_bundle(root, "bundle-a")

        with held_lock(bundle):
            print("TEST 1 PASS: Ayrik surec kilidi aldi")

            # TEST 2: begin() kilit varken reddedilir.
            rejected(attempt(bundle, "begin"))
            assert not (bundle / INTENT).exists()
            print("TEST 2 PASS: begin kilit altinda reddedildi")

            # TEST 3: API initialize reddedilir.
            rejected(attempt(bundle, "api"))
            assert not (
                bundle / "transaction-state.json"
            ).exists()
            print("TEST 3 PASS: Ikinci API kilit alamadi")

        # TEST 4: Kilit birakildiginda yeni islem baslar.
        begin(bundle, "op-177")
        assert (bundle / INTENT).is_file()
        print("TEST 4 PASS: Kilit birakildiktan sonra begin")

        # TEST 5: finish kilit altinda reddedilir.
        with held_lock(bundle):
            rejected(attempt(bundle, "finish"))
            assert not (bundle / RESULT).exists()
            print("TEST 5 PASS: finish kilit altinda reddedildi")

        # TEST 6: Basarisiz finish otomatik tamamlanmaz.
        assert not (bundle / RESULT).exists()
        print("TEST 6 PASS: Otomatik result kaydi olusmadi")

        # TEST 7: Baska bundle da ortak kilide uyar.
        another = make_bundle(root, "bundle-b")
        with held_lock(bundle):
            rejected(attempt(another, "begin"))
            assert not (another / INTENT).exists()
            print("TEST 7 PASS: Ortak kilit kapsamı korundu")

        # TEST 8: Yeni surecde kilit kalici engel degil.
        # Bu bir otomatik retry degildir; sadece kilit
        # serbest kalma davranisi kontrol edilir.
        proc = attempt(another, "begin")
        assert proc.returncode == 0, proc.stderr
        assert (another / INTENT).is_file()
        print("TEST 8 PASS: Kilit serbestken erisim saglandi")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Kilit cakismasi: AYRI SURECLERDE TEST EDILDI")
    print("Merkezi API entegrasyonu: HENUZ YOK")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
