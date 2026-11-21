
"""V3.8 transaction testlerini ayri sureclerde calistirir."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
tests = sorted(root.glob("*test.py"))
passed = []
failed = []
failure_output = {}

for path in tests:
    print("CALISIYOR:", path.name, flush=True)

    command = [sys.executable, str(path)]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            passed.append(path.name)
            print("PASS:", path.name, flush=True)
        else:
            failed.append(path.name)
            failure_output[path.name] = result.stdout + result.stderr
            print("FAIL:", path.name, flush=True)
            print((result.stdout + result.stderr)[-3000:], flush=True)
    except subprocess.TimeoutExpired:
        failed.append(path.name)
        print("TIMEOUT:", path.name, flush=True)

print()
print("TOPLAM:", len(tests))
print("BASARILI:", len(passed))
print("BASARISIZ:", len(failed))

if failed:
    print("BASARISIZ DOSYALAR:")
    for name in failed:
        print("-", name)


# Bilinen uyumsuzluklari yalnizca raporda siniflandir.
legacy = {
    "transaction_api_binding_integration_test.py",
    "transaction_atomic_crash_test.py",
    "transaction_consistency_test.py",
    "transaction_context_integration_test.py",
    "transaction_locked_flow_test.py",
    "transaction_migration_crash_test.py",
    "transaction_migration_test.py",
    "transaction_recovered_state_test.py",
    "transaction_recovered_test.py",
}

print("SINIFLANDIRMA:")
for name in failed:
    output = failure_output.get(name, "")
    if (name == "transaction_multistep_test.py"
            and "Onceki state girisimi mevcut" in output):
        category = "MULTISTEP_BLOCKED"
    elif (name in legacy
            and "Intentsiz transition kapali" in output):
        category = "KNOWN_INCOMPATIBILITY"
    else:
        category = "FAIL"
    print(f"{category}: {name}")

sys.exit(1 if failed else 0)
