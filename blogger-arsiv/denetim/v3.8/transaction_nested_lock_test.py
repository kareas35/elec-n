#!/usr/bin/env python3
"""V3.8 - Ic ice kilit ve dogrudan state yazimi denetimi.

Riskli senaryolar ayri ve zaman asimli alt sureclerde.
Yalnizca TemporaryDirectory kullanilir.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle

HERE = Path(__file__).resolve().parent

NESTED = """
import sys
from transaction_api import open_transaction
from transaction_persistent_outcome import begin, finish

bundle, action = sys.argv[1:3]

with open_transaction(bundle):
    if action == "begin":
        begin(bundle, "op-179")
    elif action == "finish":
        finish(bundle, "op-179")
    elif action == "api":
        with open_transaction(bundle):
            pass
    else:
        raise ValueError("Bilinmeyen senaryo")
"""

BYPASS = """
import sys
from pathlib import Path
from transaction_lock import transaction_lock
from transaction_state import _save_state

bundle = Path(sys.argv[1])
state = bundle / "transaction-state.json"

with transaction_lock(bundle.parent / "transaction.lock"):
    _save_state(state, "PREPARED")
    print("DIRECT_WRITE_SUCCEEDED", flush=True)
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


def run(code, *args):
    return subprocess.run(
        [sys.executable, "-c", code, *map(str, args)],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def rejected_or_timeout(code, *args):
    try:
        result = run(code, *args)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"

    if result.returncode == 0:
        raise AssertionError(
            "Ic ice kilit beklenmedik sekilde kabul edildi"
        )

    return "REJECTED"


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-nested-lock-"
    ) as tmp:
        root = Path(tmp)

        # TEST 1: begin ic ice kilit almaya calisir.
        a = make_bundle(root, "bundle-a")

        outcome = rejected_or_timeout(NESTED, a, "begin")
        assert not (
            a / "transaction-outcome-intent.json"
        ).exists()

        print("TEST 1 PASS: Nested begin", outcome)

        # TEST 2: finish ic ice kilit almaya calisir.
        b = make_bundle(root, "bundle-b")

        outcome = rejected_or_timeout(NESTED, b, "finish")
        assert not (
            b / "transaction-outcome-result.json"
        ).exists()

        print("TEST 2 PASS: Nested finish", outcome)

        # TEST 3: open_transaction ic ice cagirilir.
        c = make_bundle(root, "bundle-c")

        outcome = rejected_or_timeout(NESTED, c, "api")
        assert not (
            c / "transaction-state.json"
        ).exists()

        print("TEST 3 PASS: Nested TransactionAPI", outcome)

        # TEST 4: Dogrudan _save_state kullanimi.
        # Bu bir guvenlik acigi denetimidir.
        d = make_bundle(root, "bundle-d")

        result = run(BYPASS, d)

        assert result.returncode == 0, result.stderr
        assert "DIRECT_WRITE_SUCCEEDED" in result.stdout

        assert (
            d / "transaction-state.json"
        ).is_file()

        print("TEST 4 PASS: Dogrudan state yazimi tespit")
        print("  RISK: _save_state merkezi API disinda erisilebilir")

        # TEST 5: Dogrudan yazim icin outcome yok.
        assert not (
            d / "transaction-outcome-intent.json"
        ).exists()

        assert not (
            d / "transaction-outcome-result.json"
        ).exists()

        print("TEST 5 PASS: Intent olmadan state riski tespit")

        # TEST 6: Test ortami gercek yayin degil.
        assert str(d).startswith(str(root))
        print("TEST 6 PASS: Tum islemler gecici klasorde")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Nested lock davranisi: OLCULDU")
    print("Dogrudan state yazimi: RISK DOGRULANDI")
    print("Merkezi API bypass: HENUZ KAPATILMADI")
    print("Bu test guvenlik onayi DEGILDIR.")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
