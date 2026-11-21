#!/usr/bin/env python3
"""V3.8 - Bundle kapsamli TransactionContext prototipi.

Yalnizca TemporaryDirectory kullanir.
Gercek yayinlari, CSV'yi veya rollback kodunu degistirmez.
"""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from transaction_bundle import create_bundle
from transaction_api import open_transaction
from transaction_persistent_outcome import begin
from transaction_state import load_state


class ScopedBundleContext:
    def __init__(self, ctx, bundle):
        ctx._require_active()

        self._ctx = ctx
        self._bundle = Path(bundle).absolute()

        if self._bundle.is_symlink():
            raise ValueError("Sembolik bundle yasak")

        info = self._bundle.stat()
        self._identity = (info.st_dev, info.st_ino)
        self._resolved = self._bundle.resolve(strict=True)

    def transition(self, bundle, expected, target):
        self._ctx._require_active()

        requested = Path(bundle).absolute()

        if requested.is_symlink():
            raise ValueError("Sembolik bundle yasak")

        if requested != self._bundle:
            raise ValueError("BUNDLE_SCOPE_MISMATCH")

        info = requested.stat()
        identity = (info.st_dev, info.st_ino)

        if identity != self._identity:
            raise ValueError("BUNDLE_IDENTITY_CHANGED")

        if requested.resolve(strict=True) != self._resolved:
            raise ValueError("BUNDLE_PATH_CHANGED")

        if expected is None:
            if target != "PREPARED":
                raise ValueError("Gecersiz baslangic durumu")
            return self._ctx.initialize()
        return self._ctx.guarded_transition(
            "op-215-bundle-a", expected, target
        )


@contextmanager
def bundle_context(bundle):
    bundle = Path(bundle).absolute()

    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("Gecersiz bundle")

    with open_transaction(bundle) as ctx:
        yield ScopedBundleContext(ctx, bundle)


def make_bundle(root, name):
    before = root / (name + "-before.html")
    after = root / (name + "-after.html")

    before.write_bytes(b"<html>before</html>")
    after.write_bytes(b"<html>after</html>")

    bundle = root / name
    create_bundle(bundle, [{
        "name": "100.html",
        "before": before,
        "after": after
    }])

    return bundle


def expect_value_error(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Yetkisiz islem kabul edildi")


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-bundle-scope-"
    ) as tmp:
        root = Path(tmp)

        a = make_bundle(root, "bundle-a")
        b = make_bundle(root, "bundle-b")

        assert a.parent == b.parent
        print("TEST 1 PASS: Iki bundle ayni kilit klasorunde")

        begin(a, "op-215-bundle-a")
        with bundle_context(a) as scoped:
            scoped.transition(a, None, "PREPARED")
            assert load_state(
                a / "transaction-state.json"
            ) == "PREPARED"
            print("TEST 2 PASS: Bundle A yetkili gecis")

            expect_value_error(
                lambda: scoped.transition(b, None, "PREPARED")
            )
            assert not (
                b / "transaction-state.json"
            ).exists()
            print("TEST 3 PASS: Bundle B yetkisiz")

            alias = root / "bundle-alias"
            alias.symlink_to(a, target_is_directory=True)

            expect_value_error(
                lambda: scoped.transition(
                    alias, "PREPARED", "IN_PROGRESS"
                )
            )
            print("TEST 4 PASS: Sembolik bundle reddedildi")

            scoped.transition(
                a, "PREPARED", "IN_PROGRESS"
            )
            assert load_state(
                a / "transaction-state.json"
            ) == "IN_PROGRESS"
            print("TEST 5 PASS: Bundle A ikinci gecis")

        try:
            scoped.transition(
                a, "IN_PROGRESS", "COMPLETED"
            )
        except RuntimeError:
            print("TEST 6 PASS: Eski context reddedildi")
        else:
            raise AssertionError("Suresi dolmus context kabul edildi")

        with bundle_context(b) as other:
            other.transition(b, None, "PREPARED")

            expect_value_error(
                lambda: other.transition(
                    a, "IN_PROGRESS", "COMPLETED"
                )
            )

        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 7 PASS: Bundle B kendi yetkisiyle calisti")

        assert load_state(
            a / "transaction-state.json"
        ) == "IN_PROGRESS"
        assert load_state(
            b / "transaction-state.json"
        ) == "PREPARED"
        print("TEST 8 PASS: Bundle durumlari izole edildi")

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Rollback guvenlik kilidi: AKTIF")


if __name__ == "__main__":
    main()
