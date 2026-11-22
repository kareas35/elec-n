"""V3.8: fail-closed evidence and file-content inspection (no confirmation).

The operator, not the submitted package, selects reference files. Comparing
files controlled by the same executor is NOT independent verification.
"""
import hashlib
import json
from pathlib import Path
from transaction_evidence_review import review
from transaction_persistent_outcome import digest

BLOCKED = {"status": "BLOCKED", "transaction_confirmed": False,
           "automatic_retry": False, "next_step_authorized": False}


def _file_hash(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or unsafe file")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_against_files(package, manifest_path, html_dir, csv_path):
    """Recheck journal relationships and hashes against operator-selected bytes."""
    try:
        if review(package)["status"] != "PACKAGE_STRUCTURE_REVIEW_REQUIRED":
            return dict(BLOCKED)
        tx, evidence, artifacts = (package[k] for k in
                                   ("transaction", "evidence", "artifacts"))
        intent, attempt, result = (evidence[k] for k in
                                   ("intent", "attempt", "write_result"))
        if not all(isinstance(v, dict) for v in (intent, attempt, result)):
            return dict(BLOCKED)
        if intent.get("version") != 1 or intent.get("status") != "IN_FLIGHT":
            return dict(BLOCKED)
        if intent.get("operation_id") != tx["operation_id"]:
            return dict(BLOCKED)
        if attempt.get("operation_id") != tx["operation_id"]:
            return dict(BLOCKED)
        if attempt.get("intent_sha256") != digest(intent):
            return dict(BLOCKED)
        if attempt.get("expected_state") != "PREPARED" or attempt.get("target_state") != "IN_PROGRESS":
            return dict(BLOCKED)
        expected = {"version": 1, "status": "WRITE_RETURNED", "step": 1,
                    "attempt_sha256": digest(attempt), "observed_state": "IN_PROGRESS",
                    "transaction_confirmed": False, "automatic_retry": False}
        if result != expected:
            return dict(BLOCKED)

        manifest_path, html_dir, csv_path = (Path(p) for p in
                                             (manifest_path, html_dir, csv_path))
        if html_dir.is_symlink() or not html_dir.is_dir():
            return dict(BLOCKED)
        if artifacts["manifest_sha256"] != _file_hash(manifest_path):
            return dict(BLOCKED)
        if artifacts["csv_sha256"] != _file_hash(csv_path):
            return dict(BLOCKED)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["entries"]
        if not isinstance(entries, list) or not entries:
            return dict(BLOCKED)
        names = []
        for entry in entries:
            if not isinstance(entry, dict):
                return dict(BLOCKED)
            name = entry.get("name")
            if (not isinstance(name, str) or not name.endswith(".html")
                    or Path(name).name != name or name in (".", "..")):
                return dict(BLOCKED)
            names.append(name)
        if len(names) != len(set(names)) or set(names) != set(artifacts["html_sha256"]):
            return dict(BLOCKED)
        for name in names:
            if artifacts["html_sha256"][name] != _file_hash(html_dir / name):
                return dict(BLOCKED)
        return {"status": "FILES_MATCH_REVIEW_REQUIRED",
                "transaction_confirmed": False, "automatic_retry": False,
                "next_step_authorized": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return dict(BLOCKED)
