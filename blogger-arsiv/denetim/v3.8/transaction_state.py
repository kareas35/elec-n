#!/usr/bin/env python3
"""V3.8 - Transaction durum yonetimi (test altyapisi)."""

import json
import os
import tempfile
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

from transaction_bundle import verify_bundle

ALLOWED = {
    "PREPARED": {"IN_PROGRESS"},
    "IN_PROGRESS": {"COMPLETED", "RECOVERED"},
    "COMPLETED": set(),
    "RECOVERED": set(),
}


_write_scope = ContextVar(
    "v38_state_write_scope", default=False
)


@contextmanager
def _state_write_scope():
    """Yalnizca TransactionAPI yazma metotlari icin."""
    token = _write_scope.set(True)
    try:
        yield
    finally:
        _write_scope.reset(token)


def _save_state(path, state, expected=None, live_dir=None, csv_path=None):
    """API yazma kapsami disinda state degisikligini reddet."""
    if not _write_scope.get():
        raise RuntimeError(
            "Dogrudan state yazimi yasak; TransactionAPI gerekli"
        )
    path = Path(path)

    if state not in ALLOWED:
        raise ValueError("Gecersiz transaction durumu")

    if path.is_symlink():
        raise ValueError("Guvensiz state dosyasi")

    if expected is None:
        if path.exists():
            raise FileExistsError("State zaten mevcut")
    else:
        current = load_state(path)
        if current != expected:
            raise ValueError("Beklenmeyen onceki durum")
        if state not in ALLOWED[current]:
            raise ValueError("Gecersiz durum gecisi")

    # RECOVERED icin entegre HTML ve kalici CSV kopyasi zorunlu.
    if state == "RECOVERED":
        if expected != "IN_PROGRESS":
            raise ValueError("RECOVERED yalnizca IN_PROGRESS sonrasi")
        if live_dir is None or csv_path is None:
            raise ValueError("RECOVERED icin HTML ve CSV zorunlu")
        from transaction_recovery_validator import verify_recovered
        verify_recovered(path.parent, Path(live_dir), Path(csv_path))

    # COMPLETED ancak HTML ve CSV birlikte dogrulanirsa yazilir.
    if state == "COMPLETED":
        if live_dir is None or csv_path is None:
            raise ValueError("COMPLETED icin HTML ve CSV zorunlu")
        from transaction_completion_test import verify_completion
        verify_completion(path.parent, Path(live_dir), Path(csv_path))

    fd, temp = tempfile.mkstemp(
        prefix=".transaction-state-",
        dir=path.parent
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"state": state}, f)
            f.flush()
            os.fsync(f.fileno())

        if expected is None:
            # Yeni state dosyasi mevcut dosyayi ezemez.
            os.link(temp, path)
        else:
            os.replace(temp, path)

        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    finally:
        Path(temp).unlink(missing_ok=True)



def save_state(path, state, expected=None, live_dir=None, csv_path=None):
    """Eski public yazma girisi. Guvenlik nedeniyle kapali.

    Yeni state yazimlari TransactionAPI uzerinden yapilir.
    """
    raise RuntimeError(
        "Legacy save_state kapali; open_transaction kullanilmali"
    )


def load_state(path):
    path = Path(path)

    if path.is_symlink():
        raise ValueError("Guvensiz state dosyasi")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Gecersiz state kaydi")

    state = data.get("state")

    if state not in ALLOWED:
        raise ValueError("Bilinmeyen transaction durumu")

    return state


def initialize(bundle):
    bundle = Path(bundle)
    verify_bundle(bundle)
    save_state(bundle / "transaction-state.json", "PREPARED")


def transition(bundle, expected, target, live_dir=None, csv_path=None):
    bundle = Path(bundle)
    verify_bundle(bundle)
    save_state(
        bundle / "transaction-state.json",
        target,
        expected=expected,
        live_dir=live_dir,
        csv_path=csv_path
    )


def self_test():
    from transaction_bundle import create_bundle, V38, ROOT

    with tempfile.TemporaryDirectory(prefix="v38-state-") as tmp:
        base = Path(tmp)
        bundle = base / "transaction-001"

        entries = [
            {
                "name": name,
                "before": V38 / "integration-backups" /
                          (name + ".before-e14.gif"),
                "after": ROOT / "Arsiv/yayinlar" / name
            }
            for name in ("100.html", "171.html")
        ]

        create_bundle(bundle, entries)
        initialize(bundle)

        statefile = bundle / "transaction-state.json"

        assert load_state(statefile) == "PREPARED"
        print("TEST 1 PASS: PREPARED olusturuldu")

        transition(bundle, "PREPARED", "IN_PROGRESS")
        assert load_state(statefile) == "IN_PROGRESS"
        print("TEST 2 PASS: IN_PROGRESS gecisi")

        # Mevcut durum disindaki gecis reddedilmeli.
        try:
            transition(bundle, "PREPARED", "COMPLETED")
            raise AssertionError("Yanlis gecis kabul edildi")
        except ValueError:
            pass
        print("TEST 3 PASS: Gecersiz gecis reddedildi")

        # Tamamlanma testi icin yalnizca gecici kopyalar.
        import csv
        import shutil

        live = base / "live"
        live.mkdir()

        for name in ("100.html", "171.html"):
            shutil.copy2(
                bundle / "before" / name,
                live / name
            )

        plan = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )

        with plan.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)

        for row in rows:
            if (row["Original"] == "e14.gif"
                    and row["Publication"] in ("100.html", "171.html")):
                row["Integrated"] = "false"
                row["Status"] = "technical_review"

        with plan.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        transition(
            bundle, "IN_PROGRESS", "COMPLETED",
            live_dir=live, csv_path=plan
        )
        assert load_state(statefile) == "COMPLETED"
        print("TEST 4 PASS: COMPLETED kaydedildi")

        try:
            transition(bundle, "COMPLETED", "IN_PROGRESS")
            raise AssertionError("Tamamlanmis islem degistirildi")
        except ValueError:
            pass
        print("TEST 5 PASS: Tamamlanmis durum korundu")

        try:
            initialize(bundle)
            raise AssertionError("State ikinci kez olusturuldu")
        except FileExistsError:
            pass
        print("TEST 6 PASS: Mevcut state korunuyor")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    self_test()
