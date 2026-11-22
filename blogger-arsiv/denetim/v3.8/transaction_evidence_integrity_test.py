"""Focused regression tests; fixtures stay in TemporaryDirectory."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from transaction_evidence_integrity import inspect_against_files
from transaction_persistent_outcome import digest


def sha(b):
    return hashlib.sha256(b).hexdigest()


class EvidenceIntegrityTests(unittest.TestCase):
    def test_file_and_journal_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            html = root / "html"
            html.mkdir()
            (html / "027.html").write_bytes(b"safe html")
            csv = root / "status.csv"
            csv.write_bytes(b"a,b\n1,2\n")
            manifest = root / "transaction.json"
            manifest.write_text(json.dumps({"entries": [{"name": "027.html"}]}))
            intent = {"version": 1, "status": "IN_FLIGHT", "operation_id": "test"}
            attempt = {"operation_id": "test", "intent_sha256": digest(intent),
                       "expected_state": "PREPARED", "target_state": "IN_PROGRESS"}
            result = {"version": 1, "status": "WRITE_RETURNED", "step": 1,
                      "attempt_sha256": digest(attempt), "observed_state": "IN_PROGRESS",
                      "transaction_confirmed": False, "automatic_retry": False}
            p = {"schema_version": 1, "purpose": "V38_INDEPENDENT_REVIEW",
                 "transaction": {"operation_id": "test", "step": 1,
                                 "expected_state": "PREPARED", "target_state": "IN_PROGRESS"},
                 "evidence": {"intent": intent, "attempt": attempt, "write_result": result,
                              "state": "IN_PROGRESS", "payload": None,
                              "signature": None, "public": None},
                 "artifacts": {"manifest_sha256": sha(manifest.read_bytes()),
                               "html_sha256": {"027.html": sha((html / "027.html").read_bytes())},
                               "csv_sha256": sha(csv.read_bytes())},
                 "transaction_confirmed": False, "automatic_retry": False,
                 "next_step_authorized": False}

            def check(package=p):
                out = inspect_against_files(package, manifest, html, csv)
                self.assertIs(out["transaction_confirmed"], False)
                self.assertIs(out["next_step_authorized"], False)
                return out["status"]

            self.assertEqual(check(), "FILES_MATCH_REVIEW_REQUIRED")
            (html / "027.html").write_bytes(b"tampered")
            self.assertEqual(check(), "BLOCKED")
            (html / "027.html").write_bytes(b"safe html")
            self.assertEqual(check(), "FILES_MATCH_REVIEW_REQUIRED")
            changed = json.loads(json.dumps(p))
            changed["evidence"]["write_result"]["attempt_sha256"] = "0" * 64
            self.assertEqual(check(changed), "BLOCKED")
            changed = json.loads(json.dumps(p))
            changed["transaction"]["step"] = 2
            self.assertEqual(check(changed), "BLOCKED")
            csv.write_bytes(b"changed")
            self.assertEqual(check(), "BLOCKED")

if __name__ == "__main__":
    unittest.main()
