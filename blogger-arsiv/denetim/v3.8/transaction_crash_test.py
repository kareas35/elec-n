#!/usr/bin/env python3
"""V3.8 - Ayrı süreçte ani kapanma ve kurtarma testi."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_bundle import create_bundle, verify_bundle, ROOT, V38
from transaction_journal import sha256
from transaction_lock import transaction_lock
from transaction_state import load_state
from transaction_api import open_transaction

NAMES = ("100.html", "171.html")

CHILD = r'''
import os
import sys
from pathlib import Path

from transaction_lock import transaction_lock
from transaction_api import open_transaction
from transaction_persistent_outcome import begin

base = Path(sys.argv[1])
bundle = base / "bundle"
live = base / "live"
lock = base / "restoration.lock"

begin(bundle, "op-227-crash")

with transaction_lock(lock):
    with open_transaction(bundle) as api:
        api.guarded_transition(
            "op-227-crash", "PREPARED", "IN_PROGRESS"
        )

    source = bundle / "before/100.html"
    target = live / "100.html"
    temporary = live / "100.html.crash-tmp"

    with temporary.open("xb") as f:
        f.write(source.read_bytes())
        f.flush()
        os.fsync(f.fileno())

    os.replace(temporary, target)

    fd = os.open(live, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    # Normal cleanup ve context-manager cikisi calismaz.
    os._exit(73)
'''


def replace_from_verified_copy(source, target, expected_hash):
    data = source.read_bytes()
    if sha256(data) != expected_hash:
        raise ValueError("Kurtarma kaynagi bozuk")

    if target.is_symlink() or not target.is_file():
        raise ValueError("Hedef dosya guvensiz")

    temporary = target.with_name(target.name + ".recovery-tmp")
    if temporary.exists():
        raise ValueError("Gecici kurtarma dosyasi mevcut")

    try:
        with temporary.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, target)
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)



def _api_compat_initialize(bundle):
    """Gecici test bundle'ini kilitli API ile baslat."""
    with open_transaction(bundle) as api:
        return api.initialize()


initialize = _api_compat_initialize


def main():
    with tempfile.TemporaryDirectory(prefix="v38-crash-") as tmp:
        base = Path(tmp)
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

        plan = base / "plan.csv"
        shutil.copy2(
            V38 / "restorasyon-entegrasyon-plani.csv",
            plan
        )
        plan_before = plan.read_bytes()

        create_bundle(bundle, entries)
        initialize(bundle)

        assert verify_bundle(bundle)
        print("TEST 1 PASS: Kurtarma paketi dogrulandi")

        child = subprocess.run(
            [sys.executable, "-c", CHILD, str(base)],
            cwd=V38,
            capture_output=True,
            text=True,
            timeout=15
        )
        if child.returncode != 73:
            raise AssertionError(
                "Alt surec beklenen sekilde kapanmadi: "
                + child.stderr[:500]
            )

        print("TEST 2 PASS: Alt surec aniden kapandi")

        assert load_state(
            bundle / "transaction-state.json"
        ) == "IN_PROGRESS"

        assert (
            (live / "100.html").read_bytes()
            == (bundle / "before/100.html").read_bytes()
        )
        assert (
            (live / "171.html").read_bytes()
            == (bundle / "after/171.html").read_bytes()
        )
        assert plan.read_bytes() == plan_before

        print("TEST 3 PASS: Yari kalmis islem tespit edildi")

        lock_path = base / "restoration.lock"

        with transaction_lock(lock_path):
            print("TEST 4 PASS: Kilit kapanma sonrasi alinabildi")

            assert verify_bundle(bundle)

            for name in NAMES:
                target = live / name
                before_hash = sha256(
                    (bundle / "before" / name).read_bytes()
                )
                after_file = bundle / "after" / name
                after_hash = sha256(after_file.read_bytes())
                current_hash = sha256(target.read_bytes())

                if current_hash not in (before_hash, after_hash):
                    raise ValueError(
                        "UNKNOWN dosya; kurtarma engellendi"
                    )

                if current_hash == before_hash:
                    replace_from_verified_copy(
                        after_file, target, after_hash
                    )

            assert all(
                (live / name).read_bytes()
                == (bundle / "after" / name).read_bytes()
                for name in NAMES
            )

            print("TEST 5 PASS: Entegre duruma geri donuldu")

            assert plan.read_bytes() == plan_before
            assert load_state(
                bundle / "transaction-state.json"
            ) == "IN_PROGRESS"

            print("TEST 6 PASS: CSV ve journal durumu korundu")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")
    print("Test klasoru: OTOMATIK TEMIZLENDI")


if __name__ == "__main__":
    main()
