#!/usr/bin/env python3
"""V3.8 - Kilitli transaction akis testi.

Sadece gecici klasorde calisir.
Gercek yayinlara ve CSV'ye yazmaz.
"""
import csv
import shutil
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, V38, ROOT
from transaction_lock import transaction_lock
from transaction_state import initialize, transition, load_state

NAMES = ("100.html", "171.html")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-locked-flow-"
    ) as tmp:
        base = Path(tmp)
        bundle = base / "bundle"
        live = base / "live"
        live.mkdir()

        entries = []

        for name in NAMES:
            before = (
                V38 / "integration-backups" /
                (name + ".before-e14.gif")
            )
            after = ROOT / "Arsiv/yayinlar" / name

            entries.append({
                "name": name,
                "before": before,
                "after": after,
            })
            shutil.copy2(after, live / name)

        create_bundle(bundle, entries)

        plan = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        # Kilit bundle disinda; tum islemler ayni
        # dosya yolunu kullanmali.
        lock_path = base / "restoration.lock"

        with transaction_lock(lock_path):
            initialize(bundle)
            assert load_state(
                bundle / "transaction-state.json"
            ) == "PREPARED"
            print("TEST 1 PASS: Kilit altinda PREPARED")

            transition(bundle, "PREPARED", "IN_PROGRESS")
            assert load_state(
                bundle / "transaction-state.json"
            ) == "IN_PROGRESS"
            print("TEST 2 PASS: Kilit altinda IN_PROGRESS")

            # Ikinci islem ayni kilidi alamaz.
            try:
                with transaction_lock(lock_path):
                    raise AssertionError("Cakisma engellenmedi")
            except RuntimeError as error:
                assert "ISLEM KILITLI" in str(error)

            print("TEST 3 PASS: Ikinci islem engellendi")

            # HTML ve CSV eski durumdayken COMPLETED yasak.
            statefile = bundle / "transaction-state.json"
            state_before = statefile.read_bytes()

            try:
                transition(
                    bundle, "IN_PROGRESS", "COMPLETED",
                    live_dir=live,
                    csv_path=plan
                )
                raise AssertionError(
                    "Eksik islem tamamlandi sayildi"
                )
            except ValueError:
                pass

            assert statefile.read_bytes() == state_before
            print("TEST 4 PASS: Eksik islem tamamlanamadi")

            # Yalnizca gecici HTML kopyalarini geri al.
            for name in NAMES:
                shutil.copy2(bundle / "before" / name, live / name)

            # Yalnizca gecici CSV'yi guncelle.
            with plan.open(
                encoding="utf-8-sig", newline=""
            ) as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames
                rows = list(reader)

            for row in rows:
                if (
                    row["Original"] == "e14.gif"
                    and row["Publication"] in NAMES
                ):
                    row["Integrated"] = "false"
                    row["Status"] = "technical_review"

            with plan.open(
                "w", encoding="utf-8-sig", newline=""
            ) as f:
                writer = csv.DictWriter(
                    f, fieldnames=fields
                )
                writer.writeheader()
                writer.writerows(rows)

            transition(
                bundle, "IN_PROGRESS", "COMPLETED",
                live_dir=live,
                csv_path=plan
            )

            assert load_state(statefile) == "COMPLETED"
            print("TEST 5 PASS: Dogrulanmis COMPLETED")

        # Islem bittikten sonra kilit yeniden alinabilir.
        with transaction_lock(lock_path):
            assert load_state(statefile) == "COMPLETED"

        print("TEST 6 PASS: Kilit guvenle serbest kaldi")

        # Tamamlanan islem tekrar degistirilemez.
        try:
            transition(bundle, "COMPLETED", "IN_PROGRESS")
            raise AssertionError("Tamamlanmis islem degisti")
        except ValueError:
            pass

        print("TEST 7 PASS: Tamamlanmis islem korundu")

    print("\nSONUC: 7/7 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
