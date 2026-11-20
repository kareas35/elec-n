#!/usr/bin/env python3
"""V3.8 - Gercek TransactionAPI + outcome binding entegrasyon testi.

Yalnizca TemporaryDirectory kullanir.
Gercek restorasyon, rollback, retry ve silme islemi YOK.
"""
import hashlib
import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_bundle import create_bundle
from transaction_csv_baseline import capture_baseline
from transaction_integrity_gate import evaluate
from transaction_journal import atomic_json_write
from transaction_lock import transaction_lock
from transaction_persistent_outcome import begin, finish, digest
from transaction_state import load_state
from transaction_state_binding import BINDING, verify_binding


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-real-api-binding-"
    ) as tmp:
        root = Path(tmp)
        sources = root / "sources"
        live = root / "live"
        sources.mkdir()
        live.mkdir()

        entries = []

        for name in ("100.html", "171.html"):
            before = sources / ("old-" + name)
            after = sources / ("new-" + name)

            before.write_text(
                "<html>OLD " + name + "</html>",
                encoding="utf-8"
            )
            after.write_text(
                "<html>NEW " + name + "</html>",
                encoding="utf-8"
            )

            (live / name).write_bytes(after.read_bytes())

            entries.append({
                "name": name,
                "before": before,
                "after": after,
            })

        bundle = root / "bundle"
        create_bundle(bundle, entries)

        csv_path = root / "plan.csv"
        csv_path.write_text(
            "name,status\n100.html,ready\n171.html,ready\n",
            encoding="utf-8"
        )

        with transaction_lock(root / "transaction.lock"):
            assert capture_baseline(bundle, csv_path)

        state_path = bundle / "transaction-state.json"
        manifest_path = bundle / "transaction.json"
        operation_id = "operation-174"

        # TEST 1: State degismeden once intent yazilir.
        intent = begin(bundle, operation_id)

        assert (bundle / "transaction-outcome-intent.json").is_file()
        assert not state_path.exists()
        print("TEST 1 PASS: Intent state degisiminden once")

        # TEST 2: Gercek API ile PREPARED.
        with open_transaction(bundle) as api:
            api.initialize()

        assert load_state(state_path) == "PREPARED"
        print("TEST 2 PASS: TransactionAPI PREPARED")

        # TEST 3: Gercek API ile IN_PROGRESS.
        with open_transaction(bundle) as api:
            api.transition("PREPARED", "IN_PROGRESS")

        assert load_state(state_path) == "IN_PROGRESS"
        print("TEST 3 PASS: TransactionAPI IN_PROGRESS")

        # TEST 4: Gercek API ile RECOVERED.
        # Mevcut recovery validator HTML ve CSV'yi dogrular.
        with open_transaction(bundle) as api:
            api.transition(
                "IN_PROGRESS",
                "RECOVERED",
                live_dir=live,
                csv_path=csv_path,
            )

        assert load_state(state_path) == "RECOVERED"
        print("TEST 4 PASS: TransactionAPI RECOVERED")

        # TEST 5: Outcome sonucu kendi basina onay degil.
        assert finish(bundle, operation_id) == "REVIEW_REQUIRED"

        integrity = evaluate(bundle, live, csv_path)
        assert integrity["status"] == "REVIEW_REQUIRED"
        assert integrity["integrity_verified"] is True
        assert integrity["transaction_confirmed"] is False
        print("TEST 5 PASS: Outcome ve butunluk onay vermedi")

        # Test amacli baglanti kaydi.
        # Uretim TransactionAPI bu kaydi HENUZ uretmiyor.
        manifest_hash = sha(manifest_path)

        record = {
            "version": 1,
            "operation_id": operation_id,
            "expected_state": "IN_PROGRESS",
            "target_state": "RECOVERED",
            "manifest_sha256": manifest_hash,
            "state_sha256": sha(state_path),
            "intent_sha256": digest(intent),
        }

        binding_path = bundle / BINDING

        def check(status, op=operation_id):
            result = verify_binding(
                bundle, live, csv_path,
                op, "IN_PROGRESS",
                "RECOVERED", manifest_hash
            )
            assert result["status"] == status, result
            assert result["transaction_confirmed"] is False
            assert result["automatic_retry"] is False
            return result

        # TEST 6: Binding olmadan onay yok.
        check("BLOCKED")
        print("TEST 6 PASS: Binding eksik BLOCKED")

        atomic_json_write(binding_path, record)

        result = check("REVIEW_REQUIRED")
        assert result["binding_verified"] is True
        print("TEST 7 PASS: Gercek API state binding uyumlu")

        # TEST 8: Yanlis islem kimligi reddedilir.
        check("BLOCKED", op="different-operation")
        print("TEST 8 PASS: Baska operation_id BLOCKED")

        # TEST 9: HTML bozulursa binding de reddedilir.
        page = live / "100.html"
        original_html = page.read_bytes()
        page.write_bytes(original_html + b"\nTAMPER")

        check("BLOCKED")
        page.write_bytes(original_html)
        print("TEST 9 PASS: Bozuk HTML binding engellendi")

        # TEST 10: Terminal state'den gecis reddedilir.
        with open_transaction(bundle) as api:
            try:
                api.transition("RECOVERED", "IN_PROGRESS")
            except ValueError:
                pass
            else:
                raise AssertionError("Terminal state degistirildi")

        assert load_state(state_path) == "RECOVERED"
        check("REVIEW_REQUIRED")
        print("TEST 10 PASS: Terminal state korundu")

    print("\nSONUC: 10/10 TEST BASARILI")
    print("Gercek TransactionAPI state gecisi: TEST EDILDI")
    print("Test ortami: TemporaryDirectory")
    print("Binding kaydi: TEST KODUNDA OLUSTURULDU")
    print("Otomatik API binding entegrasyonu: YOK")
    print("Nihai transaction onayi: YOK")
    print("Gercek disk durability garantisi: KANITLANMADI")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
