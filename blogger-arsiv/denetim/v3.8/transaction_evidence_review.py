"""V3.8 kanit paketi on incelemesi. Transaction onayi vermez."""

import json
import re
import sys
from pathlib import Path

SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def review(package):
    blocked = {
        "status": "BLOCKED",
        "transaction_confirmed": False,
        "automatic_retry": False,
        "next_step_authorized": False,
    }

    try:
        if not isinstance(package, dict):
            return blocked

        if package["schema_version"] != 1:
            return blocked
        if package["purpose"] != "V38_INDEPENDENT_REVIEW":
            return blocked

        transaction = package["transaction"]
        evidence = package["evidence"]
        artifacts = package["artifacts"]

        if not all(isinstance(x, dict) for x in
                   (transaction, evidence, artifacts)):
            return blocked

        if type(transaction["step"]) is not int or transaction["step"] != 1:
            return blocked

        if transaction["expected_state"] != "PREPARED":
            return blocked
        if transaction["target_state"] != "IN_PROGRESS":
            return blocked

        if not isinstance(transaction["operation_id"], str):
            return blocked
        if not transaction["operation_id"]:
            return blocked

        if any(package[k] is not False for k in (
            "transaction_confirmed",
            "automatic_retry",
            "next_step_authorized",
        )):
            return blocked

        for key in ("manifest_sha256", "csv_sha256"):
            value = artifacts[key]
            if not isinstance(value, str) or not SHA256.fullmatch(value):
                return blocked

        html = artifacts["html_sha256"]
        if not isinstance(html, dict) or not html:
            return blocked
        for name, value in html.items():
            if (
                not isinstance(name, str)
                or not name.endswith(".html")
                or Path(name).name != name
                or not isinstance(value, str)
                or not SHA256.fullmatch(value)
            ):
                return blocked

        if evidence["state"] != "IN_PROGRESS":
            return blocked

        if evidence["intent"]["operation_id"] != transaction["operation_id"]:
            return blocked

        if evidence["attempt"]["operation_id"] != transaction["operation_id"]:
            return blocked

        if evidence["payload"] is not None:
            return blocked
        if evidence["signature"] is not None:
            return blocked
        if evidence["public"] is not None:
            return blocked

        return {
            "status": "PACKAGE_STRUCTURE_REVIEW_REQUIRED",
            "transaction_confirmed": False,
            "automatic_retry": False,
            "next_step_authorized": False,
        }

    except (KeyError, TypeError, ValueError, AttributeError):
        return blocked


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Kullanim: python transaction_evidence_review.py paket.json")

    try:
        package = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        outcome = review(package)
    except (OSError, ValueError):
        outcome = {"status": "BLOCKED"}

    print(json.dumps(outcome, sort_keys=True))
    if outcome["status"] != "PACKAGE_STRUCTURE_REVIEW_REQUIRED":
        raise SystemExit(1)
