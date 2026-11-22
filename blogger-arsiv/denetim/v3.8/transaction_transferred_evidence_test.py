
import hashlib
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from transaction_persistent_outcome import digest
from transaction_confirmation_signature import canonical_bytes, confirmation_payload
from transaction_independent_verifier import inspect_transferred_evidence


class TransferredEvidenceTests(unittest.TestCase):
    def test_missing_evidence(self):
        result = inspect_transferred_evidence({}, "0" * 64)
        self.assertEqual(result["status"], "BLOCKED")

    def test_valid_signature(self):
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        intent = {
            "version": 1,
            "status": "IN_FLIGHT",
            "operation_id": "test-335",
        }
        attempt = {
            "operation_id": "test-335",
            "intent_sha256": digest(intent),
            "expected_state": "PREPARED",
            "target_state": "IN_PROGRESS",
        }
        result = {
            "version": 1,
            "status": "WRITE_RETURNED",
            "step": 1,
            "attempt_sha256": digest(attempt),
            "observed_state": "IN_PROGRESS",
            "transaction_confirmed": False,
            "automatic_retry": False,
        }
        payload = confirmation_payload(
            "test-335", digest(intent), 1,
            digest(attempt), "IN_PROGRESS"
        )
        data = {
            "intent": intent,
            "attempt": attempt,
            "write_result": result,
            "state": "IN_PROGRESS",
            "payload": payload,
            "signature": private.sign(canonical_bytes(payload)).hex(),
            "public": public.hex(),
        }
        checked = inspect_transferred_evidence(
            data, hashlib.sha256(public).hexdigest()
        )
        self.assertEqual(
            checked["status"], "TRANSFERRED_EVIDENCE_REVIEW_REQUIRED"
        )
        self.assertFalse(checked["transaction_confirmed"])
        self.assertFalse(checked["automatic_retry"])

        # Gecerli kanittan turetilen olumsuz senaryolar
        fingerprint = hashlib.sha256(public).hexdigest()
        second_payload = confirmation_payload(
            "test-335", digest(intent), 2,
            digest(attempt), "IN_PROGRESS"
        )
        second_data = dict(
            data,
            payload=second_payload,
            signature=private.sign(
                canonical_bytes(second_payload)
            ).hex(),
        )
        second_check = inspect_transferred_evidence(
            second_data, fingerprint
        )
        self.assertEqual(second_check["status"], "BLOCKED")
        self.assertFalse(second_check["transaction_confirmed"])
        self.assertFalse(second_check["automatic_retry"])

        cases = [
            ("changed_state", dict(data, state="COMPLETED"), fingerprint),
            ("fake_signature", dict(data, signature="00" * 64), fingerprint),
            ("wrong_fingerprint", data, "0" * 64),
        ]
        cases.extend([
            (
                "wrong_expected_state",
                dict(data, attempt=dict(
                    attempt, expected_state="IN_PROGRESS"
                )),
                fingerprint,
            ),
            (
                "wrong_target_state",
                dict(data, attempt=dict(
                    attempt, target_state="RECOVERED"
                )),
                fingerprint,
            ),
        ])
        for name, altered, fp in cases:
            with self.subTest(test_tampered_cases=name):
                outcome = inspect_transferred_evidence(altered, fp)
                self.assertEqual(outcome["status"], "BLOCKED")
                self.assertFalse(outcome["transaction_confirmed"])
                self.assertFalse(outcome["automatic_retry"])


if __name__ == "__main__":
    unittest.main()
