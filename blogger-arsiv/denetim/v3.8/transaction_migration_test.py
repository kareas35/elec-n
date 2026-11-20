#!/usr/bin/env python3
"""V3.8 - Eski kayitlardan birlesik transaction kaydina gecis.

Yalnizca gecici test klasorlerinde calisir.
"""
import json
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import (
    create_bundle, verify_bundle, V38, ROOT
)
from transaction_csv_baseline import capture_baseline
from transaction_journal import sha256, atomic_json_write
from transaction_lock import transaction_lock
from transaction_recovery_validator import verify_recovered
from transaction_state import initialize, transition, load_state
from transaction_unified_record_test import validate_record

NAMES = ("100.html", "171.html")


def expected_recovery(bundle):
    manifest_path = bundle / "transaction.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))

    return {
        "recovered_to": "INTEGRATED",
        "manifest_sha256": sha256(manifest_path.read_bytes()),
        "csv_sha256": sha256(
            (bundle / "csv-baseline.csv").read_bytes()
        ),
        "files": sorted(e["name"] for e in manifest["entries"])
    }


def migrate_legacy(bundle, live, csv_path):
    """Eski kayitlari okumakla yetin; yeni kaydi tek sefer yaz."""
    bundle = Path(bundle)
    live = Path(live)
    csv_path = Path(csv_path)
    output = bundle / "transaction-record.json"

    # Tum test islemleri ayni ortak kilidi kullanir.
    lock_path = bundle.parent / "transaction.lock"

    with transaction_lock(lock_path):
        verify_bundle(bundle)

        if output.exists() or output.is_symlink():
            raise FileExistsError("Birlesik kayit zaten mevcut")

        state = load_state(bundle / "transaction-state.json")
        result_path = bundle / "recovery-result.json"

        if state == "COMPLETED":
            raise ValueError(
                "COMPLETED migrasyonu henuz desteklenmiyor"
            )

        if state == "RECOVERED":
            if result_path.is_symlink() or not result_path.is_file():
                raise ValueError("Recovery result eksik veya guvensiz")

            verify_recovered(bundle, live, csv_path)

            result = json.loads(
                result_path.read_text(encoding="utf-8")
            )

            expected = {
                "version": 1,
                "state": "RECOVERED",
                **expected_recovery(bundle)
            }

            if result != expected:
                raise ValueError(
                    "Eski recovery result bilgileri uyusmuyor"
                )

            record = {
                "version": 1,
                "state": "RECOVERED",
                "recovery": expected_recovery(bundle)
            }
        else:
            if result_path.exists() or result_path.is_symlink():
                raise ValueError(
                    "Recovery result beklenmeyen durumda mevcut"
                )

            record = {
                "version": 1,
                "state": state,
                "recovery": None
            }

        validate_record(record)
        atomic_json_write(output, record)
        return record


def fixture(base):
    base = Path(base)
    base.mkdir()
    live = base / "live"
    live.mkdir()
    bundle = base / "bundle"

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

    csv_path = base / "plan.csv"
    shutil.copy2(
        V38 / "restorasyon-entegrasyon-plani.csv",
        csv_path
    )

    with transaction_lock(base / "transaction.lock"):
        capture_baseline(bundle, csv_path)

    initialize(bundle)
    return bundle, live, csv_path


def make_recovered(bundle, live, csv_path):
    transition(bundle, "PREPARED", "IN_PROGRESS")
    transition(
        bundle, "IN_PROGRESS", "RECOVERED",
        live_dir=live, csv_path=csv_path
    )

    atomic_json_write(
        bundle / "recovery-result.json",
        {
            "version": 1,
            "state": "RECOVERED",
            **expected_recovery(bundle)
        }
    )


def assert_rejected(action, output, exceptions):
    try:
        action()
    except exceptions:
        assert not output.exists()
    else:
        raise AssertionError("Guvensiz migrasyon kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-migration-"
    ) as tmp:
        root = Path(tmp)

        # 1: PREPARED migrasyonu
        bundle, live, csv_path = fixture(root / "prepared")
        before = (
            bundle / "transaction-state.json"
        ).read_bytes()

        record = migrate_legacy(bundle, live, csv_path)
        assert record["state"] == "PREPARED"
        assert (
            bundle / "transaction-state.json"
        ).read_bytes() == before
        print("TEST 1 PASS: PREPARED ve eski kayit korundu")

        # 2: Var olan kayit tekrar yazilamaz
        output = bundle / "transaction-record.json"
        saved = output.read_bytes()
        try:
            migrate_legacy(bundle, live, csv_path)
            raise AssertionError("Mevcut kayit ezildi")
        except FileExistsError:
            pass
        assert output.read_bytes() == saved
        print("TEST 2 PASS: Tekrar migrasyon engellendi")

        # 3: IN_PROGRESS migrasyonu
        bundle, live, csv_path = fixture(root / "progress")
        transition(bundle, "PREPARED", "IN_PROGRESS")
        record = migrate_legacy(bundle, live, csv_path)
        assert record["state"] == "IN_PROGRESS"
        print("TEST 3 PASS: IN_PROGRESS destekleniyor")

        # 4: Dogrulanmis RECOVERED migrasyonu
        bundle, live, csv_path = fixture(root / "recovered")
        make_recovered(bundle, live, csv_path)

        state_before = (
            bundle / "transaction-state.json"
        ).read_bytes()
        result_before = (
            bundle / "recovery-result.json"
        ).read_bytes()

        record = migrate_legacy(bundle, live, csv_path)

        assert record["state"] == "RECOVERED"
        assert record["recovery"] == expected_recovery(bundle)
        assert (
            bundle / "transaction-state.json"
        ).read_bytes() == state_before
        assert (
            bundle / "recovery-result.json"
        ).read_bytes() == result_before

        print("TEST 4 PASS: RECOVERED ve eski kayitlar korundu")

        # 5: Tutarsiz result migrasyonu
        bundle, live, csv_path = fixture(root / "bad-result")
        make_recovered(bundle, live, csv_path)
        result_path = bundle / "recovery-result.json"
        result = json.loads(result_path.read_text("utf-8"))
        result["csv_sha256"] = "0" * 64
        result_path.write_text(json.dumps(result), encoding="utf-8")

        assert_rejected(
            lambda: migrate_legacy(bundle, live, csv_path),
            bundle / "transaction-record.json",
            (ValueError,)
        )
        print("TEST 5 PASS: Tutarsiz result reddedildi")

        # 6: Bozulmus HTML migrasyonu
        bundle, live, csv_path = fixture(root / "bad-html")
        make_recovered(bundle, live, csv_path)
        page = live / "100.html"
        page.write_bytes(page.read_bytes() + b"\nTAMPER")

        assert_rejected(
            lambda: migrate_legacy(bundle, live, csv_path),
            bundle / "transaction-record.json",
            (ValueError,)
        )
        print("TEST 6 PASS: Bozuk HTML reddedildi")

        # 7: Eksik recovery-result migrasyonu
        bundle, live, csv_path = fixture(root / "missing-result")
        transition(bundle, "PREPARED", "IN_PROGRESS")
        transition(
            bundle, "IN_PROGRESS", "RECOVERED",
            live_dir=live, csv_path=csv_path
        )

        assert_rejected(
            lambda: migrate_legacy(bundle, live, csv_path),
            bundle / "transaction-record.json",
            (ValueError,)
        )
        print("TEST 7 PASS: Eksik result reddedildi")

        # 8: COMPLETED icin guvensiz donusume izin verme
        bundle, live, csv_path = fixture(root / "unsupported")
        state = bundle / "transaction-state.json"
        state.write_text(
            '{"state":"COMPLETED"}',
            encoding="utf-8"
        )

        assert_rejected(
            lambda: migrate_legacy(bundle, live, csv_path),
            bundle / "transaction-record.json",
            (ValueError,)
        )
        print("TEST 8 PASS: Desteklenmeyen durum reddedildi")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
