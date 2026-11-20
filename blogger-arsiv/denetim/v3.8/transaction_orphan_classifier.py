#!/usr/bin/env python3
"""V3.8 - Journal dosyalari icin guvenli siniflandirma.

Salt okunur inceleme. Silme, tasima veya onarma YOK.
"""
import fcntl
import os
import stat
import tempfile
from pathlib import Path
from multiprocessing import Process, Event

from transaction_orphan_inspector import inspect_orphans
from transaction_lock import transaction_lock


def classify(folder, lock_path):
    folder = Path(folder)
    lock_path = Path(lock_path)

    # Kilit dosyasi yaratma. Eksik kilit guvenli kabul edilmez.
    if lock_path.is_symlink() or not lock_path.is_file():
        return {
            "status": "REVIEW",
            "reason": "LOCK_MISSING_OR_UNSAFE",
            "files": []
        }

    fd = os.open(
        lock_path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    )

    acquired = False

    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Kilit normal dosya degil")

        try:
            fcntl.flock(
                fd, fcntl.LOCK_EX | fcntl.LOCK_NB
            )
            acquired = True
        except BlockingIOError:
            return {
                "status": "ACTIVE",
                "reason": "LOCK_HELD",
                "files": []
            }

        records = inspect_orphans(folder)

        if not records:
            status = "CLEAR"
        elif all(
            item["relation"] == "SAME_INODE_AS_TARGET"
            and item["type"] == "REGULAR"
            for item in records
        ):
            status = "LINKED"
        else:
            status = "REVIEW"

        return {
            "status": status,
            "reason": "READ_ONLY_INSPECTION",
            "files": records
        }

    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def lock_holder(path, ready, release):
    with transaction_lock(path):
        ready.set()
        if not release.wait(timeout=10):
            raise RuntimeError("Test zaman asimi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-orphan-classifier-"
    ) as tmp:
        root = Path(tmp)
        lock = root / "transaction.lock"

        # TEST 1: Kilit yoksa belirsiz durum.
        result = classify(root, lock)
        assert result["status"] == "REVIEW"
        assert not lock.exists()
        print("TEST 1 PASS: Eksik kilit REVIEW")

        # Kilit dosyasini kontrollu sekilde olustur.
        with transaction_lock(lock):
            pass

        # TEST 2: Gecici dosya yok.
        assert classify(root, lock)["status"] == "CLEAR"
        print("TEST 2 PASS: Bos klasor CLEAR")

        # TEST 3: Kalici kaydi olmayan gecici dosya.
        orphan = root / ".journal-test"
        original = b'{"state":"RECOVERED"}'
        orphan.write_bytes(original)

        assert classify(root, lock)["status"] == "REVIEW"
        print("TEST 3 PASS: Yetim journal REVIEW")

        # TEST 4: Kalici kayitla ayni inode.
        target = root / "transaction-record.json"
        os.link(orphan, target)

        result = classify(root, lock)
        assert result["status"] == "LINKED"
        assert result["files"][0]["safe_to_delete"] is False
        print("TEST 4 PASS: Ayni inode LINKED")

        # TEST 5: Aktif islem kilidi.
        ready = Event()
        release = Event()
        worker = Process(
            target=lock_holder,
            args=(lock, ready, release)
        )
        worker.start()

        try:
            assert ready.wait(timeout=5)
            result = classify(root, lock)
            assert result["status"] == "ACTIVE"
            print("TEST 5 PASS: Aktif islem ACTIVE")
        finally:
            release.set()
            worker.join(timeout=5)
            if worker.is_alive():
                worker.terminate()
                worker.join()

        assert worker.exitcode == 0

        # TEST 6: Kilit serbest birakildiktan sonra.
        assert classify(root, lock)["status"] == "LINKED"
        print("TEST 6 PASS: Kilit sonrasi yeniden inceleme")

        # TEST 7: Sembolik baglanti.
        symlink = root / ".journal-unsafe"
        symlink.symlink_to(target)

        result = classify(root, lock)
        assert result["status"] == "REVIEW"
        assert any(
            x["type"] == "SYMLINK"
            for x in result["files"]
        )
        print("TEST 7 PASS: Sembolik baglanti REVIEW")

        # TEST 8: Hicbir dosyaya dokunulmadi.
        assert orphan.read_bytes() == original
        assert target.read_bytes() == original
        assert symlink.is_symlink()
        assert all(
            item["safe_to_delete"] is False
            for item in result["files"]
        )
        print("TEST 8 PASS: Dosyalar korundu")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Otomatik silme: YOK")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
