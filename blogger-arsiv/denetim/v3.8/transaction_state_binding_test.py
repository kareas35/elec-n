#!/usr/bin/env python3
"""V3.8 - State ve outcome baglanti testleri."""
import hashlib
import json
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_csv_baseline import capture_baseline
from transaction_lock import transaction_lock
from transaction_journal import atomic_json_write
from transaction_persistent_outcome import (
    begin, finish, digest
)
from transaction_state_binding import (
    BINDING, verify_binding
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-state-binding-"
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

            before.write_text("OLD " + name, encoding="utf-8")
            after.write_text("NEW " + name, encoding="utf-8")
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

        operation_id = "operation-172"
        intent = begin(bundle, operation_id)
        assert finish(bundle, operation_id) == "REVIEW_REQUIRED"

        # Sentetik state: gercek TransactionAPI gecisi DEGIL.
        state_path = bundle / "transaction-state.json"
        state_path.write_text(
            '{"state":"RECOVERED"}',
            encoding="utf-8"
        )

        manifest_path = bundle / "transaction.json"
        manifest_hash = sha(manifest_path.read_bytes())

        record = {
            "version": 1,
            "operation_id": operation_id,
            "expected_state": "IN_PROGRESS",
            "target_state": "RECOVERED",
            "manifest_sha256": manifest_hash,
            "state_sha256": sha(state_path.read_bytes()),
            "intent_sha256": digest(intent),
        }

        binding_path = bundle / BINDING

        def check(status, op=operation_id,
                  previous="IN_PROGRESS", target="RECOVERED",
                  manifest=manifest_hash):
            result = verify_binding(
                bundle, live, csv_path,
                op, previous, target, manifest
            )
            assert result["status"] == status, result
            assert result["transaction_confirmed"] is False
            assert result["automatic_retry"] is False
            return result

        # TEST 1: Baglanti kaydi yok.
        check("BLOCKED")
        print("TEST 1 PASS: Eksik baglanti BLOCKED")

        atomic_json_write(binding_path, record)

        # TEST 2: Kayitlar eslesiyor.
        result = check("REVIEW_REQUIRED")
        assert result["binding_verified"] is True
        print("TEST 2 PASS: Eslesen kayit REVIEW_REQUIRED")

        # TEST 3: Yanlis operation_id.
        check("BLOCKED", op="another-operation")
        print("TEST 3 PASS: Yanlis operation_id BLOCKED")

        # TEST 4: Yanlis onceki state.
        check("BLOCKED", previous="PREPARED")
        print("TEST 4 PASS: Yanlis onceki state BLOCKED")

        # TEST 5: Yanlis manifest SHA-256.
        check("BLOCKED", manifest="0" * 64)
        print("TEST 5 PASS: Yanlis manifest hash BLOCKED")

        # TEST 6: State icerigi degistirildi.
        original_state = state_path.read_bytes()
        state_path.write_text(
            '{"state":"COMPLETED"}',
            encoding="utf-8"
        )
        check("BLOCKED")
        state_path.write_bytes(original_state)
        print("TEST 6 PASS: State uyusmazligi BLOCKED")

        # TEST 7: Baglanti kaydi bozuldu.
        original_binding = binding_path.read_bytes()
        binding_path.write_text(
            '{"version":1}',
            encoding="utf-8"
        )
        check("BLOCKED")
        binding_path.write_bytes(original_binding)
        print("TEST 7 PASS: Bozuk baglanti BLOCKED")

        # TEST 8: Baglanti kaydi sembolik yapildi.
        # Bu testteki dosyalar gecici klasordedir.
        alias = root / "binding-copy.json"
        alias.write_bytes(original_binding)
        binding_path.unlink()
        binding_path.symlink_to(alias)

        check("BLOCKED")
        print("TEST 8 PASS: Sembolik baglanti BLOCKED")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("State/outcome baglanti kontrolu: PROTOTIP")
    print("Gercek state gecisi: TEST EDILMEDI")
    print("Kayit provenansi: KANITLANMADI")
    print("Nihai transaction onayi: YOK")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar ve CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
