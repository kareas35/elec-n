#!/usr/bin/env python3
"""V3.8 - Recovery kaydi ve ana state tutarlilik denetimi.

Salt okunur denetleyici; testler sadece gecici klasorde.
"""
import json
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, V38, ROOT
from transaction_csv_baseline import capture_baseline
from transaction_journal import sha256, atomic_json_write
from transaction_lock import transaction_lock
from transaction_recovery_validator import verify_recovered
from transaction_state import initialize, transition, load_state

NAMES = ("100.html", "171.html")


def inspect_consistency(bundle, live, csv_path):
    bundle = Path(bundle)
    result_path = bundle / "recovery-result.json"
    state = load_state(bundle / "transaction-state.json")

    if state == "IN_PROGRESS" and not result_path.exists():
        return "PENDING"

    if state != "RECOVERED" or not result_path.is_file():
        return "INCONSISTENT"

    if result_path.is_symlink():
        return "INCONSISTENT"

    try:
        verify_recovered(bundle, live, csv_path)

        result = json.loads(result_path.read_text("utf-8"))
        manifest = json.loads(
            (bundle / "transaction.json").read_text("utf-8")
        )
        baseline = bundle / "csv-baseline.csv"

        expected = {
            "version": 1,
            "state": "RECOVERED",
            "recovered_to": "INTEGRATED",
            "manifest_sha256": sha256(
                (bundle / "transaction.json").read_bytes()
            ),
            "csv_sha256": sha256(baseline.read_bytes()),
            "files": sorted(e["name"] for e in manifest["entries"])
        }

        if result != expected:
            return "INCONSISTENT"

        return "CONSISTENT"

    except (ValueError, OSError, KeyError, TypeError):
        return "INCONSISTENT"


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-consistency-"
    ) as tmp:
        base = Path(tmp)
        bundle = base / "bundle"
        live = base / "live"
        live.mkdir()

        entries = []
        for name in NAMES:
            before = V38 / "integration-backups" / (
                name + ".before-e14.gif"
            )
            after = ROOT / "Arsiv/yayinlar" / name

            entries.append({
                "name": name,
                "before": before,
                "after": after
            })
            shutil.copy2(after, live / name)

        create_bundle(bundle, entries)

        plan = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        with transaction_lock(base / "transaction.lock"):
            capture_baseline(bundle, plan)

        initialize(bundle)
        transition(bundle, "PREPARED", "IN_PROGRESS")

        assert inspect_consistency(
            bundle, live, plan
        ) == "PENDING"
        print("TEST 1 PASS: Devam eden islem PENDING")

        manifest_path = bundle / "transaction.json"
        result = {
            "version": 1,
            "state": "RECOVERED",
            "recovered_to": "INTEGRATED",
            "manifest_sha256": sha256(
                manifest_path.read_bytes()
            ),
            "csv_sha256": sha256(
                (bundle / "csv-baseline.csv").read_bytes()
            ),
            "files": sorted(NAMES)
        }

        result_path = bundle / "recovery-result.json"
        atomic_json_write(result_path, result)

        assert inspect_consistency(
            bundle, live, plan
        ) == "INCONSISTENT"
        print("TEST 2 PASS: Result var ama state eski")

        transition(
            bundle, "IN_PROGRESS", "RECOVERED",
            live_dir=live, csv_path=plan
        )

        assert inspect_consistency(
            bundle, live, plan
        ) == "CONSISTENT"
        print("TEST 3 PASS: Iki kayit uyumlu")

        good_result = result_path.read_bytes()
        result_path.write_text(
            '{"state":"RECOVERED"}', encoding="utf-8"
        )

        assert inspect_consistency(
            bundle, live, plan
        ) == "INCONSISTENT"
        print("TEST 4 PASS: Eksik result bilgisi reddedildi")

        result_path.write_bytes(good_result)

        page = live / "100.html"
        good_html = page.read_bytes()
        page.write_bytes(good_html + b"\nUNEXPECTED")

        assert inspect_consistency(
            bundle, live, plan
        ) == "INCONSISTENT"
        print("TEST 5 PASS: Sonradan bozulmus HTML tespit edildi")

        page.write_bytes(good_html)
        result_path.unlink()

        assert inspect_consistency(
            bundle, live, plan
        ) == "INCONSISTENT"
        print("TEST 6 PASS: Eksik result kaydi tespit edildi")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
