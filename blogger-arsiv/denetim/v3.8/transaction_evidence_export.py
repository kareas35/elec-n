"""V3.8 kanit paketi olusturma. Onay veya imza uretmez."""

import hashlib
import json
from pathlib import Path

from transaction_independent_verifier import collect_step_evidence


def sha256_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Gecersiz kanit dosyasi")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_evidence_package(bundle, live_dir, csv_path):
    """Yalnizca step 1 icin inceleme paketi hazirlar."""
    bundle = Path(bundle)
    live_dir = Path(live_dir)
    csv_path = Path(csv_path)

    collected = collect_step_evidence(bundle, 1)
    if collected["status"] != "EVIDENCE_COLLECTED_REVIEW_REQUIRED":
        raise ValueError("Transaction kanitlari hazir degil")

    manifest = bundle / "transaction.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Manifest bulunamadi")

    document = json.loads(manifest.read_text(encoding="utf-8"))
    entries = document["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("Gecersiz manifest")

    html_hashes = {}
    for entry in entries:
        name = entry["name"]
        if (
            not isinstance(name, str)
            or not name.endswith(".html")
            or Path(name).name != name
            or name in html_hashes
        ):
            raise ValueError("Gecersiz HTML adi")
        html_hashes[name] = sha256_file(live_dir / name)

    intent = collected["intent"]
    attempt = collected["attempt"]

    if attempt["operation_id"] != intent["operation_id"]:
        raise ValueError("Operation ID uyusmuyor")

    return {
        "schema_version": 1,
        "purpose": "V38_INDEPENDENT_REVIEW",
        "transaction": {
            "operation_id": intent["operation_id"],
            "step": 1,
            "expected_state": "PREPARED",
            "target_state": "IN_PROGRESS",
        },
        "evidence": {
            "intent": intent,
            "attempt": attempt,
            "write_result": collected["write_result"],
            "state": collected["state"],
            "payload": None,
            "signature": None,
            "public": None,
        },
        "artifacts": {
            "manifest_sha256": sha256_file(manifest),
            "html_sha256": html_hashes,
            "csv_sha256": sha256_file(csv_path),
        },
        "transaction_confirmed": False,
        "automatic_retry": False,
        "next_step_authorized": False,
    }
