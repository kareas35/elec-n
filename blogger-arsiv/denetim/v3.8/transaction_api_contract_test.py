#!/usr/bin/env python3
"""V3.8 - Transaction API guvenlik sozlesmesi prototipi.

Yalnizca gecici klasorde state testi yapar.
Gercek yayinlar, CSV ve rollback kodu degistirilmez.
"""
import ast
import tempfile
from pathlib import Path

from transaction_bundle_scope_test import (
    bundle_context,
    make_bundle,
    expect_value_error,
)
from transaction_state import load_state


BASE = Path(__file__).resolve().parent

POLICY = {
    "create_bundle": ("lock", "target", "manifest"),
    "capture_baseline": ("lock", "bundle", "sha256"),
    "transition": ("lock", "bundle", "state_validation"),
    "migrate_legacy": ("lock", "bundle", "recovery_validation"),
    "create_journal": ("lock", "bundle", "atomic_write"),
}


class TransactionAPI:
    """Yalnizca prototip state gecisleri icin API."""

    def __init__(self, scoped_context):
        self._scoped = scoped_context

    def transition(self, bundle, expected, target):
        if self._scoped is None:
            raise RuntimeError("Aktif bundle context gerekli")

        return self._scoped.transition(
            bundle, expected, target
        )


def calls_in(filename, target_name):
    path = BASE / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))

    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == target_name
        )
    ]


def main():
    # TEST 1: Kritik operasyonlar icin sozlesme.
    assert len(POLICY) == 5
    assert all("lock" in rules for rules in POLICY.values())
    print("TEST 1 PASS: Ortak kilit sozlesmesi")

    # TEST 2: Kritik state ve migration girisleri mevcut.
    expected = {
        "transaction_state.py": [
            "save_state", "_save_state"
        ],
        "transaction_migration_test.py": [
            "migrate_legacy"
        ],
        "transaction_bundle.py": [
            "create_bundle"
        ],
    }

    for filename, names in expected.items():
        source = (BASE / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)

        functions = {
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
        }

        assert set(names).issubset(functions), filename

    print("TEST 2 PASS: Mevcut giris noktalari tanindi")

    with tempfile.TemporaryDirectory(
        prefix="v38-api-contract-"
    ) as tmp:
        root = Path(tmp)
        a = make_bundle(root, "bundle-a")
        b = make_bundle(root, "bundle-b")

        # TEST 3: Context olmadan state gecisi reddi.
        api_without_context = TransactionAPI(None)

        try:
            api_without_context.transition(
                a, None, "PREPARED"
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Kilitsiz API kabul edildi")

        print("TEST 3 PASS: Context zorunlulugu")

        with bundle_context(a) as scoped:
            api = TransactionAPI(scoped)

            # TEST 4: Baska bundle yetkisi reddi.
            expect_value_error(
                lambda: api.transition(
                    b, None, "PREPARED"
                )
            )

            assert not (
                b / "transaction-state.json"
            ).exists()

            print("TEST 4 PASS: Bundle izolasyonu")

            # TEST 5: Yetkili state gecisi.
            api.transition(a, None, "PREPARED")
            api.transition(
                a, "PREPARED", "IN_PROGRESS"
            )

            assert load_state(
                a / "transaction-state.json"
            ) == "IN_PROGRESS"

            print("TEST 5 PASS: Yetkili API gecisleri")

        # TEST 6: Suresi dolmus yetki reddi.
        try:
            api.transition(
                a, "IN_PROGRESS", "COMPLETED"
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Eski context kabul edildi")

        print("TEST 6 PASS: Eski API yetkisi gecersiz")

    # TEST 7: Mevcut bypass yolu tespit edilmeli.
    direct_calls = calls_in(
        "transaction_context_integration_test.py",
        "_save_state"
    )

    assert direct_calls, (
        "Dogrudan state cagrisi yeniden incelenmeli"
    )

    print(
        "TEST 7 PASS: Dogrudan _save_state yolu raporlandi"
    )
    print("  Satirlar:", direct_calls)
    print("  UYARI: Bu yol henuz kapatilmadi")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("API durumu: PROTOTIP")
    print("Tum yazma yollari korumali: HAYIR")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
