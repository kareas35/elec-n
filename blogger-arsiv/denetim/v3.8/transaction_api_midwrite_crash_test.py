#!/usr/bin/env python3
"""V3.8 - State yayinlama sirasinda ani surec cikisi testleri.

Yalnizca TemporaryDirectory altinda calisir.
Mevcut transaction modulleri degistirilmez.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_bundle_scope_test import make_bundle
from transaction_state import load_state

CHILD = r'''
import os
import sys
from pathlib import Path
from transaction_api import open_transaction
from transaction_persistent_outcome import begin
import transaction_state
from types import SimpleNamespace

bundle = Path(sys.argv[1])
scenario = sys.argv[2]

real_link = os.link
real_replace = os.replace
real_fsync = os.fsync
fsync_count = 0

def injected_link(src, dst, *args, **kwargs):
    if Path(dst).name == "transaction-state.json":
        if scenario == "before_link":
            os._exit(71)
        result = real_link(src, dst, *args, **kwargs)
        if scenario == "after_link":
            os._exit(72)
        return result
    return real_link(src, dst, *args, **kwargs)

def injected_replace(src, dst, *args, **kwargs):
    if Path(dst).name == "transaction-state.json":
        if scenario == "before_replace":
            os._exit(73)
        result = real_replace(src, dst, *args, **kwargs)
        if scenario == "after_replace":
            os._exit(74)
        return result
    return real_replace(src, dst, *args, **kwargs)

def injected_fsync(fd):
    global fsync_count
    fsync_count += 1
    if scenario == "before_file_fsync" and fsync_count == 1:
        os._exit(75)
    if scenario == "before_dir_fsync" and fsync_count == 2:
        os._exit(76)
    return real_fsync(fd)

# INTENT kilit disinda ve hata enjeksiyonundan once olusturulur.
if scenario not in ("before_link", "after_link",
                    "before_file_fsync"):
    begin(bundle, "op-225-midwrite")

# Yalnizca state yazim katmanindaki OS cagrilari etkilenir.
proxy = SimpleNamespace(**vars(os))
proxy.link = injected_link
proxy.replace = injected_replace
proxy.fsync = injected_fsync
transaction_state.os = proxy

with open_transaction(bundle) as api:
    if scenario in ("before_link", "after_link",
                    "before_file_fsync"):
        api.initialize()
    else:
        api.guarded_transition(
            "op-225-midwrite", "PREPARED", "IN_PROGRESS"
        )

sys.exit(99)
'''

SCENARIOS = (
    ("before_link", 71, None),
    ("after_link", 72, "PREPARED"),
    ("before_replace", 73, "PREPARED"),
    ("after_replace", 74, "IN_PROGRESS"),
    ("before_file_fsync", 75, None),
    ("before_dir_fsync", 76, "IN_PROGRESS"),
)


def run_child(bundle, scenario):
    return subprocess.run(
        [sys.executable, "-c", CHILD, str(bundle), scenario],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def main():
    with tempfile.TemporaryDirectory(
        prefix="v38-midwrite-crash-"
    ) as tmp:
        root = Path(tmp)
        bundles = []

        for index, (scenario, exit_code, expected) in enumerate(
            SCENARIOS, start=1
        ):
            folder = root / ("case-" + str(index))
            folder.mkdir()

            bundle = make_bundle(folder, "bundle")
            state = bundle / "transaction-state.json"

            if scenario in (
                "before_replace",
                "after_replace",
                "before_dir_fsync",
            ):
                with open_transaction(bundle) as api:
                    api.initialize()

            result = run_child(bundle, scenario)

            assert result.returncode == exit_code, (
                scenario, result.returncode, result.stderr
            )

            if expected is None:
                assert not state.exists()
            else:
                assert load_state(state) == expected
                assert json.loads(
                    state.read_text(encoding="utf-8")
                ) == {"state": expected}

            attempt = bundle / "transaction-guarded-attempt.json"
            if scenario in (
                "before_replace", "after_replace", "before_dir_fsync"
            ):
                assert attempt.is_file(), scenario
            else:
                assert not attempt.exists(), scenario

            bundles.append((bundle, expected))

            print(
                f"TEST {index} PASS: {scenario} "
                f"-> {expected or 'STATE_YOK'}"
            )

        # TEST 7: Cokmus sureclerin kilitleri yeniden alinabilir.
        for bundle, expected in bundles:
            with open_transaction(bundle):
                state = bundle / "transaction-state.json"
                if expected is None:
                    assert not state.exists()
                else:
                    assert load_state(state) == expected

        print("TEST 7 PASS: Tum kilitler yeniden alinabildi")

        # TEST 8: Kalici state disindaki temp dosyalar
        # silinmeden kalabilir; gercek sistemde otomatik
        # temizleme karari verilmemeli.
        orphan_count = 0

        for bundle, _ in bundles:
            orphans = list(bundle.glob(".transaction-state-*"))
            orphan_count += len(orphans)

            for orphan in orphans:
                assert orphan.is_file()
                assert not orphan.is_symlink()

        assert orphan_count >= 1
        print("TEST 8 PASS: Crash temp dosyalari korundu")
        print("Kalan gecici state dosyalari:", orphan_count)

    print("\nSONUC: 8/8 TEST BASARILI")
    print("Gercek yayinlar: DEGISTIRILMEDI")
    print("Gercek CSV: DEGISTIRILMEDI")
    print("Otomatik orphan silme: YOK")
    print("Rollback guvenlik kilidi: AKTIF")
    print("NOT: Elektrik kesintisi dayanimi kanitlanmadi")


if __name__ == "__main__":
    main()
