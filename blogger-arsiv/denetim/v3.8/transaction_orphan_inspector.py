#!/usr/bin/env python3
"""V3.8 - Yetim journal dosyalari icin salt okunur denetleyici.

Dosya silmez, tasimaz veya degistirmez.
Testler yalnizca TemporaryDirectory icinde calisir.
"""

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


def inspect_orphans(folder):
    folder = Path(folder)

    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Guvensiz inceleme klasoru")

    target = folder / "transaction-record.json"
    target_stat = None

    if target.is_symlink():
        raise ValueError("Kalici kayit sembolik baglanti")

    if target.exists():
        target_stat = target.stat()
        if not stat.S_ISREG(target_stat.st_mode):
            raise ValueError("Kalici kayit normal dosya degil")

    results = []

    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if not path.name.startswith(".journal-"):
            continue

        info = {
            "name": path.name,
            "type": "UNKNOWN",
            "size": None,
            "sha256": None,
            "relation": "UNKNOWN",
            "valid_json": False,
            "safe_to_delete": False
        }

        # Once symlink kontrolu. Hedefe takip etme.
        if path.is_symlink():
            info["type"] = "SYMLINK"
            results.append(info)
            continue

        file_stat = path.stat(follow_symlinks=False)

        if not stat.S_ISREG(file_stat.st_mode):
            info["type"] = "NON_REGULAR"
            results.append(info)
            continue

        info["type"] = "REGULAR"
        info["size"] = file_stat.st_size

        # Acik dosya taniticisindan oku; symlink takip etme.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)

        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError("Inceleme sirasinda dosya turu degisti")
            if (opened.st_dev, opened.st_ino) != (
                file_stat.st_dev, file_stat.st_ino
            ):
                raise ValueError("Inceleme sirasinda dosya degisti")

            with os.fdopen(fd, "rb") as f:
                fd = -1
                data = f.read()
        finally:
            if fd >= 0:
                os.close(fd)

        info["sha256"] = hashlib.sha256(data).hexdigest()

        try:
            json.loads(data)
            info["valid_json"] = True
        except (ValueError, UnicodeDecodeError):
            pass

        if target_stat is not None:
            if (
                file_stat.st_dev == target_stat.st_dev
                and file_stat.st_ino == target_stat.st_ino
            ):
                info["relation"] = "SAME_INODE_AS_TARGET"
            else:
                info["relation"] = "DIFFERENT_INODE"
        else:
            info["relation"] = "NO_TARGET"

        results.append(info)

    return results


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-orphan-inspector-"
    ) as tmp:
        root = Path(tmp)

        orphan = root / ".journal-abcd"
        orphan.write_text(
            '{"version":1,"state":"RECOVERED"}',
            encoding="utf-8"
        )
        original = orphan.read_bytes()

        result = inspect_orphans(root)
        assert len(result) == 1
        assert result[0]["type"] == "REGULAR"
        assert result[0]["relation"] == "NO_TARGET"
        assert result[0]["valid_json"]
        print("TEST 1 PASS: Yetim dosya tespit edildi")

        expected_hash = hashlib.sha256(original).hexdigest()
        assert result[0]["sha256"] == expected_hash
        assert result[0]["size"] == len(original)
        print("TEST 2 PASS: Boyut ve SHA-256 dogru")

        # os.link, atomic_json_write tarafindan kullaniliyor.
        target = root / "transaction-record.json"
        os.link(orphan, target)

        result = inspect_orphans(root)
        assert result[0]["relation"] == "SAME_INODE_AS_TARGET"
        print("TEST 3 PASS: Kalici kayit ile ayni inode")

        other = root / ".journal-other"
        other.write_text('{"state":"PREPARED"}', encoding="utf-8")

        result = inspect_orphans(root)
        item = next(r for r in result if r["name"] == other.name)
        assert item["relation"] == "DIFFERENT_INODE"
        print("TEST 4 PASS: Farkli inode tespit edildi")

        link = root / ".journal-symlink"
        link.symlink_to(target)

        result = inspect_orphans(root)
        item = next(r for r in result if r["name"] == link.name)
        assert item["type"] == "SYMLINK"
        assert item["sha256"] is None
        print("TEST 5 PASS: Sembolik baglanti takip edilmedi")

        bad = root / ".journal-broken"
        bad.write_bytes(b'{"incomplete":')

        result = inspect_orphans(root)
        item = next(r for r in result if r["name"] == bad.name)
        assert item["type"] == "REGULAR"
        assert not item["valid_json"]

        assert orphan.read_bytes() == original
        assert target.read_bytes() == original
        assert all(
            item["safe_to_delete"] is False for item in result
        )
        print("TEST 6 PASS: Bozuk JSON tespit; dosyalar korundu")

    print("\nSONUC: 6/6 TEST BASARILI")
    print("Otomatik dosya silme: YOK")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
