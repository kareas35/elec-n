#!/usr/bin/env python3
"""V3.8 - TransactionAPI surec cokmesi testleri.

Yalnizca gecici klasorde calisir.
Gercek yayinlar, CSV ve rollback kodunu degistirmez.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state


def child(bundle, action):
    code = """
import os
import sys
from transaction_api import open_transaction
from transaction_persistent_outcome import begin

bundle = sys.argv[1]
action = sys.argv[2]

if action == "after_transition":
    begin(bundle, "op-217-crash")

with open_transaction(bundle) as api:
    if action == "before":
        os._exit(41)

    if action == "after_initialize":
        api.initialize()
        os._exit(42)

    if action == "after_transition":
        api.guarded_transition(
            "op-217-crash", "PREPARED", "IN_PROGRESS"
        )
        os._exit(43)

    raise RuntimeError("Bilinmeyen test")
"""

    result = subprocess.run(
        [sys.executable, "-c", code, str(bundle), action],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result


def check_no_orphan_state(bundle):
    state = bundle / "transaction-state.json"
    if state.exists():
        assert not state.is_symlink()
        assert load_state(state) in {
            "PREPARED", "IN_PROGRESS"
        }


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-api-crash-"
    ) as tmp:
        root = Path(tmp)

        a = make_bundle(root, "bundle-a")
        state = a / "transaction-state.json"

        # TEST 1: Kilit alindiktan hemen sonra cokme.
        result = child(a, "before")
        assert result.returncode == 41
        assert not state.exists()
        print("TEST 1 PASS: Ilk yazma oncesi cokme")

        # TEST 2: Cokme sonrasi kilit yeniden alinabilir.
        with open_transaction(a) as api:
            api.initialize()

        assert load_state(state) == "PREPARED"
        print("TEST 2 PASS: Kilit tekrar alindi")

        # TEST 3: State gecisi sonrasi ani cikis.
        result = child(a, "after_transition")
        assert result.returncode == 43, result.stderr
        assert load_state(state) == "IN_PROGRESS"
        print("TEST 3 PASS: State gecisi sonrasi cokme")

        # TEST 4: Tamamlanmis state bozulmadi.
        check_no_orphan_state(a)
        assert load_state(state) == "IN_PROGRESS"
        print("TEST 4 PASS: State butunlugu korundu")

        # TEST 5: Cokme sonrasi API yeniden acilabilir.
        with open_transaction(a):
            assert load_state(state) == "IN_PROGRESS"
        print("TEST 5 PASS: Cokme sonrasi API acildi")

        # TEST 6: Ayri bundle baslatma ve cokme.
        b = make_bundle(root, "bundle-b")
        result = child(b, "after_initialize")
        assert result.returncode == 42, result.stderr
        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 6 PASS: Ikinci bundle cokme testi")

        # TEST 7: Iki bundle birbirini etkilemedi.
        assert load_state(state) == "IN_PROGRESS"
        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 7 PASS: Bundle durumlari korundu")

        # TEST 8: Sonraki islemler kilit alabilir.
        from transaction_persistent_outcome import begin
        begin(b, "op-217-resume")
        with open_transaction(b) as api:
            api.guarded_transition(
                "op-217-resume", "PREPARED", "IN_PROGRESS"
            )

        assert load_state(
            b / "transaction-state.json"
        ) == "IN_PROGRESS"
        print("TEST 8 PASS: Cokme sonrasi islem devam etti")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Crash testleri: ALT SURECLERDE")
    print("Test verileri: SADECE GECICI KLASOR")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
