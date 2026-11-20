#!/usr/bin/env python3
"""V3.8 - Outcome + recovery butunluk entegrasyon testi."""
import json
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_csv_baseline import capture_baseline
from transaction_lock import transaction_lock
from transaction_persistent_outcome import begin, finish, RESULT
from transaction_integrity_gate import evaluate


def check(result, expected, integrity=False):
    assert result["status"] == expected, result
    assert result["transaction_confirmed"] is False
    assert result["automatic_retry"] is False
    assert result["integrity_verified"] is integrity


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-integrity-gate-"
    ) as tmp:
        root = Path(tmp)

        sources = root / "sources"
        sources.mkdir()
        live = root / "live"
        live.mkdir()
        entries = []

        for name in ("100.html", "171.html"):
            before = sources / ("before-" + name)
            after = sources / ("after-" + name)

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

        # TEST 1: Outcome eksik ama HTML/CSV dogru.
        check(
            evaluate(bundle, live, csv_path),
            "BLOCKED"
        )
        print("TEST 1 PASS: Outcome eksik BLOCKED")

        # TEST 2: Yalnizca intent yeterli degil.
        begin(bundle, "op-169")
        check(
            evaluate(bundle, live, csv_path),
            "BLOCKED"
        )
        print("TEST 2 PASS: Intent-only BLOCKED")

        # TEST 3: Kayit eslesmesi ve dosya butunlugu.
        assert finish(bundle, "op-169") == "REVIEW_REQUIRED"

        result = evaluate(bundle, live, csv_path)
        check(result, "REVIEW_REQUIRED", True)
        print("TEST 3 PASS: Butunluk OK, onay hala yok")

        # TEST 4: HTML degistirilirse reddet.
        html = live / "100.html"
        original_html = html.read_bytes()
        html.write_bytes(original_html + b"\nTAMPER")

        check(evaluate(bundle, live, csv_path), "BLOCKED")
        html.write_bytes(original_html)
        print("TEST 4 PASS: Bozuk HTML reddedildi")

        # TEST 5: CSV degistirilirse reddet.
        original_csv = csv_path.read_bytes()
        csv_path.write_bytes(original_csv + b"\nTAMPER")

        check(evaluate(bundle, live, csv_path), "BLOCKED")
        csv_path.write_bytes(original_csv)
        print("TEST 5 PASS: Bozuk CSV reddedildi")

        # TEST 6: Bundle kopyasi bozulursa reddet.
        saved = bundle / "after" / "171.html"
        original_copy = saved.read_bytes()
        saved.write_bytes(original_copy + b"\nTAMPER")

        check(evaluate(bundle, live, csv_path), "BLOCKED")
        saved.write_bytes(original_copy)
        print("TEST 6 PASS: Bozuk bundle reddedildi")

        # TEST 7: Result bozulursa reddet.
        result_path = bundle / RESULT
        original_result = result_path.read_bytes()
        result_path.write_text(
            '{"status":"CONFIRMED"}',
            encoding="utf-8"
        )

        check(evaluate(bundle, live, csv_path), "BLOCKED")
        result_path.write_bytes(original_result)
        print("TEST 7 PASS: Bozuk outcome reddedildi")

        # TEST 8: Manifest bozulursa reddet.
        manifest = bundle / "transaction.json"
        original_manifest = manifest.read_bytes()
        manifest.write_bytes(original_manifest + b"\nTAMPER")

        check(evaluate(bundle, live, csv_path), "BLOCKED")
        manifest.write_bytes(original_manifest)
        print("TEST 8 PASS: Bozuk manifest reddedildi")

        # TEST 9: Tum gecici veriler eski haline dondu.
        result = evaluate(bundle, live, csv_path)
        check(result, "REVIEW_REQUIRED", True)
        print("TEST 9 PASS: Gecerli butunluk, manuel inceleme")

    print("\nSONUC: 9/9 TEST BASARILI")
    print("Outcome + HTML + CSV entegrasyonu: TEST EDILDI")
    print("Kapsam: 100.html ve 171.html")
    print("Nihai transaction onayi: YOK")
    print("Otomatik retry/rollback: YOK")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
