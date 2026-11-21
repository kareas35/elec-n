import tempfile
from pathlib import Path

from transaction_api import open_transaction
from transaction_migration_test import fixture
from transaction_persistent_outcome import begin
from transaction_state import load_state

with tempfile.TemporaryDirectory(prefix="v38-multistep-") as tmp:
    bundle, live, csv_path = fixture(Path(tmp) / "case")
    state = bundle / "transaction-state.json"

    begin(bundle, "op-242-multistep")

    with open_transaction(bundle) as api:
        api.guarded_transition(
            "op-242-multistep", "PREPARED", "IN_PROGRESS"
        )

    assert load_state(state) == "IN_PROGRESS"
    print("TEST 1 PASS: Ilk gecis tamamlandi")

    with open_transaction(bundle) as api:
        api.guarded_transition(
            "op-242-multistep", "IN_PROGRESS", "RECOVERED",
            live_dir=live, csv_path=csv_path
        )

    assert load_state(state) == "RECOVERED"
    print("TEST 2 PASS: Ikinci gecis tamamlandi")
