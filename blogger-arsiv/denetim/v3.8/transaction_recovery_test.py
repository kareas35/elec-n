#!/usr/bin/env python3
"""V3.8: Kesinti sonrasi kurtarma prototip testi.

SADECE gecici klasor kullanir. Gercek yayinlari degistirmez.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from transaction_journal import (
    create_journal,
    inspect_transaction,
    sha256,
)

V38 = Path(__file__).resolve().parent
ROOT = V38.parents[1]
NAMES = ("100.html", "171.html")


def safe_replace(destination, data):
    """Gecici klasordeki dosyayi atomik olarak degistir."""
    temporary = destination.with_name(destination.name + ".test-tmp")
    if temporary.exists():
        raise RuntimeError("Gecici dosya zaten var")

    try:
        with temporary.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def recover(journal_path, live_dir, integrated_dir, fail_after=None):
    """Tum dosyalari once dogrula, sonra entegre duruma getir."""
    states = inspect_transaction(journal_path, live_dir)

    if any(state == "UNKNOWN" for state in states.values()):
        raise ValueError("UNKNOWN: Otomatik kurtarma yasak")

    journal = json.loads(journal_path.read_text(encoding="utf-8"))

    # Degisiklikten once butun kaynaklari denetle.
    pending = []
    for entry in journal["entries"]:
        name = entry["name"]
        source = integrated_dir / name

        if source.is_symlink() or not source.is_file():
            raise ValueError("Kurtarma kaynagi bulunamadi")

        data = source.read_bytes()
        if sha256(data) != entry["after_sha256"]:
            raise ValueError("Kurtarma kopyasi dogrulanamadi")

        if states[name] == "RESTORED":
            pending.append((live_dir / name, data))

    # Yalnizca gecici test klasorundeki dosyalar.
    for index, (destination, data) in enumerate(pending, 1):
        safe_replace(destination, data)

        if fail_after == index:
            raise OSError("SIMULATED INTERRUPTION")

    final = inspect_transaction(journal_path, live_dir)
    if not all(v == "INTEGRATED" for v in final.values()):
        raise RuntimeError("Kurtarma tamamlanamadi")

    return len(pending)


with tempfile.TemporaryDirectory(prefix="v38-recovery-") as tmp:
    folder = Path(tmp)
    before = folder / "before"
    after = folder / "after"
    live = folder / "live"

    for directory in (before, after, live):
        directory.mkdir()

    entries = []

    for name in NAMES:
        shutil.copy2(
            V38 / "integration-backups" / (name + ".before-e14.gif"),
            before / name
        )
        shutil.copy2(
            ROOT / "Arsiv/yayinlar" / name,
            after / name
        )
        shutil.copy2(after / name, live / name)

        entries.append({
            "name": name,
            "before": before / name,
            "after": after / name
        })

    journal = folder / "transaction.json"
    create_journal(journal, entries)

    # TEST 1: Journal ve iki yayin taniniyor.
    assert inspect_transaction(journal, live) == {
        "100.html": "INTEGRATED",
        "171.html": "INTEGRATED"
    }
    print("TEST 1 PASS: Baslangic tutarli")

    # TEST 2: Iki yayini da geri alinmis hale getir.
    for name in NAMES:
        shutil.copy2(before / name, live / name)

    assert set(inspect_transaction(journal, live).values()) == {
        "RESTORED"
    }
    print("TEST 2 PASS: Geri alinmis dosyalar tanindi")

    # TEST 3: Ilk dosyadan sonra yapay kesinti.
    try:
        recover(journal, live, after, fail_after=1)
        raise AssertionError("Kesinti olusmadi")
    except OSError as error:
        assert "SIMULATED INTERRUPTION" in str(error)

    assert inspect_transaction(journal, live) == {
        "100.html": "INTEGRATED",
        "171.html": "RESTORED"
    }
    print("TEST 3 PASS: Kesinti sonrasi karma durum tanindi")

    # TEST 4: Kurtarma yeniden calistirilinca tamamlaniyor.
    count = recover(journal, live, after)
    assert count == 1
    assert all(
        (live / name).read_bytes() == (after / name).read_bytes()
        for name in NAMES
    )
    print("TEST 4 PASS: Kesinti sonrasi kurtarma tamamlandi")

    # TEST 5: Tekrar calistirma dosyalari degistirmiyor.
    assert recover(journal, live, after) == 0
    print("TEST 5 PASS: Tekrar calistirma guvenli")

    # TEST 6: Beklenmeyen degisiklik otomatik kurtarmayi durdurur.
    (live / "171.html").write_bytes(
        (live / "171.html").read_bytes() + b"\nUNEXPECTED"
    )
    snapshot100 = (live / "100.html").read_bytes()

    try:
        recover(journal, live, after)
        raise AssertionError("UNKNOWN kabul edildi")
    except ValueError as error:
        assert "UNKNOWN" in str(error)

    assert (live / "100.html").read_bytes() == snapshot100
    print("TEST 6 PASS: UNKNOWN durumunda kurtarma engellendi")

print("\nSONUC: 6/6 TEST BASARILI")
print("Gercek yayinlar: DEGISTIRILMEDI")
print("Gercek CSV: DEGISTIRILMEDI")
print("Rollback guvenlik kilidi: KORUNDU")
print("Gecici test verileri: OTOMATIK TEMIZLENDI")
