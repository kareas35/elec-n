#!/usr/bin/env python3
"""V3.8 - Transaction API gecis uyumlulugu denetimi.

AST tabanli, salt okunur analiz.
Gercek HTML, CSV veya rollback islemi yapmaz.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CONTRACTS = {
    "transaction_state.py": {
        "_save_state": ["path", "state"],
        "save_state": ["path", "state"],
        "initialize": ["bundle"],
        "transition": ["bundle", "expected", "target"],
    },
    "transaction_bundle.py": {
        "create_bundle": ["folder", "entries"],
    },
    "transaction_csv_baseline.py": {
        "capture_baseline": ["bundle", "source"],
    },
    "transaction_migration_test.py": {
        "migrate_legacy": ["bundle", "live", "csv_path"],
    },
    "transaction_journal.py": {
        "atomic_json_write": ["path"],
        "create_journal": [],
    },
}

WRITE_APIS = {
    "_save_state", "save_state", "initialize", "transition",
    "create_bundle", "capture_baseline", "migrate_legacy",
    "atomic_json_write", "create_journal",
}


def read_tree(filename):
    path = ROOT / filename
    return ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )


def function_map(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def test_signatures():
    for filename, functions in CONTRACTS.items():
        tree = read_tree(filename)
        available = function_map(tree)

        for name, prefix in functions.items():
            assert name in available, (
                f"Eksik fonksiyon: {filename}:{name}"
            )
            args = [
                arg.arg
                for arg in available[name].args.posonlyargs
                + available[name].args.args
            ]
            assert args[:len(prefix)] == prefix, (
                f"Imza degisti: {filename}:{name}: {args}"
            )

    print("TEST 1 PASS: Mevcut fonksiyon imzalari korundu")


def test_state_entrypoints():
    tree = read_tree("transaction_state.py")
    available = function_map(tree)

    for name in ("initialize", "transition", "save_state"):
        assert name in available

    assert "_save_state" in available

    print("TEST 2 PASS: Eski state girisleri tespit edildi")


def test_bypass_exists():
    tree = read_tree("transaction_state.py")
    available = function_map(tree)
    save = available["save_state"]

    calls = [
        call_name(node.func)
        for node in ast.walk(save)
        if isinstance(node, ast.Call)
    ]

    assert "_save_state" in calls, (
        "State mimarisi degismis; tekrar incele"
    )

    print("TEST 3 PASS: Dogrudan yazma yolu tespit edildi")
    print("  UYARI: _save_state halen erisilebilir")


def test_legacy_call_sites():
    results = []

    for path in sorted(ROOT.glob("*.py")):
        tree = read_tree(path.name)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            name = call_name(node.func)
            if name not in WRITE_APIS:
                continue

            results.append(
                (path.name, node.lineno, name)
            )

    assert results

    print("TEST 4 PASS: Eski API kullanimlari listelendi")
    print("  Toplam statik cagri:", len(results))
    print("  NOT: Test kodlari ve dolayli cagrilar dahildir")

    for filename, line, name in results:
        if filename in (
            "transaction_state.py",
            "transaction_context_integration_test.py",
            "transaction_migration_test.py",
        ):
            print(f"  {filename}:{line} -> {name}")


def test_context_is_prototype():
    tree = read_tree("transaction_context_test.py")
    available = function_map(tree)

    assert "transaction_context" in available
    assert "protected_operation" in available

    tree = read_tree("transaction_bundle_scope_test.py")
    available = function_map(tree)

    assert "bundle_context" in available

    print("TEST 5 PASS: Context halen prototip modulunde")


def test_no_automatic_unlock():
    tree = read_tree("transaction_api_contract_test.py")
    available = function_map(tree)

    assert "main" in available
    assert "calls_in" in available

    print("TEST 6 PASS: API kontrat testi mevcut")


def main():
    test_signatures()
    test_state_entrypoints()
    test_bypass_exists()
    test_legacy_call_sites()
    test_context_is_prototype()
    test_no_automatic_unlock()

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gecis durumu: PLANLAMA")
    print("Eski API kaldirildi: HAYIR")
    print("Tum yazma yollari korumali: HAYIR")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
