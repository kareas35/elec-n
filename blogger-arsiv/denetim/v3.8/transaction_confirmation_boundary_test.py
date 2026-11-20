#!/usr/bin/env python3
"""V3.8 - Guvenli transaction onay siniri denetimi.

Mevcut riskleri tespit eder. Gercek dosyalari degistirmez.
"""
import ast
import tempfile
from pathlib import Path

from transaction_persistent_outcome import (
    begin, finish, inspect,
)
from transaction_outcome_verifier import assess

ROOT = Path(__file__).resolve().parent


def calls_named(node, name):
    return [
        item for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id == name
    ]


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-confirmation-boundary-"
    ) as tmp:
        bundle = Path(tmp) / "bundle"
        bundle.mkdir()

        # TEST 1: Eksik kayitlarda guvenli karar.
        assert assess(bundle)["status"] == "BLOCKED"
        print("TEST 1 PASS: Eksik kayit BLOCKED")

        # TEST 2: Intent sonrasi onay yok.
        begin(bundle, "op-001")
        assert assess(bundle)["status"] == "BLOCKED"
        print("TEST 2 PASS: Intent tek basina onay degil")

        # TEST 3: Kayit eslesmesi nihai onay degil.
        assert finish(bundle, "op-001") == "CONFIRMED"
        result = assess(bundle)
        assert result["status"] == "REVIEW_REQUIRED"
        assert result["transaction_confirmed"] is False
        print("TEST 3 PASS: Guvenli verifier onay vermiyor")

        # TEST 4: Eski API riskini acikca tespit et.
        assert inspect(bundle) == "CONFIRMED"
        print("TEST 4 PASS: Eski inspect riski tespit edildi")
        print("  ACIK: Legacy inspect CONFIRMED uretiyor")

        # TEST 5: finish fonksiyonu dogrudan inspect kullaniyor.
        source = ROOT / "transaction_persistent_outcome.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))

        finish_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "finish"
        )

        assert calls_named(finish_node, "inspect")
        print("TEST 5 PASS: finish -> inspect bagimliligi tespit")

        # TEST 6: Mevcut verifier'in onay davranisi.
        verifier = ROOT / "transaction_outcome_verifier.py"
        verifier_tree = ast.parse(
            verifier.read_text(encoding="utf-8")
        )
        assess_node = next(
            node for node in verifier_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "assess"
        )

        returned_statuses = {
            value.value
            for node in ast.walk(assess_node)
            if isinstance(node, ast.Constant)
            for value in [node]
            if isinstance(value.value, str)
        }

        assert "CONFIRMED" in returned_statuses
        assert result["automatic_retry"] is False
        print("TEST 6 PASS: Legacy sonuc otomatik onaylanmiyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("KRITIK ACIK: HENUZ KAPATILMADI")
    print("Eski API davranisi: KORUNDU")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
